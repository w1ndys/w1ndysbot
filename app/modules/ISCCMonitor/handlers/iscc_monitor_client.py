"""ISCC 擂台赛页面抓取与解析。

只读接口，不做任何登录/提交操作：访问 `/teamarena/<team_id>`，解析页面上的
队伍名、总分、以及已通过的擂台题列表（题目名、分类、得分、通过时间）。
"""

import asyncio
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup
from yarl import URL

from .. import BASE_URL


# 赛道常量：只监控擂台题
ARENA_TRACK = "擂台题"


class ISCCFetchError(Exception):
    """监控模块抓取 ISCC 页面失败。"""


@dataclass
class ArenaSolve:
    name: str
    category: str = ""
    score: str = ""
    solved_at: str = ""


@dataclass
class TeamArenaInfo:
    team_id: str
    team_name: str = ""
    total_score: str = ""
    solves: list[ArenaSolve] = field(default_factory=list)


class ISCCMonitorClient:
    def __init__(self, session_cookie: str = "", timeout_sec: int = 20):
        self.base_url = BASE_URL.rstrip("/")
        self.session_cookie = session_cookie or ""
        self._timeout = aiohttp.ClientTimeout(total=timeout_sec)
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7"
            ),
        }

    async def fetch_team_arena(self, team_id: str) -> TeamArenaInfo:
        if not team_id:
            raise ISCCFetchError("team_id 为空")

        cookie_jar = aiohttp.CookieJar(unsafe=True)
        if self.session_cookie:
            cookie_jar.update_cookies(
                {"session": self.session_cookie}, response_url=URL(self.base_url)
            )

        async with aiohttp.ClientSession(
            timeout=self._timeout, headers=self._headers, cookie_jar=cookie_jar
        ) as session:
            url = f"{self.base_url}/teamarena/{team_id}"
            headers = {
                "Referer": f"{self.base_url}/arenascoreboard",
                "Upgrade-Insecure-Requests": "1",
            }
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status >= 400:
                        raise ISCCFetchError(
                            f"GET /teamarena/{team_id} 失败，HTTP 状态码 {resp.status}"
                        )
                    text = await resp.text()
                    # 同步最新 session，方便外层续存（页面侧有时会刷新 cookie）
                    self._sync_session_cookie(resp, cookie_jar)
            except asyncio.TimeoutError as e:
                raise ISCCFetchError(f"请求超时：{e}")
            except aiohttp.ClientError as e:
                raise ISCCFetchError(f"请求失败：{e}")

        if self._looks_like_login_page(text):
            raise ISCCFetchError(
                "ISCC 未登录或 session 已失效，请通过 isccmsession 更新监控 session"
            )
        return self._parse(team_id, text)

    def _sync_session_cookie(
        self, resp: aiohttp.ClientResponse, cookie_jar: aiohttp.CookieJar
    ):
        if "session" in resp.cookies:
            self.session_cookie = resp.cookies["session"].value
            return
        for header in resp.headers.getall("Set-Cookie", []):
            cookie = SimpleCookie(header)
            if "session" in cookie:
                self.session_cookie = cookie["session"].value
                return
        for cookie in cookie_jar:
            if cookie.key == "session":
                self.session_cookie = cookie.value
                return

    def _looks_like_login_page(self, text: str) -> bool:
        lowered = text.lower()
        return 'name="password"' in lowered and 'name="name"' in lowered

    def _parse(self, team_id: str, html: str) -> TeamArenaInfo:
        soup = BeautifulSoup(html, "html.parser")

        info = TeamArenaInfo(team_id=team_id)

        team_node = soup.find(id="team-id")
        if team_node and team_node.get_text(strip=True):
            info.team_name = team_node.get_text(strip=True)

        # 总分/排名文本：示例文本为 "总积分为:1980,排在1位。"
        score_node = soup.find(
            lambda tag: tag.name == "h3"
            and "总积分" in tag.get_text(strip=True)
        )
        if score_node:
            info.total_score = score_node.get_text(strip=True)

        table = self._find_solve_table(soup)
        if table is None:
            return info

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")
        for tr in rows:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 4:
                continue
            name, category, score, solved_at = cells[0], cells[1], cells[2], cells[3]
            if not name:
                continue
            info.solves.append(
                ArenaSolve(
                    name=name, category=category, score=score, solved_at=solved_at
                )
            )
        return info

    def _find_solve_table(self, soup: BeautifulSoup) -> Optional["BeautifulSoup"]:
        """找到解题详情表：带有 "擂台名称"/"通过时间" 表头的那张表。"""
        for table in soup.find_all("table"):
            header_text = table.get_text(" ", strip=True)
            if "擂台名称" in header_text and "通过时间" in header_text:
                return table
        return None
