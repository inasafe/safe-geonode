"""Utilities for impact.storage
"""

import os
import copy
import numpy
from osgeo import ogr, gdal
from tempfile import mkstemp
import cgi
from urllib import urlencode
from urllib2 import urlopen
from owslib.etree import etree

# The projection string depends on the gdal version
DEFAULT_PROJECTION = '+proj=longlat +datum=WGS84 +no_defs'

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


def get_layers_metadata(url, version='1.0.0'):
    """Return the metadata for each layer as an dict formed from the keywords

    The keywords are parsed and added to the metadata dictionary
    if they conform to the format "identifier:value".

    default searches both feature and raster layers by default
      Input
        url: The wfs url
        version: The version of the wfs xml expected

      Returns
        A list of dictionaries containing the metadata for each layer
    """

    # FIXME (Ole): This should be superseded by new get_metadata
    #              function which will be entirely based on OWSLib
    #              Issue #115

    # Make sure the server is reachable before continuing
    msg = ('Server %s is not reachable' % url)
    if not is_server_reachable(url):
        raise Exception(msg)

    wcs_reader = MetadataReader(url, 'wcs', version)
    wfs_reader = MetadataReader(url, 'wfs', version)
    layers = []
    layers.extend(wfs_reader.get_metadata())
    layers.extend(wcs_reader.get_metadata())
    return layers


class MetadataReader(object):
    """Read and parse capabilities document into a lxml.etree infoset

       Adapted from:
       http://trac.gispython.org/lab/browser/OWSLib/trunk/
              owslib/feature/wfs200.py#L402
    """

    # FIXME (Ole): Why are we not using WebCoverageService and
    #              WebFeatureService from OWSLib? See issue #115
    def __init__(self, server_url, service_type, version):
        """Initialize"""
        self.WFS_NAMESPACE = '{http://www.opengis.net/wfs}'
        self.WCS_NAMESPACE = '{http://www.opengis.net/wcs}'
        self.url = server_url
        self.service_type = service_type.lower()
        self.version = version
        self.xml = None
        if self.service_type == 'wcs':
            self.typelist = 'ContentMetadata'
            self.typeelms = 'CoverageOfferingBrief'
            self.namestr = 'name'
            self.titlestr = 'label'
            self.NAMESPACE = self.WCS_NAMESPACE
            self.keywordstr = 'keywords'
            self.abstractstr = 'description'
            self.layer_type = 'raster'
        elif self.service_type == 'wfs':
            self.typelist = 'FeatureTypeList'
            self.typeelms = 'FeatureType'
            self.namestr = 'Name'
            self.titlestr = 'Title'
            self.abstractstr = 'Abstract'
            self.NAMESPACE = self.WFS_NAMESPACE
            self.keywordstr = 'Keywords'
            self.layer_type = 'feature'
        else:
            msg = 'Unknown service type: "%s"' % self.service_type
            raise NotImplemented(msg)

    def capabilities_url(self):
        """Return a capabilities url
        """
        qs = []
        if self.url.find('?') != -1:
            qs = cgi.parse_qsl(self.url.split('?')[1])

        params = [x[0] for x in qs]

        if 'service' not in params:
            qs.append(('service', self.service_type))
        if 'request' not in params:
            qs.append(('request', 'GetCapabilities'))
        if 'version' not in params:
            qs.append(('version', self.version))

        urlqs = urlencode(tuple(qs))
        return self.url.split('?')[0] + '?' + urlqs

    def read(self):
        """Get and parse a WFS capabilities document, returning an
        instance of WFSCapabilitiesInfoset

        Parameters
        ----------
        url : string
            The URL to the WFS capabilities document.
        """
        request = self.capabilities_url()
        try:
            u = urlopen(request)
        except Exception, e:
            msg = ('Can not complete the request to %s, error was %s.'
                   % (request, str(e)))
            e.args = (msg,)
            raise
        else:
            response = u.read()
            # FIXME: Make sure it is not an html page with an error message.
            self.xml = response
            return etree.fromstring(self.xml)

    def readString(self, st):
        """Parse a WFS capabilities document, returning an
        instance of WFSCapabilitiesInfoset

        string should be an XML capabilities document
        """
        if not isinstance(st, str):
            raise ValueError('String must be of type string, '
                             'not %s' % type(st))
        return etree.fromstring(st)

    def get_metadata(self):
        """Get metadata for all layers of given service_type

        FIXME (Ole): Need all metadata, especially bounding boxes
                     for both vector and raster data.
                     See issue https://github.com/AIFDR/riab/issues/95
        """

        _capabilities = self.read()
        request_url = self.capabilities_url()
        serviceidentelem = _capabilities.find(self.NAMESPACE + 'Service')
        typelistelem = _capabilities.find(self.NAMESPACE + self.typelist)

        msg = ('Could not find element "%s" in namespace %s on %s'
               % (self.typelist, self.NAMESPACE, self.url))
        assert typelistelem is not None, msg

        typeelems = typelistelem.findall(self.NAMESPACE + self.typeelms)
        layers = []
        for f in typeelems:
            metadata = {'layer_type': self.layer_type}
            name = f.findall(self.NAMESPACE + self.namestr)
            title = f.findall(self.NAMESPACE + self.titlestr)
            kwds = f.findall(self.NAMESPACE + self.keywordstr)
            abstract = f.findall(self.NAMESPACE + self.abstractstr)

            layer_name = name[0].text
            #workspace_name = 'geonode' # FIXME (Ole): This is not used

            metadata['title'] = title[0].text

            # FIXME (Ole): Why only wcs?
            if self.service_type == 'wcs':
                kwds = kwds[0].findall(self.NAMESPACE + 'keyword')

            if kwds is not None:
                for kwd in kwds[:]:
                    # Split all the keypairs
                    keypairs = str(kwd.text).split(',')
                    for val in keypairs:
                        # Only use keywords containing at least one :
                        if str(val).find(':') > -1:
                            k, v = val.split(':')
                            metadata[k.strip()] = v.strip()

            layers.append([layer_name, metadata])
        return layers


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

