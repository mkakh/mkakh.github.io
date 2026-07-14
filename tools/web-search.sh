#!/usr/bin/env bash
set -euo pipefail

provider="auto"
search_type="search"
count="10"

usage() {
  cat >&2 <<'EOF'
usage: web-search.sh [--provider auto|serper|brave|both]
                     [--type search|places|scholar|images|news|shopping]
                     [--count N] QUERY...

auto uses Serper first and falls back to Brave on a transient Serper failure
after one retry.
An empty Serper result asks for query reformulation instead of spending Brave.
Non-web types are Serper-only. Use both selectively because it spends one
request from each provider.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider) provider="${2:?missing provider}"; shift 2 ;;
    --type) search_type="${2:?missing type}"; shift 2 ;;
    --count) count="${2:?missing count}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) printf 'error: unknown option: %s\n' "$1" >&2; usage; exit 2 ;;
    *) break ;;
  esac
done

if [[ $# -eq 0 ]]; then usage; exit 2; fi
if [[ ! "$count" =~ ^[0-9]+$ ]] || (( count < 1 || count > 20 )); then
  printf 'error: count must be an integer from 1 to 20\n' >&2
  exit 2
fi
case "$provider" in auto|serper|brave|both) ;; *) printf 'error: invalid provider: %s\n' "$provider" >&2; exit 2 ;; esac
case "$search_type" in search|places|scholar|images|news|shopping) ;; *) printf 'error: invalid type: %s\n' "$search_type" >&2; exit 2 ;; esac
if [[ "$search_type" != "search" && ( "$provider" == "brave" || "$provider" == "both" ) ]]; then
  printf 'error: provider %s does not support type %s\n' "$provider" "$search_type" >&2
  exit 2
fi

root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
query="$*"
serper_query="$query"

load_serper_key() {
  if [[ -z "${SERPER_API_KEY:-}" && -r "$root_dir/secrets/serper.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    . "$root_dir/secrets/serper.env"
    set +a
  fi
}

load_brave_key() {
  if [[ -z "${BRAVE_SEARCH_API_KEY:-}" && -r "$root_dir/secrets/brave-search.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    . "$root_dir/secrets/brave-search.env"
    set +a
  fi
}

run_serper() {
  load_serper_key
  SERPER_SEARCH_COUNT="$count" "$root_dir/tools/serper-search.sh" --type "$search_type" --count "$count" "$serper_query"
}

run_brave() {
  load_brave_key
  SEARCH_COUNT="$count" "$root_dir/tools/search.sh" "$query"
}

provider_notice() {
  printf 'notice: search_provider=%s search_type=%s\n' "$1" "$search_type" >&2
}

provider_output=""
provider_state=""

capture_provider() {
  local command_name="$1"
  local captured=""
  local command_status=0

  captured="$($command_name)" || command_status=$?
  if (( command_status != 0 )); then
    provider_output=""
    if [[ "$command_name" == "run_serper" ]]; then
      case "$command_status" in
        2) provider_state="configuration" ;;
        3) provider_state="rejected" ;;
        4) provider_state="transient" ;;
        *) provider_state="failed" ;;
      esac
    else
      provider_state="failed"
    fi
    return 1
  fi

  if [[ -z "$captured" || "$captured" =~ ^NO_[A-Z_]+_RESULTS$ ]]; then
    provider_output=""
    provider_state="empty"
    return 1
  fi

  provider_output="$captured"
  provider_state="success"
  return 0
}

serper_relaxed_queries=()

build_serper_relaxed_queries() {
  local original="$1"
  local token=""
  local normalized_token=""
  local site_count=0
  local has_site_path=0
  local normalized_tokens=()
  local tokens=()

  serper_relaxed_queries=()
  read -r -a tokens <<<"$original"

  for token in "${tokens[@]}"; do
    normalized_token="$token"
    if [[ "$token" =~ ^site: ]]; then
      ((site_count += 1))
      if [[ "$token" =~ ^site:([^/[:space:]]+)/.+$ ]]; then
        normalized_token="site:${BASH_REMATCH[1]}"
        has_site_path=1
      fi
    fi

    normalized_tokens+=("$normalized_token")
  done

  if (( site_count == 1 && has_site_path == 1 && ${#normalized_tokens[@]} > 0 )); then
    serper_relaxed_queries+=("${normalized_tokens[*]}")
  fi
}

run_serper_with_transient_retry() {
  local attempt=1

  while (( attempt <= 2 )); do
    if capture_provider run_serper; then
      return 0
    fi
    if [[ "$provider_state" != "transient" || "$attempt" -ge 2 ]]; then
      return 1
    fi
    printf 'notice: Serper transient failure; retrying once with the same query\n' >&2
    ((attempt += 1))
  done
  return 1
}

try_serper() {
  local fallback_state="empty"
  local relaxed_query=""

  serper_query="$query"
  if run_serper_with_transient_retry; then
    return 0
  fi
  if [[ "$provider_state" != "empty" || "$search_type" != "search" ]]; then
    return 1
  fi

  build_serper_relaxed_queries "$query"
  for relaxed_query in "${serper_relaxed_queries[@]}"; do
    printf 'notice: Serper returned no results; retrying with relaxed query: %s\n' "$relaxed_query" >&2
    serper_query="$relaxed_query"
    if run_serper_with_transient_retry; then
      return 0
    fi
    if [[ "$provider_state" != "empty" ]]; then fallback_state="$provider_state"; fi
  done

  provider_state="$fallback_state"
  return 1
}

report_provider_error() {
  local provider_name="$1"
  case "$provider_state" in
    empty) printf 'error: %s returned no results\n' "$provider_name" >&2 ;;
    configuration) printf 'error: %s configuration failed\n' "$provider_name" >&2 ;;
    rejected) printf 'error: %s request was rejected\n' "$provider_name" >&2 ;;
    transient) printf 'error: %s remained unavailable after retry\n' "$provider_name" >&2 ;;
    *) printf 'error: %s request failed\n' "$provider_name" >&2 ;;
  esac
}

case "$provider" in
  serper)
    if try_serper; then
      provider_notice serper
      printf '%s\n' "$provider_output"
    else
      report_provider_error Serper
      exit 1
    fi
    ;;
  brave)
    if capture_provider run_brave; then
      provider_notice brave
      printf '%s\n' "$provider_output"
    else
      report_provider_error Brave
      exit 1
    fi
    ;;
  both)
    both_success=0
    printf '== Serper ==\n'
    if try_serper; then
      provider_notice serper
      printf '%s\n' "$provider_output"
      both_success=1
    else
      printf 'notice: Serper %s; continuing with Brave\n' "$provider_state" >&2
      printf 'NO_SERPER_RESULTS\n'
    fi
    printf '\n== Brave ==\n'
    if capture_provider run_brave; then
      provider_notice brave
      printf '%s\n' "$provider_output"
      both_success=1
    else
      printf 'notice: Brave %s\n' "$provider_state" >&2
      printf 'NO_BRAVE_RESULTS\n'
    fi
    if (( both_success == 0 )); then exit 1; fi
    ;;
  auto)
    if [[ "$search_type" != "search" ]]; then
      if try_serper; then
        provider_notice serper
        printf '%s\n' "$provider_output"
      else
        printf 'error: Serper %s; no equivalent Brave endpoint for type %s\n' "$provider_state" "$search_type" >&2
        exit 1
      fi
      exit 0
    fi

    if try_serper; then
      provider_notice serper
      printf '%s\n' "$provider_output"
      exit 0
    fi

    if [[ "$provider_state" == "empty" ]]; then
      printf 'error: Serper returned no results after targeted retries; reformulate the Serper query or explicitly use --provider brave\n' >&2
      exit 1
    fi

    if [[ "$provider_state" != "transient" ]]; then
      report_provider_error Serper
      exit 1
    fi

    printf 'notice: Serper remained unavailable after retry; falling back to Brave\n' >&2
    if capture_provider run_brave; then
      provider_notice brave
      printf '%s\n' "$provider_output"
    else
      printf 'error: Brave fallback %s\n' "$provider_state" >&2
      exit 1
    fi
    ;;
esac
