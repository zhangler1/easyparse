from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from utils.common import (
    safe_remove,
    cleanup,
    is_ofd_file,
    save_to_tempfile,
    convert_ofd_to_pdf,
    get_file_mimetype,
    _temp_tracker,
)
from log_manager import logger
import os
import tempfile
from typing import Optional
import json

router = APIRouter()


@router.post("/ofd_to_pdf")
async def convert_ofd_to_pdf(
    request: Request,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    request_id = request.state.request_id

    if not file.filename:
        logger.error("Empty filename provided")
        raise HTTPException(
            status_code=400,
            detail="Empty filename",
            headers={"X-Request-ID": request_id},
        )

    filename = file.filename

    if not is_ofd_file(filename):
        logger.error(f"Unsupported file format: {filename}")
        raise HTTPException(
            status_code=400,
            detail="Only OFD files are supported",
            headers={"X-Request-ID": request_id},
        )

    base_name = os.path.splitext(filename)[0]
    upload_path: Optional[str] = None
    result_path: Optional[str] = None

    try:
        upload_path, file_size = await save_to_tempfile(file)
        content_type = file.content_type or get_file_mimetype(file.filename)

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
        pdf_bytes = await convert_ofd_to_pdf(upload_path)

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as tmp:
            result_path = tmp.name
            _temp_tracker.register(result_path)
            tmp.write(pdf_bytes)
            result_size = os.path.getsize(result_path)

        logger.info(
            f"PDFConversion: original_size={file_size} converted_size={result_size}"
        )

        return_file_size = 0
        try:
            if os.path.exists(result_path):
                # 存储实际大小，供 server.py 日志中间件使用
                return_file_size = os.path.getsize(result_path)
        except Exception as e:
            pass

        response = FileResponse(
            path=result_path,
            filename=f"{base_name}.pdf",
            media_type="application/pdf",
            headers={
                "X-Request-ID": request_id,
                "Content-Encoding": "identity",
                "X-File-Size": str(return_file_size),
            },
        )

        background_tasks.add_task(cleanup, upload_path, result_path)
        return response

    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}", exc_info=True)
        safe_remove(upload_path)
        safe_remove(result_path)
        raise HTTPException(
            status_code=500,
            detail=f"Conversion failed: {str(e)}",
            headers={"X-Request-ID": request_id},
        )
