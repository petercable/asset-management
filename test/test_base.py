import fnmatch
import logging
import os
import unittest
from numbers import Number

import numpy as np
import pandas as pd
from datetime import datetime
from dateutil import parser
from nose.plugins.attrib import attr

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


class FileNameException(Exception):
    pass


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
        cls.bulk_data = pd.read_csv(cls.BULK_FILE, names=cls.BULK_COLS,
                                        skiprows=1, na_values='', keep_default_na=False)

    @staticmethod
    def valid_float(value):
        return isinstance(value, Number) and not np.isnan(value)

    @staticmethod
    def valid_time_format(timestamp):
        return timestamp == parser.parse(timestamp).isoformat()

    @staticmethod
    def isnan(val):
        return isinstance(val, Number) and np.isnan(val)

    @staticmethod
    def date_to_millis(date):
        try:
            if isinstance(date, float):
                date = str(int(date))
            dt = parser.parse(date)
            secs = (dt - datetime(1970, 1, 1)).total_seconds()
            return int(secs * 1000)

        except ValueError:
            return None

    @staticmethod
    def maybe_float(data):
        try:
            return float(data)
        except ValueError:
            return data

    @staticmethod
    def parse_cal_file(filepath):
        return pd.read_csv(filepath)

    @staticmethod
    def parse_dep_file(filepath):
        df = pd.read_csv(filepath)
        df = df.fillna({'orbit': 0.0, 'depth': 0.0})
        df['startDateTime'] = map(AssetManagementUnitTest.date_to_millis, df.startDateTime.values)
        df['stopDateTime'] = map(AssetManagementUnitTest.date_to_millis, df.stopDateTime.values)
        return df

    @staticmethod
    def _walk_files(root):
        for path, dirs, files in os.walk(root):
            for name in fnmatch.filter(files, '*.csv'):
                yield os.path.join(path, name)

    def walk_cal_files(self):
        return self._walk_files(self.CAL_ROOT)

    def walk_deployment_files(self):
        return self._walk_files(self.DEP_ROOT)

    @staticmethod
    def parse_cal_filename(filename):
        try:
            return os.path.basename(filename).replace('.csv', '').split("__")
        except Exception as e:
            log.exception('Exception parsing calibration filename')
            raise FileNameException(e.message)