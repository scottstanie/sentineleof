"""
CLI tool for downloading Sentinel 1 EOF files
"""

from __future__ import annotations

import logging
from typing import Optional

import click
from ._types import Filename

from eof import download, log
from eof._auth import NASA_HOST, DATASPACE_HOST, setup_netrc


@click.command()
@click.option(
    "--search-path",
    "-p",
    type=click.Path(exists=False, file_okay=False, writable=True),
    default=".",
    help="Path of interest for finding Sentinel products. ",
    show_default=True,
)
@click.option(
    "--save-dir",
    type=click.Path(exists=False, file_okay=False, writable=True),
    default=".",
    help="Directory to save output .EOF files into",
    show_default=True,
)
@click.option(
    "--sentinel-file",
    type=click.Path(exists=False, file_okay=True, dir_okay=True),
    help="Specify path to download only 1 .EOF for a Sentinel-1 file/folder",
    show_default=True,
)
@click.option(
    "--date",
    "-d",
    help="Alternative to specifying Sentinel products: choose date to download for.",
)
@click.option(
    "--mission",
    "-m",
    type=click.Choice(["S1A", "S1B"]),
    help=(
        "If using `--date`, optionally specify Sentinel satellite to download"
        " (default: gets both S1A and S1B)"
    ),
)
@click.option(
    "--orbit-type",
    type=click.Choice(["precise", "restituted"]),
    default="precise",
    help="Optionally specify the type of orbit file to get "
    "(default: precise (POEORB), but fallback to restituted (RESORB))",
)
@click.option(
    "--force-asf",
    is_flag=True,
    help="Force the downloader to search ASF instead of ESA.",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Set logging level to DEBUG",
)
@click.option(
    "--cdse-access-token",
    help="Copernicus Data Space Ecosystem access-token. "
    "The access token can be generated beforehand. See https://documentation.dataspace.copernicus.eu/APIs/Token.html",
)
@click.option(
    "--cdse-user",
    help="Copernicus Data Space Ecosystem username. "
    "If not provided the program asks for it",
)
@click.option(
    "--cdse-password",
    help="Copernicus Data Space Ecosystem password. "
    "If not provided the program asks for it",
)
@click.option(
    "--cdse-2fa-token",
    help="Copernicus Data Space Ecosystem Two-Factor Token. "
    "Optional, unless 2FA Authentification has been enabled in user profile.",
)
@click.option(
    "--asf-user",
    help="ASF username. If not provided the program asks for it",
)
@click.option(
    "--asf-password",
    help="ASF password. If not provided the program asks for it",
)
@click.option(
    "--ask-password",
    is_flag=True,
    help="ask for passwords interactively if needed",
)
@click.option(
    "--update-netrc",
    is_flag=True,
    help="save credentials provided interactively in the ~/.netrc file if necessary",
)
@click.option(
    "--netrc-file",
    help="Path to .netrc file. Default: ~/.netrc",
)
@click.option(
    "--max-workers",
    type=int,
    default=3,
    help="Number of parallel downloads to run. Note that CDSE has a limit of 4",
)
def cli(
    search_path: str,
    save_dir: str,
    sentinel_file: str,
    date: str,
    mission: str,
    orbit_type: str,
    force_asf: bool,
    debug: bool,
    asf_user: str = "",
    asf_password: str = "",
    cdse_access_token: Optional[str] = None,
    cdse_user: str = "",
    cdse_password: str = "",
    cdse_2fa_token: str = "",
    ask_password: bool = False,
    update_netrc: bool = False,
    netrc_file: Optional[Filename] = None,
    max_workers: int = 3,
):
    """Download Sentinel precise orbit files.

    Saves files to `save-dir` (default = current directory)

    Download EOFs for specific date, or searches for Sentinel files in --path.
    Will find both ".SAFE" and ".zip" files matching Sentinel-1 naming convention.
    With no arguments, searches current directory for Sentinel 1 products
    """
    log._set_logger_handler(level=logging.DEBUG if debug else logging.INFO)
    if ask_password:
        dryrun = not update_netrc
        if not force_asf and not (cdse_user and cdse_password):
            cdse_user, cdse_password = setup_netrc(netrc_file=netrc_file, host=DATASPACE_HOST, dryrun=dryrun)
        if not (cdse_user and cdse_password) and not (asf_user and asf_password):
            asf_user, asf_password = setup_netrc(netrc_file=netrc_file, host=NASA_HOST, dryrun=dryrun)

    download.main(
        search_path=search_path,
        save_dir=save_dir,
        sentinel_file=sentinel_file,
        mission=mission,
        date=date,
        orbit_type=orbit_type,
        force_asf=force_asf,
        asf_user=asf_user,
        asf_password=asf_password,
        cdse_access_token=cdse_access_token,
        cdse_user=cdse_user,
        cdse_password=cdse_password,
        cdse_2fa_token=cdse_2fa_token,
        netrc_file=netrc_file,
        max_workers=max_workers,
    )
