#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
from itertools import product
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SCRIPT = Path(__file__).resolve()
RELEASE_DIR = SCRIPT.parents[1]
WORKSPACE = next(parent for parent in SCRIPT.parents if parent.name == "Global_Mediation_Workspace")

SOURCE = WORKSPACE / "_incoming/from_local_not_organized/KTMD_Kin2_Su_CorrectedMontage_FINAL_HANDOFF_20260817 (1)/KTMD_Kin2_Su_CorrectedMontage_FullRerun_20260817/tables/updated_hierarchical_lodo_deep_effects.csv"
ANIMAL_SOURCE = WORKSPACE / "_incoming/from_local_not_organized/KTMD_Kin2_Su_CorrectedMontage_FINAL_HANDOFF_20260817 (1)/KTMD_Kin2_Su_CorrectedMontage_FullRerun_20260817/tables/updated_animal_level_lodo_effects.csv"
OUT_PNG = RELEASE_DIR / "figures_source/figures_macaque_corrected/figure_updated_crossday_transfer_componentfocus_pointmean_LARGEPRINT_20260830.png"
OUT_PDF = RELEASE_DIR / "figures_source/figures_macaque_corrected/figure_updated_crossday_transfer_componentfocus_pointmean_LARGEPRINT_20260830.pdf"
AUDIT = WORKSPACE / "docs/audit/FIGURE5_COMPONENTFOCUS_POINTMEAN_SOURCE_AND_STATS_2026-08-30.csv"

ORDER = ["Q", "Cspec", "Aspec", "Deff_frac", "Gpair", "Oorg", "top_share", "WMI"]
LABELS = {
    "Q": r"$Q$",
    "Cspec": r"$C_{\mathrm{spec}}$",
    "Aspec": r"$A_{\mathrm{spec}}$",
    "Deff_frac": r"$D_{\mathrm{eff}}/k$",
    "Gpair": r"$G_{\mathrm{pair}}$",
    "Oorg": r"$O_{\mathrm{org}}$",
    "top_share": "Top-mode\nshare",
    "WMI": "WMI",
}
K_COLORS = {3: "#3A7BD5", 4: "#E67E22", 5: "#2E8B57"}
TCRIT_DF3_975 = 3.182446305284263


def geom_mean(values: pd.Series) -> float:
    return math.exp(sum(math.log(float(v)) for v in values) / len(values))


def t3_two_sided_p(t_value: float) -> float:
    t_value = abs(float(t_value))
    if not math.isfinite(t_value):
        return float("nan")
    term = math.atan(t_value / math.sqrt(3.0)) + (t_value * math.sqrt(3.0)) / (t_value * t_value + 3.0)
    cdf = 0.5 + term / math.pi
    return max(0.0, min(1.0, 2.0 * (1.0 - cdf)))


def t3_one_sided_directional_p(t_value: float, direction: str) -> float:
    oriented_t = float(t_value) if direction == "increase" else -float(t_value)
    if not math.isfinite(oriented_t):
        return float("nan")
    term = math.atan(oriented_t / math.sqrt(3.0)) + (
        oriented_t * math.sqrt(3.0)
    ) / (oriented_t * oriented_t + 3.0)
    cdf = 0.5 + term / math.pi
    return max(0.0, min(1.0, 1.0 - cdf))


def exact_one_sided_signflip_p(log_values: list[float], direction: str) -> float:
    oriented = [v if direction == "increase" else -v for v in log_values]
    observed = sum(oriented)
    null_sums = [
        sum(sign * value for sign, value in zip(signs, oriented))
        for signs in product([-1, 1], repeat=len(oriented))
    ]
    return sum(value >= observed - 1e-15 for value in null_sums) / len(null_sums)


def p_stars(p_value: float) -> str:
    if not math.isfinite(p_value) or p_value >= 0.05:
        return ""
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    return "*"


def display_stars(metric: str, stats: dict[str, float | str]) -> str:
    if metric == "WMI":
        return ""
    return str(stats["stars"])


def animal_mean_stats(animal_df: pd.DataFrame, metric: str, direction: str) -> dict[str, float | str]:
    col = f"{metric}_geomean"
    animal_log_means = []
    animal_summary = []
    for animal, sub in animal_df.groupby("animal", sort=True):
        logs = [math.log(float(v)) for v in sub.sort_values("k")[col]]
        log_mean = sum(logs) / len(logs)
        animal_log_means.append(log_mean)
        animal_summary.append(f"{animal}:{math.exp(log_mean):.6g}")

    n = len(animal_log_means)
    mean_log = sum(animal_log_means) / n
    sd_log = math.sqrt(sum((v - mean_log) ** 2 for v in animal_log_means) / (n - 1))
    se_log = sd_log / math.sqrt(n)
    t_value = mean_log / se_log if se_log > 0 else float("nan")
    p_two_sided = t3_two_sided_p(t_value)
    p_directional = t3_one_sided_directional_p(t_value, direction)
    signflip_p = exact_one_sided_signflip_p(animal_log_means, direction)
    t_ci_low = math.exp(mean_log - TCRIT_DF3_975 * se_log)
    t_ci_high = math.exp(mean_log + TCRIT_DF3_975 * se_log)
    boot_log_means = np.array(
        [
            sum(animal_log_means[i] for i in sample) / n
            for sample in product(range(n), repeat=n)
        ],
        dtype=float,
    )
    boot_ci_low, boot_ci_high = np.exp(np.quantile(boot_log_means, [0.025, 0.975]))
    return {
        "mean_ratio": math.exp(mean_log),
        "mean_ci_low": float(boot_ci_low),
        "mean_ci_high": float(boot_ci_high),
        "t_ci_low": t_ci_low,
        "t_ci_high": t_ci_high,
        "t_df3": t_value,
        "p_two_sided": p_two_sided,
        "p_directional": p_directional,
        "p_signflip_one_sided": signflip_p,
        "stars": p_stars(p_directional),
        "animal_mean_ratios": ";".join(animal_summary),
    }


def nice_limits(vals: list[float]) -> tuple[float, float]:
    vals = [v for v in vals if math.isfinite(v)]
    lo = min(vals + [1.0])
    hi = max(vals + [1.0])
    span = hi - lo
    if span <= 0:
        span = max(0.1, hi * 0.1)
    pad = 0.14 * span
    lo -= pad
    hi += pad
    if lo > 0.8 and hi < 1.25:
        lo = min(lo, 0.8)
        hi = max(hi, 1.2)
    return max(0.0, lo), hi


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "mathtext.fontset": "dejavusans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.linewidth": 0.9,
        }
    )

    df = pd.read_csv(SOURCE)
    df = df[(df["state"] == "deep_anesthesia") & (df["metric"].isin(ORDER))]
    df["k"] = df["k"].astype(int)
    animal_df = pd.read_csv(ANIMAL_SOURCE)

    audit_rows = []
    stats_by_metric = {}
    for metric in ORDER:
        sub = df[df["metric"] == metric].sort_values("k")
        direction = str(sub["expected_direction"].iloc[0])
        stats = animal_mean_stats(animal_df, metric, direction)
        stats_by_metric[metric] = stats
        audit_rows.append(
            {
                "metric": metric,
                "expected_direction": direction,
                "k_values": ";".join(str(k) for k in sub["k"]),
                "k_geomean_ratios": ";".join(f"{v:.6g}" for v in sub["geomean_ratio"]),
                "k_boot_ci_low": ";".join(f"{v:.6g}" for v in sub["animal_boot_ci_low"]),
                "k_boot_ci_high": ";".join(f"{v:.6g}" for v in sub["animal_boot_ci_high"]),
                "mean_over_k_geomean_ratio": f"{stats['mean_ratio']:.6g}",
                "mean_ci_low_animal_bootstrap": f"{stats['mean_ci_low']:.6g}",
                "mean_ci_high_animal_bootstrap": f"{stats['mean_ci_high']:.6g}",
                "mean_ci_low_animal_t": f"{stats['t_ci_low']:.6g}",
                "mean_ci_high_animal_t": f"{stats['t_ci_high']:.6g}",
                "t_df3": f"{stats['t_df3']:.6g}",
                "p_two_sided_animal_log_t": f"{stats['p_two_sided']:.6g}",
                "p_prespecified_directional_animal_log_t": f"{stats['p_directional']:.6g}",
                "p_one_sided_exact_signflip": f"{stats['p_signflip_one_sided']:.6g}",
                "directional_test_significance": stats["stars"],
                "displayed_significance": display_stars(metric, stats),
                "animal_mean_ratios_over_k": stats["animal_mean_ratios"],
                "source_table": str(SOURCE.relative_to(WORKSPACE)),
                "animal_source_table": str(ANIMAL_SOURCE.relative_to(WORKSPACE)),
                "statistical_unit": "animal; log ratios averaged across k=3,4,5 within animal; directional p values use prespecified-direction one-sample t test vs log ratio 0; df=3; mean interval uses exact animal-cluster bootstrap over four animals; WMI is displayed as an unstarred composite diagnostic",
            }
        )
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)

    fig, axes = plt.subplots(4, 2, figsize=(7.2, 8.3), dpi=500)
    axes = axes.ravel()

    for ax, metric in zip(axes, ORDER):
        sub = df[df["metric"] == metric].sort_values("k")
        stats = stats_by_metric[metric]
        mean_ratio = float(stats["mean_ratio"])
        mean_ci_low = float(stats["mean_ci_low"])
        mean_ci_high = float(stats["mean_ci_high"])
        values = (
            list(sub["geomean_ratio"])
            + list(sub["animal_boot_ci_low"])
            + list(sub["animal_boot_ci_high"])
            + [mean_ratio, mean_ci_low, mean_ci_high]
        )
        ymin, ymax = nice_limits(values)

        ax.axhline(1.0, color="#555555", linestyle=(0, (3, 3)), linewidth=0.85, zorder=0)

        x_by_k = {3: 0.0, 4: 1.0, 5: 2.0}
        for _, row in sub.iterrows():
            k = int(row["k"])
            x = x_by_k[k]
            ax.errorbar(
                [x],
                [row["geomean_ratio"]],
                yerr=[[row["geomean_ratio"] - row["animal_boot_ci_low"]], [row["animal_boot_ci_high"] - row["geomean_ratio"]]],
                fmt="o",
                color=K_COLORS[k],
                ecolor=K_COLORS[k],
                elinewidth=1.7,
                capsize=3.0,
                markersize=5.8,
                markeredgecolor="white",
                markeredgewidth=0.7,
                alpha=0.88,
                zorder=4,
            )

        mean_x = 3.25
        ax.errorbar(
            [mean_x],
            [mean_ratio],
            yerr=[[mean_ratio - mean_ci_low], [mean_ci_high - mean_ratio]],
            fmt="o",
            color="#111111",
            ecolor="#111111",
            elinewidth=2.0,
            capsize=3.5,
            markersize=8.2,
            markeredgewidth=0.0,
            zorder=5,
        )
        star = display_stars(metric, stats)
        if star:
            y_star = min(ymax - 0.02 * (ymax - ymin), mean_ci_high + 0.045 * (ymax - ymin))
            ax.text(
                mean_x,
                y_star,
                star,
                ha="center",
                va="bottom",
                fontsize=13.0,
                fontweight="bold",
                color="#111111",
            )
        ax.text(
            mean_x,
            mean_ratio + (0.030 * (ymax - ymin) if mean_ratio >= 1 else -0.035 * (ymax - ymin)),
            f"{mean_ratio:.2f}x",
            ha="center",
            va="bottom" if mean_ratio >= 1 else "top",
            fontsize=10.6,
            fontweight="bold",
            color="#111111",
        )
        ax.set_title(LABELS[metric], fontsize=12.8, fontweight="bold", pad=4, loc="left")
        ax.set_xlim(-0.50, 3.72)
        ax.set_ylim(ymin, ymax)
        ax.set_xticks([0.0, 1.0, 2.0, mean_x])
        ax.set_xticklabels(["k=3", "k=4", "k=5", "Mean"], fontsize=9.6)
        ax.tick_params(axis="y", labelsize=10.2, width=0.75, length=3.0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("#9e9e9e")
        ax.spines["bottom"].set_linewidth(0.7)
        ax.spines["left"].set_linewidth(0.8)
        ax.grid(axis="y", color="#e0e0e0", linewidth=0.55, alpha=0.8)

    for ax in axes[::2]:
        ax.set_ylabel("Deep / awake ratio", fontsize=11.0)

    fig.subplots_adjust(left=0.120, right=0.985, top=0.982, bottom=0.058, hspace=0.46, wspace=0.35)

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, facecolor="white", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(OUT_PDF, facecolor="white", bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


if __name__ == "__main__":
    main()
