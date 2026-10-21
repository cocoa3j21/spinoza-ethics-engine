"""
第三次監査テスト: 攻撃由来の支持と撤回によるフィードバック、自壊的推論、および非収束・サイクル検出の検証
"""
import unittest
from engine.semantics import (
    KnowledgeBase,
    Proposition,
    InferenceRule,
    ConflictPair,
    Literal,
    TruthStatus,
    EvaluationStatus,
    SemanticsMode,
    ScenarioOptions,
    Evaluator,
    analyze_extended_dependencies,
)


class TestAuditRound3FeedbackAndOscillation(unittest.TestCase):
    """第三次監査: 自壊的推論フィードバックと停止性の検証"""

    def setUp(self):
        """
        【最小モデル】
        初期支持: +A
        規則: r1: +A -> +B
        条件: require_untainted_premises=True
        衝突: ConflictPair(+A, +B)
        """
        p_a = Proposition("A", "命題A", "", "assumption")
        p_b = Proposition("B", "命題B", "", "proposition")
        rule = InferenceRule("r1", (Literal("A", True),), Literal("B", True))
        conflict = ConflictPair(Literal("A", True), Literal("B", True))
        self.kb = KnowledgeBase(
            name="AuditRound3KB",
            propositions=[p_a, p_b],
            rules=[rule],
            conflicts=[conflict],
        )

    def test_current_semantics_phantom_justification_and_stabilization(self):
        """
        1. 実際に観測される現仕様の挙動:
        - r1 により B が導出される。
        - ConflictPair により A と B が互いに否定支持を追加する。
        - A が CONFLICT になったため、r1 が撤回され B の正支持は消滅する。
        - しかし、現仕様では Conflict 由来の否定支持は撤回されない。
        - そのため A は CONFLICT, B は FALSE に固定され、4ステップで停止する。
        """
        evaluator = Evaluator(self.kb)
        opts = ScenarioOptions(
            mode=SemanticsMode.LEGACY,
            require_untainted_premises=True,
            retract_conflicts_on_premise_loss=False,
        )
        state = evaluator.evaluate(assumptions=[Literal("A", True)], options=opts)

        # 停止性と完了ステータス
        self.assertEqual(state.status, EvaluationStatus.CONVERGED)
        self.assertTrue(state.is_complete)
        self.assertEqual(state.step_count, 4)

        # A の状態: pos に仮定、neg に conflict:B が残り CONFLICT
        self.assertEqual(state.get_status("A"), TruthStatus.CONFLICT)
        self.assertIn("assumption:A", state.positive_supports["A"])
        self.assertIn("conflict:B", state.negative_supports["A"])

        # B の状態: pos の r1 は撤回されて空、neg に conflict:A が残り FALSE
        self.assertEqual(state.get_status("B"), TruthStatus.FALSE)
        self.assertEqual(len(state.positive_supports["B"]), 0, "r1による正支持は確実に撤回されている")
        self.assertIn("conflict:A", state.negative_supports["B"], "現仕様では衝突由来の否定支持は撤回されず残存する")

        # 発火規則: 空（r1 は撤回されている）
        self.assertEqual(len(state.fired_rules), 0)

    def test_complete_retraction_causes_oscillation_cycle_detected(self):
        """
        2. もし Conflict 由来の否定支持も前提消滅時に完全撤回した場合:
        - B の正支持が消えると、A の否定支持 conflict:B も撤回される。
        - A が TRUE に復帰し、r1 が再発火して B が正支持される。
        - B が支持されると再び Conflict が成立し A が CONFLICT になり r1 が撤回される。
        - この振動（周期2の状態反復）を検出し、非収束（CYCLE_DETECTED）として報告する。
        - 非収束を成功や UNKNOWN と偽装しない。
        """
        evaluator = Evaluator(self.kb)
        opts = ScenarioOptions(
            mode=SemanticsMode.EXPERIMENTAL,
            require_untainted_premises=True,
            retract_conflicts_on_premise_loss=True,
            track_cycles=True,
        )
        state = evaluator.evaluate(assumptions=[Literal("A", True)], options=opts)

        # サイクルが検出され、非収束であることが明示される
        self.assertEqual(state.status, EvaluationStatus.CYCLE_DETECTED)
        self.assertFalse(state.is_complete)
        self.assertIsNotNone(state.cycle_info)
        self.assertIn("first_seen_step", state.cycle_info)
        self.assertIn("cycle_detected_at_step", state.cycle_info)

    def test_extended_dependencies_detects_macro_negative_cycle(self):
        """
        3. 総合依存グラフの解析:
        推論規則単体は graphlib.TopologicalSorter を通過するDAGであるが、
        規則 + ConflictPair による総合依存ネットワークには負の閉路（自壊的奇数サイクル）が存在することを検知する。
        """
        analysis = analyze_extended_dependencies(self.kb)
        self.assertTrue(analysis["has_cycles"], "マクロ依存グラフにサイクルが存在する")
        self.assertTrue(analysis["has_odd_negative_cycles"], "奇数長負サイクル（振動の原因）が検出される")

    def test_step_limit_exceeded_status(self):
        """
        4. 計算上限超過時のステータス確認:
        無限ループ時に最大ステップを超過した場合、STEP_LIMIT_EXCEEDED を返し、is_complete=False となること。
        """
        evaluator = Evaluator(self.kb)
        opts = ScenarioOptions(
            mode=SemanticsMode.EXPERIMENTAL,
            max_steps=2,
            require_untainted_premises=True,
            retract_conflicts_on_premise_loss=True,
            track_cycles=False,  # サイクル検出を切ってステップ上限到達をテスト
        )
        state = evaluator.evaluate(assumptions=[Literal("A", True)], options=opts)
        self.assertEqual(state.status, EvaluationStatus.STEP_LIMIT_EXCEEDED)
        self.assertFalse(state.is_complete)


if __name__ == "__main__":
    unittest.main()
