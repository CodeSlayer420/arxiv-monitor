# arXiv Monitor

Single-file Python pipeline that fetches recent papers from hep-th, gr-qc, and math-ph, scores them for relevance to quantum gravity and holography, and produces a terminal summary plus a dated HTML digest.

## Running

```bash
python3 arxiv_monitor.py
```

First run auto-installs `requests` and `feedparser`, then restarts automatically.

### Options

| Flag | Default | Effect |
|------|---------|--------|
| `--days N` | 3 | How many days back to include (use 5 on Mondays) |
| `--min-score N` | 3 | Minimum relevance score to include a paper |
| `--top N` | 20 | Papers printed in the terminal |
| `--no-open` | off | Skip auto-opening the HTML in a browser |

### Output

- Terminal: ranked list with score bars and matched topic tags
- File: `arxiv_digest_YYYY-MM-DD.html` in the working directory (dark mode, collapsible abstracts, links to arXiv and PDF)

## Adding or tuning keywords

All keywords live in the `KEYWORDS` list near the top of `arxiv_monitor.py`. Each entry is a 4-tuple:

```python
("phrase to match", title_weight, abstract_weight, "Topic Label")
```

- **phrase** — matched case-insensitively as a substring; terms ≤4 characters use word-boundary matching to avoid false positives
- **title_weight** — score added when the phrase appears in the title (use higher values, e.g. 4–6)
- **abstract_weight** — score added when the phrase appears only in the abstract (use lower values, e.g. 1–3)
- **Topic Label** — the tag shown in terminal output and HTML; papers that match any phrase in the same topic group share that label

### Example: adding a new keyword

```python
# Add to the KEYWORDS list
("doubly holographic",  5, 3, "Entanglement & Geometry"),
("Karch-Randall",       4, 3, "Entanglement & Geometry"),
("end-of-the-world brane", 4, 3, "Entanglement & Geometry"),
```

### Tuning the threshold

A paper must reach `--min-score` (default 3) to appear. Typical scores:
- Highly relevant paper (e.g. title contains "Ryu-Takayanagi"): 10+
- Moderately relevant (e.g. abstract mentions "entanglement entropy" and "AdS"): 4–7
- Tangentially related (e.g. abstract mentions "CFT" once): 2 — filtered out by default

Raise `--min-score` to tighten the filter; lower it to catch more borderline papers.

## Categories

Defined in `CATEGORIES` at the top of the file:

```python
CATEGORIES = ["hep-th", "gr-qc", "math-ph"]
```

Add or remove any valid arXiv category identifiers (e.g. `"quant-ph"`, `"math.DG"`).

## Notes

- arXiv occasionally returns 429 (rate limit); the script retries up to 4 times with increasing backoff — just let it run.
- Weekend runs will find fewer papers; arXiv holds Friday–Sunday submissions for Monday announcement.
- HTML files accumulate in the working directory; delete old ones manually.
