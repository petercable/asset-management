#!/usr/bin/env python
import csv
import json

import os

import pandas as pd
import sys

import numpy as np

from extractors import extract_cals_from_new_sheet


def create_filename(klass, uid, timestamp):
    timestamp = timestamp.isoformat()
    timestamp = timestamp.replace('-', '')
    timestamp = timestamp.replace(':', '')
    fname = '%s_%s.csv' % (uid, timestamp)
    group = os.path.join('CSV', klass)

    if not os.path.exists(group):
        os.makedirs(group)
    return os.path.join(group, fname)


def create_csv(cals):
    cals_df = pd.DataFrame(cals, columns=['klass', 'uid',
                                          'start', 'name', 'values', 'notes'])

    for (klass, uid, start), group in cals_df.groupby(['klass', 'uid', 'start']):
        fname = create_filename(klass, uid, start)
        group = group.sort_values('name')
        group[['name', 'values', 'notes']].to_csv(fname, index=False, encoding='utf-8')


def main():
    for filename in sys.argv[1:]:
        cals = extract_cals_from_new_sheet(filename)
        create_csv(cals)


main()