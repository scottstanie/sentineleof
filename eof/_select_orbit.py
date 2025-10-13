"""Module for filtering/selecting from orbit query"""

from __future__ import annotations

import operator
from datetime import datetime, timedelta
from typing import Sequence

from .products import SentinelOrbit

T_ORBIT = (12 * 86400.0) / 175.0
"""Orbital period of Sentinel-1 in seconds"""

DEFAULT_MARGIN = timedelta(seconds=60)


class OrbitSelectionError(RuntimeError):
    pass


class ValidityError(ValueError):
    pass


def last_valid_orbit(
    t0: datetime,
    t1: datetime,
    data: Sequence[SentinelOrbit],
    margin0: timedelta | None = DEFAULT_MARGIN,
    margin1: timedelta | None = DEFAULT_MARGIN,
) -> str:
    if margin0 is None:
        margin0 = DEFAULT_MARGIN
    if margin1 is None:
        margin1 = DEFAULT_MARGIN
    # Orbit files must cover the acquisition time with a small margin
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
