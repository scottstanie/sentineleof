import datetime
import os
from pathlib import Path
from _pytest.fixtures import SubRequest

import pytest
import json
from pytest_recording._vcr import use_cassette

from eof import download, products
from eof._auth import DATASPACE_HOST, get_netrc_credentials
from eof.dataspace_client import get_access_token


def filter_response(response):
    """Scrub various secrets from ASF and Copernicus Dataspace"""
    # Scrub SET-COOKIE from ASF responses
    response['headers'].pop('SET-COOKIE', None)
    # Scrub set-cookie from Copernicus Dataspace responses
    response['headers'].pop('set-cookie', None)
    # Scrub access_token and refresh_token from Copernicus Dataspace
    if "body" in response and "string" in response["body"]:
        body_string = response["body"]["string"]
        try:
            decoded_body = json.loads(body_string)
            for key in ("access_token", "refresh_token"):
                if key in decoded_body:
                    decoded_body[key] = f"REDACTED_{key}"
            response["body"]["string"] = bytes(json.dumps(decoded_body), 'utf8')
        except json.decoder.JSONDecodeError:
            pass
    return response


@pytest.fixture(scope="module")
def vcr_config():
    """
    Tweak the cassette recorder to remove secrets from queries and responses
    """
    return {
            "filter_headers": ["authorization", "Cookie"],
            "filter_query_parameters": ["username", "password", "totp"],
            "filter_post_data_parameters": ["username", "password", "totp"],
            "before_record_response": [filter_response],
    }


def _get_cdse_token(cdse_2fa_token):
    username, password = get_netrc_credentials(DATASPACE_HOST, netrc_file='')
    token = get_access_token(username, password, cdse_2fa_token)
    return token


@pytest.fixture(scope="module")
def cdse_access_token(
        request: SubRequest,
        vcr_cassette_dir: str,
        record_mode: str,
        vcr_config: dict,
        pytestconfig: pytest.Config
):
    # Hook used to generate cassettes with Copernicus when 2FA is used
    # In that case set $EOF_CDSE_2FA_TOKEN and $NETRC before calling pytest, e.g.:
    # $> EOF_CDSE_2FA_TOKEN=999999 NETRC=~/.config/.netrc pytest  -vvv  --log-cli-level=DEBUG -o log_cli=true --capture=no --durations=0 --record-mode=once  eof/tests/test_eof.py 2>&1  | less -R
    CDSE_2FA_TOKEN = os.getenv("EOF_CDSE_2FA_TOKEN", None)
    with use_cassette('cdse_access_token', vcr_cassette_dir, record_mode, [], vcr_config, pytestconfig):
        return _get_cdse_token(CDSE_2FA_TOKEN)


@pytest.mark.vcr
def test_find_scenes_to_download(tmpdir):
    with tmpdir.as_cwd():
        name1 = (
            "S1A_IW_SLC__1SDV_20180420T043026_20180420T043054_021546_025211_81BE.zip"
        )
        name2 = (
            "S1B_IW_SLC__1SDV_20180502T043026_20180502T043054_021721_025793_5C18.zip"
        )
        open(name1, "w").close()
        open(name2, "w").close()
        orbit_dates, missions = download.find_scenes_to_download(search_path=".")

        assert sorted(orbit_dates) == [
            datetime.datetime(2018, 4, 20, 4, 30, 26),
            datetime.datetime(2018, 5, 2, 4, 30, 26),
        ]

        assert sorted(missions) == ["S1A", "S1B"]


@pytest.mark.vcr
def test_download_eofs_errors(cdse_access_token):
    orbit_dates = [datetime.datetime(2018, 5, 2, 4, 30, 26)]
    with pytest.raises(ValueError):
        download.download_eofs(orbit_dates, missions=["BadMissionStr"], cdse_access_token=cdse_access_token)
    # 1 date, 2 missions ->
    # ValueError: missions arg must be same length as orbit_dts
    with pytest.raises(ValueError):
        download.download_eofs(orbit_dates, missions=["S1A", "S1B"], cdse_access_token=cdse_access_token)


def test_main_nothing_found(cdse_access_token):
    # Test "no sentinel products found"
    assert download.main(search_path="/notreal", cdse_access_token=cdse_access_token) == []


def test_main_error_args(cdse_access_token):
    with pytest.raises(ValueError):
        download.main(search_path="/notreal", mission="S1A", cdse_access_token=cdse_access_token)


@pytest.mark.vcr
def test_download_mission_date(tmpdir, cdse_access_token):
    with tmpdir.as_cwd():
        filenames = download.main(mission="S1A", date="20200101", cdse_access_token=cdse_access_token)
    assert len(filenames) == 1
    product = products.SentinelOrbit(filenames[0])
    assert product.start_time < datetime.datetime(2020, 1, 1)
    assert product.stop_time > datetime.datetime(2020, 1, 1, 23, 59)


@pytest.mark.vcr
def test_edge_issue45(tmpdir, cdse_access_token):
    date = "2023-10-13 11:15:11"
    with tmpdir.as_cwd():
        filenames = download.main(mission="S1A", date=date, cdse_access_token=cdse_access_token)
    assert len(filenames) == 1


@pytest.mark.vcr
@pytest.mark.parametrize("force_asf", [True, False])
def test_download_multiple(tmpdir, force_asf, cdse_access_token):
    granules = [
        "S1A_IW_SLC__1SDV_20180420T043026_20180420T043054_021546_025211_81BE.zip",
        "S1B_IW_SLC__1SDV_20180502T043026_20180502T043054_021721_025793_5C18.zip",
    ]
    with tmpdir.as_cwd():
        # Make empty files
        for g in granules:
            Path(g).write_text("")

        out_paths = download.main(search_path=".", force_asf=force_asf, max_workers=1, cdse_access_token=cdse_access_token)
        # should find two .EOF files
        expected_eofs = [
            "S1A_OPER_AUX_POEORB_OPOD_20210307T053325_V20180419T225942_20180421T005942.EOF",
            "S1B_OPER_AUX_POEORB_OPOD_20210313T012515_V20180501T225942_20180503T005942.EOF",
        ]
        assert len(out_paths) == 2
        assert sorted((p.name for p in out_paths)) == expected_eofs
