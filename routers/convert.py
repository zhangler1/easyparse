from fastapi import APIRouter, Form, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from utils.common import (
    executor,
    md,
    safe_remove,
    cleanup,
    is_ofd_file,
    save_to_tempfile,
    convert_pdf_to_txt,
    convert_ofd_to_pdf,
    get_file_mimetype,
    _temp_tracker,
)
from log_manager import logger
import os
import tempfile
import asyncio
from typing import Optional
import json
import datetime
import uuid
from config import ConversionConfig
import shutil
from utils.imgParser import ImageParser
from concurrent.futures import ThreadPoolExecutor

router = APIRouter()

img_executor = ThreadPoolExecutor(max_workers=ConversionConfig.IMG_WORKER)

# 初始化图片上传器
image_uploader = ImageParser()


def cleanup_image_output_dir(dir_path: str) -> None:
    """
    删除指定目录（包括所有内容）

    参数:
        dir_path: 要删除的目录路径

    注意:
        - 如果目录不存在，静默跳过
        - 如果删除失败，记录错误日志
        - 不进行任何安全检查，调用者需自行确保安全
    """
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
    except Exception as e:
        logger.error(f"删除目录 {dir_path} 时出错: {e}", exc_info=True)


@router.post("/convert")
async def convert_file(
        request: Request,
        file: UploadFile = File(...),
        imgNum: int = Form(0),
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
    base_name = os.path.splitext(filename)[0]
    upload_path: Optional[str] = None
    result_path: Optional[str] = None

    output_uuid = datetime.datetime.now().strftime("%y%m%d") + str(uuid.uuid4()).replace("-", "")

    try:
        # 获取文件大小
        file_size = None
        if hasattr(file.file, "fileno"):
            try:
                file_size = os.fstat(file.file.fileno()).st_size
            except (OSError, AttributeError):
                pass

        content_type = file.content_type or get_file_mimetype(file.filename)

        logger.info(
            json.dumps(
                {
                    "File info": {
                        "filename": filename,
                        "content_type": content_type,
                        "size": file_size,
                        "imgNum": imgNum,
                    }
                },
                ensure_ascii=False,
            )
        )
        result = {}
        if is_ofd_file(filename):
            upload_path, file_size = await save_to_tempfile(file)
            pdf_bytes = await convert_ofd_to_pdf(upload_path)
            result = await convert_pdf_to_txt(pdf_bytes, ConversionConfig.IMAGE_OUTPUT_DIR, output_uuid)
        else:
            upload_path, _ = await save_to_tempfile(file)
            result = await asyncio.get_running_loop().run_in_executor(
                executor, lambda: md.convert(
                    upload_path,
                    image_output_dir=ConversionConfig.IMAGE_OUTPUT_DIR,
                    output_uuid=output_uuid
                )  # 使用共享线程池
            )

        # 在你的主逻辑中添加清理（例如在 finally 块中）
        try:
            # 创建结果文件
            with tempfile.NamedTemporaryFile(
                    mode='w',
                    suffix='.txt',
                    delete=False,
                    encoding=ConversionConfig.TEMP_FILE_ENCODING
            ) as result_tmp:
                result_path = result_tmp.name
                _temp_tracker.register(result_path)
                result_tmp.write(result.text_content)

                # 处理图片路径上传
                imgs_save_path = [] if getattr(result, 'imgs_save_path', None) is None else result.imgs_save_path
                if imgs_save_path and imgNum > 0:

                    imgs_save_path = list(imgs_save_path) if imgs_save_path else []

                    # 使用线程池批量上传图片
                    upload_results = await asyncio.get_running_loop().run_in_executor(
                        img_executor,
                        lambda: image_uploader.upload_images(imgs_save_path[:imgNum], request_id)
                    )

                    # 将上传结果写入文件（仅记录成功的请求）
                    for res in upload_results:
                        if res.get("success") and res.get("response"):
                            content = ""
                            response = res["response"]
                            # 逐层检查键是否存在并获取值
                            content = response.get("RSP_BODY", {}).get("result", {}).get("choices", [{}])[0].get(
                                "message", {}).get("content", "")
                            img_name = os.path.basename(res['path'])
                            if content:
                                result_tmp.write(f"\n\n\"{img_name}\"图片内容为: {content}\nend")

        finally:
            # 确保无论是否发生异常都会执行清理
            cleanup_image_output_dir(os.path.join(ConversionConfig.IMAGE_OUTPUT_DIR, output_uuid))

        background_tasks.add_task(cleanup, upload_path, result_path)

        return_file_size = 0
        try:
            if os.path.exists(result_path):
                # 存储实际大小，供 server.py 日志中间件使用
                return_file_size = os.path.getsize(result_path)
        except Exception as e:
            pass

        return FileResponse(
            path=result_path,
            filename=f"{base_name}.txt",
            media_type="text/plain",
            headers={"X-Request-ID": request_id, "X-File-Size": str(return_file_size)},
        )

    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}", exc_info=True)
        safe_remove(upload_path)
        safe_remove(result_path)
        raise HTTPException(
            status_code=500,
            detail=f"Conversion failed: {str(e)}",
            headers={"X-Request-ID": request_id},
        )
