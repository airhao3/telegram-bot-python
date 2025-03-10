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
- 高效多线程下载处理
- 视频文件完整性检查
- 自动清理临时文件
- 智能文件大小管理（最大支持2GB）
- 优雅的错误处理
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
   # 编辑 .env 文件，填入必要的配置信息（BOT_TOKEN等）
   ```

3. 部署方式（二选一）：

   #### 方式一：使用Docker Compose（推荐）
   有两种使用Docker Compose的方式：
   
   **A. 直接使用预构建镜像（最简单）**
   ```bash
   # 从远程拉取镜像并启动所有服务
   docker-compose pull
   docker-compose up -d
   ```
   
   **B. 本地构建镜像**
   ```bash
   # 在本地构建镜像并启动所有服务
   docker-compose up -d --build
   ```

   #### 方式二：单独构建
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

#### 使用Docker Compose的维护命令（推荐）
```bash
# 查看运行日志
docker-compose logs -f telegram-video-bot
docker-compose logs -f cobalt-api

# 更新所有服务
docker-compose pull
docker-compose up -d

# 停止/启动所有服务
docker-compose stop
docker-compose start
```

#### 使用单容器的维护命令
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

### Docker Compose配置说明

项目提供的`docker-compose.yml`文件包含三个服务：

1. **telegram-video-bot**：Telegram视频下载机器人
   - 使用本地Dockerfile构建
   - 挂载下载目录到宿主机
   - 从.env文件读取环境变量

2. **cobalt-api**：视频链接解析服务
   - 使用官方Docker镜像
   - 提供视频下载链接解析功能

3. **watchtower**：自动更新服务
   - 监控并自动更新cobalt-api容器
   - 保持服务始终为最新版本

这些服务通过自定义网络`bot-network`相互通信。机器人通过`COBALT_API_URL`环境变量访问Cobalt API服务。

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
- 临时文件会在下载完成后自动清理


## 更新日志

### [2.2.0] - 2025-03-10
- 代码重构和简化：
  - 简化下载管理器，移除复杂的锁机制
  - 优化多线程下载处理
  - 改进错误处理机制
  - 使用临时文件确保下载完整性
- 用户系统优化：
  - 完善积分系统
  - 添加订阅用户特权
  - 优化下载限制逻辑
- 性能改进：
  - 提升下载稳定性
  - 优化内存使用
  - 改进异步处理

### [2.1.0] - 2025-03-09
- 代码重构：模块化架构设计
  - 添加下载管理模块
  - 添加视频处理模块
  - 添加单实例管理器
- 性能优化：
  - 设置最大文件大小限制为2GB
  - 优化下载处理逻辑
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
