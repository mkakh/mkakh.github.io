#!/usr/bin/env bash
set -euo pipefail

source_name="all"
limit="${PAPER_SEARCH_LIMIT:-5}"

usage() {
  printf 'usage: %s [--source all|openalex|arxiv] [--limit N] QUERY...\n' "$0" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      source_name="${2:?missing source}"
      shift 2
      ;;
    --limit)
      limit="${2:?missing limit}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      printf 'error: unknown option: %s\n' "$1" >&2
      usage
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -eq 0 ]]; then
  usage
  exit 2
fi

query="$*"

if [[ ! "$limit" =~ ^[0-9]+$ ]] || (( limit < 1 || limit > 50 )); then
  printf 'error: limit must be an integer from 1 to 50\n' >&2
  exit 2
fi

case "$source_name" in
  all|openalex|arxiv) ;;
  *)
    printf 'error: invalid source: %s\n' "$source_name" >&2
    usage
    exit 2
    ;;
esac

search_openalex() {
  printf '== OpenAlex ==\n'
  local response
  if ! response="$(curl -fsSG --connect-timeout 10 --max-time 30 'https://api.openalex.org/works' \
    --data-urlencode "search=${query}" \
    --data-urlencode "per-page=${limit}")"; then
    printf 'OPENALEX_ERROR\n\n'
    return 1
  fi

  local formatted
  if ! formatted="$(jq -r '
      if (.results | type) != "array" or (.results | length) == 0 then
        "NO_OPENALEX_RESULTS"
      else
        .results[]
        | [
            "TITLE: \(.title // "")",
            "YEAR: \(.publication_year // "")",
            "DOI: \(.doi // "")",
            "URL: \(.primary_location.landing_page_url // .id // "")",
            "ABSTRACT: \(
              if .abstract_inverted_index then
                .abstract_inverted_index
                | to_entries
                | map(. as $entry | $entry.value[] as $pos | {pos: $pos, word: $entry.key})
                | sort_by(.pos)
                | map(.word)
                | join(" ")
              else
                ""
              end
            )"
          ]
        | join("\n") + "\n"
      end
    ' <<<"${response}")"; then
    printf 'OPENALEX_PARSE_ERROR\n\n'
    return 1
  fi
  printf '%s\n' "$formatted"
}

search_arxiv() {
  printf '== arXiv ==\n'
  local response
  if ! response="$(curl -fsSG --connect-timeout 10 --max-time 30 'https://export.arxiv.org/api/query' \
    --data-urlencode "search_query=all:${query}" \
    --data-urlencode 'start=0' \
    --data-urlencode "max_results=${limit}")"; then
    printf 'ARXIV_ERROR\n\n'
    return 1
  fi

  local formatted
  if ! formatted="$(python3 -c '
import sys
import xml.etree.ElementTree as ET

ns = {"atom": "http://www.w3.org/2005/Atom"}
root = ET.fromstring(sys.stdin.read())
entries = root.findall("atom:entry", ns)
if not entries:
    print("NO_ARXIV_RESULTS")
for entry in entries:
    title = " ".join(entry.findtext("atom:title", default="", namespaces=ns).split())
    published = entry.findtext("atom:published", default="", namespaces=ns)[:10]
    url = entry.findtext("atom:id", default="", namespaces=ns)
    summary = " ".join(entry.findtext("atom:summary", default="", namespaces=ns).split())
    authors = ", ".join(
        name.text or ""
        for name in entry.findall("atom:author/atom:name", ns)
    )
    print(f"TITLE: {title}")
    print(f"DATE: {published}")
    print(f"AUTHORS: {authors}")
    print(f"URL: {url}")
    print(f"ABSTRACT: {summary}")
    print()
' <<<"${response}")"; then
    printf 'ARXIV_PARSE_ERROR\n\n'
    return 1
  fi
  printf '%s\n' "$formatted"
}

success_count=0
if [[ "$source_name" == "all" || "$source_name" == "openalex" ]]; then
  if search_openalex; then
    ((success_count += 1))
  fi
fi

if [[ "$source_name" == "all" || "$source_name" == "arxiv" ]]; then
  if search_arxiv; then
    ((success_count += 1))
  fi
fi

if (( success_count == 0 )); then
  printf 'error: all selected academic providers failed\n' >&2
  exit 1
fi
