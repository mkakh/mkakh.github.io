#!/usr/bin/env python3
import json
import subprocess
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "conferences.json"
SUMMARY_PATH = ROOT / "update-summary.md"
TRACKED_FIELDS = ("deadline", "fullDeadline", "url", "rating")


def load_json(text):
    return json.loads(text)


def load_head_data():
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{DATA_PATH.relative_to(ROOT)}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    return load_json(result.stdout)


def load_worktree_data():
    return load_json(DATA_PATH.read_text(encoding="utf-8"))


def parse_date(value):
    if not value or value == "N/A":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def by_acronym(conferences):
    return {conf["acronym"]: conf for conf in conferences}


def format_change(before, after):
    parts = []
    for field in TRACKED_FIELDS:
        if before.get(field) != after.get(field):
            parts.append(f"{field}: {before.get(field)} -> {after.get(field)}")
    return "; ".join(parts)


def review_reasons(before, after):
    reasons = []
    if before.get("url") != after.get("url"):
        reasons.append("URL changed")
    for field in ("deadline", "fullDeadline"):
        if before.get(field) != after.get(field):
            reasons.append(f"{field} changed")
        if before.get(field) != "N/A" and after.get(field) == "N/A":
            reasons.append(f"{field} changed to N/A")
    return reasons


def main():
    today = date.today()
    before = load_head_data()
    after = load_worktree_data()

    if before is None:
        before = after

    before_by_key = by_acronym(before)
    after_by_key = by_acronym(after)
    added = sorted(set(after_by_key) - set(before_by_key))
    removed = sorted(set(before_by_key) - set(after_by_key))
    common = sorted(set(before_by_key) & set(after_by_key))
    changed = [
        acronym
        for acronym in common
        if any(
            before_by_key[acronym].get(field) != after_by_key[acronym].get(field)
            for field in TRACKED_FIELDS
        )
    ]
    expired = sorted(
        (
            conf
            for conf in after
            if (full_deadline := parse_date(conf.get("fullDeadline"))) is not None
            and full_deadline < today
        ),
        key=lambda conf: conf["acronym"],
    )
    unknown = sorted(
        conf["acronym"] for conf in after if conf.get("fullDeadline") == "N/A"
    )

    review_items = []
    for acronym in changed:
        reasons = review_reasons(before_by_key[acronym], after_by_key[acronym])
        if reasons:
            review_items.append((acronym, reasons))
    for acronym in added:
        review_items.append((acronym, ["Unexpected conference addition"]))
    for acronym in removed:
        review_items.append((acronym, ["Unexpected conference removal"]))

    lines = [
        "# Conference deadline update",
        "",
        f"Generated on {today.isoformat()}.",
        "",
        "Rule: the conference list is a fixed CORE/ICORE genre master list. "
        "Automation may update deadlines and URLs, including changing a deadline "
        "to `N/A` when it cannot be confirmed, but must not add or remove "
        "conference entries. The abstract deadline may already be past.",
        "",
        f"- Master list size: {len(after)} conferences",
        f"- Deadline/URL/rating changes: {len(changed)} conferences",
        f"- Unexpected additions: {len(added)} conferences",
        f"- Unexpected removals: {len(removed)} conferences",
        f"- Expired full paper deadlines: {len(expired)} conferences",
        f"- Unknown full paper deadline: {len(unknown)} conferences",
        "",
        "## Codex Review Recommended",
        "",
    ]

    if review_items:
        for acronym, reasons in review_items:
            lines.append(f"- {acronym}: {', '.join(reasons)}")
    else:
        lines.append("- None")

    lines.extend(["", "## Updated Deadlines, URLs, or Ratings", ""])
    if changed:
        for acronym in changed:
            lines.append(
                f"- {acronym}: "
                + format_change(before_by_key[acronym], after_by_key[acronym])
            )
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
    if added or removed:
        for acronym in added:
            lines.append(f"- Unexpected addition: {acronym}")
        for acronym in removed:
            lines.append(f"- Unexpected removal: {acronym}")
    else:
        lines.append("- None")

    lines.extend(["", "## Unknown Full Paper Deadline", ""])
    if unknown:
        lines.extend(f"- {acronym}" for acronym in unknown)
    else:
        lines.append("- None")

    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
