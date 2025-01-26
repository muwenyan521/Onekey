import os
import winreg
from pathlib import Path
from typing import Optional
from functools import lru_cache
from .log import log
from .config import config
from .stack_error import stack_error

# 常量定义
STEAM_REG_PATH = r'Software\Valve\Steam'
CUSTOM_STEAM_PATH_KEY = "Custom_Steam_Path"

@lru_cache(maxsize=1)
def get_steam_path() -> Optional[Path]:
    """获取经过验证的Steam安装路径，优先使用用户配置的自定义路径。
    
    返回:
        Optional[Path]: 有效的Steam路径，若获取失败或路径无效则返回None
    
    异常:
        KeyboardInterrupt: 用户主动中断操作时抛出
    """
    try:
        # 优先检查用户配置的自定义路径
        custom_steam_path = config.get(CUSTOM_STEAM_PATH_KEY, "").strip()
        if custom_steam_path:
            custom_path = Path(custom_steam_path)
            if custom_path.exists():
                log.debug(f"使用自定义Steam路径: {custom_path}")
                return custom_path
            else:
                log.error(f"❌ 自定义Steam路径不存在: {custom_path}")
                return None

        # 从注册表获取默认路径
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STEAM_REG_PATH) as key:
            steam_path_value = winreg.QueryValueEx(key, 'SteamPath')[0]
            steam_path = Path(steam_path_value)
            
            if steam_path.exists():
                log.debug(f"使用注册表Steam路径: {steam_path}")
                return steam_path
            else:
                log.error(f"❌ 注册表中的Steam路径不存在: {steam_path}")
                return None

    except FileNotFoundError:
        log.error("❌ 未找到Steam注册表项，可能未安装Steam或安装路径异常")
        return None
    except PermissionError as e:
        log.error(f"❌ 访问Steam注册表时权限不足: {stack_error(e)}")
        return None
    except Exception as e:
        log.error(f'❌ 获取Steam路径时发生未知错误: {stack_error(e)}')
        return None