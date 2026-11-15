"""Retrieval tests. No API key, no network, no third-party packages."""

from __future__ import annotations

import unittest

from litlens import config, corpus, retrieval

# (question, source_key that the top hit must belong to)
IN_DOMAIN = [
    ("What do users adjust in TasteWeights?", "bostandjiev2012"),
    ("TasteWeights 让用户调整什么？", "bostandjiev2012"),
    ("什么是信息茧房", "pariser2011"),
    ("用户的信任应该如何校准", "leessee2004"),
    ("为什么用户分辨不出不同推荐算法", "ekstrand2014"),
    ("How many guidelines does Amershi propose for human-AI interaction?", "amershi2019"),
    ("解释有哪些目标", "tintarev2015"),
    ("direct manipulation 有哪些特征", "shneiderman1983"),
    ("混合主动原则要求权衡什么", "horvitz1999"),
    ("检索增强生成有什么局限", "lewis2020"),
]

OFF_TOPIC = [
    "How do I bake sourdough bread?",
    "今天北京天气怎么样",
    "Recommend a good laptop for gaming",
    "Who won the 2026 World Cup?",
    "写一段 Python 快排代码",
]


class TestRetrieval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = corpus.get_index()

    def test_in_domain_questions_reach_the_expected_source(self):
        for question, expected in IN_DOMAIN:
            with self.subTest(question=question):
                hits = self.index.search(question, k=config.TOP_K)
                self.assertTrue(hits, "no hit returned")
                source = hits[0]["doc"]["raw"].get("source_key")
                self.assertEqual(source, expected, f"top hit was {hits[0]['id']}")

    def test_in_domain_scores_clear_the_abstention_threshold(self):
        for question, _ in IN_DOMAIN:
            with self.subTest(question=question):
                self.assertGreater(self.index.best_score(question), config.MIN_SCORE)

    def test_off_topic_questions_fall_below_the_threshold(self):
        for question in OFF_TOPIC:
            with self.subTest(question=question):
                self.assertLess(self.index.best_score(question), config.MIN_SCORE)

    def test_naming_a_source_boosts_its_notes(self):
        hits = self.index.search("what does TasteWeights do", k=1)
        self.assertEqual(hits[0]["doc"]["raw"]["source_key"], "bostandjiev2012")
        self.assertGreaterEqual(hits[0]["score"], retrieval.SOURCE_BOOST)

    def test_alias_needs_every_token_of_the_registered_name(self):
        tokens = set(retrieval.tokenize("what is direct manipulation"))
        self.assertTrue(retrieval._alias_matches(tokens, ["direct manipulation"]))
        tokens = set(retrieval.tokenize("is manipulation always good"))
        self.assertFalse(retrieval._alias_matches(tokens, ["direct manipulation"]))

    def test_k_limits_and_orders_results(self):
        hits = self.index.search("用户控制与信任", k=2)
        self.assertEqual(len(hits), 2)
        self.assertGreaterEqual(hits[0]["score"], hits[1]["score"])

    def test_empty_query_returns_nothing(self):
        self.assertEqual(self.index.search("   ", k=3), [])

    def test_chinese_and_english_queries_reach_the_same_source(self):
        en = self.index.search("filter bubble personalisation", k=1)[0]
        zh = self.index.search("信息茧房 个性化", k=1)[0]
        self.assertEqual(
            en["doc"]["raw"]["source_key"], zh["doc"]["raw"]["source_key"]
        )


if __name__ == "__main__":
    unittest.main()
