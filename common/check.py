import asyncio
import time
from typing import Dict, Any, Optional
import ujson as json
from aiohttp import ClientError, ClientSession
from .log import log
from .stack_error import stack_error

GITHUB_API_RATE_LIMIT_URL = 'https://api.github.com/rate_limit'
CACHE_EXPIRE_TIME = 60  # 缓存过期时间60秒

class RateLimitCache:
    """GitHub API请求限制缓存"""
    def __init__(self):
        self._cache = None
        self._last_update = 0.0

    @property
    def is_expired(self) -> bool:
        return time.monotonic() - self._last_update > CACHE_EXPIRE_TIME

    def get(self) -> Optional[Dict[str, Any]]:
        return self._cache if not self.is_expired else None

    def set(self, data: Dict[str, Any]) -> None:
        self._cache = data
        self._last_update = time.monotonic()

rate_limit_cache = RateLimitCache()

def _process_rate_limit(data: Dict[str, Any]) -> None:
    """处理GitHub API请求限制数据"""
    rate = data.get('resources', {}).get('core', data.get('rate', {}))
    remaining = rate.get('remaining', 0)
    reset_ts = rate.get('reset', int(time.time()))
    reset_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reset_ts))

    log.info(f'[GitHub API] 剩余请求次数: {remaining}')
    
    if remaining <= 0:
        log.warning(
            f'[GitHub API] 请求限额已用尽，将在 {reset_str} 重置\n'
            '建议生成GitHub Token并配置在config.py中'
        )

async def check_github_api_rate_limit(
    headers: Dict[str, str],
    session: ClientSession,
    max_retries: int = 3
) -> None:
    """检查GitHub API请求限制，带智能重试机制"""
    try:
        if (cached := rate_limit_cache.get()):
            log.debug('[GitHub API] 使用缓存数据')
            _process_rate_limit(cached)
            return

        for attempt in range(max_retries):
            try:
                async with session.get(GITHUB_API_RATE_LIMIT_URL, headers=headers, ssl=False) as resp:
                    # 优先处理非200状态码
                    if resp.status != 200:
                        await _handle_non_200_response(resp, attempt, max_retries)
                        continue

                    # 处理成功响应
                    try:
                        data = await resp.json(loads=json.loads)
                    except json.JSONDecodeError:
                        log.warning('响应数据非JSON格式，尝试文本解析')
                        data = await _parse_fallback_response(resp)

                    rate_limit_cache.set(data)
                    _process_rate_limit(data)
                    return

            except (ClientError, asyncio.TimeoutError) as e:
                await _handle_retryable_error(e, attempt, max_retries)

    except KeyboardInterrupt:
        log.info("🛑 用户中断操作")
        raise
    except Exception as e:
        log.error(f'❌ 最终错误: {stack_error(e)}')
        raise

async def _handle_non_200_response(resp, attempt: int, max_retries: int) -> None:
    """处理非200响应"""
    error_msg = f"[GitHub API] 异常状态码: {resp.status}"
    
    try:
        error_data = await resp.json(loads=json.loads)
        error_msg += f", 信息: {error_data.get('message', '未知错误')}"
    except json.JSONDecodeError:
        error_msg += ", 响应内容非JSON格式"

    log.error(error_msg)
    
    # 对特定状态码进行特殊处理
    if resp.status in (401, 403):
        raise PermissionError("认证失败，请检查Token配置")
    elif resp.status == 429:
        reset_ts = int(resp.headers.get('X-RateLimit-Reset', time.time() + 60))
        retry_after = max(reset_ts - int(time.time()), 1)
        log.warning(f"🔄 将在 {retry_after} 秒后自动重试")
        await asyncio.sleep(retry_after)
    else:
        if attempt < max_retries - 1:
            wait = 2 ** (attempt + 1)
            log.info(f"⏳ 第 {attempt+1}/{max_retries} 次重试，等待 {wait}s...")
            await asyncio.sleep(wait)

async def _parse_fallback_response(resp) -> Dict:
    """备用的响应解析方法"""
    text = await resp.text()
    return {'rate': {
        'remaining': int(resp.headers.get('X-RateLimit-Remaining', 0)),
        'reset': int(resp.headers.get('X-RateLimit-Reset', time.time()))
    }}

async def _handle_retryable_error(e: Exception, attempt: int, max_retries: int) -> None:
    """处理可重试的错误"""
    log.warning(f'⚠️ 网络错误: {stack_error(e)}')
    if attempt < max_retries - 1:
        wait = 2 ** (attempt + 1)
        log.info(f"⏳ 第 {attempt+1}/{max_retries} 次重试，等待 {wait}s...")
        await asyncio.sleep(wait)
    else:
        raise ConnectionError(f"🚨 达到最大重试次数 {max_retries}") from e