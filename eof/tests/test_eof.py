import unittest
import tempfile
import shutil
import datetime
import os
import responses

from unittest import mock
from eof import download


class TestEOF(unittest.TestCase):
    def setUp(self):
        self.empty_api_search = {"count": 0}
        self.sample_api_search = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "creation_date": "2018-05-22T12:07:30",
                    "footprint": None,
                    "hash": "43ca6cd1bdc17a740953ab15da08ddaead6c23d3",
                    "metadata_date": "2018-06-19T13:16:41.130580",
                    "physical_name": "S1A_OPER_AUX_POEORB_OPOD_20180522T120730_V20180501T225942_20180503T005942.EOF",
                    "product_name": "S1A_OPER_AUX_POEORB_OPOD_20180522T120730_V20180501T225942_20180503T005942",
                    "product_type": "AUX_POEORB",
                    "remote_url": "http://aux.sentinel1.eo.esa.int/POEORB/2018/05/22/S1A_OPER_AUX_POEORB_OPOD_20180522T120730_V20180501T225942_20180503T005942.EOF",  # noqa
                    "size": 4410148,
                    "uuid": "a758ad6d-b718-4dff-a1b2-822874ca4017",
                    "validity_start": "2018-05-01T22:59:42",
                    "validity_stop": "2018-05-03T00:59:42",
                }
            ],
        }
        self.sample_eof = (
            """<?xml version="1.0" ?><Earth_Explorer_File></Earth_Explorer_File>"""
        )

    # @responses.activate
    # def test_eof_list(self):
    #     responses.add(
    #         responses.GET,
    #         'https://qc.sentinel1.eo.esa.int/api/v1/?product_type=AUX_POEORB&sentinel1__mission=S1A&validity_start__lt=2018-05-01T23:58:00&validity_stop__gt=2018-05-02T00:02:00',  # noqa
    #         json=self.sample_api_search,
    #         status=200)

    #     test_date = datetime.datetime(2018, 5, 2)
    #     result_list = download.eof_list(test_date, 'S1A')
    #     expected = (
    #         [
    #             'http://aux.sentinel1.eo.esa.int/POEORB/2018/05/22/S1A_OPER_AUX_POEORB_OPOD_20180522T120730_V20180501T225942_20180503T005942.EOF'  # noqa
    #         ],
    #         'POEORB')
    #     self.assertEqual(result_list, expected)

    # @responses.activate
    # def test_eof_list_empty(self):
    #     responses.add(
    #         responses.GET,
    #         'https://qc.sentinel1.eo.esa.int/api/v1/?product_type=AUX_POEORB&sentinel1__mission=S1A&validity_start__lt=2018-05-01T23:58:00&validity_stop__gt=2018-05-02T00:02:00',  # noqa
    #         json=self.empty_api_search,
    #         status=200)
    #     responses.add(
    #         responses.GET,
    #         'https://qc.sentinel1.eo.esa.int/api/v1/?product_type=AUX_RESORB&sentinel1__mission=S1A&validity_start__lt=2018-05-01T23:58:00&validity_stop__gt=2018-05-02T00:02:00',  # noqa
    #         json=self.empty_api_search,
    #         status=200)

    #     test_date = datetime.datetime(2018, 5, 2)
    #     self.assertRaises(ValueError, download.eof_list, test_date, 'S1A')
    #     self.assertEqual(download._download_and_write('S1A', test_date), None)

    def test_find_scenes_to_download(self):
        try:
            temp_dir = tempfile.mkdtemp()
            name1 = os.path.join(
                temp_dir,
                "S1A_IW_SLC__1SDV_20180420T043026_20180420T043054_021546_025211_81BE.zip",
            )
            name2 = os.path.join(
                temp_dir,
                "S1B_IW_SLC__1SDV_20180502T043026_20180502T043054_021721_025793_5C18.zip",
            )
            open(name1, "w").close()
            open(name2, "w").close()
            orbit_dates, missions = download.find_scenes_to_download(
                search_path=temp_dir
            )

            self.assertEqual(
                sorted(orbit_dates),
                [
                    datetime.datetime(2018, 4, 20, 4, 30, 26),
                    datetime.datetime(2018, 5, 2, 4, 30, 26),
                ],
            )

            self.assertEqual(sorted(missions), ["S1A", "S1B"])
        finally:
            # Clean up temp dir
            shutil.rmtree(temp_dir)

    def test_download_eofs_errors(self):
        orbit_dates = [datetime.datetime(2018, 5, 2, 4, 30, 26)]
        self.assertRaises(
            ValueError, download.download_eofs, orbit_dates, missions=["BadMissionStr"]
        )
        # More missions for dates
        self.assertRaises(
            ValueError, download.download_eofs, orbit_dates, missions=["S1A", "S1B"]
        )

    # @responses.activate
    # def test_download_eofs(self):
    #     # Mock the date search url
    #     responses.add(
    #         responses.GET,
    #         "https://qc.sentinel1.eo.esa.int/api/v1/?product_type=AUX_POEORB&sentinel1__mission=None&validity_start__lt=2018-05-02T04:28:26&validity_stop__gt=2018-05-02T04:32:26",  # noqa
    #         json=self.sample_api_search,
    #         status=200,
    #     )

    #     # Also mock the EOF download url
    #     eof_url = "http://aux.sentinel1.eo.esa.int/POEORB/2018/05/22/S1A_OPER_AUX_POEORB_OPOD_20180522T120730_V20180501T225942_20180503T005942.EOF"  # noqa
    #     responses.add(responses.GET, eof_url, body=self.sample_eof, status=200)

    #     eof_name = eof_url.split("/")[-1]
    #     orbit_dates = [datetime.datetime(2018, 5, 2, 4, 30, 26)]
    #     try:
    #         temp_dir = tempfile.mkdtemp()
    #         eof_path = os.path.join(temp_dir, eof_name)
    #         self.assertFalse(os.path.exists(eof_path))

    #         download.download_eofs(orbit_dates, save_dir=temp_dir)
    #         self.assertTrue(os.path.exists(eof_path))

    #         # Now read the file and make sure it's the same
    #         with open(eof_path) as f:
    #             eof_contents = f.read()
    #         self.assertEqual(eof_contents, self.sample_eof)
    #     finally:
    #         shutil.rmtree(temp_dir)

    def test_main_nothing_found(self):
        # Test "no sentinel products found"
        self.assertEqual(download.main(search_path="/notreal"), 0)

    def test_main_error_args(self):
        self.assertRaises(
            ValueError, download.main, search_path="/notreal", mission="S1A"
        )

    @mock.patch("eof.download.download_eofs")
    def test_mission(self, download_eofs):
        download.main(mission="S1A", date="20200101")
        download_eofs.assert_called_once_with(
            missions=["S1A"],
            orbit_dts=["20200101"],
            sentinel_file=None,
            save_dir=",",
        )
