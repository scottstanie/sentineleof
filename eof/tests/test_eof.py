import datetime

import pytest

from eof import download


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


def test_download_eofs_errors():
    orbit_dates = [datetime.datetime(2018, 5, 2, 4, 30, 26)]
    with pytest.raises(ValueError):
        download.download_eofs(orbit_dates, missions=["BadMissionStr"])
    # More missions for dates
    with pytest.raises(ValueError):
        download.download_eofs(orbit_dates, missions=["S1A", "S1B"])


def test_main_nothing_found():
    # Test "no sentinel products found"
    assert download.main(search_path="/notreal") == []


def test_main_error_args():
    with pytest.raises(ValueError):
        download.main(search_path="/notreal", mission="S1A")


def test_mission(tmpdir):
    with tmpdir.as_cwd():
        download.main(mission="S1A", date="20200101")
