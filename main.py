import sys
import os
import asyncio
import re
from typing import List

from colorama import Fore, Back, Style
from colorama import init as cinit
from common.log import log
from common.stack_error import stack_error
from common.init_text import init
from common.main_func import main

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 异步锁
lock = asyncio.Lock()

# 初始化
init()
cinit()

# GitHub仓库列表
repos: List[str] = [
    'ikun0014/ManifestHub',
    'Auiowu/ManifestAutoUpdate', 
    'tymolu233/ManifestAutoUpdate',
    'ltsj/ManifestAutoUpdate'
]

def prompt_app_id() -> str:
    """
    提示用户输入AppID并进行验证
    
    Returns:
        有效的AppID字符串
    """
    while True:
        app_id = input(f"{Fore.CYAN}{Back.BLACK}{
                       Style.BRIGHT}请输入游戏AppID: {Style.RESET_ALL}").strip()
        if re.match(r'^\d+$', app_id):
            return app_id
        print(f"{Fore.RED}无效的AppID, 请输入数字!{Style.RESET_ALL}")

async def main_loop() -> None:
    """
    主循环，持续获取AppID并处理
    """
    while True:
        try:
            app_id = prompt_app_id()
            await main(app_id, repos)
        except KeyboardInterrupt:
            log.info("程序已退出")
            break
        except EOFError:
            break
        except Exception as e:
            log.error(f"处理AppID时发生错误: {stack_error(e)}")
            await asyncio.sleep(1)

async def run() -> None:
    """
    主运行函数，处理程序生命周期
    """
    try:
        log.info('App ID可以在SteamDB或Steam商店链接页面查看')
        await main_loop()
    except KeyboardInterrupt:
        log.info("程序已退出")
    except Exception as e:
        log.error(f'发生错误: {stack_error(e)}, 将在5秒后退出')
        await asyncio.sleep(5)

if __name__ == '__main__':
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("程序已退出")
    except SystemExit:
        sys.exit()
