import datetime

import pytest
from dateutil.parser import parse

from eof.client import OrbitType
from eof.dataspace_client import DataspaceClient
from eof.products import Sentinel


@pytest.mark.vcr
def test_dataspace_query_orbit():
    # Non-regression test for query_orbit
    dt = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    mission = "S1A"
    c = DataspaceClient()
    results = c.query_orbit(dt-DataspaceClient.T0, dt+DataspaceClient.T1, mission, product_type="AUX_POEORB")
    assert len(results) == 1
    r = results[0]
    assert r["Id"] == "21db46df-3991-4700-a454-dd91b6f2217a"
    assert parse(r["ContentDate"]["End"]) > dt
    assert parse(r["ContentDate"]["Start"]) < dt


@pytest.mark.vcr
def test_dataspace_query_orbit_by_dt():
    dt = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    mission = "S1A"
    c = DataspaceClient()
    # Restituted seems to fail for old dates...
    # Need to look into sentinelsat, or if ESA has just stopped allowing it
    results = c.query_orbit_by_dt([dt], [mission], orbit_type=OrbitType.precise)
    assert len(results) == 1
    r = results[0]
    assert r["Id"] == "21db46df-3991-4700-a454-dd91b6f2217a"
    assert parse(r["ContentDate"]["End"]) > dt
    assert parse(r["ContentDate"]["Start"]) < dt


@pytest.mark.vcr
def test_dataspace_query_orbit_by_dt_range():
    dt1 = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    dt2 = datetime.datetime(2020, 1, 12, tzinfo=datetime.timezone.utc)
    mission = "S1A"
    c = DataspaceClient()
    # Restituted seems to fail for old dates...
    # Need to look into sentinelsat, or if ESA has just stopped allowing it
    results = c.query_orbits_by_dt_range(dt1, dt2, [mission], orbit_type=OrbitType.precise)
    assert len(results) == 13  # 13 days
    for r in results:
        assert parse(r["ContentDate"]["End"]) >= dt1
        assert parse(r["ContentDate"]["Start"]) <= dt2
    r = results[0]
    assert r["Id"] == "21db46df-3991-4700-a454-dd91b6f2217a"


@pytest.mark.skip("Dataspace stopped carrying resorbs older than 3 months")
@pytest.mark.vcr
def test_query_resorb_edge_case():
    p = Sentinel(
        "S1A_IW_SLC__1SDV_20230823T154908_20230823T154935_050004_060418_521B.zip"
    )

    client = DataspaceClient()

    results = client.query_orbit_by_dt(
        [p.start_time], [p.mission], orbit_type=OrbitType.restituted
    )
    assert "702fa0e1-22db-4d20-ab26-0499f262d550" in results
    r = results["702fa0e1-22db-4d20-ab26-0499f262d550"]
    assert (
        r["title"]
        == "S1A_OPER_AUX_RESORB_OPOD_20230823T174849_V20230823T141024_20230823T172754"
    )
