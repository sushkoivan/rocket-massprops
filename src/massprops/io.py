"""Load / save vehicles as JSON and write result tables as CSV (stdlib only)."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, fields
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .model import Component, PropellantTank, State, Vehicle

_COMPONENT_KEYS = {f.name for f in fields(Component)}
_TANK_KEYS = {f.name for f in fields(PropellantTank)}
_VEHICLE_KEYS = {"name", "radius", "pivot_z", "include_growth", "components", "tanks", "units",
                 "description"}


def _build(cls, data: Dict[str, Any], allowed: set, where: str):
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"{where}: unknown key(s) {sorted(unknown)}; allowed: {sorted(allowed)}")
    return cls(**data)


def vehicle_from_dict(data: Dict[str, Any]) -> Vehicle:
    """Build a :class:`Vehicle` from a plain dict (the JSON schema)."""
    unknown = set(data) - _VEHICLE_KEYS
    if unknown:
        raise ValueError(f"vehicle: unknown key(s) {sorted(unknown)}")
    units = data.get("units", "SI")
    if units != "SI":
        raise ValueError("only SI units (kg, m) are supported; set \"units\": \"SI\"")
    comps = [
        _build(Component, c, _COMPONENT_KEYS, f"components[{i}]")
        for i, c in enumerate(data.get("components", []))
    ]
    tanks = [
        _build(PropellantTank, t, _TANK_KEYS, f"tanks[{i}]")
        for i, t in enumerate(data.get("tanks", []))
    ]
    return Vehicle(
        components=comps,
        tanks=tanks,
        radius=float(data.get("radius", 0.0)),
        pivot_z=data.get("pivot_z"),
        name=data.get("name", "vehicle"),
        include_growth=bool(data.get("include_growth", True)),
    )


def _strip_defaults(obj, cls) -> Dict[str, Any]:
    d = asdict(obj)
    defaults = {f.name: f.default for f in fields(cls)}
    return {k: v for k, v in d.items() if k in ("name",) or v != defaults.get(k)}


def vehicle_to_dict(vehicle: Vehicle) -> Dict[str, Any]:
    """Inverse of :func:`vehicle_from_dict` (default-valued fields are omitted)."""
    out: Dict[str, Any] = {"name": vehicle.name, "units": "SI", "radius": vehicle.radius}
    if vehicle.pivot_z is not None:
        out["pivot_z"] = vehicle.pivot_z
    if not vehicle.include_growth:
        out["include_growth"] = False
    out["components"] = [_strip_defaults(c, Component) for c in vehicle.components]
    out["tanks"] = [_strip_defaults(t, PropellantTank) for t in vehicle.tanks]
    return out


def load_vehicle(path: str) -> Vehicle:
    """Read a vehicle definition from a JSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        return vehicle_from_dict(json.load(fh))


def save_vehicle(vehicle: Vehicle, path: str) -> None:
    """Write a vehicle definition to a JSON file."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(vehicle_to_dict(vehicle), fh, indent=2)
        fh.write("\n")


STATE_COLUMNS = ["fill", "mass_kg", "dry_mass_kg", "propellant_mass_kg", "cg_m",
                 "inertia_transverse_kgm2", "inertia_roll_kgm2", "lever_arm_m",
                 "radius_of_gyration_m"]


def state_rows(states: Iterable[State]) -> List[List[Any]]:
    rows = []
    for s in states:
        rows.append([s.fill, s.mass, s.dry_mass, s.propellant_mass, s.cg, s.inertia_transverse,
                     s.inertia_roll, "" if s.lever_arm is None else s.lever_arm,
                     s.radius_of_gyration])
    return rows


def write_csv(path: str, states: Sequence[State], authority: Optional[Sequence] = None) -> None:
    """Write the fill table (and, if given, the control-authority rows) to CSV."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["table"] + STATE_COLUMNS)
        for r in state_rows(states):
            w.writerow(["state"] + r)
        if authority:
            w.writerow([])
            w.writerow(["table", "fill", "thrust_N", "deflection_deg", "side_force_N", "lever_arm_m",
                        "moment_Nm", "angular_accel_rad_s2", "lateral_accel_m_s2",
                        "thrust_to_weight"])
            for a in authority:
                w.writerow(["authority", a.fill, a.thrust, a.deflection_deg, a.side_force,
                            a.lever_arm, a.moment, a.angular_accel, a.lateral_accel,
                            a.thrust_to_weight])
