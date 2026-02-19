"""
Hardware smoke tests for the IPS laser controller.

These tests validate the minimum end-to-end workflow against real hardware:
- Instantiate an `IpsLaser` controller object
- Discover a connected IPS laser via `find_ips_laser()`
- Connect to the first discovered instrument
- Disconnect cleanly

The tests are marked with `@pytest.mark.hardware` and will be skipped if no
compatible laser instrument is detected. They are intended to catch regressions
in basic connectivity (resource discovery, session open/close) rather than
validate full device functionality.
"""

import logging

import pytest

from lumed_ips.ips_control import IpsLaser

log = logging.getLogger(__name__)
pytestmark = pytest.mark.hardware


def _pick_first_resource(found: dict) -> str:
    return next(iter(found.keys()))


def test_create_laser_object():
    laser = IpsLaser()
    assert laser is not None
    assert hasattr(laser, "connect")
    assert hasattr(laser, "disconnect")
    assert hasattr(laser, "find_ips_laser")


def test_find_connect_disconnect_smoke():
    laser = IpsLaser()

    log.info("Discovering IPS laser instruments via find_ips_laser() ...")
    found = laser.find_ips_laser()

    if not found:
        pytest.skip("No IPS laser found. Plug it in and re-run this test.")

    log.info("Found %d candidate resource(s):", len(found))
    for name, meta in found.items():
        idn = (meta.get("idn") or "<no idn>").strip()
        log.info("  - %s (IDN: %s)", name, idn)

    resource_name = next(iter(found.keys()))
    log.info("Selecting first resource: %s", resource_name)

    log.info("Connecting ...")
    laser.comport = resource_name
    laser.connect()
    assert laser.isconnected is True
    log.info("Connected ✅")

    log.info("Disconnecting ...")
    laser.disconnect()
    assert laser.isconnected is False
    log.info("Disconnected ✅")
