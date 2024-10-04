import pytest
from eof._asf_s3 import get_orbit_files


@pytest.mark.vcr()
def test_get_orbit_files():
    """
    Test the get_orbit_files function using pytest and vcr.
    """
    precise_orbits = get_orbit_files("precise")
    restituted_orbits = get_orbit_files("restituted")

    assert len(precise_orbits) > 0, "No precise orbit files found"
    assert len(restituted_orbits) > 0, "No restituted orbit files found"
    assert all(
        orbit.startswith("AUX_POEORB") for orbit in precise_orbits
    ), "Invalid precise orbit file name"
    assert all(
        orbit.startswith("AUX_RESORB") for orbit in restituted_orbits
    ), "Invalid restituted orbit file name"
