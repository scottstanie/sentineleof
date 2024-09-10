"""Client to get orbit files from ASF."""
from __future__ import annotations
from multiprocessing.pool import ThreadPool

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence
from zipfile import ZipFile

import requests


from ._auth import NASA_HOST, get_netrc_credentials
from ._select_orbit import T_ORBIT, ValidityError, last_valid_orbit, valid_orbits
from ._types import Filename
from .client import AbstractSession, Client, OrbitType
from .log import logger
from .parsing import EOFLinkFinder
from .products import SentinelOrbit

SIGNUP_URL = "https://urs.earthdata.nasa.gov/users/new"
"""Url to prompt user to sign up for NASA Earthdata account."""


class ASFSession(AbstractSession):
    """
    Authenticated session to ASF.

    Downloading is the only service provided.
    """
    auth_url = (
        "https://urs.earthdata.nasa.gov/oauth/authorize?response_type=code&"
        "client_id=BO_n7nTIlMljdvU6kRRB3g&redirect_uri=https://auth.asf.alaska.edu/login"
    )

    def __init__(
        self,
        username: str = "",
        password: str = "",
        netrc_file: Optional[Filename] = None,
    ):
        if username and password:
            self._username = username
            self._password = password
        else:
            logger.debug(f"Get credentials form netrc ({netrc_file!r})")
            self._username = ""
            self._password = ""
            try:
                self._username, self._password = get_netrc_credentials(NASA_HOST, netrc_file)
            except FileNotFoundError:
                logger.warning("No netrc file found.")
            except ValueError as e:
                logger.warning(f"Can't find ASF cred: {e}")
                if NASA_HOST not in e.args[0]:
                    raise e
                logger.warning(
                    f"No NASA Earthdata credentials found in netrc file. Please create one using {SIGNUP_URL}"
                )

        self.session: Optional[requests.Session] = None
        if self._username and self._password:
            self.session = self.get_authenticated_session()

    def __bool__(self):
        """Tells whether the object has been correctly initialized"""
        return bool(self.session)

    def get_authenticated_session(self) -> requests.Session:
        """Get an authenticated `requests.Session` using earthdata credentials.

        Fuller example here:
        https://github.com/ASFHyP3/hyp3-sdk/blob/ec72fcdf944d676d5c8c94850d378d3557115ac0/src/hyp3_sdk/util.py#L67C8-L67C8

        Returns
        -------
        requests.Session
            Authenticated session
        """
        s = requests.Session()
        response = s.get(self.auth_url, auth=(self._username, self._password))
        response.raise_for_status()
        return s

    def _download_and_write(self, url: str, save_dir: Filename=".") -> Path:
        """Wrapper function to run the link downloading in parallel

        Args:
            url (str): url of orbit file to download
            save_dir (str): directory to save the EOF files into

        Returns:
            Path: Filename to saved orbit file
        """
        fname = Path(save_dir) / url.split("/")[-1]
        if os.path.isfile(fname):
            logger.info("%s already exists, skipping download.", url)
            return fname

        logger.info("Downloading %s", url)
        get_function = self.session.get if self.session is not None else requests.get
        try:
            response = get_function(url)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.warning(e)

            login_url = self.auth_url + f"&state={url}"
            logger.warning(
                "Failed to download %s. Trying URS login url: %s", url, login_url
            )
            # Add credentials
            response = get_function(login_url, auth=(self._username, self._password))
            response.raise_for_status()

        logger.info("Saving to %s", fname)
        with open(fname, "wb") as f:
            f.write(response.content)
        if fname.suffix == ".zip":
            ASFSession._extract_zip(fname, save_dir=save_dir)
            # Pass the unzipped file ending in ".EOF", not the ".zip"
            fname = fname.with_suffix("")
        return fname

    @staticmethod
    def _extract_zip(fname_zipped: Path, save_dir=None, delete=True):
        if save_dir is None:
            save_dir = fname_zipped.parent
        with ZipFile(fname_zipped, "r") as zip_ref:
            # Extract the .EOF to the same direction as the .zip
            zip_ref.extractall(path=save_dir)

            # check that there's not a nested zip structure
            zipped = zip_ref.namelist()[0]
            zipped_dir = os.path.dirname(zipped)
            if zipped_dir:
                no_subdir = save_dir / os.path.split(zipped)[1]
                os.rename((save_dir / zipped), no_subdir)
                os.rmdir((save_dir / zipped_dir))
        if delete:
            os.remove(fname_zipped)

    def download_all(
        self,
        eofs: list[str],
        output_directory: Filename,
        max_workers: int = 3,
    ) -> List[Filename]:
        filenames: List[Filename] = []
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
    precise_url = "https://s1qc.asf.alaska.edu/aux_poeorb/"
    res_url = "https://s1qc.asf.alaska.edu/aux_resorb/"
    urls = {OrbitType.precise: precise_url, OrbitType.restituted: res_url}
    eof_lists : Dict[OrbitType, Optional[Sequence[SentinelOrbit]]] = {
            OrbitType.precise: None,
            OrbitType.restituted: None
    }

    def __init__(
        self,
        cache_dir: Optional[Filename] = None,
    ):
        self._cache_dir = cache_dir

    def authenticate(self, *args, **kwargs) -> ASFSession:
        """
        Authenticate to the client.

        The authentication will try to use in order:
        1. ``username`` + ``password`` 
        2. dataspace entry from ``netrc_file`` (or $NETRC, or ``~/.netrc``)

        Args:
            username (str): Optional user name
            password (str): Optional use password
            netrc_file (Optional[Filename]): Optional name of netrc file

        :raise FileNotFoundError: if ``netrc`` file cannot be found.
        :raise ValueError: if there is no entry for ASF host in the netrc
        :raises RuntimeError: if the access token cannot be created
        """
        return ASFSession(*args, **kwargs)

    def query_orbit_by_dt(
            self,
            orbit_dts: Sequence[datetime],
            missions: Sequence[str],
            orbit_type: OrbitType,
            t0_margin: timedelta = Client.T0,
            t1_margin: timedelta = Client.T1,
    ) -> List[str]:
        return self.get_download_urls(orbit_dts, missions, orbit_type)

    def get_full_eof_list(
            self,
            orbit_type: OrbitType = OrbitType.precise,
            max_dt : Optional[datetime] = None
    ) -> Sequence[SentinelOrbit]:
        """Get the list of orbit files from the ASF server."""
        if orbit_type not in self.urls:
            raise ValueError(f"Unknown orbit type: {orbit_type.name}")

        if (eof_list := self.eof_lists.get(orbit_type)) is not None:
            return eof_list
        # Try to see if we have the list of EOFs in the cache
        elif os.path.exists(self._get_filename_cache_path(orbit_type)):
            eof_list = self._get_cached_filenames(orbit_type)
            # Need to clear it if it's older than what we're looking for
            max_saved = max((e.start_time for e in eof_list))
            if not max_dt or (max_saved < max_dt):
                logger.warning(f"Clearing cached {orbit_type.name} EOF list:")
                logger.warning(f"{max_saved} is older than requested {max_dt}")
                self._clear_cache(orbit_type)
            else:
                logger.info("Using %s elements from cached EOF list", len(eof_list))
                self.eof_lists[orbit_type] = eof_list
                return eof_list

        logger.info("Downloading all filenames from ASF (may take awhile)")
        assert orbit_type in self.urls
        resp = requests.get(self.urls[orbit_type])
        finder = EOFLinkFinder()
        finder.feed(resp.text)
        eof_list = [SentinelOrbit(f) for f in finder.eof_links]
        self.eof_lists[orbit_type] = eof_list
        self._write_cached_filenames(orbit_type, eof_list)
        return eof_list

    def get_download_urls(
            self,
            orbit_dts: Sequence[datetime],
            missions: Iterable[str],
            orbit_type: OrbitType = OrbitType.precise
    ) -> List[str]:
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
        if orbit_type == OrbitType.precise:
            margin0 = Client.T0
        else:
            margin0 = Client.T1

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
    ) -> List[str]:
        orbits = self.query_orbit_files_by_dt_range(first_dt, last_dt, missions, orbit_type)
        urls = [self.urls[orbit_type] + orbit.filename for orbit in orbits]
        return urls

    def query_orbit_files_by_dt_range(
        self,
        first_dt: datetime,
        last_dt: datetime,
        missions: Sequence[str] = (),
        orbit_type: OrbitType = OrbitType.precise,
    ) -> List[SentinelOrbit]:
        eof_list = self.get_full_eof_list(orbit_type=orbit_type, max_dt=last_dt)
        missions = missions or ("S1A", "S1B")
        # Split up for quicker parsing of the latest one
        mission_to_eof_list = {
            "S1A": [eof for eof in eof_list if eof.mission == "S1A"],
            "S1B": [eof for eof in eof_list if eof.mission == "S1B"],
        }
        orbits = []
        for mission in missions:
            orbits.extend(valid_orbits(last_dt, first_dt, mission_to_eof_list[mission]))

        return orbits

    def _get_cached_filenames(
            self,
            orbit_type: OrbitType = OrbitType.precise
    ) -> List[SentinelOrbit]:
        """Get the cache path for the ASF orbit files."""
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
        """Cache the ASF orbit files."""
        eof_list = eof_list or []
        filepath = self._get_filename_cache_path(orbit_type)
        with open(filepath, "w") as f:
            for e in eof_list:
                f.write(e.filename + "\n")

    def _clear_cache(self, orbit_type: OrbitType = OrbitType.precise) -> None:
        """Clear the cache for the ASF orbit files."""
        filepath = self._get_filename_cache_path(orbit_type)
        os.remove(filepath)

    def _get_filename_cache_path(self, orbit_type: OrbitType = OrbitType.precise) -> str:
        fname = f"{orbit_type.name}_filenames.txt"
        return os.path.join(self.get_cache_dir(), fname)

    def get_cache_dir(self) -> Filename:
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
