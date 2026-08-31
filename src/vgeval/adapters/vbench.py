"""VBench / VBench++ adapter — ingest their technical scores as an external band.

Design intent: don't reimplement VBench's technical dimensions (temporal quality,
imaging quality, subject/background consistency, camera motion, ...). Instead run
VBench separately and *attach* its per-clip scores to a vgeval run, so vgeval owns
the brand/creative layer and treats technical quality as an imported signal.

Expected input (a JSON you export after running VBench over the same clips):

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

`job_id` is derived as ``f"{provider}__{prompt_id}"`` to match vgeval's runner.
This module is intentionally a thin, dependency-free importer; actually running
VBench (GPU + their models) is out of scope and lives in their repo.
"""

from __future__ import annotations

import json
from pathlib import Path

from vgeval.schemas import ExternalScore
from vgeval.store import RunStore


def parse_vbench_export(path: str | Path) -> list[ExternalScore]:
    """Parse a VBench export JSON into ExternalScore rows (no run mutation)."""
    data = json.loads(Path(path).read_text())
    source = data.get("source", "vbench")
    out: list[ExternalScore] = []
    for row in data.get("scores", []):
        provider = row["provider"]
        prompt_id = row["prompt_id"]
        out.append(
            ExternalScore(
                job_id=f"{provider}__{prompt_id}",
                provider=provider,
                prompt_id=prompt_id,
                source=source,
                dims={k: float(v) for k, v in row.get("dims", {}).items()},
            )
        )
    return out


def attach_to_run(run_id: str, export_path: str | Path) -> int:
    """Import a VBench export and append it to the run's external.jsonl.

    Returns the number of external scores attached. The dashboard/report can then
    show a technical band alongside the creative band.
    """
    store = RunStore.open(run_id)
    scores = parse_vbench_export(export_path)
    for s in scores:
        store.append_external(s)
    return len(scores)
