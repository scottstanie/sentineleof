import datetime

import pytest

from eof.asf_client import ASFClient


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
