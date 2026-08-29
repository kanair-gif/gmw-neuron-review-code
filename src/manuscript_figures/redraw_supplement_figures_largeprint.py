#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import NullFormatter


SCRIPT = Path(__file__).resolve()
RELEASE = SCRIPT.parents[1]
WORKSPACE = next(parent for parent in SCRIPT.parents if parent.name == "Global_Mediation_Workspace")
OUT = RELEASE / "figures_source" / "figures_supp_largeprint_20260830"

NONLINEAR_ZIP = WORKSPACE / "_incoming/kanai_manual_transfer/various_data/Global_Workspace_Nonlinear_Thread_All_Files_with_All_Code_2026-08-19.zip"
NONLINEAR_RESULTS_PREFIX = (
    "Global_Workspace_Nonlinear_Thread_All_Files_with_All_Code_2026-08-19/"
    "V10_Nonlinear_Extension_Handoff_2026-08-14/05_COMPLETE_MATERIALS/"
    "nonlinear_workspace_extension/results/"
)
ACTIVATION_RESULTS_PREFIX = (
    "Global_Workspace_Nonlinear_Thread_All_Files_with_All_Code_2026-08-19/"
    "V10_Nonlinear_Extension_Handoff_2026-08-14/05_COMPLETE_MATERIALS/"
    "nonlinear_workspace_extension/activation_core_benchmark/results/"
)
C2_ZIP = WORKSPACE / "_incoming/kanai_manual_transfer/various_data/Control_Theory_Global_Workspace_Analysis_Code_Complete_20260819.zip"
C2_PREFIX = "Control_Theory_Global_Workspace_Analysis_Code_20260819/02_C2_MST126_LINEAR_NONLINEAR/tables/"

MACAQUE_TABLES = (
    WORKSPACE
    / "_incoming/from_local_not_organized/KTMD_Kin2_Su_CorrectedMontage_FINAL_HANDOFF_20260817 (1)"
    / "KTMD_Kin2_Su_CorrectedMontage_FullRerun_20260817/tables"
)

COLORS = {
    "blue": "#0072B2",
    "orange": "#D55E00",
    "green": "#009E73",
    "purple": "#6A51A3",
    "vermillion": "#CC3311",
    "sky": "#56B4E9",
    "black": "#101820",
    "gray": "#64748B",
    "light_gray": "#E5E7EB",
}
METHOD_COLORS = {
    "mean Jacobian": COLORS["blue"],
    "secant eps=0.1": COLORS["green"],
    "passive VAR(1)": COLORS["orange"],
    "pathwise Jacobian": COLORS["gray"],
    "noise-averaged Jacobian": COLORS["purple"],
    "logistic GLM": COLORS["vermillion"],
}
K_COLORS = {3: COLORS["blue"], 4: COLORS["green"], 5: COLORS["orange"]}
ANIMAL_ORDER = ["George", "Chibi", "Kin2", "Su"]
ANIMAL_LABELS = {
    "George": "Monkey A",
    "Chibi": "Monkey B",
    "Kin2": "Monkey C",
    "Su": "Monkey D",
}
ANIMAL_COLORS = {
    "George": "#2f7ecb",
    "Chibi": "#2ca25f",
    "Kin2": "#f28e2b",
    "Su": "#8a5fd3",
}
STATE_ORDER = [
    "eyes_open",
    "eyes_closed",
    "deep_anesthesia",
    "recovery_eyes_closed",
    "recovery_eyes_open",
]
STATE_LABELS = {
    "eyes_open": "Awake\nEO",
    "eyes_closed": "Awake\nEC",
    "deep_anesthesia": "Deep",
    "recovery_eyes_closed": "Recovery\nEC",
    "recovery_eyes_open": "Recovery\nEO",
}
RECOVERY_STATES = ["deep_anesthesia", "recovery_eyes_closed", "recovery_eyes_open"]
RECOVERY_LABELS = {
    "deep_anesthesia": "Deep",
    "recovery_eyes_closed": "Recovery\nEC",
    "recovery_eyes_open": "Recovery\nEO",
}
METRIC_LABELS = {
    "Q": r"$Q$",
    "Cspec": r"$C_{\mathrm{spec}}$",
    "Aspec": r"$A_{\mathrm{spec}}$",
    "Deff_frac": r"$D_{\mathrm{eff}}/k$",
    "Gpair": r"$G_{\mathrm{pair}}$",
    "Oorg": r"$O_{\mathrm{org}}$",
    "top_share": "Leading-mode share",
    "WMI": "Raw WMI",
}
METRIC_ORDER = ["Q", "Cspec", "Aspec", "Deff_frac", "Gpair", "Oorg", "top_share", "WMI"]
TRANSFORM_ORDER = ["broadband", "state_zscore", "highpass4", "delta", "remove_pc1"]
TRANSFORM_LABELS = {
    "broadband": "Broadband",
    "state_zscore": "State\nz-score",
    "highpass4": ">4 Hz",
    "delta": "0.5-4 Hz",
    "remove_pc1": "Remove\nPC1",
}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "mathtext.fontset": "dejavusans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.dpi": 500,
            "axes.linewidth": 0.9,
            "axes.titlesize": 11.2,
            "axes.labelsize": 10.4,
            "xtick.labelsize": 8.8,
            "ytick.labelsize": 8.8,
            "legend.fontsize": 8.4,
            "figure.titlesize": 12.6,
        }
    )


def panel_label(ax, label: str, x: float = -0.12, y: float = 1.08) -> None:
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        fontsize=13.0,
        fontweight="bold",
        ha="left",
        va="bottom",
    )


def clean_axis(ax, grid_axis: str = "y") -> None:
    ax.grid(axis=grid_axis, color=COLORS["light_gray"], lw=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def save_both(fig, stem: str) -> list[str]:
    OUT.mkdir(parents=True, exist_ok=True)
    pdf = OUT / f"{stem}.pdf"
    png = OUT / f"{stem}.png"
    fig.savefig(pdf, facecolor="white", bbox_inches="tight", pad_inches=0.04)
    fig.savefig(png, facecolor="white", dpi=500, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    return [str(pdf.relative_to(RELEASE)), str(png.relative_to(RELEASE))]


def read_zip_csv(zip_path: Path, member: str) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(member) as handle:
            return pd.read_csv(handle)


def read_nonlinear_csv(name: str) -> pd.DataFrame:
    return read_zip_csv(NONLINEAR_ZIP, NONLINEAR_RESULTS_PREFIX + name)


def read_activation_csv(name: str) -> pd.DataFrame:
    return read_zip_csv(NONLINEAR_ZIP, ACTIVATION_RESULTS_PREFIX + name)


def read_c2_csv(name: str) -> pd.DataFrame:
    return read_zip_csv(C2_ZIP, C2_PREFIX + name)


def geo_mean(values) -> float:
    vals = np.asarray([v for v in values if np.isfinite(v) and v > 0], dtype=float)
    if vals.size == 0:
        return float("nan")
    return float(np.exp(np.mean(np.log(vals))))


def bootstrap_ci(values, rng, n_boot: int = 4000) -> tuple[float, float]:
    vals = np.asarray([v for v in values if np.isfinite(v) and v > 0], dtype=float)
    if vals.size == 0:
        return float("nan"), float("nan")
    boots = []
    for _ in range(n_boot):
        sample = rng.choice(vals, size=vals.size, replace=True)
        boots.append(geo_mean(sample))
    return tuple(np.percentile(boots, [2.5, 97.5]))


def grouped_animal_summary(data: pd.DataFrame, value_col: str, group_cols: list[str]) -> pd.DataFrame:
    rng = np.random.default_rng(20260830)
    rows = []
    for keys, group in data.groupby(group_cols, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        animal_values = []
        for animal in ANIMAL_ORDER:
            vals = group.loc[group["animal"] == animal, value_col]
            if not vals.empty:
                animal_values.append(geo_mean(vals))
        low, high = bootstrap_ci(animal_values, rng)
        row = dict(zip(group_cols, keys))
        row.update(
            {
                "estimate": geo_mean(animal_values),
                "ci_low": low,
                "ci_high": high,
                "n_animals": len(animal_values),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def set_log_ticks(ax, ticks: list[float]) -> None:
    ax.set_xscale("log")
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{tick:g}" for tick in ticks])
    ax.xaxis.set_minor_formatter(NullFormatter())


def set_log_y_ticks(ax, ticks: list[float]) -> None:
    ax.set_yscale("log")
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{tick:g}" for tick in ticks])
    ax.yaxis.set_minor_formatter(NullFormatter())


def make_s2_finite_amplitude() -> list[str]:
    df = read_nonlinear_csv("finite_amplitude.csv")
    peak = df.loc[df["Q_FA"].idxmax()]

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.55), gridspec_kw={"wspace": 0.42})
    ax = axes[0]
    ax.plot(df["amplitude"], df["Q_FA"], color=COLORS["blue"], lw=2.1, marker="o", ms=3.4, label=r"$Q^{FA}$")
    ax.plot(df["amplitude"], df["top_singular_value"], color=COLORS["purple"], lw=1.5, label="Mode 1")
    ax.plot(df["amplitude"], df["second_singular_value"], color=COLORS["green"], lw=1.5, label="Mode 2")
    ax.scatter([peak["amplitude"]], [peak["Q_FA"]], s=42, color=COLORS["vermillion"], edgecolor="white", linewidth=0.7, zorder=5)
    ax.set_title("Secant strength", loc="left", fontweight="bold", pad=4)
    ax.set_xlabel("Input amplitude")
    ax.set_ylabel("Strength")
    ax.set_xlim(df["amplitude"].min() - 0.03, df["amplitude"].max() + 0.03)
    ax.legend(frameon=False, loc="upper left", handlelength=1.7)
    clean_axis(ax)
    panel_label(ax, "A")

    ax = axes[1]
    ax.plot(df["amplitude"], df["Deff_FA"], color=COLORS["orange"], lw=2.1, marker="o", ms=3.2)
    ax.set_title("Effective rank", loc="left", fontweight="bold", pad=4)
    ax.set_xlabel("Input amplitude")
    ax.set_ylabel(r"$D_{\mathrm{eff}}$")
    ax.set_ylim(1.88, 2.03)
    clean_axis(ax)
    panel_label(ax, "B")

    ax = axes[2]
    ax.plot(df["amplitude"], df["max_gate"], color=COLORS["blue"], lw=2.0, label="Max gate")
    ax.plot(df["amplitude"], df["mean_max_gate"], color=COLORS["green"], lw=1.8, label="Mean max gate")
    ax.plot(df["amplitude"], df["nonlinear_residual"], color=COLORS["vermillion"], lw=1.6, label="Residual")
    ax.set_title("Gating and residual", loc="left", fontweight="bold", pad=4)
    ax.set_xlabel("Input amplitude")
    ax.set_ylabel("Value")
    ax.set_yscale("log")
    ax.legend(frameon=False, loc="lower right", handlelength=1.7)
    clean_axis(ax)
    panel_label(ax, "C")

    return save_both(fig, "figS2_finite_amplitude_largeprint_20260830")


def make_s3_nonlinear_extra() -> list[str]:
    hyst = read_nonlinear_csv("hysteresis.csv")
    sy = read_nonlinear_csv("higher_order_synergy.csv")

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.85), gridspec_kw={"wspace": 0.38})
    ax = axes[0]
    for branch, color, label in [("up", COLORS["blue"], "Increasing drive"), ("down", COLORS["orange"], "Decreasing drive")]:
        sub = hyst[hyst["branch"] == branch].sort_values("drive")
        ax.plot(sub["drive"], sub["WMI"], lw=2.0, color=color, label=label)
    ax.axvline(-0.305, color=COLORS["gray"], lw=1.0, ls="--")
    ax.axvline(0.305, color=COLORS["gray"], lw=1.0, ls="--")
    ax.set_yscale("log")
    ax.set_xlabel("Drive")
    ax.set_ylabel("WMI")
    ax.set_title("Bistable hysteresis", loc="left", fontweight="bold", pad=4)
    ax.legend(frameon=False, loc="upper left")
    clean_axis(ax)
    panel_label(ax, "A")

    ax = axes[1]
    ax.plot(sy["amplitude"], sy["joint_output_norm"], color=COLORS["purple"], lw=2.1, marker="o", ms=4.0, label="Joint sources")
    ax.plot(sy["amplitude"], sy["source_1_only_norm"], color=COLORS["gray"], lw=1.5, marker="s", ms=3.4, label="Source 1 only")
    ax.plot(sy["amplitude"], sy["source_2_only_norm"], color=COLORS["orange"], lw=1.5, marker="^", ms=3.4, label="Source 2 only")
    ax.set_xlabel("Input amplitude")
    ax.set_ylabel("Output norm")
    ax.set_title("Higher-order route", loc="left", fontweight="bold", pad=4)
    ax.set_ylim(-0.04, sy["joint_output_norm"].max() * 1.18)
    ax.legend(frameon=False, loc="upper left")
    clean_axis(ax)
    panel_label(ax, "B")

    return save_both(fig, "figS3_nonlinear_extra_largeprint_20260830")


def plot_rank_sweep(ax, data: pd.DataFrame, family: str, title: str, xlabel: str, label: str) -> None:
    sub = data[data["family"] == family].copy()
    for method, group in sub.groupby("method", sort=False):
        group = group.sort_values("value")
        ax.plot(
            group["value"],
            group["log10_core_rank"],
            lw=1.9,
            marker="o",
            ms=3.6,
            color=METHOD_COLORS.get(method, COLORS["gray"]),
            label=method,
        )
    ax.axhline(0, color=COLORS["black"], lw=0.8)
    ax.set_title(title, loc="left", fontweight="bold", pad=4)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(r"$\log_{10}$ core rank")
    clean_axis(ax)
    panel_label(ax, label)


def make_s4_activation_controls() -> list[str]:
    sweep = read_activation_csv("activation_sweep.csv")
    sample = read_activation_csv("sample_size_sweep.csv")
    ensemble = read_activation_csv("ensemble_summary.csv")

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.55), gridspec_kw={"hspace": 0.52, "wspace": 0.34})
    plot_rank_sweep(axes[0, 0], sweep, "tanh", "tanh gain sweep", "Recurrent gain", "A")
    plot_rank_sweep(axes[0, 1], sweep, "ReLU", "ReLU bias sweep", "Scalar bias", "B")

    ax = axes[1, 0]
    sample = sample.sort_values("sample_count")
    ax.plot(sample["sample_count"], sample["log10_core_rank"], color=COLORS["orange"], lw=2.1, marker="o", ms=4.0)
    ax.set_xscale("log", base=2)
    ax.set_title("Passive sample-size sweep", loc="left", fontweight="bold", pad=4)
    ax.set_xlabel("Transitions")
    ax.set_ylabel(r"$\log_{10}$ core rank")
    ax.set_xticks(sample["sample_count"])
    ax.set_xticklabels([str(int(v)) for v in sample["sample_count"]], rotation=35, ha="right")
    clean_axis(ax)
    panel_label(ax, "C")

    ax = axes[1, 1]
    keep = [
        "tanh, gain 0.8",
        "ReLU, scalar bias 0.15",
        "stochastic hard threshold, noise 1.2",
        "ReLU, calibrated all-active point",
    ]
    cond_labels = {
        "tanh, gain 0.8": "tanh\n0.8",
        "ReLU, scalar bias 0.15": "ReLU\n0.15",
        "stochastic hard threshold, noise 1.2": "Hard thr.\nnoise",
        "ReLU, calibrated all-active point": "ReLU\nactive",
    }
    sub = ensemble[ensemble["condition"].isin(keep)].copy()
    methods = [m for m in ["mean Jacobian", "secant eps=0.1", "passive VAR(1)", "noise-averaged Jacobian", "pathwise Jacobian", "logistic GLM"] if m in set(sub["method"])]
    x = np.arange(len(keep))
    offsets = np.linspace(-0.32, 0.32, len(methods))
    for off, method in zip(offsets, methods):
        vals = []
        for cond in keep:
            row = sub[(sub["condition"] == cond) & (sub["method"] == method)]
            vals.append(float(row["exact_recovery_rate"].iloc[0]) if not row.empty else np.nan)
        ax.scatter(x + off, vals, s=38, color=METHOD_COLORS.get(method, COLORS["gray"]), label=method, zorder=4)
    ax.set_ylim(-0.04, 1.08)
    ax.set_xticks(x)
    ax.set_xticklabels([cond_labels[c] for c in keep])
    ax.set_ylabel("Exact recovery rate")
    ax.set_title("Ensemble recovery", loc="left", fontweight="bold", pad=4)
    clean_axis(ax)
    ax.legend(frameon=False, loc="lower left", ncol=2, fontsize=7.2, handletextpad=0.3, columnspacing=0.7)
    panel_label(ax, "D")

    return save_both(fig, "figS4_activation_controls_largeprint_20260830")


def make_s5_lodo_transfer() -> list[str]:
    df = pd.read_csv(MACAQUE_TABLES / "updated_hierarchical_lodo_deep_effects.csv")
    df["metric"] = pd.Categorical(df["metric"], METRIC_ORDER, ordered=True)
    df = df.sort_values(["metric", "k"])

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    y_base = np.arange(len(METRIC_ORDER))[::-1]
    offsets = {3: -0.22, 4: 0.0, 5: 0.22}
    for k in [3, 4, 5]:
        sub = df[df["k"] == k]
        ys = [y_base[METRIC_ORDER.index(metric)] + offsets[k] for metric in sub["metric"]]
        x = sub["geomean_ratio"].to_numpy()
        xerr = np.vstack([x - sub["animal_boot_ci_low"].to_numpy(), sub["animal_boot_ci_high"].to_numpy() - x])
        ax.errorbar(
            x,
            ys,
            xerr=xerr,
            fmt="o",
            ms=4.4,
            lw=1.5,
            capsize=2.6,
            color=K_COLORS[k],
            label=f"k={k}",
            zorder=4,
        )
    ax.axvline(1.0, color=COLORS["black"], lw=0.9, ls="--")
    set_log_ticks(ax, [0.5, 0.75, 1, 1.5, 2, 3, 5])
    ax.set_xlim(0.43, 6.3)
    ax.set_yticks(y_base)
    ax.set_yticklabels([METRIC_LABELS[m] for m in METRIC_ORDER])
    ax.set_xlabel("Deep / awake ratio")
    ax.set_title("Same-animal LODO transfer", loc="left", fontweight="bold", pad=4)
    clean_axis(ax, grid_axis="x")
    ax.legend(frameon=False, loc="upper left", ncol=3)

    return save_both(fig, "figS5_macaque_lodo_largeprint_20260830")


def make_s6_crossfit_directional() -> list[str]:
    df = pd.read_csv(MACAQUE_TABLES / "updated_crossfit_directional_summary.csv")
    df["metric"] = pd.Categorical(df["metric"], METRIC_ORDER, ordered=True)
    df = df.sort_values("metric")

    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    y = np.arange(len(df))[::-1]
    colors = [COLORS["blue"] if d == "increase" else COLORS["orange"] for d in df["expected_direction"]]
    ax.barh(y, df["fraction"], height=0.58, color=colors, edgecolor="white", linewidth=0.7)
    for yi, row in zip(y, df.itertuples(index=False)):
        ax.text(min(row.fraction + 0.018, 0.985), yi, f"{int(row.count)}/{int(row.total)}", va="center", ha="left", fontsize=8.5)
    ax.set_xlim(0, 1.05)
    ax.set_yticks(y)
    ax.set_yticklabels([METRIC_LABELS[m] for m in df["metric"]])
    ax.set_xlabel("Fraction with prespecified direction")
    ax.set_title("Held-out directional consistency", loc="left", fontweight="bold", pad=4)
    clean_axis(ax, grid_axis="x")
    inc = plt.Line2D([], [], marker="s", color=COLORS["blue"], linestyle="", label="Expected increase")
    dec = plt.Line2D([], [], marker="s", color=COLORS["orange"], linestyle="", label="Expected decrease")
    ax.legend(handles=[inc, dec], frameon=False, loc="lower center", bbox_to_anchor=(0.50, -0.23), ncol=2)

    return save_both(fig, "figS6_crossfit_directional_largeprint_20260830")


def make_s7_qc_diagnostics() -> list[str]:
    model = pd.read_csv(MACAQUE_TABLES / "updated_day_model_qc_11days.csv")
    blocks = pd.read_csv(MACAQUE_TABLES / "updated_block_spectral_dynamical_metrics.csv")

    fig = plt.figure(figsize=(7.2, 4.85))
    gs = fig.add_gridspec(1, 2, width_ratios=[0.78, 1.22], wspace=0.62)
    ax = fig.add_subplot(gs[0, 0])
    x_pos = {"Awake": 0, "Deep": 1}
    for animal in ANIMAL_ORDER:
        sub = model[model["animal"] == animal].copy()
        for _, row in sub.iterrows():
            ax.plot(
                [x_pos["Awake"], x_pos["Deep"]],
                [row["full_awake_r2"], row["deep_anesthesia_r2"]],
                color=ANIMAL_COLORS[animal],
                lw=1.2,
                alpha=0.55,
            )
            ax.scatter(
                [x_pos["Awake"], x_pos["Deep"]],
                [row["full_awake_r2"], row["deep_anesthesia_r2"]],
                color=ANIMAL_COLORS[animal],
                s=24,
                edgecolor="white",
                linewidth=0.5,
                zorder=4,
            )
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Awake", "Deep"])
    ax.set_ylabel(r"Held-out $R^2$")
    ax.set_title("Short-lag prediction", loc="left", fontweight="bold", pad=4)
    ax.set_ylim(0.0, 1.0)
    clean_axis(ax)
    panel_label(ax, "A")

    ratio_rows = []
    diagnostic_cols = [
        "rms_median",
        "delta_fraction",
        "autocorr_25ms",
        "mean_abs_correlation",
        "pc1_variance_fraction",
        "covariance_effective_rank",
    ]
    diag_labels = {
        "rms_median": "RMS amplitude",
        "delta_fraction": "Delta fraction",
        "autocorr_25ms": "25-ms autocorr.",
        "mean_abs_correlation": "Mean abs. corr.",
        "pc1_variance_fraction": "PC1 variance",
        "covariance_effective_rank": "Cov. eff. rank",
    }
    for (animal, date), group in blocks.groupby(["animal", "date"], sort=False):
        awake = group[group["state"].isin(["eyes_open", "eyes_closed"])]
        deep = group[group["state"] == "deep_anesthesia"]
        if awake.empty or deep.empty:
            continue
        for col in diagnostic_cols:
            awake_med = float(np.nanmedian(awake[col]))
            deep_med = float(np.nanmedian(deep[col]))
            if awake_med > 0 and np.isfinite(deep_med):
                ratio_rows.append({"animal": animal, "date": date, "metric": col, "ratio": deep_med / awake_med})
    ratios = pd.DataFrame(ratio_rows)

    ax = fig.add_subplot(gs[0, 1])
    y_base = np.arange(len(diagnostic_cols))[::-1]
    for animal in ANIMAL_ORDER:
        sub = ratios[ratios["animal"] == animal]
        ys = [y_base[diagnostic_cols.index(m)] for m in sub["metric"]]
        ax.scatter(sub["ratio"], ys, s=22, color=ANIMAL_COLORS[animal], alpha=0.75, label=ANIMAL_LABELS[animal], zorder=3)
    for metric in diagnostic_cols:
        vals = ratios.loc[ratios["metric"] == metric, "ratio"]
        if not vals.empty:
            y = y_base[diagnostic_cols.index(metric)]
            ax.scatter([geo_mean(vals)], [y], marker="D", color=COLORS["black"], s=36, zorder=5)
    ax.axvline(1.0, color=COLORS["black"], lw=0.9, ls="--")
    set_log_ticks(ax, [0.4, 0.5, 1, 2, 3, 4])
    ax.set_xlim(0.35, 4.7)
    ax.set_yticks(y_base)
    ax.set_yticklabels([diag_labels[m] for m in diagnostic_cols])
    ax.set_xlabel("Deep / awake median ratio")
    ax.set_title("Whole-network diagnostics", loc="left", fontweight="bold", pad=4)
    clean_axis(ax, grid_axis="x")
    panel_label(ax, "B")
    handles = [plt.Line2D([], [], marker="o", color=ANIMAL_COLORS[a], linestyle="", label=ANIMAL_LABELS[a]) for a in ANIMAL_ORDER]
    handles.append(plt.Line2D([], [], marker="D", color=COLORS["black"], linestyle="", label="Geometric mean"))
    ax.legend(handles=handles, frameon=False, loc="lower center", bbox_to_anchor=(0.50, -0.33), ncol=3, fontsize=7.3, handletextpad=0.2, columnspacing=0.8)

    return save_both(fig, "figS7_macaque_qc_largeprint_20260830")


def plot_slowwave_panel(ax, df: pd.DataFrame, metric_col: str, title: str, ylabel: str, ylim: tuple[float, float], label: str) -> None:
    summary = grouped_animal_summary(df, metric_col, ["transform", "k"])
    summary["transform"] = pd.Categorical(summary["transform"], TRANSFORM_ORDER, ordered=True)
    summary = summary.sort_values(["transform", "k"])

    x = np.arange(len(TRANSFORM_ORDER))
    for k in [3, 4, 5]:
        sub = summary[summary["k"] == k]
        xs = np.array([x[TRANSFORM_ORDER.index(t)] for t in sub["transform"]])
        y = sub["estimate"].to_numpy()
        yerr = np.vstack([y - sub["ci_low"].to_numpy(), sub["ci_high"].to_numpy() - y])
        ax.errorbar(
            xs,
            y,
            yerr=yerr,
            color=K_COLORS[k],
            lw=1.6,
            marker="o",
            ms=4.2,
            capsize=2.5,
            label=f"k={k}",
            zorder=4,
        )
    ax.axhline(1.0, color=COLORS["black"], lw=0.9, ls="--")
    low = min(ylim[0], float(summary["ci_low"].min()) * 0.88)
    high = max(ylim[1], float(summary["ci_high"].max()) * 1.12)
    set_log_y_ticks(ax, [0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5, 8])
    ax.set_ylim(low, high)
    ax.set_xticks(x)
    ax.set_xticklabels([TRANSFORM_LABELS[t] for t in TRANSFORM_ORDER])
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", fontweight="bold", pad=4)
    panel_label(ax, label, x=-0.10, y=1.08)
    clean_axis(ax)


def make_s8_slowwave_controls() -> list[str]:
    df = pd.read_csv(MACAQUE_TABLES / "updated_slowwave_transform_controls_lodo_candidates.csv")
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 5.7), gridspec_kw={"hspace": 0.62})

    plot_slowwave_panel(
        axes[0],
        df,
        "Q_ratio",
        "Mediation strength",
        r"Deep / awake $Q$ ratio",
        (1.05, 7.8),
        "A",
    )
    axes[0].legend(frameon=False, loc="upper left", ncol=3)
    plot_slowwave_panel(
        axes[1],
        df,
        "Oorg_ratio",
        "Gain-free organization",
        r"Deep / awake $O_{\mathrm{org}}$ ratio",
        (0.30, 1.35),
        "B",
    )

    return save_both(fig, "figS8_slowwave_Q_Oorg_largeprint_20260830")


def make_s11_montage_sensitivity() -> list[str]:
    df = pd.read_csv(MACAQUE_TABLES / "working_vs_corrected_kin2_su_lodo_effects.csv")
    metrics = ["Q", "Cspec", "Aspec", "Oorg"]
    titles = ["Mediation strength", "Capacity envelope", "Alignment", "Gain-free organization"]
    source_styles = {
        "working_montage": ("Working montage", "--", "o"),
        "corrected_official_map": ("Corrected map", "-", "s"),
    }

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.1), gridspec_kw={"hspace": 0.48, "wspace": 0.32})
    for ax, metric, title, letter in zip(axes.ravel(), metrics, titles, list("ABCD")):
        for animal in ["Kin2", "Su"]:
            for source, (label_source, ls, marker) in source_styles.items():
                sub = df[(df["animal"] == animal) & (df["source"] == source)].sort_values("k")
                ax.plot(
                    sub["k"],
                    sub[metric],
                    color=ANIMAL_COLORS[animal],
                    ls=ls,
                    marker=marker,
                    ms=4.0,
                    lw=1.8,
                )
        ax.axhline(1.0, color=COLORS["black"], lw=0.8, ls="--")
        ax.set_xticks([3, 4, 5])
        ax.set_xlabel("Candidate size k")
        ax.set_ylabel("Deep / awake ratio")
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
        ax.set_yscale("log")
        vals = df[metric].to_numpy()
        ax.set_ylim(max(0.18, np.nanmin(vals) * 0.72), np.nanmax(vals) * 1.32)
        clean_axis(ax)
        panel_label(ax, letter)
    animal_handles = [
        plt.Line2D([], [], color=ANIMAL_COLORS["Kin2"], lw=1.8, label=ANIMAL_LABELS["Kin2"]),
        plt.Line2D([], [], color=ANIMAL_COLORS["Su"], lw=1.8, label=ANIMAL_LABELS["Su"]),
    ]
    source_handles = [
        plt.Line2D([], [], color=COLORS["black"], ls="--", marker="o", lw=1.4, label="Working montage"),
        plt.Line2D([], [], color=COLORS["black"], ls="-", marker="s", lw=1.4, label="Corrected map"),
    ]
    fig.legend(handles=animal_handles + source_handles, frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.025), ncol=4, fontsize=8.0)
    return save_both(fig, "figS10_montage_sensitivity_largeprint_20260830")


def make_s12_recovery() -> list[str]:
    df = pd.read_csv(MACAQUE_TABLES / "updated_recovery_summary.csv")
    df = df[df["metric"].isin(METRIC_ORDER)].copy()
    df["metric"] = pd.Categorical(df["metric"], METRIC_ORDER, ordered=True)
    df["state"] = pd.Categorical(df["state"], RECOVERY_STATES, ordered=True)

    fig, axes = plt.subplots(4, 2, figsize=(7.2, 8.15), gridspec_kw={"hspace": 0.58, "wspace": 0.34})
    for ax, metric, letter in zip(axes.ravel(), METRIC_ORDER, list("ABCDEFGH")):
        sub_metric = df[df["metric"] == metric]
        for k in [3, 4, 5]:
            sub = sub_metric[sub_metric["k"] == k].sort_values("state")
            x = np.arange(len(RECOVERY_STATES))
            y = sub["geomean_ratio"].to_numpy()
            yerr = np.vstack([y - sub["ci_low"].to_numpy(), sub["ci_high"].to_numpy() - y])
            ax.errorbar(x, y, yerr=yerr, color=K_COLORS[k], lw=1.4, marker="o", ms=3.6, capsize=2.0, label=f"k={k}", zorder=4)
        ax.axhline(1.0, color=COLORS["black"], lw=0.8, ls="--")
        ax.set_yscale("log")
        vals = sub_metric["geomean_ratio"].to_numpy()
        lows = sub_metric["ci_low"].to_numpy()
        highs = sub_metric["ci_high"].to_numpy()
        ax.set_ylim(max(0.16, np.nanmin(lows) * 0.78), np.nanmax(highs) * 1.22)
        ax.set_xticks(np.arange(len(RECOVERY_STATES)))
        ax.set_xticklabels([RECOVERY_LABELS[s] for s in RECOVERY_STATES], fontsize=7.5)
        if metric in ["Q", "Gpair"]:
            ax.set_ylabel("Ratio to awake")
        ax.set_title(METRIC_LABELS[metric], loc="left", fontweight="bold", pad=4)
        clean_axis(ax)
        panel_label(ax, letter, x=-0.16, y=1.07)
    axes[0, 0].legend(frameon=False, loc="upper left", ncol=1, fontsize=7.2)
    return save_both(fig, "figS11_recovery_largeprint_20260830")


def build_block_positions(block_gap: float = 1.15):
    positions = {}
    centers = {}
    x = 0.0
    for state in STATE_ORDER:
        xs = []
        for block in range(1, 7):
            positions[(state, block)] = x
            xs.append(x)
            x += 1.0
        centers[state] = float(np.mean(xs))
        x += block_gap
    return positions, centers


def make_s13_blockwise_raw() -> list[str]:
    data = pd.read_csv(MACAQUE_TABLES / "updated_blockwise_trajectories_raw_means.csv")
    metrics = ["Aspec", "Deff_frac", "Gpair", "Oorg", "top_share"]
    titles = ["Alignment", "Effective-rank fraction", "Routed breadth", "Gain-free organization", "Leading-mode share"]
    positions, centers = build_block_positions()

    fig = plt.figure(figsize=(7.2, 6.25))
    axes = [
        fig.add_axes([0.07, 0.720, 0.40, 0.18]),
        fig.add_axes([0.57, 0.720, 0.40, 0.18]),
        fig.add_axes([0.07, 0.455, 0.40, 0.18]),
        fig.add_axes([0.57, 0.455, 0.40, 0.18]),
        fig.add_axes([0.07, 0.190, 0.40, 0.18]),
    ]
    for ax, metric, title, letter in zip(axes, metrics, titles, list("ABCDE")):
        sub_metric = data[data["metric"] == metric].copy()
        for idx, state in enumerate(STATE_ORDER):
            xs = [positions[(state, block)] for block in range(1, 7)]
            if idx % 2 == 0:
                ax.axvspan(min(xs) - 0.5, max(xs) + 0.5, color="#F4F6F8", zorder=0)
            if idx > 0:
                ax.axvline(min(xs) - 0.85, color="#CCD2D9", lw=1.0, zorder=1)
        for animal in ANIMAL_ORDER:
            sub_animal = sub_metric[sub_metric["animal"] == animal]
            for state in STATE_ORDER:
                sub = sub_animal[sub_animal["state"] == state].sort_values("block")
                if sub.empty:
                    continue
                xs = [positions[(state, int(block))] for block in sub["block"]]
                ax.plot(xs, sub["raw_arithmetic_mean"], color=ANIMAL_COLORS[animal], lw=1.15, marker="o", ms=2.6, alpha=0.9, zorder=3)
        for state in STATE_ORDER:
            xs = []
            ys = []
            for block in range(1, 7):
                vals = sub_metric[(sub_metric["state"] == state) & (sub_metric["block"] == block)]["raw_arithmetic_mean"]
                if not vals.empty:
                    xs.append(positions[(state, block)])
                    ys.append(float(np.nanmean(vals)))
            if xs:
                ax.plot(xs, ys, color=COLORS["black"], lw=2.0, marker="o", ms=3.5, zorder=5)
        ax.set_xticks([centers[s] for s in STATE_ORDER])
        ax.set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=7.4, linespacing=0.9)
        ax.set_title(title, loc="left", fontweight="bold", pad=4)
        ax.tick_params(axis="y", labelsize=8.0)
        clean_axis(ax)
        panel_label(ax, letter, x=-0.15, y=1.08)

    ax_legend = fig.add_axes([0.57, 0.150, 0.40, 0.22])
    ax_legend.axis("off")
    handles = [
        plt.Line2D([], [], color=ANIMAL_COLORS[a], marker="o", lw=1.4, ms=3.6, label=ANIMAL_LABELS[a])
        for a in ANIMAL_ORDER
    ]
    handles.append(plt.Line2D([], [], color=COLORS["black"], marker="o", lw=2.0, ms=3.5, label="Arithmetic mean"))
    ax_legend.legend(handles=handles, frameon=False, loc="upper left", ncol=2, fontsize=8.2, columnspacing=0.9, handlelength=2.0)
    ax_legend.text(0.0, 0.32, "EO, eyes open; EC, eyes closed.\nRaw values are not awake-normalized;\nlines stop at condition boundaries.", ha="left", va="top", fontsize=8.0, linespacing=1.25)

    return save_both(fig, "figS12_blockwise_raw_largeprint_20260830")


def make_s14_static_nonlinear() -> list[str]:
    tanh = read_c2_csv("nonlinear_predictive_audit_tanh.csv")
    quad = read_c2_csv("nonlinear_predictive_audit_quadratic.csv")
    order = ["eyes_open", "eyes_closed", "deep_anesthesia"]
    labels = ["Eyes open", "Eyes closed", "Deep"]

    rows = []
    for state in order:
        t = tanh[tanh["state"] == state].iloc[0]
        q = quad[quad["state"] == state].iloc[0]
        rows.extend(
            [
                {"state": state, "model": "Linear", "test_r2": t["linear_test_r2"], "delta": 0.0},
                {"state": state, "model": "tanh residual", "test_r2": t["nonlinear_test_r2"], "delta": t["delta_test"]},
                {"state": state, "model": "Quadratic residual", "test_r2": q["quad_test"], "delta": q["delta_test"]},
            ]
        )
    df = pd.DataFrame(rows)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.95), gridspec_kw={"wspace": 0.35})
    ax = axes[0]
    x = np.arange(len(order))
    model_order = ["Linear", "tanh residual", "Quadratic residual"]
    offsets = {"Linear": -0.22, "tanh residual": 0.0, "Quadratic residual": 0.22}
    model_colors = {"Linear": COLORS["gray"], "tanh residual": COLORS["blue"], "Quadratic residual": COLORS["orange"]}
    for model in model_order:
        sub = df[df["model"] == model]
        ax.scatter(
            x + offsets[model],
            sub["test_r2"],
            color=model_colors[model],
            s=42,
            marker="o" if model == "Linear" else "s",
            label=model,
            zorder=4,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=18, ha="right")
    ax.set_ylabel(r"Held-out $R^2$")
    ax.set_title("Held-out prediction", loc="left", fontweight="bold", pad=4)
    ax.set_ylim(0.10, 0.96)
    ax.legend(frameon=False, loc="upper left", fontsize=7.6)
    clean_axis(ax)
    panel_label(ax, "A")

    ax = axes[1]
    width = 0.34
    tanh_delta = [float(tanh[tanh["state"] == s]["delta_test"].iloc[0]) for s in order]
    quad_delta = [float(quad[quad["state"] == s]["delta_test"].iloc[0]) for s in order]
    ax.set_axisbelow(True)
    ax.bar(x - width / 2, tanh_delta, width=width, color=COLORS["blue"], label="tanh residual", zorder=3)
    ax.bar(x + width / 2, quad_delta, width=width, color=COLORS["orange"], label="Quadratic residual", zorder=3)
    ax.axhline(0.0, color=COLORS["black"], lw=0.9, zorder=4)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=18, ha="right")
    ax.set_ylabel(r"$\Delta R^2$ vs linear")
    ax.set_title("Static nonlinear increment", loc="left", fontweight="bold", pad=4)
    ax.legend(frameon=False, loc="lower left", fontsize=7.8)
    clean_axis(ax)
    panel_label(ax, "B")

    return save_both(fig, "figS13_static_nonlinear_predictive_largeprint_20260830_gridbehind")


def main() -> None:
    configure_style()
    generated = {}
    makers = [
        ("S2", make_s2_finite_amplitude),
        ("S3", make_s3_nonlinear_extra),
        ("S4", make_s4_activation_controls),
        ("S5", make_s5_lodo_transfer),
        ("S6", make_s6_crossfit_directional),
        ("S7", make_s7_qc_diagnostics),
        ("S8", make_s8_slowwave_controls),
        ("S10", make_s11_montage_sensitivity),
        ("S11", make_s12_recovery),
        ("S12", make_s13_blockwise_raw),
        ("S13", make_s14_static_nonlinear),
    ]
    for label, maker in makers:
        generated[label] = maker()
    generated["S5_active_submission_override"] = [
        "figures_source/figures_supp_largeprint_20260830/figS5_macaque_componentfocus_pointmean_20260830.pdf",
        "figures_source/figures_supp_largeprint_20260830/figS5_macaque_componentfocus_pointmean_20260830.png",
    ]
    manifest = OUT / "manifest_20260830.json"
    manifest.write_text(json.dumps(generated, indent=2) + "\n")
    print(json.dumps(generated, indent=2))


if __name__ == "__main__":
    main()
