#!/usr/bin/env python
import fnmatch
import os

import pandas as pd
from datetime import datetime

import sys

name_col = 'Calibration Cofficient Name'
value_col = 'Calibration Cofficient Value'
notes_col = 'Notes'
code_col = 'Sensor Code'
start_col = 'startDateTime'
stop_col = 'stopDateTime'
uid_col = 'Sensor.uid'
serial_col = 'Sensor Serial Number'

columns = [code_col, start_col, stop_col, uid_col, serial_col, name_col, value_col, notes_col]


def extract_from_filepath(filepath):
    filename = os.path.basename(filepath)
    code = os.path.basename(os.path.dirname(filepath))
    uid, timestamp = filename.replace('.csv', '').split('__', 1)
    timestamp = datetime.strptime(timestamp, '%Y%m%dT%H%M%S')
    new_name = filename.replace('.csv', '_Cal_Info.xlsx')
    return code, uid, timestamp, new_name


def write_xlsx(filepath):
    print filepath
    df = pd.read_csv(filepath)
    df = df.rename(columns={'name': name_col, 'value': value_col, 'notes': notes_col, 'serial': serial_col})

    subsheets = {}
    for index, value in enumerate(df[value_col].values):
        if isinstance(value, basestring) and value.startswith('external'):
            name = df[name_col][index]
            path = os.path.dirname(filepath)
            fname = value.replace('external:', '')
            value = 'SheetRef:%s' % name
            subsheets[name] = pd.read_csv(os.path.join(path, fname))
            df[value_col].values[index] = value

    length = len(df)

    code, uid, start, new_name = extract_from_filepath(filepath)

    df[code_col] = [code] * length
    df[start_col] = [start] * length
    df[stop_col] = [None] * length
    df[uid_col] = [uid] * length

    writer = pd.ExcelWriter(new_name, engine='xlsxwriter', datetime_format='yyyy-mm-ddThh:mm:ss')
    df[columns].to_excel(writer, sheet_name='Asset_Cal_Info', index=False)

    for name in subsheets:
        subsheets[name].to_excel(writer, sheet_name=name, index=False, encoding='utf-8')

    writer.close()


def main():
    for path, dirs, files in os.walk(sys.argv[1]):
        for filename in fnmatch.filter(files, '*.csv'):
            write_xlsx(os.path.join(path, filename))


main()