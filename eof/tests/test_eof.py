import datetime
from pathlib import Path

import pytest

from eof import download, products


@pytest.mark.vcr
def test_find_scenes_to_download(tmpdir):
    with tmpdir.as_cwd():
        name1 = (
            "S1A_IW_SLC__1SDV_20180420T043026_20180420T043054_021546_025211_81BE.zip"
        )
        name2 = (
            "S1B_IW_SLC__1SDV_20180502T043026_20180502T043054_021721_025793_5C18.zip"
        )
        name3 = "S1C_IW_SLC__1SDV_20250331T060116_20250331T060143_001681_002CD0_8D44"
        # Fake S1D name
        name4 = "S1D_IW_SLC__1SDV_20250731T060116_20250731T060143_001681_1234D0_1234"
        open(name1, "w").close()
        open(name2, "w").close()
        open(name3, "w").close()
        open(name4, "w").close()
        orbit_dates, missions = download.find_scenes_to_download(search_path=".")

        assert sorted(missions) == ["S1A", "S1B", "S1C", "S1D"]
        assert sorted(orbit_dates) == [
            datetime.datetime(2018, 4, 20, 4, 30, 26),
            datetime.datetime(2018, 5, 2, 4, 30, 26),
            datetime.datetime(2025, 3, 31, 6, 1, 16),
            datetime.datetime(2025, 7, 31, 6, 1, 16),
        ]


def test_other_mission_orbit_does_not_skip_scene(tmp_path):
    """Check that one mission's orbit does not suppress another mission's scene.

    POEORB validity windows are day-aligned identically for every S1 platform, so
    a containment check on the start time alone treats an S1B orbit as covering an
    S1A scene, and no S1A orbit is ever fetched.
    """
    search_path, save_dir = tmp_path / "scenes", tmp_path / "orbits"
    search_path.mkdir()
    save_dir.mkdir()
    scene = "S1A_IW_SLC__1SDV_20180721T225743_20180721T225813_022898_027BD5_F737.zip"
    other_mission_orbit = (
        "S1B_OPER_AUX_POEORB_OPOD_20210313T235723_V20180720T225942_20180722T005942.EOF"
    )
    (search_path / scene).write_text("")
    (save_dir / other_mission_orbit).write_text("")

    orbit_dts, missions = download.find_scenes_to_download(
        search_path=str(search_path), save_dir=str(save_dir)
    )
    assert missions == ["S1A"]
    assert orbit_dts == [datetime.datetime(2018, 7, 21, 22, 57, 43)]


def test_same_mission_orbit_skips_scene(tmp_path):
    """Check that a matching-mission orbit still suppresses the download."""
    search_path, save_dir = tmp_path / "scenes", tmp_path / "orbits"
    search_path.mkdir()
    save_dir.mkdir()
    scene = "S1A_IW_SLC__1SDV_20180721T225743_20180721T225813_022898_027BD5_F737.zip"
    same_mission_orbit = (
        "S1A_OPER_AUX_POEORB_OPOD_20210313T235723_V20180720T225942_20180722T005942.EOF"
    )
    (search_path / scene).write_text("")
    (save_dir / same_mission_orbit).write_text("")

    orbit_dts, missions = download.find_scenes_to_download(
        search_path=str(search_path), save_dir=str(save_dir)
    )
    assert orbit_dts == []
    assert missions == []


def test_same_start_time_different_missions_both_downloaded(tmp_path):
    """Check that scenes sharing a start time are kept per mission.

    The de-duplication of already-seen scenes keys on ``(start_time, mission)``;
    keying on the time alone would drop one of the two missions from the result.
    """
    search_path = tmp_path / "scenes"
    search_path.mkdir()
    # Same start/stop time, different platform and product uid
    (
        search_path
        / "S1A_IW_SLC__1SDV_20180721T225743_20180721T225813_022898_027BD5_F737.zip"
    ).write_text("")
    (
        search_path
        / "S1B_IW_SLC__1SDV_20180721T225743_20180721T225813_011036_014389_67D8.zip"
    ).write_text("")

    orbit_dts, missions = download.find_scenes_to_download(search_path=str(search_path))
    assert sorted(missions) == ["S1A", "S1B"]
    assert orbit_dts == [datetime.datetime(2018, 7, 21, 22, 57, 43)] * 2


@pytest.mark.vcr
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


@pytest.mark.vcr
def test_download_mission_date(tmpdir):
    with tmpdir.as_cwd():
        filenames = download.main(mission="S1A", date="20200101")
    assert len(filenames) == 1
    product = products.SentinelOrbit(filenames[0])
    assert product.start_time < datetime.datetime(2020, 1, 1)
    assert product.stop_time > datetime.datetime(2020, 1, 1, 23, 59)


@pytest.mark.vcr
def test_edge_issue45(tmpdir):
    date = "2023-10-13 11:15:11"
    with tmpdir.as_cwd():
        filenames = download.main(mission="S1A", date=date)
    assert len(filenames) == 1


@pytest.mark.vcr
@pytest.mark.parametrize("force_asf", [True, False])
def test_download_multiple(tmpdir, force_asf):
    granules = [
        "S1A_IW_SLC__1SDV_20180420T043026_20180420T043054_021546_025211_81BE.zip",
        "S1B_IW_SLC__1SDV_20180502T043026_20180502T043054_021721_025793_5C18.zip",
    ]
    with tmpdir.as_cwd():
        # Make empty files
        for g in granules:
            Path(g).write_text("")

        out_paths = download.main(search_path=".", force_asf=force_asf, max_workers=1)
        # should find two .EOF files
        expected_eofs = [
            "S1A_OPER_AUX_POEORB_OPOD_20210307T053325_V20180419T225942_20180421T005942.EOF",
            "S1B_OPER_AUX_POEORB_OPOD_20210313T012515_V20180501T225942_20180503T005942.EOF",
        ]
        assert len(out_paths) == 2
        assert sorted((p.name for p in out_paths)) == expected_eofs


def test_edge_issue78():
    """Test orbit selection with looser margins for issue 78.

    This tests the edge case where a RESORB file starts slightly less than
    one full orbit before the acquisition start time. With the new looser
    defaults (60 second margins), this should work. With the old strict margins
    (T_ORBIT + 60), it would fail.
    """
    from datetime import datetime, timedelta
    from eof._select_orbit import last_valid_orbit, ValidityError, T_ORBIT

    # Scene from issue 78
    scene_start = datetime(2025, 7, 15, 11, 25, 31)
    scene_stop = datetime(2025, 7, 15, 11, 25, 58)

    # Three candidate RESORB files
    orbit_files = [
        products.SentinelOrbit(
            "AUX_RESORB/S1A_OPER_AUX_RESORB_OPOD_20250715T120248_V20250715T080808_20250715T112538.EOF"
        ),
        products.SentinelOrbit(
            "AUX_RESORB/S1A_OPER_AUX_RESORB_OPOD_20250715T133833_V20250715T094652_20250715T130422.EOF"
        ),
        products.SentinelOrbit(
            "AUX_RESORB/S1A_OPER_AUX_RESORB_OPOD_20250715T150939_V20250715T112537_20250715T144307.EOF"
        ),
    ]

    # With new looser margins (60 seconds), should select the second file
    result = last_valid_orbit(
        scene_start,
        scene_stop,
        orbit_files,
        margin0=timedelta(seconds=60),
        margin1=timedelta(seconds=60),
    )
    assert (
        "S1A_OPER_AUX_RESORB_OPOD_20250715T133833_V20250715T094652_20250715T130422.EOF"
        in result
    )

    # With strict margins (T_ORBIT + 60), none should be valid
    with pytest.raises(ValidityError):
        last_valid_orbit(
            scene_start,
            scene_stop,
            orbit_files,
            margin0=timedelta(seconds=T_ORBIT + 60),
            margin1=timedelta(seconds=60),
        )
