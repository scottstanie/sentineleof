"""sentinelsat based client to get orbit files form scihub.copernicu.eu."""

import logging
import datetime
import operator
import collections
from typing import Sequence

from .products import SentinelOrbit, Sentinel as S1Product

from sentinelsat import SentinelAPI


_log = logging.getLogger(__name__)


class ValidityError(ValueError):
    pass


def get_validity_info(products: Sequence[str]) -> Sequence[SentinelOrbit]:
    return [SentinelOrbit(product_id) for product_id in products]


def lastval_cover(t0: datetime.datetime, t1: datetime.datetime,
                  data: Sequence[SentinelOrbit]) -> str:
    candidates = [
        item for item in data
        if item.start_time <= t0 and item.stop_time >= t1
    ]
    if not candidates:
        raise ValidityError(
            f'none of the input products completely covers the requested '
            f'time interval: [t0={t0}, t1={t1}]')

    candidates.sort(key=operator.attrgetter('created_time'), reverse=True)

    return candidates[0].filename


class OrbitSelectionError(RuntimeError):
    pass


class ScihubGnssClient:
    T0 = datetime.timedelta(days=1)
    T1 = datetime.timedelta(days=1)

    def __init__(self, user: str = "gnssguest", password: str = "gnssguest",
                 api_url: str = "https://scihub.copernicus.eu/gnss/",
                 **kwargs):
        self._api = SentinelAPI(user=user, password=password, api_url=api_url,
                                **kwargs)

    def query_orbit(self, t0, t1, satellite_id: str,
                    product_type: str = 'AUX_POEORB'):
        assert satellite_id in {'S1A', 'S1B'}
        assert product_type in {'AUX_POEORB', 'AUX_RESORB'}

        query_params = dict(
            producttype=product_type,
            platformserialidentifier=satellite_id[1:],
            date=[t0, t1],
        )
        _log.debug('query parameter: %s', query_params)
        products = self._api.query(**query_params)
        return products

    @staticmethod
    def _select_orbit(products, t0, t1):
        orbit_products = [p['identifier'] for p in products.values()]
        validity_info = get_validity_info(orbit_products)
        product_id = lastval_cover(t0, t1, validity_info)
        return collections.OrderedDict(
            (k, v) for k, v in products.items()
            if v['identifier'] == product_id
        )

    def query_orbit_for_product(self, product,
                                product_type: str = 'AUX_POEORB',
                                t0_margin: datetime.timedelta = T0,
                                t1_margin: datetime.timedelta = T1):
        if isinstance(product, str):
            product = S1Product(product)

        t0 = product.start_time
        t1 = product.stop_time

        products = self.query_orbit(t0 - t0_margin, t1 + t1_margin,
                                    satellite_id=product.mission,
                                    product_type=product_type)
        return self._select_orbit(products, t0, t1)

    def download(self, uuid, **kwargs):
        """Download a single orbit product.

        See sentinelsat.SentinelAPI.download for a detailed description
        of arguments.
        """
        return self._api.download(uuid, **kwargs)

    def download_all(self, products, **kwargs):
        """Download all the specified orbit products.

        See sentinelsat.SentinelAPI.download_all for a detailed description
        of arguments.
        """
        return self._api.download_all(products, **kwargs)
