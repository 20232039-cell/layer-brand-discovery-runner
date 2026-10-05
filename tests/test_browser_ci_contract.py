from pathlib import Path
import unittest

class BrowserCIContractTests(unittest.TestCase):
    def test_synthetic_workflow_has_no_private_transfer_or_outputs(self):
        root=Path(__file__).resolve().parents[1]
        workflow=(root/'.github/workflows/browser-synthetic-ci.yml').read_text()
        for banned in ['secrets.','DATA_TOKEN','DATA_REPOSITORY','private_sync','upload-artifact','download-artifact','actions/cache','schedule:','GITHUB_OUTPUT','GITHUB_STEP_SUMMARY']:
            self.assertNotIn(banned,workflow)
        self.assertIn('contents: read',workflow)
        self.assertIn('persist-credentials: false',workflow)
        self.assertIn('https://pypi.org/simple',workflow)
    def test_browser_fixtures_never_navigate_or_record(self):
        root=Path(__file__).resolve().parents[1]
        code=(root/'browser_tests/test_offline_browser.py').read_text()
        self.assertIn('offline=True',code)
        self.assertIn('route.abort()',code)
        self.assertIn('set_content(',code)
        for banned in ['.goto(','.request.get(','.screenshot(','.tracing.start(','record_video','record_har','storage_state=', 'user_agent=', 'proxy=']:
            self.assertNotIn(banned,code)

if __name__=='__main__':unittest.main()
