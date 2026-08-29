#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import math
import sys
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SCRIPT = Path(__file__).resolve()
RELEASE = SCRIPT.parents[1]
WORKSPACE = next(parent for parent in SCRIPT.parents if parent.name == "Global_Mediation_Workspace")
SYNTH = WORKSPACE / "_incoming/from_local_not_organized/workspace_core_experiment"
SYNTH_RESULTS = SYNTH / "results"
NONLINEAR_ZIP = WORKSPACE / "_incoming/kanai_manual_transfer/various_data/Global_Workspace_Nonlinear_Thread_All_Files_with_All_Code_2026-08-19.zip"
NONLINEAR_RESULTS_PREFIX = (
    "Global_Workspace_Nonlinear_Thread_All_Files_with_All_Code_2026-08-19/"
    "V10_Nonlinear_Extension_Handoff_2026-08-14/05_COMPLETE_MATERIALS/"
    "nonlinear_workspace_extension/results/"
)
OUT = RELEASE / "figures_source/figures_largeprint_20260827"
AUDIT = WORKSPACE / "docs/audit/FIGURE2_4_LARGEPRINT_SOURCE_NOTES_2026-08-27.md"


COLORS = {
    "Workspace": "#0072B2",
    "Actuator-only": "#D55E00",
    "Observer-only": "#009E73",
    "Degree hub": "#6A51A3",
    "Split I/O decoy": "#D55E00",
    "Random peripheral": "#64748B",
    "blue": "#0072B2",
    "orange": "#D55E00",
    "green": "#009E73",
    "purple": "#6A51A3",
    "gray": "#64748B",
    "black": "#101820",
}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "mathtext.fontset": "dejavusans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.linewidth": 0.9,
            "axes.titlesize": 11.6,
            "axes.labelsize": 10.8,
            "xtick.labelsize": 9.4,
            "ytick.labelsize": 9.4,
            "legend.fontsize": 8.9,
            "figure.titlesize": 13.0,
        }
    )


def panel_label(ax, label: str, x: float = -0.12, y: float = 1.09) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontsize=14.0, fontweight="bold", va="bottom", ha="left")


def load_workspace_module():
    spec = importlib.util.spec_from_file_location("workspace_core_experiment", SYNTH / "workspace_core_experiment.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load workspace_core_experiment.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_nonlinear_csv(name: str) -> pd.DataFrame:
    with zipfile.ZipFile(NONLINEAR_ZIP) as zf:
        with zf.open(NONLINEAR_RESULTS_PREFIX + name) as handle:
            return pd.read_csv(handle)


def parse_nodes(value: str) -> np.ndarray:
    return np.array([int(part) for part in str(value).split()], dtype=int)


def mediation_decomposition(workspace_module, A: np.ndarray, modules, nodes: np.ndarray, horizon: int = 10) -> dict[str, float]:
    nodes = np.array(sorted(nodes.tolist()), dtype=int)
    rest = np.array([i for i in range(A.shape[0]) if i not in set(nodes.tolist())], dtype=int)
    A_ss = A[np.ix_(nodes, nodes)]
    B_in = A[np.ix_(nodes, rest)]
    C_out = A[np.ix_(rest, nodes)]

    Wc = np.zeros((len(nodes), len(nodes)))
    Wo = np.zeros((len(nodes), len(nodes)))
    A_power = np.eye(len(nodes))
    for _ in range(horizon):
        Wc += A_power @ B_in @ B_in.T @ A_power.T
        Wo += A_power.T @ C_out.T @ C_out @ A_power
        A_power = A_ss @ A_power

    spectrum = workspace_module.joint_spectrum(Wc, Wo)
    eval_c = np.linalg.eigvalsh((Wc + Wc.T) / 2.0)[::-1]
    eval_o = np.linalg.eigvalsh((Wo + Wo.T) / 2.0)[::-1]
    eval_c = np.clip(eval_c, 0.0, None)
    eval_o = np.clip(eval_o, 0.0, None)
    c_spec = float(np.sum(np.sqrt(eval_c * eval_o)))
    q = float(np.sum(spectrum))
    d_eff = workspace_module.effective_rank(spectrum)
    a_spec = q / c_spec if c_spec > 0 else 0.0
    read_by_module = np.array([np.linalg.norm(A[np.ix_(nodes, module)], "fro") ** 2 for module in modules])
    write_by_module = np.array([np.linalg.norm(A[np.ix_(module, nodes)], "fro") ** 2 for module in modules])
    g_pair = math.sqrt(workspace_module.entropy_globality(read_by_module) * workspace_module.entropy_globality(write_by_module))
    return {"Cspec": c_spec, "Aspec": a_spec, "Q": q, "Deff": d_eff, "Gpair": float(g_pair), "WMI": q * (d_eff / len(nodes)) * g_pair}


def load_synthetic():
    module = load_workspace_module()
    A = np.load(SYNTH_RESULTS / "seed0_coupling_matrix.npy")
    _, modules, _ = module.make_network(seed=0)
    table = pd.read_csv(SYNTH_RESULTS / "candidate_cluster_metrics.csv")
    table["nodes_array"] = table["Nodes"].map(parse_nodes)
    decomp = []
    for _, row in table.iterrows():
        values = mediation_decomposition(module, A, modules, row["nodes_array"])
        values["Cluster"] = row["Cluster"]
        decomp.append(values)
    decomp_df = pd.DataFrame(decomp).set_index("Cluster")
    return module, A, modules, table.set_index("Cluster"), decomp_df


def save_both(fig, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.pdf", facecolor="white", bbox_inches="tight", pad_inches=0.04)
    fig.savefig(OUT / f"{stem}.png", facecolor="white", dpi=500, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def make_figure2() -> None:
    _, A, _, table, decomp = load_synthetic()
    order = ["Workspace", "Split I/O decoy", "Degree hub", "Actuator-only", "Observer-only", "Random peripheral"]
    short = {
        "Workspace": "Workspace",
        "Split I/O decoy": "Split I/O",
        "Degree hub": "Degree hub",
        "Actuator-only": "Actuator",
        "Observer-only": "Observer",
        "Random peripheral": "Random",
    }

    fig = plt.figure(figsize=(7.2, 6.75), dpi=500)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.02, 1.0], width_ratios=[0.86, 1.14], hspace=0.48, wspace=0.54)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    image = ax_a.imshow(np.abs(A), cmap="magma_r", vmin=0, vmax=np.percentile(np.abs(A), 99.6), aspect="equal")
    for boundary in [12, 24, 36, 48, 52, 56, 60]:
        ax_a.axhline(boundary - 0.5, color="white", lw=0.8, alpha=0.9)
        ax_a.axvline(boundary - 0.5, color="white", lw=0.8, alpha=0.9)
    ax_a.set_title("Directed coupling matrix", loc="left", fontweight="bold", pad=4)
    ax_a.set_xlabel("Source node")
    ax_a.set_ylabel("Target node")
    ax_a.set_xticks([0, 16, 32, 48, 63])
    ax_a.set_yticks([0, 16, 32, 48, 63])
    panel_label(ax_a, "A")

    y = np.arange(len(order))
    ext = table.loc[order, "External access score"].astype(float).to_numpy()
    wmi = table.loc[order, "Workspace mediation score"].astype(float).to_numpy()
    ax_b.barh(y + 0.18, ext, height=0.34, color="#C7C9CC", edgecolor="#777777", label="External access")
    ax_b.barh(y - 0.18, wmi, height=0.34, color=[COLORS[name] for name in order], edgecolor="white", label="WMI")
    ax_b.set_yticks(y)
    ax_b.set_yticklabels([short[name] for name in order])
    ax_b.invert_yaxis()
    ax_b.set_xlabel("Score")
    ax_b.set_title("External access vs WMI", loc="left", fontweight="bold", pad=4)
    ax_b.legend(frameon=False, loc="lower right", fontsize=8.4)
    ax_b.tick_params(axis="y", labelsize=8.8)
    ax_b.grid(axis="x", color="#e5e7eb", lw=0.8)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    panel_label(ax_b, "B")

    modes = np.arange(1, 5)
    for name in ["Workspace", "Degree hub", "Split I/O decoy", "Random peripheral"]:
        # Recreate spectra from the published source module to avoid reading from raster artwork.
        module, A_local, modules, table_local, _ = load_synthetic()
        spec = module.mediation_metrics(A_local, modules, table_local.loc[name, "nodes_array"], horizon=10)["spectrum"][:4]
        ax_c.plot(modes, spec, marker="o", lw=2.0, ms=4.2, color=COLORS[name], label=short[name])
    ax_c.set_title("Mediation mode spectrum", loc="left", fontweight="bold", pad=4)
    ax_c.set_xlabel("Mediation mode")
    ax_c.set_ylabel("Singular value")
    ax_c.set_xticks(modes)
    ax_c.grid(axis="y", color="#e5e7eb", lw=0.8)
    ax_c.legend(
        frameon=False,
        fontsize=7.0,
        ncol=1,
        loc="upper left",
        bbox_to_anchor=(0.66, 0.98),
        borderaxespad=0.0,
        handlelength=1.25,
        handletextpad=0.35,
        labelspacing=0.25,
    )
    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)
    panel_label(ax_c, "C")

    for name in order:
        ax_d.scatter(
            decomp.loc[name, "Aspec"],
            decomp.loc[name, "Deff"],
            s=85 if name == "Workspace" else 55,
            color=COLORS[name],
            edgecolor="white",
            linewidth=0.8,
            zorder=3,
        )
    label_offsets = {
        "Workspace": (-0.22, 0.14),
        "Split I/O decoy": (0.03, -0.22),
        "Degree hub": (-0.30, 0.10),
    }
    for name in ["Workspace", "Split I/O decoy", "Degree hub"]:
        dx, dy = label_offsets[name]
        ax_d.text(decomp.loc[name, "Aspec"] + dx, decomp.loc[name, "Deff"] + dy, short[name], fontsize=8.4, color=COLORS[name])
    ax_d.set_xlim(0, 1.05)
    ax_d.set_ylim(0.7, 4.15)
    ax_d.set_xlabel(r"Alignment $A_{\mathrm{spec}}$")
    ax_d.set_ylabel(r"Effective modes $D_{\mathrm{eff}}$")
    ax_d.set_title("Alignment and rank", loc="left", fontweight="bold", pad=4)
    ax_d.grid(color="#e5e7eb", lw=0.8)
    ax_d.spines["top"].set_visible(False)
    ax_d.spines["right"].set_visible(False)
    panel_label(ax_d, "D")

    save_both(fig, "fig2_synthetic_largeprint_20260830_legendinset")


def perturbation_recovery(module, A: np.ndarray, modules, eps_values: np.ndarray, repeats: int = 8) -> pd.DataFrame:
    rng = np.random.default_rng(9173)
    truth = tuple(range(48, 52))
    rows = []
    base_norm = np.linalg.norm(A, "fro")
    for eps in eps_values:
        for repeat in range(repeats):
            if eps == 0:
                perturbed = A.copy()
            else:
                noise = rng.normal(size=A.shape)
                noise *= (eps * base_norm) / max(np.linalg.norm(noise, "fro"), 1e-12)
                perturbed = A + noise
                rho = float(np.max(np.abs(np.linalg.eigvals(perturbed))))
                if rho > 0.92:
                    perturbed *= 0.92 / rho
            beam = module.beam_search(perturbed, modules, k=4, width=50, horizon=10)
            top = tuple(beam[0][0])
            inter = len(set(top) & set(truth))
            union = len(set(top) | set(truth))
            rows.append({"epsilon": eps, "repeat": repeat, "exact": top == truth, "jaccard": inter / union})
    return pd.DataFrame(rows)


def make_figure3() -> None:
    module, A, modules, _, _ = load_synthetic()
    null = pd.read_csv(SYNTH_RESULTS / "random_cluster_null.csv")["Random four-node WMS"].astype(float)
    summary = json.loads((SYNTH_RESULTS / "summary.json").read_text())
    exact = json.loads((SYNTH_RESULTS / "exact_search_result.json").read_text())
    robustness = pd.read_csv(SYNTH_RESULTS / "robustness_results.csv")

    method_ranks = pd.DataFrame(
        [
            ("WMI", 1),
            ("BC", 1),
            ("WS", 36),
            ("Comm", 44),
            ("PC", 76),
            ("AC", 137),
            ("SP", 40691),
            ("MC", 635365),
        ],
        columns=["metric", "rank"],
    )
    horizons = np.arange(4, 21, 2)
    horizon_scores = [
        module.mediation_metrics(A, modules, np.array([48, 49, 50, 51]), horizon=int(h))["score"]
        for h in horizons
    ]
    background = (
        robustness.groupby("Background strength")
        .agg(sampled_recovery=("Beats all sampled random clusters", "mean"), motif_recovery=("Best planted motif is workspace", "mean"))
        .reset_index()
    )
    perturb = perturbation_recovery(module, A, modules, np.array([0.0, 0.15, 0.30, 0.45, 0.60]), repeats=8)
    perturb_summary = perturb.groupby("epsilon").agg(exact=("exact", "mean"), jaccard=("jaccard", "mean")).reset_index()

    fig = plt.figure(figsize=(7.2, 6.85), dpi=500)
    gs = fig.add_gridspec(2, 2, hspace=0.45, wspace=0.38)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    ax_a.hist(null, bins=34, color="#A8B3BD", edgecolor="white", linewidth=0.5)
    target = float(exact["target_score"])
    ax_a.axvline(target, color=COLORS["blue"], lw=2.4)
    ax_a.text(
        0.61,
        0.92,
        f"Rank {exact['target_rank']} of\n{exact['total_clusters']:,}",
        transform=ax_a.transAxes,
        ha="left",
        va="top",
        fontsize=10.0,
        fontweight="bold",
        color=COLORS["blue"],
    )
    ax_a.set_title("Exact search score landscape", loc="left", fontweight="bold", pad=4)
    ax_a.set_xlabel("WMI")
    ax_a.set_ylabel("Random sets")
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    panel_label(ax_a, "A")

    method_ranks = method_ranks.sort_values("rank", ascending=True)
    y = np.arange(len(method_ranks))
    colors = [COLORS["blue"] if m == "WMI" else "#7B8794" for m in method_ranks["metric"]]
    ax_b.barh(y, np.log10(method_ranks["rank"].astype(float)), color=colors, edgecolor="white", height=0.62)
    for yy, rank in zip(y, method_ranks["rank"]):
        ax_b.text(np.log10(rank) + 0.08, yy, f"{rank:,}", va="center", fontsize=8.6)
    ax_b.set_yticks(y)
    ax_b.set_yticklabels(method_ranks["metric"])
    ax_b.invert_yaxis()
    ax_b.set_xlim(0, 6.05)
    ax_b.set_xlabel(r"$\log_{10}$ workspace rank")
    ax_b.set_title("Metric ranks", loc="left", fontweight="bold", pad=4)
    ax_b.grid(axis="x", color="#e5e7eb", lw=0.8)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    panel_label(ax_b, "B")

    ax_c.plot(horizons, horizon_scores, marker="o", lw=2.0, ms=4.2, color=COLORS["blue"])
    ax_c.set_xlabel("Horizon L")
    ax_c.set_ylabel("Workspace WMI")
    ax_c.set_title("Finite-horizon sensitivity", loc="left", fontweight="bold", pad=4)
    ax_c.grid(color="#e5e7eb", lw=0.8)
    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)
    ax_c.text(
        0.05,
        0.08,
        "Beam recovery:\n45/50 exact\nmean Jaccard 0.955",
        transform=ax_c.transAxes,
        fontsize=8.2,
        color="#374151",
        ha="left",
        va="bottom",
    )
    panel_label(ax_c, "C")

    ax_d.plot(background["Background strength"], 100 * background["sampled_recovery"], marker="o", lw=2.0, color=COLORS["green"], label="background")
    ax_d.plot(perturb_summary["epsilon"], 100 * perturb_summary["exact"], marker="s", lw=2.0, color=COLORS["orange"], label="perturb exact")
    ax_d.plot(perturb_summary["epsilon"], 100 * perturb_summary["jaccard"], marker="^", lw=2.0, color=COLORS["purple"], label="perturb Jaccard")
    ax_d.set_ylim(0, 105)
    ax_d.set_xlabel("Multiplier or perturbation")
    ax_d.set_ylabel("Recovery (%)")
    ax_d.set_title("Robustness checks", loc="left", fontweight="bold", pad=4)
    ax_d.grid(color="#e5e7eb", lw=0.8)
    ax_d.legend(frameon=False, loc="lower left", fontsize=7.6)
    ax_d.spines["top"].set_visible(False)
    ax_d.spines["right"].set_visible(False)
    panel_label(ax_d, "D")

    save_both(fig, "fig3_benchmark_largeprint_20260827")


def make_figure4() -> None:
    context = read_nonlinear_csv("context_gate.csv")
    dynamic = read_nonlinear_csv("dynamic_core_scores.csv")

    fig = plt.figure(figsize=(7.2, 6.65), dpi=500)
    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.36)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    ax_a.plot(context["context"], context["gate"], color=COLORS["gray"], lw=2.0, label="route gate")
    ax_a.plot(context["context"], context["Aspec"], color=COLORS["blue"], lw=2.2, label=r"$A_{\mathrm{spec}}$")
    ax_a.set_xlabel("Context state q")
    ax_a.set_ylabel("Fraction")
    ax_a.set_ylim(-0.04, 1.04)
    ax_a.set_title("Gate opens alignment", loc="left", fontweight="bold", pad=4)
    ax_a.legend(frameon=False, loc="upper left")
    ax_a.grid(color="#e5e7eb", lw=0.8)
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    panel_label(ax_a, "A")

    for metric, color, linewidth, label in [
        ("Cspec", COLORS["gray"], 1.8, r"$C_{\mathrm{spec}}$"),
        ("Q", COLORS["blue"], 2.2, r"$Q$"),
        ("WMI", COLORS["orange"], 2.2, "WMI"),
    ]:
        values = context[metric].to_numpy(dtype=float)
        peak = np.nanmax(np.abs(values))
        normalized = values / peak if peak > 0 else values
        ax_b.plot(context["context"], normalized, color=color, lw=linewidth, label=label)
    ax_b.set_xlabel("Context state q")
    ax_b.set_ylabel("Peak-normalized value")
    ax_b.set_ylim(-0.04, 1.04)
    ax_b.set_title("Capacity becomes realized mediation", loc="left", fontweight="bold", pad=4)
    ax_b.legend(frameon=False, loc="upper left")
    ax_b.grid(color="#e5e7eb", lw=0.8)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    panel_label(ax_b, "B")

    phase_colors = {"visual": "#EAF3FB", "transition": "#F5F0FA", "mixed": "#EAF6F1", "auditory": "#FDEEE7"}
    for phase, sub in dynamic.groupby("phase", sort=False):
        ax_c.axvspan(sub["time"].min(), sub["time"].max(), color=phase_colors.get(phase, "#f3f4f6"), zorder=0)
    ax_c.plot(dynamic["time"], dynamic["visual_input"], color=COLORS["blue"], lw=2.0, label="visual drive")
    ax_c.plot(dynamic["time"], dynamic["auditory_input"], color=COLORS["orange"], lw=2.0, label="auditory drive")
    ax_c.plot(dynamic["time"], (dynamic["context"] + 1.0) / 2.0, color=COLORS["black"], lw=1.8, label="context (scaled)")
    ax_c.set_xlabel("Time step")
    ax_c.set_ylabel("Drive / context")
    ax_c.set_ylim(-0.04, 1.04)
    ax_c.set_title("Sensory evidence shifts state", loc="left", fontweight="bold", pad=4)
    ax_c.legend(frameon=False, loc="upper right", fontsize=7.9)
    ax_c.grid(color="#e5e7eb", lw=0.8)
    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)
    panel_label(ax_c, "C")

    ax_d.plot(dynamic["time"], dynamic["visual_core_WMI"], color=COLORS["blue"], lw=2.1, label="visual core")
    ax_d.plot(dynamic["time"], dynamic["multimodal_core_WMI"], color=COLORS["green"], lw=2.1, label="multimodal core")
    ax_d.plot(dynamic["time"], dynamic["auditory_core_WMI"], color=COLORS["orange"], lw=2.1, label="auditory core")
    for phase, sub in dynamic.groupby("phase", sort=False):
        ax_d.axvspan(sub["time"].min(), sub["time"].max(), color=phase_colors.get(phase, "#f3f4f6"), zorder=0)
    ax_d.set_xlabel("Time step")
    ax_d.set_ylabel("Differential WMI")
    ax_d.set_title("Fixed-size search follows coalition", loc="left", fontweight="bold", pad=4)
    ax_d.legend(frameon=False, loc="upper right", fontsize=7.8)
    ax_d.grid(color="#e5e7eb", lw=0.8)
    ax_d.spines["top"].set_visible(False)
    ax_d.spines["right"].set_visible(False)
    panel_label(ax_d, "D")

    save_both(fig, "fig4_nonlinear_largeprint_20260830_finaltouch")


def write_audit_note() -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(
        "\n".join(
            [
                "# Figure 2-4 Large-Print Source Notes",
                "",
                "Date: 2026-08-27 (Asia/Tokyo)",
                "",
                "- Figure 2 was regenerated from `_incoming/from_local_not_organized/workspace_core_experiment/results/seed0_coupling_matrix.npy`, `candidate_cluster_metrics.csv`, and the metric functions in `workspace_core_experiment.py`.",
                "- Figure 3 was regenerated from `random_cluster_null.csv`, `exact_search_result.json`, `robustness_results.csv`, and `workspace_core_experiment.py`. The conventional-rank labels follow the existing manuscript/source figure values because no separate source table for that panel was found in the current package.",
                "- Figure 3 includes an explicit note that the 45/50 beam-search recovery statistic is present in the V21/source manuscript text, while the current `beam_search_recovery.csv` contains 12 rows. This should be resolved before final submission if a full provenance table is required.",
                "- Figure 4 was regenerated from the nonlinear-extension result tables inside `Global_Workspace_Nonlinear_Thread_All_Files_with_All_Code_2026-08-19.zip`.",
                "- Raw data and incoming source archives were not modified.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    configure_style()
    make_figure2()
    make_figure3()
    make_figure4()
    write_audit_note()
    print(OUT)
    print(AUDIT)


if __name__ == "__main__":
    main()
