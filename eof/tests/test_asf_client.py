import datetime
import os

import pytest
from sortedcontainers import SortedSet

from eof.asf_client import ASFClient
from eof.client import OrbitType

# pytest --record-mode=all

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASELINE_DIR = os.path.join(SCRIPT_DIR, 'baseline')
MAX_DT = datetime.datetime(2024, 1, 1)


@pytest.fixture(name="asfclient", scope="module")
def generate_asfclient() -> ASFClient:
    baseline_asfclient = ASFClient(cache_dir=BASELINE_DIR)
    return baseline_asfclient


@pytest.mark.vcr
def test_asf_client():
    ASFClient()


@pytest.mark.vcr
def test_asf_read_from_cached_baseline(asfclient):
    """
    Sanity check: the baseline can be loaded
    """
    eofs = asfclient.get_full_eof_list(max_dt=MAX_DT)
    assert len(eofs) == 10122


@pytest.mark.vcr
def test_asf_full_url_list(tmp_path, asfclient: ASFClient):
    """
    Check:
    - we can request EOFs available on ASF servers
    - the EOFs obtained are a superset (more up-to-date) that the baseline
    """
    baseline_urls = SortedSet((eof.filename for eof in asfclient.get_full_eof_list(max_dt=MAX_DT)))

    cache_dir = tmp_path / "sentineleof1"
    cache_dir.mkdir()
    remote_asfclient = ASFClient(cache_dir=cache_dir)

    remote_urls = SortedSet((eof.filename for eof in remote_asfclient.get_full_eof_list(max_dt=MAX_DT)))
    assert len(remote_urls) > 0
    # Should be quick second time
    assert len(remote_asfclient.get_full_eof_list(max_dt=MAX_DT))

    assert baseline_urls <= remote_urls, "We expect ASF won't remove old EOF products..."


@pytest.mark.vcr
def test_asf_client_download(asfclient: ASFClient):
    dt = datetime.datetime(2020, 1, 1)
    mission = "S1A"
    urls = asfclient.get_download_urls([dt], [mission], orbit_type=OrbitType.precise)
    expected = "https://s1qc.asf.alaska.edu/aux_poeorb/S1A_OPER_AUX_POEORB_OPOD_20210315T155112_V20191230T225942_20200101T005942.EOF"  # noqa
    assert urls == [expected]
