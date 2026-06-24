#!/usr/bin/env python
"""Verify the ``Sentinel.relative_orbit`` formula against the CDSE catalogue.

For each Sentinel-1 SLC product returned by the Copernicus Data Space (CDSE)
OData catalogue, this compares the official ``relativeOrbitNumber`` attribute
against the value computed by :class:`eof.products.Sentinel` from the absolute
orbit number in the filename. It also reports the *implied* offset
``(absolute_orbit - (relative_orbit - 1)) % 175`` for each product, which is
handy for discovering or sanity-checking a new offset (e.g. after the 2026 S1C
orbital reconfiguration).

The catalogue search endpoint is unauthenticated, so no credentials are needed.

Usage
-----
# Verify the most recent S1C SLCs (default mission)
python verify_relative_orbit.py

# Verify S1D over an explicit acquisition window
python verify_relative_orbit.py --mission S1D --start 2026-06-01 --end 2026-06-25

# Confirm the post-maneuver S1C offset once products start flowing
python verify_relative_orbit.py --mission S1C --start 2026-06-24
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from collections import Counter

from eof.products import Sentinel

CATALOGUE_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
RELATIVE_ORBIT_PERIOD = 175


def query_cdse(
    mission: str,
    start: str | None = None,
    end: str | None = None,
    top: int = 50,
) -> list[dict]:
    """Query the CDSE OData catalogue for SLC products of one mission.

    Parameters
    ----------
    mission : str
        Mission prefix, one of "S1A", "S1B", "S1C", "S1D".
    start, end : str or None
        Optional ISO-8601 acquisition-date bounds (e.g. "2026-06-24" or
        "2026-06-24T00:00:00"). Compared against ``ContentDate/Start``.
    top : int
        Maximum number of products to return, newest first.

    Returns
    -------
    list of dict
        Raw CDSE product entries, each including expanded ``Attributes``.
    """
    filters = [f"startswith(Name,'{mission}')", "contains(Name,'SLC')"]
    if start is not None:
        filters.append(f"ContentDate/Start gt {_to_odata_datetime(start)}")
    if end is not None:
        filters.append(f"ContentDate/Start lt {_to_odata_datetime(end)}")

    query = urllib.parse.urlencode(
        {
            "$filter": " and ".join(filters),
            "$top": str(top),
            "$expand": "Attributes",
            "$orderby": "ContentDate/Start desc",
        }
    )
    with urllib.request.urlopen(f"{CATALOGUE_URL}?{query}", timeout=120) as resp:
        return json.load(resp)["value"]


def _to_odata_datetime(value: str) -> str:
    """Normalize a date/datetime string to the OData ``...Z`` form."""
    if "T" not in value:
        value += "T00:00:00"
    return value + ".000Z"


def official_relative_orbit(product: dict) -> int:
    """Return the ESA ``relativeOrbitNumber`` attribute for a CDSE product."""
    for attribute in product["Attributes"]:
        if attribute["Name"] == "relativeOrbitNumber":
            return int(attribute["Value"])
    raise KeyError(f"No relativeOrbitNumber attribute in {product['Name']}")


def verify(products: list[dict]) -> int:
    """Print a comparison table and return the number of mismatches.

    Parameters
    ----------
    products : list of dict
        CDSE product entries from :func:`query_cdse`.

    Returns
    -------
    int
        Count of products whose computed relative orbit disagrees with ESA.
    """
    header = f"{'date':<19} {'absOrbit':>8} {'ESA':>4} {'ours':>5} {'offset':>6}  match"
    print(header)
    print("-" * len(header))

    offsets: Counter[int] = Counter()
    mismatches = 0
    # Deduplicate by (absolute orbit, relative orbit): a single pass has many
    # slices/bursts sharing the same orbit, which would clutter the table.
    seen: set[tuple[int, int]] = set()
    for product in products:
        parsed = Sentinel(product["Name"].replace(".SAFE", ""))
        official = official_relative_orbit(product)
        key = (parsed.absolute_orbit, official)
        if key in seen:
            continue
        seen.add(key)

        ours = parsed.relative_orbit
        implied_offset = (
            parsed.absolute_orbit - (official - 1)
        ) % RELATIVE_ORBIT_PERIOD
        offsets[implied_offset] += 1
        matched = ours == official
        mismatches += not matched
        print(
            f"{str(parsed.start_time):<19} {parsed.absolute_orbit:>8} "
            f"{official:>4} {ours:>5} {implied_offset:>6}  "
            f"{'ok' if matched else 'MISMATCH'}"
        )

    print(f"\nImplied offset distribution: {dict(offsets)}")
    print(f"{len(seen)} unique orbits checked, {mismatches} mismatch(es)")
    return mismatches


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mission",
        default="S1C",
        choices=["S1A", "S1B", "S1C", "S1D"],
        help="Mission to verify (default: %(default)s)",
    )
    parser.add_argument("--start", help="Acquisition start bound, ISO-8601")
    parser.add_argument("--end", help="Acquisition end bound, ISO-8601")
    parser.add_argument(
        "--max",
        type=int,
        default=50,
        dest="top",
        help="Max products to fetch, newest first (default: %(default)s)",
    )
    args = parser.parse_args()

    products = query_cdse(args.mission, args.start, args.end, args.top)
    if not products:
        print(
            f"No {args.mission} SLC products found for the given window "
            "(e.g. none have been produced yet)."
        )
        return

    mismatches = verify(products)
    raise SystemExit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
