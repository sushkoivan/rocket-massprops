"""Command-line interface: ``python -m massprops vehicle.json [options]``."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

from . import __version__
from .io import load_vehicle, write_csv
from .model import Vehicle


def _floats(text: str) -> List[float]:
    try:
        return [float(x) for x in text.split(",") if x.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected comma-separated numbers, got {text!r}")


def _print_table(headers: Sequence[str], rows: Sequence[Sequence[str]], out) -> None:
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
              for i, h in enumerate(headers)]
    print("  ".join(h.rjust(w) for h, w in zip(headers, widths)), file=out)
    print("  ".join("-" * w for w in widths), file=out)
    for r in rows:
        print("  ".join(c.rjust(w) for c, w in zip(r, widths)), file=out)


def _components(v: Vehicle, out) -> None:
    rows = []
    for c in v.components:
        m = c.mass_with_growth if v.include_growth else c.mass
        rows.append([c.name, f"{c.mass:.3f}", f"{c.growth * 100:.0f}" if v.include_growth else "-",
                     f"{m:.3f}", f"{c.z_bottom:.3f}", f"{c.z_top:.3f}", c.maturity, c.shape])
    for t in v.tanks:
        rows.append([t.name, f"{t.mass_full:.3f}", "-", f"{t.mass_full:.3f}", f"{t.z_bottom:.3f}",
                     f"{t.z_top:.3f}", f"prop, res {t.residual_fraction * 100:.0f}%", t.depletion])
    _print_table(["item", "m [kg]", "growth %", "m+gr [kg]", "z_bot [m]", "z_top [m]",
                  "maturity", "model"], rows, out)


def main(argv: Optional[Sequence[str]] = None, out=None) -> int:
    out = out or sys.stdout
    p = argparse.ArgumentParser(
        prog="massprops",
        description="Mass, CG and inertia budget of a vertical rocket vs propellant fill.",
    )
    p.add_argument("vehicle", help="vehicle definition (JSON)")
    p.add_argument("--fills", type=_floats, default=[1.0, 0.75, 0.5, 0.25, 0.0],
                   help="fill fractions of usable propellant, e.g. 1,0.5,0 (default 1,.75,.5,.25,0)")
    p.add_argument("--thrust", type=float, default=None,
                   help="thrust [N] for the control-authority table (default: hover, T = m g0)")
    p.add_argument("--gimbal", type=_floats, default=None,
                   help="gimbal deflections [deg], e.g. 5,10,15 (needs pivot_z in the file)")
    p.add_argument("--no-growth", action="store_true", help="ignore growth allowances")
    p.add_argument("--components", action="store_true", help="also print the component table")
    p.add_argument("--csv", metavar="PATH", help="write the tables to CSV")
    p.add_argument("--plot", metavar="PATH", help="save CG / lever arm vs fill plot (needs matplotlib)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = p.parse_args(argv)

    v = load_vehicle(a.vehicle)
    if a.no_growth:
        v.include_growth = False

    print(f"{v.name}: dry {v.dry_mass():.2f} kg (growth {v.growth_mass():.2f} kg incl.), "
          f"propellant {v.propellant_mass(1.0):.2f} kg, radius {v.radius:.3f} m"
          + (f", pivot z = {v.pivot_z:.3f} m" if v.pivot_z is not None else ", no gimbal"),
          file=out)

    if a.components:
        print(file=out)
        _components(v, out)

    states = v.table(a.fills)
    has_pivot = v.pivot_z is not None
    rows = []
    for s in states:
        r = [f"{s.fill:.2f}", f"{s.mass:.2f}", f"{s.propellant_mass:.2f}", f"{s.cg:.4f}",
             f"{s.inertia_transverse:.3f}", f"{s.inertia_roll:.4f}"]
        if has_pivot:
            r.append(f"{s.lever_arm:.4f}")
        rows.append(r)
    headers = ["fill", "m [kg]", "prop [kg]", "z_cg [m]", "I_pitch [kg m2]", "I_roll [kg m2]"]
    if has_pivot:
        headers.append("lever [m]")
    print(file=out)
    _print_table(headers, rows, out)

    authority = []
    if a.gimbal or a.thrust is not None:
        if not has_pivot:
            print("\n(no pivot_z in the vehicle file -> control-authority table skipped)", file=out)
        else:
            defl = a.gimbal or [1.0, 5.0, 10.0]
            for f in a.fills:
                authority.extend(v.control_authority(a.thrust, defl, f))
            thrust_txt = "hover T = m g0" if a.thrust is None else f"T = {a.thrust:g} N"
            print(f"\nControl authority ({thrust_txt}; M = T sin(delta) * lever)", file=out)
            _print_table(
                ["fill", "T [N]", "T/W", "delta [deg]", "F_side [N]", "M [N m]",
                 "alpha [deg/s2]", "a_lat [m/s2]"],
                [[f"{x.fill:.2f}", f"{x.thrust:.1f}", f"{x.thrust_to_weight:.2f}",
                  f"{x.deflection_deg:g}", f"{x.side_force:.1f}", f"{x.moment:.2f}",
                  f"{x.angular_accel_deg:.1f}", f"{x.lateral_accel:.2f}"] for x in authority],
                out,
            )

    if a.csv:
        write_csv(a.csv, states, authority)
        print(f"\nwrote {a.csv}", file=out)

    if a.plot:
        from .plot import plot_fill_curves

        try:
            plot_fill_curves(v, a.plot)
        except ImportError:
            print("\nmatplotlib is not installed: pip install rocket-massprops[plot]", file=sys.stderr)
            return 2
        print(f"wrote {a.plot}", file=out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
