These files exist for a one-time conversion of the existing asset-management
files into the new format. All existing data is ingested into a temporary
SQLITE database, then this data is used to generate the new files.

```
./create_db.py <path/to/ingestion-csvs> <path/to/deployment> <mask>
```

If a mask is supplied, only files matching the specified mask will be processed.
Once the database has been created the resulting CSV can be generated with the
make scripts:

```
./make_cal.py
./make_deploy.py
```

The temporary database should NOT be committed back to this repository. Once
migration is complete, this folder will be removed from this repository to avoid
any future confusion.