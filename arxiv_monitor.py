#!/usr/bin/env python3
"""
arXiv Daily Monitor — Quantum gravity, holography, AdS/CFT, and related fields.

Usage:
    python arxiv_monitor.py
    python arxiv_monitor.py --days 5 --min-score 4 --top 30 --no-open
"""

import sys
import subprocess

# ── Auto-install dependencies ──────────────────────────────────────────────────
_REQUIRED = ["requests", "feedparser"]

def _bootstrap() -> None:
    missing = [p for p in _REQUIRED if not _can_import(p)]
    if missing:
        import os
        print(f"[setup] Installing: {', '.join(missing)} ...", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing
        )
        print("[setup] Done. Restarting...\n")
        # Replace current process so the new packages are on sys.path
        os.execv(sys.executable, [sys.executable] + sys.argv)

def _can_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False

_bootstrap()

# ── Imports ────────────────────────────────────────────────────────────────────
import re
import json
import time
import html as _html
import argparse
import warnings
import webbrowser
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
from textwrap import shorten
from typing import Optional

warnings.filterwarnings("ignore", category=Warning, module="urllib3")

import requests
import feedparser

# ── Configuration ──────────────────────────────────────────────────────────────
CATEGORIES = ["hep-th", "gr-qc", "math-ph"]
MAX_RESULTS_PER_CATEGORY = 400

DEFAULT_DAYS_LOOKBACK = 3   # look back this many days (handles weekends)
DEFAULT_MIN_SCORE     = 3   # minimum relevance score to include
DEFAULT_TOP_N         = 20  # max papers printed in terminal
DEFAULT_AUTO_OPEN     = True

OUTPUT_DIR = Path(".")

PROFESSORS_FILE = OUTPUT_DIR / "professors_list.json"
PROFESSORS_MD   = OUTPUT_DIR / "professors_list.md"

# ── Keywords ───────────────────────────────────────────────────────────────────
# (phrase, title_weight, abstract_weight, topic_label)
KEYWORDS = [
    # AdS/CFT & Holography
    ("AdS/CFT",                         6, 4, "AdS/CFT"),
    ("AdS-CFT",                         6, 4, "AdS/CFT"),
    ("holographic duality",             5, 3, "AdS/CFT"),
    ("gauge/gravity duality",           5, 3, "AdS/CFT"),
    ("gauge gravity duality",           5, 3, "AdS/CFT"),
    ("anti-de Sitter",                  4, 2, "AdS/CFT"),
    ("bulk reconstruction",             4, 3, "AdS/CFT"),
    ("holographic renormalization",     3, 2, "AdS/CFT"),
    ("Maldacena conjecture",            4, 3, "AdS/CFT"),
    ("holography",                      3, 2, "AdS/CFT"),
    ("holographic",                     2, 1, "AdS/CFT"),
    ("AdS",                             2, 1, "AdS/CFT"),
    ("BFSS",                            3, 2, "AdS/CFT"),
    ("ABJM",                            3, 2, "AdS/CFT"),

    # Quantum Gravity
    ("quantum gravity",                 5, 3, "Quantum Gravity"),
    ("loop quantum gravity",            5, 4, "Quantum Gravity"),
    ("spin foam",                       4, 3, "Quantum Gravity"),
    ("causal dynamical triangulation",  4, 3, "Quantum Gravity"),
    ("CDT",                             3, 2, "Quantum Gravity"),
    ("JT gravity",                      4, 3, "Quantum Gravity"),
    ("Jackiw-Teitelboim",               4, 3, "Quantum Gravity"),
    ("quantum spacetime",               4, 3, "Quantum Gravity"),
    ("black hole information",          4, 3, "Quantum Gravity"),
    ("information paradox",             4, 3, "Quantum Gravity"),
    ("Page curve",                      4, 3, "Quantum Gravity"),
    ("island formula",                  5, 4, "Quantum Gravity"),
    ("replica wormhole",                5, 4, "Quantum Gravity"),
    ("Hawking radiation",               3, 2, "Quantum Gravity"),
    ("black hole evaporation",          3, 2, "Quantum Gravity"),

    # String Theory
    ("string theory",                   4, 3, "String Theory"),
    ("string duality",                  4, 3, "String Theory"),
    ("M-theory",                        3, 2, "String Theory"),
    ("D-brane",                         3, 2, "String Theory"),
    ("superstring",                     3, 2, "String Theory"),
    ("supergravity",                    2, 1, "String Theory"),
    ("worldsheet",                      3, 2, "String Theory"),
    ("compactification",                2, 1, "String Theory"),

    # Entanglement & Geometry
    ("Ryu-Takayanagi",                  6, 4, "Entanglement & Geometry"),
    ("RT formula",                      5, 4, "Entanglement & Geometry"),
    ("holographic entanglement entropy",5, 4, "Entanglement & Geometry"),
    ("entanglement entropy",            4, 3, "Entanglement & Geometry"),
    ("holographic complexity",          4, 3, "Entanglement & Geometry"),
    ("ER=EPR",                          5, 4, "Entanglement & Geometry"),
    ("entanglement wedge",              4, 3, "Entanglement & Geometry"),
    ("modular Hamiltonian",             3, 2, "Entanglement & Geometry"),
    ("relative entropy",                2, 1, "Entanglement & Geometry"),
    ("tensor network",                  3, 2, "Entanglement & Geometry"),
    ("wormhole",                        3, 2, "Entanglement & Geometry"),
    ("quantum error correction",        3, 2, "Entanglement & Geometry"),

    # CFT
    ("conformal field theory",          4, 3, "CFT"),
    ("CFT",                             3, 2, "CFT"),
    ("conformal bootstrap",             4, 3, "CFT"),
    ("operator product expansion",      3, 2, "CFT"),
    ("OPE",                             2, 1, "CFT"),
    ("Virasoro algebra",                3, 2, "CFT"),
    ("Virasoro",                        2, 1, "CFT"),
    ("conformal block",                 3, 2, "CFT"),
    ("Weyl anomaly",                    3, 2, "CFT"),
    ("c-theorem",                       3, 2, "CFT"),
    ("central charge",                  2, 1, "CFT"),

    # Asymptotic Symmetries
    ("asymptotic symmetries",           5, 4, "Asymptotic Symmetries"),
    ("BMS symmetry",                    5, 4, "Asymptotic Symmetries"),
    ("BMS group",                       5, 4, "Asymptotic Symmetries"),
    ("Bondi-Metzner-Sachs",             5, 4, "Asymptotic Symmetries"),
    ("soft theorem",                    4, 3, "Asymptotic Symmetries"),
    ("gravitational memory",            4, 3, "Asymptotic Symmetries"),
    ("memory effect",                   3, 2, "Asymptotic Symmetries"),
    ("asymptotic charges",              4, 3, "Asymptotic Symmetries"),
    ("supertranslation",                4, 3, "Asymptotic Symmetries"),
    ("superrotation",                   4, 3, "Asymptotic Symmetries"),

    # Celestial Holography
    ("celestial holography",            6, 5, "Celestial Holography"),
    ("celestial amplitudes",            5, 4, "Celestial Holography"),
    ("celestial CFT",                   5, 4, "Celestial Holography"),
    ("CCFT",                            4, 3, "Celestial Holography"),
    ("flat space holography",           5, 4, "Celestial Holography"),
    ("flat holography",                 5, 4, "Celestial Holography"),
    ("carrollian",                      4, 3, "Celestial Holography"),
    ("Carrollian symmetry",             4, 3, "Celestial Holography"),
    ("scri",                            3, 2, "Celestial Holography"),
    ("null infinity",                   3, 2, "Celestial Holography"),

    # Geometric Gravity
    ("geometric approach",              3, 2, "Geometric Gravity"),
    ("causal structure",                3, 2, "Geometric Gravity"),
    ("Penrose diagram",                 3, 2, "Geometric Gravity"),
    ("black hole entropy",              4, 3, "Geometric Gravity"),
    ("black hole thermodynamics",       3, 2, "Geometric Gravity"),
    ("Bekenstein-Hawking",              4, 3, "Geometric Gravity"),
    ("near-horizon symmetry",           4, 3, "Geometric Gravity"),
    ("near horizon",                    3, 2, "Geometric Gravity"),
    ("horizon entropy",                 3, 2, "Geometric Gravity"),
    ("gravitational entropy",           3, 2, "Geometric Gravity"),
]

# ── ANSI colors ────────────────────────────────────────────────────────────────
_TTY = sys.stdout.isatty()

BOLD = "\033[1m"
DIM  = "\033[2m"
CYAN = "\033[36m"
YEL  = "\033[33m"
GRN  = "\033[32m"
MAG  = "\033[35m"
RST  = "\033[0m"

def c(text: str, *codes: str) -> str:
    return ("".join(codes) + text + RST) if _TTY else text

# ── arXiv fetcher ──────────────────────────────────────────────────────────────
_ARXIV_API = "http://export.arxiv.org/api/query"

def fetch_category(category: str, max_results: int) -> list:
    params = {
        "search_query": f"cat:{category}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    print(f"  {c('Fetching', BOLD)} {c(category, CYAN)} ...", end="", flush=True)
    for attempt in range(4):
        try:
            resp = requests.get(_ARXIV_API, params=params, timeout=60)
            if resp.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f" rate-limited, waiting {wait}s...", end="", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            papers = []
            for entry in feed.entries:
                raw_id = entry.get("id", "")
                arxiv_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id
                raw_authors = entry.get("authors", [])
                papers.append({
                    "arxiv_id": arxiv_id,
                    "url":      f"https://arxiv.org/abs/{arxiv_id}",
                    "title":    " ".join(entry.get("title",   "").split()),
                    "abstract": " ".join(entry.get("summary", "").split()),
                    "authors":  [a.get("name", "") for a in raw_authors],
                    "author_info": [
                        {
                            "name":        a.get("name", "").strip(),
                            "affiliation": a.get("arxiv_affiliation", "").strip(),
                        }
                        for a in raw_authors
                    ],
                    "published": entry.get("published", ""),
                    "categories": [t.get("term", "") for t in entry.get("tags", [])],
                    "primary_cat": entry.get("arxiv_primary_category", {}).get("term", category),
                })
            print(f" {c(str(len(papers)), GRN)} papers")
            return papers
        except Exception as exc:
            print(f" {c('ERROR', YEL)}: {exc}")
            return []
    print(f" {c('FAILED after retries', YEL)}")
    return []

# ── Scoring ────────────────────────────────────────────────────────────────────
def score_paper(paper: dict) -> tuple:
    title_l    = paper["title"].lower()
    abstract_l = paper["abstract"].lower()
    score  = 0
    topics: set = set()

    for phrase, tw, aw, topic in KEYWORDS:
        p = phrase.lower()
        # Use word-boundary regex for short tokens to avoid false positives
        if len(p) <= 4:
            pat   = r'\b' + re.escape(p) + r'\b'
            in_t  = bool(re.search(pat, title_l))
            in_a  = bool(re.search(pat, abstract_l))
        else:
            in_t  = p in title_l
            in_a  = p in abstract_l

        if in_t:
            score += tw
            topics.add(topic)
        elif in_a:
            score += aw
            topics.add(topic)

    return score, sorted(topics)

def _parse_dt(s: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None

def process_papers(raw: list, days: int, min_score: int) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    seen: set = set()
    results = []

    for p in raw:
        base_id = p["arxiv_id"].split("v")[0]
        if base_id in seen:
            continue
        seen.add(base_id)

        pub_dt = _parse_dt(p["published"])
        if pub_dt and pub_dt < cutoff:
            continue

        score, topics = score_paper(p)
        if score >= min_score:
            results.append({**p, "score": score, "topics": topics})

    return sorted(results, key=lambda x: x["score"], reverse=True)

# ── Professors / researcher tracker ───────────────────────────────────────────
def _load_professors() -> dict:
    if PROFESSORS_FILE.exists():
        try:
            return {r["name"]: r for r in json.loads(PROFESSORS_FILE.read_text())}
        except Exception:
            pass
    return {}

def update_professors_list(papers: list) -> tuple:
    """Upsert authors from filtered papers into professors_list.json/.md.

    Returns (total_researchers, new_this_run).
    """
    today = datetime.now().strftime("%Y-%m-%d")
    db    = _load_professors()
    new_count = 0

    for paper in papers:
        paper_topics = paper.get("topics", [])
        for ai in paper.get("author_info", []):
            name = ai["name"]
            if not name:
                continue
            affiliation = ai.get("affiliation", "")

            if name in db:
                rec = db[name]
                rec["count"]    += 1
                rec["last_seen"] = today
                merged = set(rec["topics"]) | set(paper_topics)
                rec["topics"] = sorted(merged)
                # Fill in institution only if we now have one and didn't before
                if affiliation and not rec.get("institution"):
                    rec["institution"] = affiliation
            else:
                db[name] = {
                    "name":        name,
                    "institution": affiliation,
                    "topics":      sorted(paper_topics),
                    "count":       1,
                    "last_seen":   today,
                }
                new_count += 1

    sorted_list = sorted(db.values(), key=lambda r: (-r["count"], r["name"]))
    PROFESSORS_FILE.write_text(
        json.dumps(sorted_list, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    _write_professors_md(sorted_list, today)
    return len(sorted_list), new_count

def _write_professors_md(records: list, today: str) -> None:
    lines = [
        "# Researcher Tracker",
        "",
        f"_Updated {today} &middot; {len(records)} researchers tracked_",
        "",
        "| # | Name | Institution | Topics | Appearances | Last Seen |",
        "|---|------|-------------|--------|:-----------:|-----------|",
    ]
    for i, r in enumerate(records, 1):
        topics = r["topics"]
        topic_str = ", ".join(topics[:4])
        if len(topics) > 4:
            topic_str += f" +{len(topics) - 4}"
        inst = r.get("institution") or "—"
        lines.append(
            f"| {i} | {r['name']} | {inst} | {topic_str} | {r['count']} | {r['last_seen']} |"
        )
    PROFESSORS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

# ── Terminal output ────────────────────────────────────────────────────────────
def print_digest(papers: list, top_n: int, html_path: Path) -> None:
    now      = datetime.now()
    date_str = now.strftime(f"%A, %B {now.day}, %Y")
    sep      = "─" * 62

    print()
    print(c(f"  {sep}", DIM))
    print(c(f"  arXiv Daily Digest  ·  {date_str}", BOLD + CYAN))
    print(c(f"  {len(papers)} relevant papers found", DIM))
    print(c(f"  {sep}", DIM))
    print()

    for i, p in enumerate(papers[:top_n], 1):
        bar      = c("█" * min(p["score"] // 3, 18), GRN)
        topics   = c("  ".join(p["topics"][:4]), MAG)
        authors  = p["authors"]
        au_str   = (authors[0] + (" et al." if len(authors) > 1 else "")) if authors else "Unknown"

        print(c(f"  {i:3d}. ", DIM) + c(p["title"], BOLD))
        print(f"       {c(au_str, DIM)}")
        score_str = f"Score {p['score']:3d}"
        print(f"       {c(score_str, YEL)}  {bar}  {topics}")
        print(c(f"       {shorten(p['abstract'], 190, placeholder='...')}", DIM))
        print(f"       {c(p['url'], CYAN)}")
        print()

    if len(papers) > top_n:
        print(c(f"  ... and {len(papers) - top_n} more papers in the full HTML digest.", DIM))

    print(c(f"\n  HTML digest → {html_path.absolute()}\n", GRN + BOLD))

# ── HTML generation ────────────────────────────────────────────────────────────
_CSS = """
:root{
  --bg:#0d1117;--surface:#161b22;--card:#1c2128;--border:#30363d;
  --text:#e6edf3;--muted:#8b949e;--accent:#7c3aed;--link:#58a6ff;
  --green:#3fb950;--yellow:#d29922;--pink:#f778ba;--tag:#1c2432;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter','Segoe UI',system-ui,sans-serif;
     background:var(--bg);color:var(--text);line-height:1.6;font-size:15px}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline}

.header{background:var(--surface);border-bottom:1px solid var(--border);padding:2rem 2.5rem}
.header h1{font-size:1.65rem;font-weight:700;letter-spacing:-.02em;color:#fff;margin-bottom:.2rem}
.tagline{color:var(--muted);font-size:.85rem;margin-bottom:1rem}
.stats{display:flex;flex-wrap:wrap;gap:.45rem}
.stat{background:var(--card);border:1px solid var(--border);border-radius:6px;
      padding:.28rem .7rem;font-size:.78rem;color:var(--muted)}
.stat b{color:var(--text)}

.container{max-width:960px;margin:0 auto;padding:1.5rem 2rem}
.section-label{font-size:.7rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
               color:var(--muted);margin:1.5rem 0 .75rem;padding-bottom:.4rem;
               border-bottom:1px solid var(--border)}

.card{background:var(--card);border:1px solid var(--border);border-radius:10px;
      padding:1.2rem 1.4rem;margin-bottom:.8rem;transition:border-color .15s}
.card:hover{border-color:var(--accent)}
.rank{float:right;font-size:1.4rem;font-weight:700;color:var(--border);margin-left:.75rem;line-height:1}

.title{font-size:1.05rem;font-weight:600;margin-bottom:.4rem}
.title a{color:var(--text)}
.title a:hover{color:var(--link)}

.meta{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center;margin-bottom:.55rem;font-size:.82rem}
.authors{color:var(--muted)}
.aid{font-family:monospace;font-size:.76rem}
.score{color:var(--yellow);font-weight:600}
.bar-outer{display:inline-block;vertical-align:middle;background:var(--border);
           border-radius:3px;height:5px;width:90px;margin-left:.35rem}
.bar-inner{background:linear-gradient(90deg,var(--accent),var(--pink));
           height:100%;border-radius:3px}
.pdf{color:var(--green);font-size:.76rem;font-weight:500}

.tags{display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:.55rem}
.tag{background:var(--tag);color:var(--link);border:1px solid var(--border);
     border-radius:20px;padding:.12rem .5rem;font-size:.73rem}
.cat{color:var(--muted)}

.abstract{color:var(--muted);font-size:.84rem;line-height:1.75}
.abstract.clamp{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.toggle{background:none;border:none;color:var(--link);cursor:pointer;font-size:.76rem;margin-top:.25rem;padding:0}
.toggle:hover{text-decoration:underline}

footer{text-align:center;padding:1.5rem;color:var(--muted);font-size:.76rem;
       border-top:1px solid var(--border);margin-top:1rem}
"""

_JS = """
function tog(btn,id){
  var el=document.getElementById(id),cl=el.classList;
  if(cl.contains('clamp')){cl.remove('clamp');btn.textContent='Show less ▲';}
  else{cl.add('clamp');btn.textContent='Show more ▼';}
}
"""

def _scorebar(score: int, max_s: int = 60) -> str:
    pct = min(score / max_s * 100, 100)
    return (f'<div class="bar-outer">'
            f'<div class="bar-inner" style="width:{pct:.0f}%"></div></div>')

def generate_html(papers: list, categories: list) -> str:
    now      = datetime.now()
    date_str = now.strftime(f"%A, %B {now.day}, %Y at %H:%M")

    topic_counts: dict = defaultdict(int)
    for p in papers:
        for t in p["topics"]:
            topic_counts[t] += 1

    stat_rows = [
        f'<div class="stat">Generated: <b>{_html.escape(date_str)}</b></div>',
        f'<div class="stat">Papers: <b>{len(papers)}</b></div>',
        f'<div class="stat">Categories: <b>{", ".join(categories)}</b></div>',
    ]
    for topic, cnt in sorted(topic_counts.items(), key=lambda x: -x[1])[:6]:
        stat_rows.append(
            f'<div class="stat">{_html.escape(topic)}: <b>{cnt}</b></div>'
        )

    cards = []
    for i, p in enumerate(papers, 1):
        aid    = _html.escape(p["arxiv_id"])
        url    = _html.escape(p["url"])
        title  = _html.escape(p["title"])
        au_raw = p["authors"]
        au     = _html.escape(
            (", ".join(au_raw[:3]) + (" et al." if len(au_raw) > 3 else ""))
            if au_raw else "Unknown"
        )
        topic_tags = "".join(
            f'<span class="tag">{_html.escape(t)}</span>' for t in p["topics"]
        )
        cat_tags = "".join(
            f'<span class="tag cat">{_html.escape(cat)}</span>'
            for cat in p["categories"][:3]
        )
        abs_id  = f"a{i}"
        bar_html = _scorebar(p["score"])

        cards.append(f"""
<div class="card">
  <div class="rank">#{i}</div>
  <div class="title"><a href="{url}" target="_blank">{title}</a></div>
  <div class="meta">
    <span class="authors">{au}</span>
    <a class="aid" href="{url}" target="_blank">{aid}</a>
    <a class="pdf" href="https://arxiv.org/pdf/{_html.escape(p['arxiv_id'])}" target="_blank">[PDF]</a>
    <span class="score">Score&nbsp;{p['score']}</span>{bar_html}
  </div>
  <div class="tags">{topic_tags}{cat_tags}</div>
  <div class="abstract clamp" id="{abs_id}">{_html.escape(p['abstract'])}</div>
  <button class="toggle" onclick="tog(this,'{abs_id}')">Show more &#9660;</button>
</div>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>arXiv Digest — {_html.escape(now.strftime('%Y-%m-%d'))}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="header">
  <h1>arXiv Daily Digest</h1>
  <div class="tagline">
    Quantum Gravity &middot; Holography &middot; AdS/CFT &middot; String Theory
    &middot; Celestial Holography &middot; Asymptotic Symmetries &middot; CFT
    &middot; Ryu-Takayanagi &middot; Entanglement &amp; Geometry
  </div>
  <div class="stats">{''.join(stat_rows)}</div>
</div>
<div class="container">
  <div class="section-label">Papers ranked by relevance &mdash; click title to open on arXiv</div>
  {''.join(cards)}
</div>
<footer>arXiv Monitor &middot; {_html.escape(date_str)}</footer>
<script>{_JS}</script>
</body>
</html>"""

# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(
        description="arXiv daily digest for quantum gravity & holography"
    )
    ap.add_argument("--days",      type=int,            default=DEFAULT_DAYS_LOOKBACK,
                    help=f"lookback window in days (default {DEFAULT_DAYS_LOOKBACK})")
    ap.add_argument("--min-score", type=int,            default=DEFAULT_MIN_SCORE,
                    help=f"minimum relevance score (default {DEFAULT_MIN_SCORE})")
    ap.add_argument("--top",       type=int,            default=DEFAULT_TOP_N,
                    help=f"papers shown in terminal (default {DEFAULT_TOP_N})")
    ap.add_argument("--no-open",   action="store_true", default=False,
                    help="don't auto-open the HTML file in your browser")
    args = ap.parse_args()

    print(c("\narXiv Monitor — fetching daily digest...\n", BOLD + CYAN))

    all_papers: list = []
    for i, cat in enumerate(CATEGORIES):
        papers = fetch_category(cat, MAX_RESULTS_PER_CATEGORY)
        all_papers.extend(papers)
        if i < len(CATEGORIES) - 1:
            time.sleep(3)  # polite rate-limiting

    print(f"\n  Processing {len(all_papers)} total entries "
          f"(deduplicating, date-filtering, scoring)...")
    ranked = process_papers(all_papers, days=args.days, min_score=args.min_score)
    print(f"  {c(str(len(ranked)), GRN)} papers above score threshold "
          f"({args.min_score})\n")

    html_path = OUTPUT_DIR / f"arxiv_digest_{datetime.now().strftime('%Y-%m-%d')}.html"
    html_path.write_text(generate_html(ranked, CATEGORIES), encoding="utf-8")

    total_researchers, new_researchers = update_professors_list(ranked)
    new_label = f"{c(f'+{new_researchers} new', GRN)}  " if new_researchers else ""
    print(f"  Researchers: {c(str(total_researchers), BOLD)} tracked  "
          f"{new_label}→ {c(str(PROFESSORS_MD), CYAN)}\n")

    print_digest(ranked, args.top, html_path)

    if not args.no_open:
        webbrowser.open(html_path.absolute().as_uri())


if __name__ == "__main__":
    main()
