"""Module for parsing the orbit state vectors (OSVs) from the .EOF file"""
from datetime import datetime
from xml.etree import ElementTree
from html.parser import HTMLParser
from .log import logger


class EOFLinkFinder(HTMLParser):
    """Finds EOF download links in aux.sentinel1.eo.esa.int page

    Example page to search:
    http://step.esa.int/auxdata/orbits/Sentinel-1/POEORB/S1B/2020/10/

    Usage:
    >>> import requests
    >>> resp = requests.get("http://step.esa.int/auxdata/orbits/Sentinel-1/POEORB/S1B/2020/10/")
    >>> parser = EOFLinkFinder()
    >>> parser.feed(resp.text)
    >>> print(sorted(parser.eof_links)[0])
    S1B_OPER_AUX_POEORB_OPOD_20201022T111233_V20201001T225942_20201003T005942.EOF.zip
    """

    def __init__(self):
        super().__init__()
        self.eof_links = set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and (
                    value.endswith(".EOF.zip") or value.endswith(".EOF")
                ):
                    self.eof_links.add(value)


def parse_utc_string(timestring):
    #    dt = datetime.strptime(timestring, 'TAI=%Y-%m-%dT%H:%M:%S.%f')
    #    dt = datetime.strptime(timestring, 'UT1=%Y-%m-%dT%H:%M:%S.%f')
    return datetime.strptime(timestring, "UTC=%Y-%m-%dT%H:%M:%S.%f")


def dt_to_secs(dt):
    return dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1000000.0


def _convert_osv_field(osv, field, converter=float):
    # osv is a xml.etree.ElementTree.Element
    field_str = osv.find(field).text
    return converter(field_str)


def parse_orbit(
    eof_filename,
    min_time=datetime(1900, 1, 1),
    max_time=datetime(2100, 1, 1),
):
    logger.info(
        "parsing OSVs from %s between %s and %s",
        eof_filename,
        min_time,
        max_time,
    )
    tree = ElementTree.parse(eof_filename)
    root = tree.getroot()
    all_osvs = []
    for osv in root.findall("./Data_Block/List_of_OSVs/OSV"):
        utc_dt = _convert_osv_field(osv, "UTC", parse_utc_string)
        if utc_dt < min_time or utc_dt > max_time:
            continue

        utc_secs = dt_to_secs(utc_dt)
        cur_osv = [utc_secs]
        for field in ("X", "Y", "Z", "VX", "VY", "VZ"):
            # Note: the 'unit' would be elem.attrib['unit']
            cur_osv.append(_convert_osv_field(osv, field, float))
        all_osvs.append(cur_osv)

    return all_osvs


def write_orbinfo(orbit_tuples, outname="out.orbtiming"):
    """Write file with orbit states parsed into simpler format

    seconds x y z vx vy vz ax ay az
    """
    with open(outname, "w") as f:
        f.write("0\n")
        f.write("0\n")
        f.write("0\n")
        f.write("%s\n" % len(orbit_tuples))
        for tup in orbit_tuples:
            # final 0.0 0.0 0.0 is ax, ax, az accelerations
            f.write(" ".join(map(str, tup)) + " 0.0 0.0 0.0\n")
