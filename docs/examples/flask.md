# Example: pallets/flask

[Flask](https://github.com/pallets/flask) is a medium-size framework repo — between `mini_repo` and `click` in complexity.

## Clone and analyze

```bash
git clone --depth 1 https://github.com/pallets/flask.git /tmp/flask
cd backend && source .venv/bin/activate

python -m app.parser.cli /tmp/flask/src/flask
python -m app.pipeline /tmp/flask/src/flask
python -m app.benchmark --repo /tmp/flask/src/flask
```

## Via HTTP

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -F "github_url=https://github.com/pallets/flask" | python3 -m json.tool
```

## Suggested exploration

1. **Parser** — inspect `app.py` or `blueprints.py` import patterns
2. **Cycles** — does Flask's internal graph have import loops?
3. **Impact** — query impact for a core module after analyze; compare direct vs indirect dependents
4. **Compare** — run same commands on [click](click.md); contrast graph density and top critical files

## Analysis root

Flask 3.x sources typically live under `src/flask/`. Pass that directory (or parent) so `from flask.xxx` resolves to in-repo paths.

## Portfolio angle

Show side-by-side benchmark timings: `mini_repo` vs `flask` vs `click`. Discuss which stage scales with file count.

## Related

- [examples/click.md](click.md)
- [backend/pipeline.md](../backend/pipeline.md#benchmark-cli)
