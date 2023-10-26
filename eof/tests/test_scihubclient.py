import datetime

import pytest

from eof.scihubclient import ASFClient, ScihubGnssClient
from eof.products import Sentinel


def test_scihub_query_orbit_by_dt():
    dt = datetime.datetime(2020, 1, 1)
    mission = "S1A"
    c = ScihubGnssClient()
    # Restituted seems to fail for old dates...
    # Need to look into sentinelsat, or if ESA has just stopped allowing it
    results = c.query_orbit_by_dt([dt], [mission], orbit_type="precise")
    assert len(results) == 1
    r = results["21db46df-3991-4700-a454-dd91b6f2217a"]
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


@pytest.mark.skip("Local testing only for ASF")
def test_asf_client():
    dt = datetime.datetime(2020, 1, 1)
    mission = "S1A"
    asfclient = ASFClient()
    urls = asfclient.get_download_urls([dt], [mission], orbit_type="precise")
    expected = "https://s1qc.asf.alaska.edu/aux_poeorb/S1A_OPER_AUX_POEORB_OPOD_20210315T155112_V20191230T225942_20200101T005942.EOF"  # noqa
    assert urls == [expected]


@pytest.mark.skip("Local testing only for ASF")
def test_asf_full_url_list(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    asfclient = ASFClient()
    urls = asfclient.get_full_eof_list()
    assert len(urls) > 0
    assert (tmp_path / "sentineleof" / "precise_filenames.txt").exists()
    # Should be quick second time
    assert len(asfclient.get_full_eof_list())
