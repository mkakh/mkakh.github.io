#!/usr/bin/env python3
import json
import os
import re
from copy import deepcopy
from datetime import date
from html import unescape
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "conferences.json"
SUMMARY_PATH = ROOT / "update-summary.md"
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


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


def fetch_text(url):
    request = Request(url, headers={"User-Agent": "conference-deadline-updater"})
    with urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8", errors="replace")
    text = re.sub(r"(?i)<(script|style).*?</\1>", " ", raw, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[\u200b-\u206f\ufeff]", " ", text)
    return re.sub(r"\s+", " ", text)


def parse_human_date(value):
    value = re.sub(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", "", value, flags=re.I)
    value = value.replace(",", " ")
    value = re.sub(r"\s+", " ", value).strip()
    parts = value.split()
    if len(parts) != 3:
        return None
    if parts[0].isdigit():
        day = int(parts[0])
        month = MONTHS.get(parts[1].lower())
        year = int(parts[2])
    elif parts[1].isdigit():
        month = MONTHS.get(parts[0].lower())
        day = int(parts[1])
        year = int(parts[2])
    else:
        return None
    if month is None:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


DATE_PATTERN = (
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*"
    r"(?:\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})"
)
UPDATE_MARKER_PATTERN = r"(?:updated|extended|revised|postponed)"


def find_researchr_deadline(text, label_pattern):
    # researchr renders some schedules as label -> date and others as date ->
    # label. The opposite orientation silently assigns an adjacent event's date.
    section = re.search("Important Dates", text, flags=re.I)
    if section:
        tail = text[section.end():]
        next_section = re.search("Important Dates", tail, flags=re.I)
        schedule = tail[:next_section.start() if next_section else 1000]
        first_date = re.search(DATE_PATTERN, schedule, flags=re.I)
        first_label = re.search(
            r"(?:Abstract|Paper|Full Paper|Submission)[ ]+Submission[ ]+Deadline|"
            r"Abstract[ ]+Submission[ ]+Deadline|Submission[ ]+Deadline",
            schedule, flags=re.I,
        )
        if first_label and first_date and first_label.start() < first_date.start():
            values = re.findall(
                rf"{label_pattern}[ ]*(?:\([^)]*\))?[ ]*:?[ ]*({DATE_PATTERN})",
                schedule, flags=re.I,
            )
            if values:
                return parse_human_date(values[-1])
    date_before = re.findall(
        rf"({DATE_PATTERN})\s+{UPDATE_MARKER_PATTERN}\s+{label_pattern}",
        text,
        flags=re.I,
    )
    if date_before:
        return parse_human_date(date_before[-1])

    # researchr's Important Dates list puts the date before its label. Reading
    # the date after the label instead picks the next event's deadline.
    date_before = re.findall(
        rf"({DATE_PATTERN})\s+{label_pattern}", text, flags=re.I
    )
    if date_before:
        return parse_human_date(date_before[-1])

    label_before = re.findall(
        rf"{label_pattern}\s*(?:\([^)]*\))?\s*:?\s*({DATE_PATTERN})",
        text,
        flags=re.I,
    )
    if label_before:
        return parse_human_date(label_before[-1])
    return None


def extract_researchr_deadlines(url):
    text = fetch_text(url)
    abstract_deadline = find_researchr_deadline(
        text,
        r"Abstract\s+Submission\s+Deadline(?:\s*\([^)]*\))?",
    )
    full_deadline = find_researchr_deadline(
        text,
        r"(?:Full\s+Paper\s+Submission|Paper\s+Submission\s+Deadline|Submission\s+deadline)",
    )
    if abstract_deadline or full_deadline:
        return abstract_deadline, full_deadline
    return None


def extract_compsac_deadline(url):
    # A year-specific official CFP is required: the generic landing page may
    # point to a prior edition and must not resurrect an expired deadline.
    year_match = re.search(r"^https://ieeecompsac\.computer\.org/(20\d{2})/", url)
    if not year_match:
        return None
    text = fetch_text(url)
    matches = re.findall(r"Full papers due\s+(" + DATE_PATTERN + r")", text, flags=re.I)
    for value in matches:
        parsed = parse_human_date(value)
        if parsed and parsed.startswith(year_match.group(1) + "-"):
            return parsed
    return None


def extract_eics_deadline(url, today):
    # Select the next PACM full-paper round, not the notification/rebuttal dates.
    year_match = re.fullmatch(
        r"https://eics[.]acm[.]org/(20[0-9]{2})/contributions/full-papers[.]md",
        url,
    )
    if not year_match:
        return None
    text = fetch_text(url)
    if not re.search(r"EICS PACM[ ]+" + year_match.group(1), text, flags=re.I):
        return None
    candidates = [
        parsed
        for value in re.findall(r"Paper submissions:[ ]*(" + DATE_PATTERN + r")", text, flags=re.I)
        if (parsed := parse_human_date(value))
        and int(parsed[:4]) in (int(year_match.group(1)) - 1, int(year_match.group(1)))
        and parsed >= today.isoformat()
    ]
    return min(candidates) if candidates else None


def update_known_page_deadlines(conferences, today=None):
    if today is None:
        today = date.today()
    updated = deepcopy(conferences)
    for conf in updated:
        url = conf.get("url", "")
        try:
            if "conf.researchr.org" in url:
                deadlines = extract_researchr_deadlines(url)
            elif conf.get("acronym") == "COMPSAC":
                full_deadline = extract_compsac_deadline(url)
                deadlines = (full_deadline, full_deadline) if full_deadline else None
            elif conf.get("acronym") == "EICS":
                full_deadline = extract_eics_deadline(url, today)
                deadlines = (None, full_deadline) if full_deadline else None
            else:
                continue
        except (OSError, TimeoutError, URLError, ValueError):
            continue
        if not deadlines:
            continue
        abstract_deadline, full_deadline = deadlines
        if abstract_deadline:
            conf["deadline"] = abstract_deadline
        if full_deadline:
            conf["fullDeadline"] = full_deadline
    return updated


def reset_expired_full_deadlines(conferences, today):
    updated = deepcopy(conferences)
    for conf in updated:
        full_deadline = parse_date(conf.get("fullDeadline"))
        if full_deadline is not None and full_deadline < today:
            conf["deadline"] = "N/A"
            conf["fullDeadline"] = "N/A"
    return updated


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
        "conference entries. If only the abstract deadline has passed, keep the "
        "dates. If the full paper deadline has passed, reset both `deadline` and "
        "`fullDeadline` to `N/A` so the next announced cycle can be entered later.",
        "",
        f"- Master list size: {len(updated)} conferences",
        f"- Unexpected additions: {len(added_keys)} conferences",
        f"- Unexpected removals: {len(removed_keys)} conferences",
        f"- Expired full paper deadlines remaining: {len(expired)} conferences",
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
    updated = update_known_page_deadlines(original, today)
    updated = reset_expired_full_deadlines(updated, today)

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
