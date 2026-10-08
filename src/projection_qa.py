"""Topic A: reproducible LiDAR-camera calibration QA on supplied datasets.

Original student implementation assisted by OpenAI Codex; geometry conventions
and dataset access follow the lab's starter code and data/README.md.
No pretrained model, external code copy, or generated evidence is used.
Run: python -m src.projection_qa --help
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from starter.data_health import point_stats
from starter.datasets import dataset_type, list_frames, load_frame
from starter.projection import (
    draw_box2d, overlay_points, perturb_extrinsic, project_velo_to_image, velo_to_cam,
)

YAW_LEVELS = (-3., -2., -1., -.5, 0., .5, 1., 2., 3.)
TRANSLATION_LEVELS = (-10., -5., -2., 0., 2., 5., 10.)
SMALL_YAW_LEVELS = (-.25, -.1, .1, .25)


def points_in_box(points_cam, obj):
    """KITTI box: bottom center, dimensions (h,w,l), rotation about camera y.

    Row-vector inverse rotation: (point - bottom_center) @ R.
    nuScenes converted boxes follow the starter's yaw-only approximation.
    """
    h, w, length = obj.dimensions
    c, s = np.cos(obj.rotation_y), np.sin(obj.rotation_y)
    rotation = np.array([[c, 0., s], [0., 1., 0.], [-s, 0., c]])
    local = (points_cam - obj.location) @ rotation
    return (np.isfinite(local).all(axis=1)
            & (np.abs(local[:, 0]) <= length / 2 + 1e-6)
            & (local[:, 1] >= -h - 1e-6) & (local[:, 1] <= 1e-6)
            & (np.abs(local[:, 2]) <= w / 2 + 1e-6))


def range_bucket(distance_m):
    return "near_lt10m" if distance_m < 10 else "mid_10to30m" if distance_m <= 30 else "far_gt30m"


def expanded_projection(points, calib, shape):
    """Keep point indices: invalid/out-of-FOV pixels stay NaN."""
    uv, depth, mask = project_velo_to_image(points, calib, shape)
    full_uv = np.full((len(points), 2), np.nan)
    full_depth = np.full(len(points), np.nan)
    full_uv[mask], full_depth[mask] = uv, depth
    return full_uv, full_depth, mask


def count_inside(uv, bbox):
    x1, y1, x2, y2 = bbox
    return int(((uv[:, 0] >= x1) & (uv[:, 0] <= x2)
                & (uv[:, 1] >= y1) & (uv[:, 1] <= y2)).sum())


def percent(numerator, denominator):
    return 100. * numerator / denominator if denominator else np.nan


def alignment_metrics(n, baseline_hits, hits, threshold_pp=10.):
    """Fixed denominator; undefined scores and alerts stay NaN without support."""
    baseline = percent(baseline_hits, n)
    score = percent(hits, n)
    drop = baseline - score
    return baseline, score, drop, bool(drop >= threshold_pp) if n else np.nan


def drift_calib(calib, kind, value, dtype):
    if kind in {"yaw", "small_yaw"}:
        # Yaw is rotation about z-up in BOTH datasets; their horizontal axes differ.
        return perturb_extrinsic(calib, yaw_deg=value)
    # Signed displacement along native lateral axis: KITTI y-left, nuScenes x-right.
    lateral = (0., value / 100., 0.) if dtype == "kitti" else (value / 100., 0., 0.)
    return perturb_extrinsic(calib, t_xyz_m=lateral)


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"No rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def evaluate_frame(root, fid, threshold):
    dtype = dataset_type(root)
    dataset = Path(root).name
    fr = load_frame(root, fid)
    pts, shape = fr["points"], fr["image"].shape
    base_uv, _, base_mask = expanded_projection(pts, fr["calib"], shape)
    cam = velo_to_cam(pts[:, :3], fr["calib"])
    objects = []
    for index, obj in enumerate(fr["labels"]):
        selection = np.flatnonzero(points_in_box(cam, obj) & base_mask)
        objects.append((index, obj, selection, count_inside(base_uv[selection], obj.bbox)))

    frame_rows, object_rows = [], []
    configs = [("yaw", v, "deg") for v in YAW_LEVELS]
    configs += [("translation", v, "cm") for v in TRANSLATION_LEVELS]
    configs += [("small_yaw", v, "deg") for v in SMALL_YAW_LEVELS]
    finite_count = int(np.isfinite(pts[:, :3]).all(axis=1).sum())
    total = sum(len(indices) for _, _, indices, _ in objects)
    baseline_hits = sum(hits for _, _, _, hits in objects)
    for kind, value, unit in configs:
        calib = drift_calib(fr["calib"], kind, value, dtype)
        uv, _, mask = expanded_projection(pts, calib, shape)
        common = base_mask & mask
        displacement = np.linalg.norm(uv[common] - base_uv[common], axis=1)
        common_p50, common_p95 = np.percentile(displacement, [50, 95]) if len(displacement) else (np.nan, np.nan)
        shared = {"dataset": dataset, "scene": fid.rsplit("_", 1)[0] if dtype == "nuscenes" else "kitti",
                  "frame_id": fid, "kind": kind, "value": value, "unit": unit}
        total_hits = 0
        for index, obj, indices, initial_hits in objects:
            n = len(indices)
            hits = count_inside(uv[indices], obj.bbox)
            total_hits += hits
            base_score, score, drop, alert = alignment_metrics(n, initial_hits, hits, threshold)
            valid_indices = indices[mask[indices]]
            movement = np.linalg.norm(uv[valid_indices] - base_uv[valid_indices], axis=1)
            distance = float(np.linalg.norm(obj.location))
            object_rows.append({**shared, "object_index": index, "class": obj.type,
                                "distance_m": distance, "range_bucket": range_bucket(distance),
                                "occluded": obj.occluded, "truncated": obj.truncated,
                                "baseline_points": n, "baseline_hits": initial_hits,
                                "inside_box_hits": hits, "out_of_fov_points": n - len(valid_indices),
                                "baseline_score_pct": base_score, "alignment_score_pct": score,
                                "drop_pp": drop, "alert": alert,
                                "pixel_shift_p50": float(np.median(movement)) if len(movement) else np.nan})
        base_score, score, drop, alert = alignment_metrics(total, baseline_hits, total_hits, threshold)
        frame_rows.append({**shared, "n_points": len(pts), "finite_xyz_points": finite_count,
                           "fov_points": int(mask.sum()), "fov_pct": percent(int(mask.sum()), finite_count),
                           "baseline_fov_lost_points": int((base_mask & ~mask).sum()),
                           "common_fov_points": int(common.sum()),
                           "pixel_shift_p50": float(common_p50), "pixel_shift_p95": float(common_p95),
                           "objects": len(objects), "objects_with_points": sum(len(i) > 0 for _, _, i, _ in objects),
                           "baseline_points": total, "baseline_hits": baseline_hits, "inside_box_hits": total_hits,
                           "baseline_score_pct": base_score, "alignment_score_pct": score,
                           "drop_pp": drop, "alert": alert})
    meta = {"dataset": dataset, "frame_id": fid, "image_width": shape[1], "image_height": shape[0],
            "timestamp_lidar_us": fr.get("timestamp_lidar_us", ""),
            "camera_minus_lidar_ms": (fr["timestamp_camera_us"] - fr["timestamp_lidar_us"]) / 1000.
            if "timestamp_lidar_us" in fr else "",
            **point_stats(pts)}
    return frame_rows, object_rows, meta


def aggregate(frame_rows, object_rows, out):
    frames = pd.DataFrame(frame_rows)
    objects = pd.DataFrame(object_rows)
    summary = []
    for keys, g in frames.groupby(["dataset", "kind", "value", "unit"], sort=True):
        dataset, kind, value, unit = keys
        baseline, score, drop, _ = alignment_metrics(g.baseline_points.sum(), g.baseline_hits.sum(), g.inside_box_hits.sum())
        defined = g[g.baseline_points > 0]
        summary.append({"dataset": dataset, "kind": kind, "value": value, "unit": unit,
                        "frames": len(g), "evaluable_frames": len(defined),
                        "fov_pct": percent(g.fov_points.sum(), g.finite_xyz_points.sum()),
                        "baseline_score_pct": baseline, "alignment_score_pct": score, "drop_pp": drop,
                        "median_frame_pixel_shift_p50": g.pixel_shift_p50.median(),
                        "median_frame_pixel_shift_p95": g.pixel_shift_p95.median(),
                        "alert_rate_pct": 100. * defined.alert.astype(float).mean() if len(defined) else np.nan})
    write_csv(out / "calibration_summary.csv", summary)
    ranges = []
    for keys, g in objects.groupby(["dataset", "kind", "value", "unit", "range_bucket"], sort=True):
        baseline, score, drop, _ = alignment_metrics(g.baseline_points.sum(), g.baseline_hits.sum(), g.inside_box_hits.sum())
        ranges.append(dict(zip(["dataset", "kind", "value", "unit", "range_bucket"], keys)) | {
            "objects": len(g), "objects_with_points": int((g.baseline_points > 0).sum()),
            "baseline_points": int(g.baseline_points.sum()), "baseline_score_pct": baseline,
            "alignment_score_pct": score, "drop_pp": drop,
            "median_object_pixel_shift_p50": g.pixel_shift_p50.median()})
    write_csv(out / "range_summary.csv", ranges)
    # Keep scenes separate: day/night are confounded with scene geometry and traffic.
    scenes = []
    for keys, g in frames.groupby(["dataset", "scene", "kind", "value", "unit"], sort=True):
        base, score, drop, _ = alignment_metrics(g.baseline_points.sum(), g.baseline_hits.sum(), g.inside_box_hits.sum())
        scenes.append(dict(zip(["dataset", "scene", "kind", "value", "unit"], keys)) | {
            "frames": len(g), "baseline_score_pct": base, "alignment_score_pct": score,
            "drop_pp": drop, "median_frame_pixel_shift_p50": g.pixel_shift_p50.median()})
    write_csv(out / "scene_summary.csv", scenes)
    return pd.DataFrame(summary), objects, frames


def plot_results(summary, frames, out, threshold):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for j, kind in enumerate(("yaw", "translation")):
        for dataset, g in summary[summary.kind == kind].groupby("dataset"):
            axes[0, j].plot(g.value, g.drop_pp, "o-", label=dataset)
            axes[1, j].plot(g.value, g.median_frame_pixel_shift_p50, "o-", label=dataset)
        axes[0, j].axhline(threshold, color="crimson", linestyle="--", label=f"{threshold:g} pp reference")
        axes[0, j].set_ylabel("Pooled alignment loss (percentage points)")
        axes[1, j].set_ylabel("Median of frame p50 pixel shifts (px)")
        for i in (0, 1):
            axes[i, j].set_xlabel("Yaw drift (deg)" if kind == "yaw" else "Native lateral translation (cm)")
            axes[i, j].grid(alpha=.25)
            axes[i, j].legend(fontsize=8)
    fig.suptitle("Calibration sensitivity | fixed baseline object points | KITTI + nuScenes")
    fig.savefig(out / "calibration_sweep.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    for dataset, g in summary[summary.kind.isin(["yaw", "small_yaw"])].groupby("dataset"):
        g = g.sort_values("value")
        axes[0].plot(g.value, g.alert_rate_pct, "o-", label=dataset)
    axes[0].set(xlabel="Yaw drift (deg)", ylabel="Frames alerting (%)", title="Alert: frame score drop >= threshold")
    axes[0].legend(fontsize=8)
    for dataset, g in frames.groupby("dataset"):
        g = g[(g.kind == "small_yaw") & (g.baseline_points > 0)]
        axes[1].scatter(g.pixel_shift_p50, g.drop_pp, s=12, alpha=.4, label=dataset)
    axes[1].axhline(threshold, color="crimson", linestyle="--")
    axes[1].set(xlabel="Frame p50 displacement (px)", ylabel="Frame alignment loss (pp)", title="Small drift may remain below threshold")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.25)
    fig.savefig(out / "drift_detection.png", dpi=160)
    plt.close(fig)


def annotated_object(root, row, kind=None, value=0.):
    fr = load_frame(root, row.frame_id)
    obj = fr["labels"][int(row.object_index)]
    cam = velo_to_cam(fr["points"][:, :3], fr["calib"])
    _, _, base_mask = expanded_projection(fr["points"], fr["calib"], fr["image"].shape)
    indices = np.flatnonzero(points_in_box(cam, obj) & base_mask)
    calib = drift_calib(fr["calib"], kind, value, dataset_type(root)) if kind else fr["calib"]
    uv, depth, _ = project_velo_to_image(fr["points"][indices], calib, fr["image"].shape)
    image = overlay_points(fr["image"], uv, depth, radius=2)
    image = draw_box2d(image, obj.bbox, color=(0, 255, 0))
    hits = count_inside(uv, obj.bbox)
    return image, obj, len(indices), hits


def save_comparison(root, row, path, title):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    for ax, kind, value in zip(axes, (None, row.kind), (0., row.value)):
        vis, obj, n, hits = annotated_object(root, row, kind, value)
        ax.imshow(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
        ax.set_title(f"{'Baseline' if kind is None else str(kind) + ' ' + str(value) + ' ' + row.unit}\n"
                     f"{obj.type}: {hits}/{n} points inside fixed 2D box")
        ax.axis("off")
    fig.suptitle(title, fontsize=11)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def make_evidence(roots, objects, frames, out):
    root_of = {Path(root).name: root for root in roots}
    baseline = objects[(objects.kind == "yaw") & (objects.value == 0) & (objects.baseline_points >= 20)]
    records = []
    for bucket in ("near_lt10m", "mid_10to30m", "far_gt30m"):
        candidates = baseline[(baseline.range_bucket == bucket) & (baseline.dataset == "kitti_mini")]
        if candidates.empty:
            candidates = baseline[baseline.range_bucket == bucket]
        if candidates.empty:
            raise ValueError(f"No supported demo object in {bucket}")
        row = candidates.sort_values(["baseline_points", "frame_id", "object_index"], ascending=[False, True, True]).iloc[0]
        vis, obj, n, hits = annotated_object(root_of[row.dataset], row)
        title = f"{row.dataset}/{row.frame_id} | {obj.type} | {row.distance_m:.1f} m | {hits}/{n} inside box"
        cv2.rectangle(vis, (0, 0), (vis.shape[1], 30), (0, 0, 0), -1)
        cv2.putText(vis, title, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1)
        filename = f"demo_{bucket}.png"
        if not cv2.imwrite(str(out / filename), vis):
            raise OSError(f"Could not write {filename}")
        records.append({"type": "demo", "dataset": row.dataset, "frame_id": row.frame_id,
                        "object_index": int(row.object_index), "class": row["class"],
                        "distance_m": row.distance_m, "figure": filename,
                        "kind": "yaw", "value": 0., "drop_pp": 0., "pixel_shift_p50": 0.})

    drift = objects[(objects.kind == "yaw") & (objects.value.abs() >= 1) & (objects.baseline_points >= 20)]
    if drift.empty:
        raise ValueError("No supported geometry failure candidate")
    row = drift.sort_values(["drop_pp", "baseline_points"], ascending=[False, False]).iloc[0]
    filename = "fail_01_geometry_yaw.png"
    save_comparison(root_of[row.dataset], row, out / filename,
                    f"Geometry failure | {row.dataset}/{row.frame_id} | alignment loss {row.drop_pp:.1f} pp")
    records.append({"type": "geometry_failure", "dataset": row.dataset, "frame_id": row.frame_id,
                    "object_index": int(row.object_index), "class": row["class"], "distance_m": row.distance_m,
                    "figure": filename, "kind": row.kind, "value": row.value,
                    "drop_pp": row.drop_pp, "pixel_shift_p50": row.pixel_shift_p50})

    # Operational alert is per frame, not per object. Require the frame AND object to miss.
    missed_frames = frames[(frames.kind.isin(["small_yaw", "yaw"])) & (frames.value != 0)
                           & (frames.baseline_points > 0) & (frames.alert == False)
                           & (frames.pixel_shift_p50 >= 5)][["dataset", "frame_id", "kind", "value"]]
    missed = objects.merge(missed_frames, on=["dataset", "frame_id", "kind", "value"])
    missed = missed[(missed.baseline_points >= 20) & (missed.alert == False) & (missed.pixel_shift_p50 >= 5)]
    if not missed.empty:
        row = missed.sort_values(["pixel_shift_p50", "baseline_points"], ascending=[False, False]).iloc[0]
        filename = "fail_02_metric_missed_drift.png"
        save_comparison(root_of[row.dataset], row, out / filename,
                        f"Metric failure | {row.dataset}/{row.frame_id} | shift {row.pixel_shift_p50:.1f}px, loss {row.drop_pp:.1f}pp < threshold")
        records.append({"type": "metric_failure", "dataset": row.dataset, "frame_id": row.frame_id,
                        "object_index": int(row.object_index), "class": row["class"], "distance_m": row.distance_m,
                        "figure": filename, "kind": row.kind, "value": row.value,
                        "drop_pp": row.drop_pp, "pixel_shift_p50": row.pixel_shift_p50})
    return records


def main():
    ap = argparse.ArgumentParser(description="Topic A: benchmark calibration drift and create real evidence on CPU")
    ap.add_argument("--data-roots", nargs="+", default=["data/kitti_mini", "data/nuscenes_mini_subset"])
    ap.add_argument("--frames", nargs="+", help="Optional frame IDs; validated against each specified dataset")
    ap.add_argument("--out-dir", type=Path, default=Path("results"))
    ap.add_argument("--threshold-pp", type=float, default=10., help="Frame alignment loss threshold in percentage points")
    ap.add_argument("--seed", type=int, default=42, help="Recorded seed; experiment itself uses no random sampling")
    ap.add_argument("--skip-figures", action="store_true", help="CSV-only repeat for reproducibility checks")
    args = ap.parse_args()
    if not np.isfinite(args.threshold_pp) or not 0 < args.threshold_pp <= 100:
        ap.error("--threshold-pp must be finite and in (0,100]")
    roots = args.data_roots
    if len({Path(r).name for r in roots}) != len(roots):
        ap.error("Dataset directory names must be unique")
    # Validate all inputs before producing partial outputs.
    selections = []
    for root in roots:
        available = list_frames(root)
        fids = args.frames or available
        missing = sorted(set(fids) - set(available))
        if missing or not fids:
            ap.error(f"Invalid/empty frames for {root}: {missing}")
        selections.append((root, fids))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    figures = args.out_dir / "figures"
    figures.mkdir(exist_ok=True)
    frame_rows, object_rows, metadata = [], [], []
    for root, fids in selections:
        for i, fid in enumerate(fids, 1):
            f, o, meta = evaluate_frame(root, fid, args.threshold_pp)
            frame_rows.extend(f)
            object_rows.extend(o)
            metadata.append(meta)
            if i == 1 or i % 10 == 0 or i == len(fids):
                print(f"{Path(root).name}: {i}/{len(fids)} frames", flush=True)
    write_csv(args.out_dir / "calibration_frames.csv", frame_rows)
    write_csv(args.out_dir / "calibration_objects.csv", object_rows)
    write_csv(args.out_dir / "frames.csv", metadata)
    summary, objects, frames = aggregate(frame_rows, object_rows, args.out_dir)
    evidence = []
    if not args.skip_figures:
        plot_results(summary, frames, figures, args.threshold_pp)
        evidence = make_evidence(roots, objects, frames, figures)
        write_csv(args.out_dir / "evidence.csv", evidence)
    config = {"topic": "A", "seed": args.seed, "random_sampling": False,
              "data_roots": roots, "frames": {root: fids for root, fids in selections},
              "yaw_deg": YAW_LEVELS, "lateral_translation_cm": TRANSLATION_LEVELS,
              "small_yaw_deg": SMALL_YAW_LEVELS, "threshold_pp": args.threshold_pp,
              "min_depth_m": .1, "ego_motion_compensation": True,
              "projection_displacement": "Common FOV point IDs; losses from baseline FOV reported separately",
              "alignment": "Point-object pairs in original 3D boxes and baseline FOV; fixed denominator, all classes",
              "alert": "Per-frame baseline_score_pct - alignment_score_pct >= threshold_pp; missing support is undefined",
              "range": "Euclidean norm of camera-frame bottom center (m); <10,10-30,>30",
              "summary_displacement": "Median of per-frame p50/p95; not a pooled point percentile",
              "python": platform.python_version(), "platform": platform.platform(),
              "machine": platform.machine(), "numpy": np.__version__, "opencv": cv2.__version__,
              "matplotlib": matplotlib.__version__, "pandas": pd.__version__}
    (args.out_dir / "experiment_config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Done: {len(metadata)} frames, {len(frame_rows)} configurations, {len(object_rows)} object rows -> {args.out_dir}")


if __name__ == "__main__":
    main()
