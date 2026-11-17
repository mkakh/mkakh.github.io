import hashlib
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AOE = timezone(-timedelta(hours=12))


def current_aoe_date(now=None):
    """Keep a dated deadline visible until its Anywhere-on-Earth day ends."""
    return (now or datetime.now(timezone.utc)).astimezone(AOE).date()


class PublishedDataTests(unittest.TestCase):
    def test_aoe_deadline_boundary(self):
        self.assertEqual(current_aoe_date(datetime(2026, 11, 17, 11, 59, tzinfo=timezone.utc)), date(2026, 11, 16))
        self.assertEqual(current_aoe_date(datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)), date(2026, 11, 17))

    def test_master_deadlines_and_generated_site(self):
        entries = json.loads((ROOT / 'data/conferences.json').read_text())
        acronyms = [c['acronym'] for c in entries]
        self.assertEqual(len(acronyms), 145)
        self.assertNotIn('SPLC', acronyms)
        self.assertNotIn('ICSR', acronyms)
        self.assertIn('VARIABILITY', acronyms)
        successor = next(c for c in entries if c['acronym'] == 'VARIABILITY')
        self.assertEqual(successor['rank'], 'Unranked')
        self.assertNotIn('IFM', acronyms)
        self.assertIn('iFS', acronyms)
        self.assertEqual(len(acronyms), len(set(acronyms)))
        # Date-only site deadlines are valid through the AoE day, even on the next JST date.
        today = current_aoe_date()
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
