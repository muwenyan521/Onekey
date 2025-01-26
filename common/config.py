import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import ujson as json
from .stack_error import stack_error
from .log import log

DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "Custom_Steam_Path": "",
    "QA1": "温馨提示: Github_Personal_Token可在Github设置的最底下开发者选项找到，详情看教程",
    "教程": "https://ikunshare.com/Onekey_tutorial"
}

class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or "./config.json").absolute()
        
    def gen_config_file(self) -> None:
        """生成默认配置文件"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(
                    DEFAULT_CONFIG,
                    f,
                    indent=2,
                    ensure_ascii=False,
                    escape_forward_slashes=False
                )
            log.info('📄 配置文件已生成，请填写后重新启动程序')
        except (OSError, TypeError, ValueError) as e:
            log.error(f'❌ 配置文件生成失败: {stack_error(e)}')
            sys.exit(1)
        except KeyboardInterrupt:
            log.info("🛑 程序已退出")
            sys.exit(0)

    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_path.exists():
            log.warning("⚠️ 配置文件不存在，正在生成默认配置...")
            self.gen_config_file()
            log.info("🛑 请填写配置文件后重新启动程序")
            sys.exit(1)

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            log.error(f"❌ 配置文件加载失败: {stack_error(e)}")
            try:
                self.config_path.unlink(missing_ok=True)
                log.warning("⚠️ 已删除损坏的配置文件")
            except OSError as del_err:
                log.error(f"❌ 无法删除损坏的配置文件: {stack_error(del_err)}")
            self.gen_config_file()
            log.info("🛑 配置文件已重置，请修改后重新启动")
            sys.exit(1)
        except KeyboardInterrupt:
            log.info("🛑 程序已退出")
            sys.exit(0)

# 单例配置管理器实例
config_manager = ConfigManager()

def get_config() -> Dict[str, Any]:
    """同步获取配置"""
    return config_manager.load_config()