import psutil
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class ResourceMonitor:
    def __init__(self, memory_threshold: int = 75, min_memory_available: int = 500):
        self.memory_threshold = memory_threshold
        self.min_memory_available = min_memory_available

    def check_system_resources(self) -> Tuple[bool, str]:
        """检查系统资源状态"""
        try:
            memory_info = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            available_memory_mb = memory_info.available / 1024 / 1024
            memory_usage = memory_info.percent

            if memory_usage > self.memory_threshold:
                return False, f"系统内存使用率过高: {memory_usage:.1f}%"
            
            if available_memory_mb < self.min_memory_available:
                return False, f"系统可用内存不足: {available_memory_mb:.1f}MB"
            
            if cpu_percent > 90:
                return False, f"CPU使用率过高: {cpu_percent:.1f}%"
            
            return True, ""
        except Exception as e:
            logger.error(f"检查系统资源失败: {e}")
            return False, "无法获取系统资源信息"

    def get_resource_usage(self) -> dict:
        """获取当前资源使用情况"""
        try:
            memory_info = psutil.virtual_memory()
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': memory_info.percent,
                'memory_available': memory_info.available / 1024 / 1024,
                'load_avg': psutil.getloadavg()
            }
        except Exception as e:
            logger.error(f"获取资源使用情况失败: {e}")
            return {}
