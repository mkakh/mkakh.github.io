import hashlib
import json
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublishedDataTests(unittest.TestCase):
    def test_master_deadlines_and_generated_site(self):
        entries = json.loads((ROOT / 'data/conferences.json').read_text())
        acronyms = [c['acronym'] for c in entries]
        self.assertEqual(len(acronyms), 146)
        self.assertNotIn('IFM', acronyms)
        self.assertIn('iFS', acronyms)
        self.assertEqual(len(acronyms), len(set(acronyms)))
        today = date.today()
        for c in entries:
            with self.subTest(acronym=c['acronym']):
                abstract = None if c['deadline'] == 'N/A' else date.fromisoformat(c['deadline'])
                full = None if c['fullDeadline'] == 'N/A' else date.fromisoformat(c['fullDeadline'])
                if abstract and full:
                    self.assertLessEqual(abstract, full)
                if full:
                    self.assertGreaterEqual(full, today)
                self.assertTrue(c['url'].startswith(('https://', 'http://')))
        html = (ROOT / 'index.html').read_text()
        data_start = html.index('const DATA = ') + len('const DATA = ')
        data_end = html.index(';', data_start)
        self.assertEqual(json.loads(html[data_start:data_end]), entries)
        canonical = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        version = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        self.assertEqual(json.loads((ROOT / 'version.json').read_text()), {'version': version})
        self.assertIn('const BUILD_VERSION = "' + version + '";', html)


if __name__ == '__main__':
    unittest.main()
