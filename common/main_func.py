import os
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from aiohttp import ClientSession, ConnectionTimeoutError
from common.checkcn import checkcn
from common.config import config
from common.dkey_merge import depotkey_merge
from common.migration import migrate
from common.unlock import stool_add, greenluma_add
from common.get_manifest_info import get_manifest
from common.check import check_github_api_rate_limit
from common.log import log
from common.get_steam_path import steam_path
from common.stack_error import stack_error

# 检查GreenLuma是否存在
isGreenLuma: bool = any((steam_path / dll).exists()
                  for dll in ['GreenLuma_2024_x86.dll', 'GreenLuma_2024_x64.dll', 'User32.dll'])

# 检查SteamTools是否存在
isSteamTools: bool = (steam_path / 'config' / 'stUI').is_dir()

async def fetch_branch_info(
    session: ClientSession, 
    url: str, 
    headers: Optional[Dict[str, str]]
) -> Optional[Dict[str, Any]]:
    """
    从GitHub API获取分支信息
    
    Args:
        session: aiohttp会话对象
        url: API请求URL
        headers: 请求头
        
    Returns:
        包含分支信息的字典，如果失败返回None
    """
    try:
        async with session.get(url, headers=headers, ssl=False) as response:
            if response.status == 200:
                return await response.json()
            log.error(f"获取分支信息失败，状态码: {response.status}")
            return None
    except KeyboardInterrupt:
        log.info("程序已退出")
        return None
    except ConnectionTimeoutError as e:
        log.error(f'获取信息时超时: {stack_error(e)}')
        return None
    except Exception as e:
        log.error(f'获取信息失败: {stack_error(e)}')
        return None

async def get_latest_repo_info(
    session: ClientSession,
    repos: List[str],
    app_id: str,
    headers: Optional[Dict[str, str]]
) -> Tuple[Optional[str], Optional[str]]:
    """
    获取最新的仓库信息
    
    Args:
        session: aiohttp会话对象
        repos: 仓库列表
        app_id: 应用ID
        headers: 请求头
        
    Returns:
        包含最新仓库和日期的元组
    """
    latest_date: Optional[str] = None
    selected_repo: Optional[str] = None

    for repo in repos:
        url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
        r_json = await fetch_branch_info(session, url, headers)
        if r_json and 'commit' in r_json:
            date = r_json['commit']['commit']['author']['date']
            if latest_date is None or date > latest_date:
                latest_date = date
                selected_repo = repo

    return selected_repo, latest_date

async def main(app_id: str, repos: List[str]) -> bool:
    """
    主处理函数
    
    Args:
        app_id: 应用ID
        repos: 仓库列表
        
    Returns:
        操作是否成功
    """
    app_id_list = list(filter(str.isdecimal, app_id.strip().split('-')))

    if not app_id_list:
        log.error('App ID无效')
        return False

    app_id = app_id_list[0]

    async with ClientSession() as session:
        github_token = config.get("Github_Personal_Token", "")
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None

        await checkcn(session)
        await check_github_api_rate_limit(headers, session)

        selected_repo, latest_date = await get_latest_repo_info(session, repos, app_id, headers)

        if selected_repo:
            log.info(f'选择清单仓库: {selected_repo}')
            url = f'https://api.github.com/repos/{selected_repo}/branches/{app_id}'
            r_json = await fetch_branch_info(session, url, headers)

            if r_json and 'commit' in r_json:
                sha = r_json['commit']['sha']
                url = r_json['commit']['commit']['tree']['url']
                r2_json = await fetch_branch_info(session, url, headers)

                if r2_json and 'tree' in r2_json:
                    collected_depots = []
                    for item in r2_json['tree']:
                        result = await get_manifest(sha, item['path'], steam_path, selected_repo, session)
                        collected_depots.extend(result)

                    if collected_depots:
                        if isSteamTools:
                            await migrate(st_use=True, session=session)
                            await stool_add(collected_depots, app_id)
                            log.info('找到SteamTools, 已添加解锁文件')

                        if isGreenLuma:
                            await migrate(st_use=False, session=session)
                            await greenluma_add([app_id])
                            depot_config = {'depots': {depot_id: {
                                'DecryptionKey': depot_key} for depot_id, depot_key in collected_depots}}
                            await depotkey_merge(steam_path / 'config' / 'config.vdf', depot_config)
                            if await greenluma_add([int(i) for i in depot_config['depots'] if i.isdecimal()]):
                                log.info('找到GreenLuma, 已添加解锁文件')

                        log.info(f'清单最后更新时间: {latest_date}')
                        log.info(f'入库成功: {app_id}')
                        os.system('pause')
                        return True

        log.error(f'清单下载或生成失败: {app_id}')
        os.system('pause')
        return False
