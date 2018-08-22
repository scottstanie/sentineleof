import unittest
from datetime import datetime
from .parsers import Sentinel


class TestSentinel(unittest.TestCase):
    def setUp(self):
        self.filename = 'S1A_IW_SLC__1SDV_20180408T043025_20180408T043053_021371_024C9B_1B70.zip'
        self.parser = Sentinel(self.filename)

    def test_bad_filename(self):
        self.assertRaises(ValueError, Sentinel, 'asdf')
        self.assertRaises(ValueError, Sentinel, 'A_b_c_d_e_f_g_h_i_j_k_l')

    def test_full_parse(self):
        expected_output = ('S1A', 'IW', 'SLC', '_', '1', 'S', 'DV', '20180408T043025',
                           '20180408T043053', '021371', '024C9B', '1B70')

        self.assertEqual(self.parser.full_parse(), expected_output)
        self.assertEqual(len(self.parser.full_parse()), 12)

    def test_path_parse(self):
        path_filename = '/some/path/' + self.filename
        self.assertEqual(Sentinel(path_filename).full_parse(), self.parser.full_parse())

    def test_start_time(self):
        expected_start = datetime(2018, 4, 8, 4, 30, 25)
        self.assertEqual(self.parser.start_time, expected_start)

    def test_stop_time(self):
        expected_stop = datetime(2018, 4, 8, 4, 30, 53)
        self.assertEqual(self.parser.stop_time, expected_stop)

    def test_polarization(self):
        self.assertEqual(self.parser.polarization, 'DV')

    def test_mission(self):
        self.assertEqual(self.parser.mission, 'S1A')
