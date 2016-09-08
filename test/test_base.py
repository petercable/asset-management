import logging
import os
import unittest
from numbers import Number

import numpy
import pandas
from dateutil import parser
from nose.plugins.attrib import attr

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


@attr('UNIT')
class AssetManagementUnitTest(unittest.TestCase):
    TEST_ROOT = os.path.dirname(__file__)
    AM_ROOT = os.path.abspath(os.path.join(TEST_ROOT, '..'))
    BULK_ROOT = os.path.join(AM_ROOT, 'bulk')
    CAL_ROOT = os.path.join(AM_ROOT, 'calibration')
    DEP_ROOT = os.path.join(AM_ROOT, 'deployment')
    BULK_FILE = os.path.join(BULK_ROOT, 'bulk_load-AssetRecord.csv')

    BULK_COLS = [
        'uid',
        'assetType',
        'mobile',
        'description',
        'manufacturer',
        'modelNumber',
        'serialNumber',
        'firmwareVersion',
        'purchaseDate',
        'purchasePrice',
        'notes'
    ]

    @classmethod
    def setUpClass(cls):
        """
        Read bulk load asset management data and save UID and serial numbers
        :return:
        """
        cls.bulk_data = pandas.read_csv(cls.BULK_FILE, names=cls.BULK_COLS,
                                        skiprows=1, na_values='', keep_default_na=False)

    @staticmethod
    def valid_float(value):
        return isinstance(value, Number) and not numpy.isnan(value)

    @staticmethod
    def valid_time_format(timestamp):
        return timestamp == parser.parse(timestamp).isoformat()
