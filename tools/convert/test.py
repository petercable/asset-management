#!/usr/bin/env python
import json

import os
import pandas as pd
import numpy as np
import sys


def isnan(val):
    return isinstance(val, float) and np.isnan(val)


def load_df(fname):
    df = pd.read_csv(fname)
    df = load_json(df, fname)
    return df


def load_sheetref(fname, name, value):
    basedir = os.path.dirname(fname)
    fname = os.path.basename(fname)
    sheetref_name = None
    if value.startswith('SheetRef'):
        sheetref_name = fname.replace('.csv', '__%s.ext' % name)
    if value.startswith('external'):
        sheetref_name = fname.replace('.csv', '__%s.ext' % name)

    if sheetref_name:
        return pd.read_csv(os.path.join(basedir, sheetref_name), header=None).as_matrix()


def load_json(df, fname):
    vals = df.value.values
    new_vals = []
    for index, v in enumerate(vals):
        if isinstance(v, basestring):
            if v.startswith('SheetRef') or v.startswith('external'):
                new_vals.append(load_sheetref(fname, df.name.values[index], v))
            else:
                new_vals.append(np.array(json.loads(v)))

        else:
            new_vals.append(v)

    df['value'] = new_vals
    return df


def compare(df1, df2):
    df1.sort_values('name', inplace=True)
    df2.sort_values('name', inplace=True)

    fail = []

    try:
        if not all(df1.serial == df2.serial):
            fail.append('serial')
    except ValueError:
        fail.append('shape')
        return fail

    # for index, v1 in enumerate(df1.notes.values):
    #     v2 = df2.notes.values[index]
    #     if all(map(isnan, (v1, v2))):
    #         continue
    #
    #     elif v1 != v2:
    #         fail.append('notes')
    #         break

    for index, v1 in enumerate(df1.value.values):
        v2 = df2.value.values[index]

        try:
            np.testing.assert_array_almost_equal(v1, v2)
        except AssertionError as e:
            print e
            fail.append('value: %s' % df1.name.values[index])
            break
        except TypeError as e:
            print e
            fail.append('value: %s' % df1.name.values[index])
            break

    return fail


a_dir = sys.argv[1]
b_dir = sys.argv[2]

for path, dirs, files in os.walk(a_dir):
    for f in files:
        if not f.endswith('.csv'):
            continue

        f1 = os.path.join(path, f)
        f2 = os.path.join(path.replace(a_dir, b_dir), f)

        if not os.path.exists(f2):
            print 'NO MATCH:', f1
            continue

        d1 = load_df(f1)
        d2 = load_df(f2)

        fail = compare(d1, d2)
        if fail:
            print f
            print fail
            print d1
            print d2