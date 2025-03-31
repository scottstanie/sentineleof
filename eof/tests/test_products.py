from datetime import datetime
from pathlib import Path

from eof.products import Sentinel, SentinelOrbit


def test_sentinel():
    p = Sentinel(
        "S1A_IW_SLC__1SDV_20230823T154908_20230823T154935_050004_060418_521B.zip"
    )
    assert (
        p.filename
        == "S1A_IW_SLC__1SDV_20230823T154908_20230823T154935_050004_060418_521B.zip"
    )
    assert p.start_time == datetime(2023, 8, 23, 15, 49, 8)
    assert p.stop_time == datetime(2023, 8, 23, 15, 49, 35)
    assert p.relative_orbit == 57
    assert p.polarization == "DV"
    assert p.mission == "S1A"


def test_sentinel_orbit():
    p = SentinelOrbit(
        "S1A_OPER_AUX_RESORB_OPOD_20230823T174849_V20230823T141024_20230823T172754"
    )
    assert (
        p.filename
        == "S1A_OPER_AUX_RESORB_OPOD_20230823T174849_V20230823T141024_20230823T172754"
    )
    assert p.orbit_type == "restituted"
    assert p.start_time == datetime(2023, 8, 23, 14, 10, 24)
    assert p.stop_time == datetime(2023, 8, 23, 17, 27, 54)


def test_pathlib():
    p1 = SentinelOrbit(
        "S1A_OPER_AUX_RESORB_OPOD_20230823T174849_V20230823T141024_20230823T172754"
    )
    p2 = SentinelOrbit(
        Path(
            "S1A_OPER_AUX_RESORB_OPOD_20230823T174849_V20230823T141024_20230823T172754"
        )
    )
    assert p1 == p2

    p1 = Sentinel(
        "S1A_IW_SLC__1SDV_20230823T154908_20230823T154935_050004_060418_521B.zip"
    )
    p2 = Sentinel(
        Path("S1A_IW_SLC__1SDV_20230823T154908_20230823T154935_050004_060418_521B.zip")
    )
    assert p1 == p2


def test_s1c():
    fname = "S1C_IW_SLC__1SDV_20250331T060116_20250331T060143_001681_002CD0_8D44"
    p = Sentinel(fname)

    assert p.filename == fname
    assert p.start_time == datetime(2025, 3, 31, 6, 1, 16)
    assert p.stop_time == datetime(2025, 3, 31, 6, 1, 43)
    assert p.relative_orbit == 110
    assert p.polarization == "DV"
    assert p.mission == "S1C"
