import os
import time
import hashlib
import asyncio
from typing import Optional, List
from aiohttp import ClientError, ClientSession
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, DownloadColumn
import aiofiles
from .log import log

class NotFoundError(Exception):
    """当资源不存在时抛出异常"""
    def __init__(self, url):
        super().__init__(f"Resource not found at {url}")
        self.url = url

class HttpError(Exception):
    """HTTP错误异常"""
    def __init__(self, status_code: int, url: str):
        super().__init__(f"HTTP Error {status_code} at {url}")
        self.status_code = status_code
        self.url = url

class Downloader:
    @staticmethod
    def get_cn_urls(repo: str, sha: str, path: str) -> List[str]:
        return [
            f'https://jsdelivr.pai233.top/gh/{repo}@{sha}/{path}',
            f'https://cdn.jsdmirror.com/gh/{repo}@{sha}/{path}',
            f'https://raw.gitmirror.com/{repo}/{sha}/{path}',
            f'https://raw.dgithub.xyz/{repo}/{sha}/{path}',
            f'https://gh.akass.cn/{repo}/{sha}/{path}'
        ]

    @staticmethod
    def get_default_url(repo: str, sha: str, path: str) -> str:
        return f'https://raw.githubusercontent.com/{repo}/{sha}/{path}'

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir
        self.memory_cache = {}
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_path(self, cache_key: str) -> str:
        """生成安全的缓存文件路径"""
        filename = hashlib.md5(cache_key.encode()).hexdigest()
        return os.path.join(self.cache_dir, filename) if self.cache_dir else ""

    async def _try_read_cache(self, cache_key: str) -> Optional[bytearray]:
        """尝试从缓存读取内容"""
        # 检查内存缓存
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]

        # 检查磁盘缓存
        if self.cache_dir:
            cache_path = self._get_cache_path(cache_key)
            try:
                async with aiofiles.open(cache_path, 'rb') as f:
                    content = bytearray(await f.read())
                    self.memory_cache[cache_key] = content
                    return content
            except FileNotFoundError:
                pass
            except Exception as e:
                log.error(f"缓存读取失败: {str(e)}")
        return None

    async def _write_cache(self, cache_key: str, content: bytearray):
        """写入缓存"""
        self.memory_cache[cache_key] = content
        if self.cache_dir:
            cache_path = self._get_cache_path(cache_key)
            try:
                async with aiofiles.open(cache_path, 'wb') as f:
                    await f.write(content)
            except Exception as e:
                log.error(f"缓存写入失败: {str(e)}")

    async def _download_url(self, url: str, session: ClientSession, path: str, 
                           chunk_size: int, progress: Progress, task: int) -> bytearray:
        """从单个URL下载内容"""
        async with session.get(url, ssl=False, timeout=30) as response:
            if response.status == 200:
                content = bytearray()
                async for chunk in response.content.iter_chunked(chunk_size):
                    content.extend(chunk)
                    progress.update(task, advance=len(chunk))
                return content
            
            if response.status == 404:
                raise NotFoundError(url)
            raise HttpError(response.status, url)

    async def get(self, sha: str, path: str, repo: str, session: ClientSession,
                 chunk_size: int = 1024, timeout: int = 30) -> bytearray:
        cache_key = f"{repo}@{sha}/{path}"
        
        # 尝试读取缓存
        cached = await self._try_read_cache(cache_key)
        if cached is not None:
            return cached

        # 生成URL列表
        url_list = (
            self.get_cn_urls(repo, sha, path) 
            if os.environ.get('IS_CN') == 'yes' 
            else [self.get_default_url(repo, sha, path)]
        )

        # 初始化进度条
        with Progress(
            TextColumn("[progress.description]{task.description}", style="#66CCFF"),
            BarColumn(style="#66CCFF", complete_style="#4CE49F", finished_style="#2FE9D9"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%", style="#66CCFF"),
            TimeElapsedColumn(),
            DownloadColumn(),
        ) as progress:
            task_id = progress.add_task(f"📥 下载 {path} 中...", total=0)

            retry_count = 3
            errors = []
            remaining_urls = url_list.copy()

            while retry_count > 0 and remaining_urls:
                current_errors = []
                for url in list(remaining_urls):
                    try:
                        # 更新进度条描述为当前尝试的URL
                        progress.update(task_id, description=f"📥 尝试 {url}")

                        # 获取内容并更新进度条
                        content = await self._download_url(
                            url, session, path, chunk_size, progress, task_id
                        )
                        
                        # 写入缓存并返回内容
                        await self._write_cache(cache_key, content)
                        return content

                    except NotFoundError as e:
                        log.warning(f"⚠️ 资源不存在: {e.url}")
                        remaining_urls.remove(url)
                    except (ClientError, HttpError, asyncio.TimeoutError) as e:
                        error_msg = f"{type(e).__name__}: {str(e)}"
                        current_errors.append(f"URL {url}: {error_msg}")
                        log.error(f"❌ 下载失败: {path} @ {url} - {error_msg}")

                # 记录本轮错误并准备重试
                if current_errors:
                    errors.extend(current_errors)
                    retry_count -= 1
                    if retry_count > 0 and remaining_urls:
                        log.warning(f"⚠️ 剩余重试次数: {retry_count} - {path}")
                        await asyncio.sleep(1)  # 重试间隔

        # 所有尝试失败后抛出异常
        error_log = "\n".join(errors)
        log.error(f"❌ 无法下载 {path}，所有尝试失败:\n{error_log}")
        raise Exception(f"无法下载 {path}，详细错误:\n{error_log}")