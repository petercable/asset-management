import fnmatch
import json
import os
from numbers import Number

import pandas
import logging
import unittest

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


class AssetManagementTest(unittest.TestCase):
    def setUp(self):
        """
        Read bulk load asset management data and save UID and serial numbers
        :return:
        """
        fn = '../bulk/bulk_load-AssetRecord.csv'
        self.data = pandas.read_csv(fn)
        self.ids = {}  # dictionary of all the UIDs and corresponding serial numbers
        for _, record in self.data.iterrows():
            uid = str(record.ASSET_UID)
            sn = str(record["Manufacturer's Serial No./Other Identifier"])
            self.ids[uid] = sn

    def check_cal_file(self, fn):
        """
        Check a single calibration file for format and consistency
        :param fn:  calibration filename
        :return:  list of errors (if any)
        """
        errors = []
        cal_data = pandas.read_csv(fn)
        parts = os.path.basename(fn).split("_")
        if len(parts) < 2:
            errors.append('Invalid calibration filename (%s) - expected "_" after UID' % fn)
            log.error('Invalid calibration filename')
            return errors
        uid = parts[0]

        if uid not in self.ids:
            errors.append('UID (%s) does not exist' % uid)
            return errors

        for record in cal_data.itertuples(index=False):
            try:
                sn = str(record.serial)
                if sn != self.ids[uid]:
                    errors.append('Serial Number mismatch for %s (%s != %s)' % (uid, sn, self.ids[uid]))

                if not self.check_value(record.value):
                    errors.append('Value %r is not valid JSON' % record.value)
            except AttributeError as e:
                errors.append('Calibration file is missing required fields: %s' % e)
                break  # do not process the rest of the file
        return errors

    def test_cal(self):
        """
        Cycle through all available calibration files and check
        """
        error_count = 0
        cal_root = '../calibration'
        for root, dirs, files in os.walk(cal_root, topdown=False):
            for name in fnmatch.filter(files, '*.csv'):
                filename = os.path.join(root, name)
                log.debug('Parsing %s', filename)
                errors = self.check_cal_file(filename)
                if errors:
                    log.error('%s: Error processing calibration file:', filename)
                    for error in errors:
                        log.error('    %s', error)
                    error_count += len(errors)
                else:
                    log.debug('%s: success', filename)
                # break  # TODO - remove - just one file to start
            # break  # TODO - remove - just one file to start
        self.assertEqual(error_count, 0, '%s errors encountered processing calibration files' % error_count)

    @staticmethod
    def check_value(value):
        """
        Check a single calibration value for validity
        :param value:  must be a number, SheetRef, or valid JSON
        :return:  True if valid
        """
        if isinstance(value, Number):
            return True

        if isinstance(value, basestring):
            if 'SheetRef:' in value:
                return True
            try:
                json.loads(value)
            except ValueError:
                return False
            return True
        return False

