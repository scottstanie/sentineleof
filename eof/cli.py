"""
CLI tool for downloading Sentinel 1 EOF files
"""
import click
from eof import download
from eof import log


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
@click.option("--date", "-d", help="Validity date for EOF to download")
@click.option(
    "--mission",
    "-m",
    type=click.Choice(["S1A", "S1B"]),
    help="Optionally specify Sentinel satellite to download (default: gets both S1A and S1B)",
)
def cli(search_path, save_dir, sentinel_file, date, mission):
    """Download Sentinel precise orbit files.

    Saves files to `save-dir` (default = current directory)

    Download EOFs for specific date, or searches for Sentinel files in --path.
    Will find both ".SAFE" and ".zip" files matching Sentinel-1 naming convention.
    With no arguments, searches current directory for Sentinel 1 products
    """
    log._set_logger_handler()
    download.main(
        search_path=search_path,
        save_dir=save_dir,
        sentinel_file=sentinel_file,
        mission=mission,
        date=date,
    )
