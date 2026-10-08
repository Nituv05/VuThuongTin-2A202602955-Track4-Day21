"""Validate benchmark evidence, support counts, and optional byte-for-byte replay."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd

CANONICAL = ["calibration_frames.csv", "calibration_objects.csv", "calibration_summary.csv",
             "range_summary.csv", "scene_summary.csv", "frames.csv", "experiment_config.json"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, default=Path("results"))
    ap.add_argument("--compare-dir", type=Path, help="CSV-only replay directory")
    ap.add_argument("--report", type=Path, default=Path("report/REPORT.md"))
    args = ap.parse_args()
    r = args.results
    frames = pd.read_csv(r / "calibration_frames.csv", dtype={"frame_id": str})
    objects = pd.read_csv(r / "calibration_objects.csv", dtype={"frame_id": str})
    assert not frames.duplicated(["dataset", "frame_id", "kind", "value"]).any(), "Duplicate configurations"
    for table in (frames, objects):
        supported = table.baseline_points > 0
        assert ((table.inside_box_hits >= 0) & (table.inside_box_hits <= table.baseline_points)).all()
        np.testing.assert_allclose(table.loc[supported, "alignment_score_pct"],
                                   100. * table.loc[supported, "inside_box_hits"] / table.loc[supported, "baseline_points"])
        assert table.loc[~supported, "alignment_score_pct"].isna().all()
        assert table.loc[~supported, "alert"].isna().all()
        base = table[(table.kind == "yaw") & (table.value == 0)]
        np.testing.assert_allclose(base.drop_pp.dropna(), 0.)
        np.testing.assert_allclose(base.pixel_shift_p50.dropna(), 0.)
    grouped = objects.groupby(["dataset", "frame_id", "kind", "value"])[["baseline_points", "baseline_hits", "inside_box_hits"]].sum()
    actual = frames.set_index(["dataset", "frame_id", "kind", "value"])[grouped.columns].sort_index()
    pd.testing.assert_frame_equal(actual, grouped.sort_index(), check_dtype=False)
    for _, g in frames.groupby(["dataset", "frame_id"]):
        assert len(g) == 20, "Expected 9 yaw, 7 translation, 4 small-yaw levels"
        assert g.baseline_points.nunique() == 1, "Baseline support changed between drift levels"
    evidence = pd.read_csv(r / "evidence.csv", dtype={"frame_id": str})
    assert (evidence.type == "demo").sum() == 3
    assert (evidence.type == "geometry_failure").sum() >= 1
    for _, row in evidence.iterrows():
        assert (r / "figures" / row.figure).is_file(), row.figure
        match = objects[(objects.dataset == row.dataset) & (objects.frame_id == row.frame_id)
                        & (objects.object_index == row.object_index) & (objects.kind == row.kind)
                        & (objects.value == row.value)]
        assert len(match) == 1, "Evidence must map to one real benchmark row"
        for column in ("distance_m", "drop_pp", "pixel_shift_p50"):
            np.testing.assert_allclose(match.iloc[0][column], row[column], atol=1e-10)
    text = args.report.read_text(encoding="utf-8")
    for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        if "://" not in link:
            assert (args.report.parent / link).is_file(), f"Missing report link: {link}"
    assert "[ĐIỀN" not in text, "Report has placeholders"
    print(f"PASS: {len(frames)} configurations, {len(objects)} object rows; counts, scores, evidence and report links")
    if args.compare_dir:
        for name in CANONICAL:
            data = (r / name).read_bytes()
            assert data == (args.compare_dir / name).read_bytes(), f"Replay differs: {name}"
            print(f"IDENTICAL: {name} sha256={hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
