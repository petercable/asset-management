import json

import pandas as pd
import numpy as np
from datetime import datetime

from unidecode import unidecode
from xlrd import XLRDError


def extract_cals_from_new_sheet(filename):
    cals = []
    sheets = pd.read_excel(filename, sheetname=None)

    cal_sheet_name = 'Cal_Info'
    columns = ['Sensor Code', 'startDateTime', 'Sensor.uid', 'Sensor Serial Number',
               'Calibration Cofficient Name', 'Calibration Cofficient Value', 'Notes']

    cal_sheets = [sheet for sheet in sheets if cal_sheet_name in sheet]

    for sheet_name in cal_sheets:

        cal_info = sheets[sheet_name]

        if 'Notes' not in cal_info:
            cal_info['Notes'] = [None] * len(cal_info['Sensor Code'])

        cal_info = cal_info[columns]
        cal_info = cal_info.dropna(how='all')

        for code, start, uid, serial, name, value, notes in cal_info.itertuples(index=False):
            if isinstance(value, basestring):
                if value.startswith('SheetRef'):
                    sheetref_name = value.replace('SheetRef:', '')
                    value = 'external'
                    external_name = filename.replace('.csv', '-%s.csv' % name)
                    try:
                        sheets[sheetref_name].to_csv(external_name, index=False, header=False)
                    except KeyError:
                        print repr(sheetref_name), sheets.keys()
                else:
                    try:
                        value = json.loads(value)
                    except ValueError:
                        print value
                        continue

            value = json.dumps(value, cls=NumpyJSONEncoder)
            cals.append((code, uid, start, name, value, notes))

    return cals


def get_deployments(moorings):
    moorings = moorings[['Mooring OOIBARCODE', 'Deployment Number', 'Anchor Launch Date', 'Anchor Launch Time']]
    moorings = moorings.dropna(how='any')
    deployments = {}

    for row in moorings.itertuples(index=False):
        barcode, number, date, rowtime = row

        if date == rowtime:
            dt = date
        else:
            if isinstance(rowtime, datetime):
                rowtime = rowtime.time()
            dt = datetime.combine(date.date(), rowtime)

        deployments[(barcode, int(number))] = dt
    return deployments


def is_nan(value):
    return isinstance(value, float) and np.isnan(value)


def extract_cals_from_old_sheet(filename):
    cals = []
    sheets = pd.read_excel(filename, sheetname=None)
    if 'Moorings' in sheets and 'Asset_Cal_Info' in sheets:
        deployments = get_deployments(sheets['Moorings'])
        all_moorings = list({x[0] for x in deployments})

        df = sheets['Asset_Cal_Info']
        try:
            if 'Notes' not in df:
                df['Notes'] = [None] * len(df)

            df = df[
                ['Ref Des', 'Mooring OOIBARCODE', 'Sensor OOIBARCODE', 'Sensor Serial Number', 'Deployment Number',
                 'Calibration Cofficient Name', 'Calibration Cofficient Value', 'Notes']]
            df = df.dropna(how='all')

            for each in df.itertuples(index=False):
                refdes, mooring_uid, uid, serial, deployment, name, value, notes = each

                if any(map(is_nan, [refdes, uid, serial, deployment, name, value])):
                    continue

                if is_nan(notes):
                    notes = None

                instrument_class = refdes.split('-')[-1][:6]

                if mooring_uid is None or is_nan(mooring_uid):
                    if len(all_moorings) == 1:
                        mooring_uid = all_moorings[0]

                start = deployments.get((uid, deployment))
                if start is None:
                    start = deployments.get((mooring_uid, deployment))
                if start is None:
                    print 'deployment not found', each, deployments
                    continue

                if isinstance(value, basestring):
                    if value.startswith('SheetRef:'):
                        sheetref_name = value.replace('SheetRef:', '')
                        value = pd.read_excel(filename, sheetname=sheetref_name, header=None)
                        # value = sheets[sheetref_name]
                        value.dropna(axis=(0,1), how='all', inplace=True)
                    else:
                        try:
                            value = json.loads(value)
                            value = json.dumps(value)
                        except ValueError:
                            error = 'invalid JSON value'
                            print error, each
                            continue
                else:
                    value = json.dumps(value, cls=NumpyJSONEncoder)

                if isinstance(notes, unicode):
                    notes = unidecode(notes)

                cals.append((instrument_class, refdes, deployment, uid, serial, start, name, value, notes))
        except (XLRDError, KeyError) as e:
            print e

    return cals


class NumpyJSONEncoder(json.JSONEncoder):
    """
    numpy array indexing will often return numpy scalars, for
    example a = array([0.5]), type(a[0]) will be numpy.float64.
    The problem is that numpy types are not json serializable.
    However, they have a lot of the same methods as ndarrays, so
    for example, tolist() can be called on a numpy scalar or
    numpy ndarray to convert to regular python types.
    """
    def default(self, o):
        if isinstance(o, (np.generic, np.ndarray)):
            return o.tolist()
        else:
            return json.JSONEncoder.default(self, o)