import logging
import os
import re
import requests
import uuid
import time
import random
import asyncio
import subprocess
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from concurrent.futures import ThreadPoolExecutor
from telegram.error import TimedOut, NetworkError
import backoff  # 需要安装: pip install backoff
import threading
import json

import ssl
import httpx
from telegram.request import HTTPXRequest
import socket

# Load environment variables and set up logging
load_dotenv()
TOKEN = os.getenv('TOKEN')
DOWNLOAD_DIR = "download"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
COBALT_API_URL = os.getenv('COBALT_API_URL', "http://cvatserver.me:9999/")  # Default to your address, if not provided in .env

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables
# driver = None (no longer needed)

# 添加全局线程池配置
MAX_WORKERS = 3  # 最大工作线程数
download_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
active_downloads = {}  # 用于追踪活跃下载任务
download_lock = threading.Lock()  # 用于同步访问 active_downloads

def is_url(text):
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return bool(url_pattern.match(text))

# def get_url_type(url):
#     if 'instagram.com' in url:
#         return 'instagram'
#     elif 'twitter.com' in url or 'x.com' in url:
#         return 'twitter'
#     elif 'youtube.com' in url or 'youtu.be' in url:
#         return 'youtube'
#     elif 'tiktok.com' in url or 'vt.tiktok.com' in url or 'vm.tiktok.com' in url:
#         return 'tiktok'
#     else:
#         return 'unknown'
# removed link type detection since all downloads will go through cobalt api.

async def fetch_video_with_cobalt(url):
    """Fetches a video using the Cobalt API."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    data = {"url": url}

    try:
        response = requests.post(COBALT_API_URL, headers=headers, json=data)
        response.raise_for_status()  # Raises an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"请求 Cobalt API 失败: {e}")
        return None

async def download_video_from_url(url, user_cache_dir):
    """下载视频从链接"""
    try:
        response = await fetch_video_with_cobalt(url)
        if not response or 'url' not in response:
            logger.error("没有返回有效的下载链接 from cobalt api")
            return None

        download_url = response['url']
        file_uuid = str(uuid.uuid4())
        video_path = os.path.join(user_cache_dir, f"{file_uuid}.mp4")
        logger.info(f"开始下载视频，下载链接为: {download_url}")

        # Download the video
        with requests.get(download_url, stream=True, timeout=30) as r:
            r.raise_for_status()  # Raise an exception for bad status codes
            with open(video_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        logger.info(f"下载成功到: {video_path}")
        return video_path

    except Exception as e:
        logger.exception(f"下载视频失败: {e}")
        return None


async def download_video_task(url,  update: Update, context: ContextTypes.DEFAULT_TYPE, status_message, max_retries=3):
    user_id = update.effective_user.id
    user_cache_dir = os.path.join(DOWNLOAD_DIR, str(user_id))
    os.makedirs(user_cache_dir, exist_ok=True)

    for attempt in range(max_retries):
        try:
            logger.info(f"Starting download attempt {attempt + 1} for URL: {url}")
            video_file = await download_video_from_url(url, user_cache_dir)


            if not video_file:
                raise FileNotFoundError("Video file not found after download")

            unique_id = str(uuid.uuid4())
            new_video_file = os.path.join(DOWNLOAD_DIR, f"{unique_id}_{os.path.basename(video_file)}")
            os.rename(video_file, new_video_file)

            logger.info(f"Download completed successfully: {new_video_file}")
            return new_video_file

        except Exception as e:
            logger.error(f"Download attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(5)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Welcome! Send me a video link to download.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    start_time = time.time()
    user = update.effective_user
    message_text = update.message.text
    status_message = None

    # 检查用户是否可以开始新的下载
    if not await manage_download_tasks(user.id):
        await update.message.reply_text(
            "您当前有太多正在进行的下载。请等待当前下载完成后再试。"
        )
        return

    try:
        logger.info(f"Received message from user {user.id} ({user.username}): {message_text}")

        if not is_url(message_text):
            with download_lock:
                active_downloads[user.id] -= 1
            await update.message.reply_text("Please send a valid video link.")
            return

        # url_type = get_url_type(message_text)
        # if url_type == 'unknown':
        #     with download_lock:
        #         active_downloads[user.id] -= 1
        #     await update.message.reply_text("Unsupported URL type. Please send a YouTube, Twitter, or Instagram URL.")
        #     return

        status_message = await update.message.reply_text("Starting download. Please wait...")
        
        try:
            # 使用线程池执行下载任务
            download_start = time.time()
            loop = asyncio.get_event_loop()
            video_file = await loop.run_in_executor(
                download_executor,
                lambda: asyncio.run(download_video_task(
                    message_text, update, context, status_message
                ))
            )
            download_end = time.time()
            download_duration = download_end - download_start

            if not video_file:
                raise Exception("Download failed")

            # 记录发送开始时间
            send_start = time.time()
            await update_status_message(status_message, "正在发送视频...")
            await send_video_with_retry(update.message, video_file)
            send_end = time.time()
            send_duration = send_end - send_start
            
            # 计算总耗时
            total_time = time.time() - start_time
            
            # 发送完成状态消息，包含时间统计
            await status_message.edit_text(
                f"下载完成并已发送文件！\n"
                f"总耗时: {total_time:.2f}秒\n"
                f"下载耗时: {download_duration:.2f}秒\n"
                f"发送耗时: {send_duration:.2f}秒"
            )
            
            # 记录详细日志
            logger.info(
                f"处理完成 - URL类型: all via cobalt \n"
                f"总耗时: {total_time:.2f}秒\n"
                f"下载耗时: {download_duration:.2f}秒\n"
                f"发送耗时: {send_duration:.2f}秒"
            )
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"发送件失败: {str(e)}")
            if status_message is not None:
              await status_message.edit_text(
                f"文件发送失败，请稍后重试。\n"
                f"总耗时: {total_time:.2f}秒\n"
                f"下载耗时: {download_duration:.2f}秒"
            )
        finally:
            # 清理用户的下载计数
            with download_lock:
                active_downloads[user.id] = max(0, active_downloads.get(user.id, 1) - 1)
            
            # 启动异步清任务
            if video_file and os.path.exists(video_file):
                asyncio.create_task(cleanup_files(video_file))

    except Exception as e:
        logger.error(f"Error during download and send process: {str(e)}", exc_info=True)
        if status_message is not None:
            await status_message.edit_text(f"An error occurred. Please try again later.")
        # 确保在错误情况下也减少下载计数
        with download_lock:
            active_downloads[user.id] = max(0, active_downloads.get(user.id, 1) - 1)

async def compress_video_if_needed(video_file, max_size_mb=50):
    """如果视频太大，尝试压缩"""
    if await check_file_size(video_file, max_size_mb):
        return video_file
        
    output_file = f"{os.path.splitext(video_file)[0]}_compressed.mp4"
    try:
        process = await asyncio.create_subprocess_exec(
            'ffmpeg', '-i', video_file, 
            '-c:v', 'libx264', '-crf', '28',
            '-c:a', 'aac', '-b:a', '128k',
            output_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        if await check_file_size(output_file, max_size_mb):
            os.remove(video_file)
            return output_file
        else:
            os.remove(output_file)
            return video_file
    except Exception as e:
        logger.error(f"压缩视频失败: {str(e)}")
        return video_file

async def check_file_size(file_path, max_size_mb=50):
    """检查文件大小是否超过限制"""
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False
    file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为 MB
    logger.info(f"文件大小: {file_size:.2f}MB")
    return file_size <= max_size_mb

@backoff.on_exception(
    backoff.expo,
    (TimedOut, NetworkError),
    max_tries=3,
    max_time=300
)
async def send_video_with_retry(message, video_file):
    """带重试机制的视频发送函数"""
    with open(video_file, 'rb') as video:
        return await message.reply_document(
            document=video,
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30,
            pool_timeout=30
        )

async def update_status_message(status_message, text):
    """更新状态消息的助函数"""
    try:
        await status_message.edit_text(text)
    except Exception as e:
        logger.warning(f"更新状态消息失败: {str(e)}")

# 添加清理任务函数
async def cleanup_files(file_path: str, delay: int = 60):
    """
    异步清理文件
    :param file_path: 要删除的文件路径
    :param delay: 延迟删除的秒数，默认60秒
    """
    try:
        await asyncio.sleep(delay)  # 等待一定时间后再删除
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"已清理文件: {file_path}")
    except Exception as e:
        logger.error(f"清理文件失败 {file_path}: {str(e)}")

# 添加下载任务管理函数
async def manage_download_tasks(user_id: int) -> bool:
    """
    管理用户下载任务
    :param user_id: 用户ID
    :return: 是否可以开始新的下载
    """
    with download_lock:
        # 清理已完成的任务
        active_downloads.update({
            uid: count for uid, count in active_downloads.items()
            if count > 0
        })
        
        # 检查用户当前的下载数量
        current_downloads = active_downloads.get(user_id, 0)
        if current_downloads >= 2:  # 每个用户最多同时下载2个视频
            return False
            
        # 增加用户的下载计数
        active_downloads[user_id] = current_downloads + 1
        return True

# 添加定期清理函数
async def cleanup_download_counts():
    """定期清理过期的下载计数"""
    while True:
        await asyncio.sleep(300)  # 每5分钟清理一次
        with download_lock:
            # 清理计数为0的用户
            active_downloads.clear()
        logger.info("已清理下载计数")

def main() -> None:
    try:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        
        def create_ssl_connection(*args, **kwargs):
            sock = socket.create_connection(*args, **kwargs)
            ssl_sock = ssl_context.wrap_socket(sock, server_hostname=kwargs.get("server_hostname"))
            return ssl_sock
        
        transport = httpx.AsyncHTTPTransport()
        
        http_client = httpx.AsyncClient(verify=True)
        
        http_request = HTTPXRequest()
        
        application = Application.builder().token(TOKEN).request(http_request).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # 启动清理任务
        loop = asyncio.get_event_loop()
        loop.create_task(cleanup_download_counts())

        # 运行应用
        application.run_polling()
    finally:
        download_executor.shutdown(wait=True)

if __name__ == "__main__":
    main()
