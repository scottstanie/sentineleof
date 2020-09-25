"""Module for parsing the orbit state vectors (OSVs) from the .EOF file"""
from datetime import datetime
from xml.etree import ElementTree
from .log import logger


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
