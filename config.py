from typing import Final
import logging
import os


class ServerConfig:
    PORT: Final[int] = int(os.getenv("PORT", 5000))
    SERVER_WORKERS: Final[int] = int(os.getenv("SERVER_WORKERS", 4))
    LIMIT_MAX_REQUESTS: Final[int] = int(os.getenv("LIMIT_MAX_REQUESTS", 100))
    TIMEOUT_GRACEFUL_SHUTDOWN: Final[int] = int(os.getenv("TIMEOUT_GRACEFUL_SHUTDOWN", 30))


class ConversionConfig:
    """文件转换相关配置"""

    # 线程池配置
    """最大线程池工作线程数"""
    MD_WORKER: Final[int] = int(os.getenv("MD_WORKER", 4))  # md转化线程池大小
    IMG_WORKER: Final[int] = int(os.getenv("IMG_WORKER", 4))  # 图片识别线程池大小

    # 文件分块配置
    """文件分块大小(字节)"""
    CHUNK_SIZE: Final[int] = 8192 * 4  # 32KB
    TEMP_FILE_ENCODING: Final[str] = 'utf-8'

    # 图片上传配置
    IMAGE_UPLOAD_URL: Final[str] = os.getenv("IMAGE_UPLOAD_URL", "")
    IMG_MODEL: Final[str] = "qwen2half-vl-72b-instruct-awq";
    IMG_ReqSystemCode: Final[str] = "JXWDWD";
    MAX_UPLOAD_WORKERS: Final[int] = int(os.getenv("MAX_UPLOAD_WORKERS", 2))  # 图片上传线程池大小
    IMAGE_OUTPUT_DIR: Final[str] = os.getenv("IMAGE_OUTPUT_DIR", "/tmp/shared_all/assert")
    ERROR_IMG_DIR: Final[str] = os.getenv("ERROR_IMG_DIR", "/tmp/shared_all/error")

    # 文件处理配置
    PARSE_IMAGE = "你是一个图片识别模型，请识别图中的文字"


class LoggingConfig:
    """日志系统配置常量类

    该类包含日志系统所有相关配置参数，使用Final类型确保配置不会被意外修改。
    所有路径配置建议使用绝对路径，确保在不同工作目录下都能正确定位文件。
    """

    # 日志目录配置
    """日志文件存储目录，所有日志文件将保存在此目录下"""
    LOG_DIR: Final[str] = os.getenv("LOG_DIR", "/tmp/shared_all/logs")

    """文件锁目录，用于存放日志清理时的锁文件，防止多进程同时清理"""
    LOCK_DIR: Final[str] = os.getenv("LOCK_DIR", "/tmp/shared_all/logs")

    # 日志文件配置
    """日志文件前缀，生成的文件名格式为：前缀-YYYY-MM-DD.log"""
    LOG_PREFIX: Final[str] = os.getenv("LOG_PREFIX", "markitdown")

    """日志保留天数，超过此天数的日志文件将被自动清理"""
    LOG_RETENTION_DAYS: Final[int] = int(os.getenv("LOG_RETENTION_DAYS", 7))

    """每天执行日志清理的小时时间(24小时制)"""
    LOG_CLEANUP_HOUR: Final[int] = int(os.getenv("LOG_CLEANUP_HOUR", 1))

    """每天执行日志清理的分钟时间"""
    LOG_CLEANUP_MINUTE: Final[int] = int(os.getenv("LOG_CLEANUP_MINUTE", 10))

    """日志清理的最小间隔时间(小时)，防止短时间内重复清理"""
    LOG_CLEANUP_INTERVAL_HOURS: Final[int] = int(os.getenv("LOG_CLEANUP_INTERVAL_HOURS", 23))

    # 日志级别配置
    """默认日志级别，可选值：
    - logging.DEBUG: 最详细的日志信息，用于调试
    - logging.INFO: 常规操作日志（默认值）
    - logging.WARNING: 警告信息
    - logging.ERROR: 错误信息
    - logging.CRITICAL: 严重错误
    """
    LOG_LEVEL: Final[int] = logging.INFO

    # 是否启用各类日志
    """是否启用文件日志记录，True表示将日志写入文件"""
    ENABLE_FILE_LOG: Final[bool] = True

    """是否启用控制台日志输出，True表示在控制台打印日志"""
    ENABLE_CONSOLE_LOG: Final[bool] = True
