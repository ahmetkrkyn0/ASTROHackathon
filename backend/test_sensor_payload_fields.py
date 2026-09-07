"""Rover catalogue sensor-payload field tests."""

from __future__ import annotations

from app.constants import ROVERS, get_rover, rover_catalog


def test_every_rover_declares_sensor_fields():
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        assert "sensor_payload_w" in rover
        assert "sensor_heater_w" in rover


def test_baseline_rovers_carry_no_sensor_payload_by_default():
    """Existing profiles are LiDAR-less until Task 3 builds a variant."""
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        assert rover["sensor_payload_w"] is None
        assert rover["sensor_heater_w"] is None


def test_rover_catalog_exposes_sensor_fields():
    catalog = rover_catalog()
    assert len(catalog) == len(ROVERS)
    for entry in catalog:
        assert "sensor_payload_w" in entry
        assert "sensor_heater_w" in entry
