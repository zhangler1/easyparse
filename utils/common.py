import os
import tempfile
import time
import asyncio
import base64
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
    """清理多个临时文件"""
    for path in filepaths:
        safe_remove(path)


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

    try:
        result = await asyncio.get_event_loop().run_in_executor(
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

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: process_ofd_conversion(ofdb64))


def get_file_mimetype(filename: str, fallback: str = "application/octet-stream") -> str:
    """根据文件后缀名智能推断MIME类型"""
    # 注册OFD等特殊类型的MIME（如果标准库没有收录）
    mimetypes.add_type("application/ofd", ".ofd")

    # 获取文件扩展名
    ext = os.path.splitext(filename)[1].lower() if filename else ""

    # 优先使用标准库推断，失败则返回fallback
    return mimetypes.guess_type(filename)[0] or fallback
