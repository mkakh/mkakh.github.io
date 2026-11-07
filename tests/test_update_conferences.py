import unittest
from datetime import date
from unittest.mock import patch

from scripts.update_conferences import (
    extract_compsac_deadline,
    extract_researchr_deadlines,
    reset_expired_full_deadlines,
    update_known_page_deadlines,
)


class OfficialDeadlineTests(unittest.TestCase):
    def test_researchr_dates_belong_to_preceding_labels(self):
        text = (
            'Important Dates AoE (UTC-12h) Mon 4 Jan 2027 Abstract Submission Deadline '
            'Mon 11 Jan 2027 Paper Submission Deadline '
            'Fri 26 Feb 2027 Author Notification'
        )
        with patch('scripts.update_conferences.fetch_text', return_value=text):
            self.assertEqual(
                extract_researchr_deadlines('https://conf.researchr.org/home/nfm-2027'),
                ('2027-01-04', '2027-01-11'),
            )

    def test_researchr_generic_submission_label(self):
        text = ('Fri 15 Jan 2027 Abstract Submission deadline '
                'Fri 22 Jan 2027 Submission deadline '
                'Fri 12 Mar 2027 Notification')
        with patch('scripts.update_conferences.fetch_text', return_value=text):
            self.assertEqual(
                extract_researchr_deadlines('https://conf.researchr.org/track/ease-2027'),
                ('2027-01-15', '2027-01-22'),
            )

    def test_updated_researchr_date_takes_priority(self):
        text = ('Fri 15 Jan 2027 Abstract Submission Deadline '
                'Fri 22 Jan 2027 updated Abstract Submission Deadline '
                'Fri 29 Jan 2027 Paper Submission Deadline')
        with patch('scripts.update_conferences.fetch_text', return_value=text):
            self.assertEqual(
                extract_researchr_deadlines('https://conf.researchr.org/track/example-2027'),
                ('2027-01-22', '2027-01-29'),
            )

    def test_compsac_year_specific_full_paper_only(self):
        text = ('Workshop proposals due October 15, 2026 '
                'Full papers due January 31, 2027 Paper notification April 7, 2027')
        with patch('scripts.update_conferences.fetch_text', return_value=text) as fetch:
            self.assertEqual(extract_compsac_deadline(
                'https://ieeecompsac.computer.org/2027/information-for-authors/'),
                '2027-01-31')
            self.assertIsNone(extract_compsac_deadline('https://ieeecompsac.computer.org/'))
            self.assertIsNone(extract_compsac_deadline(
                'https://ieeecompsac.computer.org/2028/information-for-authors/'))
            self.assertEqual(fetch.call_count, 2)

    def test_refresh_and_expiry(self):
        conferences = [
            dict(acronym='COMPSAC', url='https://ieeecompsac.computer.org/2027/information-for-authors/',
                 deadline='N/A', fullDeadline='N/A'),
        ]
        with patch('scripts.update_conferences.fetch_text', return_value='Full papers due January 31, 2027'):
            updated = update_known_page_deadlines(conferences)
        self.assertEqual(updated[0]['deadline'], '2027-01-31')
        self.assertEqual(updated[0]['fullDeadline'], '2027-01-31')
        self.assertEqual(reset_expired_full_deadlines(updated, date(2027, 2, 1))[0]['fullDeadline'], 'N/A')
        self.assertEqual(conferences[0]['fullDeadline'], 'N/A')


if __name__ == '__main__':
    unittest.main()
