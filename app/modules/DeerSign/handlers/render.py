import base64
import calendar
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _to_base64(image: Image.Image) -> str:
    output = BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("utf-8")


def render_calendar(year: int, month: int, user_label: str, records: dict[int, int], today: int) -> str:
    width, height = 900, 760
    image = Image.new("RGB", (width, height), "#f7f2e9")
    draw = ImageDraw.Draw(image)
    title_font = _font(42)
    text_font = _font(26)
    small_font = _font(20)
    day_font = _font(28)

    draw.rounded_rectangle((30, 30, width - 30, height - 30), radius=28, fill="#fffaf2", outline="#d9b77b", width=3)
    draw.text((70, 58), f"鹿管签到 {year}-{month:02d}", fill="#6b3f1d", font=title_font)
    draw.text((70, 118), f"用户：{user_label}", fill="#7a5a34", font=text_font)
    signed_days = len(records)
    total_count = sum(records.values())
    draw.text((70, 158), f"本月已签到 {signed_days} 天，累计 {total_count} 次", fill="#7a5a34", font=text_font)

    week_names = ["一", "二", "三", "四", "五", "六", "日"]
    start_x, start_y = 70, 230
    cell_w, cell_h = 108, 78
    for index, name in enumerate(week_names):
        draw.text((start_x + index * cell_w + 38, start_y - 42), name, fill="#8b6a3f", font=text_font)

    for week_idx, week in enumerate(calendar.monthcalendar(year, month)):
        for day_idx, day in enumerate(week):
            x = start_x + day_idx * cell_w
            y = start_y + week_idx * cell_h
            fill = "#f0e2c8" if day else "#f8f0e2"
            outline = "#d8c09a"
            if day in records:
                fill = "#8fbf76"
                outline = "#5f934b"
            if day == today:
                outline = "#c35b2e"
            draw.rounded_rectangle((x, y, x + 92, y + 62), radius=14, fill=fill, outline=outline, width=3 if day == today else 1)
            if day:
                draw.text((x + 14, y + 12), str(day), fill="#3c2a18", font=day_font)
                if records.get(day, 0) > 1:
                    draw.text((x + 50, y + 28), f"x{records[day]}", fill="#26451f", font=small_font)

    draw.text((70, 705), "绿色表示已签到，红框表示今天。", fill="#8b6a3f", font=small_font)
    return _to_base64(image)


def render_rank(year: int, month: int, rankings: list[dict], labels: dict[str, str]) -> str:
    width = 900
    height = max(420, 210 + len(rankings) * 70)
    image = Image.new("RGB", (width, height), "#f2f6ee")
    draw = ImageDraw.Draw(image)
    title_font = _font(42)
    text_font = _font(26)
    small_font = _font(22)

    draw.rounded_rectangle((30, 30, width - 30, height - 30), radius=28, fill="#fbfff6", outline="#91b879", width=3)
    draw.text((70, 58), f"鹿管签到榜 {year}-{month:02d}", fill="#385c2b", font=title_font)
    draw.text((70, 125), "按本月累计签到次数排序", fill="#5f754e", font=text_font)

    if not rankings:
        draw.text((70, 220), "本群本月暂无签到记录", fill="#5f754e", font=text_font)
        return _to_base64(image)

    y = 200
    for index, item in enumerate(rankings, 1):
        user_id = str(item["user_id"])
        total = int(item["total"])
        days = int(item["days"])
        fill = "#e8f2df" if index % 2 else "#f3f8ed"
        draw.rounded_rectangle((70, y, width - 70, y + 52), radius=14, fill=fill)
        draw.text((95, y + 10), f"#{index}", fill="#385c2b", font=text_font)
        draw.text((180, y + 10), labels.get(user_id, user_id), fill="#26391f", font=text_font)
        draw.text((610, y + 12), f"{total} 次 / {days} 天", fill="#4d6f3e", font=small_font)
        y += 70

    return _to_base64(image)
