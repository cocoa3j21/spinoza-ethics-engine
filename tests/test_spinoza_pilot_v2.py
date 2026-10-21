"""
スピノザ新スキーマパイロットデータ (data/spinoza_pilot_v2.json) の
依存解析整合性検証テスト
(tests/test_spinoza_pilot_v2.py)
"""
import unittest
import os
import sys
import json
from typing import Dict, List, Tuple

# パス追加
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from engine.semantics import (
    KnowledgeBase,
    Proposition,
    InferenceRule,
    Literal,
    SemanticsMode,
)
from engine.grounds_and_cuts import GroundsAndCutsAnalyzer


def load_pilot_v2_as_kb(
    filepath: str,
    active_variants: Dict[str, List[str]]
) -> KnowledgeBase:
    """
    新スキーマ (v2) JSONから指定された proof_variant を選択して KnowledgeBase を構築
    active_variants: { prop_id: [variant_id, ...] }
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    propositions: List[Proposition] = []
    rules: List[InferenceRule] = []

    for item in data.get("nodes", []):
        pid = item["id"]
        prop = Proposition(
            id=pid,
            title=item["name"]["ja"],
            text_ja=item["formalization_levels"]["level_0_natural"],
            prop_type=item["category"],
            logical_form=item["formalization_levels"].get("level_2_first_order") or "",
            source_system="Spinoza_Pilot_v2",
            source_ref=item["source"]["locator"],
        )
        propositions.append(prop)

        # 指定された proof_variants から推論規則を構築
        selected_variant_ids = active_variants.get(pid, ["proof_standard"])
        for pv in item.get("proof_variants", []):
            vid = pv["variant_id"]
            if vid in selected_variant_ids:
                rule_id = f"R_{pid}_{vid.upper()}" if vid != "proof_standard" else f"R_{pid}"
                premises = tuple(Literal(prem_id, True) for prem_id in pv["direct_premises"])
                conclusion = Literal(pid, True)
                rules.append(InferenceRule(rule_id, premises, conclusion))

    return KnowledgeBase("Spinoza_Pilot_v2_KB", propositions, rules)


class TestSpinozaPilotV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pilot_path = os.path.join(BASE_DIR, "data", "spinoza_pilot_v2.json")
        cls.assertTrue(os.path.exists(cls.pilot_path), "Pilot v2 JSON must exist.")

    def test_model_a_grounds_and_cuts(self):
        """モデルA: 標準本文証明のみ (PROP_11 standard, PROP_6 standard)"""
        # モデルAの採用バリアント
        active_variants = {
            "PROP_2": ["proof_standard"],
            "PROP_3": ["proof_standard"],
            "PROP_5": ["proof_standard"],
            "PROP_6": ["proof_standard"],
            "PROP_7": ["proof_standard"],
            "PROP_11": ["proof_standard"],
        }
        kb = load_pilot_v2_as_kb(self.pilot_path, active_variants)
        analyzer = GroundsAndCutsAnalyzer(kb)

        # 最小支持根拠
        res = analyzer.find_minimal_support_grounds(Literal("PROP_11", True))
        self.assertTrue(res.is_complete)
        self.assertEqual(len(res.subset_minimal_grounds), 1)
        ground = res.subset_minimal_grounds[0]

        # パイロットデータ（12項目）内の前提:
        # PROP_11 <- PROP_7, DEF_6, AX_7
        # PROP_7 <- PROP_6, DEF_1
        # PROP_6 <- PROP_2, PROP_3, PROP_5
        # PROP_2 <- DEF_3
        # PROP_3 <- AX_4, AX_5
        # PROP_5 <- DEF_3, DEF_6
        # したがって前提集合は: {AX_4, AX_5, AX_7, DEF_1, DEF_3, DEF_6} (6件)
        expected_premises = {"AX_4", "AX_5", "AX_7", "DEF_1", "DEF_3", "DEF_6"}
        self.assertEqual(set(ground.to_prop_ids()), expected_premises)
        self.assertEqual(set(p.prop_id for p in res.common_premises), expected_premises)

    def test_model_b_alternative_proof(self):
        """モデルB: PROP_11 に別証明1 (Aliter 1) を追加"""
        active_variants = {
            "PROP_2": ["proof_standard"],
            "PROP_3": ["proof_standard"],
            "PROP_5": ["proof_standard"],
            "PROP_6": ["proof_standard"],
            "PROP_7": ["proof_standard"],
            "PROP_11": ["proof_standard", "proof_aliter_1"],
        }
        kb = load_pilot_v2_as_kb(self.pilot_path, active_variants)
        analyzer = GroundsAndCutsAnalyzer(kb)

        res = analyzer.find_minimal_support_grounds(Literal("PROP_11", True))
        self.assertTrue(res.is_complete)
        # 2つの最小支持根拠が存在すること
        self.assertEqual(len(res.subset_minimal_grounds), 2)
        found_grounds = [set(g.to_prop_ids()) for g in res.subset_minimal_grounds]

        # ルート1 (本文): {AX_4, AX_5, AX_7, DEF_1, DEF_3, DEF_6}
        # ルート2 (Aliter1: DEF_6, SPIN_AX_RATIO, PROP_2(DEF_3), PROP_3(AX_4, AX_5)):
        #   -> {AX_4, AX_5, DEF_3, DEF_6, SPIN_AX_RATIO}
        expected_aliter_premises = {"AX_4", "AX_5", "DEF_3", "DEF_6", "SPIN_AX_RATIO"}
        self.assertIn(expected_aliter_premises, found_grounds)

        # 共通前提: 積集合は {AX_4, AX_5, DEF_3, DEF_6}
        expected_common = {"AX_4", "AX_5", "DEF_3", "DEF_6"}
        self.assertEqual(set(p.prop_id for p in res.common_premises), expected_common)

    def test_model_c1_corollary_alternative(self):
        """モデルC1: PROP_6 に系別証明 (proof_aliter_corollary) を追加"""
        active_variants = {
            "PROP_2": ["proof_standard"],
            "PROP_3": ["proof_standard"],
            "PROP_5": ["proof_standard"],
            "PROP_6": ["proof_standard", "proof_aliter_corollary"],
            "PROP_7": ["proof_standard"],
            "PROP_11": ["proof_standard"],
        }
        kb = load_pilot_v2_as_kb(self.pilot_path, active_variants)
        analyzer = GroundsAndCutsAnalyzer(kb)

        res = analyzer.find_minimal_support_grounds(Literal("PROP_11", True))
        self.assertTrue(res.is_complete)
        # 最小支持根拠は1件 (サイズ5)
        # 系別証明 (DEF_3, AX_4 -> PROP_6) が PROP_5 経由ルートより短いためこれのみが極小
        self.assertEqual(len(res.subset_minimal_grounds), 1)
        expected_premises = {"AX_4", "AX_7", "DEF_1", "DEF_3", "DEF_6"}
        self.assertEqual(set(res.subset_minimal_grounds[0].to_prop_ids()), expected_premises)
        self.assertEqual(set(p.prop_id for p in res.common_premises), expected_premises)

        # 前提遮断集合は5件 (サイズ1×5)
        prem_cuts = analyzer.find_minimal_cut_sets(Literal("PROP_11", True), cut_type="premises")
        self.assertEqual(len(prem_cuts.subset_minimal_cuts), 5)

    def test_model_c2_all_alternatives(self):
        """モデルC2: PROP_11別証明 + PROP_6系別証明"""
        active_variants = {
            "PROP_2": ["proof_standard"],
            "PROP_3": ["proof_standard"],
            "PROP_5": ["proof_standard"],
            "PROP_6": ["proof_standard", "proof_aliter_corollary"],
            "PROP_7": ["proof_standard"],
            "PROP_11": ["proof_standard", "proof_aliter_1"],
        }
        kb = load_pilot_v2_as_kb(self.pilot_path, active_variants)
        analyzer = GroundsAndCutsAnalyzer(kb)

        res = analyzer.find_minimal_support_grounds(Literal("PROP_11", True))
        self.assertTrue(res.is_complete)
        # 2つの最小支持根拠 (G1: Aliter1, G2: 系別証明)
        self.assertEqual(len(res.subset_minimal_grounds), 2)
        found_grounds = [set(g.to_prop_ids()) for g in res.subset_minimal_grounds]
        g1 = {"AX_4", "AX_5", "DEF_3", "DEF_6", "SPIN_AX_RATIO"}
        g2 = {"AX_4", "AX_7", "DEF_1", "DEF_3", "DEF_6"}
        self.assertIn(g1, found_grounds)
        self.assertIn(g2, found_grounds)

        # 全証明経路に共通する前提は {AX_4, DEF_3, DEF_6}
        expected_common = {"AX_4", "DEF_3", "DEF_6"}
        self.assertEqual(set(p.prop_id for p in res.common_premises), expected_common)

        # 前提遮断集合は7件 (サイズ1×3, サイズ2×4)
        prem_cuts = analyzer.find_minimal_cut_sets(Literal("PROP_11", True), cut_type="premises")
        self.assertEqual(len(prem_cuts.subset_minimal_cuts), 7)


if __name__ == "__main__":
    unittest.main()
