"""
最小前提探索の回帰テストスイート (Test Minimal Assumption Search)
"""
import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.semantics import (
    KnowledgeBase,
    Proposition,
    InferenceRule,
    Literal,
    TruthStatus,
)
from engine.search import MinimalAssumptionSearch


class TestSearchRegression(unittest.TestCase):
    def test_subset_vs_cardinality_minimality(self):
        """包含極小 (subset-minimal) と 要素数最小 (cardinality-minimal) の区別"""
        # ルート1: A (要素数1) -> Q
        # ルート2: B, C (要素数2) -> Q
        # 双方とも包含極小解であるが、要素数最小解は ルート1 のみ
        a = Proposition("A", "A", "", "definition")
        b = Proposition("B", "B", "", "definition")
        c = Proposition("C", "C", "", "definition")
        q = Proposition("Q", "Q", "", "proposition")

        r1 = InferenceRule("R1", (Literal("A", True),), Literal("Q", True))
        r2 = InferenceRule("R2", (Literal("B", True), Literal("C", True)), Literal("Q", True))

        kb = KnowledgeBase("KB_Search", [a, b, c, q], [r1, r2])
        searcher = MinimalAssumptionSearch(kb)

        res = searcher.find_assumptions_for_target("Q", target_sign=True)

        self.assertTrue(res.is_complete)
        self.assertFalse(res.unverified_minimality)

        # 要素数最小解は [A] のみ (サイズ 1)
        card_min_sets = [set(s.assumptions) for s in res.cardinality_minimal_solutions]
        self.assertEqual(len(card_min_sets), 1)
        self.assertIn({Literal("A", True)}, card_min_sets)

        # 包含極小解は [A] と [B, C] の両方
        subset_min_sets = [set(s.assumptions) for s in res.subset_minimal_solutions]
        self.assertEqual(len(subset_min_sets), 2)
        self.assertIn({Literal("A", True)}, subset_min_sets)
        self.assertIn({Literal("B", True), Literal("C", True)}, subset_min_sets)

    def test_target_self_assumption_forbidden_by_default(self):
        """目標命題そのものの仮定は初期設定で禁止される"""
        q = Proposition("Q", "Q", "", "definition")
        kb = KnowledgeBase("KB_Self", [q])
        searcher = MinimalAssumptionSearch(kb)

        # allow_target_as_assumption=False の場合、Q 自体は仮定候補から除外され、解は見つからない
        res = searcher.find_assumptions_for_target("Q", allow_target_as_assumption=False)
        self.assertEqual(len(res.subset_minimal_solutions), 0)

        # allow_target_as_assumption=True の場合、{Q} が解として見つかる
        res_allow = searcher.find_assumptions_for_target("Q", allow_target_as_assumption=True)
        self.assertEqual(len(res_allow.subset_minimal_solutions), 1)
        self.assertEqual(res_allow.subset_minimal_solutions[0].assumptions, (Literal("Q", True),))

    def test_unverified_minimality_on_cutoff(self):
        """探索打ち切り時は最小性未確認と表示される"""
        # 多数の候補がある状態で試行上限を極小にする
        props = [Proposition(f"P{i}", f"P{i}", "", "definition") for i in range(10)]
        q = Proposition("Q", "Q", "", "proposition")
        # P9 からのみ Q が導出されるが、P9 を試す前に上限に達する
        r = InferenceRule("R", (Literal("P9", True),), Literal("Q", True))

        kb = KnowledgeBase("KB_Cutoff", props + [q], [r])
        searcher = MinimalAssumptionSearch(kb)

        # max_evaluations=3 で打ち切り
        res = searcher.find_assumptions_for_target("Q", max_evaluations=3)
        self.assertFalse(res.is_complete)
        self.assertTrue(res.unverified_minimality)


if __name__ == "__main__":
    unittest.main()
