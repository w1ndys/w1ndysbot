"""ISCC 擂台赛监控核心逻辑：抓取、对比、落库、通知管理员。

复用模块内现有的 `ISCCClient`（包含自动重登录与 session 刷新），
避免再维护第二套 HTTP 客户端。监控只关注**擂台题**，练武题暂不包含。
"""

import asyncio
from typing import Optional

from api.message import send_private_msg
from logger import logger
from utils.generate import generate_text_message

from .. import MODULE_NAME
from .data_manager import DataManager
from .iscc_client import ArenaSolve, ISCCClient, ISCCClientError, TeamArenaSnapshot


async def run_monitor_once(
    websocket,
    owner_id: str,
    account: Optional[dict] = None,
    manual_trigger: bool = False,
) -> dict:
    """执行一次全量擂台赛监控轮询。

    - 使用当前已登录账号的 session 作为抓取凭据（不强制目标 team 必须是该账号自己）。
    - 首次抓取某个 team 时，仅把当前通过列表作为基线入库、不推送通知；之后的差异才通知。
    - `manual_trigger` 为 True 时，无论是否有变化都会给 owner_id 发一次状态反馈。
    """
    if not owner_id:
        logger.warning(f"[{MODULE_NAME}]未配置 OWNER_ID，跳过擂台赛监控")
        return {"targets": 0, "new_submits": 0, "errors": 0}

    with DataManager() as dm:
        targets = dm.list_monitor_targets()
        if account is None:
            account = dm.get_account(owner_id)

    if not targets:
        if manual_trigger:
            await _send(
                websocket,
                owner_id,
                "ISCC 擂台赛监控：当前未配置任何监控 team id，\n"
                "可以通过 `isccm添加 <team_id> [备注]` 添加。",
            )
        return {"targets": 0, "new_submits": 0, "errors": 0}

    session = (account or {}).get("session", "")
    client = ISCCClient(session)

    total_new = 0
    total_errors = 0
    manual_lines: list[str] = []

    for target in targets:
        team_id = target["team_id"]
        remark = target.get("remark") or ""
        baseline_ready = bool(target.get("baseline_ready_at"))

        try:
            snapshot = await client.fetch_team_arena_snapshot(team_id)
        except ISCCClientError as e:
            total_errors += 1
            logger.warning(f"[{MODULE_NAME}]监控抓取 team {team_id} 失败: {e}")
            if manual_trigger:
                manual_lines.append(
                    f"- {_display_target(team_id, remark)} 抓取失败：{e}"
                )
            continue
        except Exception as e:
            total_errors += 1
            logger.error(f"[{MODULE_NAME}]监控抓取 team {team_id} 未知错误: {e}")
            if manual_trigger:
                manual_lines.append(
                    f"- {_display_target(team_id, remark)} 抓取异常：{e}"
                )
            continue

        new_solves = _diff_and_persist(team_id, snapshot, baseline_ready)
        total_new += len(new_solves)

        with DataManager() as dm:
            dm.update_monitor_profile(team_id, snapshot.team_name, snapshot.total_score)
            if not baseline_ready:
                dm.mark_monitor_baseline_ready(team_id)

        if new_solves and baseline_ready:
            await _notify_new_submits(
                websocket, owner_id, team_id, remark, snapshot, new_solves
            )

        if manual_trigger:
            manual_lines.append(
                _format_manual_line(team_id, remark, snapshot, new_solves, baseline_ready)
            )

    # session 可能被刷新过，回写给当前账号
    if account and client.session_cookie and client.session_cookie != session:
        with DataManager() as dm:
            dm.save_session(str(account["user_id"]), client.session_cookie)

    if manual_trigger:
        summary = (
            f"ISCC 擂台赛监控 手动触发 完成\n"
            f"监控目标：{len(targets)} 个\n"
            f"新通过：{total_new} 题\n"
            f"失败：{total_errors} 次"
        )
        text = summary if not manual_lines else summary + "\n\n" + "\n".join(manual_lines)
        await _send(websocket, owner_id, text)

    return {"targets": len(targets), "new_submits": total_new, "errors": total_errors}


def _diff_and_persist(
    team_id: str,
    snapshot: TeamArenaSnapshot,
    baseline_ready: bool,
) -> list[ArenaSolve]:
    """对比并持久化；baseline 未就绪时不把当前通过当作新通过。"""
    with DataManager() as dm:
        known = dm.get_monitor_known_submits(team_id)
        fresh: list[ArenaSolve] = [
            solve for solve in snapshot.solves if solve.name not in known
        ]
        for solve in snapshot.solves:
            dm.record_monitor_submit(
                team_id=team_id,
                challenge_name=solve.name,
                category=solve.category,
                score=solve.score,
                solved_at=solve.solved_at,
            )

    # 首次抓取视为基线，此时不通知
    if not baseline_ready:
        return []
    return fresh


async def _notify_new_submits(
    websocket,
    owner_id: str,
    team_id: str,
    remark: str,
    snapshot: TeamArenaSnapshot,
    new_solves: list[ArenaSolve],
):
    header = (
        "[ISCC 擂台赛监控] 检测到新提交\n"
        f"监控对象：{_display_target(team_id, remark)}\n"
        f"当前队名：{snapshot.team_name or '未知'}\n"
        f"{snapshot.total_score or ''}".rstrip()
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
    snapshot: TeamArenaSnapshot,
    new_solves: list[ArenaSolve],
    baseline_ready: bool,
) -> str:
    team_display = _display_target(team_id, remark)
    name_display = snapshot.team_name or "未知"
    if not baseline_ready:
        return (
            f"- {team_display}：队名 {name_display}，首次抓取完成，已建立基线 "
            f"{len(snapshot.solves)} 题（不作为新通过通知）"
        )
    if new_solves:
        return (
            f"- {team_display}：队名 {name_display}，新通过 {len(new_solves)} 题 "
            "（已通知管理员）"
        )
    return (
        f"- {team_display}：队名 {name_display}，当前已通过 "
        f"{len(snapshot.solves)} 题，暂无新提交"
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


class MonitorLock:
    """模块级 asyncio 互斥锁；确保同一时刻只有一次监控轮询在跑。"""

    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def get(cls) -> asyncio.Lock:
        return cls._lock
