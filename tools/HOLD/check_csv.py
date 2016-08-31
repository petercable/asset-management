#!/usr/bin/env python

import sys
import os
from collections import Counter

import pandas as pd


for path, dirs, files in os.walk(sys.argv[1]):
    for f in files:
        counter = Counter()
        if f.endswith('csv'):
            fname = os.path.join(path, f)
            df = pd.read_csv(fname)
            for name in df.name.values:
                counter[name] += 1

            for k, v in counter.items():
                if v > 1:
                    print fname, k, v