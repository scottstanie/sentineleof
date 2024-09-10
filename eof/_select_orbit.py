"""Module for filtering/selecting from orbit query"""
from __future__ import annotations

import operator
from datetime import datetime, timedelta
from typing import List, Sequence
from sortedcontainers import SortedList

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
    margin0=timedelta(seconds=T_ORBIT + 60),
    margin1=timedelta(minutes=5),
) -> List[SentinelOrbit]:
    # Using a start margin of > 1 orbit so that the start of the orbit file will
    # cover the ascending node crossing of the acquisition
    candidates = SortedList([
        item
        for item in data
        if item.start_time <= (t0 - margin0) and item.stop_time >= (t1 + margin1)
    ])
    if not candidates:
        raise ValidityError(
            "none of the input products completely covers the requested "
            "time interval: [t0={}, t1={}]".format(t0, t1)
        )

    # Make sure the last updated EOF is returned for each time range
    # candidates are sorted at this point, but we should keep those with the
    # highest created_time
    # (not sure whether there is a sort|uniq-like way of doing it simply in
    # python...)
    result = []
    last  = None
    for candidate in candidates:
        if last and candidate == last:  # compare on everything but created_time
            result.append(last if last.created_time > candidate.created_time else candidate)
            last = None
        else:
            last = candidate
    if last:
        result.append(last)

    return result


def last_valid_orbit(
    t0: datetime,
    t1: datetime,
    data: Sequence[SentinelOrbit],
    margin0=timedelta(seconds=T_ORBIT + 60),
    margin1=timedelta(minutes=5),
) -> str:
    candidates = valid_orbits(t0, t1, data, margin0, margin1)

    candidates.sort(key=operator.attrgetter("created_time"), reverse=True)
    return candidates[0].filename
