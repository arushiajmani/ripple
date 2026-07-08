# Example: pallets/click

[Click](https://github.com/pallets/click) is a well-structured CLI library — good medium-size real-world target for parser and graph analysis.

## Clone and analyze locally

```bash
git clone --depth 1 https://github.com/pallets/click.git /tmp/click
cd backend && source .venv/bin/activate

python -m app.parser.cli /tmp/click/src/click
python -m app.pipeline /tmp/click/src/click
python -m app.benchmark --repo /tmp/click/src/click
python -m app.pipeline /tmp/click/src/click --json /tmp/click-analysis.json
```

**Analysis root:** pass the directory that owns package paths (often `src/click` or the repo root containing `src/click/...`). If imports misclassify as `external_deps`, move the root up one level. See [parser — analysis root](../backend/parser.md#analysis-root-convention).

## Via HTTP (GitHub)

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -F "github_url=https://github.com/pallets/click" | python3 -m json.tool
```

Requires git on the server. Shallow clone lands under `/tmp/ripple/{job_id}/`.

## What to look for

| Output | Question to ask |
|--------|-----------------|
| Parser | Which modules are most connected via `resolved_deps`? |
| Graph | Any circular dependencies? (`cycle_count` in summary) |
| Scores | Which modules rank highest on criticality? (`core.py`, `types.py`, …) |
| Impact | Pick a high-centrality file — how large is the blast radius? |
| Benchmark | Does `ast_parsing` dominate? (expected on first run) |

Record your findings here when you run the commands — this doc intentionally does not hard-code scores (they change with Click versions).

## Portfolio angle

Compare Click's hub modules (high in-degree) vs leaf command modules. Relate to how you'd prioritize reading an unfamiliar CLI codebase.

## Related

- [examples/django.md](django.md) — larger repo benchmark
- [reference/performance-metrics.md](../reference/performance-metrics.md)
