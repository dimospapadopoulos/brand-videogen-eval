# videogen-eval-portfolio

**The Problem**

Enterprise-wide generative evaluation is an unsolved gap. On one hand, there's brand teams requiring adherence to the bible (logos, fonts, typography, style, esthetic etc.), on the other creative and marketing agencies who are interested in both the experience but also the sheer volume of assets to meet campaign demands.
And in the middle of it all? Performance. Creative that not only invokes emotion but also converts or generates awareness; the buzz that all brands chase.

From research, I couldn't find any major good open standard tailored to enterprise marketing, so I wanted to design some rubric based on what I learned shipping creative for my original IP (The Cosmic Ones) at-scale (email+medium+pinterest+youtube+meta+book content) and at my current role.

With inspiration from VBench and VBench++, I have redefined some of the rubrics to what a brand would absolutely care more about and enriched it with a few core rubrics.
<img width="2000" height="590" alt="image" src="https://github.com/user-attachments/assets/9cb38b72-312d-452c-a3b1-51c0dfe87868" />


This project aims to automate evaluations using AI to score and judge different models' performance at the core of what a marketer or brand creative would most care about.

This working reference implementation proves out that an LLM-as-a-judge with computer vision capabilities can judge creative and score it, thus helping in the creative generation process.

**The What**

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

**Connect:**
- GitHub: [@dimospapadopoulos](https://github.com/dimospapadopoulos)
- LinkedIn: [Dimos Papadopoulos](https://linkedin.com/in/dimosp)
- Portfolio: [Other Projects](https://www.notion.so/Dimos-Papadopoulos-Product-Portfolio-ad6dd941f79c4d28bfc741db4ea6be95)

## Related Projects

- **[PRD Completeness Validator](https://github.com/dimospapadopoulos/prd-completeness-validator)** - Validates PRDs against quality standards (pairs with PRD Generator skill directly into your Projects - as you automate 60% of your time towards more strategic thinking)
- **[Voice of Customer Synthesizer](https://github.com/dimospapadopoulos/voc-portfolio-clean)** - Analyzes 150k+ feedback entries annually (feeds insights into Slack for actionability)

---

Author: Dimos Papadopoulos
Role: Product leader / builder
Version: 2.0 (Slack integration)
