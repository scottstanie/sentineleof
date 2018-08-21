"""
Utilities for parsing file names of Sentinel SAR products.
"""

import re
from datetime import datetime


class Sentinel(object):
    """
    Sentinel 1 reference:
    https://sentinel.esa.int/web/sentinel/user-guides/sentinel-1-sar/naming-conventions
    or https://sentinel.esa.int/documents/247904/349449/Sentinel-1_Product_Specification

    Example:
        S1A_IW_SLC__1SDV_20180408T043025_20180408T043053_021371_024C9B_1B70.zip

    File name format:
        MMM_BB_TTTR_LFPP_YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_OOOOOO_DDDDDD_CCCC.EEEE

    MMM: mission/satellite S1A or S1B
    BB: Mode/beam identifier. The S1-S6 beams apply to SM products
        IW, EW and WV identifiers appply to products from the respective modes.
    TTT: Product Type: RAW, SLC, GRD, OCN
    R: Resolution class: F, H, M, or _ (N/A)
    L: Processing Level: 0, 1, 2
    F: Product class: S (standard), A (annotation, only used internally)
    PP: Polarization: SH (single HH), SV (single VV), DH (dual HH+HV), DV (dual VV+VH)
    Start date + time (date/time separated by T)
    Stop date + time
    OOOOOO: absolute orbit number: 000001-999999
    DDDDDD: mission data-take identifier: 000001-FFFFFF.
    CCCC: product unique identifier: hexadecimal string from CRC-16 the manifest file using CRC-CCITT.

    Once unzipped, the folder extension is always "SAFE".

    Attributes:
        filename (str) name of the sentinel data product
    """
    FILE_REGEX = r'(S1A|S1B)_([\w\d]{2})_([\w_]{3})([FHM_])_(\d)([SA])([SDHV]{2})_([T\d]{15})_([T\d]{15})_(\d{6})_([\d\w]{6})_([\d\w]{4})'
    TIME_FMT = '%Y%m%dT%H%M%S'
    _FIELD_MEANINGS = ('mission', 'beam', 'product type', 'resolution class', 'product level',
                       'product class', 'polarization', 'start datetime', 'stop datetime',
                       'orbit number', 'data-take identified', 'product unique id')

    def __init__(self, filename):
        """
        Extract data from filename
            filename (str): name of SAR/InSAR product
        """
        self.filename = filename
        self.full_parse()  # Run a parse to check validity of filename

    def __repr__(self):
        return str(self)

    def full_parse(self):
        """Returns all parts of the data contained in filename

        Returns:
            tuple: parsed file data. Entry order will match `field_meanings`

        Raises:
            ValueError: if filename string is invalid
        """
        if not self.FILE_REGEX:
            raise NotImplementedError("Must define class FILE_REGEX to parse")

        match = re.search(self.FILE_REGEX, self.filename)
        if not match:
            raise ValueError('Invalid {} filename: {}'.format(self.__class__.__name__,
                                                              self.filename))
        else:
            return match.groups()

    @property
    def field_meanings(self):
        """List the fields returned by full_parse()"""
        return self._FIELD_MEANINGS

    def _get_field(self, fieldname):
        """Pick a specific field based on its name"""
        idx = self.field_meanings.index(fieldname)
        return self.full_parse()[idx]

    def __str__(self):
        return "{} {}, path {} from {}".format(self.__class__.__name__, self.mission, self.path,
                                               self.date)

    @property
    def start_time(self):
        """Returns start datetime from a sentinel file name

        Args:
            filename (str): filename of a sentinel 1 product

        Returns:
            datetime: start datetime of mission


        Example:
            >>> s = Sentinel('S1A_IW_SLC__1SDV_20180408T043025_20180408T043053_021371_024C9B_1B70')
            >>> print(s.start_time)
            2018-04-08 04:30:25
        """
        start_time_str = self._get_field('start datetime')
        return datetime.strptime(start_time_str, self.TIME_FMT)

    @property
    def stop_time(self):
        """Returns stop datetime from a sentinel file name

        Args:
            filename (str): filename of a sentinel 1 product

        Returns:
            datetime: stop datetime

        Example:
            >>> s = Sentinel('S1A_IW_SLC__1SDV_20180408T043025_20180408T043053_021371_024C9B_1B70')
            >>> print(s.stop_time)
            2018-04-08 04:30:53
        """
        stop_time_str = self._get_field('stop datetime')
        return datetime.strptime(stop_time_str, self.TIME_FMT)

    @property
    def polarization(self):
        """Returns type of polarization of product

        Example:
            >>> s = Sentinel('S1A_IW_SLC__1SDV_20180408T043025_20180408T043053_021371_024C9B_1B70')
            >>> print(s.polarization)
            DV
        """
        return self._get_field('polarization')

    @property
    def mission(self):
        """Returns satellite/mission of product (S1A/S1B)

        Example:
            >>> s = Sentinel('S1A_IW_SLC__1SDV_20180408T043025_20180408T043053_021371_024C9B_1B70')
            >>> print(s.mission)
            S1A
        """
        return self._get_field('mission')

    @property
    def absolute_orbit(self):
        """Absolute orbit of data, included in file name

        Example:
            >>> s = Sentinel('S1A_IW_SLC__1SDV_20180408T043025_20180408T043053_021371_024C9B_1B70')
            >>> print(s.absolute_orbit)
            21371
        """
        return int(self._get_field('orbit number'))

    @property
    def relative_orbit(self):
        """Relative orbit number/ path

        Formulas for relative orbit from absolute come from:
        https://forum.step.esa.int/t/sentinel-1-relative-orbit-from-filename/7042

        Example:
            >>> s = Sentinel('S1A_IW_SLC__1SDV_20180408T043025_20180408T043053_021371_024C9B_1B70')
            >>> print(s.relative_orbit)
            124
            >>> s = Sentinel('S1B_WV_OCN__2SSV_20180522T161319_20180522T164846_011036_014389_67D8')
            >>> print(s.relative_orbit)
            160
        """
        if self.mission == 'S1A':
            return ((self.absolute_orbit - 73) % 175) + 1
        elif self.mission == 'S1B':
            return ((self.absolute_orbit - 27) % 175) + 1

    @property
    def path(self):
        """Alias for relative orbit number"""
        return self.relative_orbit

    @property
    def date(self):
        """Date of acquisition: shortcut for start_time.date()"""
        return self.start_time.date()
