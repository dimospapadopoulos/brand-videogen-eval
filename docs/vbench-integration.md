# Ingesting VBench / VBench++ technical scores

![VBench / VBench++ evaluation suite overview](https://github.com/user-attachments/assets/9cb38b72-312d-452c-a3b1-51c0dfe87868)

*Figure: the VBench / VBench++ evaluation suite. Source:
[VBench (Vchitect)](https://github.com/Vchitect/VBench) — shown for prior-art
comparison; all credit to the original authors.*

vgeval deliberately does **not** reimplement VBench's technical dimensions
(temporal quality, imaging quality, subject/background consistency, camera
motion, …). Those are well covered by [VBench](https://github.com/Vchitect/VBench)
and require their models + a GPU. Instead, run VBench separately over the *same
clips* and **attach** its per-clip scores to a vgeval run as an external
"technical band", so vgeval owns the brand/creative layer.

## Flow

```
vgeval run  ──►  runs/<id>/videos/*.mp4
                      │
                      ├─► VBench (their repo, GPU) ──► vbench_export.json
                      │
                      └─► vgeval judge (creative/brand band)
                                     │
        vbench_export.json ──────────┴──► attach_to_run() ──► runs/<id>/external.jsonl
                                                                    │
                                                       dashboard shows both bands
```

## Export format

After running VBench, produce a JSON keyed to the same `provider` / `prompt_id`
vgeval used (job id is `f"{provider}__{prompt_id}"`):

```json
{
  "source": "vbench++",
  "scores": [
    {
      "provider": "runway",
      "prompt_id": "lipton_icetea",
      "dims": {
        "subject_consistency": 0.94,
        "temporal_flickering": 0.88,
        "video_image_subject_consistency": 0.91,
        "video_text_camera_motion": 0.72
      }
    }
  ]
}
```

## Attach it

```python
from vgeval.adapters.vbench import attach_to_run
n = attach_to_run("run_20260831_110544", "vbench_export.json")
print(f"attached {n} external scores")
```

This appends `ExternalScore` rows to `runs/<id>/external.jsonl`. The dashboard /
report can then render a technical band beside the creative band without vgeval
ever computing those metrics.

## Why this split is the right call

- **No duplication / no drift** — you get VBench's validated metrics as-is.
- **Clear value story** — vgeval is the *creative & brand* layer; VBench is the
  *technical* layer; the two compose.
- **Cheap** — the adapter is dependency-free JSON ingestion; the expensive
  GPU eval stays in VBench's environment.

> Status: this adapter is a thin, tested importer. Actually invoking VBench
> (model download, GPU inference) is intentionally out of scope and lives in
> their repo; wire it into your own pipeline and emit the JSON above.
