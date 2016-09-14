#!/usr/bin/env python
# -*- encoding:utf-8 -*-
import csv
import datetime
import json
import sys
import traceback
from numbers import Number

import fnmatch
import numpy as np
import os
import pandas as pd
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.elements import and_
from unidecode import unidecode
from xlrd import XLRDError

from model import Base, IngestRoute, Deployment, Calibration, Bulk

dbfile = 'convert.db'
url = 'sqlite:///%s' % dbfile
bulk_path = '../../bulk/bulk_load-AssetRecord.csv'


if os.path.exists(dbfile):
    os.unlink(dbfile)

engine = create_engine(url, convert_unicode=True)
Session = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


dms_re = re.compile(u"(\d+)\s*[\xb0]\s*(\d+)\.*\s*(\d*)\s*['|\u2019]?\s*([NSEW])")


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


def dms_to_float(value_string):
    if isinstance(value_string, float):
        return value_string
    try:
        return float(value_string)
    except ValueError:
        pass

    match = dms_re.search(value_string)
    if match:
        degrees, minutes, decimal_minutes, sign = match.groups()
        minutes = float(minutes) + float('0.' + decimal_minutes)
        value = int(degrees) + float(minutes) / 60
        if sign in 'NE':
            return value
        else:
            return -value
    else:
        print 'no match: %r' % value_string
        raise Exception


def date_string_to_datetime(date_string, time_string):
    # transform date_string as necessary
    if isinstance(date_string, pd.tslib.Timestamp):
        d = date_string.to_datetime()
    elif isinstance(date_string, pd.tslib.NaTType):
        d = None
    elif isinstance(date_string, datetime.datetime):
        d = date_string
    elif isinstance(date_string, basestring):
        if not date_string or date_string == ' ':
            d = None
        else:
            year, month, day = date_string.split('-')
            d = datetime.date(year, month, day)
    elif isinstance(date_string, float) and np.isnan(date_string):
        d = None
    else:
        print 'date', date_string, type(date_string)
        d = None

    # transform time_string as necessary
    if time_string is None:
        t = None
    elif isinstance(time_string, datetime.time):
        t = time_string
    elif isinstance(time_string, datetime.datetime):
        t = None
    elif isinstance(time_string, float) and np.isnan(time_string):
        t = None
    else:
        print 'time', time_string, type(time_string)
        t = None

    if d is not None and t is not None:
        return datetime.datetime.combine(d, t).isoformat()

    if isinstance(d, datetime.datetime) and t is None:
        return d.isoformat()

    if d is not None and t is None:
        return datetime.datetime.combine(d, datetime.time()).isoformat()

    return None


def isnan(val):
    return val is None or isinstance(val, float) and np.isnan(val)


def in_bulk(uid, session):
    return session.query(Bulk).filter(Bulk.uid == uid).count() > 0


def get_bulk():
    print 'Getting BULK records'
    session = Session()
    with open(bulk_path) as fh:
        reader = csv.reader(fh)
        next(reader)
        for row in reader:
            uid, asset_type, mobile, desc, manu, model, serial, firmware, date, cost, comments = row
            if mobile == '':
                mobile = False
            bulk = Bulk(uid=uid, asset_type=asset_type, mobile=mobile, desc=desc, manu=manu,
                        model=model, serial=serial, firmware=firmware, date=date,
                        cost=cost, comments=comments)
            session.add(bulk)
    session.commit()


def get_ingest(ingest_dir):
    print 'Getting INGEST records'
    session = Session()
    for path, dirs, files in os.walk(ingest_dir):
        for f in files:
            if f.endswith('.csv'):
                df = pd.read_csv(os.path.join(path, f))
                # "uframe_route,filename_mask,reference_designator,data_source,"
                for each in df.itertuples(index=False):
                    try:
                        route, fmask, refdes, source = each[:4]
                        if not isinstance(route, basestring):
                            continue
                        if route.startswith('#'):
                            continue

                        if len(each) > 4:
                            notes = each[4]
                        else:
                            notes = None

                        try:
                            fparts = f.split('_')
                            deployment = int(fparts[1][1:])

                            ingest_route = IngestRoute()
                            ingest_route.route = route
                            ingest_route.mask = fmask
                            ingest_route.refdes = refdes
                            ingest_route.source = source
                            ingest_route.notes = notes
                            ingest_route.deployment = deployment
                            session.add(ingest_route)
                            session.flush()

                        except IndexError:
                            print f
                    except ValueError:
                        print each
    session.commit()


def get_or_create_deployment(refdes, deployment, uid, session=None):
    if session is None:
        session = Session()

    d = session.query(Deployment).filter(and_(Deployment.refdes == refdes,
                                              Deployment.deployment == deployment,
                                              Deployment.sensor_uid == uid)).first()

    if d is None:
        d = Deployment(refdes=refdes, deployment=deployment, sensor_uid=uid)

    return d


def get_sheetref(filepath, sheetname):
    df = pd.read_excel(filepath, sheetname=sheetname, header=None)
    df.dropna(how='all', inplace=True)
    df.dropna(axis=1, how='all', inplace=True)
    data = df.as_matrix()
    for x in data.flatten():
        if not isinstance(x, Number):
            print 'NON-NUMERIC', x
    return json.dumps(df.as_matrix(), cls=NumpyJSONEncoder)


def update_deployments(refdes, dnum, uid, launch, recover, lat, lon, cruise, depth, session):
    # print
    # print
    # print refdes, dnum, uid, launch, recover, lat, lon, cruise, depth
    deployments = session.query(Deployment).filter(and_(Deployment.sensor_uid == uid,
                                                        Deployment.deployment == dnum)).all()

    deployments += session.query(Deployment).filter(and_(Deployment.mooring_uid == uid,
                                                         Deployment.deployment == dnum)).all()

    # for each in deployments:
    #     print 'depl', each

    if deployments:
        for d in deployments:
            d.launch_date = launch
            d.recover_date = recover
            d.latitude = lat
            d.longitude = lon
            d.cruise = cruise
            d.depth = depth
            session.add(d)

    else:
        d = Deployment(refdes=refdes, deployment=dnum, launch_date=launch, recover_date=recover,
                       latitude=lat, longitude=lon, cruise=cruise, depth=depth, mooring_uid=uid)
        session.add(d)

    session.flush()


def get_deployments(deployment_dir, pat='*.xlsx'):
    print 'get_deployments'
    session = Session()
    for path, dirs, files in os.walk(deployment_dir):
        for f in fnmatch.filter(files, pat):
            try:
                f = os.path.join(path, f)
                print 'Reading:', f
                df = pd.read_excel(f, sheetname='Moorings')
                for row in df.itertuples(index=False):
                    (barcode, refdes, serial, deployment_num, launch_date, launch_time,
                     recover_date, latitude, longitude, depth, cruise) = row[:11]
                    if not isinstance(barcode, basestring):
                        continue

                    latitude = dms_to_float(latitude)
                    longitude = dms_to_float(longitude)
                    launch_date = date_string_to_datetime(launch_date, launch_time)
                    recover_date = date_string_to_datetime(recover_date, None)
                    deployment_num = int(deployment_num)
                    try:
                        depth = int(depth)
                    except ValueError:
                        depth = None

                    if not all((barcode, refdes, serial, launch_date, latitude, longitude, deployment_num)):
                        print barcode, refdes, serial, launch_date, latitude, longitude, deployment_num
                        continue

                    update_deployments(refdes, deployment_num, barcode, launch_date, recover_date,
                                       latitude, longitude, cruise, depth, session)

            except XLRDError:
                pass
    session.commit()


def get_cals(deployment_dir, pat='*.xlsx'):
    print 'get_cals'
    session = Session()
    fields = ['Ref Des', 'Mooring OOIBARCODE', 'Deployment Number', 'Sensor OOIBARCODE', 'Sensor Serial Number',
              'Calibration Cofficient Name', 'Calibration Cofficient Value', 'Notes']
    for path, dirs, files in os.walk(deployment_dir):
        for f in fnmatch.filter(files, pat):
            f = os.path.join(path, f)
            print 'Calibration file:', f
            try:
                df = pd.read_excel(f, sheetname='Asset_Cal_Info')
                if 'Notes' not in df:
                    df['Notes'] = [None] * len(df)

                df = df[fields].dropna(how='all')

                for each in df.itertuples(index=False):
                    refdes, mooring_uid, dnum, sensor_uid, serial, name, value, notes = each

                    if notes is None:
                        notes = ''

                    if isinstance(notes, unicode):
                        notes = unidecode(notes)

                    if any(map(isnan, (refdes, dnum, mooring_uid, sensor_uid))):
                        print 'SKIPPING:', each
                        continue

                    if not all((in_bulk(mooring_uid, session), in_bulk(sensor_uid, session))):
                        print 'NOT IN BULK', each

                    # sometimes the serial field is a NUMERIC cell, so
                    if isinstance(serial, float):
                        serial_str = str(serial)
                        if serial_str.endswith('.0'):
                            serial = str(int(serial))
                        else:
                            serial = serial_str

                    deployment = get_or_create_deployment(refdes, dnum, sensor_uid, session)
                    deployment.mooring_uid = mooring_uid
                    deployment.sensor_uid = sensor_uid
                    deployment.serial = serial
                    session.add(deployment)

                    if not any(map(isnan, (name, value))):
                        if isinstance(value, basestring) and value.startswith('SheetRef'):
                            value = get_sheetref(f, value.replace('SheetRef:', ''))
                        calibration = Calibration(name=name, value=value, notes=notes, deployment=deployment)
                        session.add(calibration)
                    session.flush()
            except XLRDError:
                traceback.print_exc()

    session.commit()


ingest_dir = sys.argv[1]
deploy_dir = sys.argv[2]
mask = '*.xlsx'

if len(sys.argv) > 3:
    mask = sys.argv[3]

get_bulk()
get_ingest(ingest_dir)
get_cals(deploy_dir, pat=mask)
get_deployments(deploy_dir, pat=mask)
