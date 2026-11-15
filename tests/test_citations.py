"""Citation-whitelist tests: the model may only cite passages it was given."""

from __future__ import annotations

import re
import unittest

from litlens import citations, prompt


class TestCitations(unittest.TestCase):
    def test_invented_citation_is_removed(self):
        clean, removed = citations.validate("Trust must be calibrated [S1][S7].", {1, 2, 3})
        self.assertEqual(clean, "Trust must be calibrated [S1].")
        self.assertEqual(removed, [7])

    def test_valid_citations_are_kept_untouched(self):
        text = "Two aims conflict [S1][S3]."
        clean, removed = citations.validate(text, {1, 2, 3})
        self.assertEqual(clean, text)
        self.assertEqual(removed, [])

    def test_grouped_citations_are_normalised(self):
        self.assertEqual(citations.normalise("[S1, S2]"), "[S1][S2]")
        clean, _ = citations.validate("Both [S1, S2] apply.", {1, 2})
        self.assertEqual(clean, "Both [S1][S2] apply.")

    def test_citation_outside_range_when_fewer_passages_were_sent(self):
        clean, removed = citations.validate("Claim [S2][S3].", {1, 2})
        self.assertEqual(clean, "Claim [S2].")
        self.assertEqual(removed, [3])

    def test_duplicates_are_preserved_but_listed_once(self):
        clean, removed = citations.validate("[S1] and again [S1]", {1})
        self.assertEqual(clean, "[S1] and again [S1]")
        self.assertEqual(removed, [])

    def test_whitespace_is_tidied_after_removal(self):
        clean, _ = citations.validate("Point [S9] made here.", {1})
        self.assertEqual(clean, "Point made here.")

    def test_cited_lists_ids_in_order(self):
        self.assertEqual(citations.cited("[S3] then [S1] then [S3]"), [3, 1])


class TestPrompt(unittest.TestCase):
    def setUp(self):
        from litlens import corpus

        self.passages = [p for p in corpus.load_passages() if p["id"] in {"p01", "p05"}]

    def test_passages_are_numbered_from_one(self):
        system = prompt.build_system(self.passages)
        headers = re.findall(r"^\[S(\d+)\] ", system, re.MULTILINE)
        self.assertEqual(headers, ["1", "2"])
        self.assertIn("[S1]", system)
        self.assertIn("[S2]", system)

    def test_both_languages_are_included_for_each_passage(self):
        system = prompt.build_system(self.passages)
        for p in self.passages:
            self.assertIn(p["en"][:40], system)
            self.assertIn(p["zh"][:12], system)

    def test_messages_have_system_then_user(self):
        messages = prompt.build_messages("什么是信息茧房", self.passages)
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertEqual(messages[1]["content"], "什么是信息茧房")

    def test_insufficient_sentinel_is_detected(self):
        self.assertTrue(prompt.is_insufficient(prompt.INSUFFICIENT + " 缺少来源"))
        self.assertFalse(prompt.is_insufficient("用户在 TasteWeights 中调整权重 [S1]"))


if __name__ == "__main__":
    unittest.main()
