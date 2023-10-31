import datetime

import pytest

from eof.asf_client import ASFClient


# pytest --record-mode=once test_network.py
@pytest.mark.vcr
def test_asf_client():
    dt = datetime.datetime(2020, 1, 1)
    mission = "S1A"
    asfclient = ASFClient()
    urls = asfclient.get_download_urls([dt], [mission], orbit_type="precise")
    expected = "https://s1qc.asf.alaska.edu/aux_poeorb/S1A_OPER_AUX_POEORB_OPOD_20210315T155112_V20191230T225942_20200101T005942.EOF"  # noqa
    assert urls == [expected]


@pytest.mark.vcr
def test_asf_full_url_list(tmp_path):
    cache_dir = tmp_path / "sentineleof"
    cache_dir.mkdir()
    asfclient = ASFClient(cache_dir=(tmp_path / "sentineleof"))
    urls = asfclient.get_full_eof_list()
    assert len(urls) > 0
    assert (cache_dir / "precise_filenames.txt").exists()
    # Should be quick second time
    assert len(asfclient.get_full_eof_list())
