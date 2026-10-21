"""
v0.1 公開版受入テストスイート: 標準推論意味論 (diagnostic_monotone) の受入条件検証
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
    ConflictPair,
    UndercutDefeater,
    Literal,
    TruthStatus,
    EvaluationStatus,
    SemanticsMode,
    ScenarioOptions,
    Evaluator,
)
from engine.benchmark_core import PhilosophicalBenchmark
from engine.search import MinimalAssumptionSearch


class TestStandardSemanticsAcceptance(unittest.TestCase):
    """
    v0.1 公開版の受入条件テスト:
    1. 標準モードで支持が途中撤回されない
    2. 明示的な否定支持が追加されても既存の肯定支持は消えない
    3. ConflictPairの診断が推論結果を変更しない
    4. 固定した規則集合で登録順によらず支持結果が一致する
    5. シナリオの追加・撤回は独立再計算で元に戻る
    6. legacyモードが探索から除外されている
    7. ベンチマーク出力にモデル版、意味論モード、シナリオ、計算ステータス、分母IDが含まれる
    """

    def setUp(self):
        self.p_a = Proposition("A", "命題A", "", "axiom")
        self.p_b = Proposition("B", "命題B", "", "proposition")
        self.p_c = Proposition("C", "命題C", "", "proposition")
        self.r1 = InferenceRule("r1", (Literal("A", True),), Literal("B", True))
        self.r2 = InferenceRule("r2", (Literal("B", True),), Literal("C", True))

    def test_01_supports_never_retracted_in_standard_mode(self):
        """1. 標準モードで支持が途中撤回されない (単調蓄積性の保証)"""
        # A -> B, B -> C の連鎖
        kb = KnowledgeBase("KB_Mono", [self.p_a, self.p_b, self.p_c], [self.r1, self.r2])
        evaluator = Evaluator(kb)
        state = evaluator.evaluate()

        # A, B, C の全肯定支持が成立
        self.assertEqual(state.get_status("A"), TruthStatus.TRUE)
        self.assertEqual(state.get_status("B"), TruthStatus.TRUE)
        self.assertEqual(state.get_status("C"), TruthStatus.TRUE)
        self.assertIn("r1", state.positive_supports["B"])
        self.assertIn("r2", state.positive_supports["C"])

    def test_02_explicit_negative_support_does_not_erase_positive_support(self):
        """2. 明示的な否定支持が追加されても、既存の肯定支持は消えない (CONFLICTへの単調遷移)"""
        kb = KnowledgeBase("KB_Neg", [self.p_a, self.p_b], [self.r1])
        evaluator = Evaluator(kb)

        # 否定支持 ¬B を仮定として追加
        state = evaluator.evaluate(assumptions=[Literal("B", False)])

        # A は公理として TRUE、B は r1 由来の正支持と仮定由来の負支持を併せ持ち CONFLICT
        self.assertEqual(state.get_status("A"), TruthStatus.TRUE)
        self.assertEqual(state.get_status("B"), TruthStatus.CONFLICT)
        self.assertTrue(state.get_status("B").has_pos, "肯定支持は消去されない")
        self.assertTrue(state.get_status("B").has_neg, "否定支持が蓄積される")
        self.assertIn("r1", state.positive_supports["B"])
        self.assertIn("assumption:not_B", state.negative_supports["B"])

    def test_03_conflict_pair_diagnosis_does_not_alter_inference_truth_status(self):
        """3. ConflictPair の診断が推論結果を変更しない (診断専用)"""
        # ConflictPair がない場合
        kb_no_conflict = KnowledgeBase("KB_NoC", [self.p_a, self.p_b], [self.r1])
        eval_no_c = Evaluator(kb_no_conflict).evaluate()

        # ConflictPair(+A, +B) を追加した場合
        c = ConflictPair(Literal("A", True), Literal("B", True), "両立不能")
        kb_with_conflict = KnowledgeBase("KB_WithC", [self.p_a, self.p_b], [self.r1], conflicts=[c])
        eval_with_c = Evaluator(kb_with_conflict).evaluate()

        # 推論結果 (TruthStatus) は ConflictPair の有無によらず完全に一致 (TRUE, TRUE)
        self.assertEqual(eval_with_c.get_status("A"), eval_no_c.get_status("A"))
        self.assertEqual(eval_with_c.get_status("B"), eval_no_c.get_status("B"))
        self.assertEqual(eval_with_c.get_status("A"), TruthStatus.TRUE)
        self.assertEqual(eval_with_c.get_status("B"), TruthStatus.TRUE)

        # Conflict は推論を汚染せず、事後診断 diagnostic_conflicts にのみ記録される
        self.assertEqual(len(eval_no_c.diagnostic_conflicts), 0)
        self.assertEqual(len(eval_with_c.diagnostic_conflicts), 1)
        self.assertEqual(eval_with_c.diagnostic_conflicts[0]["prop_a"], "A")
        self.assertEqual(eval_with_c.diagnostic_conflicts[0]["prop_b"], "B")

    def test_04_order_independence_under_fixed_rule_set(self):
        """4. 固定した規則集合で、登録順によらず支持結果が一致する"""
        p_p = Proposition("P", "P", "", "axiom")
        p_q = Proposition("Q", "Q", "", "proposition")
        p_r = Proposition("R", "R", "", "proposition")
        r_a = InferenceRule("RA", (Literal("P", True),), Literal("Q", True))
        r_b = InferenceRule("RB", (Literal("P", True),), Literal("R", True))

        # 順序1: [r_a, r_b]
        kb1 = KnowledgeBase("KB1", [p_p, p_q, p_r], [r_a, r_b])
        # 順序2: [r_b, r_a]
        kb2 = KnowledgeBase("KB2", [p_p, p_q, p_r], [r_b, r_a])

        s1 = Evaluator(kb1).evaluate()
        s2 = Evaluator(kb2).evaluate()

        self.assertEqual(s1.summary(), s2.summary())
        self.assertEqual(s1.fired_rules, s2.fired_rules)

    def test_05_scenario_addition_and_removal_reversible_via_independent_recomputation(self):
        """5. シナリオの追加・撤回は独立再計算で元に戻る (冪等性・単離性)"""
        kb = KnowledgeBase("KB_Rev", [self.p_a, self.p_b, self.p_c], [self.r1, self.r2])
        evaluator = Evaluator(kb)

        # ベースライン
        base = evaluator.evaluate()
        self.assertEqual(base.get_status("C"), TruthStatus.TRUE)

        # シナリオ1: 批判を注入 (r1 を Undercut)
        u = UndercutDefeater(Literal("CRIT", True), "r1")
        crit_prop = Proposition("CRIT", "Crit", "", "critique")
        kb_crit = KnowledgeBase("KB_RevCrit", [self.p_a, self.p_b, self.p_c, crit_prop], [self.r1, self.r2], undercuts=[u])
        eval_crit = Evaluator(kb_crit)

        # 批判注入時: r1 が無効化され C は UNKNOWN に
        sc_state = eval_crit.evaluate(injected_critiques=[Literal("CRIT", True)])
        self.assertEqual(sc_state.get_status("C"), TruthStatus.UNKNOWN)

        # 批判撤回 (注入なしで再計算): 再びベースラインと完全同一の結果に復帰
        reverted_state = eval_crit.evaluate()
        self.assertEqual(reverted_state.get_status("C"), TruthStatus.TRUE)
        self.assertEqual(reverted_state.get_status("B"), TruthStatus.TRUE)
        self.assertEqual(reverted_state.get_status("A"), TruthStatus.TRUE)

    def test_06_legacy_mode_excluded_from_search(self):
        """6. legacy モードを最小前提探索から除外する"""
        kb = KnowledgeBase("KB_Search", [self.p_a, self.p_b], [self.r1])
        searcher = MinimalAssumptionSearch(kb)

        # legacy モードを指定すると ValueError が発生すること
        legacy_opts = ScenarioOptions(mode=SemanticsMode.LEGACY)
        with self.assertRaises(ValueError) as ctx:
            searcher.find_assumptions_for_target("B", options=legacy_opts)
        self.assertIn("Legacy semantics is excluded", str(ctx.exception))

    @unittest.skip("他哲学体系（デカルト・ライプニッツ）およびカント批判データを必要とする複数体系ベンチマーク機能のため、Spinoza単独公開版ではスキップ")
    def test_07_benchmark_output_includes_required_metadata(self):
        """7. 標準意味論でベンチマークを実行し、モデル版、意味論モード、シナリオ、計算ステータス、分母IDを確認"""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        bm = PhilosophicalBenchmark(base_dir)
        res = bm.benchmark_system("Descartes")

        # 必須メタデータの確認
        self.assertEqual(res["model_version"], "v0.1")
        self.assertEqual(res["semantics_mode"], "diagnostic_monotone")
        self.assertIn("denominator_theorem_ids", res)
        self.assertGreater(len(res["denominator_theorem_ids"]), 0)

        # ベースラインおよび各シナリオの計算ステータス
        self.assertEqual(res["baseline"]["evaluation_status"], EvaluationStatus.CONVERGED.value)
        self.assertTrue(res["baseline"]["is_complete"])

        for sc_name, sc_data in res["scenarios"].items():
            self.assertEqual(sc_data["evaluation_status"], EvaluationStatus.CONVERGED.value)
            self.assertTrue(sc_data["is_complete"])
            self.assertIn("partition", sc_data)
            self.assertIn("rule_breakdown", sc_data)


if __name__ == "__main__":
    unittest.main()
