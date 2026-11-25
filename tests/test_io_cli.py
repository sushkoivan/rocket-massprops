"""JSON round-trip, the bundled examples and the command-line interface."""

import csv
import io
import json
from pathlib import Path

import pytest

from massprops import load_vehicle, save_vehicle, vehicle_from_dict, vehicle_to_dict
from massprops.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
HOPPER = EXAMPLES / "hopper.json"
ROCKET = EXAMPLES / "sounding_rocket.json"


def test_json_round_trip(tmp_path):
    v = load_vehicle(str(HOPPER))
    out = tmp_path / "copy.json"
    save_vehicle(v, str(out))
    w = load_vehicle(str(out))
    assert vehicle_to_dict(w) == vehicle_to_dict(v)
    for f in (1.0, 0.37, 0.0):
        assert w.cg(f) == pytest.approx(v.cg(f), rel=1e-12)
        assert w.inertia_transverse(f) == pytest.approx(v.inertia_transverse(f), rel=1e-12)


def test_unknown_key_is_rejected():
    with pytest.raises(ValueError, match="unknown"):
        vehicle_from_dict({"components": [{"name": "a", "mass": 1, "z_bottom": 0, "z_top": 1,
                                           "colour": "red"}]})


@pytest.mark.parametrize("path", [HOPPER, ROCKET])
def test_examples_load_and_are_sane(path):
    v = load_vehicle(str(path))
    full, empty = v.state(1.0), v.state(0.0)
    assert full.mass > empty.mass > 0
    assert full.inertia_transverse > 0 and full.inertia_roll > 0
    with open(path, encoding="utf-8") as fh:
        assert json.load(fh)["units"] == "SI"


def run_cli(args):
    buf = io.StringIO()
    code = main(args, out=buf)
    return code, buf.getvalue()


def test_cli_hopper_with_authority_and_csv(tmp_path):
    csv_path = tmp_path / "out.csv"
    code, text = run_cli([str(HOPPER), "--fills", "1,0.5,0", "--thrust", "600",
                          "--gimbal", "5,10,15", "--csv", str(csv_path)])
    assert code == 0
    assert "lever [m]" in text and "Control authority" in text
    text.encode("ascii")  # output must be plain ASCII (Windows consoles)
    with open(csv_path, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    assert sum(r[0] == "state" for r in rows if r) == 3
    assert sum(r[0] == "authority" for r in rows if r) == 9


def test_cli_sounding_rocket_without_pivot():
    code, text = run_cli([str(ROCKET), "--gimbal", "5", "--components"])
    assert code == 0
    assert "skipped" in text and "lever" not in text


def test_cli_plot(tmp_path):
    pytest.importorskip("matplotlib")
    png = tmp_path / "plot.png"
    code, _ = run_cli([str(HOPPER), "--plot", str(png)])
    assert code == 0 and png.stat().st_size > 1000
