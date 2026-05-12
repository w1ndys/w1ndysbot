import asyncio
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from http.cookies import SimpleCookie

import aiohttp
from bs4 import BeautifulSoup
from yarl import URL

from .. import BASE_URL


STATUS_TEXT = {
    "1": "正确",
    "0": "错误",
    "2": "已解决",
    "3": "提交过快",
    "4": "题目未开放或无权限",
    "5": "服务器错误",
    "-1": "Nonce 错误或登录失效",
}


@dataclass
class ChallengeContext:
    track: str
    submit_path: str
    challenge_ids: list[int]


@dataclass
class SubmitResult:
    track: str
    challenge_id: int
    status: str
    message: str


@dataclass
class ArenaSolve:
    """擂台赛单题通过记录。"""

    name: str
    category: str = ""
    score: str = ""
    solved_at: str = ""


@dataclass
class TeamArenaSnapshot:
    """某个 team 在擂台赛页面上的快照，用于监控对比。"""

    team_id: str
    team_name: str = ""
    total_score: str = ""
    solves: list[ArenaSolve] = field(default_factory=list)


class ISCCClientError(Exception):
    pass


class ISCCClient:
    def __init__(self, session_cookie: str = ""):
        self.base_url = BASE_URL.rstrip("/")
        self.session_cookie = session_cookie
        self._session: aiohttp.ClientSession | None = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    async def login(self, username: str, password: str) -> str:
        async with self._operation_session() as session:
            async with session.post(
                f"{self.base_url}/login",
                data={"name": username, "password": password},
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": self.base_url,
                    "Referer": f"{self.base_url}/login",
                },
            ) as response:
                if response.status >= 400:
                    raise ISCCClientError(f"登录失败，HTTP 状态码 {response.status}")
                cookie = self._extract_session_cookie(response)
                if not cookie:
                    raise ISCCClientError("登录失败，响应中未返回 session")
                self.session_cookie = cookie
                self._sync_session_cookie()
                return cookie

    async def verify_login(self) -> bool:
        if not self.session_cookie:
            return False
        try:
            async with self._operation_session():
                html = await self._request_text("GET", "/challenges", referer=f"{self.base_url}/")
        except ISCCClientError:
            return False
        return bool(self._extract_team_id(html)) and "login" not in html.lower()

    async def fetch_nonces(self) -> tuple[str, str]:
        """获取练武题与擂台题的 nonce，返回 (regular_nonce, arena_nonce)。

        - 登录失效异常会向外抛出，让调用侧决定是否重登录重试。
        - 其它网络/HTTP 错误视为"这次取不到"，对应字段返回空串。
        """
        async with self._operation_session():
            async def _fetch(path: str) -> str:
                try:
                    html = await self._request_text("GET", path, referer=f"{self.base_url}/")
                    return self._extract_nonce(html)
                except ISCCClientError as e:
                    if "登录状态失效" in str(e):
                        raise
                    return ""

            regular_nonce = await _fetch("/challenges")
            arena_nonce = await _fetch("/arena")
            return regular_nonce, arena_nonce

    async def keep_alive_arena_score(self) -> str:
        async with self._operation_session():
            html = await self._request_text("GET", "/arena", referer=f"{self.base_url}/")
            team_id = self._extract_team_id(html)
            if not team_id:
                raise ISCCClientError("获取队伍信息失败")
            await self._request_text("GET", f"/teamarena/{team_id}", referer=f"{self.base_url}/team/{team_id}")
            return team_id

    async def fetch_team_arena_snapshot(self, team_id: str) -> TeamArenaSnapshot:
        """拉取指定 team 的擂台赛页面并解析，供监控模块对比使用。

        仅做只读访问：不依赖当前登录账号是否为该 team 的成员。
        """
        if not team_id:
            raise ISCCClientError("team_id 为空")

        async with self._operation_session():
            html = await self._request_text(
                "GET",
                f"/teamarena/{team_id}",
                referer=f"{self.base_url}/arenascoreboard",
            )
            return self._parse_team_arena(team_id, html)

    def _parse_team_arena(self, team_id: str, html: str) -> TeamArenaSnapshot:
        soup = BeautifulSoup(html, "html.parser")
        snapshot = TeamArenaSnapshot(team_id=team_id)

        team_node = soup.find(id="team-id")
        if team_node and team_node.get_text(strip=True):
            snapshot.team_name = team_node.get_text(strip=True)

        score_node = soup.find(
            lambda tag: tag.name == "h3"
            and "总积分" in tag.get_text(strip=True)
        )
        if score_node:
            snapshot.total_score = score_node.get_text(strip=True)

        table = self._find_arena_solve_table(soup)
        if table is None:
            return snapshot

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")
        for tr in rows:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 4:
                continue
            name, category, score, solved_at = cells[0], cells[1], cells[2], cells[3]
            if not name:
                continue
            snapshot.solves.append(
                ArenaSolve(name=name, category=category, score=score, solved_at=solved_at)
            )
        return snapshot

    def _find_arena_solve_table(self, soup: BeautifulSoup):
        """从 /teamarena/<id> 页面找到擂台解题详情表。"""
        for table in soup.find_all("table"):
            header_text = table.get_text(" ", strip=True)
            if "擂台名称" in header_text and "通过时间" in header_text:
                return table
        return None

    async def submit_flag_to_unsolved(self, flag: str) -> list[SubmitResult]:
        async with self._operation_session():
            regular_result, arena_result = await asyncio.gather(self._regular_context(), self._arena_context(), return_exceptions=True)
            contexts = []
            errors = []
            for track, result in (("练武题", regular_result), ("擂台题", arena_result)):
                if isinstance(result, Exception):
                    errors.append(SubmitResult(track, 0, "error", f"获取题目失败：{result}"))
                else:
                    contexts.append(result)

            results = []
            for context in contexts:
                for challenge_id in context.challenge_ids:
                    results.append(await self._submit_challenge(context, challenge_id, flag))
            return [*errors, *results]

    async def _regular_context(self) -> ChallengeContext:
        html = await self._request_text("GET", "/challenges", referer=f"{self.base_url}/")
        nonce = self._extract_nonce(html)
        team_id = self._extract_team_id(html)
        if not nonce or not team_id:
            raise ISCCClientError("获取练武题页面失败，缺少 nonce 或队伍信息")
        challenge_ids = self._extract_regular_challenge_ids(html)
        solved_ids = await self._regular_solved_ids(team_id)
        return ChallengeContext("练武题", "/chal", sorted(challenge_ids - solved_ids))

    async def _arena_context(self) -> ChallengeContext:
        html = await self._request_text("GET", "/arena", referer=f"{self.base_url}/")
        nonce = self._extract_nonce(html)
        if not nonce:
            raise ISCCClientError("获取擂台题页面失败，缺少 nonce")
        challenge_ids, solved_ids = await asyncio.gather(self._arena_challenge_ids(), self._arena_solved_ids())
        return ChallengeContext("擂台题", "/are", sorted(challenge_ids - solved_ids))

    async def _regular_solved_ids(self, team_id: str) -> set[int]:
        data = await self._request_json("GET", f"/solves/{team_id}", referer=f"{self.base_url}/team/{team_id}")
        return {int(item["chalid"]) for item in data.get("solves", []) if str(item.get("chalid", "")).isdigit()}

    async def _arena_challenge_ids(self) -> set[int]:
        data = await self._request_json("GET", "/arenas", referer=f"{self.base_url}/arena")
        return {int(item["id"]) for item in data.get("game", []) if str(item.get("id", "")).isdigit()}

    async def _arena_solved_ids(self) -> set[int]:
        data = await self._request_json("GET", "/arenasolves", referer=f"{self.base_url}/arena")
        return {int(item["chalid"]) for item in data.get("solves", []) if str(item.get("chalid", "")).isdigit()}

    async def _submit_challenge(self, context: ChallengeContext, challenge_id: int, flag: str) -> SubmitResult:
        try:
            nonce = await self._get_nonce_for_track(context.track)
            text = await self._request_text(
                "POST",
                f"{context.submit_path}/{challenge_id}",
                data={"key": flag, "nonce": nonce},
                referer=f"{self.base_url}/arena" if context.track == "擂台题" else f"{self.base_url}/challenges",
                ajax=True,
            )
            status = text.strip()
            return SubmitResult(context.track, challenge_id, status, STATUS_TEXT.get(status, f"未知返回：{status}"))
        except Exception as e:
            return SubmitResult(context.track, challenge_id, "error", f"提交异常：{e}")

    async def _get_nonce_for_track(self, track: str) -> str:
        path = "/arena" if track == "擂台题" else "/challenges"
        html = await self._request_text("GET", path, referer=f"{self.base_url}/")
        nonce = self._extract_nonce(html)
        if not nonce:
            raise ISCCClientError(f"获取{track} nonce 失败")
        return nonce

    async def _request_text(self, method: str, path: str, data: dict | None = None, referer: str = "", ajax: bool = False) -> str:
        headers = self._request_headers(referer, ajax)
        async with self._request_session().request(method, f"{self.base_url}{path}", data=data, headers=headers) as response:
            text = await response.text()
            self._sync_session_cookie()
            if response.status >= 400:
                raise ISCCClientError(f"{method} {path} 失败，HTTP 状态码 {response.status}")
            if self._looks_like_login_page(text):
                raise ISCCClientError("登录状态失效")
            return text

    async def _request_json(self, method: str, path: str, referer: str) -> dict:
        headers = self._request_headers(referer, True)
        async with self._request_session().request(method, f"{self.base_url}{path}", headers=headers) as response:
            self._sync_session_cookie()
            if response.status >= 400:
                raise ISCCClientError(f"{method} {path} 失败，HTTP 状态码 {response.status}")
            return await response.json(content_type=None)

    @asynccontextmanager
    async def _operation_session(self):
        if self._session is not None:
            yield self._session
            return

        timeout = aiohttp.ClientTimeout(total=20)
        self._session = aiohttp.ClientSession(timeout=timeout, headers=self.headers, cookie_jar=aiohttp.CookieJar(unsafe=True))
        if self.session_cookie:
            self._session.cookie_jar.update_cookies({"session": self.session_cookie}, response_url=URL(self.base_url))
        try:
            yield self._session
        finally:
            self._sync_session_cookie()
            await self._session.close()
            self._session = None

    def _request_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise ISCCClientError("请求会话未初始化")
        return self._session

    def _sync_session_cookie(self):
        if self._session is None:
            return
        for cookie in self._session.cookie_jar:
            if cookie.key == "session":
                self.session_cookie = cookie.value
                return

    def _request_headers(self, referer: str, ajax: bool) -> dict:
        headers = {
            "Accept": "*/*" if ajax else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": referer or self.base_url,
        }
        if ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Origin"] = self.base_url
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        return headers

    def _extract_session_cookie(self, response: aiohttp.ClientResponse) -> str:
        if "session" in response.cookies:
            return response.cookies["session"].value
        for header in response.headers.getall("Set-Cookie", []):
            cookie = SimpleCookie(header)
            if "session" in cookie:
                return cookie["session"].value
        return ""

    def _extract_nonce(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for name in ("nonce", "csrf_nonce"):
            node = soup.find("input", attrs={"name": name})
            if node and node.get("value"):
                return str(node["value"])
        match = re.search(r'name=["\'](?:nonce|csrf_nonce)["\'][^>]*value=["\']([^"\']+)', html)
        return match.group(1) if match else ""

    def _extract_team_id(self, html: str) -> str:
        match = re.search(r'href=["\']/team/([0-9a-fA-F]+)["\']', html)
        return match.group(1) if match else ""

    def _extract_regular_challenge_ids(self, html: str) -> set[int]:
        ids = {int(value) for value in re.findall(r'href=["\']/chal/(\d+)["\']', html)}
        ids.update(int(value) for value in re.findall(r'data-id=["\'](\d+)["\']', html))
        ids.update(int(value) for value in re.findall(r'id=["\']chal-(\d+)["\']', html))
        return ids

    def _looks_like_login_page(self, text: str) -> bool:
        lowered = text.lower()
        return "name=\"password\"" in lowered and "name=\"name\"" in lowered
