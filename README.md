# videogen-eval-portfolio

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-BSD--3--Clause-green)
![Judge](https://img.shields.io/badge/judge-Claude%20Opus%204.8-8A2BE2)
![Scoring](https://img.shields.io/badge/scoring-VLM%20%2B%20deterministic%20%2B%20human-orange)
![Tests](https://img.shields.io/badge/tests-23%20passing-brightgreen)

> An enterprise **image-to-video** evaluation harness that scores generated ad
> creative on what a **brand and marketer** actually care about — on-brand,
> campaign-usable, and safe to ship at scale — as a layer *on top of* technical
> benchmarks like VBench.

## The Problem

Enterprise-wide generative evaluation is an unsolved gap. On one hand, there's
brand teams requiring adherence to the bible (logos, fonts, typography, style,
esthetic etc.), on the other creative and marketing agencies who are interested in
both the experience but also the sheer volume of assets to meet campaign demands.
And in the middle of it all? Performance. Creative that not only invokes emotion
but also converts or generates awareness; the buzz that all brands chase.

From research, I found VBench (and later VBench++) which is a great benchmark
answering the question: 'Is this a good, faithful generation?'. It's very elaborate
and covers many aspects required for on-point technical generations.

![VBench / VBench++ evaluation suite (image-to-video)](https://github.com/user-attachments/assets/9cb38b72-312d-452c-a3b1-51c0dfe87868)

*The VBench / VBench++ suite. Source: [VBench by Vchitect](https://github.com/Vchitect/VBench) — shown for prior-art comparison; all credit to the original authors. vgeval layers the marketing/brand rubric on top rather than replacing it.*

However, I couldn't find any major good open standard tailored to enterprise
marketing, so I wanted to design some rubric based on what I learned shipping
creative for my original IP (The Cosmic Ones) at-scale (email+medium+pinterest+
youtube+meta+book content) and at my current role.

I have redefined some of the rubrics to what a brand would absolutely care more
about and enriched it with a few core rubrics. The core questions I want my model
to evaluate on top are 'is this clip on-brand, campaign-usable, and safe to ship at
scale without brand/legal risk?'.

This project aims to automate evaluations using AI to score and judge different
models' performance at the core of what a marketer or brand creative would most
care about on top of the technical rubrics that VBench covers.

This working reference implementation proves out that an LLM-as-a-judge with
computer vision capabilities, ground truth alongside a deterministic model and a
human flag (per different dimensions) can judge creative and score it, thus helping
in the creative generation process.

## The What

An image-to-video (img2video) model evaluation harness, built for producing and
comparing advertising / promotional video at scale. Give it a source image +
prompt; it generates a clip per model, scores each with a **hybrid vision judge**
against a configurable rubric — a 9-dimension technical baseline (`rubric_v1`) and
a **creative & brand band** (`rubric_v2`) — and lets you browse results in an
interactive dashboard.

The design goal is extensibility: adding a new model as it ships is one adapter
file + one decorator — the runner, judge, and dashboard never change.

**Runs with zero keys and zero cost.** v1 ships a `mock` provider that serves
bundled/synthetic clips, so the whole pipeline — generate → judge → dashboard —
works offline out of the box. Real judging uses Claude Opus 4.8 and needs an API
key. The deterministic scorers (color, loop) and the keyless stub judge run
without any key at all.

## Architecture

```
        prompts/suite.yaml (+ optional ground truth) + assets/samples/images
                              │
                              ▼
   ┌────────────┐   provider × prompt matrix    ┌──────────────┐
   │  Providers │ ───────────────────────────▶  │   Runner     │  async, resumable, cached
   │ (registry) │   mock | runway | veo | …      │ runs/<id>/   │  → videos + sampled frames
   └────────────┘                                └──────┬───────┘
                                                        │ source image + frames + ground truth
                                                        ▼
                          ┌───────────────────────────────────────────────┐
                          │             Hybrid judge (per dimension)        │
                          │  • VLM (Claude Opus 4.8)  — qualitative dims     │
                          │  • deterministic (numpy)  — ΔE color, loop seam  │
                          │  • ground-truth (OCR/str) — copy & language      │
                          │  • human_flag             — legal/culture review │
                          │  stub judge = keyless · rubric frozen per run    │
                          └───────────────────────┬─────────────────────────┘
                                                  │ results.jsonl (+ methods, needs_review)
              VBench/VBench++ technical scores ──▶ external.jsonl   (see docs/vbench-integration.md)
                                                  ▼
                                      ┌───────────────────┐
                                      │ Streamlit dashboard│  leaderboard · gallery ·
                                      │                   │  compare · per-dim charts
                                      └───────────────────┘
```

## Evaluation rubrics

Two rubrics ship, selectable with `--rubric`:

- **`rubric_v1`** — a lean 9-dimension **technical** baseline (overlaps VBench).
- **`rubric_v2`** — the differentiator: a **creative & brand band** for
  marketing-at-scale, grouped into *technical fidelity · brand fidelity · product
  truth · creative craft · localization*.

Every v2 dimension declares a **`method`** so each score is auditable — you always
know *how* it was produced and how much to trust it:

| method | who scores it | example dims |
|---|---|---|
| `vlm_absolute` | VLM from frames + source image | prompt_adherence, sku_fidelity |
| `vlm_with_ground_truth` | VLM + expected copy/locale injected | copy_language_adherence |
| `vlm_pairwise` | VLM A/B preference (`vgeval compare`) | motion_tastefulness |
| `deterministic` | CV/text code, **not** the VLM | brand_color_adherence, loopability |
| `human_flag` | VLM triages → routed to a human | design_system, claims, cultural fit |

The rubric used is **frozen into each run** (`rubric.snapshot.yaml`), scores carry
their `methods`, and `human_flag` dims populate `needs_review` — so the harness is
reproducible and defensible for brand/legal governance. See
[docs/creative-rubric.md](docs/creative-rubric.md) for the full reasoning, and
[docs/vbench-integration.md](docs/vbench-integration.md) for ingesting VBench's
technical band instead of reimplementing it.

### Rubric dimensions

`Version` = which rubric it appears in. `VLM-scorable today?` is an honest read for
current frontier VLMs (Opus 4.8-class); the sampled-frames design also under-observes
fine temporal dynamics (flicker, loop seams), which is why some dims route to CV.

| Rubric dimension | Version | Why a creative / marketer cares | VLM-scorable today? | Recommended scoring technology |
|---|---|---|---|---|
| `prompt_adherence` | v1, v2 | The clip must depict the brief/concept, or it's off-message | ✅ Yes — strong | VLM absolute (Opus 4.8 vision) |
| `object_deformation` | v1, v2 | Hero product must not warp/melt — integrity is non-negotiable | ✅ Yes, with source ref | VLM + source-image comparison |
| `object_cutoff` | v1 | Product/subject clipped at frame edges ruins the shot | ⚠️ Partial | Deterministic subject-bbox vs safe-area; VLM backup |
| `flickering` | v1, v2 | Strobing/texture-crawl reads cheap, not premium | ⚠️ Limited (temporal) | Dense sampling + optical-flow/pixel-diff (CV) |
| `fast_camera_movement` | v1 | Jarring motion feels low-budget, breaks brand tone | ⚠️ Partial | VLM + optical-flow magnitude (CV) |
| `video_quality` | v1 | Sharpness/artifacts gate broadcast/paid usage | ⚠️ Partial | VLM + no-ref IQA (BRISQUE/NIQE) or VBench imaging |
| `defied_physics` | v1, v2 | Implausible motion breaks believability of the ad | ✅ Yes — moderate | VLM absolute |
| `temporal_object_creation` | v1 | Objects popping in/out looks broken and unshippable | ⚠️ Limited (temporal) | Dense frames + object tracking (CV); VLM backup |
| `aesthetics` | v1, v2* | Overall premium appeal — the "buzz" brands chase | ✅ Yes, subjective | VLM + aesthetic predictor (LAION) / pairwise |
| `logo_integrity` | v2 | The logo is sacred — distortion is a brand & legal failure | ✅ gross / ❌ subtle geometry | VLM + template/feature match to `logo_ref` |
| `typography_legibility` | v2 | Garbled on-product text is instantly unusable | ⚠️ Partial | OCR (rapidocr/tesseract) legibility + VLM |
| `copy_language_adherence` | v2 | Right words & language for localized, compliant campaigns | ✅ Yes, with ground truth | VLM-with-ground-truth + OCR + fuzzy string match |
| `brand_color_adherence` | v2 | Palette *is* brand identity; drift is off-brand | ❌ No (numeric task) | **Deterministic CIE ΔE** vs brand hex palette *(implemented)* |
| `design_system_adherence` | v2 | Holistic on-brand feel — spacing, tone, guidelines | ⚠️ Weak / subjective | `human_flag` (VLM triage) + guideline RAG (future) |
| `sku_fidelity` | v2 | Must show the exact product sold — claims/legal accuracy | ✅ Yes (reference compare) | VLM + source-image compare / embedding similarity |
| `unauthorized_claims_or_marks` | v2 | Invented claims or competitor marks = legal exposure | 🔎 Detect yes / adjudicate no | OCR + VLM detect → policy allowlist → `human_flag` |
| `hero_focal_clarity` | v2 | Product must be the unmistakable hero, not upstaged | ✅ Yes | VLM + saliency map (CV) optional |
| `crop_safety_multiformat` | v2 | One master must reframe to 9:16 / 1:1 / 16:9 safely | ⚠️ Partial | Deterministic subject-bbox vs safe-area per ratio + VLM |
| `motion_tastefulness` | v2 | Premium vs gimmicky motion — brand tone | 🎭 Subjective → pairwise | VLM pairwise preference |
| `loopability` | v2 | Seamless loops for social/stock reuse at scale | ❌ No (temporal seam) | **Deterministic first/last-frame diff** *(implemented)* |
| `market_cultural_fit` | v2 | Locale-appropriate gestures/symbols — reputational risk | ⚠️ Risky / subjective | `human_flag` (VLM triage) + regional reviewer |

\* `aesthetics` is scored in v1; v2 expresses the same intent through
`hero_focal_clarity` and `motion_tastefulness`.

## Quickstart (no API key)

```bash
# 1. Install uv (https://astral.sh/uv). If behind a TLS-inspecting proxy:
export UV_SYSTEM_CERTS=1

# 2. Create env + install
uv venv --python 3.11
uv pip install -e ".[dev]"

# 3a. Technical baseline (rubric_v1) with the keyless stub judge
uv run vgeval run --provider mock
uv run vgeval judge --stub

# 3b. Or the creative & brand band (rubric_v2) — runs the deterministic scorers too
uv run vgeval run --suite promo_v1 --provider mock --rubric rubric_v2
uv run vgeval judge --stub

# 4. Browse results
uv run vgeval dashboard
```

## Real judging (Claude Opus 4.8)

```bash
cp .env.example .env    # set ANTHROPIC_API_KEY
uv run vgeval judge     # scores the latest run with Opus 4.8
```

## Compare real model outputs (bring-your-own clips)

No per-vendor API integration needed to compare models. Generate clips in each
model's UI (Sora, Veo, Runway, Kling, …) or your own pipeline, then drop them into
**one folder per model** — the folder name becomes the provider, the filename is
the prompt id:

```
assets/samples/videos/
  sora/    nike_basketball.mp4   lipton_icetea.mp4
  veo/     nike_basketball.mp4   lipton_icetea.mp4
  runway/  nike_basketball.mp4   lipton_icetea.mp4
```

Then run and judge — **only the judge costs money; there is no generation cost**:

```bash
uv run vgeval providers                                  # sora, veo, runway now listed
uv run vgeval run --suite promo_v1 \
  --provider sora --provider veo --provider runway --rubric rubric_v2
uv run vgeval judge                                      # Opus 4.8 scores every clip
uv run vgeval dashboard                                  # Compare tab shows them side by side
```

## Cost & controls

The judge makes **one Opus vision call per clip** (source image + sampled frames),
so cost scales with *clips × frames* — not with the number of rubric dimensions
(deterministic and `human_flag` dims make no API call). Levers:

- `vgeval judge` is **idempotent** — re-runs don't re-charge scored clips (use `--force` to re-score).
- Iterate cheaply on Sonnet, do the final pass on Opus: `VGEVAL_JUDGE_MODEL=claude-sonnet-5`.
- Fewer frames = fewer image tokens: `VGEVAL_JUDGE_FRAMES=4`.
- Use `--stub` (free) for any pipeline/dashboard change; spend only on the final judge pass.

## Add your own content

* **Prompt suite** → drop a YAML in `prompts/` (see `prompts/promo_v1.yaml`).
* **Source images** → `assets/samples/images/`.
* **Sample output videos** (served by the mock provider) → `assets/samples/videos/`.
* **Ground truth** (per prompt entry, optional) → `expected_copy`, `locale`,
  `brand_palette` (hex list), `logo_ref` — these power the brand/creative dims.
* **Rubric** → edit `src/vgeval/judge/rubric.yaml` (v1) or
  `src/vgeval/judge/rubric_v2.yaml` (v2). Dimension names are fixed; the
  definitions, scale, and `method` routing are yours.

## Add a new model

See [docs/adding-a-provider.md](docs/adding-a-provider.md). In short: subclass
`ImageToVideoProvider`, add `@register("<name>")`, implement `generate()`. It
appears on the CLI and in the dashboard automatically.

## Development

```bash
uv run ruff check .
uv run pytest
uv run vgeval canary    # full mock pipeline end-to-end, rubric_v2 (what CI/cron run)
```

## License & attribution

BSD 3-Clause (see `LICENSE`). If you use or build on this work, please retain the
copyright notice and credit the author — see `NOTICE`.

## Connect

* GitHub: [@dimospapadopoulos](https://github.com/dimospapadopoulos)
* LinkedIn: [Dimos Papadopoulos](https://linkedin.com/in/dimosp)
* Portfolio: [Other Projects](https://www.notion.so/Dimos-Papadopoulos-Product-Portfolio-ad6dd941f79c4d28bfc741db4ea6be95)

## Other Projects

* [Multi-agent PRD Checker](https://github.com/dimospapadopoulos/multi-agent-prd-reviewer) — AI-powered system that uses four specialised agents to review Product Requirement Documents, combining rule-based validation with AI-driven technical, UX, and legal critique. 
* [PRD Completeness Validator](https://github.com/dimospapadopoulos/prd-completeness-validator) — Validates PRDs against quality standards (pairs with the PRD Generator skill directly into your Projects — automating ~60% of the busywork toward more strategic thinking)
* [Voice of Customer Synthesizer](https://github.com/dimospapadopoulos/voc-portfolio-clean) — Analyzes 150k+ feedback entries annually (feeds insights into Slack for actionability)

---

*Author: Dimos Papadopoulos · Role: Product leader / builder · Version: 2.0 (creative & brand rubric + hybrid judge)*
