import test from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const mockCurlPrelude = [
  'mock_reply() {',
  '  local body="$1"',
  '  local status="$2"',
  '  local output_file=""',
  '  shift 2',
  '  while (( $# > 0 )); do',
  '    case "$1" in',
  '      -o|--output) output_file="$2"; shift 2 ;;',
  '      *) shift ;;',
  '    esac',
  '  done',
  '  if [[ -n "$output_file" ]]; then',
  '    printf "%s" "$body" > "$output_file"',
  '    printf "%s" "$status"',
  '  else',
  '    printf "%s\\n" "$body"',
  '  fi',
  '}'
].join('\n');

function withMockCurl(source, run) {
  const directory = mkdtempSync(path.join(tmpdir(), 'chat-search-test-'));
  const curl = path.join(directory, 'curl');
  writeFileSync(curl, `#!/usr/bin/env bash\n${mockCurlPrelude}\n${source}\n`);
  chmodSync(curl, 0o700);
  try {
    return run({ ...process.env, PATH: `${directory}:${process.env.PATH}` });
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

function runScript(script, args, env) {
  return spawnSync(path.join(root, script), args, {
    cwd: root,
    env,
    encoding: 'utf8'
  });
}

test('low-level web helpers report empty result sets', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* ]]; then
  mock_reply '{"organic":[]}' 200 "$@"
else
  mock_reply '{"web":{"results":[]}}' 200 "$@"
fi
`;
  withMockCurl(mock, (env) => {
    const brave = runScript('tools/search.sh', ['nothing'], { ...env, BRAVE_SEARCH_API_KEY: 'test' });
    assert.equal(brave.status, 0);
    assert.equal(brave.stdout.trim(), 'NO_WEB_RESULTS');

    const serper = runScript('tools/serper-search.sh', ['nothing'], { ...env, SERPER_API_KEY: 'test' });
    assert.equal(serper.status, 0);
    assert.equal(serper.stdout.trim(), 'NO_SERPER_RESULTS');
  });
});

test('serper-search reports missing key as a configuration error', () => {
  const env = { ...process.env };
  delete env.SERPER_API_KEY;
  const result = runScript('tools/serper-search.sh', ['example'], env);
  assert.equal(result.status, 2);
  assert.match(result.stderr, /set SERPER_API_KEY/);
});

test('web-search explicitly falls back from Serper to Brave', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* ]]; then
  exit 22
fi
mock_reply '{"web":{"results":[{"title":"Brave result","url":"https://example.com/","description":"ok"}]}}' 200 "$@"
`;
  withMockCurl(mock, (env) => {
    const result = runScript('tools/web-search.sh', ['--count', '1', 'example'], {
      ...env,
      SERPER_API_KEY: 'test',
      BRAVE_SEARCH_API_KEY: 'test'
    });
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    assert.match(result.stderr, /retrying once with the same query/);
    assert.match(result.stderr, /falling back to Brave/);
    assert.match(result.stderr, /search_provider=brave/);
    assert.match(result.stdout, /TITLE: Brave result/);
  });
});

test('web-search does not spend Brave after an empty Serper response', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* ]]; then
  mock_reply '{"organic":[]}' 200 "$@"
  exit 0
fi
mock_reply '{"web":{"results":[{"title":"Unexpected Brave result","url":"https://example.com/","description":"should not run"}]}}' 200 "$@"
`;
  withMockCurl(mock, (env) => {
    const result = runScript('tools/web-search.sh', ['nothing'], {
      ...env,
      SERPER_API_KEY: 'test',
      BRAVE_SEARCH_API_KEY: 'test'
    });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /reformulate the Serper query/);
    assert.doesNotMatch(result.stderr, /search_provider=brave/);
    assert.doesNotMatch(result.stdout, /Unexpected Brave result/);
  });
});

test('web-search both mode intentionally returns both indexes', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* ]]; then
  mock_reply '{"organic":[{"title":"Serper result","link":"https://serper.example/","snippet":"primary"}]}' 200 "$@"
else
  mock_reply '{"web":{"results":[{"title":"Brave result","url":"https://brave.example/","description":"secondary"}]}}' 200 "$@"
fi
`;
  withMockCurl(mock, (env) => {
    const result = runScript('tools/web-search.sh', ['--provider', 'both', 'example'], {
      ...env,
      SERPER_API_KEY: 'test',
      BRAVE_SEARCH_API_KEY: 'test'
    });
    assert.equal(result.status, 0);
    assert.match(result.stdout, /== Serper ==/);
    assert.match(result.stdout, /TITLE: Serper result/);
    assert.match(result.stdout, /== Brave ==/);
    assert.match(result.stdout, /TITLE: Brave result/);
  });
});

test('web-search keeps non-web search types on Serper', () => {
  const mock = `
if [[ "$*" == *google.serper.dev\\/places* ]]; then
  mock_reply '{"places":[{"title":"Place result","address":"Tokyo","category":"Cafe"}]}' 200 "$@"
  exit 0
fi
exit 22
`;
  withMockCurl(mock, (env) => {
    const result = runScript('tools/web-search.sh', ['--type', 'places', 'cafe'], {
      ...env,
      SERPER_API_KEY: 'test',
      BRAVE_SEARCH_API_KEY: 'test'
    });
    assert.equal(result.status, 0);
    assert.match(result.stderr, /search_provider=serper search_type=places/);
    assert.doesNotMatch(result.stderr, /search_provider=brave/);
    assert.match(result.stdout, /TITLE: Place result/);
  });
});

test('web-search passes a supported domain-level site query through unchanged', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* && "$*" == *site:example.com* ]]; then
  mock_reply '{"organic":[{"title":"Site result","link":"https://example.com/item","snippet":"found"}]}' 200 "$@"
  exit 0
fi
exit 22
`;
  withMockCurl(mock, (env) => {
    const result = runScript(
      'tools/web-search.sh',
      ['--provider', 'serper', '--count', '1', 'site:example.com model'],
      { ...env, SERPER_API_KEY: 'test' }
    );
    assert.equal(result.status, 0);
    assert.match(result.stderr, /search_provider=serper/);
    assert.doesNotMatch(result.stderr, /retrying with relaxed query/);
    assert.match(result.stdout, /TITLE: Site result/);
  });
});

test('web-search does not relax an ambiguous query with multiple site operators', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* ]]; then
  mock_reply '{"organic":[]}' 200 "$@"
  exit 0
fi
exit 22
`;
  withMockCurl(mock, (env) => {
    const result = runScript(
      'tools/web-search.sh',
      ['site:maker.example site:shop.example exact product'],
      { ...env, SERPER_API_KEY: 'test' }
    );
    assert.equal(result.status, 1);
    assert.doesNotMatch(result.stderr, /retrying with relaxed query/);
    assert.match(result.stderr, /reformulate the Serper query/);
  });
});

test('web-search normalizes a path in a site restriction after an empty result', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* ]]; then
  if [[ "$*" == *site:example.com\\/products\\/item* ]]; then
    mock_reply '{"organic":[]}' 200 "$@"
  else
    mock_reply '{"organic":[{"title":"Normalized site result","link":"https://example.com/products/item","snippet":"found"}]}' 200 "$@"
  fi
  exit 0
fi
exit 22
`;
  withMockCurl(mock, (env) => {
    const result = runScript(
      'tools/web-search.sh',
      ['--provider', 'serper', '--count', '1', 'site:example.com/products/item model'],
      { ...env, SERPER_API_KEY: 'test' }
    );
    assert.equal(result.status, 0);
    assert.match(result.stderr, /retrying with relaxed query: site:example.com model/);
    assert.match(result.stdout, /TITLE: Normalized site result/);
  });
});

test('web-search distinguishes an empty Serper response from a failed request', () => {
  withMockCurl("mock_reply '{\"organic\":[]}' 200 \"$@\"", (env) => {
    const empty = runScript('tools/web-search.sh', ['--provider', 'serper', 'nothing'], {
      ...env,
      SERPER_API_KEY: 'test'
    });
    assert.equal(empty.status, 1);
    assert.match(empty.stderr, /Serper returned no results/);
    assert.doesNotMatch(empty.stderr, /request failed/);
  });

  withMockCurl('exit 22', (env) => {
    const failed = runScript('tools/web-search.sh', ['--provider', 'serper', 'nothing'], {
      ...env,
      SERPER_API_KEY: 'test'
    });
    assert.equal(failed.status, 1);
    assert.match(failed.stderr, /retrying once with the same query/);
    assert.match(failed.stderr, /Serper remained unavailable after retry/);
  });
});

test('web-search does not hide Serper authentication rejection behind Brave', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* ]]; then
  mock_reply '{"message":"Unauthorized"}' 401 "$@"
  exit 0
fi
mock_reply '{"web":{"results":[{"title":"Unexpected Brave result","url":"https://example.com/","description":"should not run"}]}}' 200 "$@"
`;
  withMockCurl(mock, (env) => {
    const result = runScript('tools/web-search.sh', ['example'], {
      ...env,
      SERPER_API_KEY: 'bad',
      BRAVE_SEARCH_API_KEY: 'test'
    });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /authentication rejected with HTTP status 401/);
    assert.match(result.stderr, /Serper request was rejected/);
    assert.doesNotMatch(result.stderr, /search_provider=brave/);
    assert.doesNotMatch(result.stdout, /Unexpected Brave result/);
  });
});

test('web-search does not hide another Serper client rejection behind Brave', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* ]]; then
  mock_reply '{"message":"Bad request"}' 400 "$@"
  exit 0
fi
mock_reply '{"web":{"results":[{"title":"Unexpected Brave result","url":"https://example.com/","description":"should not run"}]}}' 200 "$@"
`;
  withMockCurl(mock, (env) => {
    const result = runScript('tools/web-search.sh', ['example'], {
      ...env,
      SERPER_API_KEY: 'test',
      BRAVE_SEARCH_API_KEY: 'test'
    });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /request rejected with HTTP status 400/);
    assert.match(result.stderr, /Serper request was rejected/);
    assert.doesNotMatch(result.stderr, /search_provider=brave/);
    assert.doesNotMatch(result.stdout, /Unexpected Brave result/);
  });
});

test('web-search retries transient Serper HTTP failure before Brave fallback', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* ]]; then
  mock_reply '{"message":"Unavailable"}' 503 "$@"
  exit 0
fi
mock_reply '{"web":{"results":[{"title":"Brave after retry","url":"https://example.com/","description":"fallback"}]}}' 200 "$@"
`;
  withMockCurl(mock, (env) => {
    const result = runScript('tools/web-search.sh', ['example'], {
      ...env,
      SERPER_API_KEY: 'test',
      BRAVE_SEARCH_API_KEY: 'test'
    });
    assert.equal(result.status, 0);
    assert.match(result.stderr, /transient HTTP status 503/);
    assert.match(result.stderr, /retrying once with the same query/);
    assert.match(result.stderr, /falling back to Brave/);
    assert.match(result.stdout, /TITLE: Brave after retry/);
  });
});

test('web-search treats Serper HTTP 429 as transient before Brave fallback', () => {
  const mock = `
if [[ "$*" == *google.serper.dev* ]]; then
  mock_reply '{"message":"Rate limited"}' 429 "$@"
  exit 0
fi
mock_reply '{"web":{"results":[{"title":"Brave after rate limit","url":"https://example.com/","description":"fallback"}]}}' 200 "$@"
`;
  withMockCurl(mock, (env) => {
    const result = runScript('tools/web-search.sh', ['example'], {
      ...env,
      SERPER_API_KEY: 'test',
      BRAVE_SEARCH_API_KEY: 'test'
    });
    assert.equal(result.status, 0);
    assert.match(result.stderr, /transient HTTP status 429/);
    assert.match(result.stderr, /retrying once with the same query/);
    assert.match(result.stderr, /falling back to Brave/);
    assert.match(result.stdout, /TITLE: Brave after rate limit/);
  });
});

test('serper-search emits supplemental results when organic results are absent', () => {
  const mock = `
mock_reply '{"organic":[],"answerBox":{"title":"Mount Fuji","answer":"3,776 m","link":"https://example.com/fuji"},"knowledgeGraph":{"title":"Mount Fuji","description":"Mountain in Japan","website":"https://example.com/mount-fuji"},"peopleAlsoAsk":[{"question":"Where is it?","snippet":"Japan","link":"https://example.com/where"}],"topStories":[{"title":"Fuji story","link":"https://example.com/story","source":"Example","date":"Today"}]}' 200 "$@"
`;
  withMockCurl(mock, (env) => {
    const result = runScript('tools/serper-search.sh', ['fuji'], {
      ...env,
      SERPER_API_KEY: 'test'
    });
    assert.equal(result.status, 0);
    assert.match(result.stdout, /TYPE: ANSWER_BOX/);
    assert.match(result.stdout, /ANSWER: 3,776 m/);
    assert.match(result.stdout, /TYPE: KNOWLEDGE_GRAPH/);
    assert.match(result.stdout, /TYPE: RELATED_ANSWER/);
    assert.match(result.stdout, /TYPE: TOP_STORY/);
    assert.doesNotMatch(result.stdout, /NO_SERPER_RESULTS/);
  });
});

test('serper-search ignores empty supplemental result objects', () => {
  const mock = `
mock_reply '{"organic":[],"answerBox":{},"knowledgeGraph":{},"peopleAlsoAsk":[{}],"topStories":[{}]}' 200 "$@"
`;
  withMockCurl(mock, (env) => {
    const result = runScript('tools/serper-search.sh', ['nothing'], {
      ...env,
      SERPER_API_KEY: 'test'
    });
    assert.equal(result.status, 0);
    assert.equal(result.stdout.trim(), 'NO_SERPER_RESULTS');
  });
});

test('paper-search fails when every selected provider fails', () => {
  withMockCurl('exit 22', (env) => {
    const result = runScript('tools/paper-search.sh', ['query'], env);
    assert.equal(result.status, 1);
    assert.match(result.stdout, /OPENALEX_ERROR/);
    assert.match(result.stdout, /ARXIV_ERROR/);
    assert.match(result.stderr, /all selected academic providers failed/);
  });
});
