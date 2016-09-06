#!/usr/bin/env python

import glob
import os

import pandas as pd
import sys

from extractors import extract_cals_from_old_sheet


columns = ['Sensor Code', 'startDateTime', 'stopDateTime', 'Sensor.uid', 'Sensor Serial Number',
           'Calibration Cofficient Name', 'Calibration Cofficient Value',	'Notes']


def create_filename(klass, uid, timestamp):
    timestamp = timestamp.isoformat()
    timestamp = timestamp.replace('-', '')
    timestamp = timestamp.replace(':', '')
    fname = '%s__%s.csv' % (uid, timestamp)
    group = os.path.join('CSV', klass)

    if not os.path.exists(group):
        os.makedirs(group)
    return os.path.join(group, fname)


def generate_csv_from_old(directory):
    for filename in glob.glob(directory):
        cals = extract_cals_from_old_sheet(filename)
        cals_df = pd.DataFrame(cals, columns=['klass', 'refdes', 'deployment', 'uid', 'serial',
                                              'start', 'name', 'value', 'notes'])
        for (klass, uid, start), group in cals_df.groupby(['klass', 'uid', 'start']):
            fname = create_filename(klass, uid, start)
            group = group.sort_values('name')
            for index, value in enumerate(group.value.values[:]):
                if isinstance(value, pd.DataFrame):
                    sub_fname = fname.replace('.csv', '__%s.ext' % group.name.values[index])
                    # print sub_fname, list(value.as_matrix().flatten())
                    value.to_csv(sub_fname, index=False, header=False)
                    group.value.values[index] = 'external:%s' % os.path.basename(sub_fname)
            group[['serial', 'name', 'value', 'notes']].to_csv(fname, index=False)


mask = '/Users/petercable/src/asset-management/deployment/Omaha_Cal*xlsx'
if len(sys.argv) > 1:
    mask = sys.argv[1]


generate_csv_from_old(mask)