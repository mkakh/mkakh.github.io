#!/usr/bin/env bash
set -euo pipefail

search_type="search"
count="${SERPER_SEARCH_COUNT:-10}"
country="${SERPER_COUNTRY:-jp}"
language="${SERPER_LANGUAGE:-ja}"
location="${SERPER_LOCATION:-}"

usage() {
  printf 'usage: %s [--type search|places|scholar|images|news|shopping] [--count N] QUERY...\n' "$0" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --type) search_type="${2:?missing type}"; shift 2 ;;
    --count) count="${2:?missing count}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) printf 'error: unknown option: %s\n' "$1" >&2; usage; exit 2 ;;
    *) break ;;
  esac
done

if [[ $# -eq 0 ]]; then usage; exit 2; fi
if [[ -z "${SERPER_API_KEY:-}" ]]; then
  printf 'error: set SERPER_API_KEY\n' >&2
  exit 2
fi
if [[ ! "$count" =~ ^[0-9]+$ ]] || (( count < 1 || count > 20 )); then
  printf 'error: count must be an integer from 1 to 20\n' >&2
  exit 2
fi
case "$search_type" in
  search|places|scholar|images|news|shopping) ;;
  *) printf 'error: unsupported type: %s\n' "$search_type" >&2; exit 2 ;;
esac

query="$*"
payload="$(jq -cn \
  --arg q "$query" \
  --arg gl "$country" \
  --arg hl "$language" \
  --arg location "$location" \
  --argjson num "$count" \
  '{q:$q, gl:$gl, hl:$hl, num:$num} + if $location == "" then {} else {location:$location} end')"

response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT

curl_exit=0
http_status="$(curl -sS --connect-timeout 10 --max-time 30 \
  -o "$response_file" \
  -w '%{http_code}' \
  -X POST "https://google.serper.dev/${search_type}" \
  -H 'Content-Type: application/json' \
  -H "X-API-KEY: ${SERPER_API_KEY}" \
  --data "$payload")" || curl_exit=$?

if (( curl_exit != 0 )); then
  printf 'error: Serper transport failure (curl exit %d)\n' "$curl_exit" >&2
  exit 4
fi

case "$http_status" in
  2??) ;;
  408|425|429|5??)
    printf 'error: Serper transient HTTP status %s\n' "$http_status" >&2
    exit 4
    ;;
  401|403)
    printf 'error: Serper authentication rejected with HTTP status %s\n' "$http_status" >&2
    exit 3
    ;;
  4??)
    printf 'error: Serper request rejected with HTTP status %s\n' "$http_status" >&2
    exit 3
    ;;
  *)
    printf 'error: Serper unexpected HTTP status %s\n' "$http_status" >&2
    exit 3
    ;;
esac

if ! jq -e . "$response_file" >/dev/null; then
  printf 'error: Serper returned invalid JSON\n' >&2
  exit 4
fi

response="$(<"$response_file")"

formatted="$(jq -r --arg type "$search_type" --argjson limit "$count" '
  def text:
    if . == null then ""
    elif type == "string" then .
    else tojson
    end;

  def present:
    . != null and . != "" and . != [] and . != {};

  if $type == "scholar" then
    (.organic // [])[0:$limit][]
    | "TITLE: \(.title // "")\nURL: \(.link // "")\nPUBLICATION: \(if (.publicationInfo | type) == "object" then (.publicationInfo.summary // "") else (.publicationInfo // "") end)\nCITED BY: \((.citedBy // "") | tostring)\nDESC: \(.snippet // "")\n"
  elif $type == "places" then
    (.places // [])[0:$limit][]
    | "TITLE: \(.title // "")\nADDRESS: \(.address // "")\nCATEGORY: \(.category // "")\nRATING: \(.rating // "") (\(.ratingCount // ""))\nPHONE: \(.phoneNumber // "")\nWEBSITE: \(.website // "")\n"
  elif $type == "images" then
    (.images // [])[0:$limit][]
    | "TITLE: \(.title // "")\nURL: \(.link // "")\nIMAGE: \(.imageUrl // "")\nSOURCE: \(.source // "")\n"
  elif $type == "shopping" then
    (.shopping // [])[0:$limit][]
    | "TITLE: \(.title // "")\nPRICE: \(.price // "")\nSOURCE: \(.source // "")\nURL: \(.link // "")\nRATING: \(.rating // "") (\(.ratingCount // ""))\n"
  elif $type == "news" then
    (.news // [])[0:$limit][]
    | "TITLE: \(.title // "")\nURL: \(.link // "")\nDATE: \(.date // "")\nSOURCE: \(.source // "")\nDESC: \(.snippet // "")\n"
  else
    if ((.organic // []) | length) > 0 then
      (.organic // [])[0:$limit][]
      | "TITLE: \(.title // "")\nURL: \(.link // "")\nDESC: \(.snippet // "")\n"
    else
      (
        [
          if ((.answerBox | type) == "object" and
              ([.answerBox.title, .answerBox.link, .answerBox.answer, .answerBox.snippet, .answerBox.result, .answerBox.list, .answerBox.table] | any(present))) then
            "TYPE: ANSWER_BOX\nTITLE: \((.answerBox.title // "") | text)\nURL: \((.answerBox.link // "") | text)\nANSWER: \((.answerBox.answer // .answerBox.snippet // .answerBox.result // .answerBox.list // .answerBox.table // "") | text)\n"
          else empty end,
          if ((.knowledgeGraph | type) == "object" and
              ([.knowledgeGraph.title, .knowledgeGraph.website, .knowledgeGraph.descriptionLink, .knowledgeGraph.description, .knowledgeGraph.type] | any(present))) then
            "TYPE: KNOWLEDGE_GRAPH\nTITLE: \((.knowledgeGraph.title // "") | text)\nURL: \((.knowledgeGraph.website // .knowledgeGraph.descriptionLink // "") | text)\nDESC: \((.knowledgeGraph.description // .knowledgeGraph.type // "") | text)\n"
          else empty end
        ]
        + [
          (.peopleAlsoAsk // [])[0:$limit][]
          | select([.question, .link, .snippet, .answer] | any(present))
          | "TYPE: RELATED_ANSWER\nTITLE: \((.question // "") | text)\nURL: \((.link // "") | text)\nDESC: \((.snippet // .answer // "") | text)\n"
        ]
        + [
          (.topStories // [])[0:$limit][]
          | select([.title, .link] | any(present))
          | "TYPE: TOP_STORY\nTITLE: \((.title // "") | text)\nURL: \((.link // "") | text)\nSOURCE: \((.source // "") | text)\nDATE: \((.date // "") | text)\n"
        ]
      )[]
    end
  end
' <<<"$response")"

if [[ -z "$formatted" ]]; then
  printf 'NO_SERPER_RESULTS\n'
else
  printf '%s\n' "$formatted"
fi
