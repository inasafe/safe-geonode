import numpy
import os
import sys
import unittest
import warnings
import time

from safe_geonode.views import calculate
from safe_geonode.storage import save_file_to_geonode as save_to_geonode
from safe_geonode.storage import check_layer
from safe_geonode.storage import assert_bounding_box_matches
from safe_geonode.storage import download
from safe_geonode.storage import read_layer
from safe_geonode.storage import get_metadata
from safe_geonode.storage import get_bounding_box
from safe_geonode.utilities import get_bounding_box_string
from safe_geonode.utilities import nanallclose
from safe_geonode.tests.utilities import TESTDATA, INTERNAL_SERVER_URL

from geonode.layers.utils import get_valid_user, check_geonode_is_up

from safe.common.testing import UNITDATA
from safe.engine.impact_functions_for_testing import unspecific_building_impact_model
from safe.impact_functions.core import get_admissible_plugins
from safe.impact_functions.core import requirements_collect
from safe.impact_functions.core import requirements_met
from safe.impact_functions.inundation.flood_OSM_building_impact import FloodBuildingImpactFunction

from django.test.client import Client
from django.test import LiveServerTestCase
from django.conf import settings
from django.utils import simplejson as json
from django.core.urlresolvers import reverse

from owslib.wcs import WebCoverageService


def lembang_damage_function(x):
    if x < 6.0:
        value = 0.0
    else:
        value = (0.692 * (x ** 4) -
                 15.82 * (x ** 3) +
                 135.0 * (x ** 2) -
                 509.0 * x +
                 714.4)
    return value


class TestApi(LiveServerTestCase):
    """Tests of geonode-safe API
    """

    fixtures = ['sample_admin.json']

    def setUp(self):
        """Create valid superuser
        """
        check_geonode_is_up()
        self.user = get_valid_user()

    def test_the_earthquake_fatality_estimation_allen(self):
        """Fatality computation computed correctly with GeoServer Data
        """

        # Simulate bounding box from application
        viewport_bbox_string = '104.3,-8.2,110.04,-5.17'

        # Upload exposure data for this test
        name = 'Population_2010'
        exposure_filename = '%s/%s.asc' % (TESTDATA, name)
        exposure_layer = save_to_geonode(exposure_filename,
                                         user=self.user, overwrite=True)

        workspace = exposure_layer.workspace

        layer_name = exposure_layer.name
        msg = 'Expected layer name to be "%s". Got %s' % (name, layer_name)
        assert layer_name == name.lower(), msg

        exposure_name = '%s:%s' % (workspace, layer_name)

        # Check metadata
        assert_bounding_box_matches(exposure_layer, exposure_filename)
        exp_bbox_string = get_bounding_box_string(exposure_filename)
        check_layer(exposure_layer, full=True)

        # Now we know that exposure layer is good, lets upload some
        # hazard layers and do the calculations
        filename = 'lembang_mmi_hazmap.asc'

        # Save
        hazard_filename = '%s/%s' % (TESTDATA, filename)
        hazard_layer = save_to_geonode(hazard_filename,
                                       user=self.user, overwrite=True)
        hazard_name = '%s:%s' % (hazard_layer.workspace,
                                 hazard_layer.name)

        # Check metadata
        assert_bounding_box_matches(hazard_layer, hazard_filename)
        haz_bbox_string = get_bounding_box_string(hazard_filename)
        check_layer(hazard_layer, full=True)

        calculate_url = reverse('safe-calculate')

        # Run calculation
        c = Client()
        rv = c.post(calculate_url, data=dict(
                hazard_server=INTERNAL_SERVER_URL,
                hazard=hazard_name,
                exposure_server=INTERNAL_SERVER_URL,
                exposure=exposure_name,
                #bbox=viewport_bbox_string,
                bbox=exp_bbox_string,  # This one reproduced the
                                       # crash for lembang
                impact_function='I T B Fatality Function',
                keywords='test,shakemap,usgs'))

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv['Content-Type'], 'application/json')
        data = json.loads(rv.content)
        if 'errors' in data:
            errors = data['errors']
            if errors is not None:
                msg = ('The server returned the error message: %s'
                       % str(errors))
                raise Exception(msg)

        assert 'success' in data
        assert 'hazard_layer' in data
        assert 'exposure_layer' in data
        assert 'run_duration' in data
        assert 'run_date' in data
        assert 'layer' in data

        assert data['success']

        # Download result and check
        layer = data['layer']
        layer_id = layer['id']

        result_layer = download(INTERNAL_SERVER_URL,
                                layer_id,
                                get_bounding_box_string(hazard_filename))
        assert os.path.exists(result_layer.filename)


    def test_jakarta_flood_study(self):
        """HKV Jakarta flood study calculated correctly using the API
        """

        # FIXME (Ole): Redo with population as shapefile later

        # Expected values from HKV
        expected_value = 1537920

        # Name files for hazard level, exposure and expected fatalities
        population = 'Population_Jakarta_geographic'
        plugin_name = 'Flood Evacuation Function'

        # Upload exposure data for this test
        exposure_filename = '%s/%s.asc' % (TESTDATA, population)
        exposure_layer = save_to_geonode(exposure_filename,
                                         user=self.user, overwrite=True)

        workspace = exposure_layer.workspace

        exposure_name = '%s:%s' % (workspace, exposure_layer.name)

        # Check metadata
        assert_bounding_box_matches(exposure_layer, exposure_filename)
        exp_bbox_string = get_bounding_box_string(exposure_filename)
        check_layer(exposure_layer, full=True)

        # Now we know that exposure layer is good, lets upload some
        # hazard layers and do the calculations

        filename = 'jakarta_flood_design.tif'

        hazard_filename = os.path.join(UNITDATA, 'hazard', filename)
        exposure_filename = os.path.join(TESTDATA, population)

        # Save
        hazard_layer = save_to_geonode(hazard_filename,
                                       user=self.user, overwrite=True)
        hazard_name = '%s:%s' % (hazard_layer.workspace,
                                 hazard_layer.name)

        # Check metadata
        assert_bounding_box_matches(hazard_layer, hazard_filename)
        haz_bbox_string = get_bounding_box_string(hazard_filename)
        check_layer(hazard_layer, full=True)

        calculate_url = reverse('safe-calculate')

        # Run calculation
        c = Client()
        rv = c.post(calculate_url, data=dict(
                hazard_server=INTERNAL_SERVER_URL,
                hazard=hazard_name,
                exposure_server=INTERNAL_SERVER_URL,
                exposure=exposure_name,
                bbox=exp_bbox_string,
                impact_function=plugin_name,
                keywords='test,flood,HKV'))

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv['Content-Type'], 'application/json')
        data = json.loads(rv.content)
        if 'errors' in data:
            errors = data['errors']
            if errors is not None:
                raise Exception(errors)

        assert 'hazard_layer' in data
        assert 'exposure_layer' in data
        assert 'run_duration' in data
        assert 'run_date' in data
        assert 'layer' in data


    def test_exceptions_in_calculate_endpoint(self):
        """Wrong bbox input is handled nicely by /safe/api/calculate/
        """

        # Upload input data
        hazardfile = os.path.join(TESTDATA, 'lembang_mmi_hazmap.asc')
        hazard_layer = save_to_geonode(hazardfile, user=self.user)
        hazard_name = '%s:%s' % (hazard_layer.workspace, hazard_layer.name)

        exposurefile = os.path.join(UNITDATA, 'exposure', 'buildings_osm_4326.shp')
        exposure_layer = save_to_geonode(exposurefile, user=self.user)
        exposure_name = '%s:%s' % (exposure_layer.workspace,
                                   exposure_layer.name)

        bbox_correct = '105.592,-7.809,110.159,-5.647'
        bbox_with_spaces = '105.592, -7.809, 110.159, -5.647'
        bbox_non_numeric = '105.592,-7.809,x,-5.647'
        bbox_list = [1, 2, 3, 4]
        bbox_list_non_numeric = [1, '2', 3, 4]
        bbox_none = None
        bbox_wrong_number1 = '105.592,-7.809,-5.647'
        bbox_wrong_number2 = '105.592,-7.809,-5.647,34,123'
        bbox_empty = ''
        bbox_inconsistent1 = '110,-7.809,105,-5.647'
        bbox_inconsistent2 = '105.592,-5,110.159,-7'
        bbox_out_of_bound1 = '-185.592,-7.809,110.159,-5.647'
        bbox_out_of_bound2 = '105.592,-97.809,110.159,-5.647'
        bbox_out_of_bound3 = '105.592,-7.809,189.159,-5.647'
        bbox_out_of_bound4 = '105.592,-7.809,110.159,-105.647'

        data = dict(hazard_server=INTERNAL_SERVER_URL,
                    hazard=hazard_name,
                    exposure_server=INTERNAL_SERVER_URL,
                    exposure=exposure_name,
                    bbox=bbox_correct,
                    impact_function='Earthquake Building Damage Function',
                    keywords='test,schools,lembang')


        calculate_url = reverse('safe-calculate')

        # First do it correctly (twice)
        c = Client()
        rv = c.post(calculate_url, data=data)
        rv = c.post(calculate_url, data=data)

        # Then check that spaces are dealt with correctly
        data['bbox'] = bbox_with_spaces
        rv = c.post(calculate_url, data=data)

        # Then with a range of wrong bbox inputs
        for bad_bbox in [bbox_list,
                         bbox_none,
                         bbox_empty,
                         bbox_non_numeric,
                         bbox_list_non_numeric,
                         bbox_wrong_number1,
                         bbox_wrong_number2,
                         bbox_inconsistent1,
                         bbox_inconsistent2,
                         bbox_out_of_bound1,
                         bbox_out_of_bound2,
                         bbox_out_of_bound3,
                         bbox_out_of_bound4]:

            # Use erroneous bounding box
            data['bbox'] = bad_bbox

            # FIXME (Ole): Suppress error output from c.post
            rv = c.post(calculate_url, data=data)
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv['Content-Type'], 'application/json')
            data_out = json.loads(rv.content)

            msg = ('Bad bounding box %s should have raised '
                       'an error' % bad_bbox)
            assert 'errors' in data_out, msg

    @numpy.testing.dec.skipif(True, ' * Talk to Ole. Intergrid interpolation not yet implemented')
    def test_earthquake_exposure_plugin(self):
        """Population exposure to individual MMI levels can be computed
        """

        # Upload exposure data for this test
        # FIXME (Ole): While this dataset is ok for testing,
        # note that is has been resampled without scaling
        # so numbers are about 25 times too large.
        # Consider replacing test populations dataset for good measures,
        # just in case any one accidentally started using this dataset
        # for real.

        name = 'Population_2010'
        exposure_filename = '%s/%s.asc' % (TESTDATA, name)
        exposure_layer = save_to_geonode(exposure_filename,
                                         user=self.user, overwrite=True)
        exposure_name = '%s:%s' % (exposure_layer.workspace,
                                   exposure_layer.name)

        # Check metadata
        assert_bounding_box_matches(exposure_layer, exposure_filename)
        exp_bbox_string = get_bounding_box_string(exposure_filename)
        check_layer(exposure_layer, full=True)

        # Upload hazard data
        filename = 'lembang_mmi_hazmap.asc'
        hazard_filename = '%s/%s' % (TESTDATA, filename)
        hazard_layer = save_to_geonode(hazard_filename,
                                       user=self.user, overwrite=True)
        hazard_name = '%s:%s' % (hazard_layer.workspace,
                                 hazard_layer.name)

        # Check metadata
        assert_bounding_box_matches(hazard_layer, hazard_filename)
        haz_bbox_string = get_bounding_box_string(hazard_filename)
        check_layer(hazard_layer, full=True)

        calculate_url = reverse('safe-calculate')

        # Run calculation
        c = Client()
        rv = c.post(calculate_url, data=dict(
                hazard_server=INTERNAL_SERVER_URL,
                hazard=hazard_name,
                exposure_server=INTERNAL_SERVER_URL,
                exposure=exposure_name,
                bbox=haz_bbox_string,
                impact_function='Earthquake Building Damage Function',
                keywords='test,population,exposure,usgs'))

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv['Content-Type'], 'application/json')
        data = json.loads(rv.content)
        if 'errors' in data:
            errors = data['errors']
            if errors is not None:
                msg = ('The server returned the error message: %s'
                       % str(errors))
                raise Exception(msg)

        assert 'success' in data
        assert 'hazard_layer' in data
        assert 'exposure_layer' in data
        assert 'run_duration' in data
        assert 'run_date' in data
        assert 'layer' in data

        assert data['success']

        # Download result and check
        layer_name = data['layer'].split('/')[-1]

        result_layer = download(INTERNAL_SERVER_URL,
                                layer_name,
                                get_bounding_box_string(hazard_filename))
        assert os.path.exists(result_layer.filename)

        # Check calculated values
        keywords = result_layer.get_keywords()

        assert 'mmi-classes' in keywords
        assert 'affected-population' in keywords

        mmi_classes = [int(x) for x in keywords['mmi-classes'].split('_')]
        count = [float(x) for x in keywords['affected-population'].split('_')]

        # Brute force count for each population level
        population = download(INTERNAL_SERVER_URL,
                              exposure_name,
                              get_bounding_box_string(hazard_filename))
        intensity = download(INTERNAL_SERVER_URL,
                             hazard_name,
                             get_bounding_box_string(hazard_filename))

        # Extract data
        H = intensity.get_data(nan=0)
        P = population.get_data(nan=0)

        brutecount = {}
        for mmi in mmi_classes:
            brutecount[mmi] = 0

        for i in range(P.shape[0]):
            for j in range(P.shape[1]):
                mmi = H[i, j]
                if not numpy.isnan(mmi):
                    mmi_class = int(round(mmi))

                    pop = P[i, j]
                    if not numpy.isnan(pop):
                        brutecount[mmi_class] += pop

        for i, mmi in enumerate(mmi_classes):
            assert numpy.allclose(count[i], brutecount[mmi], rtol=1.0e-6)


    def test_functions(self):
        """Functions can be retrieved from the HTTP Rest API
        """

        c = Client()
        functions_url = reverse('safe-questions')
        rv = c.get(functions_url)
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv['Content-Type'], 'application/json')
        data = json.loads(rv.content)

        msg = ('The api should return a dictionary with at least one item. '
               'The key of that item should be "functions"')
        assert 'functions' in data, msg
        functions = data['functions']

        assert 'layers' in data
        assert 'questions' in data

        msg = ('No functions were found in the functions list, '
               'not even the built-in ones')
        assert len(functions) > 0, msg


    def test_plugin_selection(self):
        """Verify the plugins can recognize compatible layers.
        """
        exposure =[
                 'topp:buildings_osm_4326',
                 {'layertype': 'vector',
                  'category': 'exposure',
                  'subcategory': 'structure',
                  'title': 'buildings_osm_4326',
                  'datatype': 'osm',
                  'purpose': 'dki'
                 }
               ]
        hazard = [
                 'topp:jakarta_flood_like_2007_with_structural_improvements',
                  {'layertype': 'raster',
                   'category': 'hazard',
                   'subcategory': 'flood',
                   'title': 'Jakarta flood like 2007 with structural improvements',
                   'resolution': '0.00045228819716',
                   'unit': 'm'
                   }
               ]
        layers = [exposure, hazard]

        exposure_name, exposure_params = exposure
        hazard_name, hazard_params = hazard

        requirements = requirements_collect(FloodBuildingImpactFunction)

        exposure_compatible = requirements_met(requirements, exposure_params)
        assert exposure_compatible

        hazard_compatible = requirements_met(requirements, hazard_params)
        assert hazard_compatible


    def test_plugin_selection_http(self):
        """Verify the plugins can recognize compatible layers (HTTP).
        """

        # Upload a raster and a vector data set
        hazard_filename = os.path.join(UNITDATA, 'hazard',
                                       'jakarta_flood_design.tif')
        hazard_layer = save_to_geonode(hazard_filename,
                                       user=self.user,
                                       overwrite=True)
        check_layer(hazard_layer, full=True)

        msg = 'No keywords found in layer %s' % hazard_layer.name
        assert hazard_layer.keywords.count() > 0, msg

        exposure_filename = os.path.join(UNITDATA, 'exposure',
                                         'buildings_osm_4326.shp')
        exposure_layer = save_to_geonode(exposure_filename)
        check_layer(exposure_layer, full=True)

        msg = 'No keywords found in layer %s' % exposure_layer.name
        assert exposure_layer.keywords.count() > 0, msg

        # make sure the keywords for the flood building impact
        # function are present.
        hazard_keywords = [k.name for k in hazard_layer.keywords.all()]
        exposure_keywords = [k.name for k in exposure_layer.keywords.all()]

        assert 'category:hazard' in hazard_keywords
        assert 'subcategory:flood' in hazard_keywords

        assert 'category:exposure' in exposure_keywords
        assert 'subcategory:structure' in exposure_keywords

        c = Client()
        functions_url = reverse('safe-questions')
        rv = c.get(functions_url)

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv['Content-Type'], 'application/json')
        data = json.loads(rv.content)

        assert 'questions' in data

        questions = data['questions']
        found_it = False
        function_name = 'Flood Building Impact Function'

        for question in questions:
            function = question['function']
            hazard = question['hazard']
            exposure = question['exposure']

            if function == function_name:
                if hazard == hazard_layer.typename:
                    if exposure == exposure_layer.typename:
                        found_it = True

        msg = ('Expected to find %s, %s and %s in questions: %s' % (
            hazard_layer.typename, exposure_layer.typename,
            function_name, questions))
        assert found_it, msg
