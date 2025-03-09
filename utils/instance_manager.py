import os
import sys
import logging
import fcntl
import atexit

logger = logging.getLogger(__name__)

class SingleInstanceManager:
    """
    确保只有一个机器人实例在运行
    使用文件锁定机制防止多个实例同时运行
    """
    def __init__(self, lock_file='/tmp/telegram_bot.lock'):
        self.lock_file = lock_file
        self.lock_fd = None
        self.locked = False
        
    def ensure_single_instance(self):
        """
        确保只有一个实例在运行
        如果已有实例在运行，则退出程序
        """
        try:
            # 创建或打开锁文件
            self.lock_fd = open(self.lock_file, 'w')
            
            # 尝试获取独占锁
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # 写入PID
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()
            
            # 注册退出时的清理函数
            atexit.register(self.cleanup)
            
            self.locked = True
            logger.info("成功获取实例锁，确保只有一个机器人实例在运行")
            return True
            
        except IOError:
            logger.error("另一个机器人实例已在运行，本实例将退出")
            if self.lock_fd:
                self.lock_fd.close()
            return False
    
    def cleanup(self):
        """
        清理锁文件
        """
        if self.locked and self.lock_fd:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
                os.unlink(self.lock_file)
                logger.info("已释放实例锁并清理锁文件")
            except Exception as e:
                logger.error(f"清理锁文件时出错: {e}")
