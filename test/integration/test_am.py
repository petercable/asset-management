import csv
import json
import logging
import os
import time
import unittest
from bisect import bisect
from collections import OrderedDict
from datetime import datetime
from glob import glob
from numbers import Number

import javaobj
import numpy as np
import pandas as pd
import psycopg2
import requests
from dateutil import parser
from xlrd import XLRDError

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


TEST_ROOT = os.path.dirname(__file__)
AM_ROOT = os.path.abspath(os.path.join(TEST_ROOT, '..'))
BULK_ROOT = os.path.join(AM_ROOT, 'bulk')
CAL_ROOT = os.path.join(AM_ROOT, 'calibration')
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


class AssetManagementTest(unittest.TestCase):
    def setUp(self):
        self.amhost = 'localhost'
        self.refdes = 'CE04OSPS-SF01B-2A-CTDPFA107'
        self.conn = psycopg2.connect(host='localhost', database='metadata', user='awips')
        self.maxDiff = None

    @staticmethod
    def isnan(val):
        return isinstance(val, Number) and np.isnan(val)

    @staticmethod
    def date_to_millis(date):
        try:
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

    def ordered_bulk_entry(self, data):
        out = OrderedDict()
        for k in BULK_COLS:
            v = data.get(k)
            if isinstance(v, unicode):
                v = str(v)
            elif v is None:
                v = ''
            elif self.isnan(v):
                v = ''
            if k == 'assetType' and v == 'Platform':
                v = 'Mooring'
            out[k] = v
        return out

    def assert_bulk_entry(self, row):
        # retrieve the asset
        asset = requests.get('http://localhost:12587/asset', params={'uid': row['uid']}).json()
        asset_map = self.ordered_bulk_entry(asset)
        row_map = self.ordered_bulk_entry(row)

        print 'AM  :', asset_map
        print 'BULK:', row_map
        print
        self.assertDictEqual(asset_map, row_map)

    def test_bulk_load(self):
        df = pd.read_csv(BULK_FILE, names=BULK_COLS, skiprows=1, na_values='', keep_default_na=False)
        df.fillna({'mobile': 0, 'assetType': 'notClassified'}, inplace=True)
        df['mobile'] = df.mobile.values.astype(bool)
        df['purchaseDate'] = map(self.date_to_millis, df.purchaseDate.values)
        df['purchasePrice'] = map(self.maybe_float, df.purchasePrice.values)
        for _, row in df.iterrows():
            print row.to_dict()
            self.assert_bulk_entry(row.to_dict())

    def assert_cal_times(self, calibrations, asset, dstart, dstop):
        if not calibrations:
            return

        # verify that one of the calibrations is valid for this deployment
        cal_dict = {}
        for cal in calibrations:
            name = cal['name']
            # print name, len(cal['calData'])
            for each in cal['calData']:
                cstart = each['eventStartTime']

                cal_asset = each['assetUid']
                self.assertEqual(asset, cal_asset)
                # print name, cal_asset, cstart
                cal_dict.setdefault(name, []).append(cstart)

        # assert that there are an equal number of cals for each deployment
        lengths = {len(x) for x in cal_dict.values()}
        if len(lengths) != 1:
            print 'missing cal values? asset: %s cals: %s' % (asset, cal_dict)
        # self.assertEqual(len(lengths), 1, msg='missing cal values? asset: %s cals: %s' % (asset, cal_dict))
        import pprint
        pprint.pprint(cal_dict)

    def assert_events(self, events):
        self.assertEqual(len(events), 1)
        now = time.time() * 1000
        deployment = events[0]
        dstart = deployment['eventStartTime']
        dstop = deployment['eventStopTime']
        sensor = deployment['sensor']
        asset = sensor['uid']
        calibrations = sensor['calibration']
        if not dstop:
            dstop = now

        self.assert_cal_times(calibrations, asset, dstart, dstop)

    def test_all_cals(self):
        import requests
        base_url = 'http://localhost:12587/events/deployment/inv'
        subsites = requests.get(base_url).json()
        for subsite in subsites:
            nodes = requests.get('%s/%s' % (base_url, subsite)).json()
            for node in nodes:
                sensors = requests.get('%s/%s/%s' % (base_url, subsite, node)).json()
                for sensor in sensors:
                    deployments = requests.get('%s/%s/%s/%s' % (base_url, subsite, node, sensor)).json()
                    for deployment in deployments:
                        events = requests.get('%s/%s/%s/%s/%d' % (base_url, subsite, node, sensor, deployment)).json()
                        print subsite, node, sensor, deployment
                        self.assert_events(events)
            break
            # print subsite, node, sensor, deployment, events
        assert subsites is False

    def make_array(self, dimensions, values):
        if dimensions == [1] and len(values) == 1:
            return values[0]

        a = np.array(values)
        return list(np.reshape(a, dimensions))

    def assert_cal_value(self, refdes, depnum, uid, start, name, value, adj_time=False):
        # print repr(uid), start, repr(name), repr(value)
        cur = self.conn.cursor()
        never = False

        if adj_time:
            cur.execute('''
            select eventstarttime/1000
                from xasset xa, xdeployment xd, xevent xe
                where xa.assetid=xd.sassetid and xd.eventid=xe.eventid and xa.uid=%s and eventstarttime >= %s
                order by eventstarttime limit 1''', (uid, start * 1000))
            row = cur.fetchone()
            if row:
                start = row[0]
            else:
                never = True

        cur.execute(
            'select name, dimensions, values, eventstarttime from xcalibration xc, xcalibrationdata xcd, xevent xe where xc.calid = xcd.calid and xe.eventid = xcd.eventid and assetuid=%s and name=%s',
            (uid, name))
        rows = cur.fetchall()
        values = []
        for name, dims, vals, t in rows:
            try:
                if dims is not None and vals is not None:
                    dims = javaobj.loads(dims)
                    vals = javaobj.loads(vals)
                    a = self.make_array(dims, vals)
                    t /= 1000.0
                    values.append((t, a))
            except IOError:
                print name, repr(dims), repr(vals)

        rvalues = [datetime.utcfromtimestamp(x).isoformat() for x, y in values]

        if not values and never:
            rval = 'neverdeployed', refdes, depnum, name, uid, start, datetime.utcfromtimestamp(
                start).isoformat(), str(value)[:20], rvalues
            print rval
            return rval

        if not values:
            rval = 'missing', refdes, depnum, name, uid, start, datetime.utcfromtimestamp(start).isoformat(), str(value)[:20], rvalues
            print rval
            return rval

        values.sort()
        times = [v[0] for v in values]
        index = bisect(times, start)

        if index <= 0:
            rval = 'notfound', refdes, depnum, name, uid, start, datetime.utcfromtimestamp(start).isoformat(), str(value)[:20], rvalues
            print rval
            return rval

        t, expected = values[index - 1]
        try:
            np.testing.assert_array_almost_equal(expected, value)
        except AssertionError:
            rval = 'mismatch', refdes, depnum, name, uid, start, datetime.utcfromtimestamp(start).isoformat(), str(value)[:20], rvalues
            print rval
            return rval

    def test_new_spreadsheets(self):
        import pandas as pd
        unix_epoch = datetime(1970, 1, 1)
        results = []
        for filename in glob('/Users/petercable/src/asset-management/ARCHIVE/refactored_asset_management/Calibration/*xlsx'):
            print filename
            sheets = pd.read_excel(filename, sheetname=None)
            cal_sheets = [sheet for sheet in sheets if 'Cal_Info' in sheet]
            for sheet in cal_sheets:
                df = sheets[sheet]
                try:
                    df = df[
                        ['Sensor.uid', 'startDateTime', 'Calibration Cofficient Name', 'Calibration Cofficient Value']]
                    df = df.dropna(how='all')
                    for each in df.itertuples(index=False):
                        uid, start, name, value = each
                        if (isinstance(uid, float) and np.isnan(uid) or
                                    isinstance(name, float) and np.isnan(name) or
                                    isinstance(value, float) and np.isnan(value)):
                            continue

                        if isinstance(value, basestring):
                            try:
                                value = json.loads(value)
                            except ValueError:
                                continue
                        start = (start - unix_epoch).total_seconds()
                        result = self.assert_cal_value(None, None, uid, start, name, value, adj_time=True)
                        if result:
                            results.append(result)
                except (XLRDError):
                    pass

        print len(results)
        with open('new_results.csv', 'w') as fh:
            writer = csv.writer(fh)
            writer.writerows(results)
        assert False

    def test_old_spreadsheets(self):
        skip = ['CC_lat', 'CC_lon', 'CC_latitude', 'CC_longitude', 'Inductive ID', 'Induction ID', 'CC_depth']
        unix_epoch = datetime(1970, 1, 1)
        results = []
        count = 0
        for filename in glob('/Users/petercable/src/asset-management/ARCHIVE/deployment/Omaha_Cal*xlsx'):
            print filename
            sheets = pd.read_excel(filename, sheetname=None)
            if 'Moorings' in sheets and 'Asset_Cal_Info' in sheets:
                moorings = sheets['Moorings']
                moorings = moorings[['Mooring OOIBARCODE', 'Deployment Number', 'Anchor Launch Date', 'Anchor Launch Time']]
                moorings = moorings.dropna(how='any')
                deployments = {}

                for row in moorings.itertuples(index=False):
                    barcode, number, date, rowtime = row

                    if date == rowtime:
                        dt = date
                    else:
                        if isinstance(time, datetime):
                            rowtime = rowtime.time()
                        dt = datetime.combine(date.date(), rowtime)

                    deployments[(barcode, int(number))] = dt

                all_moorings = list({x[0] for x in deployments})

                df = sheets['Asset_Cal_Info']
                try:
                    df = df[
                        ['Ref Des', 'Mooring OOIBARCODE', 'Sensor OOIBARCODE', 'Deployment Number',
                         'Calibration Cofficient Name', 'Calibration Cofficient Value']]
                    df = df.dropna(how='all')
                    for each in df.itertuples(index=False):
                        refdes, mooring_uid, uid, deployment, name, value = each

                        if name in skip:
                            continue

                        if mooring_uid is None or isinstance(mooring_uid, float) and np.isnan(mooring_uid):
                            if len(all_moorings) == 1:
                                mooring_uid = all_moorings[0]

                        start = deployments.get((uid, deployment))
                        if start is None:
                            start = deployments.get((mooring_uid, deployment))
                        if start is None:
                            print 'deployment not found', each, deployments
                            continue

                        if (isinstance(uid, float) and np.isnan(uid) or
                                    isinstance(name, float) and np.isnan(name) or
                                    isinstance(value, float) and np.isnan(value)):
                            continue

                        if isinstance(value, basestring):
                            try:
                                value = json.loads(value)
                            except ValueError:
                                continue
                        start = (start - unix_epoch).total_seconds()
                        count += 1
                        result = self.assert_cal_value(refdes, deployment, uid, start, name, value)
                        if result:
                            results.append(result)
                except (XLRDError, KeyError) as e:
                    print e

        print len(results)
        print count
        with open('old_results.csv', 'w') as fh:
            writer = csv.writer(fh)
            writer.writerow(('reason', 'refdes', 'deployment', 'name', 'uid', 'start', 'start_ts', 'value', 'retrieved'))
            writer.writerows(results)

        assert False