#!/usr/bin/env python

from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class Bulk(Base):
    __tablename__ = 'bulk'
    id = Column(Integer, primary_key=True)
    uid = Column(String, nullable=False)
    asset_type = Column(String)
    mobile = Column(Boolean)
    desc = Column(String)
    manu = Column(String)
    model = Column(String)
    serial = Column(String)
    firmware = Column(String)
    date = Column(String)
    cost = Column(String)
    comments = Column(String)


class IngestRoute(Base):
    __tablename__ = 'ingest_route'
    id = Column(Integer, primary_key=True)
    route = Column(String, nullable=False)
    mask = Column(String, nullable=False)
    refdes = Column(String, nullable=False)
    source = Column(String, nullable=False)
    notes = Column(String)
    deployment = Column(Integer, nullable=False)


class Deployment(Base):
    # barcode, refdes, repr(serial), deployment, launch_date, recover_date, latitude, longitude, depth, cruise
    __tablename__ = 'deployment'
    id = Column(Integer, primary_key=True)
    refdes = Column(String, nullable=False)
    deployment = Column(Integer, nullable=False)
    mooring_uid = Column(String)
    node_uid = Column(String)
    sensor_uid = Column(String)
    serial = Column(String)
    launch_date = Column(String)
    recover_date = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    depth = Column(Integer)
    cruise = Column(String)

    def __repr__(self):
        return str((self.refdes, self.deployment, self.mooring_uid, self.sensor_uid,
                    self.serial, self.launch_date, self.recover_date, self.latitude,
                    self.longitude, self.depth, self.cruise))


class Calibration(Base):
    # refdes, mooring_uid, dnum, sensor_uid, name, value, notes
    __tablename__ = 'calibration'
    id = Column(Integer, primary_key=True)
    deployment_id = Column(Integer, ForeignKey(Deployment.id), nullable=False)
    deployment = relationship(Deployment)
    name = Column(String)
    value = Column(String)
    notes = Column(String)