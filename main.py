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
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# Load environment variables and set up logging
load_dotenv()
TOKEN = os.getenv('TOKEN')
DOWNLOAD_DIR = "download"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables
driver = None

def initialize_driver():
    global driver
    if driver is None:
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 启用无头模式
        chrome_options.add_argument("--disable-gpu")  # 禁用 GPU 加速
        chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data")  # 设置用户数据目录
        chrome_options.add_argument("--remote-debugging-port=9222")  # 设置远程调试端口
        chrome_options.page_load_strategy = 'normal'  # 使用正常的页面加载策略
        chrome_options.page_load_timeout = 30  # 设置页面加载超时为30秒
        
        # 添加以下选项以解决无头模式问题
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        logger.info("正在初始化 Chrome driver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)  # 移除 timeout 参数
        logger.info("Chrome driver 初始化成功")

def random_sleep(min_seconds, max_seconds):
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_like_input(element, text):
    for char in text:
        element.send_keys(char)
        random_sleep(0.05, 0.15)

def handle_popups():
    try:
        cookie_accept_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept')]"))
        )
        cookie_accept_button.click()
        logger.info("Accepted cookie policy")
    except Exception as e:
        logger.warning("Cookie accept popup not found or not clickable: %s", e)

    try:
        close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Close')]"))
        )
        close_button.click()
        logger.info("Closed popup")
    except Exception as e:
        logger.warning("Close popup button not found: %s", e)

def is_url(text):
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return bool(url_pattern.match(text))

def get_url_type(url):
    if 'instagram.com' in url:
        return 'instagram'
    elif 'twitter.com' in url or 'x.com' in url:
        return 'twitter'
    elif 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    else:
        return 'unknown'

async def download_instagram_video(instagram_link, user_cache_dir):
    global driver
    try:
        logger.info("Visiting SaveVid website...")
        driver.get("https://savevid.net/en")
        logger.info(f"Page title: {driver.title}")

        handle_popups()

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        input_box = None
        for selector in ["#s_input", "input[name='url']", "input[type='text']"]:
            try:
                input_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if input_box:
                    logger.info("Input box found")
                    break
            except Exception as e:
                logger.error(f"Error finding input box: {e}")

        if not input_box:
            raise Exception("Input box not found")

        input_box.clear()
        human_like_input(input_box, instagram_link)
        logger.info(f"Entered Instagram link: {instagram_link}")

        random_sleep(0.5, 1)

        try:
            submit_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "btn_submit"))
            )
            submit_button.click()
        except Exception as e:
            logger.error(f"Submit button click failed: {e}")
            input_box.send_keys(Keys.RETURN)

        logger.info("Form submitted")

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "download-items"))
        )
        logger.info("Search results loaded")

        download_links = driver.find_elements(By.CSS_SELECTOR, ".download-items .abutton")
        if download_links:
            logger.info("Found download links")
            video_url = next((link.get_attribute('href') for link in download_links if "Download Video" in link.text), None)
            
            if video_url:
                logger.info("Successfully obtained video link")
                file_uuid = str(uuid.uuid4())
                video_path = os.path.join(user_cache_dir, f"{file_uuid}.mp4")
                
                response = requests.get(video_url, stream=True)
                with open(video_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.info(f"Instagram video downloaded: {video_path}")
                return video_path
            else:
                raise Exception("Failed to obtain video link")
        else:
            raise Exception("No download links found")

    except Exception as e:
        logger.exception(f"Error occurred during Instagram download: {e}")
        return None

async def download_video_task(url, url_type, update: Update, context: ContextTypes.DEFAULT_TYPE, status_message, max_retries=3):
    user_id = update.effective_user.id
    user_cache_dir = os.path.join(DOWNLOAD_DIR, str(user_id))
    os.makedirs(user_cache_dir, exist_ok=True)

    for attempt in range(max_retries):
        try:
            logger.info(f"Starting download attempt {attempt + 1} for URL: {url}")

            if url_type == 'instagram':
                video_file = await download_instagram_video(url, user_cache_dir)
            elif url_type in ['twitter', 'youtube']:
                if url_type == 'twitter':
                    command = [
                        'gallery-dl', '-v', '--write-metadata', '--write-info-json',
                        '-D', user_cache_dir, url
                    ]
                else:  # youtube
                    command = [
                        'yt-dlp', '-v', '--write-info-json',
                        '--output', os.path.join(user_cache_dir, '%(title)s.%(ext)s'),
                        url
                    ]

                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    progress = line.decode().strip()
                    try:
                        await status_message.edit_text(f"Downloading: {progress}")
                    except Exception as e:
                        logger.warning(f"Failed to update progress message: {e}")

                await process.wait()
                if process.returncode != 0:
                    error = await process.stderr.read()
                    raise RuntimeError(f"{url_type} download failed with error: {error.decode()}")

                video_file = next(
                    (os.path.join(user_cache_dir, f) for f in os.listdir(user_cache_dir)
                     if f.endswith((".mp4", ".mkv", ".webm"))),
                    None
                )

                if not video_file:
                    raise FileNotFoundError("Downloaded video file not found")

                if url_type == 'youtube' and not video_file.endswith('.mp4'):
                    merged_file = f"{os.path.splitext(video_file)[0]}_merged.mp4"
                    ffmpeg_command = ['ffmpeg', '-i', video_file, '-c', 'copy', merged_file]
                    await asyncio.create_subprocess_exec(*ffmpeg_command)
                    os.remove(video_file)
                    video_file = merged_file
            else:
                raise ValueError("Unsupported URL type")

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
    await update.message.reply_text('Welcome! Send me a YouTube, Twitter, or Instagram video link to download.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message_text = update.message.text
    logger.info(f"Received message from user {user.id} ({user.username}): {message_text}")

    if not is_url(message_text):
        await update.message.reply_text("Please send a valid video link.")
        return

    url_type = get_url_type(message_text)
    if url_type == 'unknown':
        await update.message.reply_text("Unsupported URL type. Please send a YouTube, Twitter, or Instagram URL.")
        return

    status_message = await update.message.reply_text("Starting download. Please wait...")
    
    try:
        video_file = await download_video_task(message_text, url_type, update, context, status_message)

        with open(video_file, 'rb') as video:
            await update.message.reply_document(document=video)

        await status_message.edit_text("Download completed and file sent!")
        
        os.remove(video_file)
        logger.info(f"Deleted downloaded video file: {video_file}")
        
        user_cache_dir = os.path.join(DOWNLOAD_DIR, str(user.id))
        for file in os.listdir(user_cache_dir):
            os.remove(os.path.join(user_cache_dir, file))

    except Exception as e:
        logger.error(f"Error during download and send process: {str(e)}", exc_info=True)
        await status_message.edit_text(f"An error occurred. Please try again later.")

def main() -> None:
    initialize_driver()

    application = Application.builder().token(TOKEN).build()  # 移除 request_kwargs
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

    if driver:
        driver.quit()

if __name__ == "__main__":
    main()