#!/usr/bin/env python
import csv
import json
from numbers import Number

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unidecode import unidecode

from model import Calibration

url = 'sqlite:///convert.db'

engine = create_engine(url, convert_unicode=True)
Session = sessionmaker(bind=engine)
session = Session()


def create_filename(klass, uid, timestamp):
    timestamp = timestamp.split('T')[0]
    timestamp = timestamp.replace('-', '')
    # timestamp = timestamp.replace(':', '')
    fname = '%s__%s.csv' % (uid, timestamp)
    group = os.path.join('CAL_CSV', klass)

    if not os.path.exists(group):
        os.makedirs(group)
    return os.path.join(group, fname)


cals = {}
IGNORE = ['CC_lat', 'CC_lon', 'CC_latitude', 'CC_longitude', 'Induction ID']

for cal in session.query(Calibration).all():
    dep = cal.deployment
    uid = dep.sensor_uid
    serial = dep.serial
    launch = dep.launch_date
    klass = dep.refdes.split('-')[-1][:6]

    if cal.name in IGNORE:
        continue

    # print klass, uid, launch, cal.name, cal.value

    if not all((cal.name, cal.value)):
        continue
    if not all((klass, uid, launch)):
        print 'MISSING DATA', (klass, uid, launch, cal.name, cal.value)
        continue

    notes = cal.notes
    if notes is not None:
        notes = unidecode(notes)

    try:
        data = json.loads(cal.value)
        if isinstance(data, (tuple, list)):
            for each in data:
                if isinstance(each, basestring):
                    each = json.loads(each)
                if isinstance(each, list):
                    for x in each:
                        if not isinstance(x, Number):
                            print 'NON-NUMERIC', each
                            break
                elif not isinstance(each, Number):
                    print 'NON-NUMERIC', each
        value = json.dumps(json.loads(cal.value))

        cals.setdefault((klass, uid, launch), []).append((serial, cal.name, value, notes))
    except ValueError:
        print 'invalid JSON', (klass, uid, launch, cal.name, cal.value)


for (klass, uid, launch), rows in cals.iteritems():
    if launch is None:
        print uid, launch, rows
        continue
    rows.sort()

    fname = create_filename(klass, uid, launch)

    with open(fname, 'wb') as fh:
        writer = csv.writer(fh, lineterminator='\n')
        writer.writerow(('serial', 'name', 'value', 'notes'))
        for row in rows:
            serial, name, value, notes = row
            if len(value) > 10000:
                data = json.loads(value)
                sheet_fname = fname.replace('.csv', '__%s.ext' % name)
                with open(sheet_fname, 'w') as sheet_fh:
                    sheet_writer = csv.writer(sheet_fh)
                    sheet_writer.writerows(data)
                writer.writerow((serial, name, 'SheetRef:%s' % name, notes))
            else:
                writer.writerow(row)
