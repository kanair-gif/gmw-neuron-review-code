from pathlib import Path

import matplotlib.pyplot as plt


OUT = Path(__file__).resolve().parents[1] / "figures_source" / "panel_labels"


def main():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    OUT.mkdir(parents=True, exist_ok=True)
    for letter in "ABCDE":
        fig = plt.figure(figsize=(0.28, 0.24), dpi=400)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.text(
            0.0,
            0.96,
            letter,
            ha="left",
            va="top",
            fontsize=13.2,
            fontweight="bold",
            color="black",
        )
        fig.savefig(OUT / f"panel_{letter}_dejavu_sans_bold.pdf", transparent=True, bbox_inches="tight", pad_inches=0)
        fig.savefig(OUT / f"panel_{letter}_dejavu_sans_bold.png", transparent=True, bbox_inches="tight", pad_inches=0, dpi=400)
        plt.close(fig)


if __name__ == "__main__":
    main()
