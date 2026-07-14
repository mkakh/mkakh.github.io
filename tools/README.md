# Search Tools

Use these helpers instead of scraping Google, Bing, or DuckDuckGo result pages.
They require `bash`, `curl`, and `jq`.

These tools are intended for local Codex-assisted research. GitHub Actions do
not call them or require their API keys.

## Default routed search

`web-search.sh` is the normal entry point. It loads ignored key files from
`secrets/`, uses Serper first, and reports the chosen provider on standard
error. A transient Serper failure is retried once before Brave fallback. A
valid empty response asks for a better Serper query rather than spending the
limited Brave quota. Use Brave explicitly only after reasonable Serper
reformulation still fails or when an independent index is useful.

```bash
./tools/web-search.sh 'ICSE 2027 submission deadline official'
./tools/web-search.sh --type scholar 'software model checking Rust'
./tools/web-search.sh --provider brave 'site:conf.researchr.org ICSE 2027 dates'
./tools/web-search.sh --provider both 'ICSE 2027 call for papers'
```

Serper receives ordinary domain-level `site:` operators unchanged. After a
valid empty response, the router can broaden `site:domain/path` to
`site:domain`. If a URL is already known, fetch it directly instead of relying
on broadened search ranking.

For ordinary web search, organic links are preferred. Answer-box,
knowledge-graph, related-answer, and top-story fields are only supplemental
discovery hints. Conference deadlines and other consequential facts still
need verification on the current primary source.

## Keys

Store the keys locally as:

```text
secrets/serper.env
secrets/brave-search.env
```

`web-search.sh` loads them automatically. Direct low-level use requires the
matching environment variable:

```bash
source secrets/serper.env
./tools/serper-search.sh --type scholar 'automatic Promela generation'

source secrets/brave-search.env
./tools/search.sh 'site:acm.org software verification conference'
```

Never commit either key.

## Academic metadata and preprints

`paper-search.sh` queries OpenAlex and arXiv without an API key. Use it alongside
Serper Scholar for structured paper metadata and preprints; verify titles,
authors, venues, years, DOI values, and citation claims against publisher or
repository pages before relying on them.

```bash
./tools/paper-search.sh 'Rust formal verification'
./tools/paper-search.sh --source openalex --limit 3 'model checking Rust'
./tools/paper-search.sh --source arxiv --limit 3 'Promela generation'
```

## Validation

```bash
bash -n tools/*.sh
shellcheck tools/*.sh
node --test tools/search-tools.test.mjs
./tools/web-search.sh --provider serper --count 3 'ICSE 2027 Research Track official'
```
