#!/usr/bin/env bash
set -euo pipefail

count="${SEARCH_COUNT:-10}"

if [[ ! "$count" =~ ^[0-9]+$ ]] || (( count < 1 || count > 20 )); then
  printf 'error: SEARCH_COUNT must be an integer from 1 to 20\n' >&2
  exit 2
fi

if [[ $# -eq 0 ]]; then
  printf 'usage: %s QUERY...\n' "$0" >&2
  printf 'requires: BRAVE_SEARCH_API_KEY\n' >&2
  exit 2
fi

if [[ -z "${BRAVE_SEARCH_API_KEY:-}" ]]; then
  printf 'error: set BRAVE_SEARCH_API_KEY\n' >&2
  exit 2
fi

query="$*"

curl -fsSG --connect-timeout 10 --max-time 30 'https://api.search.brave.com/res/v1/web/search' \
  -H 'Accept: application/json' \
  -H "X-Subscription-Token: ${BRAVE_SEARCH_API_KEY}" \
  --data-urlencode "q=${query}" \
  --data-urlencode "count=${count}" \
| jq -r '
  if ((.web.results // []) | length) > 0 then
    .web.results[]
    | "TITLE: \(.title)\nURL: \(.url)\nDESC: \(.description // "")\n"
  else
    "NO_WEB_RESULTS"
  end
'
