#!/usr/bin/env python3
import json
import os
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "conferences.json"
SUMMARY_PATH = ROOT / "update-summary.md"


def parse_date(value):
    if not value or value == "N/A":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def key(conf):
    return conf["acronym"]


def index_by_acronym(conferences):
    return {key(conf): conf for conf in conferences}


def build_summary(original, updated, today):
    original_by_key = index_by_acronym(original)
    updated_by_key = index_by_acronym(updated)
    added_keys = sorted(set(updated_by_key) - set(original_by_key))
    removed_keys = sorted(set(original_by_key) - set(updated_by_key))
    changed_keys = sorted(
        k
        for k in set(original_by_key) & set(updated_by_key)
        if original_by_key[k] != updated_by_key[k]
    )
    expired = sorted(
        (
            conf
            for conf in updated
            if (full_deadline := parse_date(conf.get("fullDeadline"))) is not None
            and full_deadline < today
        ),
        key=key,
    )
    unknown_deadline = sorted(
        conf["acronym"] for conf in updated if conf.get("fullDeadline") == "N/A"
    )

    lines = [
        "# Conference deadline update",
        "",
        f"Generated on {today.isoformat()}.",
        "",
        "Rule: the conference list is a fixed CORE/ICORE genre master list. "
        "Automation may update deadlines and URLs, but must not add or remove "
        "conference entries. The abstract deadline may already be past. Entries "
        "with `N/A` full paper deadline are kept for manual review.",
        "",
        f"- Master list size: {len(updated)} conferences",
        f"- Unexpected additions: {len(added_keys)} conferences",
        f"- Unexpected removals: {len(removed_keys)} conferences",
        f"- Expired full paper deadlines: {len(expired)} conferences",
        f"- Unknown full paper deadline: {len(unknown_deadline)} conferences",
        "",
        "## Updated Deadlines or URLs",
        "",
    ]

    if changed_keys:
        for acronym in changed_keys:
            before = original_by_key[acronym]
            after = updated_by_key[acronym]
            changes = []
            for field in ("rank", "rating", "deadline", "fullDeadline", "url"):
                if before.get(field) != after.get(field):
                    changes.append(f"{field}: {before.get(field)} -> {after.get(field)}")
            lines.append(f"- {acronym}: " + "; ".join(changes))
    else:
        lines.append("- None")

    lines.extend(["", "## Expired Full Paper Deadlines", ""])
    if expired:
        lines.append("These entries remain in `data/conferences.json`.")
        lines.append("")
        for conf in expired:
            lines.append(f"- {conf['acronym']}: {conf.get('fullDeadline', 'N/A')}")
    else:
        lines.append("- None")

    lines.extend(["", "## Unexpected Master List Changes", ""])
    if added_keys or removed_keys:
        for acronym in added_keys:
            lines.append(f"- Unexpected addition: {acronym}")
        for acronym in removed_keys:
            lines.append(f"- Unexpected removal: {acronym}")
    else:
        lines.append("- None")

    lines.extend(["", "## Unknown Full Paper Deadline", ""])
    if unknown_deadline:
        lines.extend(f"- {acronym}" for acronym in unknown_deadline)
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def main():
    today = date.fromisoformat(os.environ.get("TODAY", date.today().isoformat()))
    original = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    updated = original

    DATA_PATH.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    SUMMARY_PATH.write_text(
        build_summary(original, updated, today),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
