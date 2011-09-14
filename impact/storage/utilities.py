"""Utilities for impact.storage
"""

import os
import copy
import numpy
from osgeo import ogr
from tempfile import mkstemp
from urllib2 import urlopen

# Spatial layer file extensions that are recognised in Risiko
# FIXME: Perhaps add '.gml', '.zip', ...
LAYER_TYPES = ['.shp', '.asc', '.tif', '.tiff', '.geotif', '.geotiff']

# Map between extensions and ORG drivers
DRIVER_MAP = {'.shp': 'ESRI Shapefile',
              '.gml': 'GML',
              '.tif': 'GTiff',
              '.asc': 'AAIGrid'}

# Map between Python types and OGR field types
# FIXME (Ole): I can't find a double precision type for OGR
TYPE_MAP = {type(None): ogr.OFTString,  # What else should this be?
            type(''): ogr.OFTString,
            type(0): ogr.OFTInteger,
            type(0.0): ogr.OFTReal,
            type(numpy.array([0.0])[0]): ogr.OFTReal,  # numpy.float64
            type(numpy.array([[0.0]])[0]): ogr.OFTReal}  # numpy.ndarray


# Miscellaneous auxiliary functions
def unique_filename(**kwargs):
    """Create new filename guaranteed not to exist previoously

    Use mkstemp to create the file, then remove it and return the name

    See http://docs.python.org/library/tempfile.html for details.
    """

    _, filename = mkstemp(**kwargs)

    try:
        os.remove(filename)
    except:
        pass

    return filename

def truncate_field_names(data, n=10):
    """Truncate field names to fixed width

    Input
        data: List of dictionary with names as keys. Can also be None.
        n: Max number of characters allowed

    Output
        dictionary with same values as data but with keys truncated
    """

    if data is None:
        return None

    N = len(data)

    # Check if truncation is needed
    need_to_truncate = False
    for key in data[0]:
        if len(key) > n:
            need_to_truncate = True

    if not need_to_truncate:
        return data

    # Go ahead and truncate attribute table for every entry
    new = []
    for i in range(N):
        D = {}  # New dictionary
        for key in data[i]:
            x = key[:n]
            if x in D:
                msg = ('Truncated attribute name %s is duplicated: %s ' %
                       (key, str(D.keys())))
                raise Exception(msg)

            D[x] = data[i][key]

        new.append(D)

    return new

""" FIXME: The truncation method can be replaced with something like this

>>> from osgeo import ogr
>>> from osgeo import osr
>>> drv = ogr.GetDriverByName('ESRI Shapefile')
>>> ds = drv.CreateDataSource('shptest.shp')
>>> lyr = ds.CreateLayer('mylyr', osr.SpatialReference(), ogr.wkbPolygon)
>>> fd = ogr.FieldDefn('A slightly long name', ogr.OFTString)
>>> lyr.CreateField(fd)
Warning 6: Normalized/laundered field name: 'A slightly long name' to 'A slightly'
0
>>> layer_defn = lyr.GetLayerDefn()
>>> last_field_idx = layer_defn.GetFieldCount() - 1
>>> real_field_name = layer_defn.GetFieldDefn(last_field_idx).GetNameRef()
>>> feature = ogr.Feature(layer_defn)
>>> feature.SetField('A slightly', 'value')
>>> real_field_name
'A slightly'
"""


# GeoServer utility functions
def is_server_reachable(url):
    """Make an http connection to url to see if it is accesible.

       Returns boolean
    """
    try:
        urlopen(url)
    except Exception:
        return False
    else:
        return True


def write_keywords(keywords, filename):
    """Write keywords dictonary to file

    Input
        keywords: Dictionary of keyword, value pairs
        filename: Name of keywords file. Extension expected to be .keywords

    Keys must be strings
    Values must be strings or None.

    If value is None, only the key will be written. Otherwise key, value pairs
    will be written as key: value

    Trailing or preceding whitespace will be ignored.
    """

    # Input checks
    basename, ext = os.path.splitext(filename)

    msg = ('Unknown extension for file %s. '
           'Expected %s.keywords' % (filename, basename))
    assert ext == '.keywords', msg

    # Write
    fid = open(filename, 'w')
    for k, v in keywords.items():

        msg = ('Key in keywords dictionary must be a string. '
               'I got %s with type %s' % (k, type(k)))
        assert isinstance(k, basestring), msg

        key = k.strip()

        msg = ('Key in keywords dictionary must not contain the ":" '
               'character. I got "%s"' % key)
        assert ':' not in key, msg

        if v is None:
            fid.write('%s\n' % key)
        else:
            val = v.strip()

            msg = ('Value in keywords dictionary must be a string or None. '
                   'I got %s with type %s' % (val, type(val)))
            assert isinstance(val, basestring), msg

            msg = ('Value must not contain the ":" character. '
                   'I got "%s"' % val)
            assert ':' not in val, msg

            fid.write('%s: %s\n' % (key, val))
    fid.close()


def read_keywords(filename):
    """Read keywords dictonary from file

    Input
        filename: Name of keywords file. Extension expected to be .keywords
                  The format of one line is expected to be either
                  string: string
                  or
                  string
    Output
        keywords: Dictionary of keyword, value pairs
    """

    # Input checks
    basename, ext = os.path.splitext(filename)

    msg = ('Unknown extension for file %s. '
           'Expected %s.keywords' % (filename, basename))
    assert ext == '.keywords', msg

    if not os.path.isfile(filename):
        return {}

    # Read
    keywords = {}
    fid = open(filename, 'r')
    for line in fid.readlines():
        text = line.strip()
        if text == '':
            continue

        fields = text.split(':')

        msg = ('Keyword must be either "string" or "string: string". '
               'I got %s ' % text)
        assert len(fields) in [1, 2], msg

        key = fields[0].strip()

        if len(fields) == 2:
            val = fields[1].strip()
        else:
            val = None

        keywords[key] = val
    fid.close()

    return keywords


def extract_geotransform(layer):
    """Extract geotransform from OWS layer object.

    Input
        layer: Raster layer object e.g. obtained from WebCoverageService

    Output:
        geotransform: GDAL geotransform (www.gdal.org/gdal_tutorial.html)
    """

    grid = layer.grid

    top_left_x = float(grid.origin[0])
    we_pixel_res = float(grid.offsetvectors[0][0])
    x_rotation = float(grid.offsetvectors[0][1])
    top_left_y = float(grid.origin[1])
    y_rotation = float(grid.offsetvectors[1][0])
    ns_pixel_res = float(grid.offsetvectors[1][1])

    # There is half a pixel_resolution difference between
    # what WCS reports and what GDAL reports.
    # A pixel CENTER vs pixel CORNER difference.
    adjusted_top_left_x = top_left_x - we_pixel_res / 2
    adjusted_top_left_y = top_left_y - ns_pixel_res / 2

    return (adjusted_top_left_x, we_pixel_res, x_rotation,
            adjusted_top_left_y, y_rotation, ns_pixel_res)


def geotransform2bbox(geotransform, columns, rows):
    """Convert geotransform to bounding box

    Input
        geotransform: GDAL geotransform (6-tuple).
                      (top left x, w-e pixel resolution, rotation,
                      top left y, rotation, n-s pixel resolution).
                      See e.g. http://www.gdal.org/gdal_tutorial.html
        columns: Number of columns in grid
        rows: Number of rows in grid

    Output
        bbox: Bounding box as a list of geographic coordinates
              [west, south, east, north]
    """

    x_origin = geotransform[0]  # top left x
    y_origin = geotransform[3]  # top left y
    x_res = geotransform[1]     # w-e pixel resolution
    y_res = geotransform[5]     # n-s pixel resolution
    x_pix = columns
    y_pix = rows

    minx = x_origin
    maxx = x_origin + (x_pix * x_res)
    miny = y_origin + (y_pix * y_res)
    maxy = y_origin

    return [minx, miny, maxx, maxy]


def bbox_intersection(*args):
    """Compute intersection between two or more bounding boxes

    Input
        args: two or more bounding boxes.
              Each is assumed to be a list or a tuple with
              four coordinates (W, S, E, N)

    Output
        result: The minimal common bounding box

    """

    msg = 'Function bbox_intersection must take at least 2 arguments.'
    assert len(args) > 1, msg

    result = [-180, -90, 180, 90]
    for a in args:
        msg = ('Bounding box expected to be a list of the '
               'form [W, S, E, N]. '
               'Instead i got "%s"' % str(a))
        try:
            box = list(a)
        except:
            raise Exception(msg)

        assert len(box) == 4, msg

        msg = 'Western boundary must be less than eastern. I got %s' % box
        assert box[0] < box[2], msg

        msg = 'Southern boundary must be less than northern. I got %s' % box
        assert box[1] < box[3], msg

        # Compute intersection

        # West and South
        for i in [0, 1]:
            result[i] = max(result[i], box[i])

        # East and North
        for i in [2, 3]:
            result[i] = min(result[i], box[i])

    # Check validity and return
    if result[0] < result[2] and result[1] < result[3]:
        return result
    else:
        return None


def minimal_bounding_box(bbox, min_res, eps=1.0e-6):
    """Grow bounding box to exceed specified resolution if needed

    Input
        bbox: Bounding box with format [W, S, E, N]
        min_res: Minimal acceptable resolution to exceed
        eps: Optional tolerance that will be applied to 'buffer' result

    Ouput
        Adjusted bounding box guarenteed to exceed specified resolution
    """

    bbox = copy.copy(list(bbox))

    delta_x = bbox[2] - bbox[0]
    delta_y = bbox[3] - bbox[1]

    if delta_x < min_res:
        dx = (min_res - delta_x) / 2 + eps
        bbox[0] -= dx
        bbox[2] += dx

    if delta_y < min_res:
        dy = (min_res - delta_y) / 2 + eps
        bbox[1] -= dy
        bbox[3] += dy

    return bbox


def get_geometry_type(geometry):
    """Determine geometry type based on data

    Input
        geometry: A list of either point coordinates [lon, lat] or polygons
                  which are assumed to be numpy arrays of coordinates

    Output
        geometry_type: Either ogr.wkbPoint or ogr.wkbPolygon

    If geometry type cannot be determined an Exception is raised.

    Note, there is no consistency check across all entries of the
    geometry list, only the first element is used in this determination.
    """

    msg = 'Argument geometry must be a sequence. I got %s ' % type(geometry)
    assert is_sequence(geometry), msg

    msg = ('The first element in geometry must be a sequence of length > 2. '
           'I got %s ' % str(geometry[0]))
    assert is_sequence(geometry[0]), msg
    assert len(geometry[0]) >= 2, msg

    if len(geometry[0]) == 2:
        try:
            float(geometry[0][0])
            float(geometry[0][1])
        except:
            pass
        else:
            # This geometry appears to be point data
            geometry_type = ogr.wkbPoint
    elif len(geometry[0]) > 2:
        try:
            x = numpy.array(geometry[0])
        except:
            pass
        else:
            # This geometry appears to be polygon data
            if x.shape[0] > 2 and x.shape[1] == 2:
                geometry_type = ogr.wkbPolygon

    if geometry_type is None:
        msg = 'Could not determine geometry type'
        raise Exception(msg)

    return geometry_type


def is_sequence(x):
    """Determine if x behaves like a true sequence but not a string

    This will for example return True for lists, tuples and numpy arrays
    but False for strings and dictionaries.
    """

    if isinstance(x, basestring):
        return False

    try:
        x[0]
    except:
        return False
    else:
        return True


def array2wkt(A, geom_type='POLYGON'):
    """Convert coordinates to wkt format

    Input
        A: Nx2 Array of coordinates representing either a polygon or a line.
           A can be either a numpy array or a list of coordinates.
        geom_type: Determines output keyword 'POLYGON' or 'LINESTRING'

    Output
        wkt: geometry in the format known to ogr: Examples

        POLYGON((1020 1030,1020 1045,1050 1045,1050 1030,1020 1030))
        LINESTRING(1000 1000, 1100 1050)

    """

    if geom_type == 'LINESTRING':
        # One bracket
        n = 1
    elif geom_type == 'POLYGON':
        # Two brackets (tsk tsk)
        n = 2
    else:
        msg = 'Unknown geom_type: %s' % geom_type
        raise Exception(msg)

    wkt_string = geom_type + '(' * n

    N = len(A)
    for i in range(N):
        wkt_string += '%f %f, ' % tuple(A[i])  # Works for both lists and arrays

    return wkt_string[:-2] + ')' * n

def calculate_polygon_area(polygon, signed=False):
    """Calculate the signed area of non-self-intersecting polygon

    Input
        polygon: Numeric array of points (longitude, latitude). It is assumed
                 to be closed, i.e. first and last points are identical
        signed: Optional flag deciding whether returned area retains its sign:
                If points are ordered counter clockwise, the signed area will be positive.
                If points are ordered clockwise, it will be negative
                Default is False which means that the area is always positive.

    Output
        area: Area of polygon (subject to the value of argument signed)

    Sources
        http://paulbourke.net/geometry/polyarea/
        http://en.wikipedia.org/wiki/Centroid
    """

    # Make sure it is numeric
    P = numpy.array(polygon)

    msg = ('Polygon is assumed to consist of coordinate pairs. '
           'I got second dimension %i instead of 2' % P.shape[1])
    assert P.shape[1] == 2, msg

    x = P[:, 0]
    y = P[:, 1]

    # Calculate 0.5 sum_{i=0}^{N-1} (x_i y_{i+1} - x_{i+1} y_i)
    a = x[:-1] * y[1:]
    b = y[:-1] * x[1:]

    A = numpy.sum(a - b) / 2.

    if signed:
        return A
    else:
        return abs(A)

def calculate_polygon_centroid(polygon):
    """Calculate the centroid of non-self-intersecting polygon

    Input
        polygon: Numeric array of points (longitude, latitude). It is assumed
                 to be closed, i.e. first and last points are identical

    Sources
        http://paulbourke.net/geometry/polyarea/
        http://en.wikipedia.org/wiki/Centroid
    """

    # Make sure it is numeric
    P = numpy.array(polygon)

    # Normalise to ensure numerical accurracy.
    # This requirement in backed by tests in test_io.py and without it
    # centroids at building footprint level may get shifted outside the polygon!
    P_origin = numpy.amin(P, axis=0)
    P = P - P_origin

    # Get area. This calculation could be incorporated to save time
    # if necessary as the two formulas are very similar.
    A = calculate_polygon_area(polygon, signed=True)

    x = P[:, 0]
    y = P[:, 1]

    # Calculate Cx = sum_{i=0}^{N-1} (x_i + x_{i+1})(x_i y_{i+1} - x_{i+1} y_i)/(6A)
    # Calculate Cy = sum_{i=0}^{N-1} (y_i + y_{i+1})(x_i y_{i+1} - x_{i+1} y_i)/(6A)
    a = x[:-1] * y[1:]
    b = y[:-1] * x[1:]

    cx = x[:-1] + x[1:]
    cy = y[:-1] + y[1:]

    Cx = numpy.sum(cx * (a - b)) / (6. * A)
    Cy = numpy.sum(cy * (a - b)) / (6. * A)

    # Translate back to real location
    C = numpy.array([Cx, Cy]) + P_origin
    return C
