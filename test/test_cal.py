import fnmatch
import json
import os

import pandas
import logging
import unittest

from dateutil import parser

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


TEST_ROOT = os.path.dirname(__file__)
AM_ROOT = os.path.abspath(os.path.join(TEST_ROOT, '..'))
BULK_ROOT = os.path.join(AM_ROOT, 'bulk')
CAL_ROOT = os.path.join(AM_ROOT, 'calibration')
BULK_FILE = os.path.join(BULK_ROOT, 'bulk_load-AssetRecord.csv')


class AssetManagementTest(unittest.TestCase):
    def setUp(self):
        """
        Read bulk load asset management data and save UID and serial numbers
        :return:
        """
        self.data = pandas.read_csv(BULK_FILE)
        self.ids = {}  # dictionary of all the UIDs and corresponding serial numbers
        for _, record in self.data.iterrows():
            uid = str(record.ASSET_UID)
            sn = str(record["Manufacturer's Serial No./Other Identifier"])
            self.ids[uid] = sn

    @staticmethod
    def walk_cal_files():
        for path, dirs, files in os.walk(CAL_ROOT):
            for name in fnmatch.filter(files, '*.csv'):
                yield os.path.join(path, name)

    @staticmethod
    def parse_cal_file(filepath):
        return pandas.read_csv(filepath)

    @staticmethod
    def parse_filename(filename):
        return os.path.basename(filename).replace('.csv', '').split("__")

    def check_filename(self, filename):
        errors = []

        try:
            uid, timestamp = self.parse_filename(filename)
        except:
            return ['Invalid calibration filename (%s)' % filename]

        if uid not in self.ids:
            errors.append('UID (%s) does not exist' % filename)

        try:
            dt = parser.parse(timestamp)
            if not timestamp == dt.date().isoformat().replace('-', ''):
                errors.append('Invalid timestamp (%s)' % filename)
        except ValueError:
            errors.append('Invalid timestamp (%s)' % filename)

        return errors

    def check_serial(self, filename):
        errors = []
        try:
            uid, _ = self.parse_filename(filename)
        except:
            return ['Unable to parse file (%s)' % filename]

        df = self.parse_cal_file(filename)
        serials = df.serial.values.astype('str')
        serials_set = set(serials)
        if len(serials_set) != 1:
            errors.append('Multiple serial numbers found (%s)' % filename)

        expected_serial = self.ids.get(uid)

        for serial in serials_set:
            if serial != expected_serial:
                errors.append('Serial does not match bulk load CAL(%r) != BULK(%r) (%s)' %
                              (serial, expected_serial, filename))

        return errors

    @staticmethod
    def check_sheetref(filename, value):
        name = value.replace('SheetRef:', '')
        sheetref_name = filename.replace('.csv', '__%s.ext' % name)
        if not os.path.exists(sheetref_name):
            return ['Cannot find sheetref (%s) (%s)' % (filename, value)]

        pandas.read_csv(sheetref_name, header=None).as_matrix()
        return []

    def check_values(self, filename):
        errors = []
        try:
            uid, _ = self.parse_filename(filename)
        except:
            return ['Unable to parse file (%s)' % filename]

        df = self.parse_cal_file(filename)
        values = df.value.values.astype('str')

        for value in values:
            if value.startswith('SheetRef:'):
                errors.extend(self.check_sheetref(filename, value))

            else:
                try:
                    json.loads(value)
                except ValueError:
                    errors.append('Invalid JSON value (%s) (%r)' % (filename, value))

        return errors

    def assert_errors(self, errors):
        for error in errors:
            log.error(error)
        self.assertEqual(errors, [])

    def test_filename(self):
        errors = []
        for filepath in self.walk_cal_files():
            errors.extend(self.check_filename(filepath))

        self.assert_errors(errors)

    def test_serial(self):
        errors = []
        for filepath in self.walk_cal_files():
            errors.extend(self.check_serial(filepath))

        self.assert_errors(errors)

    def test_values(self):
        errors = []
        for filepath in self.walk_cal_files():
            errors.extend(self.check_values(filepath))

        self.assert_errors(errors)

    def test_class_variables(self):
        klass_dict = {}
        for filepath in self.walk_cal_files():
            inst_klass = os.path.basename(os.path.dirname(filepath))
            names = self.parse_cal_file(filepath).name.values
            klass_dict.setdefault(inst_klass, []).append((filepath, names))

        errors = []
        for klass in klass_dict:
            name_set = None
            for filepath, names in klass_dict[klass]:
                if name_set is None:
                    name_set = set(names)
                else:
                    diff = name_set.difference(names)
                    if diff:
                        errors.append('Inconsistent set of parameters for instrument class %s %s %s' %
                                      (klass, diff, filepath))

        self.assert_errors(errors)
