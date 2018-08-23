[![Build Status](https://travis-ci.org/scottstanie/sentineleof.svg?branch=master)](https://travis-ci.org/scottstanie/sentineleof) 
[![Coverage Status](https://coveralls.io/repos/github/scottstanie/sentineleof/badge.svg?branch=master)](https://coveralls.io/github/scottstanie/sentineleof?branch=master)

# Sentinel EOF

Tool to download Sentinel 1 precise orbit files (.EOF files) for processing SLCs


## Setup and installation

```bash
pip install sentineleof
```

This will put the executable `eof` on your path 


virtualenv is optional but recommended.

## Command Line Interface Reference

The command line tool in `cli.py` was made using the [click](https://pocco-click.readthedocs.io/en/latest/) library.

```
$ eof --help
Usage: eof [OPTIONS]

  Download Sentinel precise orbit files.

  Saves files to current directory, regardless of what --path is given to
  search.

  Download EOFs for specific date, or searches for Sentinel files in --path.
  With no arguments, searches current directory for Sentinel 1 products

Options:
  -r, --date TEXT          Validity date for EOF to download
  -m, --mission [S1A|S1B]  Sentinel satellite to download (None gets both S1A
                           and S1B)
  --help                   Show this message and exit.
```

To use the function from python, you can pass a list of dates:

```python
from eof.download import download_eofs

download_eofs([datetime.datetime(2018, 5, 3, 0, 0, 0)])
download_eofs(['20180503', '20180507'], ['S1A', 'S1B'])
```

#### parsers.py

Class to deal with extracting relevant data from SAR filenames.
Example:

```python
from parsers import Sentinel

parser = Sentinel('S1A_IW_SLC__1SDV_20180408T043025_20180408T043053_021371_024C9B_1B70.zip')
parser.start_time
    datetime.datetime(2018, 4, 8, 4, 30, 25)

parser.mission
    'S1A'

parser.polarization
    'DV'
parser.full_parse
('S1A',
 'IW',
 'SLC',
 '_',
 '1',
 'S',
 'DV',
 '20180408T043025',
 '20180408T043053',
 '021371',
 '024C9B',
 '1B70')


parser.field_meanings
('Mission',
 'Beam',
 'Product type',
 'Resolution class',
 'Product level',
 'Product class',
 'Polarization',
 'Start datetime',
 'Stop datetime',
 'Orbit number',
 'data-take identified',
 'product unique id')

```
