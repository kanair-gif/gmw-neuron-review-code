#!/usr/bin/env python3
"""Synthetic test of a control-theoretic Global Workspace definition.

The experiment embeds five motifs in a 64-node directed linear network:
1. a true internally integrated bidirectional workspace,
2. an actuator-only cluster,
3. an observer-only cluster,
4. a dense but dynamically low-rank degree hub,
5. a split input/output decoy assembled from actuator and observer nodes.

It compares the original external controllability-observability score with an
internal mediation score, performs null tests, robustness tests, beam search,
and (optionally) exhaustive search over every four-node cluster.

Usage:
    python workspace_core_experiment.py --output-dir results
    python workspace_core_experiment.py --output-dir results --full

The --full flag adds 12 repeated beam searches and exhaustive enumeration of
all C(64,4)=635,376 four-node clusters.
"""
from __future__ import annotations

import argparse
import heapq
import itertools
import json
import math
import multiprocessing as mp
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def rand_sparse(rng: np.random.Generator, shape: Tuple[int, int], density: float, scale: float) -> np.ndarray:
    mask = rng.random(shape) < density
    return mask * rng.normal(0.0, scale, shape)


def make_network(seed: int = 0, background: float = 1.0, core_strength: float = 1.0):
    rng = np.random.default_rng(seed)
    n = 64
    modules = [np.arange(i * 12, (i + 1) * 12) for i in range(4)]
    workspace = np.arange(48, 52)
    actuator = np.arange(52, 56)
    observer = np.arange(56, 60)
    degree_hub = np.arange(60, 64)
    A = np.zeros((n, n), dtype=float)
    np.fill_diagonal(A, 0.48)

    # Four specialist modules with recurrent local dynamics.
    for module in modules:
        block = rand_sparse(rng, (12, 12), 0.28, 0.12 * background)
        np.fill_diagonal(block, 0.0)
        A[np.ix_(module, module)] += block

    # Weak background coupling between modules.
    for i, target in enumerate(modules):
        for j, source in enumerate(modules):
            if i != j:
                A[np.ix_(target, source)] += rand_sparse(rng, (12, 12), 0.035, 0.035 * background)

    # True workspace: broad, heterogeneous, bidirectional access plus internal mixing.
    for w in workspace:
        for module in modules:
            mask_out = rng.random(12) < 0.72
            mask_in = rng.random(12) < 0.72
            vals_out = rng.normal(0.0, 0.22 * core_strength, 12)
            vals_in = rng.normal(0.0, 0.22 * core_strength, 12)
            A[module, w] += mask_out * vals_out       # workspace -> module
            A[w, module] += mask_in * vals_in         # module -> workspace
    A[np.ix_(workspace, workspace)] += rand_sparse(rng, (4, 4), 0.75, 0.16 * core_strength)

    # Actuator-only: strong diverse outgoing access, almost no incoming access.
    for node in actuator:
        for module in modules:
            A[module, node] += (rng.random(12) < 0.78) * rng.normal(0.0, 0.25 * core_strength, 12)
            A[node, module] += (rng.random(12) < 0.08) * rng.normal(0.0, 0.018 * background, 12)
    A[np.ix_(actuator, actuator)] += rand_sparse(rng, (4, 4), 0.60, 0.10)

    # Observer-only: strong diverse incoming access, almost no outgoing access.
    for node in observer:
        for module in modules:
            A[node, module] += (rng.random(12) < 0.78) * rng.normal(0.0, 0.25 * core_strength, 12)
            A[module, node] += (rng.random(12) < 0.08) * rng.normal(0.0, 0.018 * background, 12)
    A[np.ix_(observer, observer)] += rand_sparse(rng, (4, 4), 0.60, 0.10)

    # Dense degree hub, but all four nodes use nearly the same input/output pattern.
    all_specialists = np.concatenate(modules)
    v_out = rng.normal(0.0, 0.14 * core_strength, len(all_specialists))
    v_in = rng.normal(0.0, 0.14 * core_strength, len(all_specialists))
    alpha_out = np.array([1.00, 0.98, 1.02, 1.01])
    alpha_in = np.array([1.00, 1.01, 0.99, 1.02])
    A[np.ix_(all_specialists, degree_hub)] += np.outer(v_out, alpha_out)
    A[np.ix_(degree_hub, all_specialists)] += np.outer(alpha_in, v_in)
    sync = 0.10 * np.ones((4, 4))
    np.fill_diagonal(sync, 0.0)
    A[np.ix_(degree_hub, degree_hub)] += sync

    # Small incidental links among special groups.
    special = np.concatenate([workspace, actuator, observer, degree_hub])
    A[np.ix_(special, special)] += rand_sparse(rng, (16, 16), 0.08, 0.015)

    # Stabilize the discrete-time system.
    spectral_radius = float(np.max(np.abs(np.linalg.eigvals(A))))
    A *= 0.92 / spectral_radius

    groups = {
        "Workspace": workspace,
        "Actuator-only": actuator,
        "Observer-only": observer,
        "Degree hub": degree_hub,
    }
    return A, modules, groups


def joint_spectrum(Wc: np.ndarray, Wo: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh((Wo + Wo.T) / 2.0)
    vals = np.clip(vals, 0.0, None)
    sqrt_wo = (vecs * np.sqrt(vals)) @ vecs.T
    K = sqrt_wo @ ((Wc + Wc.T) / 2.0) @ sqrt_wo
    eigvals = np.linalg.eigvalsh((K + K.T) / 2.0)
    return np.sqrt(np.clip(eigvals, 0.0, None))[::-1]


def effective_rank(values: np.ndarray, eps: float = 1e-15) -> float:
    values = np.asarray(values, dtype=float)
    values = values[values > eps]
    if values.size == 0:
        return 0.0
    p = values / values.sum()
    return float(np.exp(-np.sum(p * np.log(p))))


def entropy_globality(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    if values.sum() <= 0:
        return 0.0
    p = values / values.sum()
    p = p[p > 0]
    return float(np.exp(-np.sum(p * np.log(p))) / len(values))


def gramian_node_contributions(A: np.ndarray, horizon: int = 10):
    n = A.shape[0]
    Wc_node = np.zeros((n, n, n))
    Wo_node = np.zeros((n, n, n))
    A_power = np.eye(n)
    for _ in range(horizon):
        columns = A_power.T
        rows = A_power
        Wc_node += np.einsum("ik,il->ikl", columns, columns)
        Wo_node += np.einsum("ik,il->ikl", rows, rows)
        A_power = A @ A_power
    return Wc_node, Wo_node


def external_access_metrics(A, modules, Wc_node, Wo_node, S: Sequence[int]):
    n = A.shape[0]
    S = np.array(sorted(set(int(x) for x in S)), dtype=int)
    S_set = set(S.tolist())
    R = np.array([i for i in range(n) if i not in S_set], dtype=int)
    Wc = Wc_node[S].sum(axis=0)
    Wo = Wo_node[S].sum(axis=0)
    Wc_R = Wc[np.ix_(R, R)]
    Wo_R = Wo[np.ix_(R, R)]
    spectrum = joint_spectrum(Wc_R, Wo_R)
    dimension = effective_rank(spectrum)

    module_strengths = []
    for module in modules:
        idx = np.array([i for i in module if i in S_set or i in set(R.tolist())], dtype=int)
        local_spectrum = joint_spectrum(Wc[np.ix_(idx, idx)], Wo[np.ix_(idx, idx)])
        module_strengths.append(float(local_spectrum.sum()))
    globality = entropy_globality(np.asarray(module_strengths))
    score = float(spectrum.sum() * (dimension / len(S)) * globality)
    return {
        "write": float(np.trace(Wc_R)),
        "read": float(np.trace(Wo_R)),
        "joint_strength": float(spectrum.sum()),
        "effective_rank": dimension,
        "globality": globality,
        "score": score,
        "spectrum": spectrum,
    }


def mediation_metrics(A: np.ndarray, modules, S: Sequence[int], horizon: int = 10):
    n = A.shape[0]
    S = np.array(sorted(set(int(x) for x in S)), dtype=int)
    S_set = set(S.tolist())
    R = np.array([i for i in range(n) if i not in S_set], dtype=int)
    A_SS = A[np.ix_(S, S)]
    B_in = A[np.ix_(S, R)]       # rest -> S
    C_out = A[np.ix_(R, S)]      # S -> rest

    Wc = np.zeros((len(S), len(S)))
    Wo = np.zeros((len(S), len(S)))
    A_power = np.eye(len(S))
    for _ in range(horizon):
        Wc += A_power @ B_in @ B_in.T @ A_power.T
        Wo += A_power.T @ C_out.T @ C_out @ A_power
        A_power = A_SS @ A_power

    spectrum = joint_spectrum(Wc, Wo)
    strength = float(spectrum.sum())
    dimension = effective_rank(spectrum)
    read_by_module = np.array([np.linalg.norm(A[np.ix_(S, module)], "fro") ** 2 for module in modules])
    write_by_module = np.array([np.linalg.norm(A[np.ix_(module, S)], "fro") ** 2 for module in modules])
    g_in = entropy_globality(read_by_module)
    g_out = entropy_globality(write_by_module)
    globality = float(np.sqrt(g_in * g_out))
    score = float(strength * (dimension / len(S)) * globality)
    return {
        "strength": strength,
        "effective_rank": dimension,
        "globality": globality,
        "globality_in": g_in,
        "globality_out": g_out,
        "score": score,
        "spectrum": spectrum,
    }


@dataclass
class FastWorkspaceScorer:
    A: np.ndarray
    modules: List[np.ndarray]
    horizon: int = 10

    def __post_init__(self):
        self.row_gram = self.A @ self.A.T
        self.col_gram = self.A.T @ self.A
        self.read_module = np.stack([(self.A[:, m] ** 2).sum(axis=1) for m in self.modules], axis=1)
        self.write_module = np.stack([(self.A[m, :] ** 2).sum(axis=0) for m in self.modules], axis=1)

    def score(self, S: Sequence[int]) -> float:
        S = np.asarray(S, dtype=int)
        k = len(S)
        A_SS = self.A[np.ix_(S, S)]
        BBT = self.row_gram[np.ix_(S, S)] - A_SS @ A_SS.T
        CTC = self.col_gram[np.ix_(S, S)] - A_SS.T @ A_SS
        Wc = np.zeros((k, k))
        Wo = np.zeros((k, k))
        A_power = np.eye(k)
        for _ in range(self.horizon):
            Wc += A_power @ BBT @ A_power.T
            Wo += A_power.T @ CTC @ A_power
            A_power = A_SS @ A_power
        spectrum = joint_spectrum(Wc, Wo)
        strength = float(spectrum.sum())
        dimension = effective_rank(spectrum)
        read_by_module = self.read_module[S].sum(axis=0)
        write_by_module = self.write_module[S].sum(axis=0)
        globality = math.sqrt(entropy_globality(read_by_module) * entropy_globality(write_by_module))
        return float(strength * (dimension / k) * globality)


def edge_count(A: np.ndarray, S: Sequence[int], threshold: float = 1e-12) -> int:
    S = np.asarray(S, dtype=int)
    R = np.array([i for i in range(A.shape[0]) if i not in set(S.tolist())], dtype=int)
    return int(np.count_nonzero(np.abs(A[np.ix_(R, S)]) > threshold) +
               np.count_nonzero(np.abs(A[np.ix_(S, R)]) > threshold))


def cross_module_communicability(A: np.ndarray, modules, horizon: int = 10) -> float:
    A_power = np.eye(A.shape[0])
    total = 0.0
    for _ in range(horizon):
        A_power = A @ A_power
        for i, target in enumerate(modules):
            for j, source in enumerate(modules):
                if i != j:
                    total += float(np.linalg.norm(A_power[np.ix_(target, source)], "fro") ** 2)
    return total


def beam_search(A: np.ndarray, modules, k: int = 4, width: int = 50, horizon: int = 10):
    scorer = FastWorkspaceScorer(A, modules, horizon)
    beam = [(tuple(), 0.0)]
    for size in range(1, k + 1):
        candidates: Dict[Tuple[int, ...], float] = {}
        for current, _ in beam:
            for node in range(A.shape[0]):
                if node in current:
                    continue
                trial = tuple(sorted(current + (node,)))
                if trial not in candidates:
                    candidates[trial] = scorer.score(trial)
        beam = sorted(candidates.items(), key=lambda item: item[1], reverse=True)[:width]
    return beam


_GLOBAL_SCORER = None
_GLOBAL_TARGET = None


def _exact_init(scorer, target):
    global _GLOBAL_SCORER, _GLOBAL_TARGET
    _GLOBAL_SCORER = scorer
    _GLOBAL_TARGET = target


def _exact_worker(first_node: int):
    count = 0
    above = 0
    top: List[Tuple[float, Tuple[int, ...]]] = []
    for tail in itertools.combinations(range(first_node + 1, 64), 3):
        cluster = (first_node,) + tail
        score = _GLOBAL_SCORER.score(cluster)
        count += 1
        if score > _GLOBAL_TARGET + 1e-12:
            above += 1
        item = (score, cluster)
        if len(top) < 20:
            heapq.heappush(top, item)
        elif score > top[0][0]:
            heapq.heapreplace(top, item)
    return count, above, top


def exhaustive_four_node_search(A, modules, target_cluster=(48, 49, 50, 51), processes: int = 4):
    scorer = FastWorkspaceScorer(A, modules, horizon=10)
    target_score = scorer.score(target_cluster)
    first_nodes = list(range(61))
    process_count = max(1, min(processes, os.cpu_count() or 1))
    if process_count == 1:
        _exact_init(scorer, target_score)
        results = [_exact_worker(i) for i in first_nodes]
    else:
        try:
            context = mp.get_context("fork")
        except ValueError:
            context = mp.get_context()
        with context.Pool(process_count, initializer=_exact_init, initargs=(scorer, target_score)) as pool:
            results = pool.map(_exact_worker, first_nodes)
    total = sum(item[0] for item in results)
    above = sum(item[1] for item in results)
    top = []
    for _, _, local_top in results:
        top.extend(local_top)
    top = sorted(top, reverse=True)[:20]
    return {
        "total_clusters": total,
        "target_cluster": list(target_cluster),
        "target_score": target_score,
        "clusters_above_target": above,
        "target_rank": above + 1,
        "best_cluster": list(top[0][1]),
        "best_score": top[0][0],
        "top20": [{"cluster": list(cluster), "score": score} for score, cluster in top],
    }


def save_figures(output_dir: Path, A, modules, candidates, candidate_df, random_scores, sweep_df, robustness_df):
    boundaries = [12, 24, 36, 48, 52, 56, 60]

    fig, ax = plt.subplots(figsize=(8, 7))
    image = ax.imshow(np.abs(A), aspect="auto")
    for boundary in boundaries:
        ax.axhline(boundary - 0.5, linestyle="--", linewidth=0.8)
        ax.axvline(boundary - 0.5, linestyle="--", linewidth=0.8)
    ax.set_xlabel("Source node")
    ax.set_ylabel("Target node")
    ax.set_title("Absolute coupling matrix |A|")
    fig.colorbar(image, ax=ax, label="Absolute coupling")
    fig.tight_layout()
    fig.savefig(output_dir / "fig1_adjacency_matrix.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(candidate_df))
    width = 0.38
    ax.bar(x - width / 2, candidate_df["External access score"], width, label="External access")
    ax.bar(x + width / 2, candidate_df["Workspace mediation score"], width, label="Internal mediation")
    ax.set_xticks(x)
    ax.set_xticklabels(candidate_df.index, rotation=25, ha="right")
    ax.set_ylabel("Score")
    ax.set_title("The external score is fooled by a split input/output decoy")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "fig2_external_vs_mediation.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for name in ["Workspace", "Degree hub", "Split I/O decoy", "Random peripheral"]:
        spectrum = candidates[name]["mediation"]["spectrum"]
        ax.plot(np.arange(1, len(spectrum) + 1), spectrum, marker="o", label=name)
    ax.set_xlabel("Internal mediation mode")
    ax.set_ylabel("Mediation singular value")
    ax.set_title("Workspace: several strong modes; degree hub: one redundant mode")
    ax.set_xticks([1, 2, 3, 4])
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "fig3_mediation_spectra.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(random_scores, bins=40, alpha=0.8)
    workspace_score = candidate_df.loc["Workspace", "Workspace mediation score"]
    hub_score = candidate_df.loc["Degree hub", "Workspace mediation score"]
    ax.axvline(workspace_score, linewidth=2.0, label="Workspace", linestyle="-")
    ax.axvline(hub_score, linewidth=2.0, label="Degree hub", linestyle="--")
    ax.set_xlabel("Workspace mediation score")
    ax.set_ylabel("Count")
    ax.set_title("Null distribution: 2,000 random four-node clusters")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "fig4_null_distribution.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(sweep_df["Observer-to-actuator coupling"], sweep_df["Split decoy WMS"], marker="o", label="Split I/O cluster")
    ax.axhline(candidate_df.loc["Workspace", "Workspace mediation score"], linestyle="--", label="Original workspace")
    ax.set_xlabel("Added observer-to-actuator coupling")
    ax.set_ylabel("Workspace mediation score")
    ax.set_title("A decoy becomes a genuine mediator when internal routing is added")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "fig5_internal_coupling_sweep.png", dpi=220)
    plt.close(fig)

    grouped = robustness_df.groupby("Background strength")["Beats all sampled random clusters"].mean() * 100.0
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(grouped.index, grouped.values, marker="o")
    ax.set_xlabel("Background-network strength")
    ax.set_ylabel("Recovery rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Robustness across 20 networks per background level")
    fig.tight_layout()
    fig.savefig(output_dir / "fig6_robustness.png", dpi=220)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="workspace_results")
    parser.add_argument("--full", action="store_true", help="Run repeated beam search and exhaustive four-node search")
    parser.add_argument("--processes", type=int, default=4)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    print("[1/7] Building the seed-0 synthetic network", flush=True)
    A, modules, groups = make_network(seed=0)
    Wc_node, Wo_node = gramian_node_contributions(A, horizon=10)
    base_communicability = cross_module_communicability(A, modules, horizon=10)

    candidate_sets = {
        **groups,
        "Split I/O decoy": np.array([52, 53, 56, 57]),
        "Random peripheral": np.array([2, 15, 28, 41]),
    }
    candidate_details = {}
    table_rows = []
    print("[2/7] Evaluating planted motifs and the split-I/O failure case", flush=True)
    for name, cluster in candidate_sets.items():
        external = external_access_metrics(A, modules, Wc_node, Wo_node, cluster)
        mediation = mediation_metrics(A, modules, cluster, horizon=10)
        lesioned = A.copy()
        lesioned[cluster, :] = 0.0
        lesioned[:, cluster] = 0.0
        lesion_drop = (base_communicability - cross_module_communicability(lesioned, modules, horizon=10)) / base_communicability
        candidate_details[name] = {"cluster": [int(x) for x in cluster], "external": external, "mediation": mediation}
        table_rows.append({
            "Cluster": name,
            "Nodes": " ".join(str(int(x)) for x in cluster),
            "Edge count": edge_count(A, cluster),
            "Write trace": external["write"],
            "Read trace": external["read"],
            "External access score": external["score"],
            "Mediation strength": mediation["strength"],
            "Mediation effective rank": mediation["effective_rank"],
            "I/O globality": mediation["globality"],
            "Workspace mediation score": mediation["score"],
            "Cross-module lesion drop": lesion_drop,
        })
    candidate_df = pd.DataFrame(table_rows).set_index("Cluster")
    candidate_df.to_csv(out / "candidate_cluster_metrics.csv")

    print("[3/7] Sampling same-size null clusters and robustness ensembles", flush=True)
    scorer = FastWorkspaceScorer(A, modules, horizon=10)
    rng = np.random.default_rng(123)
    random_scores = np.array([scorer.score(rng.choice(64, 4, replace=False)) for _ in range(2000)])
    pd.DataFrame({"Random four-node WMS": random_scores}).to_csv(out / "random_cluster_null.csv", index=False)

    robustness_rows = []
    for background in [0.75, 1.00, 1.50, 2.00]:
        for seed in range(20):
            A_s, modules_s, groups_s = make_network(seed=seed, background=background)
            scorer_s = FastWorkspaceScorer(A_s, modules_s, horizon=10)
            workspace_score = scorer_s.score(groups_s["Workspace"])
            local_rng = np.random.default_rng(50000 + seed + int(background * 1000))
            sampled = np.array([scorer_s.score(local_rng.choice(64, 4, replace=False)) for _ in range(300)])
            decoys = {
                **groups_s,
                "Split I/O decoy": np.array([52, 53, 56, 57]),
            }
            decoy_scores = {name: scorer_s.score(cluster) for name, cluster in decoys.items()}
            robustness_rows.append({
                "Background strength": background,
                "Seed": seed,
                "Workspace score": workspace_score,
                "Random percentile": 100.0 * float(np.mean(sampled < workspace_score)),
                "Beats all sampled random clusters": bool(workspace_score > sampled.max()),
                "Best planted motif is workspace": max(decoy_scores, key=decoy_scores.get) == "Workspace",
                "Margin over best planted decoy": workspace_score - max(v for k, v in decoy_scores.items() if k != "Workspace"),
            })
    robustness_df = pd.DataFrame(robustness_rows)
    robustness_df.to_csv(out / "robustness_results.csv", index=False)

    print("[4/7] Sweeping internal observer-to-actuator coupling", flush=True)
    split_cluster = np.array([52, 53, 56, 57])
    actuator_nodes = np.array([52, 53])
    observer_nodes = np.array([56, 57])
    routing_pattern = np.array([[1.0, 0.35], [-0.4, 0.9]])
    sweep_rows = []
    for coupling in np.linspace(0.0, 1.2, 13):
        modified = A.copy()
        modified[np.ix_(actuator_nodes, observer_nodes)] += coupling * routing_pattern
        rho = float(np.max(np.abs(np.linalg.eigvals(modified))))
        if rho > 0.92:
            modified *= 0.92 / rho
        split_score = FastWorkspaceScorer(modified, modules, horizon=10).score(split_cluster)
        sweep_rows.append({
            "Observer-to-actuator coupling": coupling,
            "Split decoy WMS": split_score,
            "Original workspace WMS": candidate_df.loc["Workspace", "Workspace mediation score"],
        })
    sweep_df = pd.DataFrame(sweep_rows)
    sweep_df.to_csv(out / "internal_coupling_sweep.csv", index=False)

    print("[5/7] Generating figures", flush=True)
    save_figures(out, A, modules, candidate_details, candidate_df, random_scores, sweep_df, robustness_df)

    full_summary = {}
    if args.full:
        print("[6/7] Repeating approximate combinatorial search across 12 networks", flush=True)
        beam_rows = []
        for seed in range(12):
            A_s, modules_s, groups_s = make_network(seed=seed)
            beam = beam_search(A_s, modules_s, k=4, width=50, horizon=10)
            top_cluster, top_score = beam[0]
            truth = tuple(int(x) for x in groups_s["Workspace"])
            intersection = len(set(top_cluster) & set(truth))
            union = len(set(top_cluster) | set(truth))
            truth_rank = next((rank for rank, (cluster, _) in enumerate(beam, start=1) if cluster == truth), None)
            beam_rows.append({
                "Seed": seed,
                "Top cluster": " ".join(map(str, top_cluster)),
                "Top score": top_score,
                "Exact recovery": top_cluster == truth,
                "Jaccard with true workspace": intersection / union,
                "True workspace rank within beam": truth_rank,
            })
        beam_df = pd.DataFrame(beam_rows)
        beam_df.to_csv(out / "beam_search_recovery.csv", index=False)
        full_summary["beam_exact_recovery_rate"] = float(beam_df["Exact recovery"].mean())
        full_summary["beam_mean_jaccard"] = float(beam_df["Jaccard with true workspace"].mean())

        print("[7/7] Exhaustively searching all 635,376 four-node clusters", flush=True)
        exact = exhaustive_four_node_search(A, modules, processes=args.processes)
        with open(out / "exact_search_result.json", "w", encoding="utf-8") as handle:
            json.dump(exact, handle, indent=2)
        full_summary["exact_search"] = exact
    else:
        print("[6/7] Skipping repeated and exhaustive search (use --full to run them)", flush=True)
        print("[7/7] Finalizing outputs", flush=True)

    summary = {
        "network": {
            "nodes": 64,
            "specialist_modules": 4,
            "module_size": 12,
            "workspace_nodes": [48, 49, 50, 51],
            "spectral_radius": float(np.max(np.abs(np.linalg.eigvals(A)))),
            "horizon": 10,
        },
        "headline": {
            "workspace_external_score": float(candidate_df.loc["Workspace", "External access score"]),
            "split_decoy_external_score": float(candidate_df.loc["Split I/O decoy", "External access score"]),
            "workspace_mediation_score": float(candidate_df.loc["Workspace", "Workspace mediation score"]),
            "split_decoy_mediation_score": float(candidate_df.loc["Split I/O decoy", "Workspace mediation score"]),
            "degree_hub_mediation_score": float(candidate_df.loc["Degree hub", "Workspace mediation score"]),
            "workspace_null_percentile": 100.0 * float(np.mean(random_scores < candidate_df.loc["Workspace", "Workspace mediation score"])),
        },
        "robustness": robustness_df.groupby("Background strength").agg(
            sampled_random_recovery_rate=("Beats all sampled random clusters", "mean"),
            planted_motif_recovery_rate=("Best planted motif is workspace", "mean"),
            mean_random_percentile=("Random percentile", "mean"),
        ).reset_index().to_dict(orient="records"),
        **full_summary,
    }
    with open(out / "summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    np.save(out / "seed0_coupling_matrix.npy", A)
    print(f"Complete. Outputs written to {out}", flush=True)


if __name__ == "__main__":
    main()
