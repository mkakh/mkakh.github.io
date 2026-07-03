---
name: conference-deadline-review
description: Use when reviewing or editing this repository's conference deadline PRs, data/conferences.json changes, update-summary.md, or deadline/url changes for the fixed CORE/ICORE conference list. Applies when Codex is asked to manually review an update PR without using API automation.
---

# Conference Deadline Review

Use this skill for manual Codex review of conference update PRs in this repository.

## Fixed Rules

- Treat `data/conferences.json` as the fixed CORE/ICORE genre master list.
- Do not add or remove conference entries.
- Do not rename `acronym` values unless the user explicitly asks.
- Allowed fields to update: `deadline`, `fullDeadline`, `url`, and, when justified, `rating`.
- Changing `deadline` or `fullDeadline` to `N/A` is allowed when the date cannot be confirmed.
- If only the abstract deadline has passed, keep both dates.
- If `fullDeadline` has passed, reset both `deadline` and `fullDeadline` to `N/A`.
- A past `fullDeadline` must not remove the conference entry from the master list.

## Review Workflow

1. Inspect `git diff -- data/conferences.json update-summary.md`.
2. Confirm the acronym set is unchanged. If not, flag it as a rule violation.
3. For each `deadline`, `fullDeadline`, or `url` change, check whether the PR summary gives a plausible source or reason.
4. Treat changes to `N/A` as requiring manual confidence: confirm whether the source page lost the date or extraction likely failed.
5. For past `fullDeadline` values, confirm `deadline` and `fullDeadline` were reset to `N/A` and the entry was retained.
6. Rebuild with `python scripts/build_site.py` after data edits.

## Comment Shape

Prefer concise review comments:

```markdown
## Codex Review

Needs manual check:
- ACRONYM: fullDeadline changed `old -> N/A`; verify the CFP page still lacks a full paper deadline.

Looks OK:
- ACRONYM: URL changed to the current CFP page.

Rule violations:
- None
```
