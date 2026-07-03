---
name: conference-url-discovery
description: Use when searching for or validating newly published CFP/important-date URLs for existing conferences in this repository's fixed CORE/ICORE list, especially when GitHub Actions cannot confidently detect a new URL and the user wants local Codex-assisted discovery without API automation.
---

# Conference URL Discovery

Use this skill to help find newer CFP or important-date URLs for existing entries in `data/conferences.json`.

## Scope

- Only search for URLs for existing `acronym` entries.
- Never add a new conference because a new site was found.
- Never delete a conference because no current URL is found.
- Prefer official conference pages, Researchr pages, SIGPLAN pages, society pages, or established series pages.
- Avoid using aggregator pages as the primary URL unless no official page is available.

## Detection Reality

Automatic detection is possible only within bounded sources:

- Existing `url` redirects or content changes.
- Known series pages that list future editions.
- Predictable year URL patterns such as `/2027/`, `-2027`, or `2027.`.
- Pages linked from current official conference home pages.

General discovery of a newly created website is not reliable without a search engine or human/Codex web browsing. When bounded detection fails, recommend manual Codex review.

## Monthly Reminder

This repository uses a monthly GitHub Actions reminder issue for detection outside normal automation. The reminder should prompt a local Codex run, not Codex inside GitHub Actions.

Use the monthly check to review:

- A*, A, then B-ranked entries with `fullDeadline: "N/A"`.
- Entries whose `url` points to an old year, generic series page, or aggregator page.
- Entries close to likely submission season with no current CFP URL.

## Manual Workflow

1. Pick one acronym from `data/conferences.json`.
2. Check the existing `url`.
3. Look for links containing `cfp`, `call for papers`, `important dates`, `dates`, `submission`, or the next conference year.
4. If a stronger URL is found, update only `url`, `deadline`, and `fullDeadline`.
5. If dates cannot be confirmed, use `N/A`.
6. Run:

```bash
python scripts/build_site.py
python scripts/summarize_changes.py
```

7. In the PR/comment, include the old URL, new URL, and why the new URL is better.
