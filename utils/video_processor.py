import os
import logging
import asyncio
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, max_size_mb: int = 50):
        self.max_size_mb = max_size_mb

    async def compress_video(self, input_path: str) -> Optional[str]:
        """压缩视频文件"""
        try:
            # 检查输入文件是否存在
            if not os.path.exists(input_path):
                logger.error(f"输入文件不存在: {input_path}")
                return None

            # 获取文件大小（MB）
            file_size = os.path.getsize(input_path) / (1024 * 1024)
            if file_size <= self.max_size_mb:
                return input_path

            # 创建输出文件路径
            output_path = f"{os.path.splitext(input_path)[0]}_compressed.mp4"
            
            # 计算目标比特率（kbps）
            target_size = self.max_size_mb * 8192  # 将MB转换为kbit
            duration = await self._get_video_duration(input_path)
            if not duration:
                return None
            
            bitrate = int(target_size / duration)
            
            # 使用ffmpeg压缩视频
            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264',
                '-b:v', f'{bitrate}k',
                '-preset', 'medium',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',  # 覆盖已存在的文件
                output_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"视频压缩失败: {stderr.decode()}")
                return None

            # 检查压缩后的文件大小
            compressed_size = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"视频压缩完成: {file_size:.1f}MB -> {compressed_size:.1f}MB")
            
            # 删除原文件
            os.remove(input_path)
            return output_path

        except Exception as e:
            logger.error(f"视频压缩过程出错: {e}")
            return None

    async def _get_video_duration(self, video_path: str) -> Optional[float]:
        """获取视频时长（秒）"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"获取视频时长失败: {stderr.decode()}")
                return None
                
            duration = float(stdout.decode().strip())
            return duration

        except Exception as e:
            logger.error(f"获取视频时长出错: {e}")
            return None

    @staticmethod
    async def check_video_integrity(file_path: str) -> bool:
        """检查视频文件完整性"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_type',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            return process.returncode == 0 and stdout.decode().strip() == 'video'
            
        except Exception as e:
            logger.error(f"检查视频完整性失败: {e}")
            return False
