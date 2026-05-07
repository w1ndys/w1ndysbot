# AGENTS.md

## Project Shape

- This is a Python 3.12 `uv` project; trust `.python-version`, `pyproject.toml`, and `uv.lock` over the README Python range.
- Run app commands from `app/` so absolute imports like `from config import ...`, `from core.switchs import ...`, and `from modules.X import ...` resolve correctly.
- Runtime entrypoint is `app/main.py`; it requires a root `.env` with `OWNER_ID` and `WS_URL`, while `TOKEN`, `FEISHU_BOT_URL`, and `FEISHU_BOT_SECRET` are optional.
- Main long-running command is `uv run python app/main.py` from repo root, or `uv run python main.py` from `app/`.

## Verification

- There is no repo-wide pytest/lint/typecheck config at present; do not invent a standard test suite.
- Use `uv run python -m compileall app` as the safest broad syntax/import-adjacent check after Python edits.
- `app/modules/FAQSystem/test_FAQSystem.py` is an interactive script, not an automated pytest test.

## Module Loading

- `app/handle_events.py` dynamically loads every `app/modules/*/main.py` directory that is not prefixed with `_` and whose `__init__.py` has `MODULE_ENABLED=True` or omits it.
- A module is considered loadable only if `main.py` exposes async `handle_events(websocket, msg)`.
- `app/modules/Template/` is the canonical module skeleton: `__init__.py` defines `MODULE_NAME`, `MODULE_ENABLED`, `SWITCH_NAME`, `MODULE_DESCRIPTION`, `DATA_DIR`, and `COMMANDS`; `main.py` dispatches to handler classes by NapCat event type.
- Keep using `core.switchs` for module switch imports; it is a compatibility facade over the newer `core/switch/` package and is what existing modules use.

## Message Flow

- `app/bot.py` connects to NapCat via WebSocket and schedules `EventHandler.handle_message` with `asyncio.create_task`; each registered handler is also run as its own background task.
- Module handlers must not assume ordering or synchronous completion across handlers because events are fanned out concurrently.
- Group modules typically handle the switch command before the menu command, then return early unless `is_group_switch_on(group_id, MODULE_NAME)` is true.
- Menu commands conventionally use `SWITCH_NAME + MENU_COMMAND` and `MenuManager.get_module_commands_text(MODULE_NAME)`.

## NapCat Responses

- NapCat API calls such as `send_group_msg`, `send_private_msg`, and `get_msg` do not synchronously return usable response data; their responses arrive later as WebSocket messages.
- Any feature depending on response data must send a unique `echo` marker containing module, feature, and business request ID, for example `send_group_msg-qfnukjs_empty_classroom_pending=<id>`.
- Parse that marker only in the module's `ResponseHandler`, read data such as `data.message_id` there, and store request context in module state or persistence.
- Design these flows for response-before-work-completes, work-before-response, missing response, and failed response cases.

## Data And Config

- Runtime data and logs are intentionally ignored by git: `data/`, `logs/`, `.env`, `.venv`, and caches should not be committed.
- Some modules load their own `.env` from the module directory, for example `app/modules/qfnukjs/.env` and `app/modules/SentimentAnalysis/.env`; check the module README or `.env.example` before changing config behavior.
- Module `DATA_DIR` values usually point under repo-root `data/<MODULE_NAME>` and may be created at import time.
