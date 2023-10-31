"""Client to get orbit files from dataspace.copernicus.eu ."""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import requests
from sentinelsat import SentinelAPI
from sentinelsat.exceptions import ServerError

from ._select_orbit import T_ORBIT, ValidityError, lastval_cover
from .log import logger
from .parsing import EOFLinkFinder
from .products import Sentinel as S1Product
from .products import SentinelOrbit

QUERY_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
"""Default URL endpoint for the Copernicus Data Space Ecosystem (CDSE) query REST service"""

AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
"""Default URL endpoint for performing user authentication with CDSE"""

DOWNLOAD_URL = "https://zipper.dataspace.copernicus.eu/odata/v1/Products"
"""Default URL endpoint for CDSE download REST service"""

SIGNUP_URL = "https://dataspace.copernicus.eu/"
"""Url to prompt user to sign up for CDSE account."""


class DataspaceClient:
    T0 = timedelta(days=1)
    T1 = timedelta(days=1)

    def __init__(
        self,
        user: str = "gnssguest",
        password: str = "gnssguest",
        api_url: str = "https://scihub.copernicus.eu/gnss/",
        **kwargs,
    ):
        self._api = SentinelAPI(user=user, password=password, api_url=api_url, **kwargs)

    def query_orbit(
        self, t0, t1, satellite_id: str, product_type: str = "AUX_POEORB"
    ) -> dict[str, dict]:
        assert satellite_id in {"S1A", "S1B"}
        assert product_type in {"AUX_POEORB", "AUX_RESORB"}

        query_params = dict(
            producttype=product_type,
            platformserialidentifier=satellite_id[1:],
            # date=[t0, t1],
            # use the following instead
            beginposition=(None, t1),
            endposition=(t0, None),
        )
        logger.debug("query parameter: %s", query_params)
        products = self._api.query(**query_params)
        return products

    @staticmethod
    def _select_orbit(
        products: dict[str, dict],
        t0: datetime,
        t1: datetime,
        margin0: timedelta = timedelta(seconds=T_ORBIT + 60),
    ):
        if not products:
            return {}
        orbit_products = [p["identifier"] for p in products.values()]
        validity_info = [SentinelOrbit(product_id) for product_id in orbit_products]
        product_id = lastval_cover(t0, t1, validity_info, margin0=margin0)
        return {k: v for k, v in products.items() if v["identifier"] == product_id}

    def query_orbit_for_product(
        self,
        product,
        orbit_type: str = "precise",
        t0_margin: timedelta = T0,
        t1_margin: timedelta = T1,
    ):
        if isinstance(product, str):
            product = S1Product(product)

        return self.query_orbit_by_dt(
            [product.start_time],
            [product.mission],
            orbit_type=orbit_type,
            t0_margin=t0_margin,
            t1_margin=t1_margin,
        )

    def query_orbit_by_dt(
        self,
        orbit_dts,
        missions,
        orbit_type: str = "precise",
        t0_margin: timedelta = T0,
        t1_margin: timedelta = T1,
    ):
        """Query the Scihub api for product info for the specified missions/orbit_dts.

        Args:
            orbit_dts (list[datetime]): list of orbit datetimes
            missions (list[str]): list of mission names
            orbit_type (str, optional): Type of orbit to prefer in search.
                Defaults to "precise".
            t0_margin (timedelta, optional): Margin used in searching for early bound
                for orbit.  Defaults to 1 day.
            t1_margin (timedelta, optional): Margin used in searching for late bound
                for orbit.  Defaults to 1 day.

        Returns:
            query (dict): API info from scihub with the requested products
        """
        remaining_dates = []
        query = {}
        for dt, mission in zip(orbit_dts, missions):
            found_result = False
            # Only check for precise orbits if that is what we want
            if orbit_type == "precise":
                products = self.query_orbit(
                    dt - t0_margin,
                    dt + t1_margin,
                    mission,
                    product_type="AUX_POEORB",
                )
                try:
                    result = self._select_orbit(
                        products,
                        dt,
                        dt + timedelta(minutes=1),
                        margin0=timedelta(seconds=T_ORBIT + 60),
                    )
                except ValidityError:
                    result = None
            else:
                result = None

            if result:
                found_result = True
                query.update(result)
            else:
                # try with RESORB
                products = self.query_orbit(
                    dt - timedelta(hours=2),
                    dt + timedelta(hours=2),
                    mission,
                    product_type="AUX_RESORB",
                )
                result = (
                    self._select_orbit(
                        products,
                        dt,
                        dt + timedelta(minutes=1),
                        # For restituted orbits, we need to be more lenient
                        # and can't use a full orbit margin for the search
                        margin0=timedelta(seconds=60),
                    )
                    if products
                    else None
                )
                if result:
                    found_result = True
                    query.update(result)

            if not found_result:
                remaining_dates.append((mission, dt))

        if remaining_dates:
            logger.warning("The following dates were not found: %s", remaining_dates)
        return query

    def download(self, uuid, **kwargs):
        """Download a single orbit product.

        See sentinelsat.SentinelAPI.download for a detailed description
        of arguments.
        """
        # return self._api.download(uuid, **kwargs)
        raise NotImplementedError

    def download_all(self, products, **kwargs):
        """Download all the specified orbit products.

        See sentinelsat.SentinelAPI.download_all for a detailed description
        of arguments.
        """
        return self._api.download_all(products, **kwargs)

    def server_is_up(self):
        """Ping the ESA server using sentinelsat to verify the connection."""
        try:
            self._api.query(producttype="AUX_POEORB", platformserialidentifier="S1A")
            return True
        except ServerError as e:
            logger.warning("Cannot connect to the server: %s", e)
            return False


def _construct_orbit_file_query(mission_id, orbit_type, search_start, search_stop):
    """Constructs the query used with the query URL to determine the
    available Orbit files for the given time range.

    Parameters
    ----------
    mission_id : str
        The mission ID parsed from the SAFE file name, should always be one
        of S1A or S1B.
    orbit_type : str
        String identifying the type of orbit file to query for. Should be either
        POEORB for Precise Orbit files, or RESORB for Restituted.
    search_start : datetime
        The start time to use with the query in YYYYmmddTHHMMSS format.
        Any resulting orbit files will have a starting time before this value.
    search_stop : datetime
        The stop time to use with the query in YYYYmmddTHHMMSS format.
        Any resulting orbit files will have an ending time after this value.

    Returns
    -------
    query : str
        The Orbit file query string formatted as the query service expects.

    """
    # Set up templates that use the OData domain specific syntax expected by the
    # query service
    query_template = (
        "startswith(Name,'{mission_id}') and contains(Name,'AUX_{orbit_type}') "
        "and ContentDate/Start lt '{start_time}' and ContentDate/End gt '{stop_time}'"
    )

    # Format the query template using the values we were provided
    query_start_date_str = search_start.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    query_stop_date_str = search_stop.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    query = query_template.format(
        start_time=query_start_date_str,
        stop_time=query_stop_date_str,
        mission_id=mission_id,
        orbit_type=orbit_type,
    )

    logger.debug(f"query: {query}")

    return query


def query_orbit_file_service(url, query):
    """Submits a request to the Orbit file query REST service, and returns the
    JSON-formatted response.

    Parameters
    ----------
    url : str
        The URL for the query endpoint, to which the query is appended to as
        the payload.
    query : str
        The query for the Orbit files to find, filtered by a time range and mission
        ID corresponding to the provided SAFE SLC archive file.

    Returns
    -------
    query_results : list of dict
        The list of results from a successful query. Each result should
        be a Python dictionary containing the details of the orbit file which
        matched the query.

    Raises
    ------
    requests.HTTPError
        If the request fails for any reason (HTTP return code other than 200).

    References
    ----------
    .. [1] https://documentation.dataspace.copernicus.eu/APIs/OData.html#query-by-sensing-date
    """
    # Set up parameters to be included with query request
    query_params = {"$filter": query, "$orderby": "ContentDate/Start asc", "$top": 1}

    # Make the HTTP GET request on the endpoint URL, no credentials are required
    response = requests.get(url, params=query_params)

    logger.debug(f"response.url: {response.url}")
    logger.debug(f"response.status_code: {response.status_code}")

    response.raise_for_status()

    # Response should be within the text body as JSON
    json_response = response.json()
    logger.debug(f"json_response: {json_response}")

    query_results = json_response["value"]

    return query_results


def get_access_token(username, password):
    """
    https://documentation.dataspace.copernicus.eu/APIs/Token.html
    """


class ASFClient:
    precise_url = "https://s1qc.asf.alaska.edu/aux_poeorb/"
    res_url = "https://s1qc.asf.alaska.edu/aux_resorb/"
    urls = {"precise": precise_url, "restituted": res_url}
    eof_lists = {"precise": None, "restituted": None}

    def get_full_eof_list(self, orbit_type="precise", max_dt=None):
        """Get the list of orbit files from the ASF server."""
        if orbit_type not in self.urls.keys():
            raise ValueError("Unknown orbit type: {}".format(orbit_type))

        if self.eof_lists.get(orbit_type) is not None:
            return self.eof_lists[orbit_type]
        # Try to see if we have the list of EOFs in the cache
        elif os.path.exists(self._get_filename_cache_path(orbit_type)):
            eof_list = self._get_cached_filenames(orbit_type)
            # Need to clear it if it's older than what we're looking for
            max_saved = max([e.start_time for e in eof_list])
            if max_saved < max_dt:
                logger.warning("Clearing cached {} EOF list:".format(orbit_type))
                logger.warning(
                    "{} is older than requested {}".format(max_saved, max_dt)
                )
                self._clear_cache(orbit_type)
            else:
                logger.info("Using cached EOF list")
                self.eof_lists[orbit_type] = eof_list
                return eof_list

        logger.info("Downloading all filenames from ASF (may take awhile)")
        resp = requests.get(self.urls.get(orbit_type))
        finder = EOFLinkFinder()
        finder.feed(resp.text)
        eof_list = [SentinelOrbit(f) for f in finder.eof_links]
        self.eof_lists[orbit_type] = eof_list
        self._write_cached_filenames(orbit_type, eof_list)
        return eof_list

    def get_download_urls(self, orbit_dts, missions, orbit_type="precise"):
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
        remaining_orbits = []
        urls = []
        for dt, mission in zip(orbit_dts, missions):
            try:
                filename = lastval_cover(dt, dt, mission_to_eof_list[mission])
                urls.append(self.urls[orbit_type] + filename)
            except ValidityError:
                remaining_orbits.append((dt, mission))

        if remaining_orbits:
            logger.warning("The following dates were not found: %s", remaining_orbits)
            if orbit_type == "precise":
                logger.warning(
                    "Attempting to download the restituted orbits for these dates."
                )
                remaining_dts, remaining_missions = zip(*remaining_orbits)
                urls.extend(
                    self.get_download_urls(
                        remaining_dts, remaining_missions, orbit_type="restituted"
                    )
                )

        return urls

    def _get_cached_filenames(self, orbit_type="precise"):
        """Get the cache path for the ASF orbit files."""
        filepath = self._get_filename_cache_path(orbit_type)
        logger.debug(f"ASF file path cache: {filepath = }")
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return [SentinelOrbit(f) for f in f.read().splitlines()]
        return None

    def _write_cached_filenames(self, orbit_type="precise", eof_list=[]):
        """Cache the ASF orbit files."""
        filepath = self._get_filename_cache_path(orbit_type)
        with open(filepath, "w") as f:
            for e in eof_list:
                f.write(e.filename + "\n")

    def _clear_cache(self, orbit_type="precise"):
        """Clear the cache for the ASF orbit files."""
        filepath = self._get_filename_cache_path(orbit_type)
        os.remove(filepath)

    @staticmethod
    def _get_filename_cache_path(orbit_type="precise"):
        fname = "{}_filenames.txt".format(orbit_type.lower())
        return os.path.join(ASFClient.get_cache_dir(), fname)

    @staticmethod
    def get_cache_dir():
        """Find location of directory to store .hgt downloads
        Assuming linux, uses ~/.cache/sentineleof/
        """
        path = os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        path = os.path.join(path, "sentineleof")  # Make subfolder for our downloads
        print(path)
        if not os.path.exists(path):
            os.makedirs(path)
        return path
