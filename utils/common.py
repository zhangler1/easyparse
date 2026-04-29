import os
import tempfile
import time
import asyncio
import base64
import atexit
import threading
from typing import Tuple, Any
from concurrent.futures import ThreadPoolExecutor
from easyofd.ofd import OFD
from fastapi import UploadFile
from markitdown import MarkItDown
import mimetypes
from config import ConversionConfig

# 初始化共享线程池
executor = ThreadPoolExecutor(max_workers=ConversionConfig.MD_WORKER)

# 初始化MarkItDown转换器
md = MarkItDown(enable_plugins=False)

# 分块大小
CHUNK_SIZE = ConversionConfig.CHUNK_SIZE  # 32KB chunks


# ── 临时文件追踪器 ──────────────────────────────────────────────
class TempFileTracker:
    """
    全局临时文件追踪器，解决进程崩溃时 BackgroundTasks 不执行导致文件泄漏的问题。

    三层防护：
      1. 正常流程：BackgroundTasks 在响应后异步清理
      2. atexit 兜底：进程正常退出时清理所有追踪中的文件
      3. 启动扫描：清理上次崩溃遗留的过期临时文件
    """

    # 临时文件前缀，用于启动时扫描识别本项目产生的临时文件
    PREFIX = ("tmp",)  # tempfile.NamedTemporaryFile 默认前缀
    # 文件最大保留时间（秒），超过此时间的视为残留文件
    MAX_AGE_SECONDS = 3600  # 1小时

    def __init__(self):
        self._paths: set = set()
        self._lock = threading.Lock()

    def register(self, *paths: str) -> None:
        """注册临时文件路径"""
        with self._lock:
            for p in paths:
                if p:
                    self._paths.add(p)

    def unregister(self, *paths: str) -> None:
        """取消注册（文件已被清理）"""
        with self._lock:
            for p in paths:
                self._paths.discard(p)

    def cleanup_all(self) -> int:
        """清理所有追踪中的临时文件，返回清理数量"""
        with self._lock:
            paths = self._paths.copy()
            self._paths.clear()
        count = 0
        for p in paths:
            if safe_remove(p):
                count += 1
        return count

    def cleanup_stale_files(self) -> int:
        """
        扫描 /tmp 目录，清理本项目产生的过期临时文件。
        识别规则：文件名匹配 tempfile 默认前缀 + 创建时间超过 MAX_AGE_SECONDS。
        """
        count = 0
        now = time.time()
        tmp_dir = tempfile.gettempdir()
        try:
            for entry in os.scandir(tmp_dir):
                if not entry.is_file():
                    continue
                # 只清理以 'tmp' 开头且带有本项目常用后缀的文件
                name = entry.name.lower()
                if not name.startswith("tmp"):
                    continue
                if not any(name.endswith(ext) for ext in (".pdf", ".ofd", ".txt", ".docx", ".md")):
                    continue
                try:
                    if now - entry.stat().st_mtime > self.MAX_AGE_SECONDS:
                        os.unlink(entry.path)
                        count += 1
                except (OSError, PermissionError):
                    pass
        except (OSError, PermissionError):
            pass
        return count


# 全局单例
_temp_tracker = TempFileTracker()

# atexit 兜底：进程退出时自动清理追踪中的临时文件
atexit.register(_temp_tracker.cleanup_all)

# 启动时扫描清理上次崩溃遗留的过期临时文件
_temp_tracker.cleanup_stale_files()


def safe_remove(filepath: str, max_retries: int = 3, delay: float = 0.1) -> bool:
    """安全删除文件"""
    for _ in range(max_retries):
        try:
            if filepath and os.path.exists(filepath):
                os.unlink(filepath)
                return True
        except PermissionError:
            time.sleep(delay)
    return False


def cleanup(*filepaths: str):
    """清理多个临时文件，并从追踪器中移除"""
    for path in filepaths:
        if safe_remove(path):
            _temp_tracker.unregister(path)


def is_ofd_file(filename: str) -> bool:
    """检查文件是否是OFD格式"""
    return filename.lower().endswith(".ofd")


def process_ofd_conversion(ofdb64: str) -> bytes:
    """处理OFD转换的核心逻辑"""
    ofd = OFD()
    try:
        ofd.read(ofdb64, save_xml=False)
        return ofd.to_pdf()
    finally:
        ofd.del_data()


async def save_to_tempfile(file: UploadFile) -> Tuple[str, int]:
    """
    将上传文件分块保存到临时文件，并保留原始文件扩展名
    返回 (temp_path: str, file_size: int)
    """
    temp_path = None
    file_size = 0

    # 获取原始文件名并提取扩展名
    original_filename = file.filename or "unknown"
    _, ext = os.path.splitext(original_filename)

    try:
        # 添加 suffix 以保留原文件扩展名
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            temp_path = tmp.name
            while chunk := await file.read(CHUNK_SIZE):
                tmp.write(chunk)
                file_size += len(chunk)
        # 注册到追踪器，防止崩溃时泄漏
        _temp_tracker.register(temp_path)
        return temp_path, file_size
    except Exception as e:
        if temp_path:
            safe_remove(temp_path)
        raise e


async def convert_pdf_to_txt(pdf_bytes: bytes, image_output_dir: str, output_uuid: str) -> Any:
    """将PDF字节流转换为文本"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_tmp:
        pdf_path = pdf_tmp.name
        pdf_tmp.write(pdf_bytes)

    # 注册到追踪器
    _temp_tracker.register(pdf_path)

    try:
        result = await asyncio.get_running_loop().run_in_executor(
            executor, lambda: md.convert(pdf_path,
                                         image_output_dir=image_output_dir,
                                         output_uuid=output_uuid)  # 使用共享线程池
        )
        return result
    finally:
        safe_remove(pdf_path)


async def convert_ofd_to_pdf(upload_path: str) -> bytes:
    """将OFD文件转换为PDF"""
    with open(upload_path, "rb") as f:
        ofdb64 = base64.b64encode(f.read()).decode("utf-8")

    loop = asyncio.get_running_loop()
    pdf_bytes = await loop.run_in_executor(executor, lambda: process_ofd_conversion(ofdb64))
    # 主动释放 base64 字符串（避免等到函数栈帧回收）
    del ofdb64
    return pdf_bytes


def get_file_mimetype(filename: str, fallback: str = "application/octet-stream") -> str:
    """根据文件后缀名智能推断MIME类型"""
    # 注册OFD等特殊类型的MIME（如果标准库没有收录）
    mimetypes.add_type("application/ofd", ".ofd")

    # 获取文件扩展名
    ext = os.path.splitext(filename)[1].lower() if filename else ""

    # 优先使用标准库推断，失败则返回fallback
    return mimetypes.guess_type(filename)[0] or fallback
