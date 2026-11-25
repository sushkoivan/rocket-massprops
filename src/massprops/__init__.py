"""massprops -- mass, CG and inertia budgets for small vertical rockets and VTVL hoppers."""

from .model import (
    G0,
    MATURITY_GROWTH,
    Authority,
    Component,
    PropellantTank,
    Segment,
    State,
    Vehicle,
)
from .io import load_vehicle, save_vehicle, vehicle_from_dict, vehicle_to_dict, write_csv

__version__ = "0.1.0"

__all__ = [
    "G0",
    "MATURITY_GROWTH",
    "Authority",
    "Component",
    "PropellantTank",
    "Segment",
    "State",
    "Vehicle",
    "load_vehicle",
    "save_vehicle",
    "vehicle_from_dict",
    "vehicle_to_dict",
    "write_csv",
    "__version__",
]
