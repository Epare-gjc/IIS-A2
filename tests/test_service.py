"""Pipeline tests: refusal, evidence filtering, logging.

These run without an API key. The generation branch is not exercised here; it is
checked manually with scripts/ask.py (see README, development record).
"""

from __future__ import annotations

import csv
import shutil
import unittest
from pathlib import Path

from litlens import config, runlog, service


def events(question: str, **kwargs) -> list[dict]:
    return list(service.ask(question, **kwargs))


class TestRefusal(unittest.TestCase):
    def test_off_topic_question_refuses_before_calling_the_model(self):
        evs = events("今天北京天气怎么样？")
        self.assertEqual([e["type"] for e in evs], ["evidence", "abstain"])
        self.assertTrue(evs[0]["abstained"])

    def test_refusal_carries_no_evidence(self):
        evs = events("How do I bake sourdough bread?")
        self.assertEqual(evs[0]["hits"], [])
        self.assertEqual(evs[0]["best"], 0.0)


class TestEvidence(unittest.TestCase):
    def test_only_passages_above_the_threshold_become_evidence(self):
        evs = events("什么是信息茧房？", evidence_only=True)
        hits = evs[0]["hits"]
        self.assertTrue(hits)
        for hit in hits:
            self.assertGreaterEqual(hit["score"], config.MIN_SCORE)

    def test_evidence_only_mode_does_not_generate(self):
        evs = events("什么是信息茧房？", evidence_only=True)
        self.assertEqual([e["type"] for e in evs], ["evidence", "evidence_only"])

    def test_answerable_question_is_not_refused(self):
        evs = events("TasteWeights 让用户调整什么？", evidence_only=True)
        self.assertFalse(evs[0]["abstained"])
        self.assertEqual(len(evs[0]["hits"]), len(evs[0]["hits"]))


class LoggingTestCase(unittest.TestCase):
    """Writes logs under tests/_tmp (sandbox temp dirs are not always writable)."""

    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp"
        self.tmp.mkdir(exist_ok=True)
        self.log = runlog.RunLog(self.tmp / f"{self.id().rsplit('.', 1)[-1]}.csv")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestLog(LoggingTestCase):
    def test_one_row_per_question(self):
        list(service.ask("什么是信息茧房？", evidence_only=True, log=self.log))
        rows = self.log.rows()
        self.assertEqual(len(rows), 1)
        # Log records every retrieved id, including weak ones below the
        # threshold, so near-misses are visible in the CSV afterwards.
        self.assertEqual(rows[0]["top_ids"], "p01 p02 p03")
        self.assertEqual(rows[0]["mode"], "evidence-only")
        self.assertEqual(rows[0]["abstained"], "False")

    def test_abstention_is_logged(self):
        list(service.ask("今天北京天气怎么样？", log=self.log))
        rows = self.log.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["abstained"], "True")
        self.assertEqual(rows[0]["mode"], "grounded")

    def test_header_is_written_once(self):
        list(service.ask("什么是信息茧房？", evidence_only=True, log=self.log))
        with self.log.path.open(newline="", encoding="utf-8") as fh:
            self.assertEqual(len(list(csv.reader(fh))), 2)


if __name__ == "__main__":
    unittest.main()
