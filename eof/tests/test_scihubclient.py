import datetime

from eof.scihubclient import ScihubGnssClient


def test_query_orbit_by_dr():
    dt = datetime.datetime(2020, 1, 1)
    missions = ["S1A"]
    c = ScihubGnssClient()
    results = c.query_orbit_by_dt([dt], missions, orbit_type="restituted")
    assert len(results) == 1
    r = results["9a844886-45e7-48ec-8bc4-5d9ea91f0553"]
    assert r["endposition"] > dt
    assert r["beginposition"] < dt
