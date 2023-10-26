import datetime

import pytest

from eof import download, products


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
    # 1 date, 2 missions ->
    # ValueError: missions arg must be same length as orbit_dts
    with pytest.raises(ValueError):
        download.download_eofs(orbit_dates, missions=["S1A", "S1B"])


def test_main_nothing_found():
    # Test "no sentinel products found"
    assert download.main(search_path="/notreal") == []


def test_main_error_args():
    with pytest.raises(ValueError):
        download.main(search_path="/notreal", mission="S1A")


def test_download_mission_date(tmpdir):
    with tmpdir.as_cwd():
        filenames = download.main(mission="S1A", date="20200101")
    assert len(filenames) == 1
    product = products.SentinelOrbit(filenames[0])
    assert product.start_time < datetime.datetime(2020, 1, 1)
    assert product.stop_time > datetime.datetime(2020, 1, 1, 23, 59)


def test_edge_issue45(tmpdir):
    date = "2023-10-13 11:15:11"
    with tmpdir.as_cwd():
        filenames = download.main(mission="S1A", date=date)
    assert len(filenames) == 1
