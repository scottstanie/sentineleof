"""Client to get orbit files from dataspace.copernicus.eu ."""
from __future__ import annotations
from abc import abstractmethod

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import requests

from ._auth import DATASPACE_HOST, get_netrc_credentials
from ._select_orbit import T_ORBIT
from ._types import Filename
from .client import Client, OrbitType, AbstractSession
from .log import logger

QUERY_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
"""Default URL endpoint for the Copernicus Data Space Ecosystem (CDSE) query REST service"""

AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
"""Default URL endpoint for performing user authentication with CDSE"""

DOWNLOAD_URL = "https://zipper.dataspace.copernicus.eu/odata/v1/Products"
"""Default URL endpoint for CDSE download REST service"""

SIGNUP_URL = "https://dataspace.copernicus.eu/"
"""Url to prompt user to sign up for CDSE account."""


class DataspaceSession(AbstractSession):
    """
    Authenticated session to Copernicus Dataspace.

    Downloading is the only service provided.
    """
    def __init__(
        self,
        access_token: Optional[str] = None,
        username: str = "",
        password: str = "",
        token_2fa: str = "",
        netrc_file: Optional[Filename] = None,
    ):
        self._access_token = access_token
        if access_token:
            logger.debug("Using provided CDSE access token")
        else:
            try:
                if not (username and password):
                    logger.debug(f"Get credentials form netrc ({netrc_file!r})")
                    # Shall we keep username if explicitly set?
                    username, password = get_netrc_credentials(DATASPACE_HOST, netrc_file)
                else:
                    logger.debug("Using provided username and password")
                self._access_token = get_access_token(username, password, token_2fa)
            except FileNotFoundError:
                logger.warning("No netrc file found.")
            except ValueError as e:
                if DATASPACE_HOST not in e.args[0]:
                    raise e
                logger.warning(
                    f"No CDSE credentials found in netrc file {netrc_file!r}. Please create one using {SIGNUP_URL}"
                )
            except Exception as e:
                logger.warning(f"Error: {str(e)}")

            # Obtain an access token the download request from the provided credentials

    def __bool__(self):
        """Tells whether the object has been correctly initialized"""
        return bool(self._access_token)

    def download_all(
        self,
        eofs: Sequence[dict],
        output_directory: Filename,
        max_workers: int = 3,
    ) -> List[Path]:
        """Download all the specified orbit products."""
        return download_all(
            query_results=eofs,
            output_directory=output_directory,
            access_token=self._access_token,
            max_workers=max_workers,
        )


class DataspaceClient(Client):
    """
    Client dedicated to Copernicus dataspace.

    Provides:
    - query methods that return eof products matching the search
      criteria.
    - authentication method that'll return a :class:`DataspaceSession`
      object which will permit downloading eof products found.
    """
    def authenticate(self, *args, **kwargs) -> DataspaceSession:
        """
        Authenticate to the client.

        The authentication will try to use in order:
        1. ``access_token``
        2. ``username`` + ``password`` (+ ``token_2fa`` is set)
        3. dataspace entry from ``netrc_file`` (or $NETRC, or ``~/.netrc``)

        Args:
            access_token (Optional[str]): already esstablished access token to Copernicus Dataspace
            username (str): Optional user name
            password (str): Optional use password
            token_2fa (str): Optional 2FA Token
            netrc_file (Optional[Filename]): Optional name of netrc file

        :raise FileNotFoundError: if ``netrc`` file cannot be found.
        :raise ValueError: if there is no entry for dataspace host in the netrc
        :raises RuntimeError: if the access token cannot be created
        """
        return DataspaceSession(*args, **kwargs)

    def query_orbit(
        self,
        t0: datetime,
        t1: datetime,
        satellite_id: str,
        product_type: str = "AUX_POEORB",
    ) -> list[dict]:
        """
        Returns the only orbit file (of type ``product_type``, and for
        the given ``satellite_id``) that contains the the time range
        specified in parameter.
        """
        # Forward the call to the specialized Query objet
        return _QueryOneOrbitFileAroundRange().query_orbit(
                t0,
                t1,
                satellite_id,
                product_type,
        )

    def query_orbit_by_dt(
        self,
        orbit_dts : Sequence[datetime],
        missions : Iterable[str],
        orbit_type: OrbitType = OrbitType.precise,
        t0_margin: timedelta = Client.T0,
        t1_margin: timedelta = Client.T1,
    ) -> List[dict]:
        """Query the Copernicus dataspace API for product info for the specified missions/orbit_dts.

        This method returns a single orbit file that completely includes
        the requested range.

        Parameters
        ----------
        orbit_dts : list[datetime.datetime]
            List of datetimes to query for
        missions : list[str], choices = {"S1A", "S1B"}
            List of missions to query for. Must be same length as orbit_dts
        orbit_type (OrbitType): precise or restituted
            String identifying the type of orbit file to query for.

            Search with restituted orbit is done when:
            1. requested explicitly
            2. or when nothing is found with precise orbit
        t0_margin : timedelta
            Margin to add to the start time of the orbit file in the query
            Applies only to precise orbits
        t1_margin : timedelta
            Margin to add to the end time of the orbit file in the query
            Applies only to precise orbits

        Returns
        -------
        list[dict]
            list of results from the query
        """
        # Forward the call to the specialized Query objet
        return _QueryOneOrbitFileAroundRange().query_orbit_by_dt(
                orbit_dts,
                missions,
                orbit_type,
                t0_margin,
                t1_margin,
        )

    def query_orbits_by_dt_range(
        self,
        first_dt: datetime,
        last_dt: datetime,
        missions: Sequence[str] = (),
        orbit_type: OrbitType = OrbitType.precise,
    ) -> List[dict]:
        """Query the Copernicus dataspace API for product info for the specified missions/orbit time range.

        This method returns the information all orbit files that intersect the requested range.

        Parameters
        ----------
        first_dt (str datetime.datetime): first datetime for orbit coverage
        last_dt (str datetime.datetime): last datetime for orbit coverage
        missions (list[str]): optional, to specify S1A or S1B
            No input downloads both.
        orbit_type : OrbitType, choices = {precise, restituted}

            Search with restituted orbit is done when:
            1. requested explicitly
            2. or when nothing is found with precise orbit

        Returns
        -------
        list[dict]
            list of results from the query.
            This result can be directly used by:method:`DataspaceClient.download_all`.
        """
        # Forward the call to the specialized Query objet
        return _QueryAllOrbitFileWithinRange().query_orbits_by_dt_range(
                first_dt,
                last_dt,
                missions,
                orbit_type,
        )


def query_orbit_file_service(query: str, how_many: int = 0) -> list[dict]:
    """Submit a request to the Orbit file query REST service.

    Parameters
    ----------
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
    query_params = {"$filter": query, "$orderby": "ContentDate/Start asc"}
    if how_many > 0:
        query_params["$top"] = str(how_many)

    # Make the HTTP GET request on the endpoint URL, no credentials are required
    print(f"{query_params=}")
    response = requests.get(QUERY_URL, params=query_params)  # type: ignore

    logger.debug(f"response.url: {response.url}")
    logger.debug(f"response.status_code: {response.status_code}")

    response.raise_for_status()

    # Response should be within the text body as JSON
    json_response = response.json()
    logger.debug(f"json_response: {json_response}")

    query_results = json_response["value"]

    return query_results


def get_access_token(
        username: Optional[str],
        password: Optional[str],
        token_2fa: Optional[str]
) -> str:
    """Get an access token for the Copernicus Data Space Ecosystem (CDSE) API.

    Code from https://documentation.dataspace.copernicus.eu/APIs/Token.html

    :raises ValueError: if either username or password is empty
    :raises RuntimeError: if the access token cannot be created
    """
    if not (username and password):
        raise ValueError("Username and password values are expected!")

    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password",
    }
    if token_2fa:  # Double authentication is used
        data["totp"] = token_2fa

    try:
        r = requests.post(AUTH_URL, data=data)
        r.raise_for_status()
    except Exception as err:
        raise RuntimeError(f"CDSE access token creation failed. Reason: {str(err)}") from err

    # Parse the access token from the response
    try:
        access_token = r.json()["access_token"]
        return access_token
    except KeyError:
        raise RuntimeError(
            'Failed to parse expected field "access_token" from CDSE authentication response.'
        )


def download_orbit_file(
    request_url, output_directory, orbit_file_name, access_token
) -> Path:
    """Downloads an Orbit file using the provided request URL.

    Should contain product ID for the file to download, as obtained from a query result.

    The output file is named according to the orbit_file_name parameter, and
    should correspond to the file name parsed from the query result. The output
    file is written to the directory indicated by output_directory.

    Parameters
    ----------
    request_url : str
        The full request URL, which includes the download endpoint, as well as
        a payload that contains the product ID for the Orbit file to be downloaded.
    output_directory : str
        The directory to store the downloaded Orbit file to.
    orbit_file_name : str
        The file name to assign to the Orbit file once downloaded to disk. This
        should correspond to the file name parsed from a query result.
    access_token : str
        Access token returned from an authentication request with the provided
        username and password. Must be provided with all download requests for
        the download service to respond.

    Returns
    -------
    output_orbit_file_path : Path
        The full path to where the resulting Orbit file was downloaded to.

    Raises
    ------
    requests.HTTPError
        If the request fails for any reason (HTTP return code other than 200).

    """
    # Make the HTTP GET request to obtain the Orbit file contents
    headers = {"Authorization": f"Bearer {access_token}"}
    session = requests.Session()
    session.headers.update(headers)
    response = session.get(request_url, headers=headers, stream=True)

    logger.debug(f"r.url: {response.url}")
    logger.debug(f"r.status_code: {response.status_code}")

    response.raise_for_status()

    # Write the contents to disk
    output_orbit_file_path = Path(output_directory) / orbit_file_name

    with open(output_orbit_file_path, "wb") as outfile:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                outfile.write(chunk)

    logger.info(f"Orbit file downloaded to {output_orbit_file_path!r}")
    return output_orbit_file_path


def download_all(
    query_results: Sequence[dict],
    output_directory: Filename,
    access_token: Optional[str],
    max_workers: int = 3,
) -> List[Path]:
    """Download all the specified orbit products.

    Parameters
    ----------
    query_results : list[dict]
        list of results from the query
    output_directory : str | Path
        Directory to save the orbit files to.
    username : str
        CDSE username
    password : str
        CDSE password
    token_2fa : str
        2FA Token used in profiles with double authentication
    max_workers : int, default = 3
        Maximum parallel downloads from CDSE.
        Note that >4 connections will result in a HTTP 429 Error

    """
    if not access_token:
        raise RuntimeError("Invalid CDSE access token. Aborting.")
    downloaded_paths: list[Path] = []
    # Select an appropriate orbit file from the list returned from the query
    # orbit_file_name, orbit_file_request_id = select_orbit_file(
    #     query_results, start_time, stop_time
    # )

    output_names = []
    download_urls = []
    for query_result in query_results:
        orbit_file_request_id = query_result["Id"]

        # Construct the URL used to download the Orbit file
        download_url = f"{DOWNLOAD_URL}({orbit_file_request_id})/$value"
        download_urls.append(download_url)

        orbit_file_name = query_result["Name"]
        output_names.append(orbit_file_name)

        logger.debug(
            f"Downloading Orbit file {orbit_file_name} from service endpoint "
            f"{download_url}"
        )

    downloaded_paths = []
    with ThreadPoolExecutor(max_workers=max_workers) as exc:
        futures = [
            exc.submit(
                download_orbit_file,
                request_url=u,
                output_directory=output_directory,
                orbit_file_name=n,
                access_token=access_token,
            )
            for (u, n) in zip(download_urls, output_names)
        ]
        for f in futures:
            downloaded_paths.append(f.result())

    return downloaded_paths


class _QueryOrbitFile:
    """
    Abstract class for all Copernicus Dataspace query classes.
    """
    @abstractmethod
    def _do_get_query_template(self) -> str:
        """
        Internal variation point that returns the template query string.
        """

    @abstractmethod
    def _do_get_number_of_elements(self) -> int:
        """
        Internal variation point that returns the maximum number of
        orbit files requested.
        """

    def _construct_orbit_file_query(
        self,
        mission_id: str,
        orbit_type: str,
        search_start: datetime,
        search_stop: datetime
    ) -> str:
        """
        Internal and generic service that builds the query string.

        The exact result depends on :method:`_do_get_query_template` and
        :metod:`_do_get_number_of_elements`.
        """
        assert search_start < search_stop
        # Set up templates that use the OData domain specific syntax expected by the
        # query service

        # Format the query template using the values we were provided
        query_start_date_str = search_start.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        query_stop_date_str = search_stop.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        query = self._do_get_query_template().format(
            start_time=query_start_date_str,
            stop_time=query_stop_date_str,
            mission_id=mission_id,
            orbit_type=orbit_type,
        )

        logger.debug("query: %s", query)
        return query

    def query_orbit(
        self,
        t0: datetime,
        t1: datetime,
        satellite_id: str,
        product_type: str = "AUX_POEORB",
    ) -> list[dict]:
        """
        Returns:
        - either the only orbit file (of type ``product_type``, and for
          the given ``satellite_id``) that contains the the time range
          specified in parameter.
        - or all the orbit files contained in the time range.

        The actual behaviour will depend on the exact type of ``self``.
        """
        assert satellite_id in {"S1A", "S1B"}
        assert product_type in {"AUX_POEORB", "AUX_RESORB"}
        # return run_query(t0, t1, satellite_id, product_type)
        # Construct the query based on the time range parsed from the input file
        logger.info(
            f"Querying for {product_type} orbit files from endpoint {QUERY_URL}"
        )
        query = self._construct_orbit_file_query(satellite_id, product_type, t0, t1)
        # Make the query to determine what Orbit files are available for the time
        # range
        return query_orbit_file_service(query, self._do_get_number_of_elements())

    def _search_dt_range(
        self,
        first_dt: datetime,
        last_dt: datetime,
        mission : str,
        orbit_type: OrbitType,
    ) -> List[dict]:
        """
        Internal method that wraps :method:`_QueryOrbitFile.query_orbit`.

        While ``query_orbit`` only returns references to orbit product of the requested type
        (precise or restituted), ``_search_dt_range`` will try to return references to restituted
        orbit products if no "precise" ones were found (and requested).
        """
        expect_only_one_result = self._do_get_number_of_elements() == 1
        all_results = []

        # Only check for precise orbits if that is what we want
        if orbit_type == OrbitType.precise:
            products = self.query_orbit(
                first_dt,
                last_dt,
                mission,
                product_type="AUX_POEORB",
            )
            if len(products) > 1 and expect_only_one_result:
                logger.warning(f"Found more than one result: {products}")
                all_results.append(products[0])
            else:
                all_results.extend(products)
        else:
            products = None

        if not products:
            # try with RESORB
            products = self.query_orbit(
                first_dt,
                last_dt,
                mission,
                product_type="AUX_RESORB",
            )
            if len(products) > 1 and expect_only_one_result:
                logger.warning(f"Found more than one result: {products}")
                all_results.append(products[0])
            else:
                all_results.extend(products)
        return all_results


class _QueryOneOrbitFileAroundRange(_QueryOrbitFile):
    """
    Query specialization for requesting the single orbit files that
    contains the request time range.

    The time range is expected to be short and under a day wide.
    """
    def query_orbit_by_dt(
        self,
        orbit_dts : Sequence[datetime],
        missions : Iterable[str],
        orbit_type: OrbitType = OrbitType.precise,
        t0_margin: timedelta = Client.T0,
        t1_margin: timedelta = Client.T1,
    ) -> List[dict]:
        """Query the Copernicus dataspace API for product info for the specified missions/orbit_dts.

        This method returns a single orbit file that completely includes
        the requested range.

        Parameters
        ----------
        orbit_dts : list[datetime.datetime]
            List of datetimes to query for
        missions : list[str], choices = {"S1A", "S1B"}
            List of missions to query for. Must be same length as orbit_dts
        orbit_type : OrbitType, choices = {"precise", "restituted"}
            String identifying the type of orbit file to query for.
        t0_margin : timedelta
            Margin to add to the start time of the orbit file in the query
            Applies only to precise orbits
        t1_margin : timedelta
            Margin to add to the end time of the orbit file in the query
            Applies only to precise orbits

        Returns
        -------
        list[dict]
            list of results from the query
        """
        remaining_dates: list[tuple[str, datetime]] = []
        all_results = []
        for dt, mission in zip(orbit_dts, missions):
            # Only check for precise orbits if that is what we want
            if orbit_type == OrbitType.precise:
                first_dt = dt - t0_margin
                last_dt = dt + t1_margin
            else:
                first_dt = dt - timedelta(seconds=T_ORBIT + 60)
                last_dt = dt + timedelta(seconds=60)

            results = self._search_dt_range(
                    first_dt,
                    last_dt,
                    mission,
                    orbit_type,
            )
            all_results.extend(results)
            if not results:
                remaining_dates.append((mission, dt))
                logger.warning(f"Found no restituted results for {dt} {mission}")

        if remaining_dates:
            logger.warning("The following dates were not found: %s", remaining_dates)
        return all_results

    def _do_get_query_template(self) -> str:
        """
        Variation point that returns the specialized query request
        template for obtaining a single orbit file that contains the
        request time range.
        """
        query_template = (
            "Collection/Name eq 'SENTINEL-1' "
            "and startswith(Name,'{mission_id}') and contains(Name,'{orbit_type}') "
            "and ContentDate/Start lt '{start_time}' and ContentDate/End gt '{stop_time}'"
        )
        return query_template

    def _do_get_number_of_elements(self) -> int:
        """
        Variation point for $top query parameter: return at most one
        orbit file.
        """
        return 1


class _QueryAllOrbitFileWithinRange(_QueryOrbitFile):
    """
    Query specialization for requesting all orbit files that intersect a given range.
    """
    def query_orbits_by_dt_range(
        self,
        first_dt: datetime,
        last_dt: datetime,
        missions: Sequence[str] = (),
        orbit_type: OrbitType = OrbitType.precise,
    ) -> List[dict]:
        """Query the Copernicus dataspace API for product info for the specified missions/orbit_dts.

        Parameters
        ----------
        orbit_dts : list[datetime.datetime]
            List of datetimes to query for
        missions (list[str]): optional, to specify S1A or S1B
            No input downloads both.
        orbit_type : OrbitType, choices = {precise, restituted}
            String identifying the type of orbit file to query for.
            Search with restituted orbit is done when:
            1. requested explicitly
            2. or when nothing is found with precise orbit
        t0_margin : timedelta
            Margin to add to the start time of the orbit file in the query
        t1_margin : timedelta
            Margin to add to the end time of the orbit file in the query

        Returns
        -------
        list[dict]
            list of results from the query
        """
        if not missions:
            missions = ("S1A", "S1B")
        all_results = []
        for mission in missions:
            results = self._search_dt_range(
                    first_dt, last_dt,
                    mission,
                    orbit_type,
            )
            all_results.extend(results)

        return all_results

    def _do_get_query_template(self) -> str:
        """
        Variation point that returns the specialized query request
        template for obtaining all orbit files within a time range.
        """
        # Notes:
        # * > Crucial for the search performance is specifying the
        #   > collection name. Example: Collection/Name eq ‘SENTINEL-3’
        #   -- https://documentation.dataspace.copernicus.eu/APIs/OData.html#odata-products-endpoint
        # * "'{start_time}' lt ContentDate/End" only returns 2 results
        #   while "ContentDate/End gt '{start_time}'" returns all of them
        query_template = (
            "Collection/Name eq 'SENTINEL-1' "
            "and startswith(Name,'{mission_id}') and contains(Name,'{orbit_type}') "
            "and ContentDate/Start lt '{stop_time}' "
            "and ContentDate/End gt '{start_time}'"
        )
        return query_template

    def _do_get_number_of_elements(self) -> int:
        """
        Variation point for $top query parameter: return as many orbit
        files as found (up to 20, which is Copernicus datasapce default
        value for $top)
        """
        return 0
