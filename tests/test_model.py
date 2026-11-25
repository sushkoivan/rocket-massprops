"""Checks against closed-form results."""

import math

import pytest

from massprops import G0, Component, PropellantTank, Vehicle

REL = 1e-12


def rod(m=4.0, zb=1.0, zt=3.0, r=0.1, shape="solid"):
    return Vehicle([Component("rod", m, zb, zt, radius=r, shape=shape)])


def test_uniform_rod_cg_is_midpoint():
    assert rod().cg() == pytest.approx(2.0, rel=REL)


def test_uniform_solid_rod_inertia():
    m, L, r = 4.0, 2.0, 0.1
    assert rod().inertia_transverse() == pytest.approx(m * (L**2 / 12 + r**2 / 4), rel=REL)
    assert rod().inertia_roll() == pytest.approx(m * r**2 / 2, rel=REL)


def test_thin_tube_inertia():
    m, L, r = 4.0, 2.0, 0.1
    v = rod(shape="tube")
    assert v.inertia_transverse() == pytest.approx(m * (L**2 / 12 + r**2 / 2), rel=REL)
    assert v.inertia_roll() == pytest.approx(m * r**2, rel=REL)


def test_vehicle_radius_used_when_component_has_none():
    v = Vehicle([Component("rod", 2.0, 0.0, 1.0)], radius=0.2)
    assert v.inertia_roll() == pytest.approx(2.0 * 0.2**2 / 2, rel=REL)


def test_two_point_masses_cg_and_parallel_axis():
    m1, m2, z1, z2 = 3.0, 1.0, 0.0, 2.0
    v = Vehicle([Component("a", m1, z1, z1, radius=0.0), Component("b", m2, z2, z2, radius=0.0)])
    assert v.cg() == pytest.approx((m1 * z1 + m2 * z2) / (m1 + m2), rel=REL)
    # reduced-mass form of the parallel-axis theorem
    assert v.inertia_transverse() == pytest.approx(m1 * m2 / (m1 + m2) * (z2 - z1) ** 2, rel=REL)


def test_split_rod_equals_whole_rod():
    whole = rod(m=4.0, zb=0.0, zt=2.0)
    halves = Vehicle([Component("lo", 2.0, 0.0, 1.0, radius=0.1),
                      Component("hi", 2.0, 1.0, 2.0, radius=0.1)])
    assert halves.cg() == pytest.approx(whole.cg(), rel=REL)
    assert halves.inertia_transverse() == pytest.approx(whole.inertia_transverse(), rel=REL)


def test_growth_applied_at_own_location():
    base = Vehicle([Component("a", 2.0, 0.0, 1.0, growth=0.5)])
    assert base.mass() == pytest.approx(3.0)
    assert base.cg() == pytest.approx(0.5)
    base.include_growth = False
    assert base.mass() == pytest.approx(2.0)


def tank_vehicle(residual=0.1, density=1000.0, r=0.1, mass_full=10.0):
    return Vehicle(
        [Component("structure", 5.0, 0.0, 2.0, radius=r)],
        [PropellantTank("liquid", mass_full, 0.0, 1.0, density=density, inner_radius=r,
                        residual_fraction=residual)],
        radius=r,
    )


def test_fill_zero_leaves_residual():
    v = tank_vehicle(residual=0.1)
    assert v.propellant_mass(0.0) == pytest.approx(1.0)
    assert v.propellant_mass(1.0) == pytest.approx(10.0)
    assert v.propellant_mass(0.5) == pytest.approx(1.0 + 0.9 * 0.5 * 10.0)
    assert v.dry_mass() == pytest.approx(5.0)


def test_liquid_column_height_from_density():
    v = tank_vehicle(residual=0.0)
    h_full = 10.0 / (1000.0 * math.pi * 0.1**2)
    seg = [s for s in v.segments(1.0) if s.is_propellant][0]
    assert seg.z_top == pytest.approx(h_full)
    seg = [s for s in v.segments(0.5) if s.is_propellant][0]
    assert seg.z_top == pytest.approx(0.5 * h_full)


def test_liquid_that_does_not_fit_raises():
    with pytest.raises(ValueError, match="column"):
        tank_vehicle(mass_full=100.0).segments(1.0)


def test_cg_moves_monotonically_when_bottom_tank_drains():
    # Tank sits entirely below the structure's CG, so the liquid surface never
    # crosses the vehicle CG and dz_cg/dm keeps one sign.
    v = Vehicle(
        [Component("structure", 20.0, 1.0, 3.0, radius=0.1)],
        [PropellantTank("liquid", 10.0, 0.0, 1.0, full_column_fraction=0.9, inner_radius=0.1)],
    )
    cgs = [v.cg(f / 20) for f in range(21)]  # fill 0 -> 1
    assert all(b < a for a, b in zip(cgs, cgs[1:]))  # fuller tank -> lower CG


def test_uniform_depletion_keeps_propellant_cg_fixed():
    v = Vehicle([], [PropellantTank("grain", 4.0, 0.2, 1.0, residual_fraction=0.0,
                                    depletion="uniform")], radius=0.05)
    assert v.cg(1.0) == pytest.approx(0.6)
    assert v.cg(0.3) == pytest.approx(0.6)


def test_lever_arm_and_control_moment():
    v = Vehicle([Component("body", 10.0, 0.0, 2.0, radius=0.1)], pivot_z=0.2)
    lever = v.lever_arm()
    assert lever == pytest.approx(0.8)
    T = 275.0
    rows = v.control_authority(T, [0.0, 7.0, 30.0])
    for r in rows:
        s = math.sin(math.radians(r.deflection_deg))
        assert r.moment == pytest.approx(T * s * lever, rel=REL)
        assert r.angular_accel == pytest.approx(T * s * lever / v.inertia_transverse(), rel=REL)
        assert r.lateral_accel == pytest.approx(T * s / 10.0, rel=REL)


def test_hover_thrust_default():
    v = Vehicle([Component("body", 10.0, 0.0, 2.0, radius=0.1)], pivot_z=0.2)
    (row,) = v.control_authority(None, [5.0])
    assert row.thrust == pytest.approx(10.0 * G0)
    assert row.thrust_to_weight == pytest.approx(1.0)


def test_no_pivot_raises():
    v = rod()
    with pytest.raises(ValueError, match="pivot"):
        v.lever_arm()
    with pytest.raises(ValueError, match="pivot"):
        v.control_authority(100.0, [5.0])
    assert v.state().lever_arm is None


def test_sensitivity_matches_hand_calc():
    # adding dm at z_mid = 1.5 to a 2 kg body centred at 0.5
    v = Vehicle([Component("body", 2.0, 0.0, 1.0), Component("top", 0.0, 1.0, 2.0)], pivot_z=0.0)
    (row,) = v.sensitivity("top", 2.0, fills=[1.0])
    assert row["d_mass"] == pytest.approx(2.0)
    assert row["d_cg"] == pytest.approx((2 * 0.5 + 2 * 1.5) / 4 - 0.5)
    assert row["d_lever"] == pytest.approx(row["d_cg"])


@pytest.mark.parametrize("fill", [-0.1, 1.5])
def test_fill_out_of_range(fill):
    with pytest.raises(ValueError):
        rod().mass(fill)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        Component("bad", 1.0, 2.0, 1.0)
    with pytest.raises(ValueError):
        PropellantTank("bad", 1.0, 0.0, 1.0, residual_fraction=1.0)
    with pytest.raises(ValueError):
        Vehicle([Component("x", 1.0, 0, 1), Component("x", 1.0, 1, 2)])
