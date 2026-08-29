#!/usr/bin/env python3
"""Regenerate the awake-centered state summary and swapped-axis recovery figure."""

from __future__ import annotations

from pathlib import Path
import shutil

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables"
FIGURES = ROOT / "figures"

STATE_ORDER = [
    "eyes_open",
    "eyes_closed",
    "deep_anesthesia",
    "recovery_eyes_closed",
    "recovery_eyes_open",
]
STATE_LABELS = ["Awake\nEO", "Awake\nEC", "Deep\nanesthesia", "Recovery\nEC", "Recovery\nEO"]

SUMMARY_METRICS = ["Aspec", "Deff_frac", "Gpair", "Oorg", "top_share"]
SUMMARY_TITLES = {
    "Aspec": "Alignment",
    "Deff_frac": "Effective-rank fraction",
    "Gpair": "Routed breadth",
    "Oorg": "Gain-free organization",
    "top_share": "Leading-mode share",
}

RECOVERY_METRICS = ["Q", "Aspec", "Deff_frac", "Gpair", "Oorg"]
RECOVERY_STATES = ["deep_anesthesia", "recovery_eyes_closed", "recovery_eyes_open"]
RECOVERY_LABELS = ["Deep\nanesthesia", "Recovery\nEC", "Recovery\nEO"]

ANIMAL_COLORS = {
    "George": "#0072B2",
    "Chibi": "#E69F00",
    "Kin2": "#009E73",
    "Su": "#CC79A7",
}
K_COLORS = {3: "#0072B2", 4: "#E69F00", 5: "#009E73"}


def geometric_mean(values) -> float:
    x = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    x = x[np.isfinite(x) & (x > 0)]
    if not len(x):
        return np.nan
    return float(np.exp(np.mean(np.log(x))))


def arithmetic_mean(values) -> float:
    x = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    x = x[np.isfinite(x)]
    if not len(x):
        return np.nan
    return float(np.mean(x))


def padded_log_limits(values, minimum_span: float = 0.36) -> tuple[float, float]:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x) & (x > 0)]
    x = np.r_[x, 1.0]
    logs = np.log2(x)
    lo, hi = float(logs.min()), float(logs.max())
    span = max(hi - lo, minimum_span)
    pad = 0.13 * span
    return 2 ** (lo - pad), 2 ** (hi + pad)


def ratio_tick_formatter(value, _position) -> str:
    if value >= 10:
        return f"{value:.0f}"
    if value >= 1:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{value:.2f}".rstrip("0").rstrip(".")


def build_awake_centered_summary(blocktraj: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight blocks within day, days within k, and k within animal."""
    records = []
    for metric in SUMMARY_METRICS:
        value_col = metric
        day_k_state = (
            blocktraj.groupby(["animal", "date", "k", "state"], sort=False)[value_col]
            .apply(geometric_mean)
            .rename("day_value")
            .reset_index()
        )
        animal_k_state = (
            day_k_state.groupby(["animal", "k", "state"], sort=False)["day_value"]
            .apply(geometric_mean)
            .rename("k_value")
            .reset_index()
        )
        animal_state = (
            animal_k_state.groupby(["animal", "state"], sort=False)["k_value"]
            .apply(geometric_mean)
            .rename("state_value")
            .reset_index()
        )
        for animal, group in animal_state.groupby("animal", sort=False):
            state_values = group.set_index("state")["state_value"]
            if not {"eyes_open", "eyes_closed"}.issubset(state_values.index):
                raise ValueError(f"Missing awake state for {animal}, {metric}")
            baseline = float(np.sqrt(state_values["eyes_open"] * state_values["eyes_closed"]))
            if not np.isfinite(baseline) or baseline <= 0:
                raise ValueError(f"Invalid awake baseline for {animal}, {metric}: {baseline}")
            for state, value in state_values.items():
                if state not in STATE_ORDER or not np.isfinite(value) or value <= 0:
                    continue
                records.append(
                    {
                        "animal": animal,
                        "metric": metric,
                        "state": state,
                        "state_value": float(value),
                        "awake_geometric_baseline": baseline,
                        "normalized_value": float(value / baseline),
                    }
                )

    summary = pd.DataFrame(records)
    summary["state_order"] = summary["state"].map({s: i for i, s in enumerate(STATE_ORDER)})
    summary = summary.sort_values(["metric", "animal", "state_order"]).reset_index(drop=True)

    # Required invariant: for every animal-metric pair, GM(Awake EO, Awake EC) == 1.
    checks = []
    for (animal, metric), group in summary.groupby(["animal", "metric"]):
        awake = group[group.state.isin(["eyes_open", "eyes_closed"])]["normalized_value"]
        if len(awake) != 2:
            raise AssertionError(f"Expected two awake values for {animal}, {metric}")
        checks.append((animal, metric, geometric_mean(awake)))
    worst_error = max(abs(value - 1.0) for _, _, value in checks)
    if worst_error > 1e-12:
        raise AssertionError(f"Awake normalization failed; maximum error={worst_error}")
    return summary


def build_raw_state_summary(blocktraj: pd.DataFrame) -> pd.DataFrame:
    """Aggregate unnormalized metric values with equal arithmetic weight by day and k."""
    records = []
    for metric in SUMMARY_METRICS:
        day_k_state = (
            blocktraj.groupby(["animal", "date", "k", "state"], sort=False)[metric]
            .apply(arithmetic_mean)
            .rename("day_mean")
            .reset_index()
        )
        animal_k_state = (
            day_k_state.groupby(["animal", "k", "state"], sort=False)["day_mean"]
            .apply(arithmetic_mean)
            .rename("k_mean")
            .reset_index()
        )
        animal_state = (
            animal_k_state.groupby(["animal", "state"], sort=False)["k_mean"]
            .apply(arithmetic_mean)
            .rename("raw_mean")
            .reset_index()
        )
        for row in animal_state.itertuples(index=False):
            if row.state in STATE_ORDER and np.isfinite(row.raw_mean):
                records.append(
                    {
                        "animal": row.animal,
                        "metric": metric,
                        "state": row.state,
                        "raw_arithmetic_mean": float(row.raw_mean),
                    }
                )
    summary = pd.DataFrame(records)
    summary["state_order"] = summary["state"].map({s: i for i, s in enumerate(STATE_ORDER)})
    return summary.sort_values(["metric", "animal", "state_order"]).reset_index(drop=True)


def build_blockwise_summaries(blocktraj: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build within-condition block trajectories for normalized and raw displays."""
    normalized_records = []
    raw_records = []
    for metric in SUMMARY_METRICS:
        # Each date-k combination contributes one equally weighted value to each block.
        grouped = blocktraj.groupby(["animal", "state", "block"], sort=False)[metric]
        block_gm = grouped.apply(geometric_mean).rename("block_geometric_mean").reset_index()
        block_am = grouped.apply(arithmetic_mean).rename("block_arithmetic_mean").reset_index()

        for animal, animal_rows in blocktraj.groupby("animal", sort=False):
            state_gm = animal_rows.groupby("state", sort=False)[metric].apply(geometric_mean)
            if not {"eyes_open", "eyes_closed"}.issubset(state_gm.index):
                raise ValueError(f"Missing awake state for {animal}, {metric}")
            baseline = float(np.sqrt(state_gm["eyes_open"] * state_gm["eyes_closed"]))
            if not np.isfinite(baseline) or baseline <= 0:
                raise ValueError(f"Invalid blockwise awake baseline for {animal}, {metric}")
            for row in block_gm[block_gm.animal.eq(animal)].itertuples(index=False):
                if row.state in STATE_ORDER:
                    normalized_records.append(
                        {
                            "animal": animal,
                            "metric": metric,
                            "state": row.state,
                            "block": int(row.block),
                            "block_geometric_mean": float(row.block_geometric_mean),
                            "awake_geometric_baseline": baseline,
                            "normalized_value": float(row.block_geometric_mean / baseline),
                        }
                    )
        for row in block_am.itertuples(index=False):
            if row.state in STATE_ORDER:
                raw_records.append(
                    {
                        "animal": row.animal,
                        "metric": metric,
                        "state": row.state,
                        "block": int(row.block),
                        "raw_arithmetic_mean": float(row.block_arithmetic_mean),
                    }
                )

    normalized = pd.DataFrame(normalized_records)
    raw = pd.DataFrame(raw_records)
    order_map = {state: i for i, state in enumerate(STATE_ORDER)}
    for frame in (normalized, raw):
        frame["state_order"] = frame.state.map(order_map)
        frame.sort_values(["metric", "animal", "state_order", "block"], inplace=True)
        frame.reset_index(drop=True, inplace=True)

    # Check the baseline using all six block estimates in both awake states.
    for (animal, metric), group in normalized.groupby(["animal", "metric"]):
        awake = group[group.state.isin(["eyes_open", "eyes_closed"])]["normalized_value"]
        if abs(geometric_mean(awake) - 1.0) > 1e-12:
            raise AssertionError(f"Blockwise awake normalization failed for {animal}, {metric}")
    return normalized, raw


def block_positions(gap: float = 2.0) -> tuple[dict[str, np.ndarray], list[float]]:
    positions = {}
    centers = []
    for index, state in enumerate(STATE_ORDER):
        start = index * (6.0 + gap)
        x = start + np.arange(6, dtype=float)
        positions[state] = x
        centers.append(float(np.mean(x)))
    return positions, centers


def add_block_and_state_axes(ax, positions: dict[str, np.ndarray], centers: list[float]) -> None:
    all_positions = np.concatenate([positions[state] for state in STATE_ORDER])
    ax.set_xticks(all_positions, [str(block) for _state in STATE_ORDER for block in range(1, 7)])
    ax.tick_params(axis="x", labelsize=6.8, pad=2, length=2.5)
    ax.set_xlabel("Block within condition", labelpad=4, fontsize=8)
    state_axis = ax.secondary_xaxis("bottom")
    state_axis.set_xticks(centers, STATE_LABELS)
    state_axis.spines["bottom"].set_position(("outward", 28))
    state_axis.spines["bottom"].set_visible(False)
    state_axis.tick_params(axis="x", length=0, pad=1, labelsize=8)


def plot_gapped_blockwise(summary: pd.DataFrame, normalized: bool) -> Path:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titleweight": "semibold",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    value_col = "normalized_value" if normalized else "raw_arithmetic_mean"
    positions, centers = block_positions()
    fig, axes = plt.subplots(2, 3, figsize=(15.4, 9.1), dpi=240)
    axes = axes.ravel()

    for panel_index, metric in enumerate(SUMMARY_METRICS):
        ax = axes[panel_index]
        metric_data = summary[summary.metric.eq(metric)]
        all_values = []
        for state_index, state in enumerate(STATE_ORDER):
            x = positions[state]
            state_data = metric_data[metric_data.state.eq(state)]
            if state_index % 2 == 0:
                ax.axvspan(x[0] - 0.45, x[-1] + 0.45, color="#F5F6F7", zorder=0)

            for animal in ["George", "Chibi", "Kin2", "Su"]:
                animal_data = state_data[state_data.animal.eq(animal)].set_index("block")
                y = np.array(
                    [animal_data.at[block, value_col] if block in animal_data.index else np.nan for block in range(1, 7)],
                    dtype=float,
                )
                all_values.extend(y[np.isfinite(y)])
                ax.plot(
                    x,
                    y,
                    color=ANIMAL_COLORS[animal],
                    lw=1.0,
                    alpha=0.55,
                    marker="o",
                    markersize=2.5,
                    label=animal if state_index == 0 else None,
                    zorder=2,
                )

            mean_values = []
            lower_values = []
            upper_values = []
            for block in range(1, 7):
                values = state_data.loc[state_data.block.eq(block), value_col].dropna().to_numpy(dtype=float)
                if normalized:
                    logs = np.log(values[values > 0])
                    mean_value = float(np.exp(np.mean(logs)))
                    if len(logs) > 1:
                        factor = float(np.exp(np.std(logs, ddof=1) / np.sqrt(len(logs))))
                    else:
                        factor = 1.0
                    lower, upper = mean_value / factor, mean_value * factor
                else:
                    mean_value = float(np.mean(values))
                    sem = float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0.0
                    lower, upper = max(0.0, mean_value - sem), mean_value + sem
                mean_values.append(mean_value)
                lower_values.append(lower)
                upper_values.append(upper)
            all_values.extend(lower_values)
            all_values.extend(upper_values)
            ax.fill_between(x, lower_values, upper_values, color="black", alpha=0.13, linewidth=0, zorder=3)
            ax.plot(
                x,
                mean_values,
                color="black",
                lw=2.5,
                marker="o",
                markersize=3.2,
                label=("Across-animal geometric mean" if normalized else "Across-animal arithmetic mean")
                if state_index == 0
                else None,
                zorder=5,
            )

        if normalized:
            ax.axhline(1.0, color="#666666", ls="--", lw=0.9, zorder=1)
            finite_values = np.asarray(all_values, dtype=float)
            finite_values = finite_values[np.isfinite(finite_values)]
            ymin, ymax = float(finite_values.min()), float(finite_values.max())
            span = max(ymax - ymin, 0.15)
            ax.set_ylim(max(0.0, ymin - 0.08 * span), ymax + 0.08 * span)
        else:
            ymax = max(all_values) if all_values else 1.0
            ax.set_ylim(0, ymax * 1.1 if ymax > 0 else 1.0)
        add_block_and_state_axes(ax, positions, centers)
        ax.set_xlim(positions[STATE_ORDER[0]][0] - 0.65, positions[STATE_ORDER[-1]][-1] + 0.65)
        ax.grid(axis="y", alpha=0.18, lw=0.7)
        ax.set_title(SUMMARY_TITLES[metric], pad=8)
        ax.text(-0.08, 1.04, chr(65 + panel_index), transform=ax.transAxes, fontsize=12, fontweight="bold")
        if panel_index in (0, 3):
            ylabel = "Value / within-animal awake GM" if normalized else "Raw metric value (arithmetic mean)"
            ax.set_ylabel(ylabel)

    axes[5].axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    axes[5].legend(handles, labels, loc="center", frameon=False, fontsize=10)
    axes[5].text(
        0.5,
        0.18,
        "Lines stop at every condition boundary\nGray band: across-animal SEM (log-SEM for normalized values)\nBlocks 1–6 show within-condition progression\nInter-condition gaps are not elapsed-time scaled",
        transform=axes[5].transAxes,
        ha="center",
        va="center",
        fontsize=9,
        color="#444444",
        linespacing=1.5,
    )
    title = (
        "Blockwise trajectories: awake-centered normalization"
        if normalized
        else "Blockwise trajectories: raw metric values"
    )
    fig.suptitle(title, fontsize=15, fontweight="semibold", y=0.995)
    fig.tight_layout(rect=[0, 0.045, 1, 0.965], h_pad=3.4, w_pad=1.9)
    output = FIGURES / (
        "figure_updated_blockwise_trajectories_AWAKE_GM_ONE_GAPPED.png"
        if normalized
        else "figure_updated_blockwise_trajectories_RAW_GAPPED.png"
    )
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output


def plot_awake_centered_summary(summary: pd.DataFrame) -> Path:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titleweight": "semibold",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 3, figsize=(14.2, 8.2), dpi=240)
    axes = axes.ravel()
    x = np.arange(len(STATE_ORDER), dtype=float)

    for panel_index, metric in enumerate(SUMMARY_METRICS):
        ax = axes[panel_index]
        metric_data = summary[summary.metric.eq(metric)]
        plotted_values = []
        for animal in ["George", "Chibi", "Kin2", "Su"]:
            animal_data = metric_data[metric_data.animal.eq(animal)].set_index("state")
            y = np.array(
                [animal_data.at[state, "normalized_value"] if state in animal_data.index else np.nan for state in STATE_ORDER],
                dtype=float,
            )
            plotted_values.extend(y[np.isfinite(y)])
            ax.plot(
                x,
                y,
                color=ANIMAL_COLORS[animal],
                lw=1.15,
                alpha=0.62,
                marker="o",
                markersize=3.7,
                label=animal,
                zorder=2,
            )

        group_means = []
        group_ns = []
        for state in STATE_ORDER:
            values = metric_data.loc[metric_data.state.eq(state), "normalized_value"]
            group_means.append(geometric_mean(values))
            group_ns.append(int(values.notna().sum()))
        plotted_values.extend(group_means)
        ax.plot(
            x,
            group_means,
            color="black",
            lw=3.0,
            marker="o",
            markersize=5.2,
            label="Across-animal geometric mean",
            zorder=5,
        )
        ax.axhline(1.0, color="#666666", ls="--", lw=1.0, zorder=1)
        ax.set_yscale("log", base=2)
        ax.set_ylim(*padded_log_limits(plotted_values))
        ax.yaxis.set_major_formatter(FuncFormatter(ratio_tick_formatter))
        ax.set_xticks(x, STATE_LABELS)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", alpha=0.18, lw=0.7)
        ax.set_title(SUMMARY_TITLES[metric], pad=8)
        ax.text(-0.13, 1.04, chr(65 + panel_index), transform=ax.transAxes, fontsize=12, fontweight="bold")
        if panel_index in (0, 3):
            ax.set_ylabel("Normalized value\n(within-animal awake GM = 1)")
        for xpos, n in zip(x, group_ns):
            ax.annotate(f"n={n}", (xpos, 0), xycoords=("data", "axes fraction"), xytext=(0, -31),
                        textcoords="offset points", ha="center", va="top", fontsize=7, color="#666666")

    axes[5].axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    axes[5].legend(handles, labels, loc="center", frameon=False, fontsize=10)
    axes[5].text(
        0.5,
        0.21,
        "Thin colored lines: individual animals\nThick black line: across-animal geometric mean\nAwake EO × Awake EC geometric mean = 1 within each animal",
        transform=axes[5].transAxes,
        ha="center",
        va="center",
        fontsize=9,
        color="#444444",
        linespacing=1.5,
    )
    fig.suptitle("Awake-centered state comparison", fontsize=15, fontweight="semibold", y=0.995)
    fig.tight_layout(rect=[0, 0.025, 1, 0.965], h_pad=2.6, w_pad=2.0)

    output = FIGURES / "figure_updated_blockwise_trajectories_RECOVERY_CONSISTENT.png"
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    alias = FIGURES / "figure_updated_state_summary_awake_mean_one.png"
    shutil.copyfile(output, alias)
    return output


def plot_raw_state_summary(summary: pd.DataFrame) -> Path:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titleweight": "semibold",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 3, figsize=(14.2, 8.2), dpi=240)
    axes = axes.ravel()
    x = np.arange(len(STATE_ORDER), dtype=float)

    for panel_index, metric in enumerate(SUMMARY_METRICS):
        ax = axes[panel_index]
        metric_data = summary[summary.metric.eq(metric)]
        plotted_values = []
        for animal in ["George", "Chibi", "Kin2", "Su"]:
            animal_data = metric_data[metric_data.animal.eq(animal)].set_index("state")
            y = np.array(
                [animal_data.at[state, "raw_arithmetic_mean"] if state in animal_data.index else np.nan for state in STATE_ORDER],
                dtype=float,
            )
            plotted_values.extend(y[np.isfinite(y)])
            ax.plot(
                x,
                y,
                color=ANIMAL_COLORS[animal],
                lw=1.15,
                alpha=0.62,
                marker="o",
                markersize=3.7,
                label=animal,
                zorder=2,
            )

        group_means = []
        group_ns = []
        for state in STATE_ORDER:
            values = metric_data.loc[metric_data.state.eq(state), "raw_arithmetic_mean"]
            group_means.append(arithmetic_mean(values))
            group_ns.append(int(values.notna().sum()))
        plotted_values.extend(group_means)
        ax.plot(
            x,
            group_means,
            color="black",
            lw=3.0,
            marker="o",
            markersize=5.2,
            label="Across-animal arithmetic mean",
            zorder=5,
        )
        ymax = max(plotted_values) if plotted_values else 1.0
        ax.set_ylim(0, ymax * 1.12 if ymax > 0 else 1.0)
        ax.set_xticks(x, STATE_LABELS)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", alpha=0.18, lw=0.7)
        ax.set_title(SUMMARY_TITLES[metric], pad=8)
        ax.text(-0.13, 1.04, chr(65 + panel_index), transform=ax.transAxes, fontsize=12, fontweight="bold")
        if panel_index in (0, 3):
            ax.set_ylabel("Raw metric value\n(arithmetic mean)")
        for xpos, n in zip(x, group_ns):
            ax.annotate(f"n={n}", (xpos, 0), xycoords=("data", "axes fraction"), xytext=(0, -31),
                        textcoords="offset points", ha="center", va="top", fontsize=7, color="#666666")

    axes[5].axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    axes[5].legend(handles, labels, loc="center", frameon=False, fontsize=10)
    axes[5].text(
        0.5,
        0.2,
        "No awake-baseline division\nThin colored lines: individual animals\nThick black line: across-animal arithmetic mean\nConditions are chronological categories; spacing is not elapsed time",
        transform=axes[5].transAxes,
        ha="center",
        va="center",
        fontsize=9,
        color="#444444",
        linespacing=1.5,
    )
    fig.suptitle("Raw state estimates (no awake normalization)", fontsize=15, fontweight="semibold", y=0.995)
    fig.tight_layout(rect=[0, 0.025, 1, 0.965], h_pad=2.6, w_pad=2.0)

    output = FIGURES / "figure_updated_state_summary_raw_means.png"
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output


def plot_swapped_recovery(recovery: pd.DataFrame) -> Path:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titleweight": "semibold",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(1, 5, figsize=(16.2, 4.45), dpi=240)
    x = np.arange(len(RECOVERY_STATES), dtype=float)
    offsets = {3: -0.045, 4: 0.0, 5: 0.045}

    for panel_index, (ax, metric) in enumerate(zip(axes, RECOVERY_METRICS)):
        panel_values = []
        for k in (3, 4, 5):
            subset = recovery[(recovery.metric.eq(metric)) & (recovery.k.eq(k))].set_index("state")
            y = np.array([subset.at[state, "geomean_ratio"] for state in RECOVERY_STATES], dtype=float)
            low = np.array([subset.at[state, "ci_low"] for state in RECOVERY_STATES], dtype=float)
            high = np.array([subset.at[state, "ci_high"] for state in RECOVERY_STATES], dtype=float)
            panel_values.extend(low)
            panel_values.extend(high)
            yerr = np.vstack([y - low, high - y])
            ax.errorbar(
                x + offsets[k],
                y,
                yerr=yerr,
                color=K_COLORS[k],
                lw=2.0,
                marker="o",
                markersize=4.7,
                capsize=2.5,
                elinewidth=1.0,
                alpha=0.95,
                label=f"k={k}",
                zorder=3,
            )
        ax.axhline(1.0, color="#555555", ls="--", lw=1.0, zorder=1)
        ax.set_yscale("log", base=2)
        ax.set_ylim(*padded_log_limits(panel_values, minimum_span=0.5))
        ax.yaxis.set_major_formatter(FuncFormatter(ratio_tick_formatter))
        ax.set_xticks(x, RECOVERY_LABELS)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", alpha=0.18, lw=0.7)
        ax.set_title(metric, pad=8)
        ax.text(-0.14, 1.04, chr(65 + panel_index), transform=ax.transAxes, fontsize=12, fontweight="bold")
        if panel_index == 0:
            ax.set_ylabel("Ratio to awake (geometric mean, 95% CI)")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.98), ncol=3, frameon=False)
    fig.suptitle("Recovery across candidate-core sizes", fontsize=14.5, fontweight="semibold", y=1.055)
    fig.tight_layout(rect=[0, 0, 1, 0.9], w_pad=1.25)

    output = FIGURES / "figure_updated_recovery_swapped_axes.png"
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    # This is the requested replacement for the earlier x=k, line=state version.
    shutil.copyfile(output, FIGURES / "figure_updated_recovery.png")
    return output


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    blocktraj = pd.read_csv(TABLES / "updated_lodo_blockwise_trajectories.csv")
    recovery = pd.read_csv(TABLES / "updated_recovery_summary.csv")

    summary = build_awake_centered_summary(blocktraj)
    summary.to_csv(TABLES / "updated_state_summary_awake_mean_one.csv", index=False)
    raw_summary = build_raw_state_summary(blocktraj)
    raw_summary.to_csv(TABLES / "updated_state_summary_raw_means.csv", index=False)
    normalized_blocks, raw_blocks = build_blockwise_summaries(blocktraj)
    normalized_blocks.to_csv(TABLES / "updated_blockwise_trajectories_awake_gm_one.csv", index=False)
    raw_blocks.to_csv(TABLES / "updated_blockwise_trajectories_raw_means.csv", index=False)
    state_figure = plot_awake_centered_summary(summary)
    raw_figure = plot_raw_state_summary(raw_summary)
    normalized_block_figure = plot_gapped_blockwise(normalized_blocks, normalized=True)
    raw_block_figure = plot_gapped_blockwise(raw_blocks, normalized=False)
    recovery_figure = plot_swapped_recovery(recovery)

    max_error = 0.0
    for (_animal, _metric), group in summary.groupby(["animal", "metric"]):
        awake = group[group.state.isin(["eyes_open", "eyes_closed"])]["normalized_value"]
        max_error = max(max_error, abs(geometric_mean(awake) - 1.0))
    print(f"Wrote {state_figure}")
    print(f"Wrote {raw_figure}")
    print(f"Wrote {normalized_block_figure}")
    print(f"Wrote {raw_block_figure}")
    print(f"Wrote {recovery_figure}")
    print(f"Awake geometric-mean normalization maximum absolute error: {max_error:.3e}")


if __name__ == "__main__":
    main()
