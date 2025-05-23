#!/usr/bin/env python
"""
Utility for downloading Sentinel precise orbit ephemerides (EOF) files

Example filtering URL:
?validity_start_time=2014-08&page=2

Example EOF: 'S1A_OPER_AUX_POEORB_OPOD_20140828T122040_V20140806T225944_20140808T005944.EOF'

 'S1A' : mission id (satellite it applies to)
 'OPER' : OPER for "Routine Operations" file
 'AUX_POEORB' : AUX_ for "auxiliary data file", POEORB=Precise Orbit Ephemerides (POE) Orbit File
 'OPOD'  Site Center of the file originator

 '20140828T122040' creation date of file
 'V20140806T225944' Validity start time (when orbit is valid)
 '20140808T005944' Validity end time

Full EOF sentinel doumentation:
https://earth.esa.int/documents/247904/349490/GMES_Sentinels_POD_Service_File_Format_Specification_GMES-GSEG-EOPG-FS-10-0075_Issue1-3.pdf

See parsers for Sentinel file naming description
"""

from __future__ import annotations

import glob
import itertools
import os
from collections.abc import Sequence
from datetime import datetime
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import Literal, Optional

from dateutil.parser import parse
from requests.exceptions import HTTPError

from ._types import Filename
from .asf_client import ASFClient
from .dataspace_client import DataspaceClient
from .log import logger
from .products import Sentinel, SentinelOrbit

MAX_WORKERS = 6  # workers to download in parallel (for ASF backup)


def download_eofs(
    orbit_dts: Sequence[datetime | str] | None = None,
    missions: Sequence[str] | None = None,
    sentinel_file: str | None = None,
    save_dir: str = ".",
    orbit_type: Literal["precise", "restituted"] = "precise",
    force_asf: bool = False,
    asf_user: str = "",
    asf_password: str = "",
    cdse_access_token: Optional[str] = None,
    cdse_user: str = "",
    cdse_password: str = "",
    cdse_2fa_token: str = "",
    netrc_file: Optional[Filename] = None,
    max_workers: int = MAX_WORKERS,
) -> list[Path]:
    """Downloads and saves Sentinel precise or restituted orbit files (EOF).

    By default, it tries to download from Copernicus Data Space Ecosystem first,
    then falls back to ASF if the first source fails (unless `force_asf` is True).

    Parameters
    ----------
    orbit_dts : list[datetime] or list[str] or None
        List of datetimes for orbit coverage.
        If strings are provided, they will be parsed into datetime objects.
    missions : list[str] or None
        List of mission identifiers ('S1A', 'S1B', or 'S1C'). If None,
        orbits for all missions will be attempted. Must be same length as orbit_dts.
    sentinel_file : str or None
        Path to a Sentinel-1 file to download a matching EOF for.
        If provided, orbit_dts and missions are ignored.
    save_dir : str, default="."
        Directory to save the downloaded EOF files into.
    orbit_type : {'precise', 'restituted'}, default='precise'
        Type of orbit file to download (precise=POEORB or restituted=RESORB).
    force_asf : bool, default=False
        If True, skip trying Copernicus Data Space and download directly from ASF.
    asf_user : str, default=""
        ASF username (deprecated, ASF orbits are now publicly available).
    asf_password : str, default=""
        ASF password (deprecated, ASF orbits are now publicly available).
    cdse_access_token : str or None, default=None
        Copernicus Data Space Ecosystem access token.
    cdse_user : str, default=""
        Copernicus Data Space Ecosystem username.
    cdse_password : str, default=""
        Copernicus Data Space Ecosystem password.
    cdse_2fa_token : str, default=""
        Copernicus Data Space Ecosystem two-factor authentication token.
    netrc_file : str or None, default=None
        Path to .netrc file for authentication credentials.
    max_workers : int, default=MAX_WORKERS
        Number of parallel downloads to run.

    Returns
    -------
    list[Path]
        Paths to all successfully downloaded orbit files.

    Raises
    ------
    ValueError
        If missions argument contains values other than 'S1A', 'S1B', 'S1C',
        if missions and orbit_dts have different lengths, or if sentinel_file is invalid.
    HTTPError
        If there's an HTTP error during download that's not a rate limit error.
    """
    # TODO: condense list of same dates, different hours?
    if missions and all(m not in ("S1A", "S1B", "S1C") for m in missions):
        raise ValueError('missions argument must be "S1A", "S1B" or "S1C"')
    if sentinel_file:
        sent = Sentinel(sentinel_file)
        orbit_dts, missions = [sent.start_time], [sent.mission]
    assert orbit_dts is not None and missions is not None
    if missions and len(missions) != len(orbit_dts):
        raise ValueError("missions arg must be same length as orbit_dts")
    if not missions:
        missions = itertools.repeat(None)

    # First make sure all are datetimes if given string
    orbit_dts = [parse(dt) if isinstance(dt, str) else dt for dt in orbit_dts]

    filenames = []
    dataspace_successful = False

    # First, check that Scihub isn't having issues
    if not force_asf:
        client = DataspaceClient(
            access_token=cdse_access_token,
            username=cdse_user,
            password=cdse_password,
            token_2fa=cdse_2fa_token,
            netrc_file=netrc_file,
        )
        if client:
            # try to search on scihub
            if sentinel_file:
                query = client.query_orbit_for_product(
                    sentinel_file, orbit_type=orbit_type
                )
            else:
                query = client.query_orbit_by_dt(
                    orbit_dts, missions, orbit_type=orbit_type
                )

            if query:
                logger.info("Attempting download from Copernicus Data Space Ecosystem")
                try:
                    results = client.download_all(
                        query, output_directory=save_dir, max_workers=max_workers
                    )
                    filenames.extend(results)
                    dataspace_successful = True
                except HTTPError as e:
                    assert e.response is not None
                    if e.response.status_code == 429:
                        logger.warning(f"Failed due to too many requests: {e.args}")
                        # Dataspace failed -> try asf
                    else:
                        raise

    # For failures from scihub, try ASF
    if not dataspace_successful:
        if not force_asf:
            logger.warning("Dataspace failed, trying ASF")

        asf_client = ASFClient()
        urls = asf_client.get_download_urls(orbit_dts, missions, orbit_type=orbit_type)
        # Download and save all links in parallel
        pool = ThreadPool(processes=max_workers)
        result_url_dict = {
            pool.apply_async(
                asf_client._download_and_write,
                args=[url, save_dir],
            ): url
            for url in urls
        }

        for result, url in result_url_dict.items():
            cur_filename = result.get()
            if cur_filename is None:
                logger.error("Failed to download orbit for %s", url)
            else:
                logger.info("Finished %s, saved to %s", url, cur_filename)
                filenames.append(cur_filename)

    return filenames


def find_current_eofs(cur_path):
    """Returns a list of SentinelOrbit objects located in `cur_path`"""
    return sorted(
        [
            SentinelOrbit(filename)
            for filename in glob.glob(os.path.join(cur_path, "S1*OPER*.EOF"))
        ]
    )


def find_unique_safes(search_path):
    file_set = set()
    for filename in glob.glob(os.path.join(search_path, "S1*")):
        try:
            parsed_file = Sentinel(filename)
        except ValueError:  # Doesn't match a sentinel file
            logger.debug("Skipping {}, not a Sentinel 1 file".format(filename))
            continue
        file_set.add(parsed_file)
    return file_set


def find_scenes_to_download(search_path="./", save_dir="./"):
    """Parse the search_path directory for any Sentinel 1 products' date and mission"""
    orbit_dts = []
    missions = []
    # Check for already-downloaded orbit files, skip ones we have
    current_eofs = find_current_eofs(save_dir)

    # Now loop through each Sentinel scene in search_path
    for parsed_file in find_unique_safes(search_path):
        if parsed_file.start_time in orbit_dts:
            # start_time is a datetime, already found
            continue
        if any(parsed_file.start_time in orbit for orbit in current_eofs):
            logger.info(
                "Skipping {}, already have EOF file".format(
                    os.path.splitext(parsed_file.filename)[0]
                )
            )
            continue

        logger.info(
            "Downloading precise orbits for {} on {}".format(
                parsed_file.mission, parsed_file.start_time.strftime("%Y-%m-%d")
            )
        )
        orbit_dts.append(parsed_file.start_time)
        missions.append(parsed_file.mission)

    return orbit_dts, missions


def main(
    search_path=".",
    save_dir=".",
    sentinel_file=None,
    mission=None,
    date=None,
    orbit_type="precise",
    force_asf: bool = False,
    asf_user: str = "",
    asf_password: str = "",
    cdse_access_token: Optional[str] = None,
    cdse_user: str = "",
    cdse_password: str = "",
    cdse_2fa_token: str = "",
    netrc_file: Optional[Filename] = None,
    max_workers: int = MAX_WORKERS,
):
    """Function used for entry point to download eofs"""

    if not os.path.exists(save_dir):
        logger.info("Creating directory for output: %s", save_dir)
        os.mkdir(save_dir)

    if mission and not date:
        raise ValueError("Must specify date if providing mission.")

    if sentinel_file:
        # Handle parsing in download_eof
        orbit_dts, missions = None, None
    elif date:
        missions = [mission] if mission else ["S1A", "S1B", "S1C"]
        orbit_dts = [parse(date)] * len(missions)
        # Check they didn't pass a whole datetime
        if all((dt.hour == 0 and dt.minute == 0) for dt in orbit_dts):
            # If we only specify dates, make sure the whole thing is covered
            # This means we should set the `hour` to be late in the day
            orbit_dts = [dt.replace(hour=23) for dt in orbit_dts]
    else:
        # No command line args given: search current directory
        orbit_dts, missions = find_scenes_to_download(
            search_path=search_path, save_dir=save_dir
        )
        if not orbit_dts:
            logger.info(
                "No Sentinel products found in directory %s, exiting", search_path
            )
            return []

    return download_eofs(
        orbit_dts=orbit_dts,
        missions=missions,
        sentinel_file=sentinel_file,
        save_dir=save_dir,
        orbit_type=orbit_type,
        force_asf=force_asf,
        asf_user=asf_user,
        asf_password=asf_password,
        cdse_access_token=cdse_access_token,
        cdse_user=cdse_user,
        cdse_password=cdse_password,
        cdse_2fa_token=cdse_2fa_token,
        netrc_file=netrc_file,
        max_workers=max_workers,
    )
