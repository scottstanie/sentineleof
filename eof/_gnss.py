"""Client for GNSS data."""

import os
import logging

from sentinelsat.sentinel import SentinelAPI


class GnssAPI(SentinelAPI):
    """Class to connect to Copernicus Open Access Hub, search and download GNSS data.

    Parameters
    ----------
    user : string
        username for DataHub
        set to None to use ~/.netrc
    password : string
        password for DataHub
        set to None to use ~/.netrc
    api_url : string, optional
        URL of the DataHub
        defaults to 'https://scihub.copernicus.eu/gnss'
    show_progressbars : bool
        Whether progressbars should be shown or not, e.g. during download. Defaults to True.
    timeout : float or tuple, optional
        How long to wait for DataHub response (in seconds).
        Tuple (connect, read) allowed.

    Attributes
    ----------
    session : requests.Session
        Session to connect to DataHub
    api_url : str
        URL to the DataHub
    page_size : int
        Number of results per query page.
        Current value: 100 (maximum allowed on ApiHub)
    timeout : float or tuple
        How long to wait for DataHub response (in seconds).
    """

    logger = logging.getLogger("sentinelsat.GnssAPI")

    def __init__(
        self,
        user: str = "gnssguest",
        password: str = "gnssguest",
        api_url: str = "https://scihub.copernicus.eu/gnss/",
        show_progressbars: bool = True,
        timeout: bool = None,
    ):
        super().__init__(user, password, api_url, show_progressbars, timeout)

    def download(self, id, directory_path=".", checksum=True, **kwargs):
        product_info =  super().download(id, directory_path, checksum, **kwargs)

        name = product_info['path']
        newname = os.path.splitext(name)[0] + '.EOF'
        os.rename(name, newname)
        product_info['path'] = newname

        return product_info

    def download_all(
        self,
        products,
        directory_path=".",
        max_attempts=10,
        checksum=True,
        n_concurrent_dl=2,
        lta_retry_delay=600,
        **kwargs
    ):
        downloaded, scheduled, failed = super().download_all(
            products,
            directory_path,
            max_attempts,
            checksum,
            n_concurrent_dl,
            lta_retry_delay,
            **kwargs
        )
        for item in downloaded:
            name = item['path']
            newname = os.path.splitext(name)[0] + '.EOF'
            os.rename(name, newname)
            item['path'] = newname

        return downloaded, scheduled, failed