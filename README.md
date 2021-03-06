[![Build Status](https://travis-ci.org/scottstanie/sentineleof.svg?branch=master)](https://travis-ci.org/scottstanie/sentineleof) 

# Sentinel EOF

Tool to download Sentinel 1 precise/restituted orbit files (.EOF files) for processing SLCs


## Setup and installation

```bash
pip install sentineleof
```

or through conda:

```bash
conda install -c conda-forge sentineleof
```

This will put the executable `eof` on your path 


If you have a bunch of Sentinel 1 zip files (or unzipped SAFE folders), you can simply run

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

The command line tool in `cli.py` was made using the [click](https://pocco-click.readthedocs.io/en/latest/) library.

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
  -p, --search-path DIRECTORY  Path of interest for finding Sentinel products.
                               [default: .]

  --save-dir DIRECTORY         Directory to save output .EOF files into
                               [default: .]

  --sentinel-file PATH         Specify path to download only 1 .EOF for a
                               Sentinel-1 file/folder

  -d, --date TEXT              Validity date for EOF to download
  -m, --mission [S1A|S1B]      Optionally specify Sentinel satellite to
                               download (default: gets both S1A and S1B)

  --help                       Show this message and exit.
```

To use the function from python, you can pass a list of dates:

```python
from eof.download import download_eofs

download_eofs([datetime.datetime(2018, 5, 3, 0, 0, 0)])
download_eofs(['20180503', '20180507'], ['S1A', 'S1B'])
```
