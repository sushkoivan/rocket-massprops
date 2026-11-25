"""Core stick model: components, propellant tanks and the vehicle.

Coordinate system
-----------------
``z`` is the axial station in metres, measured along the vehicle axis and
increasing *upward* (towards the nose). The origin is arbitrary -- the ground
under the landing legs for a hopper, the aft end of the body tube for a
sounding rocket -- but it must be the same for every item.

Model in one paragraph
----------------------
Every item is an axisymmetric segment between ``z_bottom`` and ``z_top`` whose
mass is spread uniformly along that length. Dry items keep their position.
Propellant is either a liquid column resting on the bottom of its tank (the
vehicle accelerates upward, so the liquid settles aft) whose height shrinks
in proportion to the remaining mass, or -- for a solid grain -- mass that
depletes uniformly over the whole tank length. Vehicle mass, centre of
gravity (CG) and moments of inertia are sums over the segments, with the
parallel-axis theorem moving each segment's own inertia to the vehicle CG.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, List, Optional, Sequence, Union

G0 = 9.80665  # m/s^2, standard gravity

SHAPES = ("solid", "tube")
DEPLETION_MODES = ("column", "uniform")

#: Typical growth allowance per maturity level. Not applied automatically --
#: it is a convenience for filling in ``Component.growth`` (see README).
MATURITY_GROWTH: Dict[str, float] = {
    "estimate": 0.15,
    "cad": 0.08,
    "weighed": 0.03,
}


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Component:
    """A dry item with a fixed mass and axial extent.

    Parameters
    ----------
    name:      unique label.
    mass:      basic mass [kg] *without* growth allowance.
    z_bottom:  lower end of the item [m].
    z_top:     upper end of the item [m]; equal to ``z_bottom`` for a point mass.
    radius:    radius used for the item's own inertia [m]. ``None`` means
               "use the vehicle radius". ``0`` makes the item a line/point mass.
    growth:    growth allowance as a fraction (0.15 = +15 %). Added at the
               item's own location, so it never shifts the CG artificially.
    maturity:  free-text label ("estimate", "cad", "weighed", ...), used for
               the maturity summary only.
    shape:     ``"solid"`` cylinder or thin-walled ``"tube"`` (inertia formula).
    """

    name: str
    mass: float
    z_bottom: float
    z_top: float
    radius: Optional[float] = None
    growth: float = 0.0
    maturity: str = "estimate"
    shape: str = "solid"

    def __post_init__(self) -> None:
        _check_extent(self.name, self.z_bottom, self.z_top)
        if self.mass < 0:
            raise ValueError(f"{self.name}: mass must be >= 0")
        if self.growth < 0:
            raise ValueError(f"{self.name}: growth must be >= 0")
        if self.radius is not None and self.radius < 0:
            raise ValueError(f"{self.name}: radius must be >= 0")
        if self.shape not in SHAPES:
            raise ValueError(f"{self.name}: shape must be one of {SHAPES}")

    @property
    def mass_with_growth(self) -> float:
        return self.mass * (1.0 + self.growth)


@dataclass(frozen=True)
class PropellantTank:
    """Propellant load inside a tank (the tank *structure* is a separate Component).

    Parameters
    ----------
    name:            unique label.
    mass_full:       propellant mass loaded at lift-off [kg].
    z_bottom, z_top: inner extent of the tank [m].
    density:         propellant density [kg/m^3]; together with ``inner_radius``
                     it sets the height of the full liquid column.
    inner_radius:    tank inner radius [m]; also used for the liquid's own
                     inertia. ``None`` = vehicle radius.
    full_column_fraction:
                     alternative to ``density``: full liquid height as a
                     fraction of the tank length (useful for domed or
                     irregular tanks where you know the fill level from CAD).
                     If neither is given the full load fills the whole tank.
    residual_fraction:
                     fraction of ``mass_full`` that is unusable and stays on
                     board at fill = 0 (trapped liquid, ullage margin, ...).
    depletion:       ``"column"`` (liquid settles at the tank bottom, the
                     default) or ``"uniform"`` (mass is lost evenly over the
                     tank length, e.g. a core-burning solid grain).
    """

    name: str
    mass_full: float
    z_bottom: float
    z_top: float
    density: Optional[float] = None
    inner_radius: Optional[float] = None
    full_column_fraction: Optional[float] = None
    residual_fraction: float = 0.0
    depletion: str = "column"

    def __post_init__(self) -> None:
        _check_extent(self.name, self.z_bottom, self.z_top)
        if self.mass_full < 0:
            raise ValueError(f"{self.name}: mass_full must be >= 0")
        if not 0.0 <= self.residual_fraction < 1.0:
            raise ValueError(f"{self.name}: residual_fraction must be in [0, 1)")
        if self.depletion not in DEPLETION_MODES:
            raise ValueError(f"{self.name}: depletion must be one of {DEPLETION_MODES}")
        if self.density is not None and self.full_column_fraction is not None:
            raise ValueError(f"{self.name}: give density OR full_column_fraction, not both")
        if self.density is not None and self.density <= 0:
            raise ValueError(f"{self.name}: density must be > 0")
        if self.full_column_fraction is not None and not 0.0 < self.full_column_fraction <= 1.0:
            raise ValueError(f"{self.name}: full_column_fraction must be in (0, 1]")

    @property
    def length(self) -> float:
        return self.z_top - self.z_bottom

    def remaining_fraction(self, fill: float) -> float:
        """Propellant on board as a fraction of ``mass_full``.

        ``k = r + (1 - r) * fill`` with r = residual fraction: fill = 1 is the
        full load, fill = 0 leaves only the residual.
        """
        _check_fill(fill)
        r = self.residual_fraction
        return r + (1.0 - r) * fill

    def full_column_height(self, inner_radius: float) -> float:
        """Height of the liquid column when the tank holds ``mass_full`` [m]."""
        if self.full_column_fraction is not None:
            return self.full_column_fraction * self.length
        if self.density is None:
            return self.length
        if inner_radius <= 0:
            raise ValueError(f"{self.name}: density needs an inner_radius > 0")
        h = self.mass_full / (self.density * math.pi * inner_radius ** 2)
        if h > self.length * (1.0 + 1e-9):
            raise ValueError(
                f"{self.name}: {self.mass_full} kg at {self.density} kg/m^3 needs a "
                f"{h:.3f} m column but the tank is only {self.length:.3f} m long"
            )
        return min(h, self.length)


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Segment:
    """Resolved mass element at one fill fraction (what the sums run over)."""

    name: str
    mass: float
    z_bottom: float
    z_top: float
    radius: float
    shape: str
    is_propellant: bool

    @property
    def length(self) -> float:
        return self.z_top - self.z_bottom

    @property
    def z_mid(self) -> float:
        return 0.5 * (self.z_bottom + self.z_top)

    def own_transverse_inertia(self) -> float:
        """Inertia about a transverse axis through the segment's own centre.

        solid cylinder:      m (L^2/12 + r^2/4)
        thin-walled tube:    m (L^2/12 + r^2/2)
        """
        k = 0.25 if self.shape == "solid" else 0.5
        return self.mass * (self.length ** 2 / 12.0 + k * self.radius ** 2)

    def roll_inertia(self) -> float:
        """Inertia about the vehicle (z) axis: m r^2/2 solid, m r^2 tube."""
        k = 0.5 if self.shape == "solid" else 1.0
        return self.mass * k * self.radius ** 2


@dataclass(frozen=True)
class State:
    """Mass properties at one fill fraction."""

    fill: float
    mass: float
    dry_mass: float
    propellant_mass: float
    cg: float
    inertia_transverse: float
    inertia_roll: float
    lever_arm: Optional[float]

    @property
    def radius_of_gyration(self) -> float:
        return math.sqrt(self.inertia_transverse / self.mass) if self.mass > 0 else 0.0


@dataclass(frozen=True)
class Authority:
    """Control authority of a gimballed engine at one fill and deflection."""

    fill: float
    mass: float
    thrust: float
    deflection_deg: float
    side_force: float          # N     T sin(delta)
    lever_arm: float           # m     pivot -> CG
    moment: float              # N m   T sin(delta) * lever
    inertia_transverse: float  # kg m^2 about the CG
    angular_accel: float       # rad/s^2  M / I
    lateral_accel: float       # m/s^2    T sin(delta) / m
    thrust_to_weight: float    # -        T / (m g0)

    @property
    def angular_accel_deg(self) -> float:
        return math.degrees(self.angular_accel)


# --------------------------------------------------------------------------- #
# Vehicle
# --------------------------------------------------------------------------- #
@dataclass
class Vehicle:
    """A vertical rocket described as a stack of axisymmetric segments.

    Parameters
    ----------
    components:     dry items.
    tanks:          propellant loads. All tanks drain *proportionally*: one
                    fill fraction applies to every tank.
    radius:         default radius [m] for items that do not give their own.
    pivot_z:        gimbal pivot station [m] (``None`` for vehicles without TVC).
    name:           label used in reports.
    include_growth: apply each component's growth allowance (switch it off to
                    see the basic mass).
    """

    components: List[Component] = field(default_factory=list)
    tanks: List[PropellantTank] = field(default_factory=list)
    radius: float = 0.0
    pivot_z: Optional[float] = None
    name: str = "vehicle"
    include_growth: bool = True

    def __post_init__(self) -> None:
        self.components = list(self.components)
        self.tanks = list(self.tanks)
        if self.radius < 0:
            raise ValueError("radius must be >= 0")
        names = [c.name for c in self.components] + [t.name for t in self.tanks]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate item names: {', '.join(dupes)}")

    # ---- resolution ------------------------------------------------------- #
    def segments(self, fill: float = 1.0) -> List[Segment]:
        """All mass elements at a fill fraction (0 = residuals only, 1 = full)."""
        _check_fill(fill)
        out: List[Segment] = []
        for c in self.components:
            m = c.mass_with_growth if self.include_growth else c.mass
            r = self.radius if c.radius is None else c.radius
            out.append(Segment(c.name, m, c.z_bottom, c.z_top, r, c.shape, False))
        for t in self.tanks:
            k = t.remaining_fraction(fill)
            r = self.radius if t.inner_radius is None else t.inner_radius
            if t.depletion == "column":
                h = t.full_column_height(r) * k
                zb, zt = t.z_bottom, t.z_bottom + h
            else:  # uniform: mass shrinks, extent and CG stay put
                zb, zt = t.z_bottom, t.z_top
            out.append(Segment(t.name, t.mass_full * k, zb, zt, r, "solid", True))
        return out

    # ---- scalar properties ----------------------------------------------- #
    def mass(self, fill: float = 1.0) -> float:
        """Total mass [kg]:  m = sum(m_i)."""
        return sum(s.mass for s in self.segments(fill))

    def dry_mass(self) -> float:
        """Mass without any propellant (not even residuals) [kg]."""
        return sum(s.mass for s in self.segments(0.0) if not s.is_propellant)

    def propellant_mass(self, fill: float = 1.0) -> float:
        return sum(s.mass for s in self.segments(fill) if s.is_propellant)

    def cg(self, fill: float = 1.0) -> float:
        """CG station [m]:  z_cg = sum(m_i z_mid,i) / sum(m_i)."""
        segs = self.segments(fill)
        m = sum(s.mass for s in segs)
        if m <= 0:
            raise ValueError("vehicle has no mass")
        return sum(s.mass * s.z_mid for s in segs) / m

    def inertia_transverse(self, fill: float = 1.0) -> float:
        """Pitch/yaw inertia about the CG [kg m^2]:
        I = sum[ I_own,i + m_i (z_mid,i - z_cg)^2 ]   (parallel-axis theorem)."""
        segs = self.segments(fill)
        zc = self.cg(fill)
        return sum(s.own_transverse_inertia() + s.mass * (s.z_mid - zc) ** 2 for s in segs)

    def inertia_roll(self, fill: float = 1.0) -> float:
        """Roll inertia about the vehicle axis [kg m^2]: sum of k m_i r_i^2."""
        return sum(s.roll_inertia() for s in self.segments(fill))

    def lever_arm(self, fill: float = 1.0) -> float:
        """Distance gimbal pivot -> CG [m] (positive when the CG is above the pivot)."""
        if self.pivot_z is None:
            raise ValueError(f"{self.name}: no pivot_z defined (vehicle has no gimbal)")
        return self.cg(fill) - self.pivot_z

    # ---- tables ------------------------------------------------------------ #
    def state(self, fill: float = 1.0) -> State:
        segs = self.segments(fill)
        return State(
            fill=fill,
            mass=sum(s.mass for s in segs),
            dry_mass=sum(s.mass for s in segs if not s.is_propellant),
            propellant_mass=sum(s.mass for s in segs if s.is_propellant),
            cg=self.cg(fill),
            inertia_transverse=self.inertia_transverse(fill),
            inertia_roll=self.inertia_roll(fill),
            lever_arm=None if self.pivot_z is None else self.lever_arm(fill),
        )

    def table(self, fills: Iterable[float] = (1.0, 0.75, 0.5, 0.25, 0.0)) -> List[State]:
        """Mass properties at each fill fraction."""
        return [self.state(f) for f in fills]

    def control_authority(
        self,
        thrust: Optional[float] = None,
        deflections_deg: Sequence[float] = (1.0, 5.0, 10.0),
        fill: float = 1.0,
    ) -> List[Authority]:
        """Rigid-body response to a gimbal deflection delta.

        The thrust line passes through the pivot. Its perpendicular distance
        to the CG is ``lever * sin(delta)``, hence

            M     = T sin(delta) * lever          [N m]
            alpha = M / I_cg                      [rad/s^2]
            a_lat = T sin(delta) / m              [m/s^2]

        ``thrust=None`` means hover thrust, T = m g0 at this fill.
        """
        st = self.state(fill)
        if st.lever_arm is None:
            raise ValueError(f"{self.name}: no pivot_z defined (vehicle has no gimbal)")
        T = st.mass * G0 if thrust is None else float(thrust)
        rows = []
        for d in deflections_deg:
            fs = T * math.sin(math.radians(d))
            mom = fs * st.lever_arm
            rows.append(
                Authority(
                    fill=fill,
                    mass=st.mass,
                    thrust=T,
                    deflection_deg=float(d),
                    side_force=fs,
                    lever_arm=st.lever_arm,
                    moment=mom,
                    inertia_transverse=st.inertia_transverse,
                    angular_accel=mom / st.inertia_transverse,
                    lateral_accel=fs / st.mass,
                    thrust_to_weight=T / (st.mass * G0),
                )
            )
        return rows

    # ---- what-if ----------------------------------------------------------- #
    def item(self, name: str) -> Union[Component, PropellantTank]:
        for x in list(self.components) + list(self.tanks):
            if x.name == name:
                return x
        raise KeyError(f"no component or tank named {name!r}")

    def with_mass(self, name: str, new_mass: float) -> "Vehicle":
        """Copy of the vehicle with one item's basic mass (or tank load) replaced."""
        self.item(name)  # raises KeyError if unknown
        comps = [replace(c, mass=new_mass) if c.name == name else c for c in self.components]
        tanks = [replace(t, mass_full=new_mass) if t.name == name else t for t in self.tanks]
        return replace(self, components=comps, tanks=tanks)

    def sensitivity(
        self, component: str, delta: float, fills: Sequence[float] = (1.0, 0.0)
    ) -> List[Dict[str, float]]:
        """Change in mass, CG, lever arm and inertia when ``component`` gains ``delta`` kg.

        Returns one dict per fill with keys ``fill, d_mass, d_cg, d_lever,
        d_inertia`` (``d_lever`` is NaN without a pivot).
        """
        it = self.item(component)
        base_mass = it.mass if isinstance(it, Component) else it.mass_full
        other = self.with_mass(component, base_mass + delta)
        out = []
        for f in fills:
            a, b = self.state(f), other.state(f)
            out.append(
                {
                    "fill": f,
                    "d_mass": b.mass - a.mass,
                    "d_cg": b.cg - a.cg,
                    "d_lever": (b.lever_arm - a.lever_arm)
                    if a.lever_arm is not None
                    else float("nan"),
                    "d_inertia": b.inertia_transverse - a.inertia_transverse,
                }
            )
        return out

    def maturity_summary(self) -> Dict[str, float]:
        """Basic dry mass (no growth) per maturity label [kg]."""
        out: Dict[str, float] = {}
        for c in self.components:
            out[c.maturity] = out.get(c.maturity, 0.0) + c.mass
        return out

    def growth_mass(self) -> float:
        """Total growth allowance currently carried [kg]."""
        if not self.include_growth:
            return 0.0
        return sum(c.mass_with_growth - c.mass for c in self.components)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _check_extent(name: str, zb: float, zt: float) -> None:
    if zt < zb:
        raise ValueError(f"{name}: z_top ({zt}) is below z_bottom ({zb})")


def _check_fill(fill: float) -> None:
    if not 0.0 <= fill <= 1.0:
        raise ValueError(f"fill must be within [0, 1], got {fill}")
