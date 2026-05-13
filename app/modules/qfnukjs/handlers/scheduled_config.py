import json
import os

from .. import DATA_DIR, MODULE_NAME
from logger import logger


CONFIG_PATH = os.path.join(DATA_DIR, "scheduled_empty_classrooms.json")
DEFAULT_CONFIG = {"groups": {}, "last_run_date": ""}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"[{MODULE_NAME}]读取定时空教室配置失败: {e}")
        return DEFAULT_CONFIG.copy()

    if not isinstance(data, dict):
        return DEFAULT_CONFIG.copy()

    data.setdefault("groups", {})
    data.setdefault("last_run_date", "")
    return data


def save_config(config):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def normalize_buildings(buildings):
    normalized = []
    seen = set()
    for building in buildings:
        name = str(building).strip()
        if not name or name in seen:
            continue
        normalized.append(name)
        seen.add(name)
    return normalized


def get_group_buildings(group_id):
    config = load_config()
    return normalize_buildings(config.get("groups", {}).get(str(group_id), []))


def set_group_buildings(group_id, buildings):
    config = load_config()
    groups = config.setdefault("groups", {})
    normalized = normalize_buildings(buildings)
    if normalized:
        groups[str(group_id)] = normalized
    else:
        groups.pop(str(group_id), None)
    save_config(config)
    return normalized


def get_last_run_date():
    return str(load_config().get("last_run_date", ""))


def set_last_run_date(date_text):
    config = load_config()
    config["last_run_date"] = str(date_text)
    save_config(config)


def get_api_key():
    return str(load_config().get("api_key", "")).strip()


def set_api_key(api_key):
    config = load_config()
    config["api_key"] = str(api_key).strip()
    save_config(config)


def get_forward_announcement():
    return str(load_config().get("forward_announcement", "")).strip()


def set_forward_announcement(text):
    config = load_config()
    announcement = str(text).strip()
    if announcement:
        config["forward_announcement"] = announcement
    else:
        config.pop("forward_announcement", None)
    save_config(config)
