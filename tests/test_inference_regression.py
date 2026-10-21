"""
最優先回帰テストスイート (Regression Test Suite for Inference Semantics)

【検証対象】
1. 偽の前提だけから結論の偽を導かない (No false-from-false derivation)。
2. 複数証明の一方を遮断しても別証明が残る (Alternative proofs disjunction)。
3. 批判を追加し、撤回すると元の結果へ戻る (Reversible critique injection)。
4. ノード登録順で結果が変わらない (Order independence of nodes)。
5. 衝突ペア登録順で結果が変わらない (Order independence of conflict pairs)。
6. 同じ入力の再評価で結果が変わらない (Determinism / Idempotency)。
7. 後から成立した命題の衝突も検出する (Late conflict detection)。
8. 証明依存の循環と未定義IDを明示的に拒否する (DAG validation & undefined check)。
9. 同時実行した異なるシナリオが相互汚染しない (Scenario isolation)。
10. 集計対象の全命題が排他的4分類のどれか一つに入る (Strict four-value partition)。
"""
import concurrent.futures
import unittest
import sys
import os

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
    SemanticsMode,
    ScenarioOptions,
    Evaluator,
    CyclicDependencyError,
    UndefinedIdentifierError,
)


class TestInferenceRegression(unittest.TestCase):
    def test_01_no_false_derived_from_false_premise(self):
        """1. 偽の前提だけから結論の偽を導かない (前件否定の誤謬の防止)"""
        # P -> Q
        p = Proposition("P", "Premise P", "前提P", "definition")
        q = Proposition("Q", "Conclusion Q", "結論Q", "proposition")
        rule = InferenceRule("R1", (Literal("P", True),), Literal("Q", True))

        kb = KnowledgeBase("KB1", [p, q], [rule])
        evaluator = Evaluator(kb)

        # シナリオA: P に否定支持を与える (P = FALSE)
        state_neg = evaluator.evaluate(assumptions=[Literal("P", False)])
        self.assertEqual(state_neg.get_status("P"), TruthStatus.FALSE)
        # Q は否定支持を受けてはならない（前件否定から後件否定を導いてはならない）
        # Q は未証明 (UNKNOWN) であるべき
        self.assertEqual(
            state_neg.get_status("Q"),
            TruthStatus.UNKNOWN,
            "Pが偽であっても、P->QからQが偽(FALSE)になってはならない。UNKNOWNであるべき。"
        )

        # シナリオB: P が単に未成立 (UNKNOWN) の場合
        state_unk = evaluator.evaluate(assumptions=[])
        self.assertEqual(state_unk.get_status("P"), TruthStatus.UNKNOWN)
        self.assertEqual(state_unk.get_status("Q"), TruthStatus.UNKNOWN)

    def test_02_alternative_proofs_remain_if_one_blocked(self):
        """2. 複数証明の一方を遮断しても別証明が残る"""
        # 証明1: P1, P2 -> Q
        # 証明2: P3 -> Q
        p1 = Proposition("P1", "Premise 1", "", "definition")
        p2 = Proposition("P2", "Premise 2", "", "definition")
        p3 = Proposition("P3", "Premise 3", "", "definition")
        q = Proposition("Q", "Conclusion Q", "", "proposition")

        r1 = InferenceRule("R1", (Literal("P1", True), Literal("P2", True)), Literal("Q", True), name="Proof 1")
        r2 = InferenceRule("R2", (Literal("P3", True),), Literal("Q", True), name="Proof 2")

        # 批判 C は R1 のみを無効化 (undercut) する
        c = Proposition("C", "Critique C", "", "critique")
        undercut = UndercutDefeater(Literal("C", True), "R1", reason="C invalidates R1")

        kb = KnowledgeBase("KB2", [p1, p2, p3, q, c], [r1, r2], undercuts=[undercut])
        evaluator = Evaluator(kb)

        # 前提 P1, P2, P3 をすべて承認
        assumptions = [Literal("P1", True), Literal("P2", True), Literal("P3", True)]

        # 批判なし: Q は TRUE (R1 と R2 の両方から支持)
        state_base = evaluator.evaluate(assumptions=assumptions)
        self.assertEqual(state_base.get_status("Q"), TruthStatus.TRUE)
        self.assertIn("R1", state_base.positive_supports["Q"])
        self.assertIn("R2", state_base.positive_supports["Q"])

        # 批判 C を注入: R1 が無効化されても R2 があるため Q は TRUE を維持
        state_crit = evaluator.evaluate(assumptions=assumptions, injected_critiques=[Literal("C", True)])
        self.assertIn("R1", state_crit.undercut_rules)
        self.assertEqual(state_crit.get_status("Q"), TruthStatus.TRUE)
        self.assertNotIn("R1", state_crit.positive_supports["Q"])
        self.assertIn("R2", state_crit.positive_supports["Q"])

    def test_03_critique_injection_and_retraction(self):
        """3. 批判を追加し、撤回すると元の結果へ戻る (決定論・可逆性)"""
        p = Proposition("P", "Premise P", "", "axiom")
        q = Proposition("Q", "Theorem Q", "", "proposition")
        c = Proposition("C", "Critique C", "", "critique")
        r = InferenceRule("R", (Literal("P", True),), Literal("Q", True))
        undercut = UndercutDefeater(Literal("C", True), "R", reason="C undercuts R")

        kb = KnowledgeBase("KB3", [p, q, c], [r], undercuts=[undercut])
        evaluator = Evaluator(kb)

        # 1. 初期状態 (公理PからQが演繹)
        state1 = evaluator.evaluate()
        self.assertEqual(state1.get_status("Q"), TruthStatus.TRUE)

        # 2. 批判 C を注入 (Qの証明が無効化され、他に証明がないため Q は UNKNOWN に遷移)
        state2 = evaluator.evaluate(injected_critiques=[Literal("C", True)])
        self.assertEqual(state2.get_status("Q"), TruthStatus.UNKNOWN)

        # 3. 批判 C を撤回 (injected_critiques を空に戻す) -> 元の状態に完全一致
        state3 = evaluator.evaluate()
        self.assertEqual(state3.get_status("Q"), TruthStatus.TRUE)
        self.assertEqual(state1.summary(), state3.summary())

    def test_04_order_independence_of_nodes(self):
        """4. ノード登録順で結果が変わらない"""
        props_order_a = [
            Proposition("A", "A", "", "axiom"),
            Proposition("B", "B", "", "proposition"),
            Proposition("C", "C", "", "proposition"),
        ]
        props_order_b = [
            Proposition("C", "C", "", "proposition"),
            Proposition("A", "A", "", "axiom"),
            Proposition("B", "B", "", "proposition"),
        ]
        rules = [
            InferenceRule("R1", (Literal("A", True),), Literal("B", True)),
            InferenceRule("R2", (Literal("B", True),), Literal("C", True)),
        ]

        kb_a = KnowledgeBase("KBA", props_order_a, rules)
        kb_b = KnowledgeBase("KBB", props_order_b, rules)

        eval_a = Evaluator(kb_a).evaluate()
        eval_b = Evaluator(kb_b).evaluate()

        self.assertEqual(eval_a.summary(), eval_b.summary())

    def test_05_order_independence_of_conflict_pairs(self):
        """5. 衝突ペア登録順で結果が変わらない (標準意味論およびLegacy意味論)"""
        p1 = Proposition("P1", "P1", "", "axiom")
        p2 = Proposition("P2", "P2", "", "axiom")

        c1 = ConflictPair(Literal("P1", True), Literal("P2", True), "P1 conflicts with P2")
        c2 = ConflictPair(Literal("P2", True), Literal("P1", True), "P2 conflicts with P1")

        kb1 = KnowledgeBase("KB_C1", [p1, p2], conflicts=[c1])
        kb2 = KnowledgeBase("KB_C2", [p1, p2], conflicts=[c2])

        # (A) 標準モード (diagnostic_monotone): ConflictPair は推論の真理値を汚染せず診断専用
        eval1 = Evaluator(kb1).evaluate()
        eval2 = Evaluator(kb2).evaluate()

        self.assertEqual(eval1.get_status("P1"), TruthStatus.TRUE)
        self.assertEqual(eval1.get_status("P2"), TruthStatus.TRUE)
        self.assertEqual(len(eval1.diagnostic_conflicts), 1)
        self.assertEqual(len(eval2.diagnostic_conflicts), 1)
        self.assertEqual(eval1.summary(), eval2.summary())

        # (B) LEGACY モード: 衝突ペアにより直接 CONFLICT が生成される場合も順序不変
        leg_opts = ScenarioOptions(mode=SemanticsMode.LEGACY)
        eval1_leg = Evaluator(kb1).evaluate(options=leg_opts)
        eval2_leg = Evaluator(kb2).evaluate(options=leg_opts)
        self.assertEqual(eval1_leg.get_status("P1"), TruthStatus.CONFLICT)
        self.assertEqual(eval1_leg.get_status("P2"), TruthStatus.CONFLICT)
        self.assertEqual(eval1_leg.summary(), eval2_leg.summary())

    def test_06_determinism_same_input_same_result(self):
        """6. 同じ入力の再評価で結果が変わらない (冪等性)"""
        p = Proposition("P", "P", "", "axiom")
        q = Proposition("Q", "Q", "", "proposition")
        r = InferenceRule("R", (Literal("P", True),), Literal("Q", True))
        kb = KnowledgeBase("KBD", [p, q], [r])
        evaluator = Evaluator(kb)

        res1 = evaluator.evaluate().summary()
        res2 = evaluator.evaluate().summary()
        res3 = evaluator.evaluate().summary()

        self.assertEqual(res1, res2)
        self.assertEqual(res2, res3)

    def test_07_post_deduction_conflict_detection(self):
        """7. 後から演繹によって成立した命題同士の衝突も確実に検出する"""
        # 前提 P1 -> 定理 T1
        # 前提 P2 -> 定理 T2
        # T1 と T2 は衝突関係にある
        p1 = Proposition("P1", "Premise 1", "", "definition")
        p2 = Proposition("P2", "Premise 2", "", "definition")
        t1 = Proposition("T1", "Theorem 1", "", "proposition")
        t2 = Proposition("T2", "Theorem 2", "", "proposition")

        r1 = InferenceRule("R1", (Literal("P1", True),), Literal("T1", True))
        r2 = InferenceRule("R2", (Literal("P2", True),), Literal("T2", True))
        conflict = ConflictPair(Literal("T1", True), Literal("T2", True), "T1 rebuts T2")

        kb = KnowledgeBase("KB_LateConflict", [p1, p2, t1, t2], [r1, r2], conflicts=[conflict])
        evaluator = Evaluator(kb)

        # 初期状態: P1, P2 未承認のため T1, T2 は UNKNOWN
        s0 = evaluator.evaluate()
        self.assertEqual(s0.get_status("T1"), TruthStatus.UNKNOWN)
        self.assertEqual(s0.get_status("T2"), TruthStatus.UNKNOWN)
        self.assertEqual(len(s0.diagnostic_conflicts), 0)

        # P1, P2 を承認して演繹: T1, T2 が演繹され、直ちに衝突が diagnostic_conflicts に検出される
        s1 = evaluator.evaluate(assumptions=[Literal("P1", True), Literal("P2", True)])
        self.assertEqual(s1.get_status("T1"), TruthStatus.TRUE)
        self.assertEqual(s1.get_status("T2"), TruthStatus.TRUE)
        self.assertEqual(len(s1.diagnostic_conflicts), 1)
        self.assertEqual(s1.diagnostic_conflicts[0]["prop_a"], "T1")
        self.assertEqual(s1.diagnostic_conflicts[0]["prop_b"], "T2")

        # LEGACY モードでは命題自体が CONFLICT になる
        leg_opts = ScenarioOptions(mode=SemanticsMode.LEGACY)
        s1_leg = evaluator.evaluate(assumptions=[Literal("P1", True), Literal("P2", True)], options=leg_opts)
        self.assertEqual(s1_leg.get_status("T1"), TruthStatus.CONFLICT)
        self.assertEqual(s1_leg.get_status("T2"), TruthStatus.CONFLICT)

    def test_08_circular_dependency_and_undefined_id_rejected(self):
        """8. 証明依存の循環と未定義IDを明示的に拒否する"""
        p = Proposition("P", "P", "", "proposition")
        q = Proposition("Q", "Q", "", "proposition")

        # (A) 循環依存 A -> B -> A の拒否
        r_cycle1 = InferenceRule("R1", (Literal("P", True),), Literal("Q", True))
        r_cycle2 = InferenceRule("R2", (Literal("Q", True),), Literal("P", True))
        with self.assertRaises(CyclicDependencyError):
            KnowledgeBase("KB_Cycle", [p, q], [r_cycle1, r_cycle2])

        # (B) 未定義IDの参照拒否
        r_undef = InferenceRule("R_Undef", (Literal("UNDEFINED_ID", True),), Literal("Q", True))
        with self.assertRaises(UndefinedIdentifierError):
            KnowledgeBase("KB_Undef", [q], [r_undef])

    def test_09_scenario_isolation_in_concurrency(self):
        """9. 同時実行した異なるシナリオが相互汚染しない (マルチスレッド安全)"""
        p = Proposition("P", "P", "", "definition")
        q = Proposition("Q", "Q", "", "proposition")
        r = InferenceRule("R", (Literal("P", True),), Literal("Q", True))
        kb = KnowledgeBase("KB_Iso", [p, q], [r])
        evaluator = Evaluator(kb)

        def run_scenario_true():
            st = evaluator.evaluate(assumptions=[Literal("P", True)])
            return st.get_status("Q")

        def run_scenario_false():
            st = evaluator.evaluate(assumptions=[Literal("P", False)])
            return st.get_status("Q")

        def run_scenario_none():
            st = evaluator.evaluate(assumptions=[])
            return st.get_status("Q")

        # 多数のスレッドでランダムに異なるシナリオを並行実行
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            f_true = [ex.submit(run_scenario_true) for _ in range(20)]
            f_false = [ex.submit(run_scenario_false) for _ in range(20)]
            f_none = [ex.submit(run_scenario_none) for _ in range(20)]

            for f in f_true:
                self.assertEqual(f.result(), TruthStatus.TRUE)
            for f in f_false:
                # 偽の前提からは否定は導かれないため UNKNOWN
                self.assertEqual(f.result(), TruthStatus.UNKNOWN)
            for f in f_none:
                self.assertEqual(f.result(), TruthStatus.UNKNOWN)

    def test_10_strict_four_value_partition(self):
        """10. 集計対象の全命題が排他的4分類のどれか一つに必ず入る"""
        p1 = Proposition("P1", "P1", "", "axiom")
        p2 = Proposition("P2", "P2", "", "definition")
        p3 = Proposition("P3", "P3", "", "definition")
        p4 = Proposition("P4", "P4", "", "axiom")

        c = ConflictPair(Literal("P1", True), Literal("P4", True))
        kb = KnowledgeBase("KB_Part", [p1, p2, p3, p4], conflicts=[c])
        evaluator = Evaluator(kb)

        # P2 に負支持、P3 は未指定
        state = evaluator.evaluate(assumptions=[Literal("P2", False)])
        summary = state.summary()

        all_ids = set(kb.propositions.keys())
        partition_ids = set()

        for category in ["UNKNOWN", "TRUE", "FALSE", "CONFLICT"]:
            self.assertIn(category, summary)
            ids = summary[category]
            # 各カテゴリ間で重複がないこと
            self.assertTrue(partition_ids.isdisjoint(ids), f"Category {category} overlaps with others")
            partition_ids.update(ids)

        # 和集合が全命題IDと完全に一致すること
        self.assertEqual(partition_ids, all_ids)
        self.assertEqual(len(partition_ids), 4)


if __name__ == "__main__":
    unittest.main()
