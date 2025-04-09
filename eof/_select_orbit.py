"""Module for filtering/selecting from orbit query"""
from __future__ import annotations

import operator
from collections.abc import Sequence
from datetime import datetime, timedelta

from .log import logger
from .products import SentinelOrbit

T_ORBIT = (12 * 86400.0) / 175.0
"""Orbital period of Sentinel-1 in seconds"""


class OrbitSelectionError(RuntimeError):
    pass


class ValidityError(ValueError):
    pass


def valid_orbits(
    t0: datetime,
    t1: datetime,
    data: Sequence[SentinelOrbit],
    margin0: timedelta|None = None,
    margin1: timedelta|None = None,
) -> list[SentinelOrbit]:
    """
    Filters orbits from ``data`` that have a start time <= t0-Δ0, and a stop time >= t1+Δ1.
    """
    margin0 = margin0 if margin0 is not None else  timedelta(seconds=T_ORBIT + 60)
    margin1 = margin1 if margin1 is not None else  timedelta(minutes=5)
    logger.debug("Extract valid orbits between %s-%s and %s+%s among %s elements", t0, margin0, t1, margin1, len(data))
    # Using a start margin of > 1 orbit so that the start of the orbit file will
    # cover the ascending node crossing of the acquisition
    candidates = sorted([
        item
        for item in data
        if (item.start_time <= (t0 - margin0)) and (item.stop_time >= (t1 + margin1))
    ])
    if not candidates:
        raise ValidityError(
            f"none of the input products completely covers the requested time interval: [{t0=}, {t1=}]"
        )

    # Make sure the last updated EOF is returned for each time range
    # candidates are sorted at this point, but we should keep those with the
    # highest created_time
    # (not sure whether there is a sort|uniq-like way of doing it simply in
    # python...)
    result : list[SentinelOrbit] = []
    last  = None
    for candidate in candidates:
        if last:
            if candidate == last: # compare on everything but created_time
                last = last if last.created_time > candidate.created_time else candidate
            else:
                result.append(last)
                last = candidate
        else:
            last = candidate
    if last:
        result.append(last)
    logger.debug("%s candidates kept (from %)", len(result), len(candidates))

    return result


def last_valid_orbit(
    t0: datetime,
    t1: datetime,
    data: Sequence[SentinelOrbit],
    margin0: timedelta|None = None,
    margin1: timedelta|None = None,
) -> str:
    """
    Returns the last created orbit file from ``data``  that has a start time <= t0-Δ0, and a stop
    time >= t1+Δ1.
    """
    margin0 = margin0 or timedelta(seconds=T_ORBIT + 60)
    margin1 = margin1 or timedelta(minutes=5)
    candidates = valid_orbits(t0, t1, data, margin0, margin1)

    candidates.sort(key=operator.attrgetter("created_time"), reverse=True)
    return candidates[0].filename
