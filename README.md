[![Build](https://github.com/scottstanie/sentineleof/actions/workflows/ci.yml/badge.svg)](https://github.com/scottstanie/sentineleof/actions/workflows/ci.yml)
[![PyPI version][pypi-version]][pypi-link]
[![Conda-Forge][conda-badge]][conda-link]
[![PyPI platforms][pypi-platforms]][pypi-link]

<!-- prettier-ignore-start -->
[conda-badge]:              https://img.shields.io/conda/vn/conda-forge/sentineleof
[conda-link]:               https://github.com/conda-forge/sentineleof-feedstock
[pypi-link]:                https://pypi.org/project/sentineleof/
[pypi-platforms]:           https://img.shields.io/pypi/pyversions/sentineleof
[pypi-version]:             https://img.shields.io/pypi/v/sentineleof
<!-- prettier-ignore-end -->

# Sentinel EOF

Tool to download Sentinel 1 precise/restituted orbit files (.EOF files) for processing SLCs

## (Update 2023-10-31) Changes to Sentinel-1 orbit files source

The [Copernicus Scihub client has discontinued service](https://scihub.copernicus.eu/) in favor of [the new Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/). The new service no longer allows anonymous public downloads (using the `gnssuser`), which means you must register for either a Dataspace account (to use the CDSE data) or a NASA Earthdata account (to use the orbits provided by ASF).

*Changes required by you to continue using this tool:*

Option 1: Register for CDSE

1. Register for an account with Copernicus Data Space account at https://dataspace.copernicus.eu/ (using the Loging button, which will have the option for a "Register" page)
2. After creating the username and confirming your email, store your username/password in a `~/.netrc` file with the hostname `dataspace.copernicus.eu`:
```
machine dataspace.copernicus.eu
  login MYUSERNAME
  password MYPASSWORD
```

Option 2: Register for NASA Earthdata

1. Register for an account with NASA Earthdata at https://urs.earthdata.nasa.gov/users/new
2. After creating the username and confirming your email, store your username/password in a `~/.netrc` file with the hostname `urs.earthdata.nasa.gov`:
```
machine urs.earthdata.nasa.gov
  login MYUSERNAME
  password MYPASSWORD
```

## Setup and installation

```bash
pip install sentineleof
```

or through conda:

```bash
conda install -c conda-forge sentineleof
```

This will put the executable `eof` on your path

After setting up your `~/.netrc` (see above), if you have a bunch of Sentinel 1 zip files (or unzipped SAFE folders), you can simply run

```bash
eof
```
and download either the precise orbit files, or, if the POEORB files have not been released, the restituted RESORB files.

Running
```bash
eof --search-path /path/to/safe_files/ --save-dir ./orbits/
```
will search `/path/to/safe_files/` for Sentinel-1 scenes, and save the `.EOF` files to `./orbits/` (creating it if it does not exist)


## Command Line Interface Reference

Full options available for the command line tool are:

```
$ eof --help
Usage: eof [OPTIONS]

  Download Sentinel precise orbit files.

  Saves files to `save-dir` (default = current directory)

  Download EOFs for specific date, or searches for Sentinel files in --path.
  Will find both ".SAFE" and ".zip" files matching Sentinel-1 naming
  convention. With no arguments, searches current directory for Sentinel 1
  products

Options:
  -p, --search-path DIRECTORY     Path of interest for finding Sentinel
                                  products.   [default: .]
  --save-dir DIRECTORY            Directory to save output .EOF files into
                                  [default: .]
  --sentinel-file PATH            Specify path to download only 1 .EOF for a
                                  Sentinel-1 file/folder
  -d, --date TEXT                 Alternative to specifying Sentinel products:
                                  choose date to download for.
  -m, --mission [S1A|S1B]         If using `--date`, optionally specify
                                  Sentinel satellite to download (default:
                                  gets both S1A and S1B)
  --orbit-type [precise|restituted]
                                  Optionally specify the type of orbit file to
                                  get (default: precise (POEORB), but fallback
                                  to restituted (RESORB))
  --force-asf                     Force the downloader to search ASF instead
                                  of ESA.
  --debug                         Set logging level to DEBUG
  --cdse-access-token TEXT        Copernicus Data Space Ecosystem access-
                                  token. The access token can be generated
                                  beforehand. See https://documentation.datasp
                                  ace.copernicus.eu/APIs/Token.html
  --cdse-user TEXT                Copernicus Data Space Ecosystem username. If
                                  not provided the program asks for it
  --cdse-password TEXT            Copernicus Data Space Ecosystem password. If
                                  not provided the program asks for it
  --cdse-2fa-token TEXT           Copernicus Data Space Ecosystem Two-Factor
                                  Token. Optional, unless 2FA Authentification
                                  has been enabled in user profile.
  --asf-user TEXT                 ASF username. If not provided the program
                                  asks for it
  --asf-password TEXT             ASF password. If not provided the program
                                  asks for it
  --ask-password                  ask for passwords interactively if needed
  --update-netrc                  save credentials provided interactively in
                                  the ~/.netrc file if necessary
  --netrc-file TEXT               Path to .netrc file. Default: ~/.netrc
  --max-workers INTEGER           Number of parallel downloads to run. Note
                                  that CDSE has a limit of 4
  --help                          Show this message and exit.
```

To use the function from python, you can pass a list of dates:

```python
from eof.download import download_eofs

download_eofs([datetime.datetime(2018, 5, 3, 0, 0, 0)])
download_eofs(['20180503', '20180507'], ['S1A', 'S1B'])
```
