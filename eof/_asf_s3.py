from functools import cache
from typing import Optional, Literal

import requests
import xml.etree.ElementTree as ET

from .log import logger

ASF_BUCKET_NAME = "s1-orbits"


@cache
def list_public_bucket(bucket_name: str, prefix: str = "") -> list[str]:
    """List all objects in a public S3 bucket.

    Parameters
    ----------
    bucket_name : str
        Name of the S3 bucket.
    prefix : str, optional
        Prefix to filter objects, by default "".

    Returns
    -------
    list[str]
        list of object keys in the bucket.

    Raises
    ------
    requests.RequestException
        If there's an error in the HTTP request.
    """
    endpoint = f"https://{bucket_name}.s3.amazonaws.com"
    marker: Optional[str] = None
    keys: list[str] = []

    while True:
        params = {"prefix": prefix}
        if marker:
            params["marker"] = marker

        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error fetching bucket contents: {e}")
            raise

        root = ET.fromstring(response.content)
        for contents in root.findall(
            "{http://s3.amazonaws.com/doc/2006-03-01/}Contents"
        ):
            key = contents.find("{http://s3.amazonaws.com/doc/2006-03-01/}Key")
            if key is not None:
                keys.append(key.text or "")
                logger.debug(f"Found key: {key}")

        is_truncated = root.find("{http://s3.amazonaws.com/doc/2006-03-01/}IsTruncated")
        if (
            is_truncated is not None
            and is_truncated.text
            and is_truncated.text.lower() == "true"
        ):
            next_marker = root.find(
                "{http://s3.amazonaws.com/doc/2006-03-01/}NextMarker"
            )
            if next_marker is not None:
                marker = next_marker.text
            else:
                found_keys = root.findall(
                    "{http://s3.amazonaws.com/doc/2006-03-01/}Contents/{http://s3.amazonaws.com/doc/2006-03-01/}Key"
                )
                if found_keys:
                    marker = found_keys[-1].text
                else:
                    break
        else:
            break

    return keys


def get_orbit_files(orbit_type: Literal["precise", "restituted"]) -> list[str]:
    """Get a list of precise or restituted orbit files.

    Parameters
    ----------
    orbit_type : Literal["precise", "restituted"]
        Type of orbit files to retrieve.

    Returns
    -------
    list[str]
        list of orbit file keys.

    Raises
    ------
    ValueError
        If an invalid orbit_type is provided.
    """
    if orbit_type not in ("precise", "restituted"):
        raise ValueError("orbit_type must be either 'precise' or 'restituted'")
    prefix = "AUX_POEORB" if orbit_type == "precise" else "AUX_RESORB"

    orbit_files = list_public_bucket(ASF_BUCKET_NAME, prefix=prefix)

    logger.info(f"Found {len(orbit_files)} {orbit_type} orbit files")
    return orbit_files
