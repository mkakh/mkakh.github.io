import unittest
from datetime import date
from unittest.mock import patch

from scripts.update_conferences import (
    extract_compsac_deadline,
    extract_eics_deadline,
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

    def test_label_before_date_does_not_take_previous_abstract_date(self):
        text = ('Important Dates (AoE) Abstract Submission Deadline : April 09, 2027 '
                'Paper Submission Deadline : April 16, 2027 '
                'Author Rebuttal Period : June 7, 2027')
        with patch('scripts.update_conferences.fetch_text', return_value=text):
            self.assertEqual(
                extract_researchr_deadlines('https://conf.researchr.org/track/issre-2027/issre-2027-papers'),
                ('2027-04-09', '2027-04-16'),
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

    def test_eics_selects_next_full_paper_round_without_losing_last_round(self):
        url = 'https://eics.acm.org/2027/contributions/full-papers.md'
        text = ('### EICS PACM 2027, Round 1 - Paper submissions: Jul 23, 2026 '
                '- Notification of reviews: Sep 23, 2026 '
                '### Round 2 - Paper submissions: Nov 12, 2026 '
                '### Round 3 - Paper submissions: Feb 19, 2027 '
                '- Rebuttal deadline: Apr 2, 2027')
        with patch('scripts.update_conferences.fetch_text', return_value=text):
            self.assertEqual(extract_eics_deadline(url, date(2026, 11, 7)), '2026-11-12')
            self.assertEqual(extract_eics_deadline(url, date(2026, 11, 13)), '2027-02-19')
            self.assertIsNone(extract_eics_deadline(url, date(2027, 2, 20)))
            self.assertIsNone(extract_eics_deadline('https://eics.acm.org/2028/contributions/full-papers.md', date(2026, 11, 7)))
            conf = [dict(acronym='EICS', url=url, deadline='N/A', fullDeadline='2026-11-12')]
            after = update_known_page_deadlines(conf, date(2026, 11, 13))
            self.assertEqual(after[0]['fullDeadline'], '2027-02-19')
            self.assertEqual(reset_expired_full_deadlines(after, date(2026, 11, 13))[0]['fullDeadline'], '2027-02-19')

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
