#!/usr/bin/env python3
"""Gate data-only conference PRs against the immutable GitHub event base SHA.

The workflow executes this file from the base commit, not from the PR tree.
"""
import argparse
from datetime import date
import ipaddress
import json
import re
import subprocess
from urllib.parse import urlsplit

FIELDS = frozenset({"acronym", "title", "rank", "rating", "deadline", "fullDeadline", "url"})
MUTABLE = frozenset({"deadline", "fullDeadline", "url", "rating"})
DATA = "data/conferences.json"
ALLOWED_PATHS = frozenset({DATA, "index.html", "version.json"})
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
RATING = re.compile(r"(?:[0-4]\.[0-9]|5\.0)\Z")
VERSION = re.compile(r"[0-9a-f]{16}\Z")
URL_CHARS = re.compile(r"[A-Za-z0-9\-._~:/?#\[\]@!$&()*+,;=%]+\Z")


class InvalidPR(ValueError):
    pass


def git(*args):
    return subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE).stdout


def decode_json(raw, label):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InvalidPR(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(raw, object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidPR(f"{label}: invalid JSON: {exc}") from exc


def validate_date(value, name):
    if value == "N/A":
        return
    if not isinstance(value, str) or not DATE.fullmatch(value):
        raise InvalidPR(f"{name}: expected YYYY-MM-DD or N/A")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidPR(f"{name}: invalid calendar date") from exc


def validate_url(value, name):
    if not isinstance(value, str) or not URL_CHARS.fullmatch(value):
        raise InvalidPR(f"{name}: expected a safe absolute HTTP(S) URL")
    if re.search(r"%(?![0-9a-fA-F]{2})", value):
        raise InvalidPR(f"{name}: malformed percent escape")
    try:
        url = urlsplit(value)
        host = url.hostname
        port = url.port  # Forces validation of malformed port numbers.
    except ValueError as exc:
        raise InvalidPR(f"{name}: malformed URL") from exc
    if (url.scheme not in ("http", "https") or not host or url.username is not None
            or url.password is not None or "@" in url.netloc or not url.netloc
            or port == 0 or host.endswith(".") or host == "localhost"
            or host.endswith(".localhost")):
        raise InvalidPR(f"{name}: expected a public HTTP(S) host without credentials")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", host):
            raise InvalidPR(f"{name}: invalid host")
    else:
        raise InvalidPR(f"{name}: IP address URL is not an official public host")


def validate_rows(base, head):
    if not isinstance(base, list) or not isinstance(head, list) or not base:
        raise InvalidPR("conference data must be nonempty lists")
    if len(base) != len(head):
        raise InvalidPR("master-list membership changed")
    seen = set()
    for index, (old, new) in enumerate(zip(base, head)):
        if not isinstance(old, dict) or not isinstance(new, dict) or set(old) != FIELDS or set(new) != FIELDS:
            raise InvalidPR(f"row {index}: unexpected schema")
        name = old["acronym"]
        if not isinstance(name, str) or not name or name in seen:
            raise InvalidPR(f"row {index}: invalid or duplicate base acronym")
        seen.add(name)
        for field in FIELDS - MUTABLE:
            if type(old[field]) is not str or type(new[field]) is not str or old[field] != new[field]:
                raise InvalidPR(f"row {index}: immutable {field} changed")
        for field in ("deadline", "fullDeadline"):
            validate_date(new[field], f"{name}.{field}")
        validate_url(new["url"], f"{name}.url")
        if not isinstance(new["rating"], str) or (new["rating"] != "N/A" and not RATING.fullmatch(new["rating"])):
            raise InvalidPR(f"{name}.rating: invalid rating")


def validate_changed_paths(paths):
    unexpected = set(paths) - ALLOWED_PATHS
    if unexpected:
        raise InvalidPR(f"non-data maintenance paths changed: {sorted(unexpected)}")
    if DATA not in paths:
        raise InvalidPR("no conference-data update")


def validate_version(data, html, version):
    import hashlib

    expected = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                         separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    if not isinstance(version, dict) or set(version) != {"version"} or version["version"] != expected:
        raise InvalidPR("version.json does not match conference data")
    if not VERSION.fullmatch(expected):
        raise InvalidPR("invalid generated version")
    expected_script = "const BUILD_VERSION = " + json.dumps(expected) + ";\nconst DATA = " + json.dumps(
        data, ensure_ascii=False, indent=2) + ";"
    if html.count(expected_script) != 1:
        raise InvalidPR("index.html embedded data or version does not match conference data")


def validate_regular_blob(revision, path):
    entries = git("ls-tree", revision, "--", path).splitlines()
    if len(entries) != 1 or not entries[0].startswith(b"100644 blob "):
        raise InvalidPR(f"{path}: expected a regular tracked file at {revision}")

def validate(base_sha, head_sha):
    if not re.fullmatch(r"[0-9a-fA-F]{40}", base_sha):
        raise InvalidPR("base must be a full commit SHA from the GitHub event")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", head_sha):
        raise InvalidPR("head must be a full checked-out commit SHA")
    paths = [p.decode("utf-8") for p in git("diff", "--name-only", "-z", "--no-renames",
                                               base_sha, head_sha).split(b"\0") if p]
    validate_changed_paths(paths)
    for revision in (base_sha, head_sha):
        for path in ALLOWED_PATHS:
            validate_regular_blob(revision, path)
    def at(revision, path):
        return git("show", f"{revision}:{path}")
    base = decode_json(at(base_sha, DATA), "base conference data")
    head = decode_json(at(head_sha, DATA), "PR conference data")
    validate_rows(base, head)
    validate_version(head, at(head_sha, "index.html").decode("utf-8"),
                     decode_json(at(head_sha, "version.json"), "version.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_sha", help="github.event.pull_request.base.sha")
    parser.add_argument("head_sha", help="checked-out PR merge commit SHA")
    args = parser.parse_args()
    try:
        validate(args.base_sha, args.head_sha)
    except (InvalidPR, subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        parser.exit(1, f"conference PR rejected: {exc}\n")
    print("Conference PR data, master list, and generated artifacts match the base contract.")


if __name__ == "__main__":
    main()
