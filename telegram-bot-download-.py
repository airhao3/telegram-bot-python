## 更新使用uuid标记当前的下载文件名称， 并使用uuid直接查找文件发送，
## 取消发送之后删除的功能，保留下载内容在服务器。
import logging
import re
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv
import concurrent.futures
import time
import sys
import asyncio
import subprocess
import datetime
import uuid

# 加载.env文件中的环境变量
load_dotenv()

# 将环境变量中的token赋值给TOKEN
TOKEN = os.getenv('TOKEN')
# 设置下载目录
DOWNLOAD_DIR = 'downloads'
SUBTITLE_DIR = os.path.join(DOWNLOAD_DIR, 'subtitles')

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
if not os.path.exists(SUBTITLE_DIR):
    os.makedirs(SUBTITLE_DIR)

# 配置日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# 创建线程池
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! Send me a video URL to download.",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) requested help")
    await update.message.reply_text("Send me a video URL, and I'll download it for you!")

def is_url(text):
    """Check if the given text is a URL."""
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return bool(url_pattern.match(text))

async def download_video_task(url, update: Update, context: ContextTypes.DEFAULT_TYPE, status_message, max_retries=3):
    """Download video, audio, and subtitles using gallery-dl."""
    for attempt in range(max_retries):
        try:
            logger.info(f"Starting download attempt {attempt + 1} for URL: {url}")

            # 构建gallery-dl命令
            command = [
                'gallery-dl',
                '-v',  # 详细输出
                '--write-metadata',  # 写入元数据
                '--write-info-json',  # 写入info.json
                '-D', DOWNLOAD_DIR,  # 设置下载目录
                '--exec', 'mv {} {}'.format(
                    os.path.join(DOWNLOAD_DIR, '*.srt'),
                    SUBTITLE_DIR
                ),  # 移动字幕文件到字幕目录
                url
            ]

            # 执行命令并捕获输出
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

            progress = ""

            # 实时处理输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    logger.debug(output.strip())
                    # 更新下载进度
                    new_progress = output.strip()
                    if new_progress != progress:
                        progress = new_progress
                        try:
                            await status_message.edit_text(f"Downloading: {progress}")
                        except TelegramError:
                            logger.warning("Failed to update progress message")

            # 检查是否有错误
            if process.returncode != 0:
                error = process.stderr.read()
                logger.error(f"gallery-dl error: {error}")
                raise Exception(f"gallery-dl failed with error: {error}")

            # 找到下载的文件
            video_file = None
            subtitle_file = None
            for file in os.listdir(DOWNLOAD_DIR):
                if file.endswith((".mp4", ".webm", ".mkv")):
                    video_file = os.path.join(DOWNLOAD_DIR, file)
                    break

            for file in os.listdir(SUBTITLE_DIR):
                if file.endswith(".srt"):
                    subtitle_file = os.path.join(SUBTITLE_DIR, file)
                    break

            if not video_file:
                raise Exception("Downloaded video file not found")

            # 使用UUID重命名文件以确保唯一性
            unique_id = str(uuid.uuid4())
            new_video_file = os.path.join(DOWNLOAD_DIR, f"{unique_id}_{os.path.basename(video_file)}")
            os.rename(video_file, new_video_file)
            video_file = new_video_file

            logger.info(f"Download completed successfully: {video_file}")
            if subtitle_file:
                logger.info(f"Subtitle file: {subtitle_file}")

            return video_file, subtitle_file

        except Exception as e:
            logger.error(f"Download attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise
            logger.info(f"Waiting 5 seconds before retry...")
            await asyncio.sleep(5)  # Wait for 5 seconds before retrying

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video download request."""
    user = update.effective_user
    message_text = update.message.text
    logger.info(f"Received message from user {user.id} ({user.username}): {message_text}")
    if is_url(message_text):
        status_message = await update.message.reply_text("Starting download. Please wait...")
        try:
            logger.info(f"Starting download process for URL: {message_text}")
            video_file, subtitle_file = await download_video_task(message_text, update, context, status_message)

            # 检查文件是否存在和可读
            if not os.path.exists(video_file) or not os.access(video_file, os.R_OK):
                raise FileNotFoundError(f"Video file not found or not readable: {video_file}")

            logger.info(f"Sending video file to user: {video_file}")

            # 使用 with 语句确保文件正确关闭
            with open(video_file, 'rb') as video:
                await update.message.reply_document(document=video)

            if subtitle_file:
                if not os.path.exists(subtitle_file) or not os.access(subtitle_file, os.R_OK):
                    logger.warning(f"Subtitle file not found or not readable: {subtitle_file}")
                else:
                    logger.info(f"Sending subtitle file to user: {subtitle_file}")
                    with open(subtitle_file, 'rb') as subtitle:
                        await update.message.reply_document(document=subtitle)

            logger.info("Download and send process completed successfully")
            await status_message.edit_text("Download completed and files sent!")

        except FileNotFoundError as e:
            logger.error(f"File not found: {str(e)}")
            await status_message.edit_text(f"Download failed: File not found. Please try again later.")
        except OSError as e:
            logger.error(f"OS error: {str(e)}")
            await status_message.edit_text(f"Download failed: System error. Please try again later.")
        except TelegramError as e:
            logger.error(f"Telegram API error: {str(e)}")
            await status_message.edit_text(f"Failed to send file. The file may be too large or there might be a network issue.")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            await status_message.edit_text(f"An unexpected error occurred. Please try again later.")
    else:
        logger.warning(f"User {user.id} ({user.username}) sent invalid URL: {message_text}")
        await update.message.reply_text("This is not a valid URL. Please send a video URL.")

def main() -> None:
    """Start the bot."""
    logger.info("Starting the bot")

    # 创建 Application，不使用代理
    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    logger.info("Bot is now polling for updates")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
