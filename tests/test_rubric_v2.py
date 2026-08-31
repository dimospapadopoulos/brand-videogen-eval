"""rubric_v2 structure + routing."""

from vgeval.judge.rubric import Method, resolve_rubric


def test_v2_loads_and_has_bands():
    r = resolve_rubric("rubric_v2")
    assert r.version == "rubric_v2"
    bands = {d.band for d in r.dims}
    assert {"technical_fidelity", "brand_fidelity", "product_truth", "creative_craft"} <= bands


def test_v2_routing_buckets_populated():
    r = resolve_rubric("rubric_v2")
    assert any(d.method is Method.deterministic for d in r.dims)  # ΔE, loop
    assert any(d.method is Method.human_flag for d in r.dims)  # design/claims/culture
    assert {"brand_color_adherence", "loopability"} <= {d.name for d in r.deterministic_dims()}


def test_v2_tool_schema_excludes_deterministic_dims():
    r = resolve_rubric("rubric_v2")
    vlm_names = {d.name for d in r.vlm_dims()}
    schema_props = set(resolve_rubric("rubric_v2").tool_schema().get("input_schema")["properties"])
    assert "brand_color_adherence" not in vlm_names
    assert "brand_color_adherence" not in schema_props
    # copy adherence is VLM-with-ground-truth -> in the VLM tool schema
    assert "copy_language_adherence" in schema_props


def test_v2_ground_truth_requirements():
    r = resolve_rubric("rubric_v2")
    by_name = {d.name: d for d in r.dims}
    assert "brand_palette" in by_name["brand_color_adherence"].requires
    assert "expected_copy" in by_name["copy_language_adherence"].requires
