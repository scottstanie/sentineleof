import datetime
import os

import pytest

from eof.asf_client import ASFClient
from eof.client import OrbitType
from eof._asf_s3 import ASF_BUCKET_NAME, list_public_bucket
# pytest --record-mode=all

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASELINE_DIR = os.path.join(SCRIPT_DIR, 'baseline')
MAX_DT = datetime.datetime(2024, 1, 1)


@pytest.fixture(name="asfclient", scope="module")
def generate_asfclient() -> ASFClient:
    baseline_asfclient = ASFClient(cache_dir=BASELINE_DIR)
    return baseline_asfclient


def test_asf_client():
    _ = ASFClient()


def test_asf_read_from_cached_baseline(asfclient):
    """
    Sanity check: the baseline can be loaded, and it has 6254 entries
    """
    eofs = asfclient.get_full_eof_list(max_dt=MAX_DT)
    assert len(eofs) == 6254


@pytest.mark.vcr
def test_asf_full_url_list(tmp_path, asfclient: ASFClient):
    """
    Check:
    - we can request EOFs available on ASF servers
    - the EOFs obtained are a superset (more up-to-date) that the baseline
    """
    baseline_urls = set((eof.filename for eof in asfclient.get_full_eof_list(max_dt=MAX_DT)))

    cache_dir = tmp_path / "sentineleof1"
    cache_dir.mkdir()
    remote_asfclient = ASFClient(cache_dir=cache_dir)

    remote_urls = set((eof.filename for eof in remote_asfclient.get_full_eof_list(max_dt=MAX_DT)))
    assert len(remote_urls) > 0
    # Should be quick second time
    assert len(remote_asfclient.get_full_eof_list(max_dt=MAX_DT))

    # Actually, it's possible as a same orbit may be published several times at
    # different dates...
    assert baseline_urls <= remote_urls, f"We expect ASF won't remove old EOF products..."


def test_asf_query_orbit_files_by_dt_range(asfclient: ASFClient):
    dt1 = datetime.datetime(2020, 1, 1)   # 00:00:00
    dt2 = datetime.datetime(2020, 1, 12)  # 00:00:00
    mission = "S1A"
    # Restituted seems to fail for old dates...
    # Need to look into sentinelsat, or if ESA has just stopped allowing it
    results = asfclient.query_orbit_files_by_dt_range(dt1, dt2, [mission], orbit_type=OrbitType.precise)
    assert len(results) == 13  # 12 files intersect from 20200101T00:00:00 to 20200112T00:00:00
    for r in results:
        assert r.stop_time >= dt1
        assert r.start_time <= dt2
    r = results[0]
    assert r.filename == "AUX_POEORB/S1A_OPER_AUX_POEORB_OPOD_20210315T155112_V20191230T225942_20200101T005942.EOF"


def test_asf_query_orbit_urls_by_dt_range(asfclient: ASFClient):
    dt1 = datetime.datetime(2020, 1, 1)   # 00:00:00
    dt2 = datetime.datetime(2020, 1, 12)  # 00:00:00
    mission = "S1A"
    # Restituted seems to fail for old dates...
    # Need to look into sentinelsat, or if ESA has just stopped allowing it
    results = asfclient.query_orbits_by_dt_range(dt1, dt2, [mission], orbit_type=OrbitType.precise)
    assert len(results) == 13  # 12 files intersect from 20200101T00:00:00 to 20200112T00:00:00

    expected = "https://s1-orbits.s3.amazonaws.com/AUX_POEORB/S1A_OPER_AUX_POEORB_OPOD_20210315T155112_V20191230T225942_20200101T005942.EOF"  # noqa
    assert results[0] == expected


def test_asf_client_download(asfclient: ASFClient):
    dt = datetime.datetime(2020, 1, 1)
    mission = "S1A"
    urls = asfclient.get_download_urls([dt], [mission], orbit_type=OrbitType.precise)
    expected = "https://s1-orbits.s3.amazonaws.com/AUX_POEORB/S1A_OPER_AUX_POEORB_OPOD_20210315T155112_V20191230T225942_20200101T005942.EOF"  # noqa
    assert urls == [expected]


@pytest.mark.vcr
def test_list_public_bucket_resorb():
    resorbs = list_public_bucket(ASF_BUCKET_NAME, prefix="AUX_RESORB")
    assert (
        resorbs[0]
        == "AUX_RESORB/S1A_OPER_AUX_RESORB_OPOD_20231002T140558_V20231002T102001_20231002T133731.EOF"
    )


@pytest.mark.vcr
def test_list_public_bucket_poeorb():
    precise = list_public_bucket(ASF_BUCKET_NAME, prefix="AUX_POEORB")
    assert (
        precise[0]
        == "AUX_POEORB/S1A_OPER_AUX_POEORB_OPOD_20210203T122423_V20210113T225942_20210115T005942.EOF"
    )
