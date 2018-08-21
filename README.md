[![Build Status](https://travis-ci.org/scottstanie/insar.svg?branch=master)](https://travis-ci.org/scottstanie/insar) 
[![Coverage Status](https://coveralls.io/repos/github/scottstanie/insar/badge.svg?branch=master)](https://coveralls.io/github/scottstanie/insar?branch=master)

# InSAR utils

Utilities for Synthetic apeture radar (SAR) and Interferometric SAR (InSAR) processing


## Setup and installation

```bash
pip install insar
```

This will put the executable `insar` on your path with several commands available to use:


Or for development use (to change code and have it be reflected in what is installed):

```bash
# Optional for using virtualenv
virtualenv ~/envs/insar && source ~/envs/insar/bin/activate  # Or wherever you store your virtual envs
# Or if you have virtualenv wrapper: mkvirtualenv insar

git clone https://github.com/scottstanie/insar.git
cd insar
make build     # which runs python setup.py build_ext --inplace for the cython extension
pip install -r requirements.txt
pip install --editable .
```
and to also install the necessary extras for running unit tests:
```bash
pip install -r requirements-dev.txt
```

virtualenv is optional but recommended.

## Command Line Interface Reference

The command line tool in `insar/scripts/cli.py` was made using the [click](https://pocco-click.readthedocs.io/en/latest/) library.

```
$ insar --help
Usage: insar [OPTIONS] COMMAND [ARGS]...

  Command line tools for processing insar.

Options:
  --verbose
  --path DIRECTORY  Path of interest for command. Will search for files path
                    or change directory, depending on command.
  --help            Show this message and exit.

Commands:
  animate     Creates animation for 3D image stack.
  dem         Stiches .hgt files to make one DEM and...
  download    Download Sentinel precise orbit files.
  kml         Creates .kml file for tif image TIFFILE is...
  process     Process stack of Sentinel interferograms.
  view-dem    View a .dem file with matplotlib.
  view-stack  Explore timeseries on deformation image.
```

```
$ insar dem --help
Usage: insar dem [OPTIONS]

  Stiches .hgt files to make one DEM and .dem.rsc file

  Pick a lat/lon bounding box for a DEM, and it will download the necessary
  SRTM1 tile, combine into one array, then upsample using upsample.c

  Suggestion for box: http://geojson.io gives you geojson for any polygon
  Take the output of that and save to a file (e.g. mybox.geojson

  Usage:

      insar dem --geojson data/mybox.geojson --rate 2

      insar dem -g data/mybox.geojson -r 2 -o elevation.dem

  Default out is elevation.dem for upsampled version, elevation_small.dem
  Also creates elevation.dem.rsc with start lat/lon, stride, and other info.

Options:
  -g, --geojson FILENAME        File containing the geojson object for DEM
                                bounds  [required]
  -r, --rate INTEGER RANGE      Rate at which to upsample DEM (default=1, no
                                upsampling)
  -o, --output FILENAME         Name of output dem file
                                (default=elevation.dem)
  -d, --data-source [NASA|AWS]  Source of SRTM data. See insar.dem docstring
                                for more about data.
  --help                        Show this message and exit.
```

```
$ insar download --help
Usage: insar download [OPTIONS]

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

### More on subcommands and some module example usage

#### dem.py

`insar dem` creates a cropped (and possibly upsampled) digital elevation map.


```bash
insar dem --geojson data/hawaii.geojson --rate 2 --output elevation.dem
insar dem -g data/hawaii_bigger.geojson -r 5 --output elevation.dem
```

The geojson can be any valid simple Polygon- you can get one easily from http://geojson.io , for example.

Functions for working with digital elevation maps (DEMs) are mostly contained in the `Downloader` and `Stitcher` classes within `insar/dem.py`.

Once you have made this, if you want to get a quick look in python, the script `insar/scripts/view_dem.py` opens the file and plots with matplotlib.

If you have multiple, you can plot them using matplotlib for a quick look.

```bash
insar view_dem elevation1.dem elevation2.dem
```

The default datasource is NASA's SRTM version 3 global 1 degree data.
See https://lpdaac.usgs.gov/dataset_discovery/measures/measures_products_table/srtmgl3s_v003

This data requires a username and password from here:
https://urs.earthdata.nasa.gov/users/new

You will be prompted for a username and password when running with NASA data.
It will save into your ~/.netrc file for future use, which means you will not have to enter a username and password any subsequent times.
The entry will look like this:

```
machine urs.earthdata.nasa.gov
    login USERNAME
    password PASSWORD
```

If you want to avoid this entirely, you can [use Mapzen's data hosted on AWS](https://registry.opendata.aws/terrain-tiles/) by specifying
```bash
insar dem -g data/hawaii_bigger.geojson --data-source AWS
```

`--data-source NASA` is the default.

Mapzen combines SRTM data with other sources, so the .hgt files will be slightly different.
They also list that they are discontinuing some services, which is why NASA is the default.


#### eof.py

Functions for dealing with precise orbit files (POE) for Sentinel 1 (which are .EOF files)

```bash
$ insar download
```

The script without arguments will look in the current directory for .EOF files.


You can also specify dates, with or without a mission (S1A/S1B):

```bash
insar download --date 20180301 
insar download -d 2018-03-01 --mission S1A
```

Using it from python, you can pass a list of dates:

```python
from insar.eof import download_eofs

download_eofs([datetime.datetime(2018, 5, 3, 0, 0, 0)])
download_eofs(['20180503', '20180507'], ['S1A', 'S1B'])
```

#### sario.py

Input/Output functions for SAR data.
Contains methods to load Sentinel, UAVSAR or DEM files for now.

Main function: 

```python
import insar.sario
my_slc = insar.sario.load('/file/path/radar.slc')
my_int = insar.sario.load('/file/path/interferogram.int')
my_dem = insar.sario.load('/file/path/elevation.dem')
my_hgt = insar.sario.load('/file/path/N20W100.hgt')
```


#### parsers.py

Classes to deal with extracting relevant data from SAR filenames.
Example:

```python
from insar.parsers import Sentinel

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

UAVSAR parser also exists.

More will be added in the future.


#### geojson.py

Simple functions for getting handling geojson inputs:


```python
from insar.geojson import read_json, bounding_box, print_coordinates
json_dict = read_json(input_string)
```

Running the module as a script will give you both the bounding box, and the comma-joined lon,lat pairs of the polygon:

```
$ cat data/hawaii.geojson | python insar/geojson.py 
-155.67626953125,19.077692991868297,-154.77264404296875,19.077692991868297,-154.77264404296875,19.575317892869453,-155.67626953125,19.575317892869453,-155.67626953125,19.077692991868297
-155.67626953125 19.077692991868297 -154.77264404296875 19.575317892869453

$ cat data/hawaii.geojson 
{
  "type": "Polygon",
  "coordinates": [
    [
		  [
		    -155.67626953125,
		    19.077692991868297
		  ],
		  [
		    -154.77264404296875,
		    19.077692991868297
		  ],
		  [
		    -154.77264404296875,
		    19.575317892869453
		  ],
		  [
		    -155.67626953125,
		    19.575317892869453
		  ],
		  [
		    -155.67626953125,
		    19.077692991868297
		  ]
    ]
  ]
}
```

#### log.py

Module to make logging pretty with times and module names.

If you also `pip install colorlog`, it will become colored (didn't require this in case people like non-color logs.)

```python
from insar.log import get_log
logger = get_log()
logger.info("Better than printing")
```

```
[05/29 16:28:19] [INFO log.py] Better than printing
```
