from datetime import UTC, datetime

from vgeval.schemas import RUBRIC_DIMS, JobState, JobStatus, JudgeScore, RunManifest


def test_rubric_has_nine_fixed_dims():
    assert len(RUBRIC_DIMS) == 9
    assert RUBRIC_DIMS[0] == "prompt_adherence"
    assert RUBRIC_DIMS[-1] == "aesthetics"


def test_manifest_json_round_trip():
    m = RunManifest(
        run_id="run_x",
        created_at=datetime.now(UTC),
        providers=["mock"],
        suite_version="v1",
        rubric_version="rubric_v1",
        jobs=[JobState(job_id="mock__p1", provider="mock", prompt_id="p1", cache_key="abc")],
    )
    again = RunManifest.model_validate_json(m.model_dump_json())
    assert again.jobs[0].status == JobStatus.pending
    assert again.run_id == "run_x"


def test_judge_score_round_trip():
    s = JudgeScore(
        job_id="mock__p1", provider="mock", prompt_id="p1",
        dims={d: 3 for d in RUBRIC_DIMS},
    )
    assert JudgeScore.model_validate_json(s.model_dump_json()).dims == s.dims
