from vgeval.judge.rubric import load_rubric
from vgeval.schemas import RUBRIC_DIMS


def test_rubric_dims_match_fixed_set():
    rubric = load_rubric()
    assert tuple(d.name for d in rubric.dims) == RUBRIC_DIMS


def test_tool_schema_requires_all_dims():
    rubric = load_rubric()
    schema = rubric.tool_schema()
    required = schema["input_schema"]["required"]
    assert set(required) == set(RUBRIC_DIMS)
    for dim in RUBRIC_DIMS:
        prop = schema["input_schema"]["properties"][dim]
        assert prop["type"] == "integer"
        assert prop["minimum"] == rubric.scale.min
        assert prop["maximum"] == rubric.scale.max
