#!/usr/bin/env python
import os
import sys
import pandas as pd
from datetime import timedelta
from dateutil import parser


source_dir = sys.argv[1]
dest_dir = sys.argv[2]


for f in os.listdir(source_dir):
    df = pd.read_csv(os.path.join(source_dir, f), index_col=None)
    starts = []
    stops = []

    for t in df['cruiseStartDateTime']:
        try:
            starts.append(parser.parse(t).date())
        except AttributeError:
            starts.append(None)

    for t in df['cruiseStopDateTime']:
        try:
            stops.append(parser.parse(t).date())
        except AttributeError:
            stops.append(None)

    for index, start in enumerate(starts):
        stop = stops[index]
        if start == stop:
            stops[index] = stop + timedelta(days=1)

    df['cruiseStartDateTime'] = starts
    df['cruiseStopDateTime'] = stops
    df['CUID'] = df['CruiseIdentifier']

    df = df.fillna('UNKNOWN')

    sheetname = f.replace('.csv', '')
    writer = pd.ExcelWriter(os.path.join(dest_dir, sheetname + '.xlsx'),
                            engine='xlsxwriter', datetime_format='yyyy-mm-ddThh:mm:ss')
    df.to_excel(writer, sheet_name=sheetname, index=False)
