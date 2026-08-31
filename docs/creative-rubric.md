# The creative & brand rubric (why vgeval ≠ VBench)

## Positioning

[VBench / VBench++](https://github.com/Vchitect/VBench) answer **"is this a good,
faithful video?"** — an academic benchmark spanning technical quality (temporal
flicker, motion smoothness, imaging), semantic correctness, subject/background
consistency, camera motion, and fairness/trustworthiness. It is broad and deep on
those axes.

vgeval answers a different, commercial question: **"is this clip on-brand,
campaign-usable, and safe to ship at scale without brand or legal risk?"** That is
the creative-director + brand-governance + localization lens, and it is almost
entirely absent from VBench. So the strategy is **layer, don't replace**: ingest
VBench's technical band (see [vbench-integration.md](vbench-integration.md)) and
spend originality on the brand/creative dimensions below.

Our I2V-specific edge: we **always have the source image as ground truth**, so most
brand checks are "does the output still match this exact asset?" — a comparison
task, which is where VLMs are most reliable.

## The `method` taxonomy (auditability)

Every dimension in [`rubric_v2.yaml`](../src/vgeval/judge/rubric_v2.yaml) declares
how it is scored. This is a feature enterprise brand/legal teams care about — each
score says *how* it was produced and how much to trust it.

| method | who scores it | when to use |
|---|---|---|
| `vlm_absolute` | VLM from frames + source image | comparison/qualitative dims the VLM handles well |
| `vlm_with_ground_truth` | VLM, with expected copy/locale injected | copy/language, where a target string exists |
| `vlm_pairwise` | VLM A/B preference (`vgeval compare`) | subjective dims (taste) — pairwise beats absolute |
| `deterministic` | CV/text code, **not** the VLM | color, loop seam — exact, cheap, auditable |
| `human_flag` | VLM triages → flagged for a human | legal/cultural risk — never autonomous |

## Can a VLM actually score these? (honest reasoning)

**The frames-vs-video ceiling (affects everything).** The judge sees ~6 sampled
stills, not the stream. Anything defined over fine temporal dynamics — flicker,
text "swimming", loop seams, motion smoothness — is *systematically
under-observed*. Mitigate by sampling more frames on those dims or routing to CV
(optical flow, pixel diff). Don't let a VLM claim it measured stability it never
saw. (`flickering` is marked with this caveat in the rubric.)

**Text / typography / language — feasible, but not VLM-alone.** Frontier VLMs read
rendered text and flag gibberish; since video models are notoriously bad at text,
there's a lot to catch. But they miss single-glyph errors and kerning. Reliability
jumps when you supply the **expected copy** and pose it as verification, ideally
with a real OCR pass + fuzzy string distance for an auditable number. Today vgeval
scores `copy_language_adherence` as `vlm_with_ground_truth` and logs the VLM's
`transcribed_text`; a deterministic OCR path (e.g. `rapidocr-onnxruntime`, pip-only,
no system binary) is the documented upgrade.

**Color / design system — don't use the VLM for the number.** VLMs are weak at
precise color and can't map to a hex palette. This is a solved deterministic
problem: extract dominant colors per frame, compute **CIE ΔE** vs the brand palette
(implemented in [`scorers.py`](../src/vgeval/judge/scorers.py), numpy-only). The VLM
is reserved for holistic "does this *feel* on-brand" (`design_system_adherence`,
`human_flag`).

**Logo & SKU fidelity — the VLM's sweet spot,** because I2V gives a reference. "Is
this the same logo/product as the source, intact?" is a comparison the VLM handles
well. For precise logo geometry, feature/template matching against the source logo
crop is the deterministic upgrade (`logo_ref` is already plumbed through).

**Subjective creative (taste, cultural fit) — where the tech isn't there yet.** VLMs
give plausible but low-consistency *absolute* scores and are prompt-sensitive — not
defensible for sign-off. So: `motion_tastefulness` is `vlm_pairwise` (preference is
more reliable), and `market_cultural_fit` / `design_system_adherence` /
`unauthorized_claims_or_marks` are `human_flag` (VLM triages, human decides).

## The dimensions

| band | dimension | method | notes |
|---|---|---|---|
| technical_fidelity | prompt_adherence, object_deformation, flickering, defied_physics | vlm_absolute | overlaps VBench; kept lean |
| brand_fidelity | logo_integrity | vlm_absolute | + `logo_ref` for precision |
| brand_fidelity | typography_legibility | vlm_absolute | |
| brand_fidelity | copy_language_adherence | vlm_with_ground_truth | `expected_copy`, `locale` |
| brand_fidelity | brand_color_adherence | deterministic | ΔE vs `brand_palette` |
| brand_fidelity | design_system_adherence | human_flag | |
| product_truth | sku_fidelity | vlm_absolute | reference vs source |
| product_truth | unauthorized_claims_or_marks | human_flag | legal risk |
| creative_craft | hero_focal_clarity | vlm_absolute | |
| creative_craft | crop_safety_multiformat | vlm_absolute | bbox deterministic = future |
| creative_craft | motion_tastefulness | vlm_pairwise | |
| creative_craft | loopability | deterministic | first/last-frame diff |
| localization | market_cultural_fit | human_flag | |

## Supplying ground truth

Add these optional fields per prompt entry (see `prompts/promo_v1.yaml`):

```yaml
- id: lipton_icetea
  source_image: assets/samples/images/lipton_icetea.webp
  expected_copy: "Lipton FRUITY ICE TEA"
  locale: en
  brand_palette: ["#F6C000", "#E4002B", "#00A651", "#005EB8", "#111111"]
  # logo_ref: assets/samples/logos/lipton.png   # optional, for logo_integrity
```

Run it: `vgeval run --suite promo_v1 --rubric rubric_v2 && vgeval judge`.
