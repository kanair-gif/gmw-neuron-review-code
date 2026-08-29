from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[7]
RELEASE = Path(__file__).resolve().parents[1]
SOURCE_CSV = ROOT / "docs" / "audit" / "MACAQUE_BLOCKWISE_GAPPED_HALFGAP_FIGURE_SOURCE_2026-08-27.csv"
FINAL_DIR = ROOT / "figures" / "final"
OUT_RELEASE = RELEASE / "figures_source" / "figures_macaque_corrected"


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
ANIMALS = ["George", "Chibi", "Kin2", "Su"]
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
METRICS = [
    ("Aspec", "Alignment"),
    ("Deff_frac", "Effective-rank fraction"),
    ("Gpair", "Routed breadth"),
    ("Oorg", "Gain-free organization"),
    ("top_share", "Leading-mode share"),
]
YLIMS = {
    "Aspec": (0.60, 1.15),
    "Deff_frac": (0.65, 1.25),
    "Gpair": (0.55, 1.45),
    "Oorg": (0.45, 1.50),
    "top_share": (0.70, 1.50),
}


def build_positions(block_gap=1.125):
    positions = {}
    centers = {}
    x = 0.0
    for state in STATE_ORDER:
        blocks = range(1, 7)
        xs = []
        for b in blocks:
            xs.append(x)
            positions[(state, b)] = x
            x += 1.0
        centers[state] = float(np.mean(xs))
        x += block_gap
    return positions, centers


def geo_mean(values):
    vals = np.asarray([v for v in values if np.isfinite(v) and v > 0], dtype=float)
    if vals.size == 0:
        return np.nan
    return float(np.exp(np.mean(np.log(vals))))


def plot_metric(ax, data, metric, title, panel_letter, positions, centers):
    metric_data = data[data["metric"] == metric].copy()
    for idx, state in enumerate(STATE_ORDER):
        xs = [positions[(state, b)] for b in range(1, 7)]
        if idx % 2 == 0:
            ax.axvspan(min(xs) - 0.5, max(xs) + 0.5, color="#f4f6f8", zorder=0)
        if idx > 0:
            ax.axvline(min(xs) - 0.85, color="#ccd2d9", lw=1.0, zorder=1)

    for animal in ANIMALS:
        sub_animal = metric_data[metric_data["animal"] == animal]
        for state in STATE_ORDER:
            sub = sub_animal[sub_animal["state"] == state].sort_values("block")
            if sub.empty:
                continue
            xs = [positions[(state, int(b))] for b in sub["block"]]
            ax.plot(
                xs,
                sub["ratio"],
                color=ANIMAL_COLORS[animal],
                lw=1.25,
                marker="o",
                ms=2.9,
                alpha=0.95,
                label=animal,
                zorder=3,
            )

    rows = []
    for state in STATE_ORDER:
        for block in range(1, 7):
            vals = metric_data[(metric_data["state"] == state) & (metric_data["block"] == block)]["ratio"]
            gm = geo_mean(vals)
            if np.isfinite(gm):
                rows.append((positions[(state, block)], gm))
    if rows:
        xs, ys = zip(*rows)
        # Draw phase-wise to avoid connecting across phase gaps.
        for state in STATE_ORDER:
            part = [
                (positions[(state, block)], geo_mean(metric_data[(metric_data["state"] == state) & (metric_data["block"] == block)]["ratio"]))
                for block in range(1, 7)
            ]
            part = [(x, y) for x, y in part if np.isfinite(y)]
            if part:
                px, py = zip(*part)
                ax.plot(px, py, color="black", lw=2.0, marker="o", ms=3.8, label="Geometric mean", zorder=5)

    ax.axhline(1.0, color="#6b7280", lw=1.0, ls="--", zorder=2)
    ax.set_ylim(*YLIMS[metric])
    ax.set_xticks([centers[s] for s in STATE_ORDER])
    ax.set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=8.0, linespacing=0.9)
    ax.tick_params(axis="y", labelsize=8.2)
    ax.grid(axis="y", color="#e5e7eb", lw=0.8)
    ax.set_title(title, fontsize=11.2, loc="left", fontweight="bold", pad=4)
    ax.text(-0.15, 1.09, panel_letter, transform=ax.transAxes, fontsize=12.4, fontweight="bold")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)


def main():
    data = pd.read_csv(SOURCE_CSV)
    positions, centers = build_positions(block_gap=1.125)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.linewidth": 0.9,
        }
    )

    fig = plt.figure(figsize=(7.2, 6.4), dpi=500)

    axes = [
        fig.add_axes([0.07, 0.715, 0.40, 0.19]),
        fig.add_axes([0.57, 0.715, 0.40, 0.19]),
        fig.add_axes([0.07, 0.440, 0.40, 0.19]),
        fig.add_axes([0.57, 0.440, 0.40, 0.19]),
        fig.add_axes([0.07, 0.165, 0.40, 0.19]),
    ]
    for ax, (metric, title), letter in zip(axes, METRICS, list("ABCDE")):
        plot_metric(ax, data, metric, title, letter, positions, centers)

    ax_legend = fig.add_axes([0.57, 0.145, 0.40, 0.215])
    ax_legend.axis("off")
    handles = []
    labels = []
    for animal in ANIMALS:
        h = plt.Line2D([], [], color=ANIMAL_COLORS[animal], marker="o", lw=1.4, ms=4.0, label=ANIMAL_LABELS[animal])
        handles.append(h)
        labels.append(ANIMAL_LABELS[animal])
    handles.append(plt.Line2D([], [], color="black", marker="o", lw=2.0, ms=3.8, label="Geometric mean"))
    labels.append("Geometric mean")
    ax_legend.legend(
        handles,
        labels,
        loc="upper left",
        ncol=2,
        frameon=False,
        fontsize=8.8,
        handlelength=2.2,
        columnspacing=1.2,
        borderaxespad=0.0,
    )
    ax_legend.text(
        0.0,
        0.33,
        "EO, eyes open; EC, eyes closed.\nAnimal-balanced ratios to awake baseline;\nlines stop at phase boundaries.\nRecovery excludes unavailable\nMonkey B recovery blocks.",
        ha="left",
        va="top",
        fontsize=8.2,
        linespacing=1.25,
    )

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    OUT_RELEASE.mkdir(parents=True, exist_ok=True)
    final_png = FINAL_DIR / "ktmd_blockwise_trajectories_recovery_consistent_awake_mean_one_gapped_halfgap_largeprint_legendinset_2026-08-27.png"
    release_png = OUT_RELEASE / "figure_updated_blockwise_trajectories_RECOVERY_CONSISTENT_awake_mean_one_GAPPED_HALFGAP_LARGEPRINT_LEGENDINSET_20260827.png"
    fig.savefig(final_png, dpi=500, facecolor="white")
    fig.savefig(release_png, dpi=500, facecolor="white")
    plt.close(fig)
    print(final_png)
    print(release_png)


if __name__ == "__main__":
    main()
