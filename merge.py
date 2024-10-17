import logging
import os
import re
import requests
import uuid
import time
import random
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import queue  # Import queue for update_queue parameter
# 在文件顶部添加导入语句
from dotenv import load_dotenv  # 导入 load_dotenv 函数
from telegram.ext import Application, ApplicationBuilder, filters  # 修改导入语句

# Load environment variables from .env file
load_dotenv()

# Assign the token from the environment variable
TOKEN = os.getenv('TOKEN')
print(TOKEN)
# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables
downloaded_links = set()  # Used to store downloaded links
driver = None  # Global Chrome driver

def random_sleep(min_seconds, max_seconds):
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_like_input(element, text):
    for char in text:
        element.send_keys(char)
        random_sleep(0.05, 0.15)

def initialize_driver():
    global driver
    if driver is None:
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Enable headless mode
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.page_load_strategy = 'normal'  # Use normal page load strategy

        logger.info("Initializing Chrome driver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Chrome driver initialized successfully")

def download_file(url, filename):
    try:
        logger.info(f"Starting to download file: {filename} from: {url}")
        response = requests.get(url, timeout=10)  # Set timeout
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            logger.info(f"Downloaded: {filename}")
        else:
            logger.error(f"Failed to download: {filename}, status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Error occurred during download: {e}")

def handle_popups():
    """Handle possible popups"""
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

def is_instagram_link(link):
    """Check if the link is a valid Instagram link"""
    return re.match(r'https?://(www\.)?instagram\.com/.+', link) is not None

def is_instagram_video(link):
    """Check if the link is a valid Instagram video link"""
    return re.match(r'https?://(www\.)?instagram\.com/p/.+', link) is not None or \
           re.match(r'https?://(www\.)?instagram\.com/reel/.+', link) is not None

def download_instagram_video(instagram_link):
    global driver
    if not is_instagram_video(instagram_link):
        logger.error("The provided link is not a valid Instagram video link")
        return None

    try:
        logger.info("Visiting SaveVid website...")
        driver.get("https://savevid.net/en")
        logger.info(f"Page title: {driver.title}")

        handle_popups()

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        input_box = None
        for selector in ["#s_input", "input[name='url']", "input[type='text']"]:
            try:
                logger.info(f"Trying to find input box, selector: {selector}")
                input_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if input_box:
                    logger.info("Input box found")
                    break
            except Exception as e:
                logger.error(f"Error finding input box: {e}")
                continue

        if not input_box:
            logger.error("Input box not found")
            return None

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
            logger.info("Found the following download links:")
            links_dict = {}
            for link in download_links:
                href = link.get_attribute('href')
                text = link.text
                logger.info(f"Download link: {href}, text: {text}")
                links_dict[text] = href
            
            # Check if video and thumbnail links are obtained
            video_url = links_dict.get("Download Video")
            thumbnail_url = links_dict.get("Download Thumbnail")
            if video_url and thumbnail_url:
                logger.info("Successfully obtained video and thumbnail links")
                return {"video_url": video_url, "thumbnail_url": thumbnail_url}
            else:
                logger.warning("Failed to obtain video or thumbnail links")
                return None
        else:
            logger.warning("No download links found")
            return None

    except Exception as e:
        logger.exception(f"Error occurred during download: {e}")
        return None

def download_videos(instagram_links):
    download_folder = "download"
    os.makedirs(download_folder, exist_ok=True)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(download_instagram_video, link): link for link in instagram_links}
        for future in futures:
            try:
                result = future.result()
                if result:
                    video_url = result.get("video_url")
                    thumbnail_url = result.get("thumbnail_url")
                    if video_url and thumbnail_url:
                        file_uuid = str(uuid.uuid4())
                        video_path = os.path.join(download_folder, f"{file_uuid}.mp4")
                        thumbnail_path = os.path.join(download_folder, f"{file_uuid}.jpg")
                        download_file(video_url, video_path)
                        download_file(thumbnail_url, thumbnail_path)
            except Exception as e:
                logger.error(f"Error occurred during download: {e}")

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Welcome to the Instagram Video Downloader Bot! Send me an Instagram video link to download.')

async def handle_message(update: Update, context: CallbackContext) -> None:
    instagram_link = update.message.text
    if is_instagram_link(instagram_link):
        await update.message.reply_text('Downloading video...')
        await download_videos([instagram_link])  # 确保 download_videos 也是异步的
        await update.message.reply_text('Download complete. Check the "download" folder.')
    else:
        await update.message.reply_text('The provided link is not a valid Instagram link.')

def main() -> None:
    global driver
    initialize_driver()  # Initialize the driver

    # 确保 TELEGRAM_BOT_TOKEN 已定义
    TELEGRAM_BOT_TOKEN = os.getenv('TOKEN')  # 从环境变量获取 TOKEN
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not defined in the environment variables.")
        return  # 如果未定义，退出程序

    # 使用 Application 替代 Updater
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()  # 创建 Application 实例

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))  # 更新过滤器

    application.run_polling()  # 启动轮询
    if driver:
        driver.quit()  # Close the driver on exit

if __name__ == "__main__":
    main()
