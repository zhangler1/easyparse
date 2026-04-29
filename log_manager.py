import os
import logging
import multiprocessing
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from datetime import datetime, timedelta
from logging.handlers import QueueHandler, QueueListener
import glob
import threading
import json
import fcntl
import atexit
from typing import Dict, Any
from config import LoggingConfig

# 多进程安全的日志队列
log_queue = multiprocessing.Queue(-1)


class FileLock:
    """文件锁实现，确保在任何情况下都能正确释放文件锁"""

    def __init__(self, lock_file_path):
        self.lock_file_path = lock_file_path
        self.lock_file = None
        self._is_locked = False  # 跟踪锁状态

    def __enter__(self):
        """获取文件锁（目录创建和锁获取分开处理）"""
        # 1. 先确保目录存在（单独 try-catch）
        try:
            os.makedirs(os.path.dirname(self.lock_file_path), exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"创建锁文件目录失败: {str(e)}")

        # 2. 再获取文件锁（单独 try-catch）
        try:
            self.lock_file = open(self.lock_file_path, "w")
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._is_locked = True
            return self
        except BlockingIOError:
            self.lock_file.close()
            raise RuntimeError("无法获取文件锁，可能其他进程正在执行清理")
        except Exception as e:
            if self.lock_file:
                self.lock_file.close()
            raise RuntimeError(f"获取文件锁失败: {str(e)}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """释放文件锁并清理文件"""
        if not self._is_locked:
            return

        try:
            # 先释放文件锁
            fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            self._is_locked = False

            # 然后关闭文件
            if self.lock_file:
                self.lock_file.close()

            # 最后删除锁文件
            try:
                if os.path.exists(self.lock_file_path):
                    os.unlink(self.lock_file_path)
            except OSError:
                pass

        except Exception as e:
            # 即使释放失败也尝试关闭文件
            if self.lock_file:
                try:
                    self.lock_file.close()
                except:
                    pass
            raise RuntimeError(f"释放文件锁失败: {str(e)}")

    def __del__(self):
        """对象销毁时确保释放锁"""
        if hasattr(self, "_is_locked") and self._is_locked:
            self.__exit__(None, None, None)


class DatedFileHandler(logging.FileHandler):
    """每日滚动的日志文件处理器"""

    def __init__(self, filename: str, prefix: str = "app", **kwargs):
        self.tz = pytz.timezone("Asia/Shanghai")
        self.prefix = prefix
        self.base_filename = filename  # 原始基础文件名
        self.current_date = self._get_current_date()

        # 关键修改：初始化时直接设置baseFilename为动态文件名
        self.baseFilename = self._get_dated_filename()

        os.makedirs(os.path.dirname(self.baseFilename), exist_ok=True)
        super().__init__(self.baseFilename, **kwargs)

        # 使用独立的logger记录滚动日志
        self._rollover_logger = logging.getLogger(f"{prefix}.rollover")
        self._rollover_logger.propagate = False
        if not self._rollover_logger.handlers:
            self._rollover_logger.addHandler(logging.NullHandler())

    def _get_current_date(self) -> str:
        """获取当前日期(上海时区)"""
        return datetime.now(self.tz).date()

    def _get_dated_filename(self) -> str:
        """生成带日期的文件名"""
        date_str = self.current_date.strftime("%Y-%m-%d")
        return os.path.join(
            os.path.dirname(self.base_filename),
            f"{self.prefix}-{date_str}.log",
        )

    def _check_and_rollover(self):
        """检查并执行日志滚动（使用文件锁确保多进程安全）"""
        new_date = self._get_current_date()
        if new_date != self.current_date:
            # 确保 LOCK_DIR 存在，不存在则创建
            os.makedirs(LoggingConfig.LOCK_DIR, exist_ok=True)

            # 使用 LoggingConfig.LOCK_DIR 存放锁文件
            lock_file = os.path.join(
                LoggingConfig.LOCK_DIR,  # 使用统一的锁目录
                f"{self.prefix}.rollock",  # 锁文件名
            )
            old_filename = self.baseFilename
            try:
                with FileLock(lock_file):
                    # 再次检查日期（获取锁后可能已经滚动过了）
                    if new_date != self.current_date:
                        print(f"正在执行日志滚动: {self.current_date} -> {new_date}")

                        # 1. 关闭当前文件流
                        if self.stream:
                            self.stream.flush()
                            self.close()

                        # 2. 更新日期和文件名
                        old_filename = self.baseFilename
                        self.current_date = new_date
                        self.baseFilename = self._get_dated_filename()

                        # 3. 确保目录存在
                        os.makedirs(os.path.dirname(self.baseFilename), exist_ok=True)

                        # 4. 重新打开文件（会使用新的baseFilename）
                        self.stream = self._open()
                        print(f"新日志文件: {self.stream.name}")

                        # 记录滚动事件
                        self._rollover_logger.info(
                            f"日志已滚动到: {os.path.basename(self.baseFilename)}",
                            extra={"request_id": "LOGROTATE"},
                        )
            except Exception as e:
                print(f"日志滚动失败: {str(e)}")
                # 失败时恢复旧文件
                try:
                    self.baseFilename = old_filename
                    self.stream = self._open()
                except Exception as e:
                    pass


    def emit(self, record):
        """重写emit方法，确保每次写入前都检查日期"""
        self._check_and_rollover()
        super().emit(record)


class ConciseFormatter(logging.Formatter):
    """中国时区+自动转换单位的格式化器"""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s - [%(request_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.tz = pytz.timezone("Asia/Shanghai")

    def formatTime(self, record, datefmt=None) -> str:
        ct = datetime.fromtimestamp(record.created, self.tz)
        return ct.strftime(datefmt) if datefmt else ct.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _convert_size(size) -> str:
        """将字节大小转为人类可读格式"""
        try:
            size = int(float(size))
            for unit in ["B", "KB", "MB", "GB"]:
                if size < 1024 or unit == "GB":
                    return f"{size:.1f}{unit}"
                size /= 1024
        except (ValueError, TypeError):
            return "0B"

    def _parse_log_parts(self, msg: str) -> Dict[str, Any]:
        """安全解析日志消息各部分"""
        try:
            if msg.startswith("{"):
                return json.loads(msg)
            return {p.split("=")[0]: p.split("=")[1] for p in msg.split() if "=" in p}
        except Exception:
            return {}

    def format(self, record) -> str:
        record.asctime = self.formatTime(record)
        record.request_id = getattr(record, "request_id", "SYSTEM")
        msg = record.getMessage()
        parts = self._parse_log_parts(msg)

        # 请求日志
        if "Request:" in msg:
            return (
                f"{record.asctime} - [{record.request_id}] - "
                f"请求 {parts.get('method')} {parts.get('path')}"
            )

        # 文件信息日志
        elif "File info" in parts:
            file_info = parts["File info"]
            return (
                f"{record.asctime} - [{record.request_id}] - "
                f"请求文件 {file_info.get('filename')} "
                f"类型:{file_info.get('content_type', '').split('/')[-1]} "
                f"大小:{self._convert_size(file_info.get('size', 0))} "
                f"解析图片数量参数为:{file_info.get('imgNum')}"
            )

        # 响应日志
        elif "Response:" in msg:
            return (
                f"{record.asctime} - [{record.request_id}] - "
                f"响应 状态码:{parts.get('status_code')} "
                f"耗时:{parts.get('process_time').replace('ms', '')}ms "
                f"类型:{parts.get('type', 'unknown').split(';')[0]} "
                f"大小:{self._convert_size(parts.get('size', 0))}"
            )

        # PDF转换日志
        elif "PDFConversion:" in msg:
            return (
                f"{record.asctime} - [{record.request_id}] - "
                f"PDF转换 原始大小:{self._convert_size(parts.get('original_size', 0))} "
                f"转换后大小:{self._convert_size(parts.get('converted_size', 0))}"
            )

        return super().format(record)


class LogCleanupScheduler:
    """定时日志清理调度器"""

    def __init__(
        self,
        log_dir: str,
        retention_days: int,
        prefix: str,
        cleanup_hour: int = 3,
        cleanup_minute: int = 0,
        lock_dir: str = None,
        cleanup_interval_hours: int = 12,
    ):
        self.log_dir = log_dir
        self.retention_days = retention_days
        self.prefix = prefix
        self.cleanup_hour = cleanup_hour
        self.cleanup_minute = cleanup_minute
        self.lock_dir = lock_dir if lock_dir else log_dir
        self.cleanup_interval_hours = cleanup_interval_hours
        self.lock_file = os.path.join(self.lock_dir, f"{prefix}-cleanup.lock")
        self.scheduler = None
        self.logger = logging.getLogger(__name__)

    def _should_clean(self) -> bool:
        """检查是否需要执行清理"""
        try:
            last_clean = datetime.fromtimestamp(os.path.getmtime(self.lock_file))
            return (datetime.now() - last_clean) > timedelta(
                hours=self.cleanup_interval_hours
            )
        except FileNotFoundError:
            return True

    def _clean_logs(self):
        """执行日志清理"""
        try:
            with FileLock(self.lock_file + ".lock"):
                if not self._should_clean():
                    self.logger.info("跳过清理 - 最近已清理过")
                    return

                self._perform_actual_cleanup()

                # 更新最后清理时间
                with open(self.lock_file, "a"):
                    os.utime(self.lock_file, None)
                self.logger.info("日志清理完成")
        except RuntimeError as e:
            self.logger.info(f"跳过清理: {str(e)}")
        except Exception as e:
            self.logger.error(f"清理过程中发生错误: {str(e)}", exc_info=True)

    def _perform_actual_cleanup(self):
        """实际的清理操作"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        self.logger.info(f"开始日志清理(保留最近{self.retention_days}天)")

        deleted = []
        for log_file in glob.glob(os.path.join(self.log_dir, f"{self.prefix}-*.log")):
            try:
                date_str = os.path.basename(log_file)[len(self.prefix) + 1 : -4]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    self._safe_remove(log_file)
                    deleted.append(log_file)
            except Exception as e:
                self.logger.warning(f"跳过文件 {log_file}: {str(e)}")

        if deleted:
            self.logger.info(f"已删除{len(deleted)}个旧日志文件")
        else:
            self.logger.info("没有需要删除的旧日志")

    def _safe_remove(self, path: str):
        """安全删除文件"""
        try:
            size = os.path.getsize(path)
            self.logger.info(f"正在删除文件: {path} (大小: {size}字节)")
            os.remove(path)
            self.logger.info(f"成功删除文件: {path}")
        except Exception as e:
            self.logger.error(f"删除文件失败 {path}: {str(e)}")
            raise

    def start(self):
        """启动定时清理"""
        if self.scheduler is not None:
            return

        if not os.environ.get("WORKER_CLASS"):
            self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

            self.scheduler.add_job(
                self._clean_logs,
                "cron",
                hour=self.cleanup_hour,
                minute=self.cleanup_minute,
                misfire_grace_time=3600,
                coalesce=True,
            )
            self.scheduler.start()

            # 注册退出处理
            atexit.register(self.shutdown)

            # 立即执行一次
            threading.Thread(target=self._clean_logs, daemon=True).start()
            self.logger.info("已启动定时日志清理服务")

    def shutdown(self):
        """停止清理服务"""
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            self.logger.info("已停止日志清理服务")


class AppLogger:
    """线程安全的单例日志管理器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(
        self,
        log_dir: str = "logs",
        retention_days: int = 7,
        prefix: str = "app",
        enable_file_log: bool = True,
        enable_console_log: bool = True,
        log_level: int = logging.INFO,
        cleanup_hour: int = 3,
        cleanup_minute: int = 0,
        lock_dir: str = None,
        cleanup_interval_hours: int = 12,
    ) -> logging.Logger:
        """初始化日志系统"""
        with self._lock:
            if hasattr(self, "_logger"):
                return self._logger

            # 创建日志目录
            os.makedirs(log_dir, exist_ok=True)

            # 初始化格式化器
            formatter = ConciseFormatter()

            # 处理器列表
            handlers = []

            # 控制台日志
            if enable_console_log:
                ch = logging.StreamHandler()
                ch.setFormatter(formatter)
                handlers.append(ch)

            # 文件日志（仅主进程）
            if enable_file_log and not os.environ.get("WORKER_CLASS"):
                file_handler = DatedFileHandler(
                    os.path.join(log_dir, f"{prefix}.log"),
                    prefix=prefix,
                    encoding="utf-8",
                )
                file_handler.setFormatter(formatter)
                handlers.append(file_handler)

                # 启动带文件锁的日志清理
                self.cleaner = LogCleanupScheduler(
                    log_dir=log_dir,
                    retention_days=retention_days,
                    prefix=prefix,
                    cleanup_hour=cleanup_hour,
                    cleanup_minute=cleanup_minute,
                    lock_dir=lock_dir,
                    cleanup_interval_hours=cleanup_interval_hours,
                )
                self.cleaner.start()

            # 初始化根日志记录器
            logger = logging.getLogger()
            logger.setLevel(log_level)

            # 添加队列处理器（多进程安全）
            queue_handler = QueueHandler(log_queue)
            logger.addHandler(queue_handler)

            # 启动队列监听器（主进程独占）
            if handlers and not os.environ.get("WORKER_CLASS"):
                self._listener = QueueListener(log_queue, *handlers)
                self._listener.start()

            # 配置UVicorn日志
            for name, level in {
                "uvicorn": logging.INFO,
                "uvicorn.error": logging.INFO,
                "uvicorn.access": logging.CRITICAL,
            }.items():
                logging.getLogger(name).setLevel(level)

            self._logger = logger
            return logger


# 全局单例日志实例
# 初始化应用日志记录器
# 参数说明：
#   log_dir: 日志目录，默认为"/var/logs"
#   retention_days: 日志保留天数，默认为7
#   prefix: 日志文件前缀，默认为"markitdown"
#   enable_file_log: 是否启用文件日志，默认为True
#   enable_console_log: 是否启用控制台日志，默认为True
#   log_level: 日志级别，默认为logging.INFO
#   cleanup_hour: 每天清理时间(小时)，默认为11
#   cleanup_minute: 每天清理时间(分钟)，默认为9
#   lock_dir: 锁文件存放目录，默认为"/var/lock"
#   cleanup_interval_hours: 清理间隔小时数(确保多进程不会重复执行清理)，默认为23
logger = AppLogger().initialize(
    log_dir=LoggingConfig.LOG_DIR,
    retention_days=LoggingConfig.LOG_RETENTION_DAYS,
    prefix=LoggingConfig.LOG_PREFIX,
    enable_file_log=LoggingConfig.ENABLE_FILE_LOG,
    enable_console_log=LoggingConfig.ENABLE_CONSOLE_LOG,
    log_level=LoggingConfig.LOG_LEVEL,
    cleanup_hour=LoggingConfig.LOG_CLEANUP_HOUR,
    cleanup_minute=LoggingConfig.LOG_CLEANUP_MINUTE,
    lock_dir=LoggingConfig.LOCK_DIR,
    cleanup_interval_hours=LoggingConfig.LOG_CLEANUP_INTERVAL_HOURS,
)
