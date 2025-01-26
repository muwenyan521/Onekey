import os
import re
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from aiohttp import ClientSession, ClientError
from common.checkcn import checkcn
from common.config import config
from common.dkey_merge import depotkey_merge
from common.migration import migrate
from common.unlock import stool_add, greenluma_add
from common.get_manifest_info import get_manifest
from common.check import check_github_api_rate_limit
from common.log import log
from common.get_steam_path import get_cached_steam_path
from common.stack_error import stack_error

# 获取Steam路径
steam_path = get_cached_steam_path()
if steam_path is None:
    raise RuntimeError("无法获取Steam路径")

# 检查GreenLuma存在性
is_green_luma: bool = any(
    (steam_path / dll).exists()
    for dll in ['GreenLuma_2024_x86.dll', 'GreenLuma_2024_x64.dll']
)

# 检查SteamTools存在性
is_steam_tools: bool = (steam_path / 'config' / 'stUI').is_dir()

async def fetch_branch_info(
    session: ClientSession,
    url: str,
    headers: Optional[Dict[str, str]]
) -> Optional[Dict[str, Any]]:
    """获取GitHub分支信息"""
    try:
        async with session.get(url, headers=headers, ssl=False) as response:
            if response.status == 200:
                return await response.json()
            log.error(f"❌ 获取分支信息失败，状态码: {response.status}")
            return None
    except ClientError as e:
        log.error(f'🌐 网络请求异常: {stack_error(e)}')
        return None
    except Exception as e:
        log.error(f'❌ 获取信息失败: {stack_error(e)}')
        return None

async def get_latest_repo_info(
    session: ClientSession,
    repos: List[str],
    app_id: str,
    headers: Optional[Dict[str, str]]
) -> Tuple[Optional[str], Optional[str]]:
    """获取最新仓库信息"""
    urls = [f'https://api.github.com/repos/{repo}/branches/{app_id}' for repo in repos]
    tasks = [fetch_branch_info(session, url, headers) for url in urls]
    results = await asyncio.gather(*tasks)
    
    latest_date = None
    selected_repo = None
    for repo, r_json in zip(repos, results):
        if r_json and r_json.get('commit'):
            commit_date = r_json['commit']['commit']['author']['date']
            if not latest_date or commit_date > latest_date:
                latest_date = commit_date
                selected_repo = repo
    return selected_repo, latest_date

async def process_repository_items(
    session: ClientSession,
    r_json: Dict[str, Any],
    sha: str,
    steam_path: Path,
    selected_repo: str
) -> List[Tuple[str, str]]:
    """并发处理仓库条目"""
    tasks = [
        get_manifest(sha, item['path'], steam_path, selected_repo, session)
        for item in r_json.get('tree', [])
    ]
    results = await asyncio.gather(*tasks)
    return [item for sublist in results for item in sublist]

async def handle_steam_tools(
    session: ClientSession,
    collected_depots: List[Tuple[str, str]],
    app_id: str
) -> None:
    """处理SteamTools相关操作"""
    await migrate(st_use=True, session=session)
    await stool_add(collected_depots, app_id)
    log.info('✅ 找到SteamTools，已添加解锁文件')

async def handle_green_luma(
    session: ClientSession,
    collected_depots: List[Tuple[str, str]],
    app_id: str,
    steam_path: Path
) -> None:
    """处理GreenLuma相关操作"""
    await migrate(st_use=False, session=session)
    
    # 处理应用ID
    if app_id.isdecimal():
        if await greenluma_add([int(app_id)]):
            log.info(f'✅ 已添加应用ID {app_id} 到GreenLuma')
    
    # 处理Depot密钥
    depot_config = {
        'depots': {
            depot_id: {'DecryptionKey': depot_key}
            for depot_id, depot_key in collected_depots
        }
    }
    await depotkey_merge(steam_path / 'config' / 'config.vdf', depot_config)
    
    # 处理Depot ID
    depot_ids = []
    for depot_id in depot_config['depots']:
        if depot_id.isdecimal():
            depot_ids.append(int(depot_id))
        else:
            log.warning(f'⚠️ 忽略非数字Depot ID: {depot_id}')
    
    if depot_ids and await greenluma_add(depot_ids):
        log.info('✅ 已添加Depot ID到GreenLuma')

async def main(app_id: str, repos: List[str]) -> bool:
    """主处理流程"""
    # 清理并验证App ID
    match = re.search(r'\d+', app_id.strip())
    if not match:
        log.error('❌ App ID无效')
        return False
    app_id = match.group()

    async with ClientSession() as session:
        # 配置API请求头
        github_token = config.get("Github_Personal_Token", "")
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None

        # 执行前置检查
        await checkcn(session)
        await check_github_api_rate_limit(headers, session)

        # 获取最新仓库信息
        selected_repo, latest_date = await get_latest_repo_info(session, repos, app_id, headers)
        if not selected_repo:
            log.error('❌ 未找到有效的仓库信息')
            return False

        log.info(f'✅ 选择清单仓库: {selected_repo}')
        branch_url = f'https://api.github.com/repos/{selected_repo}/branches/{app_id}'
        branch_info = await fetch_branch_info(session, branch_url, headers)

        if not branch_info or not branch_info.get('commit'):
            return False

        # 处理仓库条目
        sha = branch_info['commit']['sha']
        tree_url = branch_info['commit']['commit']['tree']['url']
        tree_info = await fetch_branch_info(session, tree_url, headers)
        if not tree_info or not tree_info.get('tree'):
            return False

        collected_depots = await process_repository_items(session, tree_info, sha, steam_path, selected_repo)
        if not collected_depots:
            log.error('❌ 未找到有效的Depot信息')
            return False

        # 执行解锁操作
        if is_steam_tools:
            await handle_steam_tools(session, collected_depots, app_id)
        if is_green_luma:
            await handle_green_luma(session, collected_depots, app_id, steam_path)

        log.info(f'📅 清单最后更新时间: {latest_date}')
        log.info(f'✅ 入库成功: {app_id}')
        os.system('pause')
        return True