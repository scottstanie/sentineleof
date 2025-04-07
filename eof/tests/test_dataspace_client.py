import datetime

import pytest
from dateutil.parser import parse

from eof.dataspace_client import DataspaceClient
from eof.products import Sentinel


@pytest.mark.vcr
def test_scihub_query_orbit_by_dt():
    dt = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    mission = "S1A"
    c = DataspaceClient()
    # Restituted seems to fail for old dates...
    # Need to look into sentinelsat, or if ESA has just stopped allowing it
    results = c.query_orbit_by_dt([dt], [mission], orbit_type="precise")
    assert len(results) == 1
    r = results[0]
    assert r["Id"] == "21db46df-3991-4700-a454-dd91b6f2217a"
    assert parse(r["ContentDate"]["End"]) > dt
    assert parse(r["ContentDate"]["Start"]) < dt


@pytest.mark.skip("Dataspace stopped carrying resorbs older than 3 months")
def test_query_resorb_edge_case():
    p = Sentinel(
        "S1A_IW_SLC__1SDV_20230823T154908_20230823T154935_050004_060418_521B.zip"
    )

    client = DataspaceClient()

    results = client.query_orbit_by_dt(
        [p.start_time], [p.mission], orbit_type="restituted"
    )
    assert "702fa0e1-22db-4d20-ab26-0499f262d550" in results
    r = results["702fa0e1-22db-4d20-ab26-0499f262d550"]
    assert (
        r["title"]
        == "S1A_OPER_AUX_RESORB_OPOD_20230823T174849_V20230823T141024_20230823T172754"
    )


@pytest.mark.vcr
def test_query_resorb_s1_reader_issue68():
    f = "S1A_IW_SLC__1SDV_20250310T204228_20250310T204253_058247_0732D8_1AA3"

    client = DataspaceClient()
    query = client.query_orbit_for_product(f, orbit_type="restituted")
    assert len(query) == 1
    expected = (
        "S1A_OPER_AUX_RESORB_OPOD_20250310T220905_V20250310T180852_20250310T212622.EOF"
    )
    assert query[0]["Name"] == expected
