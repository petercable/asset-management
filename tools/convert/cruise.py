#!/usr/bin/env python
# -*- encoding:utf-8 -*-
import csv

import os
from operator import attrgetter

import pandas as pd
from dateutil import parser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from model import IngestRoute, Deployment

url = 'sqlite:///convert.db'
deploy_dir = 'DEPLOY_CSV'

engine = create_engine(url, convert_unicode=True)
Session = sessionmaker(bind=engine)
session = Session()


def find_moorings():
    d_refdes_all = session.query(Deployment.refdes).distinct().all()
    i_refdes_all = session.query(IngestRoute.refdes).distinct().all()
    out = set()
    for refdes, in d_refdes_all + i_refdes_all:
        mooring = refdes.split('-')[0]
        out.add(mooring)
    return sorted(out)


def date_distance(a, b):
    a = parser.parse(a)
    b = parser.parse(b)
    return abs((a - b).total_seconds())


def get_cruises():
    moorings = find_moorings()
    cruises = []
    for mooring in moorings:
        query = session.query(Deployment).filter(Deployment.refdes.like(mooring + '%')).order_by(Deployment.deployment,
                                                                                                 Deployment.refdes)
        deployments = pd.read_sql(query.statement, query.session.bind)

        for deployment, rows in deployments.groupby('deployment'):
            if deployment == 0:
                # print rows
                continue

            out = []
            for row in rows.itertuples(index=False):
                (_id, refdes, dnum, mooring_uid, node_uid, sensor_uid,
                 serial, launch, recover, lat, lon, depth, cruise) = row

                try:
                    subsite, node, sensor = refdes.split('-', 2)
                    if node.startswith('GL'):
                        subsite = '-'.join((subsite, node))
                except ValueError:
                    subsite = refdes

                cruises.append((subsite, str(deployment), str(cruise), str(launch)))

    return pd.DataFrame(cruises, columns=['site', 'deployment', 'cruise', 'launch'])


def main():
    df = get_cruises()
    out = []
    for group, rows in df.groupby('cruise'):
        rows = rows.drop_duplicates()
        rows = rows.sort_values('launch')

        if group.startswith('TN'):
            ship = 'R/V Thompson'
        elif group.startswith('KN'):
            ship = 'R/V Knorr'
        elif group.startswith('OC'):
            ship = 'R/V Oceanus'
        elif group.startswith('AT'):
            ship = 'R/V Atlantis'
        elif group.startswith('MV'):
            ship = 'R/V Melville'
        elif group.startswith('AR'):
            ship = 'R/V Armstrong'
        elif group.startswith('TI'):
            ship = 'R/V Tioga'
        elif group.startswith('PS'):
            ship = 'R/V Pacific Storm'
        elif group.startswith('NBP'):
            ship = 'R/V Palmer'
        elif group.startswith('RB'):
            ship = 'R/V Ron Brown'
        else:
            ship = ''

        tbins = {}
        MAX = 86400 * 90

        for row in rows.itertuples(index=False):
            if row.launch is None or row.launch == 'None':
                continue

            found = False
            for tbin in tbins:
                if date_distance(row.launch, tbin) < MAX:
                    tbins[tbin].append(row)
                    found = True
                    break
            if not found:
                tbins[row.launch] = [row]

        for tbin in tbins:
            deploys = []
            _bin = tbins[tbin]
            # _bin.sort(key=attrgetter('launch'))
            for each in _bin:
                deploys.append(','.join((each.site, each.deployment, each.launch)))

            out.append((group, ship, tbin, _bin[-1].launch, '\n'.join(deploys)))

    with open('pete_cruises.csv', 'w') as fh:
        writer = csv.writer(fh)
        writer.writerow(('CUID', 'ShipName', 'cruiseStartDateTime', 'cruiseStopDateTime', 'notes'))
        writer.writerows(out)

if __name__ == '__main__':
    main()
