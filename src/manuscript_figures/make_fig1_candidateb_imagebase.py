from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon


OUT = Path(__file__).resolve().parents[1] / "figures_source" / "figures_v14"
OUT.mkdir(parents=True, exist_ok=True)

PALETTE = {
    "text": "#0B1220",
    "muted": "#334155",
    "outline": "#64748B",
    "workspace_fill": "#F8FAFC",
    "workspace_stroke": "#172033",
    "left_fill": "#E6F2F8",
    "right_fill": "#F7EDE4",
    "header_fill": "#EEEAF7",
    "formula_fill": "#F3F1F8",
    "input": "#0072B2",
    "output": "#D55E00",
    "mode": "#6A51A3",
}


def configure_matplotlib():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "mathtext.fontset": "dejavusans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.linewidth": 0,
        }
    )


def setup_ax(ax):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")


def rounded_box(ax, x, y, w, h, fill, stroke, lw=1.6, radius=0.022, alpha=1.0, z=3):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.006,rounding_size={radius}",
        linewidth=lw,
        edgecolor=stroke,
        facecolor=fill,
        alpha=alpha,
        zorder=z,
    )
    ax.add_patch(patch)
    return patch


def arrow(ax, start, end, color, lw=2.0, rad=0.0, scale=17, z=2, alpha=0.96):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        connectionstyle=f"arc3,rad={rad}",
        mutation_scale=scale,
        linewidth=lw,
        color=color,
        alpha=alpha,
        shrinkA=0,
        shrinkB=0,
        capstyle="round",
        joinstyle="round",
        zorder=z,
    )
    ax.add_patch(patch)
    return patch


def txt(ax, x, y, s, size, weight="normal", ha="center", va="center", color=None, **kwargs):
    return ax.text(
        x,
        y,
        s,
        fontsize=size,
        fontweight=weight,
        ha=ha,
        va=va,
        color=color or PALETTE["text"],
        path_effects=[pe.withStroke(linewidth=2.4, foreground="white", alpha=0.62)]
        if kwargs.pop("halo", False)
        else None,
        **kwargs,
    )


def draw_panel_a_base(ax):
    p = PALETTE
    cx, cy = 0.50, 0.725

    nodes = {
        "visual": (0.11, 0.835, p["left_fill"]),
        "auditory": (0.07, 0.695, p["right_fill"]),
        "memory": (0.11, 0.595, p["left_fill"]),
        "executive": (0.75, 0.835, p["right_fill"]),
        "value": (0.81, 0.695, p["left_fill"]),
        "action": (0.75, 0.595, p["right_fill"]),
    }
    box_w, box_h = 0.17, 0.055

    # Arrows are baked into the raster base so their routing is stable.
    routes = [
        ((0.28, 0.842), (0.392, 0.760), p["input"], -0.10),
        ((0.405, 0.740), (0.28, 0.814), p["output"], 0.08),
        ((0.24, 0.724), (0.352, 0.716), p["input"], 0.00),
        ((0.405, 0.700), (0.24, 0.704), p["output"], 0.00),
        ((0.28, 0.612), (0.374, 0.680), p["input"], 0.10),
        ((0.405, 0.665), (0.28, 0.585), p["output"], -0.08),
        ((0.72, 0.842), (0.608, 0.760), p["input"], 0.10),
        ((0.595, 0.740), (0.72, 0.814), p["output"], -0.08),
        ((0.76, 0.724), (0.648, 0.716), p["input"], 0.00),
        ((0.595, 0.700), (0.76, 0.704), p["output"], 0.00),
        ((0.72, 0.612), (0.626, 0.680), p["input"], -0.10),
        ((0.595, 0.665), (0.72, 0.585), p["output"], 0.08),
    ]
    for start, end, color, rad in routes:
        arrow(ax, start, end, color, lw=2.35, rad=rad, scale=20, z=2)

    for x, y, fill in nodes.values():
        rounded_box(ax, x, y, box_w, box_h, fill, p["outline"], lw=1.6, radius=0.018, z=4)

    workspace = Ellipse(
        (cx, cy - 0.010),
        0.285,
        0.130,
        facecolor=p["workspace_fill"],
        edgecolor=p["workspace_stroke"],
        linewidth=2.2,
        zorder=5,
    )
    ax.add_patch(workspace)


def draw_panel_a_text(ax):
    p = PALETTE
    txt(ax, 0.035, 0.965, "A", 19, "bold", ha="left", va="top")
    txt(ax, 0.50, 0.960, r"Specialist systems in the remainder $R$", 18, "bold", va="top")

    labels = {
        "Visual": (0.195, 0.862),
        "Auditory": (0.155, 0.722),
        "Memory": (0.195, 0.622),
        "Executive": (0.835, 0.862),
        "Value": (0.895, 0.722),
        "Action": (0.835, 0.622),
    }
    for label, (x, y) in labels.items():
        txt(ax, x, y, label, 12.7)

    txt(ax, 0.50, 0.748, "Global", 14.0, "bold")
    txt(ax, 0.50, 0.719, "Mediation", 14.0, "bold")
    txt(ax, 0.50, 0.690, "Workspace", 14.0, "bold")
    txt(ax, 0.50, 0.660, r"$S$", 15.4, "normal")

    txt(ax, 0.50, 0.538, "Every specialist can be a source, a target, or both.", 11.4)
    txt(ax, 0.50, 0.502, r"Many-to-many mediation: $R_a \rightarrow S \rightarrow R_b$", 12.4, "bold")


def draw_panel_b_base(ax):
    p = PALETTE

    # Wedges.
    ax.add_patch(Polygon([[0.075, 0.120], [0.115, 0.235], [0.075, 0.335]], closed=True, color=p["input"], alpha=0.96, zorder=2))
    ax.add_patch(Polygon([[0.925, 0.120], [0.885, 0.235], [0.925, 0.335]], closed=True, color=p["output"], alpha=0.96, zorder=2))

    rounded_box(ax, 0.185, 0.155, 0.18, 0.145, p["left_fill"], p["input"], lw=1.8, radius=0.018, z=4)
    rounded_box(ax, 0.635, 0.155, 0.18, 0.145, p["right_fill"], p["output"], lw=1.8, radius=0.018, z=4)

    arrow(ax, (0.115, 0.235), (0.185, 0.235), p["input"], lw=2.8, scale=21, z=3)
    arrow(ax, (0.815, 0.235), (0.885, 0.235), p["output"], lw=2.8, scale=21, z=3)

    mode_y = [0.297, 0.262, 0.227, 0.192, 0.157]
    left_slots = [0.284, 0.259, 0.234, 0.209, 0.184]
    right_slots = [0.284, 0.259, 0.234, 0.209, 0.184]
    rads = [0.18, 0.09, 0.0, -0.09, -0.18]
    for y0, y1, rad in zip(left_slots, mode_y, rads):
        arrow(ax, (0.365, y0), (0.485, y1), p["mode"], lw=1.85, rad=rad, scale=18, z=3, alpha=0.92)
    for y0, y1, rad in zip(mode_y, right_slots, [-r for r in rads]):
        arrow(ax, (0.515, y0), (0.635, y1), p["mode"], lw=1.85, rad=rad, scale=18, z=3, alpha=0.92)

    for y in mode_y:
        ax.add_patch(Circle((0.50, y), 0.015, facecolor=p["mode"], edgecolor=p["mode"], linewidth=1, zorder=5))

    rounded_box(ax, 0.380, 0.058, 0.240, 0.048, p["formula_fill"], "none", lw=0, radius=0.008, z=2)


def draw_panel_b_text(ax):
    txt(ax, 0.035, 0.455, "B", 19, "bold", ha="left", va="top")
    txt(ax, 0.50, 0.430, "Boundary Hankel mediation", 15.6, "bold")
    txt(ax, 0.175, 0.353, r"past inputs $u_R^-$", 11.1)
    txt(ax, 0.825, 0.353, r"future outputs $y_R^+$", 11.1)
    txt(ax, 0.50, 0.337, r"internal modes in $S$", 10.5)

    txt(ax, 0.275, 0.253, "Reachability", 12.1)
    txt(ax, 0.275, 0.225, "matrix", 12.1)
    txt(ax, 0.275, 0.188, r"$\mathcal{R}_L(S)$", 12.8)

    txt(ax, 0.725, 0.253, "Observability", 12.1)
    txt(ax, 0.725, 0.225, "matrix", 12.1)
    txt(ax, 0.725, 0.188, r"$\mathcal{O}_L(S)$", 12.8)

    txt(ax, 0.50, 0.081, r"$\mathcal{H}_L(S)=\mathcal{O}_L(S)\,\mathcal{R}_L(S)$", 12.8)
    txt(
        ax,
        0.50,
        0.018,
        "Mediation modes are jointly reachable from the remainder\nand observable through their effects on the remainder.",
        8.9,
        linespacing=0.95,
    )


def create_canvas():
    fig = plt.figure(figsize=(7.2, 6.35), facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    setup_ax(ax)
    return fig, ax


def draw_base():
    fig, ax = create_canvas()
    draw_panel_a_base(ax)
    draw_panel_b_base(ax)
    return fig, ax


def draw_final(base_path):
    fig, ax = create_canvas()
    base = mpimg.imread(base_path)
    ax.imshow(base, extent=[0, 1, 0, 1], origin="upper", zorder=0)
    draw_panel_a_text(ax)
    draw_panel_b_text(ax)
    return fig, ax


def main():
    configure_matplotlib()

    base_png = OUT / "fig1_gmw_boundary_hankel_candidateb_imagebase_20260830_arrowalign.png"
    final_pdf = OUT / "fig1_gmw_boundary_hankel_candidateb_textoverlay_20260830_arrowalign.pdf"
    final_png = OUT / "fig1_gmw_boundary_hankel_candidateb_textoverlay_20260830_arrowalign.png"

    fig, _ = draw_base()
    fig.savefig(base_png, dpi=600, facecolor="white")
    plt.close(fig)

    fig, _ = draw_final(base_png)
    fig.savefig(final_pdf, facecolor="white")
    fig.savefig(final_png, dpi=600, facecolor="white")
    plt.close(fig)

    print(base_png)
    print(final_pdf)
    print(final_png)


if __name__ == "__main__":
    main()
