import logging
import colorlog
from pathlib import Path
from typing import Optional, Union
from logging.handlers import RotatingFileHandler


class LogConfig:
    """日志配置类"""
    def __init__(
        self,
        level: int = logging.DEBUG,
        log_dir: Optional[Union[str, Path]] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        console_format: str = '%(log_color)s[%(levelname)s]%(message)s',
        log_colors: Optional[dict] = None,
        file_format: str = '%(asctime)s - %(levelname)s - %(message)s'
    ):
        self.level = level
        self.log_dir = Path(log_dir) if log_dir is not None else None
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.console_format = console_format
        self.log_colors = log_colors or {
            'DEBUG': 'blue',
            'INFO': 'cyan',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'purple'
        }
        self.file_format = file_format


def _add_handler(
    logger: logging.Logger,
    handler: logging.Handler,
    level: int,
    formatter: logging.Formatter
) -> None:
    """统一配置处理器并添加到日志器"""
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


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

    # 清除已有处理器防止重复记录
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 控制台日志处理器
    console_formatter = colorlog.ColoredFormatter(
        config.console_format,
        log_colors=config.log_colors
    )
    stream_handler = logging.StreamHandler()
    _add_handler(logger, stream_handler, config.level, console_formatter)

    # 文件日志处理器
    if config.log_dir:
        try:
            config.log_dir.mkdir(parents=True, exist_ok=True)
            log_file = config.log_dir / 'onekey.log'
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
                encoding='utf-8'
            )
            file_formatter = logging.Formatter(config.file_format)
            _add_handler(logger, file_handler, config.level, file_formatter)
        except OSError as e:
            logger.error(f"Failed to initialize file handler: {e}")

    return logger

# 模块级日志实例
log = init_log()
