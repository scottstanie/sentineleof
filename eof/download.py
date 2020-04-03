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
from apertools.parsers import Sentinel, SentinelOrbit

MAX_WORKERS = 20  # For parallel downloading

BASE_URL = "https://qc.sentinel1.eo.esa.int/api/v1/?product_type=AUX_{orbit_type}\
&sentinel1__mission={mission}&validity_start__lt={start_dt}&validity_stop__gt={stop_dt}"

PRECISE_ORBIT = "POEORB"
RESTITUTED_ORBIT = "RESORB"
DT_FMT = "%Y-%m-%dT%H:%M:%S"  # Used in sentinel API url
# 2017-10-01T00:39:50

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
    # TODO: condense list of same dates, different hours?
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


def eof_list(start_dt, mission, orbit_type=PRECISE_ORBIT):
    """Download the list of .EOF files for a specific date

    Args:
        start_dt (str or datetime): Year month day of validity start for orbit file

    Returns:
        list: urls of EOF files

    Raises:
        ValueError: if start_dt returns no results
    """
    url = BASE_URL.format(
        orbit_type=orbit_type,
        mission=mission,
        start_dt=(start_dt - timedelta(minutes=2)).strftime(DT_FMT),
        stop_dt=(start_dt + timedelta(minutes=2)).strftime(DT_FMT),
    )
    logger.info("Searching for EOFs at {}".format(url))
    response = requests.get(url)
    response.raise_for_status()

    if response.json()['count'] < 1:
        if orbit_type == PRECISE_ORBIT:
            logger.warning('No precise orbit files found for {} on {}, searching RESORB'.format(
                mission, start_dt.strftime(DT_FMT)))
            return eof_list(start_dt, mission, orbit_type=RESTITUTED_ORBIT)

        raise ValueError('No EOF files found for {} on {} at {}'.format(
            start_dt.strftime(DT_FMT), mission, url))

    return [result['remote_url'] for result in response.json()['results']]


def _dedupe_links(links):
    out = [links[0]]
    orb1 = SentinelOrbit(links[0].split('/')[-1])
    for link in links[1:]:
        if SentinelOrbit(link.split('/')[-1]).date != orb1.date:
            out.append(link)
    return out


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
        cur_links = eof_list(dt, mission)
    except ValueError as e:  # 0 found for date
        logger.warning(e.args[0])
        logger.warning('Skipping {}'.format(dt.strftime('%Y-%m-%d')))
        return

    cur_links = _dedupe_links(cur_links)

    # RESORB has multiple overlapping
    # assert len(cur_links) <= 2, "Too many links found for {}: {}".format(dt, cur_links)
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


def find_current_eofs(startpath):
    return sorted(
        [SentinelOrbit(filename) for filename in glob.glob(os.path.join(startpath, '*EOF'))])


def find_sentinel_products(startpath='./'):
    """Parse the startpath directory for any Sentinel 1 products' date and mission"""
    orbit_dts = []
    missions = []
    current_eofs = find_current_eofs(startpath)

    for filename in glob.glob(os.path.join(startpath, 'S1*')):
        try:
            sent_parse = Sentinel(filename)
        except ValueError:  # Doesn't match a sentinel file
            logger.debug('Skipping {}, not a Sentinel 1 file'.format(filename))
            continue

        if sent_parse.start_time in orbit_dts:  # start_time is a datetime
            continue
        if any(sent_parse.start_time in orbit for orbit in current_eofs):
            logger.info('Skipping {}, already have EOF file'.format(filename))
            continue

        logger.info("Downloading precise orbits for {} on {}".format(
            sent_parse.mission, sent_parse.start_time.strftime('%Y-%m-%d')))
        orbit_dts.append(sent_parse.start_time)
        missions.append(sent_parse.mission)

    return orbit_dts, missions


def main(path='.', mission=None, date=None):
    """Function used for entry point to download eofs"""
    _set_logger_handler()

    if (mission and not date) or (date and not mission):
        raise ValueError("Must specify date and mission together")

    if date:
        orbit_dts = [date]
        missions = list(mission)
    else:
        # No command line args given: search current directory
        orbit_dts, missions = find_sentinel_products(path)
        if not orbit_dts:
            logger.info("No Sentinel products found in directory %s, exiting", path)
            return 0

    download_eofs(orbit_dts, missions=missions)
