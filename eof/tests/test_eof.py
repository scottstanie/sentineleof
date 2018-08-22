import unittest
import tempfile
import shutil
import datetime
import os
import responses

from eof import download


class TestEOF(unittest.TestCase):
    def setUp(self):
        self.sample_api_search = {
            'count':
            1,
            'next':
            None,
            'previous':
            None,
            'results': [{
                'creation_date':
                '2018-05-22T12:07:30',
                'footprint':
                None,
                'hash':
                '43ca6cd1bdc17a740953ab15da08ddaead6c23d3',
                'metadata_date':
                '2018-06-19T13:16:41.130580',
                'physical_name':
                'S1A_OPER_AUX_POEORB_OPOD_20180522T120730_V20180501T225942_20180503T005942.EOF',
                'product_name':
                'S1A_OPER_AUX_POEORB_OPOD_20180522T120730_V20180501T225942_20180503T005942',
                'product_type':
                'AUX_POEORB',
                'remote_url':
                'http://aux.sentinel1.eo.esa.int/POEORB/2018/05/22/S1A_OPER_AUX_POEORB_OPOD_20180522T120730_V20180501T225942_20180503T005942.EOF',
                'size':
                4410148,
                'uuid':
                'a758ad6d-b718-4dff-a1b2-822874ca4017',
                'validity_start':
                '2018-05-01T22:59:42',
                'validity_stop':
                '2018-05-03T00:59:42'
            }]
        }
        self.sample_eof = """<?xml version="1.0" ?><Earth_Explorer_File></Earth_Explorer_File>"""

    @responses.activate
    def test_eof_list(self):
        responses.add(
            responses.GET,
            'https://qc.sentinel1.eo.esa.int/api/v1/?product_type=AUX_POEORB&validity_stop__gt=2018-05-03&validity_start__lt=2018-05-02',
            json=self.sample_api_search,
            status=200)

        test_date = datetime.datetime(2018, 5, 2)
        result_list = download.eof_list(test_date)
        expected = [
            'http://aux.sentinel1.eo.esa.int/POEORB/2018/05/22/S1A_OPER_AUX_POEORB_OPOD_20180522T120730_V20180501T225942_20180503T005942.EOF'
        ]
        self.assertEqual(result_list, expected)

    def test_find_sentinel_products(self):
        try:
            temp_dir = tempfile.mkdtemp()
            name1 = os.path.join(
                temp_dir, 'S1A_IW_SLC__1SDV_20180420T043026_20180420T043054_021546_025211_81BE.zip')
            name2 = os.path.join(
                temp_dir, 'S1B_IW_SLC__1SDV_20180502T043026_20180502T043054_021721_025793_5C18.zip')
            open(name1, 'w').close()
            open(name2, 'w').close()
            orbit_dates, missions = download.find_sentinel_products(startpath=temp_dir)

            self.assertEqual(
                sorted(orbit_dates), [
                    datetime.datetime(2018, 4, 20, 4, 30, 26),
                    datetime.datetime(2018, 5, 2, 4, 30, 26)
                ])

            self.assertEqual(sorted(missions), ['S1A', 'S1B'])
        finally:
            # Clean up temp dir
            shutil.rmtree(temp_dir)

    @responses.activate
    def test_download_eofs(self):
        # Mock the date search url
        responses.add(
            responses.GET,
            'https://qc.sentinel1.eo.esa.int/api/v1/?product_type=AUX_POEORB&validity_stop__gt=2018-05-03&validity_start__lt=2018-05-02',
            json=self.sample_api_search,
            status=200)

        # Also mock the EOF download url
        eof_url = 'http://aux.sentinel1.eo.esa.int/POEORB/2018/05/22/S1A_OPER_AUX_POEORB_OPOD_20180522T120730_V20180501T225942_20180503T005942.EOF'
        responses.add(responses.GET, eof_url, body=self.sample_eof, status=200)

        eof_name = eof_url.split('/')[-1]
        orbit_dates = [datetime.datetime(2018, 5, 2, 4, 30, 26)]
        try:
            temp_dir = tempfile.mkdtemp()
            eof_path = os.path.join(temp_dir, eof_name)
            self.assertFalse(os.path.exists(eof_path))

            download.download_eofs(orbit_dates, save_dir=temp_dir)
            self.assertTrue(os.path.exists(eof_path))

            # Now read the file and make sure it's the same
            with open(eof_path) as f:
                eof_contents = f.read()
            self.assertEqual(eof_contents, self.sample_eof)
        finally:
            shutil.rmtree(temp_dir)
