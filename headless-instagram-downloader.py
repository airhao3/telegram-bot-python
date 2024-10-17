import argparse
import pyperclip
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import logging
import time
import random
import os
import requests
import uuid
from concurrent.futures import ThreadPoolExecutor
import re
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

downloaded_links = set()  # 用于存储已下载的链接
driver = None  # 全局 Chrome 驱动

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
        chrome_options.add_argument("--headless")  # 启用无头模式
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.page_load_strategy = 'normal'  # 使用正常的页面加载策略

        logger.info("正在初始化 Chrome driver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Chrome driver 初始化成功")

def download_file(url, filename):
    try:
        logger.info(f"开始下载文件: {filename}，来自: {url}")
        response = requests.get(url, timeout=10)  # 设置超时
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            logger.info(f"已下载: {filename}")
        else:
            logger.error(f"下载失败: {filename}, 状态码: {response.status_code}")
    except Exception as e:
        logger.error(f"下载过程中发生错误: {e}")

def handle_popups():
    """处理可能出现的弹窗"""
    try:
        cookie_accept_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept')]"))
        )
        cookie_accept_button.click()
        logger.info("已接受 Cookie 政策")
    except Exception as e:
        logger.warning("未找到 Cookie 同意弹窗或未能点击: %s", e)

    try:
        close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Close')]"))
        )
        close_button.click()
        logger.info("已关闭弹窗")
    except Exception as e:
        logger.warning("未找到关闭弹窗的按钮: %s", e)

def is_instagram_link(link):
    """检查链接是否为有效的 Instagram 链接"""
    return re.match(r'https?://(www\.)?instagram\.com/.+', link) is not None

def is_instagram_video(link):
    """检查链接是否为有效的 Instagram 视频链接"""
    return re.match(r'https?://(www\.)?instagram\.com/p/.+', link) is not None or \
           re.match(r'https?://(www\.)?instagram\.com/reel/.+', link) is not None

def download_instagram_video(instagram_link):
    global driver
    if not is_instagram_video(instagram_link):
        logger.error("提供的链接不是有效的 Instagram 视频链接")
        return None

    try:
        logger.info("开始访问 SaveVid 网站...")
        driver.get("https://savevid.net/en")
        logger.info(f"页面标题: {driver.title}")

        handle_popups()

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        input_box = None
        for selector in ["#s_input", "input[name='url']", "input[type='text']"]:
            try:
                logger.info(f"尝试查找输入框，选择器: {selector}")
                input_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if input_box:
                    logger.info("成功找到输入框")
                    break
            except Exception as e:
                logger.error(f"查找输入框时发生错误: {e}")
                continue

        if not input_box:
            logger.error("无法找到输入框")
            return None

        input_box.clear()
        human_like_input(input_box, instagram_link)
        logger.info(f"已输入 Instagram 链接: {instagram_link}")

        random_sleep(0.5, 1)

        try:
            submit_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "btn_submit"))
            )
            submit_button.click()
        except Exception as e:
            logger.error(f"提交按钮点击失败: {e}")
            input_box.send_keys(Keys.RETURN)

        logger.info("已提交表单")

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "download-items"))
        )
        logger.info("搜索结果已加载")

        download_links = driver.find_elements(By.CSS_SELECTOR, ".download-items .abutton")
        if download_links:
            logger.info("找到以下下载链接：")
            links_dict = {}
            for link in download_links:
                href = link.get_attribute('href')
                text = link.text
                logger.info(f"下载链接: {href}, 文本: {text}")
                links_dict[text] = href
            
            # 检查是否获取到视频和缩略图链接
            video_url = links_dict.get("Download Video")
            thumbnail_url = links_dict.get("Download Thumbnail")
            if video_url and thumbnail_url:
                logger.info("成功获取视频和缩略图链接")
                return {"video_url": video_url, "thumbnail_url": thumbnail_url}
            else:
                logger.warning("未能获取视频或缩略图链接")
                return None
        else:
            logger.warning("未找到下载链接")
            return None

    except Exception as e:
        logger.exception(f"下载过程中发生错误: {e}")
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
                logger.error(f"下载过程中发生错误: {e}")

# 在 main 函数中添加输入验证
def main():
    global driver
    initialize_driver()  # 初始化驱动

    instagram_link = input("请输入 Instagram 视频链接：")
    if is_instagram_link(instagram_link):
        result = download_instagram_video(instagram_link)  # 直接调用下载函数
        if result:
            video_url = result.get("video_url")
            if video_url:
                print(f"视频下载链接: {video_url}")
            else:
                print("未能获取视频链接")
        else:
            print("下载过程中发生错误")
    else:
        print("提供的链接不是有效的 Instagram 链接")

    if driver:
        driver.quit()  # 退出时关闭驱动

if __name__ == "__main__":
    main()
