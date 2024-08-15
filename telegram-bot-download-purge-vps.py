import logging
import re
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv
import concurrent.futures
import sys
import asyncio
import subprocess
import uuid

# Load environment variables from .env file
load_dotenv()

# Assign the token from the environment variable
TOKEN = os.getenv('TOKEN')
# Set the download directory
DOWNLOAD_DIR = 'downloads'

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Create a thread pool executor
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

def get_url_type(url):
    """Determine the type of the given URL (Twitter or YouTube)."""
    if 'twitter.com' in url or 'x.com' in url:
        return 'twitter'
    elif 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    else:
        return 'unknown'

async def download_video_task(url, url_type, update: Update, context: ContextTypes.DEFAULT_TYPE, status_message, max_retries=3):
    """Download video using gallery-dl or yt-dlp depending on URL type."""
    for attempt in range(max_retries):
        try:
            logger.info(f"Starting download attempt {attempt + 1} for URL: {url}")

            if url_type == 'twitter':
                command = [
                    'gallery-dl',
                    '-v',
                    '--write-metadata',
                    '--write-info-json',
                    '-D', DOWNLOAD_DIR,
                    url
                ]
            elif url_type == 'youtube':
                command = [
                    'yt-dlp',
                    '-v',
                    '--write-info-json',
                    '--output', os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
                    url
                ]
            else:
                raise Exception("Unsupported URL type")

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

            progress = ""

            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    logger.debug(output.strip())
                    new_progress = output.strip()
                    if new_progress != progress:
                        progress = new_progress
                        try:
                            await status_message.edit_text(f"Downloading: {progress}")
                        except Exception as e:
                            logger.warning(f"Failed to update progress message: {e}")

            if process.returncode != 0:
                error = process.stderr.read()
                logger.error(f"{url_type} error: {error}")
                raise Exception(f"{url_type} failed with error: {error}")

            video_file = None
            for file in os.listdir(DOWNLOAD_DIR):
                if file.endswith(".mp4") or (url_type == 'youtube' and (file.endswith(".mkv") or file.endswith(".webm"))):
                    video_file = os.path.join(DOWNLOAD_DIR, file)
                    break

            if not video_file:
                raise Exception("Downloaded video file not found")

            if url_type == 'youtube':
                merged_file = os.path.splitext(video_file)[0] + '_merged.mp4'
                ffmpeg_command = [
                    'ffmpeg', '-i', video_file, '-c', 'copy', merged_file
                ]
                subprocess.run(ffmpeg_command, check=True)
                os.remove(video_file)
                video_file = merged_file

            unique_id = str(uuid.uuid4())
            new_video_file = os.path.join(DOWNLOAD_DIR, f"{unique_id}_{os.path.basename(video_file)}")
            os.rename(video_file, new_video_file)
            video_file = new_video_file

            logger.info(f"Download completed successfully: {video_file}")

            return video_file

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
        url_type = get_url_type(message_text)
        if url_type == 'unknown':
            await update.message.reply_text("Unsupported URL type. Please send a Twitter or YouTube URL.")
            return
        status_message = await update.message.reply_text("Starting download. Please wait...")
        try:
            logger.info(f"Starting download process for URL: {message_text} of type {url_type}")
            video_file = await download_video_task(message_text, url_type, update, context, status_message)

            if not os.path.exists(video_file) or not os.access(video_file, os.R_OK):
                raise FileNotFoundError(f"Video file not found or not readable: {video_file}")

            logger.info(f"Sending video file to user: {video_file}")

            with open(video_file, 'rb') as video:
                await update.message.reply_document(document=video)

            logger.info("Download and send process completed successfully")
            await status_message.edit_text("Download completed and files sent!")

            os.remove(video_file)
            logger.info(f"Deleted downloaded video file: {video_file}")

            clear_download_dir()

        except FileNotFoundError as e:
            logger.error(f"File not found: {str(e)}")
            await status_message.edit_text(f"Download failed: File not found. Please try again later.")
        except OSError as e:
            logger.error(f"OS error: {str(e)}")
            await status_message.edit_text(f"Download failed: System error. Please try again later.")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            await status_message.edit_text(f"An unexpected error occurred. Please try again later.")
    else:
        logger.warning(f"User {user.id} ({user.username}) sent invalid URL: {message_text}")
        await update.message.reply_text("This is not a valid URL. Please send a video URL.")

def clear_download_dir():
    """Clear all files in the download directory."""
    for file in os.listdir(DOWNLOAD_DIR):
        file_path = os.path.join(DOWNLOAD_DIR, file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
                logger.info(f"Deleted file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete {file_path}. Reason: {str(e)}")

def main() -> None:
    """Start the bot."""
    logger.info("Starting the bot")

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

