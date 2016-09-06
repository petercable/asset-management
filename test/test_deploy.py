import fnmatch
import logging
import os
import unittest

import numpy
import pandas

from dateutil import parser
from numbers import Number

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

required_ids = {
    'Reference Designator',
    'deploymentNumber',
    'startDateTime',
    'mooring.uid',
    'sensor.uid',
    'lat',
    'lon',
    'depth'
}

optional_ids = {
    'CUID_Deploy',
    'deployedBy',
    'CUID_Recover',
    'recoveredBy',
    'versionNumber',
    'stopDateTime',
    'node.uid',  # only required for profilers
    'orbit'
}

time_format_example = '2014-04-17T20:53:00'
time_format = 'YYYY-MM-DDThh:mm:ss'


def isnan(value):
    return isinstance(value, float) and numpy.isnan(value)


def valid_float(value):
    return isinstance(value, Number) and not numpy.isnan(value)


def valid_time_format(timestamp):
    if timestamp == parser.parse(timestamp).isoformat():
        return True
    return False


def value_set(value):
    return numpy.isnan(value)


class AssetManagementTest(unittest.TestCase):
    def setUp(self):
        """
        Read bulk load asset management data and save UID and serial numbers
        """
        fn = '../bulk/bulk_load-AssetRecord.csv'
        self.data = pandas.read_csv(fn).fillna('')
        self.ids = {}  # dictionary of all the UIDs and corresponding serial numbers
        for _, record in self.data.iterrows():
            uid = str(record.ASSET_UID)
            ttype = str(record["TYPE"])
            self.ids[uid] = ttype

        self.asset_map = {
            'mooring.uid': 'Platform',
            'sensor.uid': 'Sensor',
            'node.uid': 'Node'
        }

    def check_type_match(self, record, asset_key):
        """
        verify UIDs exist and match type
        :param record:
        :param asset_key:  one of the three asset record headings (mooring.uid, sensor.uid, node.uid)
        :return:  list of errors (if any)
        """
        if asset_key not in self.asset_map.keys():
            return 'Unexpected asset type provided (%s not one of %r)' % (asset_key, self.asset_map.keys())

        # make sure the asset has a UID loaded from bulk load
        asset_type = self.asset_map[asset_key]
        asset = str(record[asset_key])

        # nodes are optional, skip check if not present
        if asset_key == 'node.uid' and not asset:
            return

        if asset not in self.ids:
            return 'Missing UID for %s %s' % (asset_type, asset)

        if self.ids[asset] != asset_type:
            return 'Type mismatch for %s - expected "%s", found "%s"' % (asset_key, asset_type, self.ids[asset])

    def check_deploy_file(self, fn):
        """
        Check a single deployment file for format and consistency
        :param fn:  deployment filename
        :return:  list of errors (if any)
        """
        errors = []
        deployment = pandas.read_csv(fn).fillna('')

        # make sure all fields are present
        missing = required_ids.union(optional_ids) - set(deployment.columns)
        if missing:
            errors.append('Missing required column identifiers: %s' % missing)
            return errors

        # check types for Platform and Sensor
        for index, record in deployment.iterrows():
            try:
                # make sure all required fields are filled out
                set_fields = {name for name in record.index if getattr(record, name)}
                missing = required_ids - set_fields
                if missing:
                    errors.append('Missing value(s) for required fields: %s on row %d - %r' % (missing, index, record))
                    return errors

                # check asset types for matching UID records
                for asset_type in self.asset_map.keys():
                    error = self.check_type_match(record, asset_type)
                    if error:
                        errors.append(error + ' - row %d' % index)

                # start and stop (if present) must have correct format
                start_time = record['startDateTime']
                if start_time and not valid_time_format(start_time):
                    errors.append('Invalid time format for startDateTime - "%r" - row %d' % (start_time, index))

                stop_time = record['stopDateTime']
                if stop_time and not valid_time_format(stop_time):
                    errors.append('Invalid time format for stopDateTime - "%r" - row %d' % (stop_time, index))

                lat = record['lat']
                if not valid_float(lat):
                    errors.append('Invalid format for latitude - "%r" - row %d' % (lat, index))

                lon = record['lon']
                if not valid_float(lon):
                    errors.append('Invalid format for longitude - "%r" - row %d' % (lon, index))

                depth = record['depth']
                if not valid_float(depth):
                    errors.append('Invalid format for depth - "%r" - row %d' % (depth, index))

            except AttributeError as e:
                errors.append('Deployment file is missing required fields: %s - row %d' % (e, index))
                break  # do not process the rest of the file

        return errors

    def test_deploy(self):
        """
        Cycle through all available deployment files and check
        """
        error_count = 0
        deploy_root = '../deployment'
        for root, dirs, files in os.walk(deploy_root, topdown=False):
            for name in fnmatch.filter(files, '*.csv'):
                filename = os.path.join(root, name)
                log.debug('Parsing %s', filename)
                errors = self.check_deploy_file(filename)
                if errors:
                    log.error('%s: %d error%s processing deployment file:', filename, len(errors),
                              '' if len(errors) == 1 else 's')
                    for error in errors:
                        log.error('    %s', error)
                    error_count += len(errors)
                else:
                    log.debug('%s: success', filename)
        self.assertEqual(error_count, 0, '%s errors encountered processing deployment files' % error_count)

