"""
第二次監査: 矛盾前提遮断とワークリスト評価の整合性検証テストスイート
"""
import unittest
import itertools
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.semantics import (
    KnowledgeBase,
    Proposition,
    InferenceRule,
    ConflictPair,
    Literal,
    TruthStatus,
    Evaluator,
    ScenarioOptions,
)


class TestSecondAudit(unittest.TestCase):
    def setUp(self):
        self.p = Proposition("P", "Proposition P", "", "definition")
        self.s = Proposition("S", "Proposition S", "", "definition")
        self.q = Proposition("Q", "Proposition Q", "", "proposition")
        self.r = Proposition("R", "Proposition R", "", "proposition")
        self.t = Proposition("T", "Proposition T", "", "axiom")

        self.r1 = InferenceRule("r1", (Literal("P", True),), Literal("Q", True))
        self.r2 = InferenceRule("r2", (Literal("S", True),), Literal("R", True))
        self.r3 = InferenceRule("r3", (Literal("R", True),), Literal("P", False))
        self.r4 = InferenceRule("r4", (Literal("T", True),), Literal("Q", True))

    def test_01_minimal_model_current_behavior(self):
        """
        1. 最小モデルのテスト
        初期支持: +P, +S
        規則: r1: +P -> +Q, r2: +S -> +R, r3: +R -> -P
        確認事項: P が CONFLICT になった際、r1 からの Q の支持がどう扱われるか
        """
        kb = KnowledgeBase("KB_Min", [self.p, self.s, self.q, self.r], [self.r1, self.r2, self.r3])
        evaluator = Evaluator(kb)
        state = evaluator.evaluate(assumptions=[Literal("P", True), Literal("S", True)])

        # P は初期 +P と r3 からの -P により CONFLICT になる
        self.assertEqual(state.get_status("P"), TruthStatus.CONFLICT)
        self.assertEqual(state.get_status("S"), TruthStatus.TRUE)
        self.assertEqual(state.get_status("R"), TruthStatus.TRUE)

        # 【現実装の挙動の確認】
        # require_untainted_premises=True にもかかわらず、r1 は P が CONFLICT になる前に
        # 先行発火してしまい、後から P が CONFLICT になった際の撤回がないため、Q に支持が残る。
        # 本来の意図（矛盾前提遮断）に照らせば Q は UNKNOWN であるべきだが、
        # 現実装では Q は TRUE (supports={'r1'}) となっている事実を記録・検証する。
        print(f"\n[Test 1] 最小モデルのP状態: {state.get_status('P')}, Q状態: {state.get_status('Q')}, Q支持: {state.positive_supports['Q']}")

    def test_02_all_rule_permutations(self):
        """
        2. 規則集合の全順序を試し、最終的な支持状態と有効な証明根拠が一致するか確認
        """
        rules = [self.r1, self.r2, self.r3]
        results = set()

        for perm in itertools.permutations(rules):
            kb = KnowledgeBase(f"KB_Perm", [self.p, self.s, self.q, self.r], perm)
            evaluator = Evaluator(kb)
            st = evaluator.evaluate(assumptions=[Literal("P", True), Literal("S", True)])
            results.add((st.get_status("P").name, st.get_status("Q").name, tuple(sorted(list(st.positive_supports["Q"])))) )

        print(f"\n[Test 2] 規則全順列 ({len(list(itertools.permutations(rules)))}通り) の結果バリエーション:")
        for res in results:
            print(f"  P={res[0]}, Q={res[1]}, Q_supports={res[2]}")
        # 全順列で同じ結果に収束するか（単一の結果セットであるか）
        self.assertEqual(len(results), 1, "規則の登録順序によって結果が変動してはならない")

    def test_03_alternative_uncontaminated_proof_for_q(self):
        """
        3. Qへの別の非汚染証明を追加し、r1が無効になってもQの支持が残ることを確認
        """
        # r4: +T -> +Q (Tは公理)
        kb = KnowledgeBase("KB_Alt", [self.p, self.s, self.q, self.r, self.t], [self.r1, self.r2, self.r3, self.r4])
        evaluator = Evaluator(kb)
        st = evaluator.evaluate(assumptions=[Literal("P", True), Literal("S", True)])

        # Q は少なくとも非汚染証明 r4 からの支持を持つため TRUE
        self.assertEqual(st.get_status("Q"), TruthStatus.TRUE)
        self.assertIn("r4", st.positive_supports["Q"])
        print(f"\n[Test 3] 別証明追加時のQ状態: {st.get_status('Q')}, 支持一覧: {st.positive_supports['Q']}")


if __name__ == "__main__":
    unittest.main()
