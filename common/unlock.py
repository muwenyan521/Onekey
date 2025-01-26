import os
import asyncio
import aiofiles
from pathlib import Path
from typing import List, Tuple
import aiofiles.os as aios
from .get_steam_path import get_cached_steam_path
from .log import log

lock = asyncio.Lock()

async def _write_lua_file(filepath: Path, app_id: str, depot_data: List[Tuple[str, str]]) -> None:
    """生成Lua解锁文件的辅助函数"""
    content = [f'addappid({app_id}, 1, "None")']
    content.extend(f'addappid({depot_id}, 1, "{depot_key}")' for depot_id, depot_key in depot_data)
    
    async with aiofiles.open(filepath, mode="w", encoding="utf-8") as f:
        await f.write('\n'.join(content))

async def _run_luapacka(luapacka_path: Path, lua_filepath: Path) -> bool:
    """异步执行luapacka的辅助函数"""
    try:
        proc = await asyncio.create_subprocess_exec(
            str(luapacka_path),
            str(lua_filepath),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            log.error(f'❌ 调用失败: {stderr.decode().strip()}')
            return False
        return True
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.error(f'❌ 执行luapacka时发生错误: {e}')
        return False

async def stool_add(depot_data: List[Tuple[str, str]], app_id: str) -> bool:
    """生成并处理SteamTools解锁文件"""
    steam_path = get_cached_steam_path()
    if not steam_path:
        return False

    lua_filename = f"{app_id}.lua"
    lua_filepath = steam_path / "config" / "stplug-in" / lua_filename
    luapacka_path = steam_path / "config" / "stplug-in" / "luapacka.exe"

    async with lock:
        log.info(f'📄 SteamTools 解锁文件生成: {lua_filepath}')
        try:
            # 生成Lua文件
            await _write_lua_file(lua_filepath, app_id, depot_data)
            log.info(f'🔄 正在处理文件: {lua_filepath}')

            # 异步执行打包程序
            if not await _run_luapacka(luapacka_path, lua_filepath):
                return False

            log.info('✅ 处理完成')
            return True
        except asyncio.CancelledError:
            log.info("🛑 用户中断操作")
            return False
        except Exception as e:
            log.error(f'❌ 处理过程出现错误: {e}')
            return False
        finally:
            # 清理临时文件
            if await aios.path.exists(lua_filepath):
                await aios.remove(lua_filepath)
                log.info(f'🗑️ 删除临时文件: {lua_filepath}')

async def greenluma_add(depot_id_list: List[str]) -> bool:
    """处理GreenLuma配置文件"""
    steam_path = get_cached_steam_path()
    if not steam_path:
        return False

    app_list_path = steam_path / 'AppList'
    
    try:
        await aios.makedirs(app_list_path, exist_ok=True)

        # 清理旧文件
        async for file in aios.scandir(app_list_path):
            if file.name.endswith('.txt'):
                await aios.remove(file.path)

        # 读取现有配置
        depot_dict = {}
        async for file in aios.scandir(app_list_path):
            if file.is_file() and file.name.endswith('.txt'):
                stem = Path(file.name).stem
                if stem.isdecimal():
                    async with aiofiles.open(file.path, 'r', encoding='utf-8') as f:
                        depot_id = (await f.read()).strip()
                        depot_dict[int(stem)] = int(depot_id)

        # 生成新配置
        for depot_id in map(int, depot_id_list):
            if depot_id not in depot_dict.values():
                # 寻找可用索引
                index = max(depot_dict.keys(), default=-1) + 1
                while index in depot_dict:
                    index += 1

                # 异步写入新文件
                file_path = app_list_path / f'{index}.txt'
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(str(depot_id))
                depot_dict[index] = depot_id

        return True
    except asyncio.CancelledError:
        log.info("🛑 用户中断操作")
        return False
    except Exception as e:
        log.error(f'❌ 处理时出错: {e}')
        return False