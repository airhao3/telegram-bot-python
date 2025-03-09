import os
import time
import logging
import requests
import asyncio
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from .resource_monitor import ResourceMonitor

logger = logging.getLogger(__name__)

class DownloadManager:
    def __init__(
        self,
        max_workers: int = 8,
        max_concurrent_per_user: int = 3,
        download_timeout: int = 180,
        max_retries: int = 3,
        max_file_size: int = 2000,
        download_dir: str = "download"
    ):
        self.max_workers = max_workers
        self.max_concurrent_per_user = max_concurrent_per_user
        self.download_timeout = download_timeout
        self.max_retries = max_retries
        self.max_file_size = max_file_size
        self.download_dir = download_dir
        
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_downloads = {}
        self.download_lock = Lock()
        self.resource_monitor = ResourceMonitor()
        
        # 性能指标
        self.metrics = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_processing_time': 0
        }
        self.metrics_lock = Lock()

    async def can_start_download(self, user_id: int) -> Tuple[bool, str]:
        """检查用户是否可以开始新的下载"""
        # 检查系统资源
        can_proceed, message = self.resource_monitor.check_system_resources()
        if not can_proceed:
            return False, message

        with self.download_lock:
            current_downloads = self.active_downloads.get(user_id, 0)
            if current_downloads >= self.max_concurrent_per_user:
                return False, f"您当前已有{current_downloads}个下载任务正在进行"
            self.active_downloads[user_id] = current_downloads + 1
            
        return True, ""

    def update_metrics(self, success: bool, processing_time: float):
        """更新性能指标"""
        with self.metrics_lock:
            self.metrics['total_downloads'] += 1
            if success:
                self.metrics['successful_downloads'] += 1
            else:
                self.metrics['failed_downloads'] += 1
            self.metrics['total_processing_time'] += processing_time

    async def check_file_size(self, url: str) -> Tuple[bool, float, str]:
        """检查文件大小"""
        try:
            # u4f7fu7528 loop.run_in_executor u6765u5f02u6b65u6267u884cu540cu6b65u8bf7u6c42
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.head(url, timeout=10)
            )
            
            size_mb = int(response.headers.get('content-length', 0)) / (1024 * 1024)
            if size_mb > self.max_file_size:
                return False, size_mb, f"文件太大 ({size_mb:.1f}MB)，超过限制 ({self.max_file_size}MB)"
            return True, size_mb, ""
        except Exception as e:
            logger.warning(f"无法获取文件大小: {e}")
            return True, 0, ""  # 如果无法获取大小，允许继续下载

    async def download_file(self, url: str, user_id: int) -> Optional[str]:
        """下载文件"""
        start_time = time.time()
        success = False
        
        try:
            # 创建用户下载目录
            user_dir = os.path.join(self.download_dir, str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # 检查文件大小
            can_download, size_mb, message = await self.check_file_size(url)
            if not can_download:
                raise Exception(message)
                
            # 开始下载
            file_path = os.path.join(user_dir, f"{int(time.time())}.mp4")
            
            # u4f7fu7528 loop.run_in_executor u6765u5f02u6b65u6267u884cu540cu6b65u4e0bu8f7d
            loop = asyncio.get_event_loop()
            
            def download_task():
                with requests.get(url, stream=True, timeout=self.download_timeout) as response:
                    response.raise_for_status()
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
            
            # u5f02u6b65u6267u884cu4e0bu8f7du4efbu52a1
            await loop.run_in_executor(None, download_task)
            
            success = True
            return file_path
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return None
            
        finally:
            # 更新指标
            processing_time = time.time() - start_time
            self.update_metrics(success, processing_time)
            
            # 减少活跃下载计数
            with self.download_lock:
                self.active_downloads[user_id] = max(0, self.active_downloads.get(user_id, 1) - 1)

    async def cleanup_old_files(self, max_age_hours: int = 24):
        """清理旧文件"""
        try:
            current_time = time.time()
            for root, _, files in os.walk(self.download_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if current_time - os.path.getctime(file_path) > max_age_hours * 3600:
                        try:
                            os.remove(file_path)
                            logger.info(f"已清理旧文件: {file_path}")
                        except Exception as e:
                            logger.error(f"清理文件失败 {file_path}: {e}")
        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")

    def get_metrics(self) -> dict:
        """获取性能指标"""
        with self.metrics_lock:
            return self.metrics.copy()
