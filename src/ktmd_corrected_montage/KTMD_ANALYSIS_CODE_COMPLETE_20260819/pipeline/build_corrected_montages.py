#!/usr/bin/env python3
"""Build deterministic independent local bipolar montages from official NeuroTycho maps.

For Kin2 and Su, all 128 contacts in their official map are matched exactly once.
The objective is lexicographic:
  1) minimize the longest pair distance (minimum bottleneck), then
  2) among feasible perfect matchings at that bottleneck, minimize total distance.

The non-bipartite perfect matching is solved with NetworkX's Blossom implementation.
"""
from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy.io import loadmat

MAP_PATHS = {
    "Kin2": "20110513KTMD_Anesthesia+and+Sleep_Kin2_Toru+Yanagawa_mat_2Dimg/Kin2Map.mat",
    "Su": "20110523KTMD_Anesthesia+and+Sleep_Su_Toru+Yanagawa_mat_2Dimg/SuMap.mat",
}


def load_xy(zip_path: Path, animal: str) -> tuple[np.ndarray, np.ndarray]:
    with zipfile.ZipFile(zip_path) as zf:
        d = loadmat(io.BytesIO(zf.read(MAP_PATHS[animal])))
    x = np.asarray(d["X"], dtype=float).reshape(-1)
    y = np.asarray(d["Y"], dtype=float).reshape(-1)
    if len(x) != 128 or len(y) != 128 or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise RuntimeError(f"{animal}: invalid official X/Y coordinate arrays")
    return x, y


def graph_at_threshold(dist: np.ndarray, threshold: float) -> nx.Graph:
    n = len(dist)
    g = nx.Graph()
    g.add_nodes_from(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            if dist[i, j] <= threshold + 1e-10:
                g.add_edge(i, j, weight=float(dist[i, j]))
    return g


def solve_matching(x: np.ndarray, y: np.ndarray) -> tuple[list[tuple[int, int]], float]:
    xy = np.c_[x, y]
    dist = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=2)
    levels = np.unique(dist[np.triu_indices(len(x), 1)])

    lo, hi = 0, len(levels) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        g = graph_at_threshold(dist, float(levels[mid]))
        matching = nx.max_weight_matching(g, maxcardinality=True, weight=None)
        if len(matching) == len(x) // 2:
            hi = mid
        else:
            lo = mid + 1
    threshold = float(levels[lo])

    g = graph_at_threshold(dist, threshold)
    matching = nx.min_weight_matching(g, weight="weight")
    if len(matching) != len(x) // 2:
        raise RuntimeError("No perfect matching at the computed bottleneck threshold")
    pairs = sorted((min(i, j), max(i, j)) for i, j in matching)
    return pairs, threshold


def build_one(zip_path: Path, animal: str) -> tuple[pd.DataFrame, dict]:
    x, y = load_xy(zip_path, animal)
    pairs, threshold = solve_matching(x, y)
    rows = []
    for idx, (i, j) in enumerate(pairs, start=1):
        distance = float(np.hypot(x[i] - x[j], y[i] - y[j]))
        rows.append({
            "animal": animal,
            "local_pair_index": idx,
            "pair_id": f"BP{i+1:03d}-{j+1:03d}",
            "ch1": i + 1,
            "ch2": j + 1,
            "distance_px": distance,
            "x1": float(x[i]), "y1": float(y[i]),
            "x2": float(x[j]), "y2": float(y[j]),
            "mid_x": float((x[i] + x[j]) / 2),
            "mid_y": float((y[i] + y[j]) / 2),
            "algorithm": "minimum-bottleneck, minimum-total-distance perfect matching on official NeuroTycho X/Y coordinates",
            "bottleneck_threshold_px": threshold,
        })
    frame = pd.DataFrame(rows)
    contacts = pd.concat([frame.ch1, frame.ch2]).astype(int)
    incidence = np.zeros((len(frame), 128), dtype=float)
    for r, row in enumerate(frame.itertuples(index=False)):
        incidence[r, int(row.ch1) - 1] = 1
        incidence[r, int(row.ch2) - 1] = -1
    audit = {
        "animal": animal,
        "n_pairs": int(len(frame)),
        "n_unique_contacts": int(contacts.nunique()),
        "max_contact_use": int(contacts.value_counts().max()),
        "incidence_rank": int(np.linalg.matrix_rank(incidence)),
        "max_distance_px": float(frame.distance_px.max()),
        "mean_distance_px": float(frame.distance_px.mean()),
        "median_distance_px": float(frame.distance_px.median()),
        "bottleneck_threshold_px": threshold,
        "missing_contacts": sorted(set(range(1, 129)) - set(contacts)),
    }
    required = (
        audit["n_pairs"] == 64
        and audit["n_unique_contacts"] == 128
        and audit["max_contact_use"] == 1
        and audit["incidence_rank"] == 64
        and not audit["missing_contacts"]
    )
    if not required:
        raise RuntimeError(f"{animal}: montage audit failed: {audit}")
    return frame, audit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map-zip", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    frames, audits = [], []
    for animal in ("Kin2", "Su"):
        frame, audit = build_one(args.map_zip, animal)
        frame.to_csv(args.out_dir / f"{animal.lower()}_official_map_local_64pair.csv", index=False)
        frames.append(frame)
        audits.append(audit)
    pd.concat(frames, ignore_index=True).to_csv(args.out_dir / "corrected_local_montages.csv", index=False)
    (args.out_dir / "corrected_montage_audit.json").write_text(json.dumps(audits, indent=2), encoding="utf-8")
    print(json.dumps(audits, indent=2))


if __name__ == "__main__":
    main()
