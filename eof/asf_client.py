"""sentinelsat based client to get orbit files form scihub.copernicu.eu."""
from __future__ import annotations

import operator
import os
from datetime import datetime, timedelta
from typing import Sequence

import requests

from .log import logger
from .products import SentinelOrbit
from .parsing import EOFLinkFinder


T_ORBIT = (12 * 86400.0) / 175.0
"""Orbital period of Sentinel-1 in seconds"""

QUERY_ENDPOINT = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
"""Default URL endpoint for the Copernicus Data Space Ecosystem (CDSE) query REST service"""

AUTH_ENDPOINT = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
"""Default URL endpoint for performing user authentication with CDSE"""

DOWNLOAD_ENDPOINT = "https://zipper.dataspace.copernicus.eu/odata/v1/Products"
"""Default URL endpoint for CDSE download REST service"""


class ValidityError(ValueError):
    pass


def lastval_cover(
    t0: datetime,
    t1: datetime,
    data: Sequence[SentinelOrbit],
    margin0=timedelta(seconds=T_ORBIT + 60),
    margin1=timedelta(minutes=5),
) -> str:
    # Using a start margin of > 1 orbit so that the start of the orbit file will
    # cover the ascending node crossing of the acquisition
    candidates = [
        item
        for item in data
        if item.start_time <= (t0 - margin0) and item.stop_time >= (t1 + margin1)
    ]
    if not candidates:
        raise ValidityError(
            "none of the input products completely covers the requested "
            "time interval: [t0={}, t1={}]".format(t0, t1)
        )

    candidates.sort(key=operator.attrgetter("created_time"), reverse=True)

    return candidates[0].filename


class ASFClient:
    precise_url = "https://s1qc.asf.alaska.edu/aux_poeorb/"
    res_url = "https://s1qc.asf.alaska.edu/aux_resorb/"
    urls = {"precise": precise_url, "restituted": res_url}
    eof_lists = {"precise": None, "restituted": None}

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
        remaining_orbits = []
        urls = []
        for dt, mission in zip(orbit_dts, missions):
            try:
                filename = lastval_cover(dt, dt, mission_to_eof_list[mission])
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

    @staticmethod
    def _get_filename_cache_path(orbit_type="precise"):
        fname = "{}_filenames.txt".format(orbit_type.lower())
        return os.path.join(ASFClient.get_cache_dir(), fname)

    @staticmethod
    def get_cache_dir():
        """Find location of directory to store .hgt downloads
        Assuming linux, uses ~/.cache/sentineleof/
        """
        path = os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        path = os.path.join(path, "sentineleof")  # Make subfolder for our downloads
        print(path)
        if not os.path.exists(path):
            os.makedirs(path)
        return path
