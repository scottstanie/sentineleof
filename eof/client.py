# -*- coding: utf-8 -*-
"""Client interface"""

from abc import abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Sequence, Union

from ._select_orbit import T_ORBIT
from ._types import Filename
from .products import Sentinel as S1Product


class OrbitType(Enum):
    """
    Enumerate the type of orbits
    """
    precise = 1
    restituted = 2


class AbstractSession:
    """
    Common interface for all download sessions

    Once a session is created, it means we are authenticated to the related server.
    """
    @abstractmethod
    def download_all(
            self,
            eofs,
            output_directory: Filename,
            max_workers: int = 3,
    ):
        """Download all the specified orbit products."""


class Client:
    """
    Common interface for all clients.
    """

    T0 = timedelta(seconds=T_ORBIT + 60)
    T1 = timedelta(seconds=60)

    @abstractmethod
    def query_orbit_by_dt(
            self,
            orbit_dts: Sequence[datetime],
            missions: Sequence[str],
            orbit_type: OrbitType,
            t0_margin: timedelta = T0,
            t1_margin: timedelta = T1,
    ):
        """
        Request orbit information according to a list of datetimes.

        Args:
            orbit_dts (list[str] or list[datetime.datetime]): datetime for orbit coverage
            missions (list[str]): optional, to specify S1A or S1B
                List of missions to query for. Must be same length as orbit_dts
            orbit_type (OrbitType): precise or restituted
                String identifying the type of orbit file to query for.

        Returns:
            List of urls/ids that can be used in associated download function.
        """

    @abstractmethod
    def query_orbits_by_dt_range(
            self,
            first_dt: datetime,
            last_dt: datetime,
            missions: Optional[Sequence[str]] = None,
            orbit_type: OrbitType = OrbitType.precise,
    ):
        """
        Request orbit information according to a list of datetimes.

        Args:
            first_dt (str datetime.datetime): first datetime for orbit coverage
            last_dt (str datetime.datetime): last datetime for orbit coverage
            missions (list[str]): optional, to specify S1A or S1B
                No input downloads both.
            orbit_type (OrbitType): precise or restituted

        Returns:
            List of urls/ids that can be used in associated download function.
        """

    def query_orbit_for_product(
            self,
            s1_product: Union[Filename, S1Product],
            orbit_type: OrbitType = OrbitType.precise,
            t0_margin: timedelta = T0,
            t1_margin: timedelta = T1,
    ):
        """
        Request orbit information according to a Sentinel-1 filename

        Args:
            s1_product (str): path to Sentinel-1 filename to download one .EOF for
            orbit_type (OrbitType): precise or restituted

        Returns:
            List of urls/ids that can be used in associated download function.
        """
        if isinstance(s1_product, str):
            s1_product = S1Product(s1_product)
        assert isinstance(s1_product, S1Product)

        return self.query_orbit_by_dt(
            [s1_product.start_time],
            [s1_product.mission],
            orbit_type=orbit_type,
            t0_margin=t0_margin,
            t1_margin=t1_margin,
        )

    @abstractmethod
    def authenticate(
            self,
            *args,  # login, password, netrc...
            **kwargs,
    ) -> AbstractSession:
        """
        Authenticate on the client for downloading
        """
