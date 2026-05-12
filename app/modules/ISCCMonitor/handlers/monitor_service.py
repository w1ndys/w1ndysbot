"""ISCC 擂台赛监控核心逻辑：抓取、对比、落库、通知管理员。"""

import asyncio
from typing import Optional

from api.message import send_private_msg
from logger import logger
from utils.generate import generate_text_message

from .. import MODULE_NAME
from .data_manager import DataManager
from .iscc_monitor_client import (
    ARENA_TRACK,
    ISCCFetchError,
    ISCCMonitorClient,
    TeamArenaInfo,
)


async def run_once(
    websocket,
    owner_id: str,
    manual_trigger: bool = False,
) -> dict:
    """执行一次全量监控轮询。

    - 读取所有监控目标和当前 session。
    - 逐个拉取 `/teamarena/<team_id>` 页面，对比数据库里已知的通过题目。
    - 有新提交时通过私聊发给 `owner_id`；
      当 `manual_trigger` 为 True 时，即使没有变化也会发送一条状态反馈。

    返回一个简单统计字典，便于调用方展示或写日志。
    """
    if not owner_id:
        logger.warning(f"[{MODULE_NAME}]未配置 OWNER_ID，跳过监控轮询")
        return {"targets": 0, "new_submits": 0, "errors": 0}

    with DataManager() as dm:
        targets = dm.list_targets()
        session = dm.get_session()

    if not targets:
        if manual_trigger:
            await _send(
                websocket,
                owner_id,
                "ISCC 擂台赛监控：当前未配置任何监控 team id，"
                "可以通过 `isccm添加 <team_id> [备注]` 添加。",
            )
        return {"targets": 0, "new_submits": 0, "errors": 0}

    client = ISCCMonitorClient(session_cookie=session)
    total_new = 0
    total_errors = 0
    manual_lines: list[str] = []

    for target in targets:
        team_id = target["team_id"]
        remark = target.get("remark") or ""

        try:
            info = await client.fetch_team_arena(team_id)
        except ISCCFetchError as e:
            total_errors += 1
            logger.warning(f"[{MODULE_NAME}]抓取 team {team_id} 失败: {e}")
            if manual_trigger:
                manual_lines.append(f"- {_display_target(team_id, remark)} 抓取失败：{e}")
            continue
        except Exception as e:
            total_errors += 1
            logger.error(f"[{MODULE_NAME}]抓取 team {team_id} 未知错误: {e}")
            if manual_trigger:
                manual_lines.append(
                    f"- {_display_target(team_id, remark)} 抓取异常：{e}"
                )
            continue

        new_solves = _diff_and_persist(team_id, info)
        total_new += len(new_solves)

        # 更新最新队名与总分
        with DataManager() as dm:
            dm.update_target_profile(team_id, info.team_name, info.total_score)

        if new_solves:
            await _notify_new_submits(
                websocket,
                owner_id,
                team_id,
                remark,
                info,
                new_solves,
            )

        if manual_trigger:
            manual_lines.append(_format_manual_line(team_id, remark, info, new_solves))

    # 若 session 在过程中被刷新，落库一次
    if client.session_cookie and client.session_cookie != session:
        with DataManager() as dm:
            dm.set_session(client.session_cookie)

    if manual_trigger:
        summary_header = (
            f"ISCC 擂台赛监控 手动触发 完成\n"
            f"监控目标：{len(targets)} 个\n"
            f"新通过：{total_new} 题\n"
            f"失败：{total_errors} 次"
        )
        manual_text = summary_header
        if manual_lines:
            manual_text = manual_text + "\n\n" + "\n".join(manual_lines)
        await _send(websocket, owner_id, manual_text)

    return {"targets": len(targets), "new_submits": total_new, "errors": total_errors}


def _diff_and_persist(team_id: str, info: TeamArenaInfo) -> list:
    """对比并持久化，返回这次新出现的通过条目列表。"""
    with DataManager() as dm:
        known = dm.get_known_submits(team_id, ARENA_TRACK)
        new_solves = [solve for solve in info.solves if solve.name not in known]
        # 全量写入/更新，顺便补全字段变化（如分数修正）
        for solve in info.solves:
            dm.record_submit(
                team_id=team_id,
                track=ARENA_TRACK,
                challenge_name=solve.name,
                category=solve.category,
                score=solve.score,
                solved_at=solve.solved_at,
            )
    return new_solves


async def _notify_new_submits(
    websocket,
    owner_id: str,
    team_id: str,
    remark: str,
    info: TeamArenaInfo,
    new_solves: list,
):
    header = (
        f"[ISCC 擂台赛监控] 检测到新提交\n"
        f"监控对象：{_display_target(team_id, remark)}\n"
        f"当前队名：{info.team_name or '未知'}\n"
        f"{info.total_score or ''}".rstrip()
    )
    detail_lines = [
        f"- {solve.name}（{solve.category or '未分类'}）"
        f" 得分 {solve.score or '未知'}"
        f" 通过时间 {solve.solved_at or '未知'}"
        for solve in new_solves
    ]
    text = header + "\n\n新通过题目：\n" + "\n".join(detail_lines)
    await _send(websocket, owner_id, text)


def _display_target(team_id: str, remark: str) -> str:
    return f"{remark}({team_id})" if remark else team_id


def _format_manual_line(
    team_id: str,
    remark: str,
    info: TeamArenaInfo,
    new_solves: list,
) -> str:
    team_display = _display_target(team_id, remark)
    name_display = info.team_name or "未知"
    if new_solves:
        return (
            f"- {team_display}：队名 {name_display}，新通过 {len(new_solves)} 题 "
            f"（已通知管理员）"
        )
    return (
        f"- {team_display}：队名 {name_display}，当前已通过 "
        f"{len(info.solves)} 题，暂无新提交"
    )


async def _send(websocket, owner_id: str, text: str):
    try:
        await send_private_msg(
            websocket,
            owner_id,
            [generate_text_message(text)],
        )
    except Exception as e:
        logger.error(f"[{MODULE_NAME}]发送监控消息失败: {e}")


# 下面是供外部（如心跳处理器）调用时的防并发工具
class MonitorLock:
    """简单的异步互斥：同一时刻只允许一个轮询在跑。"""

    _lock: Optional[asyncio.Lock] = None

    @classmethod
    def get(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock
