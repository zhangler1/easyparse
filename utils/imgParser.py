import threading
import time
from typing import List, Dict
import requests
from concurrent.futures import ThreadPoolExecutor
from config import ConversionConfig
import base64
from PIL import Image
import os
import shutil
import json
from log_manager import logger

class ImageParser:
    """图片上传处理类"""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=ConversionConfig.MAX_UPLOAD_WORKERS)

    def send_single_request(self, img_path: str, request_id: str, max_retries: int = 1) -> Dict:
        thread_name = threading.current_thread().name;

        for attempt in range(max_retries):
            try:
                # 过滤30x30像素的图片
                with Image.open(img_path) as img:
                    width, height = img.size
                    if width < 30 or height < 30:
                        logger.info(f"[线程 {thread_name}][{request_id}] 过滤30x30像素图片: {img_path}")
                        return {
                            "path": img_path,
                            "success": False,
                            "error": f"Image too small ({width}x{height} < 30x30)"
                        }

                with open(img_path, "rb") as image_file:
                    base64_image46 = base64.b64encode(image_file.read()).decode('utf-8')
                data = {
                    'REQ_HEAD': {
                        "TRAN_PROCESS": "v1OmniChatCompletions",
                        'TRAN_ID': ''
                    },
                    'REQ_BODY': {
                        'param': {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "image_url",
                                            "image_url": {"url": f"data:image;base64,{base64_image46}"}
                                        },
                                        {
                                            "type": "text",
                                            "text": ConversionConfig.PARSE_IMAGE
                                        }
                                    ]
                                }
                            ],
                            "stream": False,
                            "model": ConversionConfig.IMG_MODEL
                        }
                    }
                }
                headers = {
                    "content-type": "application/x-www-form-urlencoded",
                    "Connection": "keep-alive",
                    "Jumpcloud-ReqSystemCode": ConversionConfig.IMG_ReqSystemCode,
                }

                response = requests.post(
                    ConversionConfig.IMAGE_UPLOAD_URL,
                    data={'REQ_MESSAGE': json.dumps(data)},
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                return {
                    "path": img_path,
                    "success": True,
                    "status_code": response.status_code,
                    "response": response.json()
                }
            except Exception as e:
                if attempt == max_retries - 1:
                    # 新增文件复制逻辑开始
                    try:
                        img_name = os.path.basename(img_path)
                        target_path = os.path.join(ConversionConfig.ERROR_IMG_DIR, img_name)
                        # 确保错误目录存在
                        os.makedirs(ConversionConfig.ERROR_IMG_DIR, exist_ok=True)
                        # 执行文件复制（保留原文件权限）
                        shutil.copy2(img_path, target_path)
                    except Exception as copy_error:
                        logger.info(f"[线程 {thread_name}[{request_id}]] 复制失败文件到错误目录失败: {str(copy_error)}")

                    logger.info(f"[线程 {thread_name}[{request_id}]] 处理图片失败: {img_path}")
                    return {
                        "path": img_path,
                        "success": False,
                        "error": str(e)
                    }
                time.sleep(1 * (attempt + 1))  # 指数退避

    def upload_images(self, imgs_save_path: List[str], request_id: str) -> List[Dict]:
        """使用线程池批量上传图片"""
        if not imgs_save_path:
            return []

        # 记录开始时间
        start_time = time.time()

        # 提交所有上传任务
        futures = [
            self.executor.submit(self.send_single_request, path, request_id)
            for path in imgs_save_path
        ]

        # 获取所有结果
        results = [future.result() for future in futures]

        # 统计结果
        success_count = sum(1 for r in results if r["success"])
        duration = time.time() - start_time

        logger.info(
            f"[{request_id}] 图片解析完成: 成功 {success_count}/{len(imgs_save_path)}, "
            f"耗时 {duration:.2f}秒"
        )

        return results

    def __del__(self):
        """清理线程池"""
        self.executor.shutdown(wait=True)


if __name__ == '__main__':

    # 测试图片路径列表 (替换为你实际要测试的图片路径)
    test_images = [
        "D:/software/assert/avatar.jpg",
    ]

    # 创建解析器实例
    parser = ImageParser()  # 注意：类名有拼写错误，建议改为 ImageParser

    # 执行批量上传测试
    print("开始测试图片上传...")
    results = parser.upload_images(test_images)

    # 打印结果
    print("\n测试结果:")
    for result in results:
        if result['success']:
            print(result["response"]['RSP_BODY']['result']['choices'][0]['message']['content'])
        else:
            print(f"失败: {result['path']} - 错误: {result['error']}")

    print("测试完成")