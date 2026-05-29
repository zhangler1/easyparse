from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Request, Form
from fastapi.responses import FileResponse
from utils.common import executor, safe_remove, cleanup, save_to_tempfile, _temp_tracker
from log_manager import logger
import os
import tempfile
import asyncio
from typing import Optional
import json
from md2word.markdocx import md2word
import uuid

router = APIRouter()


@router.post("/markdown_to_word")
async def convert_markdown_to_word(
        request: Request,
        file: UploadFile = File(...),
        footer_text: Optional[str] = Form(None),
        footer_enabled: Optional[bool] = Form(None),
        background_tasks: BackgroundTasks = BackgroundTasks(),
):
    request_id = request.state.request_id
    response = None  # 新增：用于标记是否成功返回响应

    if not file.filename:
        logger.error("Empty filename provided")
        raise HTTPException(
            status_code=400,
            detail="Empty filename",
            headers={"X-Request-ID": request_id},
        )

    filename = file.filename
    base_name = os.path.splitext(filename)[0]
    upload_path: Optional[str] = None
    result_path: Optional[str] = None

    try:
        # 保存上传的Markdown文件到临时位置（原逻辑不变）
        upload_path, file_size = await save_to_tempfile(file)
        content_type = file.content_type or "text/markdown"

        logger.info(
            json.dumps(
                {
                    "File info": {
                        "filename": filename,
                        "content_type": content_type,
                        "size": file_size,
                    }
                },
                ensure_ascii=False,
            )
        )

        # 创建临时输出文件路径（原逻辑不变）
        result_path = os.path.join(
            tempfile.gettempdir(), f"docx_{uuid.uuid4().hex}.docx"
        )
        _temp_tracker.register(result_path)

        # 使用共享线程池执行同步转换函数（原逻辑不变）
        await asyncio.get_running_loop().run_in_executor(
            executor,
            lambda: md2word(upload_path, result_path, footer_text=footer_text, footer_enabled=footer_enabled),
        )

        # 检查转换结果（原逻辑不变）
        if not os.path.exists(result_path):
            raise Exception("Word document generation failed")

        return_file_size = 0
        try:
            if os.path.exists(result_path):
                # 存储实际大小，供 server.py 日志中间件使用
                return_file_size = os.path.getsize(result_path)
        except Exception as e:
            pass

        # 返回响应（原逻辑不变）
        response = FileResponse(
            path=result_path,
            filename=f"{base_name}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "X-Request-ID": request_id,
                "Content-Encoding": "identity",
                "X-File-Size": str(return_file_size),
            },
        )
        background_tasks.add_task(cleanup, upload_path, result_path)
        return response

    except asyncio.CancelledError:
        # 新增：捕获客户端断开连接的特殊异常
        logger.warning(f"Client disconnected during conversion (Request ID: {request_id})")
        safe_remove(upload_path)
        safe_remove(result_path)
        raise  # 继续抛出以终止请求

    except Exception as e:
        # 原异常处理逻辑完全保留
        logger.error(f"Conversion failed: {str(e)}", exc_info=True)
        safe_remove(upload_path)
        safe_remove(result_path)
        raise HTTPException(
            status_code=500,
            detail=f"Conversion failed: {str(e)}",
            headers={"X-Request-ID": request_id},
        )

    finally:
        # 新增：双重保障，如果未返回响应则立即清理
        if not response:
            safe_remove(upload_path)
            safe_remove(result_path)
