#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "conferences.json"
OUTPUT_PATH = ROOT / "index.html"


def main():
    conferences = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    data_json = json.dumps(conferences, ensure_ascii=False, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Conference Rankings (ICORE 2026)</title>
<style>
  :root {{
    --bg: #f7f8fa;
    --card: #ffffff;
    --border: #e3e6ea;
    --text: #1f2430;
    --muted: #6b7280;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    margin: 0;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }}
  header {{
    padding: 2rem 1.5rem 1rem;
    max-width: 1100px;
    margin: 0 auto;
  }}
  h1 {{ margin: 0 0 .25rem; font-size: 1.6rem; }}
  header p {{ margin: 0; color: var(--muted); }}
  .controls {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 1.5rem 1rem;
    display: flex;
    flex-wrap: wrap;
    gap: .75rem;
    align-items: center;
  }}
  input[type="search"], select {{
    padding: .5rem .7rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: .95rem;
    background: var(--card);
  }}
  input[type="search"] {{ flex: 1; min-width: 200px; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 0 1.5rem 3rem; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--card);
          border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }}
  th, td {{ text-align: left; padding: .7rem .9rem; border-bottom: 1px solid var(--border); font-size: .92rem; }}
  th {{ background: #eef1f5; font-weight: 600; cursor: pointer; user-select: none; white-space: nowrap; }}
  tbody tr:hover {{ background: #f3f6fb; }}
  td:last-child {{ color: var(--muted); }}
  .rank {{ font-weight: 700; text-align: center; white-space: nowrap; }}
  .rank-Astar {{ color: #b8860b; }}
  .rank-A {{ color: #1a7f37; }}
  .rank-B {{ color: #1f6feb; }}
  .rank-C {{ color: #8957e5; }}
  .rank-other {{ color: var(--muted); }}
  .badge {{
    display: inline-block; padding: .12rem .5rem; border-radius: 999px;
    font-size: .8rem; font-weight: 700; background: #eef1f5;
  }}
  .acr {{ font-weight: 600; }}
  footer {{ max-width: 1100px; margin: 0 auto; padding: 0 1.5rem 2rem; color: var(--muted); font-size: .85rem; }}
</style>
</head>
<body>
<header>
  <h1>Conference Rankings</h1>
  <p>Source: ICORE 2026 &middot; <span id="count"></span> conferences</p>
</header>
<div class="controls">
  <input type="search" id="search" placeholder="Search title or acronym...">
  <select id="rankFilter">
    <option value="">All ranks</option>
    <option value="A*">A*</option>
    <option value="A">A</option>
    <option value="B">B</option>
    <option value="C">C</option>
    <option value="other">Other</option>
  </select>
</div>
<main>
  <table id="tbl">
    <thead>
      <tr>
        <th data-key="rank">Rank</th>
        <th data-key="acronym">Acronym</th>
        <th data-key="title">Title</th>
        <th data-key="rating">Avg Rating</th>
        <th data-key="deadline">Abstract Deadline</th>
        <th data-key="fullDeadline">Full Paper Deadline</th>
        <th data-key="url">URL</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</main>
<footer>Generated from data/conferences.json</footer>

<script>
const DATA = {data_json};

const RANK_ORDER = {{"A*":0, "A":1, "B":2, "C":3}};
function rankClass(r) {{
  if (r === "A*") return "rank-Astar";
  if (r === "A") return "rank-A";
  if (r === "B") return "rank-B";
  if (r === "C") return "rank-C";
  return "rank-other";
}}
function rankBucket(r) {{ return ["A*","A","B","C"].includes(r) ? r : "other"; }}

const tbody = document.querySelector("#tbl tbody");
const searchEl = document.getElementById("search");
const filterEl = document.getElementById("rankFilter");
const countEl = document.getElementById("count");

let sortKey = "rank", sortAsc = true;

function render() {{
  const q = searchEl.value.trim().toLowerCase();
  const rf = filterEl.value;
  let rows = DATA.filter(d => {{
    const matchesQ = !q || d.title.toLowerCase().includes(q) || d.acronym.toLowerCase().includes(q);
    const matchesR = !rf || rankBucket(d.rank) === rf;
    return matchesQ && matchesR;
  }});
  rows.sort((a, b) => {{
    let av, bv;
    if (sortKey === "rank") {{
      av = RANK_ORDER[a.rank] ?? 99; bv = RANK_ORDER[b.rank] ?? 99;
    }} else if (sortKey === "rating") {{
      av = a.rating === "N/A" ? -1 : parseFloat(a.rating);
      bv = b.rating === "N/A" ? -1 : parseFloat(b.rating);
    }} else if (sortKey === "deadline" || sortKey === "fullDeadline") {{
      av = a[sortKey] === "N/A" ? "9999" : a[sortKey];
      bv = b[sortKey] === "N/A" ? "9999" : b[sortKey];
    }} else {{
      av = (a[sortKey] || "").toLowerCase(); bv = (b[sortKey] || "").toLowerCase();
    }}
    if (av < bv) return sortAsc ? -1 : 1;
    if (av > bv) return sortAsc ? 1 : -1;
    return a.acronym.localeCompare(b.acronym);
  }});
  tbody.innerHTML = rows.map(d => `
    <tr>
      <td class="rank ${{rankClass(d.rank)}}"><span class="badge ${{rankClass(d.rank)}}">${{d.rank}}</span></td>
      <td class="acr">${{d.acronym}}</td>
      <td>${{d.title}}</td>
      <td>${{d.rating}}</td>
      <td>${{d.deadline}}</td>
      <td>${{d.fullDeadline}}</td>
      <td>${{d.url ? `<a href="${{d.url}}" target="_blank" rel="noopener">link</a>` : ""}}</td>
    </tr>`).join("");
  countEl.textContent = rows.length;
}}

document.querySelectorAll("th").forEach(th => {{
  th.addEventListener("click", () => {{
    const key = th.dataset.key;
    if (sortKey === key) sortAsc = !sortAsc; else {{ sortKey = key; sortAsc = true; }}
    render();
  }});
}});
searchEl.addEventListener("input", render);
filterEl.addEventListener("change", render);
render();
</script>
</body>
</html>
"""
    OUTPUT_PATH.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
