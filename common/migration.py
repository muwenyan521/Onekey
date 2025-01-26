import asyncio
import aiofiles
import subprocess
from aiohttp import ClientSession, ClientTimeout, ClientError
from pathlib import Path
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from .log import log
from .get_steam_path import get_cached_steam_path

# 初始化Steam路径
steam_path = get_cached_steam_path()
if steam_path is None:
    raise RuntimeError("无法获取Steam路径")

# 常量定义
DIRECTORY = Path(steam_path) / "config" / "stplug-in"
TEMP_PATH = Path('./temp')
SETUP_URL = 'https://steamtools.net/res/SteamtoolsSetup.exe'
SETUP_FILE = TEMP_PATH / 'SteamtoolsSetup.exe'
CHUNK_SIZE = 8192
TIMEOUT = ClientTimeout(total=30)


async def download_setup_file(session: ClientSession) -> bool:
    """下载安装程序并返回是否成功"""
    log.info('📥 开始下载 SteamTools 安装程序...')
    temp_file = SETUP_FILE.with_suffix('.tmp')

    try:
        async with session.get(SETUP_URL, timeout=TIMEOUT, raise_for_status=True) as response:
            total_size = int(response.headers.get('Content-Length', 0))

            with Progress(
                TextColumn("[progress.description]{task.description}", style="#66CCFF"),
                BarColumn(style="#66CCFF", complete_style="#4CE49F", finished_style="#2FE9D9"),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%", style="#66CCFF"),
                TimeElapsedColumn(),
            ) as progress:
                task = progress.add_task("📥 下载安装程序中...", total=total_size)

                try:
                    async with aiofiles.open(temp_file, 'wb') as f:
                        async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                            await f.write(chunk)
                            progress.update(task, advance=len(chunk))
                except Exception as e:
                    log.error(f'❌ 下载过程中断: {e}')
                    temp_file.unlink(missing_ok=True)
                    return False

            # 重命名临时文件
            temp_file.rename(SETUP_FILE)
            log.info('✅ 安装程序下载完成')
            return True

    except ClientError as e:
        log.error(f'❌ 网络错误: {e}')
    except asyncio.TimeoutError:
        log.error('⏳ 下载超时')
    except Exception as e:
        log.error(f'❌ 未知错误: {e}')
    
    return False


async def migrate_files():
    """迁移旧版本文件"""
    for file in DIRECTORY.iterdir():
        if file.is_file() and file.name.startswith("Onekey_unlock_"):
            new_name = file.name[len("Onekey_unlock_"):]
            try:
                file.rename(DIRECTORY / new_name)
                log.info(f'✅ 重命名成功: {file.name} -> {new_name}')
            except Exception as e:
                log.error(f'❌ 重命名失败 {file.name}: {e}')


async def install_steamtools(session: ClientSession):
    """执行安装程序并清理临时文件"""
    TEMP_PATH.mkdir(parents=True, exist_ok=True)

    if not await download_setup_file(session):
        log.error('❌ 安装程序下载失败，终止安装')
        return

    try:
        # 异步执行安装程序
        process = await asyncio.create_subprocess_exec(
            str(SETUP_FILE),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # 等待安装完成
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            log.error(f'❌ 安装失败，错误码: {process.returncode}')
            log.debug(f'标准输出: {stdout.decode().strip()}')
            log.debug(f'标准错误: {stderr.decode().strip()}')
            return

        log.info('✅ SteamTools 安装成功')
    except Exception as e:
        log.error(f'❌ 安装过程中发生错误: {e}')
    finally:
        # 清理临时文件
        for f in TEMP_PATH.glob('*'):
            try:
                f.unlink()
            except Exception as e:
                log.error(f'❌ 清理临时文件失败 {f}: {e}')
        try:
            TEMP_PATH.rmdir()
        except Exception as e:
            log.error(f'❌ 清理临时目录失败: {e}')


async def migrate(st_use: bool, session: ClientSession) -> None:
    """主迁移函数"""
    if not st_use:
        log.info('🚫 未使用 SteamTools, 停止迁移')
        return

    log.info('🔍 检测到正在使用 SteamTools, 尝试迁移旧文件')
    
    if DIRECTORY.exists():
        await migrate_files()
        return

    log.warning('⚠️ 未找到安装目录，尝试重新安装')
    await install_steamtools(session)