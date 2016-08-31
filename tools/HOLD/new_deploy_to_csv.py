#!/usr/bin/env python

import pandas as pd
import sys

cols = 'CUID_Deploy,deployedBy,CUID_Recover,recoveredBy,Reference Designator,deploymentNumber,versionNumber,startDateTime,stopDateTime,mooring.uid,node.uid,sensor.uid,lat,lon,orbit,depth'.split(',')


def get_data(fname):
    print fname
    df = pd.read_excel(fname)
    df.rename(columns={'referenceDesignator': 'Reference Designator',
                       'startDate/Time': 'startDateTime',
                       'stopDate/Time': 'stopDateTime',
                       'StopDate/Time': 'stopDateTime',
                       },
              inplace=True)
    return df[cols]


frames = []
for f in sys.argv[1:]:
    frames.append(get_data(f))

concat = pd.concat(frames)

concat.to_csv('concat.csv', index=False)