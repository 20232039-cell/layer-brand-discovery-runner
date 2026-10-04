import csv
import json
from pathlib import Path
import tempfile
import unittest
from brand_discovery.schema import adapt, MASTER_FIELDS
from brand_discovery.canary import exercise

class SchemaCanaryTests(unittest.TestCase):
    def test_master_lossless(self):
        row={k:'synthetic '+str(i) for i,k in enumerate(MASTER_FIELDS)}
        before=dict(row);a=adapt(row)
        self.assertEqual(a['source_record'],row)
        self.assertEqual(a['source_schema'],'master_17')
        self.assertEqual(row,before)
        self.assertNotIn('identity_status',a)
    def test_queue_aliases_and_verdict(self):
        a=adapt({'verification_excel_row':'12','브랜드(한글)':'예시','공식몰':'https://example.invalid/','판정':'확인완료'})
        self.assertEqual(a['official_url'],'https://example.invalid/')
        self.assertEqual(a['source_verdict'],'확인완료')
        self.assertNotIn('status',a)
    def test_synthetic_canary_all_cases(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            with (root/'candidates.csv').open('w') as f:
                w=csv.DictWriter(f,fieldnames=['name','official_url']);w.writeheader()
                w.writerows([{'name':'CANARY_SYNTHETIC_SUCCESS','official_url':'https://canary.invalid/success'},{'name':'CANARY_SYNTHETIC_ERROR','official_url':'https://canary.invalid/error'}])
            exercise(root);exercise(root)
            self.assertFalse((root/'empty-canary').exists())
            self.assertEqual(len(json.loads((root/'checkpoint.json').read_text())),2)
    def test_canary_rejects_actual_sites(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'candidates.csv').write_text('name,official_url\nReal,https://example.com/\n')
            with self.assertRaises(ValueError):exercise(root)

if __name__=='__main__':unittest.main()
