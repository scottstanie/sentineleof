"""Client to get orbit files from ASF."""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Optional

import requests

from ._auth import NASA_HOST, setup_netrc
from ._select_orbit import T_ORBIT, ValidityError, last_valid_orbit
from ._types import Filename
from .log import logger
from .parsing import EOFLinkFinder
from .products import SentinelOrbit

SIGNUP_URL = "https://urs.earthdata.nasa.gov/users/new"
"""Url to prompt user to sign up for NASA Earthdata account."""


class ASFClient:
    precise_url = "https://s1qc.asf.alaska.edu/aux_poeorb/"
    res_url = "https://s1qc.asf.alaska.edu/aux_resorb/"
    urls = {"precise": precise_url, "restituted": res_url}
    eof_lists = {"precise": None, "restituted": None}

    def __init__(self, cache_dir: Optional[Filename] = None):
        setup_netrc(host=NASA_HOST)
        self._cache_dir = cache_dir

    def get_full_eof_list(self, orbit_type="precise", max_dt=None):
        """Get the list of orbit files from the ASF server."""
        if orbit_type not in self.urls.keys():
            raise ValueError("Unknown orbit type: {}".format(orbit_type))

        if self.eof_lists.get(orbit_type) is not None:
            return self.eof_lists[orbit_type]
        # Try to see if we have the list of EOFs in the cache
        elif os.path.exists(self._get_filename_cache_path(orbit_type)):
            eof_list = self._get_cached_filenames(orbit_type)
            # Need to clear it if it's older than what we're looking for
            max_saved = max([e.start_time for e in eof_list])
            if max_saved < max_dt:
                logger.warning("Clearing cached {} EOF list:".format(orbit_type))
                logger.warning(
                    "{} is older than requested {}".format(max_saved, max_dt)
                )
                self._clear_cache(orbit_type)
            else:
                logger.info("Using cached EOF list")
                self.eof_lists[orbit_type] = eof_list
                return eof_list

        logger.info("Downloading all filenames from ASF (may take awhile)")
        resp = requests.get(self.urls.get(orbit_type))
        finder = EOFLinkFinder()
        finder.feed(resp.text)
        eof_list = [SentinelOrbit(f) for f in finder.eof_links]
        self.eof_lists[orbit_type] = eof_list
        self._write_cached_filenames(orbit_type, eof_list)
        return eof_list

    def get_download_urls(self, orbit_dts, missions, orbit_type="precise"):
        """Find the URL for an orbit file covering the specified datetime

        Args:
            dt (datetime): requested
        Args:
            orbit_dts (list[str] or list[datetime]): datetime for orbit coverage
            missions (list[str]): specify S1A or S1B

        Returns:
            str: URL for the orbit file
        """
        eof_list = self.get_full_eof_list(orbit_type=orbit_type, max_dt=max(orbit_dts))
        # Split up for quicker parsing of the latest one
        mission_to_eof_list = {
            "S1A": [eof for eof in eof_list if eof.mission == "S1A"],
            "S1B": [eof for eof in eof_list if eof.mission == "S1B"],
        }
        # For precise orbits, we can have a larger front margin to ensure we
        # cover the ascending node crossing
        if orbit_type == "precise":
            margin0 = timedelta(seconds=T_ORBIT + 60)
        else:
            margin0 = timedelta(seconds=60)

        remaining_orbits = []
        urls = []
        for dt, mission in zip(orbit_dts, missions):
            try:
                filename = last_valid_orbit(
                    dt, dt, mission_to_eof_list[mission], margin0=margin0
                )
                urls.append(self.urls[orbit_type] + filename)
            except ValidityError:
                remaining_orbits.append((dt, mission))

        if remaining_orbits:
            logger.warning("The following dates were not found: %s", remaining_orbits)
            if orbit_type == "precise":
                logger.warning(
                    "Attempting to download the restituted orbits for these dates."
                )
                remaining_dts, remaining_missions = zip(*remaining_orbits)
                urls.extend(
                    self.get_download_urls(
                        remaining_dts, remaining_missions, orbit_type="restituted"
                    )
                )

        return urls

    def _get_cached_filenames(self, orbit_type="precise"):
        """Get the cache path for the ASF orbit files."""
        filepath = self._get_filename_cache_path(orbit_type)
        logger.debug(f"ASF file path cache: {filepath = }")
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return [SentinelOrbit(f) for f in f.read().splitlines()]
        return None

    def _write_cached_filenames(self, orbit_type="precise", eof_list=[]):
        """Cache the ASF orbit files."""
        filepath = self._get_filename_cache_path(orbit_type)
        with open(filepath, "w") as f:
            for e in eof_list:
                f.write(e.filename + "\n")

    def _clear_cache(self, orbit_type="precise"):
        """Clear the cache for the ASF orbit files."""
        filepath = self._get_filename_cache_path(orbit_type)
        os.remove(filepath)

    def _get_filename_cache_path(self, orbit_type="precise"):
        fname = "{}_filenames.txt".format(orbit_type.lower())
        return os.path.join(self.get_cache_dir(), fname)

    def get_cache_dir(self):
        """Find location of directory to store .hgt downloads
        Assuming linux, uses ~/.cache/sentineleof/
        """
        if self._cache_dir is not None:
            return self._cache_dir
        path = os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        path = os.path.join(path, "sentineleof")  # Make subfolder for our downloads
        logger.debug("Cache path: %s", path)
        if not os.path.exists(path):
            os.makedirs(path)
        return path
