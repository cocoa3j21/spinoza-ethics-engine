"""
最小支持根拠・最小遮断集合 分析モジュールの単体テストスイート
(tests/test_grounds_and_cuts.py)

【テスト項目】
1. 別証明がある場合、片方だけの遮断では支持が残る
2. 全証明に共通する前提を正しく特定する
3. 基礎前提を外しても、別の規則から再導出できれば支持が残る
4. 前提の無効化が否定支持を生成しない
5. 最初から支持されていない目標を区別する
6. 探索上限時に未完了を表示する
7. 小さい合成モデルで、総当たりの期待集合と一致する
8. experimental と legacy の拒否
"""
import unittest
import os
import sys

# パス追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.semantics import (
    KnowledgeBase,
    Proposition,
    InferenceRule,
    Literal,
    TruthStatus,
    SemanticsMode,
    ScenarioOptions,
)
from engine.grounds_and_cuts import GroundsAndCutsAnalyzer, SupportGround, CutSet


class TestGroundsAndCuts(unittest.TestCase):

    def test_01_alternative_proofs_partial_cut_retains_support(self):
        """1. 別証明がある場合、片方だけの遮断では支持が残る"""
        # P1 -> Q, P2 -> Q の2つの独立した証明
        p1 = Proposition("P1", "前提1", "", "definition")
        p2 = Proposition("P2", "前提2", "", "definition")
        q = Proposition("Q", "目標", "", "proposition")

        r1 = InferenceRule("r1", (Literal("P1", True),), Literal("Q", True))
        r2 = InferenceRule("r2", (Literal("P2", True),), Literal("Q", True))

        kb = KnowledgeBase("KB_Alt", [p1, p2, q], [r1, r2])
        analyzer = GroundsAndCutsAnalyzer(kb)

        # (A) 最小支持根拠の探索: {P1} と {P2} の2つが独立した最小根拠
        grounds_res = analyzer.find_minimal_support_grounds(Literal("Q", True))
        self.assertTrue(grounds_res.is_complete)
        self.assertEqual(len(grounds_res.subset_minimal_grounds), 2)
        found_sets = {frozenset(g.premises) for g in grounds_res.subset_minimal_grounds}
        self.assertIn(frozenset([Literal("P1", True)]), found_sets)
        self.assertIn(frozenset([Literal("P2", True)]), found_sets)
        # 共通前提は空（別証明があるため）
        self.assertEqual(len(grounds_res.common_premises), 0)

        # (B) 前提の最小遮断集合: P1単体やP2単体では遮断できず、{P1, P2}の同時遮断が必要
        cuts_res = analyzer.find_minimal_cut_sets(Literal("Q", True), cut_type="premises")
        self.assertTrue(cuts_res.is_complete)
        self.assertEqual(len(cuts_res.subset_minimal_cuts), 1)
        self.assertEqual(set(cuts_res.subset_minimal_cuts[0].elements), {"P1", "P2"})
        self.assertEqual(cuts_res.subset_minimal_cuts[0].size, 2)

        # (C) 規則の最小遮断集合: r1単体やr2単体では遮断できず、{r1, r2}の同時遮断が必要
        rules_cut_res = analyzer.find_minimal_cut_sets(Literal("Q", True), cut_type="rules")
        self.assertTrue(rules_cut_res.is_complete)
        self.assertEqual(len(rules_cut_res.subset_minimal_cuts), 1)
        self.assertEqual(set(rules_cut_res.subset_minimal_cuts[0].elements), {"r1", "r2"})

    def test_02_identify_common_premises_across_proofs(self):
        """2. 全証明に共通する前提を正しく特定する"""
        # 証明1: A and B -> Q
        # 証明2: A and C -> Q
        # 共通前提は A
        p_a = Proposition("A", "公理A", "", "definition")
        p_b = Proposition("B", "定義B", "", "definition")
        p_c = Proposition("C", "定義C", "", "definition")
        q = Proposition("Q", "目標Q", "", "proposition")

        r1 = InferenceRule("r1", (Literal("A", True), Literal("B", True)), Literal("Q", True))
        r2 = InferenceRule("r2", (Literal("A", True), Literal("C", True)), Literal("Q", True))

        kb = KnowledgeBase("KB_Common", [p_a, p_b, p_c, q], [r1, r2])
        analyzer = GroundsAndCutsAnalyzer(kb)

        grounds_res = analyzer.find_minimal_support_grounds(Literal("Q", True))
        self.assertTrue(grounds_res.is_complete)
        self.assertEqual(len(grounds_res.subset_minimal_grounds), 2)
        # 共通前提として A が正しく特定される
        self.assertEqual(grounds_res.common_premises, (Literal("A", True),))

        # 前提遮断集合の探索:
        # {A} は要素数1の最小遮断集合（Aを無効化すれば両方の証明が崩壊）
        # {B, C} は要素数2の包含極小遮断集合（BとCの両方を無効化すれば崩壊）
        cuts_res = analyzer.find_minimal_cut_sets(Literal("Q", True), cut_type="premises")
        self.assertTrue(cuts_res.is_complete)
        cut_sets = [set(c.elements) for c in cuts_res.subset_minimal_cuts]
        self.assertIn({"A"}, cut_sets)
        self.assertIn({"B", "C"}, cut_sets)
        # 要素数最小は {"A"} のみ
        self.assertEqual(len(cuts_res.cardinality_minimal_cuts), 1)
        self.assertEqual(set(cuts_res.cardinality_minimal_cuts[0].elements), {"A"})

    def test_03_rederivation_retains_support_when_base_removed(self):
        """3. 基礎前提を外しても、別の規則から再導出できれば支持が残る"""
        # S -> P1
        # P1 -> Q
        # P1 を基礎前提として与えなくても、S があれば P1 が導出されて Q は支持される
        s = Proposition("S", "源泉S", "", "definition")
        p1 = Proposition("P1", "中間P1", "", "definition")
        q = Proposition("Q", "目標Q", "", "proposition")

        r_s = InferenceRule("r_s", (Literal("S", True),), Literal("P1", True))
        r_q = InferenceRule("r_q", (Literal("P1", True),), Literal("Q", True))

        kb = KnowledgeBase("KB_Rederive", [s, p1, q], [r_s, r_q])
        analyzer = GroundsAndCutsAnalyzer(kb)

        # 基礎前提として S と P1 の両方を候補とした場合
        grounds_res = analyzer.find_minimal_support_grounds(
            Literal("Q", True),
            base_premises=[Literal("S", True), Literal("P1", True)],
        )
        self.assertTrue(grounds_res.is_complete)
        found_sets = {frozenset(g.premises) for g in grounds_res.subset_minimal_grounds}
        # {P1} だけで支持可能、かつ {S} だけでも（P1が再導出されて）支持可能
        self.assertIn(frozenset([Literal("P1", True)]), found_sets)
        self.assertIn(frozenset([Literal("S", True)]), found_sets)
        self.assertEqual(len(grounds_res.subset_minimal_grounds), 2)

    def test_04_premise_deactivation_does_not_generate_negative_support(self):
        """4. 前提の無効化が否定支持を生成しない (FALSEではなくUNKNOWNのまま)"""
        p = Proposition("P", "前提P", "", "definition")
        q = Proposition("Q", "目標Q", "", "proposition")
        r = InferenceRule("r", (Literal("P", True),), Literal("Q", True))

        kb = KnowledgeBase("KB_NoNeg", [p, q], [r])
        analyzer = GroundsAndCutsAnalyzer(kb)

        cuts_res = analyzer.find_minimal_cut_sets(Literal("Q", True), cut_type="premises")
        self.assertEqual(len(cuts_res.subset_minimal_cuts), 1)
        cut = cuts_res.subset_minimal_cuts[0]
        self.assertEqual(cut.elements, ("P",))
        # 遮断された結果、目標Qは FALSE ではなく UNKNOWN に留まる
        self.assertEqual(cut.remaining_status, TruthStatus.UNKNOWN)
        self.assertFalse(cut.remaining_status.has_neg, "否定支持は生成されていない")

    def test_05_initially_unsupported_target_distinguished(self):
        """5. 最初から支持されていない目標を区別する"""
        p = Proposition("P", "前提P", "", "definition")
        q = Proposition("Q", "目標Q", "", "proposition")
        # P -> Q の規則は存在しないため、Q は最初から未支持
        kb = KnowledgeBase("KB_Unsupp", [p, q], rules=[])
        analyzer = GroundsAndCutsAnalyzer(kb)

        cuts_res = analyzer.find_minimal_cut_sets(Literal("Q", True), cut_type="premises")
        self.assertTrue(cuts_res.initially_unsupported)
        self.assertEqual(len(cuts_res.subset_minimal_cuts), 0)
        self.assertIn("最初から支持されていません", cuts_res.summary_ja())

    def test_06_eval_limit_marks_incomplete(self):
        """6. 探索上限時に未完了を表示する"""
        # 前提が多数あり、max_evaluations を小さく設定した場合
        props = [Proposition(f"P{i}", f"前提{i}", "", "definition") for i in range(10)]
        q = Proposition("Q", "目標Q", "", "proposition")
        # P0 and P1 -> Q
        r = InferenceRule("r", (Literal("P0", True), Literal("P1", True)), Literal("Q", True))

        kb = KnowledgeBase("KB_Limit", props + [q], [r])
        analyzer = GroundsAndCutsAnalyzer(kb)

        # 評価回数を極小（2回）に制限
        res = analyzer.find_minimal_support_grounds(
            Literal("Q", True),
            max_evaluations=2,
        )
        self.assertFalse(res.is_complete)
        self.assertTrue(res.eval_limit_reached)
        self.assertIn("探索未完了", res.summary_ja())

    def test_07_synthetic_model_matches_exhaustive_ground_truth(self):
        """7. 小さい合成モデルで、総当たりの期待集合と完全一致する"""
        # モデル:
        # A, B, C, D (基礎前提)
        # r1: A and B -> X
        # r2: C -> Y
        # r3: D -> Y
        # r4: X and Y -> Target
        # Targetの証明経路:
        # 1) {A, B, C} -> Target (r1, r2, r4)
        # 2) {A, B, D} -> Target (r1, r3, r4)
        p_a = Proposition("A", "A", "", "definition")
        p_b = Proposition("B", "B", "", "definition")
        p_c = Proposition("C", "C", "", "definition")
        p_d = Proposition("D", "D", "", "definition")
        x = Proposition("X", "X", "", "proposition")
        y = Proposition("Y", "Y", "", "proposition")
        target = Proposition("Target", "Target", "", "proposition")

        r1 = InferenceRule("r1", (Literal("A", True), Literal("B", True)), Literal("X", True))
        r2 = InferenceRule("r2", (Literal("C", True),), Literal("Y", True))
        r3 = InferenceRule("r3", (Literal("D", True),), Literal("Y", True))
        r4 = InferenceRule("r4", (Literal("X", True), Literal("Y", True)), Literal("Target", True))

        kb = KnowledgeBase("KB_Synthetic", [p_a, p_b, p_c, p_d, x, y, target], [r1, r2, r3, r4])
        analyzer = GroundsAndCutsAnalyzer(kb)

        # (1) 最小支持根拠の検証
        grounds_res = analyzer.find_minimal_support_grounds(Literal("Target", True))
        self.assertTrue(grounds_res.is_complete)
        self.assertEqual(len(grounds_res.subset_minimal_grounds), 2)
        found_prem_sets = {frozenset(g.to_prop_ids()) for g in grounds_res.subset_minimal_grounds}
        expected_grounds = {frozenset(["A", "B", "C"]), frozenset(["A", "B", "D"])}
        self.assertEqual(found_prem_sets, expected_grounds)
        # 共通前提: A と B
        common_ids = {p.prop_id for p in grounds_res.common_premises}
        self.assertEqual(common_ids, {"A", "B"})

        # (2) 前提遮断集合の検証
        # Target を遮断する包含極小集合:
        # {A} (Aを消すとXが立たずTarget崩壊)
        # {B} (Bを消すとXが立たずTarget崩壊)
        # {C, D} (CとDの両方を消すとYが立たずTarget崩壊)
        cuts_res = analyzer.find_minimal_cut_sets(Literal("Target", True), cut_type="premises")
        self.assertTrue(cuts_res.is_complete)
        found_cuts = {frozenset(c.elements) for c in cuts_res.subset_minimal_cuts}
        expected_cuts = {frozenset(["A"]), frozenset(["B"]), frozenset(["C", "D"])}
        self.assertEqual(found_cuts, expected_cuts)

        # 要素数最小は {"A"} と {"B"} (要素数1)
        card_cuts = {frozenset(c.elements) for c in cuts_res.cardinality_minimal_cuts}
        self.assertEqual(card_cuts, {frozenset(["A"]), frozenset(["B"])})

        # (3) 規則遮断集合の検証
        # Target を遮断する包含極小規則集合:
        # {r4} (Target導出直前の規則)
        # {r1} (X導出規則)
        # {r2, r3} (Y導出の2規則)
        rules_cut = analyzer.find_minimal_cut_sets(Literal("Target", True), cut_type="rules")
        self.assertTrue(rules_cut.is_complete)
        found_rule_cuts = {frozenset(c.elements) for c in rules_cut.subset_minimal_cuts}
        expected_rule_cuts = {frozenset(["r4"]), frozenset(["r1"]), frozenset(["r2", "r3"])}
        self.assertEqual(found_rule_cuts, expected_rule_cuts)

    def test_08_rejection_of_non_diagnostic_monotone_semantics(self):
        """8. experimental と legacy の明示的な拒否"""
        p = Proposition("P", "P", "", "definition")
        kb = KnowledgeBase("KB_Mode", [p], [])
        exp_opts = ScenarioOptions(mode=SemanticsMode.EXPERIMENTAL)
        leg_opts = ScenarioOptions(mode=SemanticsMode.LEGACY)

        with self.assertRaises(ValueError):
            GroundsAndCutsAnalyzer(kb, options=exp_opts)

        with self.assertRaises(ValueError):
            GroundsAndCutsAnalyzer(kb, options=leg_opts)


if __name__ == "__main__":
    unittest.main()
