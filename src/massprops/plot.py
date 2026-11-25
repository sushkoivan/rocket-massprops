"""Optional plotting (requires matplotlib: ``pip install rocket-massprops[plot]``)."""

from __future__ import annotations

from .model import Vehicle


def plot_fill_curves(vehicle: Vehicle, path: str, n: int = 41) -> None:
    """Save CG (and pivot -> CG lever arm, if a pivot exists) versus fill fraction."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fills = [i / (n - 1) for i in range(n)]
    states = vehicle.table(fills)
    pct = [f * 100 for f in fills]

    fig, ax = plt.subplots(figsize=(7, 4), dpi=130)
    ax.plot(pct, [s.cg for s in states], color="#1f77b4", lw=2, label="CG station z_cg")
    ax.set_xlabel("usable propellant remaining [%]")
    ax.set_ylabel("z [m]")
    ax.invert_xaxis()  # time runs left -> right: full at the left, empty at the right
    if vehicle.pivot_z is not None:
        ax.plot(pct, [s.lever_arm for s in states], color="#d62728", lw=2, ls="--",
                label="lever arm (pivot -> CG)")
    ax2 = ax.twinx()
    ax2.plot(pct, [s.inertia_transverse for s in states], color="#7f7f7f", lw=1.5, ls=":",
             label="pitch inertia about CG")
    ax2.set_ylabel("I_pitch [kg m^2]")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="best", fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_title(f"{vehicle.name}: mass properties as the tanks drain", fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
