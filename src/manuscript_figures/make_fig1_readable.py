from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon


OUT = Path(__file__).resolve().parents[1] / "figures_source" / "figures_v14"
OUT.mkdir(parents=True, exist_ok=True)


def rounded_box(ax, xy, w, h, text, fc, ec="#667085", fontsize=11):
    box = FancyBboxPatch(
        xy,
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.02",
        linewidth=1.2,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(box)
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center", fontsize=fontsize)
    return box


def arrow(ax, start, end, color, lw=1.7, mutation_scale=14, rad=0.0, alpha=1.0, zorder=3):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            connectionstyle=f"arc3,rad={rad}",
            mutation_scale=mutation_scale,
            linewidth=lw,
            color=color,
            alpha=alpha,
            shrinkA=2,
            shrinkB=2,
            zorder=zorder,
        )
    )


def panel_a(ax):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.02, 0.95, "A", fontsize=16, fontweight="bold", va="top")
    ax.text(
        0.50,
        0.94,
        r"Specialist systems in the remainder $R$",
        fontsize=15,
        fontweight="bold",
        ha="center",
        va="top",
    )

    center = (0.50, 0.49)
    circle = Circle(center, 0.145, facecolor="#f3f6f8", edgecolor="#1f2933", linewidth=2.0)
    ax.add_patch(circle)
    ax.text(0.50, 0.545, "Global", ha="center", va="center", fontsize=14, fontweight="bold")
    ax.text(0.50, 0.492, "Mediation", ha="center", va="center", fontsize=14, fontweight="bold")
    ax.text(0.50, 0.439, "Workspace", ha="center", va="center", fontsize=14, fontweight="bold")
    ax.text(0.50, 0.365, r"$S$", ha="center", va="center", fontsize=15)

    nodes = {
        "Visual": (0.15, 0.76, "#dff3ef"),
        "Auditory": (0.10, 0.54, "#ece7f7"),
        "Memory": (0.15, 0.27, "#dff3ef"),
        "Executive": (0.80, 0.76, "#ece7f7"),
        "Value": (0.86, 0.54, "#dff3ef"),
        "Action": (0.81, 0.27, "#ece7f7"),
    }
    for label, (x, y, fc) in nodes.items():
        rounded_box(ax, (x - 0.07, y - 0.04), 0.14, 0.08, label, fc, fontsize=11)

    teal = "#0f8b8d"
    orange = "#ef7b20"
    for label, (x, y, _) in nodes.items():
        if x < center[0]:
            input_start = (x + 0.080, y + 0.014)
            input_end = (center[0] - 0.155, center[1] + 0.40 * (y - center[1]))
            output_start = (center[0] - 0.158, center[1] + 0.20 * (y - center[1]) - 0.018)
            output_end = (x + 0.082, y - 0.050)
            rad_in = -0.06 if label != "Auditory" else -0.02
            rad_out = 0.06 if label != "Auditory" else 0.02
            arrow(ax, input_start, input_end, teal, lw=1.95, mutation_scale=16, rad=rad_in, zorder=4)
            arrow(ax, output_start, output_end, orange, lw=1.95, mutation_scale=16, rad=rad_out, zorder=4)
        else:
            input_start = (x - 0.080, y + 0.014)
            input_end = (center[0] + 0.155, center[1] + 0.40 * (y - center[1]))
            output_start = (center[0] + 0.158, center[1] + 0.20 * (y - center[1]) - 0.018)
            output_end = (x - 0.082, y - 0.050)
            rad_in = 0.06 if label != "Value" else 0.02
            rad_out = -0.06 if label != "Value" else -0.02
            arrow(ax, input_start, input_end, teal, lw=1.95, mutation_scale=16, rad=rad_in, zorder=4)
            arrow(ax, output_start, output_end, orange, lw=1.95, mutation_scale=16, rad=rad_out, zorder=4)

    ax.text(0.50, 0.11, "Every specialist can be a source, a target, or both.", ha="center", fontsize=11)
    ax.text(
        0.50,
        0.045,
        r"Many-to-many mediation: $R_a \rightarrow S \rightarrow R_b$",
        ha="center",
        fontsize=12,
        fontweight="bold",
    )


def panel_b(ax):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.02, 0.96, "B", fontsize=16, fontweight="bold", va="top")

    header = FancyBboxPatch(
        (0.23, 0.83),
        0.54,
        0.10,
        boxstyle="round,pad=0.02,rounding_size=0.02",
        linewidth=0,
        facecolor="#eadff6",
    )
    ax.add_patch(header)
    ax.text(0.50, 0.88, "Boundary Hankel mediation", ha="center", va="center", fontsize=15, fontweight="bold")

    ax.text(0.16, 0.70, r"past inputs $u_R^-$", ha="center", fontsize=11)
    ax.text(0.84, 0.70, r"future outputs $y_R^+$", ha="center", fontsize=11)
    ax.text(0.50, 0.705, "internal modes\nin $S$", ha="center", fontsize=11, linespacing=0.9)

    # Boundary input/output wedges.
    ax.add_patch(Polygon([[0.09, 0.31], [0.13, 0.50], [0.09, 0.69]], closed=True, color="#0f8b8d", alpha=0.9))
    ax.add_patch(Polygon([[0.91, 0.31], [0.87, 0.50], [0.91, 0.69]], closed=True, color="#ef7b20", alpha=0.95))

    rounded_box(ax, (0.18, 0.28), 0.14, 0.26, "Reachability\nmatrix\n$\\mathcal{R}_L(S)$", "#dff3ef", "#0f8b8d", 12)
    rounded_box(ax, (0.68, 0.28), 0.14, 0.26, "Observability\nmatrix\n$\\mathcal{O}_L(S)$", "#fdebd8", "#ef7b20", 12)
    arrow(ax, (0.13, 0.50), (0.18, 0.50), "#0f8b8d", lw=2.2, mutation_scale=17)
    arrow(ax, (0.82, 0.50), (0.87, 0.50), "#ef7b20", lw=2.2, mutation_scale=17)

    mode_y = [0.62, 0.55, 0.48, 0.41, 0.34]
    for y in mode_y:
        ax.add_patch(Ellipse((0.50, y), 0.023, 0.050, facecolor="#7e57c2", edgecolor="#7e57c2", zorder=5))

    left_slots = [0.535, 0.505, 0.475, 0.445, 0.415]
    right_slots = [0.535, 0.505, 0.475, 0.445, 0.415]
    rads = [0.18, 0.09, 0.0, -0.09, -0.18]
    for y0, y1, rad in zip(left_slots, mode_y, rads):
        arrow(ax, (0.32, y0), (0.487, y1), "#7e57c2", lw=1.65, mutation_scale=15, rad=rad, alpha=0.95, zorder=4)
    for y0, y1, rad in zip(mode_y, right_slots, [-r for r in rads]):
        arrow(ax, (0.513, y0), (0.655, y1), "#7e57c2", lw=1.65, mutation_scale=15, rad=rad, alpha=0.95, zorder=4)

    ax.text(
        0.50,
        0.18,
        r"$\mathcal{H}_L(S)=\mathcal{O}_L(S)\,\mathcal{R}_L(S)$",
        ha="center",
        va="center",
        fontsize=13,
        bbox=dict(boxstyle="round,pad=0.18", facecolor="#f5effa", edgecolor="none"),
    )
    ax.text(
        0.50,
        0.045,
        "Mediation modes are jointly reachable from the remainder\nand observable through their effects on the remainder.",
        ha="center",
        fontsize=9.5,
        linespacing=0.9,
    )


def main():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "mathtext.fontset": "dejavusans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig = plt.figure(figsize=(7.2, 6.35))
    ax_a = fig.add_axes([0.05, 0.54, 0.90, 0.42])
    ax_b = fig.add_axes([0.05, 0.05, 0.90, 0.43])
    panel_a(ax_a)
    panel_b(ax_b)
    pdf = OUT / "fig1_gmw_boundary_hankel_v14_readable_arrowfixed_20260827.pdf"
    png = OUT / "fig1_gmw_boundary_hankel_v14_readable_arrowfixed_20260827.png"
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(png, dpi=450, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(pdf)
    print(png)


if __name__ == "__main__":
    main()
