from .log import log

BANNER = """
  _____   __   _   _____   _   _    _____  __    __ 
 /  _  \\ |  \\ | | | ____| | | / /  | ____| \\ \\  / /
 | | | | |   \\| | | |__   | |/ /   | |__    \\ \\/ / 
 | | | | | |\\   | |  __|  | |\\ \\   |  __|    \\  /  
 | |_| | | | \\  | | |___  | | \\ \\  | |___    / /   
 \\_____/ |_|  \\_| |_____| |_|  \\_\\ |_____|  /_/    
"""

PROJECT_INFO = {
    "author": "ikun0014",
    "maintainer": "muwenyan521",
    "version": "1.3.6",
    "license": "GNU General Public License v3",
    "github": "https://github.com/muwenyan521/Onekey",
    "website": "ikunshare.com",
    "warning": "本项目完全开源免费, 如果你在淘宝, QQ群内通过购买方式获得, 你就被骗了",
    "telegram": "https://t.me/ikunshare_qun"
}

LOG_ENTRIES = [
    ('info', '👤 原作者: {author} 维护人: {maintainer}'),
    ('warning', '本项目采用{license}开源许可证，请勿用于商业用途'),
    ('info', '📦 版本: {version}'),
    ('info', '🌐 项目Github仓库: {github}'),
    ('info', '🏠 官网: {website}'),
    ('warning', '🚨 {warning}\n   交流群组:\n    {telegram}'),
]

def init() -> None:
    log.info(BANNER)
    
    for level, template in LOG_ENTRIES:
        message = template.format(**PROJECT_INFO)
        if level == 'info':
            log.info(message)
        else:
            log.warning(message)