"""Behavioral regressions for the trusted-base conference PR gate."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_conference_pr as gate


BASE = [
    {"acronym": "ASE", "title": "Automated Software Engineering", "rank": "A*",
     "rating": "5.0", "deadline": "N/A", "fullDeadline": "N/A",
     "url": "https://conf.researchr.org/series/ase"},
    {"acronym": "DSN", "title": "Dependable Systems", "rank": "A",
     "rating": "N/A", "deadline": "2028-02-29", "fullDeadline": "2028-03-01",
     "url": "https://example.org/dsn"},
]


class ConferenceGateTests(unittest.TestCase):
    def test_deadline_and_official_url_update_is_allowed(self):
        updated = copy.deepcopy(BASE)
        updated[0]["deadline"] = "2028-02-29"
        updated[0]["fullDeadline"] = "2028-03-01"
        updated[0]["url"] = "https://conf.researchr.org/track/ase-2028/ase-2028-papers"
        gate.validate_rows(BASE, updated)

    def test_master_list_cannot_gain_lose_or_reorder_rows(self):
        for changed in (BASE[:1], BASE + [dict(BASE[0], acronym="NEW")],
                        list(reversed(BASE))):
            with self.subTest(changed=[row["acronym"] for row in changed]):
                with self.assertRaises(gate.InvalidPR):
                    gate.validate_rows(BASE, changed)

    def test_rank_title_and_acronym_are_not_deadline_fields(self):
        for field, value in (("rank", "B"),
                             ("title", "Other conference"), ("acronym", "XSE")):
            with self.subTest(field=field):
                changed = copy.deepcopy(BASE)
                changed[0][field] = value
                with self.assertRaises(gate.InvalidPR):
                    gate.validate_rows(BASE, changed)

    def test_justified_rating_change_is_syntactically_allowed_but_invalid_ratings_fail(self):
        changed = copy.deepcopy(BASE)
        changed[0]["rating"] = "4.9"
        gate.validate_rows(BASE, changed)
        for value in ("5.9", "-1.0", "excellent", 4.9):
            changed[0]["rating"] = value
            with self.subTest(value=value), self.assertRaises(gate.InvalidPR):
                gate.validate_rows(BASE, changed)

    def test_invalid_calendar_dates_and_unapproved_extra_field_rejected(self):
        for value in ("2027-02-29", "2028-02-30", "2028-2-09", "next week", ""):
            with self.subTest(value=value):
                changed = copy.deepcopy(BASE)
                changed[0]["deadline"] = value
                with self.assertRaises(gate.InvalidPR):
                    gate.validate_rows(BASE, changed)
        changed = copy.deepcopy(BASE)
        changed[0]["timezone"] = "AoE"
        with self.assertRaises(gate.InvalidPR):
            gate.validate_rows(BASE, changed)

    def test_script_and_credential_urls_are_not_published(self):
        for url in ("javascript:alert(1)", "https://example.org/\" onmouseover=\"x",
                    "https://example.org/</script>", "https://user:pass@example.org/x",
                    "https://localhost/x", "https://127.0.0.1/x", "https://example.org/%zz"):
            with self.subTest(url=url):
                changed = copy.deepcopy(BASE)
                changed[0]["url"] = url
                with self.assertRaises(gate.InvalidPR):
                    gate.validate_rows(BASE, changed)

    def test_unrelated_pr_changes_fail_even_if_data_is_modified(self):
        gate.validate_changed_paths([gate.DATA, "index.html", "version.json"])
        with self.assertRaises(gate.InvalidPR):
            gate.validate_changed_paths([gate.DATA, "scripts/check_conference_pr.py"])

    def test_embedded_html_and_version_must_match_data(self):
        data = copy.deepcopy(BASE)
        fingerprint = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                            separators=(",", ":")).encode()).hexdigest()[:16]
        html = ("<script>\nconst BUILD_VERSION = " + json.dumps(fingerprint)
                + ";\nconst DATA = " + json.dumps(data, ensure_ascii=False, indent=2)
                + ";\n</script>")
        version = {"version": fingerprint}
        gate.validate_version(data, html, version)
        changed = copy.deepcopy(data)
        changed[0]["deadline"] = "2028-02-29"
        with self.assertRaises(gate.InvalidPR):
            gate.validate_version(changed, html, version)
        with self.assertRaises(gate.InvalidPR):
            gate.validate_version(data, html.replace("2028-02-29", "2028-02-28"), version)
        with self.assertRaises(gate.InvalidPR):
            gate.validate_version(data, html, {"version": "0" * 16})

    def test_duplicate_json_keys_are_rejected_instead_of_silently_overridden(self):
        with self.assertRaises(gate.InvalidPR):
            gate.decode_json(b'{"version":"safe","version":"forged"}', "version")


if __name__ == "__main__":
    unittest.main()
