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

API documentation: https://qc.sentinel1.eo.esa.int/doc/api/

See parsers for Sentinel file naming description
"""
import os
import glob
import itertools
import logging
import requests
from multiprocessing.pool import ThreadPool
from datetime import timedelta
from dateutil.parser import parse
from eof.parsers import Sentinel

MAX_WORKERS = 20  # For parallel downloading

BASE_URL = "https://qc.sentinel1.eo.esa.int/api/v1/?product_type=AUX_POEORB\
&validity_start__lt={start_date}&validity_stop__gt={stop_date}"

DATE_FMT = "%Y-%m-%d"  # Used in sentinel API url

logger = logging.Logger('sentineleof')


def _set_logger_handler(level='INFO'):
    logger.setLevel(level)
    h = logging.StreamHandler()
    h.setLevel(level)
    format_ = '[%(asctime)s] [%(levelname)s %(filename)s] %(message)s'
    fmt = logging.Formatter(format_, datefmt='%m/%d %H:%M:%S')
    h.setFormatter(fmt)
    logger.addHandler(h)


def download_eofs(orbit_dts, missions=None, save_dir="."):
    """Downloads and saves EOF files for specific dates

    Args:
        orbit_dts (list[str] or list[datetime.datetime])
        missions (list[str]): optional, to specify S1A or S1B
            No input downloads both, must be same len as orbit_dts
        save_dir (str): directory to save the EOF files into

    Returns:
        None

    Raises:
        ValueError - for missions argument not being one of 'S1A', 'S1B',
            or having different length
    """
    if missions and all(m not in ('S1A', 'S1B') for m in missions):
        raise ValueError('missions argument must be "S1A" or "S1B"')
    if missions and len(missions) != len(orbit_dts):
        raise ValueError("missions arg must be same length as orbit_dts")
    if not missions:
        missions = itertools.repeat(None)

    # First make sures all are datetimes if given string
    orbit_dts = [parse(dt) if isinstance(dt, str) else dt for dt in orbit_dts]

    # Download and save all links in parallel
    pool = ThreadPool(processes=MAX_WORKERS)
    result_dt_dict = {
        pool.apply_async(_download_and_write, (mission, dt, save_dir)): dt
        for mission, dt in zip(missions, orbit_dts)
    }
    for result in result_dt_dict:
        result.get()
        dt = result_dt_dict[result]
        logger.info('Finished {}'.format(dt.date()))


def eof_list(start_date):
    """Download the list of .EOF files for a specific date

    Args:
        start_date (str or datetime): Year month day of validity start for orbit file

    Returns:
        list: urls of EOF files

    Raises:
        ValueError: if start_date returns no results
    """
    url = BASE_URL.format(
        start_date=start_date.strftime(DATE_FMT),
        stop_date=(start_date + timedelta(days=1)).strftime(DATE_FMT),
    )
    logger.info("Searching for EOFs at {}".format(url))
    response = requests.get(url)
    response.raise_for_status()

    if response.json()['count'] < 1:
        raise ValueError('No EOF files found for {} at {}'.format(
            start_date.strftime(DATE_FMT), url))

    return [result['remote_url'] for result in response.json()['results']]


def _download_and_write(mission, dt, save_dir="."):
    """Wrapper function to run the link downloading in parallel

    Args:
        mission (str): Sentinel mission: either S1A or S1B
        dt (datetime): datetime of Sentinel product
        save_dir (str): directory to save the EOF files into

    Returns:
        None
    """
    try:
        cur_links = eof_list(dt)
    except ValueError as e:  # 0 found for date
        logger.warning(e.args[0])
        logger.warning('Skipping {}'.format(dt.strftime('%Y-%m-%d')))
        return

    if mission:
        cur_links = [link for link in cur_links if mission in link]

    # There should be a max of 2
    assert len(cur_links) <= 2, "Too many links found for {}: {}".format(dt, cur_links)
    for link in cur_links:
        fname = os.path.join(save_dir, link.split('/')[-1])
        if os.path.isfile(fname):
            logger.info("%s already exists, skipping download.", link)
            return

        logger.info("Downloading %s", link)
        response = requests.get(link)
        response.raise_for_status()
        logger.info("Saving to %s", fname)
        with open(fname, 'wb') as f:
            f.write(response.content)


def find_sentinel_products(startpath='./'):
    """Parse the startpath directory for any Sentinel 1 products' date and mission"""
    orbit_dts = []
    missions = []
    for filename in glob.glob(os.path.join(startpath, 'S1*')):
        try:
            parser = Sentinel(filename)
        except ValueError:  # Doesn't match a sentinel file
            logger.info('Skipping {}'.format(filename))
            continue

        if parser.start_time in orbit_dts:  # start_time is a datetime
            continue
        logger.info("Downloading precise orbits for {} on {}".format(
            parser.mission, parser.start_time.strftime('%Y-%m-%d')))
        orbit_dts.append(parser.start_time)
        missions.append(parser.mission)

    return orbit_dts, missions


def main(path='.', mission=None, date=None):
    """Function used for entry point to download eofs"""
    _set_logger_handler()

    if (mission and not date):
        raise ValueError("Must specify date if specifying mission")
    if not date:
        # No command line args given: search current directory
        orbit_dts, missions = find_sentinel_products(path)
        if not orbit_dts:
            logger.info("No Sentinel products found in directory %s, exiting", path)
            return 0
    if date:
        orbit_dts = [date]
        missions = list(mission) if mission else []

    download_eofs(orbit_dts, missions=missions)
