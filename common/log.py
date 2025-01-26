import logging
import colorlog
from pathlib import Path
from typing import Optional

class LogConfig:
    """日志配置类"""
    def __init__(self):
        self.level: int = logging.DEBUG
        self.log_dir: Optional[Path] = None
        self.max_bytes: int = 10 * 1024 * 1024  # 10MB
        self.backup_count: int = 5

DEFAULT_LOG_FORMAT = '%(log_color)s%(asctime)s - %(levelname)s - %(message)s'
LOG_COLORS = {
    'DEBUG': 'blue',
    'INFO': 'cyan',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'purple',
}

def init_log(config: Optional[LogConfig] = None) -> logging.Logger:
    """
    初始化日志系统
    
    Args:
        config: 日志配置对象，如果为None则使用默认配置
        
    Returns:
        配置好的Logger对象
    """
    if config is None:
        config = LogConfig()

    logger = logging.getLogger('Onekey')
    logger.setLevel(config.level)

    # 清除已有处理器
    logger.handlers.clear()

    # 控制台日志处理器
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(config.level)
    fmt = colorlog.ColoredFormatter(DEFAULT_LOG_FORMAT, log_colors=LOG_COLORS)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    # 文件日志处理器
    if config.log_dir:
        config.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = config.log_dir / 'onekey.log'
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(config.level)
        file_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

    return logger

log = init_log()
