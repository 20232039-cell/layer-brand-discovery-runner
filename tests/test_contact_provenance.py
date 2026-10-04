import unittest
from brand_discovery.collector import extract

class ContactEvidenceTests(unittest.TestCase):
    def test_anchor_target_label_conflict(self):
        r=extract('https://example.invalid/','<a href="mailto:alpha@example.invalid">beta@example.invalid</a>')
        e=r['email_link_evidence'][0]
        self.assertEqual(e['mailto_target'],'alpha@example.invalid')
        self.assertEqual(e['static_anchor_label'],'beta@example.invalid')
        self.assertIn('mailto_target_differs_from_anchor_label',e['discrepancy_flags'])
        self.assertEqual(e['official_contact_status'],'unverified')
    def test_generic_label_and_different_footer(self):
        r=extract('https://example.invalid/','<a href="mailto:alpha@example.invalid">Email us</a><footer>Contact: beta @example.invalid</footer>')
        self.assertEqual(r['email_text_evidence'][0]['address'],'beta@example.invalid')
        self.assertEqual(r['email_link_evidence'][0]['static_anchor_label'],'Email us')
        self.assertIn('mailto_target_absent_from_other_observed_text_addresses',r['email_link_evidence'][0]['discrepancy_flags'])
        self.assertEqual(r['email_contact_status'],'unverified_review_discrepancies')
    def test_matching_contact_stays_unverified(self):
        r=extract('https://example.invalid/','<a href="mailto:alpha@example.invalid?subject=test"><b>alpha@example.invalid</b></a>')
        self.assertEqual(r['email_link_evidence'][0]['discrepancy_flags'],[])
        self.assertEqual(r['email_contact_status'],'unverified')
    def test_sixshop_literal_evidence_and_unknown(self):
        r=extract('https://example.invalid/','<footer>Hosting by Sixshop</footer>')
        self.assertEqual(r['platform_hints'],['sixshop'])
        self.assertEqual(r['platform_evidence'][0]['matched_literal'],'Sixshop')
        self.assertEqual(extract('https://example.invalid/','Unknown host')['platform_hints'],[])
    def test_template_dates_never_become_recency(self):
        r=extract('https://example.invalid/','<div hidden>2026 new season template settings</div><p>제목 가격</p>')
        self.assertEqual(r['recency_status'],'unverified')
        self.assertEqual(r['current_sale_status'],'unverified')
        self.assertFalse(r['rendered_visibility_verified'])
        self.assertNotIn('visible_text_excerpt',r)
        self.assertEqual(r['evidence_schema_version'],2)

if __name__=='__main__':unittest.main()
