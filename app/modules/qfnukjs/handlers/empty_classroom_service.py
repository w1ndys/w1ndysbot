import json
import os

import aiohttp

from .. import MODULE_NAME
from logger import logger
from .scheduled_config import get_api_key


BASE_URL = os.getenv("QFNUKJS_BASE_URL", "https://kjs.easy-qfnu.top").rstrip("/")
QUERY_TIMEOUT_SECONDS = 30
API_KEY_MISSING_MESSAGE = "qfnukjs 未配置 API Key，请私聊发送：qfnukjs配置apikey <API Key>。"


def get_request_headers():
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(API_KEY_MISSING_MESSAGE)

    return {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }


def format_weekday(day_of_week):
    weekdays = {
        1: "周一",
        2: "周二",
        3: "周三",
        4: "周四",
        5: "周五",
        6: "周六",
        7: "周日",
    }
    try:
        return weekdays.get(int(day_of_week), "")
    except (TypeError, ValueError):
        return ""


def try_parse_json_string(text):
    text = text.strip()
    if not text:
        return ""

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def normalize_json_value(value):
    if isinstance(value, str):
        parsed = try_parse_json_string(value)
        if parsed == value:
            return value.strip()
        return normalize_json_value(parsed)

    if isinstance(value, list):
        return [normalize_json_value(item) for item in value]

    if isinstance(value, dict):
        return {key: normalize_json_value(item) for key, item in value.items()}

    return value


def extract_query_payload(data):
    data = normalize_json_value(data)
    if isinstance(data, dict):
        for key in ("message", "result", "data", "answer", "text"):
            value = data.get(key)
            if value not in (None, "", [], {}):
                return extract_query_payload(value)
    return data


def format_empty_classroom_result(data):
    classrooms = data.get("classrooms")
    if not isinstance(classrooms, list):
        return json.dumps(data, ensure_ascii=False, indent=2)

    date = data.get("date")
    week = data.get("week")
    day_of_week = data.get("day_of_week")
    weekday_text = format_weekday(day_of_week)

    lines = ["空教室查询结果"]
    meta_parts = []
    if date:
        meta_parts.append(f"日期：{date}")
    if week:
        meta_parts.append(f"第 {week} 周")
    if weekday_text:
        meta_parts.append(weekday_text)
    if meta_parts:
        lines.append("，".join(meta_parts))

    if not classrooms:
        lines.append("未查询到空教室信息。")
        return "\n".join(lines)

    classroom_text = "、".join(str(classroom) for classroom in classrooms)
    lines.append(f"空教室（{len(classrooms)} 间）：{classroom_text}")
    return "\n".join(lines)


def format_json_value(value):
    value = normalize_json_value(value)
    if value in (None, "", [], {}):
        return "空教室查询结果为空。"
    if isinstance(value, dict) and "classrooms" in value:
        return format_empty_classroom_result(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value).strip() or "空教室查询结果为空。"


def format_query_result(data):
    payload = extract_query_payload(data)
    if isinstance(payload, list):
        return format_json_value(payload) if payload else "未查询到空教室信息。"
    return format_json_value(payload)


def extract_classrooms(data):
    payload = extract_query_payload(data)
    if isinstance(payload, dict) and isinstance(payload.get("classrooms"), list):
        return [str(classroom) for classroom in payload["classrooms"]]
    if isinstance(payload, list):
        return [str(classroom) for classroom in payload]
    return []


async def query_empty_classroom_data(text):
    headers = get_request_headers()
    payload = {"text": text}
    timeout = aiohttp.ClientTimeout(total=QUERY_TIMEOUT_SECONDS)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{BASE_URL}/api/v1/open/ai-query",
            json=payload,
            headers=headers,
        ) as response:
            response_text = await response.text()
            if response.status >= 400:
                logger.error(
                    f"[{MODULE_NAME}]空教室查询接口返回异常: "
                    f"status={response.status}, body={response_text[:500]}"
                )
                raise RuntimeError("空教室查询失败，请稍后再试。")

            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                return response_text


async def query_empty_classroom_direct(building, start_node, end_node, date_offset=0):
    headers = get_request_headers()
    payload = {
        "building": building,
        "date_offset": date_offset,
        "start_node": start_node,
        "end_node": end_node,
    }
    timeout = aiohttp.ClientTimeout(total=QUERY_TIMEOUT_SECONDS)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{BASE_URL}/api/v1/open/query",
            json=payload,
            headers=headers,
        ) as response:
            response_text = await response.text()
            if response.status >= 400:
                logger.error(
                    f"[{MODULE_NAME}]空教室直接查询接口返回异常: "
                    f"status={response.status}, body={response_text[:500]}"
                )
                raise RuntimeError("空教室查询失败，请稍后再试。")

            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                return response_text


async def query_empty_classroom_text(text):
    try:
        data = await query_empty_classroom_data(text)
    except RuntimeError as e:
        return str(e)
    return format_query_result(data)
