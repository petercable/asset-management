#!/usr/bin/env python
from collections import namedtuple, OrderedDict
from itertools import chain

import pandas as pd
import csv

b1 = '/Users/petercable/src/asset-management/bulk/bulk_load-AssetRecord.csv'
b2 = '/Users/petercable/src/asset-management/refactored_asset_management/bulk/bulk_load-AssetRecord.csv'

cols = 'uid type mobile geometry desc quant manu model serial firmware source vests loc room cond date cost per comments tagd tago tagi stagd stago stagi doid doio doii'.split()
Row = namedtuple('Row', cols)

d1 = OrderedDict()
d2 = OrderedDict()

out_cols = OrderedDict(
    [('uid', 'ASSET_UID'),
    ('type', 'TYPE'),
    ('mobile', 'Mobile'),
    ('desc', 'DESCRIPTION OF EQUIPMENT'),
    ('manu', 'Manufacturer'),
    ('model', 'Model'),
    ('serial', "Manufacturer's Serial No./Other Identifier"),
    ('firmware', 'Firmware Version'),
    ('date', 'ACQUISITION DATE'),
    ('cost', 'ORIGINAL COST'),
    ('comments', 'comments')]
)


print 'build d1'
with open(b1) as fh1:
    reader = csv.reader(fh1)
    next(reader)
    for line in reader:
        line = line[:1] + ['', '', ''] + line[1:]
        row = Row(*line)
        d1.setdefault(row.uid, []).append(row)


print 'build d2'
with open(b2) as fh2:
    reader = csv.reader(fh2)
    out_header = next(reader)
    for line in reader:
        row = Row(*line)
        d2.setdefault(row.uid, []).append(row)


def compare(t1, t2):
    replace = {}
    if len(t1) != len(t2):
        print 'lengths differ', len(t1), len(t2)
        return replace
    for index, (a, b) in enumerate(zip(t1, t2)):
        if a != b:
            name = t1._fields[index]
            print 'field differs', t1.uid, name, repr(a), repr(b)
            if a == '':
                replace[name] = b
            elif b == '':
                continue
            else:
                choice = raw_input('1=%r 2=%r' % (a, b))
                if choice == '2':
                    replace[name] = b
    return replace


keys1 = d1.keys()
keys2 = d2.keys()
missing = set(keys2).difference(keys1)

with open('merged2.csv', 'w') as fh:
    writer = csv.writer(fh)
    # writer.writerow(list(chain(*zip(out_cols.values(), out_cols.values()))))
    writer.writerow(out_cols.values())
    rows = []

    for key in d1:
        if key:
            v1 = d1.get(key)
            v2 = d2.get(key, [None])

            if len(v1) > 1:
                print 'multiple', key
                continue

            v1 = v1[0]
            v2 = v2[0]

            if v2 is not None:
                v1 = v1._replace(type=v2.type, mobile=v2.mobile)

            v1 = [getattr(v1, k) for k in out_cols]
            rows.append(v1)
            # v2 = [getattr(v2, k) for k in out_cols]

    for key in missing:
        assert key not in d1
        if key.startswith('Waiting'):
            continue
        v2 = d2[key][0]
        rows.append([getattr(v2, k) for k in out_cols])

    rows.sort()
    writer.writerows(rows)
            # writer.writerow(v1)


    # for key in d1:
    #     if key:
    #         v1 = d1[key]
    #         v2 = d2.get(key)
    #
    #         if v2 is None:
    #             writer.writerows(v1)
    #             continue
    #
    #         if len(v1) > 1 or len(v2) > 1:
    #             print 'multiple', key
    #             writer.writerows(v1)
    #             continue
    #
    #         v1 = v1[0]
    #         v2 = v2[0]
    #
    #         if v2:
    #             v1 = v1._replace(type=v2.type, mobile=v2.mobile, quant=v2.quant)
    #             writer.writerow(v1)
    #     else:
    #         writer.writerows(d1[key])