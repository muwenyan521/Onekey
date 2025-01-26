import asyncio
import aiofiles
import vdf
import os
from pathlib import Path
from typing import Dict, Any
from .log import log

lock = asyncio.Lock()


async def _read_config(config_path: Path) -> Dict[str, Any]:
    async with aiofiles.open(config_path, encoding='utf-8') as f:
        content = await f.read()
    return vdf.loads(content)


async def _write_config(config_path: Path, config: Dict[str, Any]) -> None:
    temp_path = config_path.with_name(config_path.name + '.tmp')
    try:
        async with aiofiles.open(temp_path, mode='w', encoding='utf-8') as f:
            new_context = vdf.dumps(config, pretty=True)
            await f.write(new_context)
        # 替换原文件
        await asyncio.to_thread(os.replace, temp_path, config_path)
    except Exception:
        if await asyncio.to_thread(temp_path.exists):
            await asyncio.to_thread(temp_path.unlink)
        raise


def _get_steam_config(config: Dict[str, Any]) -> Dict[str, Any]:
    software = config.get('InstallConfigStore', {}).get('Software', {})
    return next(
        (software[key] for key in software if key.lower() == 'valve'),
        None
    )


async def depotkey_merge(config_path: Path, depots_config: Dict[str, Any]) -> bool:
    """合并Steam depot配置
    
    Args:
        config_path: Steam配置文件路径
        depots_config: 要合并的depot配置
        
    Returns:
        bool: 是否合并成功
    """
    async with lock:  # 使用锁保证原子操作
        if not await asyncio.to_thread(config_path.exists):
            log.error('❌ Steam默认配置不存在，可能是没有登录账号')
            return False

        try:
            config = await _read_config(config_path)
            steam = _get_steam_config(config)
            
            if steam is None:
                log.error('❌ 找不到Steam配置，请检查配置文件')
                return False

            depots = steam.setdefault('depots', {})
            depots.update(depots_config.get('depots', {}))
            
            await _write_config(config_path, config)
            log.info('✅ 成功合并')
            return True

        except KeyboardInterrupt:
            log.info("🛑 程序已退出")
            return False
        except vdf.VDFError as e:
            log.error(f'❌ 配置文件解析失败: {e}')
            return False
        except OSError as e:  # 合并处理IOError和OSError
            log.error(f'❌ 文件操作失败: {e}')
            return False
        except Exception as e:
            log.error(f'❌ 合并失败: {e}')
            return False