import datetime

import pytest

from eof.asf_client import ASFClient
from eof.products import Sentinel
from eof._asf_s3 import ASF_BUCKET_NAME, list_public_bucket


@pytest.mark.vcr
def test_asf_client():
    ASFClient()


@pytest.mark.vcr
def test_asf_full_url_list(tmp_path):
    cache_dir = tmp_path / "sentineleof1"
    cache_dir.mkdir()
    asfclient = ASFClient(cache_dir=cache_dir)

    urls = asfclient.get_full_eof_list()
    assert len(urls) > 0
    # Should be quick second time
    assert len(asfclient.get_full_eof_list())


@pytest.mark.vcr
def test_asf_client_download(tmp_path):
    cache_dir = tmp_path / "sentineleof2"
    cache_dir.mkdir()
    asfclient = ASFClient(cache_dir=cache_dir)

    dt = datetime.datetime(2020, 1, 1)
    mission = "S1A"
    urls = asfclient.get_download_urls([dt], [mission], orbit_type="precise")
    expected = "https://s1-orbits.s3.amazonaws.com/AUX_POEORB/S1A_OPER_AUX_POEORB_OPOD_20210315T155112_V20191230T225942_20200101T005942.EOF"
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


@pytest.mark.vcr
def test_query_resorb_s1_reader_issue68():
    f = "S1A_IW_SLC__1SDV_20250310T204228_20250310T204253_058247_0732D8_1AA3"
    sent = Sentinel(f)
    orbit_dts, missions = [sent.start_time], [sent.mission]

    client = ASFClient()

    urls = client.get_download_urls(orbit_dts, missions, orbit_type="restituted")
    assert len(urls) == 1
    expected = (
        "S1A_OPER_AUX_RESORB_OPOD_20250310T220905_V20250310T180852_20250310T212622.EOF"
    )
    assert urls[0].split("/")[-1] == expected
