from __future__ import annotations

import pytest

from lunapath_ros.route_progress import energy_used_from_soc_wh, integrate_displacement_m, polyline_length_m


def test_polyline_and_displacement_use_map_metres():
    assert polyline_length_m([(0.0, 0.0), (3.0, 4.0), (3.0, 8.0)]) == pytest.approx(9.0)
    travelled, previous = integrate_displacement_m(0.0, None, (0.0, 0.0))
    travelled, _ = integrate_displacement_m(travelled, previous, (3.0, 4.0))
    assert travelled == pytest.approx(5.0)


def test_soc_energy_is_conservative_while_charging():
    assert energy_used_from_soc_wh(100.0, 80.0, 500.0) == pytest.approx(100.0)
    assert energy_used_from_soc_wh(80.0, 90.0, 500.0) == 0.0
