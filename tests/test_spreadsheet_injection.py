"""Synthetic-only export tests; spreadsheet payloads are never evaluated."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from brand_discovery.collector import atomic_json, safe_cell, write_csv
from brand_discovery.xlsx import write_xlsx, literal_xml_text

PAYLOADS = [
    '=1+1', '+SUM(1,2)', '-SUM(1,2)', '@SUM(1,2)',
    '\t=1+1', '\r=1+1', '\n=1+1', ' \t+SUM(1,2)',
    '\tordinary text', '\rordinary text', '\nordinary text',
    ' \tordinary text', '\x00=1+1', '\x1b=1+1', '\x7f=1+1',
    '=HYPERLINK("https://example.invalid/", "synthetic")',
    '=WEBSERVICE("https://example.invalid/synthetic")',
]

class SpreadsheetInjectionTests(unittest.TestCase):
    def test_csv_neutralizes_formula_and_control_prefixes(self):
        for value in PAYLOADS:
            with self.subTest(value=repr(value)):
                self.assertEqual(safe_cell(value), "'" + value)
        for value in ['normal name', 'https://example.invalid/', '', '2 + 2', "'=1+1"]:
            self.assertEqual(safe_cell(value),value)

    def test_csv_roundtrip_preserves_boundaries_and_raw_json(self):
        # Quotes, separators and line breaks must stay inside a single CSV cell.
        payloads=PAYLOADS+['plain,"=1+1', 'plain\r\n=1+1', 'plain;=1+1']
        rows=[{'name':x,'excerpt':'synthetic'} for x in payloads]
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            atomic_json(root/'raw-evidence.json',rows)
            write_csv(root/'review.csv',rows,['name','excerpt'])
            with (root/'review.csv').open(encoding='utf-8-sig',newline='') as f:
                parsed=list(csv.DictReader(f))
            self.assertEqual(len(parsed),len(rows))
            self.assertEqual([r['name'] for r in parsed],[safe_cell(x) for x in payloads])
            self.assertTrue(all(set(r)=={'name','excerpt'} for r in parsed))
            self.assertEqual(json.loads((root/'raw-evidence.json').read_text()),rows)

    def test_csv_headers_also_neutralized(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'review.csv'
            write_csv(path,[{'=synthetic':'normal'}],['=synthetic'])
            with path.open(encoding='utf-8-sig',newline='') as f:
                parsed=list(csv.reader(f))
            self.assertEqual(parsed,[["'=synthetic"],['normal']])

    def test_xlsx_payloads_are_literal_strings_without_external_links(self):
        payloads=list(PAYLOADS)
        payloads+=['</t></is></c><f>1+1</f>','plain,"=1+1']
        rows=[{'name':x} for x in payloads]
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'review.xlsx';write_xlsx(path,rows,['name'])
            with ZipFile(path) as z:
                names=z.namelist()
                self.assertFalse(any('externalLink' in n for n in names))
                xml=z.read('xl/worksheets/sheet1.xml')
                sheet=ET.fromstring(xml)
                ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                cells=sheet.findall('.//s:c',ns)
                self.assertEqual(len(cells),len(payloads)+1)
                self.assertTrue(all(c.attrib['t']=='inlineStr' for c in cells))
                self.assertEqual(sheet.findall('.//s:f',ns),[])
                self.assertEqual(sheet.findall('.//s:hyperlink',ns),[])
                for name in names:
                    if name.endswith('.rels'):
                        self.assertNotIn(b'TargetMode="External"',z.read(name))
                observed=[c.find('s:is/s:t',ns).text for c in cells[1:]]
                # Only XML-invalid NUL/ESC become replacement glyphs in the export.
                self.assertEqual(observed,[x.replace('\x00','\ufffd').replace('\x1b','\ufffd') for x in payloads])

    def test_invalid_xml_characters_replaced_in_export_only(self):
        original = '\x00=1+1\x1b\ud800\ufffe\uffff'
        expected = '\ufffd=1+1' + '\ufffd'*4
        self.assertEqual(literal_xml_text(original), expected)
        # Input value is unchanged; the helper returns only a display representation.
        self.assertEqual(original[0], '\x00')

if __name__=='__main__':unittest.main()
