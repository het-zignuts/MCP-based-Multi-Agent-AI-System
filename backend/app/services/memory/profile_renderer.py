from dataclasses import dataclass
from datetime import datetime, timezone


MAX_PROFILE_ITEMS_PER_SECTION = 5
PROFILE_SECTIONS = ("preferences", "facts", "active_goals", "decisions")


@dataclass
class RenderedUserProfile:
    profile_items: list[dict]
    profile_text: str
    preferences: list[str]
    facts: list[str]
    active_goals: list[str]
    decisions: list[str]

    def to_text(self) -> str:
        return self.profile_text


def _parse_iso_datetime(value) -> datetime:
    if not value:
        return datetime.min
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    try:
        normalized = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _item_rank(item: dict) -> tuple[float, float, float]:
    try:
        confidence = float(item.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    try:
        update_count = float(item.get("update_count", 1) or 1)
    except (TypeError, ValueError):
        update_count = 1.0

    confirmed_at = _parse_iso_datetime(
        item.get("last_confirmed_at") or item.get("updated_at") or item.get("first_seen_at")
    )
    return confidence, update_count, confirmed_at.timestamp()


def _item_text(item: dict) -> str:
    summary = str(item.get("summary", "") or "").strip()
    if summary:
        return summary

    label = str(item.get("label", "") or "").strip()
    value = str(item.get("value", "") or "").strip()
    if label and value:
        return f"{label}: {value}"
    return value or label


def _active_items(profile_items: list[dict]) -> list[dict]:
    active = [
        item
        for item in profile_items
        if isinstance(item, dict) and str(item.get("status", "active")).strip().lower() == "active"
    ]
    return sorted(active, key=_item_rank, reverse=True)


def render_profile_snapshot(profile_items: list[dict]) -> RenderedUserProfile:
    active_items = _active_items(profile_items)
    section_buckets = {section: [] for section in PROFILE_SECTIONS}

    for item in active_items:
        text = _item_text(item)
        if not text:
            continue

        section = str(item.get("section", "facts") or "facts").strip()
        if section not in section_buckets:
            section = "facts"

        if text in section_buckets[section]:
            continue

        if len(section_buckets[section]) < MAX_PROFILE_ITEMS_PER_SECTION:
            section_buckets[section].append(text)

    sections = []
    if section_buckets["preferences"]:
        sections.append(
            "User preferences:\n" + "\n".join(f"- {item}" for item in section_buckets["preferences"])
        )
    if section_buckets["facts"]:
        sections.append(
            "Known user facts:\n" + "\n".join(f"- {item}" for item in section_buckets["facts"])
        )
    if section_buckets["active_goals"]:
        sections.append(
            "Active user goals:\n" + "\n".join(f"- {item}" for item in section_buckets["active_goals"])
        )
    if section_buckets["decisions"]:
        sections.append(
            "Important user decisions:\n" + "\n".join(f"- {item}" for item in section_buckets["decisions"])
        )

    return RenderedUserProfile(
        profile_items=active_items,
        profile_text="\n\n".join(sections),
        preferences=section_buckets["preferences"],
        facts=section_buckets["facts"],
        active_goals=section_buckets["active_goals"],
        decisions=section_buckets["decisions"],
    )
