# Telegram 视频下载机器人

一个功能强大的 Telegram 机器人，支持从多个平台下载视频。

## 功能特点

- 多平台视频下载支持：
  - Instagram 视频下载
  - Twitter 视频下载
  - YouTube 视频下载
  - TikTok 无水印视频下载
- 并发下载支持（每用户最多 2 个同时下载）
- 自动文件大小检查（限制 50MB）
- 自动重试机制
- 详细的下载进度显示
- 完整的时间统计
- 自动清理临时文件

## 系统要求

- Python 3.8+
- Google Chrome
- FFmpeg
- 稳定的网络连接
- 足够的存储空间

## 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/telegram-video-download-bot.git
cd telegram-video-download-bot
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 安装系统依赖：

Ubuntu/Debian:
```bash
# 安装 Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb

# 安装其他依赖
sudo apt-get update
sudo apt-get install -y ffmpeg
```

macOS:
```bash
# 使用 Homebrew 安装依赖
brew install --cask google-chrome
brew install ffmpeg
```

4. 配置环境变量：
创建 `.env` 文件并添加：
```plaintext
TOKEN=your_telegram_bot_token_here
```

## 使用方法

1. 启动机器人：
```bash
python main.py
```

2. 在 Telegram 中：
   - 发送 `/start` 开始使用
   - 直接发送视频链接即可下载
   - 支持的链接格式：
     - Instagram: `https://www.instagram.com/p/xxx`
     - Twitter: `https://twitter.com/xxx/status/xxx`
     - YouTube: `https://youtube.com/watch?v=xxx`
     - TikTok: `https://www.tiktok.com/@xxx/video/xxx`

## 性能统计

每次下载都会显示详细的时间统计：
- 总处理时间
- 下载耗时
- 发送耗时

## 注意事项

1. 文件大小限制：
   - Telegram 限制文件大小不超过 50MB
   - 超过限制的文件将无法发送

2. 并发限制：
   - 每个用户最多同时下载 2 个视频
   - 超过限制需等待当前下载完成

3. 网络要求：
   - 需要稳定的网络连接
   - 建议使用代理以提高访问速度

4. 存储空间：
   - 自动清理下载的临时文件
   - 建议预留足够的磁盘空间

## 故障排除

1. 下载失败：
   - 检查网络连接
   - 确认链接是否有效
   - 查看日志文件获取详细错误信息

2. 发送失败：
   - 检查文件大小是否超限
   - 确认 bot token 是否有效
   - 尝试重新发送

3. TikTok 下载问题：
   - 确保链接格式正确
   - 检查是否为私密视频
   - 尝试使用分享链接

## 更新日志

### [1.2.0] - 2024-01-20
- 添加 TikTok 无水印视频下载支持
- 添加并发下载限制
- 优化下载速度
- 添加详细的时间统计

### [1.1.0] - 2024-01-15
- 添加下载时间统计
- 优化下载速度
- 改进错误处理

### [1.0.0] - 2024-01-01
- 初始发布
- 支持多平台视频下载
- 添加自动重试机制

## 贡献

欢迎提交 Issues 和 Pull Requests！

## 许可证

[MIT](LICENSE)
