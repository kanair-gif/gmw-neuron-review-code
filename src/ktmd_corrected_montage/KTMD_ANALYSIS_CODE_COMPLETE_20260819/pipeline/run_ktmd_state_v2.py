#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import linalg, signal
from scipy.io import loadmat
from sklearn.cluster import SpectralClustering

sys.path.insert(0, str(Path(__file__).parent))
from fast_wmi import FastBoundaryMediator, effective_rank

FS = 1000.0
TARGET_FS = 200.0
BLOCK_DURATION_S = 80.0
N_BLOCKS = 6
PAD_S = 5.0
PREDICTION_LAG_SAMPLES = 5  # 25 ms at 200 Hz
HORIZON = 4
QSHIFT = 1
RIDGE_GRID = np.array([0.001, 0.003, 0.01, 0.03, 0.1, 0.3], dtype=float)
STABILITY_RADIUS = 0.98

STATE_KEY_MAP = {
    "EO": "eyes_open",
    "EC": "eyes_closed",
    "AN": "deep_anesthesia",
    "REC": "recovery_eyes_closed",
    "REO": "recovery_eyes_open",
}
GUARD_S = {
    "EO": 30.0,
    "EC": 30.0,
    "AN": 60.0,
    "REC": 30.0,
    "REO": 30.0,
}


def find_data_root(root: Path) -> Path:
    if any((root / f"Session{i}").exists() for i in range(1, 6)):
        return root
    candidates = [p for p in root.iterdir() if p.is_dir() and any((p / f"Session{i}").exists() for i in range(1, 6))]
    if len(candidates) != 1:
        raise RuntimeError(f"Could not identify one dataset root under {root}; candidates={candidates}")
    return candidates[0]


def load_conditions(path: Path, animal: str, date: str) -> dict:
    entries = json.loads(path.read_text(encoding="utf-8"))
    for entry in entries:
        if entry["animal"].lower() == animal.lower() and str(entry["date"]) == str(date):
            return entry
    raise KeyError((animal, date))


def make_evenly_spaced_blocks(lo: float, hi: float, state: str, session: int) -> list[dict]:
    guard = GUARD_S[state]
    usable_lo = float(lo) + guard
    usable_hi = float(hi) - guard
    available = usable_hi - usable_lo
    required = N_BLOCKS * BLOCK_DURATION_S
    if available + 1e-8 < required:
        raise ValueError(
            f"Not enough data for {state} Session{session}: available={available:.3f}s, required={required:.3f}s"
        )
    final_start = usable_hi - BLOCK_DURATION_S
    starts = np.linspace(usable_lo, final_start, N_BLOCKS)
    # Non-overlap should hold by construction because available >= n*duration.
    if np.min(np.diff(starts)) + 1e-8 < BLOCK_DURATION_S:
        raise RuntimeError((state, session, starts, available))
    return [
        {
            "state": STATE_KEY_MAP[state],
            "state_code": state,
            "session": int(session),
            "block": int(i + 1),
            "start_s": float(start),
            "end_s": float(start + BLOCK_DURATION_S),
            "guard_s": guard,
        }
        for i, start in enumerate(starts)
    ]


def build_block_plan(condition_entry: dict) -> pd.DataFrame:
    rows: list[dict] = []
    for session_str, spec in condition_entry["sessions"].items():
        session = int(session_str)
        for code in STATE_KEY_MAP:
            if code in spec:
                lo, hi = spec[code]
                rows.extend(make_evenly_spaced_blocks(lo, hi, code, session))
    plan = pd.DataFrame(rows)
    required_states = {"eyes_open", "eyes_closed", "deep_anesthesia"}
    missing = required_states - set(plan.state)
    if missing:
        raise ValueError(f"Missing required states: {missing}")
    return plan.sort_values(["session", "start_s", "state"]).reset_index(drop=True)


def build_pairs(animal: str, c2_pairs_csv: Path) -> pd.DataFrame:
    animal_lower = animal.lower()
    if animal_lower in {"george", "chibi", "c2"}:
        df = pd.read_csv(c2_pairs_csv)
        out = df[["ch1", "ch2", "bipolar_id"]].copy()
        out["montage_source"] = "C2/George/Chibi homologous local-neighbour topology"
        if "region" in df:
            out["region"] = df["region"].astype(str)
        else:
            out["region"] = "unknown"
        return out.reset_index(drop=True)
    # Kin2 and Su maps use a regular numbering in adjacent physical pairs.
    pairs = [(i, i + 1) for i in range(1, 129, 2)]
    return pd.DataFrame(
        {
            "ch1": [a for a, _ in pairs],
            "ch2": [b for _, b in pairs],
            "bipolar_id": [f"BP{a:03d}-{b:03d}" for a, b in pairs],
            "montage_source": "published-map adjacent odd-even local pairs",
            "region": "unknown",
        }
    )


def load_channel(session_dir: Path, channel: int) -> np.ndarray:
    path = session_dir / f"ECoG_ch{channel}.mat"
    key = f"ECoGData_ch{channel}"
    data = loadmat(path, variable_names=[key])
    if key not in data:
        keys = [k for k in data if not k.startswith("__")]
        if len(keys) != 1:
            raise KeyError((path, key, keys))
        key = keys[0]
    return np.asarray(data[key]).ravel().astype(np.float32, copy=False)


def preprocess_segment(raw_difference: np.ndarray, start_s: float, end_s: float) -> np.ndarray:
    raw_start = max(0, int(round((start_s - PAD_S) * FS)))
    raw_end = min(raw_difference.size, int(round((end_s + PAD_S) * FS)))
    segment = raw_difference[raw_start:raw_end].astype(np.float32, copy=True)
    expected_raw = int(round((BLOCK_DURATION_S + 2 * PAD_S) * FS))
    if segment.size < expected_raw - 2:
        raise RuntimeError((segment.size, expected_raw, start_s, end_s, raw_difference.size))
    segment -= np.mean(segment, dtype=np.float64)
    segment = signal.resample_poly(segment, 1, 5, padtype="line").astype(np.float32, copy=False)
    segment = signal.detrend(segment, type="linear").astype(np.float32, copy=False)
    sos = signal.butter(4, [0.5, 90.0], btype="bandpass", fs=TARGET_FS, output="sos")
    b_notch, a_notch = signal.iirnotch(50.0, Q=30.0, fs=TARGET_FS)
    segment = signal.sosfiltfilt(sos, segment).astype(np.float32, copy=False)
    segment = signal.filtfilt(b_notch, a_notch, segment).astype(np.float32, copy=False)
    trim = int(round(PAD_S * TARGET_FS))
    n_target = int(round(BLOCK_DURATION_S * TARGET_FS))
    segment = segment[trim : trim + n_target]
    if segment.size != n_target:
        raise RuntimeError((segment.size, n_target, start_s, end_s))
    return segment


def preprocess_full(raw_difference: np.ndarray) -> np.ndarray:
    segment = raw_difference.astype(np.float32, copy=True)
    segment -= np.mean(segment, dtype=np.float64)
    segment = signal.resample_poly(segment, 1, 5, padtype="line").astype(np.float32, copy=False)
    segment = signal.detrend(segment, type="linear").astype(np.float32, copy=False)
    sos = signal.butter(4, [0.5, 90.0], btype="bandpass", fs=TARGET_FS, output="sos")
    b_notch, a_notch = signal.iirnotch(50.0, Q=30.0, fs=TARGET_FS)
    segment = signal.sosfiltfilt(sos, segment).astype(np.float32, copy=False)
    segment = signal.filtfilt(b_notch, a_notch, segment).astype(np.float32, copy=False)
    return segment


def build_preprocessed_blocks(data_root: Path, pairs: pd.DataFrame, plan: pd.DataFrame, out_dir: Path, rebuild: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    n_nodes = len(pairs)
    n_time = int(round(BLOCK_DURATION_S * TARGET_FS))
    expected_paths = [out_dir / f"{r.state}_block{int(r.block):02d}.npy" for r in plan.itertuples(index=False)]
    complete_marker = out_dir / "PREPROCESS_COMPLETE.ok"
    progress_path = out_dir / "PREPROCESS_PROGRESS.json"
    if not rebuild and complete_marker.exists() and all(path.exists() for path in expected_paths):
        print("Using cached preprocessed blocks", flush=True)
        return
    complete_marker.unlink(missing_ok=True)
    if rebuild:
        progress_path.unlink(missing_ok=True)
    completed_nodes = 0
    if not rebuild and progress_path.exists():
        try:
            completed_nodes = int(json.loads(progress_path.read_text())["completed_nodes"])
        except Exception:
            completed_nodes = 0
    resume_ok = completed_nodes > 0 and all(path.exists() for path in expected_paths)

    memmaps: dict[tuple[str, int], np.memmap] = {}
    for row in plan.itertuples(index=False):
        path = out_dir / f"{row.state}_block{int(row.block):02d}.npy"
        mode = "r+" if resume_ok else "w+"
        memmaps[(row.state, int(row.block))] = np.lib.format.open_memmap(
            path, mode=mode, dtype=np.float32, shape=(n_nodes, n_time)
        )
    if resume_ok:
        print(f"Resuming preprocessing after {completed_nodes}/{n_nodes} nodes", flush=True)

    rows_by_session: dict[int, list] = {}
    for row in plan.itertuples(index=False):
        rows_by_session.setdefault(int(row.session), []).append(row)

    for node_index, pair in enumerate(pairs.itertuples(index=False)):
        if node_index < completed_nodes:
            continue
        for session, session_rows in rows_by_session.items():
            session_dir = data_root / f"Session{session}"
            channel_a = load_channel(session_dir, int(pair.ch1))
            channel_b = load_channel(session_dir, int(pair.ch2))
            if channel_a.size != channel_b.size:
                raise RuntimeError((pair.ch1, pair.ch2, channel_a.size, channel_b.size))
            filtered = preprocess_full(channel_a - channel_b)
            del channel_a, channel_b
            for row in session_rows:
                lo = int(round(float(row.start_s) * TARGET_FS))
                hi = lo + n_time
                block = filtered[lo:hi]
                if block.size != n_time:
                    raise RuntimeError((row.state, row.block, lo, hi, filtered.size))
                memmaps[(row.state, int(row.block))][node_index] = block
            del filtered
        # Flush and checkpoint every node so a Colab/container interruption is resumable.
        for memmap in memmaps.values():
            memmap.flush()
        progress_path.write_text(json.dumps({"completed_nodes": node_index + 1}), encoding="utf-8")
        if (node_index + 1) % 4 == 0 or node_index + 1 == n_nodes:
            print(f"Preprocessed bipolar node {node_index + 1}/{n_nodes}", flush=True)

    for memmap in memmaps.values():
        memmap.flush()
    complete_marker.write_text("complete\n", encoding="utf-8")
    progress_path.unlink(missing_ok=True)


def load_block(preprocessed_dir: Path, state: str, block: int) -> np.ndarray:
    return np.asarray(
        np.load(preprocessed_dir / f"{state}_block{block:02d}.npy", mmap_mode="r"), dtype=np.float64
    )


def awake_scale(preprocessed_dir: Path, plan: pd.DataFrame, n_nodes: int) -> np.ndarray:
    sum_squares = np.zeros(n_nodes, dtype=np.float64)
    count = 0
    for row in plan[plan.state.isin(["eyes_open", "eyes_closed"])].itertuples(index=False):
        block = load_block(preprocessed_dir, row.state, int(row.block))
        block -= block.mean(axis=1, keepdims=True)
        sum_squares += np.sum(block * block, axis=1)
        count += block.shape[1]
    scale = np.sqrt(sum_squares / count)
    floor = np.median(scale[np.isfinite(scale) & (scale > 0)]) * 1e-6
    return np.maximum(scale, floor)


def block_sufficient_stats(block: np.ndarray, scale: np.ndarray) -> dict:
    z = block - block.mean(axis=1, keepdims=True)
    z = z / scale[:, None]
    x = z[:, :-PREDICTION_LAG_SAMPLES]
    y = z[:, PREDICTION_LAG_SAMPLES:]
    n = x.shape[1]
    return {
        "xx": x @ x.T / n,
        "yx": y @ x.T / n,
        "yy": y @ y.T / n,
        "n": int(n),
    }


def combine_stats(stats: Iterable[dict]) -> dict:
    stats = list(stats)
    total_n = sum(item["n"] for item in stats)
    return {
        key: sum(item[key] * item["n"] for item in stats) / total_n
        for key in ("xx", "yx", "yy")
    } | {"n": int(total_n)}


def fit_operator(stats: dict, ridge_lambda: float) -> tuple[np.ndarray, float, float]:
    n_nodes = stats["xx"].shape[0]
    operator = linalg.solve(
        stats["xx"] + ridge_lambda * np.eye(n_nodes),
        stats["yx"].T,
        assume_a="pos",
        check_finite=False,
    ).T
    raw_radius = float(np.max(np.abs(np.linalg.eigvals(operator))))
    if raw_radius > STABILITY_RADIUS:
        operator *= STABILITY_RADIUS / raw_radius
    error = float(
        np.trace(stats["yy"])
        - 2 * np.sum(operator * stats["yx"])
        + np.sum((operator @ stats["xx"]) * operator)
    )
    r2 = 1.0 - error / float(np.trace(stats["yy"]))
    return operator, raw_radius, r2


def choose_ridge(stats_list: list[dict]) -> tuple[float, pd.DataFrame]:
    records = []
    for ridge_lambda in RIDGE_GRID:
        fold_scores = []
        for heldout_index, heldout in enumerate(stats_list):
            training = combine_stats(
                stat for index, stat in enumerate(stats_list) if index != heldout_index
            )
            operator, _, _ = fit_operator(training, float(ridge_lambda))
            error = float(
                np.trace(heldout["yy"])
                - 2 * np.sum(operator * heldout["yx"])
                + np.sum((operator @ heldout["xx"]) * operator)
            )
            fold_scores.append(1.0 - error / float(np.trace(heldout["yy"])))
        records.append(
            {
                "lambda": float(ridge_lambda),
                "mean_cv_r2": float(np.mean(fold_scores)),
                "min_cv_r2": float(np.min(fold_scores)),
                "sd_cv_r2": float(np.std(fold_scores)),
            }
        )
    table = pd.DataFrame(records)
    best = float(table.sort_values(["mean_cv_r2", "lambda"], ascending=[False, True]).iloc[0]["lambda"])
    return best, table


def module_membership(operator: np.ndarray, n_clusters: int = 8) -> tuple[np.ndarray, np.ndarray]:
    similarity = np.abs(operator) + np.abs(operator.T)
    np.fill_diagonal(similarity, 0)
    similarity += 1e-12
    labels = SpectralClustering(
        n_clusters=min(n_clusters, operator.shape[0] - 1),
        affinity="precomputed",
        assign_labels="cluster_qr",
        random_state=0,
    ).fit_predict(similarity)
    membership = np.zeros((labels.max() + 1, operator.shape[0]), dtype=float)
    membership[labels, np.arange(operator.shape[0])] = 1.0
    return membership, labels


def psd_sqrt(matrix: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh((matrix + matrix.T) / 2)
    return (vectors * np.sqrt(np.clip(values, 0, None))) @ vectors.T


def signature(operator: np.ndarray, membership: np.ndarray, candidate: tuple[int, ...]) -> dict:
    selected = np.asarray(sorted(candidate), dtype=int)
    rest = np.setdiff1d(np.arange(operator.shape[0]), selected)
    ass = operator[np.ix_(selected, selected)]
    boundary_in = operator[np.ix_(selected, rest)]
    boundary_out = operator[np.ix_(rest, selected)]
    wc = np.zeros((len(selected), len(selected)))
    wo = np.zeros_like(wc)
    power = np.eye(len(selected))
    for _ in range(HORIZON):
        wc += power @ boundary_in @ boundary_in.T @ power.T
        wo += power.T @ boundary_out.T @ boundary_out @ power
        power = ass @ power
    shifted = np.linalg.matrix_power(ass, QSHIFT)
    shifted_wo = shifted.T @ wo @ shifted
    root_wo = psd_sqrt(shifted_wo)
    kernel = root_wo @ wc @ root_wo
    singular_values = np.sqrt(
        np.clip(np.linalg.eigvalsh((kernel + kernel.T) / 2), 0, None)
    )[::-1]
    singular_values = singular_values[singular_values > 1e-14]
    q_strength = float(singular_values.sum())
    lambda_c = np.clip(np.linalg.eigvalsh((wc + wc.T) / 2), 0, None)[::-1]
    lambda_o = np.clip(np.linalg.eigvalsh((shifted_wo + shifted_wo.T) / 2), 0, None)[::-1]
    c_spec = float(np.sum(np.sqrt(lambda_c * lambda_o)))
    mediator = FastBoundaryMediator(operator, membership, HORIZON, QSHIFT)
    metrics = mediator.metrics(tuple(selected), full_pair=True)
    deff = effective_rank(singular_values)
    gpair = float(metrics.pair_globality or 0.0)
    return {
        "Q": q_strength,
        "Cspec": c_spec,
        "Aspec": q_strength / c_spec if c_spec > 0 else 0.0,
        "Deff": deff,
        "Deff_frac": deff / len(selected),
        "Gpair": gpair,
        "WMI": float(metrics.wmi or 0.0),
        "Oorg": deff / len(selected) * gpair,
        "top_share": float(singular_values[0] / q_strength) if q_strength > 0 else 0.0,
        "singular_values": ";".join(f"{value:.12g}" for value in singular_values),
    }


def beam_search(operator: np.ndarray, membership: np.ndarray, sizes=(3, 4, 5), width: int = 120):
    mediator = FastBoundaryMediator(operator, membership, HORIZON, QSHIFT)
    n_nodes = operator.shape[0]
    beam = [
        ((i, j), mediator.direct_score((i, j)))
        for i in range(n_nodes)
        for j in range(i + 1, n_nodes)
    ]
    beam = sorted(beam, key=lambda item: item[1], reverse=True)[:width]
    results = {}
    for depth in range(3, max(sizes) + 1):
        proposals = {}
        for candidate, _ in beam:
            for node in range(n_nodes):
                if node in candidate:
                    continue
                expanded = tuple(sorted(candidate + (node,)))
                if expanded not in proposals:
                    proposals[expanded] = mediator.direct_score(expanded)
        beam = sorted(proposals.items(), key=lambda item: item[1], reverse=True)[:width]
        print(f"Search depth {depth}: {len(proposals)} proposals", flush=True)
        if depth in sizes:
            full = [(candidate, mediator.metrics(candidate, full_pair=True)) for candidate, _ in beam]
            full.sort(key=lambda item: item[1].wmi if item[1].wmi is not None else -np.inf, reverse=True)
            results[depth] = full[0]
    return results


def save_stats_npz(path: Path, plan: pd.DataFrame, stats: dict[tuple[str, int], dict]) -> None:
    payload = {}
    for row in plan.itertuples(index=False):
        key = (row.state, int(row.block))
        safe = f"{row.state}__{int(row.block):02d}"
        for component in ("xx", "yx", "yy"):
            payload[f"{safe}__{component}"] = stats[key][component]
        payload[f"{safe}__n"] = np.array([stats[key]["n"]], dtype=np.int64)
    np.savez_compressed(path, **payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--animal", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--conditions", type=Path, required=True)
    parser.add_argument("--c2-pairs", type=Path, required=False)
    parser.add_argument("--pairs-csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    started = time.time()
    args.out.mkdir(parents=True, exist_ok=True)
    data_root = find_data_root(args.root)
    condition_entry = load_conditions(args.conditions, args.animal, args.date)
    plan = build_block_plan(condition_entry)
    plan.to_csv(args.out / "block_plan.csv", index=False)
    pairs = pd.read_csv(args.pairs_csv).copy()
    if 'bipolar_id' not in pairs.columns:
        if 'pair_id' in pairs.columns:
            pairs['bipolar_id'] = pairs['pair_id'].astype(str)
        else:
            pairs['bipolar_id'] = [f'LBP{i+1:03d}' for i in range(len(pairs))]
    required_pair_cols = {'ch1','ch2','bipolar_id'}
    if not required_pair_cols.issubset(pairs.columns):
        raise ValueError(f'Missing pair columns: {required_pair_cols - set(pairs.columns)}')
    pairs = pairs.reset_index(drop=True)
    pairs.to_csv(args.out / "bipolar_pairs.csv", index=False)

    preprocessed_dir = args.out / "preprocessed"
    build_preprocessed_blocks(data_root, pairs, plan, preprocessed_dir, args.rebuild)

    scale = awake_scale(preprocessed_dir, plan, len(pairs))
    np.save(args.out / "awake_scale.npy", scale)
    scale_table = pairs[["bipolar_id", "ch1", "ch2"]].copy()
    scale_table["awake_sd"] = scale
    scale_table["sd_over_median"] = scale / np.median(scale)
    scale_table.to_csv(args.out / "awake_scale_qc.csv", index=False)

    stats: dict[tuple[str, int], dict] = {}
    for row in plan.itertuples(index=False):
        stats[(row.state, int(row.block))] = block_sufficient_stats(
            load_block(preprocessed_dir, row.state, int(row.block)), scale
        )
    save_stats_npz(args.out / "block_sufficient_stats.npz", plan, stats)

    awake_keys = sorted(key for key in stats if key[0] in {"eyes_open", "eyes_closed"})
    ridge_lambda, ridge_table = choose_ridge([stats[key] for key in awake_keys])
    ridge_table.to_csv(args.out / "ridge_cv.csv", index=False)
    print(f"Selected ridge lambda: {ridge_lambda}", flush=True)

    def model(keys: list[tuple[str, int]]):
        return fit_operator(combine_stats(stats[key] for key in keys), ridge_lambda)

    state_keys = {
        state: sorted(key for key in stats if key[0] == state)
        for state in plan.state.unique()
    }
    models = {}
    fit_records = []
    for state, keys in state_keys.items():
        operator, raw_radius, r2 = model(keys)
        models[state] = operator
        np.save(args.out / f"A_{state}.npy", operator)
        fit_records.append({"model": state, "r2": r2, "raw_spectral_radius": raw_radius, "n_blocks": len(keys)})
    full_awake_operator, full_awake_radius, full_awake_r2 = model(awake_keys)
    models["full_awake"] = full_awake_operator
    np.save(args.out / "A_full_awake.npy", full_awake_operator)
    fit_records.append({"model": "full_awake", "r2": full_awake_r2, "raw_spectral_radius": full_awake_radius, "n_blocks": len(awake_keys)})
    pd.DataFrame(fit_records).to_csv(args.out / "model_fit.csv", index=False)

    full_membership, full_labels = module_membership(full_awake_operator)
    np.save(args.out / "full_awake_module_labels.npy", full_labels)

    signature_records = []
    candidate_records = []
    full_results = beam_search(full_awake_operator, full_membership, sizes=(3, 4, 5))
    for k in (3, 4, 5):
        candidate, _ = full_results[k]
        candidate_records.append(
            {
                "fold": "full_awake",
                "k": k,
                "candidate": ";".join(map(str, candidate)),
                "nodes": ";".join(pairs.iloc[node].bipolar_id for node in candidate),
            }
        )
        for evaluation, operator in models.items():
            signature_records.append(
                {
                    "fold": "full_awake",
                    "k": k,
                    "evaluation": evaluation,
                    "candidate": ";".join(map(str, candidate)),
                    **signature(operator, full_membership, candidate),
                }
            )

    eo_keys = state_keys["eyes_open"]
    ec_keys = state_keys["eyes_closed"]
    # Temporal cross-fit within both eye conditions. Odd/even refers to block
    # number within each state, not to the interleaved sorted key list. This
    # makes the temporal folds distinct from EO->EC and EC->EO.
    odd_keys = sorted(key for key in awake_keys if int(key[1]) % 2 == 1)
    even_keys = sorted(key for key in awake_keys if int(key[1]) % 2 == 0)
    folds = [
        ("EO_to_EC", eo_keys, ec_keys),
        ("EC_to_EO", ec_keys, eo_keys),
        ("odd_to_even", odd_keys, even_keys),
        ("even_to_odd", even_keys, odd_keys),
    ]
    for fold_name, training_keys, heldout_keys in folds:
        training_operator, _, _ = model(training_keys)
        heldout_operator, _, _ = model(heldout_keys)
        membership, _ = module_membership(training_operator)
        fold_results = beam_search(training_operator, membership, sizes=(3, 4, 5))
        for k in (3, 4, 5):
            candidate, _ = fold_results[k]
            candidate_records.append(
                {
                    "fold": fold_name,
                    "k": k,
                    "candidate": ";".join(map(str, candidate)),
                    "nodes": ";".join(pairs.iloc[node].bipolar_id for node in candidate),
                }
            )
            evaluations = {
                "train_awake": training_operator,
                "heldout_awake": heldout_operator,
                "deep_anesthesia": models["deep_anesthesia"],
            }
            if "recovery_eyes_closed" in models:
                evaluations["recovery_eyes_closed"] = models["recovery_eyes_closed"]
            if "recovery_eyes_open" in models:
                evaluations["recovery_eyes_open"] = models["recovery_eyes_open"]
            for evaluation, operator in evaluations.items():
                signature_records.append(
                    {
                        "fold": fold_name,
                        "k": k,
                        "evaluation": evaluation,
                        "candidate": ";".join(map(str, candidate)),
                        **signature(operator, membership, candidate),
                    }
                )

    signature_table = pd.DataFrame(signature_records)
    candidate_table = pd.DataFrame(candidate_records)
    signature_table.to_csv(args.out / "candidate_signatures.csv", index=False)
    candidate_table.to_csv(args.out / "candidate_sets.csv", index=False)

    ratio_records = []
    for (fold_name, k), group in signature_table[signature_table.fold != "full_awake"].groupby(["fold", "k"]):
        indexed = group.set_index("evaluation")
        record = {"fold": fold_name, "k": int(k)}
        for metric in ("Q", "Cspec", "Aspec", "Deff_frac", "Gpair", "Oorg", "top_share", "WMI"):
            denominator = float(indexed.loc["heldout_awake", metric])
            for evaluation in ("deep_anesthesia", "recovery_eyes_closed", "recovery_eyes_open"):
                if evaluation in indexed.index:
                    record[f"{metric}_{evaluation}_over_heldout"] = (
                        float(indexed.loc[evaluation, metric]) / denominator if denominator != 0 else np.nan
                    )
        ratio_records.append(record)
    pd.DataFrame(ratio_records).to_csv(args.out / "crossfit_ratios.csv", index=False)

    summary = {
        "animal": args.animal,
        "date": args.date,
        "data_root": str(data_root),
        "n_pairs": len(pairs),
        "states": plan.groupby("state").size().to_dict(),
        "block_duration_s": BLOCK_DURATION_S,
        "n_blocks_per_state": N_BLOCKS,
        "ridge_lambda": ridge_lambda,
        "full_awake_r2": full_awake_r2,
        "deep_anesthesia_r2": next(record["r2"] for record in fit_records if record["model"] == "deep_anesthesia"),
        "elapsed_minutes": (time.time() - started) / 60.0,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
