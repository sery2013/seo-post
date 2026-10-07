"""GitHub Actions schedule gate with same-day catch-up and retry support."""

from __future__ import annotations

import os
import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


MOSCOW = ZoneInfo("Europe/Moscow")
SLOTS = (9, 15, 21)
TIMESTAMP_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC\]")
SLOT_RE = re.compile(r"\[slot:([^\]]+)\]")


def _slot_id(day: date, hour: int) -> str:
    return f"{day.isoformat()}-{hour:02d}"


def decide(
    now: datetime,
    links_text: str,
    event_name: str = "schedule",
    run_id: str = "manual",
    schedule_start_at: datetime | None = None,
) -> tuple[bool, str, str]:
    """Return (should_run, slot_id, reason) for the current workflow check."""
    if event_name == "workflow_dispatch":
        return True, f"manual-{run_id}", "ручной запуск"

    local_now = now.astimezone(MOSCOW)
    today = local_now.date()
    start = (schedule_start_at or datetime.combine(today, time.min, tzinfo=MOSCOW)).astimezone(MOSCOW)
    candidate_days = (
        (start.date() + (date.resolution * offset) for offset in range((today - start.date()).days + 1))
        if start.date() <= today
        else ()
    )
    completed: set[str] = set()
    published_today = 0

    for line in links_text.splitlines():
        timestamp_match = TIMESTAMP_RE.match(line)
        published_local = None
        if timestamp_match:
            published_utc = datetime.strptime(
                timestamp_match.group(1), "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
            published_local = published_utc.astimezone(MOSCOW)
            if published_local.date() == today:
                published_today += 1

        slot_match = SLOT_RE.search(line)
        if slot_match:
            completed.add(slot_match.group(1))
        elif published_local and start.date() <= published_local.date() <= today:
            # Legacy links have no slot marker. Treat a post made after a slot
            # and before the next one as that slot, preventing duplicates on
            # the first day after upgrading this bot.
            for index, hour in enumerate(SLOTS):
                next_hour = SLOTS[index + 1] if index + 1 < len(SLOTS) else 24
                if hour <= published_local.hour < next_hour:
                    completed.add(_slot_id(published_local.date(), hour))
                    break

    if published_today >= len(SLOTS):
        return False, "", "сегодня уже опубликовано 3 поста"

    for day in candidate_days:
        for hour in SLOTS:
            scheduled = datetime.combine(day, time(hour=hour), tzinfo=MOSCOW)
            current_slot = _slot_id(day, hour)
            if start <= scheduled <= local_now and current_slot not in completed:
                return True, current_slot, f"пропущенный/текущий слот {day} {hour:02d}:00 МСК"

    return False, "", "пока нет неопубликованного слота"


def main() -> None:
    links_text = Path("links.txt").read_text(encoding="utf-8") if Path("links.txt").exists() else ""
    event_name = os.getenv("GITHUB_EVENT_NAME", "schedule")
    run_id = os.getenv("GITHUB_RUN_ID", "manual")
    start_raw = os.getenv("SCHEDULE_START_AT", "")
    schedule_start_at = datetime.fromisoformat(start_raw) if start_raw else None
    now = datetime.now(MOSCOW)
    should_run, slot_id, reason = decide(now, links_text, event_name, run_id, schedule_start_at)

    print(f"Время МСК: {now:%Y-%m-%d %H:%M}")
    print(f"Решение: {'запуск' if should_run else 'пропуск'} — {reason}")
    if slot_id:
        print(f"Слот: {slot_id}")

    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"should_run={'true' if should_run else 'false'}\n")
            output.write(f"slot_id={slot_id}\n")


if __name__ == "__main__":
    main()
