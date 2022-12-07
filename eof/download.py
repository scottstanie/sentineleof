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
import os
import glob
from zipfile import ZipFile
import itertools
import requests
from multiprocessing.pool import ThreadPool
from dateutil.parser import parse
from .scihubclient import ASFClient, ScihubGnssClient
from .products import Sentinel, SentinelOrbit
from .log import logger

MAX_WORKERS = 6  # workers to download in parallel (for ASF backup)


def download_eofs(orbit_dts=None, missions=None, sentinel_file=None, save_dir=".",
                  orbit_type="precise"):
    """Downloads and saves EOF files for specific dates

    Args:
        orbit_dts (list[str] or list[datetime.datetime]): datetime for orbit coverage
        missions (list[str]): optional, to specify S1A or S1B
            No input downloads both, must be same len as orbit_dts
        sentinel_file (str): path to Sentinel-1 filename to download one .EOF for
        save_dir (str): directory to save the EOF files into
        orbit_type (str): precise or restituted

    Returns:
        list[str]: all filenames of saved orbit files

    Raises:
        ValueError - for missions argument not being one of 'S1A', 'S1B',
            having different lengths, or `sentinel_file` being invalid
    """
    # TODO: condense list of same dates, different hours?
    if missions and all(m not in ("S1A", "S1B") for m in missions):
        raise ValueError('missions argument must be "S1A" or "S1B"')
    if sentinel_file:
        sent = Sentinel(sentinel_file)
        orbit_dts, missions = [sent.start_time], [sent.mission]
    if missions and len(missions) != len(orbit_dts):
        raise ValueError("missions arg must be same length as orbit_dts")
    if not missions:
        missions = itertools.repeat(None)

    # First make sure all are datetimes if given string
    orbit_dts = [parse(dt) if isinstance(dt, str) else dt for dt in orbit_dts]

    filenames = []
    scihub_successful = False
    client = ScihubGnssClient()

    # First, check that Scihub isn't having issues
    if client.server_is_up():
        # try to search on scihub
        if sentinel_file:
            query = client.query_orbit_for_product(sentinel_file, orbit_type=orbit_type)
        else:
            query = client.query_orbit_by_dt(orbit_dts, missions, orbit_type=orbit_type)

        if query:
            result = client.download_all(query, directory_path=save_dir)
            filenames.extend(
                item['path'] for item in result.downloaded.values()
            )
            scihub_successful = True

    # For failures from scihub, try ASF
    if not scihub_successful:
        logger.warning("Scihub failed, trying ASF")
        asfclient = ASFClient()
        urls = asfclient.get_download_urls(orbit_dts, missions, orbit_type=orbit_type)
        # Download and save all links in parallel
        pool = ThreadPool(processes=MAX_WORKERS)
        result_url_dict = {
            pool.apply_async(_download_and_write, (url,)): url
            for url in urls
        }

        for result, url in result_url_dict.items():
            cur_filenames = result.get()
            if cur_filenames is None:
                logger.error("Failed to download orbit for %s", url)
            else:
                logger.info("Finished %s, saved to %s", url, cur_filenames)
                filenames.append(cur_filenames)

    return filenames


def _download_and_write(url, save_dir="."):
    """Wrapper function to run the link downloading in parallel

    Args:
        url (str): url of orbit file to download
        save_dir (str): directory to save the EOF files into

    Returns:
        list[str]: Filenames to which the orbit files have been saved
    """
    fname = os.path.join(save_dir, url.split("/")[-1])
    if os.path.isfile(fname):
        logger.info("%s already exists, skipping download.", url)
        return [fname]

    logger.info("Downloading %s", url)
    response = requests.get(url)
    response.raise_for_status()
    logger.info("Saving to %s", fname)
    with open(fname, "wb") as f:
        f.write(response.content)
    if fname.endswith(".zip"):
        _extract_zip(fname, save_dir=save_dir)
        # Pass the unzipped file ending in ".EOF", not the ".zip"
        fname = fname.replace(".zip", "")
    return fname


def _extract_zip(fname_zipped, save_dir=None, delete=True):
    if save_dir is None:
        save_dir = os.path.dirname(fname_zipped)
    with ZipFile(fname_zipped, "r") as zip_ref:
        # Extract the .EOF to the same direction as the .zip
        zip_ref.extractall(path=save_dir)

        # check that there's not a nested zip structure
        zipped = zip_ref.namelist()[0]
        zipped_dir = os.path.dirname(zipped)
        if zipped_dir:
            no_subdir = os.path.join(save_dir, os.path.split(zipped)[1])
            os.rename(os.path.join(save_dir, zipped), no_subdir)
            os.rmdir(os.path.join(save_dir, zipped_dir))
    if delete:
        os.remove(fname_zipped)


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


def main(search_path=".", save_dir=",", sentinel_file=None, mission=None, date=None, orbit_type="precise"):
    """Function used for entry point to download eofs"""

    if not os.path.exists(save_dir):
        logger.info("Creating directory for output: %s", save_dir)
        os.mkdir(save_dir)

    if (mission and not date):
        raise ValueError("Must specify date if providing mission.")

    if sentinel_file:
        # Handle parsing in download_eof
        orbit_dts, missions = None, None
    elif date:
        missions = [mission] if mission else ["S1A", "S1B"]
        orbit_dts = [date] * len(missions)
    else:
        # No command line args given: search current directory
        orbit_dts, missions = find_scenes_to_download(
            search_path=search_path, save_dir=save_dir
        )
        if not orbit_dts:
            logger.info(
                "No Sentinel products found in directory %s, exiting", search_path
            )
            return 0

    return download_eofs(
        orbit_dts=orbit_dts,
        missions=missions,
        sentinel_file=sentinel_file,
        save_dir=save_dir,
        orbit_type=orbit_type,
    )
