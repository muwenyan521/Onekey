import os
import aiohttp
import ujson as json
from .log import log
from .stack_error import stack_error

def set_cn_environment(is_cn: bool) -> None:
    """设置中国区环境标识"""
    os.environ['IS_CN'] = 'yes' if is_cn else 'no'

async def checkcn(client: aiohttp.ClientSession, timeout: int = 10, retries: int = 3) -> bool:
    """智能检测用户网络区域
     
    Args:
        client: aiohttp 客户端会话
        timeout: 单次请求超时时间（秒）
        retries: 最大重试次数
        
    Returns:
        bool: 是否需要使用中国大陆CDN
    """
    url = 'https://mips.kugou.com/check/iscn?&format=json'
    
    for attempt in range(1, retries+1):
        try:
            async with client.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                try:
                    body = json.loads(await response.read())
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON response")

                # 处理响应数据缺失关键字段的情况
                if 'flag' not in body:
                    raise KeyError("Missing 'flag' field in response")
                
                # 解析网络区域标识
                is_in_china = bool(body['flag'])
                country = body.get('country', '未知地区')

                # 根据结果设置环境并记录日志
                log_msg, cn_flag = (
                    (f"🌍 检测到非中国大陆地区({country})，已切换至国际CDN", False)
                    if not is_in_china else
                    ("🌍 检测到中国大陆地区，已启用国内CDN", True)
                )
                log.info(log_msg)
                set_cn_environment(cn_flag)
                return cn_flag

        except KeyboardInterrupt:
            log.info("🛑 用户主动中断检测流程")
            return False
            
        except (aiohttp.ClientTimeout, aiohttp.ClientError) as e:
            error_type = "请求超时" if isinstance(e, aiohttp.ClientTimeout) else "网络连接异常"
            log.warning(f"⏳ {error_type}（{stack_error(e)}），正在进行第 {attempt}/{retries} 次重试...")
            if attempt == retries:
                log.warning("⚠️ 达到最大重试次数，默认启用中国大陆模式")
                set_cn_environment(True)
                return True

        except (KeyError, ValueError) as e:
            log.warning(f"⚠️ 响应数据异常（{stack_error(e)}）")
            if attempt == retries:
                log.warning("⚠️ 数据解析失败，默认启用中国大陆模式")
                set_cn_environment(True)
                return True

    return True  # 冗余保护，实际不会执行到此