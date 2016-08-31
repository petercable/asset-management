#!/usr/bin/env python
# -*- encoding:utf-8 -*-
import csv

import os
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.elements import and_

from model import IngestRoute, Deployment

url = 'sqlite:///convert.db'
deploy_dir = 'DEPLOY_CSV'

engine = create_engine(url, convert_unicode=True)
Session = sessionmaker(bind=engine)
session = Session()


def get_ingest(refdes, deployment):
    query = session.query(IngestRoute).filter(and_(
        IngestRoute.refdes.like('%' + refdes + '%'),
        IngestRoute.deployment == deployment)
    ).order_by(IngestRoute.deployment, IngestRoute.refdes)
    return pd.read_sql(query.statement, query.session.bind)


def flatten_routes(rows):
    out = []
    for _, row in rows.iterrows():
        path = os.path.dirname(row['mask'])
        mask = os.path.basename(row['mask'])
        out.extend((row.source, row.route, path, mask))
    return out


def find_longest(rows):
    return max((len(x) for x in rows))


def find_moorings():
    d_refdes_all = session.query(Deployment.refdes).distinct().all()
    i_refdes_all = session.query(IngestRoute.refdes).distinct().all()
    out = set()
    for refdes, in d_refdes_all + i_refdes_all:
        mooring = refdes.split('-')[0]
        out.add(mooring)
    return sorted(out)


def find_deployment(refdes, deployment):
    # print 'find_deployment(%r, %r)' % (refdes, deployment)
    # attempt to find an exact match
    record = session.query(Deployment).filter(and_(Deployment.refdes == refdes,
                                                   Deployment.deployment == deployment)).first()
    if record:
        # print 'found exact'
        return record

    parts = refdes.split('-', 2)
    mooring = parts[0]
    node = None
    if len(parts) > 1:
        node = parts[1]

    # no exact match, attempt to find the node
    if node is not None:
        record = session.query(Deployment).filter(Deployment.refdes == '-'.join((mooring, node))).first()
        if record:
            # print 'found node'
            return record

    # no node, find the mooring
    record = session.query(Deployment).filter(Deployment.refdes == mooring).first()
    # if record:
    #     print 'found mooring'
    return record


def find_location(refdes, deployment):
    record = find_deployment(refdes, deployment)
    if not record:
        return None, None, None, None

    return record.latitude, record.longitude, record.depth, None


def find_uids(refdes, deployment):
    mooring_uid = node_uid = sensor_uid = None
    parts = refdes.split('-', 2)
    while len(parts) < 3:
        parts.append(None)

    mooring, node, sensor = parts
    if all((mooring, node, sensor)):
        record = find_deployment(refdes, deployment)
        if record and record.refdes == refdes:
            sensor_uid = record.barcode

    if all((mooring, node)):
        refdes = '-'.join((mooring, node))
        record = find_deployment(refdes, deployment)
        if record and record.refdes == refdes:
            node_uid = record.barcode
        else:
            # special case, search for an ENGXXXXX
            # use that barcode as the node barcode
            record = find_deployment('-'.join((mooring, node, '%ENG%')), deployment)
            if record:
                node_uid = record.barcode

    if mooring:
        record = find_deployment(mooring, deployment)
        if record and record.refdes == mooring:
            mooring_uid = record.barcode

    return mooring_uid, node_uid, sensor_uid


def main():
    moorings = find_moorings()
    for mooring in moorings:
        query = session.query(Deployment).filter(Deployment.refdes.like(mooring + '%')).order_by(Deployment.deployment,
                                                                                                 Deployment.refdes)
        deployments = pd.read_sql(query.statement, query.session.bind)

        for deployment, rows in deployments.groupby('deployment'):
            if deployment == 0:
                print rows
                continue

            out = []
            for row in rows.itertuples(index=False):
                (_id, refdes, dnum, mooring_uid, node_uid, sensor_uid,
                 serial, launch, recover, lat, lon, depth, cruise) = row

                lat = round(float(lat), 5)
                lon = round(float(lon), 5)

                version = 1
                orbit = None
                deployed_by = None
                recovered_by = None
                recover_cruise = None

                this = [cruise, deployed_by, recover_cruise, recovered_by, refdes, deployment, version, launch,
                        recover, mooring_uid, node_uid, sensor_uid, lat, lon, orbit, depth]
                out.append(this)

            if out:
                # longest = find_longest(out)
                header = ['CUID_Deploy', 'deployedBy', 'CUID_Recover', 'recoveredBy', 'Reference Designator',
                          'deploymentNumber', 'versionNumber', 'startDateTime', 'stopDateTime', 'mooring.uid',
                          'node.uid', 'sensor.uid', 'lat', 'lon', 'orbit', 'depth']
                # ingest_header = ['Method', 'ingestQueue', 'ingestFilePath', 'ingestFileMask']
                # while len(header) < longest:
                #     header.extend(ingest_header)
                # for row in out:
                #     diff = longest - len(row)
                #     row.extend([''] * diff)

                fname = '%s_%d_Deploy.csv' % (mooring, deployment)
                if not os.path.exists(deploy_dir):
                    os.makedirs(deploy_dir)

                with open(os.path.join(deploy_dir, fname), 'w') as fh:
                    writer = csv.writer(fh)
                    writer.writerow(header)
                    writer.writerows(out)


if __name__ == '__main__':
    main()
