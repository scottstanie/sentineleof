"""Client to get orbit files from ASF via the public S3 bucket.

Now uses public S3 endpoints and does not require authentication.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import requests

from ._asf_s3 import get_orbit_files, ASF_BUCKET_NAME
from ._select_orbit import T_ORBIT, ValidityError, last_valid_orbit
from ._types import Filename
from .log import logger
from .products import SentinelOrbit


class ASFClient:
    eof_lists = {"precise": None, "restituted": None}

    def __init__(
        self,
        cache_dir: Filename | None = None,
        username: str = "",
        password: str = "",
        netrc_file: Filename | None = None,
    ):
        """Initialize the ASF client.

        The interface still accepts username, password, etc.,
        these are now ignored since orbit files are publicly available via S3.
        """
        self._cache_dir = cache_dir

    def get_full_eof_list(
        self, orbit_type="precise", max_dt=None
    ) -> list[SentinelOrbit]:
        """Get the list of orbit files from the public S3 bucket.

        If a cached file list exists and is current, that file is used.
        Otherwise the list is retrieved fresh from S3.

        Args:
            orbit_type (str): Either "precise" or "restituted"
            max_dt (datetime, optional): latest datetime requested; if the cached
                list is older than this, the cache is cleared.

        Returns:
            list[SentinelOrbit]: list of orbit file objects
        """
        if orbit_type not in ("precise", "restituted"):
            raise ValueError(f"Unknown orbit type: {orbit_type}")

        if self.eof_lists.get(orbit_type) is not None:
            return self.eof_lists[orbit_type]
        # Try to see if we have the list of EOFs in the cache
        cache_path = self._get_filename_cache_path(orbit_type)
        if os.path.exists(cache_path):
            eof_list = self._get_cached_filenames(orbit_type)
            # Clear the cache if the newest saved file is older than requested
            max_saved = max(e.start_time for e in eof_list)
            if max_dt is not None and max_saved < max_dt:
                logger.warning("Clearing cached %s EOF list:", orbit_type)
                logger.warning("%s is older than requested %s", max_saved, max_dt)
                self._clear_cache(orbit_type)
            else:
                logger.info("Using cached EOF list")
                self.eof_lists[orbit_type] = eof_list
                return eof_list

        logger.info("Downloading orbit file list from public S3 bucket")
        keys = get_orbit_files(orbit_type)
        eof_list = [SentinelOrbit(f) for f in keys]
        self.eof_lists[orbit_type] = eof_list
        self._write_cached_filenames(orbit_type, eof_list)
        return eof_list

    def get_download_urls(
        self, orbit_dts: list[datetime], missions: list[str], orbit_type="precise"
    ) -> list[str]:
        """Find the download URL for an orbit file covering the specified datetime.

        Args:
            orbit_dts (list[datetime]): requested dates for orbit coverage.
            missions (list[str]): specify S1A or S1B (should be same length as orbit_dts).
            orbit_type (str): either "precise" or "restituted".

        Returns:
            list[str]: URLs for the orbit files.

        Raises:
            ValidityError if an orbit is not found.
        """
        eof_list = self.get_full_eof_list(orbit_type=orbit_type, max_dt=max(orbit_dts))
        # Split up for quicker parsing by mission
        mission_to_eof_list = {
            "S1A": [eof for eof in eof_list if eof.mission == "S1A"],
            "S1B": [eof for eof in eof_list if eof.mission == "S1B"],
            "S1C": [eof for eof in eof_list if eof.mission == "S1C"],
        }
        # For precise orbits, use a larger front margin to ensure coverage
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
                # Construct the full download URL using the bucket name from _asf_s3
                url = f"https://{ASF_BUCKET_NAME}.s3.amazonaws.com/{filename}"
                urls.append(url)
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

    def _get_cached_filenames(
        self, orbit_type: Literal["precise", "restituted"]
    ) -> list[SentinelOrbit] | None:
        """Read the cache file for the ASF orbit filenames."""
        filepath = self._get_filename_cache_path(orbit_type)
        logger.debug(f"ASF file path cache: {filepath = }")
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return [SentinelOrbit(f) for f in f.read().splitlines()]
        return None

    def _write_cached_filenames(self, orbit_type="precise", eof_list=[]) -> None:
        """Cache the ASF orbit filenames."""
        filepath = self._get_filename_cache_path(orbit_type)
        with open(filepath, "w") as f:
            for e in eof_list:
                f.write(e.filename + "\n")

    def _clear_cache(self, orbit_type="precise") -> None:
        """Clear the cache for the ASF orbit filenames."""
        filepath = self._get_filename_cache_path(orbit_type)
        os.remove(filepath)

    def _get_filename_cache_path(self, orbit_type="precise") -> str:
        fname = f"{orbit_type.lower()}_filenames.txt"
        return os.path.join(self.get_cache_dir(), fname)

    def get_cache_dir(self) -> Path | str:
        """Determine the directory to store orbit file caches.

        Returns:
            str: Directory path
        """
        if self._cache_dir is not None:
            return self._cache_dir
        path = os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        path = os.path.join(path, "sentineleof")
        logger.debug("Cache path: %s", path)
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def _download_and_write(self, url: str, save_dir: str = ".") -> Path:
        """Download an orbit file from a URL and save it to save_dir.

        Args:
            url (str): URL of the orbit file to download.
            save_dir (str): Directory to save the orbit file.

        Returns:
            Path: Path to the saved orbit file.
        """
        fname = Path(save_dir) / url.split("/")[-1]
        if os.path.isfile(fname):
            logger.info("%s already exists, skipping download.", url)
            return fname

        logger.info("Downloading %s", url)
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error("Failed to download %s: %s", url, e)
            raise

        logger.info("Saving to %s", fname)
        with open(fname, "wb") as f:
            f.write(response.content)
        return fname
