from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
import logging
import uvicorn
import uuid
import time
from contextvars import ContextVar
from log_manager import logger
from routers import convert, ofdtopdf, mdtoword
from config import ServerConfig

# 使用ContextVar存储请求ID
request_id_var = ContextVar("request_id", default=None)


# 添加请求ID过滤器
class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get() or "system"
        return True


logger.addFilter(RequestIDFilter())

# 初始化FastAPI应用
app = FastAPI(docs_url=None, redoc_url=None)

# 添加中间件
app.add_middleware(GZipMiddleware, minimum_size=1024)

# 包含路由
app.include_router(convert.router)
app.include_router(mdtoword.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request_id_var.set(request_id)
    request.state.request_id = request_id
    request.state.start_time = time.time()

    # 请求日志
    logger.info(
        f"Request: method={request.method} path={request.url.path} "
        f"query_params={dict(request.query_params)}"
    )

    response = await call_next(request)
    process_time = (time.time() - request.state.start_time) * 1000

    # 获取响应类型（动态获取）
    response_type = response.headers.get("content-type", "unknown").split(";")[0]

    # 获取文件大小的终极方案
    actual_size = getattr(response, "state", {}).get("actual_size", None)
    if actual_size is None:
        try:
            if hasattr(response, "headers"):
                cl = response.headers.get("content-length")
                actual_size = int(cl) if cl and cl.isdigit() else 0
        except (ValueError, AttributeError):
            actual_size = 0

    # 响应日志（动态类型）
    logger.info(
        f"Response: status_code={response.status_code} "
        f"process_time={process_time:.2f} "
        f"type={response_type} "  # 动态获取类型
        f"size={actual_size}"
    )

    response.headers["X-Request-ID"] = request_id
    return response


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=ServerConfig.PORT,
        workers=ServerConfig.SERVER_WORKERS,
        log_config=None,
        access_log=False,
        server_header=False,
        limit_max_requests=ServerConfig.LIMIT_MAX_REQUESTS,  # 添加 limit_max_requests
        timeout_graceful_shutdown=ServerConfig.TIMEOUT_GRACEFUL_SHUTDOWN,  # 添加 timeout_graceful_shutdown
    )
 