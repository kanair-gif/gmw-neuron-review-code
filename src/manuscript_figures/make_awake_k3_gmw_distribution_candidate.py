#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


SCRIPT = Path(__file__).resolve()
RELEASE = SCRIPT.parents[1]
WORKSPACE = next(parent for parent in SCRIPT.parents if parent.name == "Global_Mediation_Workspace")
TABLES = (
    WORKSPACE
    / "_incoming/from_local_not_organized/KTMD_Kin2_Su_CorrectedMontage_FINAL_HANDOFF_20260817 (1)"
    / "KTMD_Kin2_Su_CorrectedMontage_FullRerun_20260817/tables"
)
OUT = RELEASE / "figures_source" / "figures_macaque_officialmap"

CANDIDATES = TABLES / "updated_same_animal_leave_one_day_out_candidates.csv"
REGISTERED_COORDS = TABLES / "updated_panel_registered_contact_frequency.csv"

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
JITTER = {
    "George": (-8.0, -6.0),
    "Chibi": (8.0, -6.0),
    "Kin2": (-8.0, 6.0),
    "Su": (8.0, 6.0),
}
TEXT = "#0B1220"
GRID = "#CBD5E1"


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "mathtext.fontset": "dejavusans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.dpi": 500,
            "axes.linewidth": 0.9,
            "axes.titlesize": 13.0,
            "axes.labelsize": 10.5,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 9.0,
        }
    )


def contact_ids(nodes: str) -> set[str]:
    contacts: set[str] = set()
    for node in nodes.split(";"):
        for value in re.findall(r"\d+", node):
            contacts.add(str(int(value)))
    return contacts


def read_coords() -> dict[tuple[str, str], dict[str, str]]:
    coords: dict[tuple[str, str], dict[str, str]] = {}
    with REGISTERED_COORDS.open(newline="") as handle:
        for row in csv.DictReader(handle):
            coords[(row["animal"], str(int(row["electrode"])))] = row
    return coords


def build_recurrence_rows() -> list[dict[str, object]]:
    coords = read_coords()
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    fold_counts: Counter[str] = Counter()
    missing: list[tuple[str, str]] = []

    with CANDIDATES.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["k"] != "3":
                continue
            animal = row["animal"]
            fold_counts[animal] += 1
            for contact in contact_ids(row["nodes"]):
                counts[animal][contact] += 1
                if (animal, contact) not in coords:
                    missing.append((animal, contact))

    if missing:
        missing_str = ", ".join(f"{animal}:{contact}" for animal, contact in missing[:20])
        raise RuntimeError(f"Missing registered coordinates for k=3 contacts: {missing_str}")

    rows: list[dict[str, object]] = []
    for animal in ANIMAL_ORDER:
        denominator = fold_counts[animal]
        for contact, selected in sorted(counts[animal].items(), key=lambda item: int(item[0])):
            coord = coords[(animal, contact)]
            rows.append(
                {
                    "animal": animal,
                    "animal_label": ANIMAL_LABELS[animal],
                    "k": 3,
                    "electrode": int(contact),
                    "panel": coord["panel"],
                    "template_x": float(coord["template_x"]),
                    "template_y": float(coord["template_y"]),
                    "selected_folds": int(selected),
                    "available_folds": int(denominator),
                    "recurrence": float(selected / denominator),
                }
            )
    return rows


def write_source_csv(rows: list[dict[str, object]], path: Path) -> None:
    fields = [
        "animal",
        "animal_label",
        "k",
        "electrode",
        "panel",
        "template_x",
        "template_y",
        "selected_folds",
        "available_folds",
        "recurrence",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def scatter_panel(ax, rows: list[dict[str, object]], panel: str, title: str) -> None:
    panel_rows = [row for row in rows if row["panel"] == panel]
    all_coords = [row for row in read_coords().values() if row["panel"] == panel]
    xs = [float(row["template_x"]) for row in all_coords]
    ys = [float(row["template_y"]) for row in all_coords]
    ax.scatter(
        xs,
        ys,
        s=15,
        color="#E2E8F0",
        edgecolor="#94A3B8",
        linewidth=0.35,
        zorder=1,
    )
    for animal in ANIMAL_ORDER:
        sub = [row for row in panel_rows if row["animal"] == animal]
        if not sub:
            continue
        dx, dy = JITTER[animal]
        ax.scatter(
            [float(row["template_x"]) + dx for row in sub],
            [float(row["template_y"]) + dy for row in sub],
            s=[55 + 245 * float(row["recurrence"]) for row in sub],
            color=ANIMAL_COLORS[animal],
            edgecolor="white",
            linewidth=0.9,
            alpha=0.88,
            label=ANIMAL_LABELS[animal],
            zorder=3,
        )
    ax.set_title(title, loc="left", fontweight="bold", pad=6)
    x_margin = max(45.0, (max(xs) - min(xs)) * 0.10)
    y_margin = max(30.0, (max(ys) - min(ys)) * 0.12)
    ax.set_xlim(min(xs) - x_margin, max(xs) + x_margin)
    ax.set_ylim(max(ys) + y_margin, min(ys) - y_margin)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(color=GRID, lw=0.5, alpha=0.35)
    ax.set_facecolor("#F8FAFC")


def make_figure(rows: list[dict[str, object]]) -> tuple[Path, Path, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "figS9_awake_k3_gmw_distribution_candidate_20260830_source.csv"
    pdf_path = OUT / "figS9_awake_k3_gmw_distribution_candidate_20260830.pdf"
    png_path = OUT / "figS9_awake_k3_gmw_distribution_candidate_20260830.png"
    write_source_csv(rows, csv_path)

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(7.2, 5.8),
        gridspec_kw={"height_ratios": [0.48, 1.16], "hspace": 0.26},
    )
    scatter_panel(axes[0], rows, "medial", "Medial panel")
    scatter_panel(axes[1], rows, "lateral", "Lateral surface")

    fig.suptitle(
        "Awake k=3 LODO GMW candidate-contact recurrence",
        x=0.055,
        y=0.985,
        ha="left",
        fontsize=14.4,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.055,
        0.936,
        "Each point is a contact endpoint from selected bipolar-pair candidates; size encodes selected folds / available folds.",
        ha="left",
        va="top",
        fontsize=9.8,
        color="#334155",
    )

    animal_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markersize=7.5,
            markerfacecolor=ANIMAL_COLORS[animal],
            markeredgecolor="white",
            label=ANIMAL_LABELS[animal],
        )
        for animal in ANIMAL_ORDER
    ]
    size_handles = [
        plt.scatter([], [], s=55 + 245 * val, color="#64748B", edgecolor="white", linewidth=0.8, label=label)
        for val, label in [(1 / 3, "1/3"), (2 / 3, "2/3"), (1.0, "1")]
    ]
    axes[1].legend(
        handles=size_handles,
        loc="lower right",
        frameon=True,
        facecolor="white",
        edgecolor="#E2E8F0",
        title="Recurrence",
        title_fontsize=9.5,
        handletextpad=0.35,
        columnspacing=0.9,
    )
    fig.legend(
        handles=animal_handles,
        loc="lower center",
        bbox_to_anchor=(0.50, 0.010),
        frameon=False,
        ncol=4,
        title="Animal",
        title_fontsize=9.5,
        handletextpad=0.35,
        columnspacing=0.9,
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.83, bottom=0.15)

    fig.savefig(pdf_path, facecolor="white", bbox_inches="tight", pad_inches=0.05)
    fig.savefig(png_path, facecolor="white", dpi=500, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return csv_path, pdf_path, png_path


def main() -> None:
    configure_style()
    for path in make_figure(build_recurrence_rows()):
        print(path)


if __name__ == "__main__":
    main()
