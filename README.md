# videogen-eval-portfolio

An **image-to-video (img2video)** model evaluation harness, built for producing
and comparing **advertising / promotional video** at scale. Give it a source
image + prompt; it generates a clip per model, scores each with a **vision judge**
against a fixed 9-dimension rubric, and lets you browse results in an interactive
dashboard.

The design goal is **extensibility**: adding a new model as it ships is *one
adapter file + one decorator* — the runner, judge, and dashboard never change.

> **Runs with zero keys and zero cost.** v1 ships a `mock` provider that serves
> bundled/synthetic clips, so the whole pipeline — generate → judge → dashboard —
> works offline out of the box. Real judging uses Claude Opus 4.8 and needs an
> API key.

## Architecture

```
                prompts/suite.yaml + assets/samples/images
                              │
                              ▼
   ┌────────────┐   provider × prompt matrix    ┌──────────────┐
   │  Providers │ ───────────────────────────▶  │   Runner     │  async, resumable, cached
   │ (registry) │   mock | runway | veo | …      │ runs/<id>/   │  → videos + sampled frames
   └────────────┘                                └──────┬───────┘
                                                        │
                              source image + frames     ▼
                                              ┌───────────────────┐
                                              │  Judge (Opus 4.8) │  tool-use → typed JudgeScore
                                              │  9-dim rubric     │  (stub judge = keyless)
                                              └─────────┬─────────┘
                                                        │ results.jsonl
                                                        ▼
                                              ┌───────────────────┐
                                              │ Streamlit dashboard│  leaderboard · gallery ·
                                              │                   │  compare · per-dim charts
                                              └───────────────────┘
```

## Rubric (fixed 9 dimensions)

`prompt_adherence`, `object_deformation`, `object_cutoff`, `flickering`,
`fast_camera_movement`, `video_quality`, `defied_physics`,
`temporal_object_creation`, `aesthetics` — defined in
[`src/vgeval/judge/rubric.yaml`](src/vgeval/judge/rubric.yaml). The judge sees the
**original source image** alongside sampled output frames, so it can score defects
(deformation, cutoff, physics) against the input.

## Quickstart (no API key)

```bash
# 1. Install uv (https://astral.sh/uv). If behind a TLS-inspecting proxy:
export UV_SYSTEM_CERTS=1

# 2. Create env + install
uv venv --python 3.11
uv pip install -e ".[dev]"

# 3. Generate (mock provider) then judge with the keyless stub
uv run vgeval run --provider mock
uv run vgeval judge --stub

# 4. Browse results
uv run vgeval dashboard
```

## Real judging (Claude Opus 4.8)

```bash
cp .env.example .env    # set ANTHROPIC_API_KEY
uv run vgeval judge     # scores the latest run with Opus 4.8
```

## Add your own content

- **Prompt suite** → drop a YAML in `prompts/` (see `prompts/example_suite.yaml`).
- **Source images** → `assets/samples/images/`.
- **Sample output videos** (served by the mock provider) → `assets/samples/videos/`.
- **Rubric definitions/scale** → edit `src/vgeval/judge/rubric.yaml` (the 9 dim
  *names* are fixed; the definitions and scale are yours).

## Add a new model

See [docs/adding-a-provider.md](docs/adding-a-provider.md). In short: subclass
`ImageToVideoProvider`, add `@register("<name>")`, implement `generate()`. It
appears on the CLI and in the dashboard automatically.

## Development

```bash
uv run ruff check .
uv run pytest
uv run vgeval canary    # full mock pipeline end-to-end (what CI/cron run)
```

## License & attribution

BSD 3-Clause (see `LICENSE`). If you use or build on this work, please retain the
copyright notice and credit the author — see [`NOTICE`](NOTICE).

Author: Dimos Papadopoulos
Role: Product leader / builder
Version: 2.0 (Slack integration)
