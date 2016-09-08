import logging
from collections import Counter

from nose.plugins.attrib import attr

from ..test_base import AssetManagementUnitTest

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)


@attr('UNIT')
class BulkLoadUnitTest(AssetManagementUnitTest):
    def test_duplicate_uid(self):
        counter = Counter(self.bulk_data.uid.values)
        counter.subtract(set(self.bulk_data.uid.values))
        dupes = counter + Counter()
        if dupes:
            log.error('Found duplicate keys in bulk load: %r', dupes)
            assert False
