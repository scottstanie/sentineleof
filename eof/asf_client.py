"""Client to get orbit files from ASF via the public S3 bucket.

Now uses public S3 endpoints and does not require authentication.
"""

from __future__ import annotations
from multiprocessing.pool import ThreadPool

import os
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from pathlib import Path

import requests

from ._asf_s3 import get_orbit_files, ASF_BUCKET_NAME
from ._select_orbit import ValidityError, last_valid_orbit, valid_orbits
from ._types import Filename
from .client import AbstractSession, Client, OrbitType
from .log import logger
from .products import SentinelOrbit


class ASFSession(AbstractSession):
    """
    Authenticated session to ASF.

    Downloading is the only service provided.

    The interface doesn't take any username, password, etc., since orbit files
    are publicly available via S3.
    """
    def __init__(self):
        pass

    def __bool__(self):
        """Tells whether the object has been correctly initialized"""
        return True

    def _download_and_write(self, url: str, save_dir: Filename=".") -> Path:
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
            _ = f.write(response.content)
        return fname

    def download_all(
        self,
        eofs: list[str],
        output_directory: Filename,
        max_workers: int = 3,
    ) -> list[Path]:
        filenames: list[Path] = []
        pool = ThreadPool(processes=max_workers)
        result_url_dict = {
            pool.apply_async(
                self._download_and_write,
                args=[url, output_directory],
            ): url
            for url in eofs
        }

        for result, url in result_url_dict.items():
            cur_filename = result.get()
            if cur_filename is None:
                # FIXME: input method (_download_and_write throws and never return None)
                # => Chose: trace and continue (what we try to do here), or abort (_download_and_write)
                logger.error("Failed to download orbit for %s", url)
            else:
                logger.info("Finished %s, saved to %s", url, cur_filename)
                filenames.append(cur_filename)
        return filenames


class ASFClient(Client):
    """
    Client dedicated to ASF.

    Provides:
    - query methods that return eof products matching the search
      criteria.
    - authentication method that'll return a :class:`DataspaceSession`
      object which will permit downloading eof products found.
    """
    precise_url : str = "https://s1qc.asf.alaska.edu/aux_poeorb/"
    res_url     : str = "https://s1qc.asf.alaska.edu/aux_resorb/"

    def __init__(
        self,
        cache_dir: Filename | None = None,
    ):
        self._cache_dir : Filename|None = cache_dir
        # Non-static member data in order to play with different data in tests
        self.eof_lists : dict[OrbitType, Sequence[SentinelOrbit]|None] = {
            OrbitType.precise: None,
            OrbitType.restituted: None
        }

    def authenticate(self) -> ASFSession:
        """
        Returns an ASF session object.
        No actual authentication is done for ASF S3 servers.
        """
        return ASFSession()

    def query_orbit_by_dt(
            self,
            orbit_dts: Sequence[datetime],
            missions: Sequence[str],
            orbit_type: OrbitType,
            t0_margin: timedelta = Client.T0,
            t1_margin: timedelta = Client.T1,
    ) -> list[str]:
        return self.get_download_urls(orbit_dts, missions, orbit_type)

    def get_full_eof_list(
            self,
            orbit_type: OrbitType = OrbitType.precise,
            max_dt : datetime|None = None
    ) -> Sequence[SentinelOrbit]:
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
        if orbit_type not in self.eof_lists:
            # Should never happen by construction
            raise AssertionError(f"Unknown orbit type: {orbit_type.name}")

        if (eof_list := self.eof_lists.get(orbit_type)) is not None:
            return eof_list
        # Try to see if we have the list of EOFs in the cache
        cache_path = self._get_filename_cache_path(orbit_type)
        if os.path.exists(cache_path):
            eof_list = self._get_cached_filenames(orbit_type)
            # Clear the cache if the newest saved file is older than requested
            max_saved = max((e.start_time for e in eof_list))
            if max_dt is not None and max_saved < max_dt:
                logger.warning("Clearing cached %s EOF list:", orbit_type.name)
                logger.warning("%s is older than requested %s", max_saved, max_dt)
                self._clear_cache(orbit_type)
            else:
                logger.info("Using %s elements from cached EOF list", len(eof_list))
                self.eof_lists[orbit_type] = eof_list
                return eof_list

        logger.info("Downloading orbit file list from public S3 bucket")
        keys = get_orbit_files(orbit_type)
        eof_list = [SentinelOrbit(f) for f in keys]
        self.eof_lists[orbit_type] = eof_list
        self._write_cached_filenames(orbit_type, eof_list)
        return eof_list

    def get_download_urls(
            self,
            orbit_dts: Sequence[datetime],
            missions: Iterable[str],
            orbit_type: OrbitType = OrbitType.precise
    ) -> list[str]:
        """Find the URL for an orbit file covering the specified datetime

        Args:
            orbit_dts (list[datetime]): requested dates for orbit coverage.
            missions (list[str]): specify S1A, S1B or S1C
            orbit_type (OrbitType): either "precise" or "restituted".

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
        if orbit_type == OrbitType.precise:
            margin0 = Client.T0
        else:
            margin0 = Client.T1

        remaining_orbits : list[tuple[datetime, str]] = []
        urls : list[str] = []
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
            if orbit_type == OrbitType.precise:
                logger.warning(
                    "Attempting to download the restituted orbits for these dates."
                )
                remaining_dts, remaining_missions = zip(*remaining_orbits)
                urls.extend(
                    self.get_download_urls(
                        remaining_dts, remaining_missions, orbit_type=OrbitType.restituted
                    )
                )

        return urls

    def query_orbits_by_dt_range(
        self,
        first_dt: datetime,
        last_dt: datetime,
        missions: Sequence[str] = (),
        orbit_type: OrbitType = OrbitType.precise,
    ) -> list[str]:
        """Query the ASF API for product URLs for the specified missions/orbit time range.

        This method returns the URLs of all orbit files that intersect the requested range.

        Parameters
        ----------
        first_dt (str datetime.datetime): first datetime for orbit coverage
        last_dt (str datetime.datetime): last datetime for orbit coverage
        missions (list[str]): optional, to specify S1A, S1B or S1C
            No input downloads both.
        orbit_type : OrbitType, choices = {precise, restituted}

        Returns
        -------
        list[str]
            list of urls to files to download.
            This result can be directly used by:method:`DataspaceClient.download_all`.
        """
        orbits = self.query_orbit_files_by_dt_range(first_dt, last_dt, missions, orbit_type)
        urls = [f"https://{ASF_BUCKET_NAME}.s3.amazonaws.com/{orbit.filename}" for orbit in orbits]
        return urls

    def query_orbit_files_by_dt_range(
        self,
        first_dt: datetime,
        last_dt: datetime,
        missions: Sequence[str] = (),
        orbit_type: OrbitType = OrbitType.precise,
    ) -> list[SentinelOrbit]:
        """Query the ASF API for product info for the specified missions/orbit time range.

        This method returns the information of all orbit files that intersect the requested range.

        Parameters
        ----------
        first_dt (str datetime.datetime): first datetime for orbit coverage
        last_dt (str datetime.datetime): last datetime for orbit coverage
        missions (list[str]): optional, to specify S1A, S1B or S1C
            No input downloads both.
        orbit_type : OrbitType, choices = {precise, restituted}

        Returns
        -------
        list[SentinelOrbit]
            list of information about the files to download
            This result CANNOT be directly used by:method:`DataspaceClient.download_all`.
        """
        eof_list = self.get_full_eof_list(orbit_type=orbit_type, max_dt=last_dt)
        missions = missions or ("S1A", "S1B", "S1C")
        # Split up for quicker parsing of the latest one
        mission_to_eof_list = {
            "S1A": [eof for eof in eof_list if eof.mission == "S1A"],
            "S1B": [eof for eof in eof_list if eof.mission == "S1B"],
            "S1C": [eof for eof in eof_list if eof.mission == "S1C"],
        }
        orbits : list[SentinelOrbit] = []
        for mission in missions:
            assert mission in ("S1A", "S1B", "S1C"), f"Invalid {mission=!r}"
            orbits.extend(valid_orbits(
                last_dt,
                first_dt,
                mission_to_eof_list[mission],
                timedelta(0),
                timedelta(0),
            ))

        return orbits

    def _get_cached_filenames(
            self,
            orbit_type: OrbitType = OrbitType.precise
    ) -> list[SentinelOrbit]:
        """Read the cache file for the ASF orbit filenames."""
        filepath = self._get_filename_cache_path(orbit_type)
        logger.debug(f"ASF file path cache: {filepath = }")
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return [SentinelOrbit(f) for f in f.read().splitlines()]
        return []

    def _write_cached_filenames(
            self,
            orbit_type: OrbitType = OrbitType.precise,
            eof_list: Sequence[SentinelOrbit] = (),
    ) -> None:
        """Cache the ASF orbit filenames."""
        eof_list = eof_list or []
        filepath = self._get_filename_cache_path(orbit_type)
        with open(filepath, "w") as f:
            for e in eof_list:
                _ = f.write(e.filename + "\n")

    def _clear_cache(self, orbit_type: OrbitType = OrbitType.precise) -> None:
        """Clear the cache for the ASF orbit filenames."""
        filepath = self._get_filename_cache_path(orbit_type)
        os.remove(filepath)

    def _get_filename_cache_path(self, orbit_type: OrbitType = OrbitType.precise) -> str:
        fname = f"{orbit_type.name}_filenames.txt"
        return os.path.join(self.get_cache_dir(), fname)

    def get_cache_dir(self) -> Filename:
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
