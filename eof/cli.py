"""
CLI tool for downloading Sentinel 1 EOF files
"""
import click
from eof import download


@click.command()
@click.option("--date", "-d", help="Validity date for EOF to download")
@click.option(
    '--path',
    type=click.Path(exists=False, file_okay=False, writable=True),
    default='.',
    help="Path of interest for finding Sentinel products. ")
@click.option(
    "--mission",
    "-m",
    type=click.Choice(["S1A", "S1B"]),
    help="Sentinel satellite to download (None gets both S1A and S1B)")
def cli(date, path, mission):
    """Download Sentinel precise orbit files.

    Saves files to current directory, regardless of what --path
    is given to search.

    Download EOFs for specific date, or searches for Sentinel files in --path.
    With no arguments, searches current directory for Sentinel 1 products
    """
    download.main(path, mission, date)
