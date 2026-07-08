# Example: django/django

[Django](https://github.com/django/django) is a large monorepo-scale target — use for **benchmark** and stress-testing import resolution, not quick iteration.

## Clone and benchmark

```bash
git clone --depth 1 https://github.com/django/django.git /tmp/django
cd backend && source .venv/bin/activate

python -m app.benchmark --repo /tmp/django
```

Expect `ast_parsing` and `import_resolution` to dominate. PageRank warm-up note still applies.

## Full pipeline (slow)

```bash
python -m app.pipeline /tmp/django --json /tmp/django-analysis.json --no-files
```

`--no-files` keeps JSON smaller when you only need graph + scores.

## Via HTTP

Not recommended for first demo — sync analyze may take minutes and large JSON responses are heavy. Prefer local benchmark first.

```bash
# Only if server timeout allows:
curl -s -X POST http://localhost:8000/api/analyze \
  -F "github_url=https://github.com/django/django" | python3 -m json.tool
```

## Analysis root

Django's package lives under `django/` inside the repo. You may need:

```bash
python -m app.pipeline /tmp/django/django
```

or the repo root `/tmp/django` depending on how paths appear in `resolved_deps`. Verify with parser CLI on one known file.

## What to record

| Metric | Your run |
|--------|----------|
| File count | (from pipeline summary) |
| Edge count | |
| Cycle count | |
| Slowest stage | (from benchmark table) |
| Top critical file | (from scores) |

## Related

- [examples/flask.md](flask.md) — smaller framework comparison
- [architecture/README.md](../architecture/README.md#scaling-interview-topic)
