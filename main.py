import logging
import os
import re
import uuid
import time
import asyncio
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut, NetworkError
import backoff
import threading
import json
import psutil

import ssl
import httpx
from telegram.request import HTTPXRequest

# 导入自定义模块
from utils.resource_monitor import ResourceMonitor
from utils.download_manager import DownloadManager
from utils.video_processor import VideoProcessor
from utils.instance_manager import SingleInstanceManager

# 加载环境变量和设置日志
load_dotenv()
TOKEN = os.getenv('TOKEN')
DOWNLOAD_DIR = "download"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
COBALT_API_URL = os.getenv('COBALT_API_URL', "http://localhost:9999/")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 初始化资源管理器和下载管理器
resource_monitor = ResourceMonitor(memory_threshold=75, min_memory_available=500)
download_manager = DownloadManager(
    max_workers=8,  # 基于CPU核心数(4)的2倍优化线程数
    max_concurrent_per_user=3,  # 每个用户的最大并发下载数
    download_timeout=180,  # 下载超时时间（秒）
    max_retries=3,  # 最大重试次数
    max_file_size=2000,  # 最大文件大小限制(MB)
    download_dir=DOWNLOAD_DIR
)
video_processor = VideoProcessor(max_size_mb=50)

# 定期任务锁
scheduled_task_lock = threading.Lock()

# URL验证函数
def is_url(text):
    """检查文本是否为URL"""
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return bool(url_pattern.match(text))


async def fetch_video_with_cobalt(url):
    """使用Cobalt API获取视频下载链接"""
    try:
        # 检查系统资源
        can_proceed, message = resource_monitor.check_system_resources()
        if not can_proceed:
            logger.warning(message)
            return None
            
        # 准备请求
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        data = {"url": url}
        
        # 异步执行请求
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: httpx.post(COBALT_API_URL, headers=headers, json=data, timeout=30)
        )
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"请求 Cobalt API 失败: {e}")
        return None


async def download_video_task(url, update: Update, context: ContextTypes.DEFAULT_TYPE, status_message):
    """处理视频下载任务"""
    user_id = update.effective_user.id
    start_time = time.time()
    success = False
    
    try:
        # 发送状态更新
        await update_status_message(status_message, "正在获取视频信息...")
        
        # 从Cobalt API获取下载链接
        response = await fetch_video_with_cobalt(url)
        if not response or 'url' not in response:
            raise Exception("无法获取有效的下载链接")
        
        download_url = response['url']
        
        # 发送状态更新
        await update_status_message(status_message, "正在下载视频...")
        
        # 执行下载
        video_file = await download_manager.download_file(download_url, user_id)
        if not video_file:
            raise Exception("下载失败")
            
        # 检查视频完整性
        if not await video_processor.check_video_integrity(video_file):
            raise Exception("下载的视频文件已损坏")
            
        # 压缩视频（如果需要）
        await update_status_message(status_message, "正在处理视频...")
        processed_file = await video_processor.compress_video(video_file)
        if not processed_file:
            # 如果压缩失败，使用原始文件
            processed_file = video_file
            
        # 生成唯一文件名
        unique_id = str(uuid.uuid4())
        final_file = os.path.join(DOWNLOAD_DIR, f"{unique_id}_{os.path.basename(processed_file)}")
        os.rename(processed_file, final_file)
        
        success = True
        processing_time = time.time() - start_time
        logger.info(f"下载完成: {url}, 耗时: {processing_time:.2f}秒")
        
        return final_file
        
    except Exception as e:
        logger.error(f"下载任务失败: {e}")
        return None
        
    finally:
        # 更新性能指标
        processing_time = time.time() - start_time
        download_manager.update_metrics(success, processing_time)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理/start命令"""
    await update.message.reply_text('欢迎使用视频下载机器人！发送视频链接即可下载。')


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """显示系统状态统计信息"""
    # 获取系统资源使用情况
    resource_usage = resource_monitor.get_resource_usage()
    
    # 获取下载统计信息
    download_stats = download_manager.get_metrics()
    
    # 格式化统计信息
    stats_text = (
        "📊 系统状态统计 📊\n\n"
        f"CPU使用率: {resource_usage.get('cpu_percent', 0):.1f}%\n"
        f"内存使用率: {resource_usage.get('memory_percent', 0):.1f}%\n"
        f"可用内存: {resource_usage.get('memory_available', 0):.1f} MB\n\n"
        f"总下载请求: {download_stats.get('total_downloads', 0)}\n"
        f"成功下载: {download_stats.get('successful_downloads', 0)}\n"
        f"失败下载: {download_stats.get('failed_downloads', 0)}\n"
    )
    
    await update.message.reply_text(stats_text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理用户消息"""
    start_time = time.time()
    user = update.effective_user
    message_text = update.message.text
    status_message = None
    video_file = None
    success = False
    
    try:
        logger.info(f"收到来自用户 {user.id} ({user.username}) 的消息: {message_text}")
        
        # 检查是否为URL
        if not is_url(message_text):
            await update.message.reply_text("请发送有效的视频链接。")
            return
            
        # 检查用户是否可以开始新的下载
        can_download, reason = await download_manager.can_start_download(user.id)
        if not can_download:
            await update.message.reply_text(reason)
            return
            
        # 发送状态消息
        status_message = await update.message.reply_text("开始处理下载请求...")
        
        # 执行下载任务
        video_file = await download_video_task(message_text, update, context, status_message)
        if not video_file:
            raise Exception("下载处理失败")
            
        # 发送视频
        await update_status_message(status_message, "正在发送视频...")
        await send_video_with_retry(update.message, video_file)
        
        # 更新成功状态
        success = True
        total_time = time.time() - start_time
        
        # 发送完成状态消息
        status_text = (
            f"下载完成并已发送文件！\n"
            f"总耗时: {total_time:.2f}秒"
        )
        await status_message.edit_text(status_text)
        
        # 记录详细日志
        logger.info(f"处理完成 - URL: {message_text}\n{status_text}")
        
    except Exception as e:
        total_time = time.time() - start_time
        error_message = f"处理失败: {str(e)}"
        logger.error(error_message)
        
        if status_message:
            await status_message.edit_text(f"文件处理失败，请稍后重试。\n总耗时: {total_time:.2f}秒")
            
    finally:
        # 启动异步清理任务
        if video_file and os.path.exists(video_file):
            asyncio.create_task(cleanup_files(video_file))


async def send_video_with_retry(message, video_file, max_retries=3):
    """带重试机制的视频发送函数"""
    for attempt in range(max_retries):
        try:
            with open(video_file, 'rb') as video:
                await message.reply_video(
                    video=video,
                    filename=os.path.basename(video_file),
                    caption="下载完成！"
                )
            return True
        except (TimedOut, NetworkError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"发送视频失败，正在重试 ({attempt+1}/{max_retries}): {e}")
                await asyncio.sleep(2)  # 短暂延迟后重试
            else:
                logger.error(f"发送视频失败，已达到最大重试次数: {e}")
                raise
        except Exception as e:
            logger.error(f"发送视频时发生错误: {e}")
            raise


async def update_status_message(status_message, text):
    """更新状态消息的辅助函数"""
    if status_message:
        try:
            await status_message.edit_text(text)
        except Exception as e:
            logger.error(f"更新状态消息失败: {e}")


async def cleanup_files(file_path, delay=60):
    """异步清理文件"""
    try:
        await asyncio.sleep(delay)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"已清理临时文件: {file_path}")
    except Exception as e:
        logger.error(f"清理文件失败: {e}")


async def scheduled_cleanup():
    """定期清理任务"""
    with scheduled_task_lock:
        try:
            # 清理旧文件
            await download_manager.cleanup_old_files(max_age_hours=24)
            
            # 检查系统资源
            resource_usage = resource_monitor.get_resource_usage()
            logger.info(f"系统资源状态 - CPU: {resource_usage.get('cpu_percent', 0):.1f}%, "
                       f"内存: {resource_usage.get('memory_percent', 0):.1f}%")
            
        except Exception as e:
            logger.error(f"定期清理任务失败: {e}")


async def run_scheduled_tasks(app):
    """运行定期任务"""
    while True:
        await scheduled_cleanup()
        await asyncio.sleep(3600)  # 每小时运行一次


async def main():
    """主函数"""
    # 确保只有一个机器人实例运行
    instance_manager = SingleInstanceManager()
    if not instance_manager.ensure_single_instance():
        logger.error("另一个机器人实例已在运行，本实例将退出")
        sys.exit(1)
        
    try:
        # 配置自定义连接池和超时设置
        request = HTTPXRequest(
            connection_pool_size=8,
            read_timeout=30.0,
            write_timeout=30.0,
            connect_timeout=30.0,
        )
        
        # 创建应用
        application = Application.builder().token(TOKEN).request(request).build()
        
        # 添加命令处理器
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("stats", stats))
        
        # 添加消息处理器
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # 启动定期任务
        asyncio.create_task(run_scheduled_tasks(application))
        
        # 启动机器人
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("机器人已启动")
        
        # 保持运行 - 兼容不同版本的python-telegram-bot
        try:
            await application.idle()
        except AttributeError:
            # 如果没有idle方法，使用无限循环保持运行
            while True:
                await asyncio.sleep(3600)
        
    except Exception as e:
        logger.error(f"启动失败: {e}")
    finally:
        # 确保在程序结束时清理资源
        if 'instance_manager' in locals():
            instance_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
