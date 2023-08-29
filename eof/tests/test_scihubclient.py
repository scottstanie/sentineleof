import datetime

from eof.scihubclient import ScihubGnssClient
from eof.products import Sentinel


def test_query_orbit_by_dr():
    dt = datetime.datetime(2020, 1, 1)
    missions = ["S1A"]
    c = ScihubGnssClient()
    results = c.query_orbit_by_dt([dt], missions, orbit_type="restituted")
    assert len(results) == 1
    r = results["9a844886-45e7-48ec-8bc4-5d9ea91f0553"]
    assert r["endposition"] > dt
    assert r["beginposition"] < dt


def test_query_resorb_edge_case():
    p = Sentinel(
        "S1A_IW_SLC__1SDV_20230823T154908_20230823T154935_050004_060418_521B.zip"
    )

    client = ScihubGnssClient()

    results = client.query_orbit_by_dt(
        [p.start_time], [p.mission], orbit_type="restituted"
    )
    assert "702fa0e1-22db-4d20-ab26-0499f262d550" in results
    r = results["702fa0e1-22db-4d20-ab26-0499f262d550"]
    assert (
        r["title"]
        == "S1A_OPER_AUX_RESORB_OPOD_20230823T174849_V20230823T141024_20230823T172754"
    )
