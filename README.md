# Telegram 视频下载机器人

这是一个功能强大的Telegram机器人，可以下载Twitter、YouTube和Instagram视频。

## 功能特点

- 支持下载Twitter、YouTube和Instagram视频
- 使用Whisper进行语音识别(STT)
- 自动清理用户缓存
- 支持从Instagram下载视频和缩略图

## 安装

1. 克隆此仓库:
   ```
   git clone https://github.com/airhao3/telegram-video-download-bot.git
   cd telegram-video-download-bot
   ```

2. 安装依赖:
   ```
   pip install -r requirements.txt
   ```

3. 安装系统依赖:
   - FFmpeg (用于音频处理)
   - gallery-dl (用于Twitter视频下载)
   - yt-dlp (用于YouTube视频下载)
   - Selenium (用于Instagram视频下载)

4. 在无 GUI 环境中安装 Google Chrome:
   - **在 Ubuntu/Debian 上**：
     ```bash
     sudo apt update
     sudo apt install -y wget
     wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
     sudo apt install -y ./google-chrome-stable_current_amd64.deb
     rm google-chrome-stable_current_amd64.deb
     ```

   - **在 CentOS/RHEL 上**：
     ```bash
     sudo yum install -y wget
     wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
     sudo yum localinstall -y google-chrome-stable_current_x86_64.rpm
     rm google-chrome-stable_current_x86_64.rpm
     ```

   - **在 Fedora 上**：
     ```bash
     sudo dnf install -y wget
     wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
     sudo dnf localinstall -y google-chrome-stable_current_x86_64.rpm
     rm google-chrome-stable_current_x86_64.rpm
     ```

   - **在 Docker 容器中**：
     ```dockerfile
     FROM ubuntu:20.04

     RUN apt-get update && apt-get install -y \
         wget \
         gnupg2 \
         && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
         && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
         && apt-get update \
         && apt-get install -y google-chrome-stable \
         && apt-get clean \
         && rm -rf /var/lib/apt/lists/*
     ```

5. 创建一个`.env`文件，并添加您的Telegram Bot Token:
   ```
   TOKEN=your_telegram_bot_token_here
   ```

6. 设置Webhook:
   - 确保您有一个带SSL证书的公共域名
   - 使用以下命令设置webhook:
     ```
     curl -F "url=https://your_domain.com/your_bot_path" https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
     ```
   - 将`your_domain.com/your_bot_path`替换为您的实际域名和机器人路径
   - 将`<YOUR_BOT_TOKEN>`替换为您的实际bot token

7. 测试Webhook设置:
   - 使用以下命令检查webhook的当前状态:
     ```
     curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
     ```
   - 如果设置成功，您应该看到类似以下的响应:
     ```json
     {
       "ok": true,
       "result": {
         "url": "https://your_domain.com/your_bot_path",
         "has_custom_certificate": false,
         "pending_update_count": 0,
         "max_connections": 40,
         "ip_address": "xxx.xxx.xxx.xxx"
       }
     }
     ```
   - 确保"url"字段与您设置的URL匹配
   - 如果看到错误或URL不匹配，请重新检查您的设置并重新执行步骤6

## 使用方法

1. 运行机器人:
   ```
   python telegram-bot-download-purge-vps.py
   ```

2. 在Telegram中与机器人对话:
   - 发送 `/start` 开始使用
   - 发送视频URL以下载视频
   - 发送Instagram视频链接以下载Instagram视频

## 注意事项

- 请确保您有足够的磁盘空间来存储下载的视频。
- 对于大文件，下载和处理可能需要一些时间。
- Instagram视频下载依赖于Selenium和Chrome驱动，请确保您的环境中已正确配置。

## 贡献

欢迎提交问题报告和拉取请求。对于重大更改，请先开issue讨论您想要改变的内容。

## CHANGELOG

### [1.0.0] - 2023-10-01
- 初始发布
- 支持下载Twitter、YouTube和Instagram视频
- 添加语音识别功能
- 自动清理用户缓存

### [1.1.0] - 2024-10-17
- 添加Instagram视频下载功能
- 支持下载视频和缩略图
- 增强错误处理和日志记录

## 许可证

[MIT](https://choosealicense.com/licenses/mit/)
