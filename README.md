# Telegram 视频下载机器人

一个轻量级的 Telegram 视频下载机器人，基于 Cobalt API 实现多平台视频下载功能。本项目采用 Docker 容器化部署，使部署和管理变得简单高效。

## 项目说明

本项目使用 Cobalt API 进行视频下载，相比之前版本有以下优势：
- 更轻量级的部署方案，无需安装浏览器
- 更稳定的下载体验
- 更快的响应速度
- 更简单的维护方式

## 功能特点

### 下载功能
- 多平台视频下载支持：
  - Instagram 视频和照片下载
  - Twitter/X 平台视频下载
  - YouTube 视频下载（支持选择质量）
  - TikTok 无水印视频下载
  - 其他平台支持（详见 Cobalt API 文档）

### 系统特性
- 模块化架构设计
- 系统资源监控与管理
- 高效并发下载处理（每用户最多3个并发任务）
- 视频文件完整性检查
- 自动清理临时文件
- 智能文件大小管理（最大支持2GB）
- 优雅的错误处理与重试机制
- 用户友好的状态更新提示
- 单实例运行保证，防止冲突

## 部署指南

### 环境要求
- Docker 环境
- Telegram Bot Token（从 @BotFather 获取）
- Cobalt API Token（可选，用于提高下载限制）

### 快速部署

1. 获取项目代码：
   ```bash
   git clone https://github.com/airhao3/telegram-bot-python.git
   cd telegram-bot-python
   ```

2. 配置环境变量：
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入必要的配置信息
   ```

3. 构建并启动：
   ```bash
   # 构建 Docker 镜像
   docker build -t telegram-video-bot .
   
   # 运行容器
   docker run -d \
     --name telegram-video-bot \
     --restart unless-stopped \
     -v $(pwd)/download:/app/download \
     --env-file .env \
     telegram-video-bot
   ```

### 维护管理

```bash
# 查看运行日志
docker logs -f telegram-video-bot

# 更新机器人
docker pull telegram-video-bot
docker restart telegram-video-bot

# 停止/启动服务
docker stop telegram-video-bot
docker start telegram-video-bot
```

## 使用说明

1. 在 Telegram 中找到您的机器人
2. 发送视频链接给机器人
3. 等待机器人处理并发送视频

### 支持的链接格式
- Instagram: https://www.instagram.com/p/xxx
- Twitter/X: https://twitter.com/xxx/status/xxx
- YouTube: https://youtube.com/watch?v=xxx
- TikTok: https://www.tiktok.com/@xxx/video/xxx

### 注意事项
- 视频大小限制为 2GB（可在配置中调整）
- 下载较大视频时会自动压缩
- 每个用户同时最多处理 3 个下载任务
- 临时文件会在下载完成后自动清理
- 系统内存使用率超过75%时会暂停新任务


## 更新日志

### [2.1.0] - 2025-03-09
- 代码重构：模块化架构设计
  - 添加资源监控模块
  - 添加下载管理模块
  - 添加视频处理模块
  - 添加单实例管理器
- 性能优化：
  - 增加每用户并发下载数至3个
  - 设置最大文件大小限制为2GB
  - 添加内存使用监控机制
- 错误处理改进
- 用户体验增强

### [2.0.0] - 2025-02-07
- 重大更新：迁移至 Cobalt API
- 移除 Chrome 依赖，大幅减小部署体积
- 优化下载稳定性
- 提升响应速度
- 简化维护流程

### [1.2.0] - 2024-01-20
- 添加 TikTok 无水印视频下载支持
- 添加并发下载限制
- 优化下载速度

### [1.1.0] - 2024-01-15
- 添加下载时间统计
- 改进错误处理
- 优化用户体验

### [1.0.0] - 2024-01-01
- 初始发布
- 支持多平台视频下载
- 基于 Selenium 和 Chrome 的下载实现

## 贡献

欢迎提交 Issues 和 Pull Requests！如果你有任何问题或建议，请随时与我们联系。

## 许可证

本项目采用 [MIT](LICENSE) 许可证。
