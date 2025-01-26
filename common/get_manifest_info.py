from pathlib import Path
from typing import List, Tuple

import aiofiles
import vdf
from aiohttp import ClientSession

from .dl import get
from .log import log
from .stack_error import stack_error

DEPOT_CACHE_PATH_NAME = 'depotcache'


async def get_manifest(
    sha: str,
    path: str,
    steam_path: Path,
    repo: str,
    session: ClientSession
) -> List[Tuple[str, str]]:
    """获取Steam清单文件或密钥文件

    Args:
        sha: 文件SHA校验值
        path: 文件路径 (.manifest 或 Key.vdf)
        steam_path: Steam安装路径
        repo: 仓库地址
        session: aiohttp会话

    Returns:
        对于.manifest文件: 返回空列表
        对于Key.vdf文件: 返回[(depot_id, decryption_key), ...]
    """
    collected_depots: List[Tuple[str, str]] = []
    depot_cache_path = steam_path / DEPOT_CACHE_PATH_NAME

    log.debug(f'准备处理文件: {path}')

    try:
        if path.endswith('.manifest'):
            # 只在需要时创建目录
            depot_cache_path.mkdir(exist_ok=True)
            save_path = depot_cache_path / path

            if save_path.exists():
                log.warning(f'⚠️ 已存在清单: {save_path}')
                return collected_depots

            content = await get(sha, path, repo, session)
            log.info(f'✅ 清单下载成功: {path}')

            async with aiofiles.open(save_path, 'wb') as f:
                await f.write(content)

        elif path == 'Key.vdf':
            content = await get(sha, path, repo, session)
            log.info(f'✅ 密钥下载成功: {path}')

            try:
                decoded_content = content.decode('utf-8')
            except UnicodeDecodeError as e:
                log.error(f'❌ Key.vdf解码失败: {stack_error(e)}')
                raise ValueError('无效的Key.vdf编码') from e

            try:
                depots_config = vdf.loads(decoded_content)
                depots = depots_config['depots']
            except KeyError as e:
                log.error(f'❌ 缺少必要字段: {stack_error(e)}')
                raise ValueError('Key.vdf格式错误: 缺少depots字段') from e
            except vdf.VDFError as e:
                log.error(f'❌ VDF解析失败: {stack_error(e)}')
                raise ValueError('无效的Key.vdf格式') from e

            collected_depots = []
            for depot_id, depot_info in depots.items():
                try:
                    key = depot_info['DecryptionKey']
                    collected_depots.append((depot_id, key))
                except KeyError:
                    log.error(f'❌ Depot {depot_id} 缺少DecryptionKey字段')
                    raise

    except KeyboardInterrupt:
        log.info("🛑 用户中断操作")
        raise
    except Exception as e:
        log.error(f'❌ 处理失败: {path} - {stack_error(e)}')
        raise

    return collected_depots