"""
保存済み web/spinoza_findings_v02.json と GroundsAndCutsAnalyzer による再計算結果の完全一致検証テスト
（データ生成の再現性と静的保存値の完全一致を機械的に保証する）
"""
import unittest
import json
import os
import sys

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ENGINE_DIR not in sys.path:
    sys.path.append(ENGINE_DIR)

from engine.semantics import KnowledgeBase, Proposition, InferenceRule, Literal
from engine.grounds_and_cuts import GroundsAndCutsAnalyzer

class TestRecomputedFindingsConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. 保存済み JSON の読み込み
        saved_json_path = os.path.join(ENGINE_DIR, "web", "spinoza_findings_v02.json")
        with open(saved_json_path, "r", encoding="utf-8") as f:
            cls.saved_payload = json.load(f)
        cls.saved_models = cls.saved_payload.get("data", {}).get("models") or cls.saved_payload["models"]

        # 2. split_prop6.json のパス
        cls.split_data_path = os.path.join(ENGINE_DIR, "data", "spinoza_ethics_part1_split_prop6.json")
        with open(cls.split_data_path, "r", encoding="utf-8") as f:
            cls.raw_data = json.load(f)

        cls.target = Literal("PROP_11", True)

        # 充足理由律
        cls.ratio_prop = Proposition(
            id="SPIN_AX_RATIO",
            title="存在と非存在の理由原理 (充足理由律)",
            text_ja="いかなる事物についても、それが存在する理由・原因とともに、存在しない理由・原因が示されなければならない。",
            prop_type="principle_in_proof",
            logical_form="",
            source_system="Spinoza_26_Props",
            source_ref="",
        )

        # 命題11別証明規則 (設定a: DEF_6, SPIN_AX_RATIO, PROP_2, PROP_3)
        cls.r_prop11_aliter1 = InferenceRule(
            "R_PROP_11_ALITER1",
            (Literal("DEF_6", True), Literal("SPIN_AX_RATIO", True), Literal("PROP_2", True), Literal("PROP_3", True)),
            Literal("PROP_11", True)
        )

    def _build_kb_for_model(self, model_key: str) -> KnowledgeBase:
        propositions = []
        rules = []

        for item in self.raw_data["nodes"]:
            pid = item["id"]
            prop = Proposition(
                id=pid,
                title=item.get("title", pid),
                text_ja=item.get("text_ja", ""),
                prop_type=item.get("type", "proposition"),
                logical_form=item.get("logical_form", ""),
                source_system="Spinoza_Split_Exact",
                source_ref="",
            )
            propositions.append(prop)

            if pid != "PROP_6_COROLLARY":
                deps = item.get("dependencies", [])
                if deps:
                    p_lits = tuple(Literal(d, True) for d in deps)
                    rules.append(InferenceRule(f"R_{pid}", p_lits, Literal(pid, True)))

        # 系の第1証明 (PROP_6, AX_1, DEF_3, DEF_5 -> PROP_6_COROLLARY)
        r_coroll_1 = InferenceRule(
            "R_PROP_6_COROLLARY_1",
            (Literal("PROP_6", True), Literal("AX_1", True), Literal("DEF_3", True), Literal("DEF_5", True)),
            Literal("PROP_6_COROLLARY", True)
        )
        rules.append(r_coroll_1)

        # 系の別証明 (DEF_3, AX_4 -> PROP_6_COROLLARY)
        r_coroll_aliter = InferenceRule(
            "R_PROP_6_COROLLARY_ALITER",
            (Literal("DEF_3", True), Literal("AX_4", True)),
            Literal("PROP_6_COROLLARY", True)
        )
        if model_key in ["C1", "C2"]:
            rules.append(r_coroll_aliter)

        if model_key in ["B", "C2"]:
            propositions.append(self.ratio_prop)
            rules.append(self.r_prop11_aliter1)

        return KnowledgeBase(f"KB_recompute_{model_key}", propositions, rules)

    def _recompute_model(self, model_key: str):
        kb = self._build_kb_for_model(model_key)
        analyzer = GroundsAndCutsAnalyzer(kb)
        base_prems = [
            Literal(p.id, True) for p in kb.propositions.values()
            if p.prop_type in ["axiom", "definition", "assumption", "principle_in_proof"]
        ]
        grounds_res = analyzer.find_minimal_support_grounds(
            self.target, base_premises=base_prems, max_evaluations=100000, timeout_seconds=30.0
        )
        prem_cuts = analyzer.find_minimal_cut_sets(self.target, cut_type="premises")
        rule_cuts = analyzer.find_minimal_cut_sets(self.target, cut_type="rules")

        grounds = [sorted(g.to_prop_ids()) for g in grounds_res.subset_minimal_grounds]
        grounds.sort()
        common_prems = sorted([p.prop_id for p in grounds_res.common_premises])
        p_cuts = [sorted(c.elements) for c in prem_cuts.subset_minimal_cuts]
        p_cuts.sort()
        r_cuts = [sorted(c.elements) for c in rule_cuts.subset_minimal_cuts]
        r_cuts.sort()

        return {
            "grounds": grounds,
            "common_premises": common_prems,
            "premise_cuts": p_cuts,
            "rule_cuts": r_cuts,
            "r_prop_2_cut": ["R_PROP_2"] in r_cuts,
            "r_prop_3_cut": ["R_PROP_3"] in r_cuts,
        }

    def test_recomputed_model_a(self):
        """モデルAの再計算結果が保存済みJSONと完全一致すること"""
        saved = self.saved_models["model_a"]
        recomputed = self._recompute_model("A")

        self.assertEqual(sorted(saved["grounds"]), sorted(recomputed["grounds"]))
        self.assertEqual(sorted(saved["common_premises"]), sorted(recomputed["common_premises"]))
        self.assertEqual(sorted(saved["premise_cuts"]), sorted(recomputed["premise_cuts"]))
        self.assertEqual(sorted(saved["rule_cuts"]), sorted(recomputed["rule_cuts"]))
        self.assertEqual(saved["r_prop_2_cut"], recomputed["r_prop_2_cut"])
        self.assertEqual(saved["r_prop_3_cut"], recomputed["r_prop_3_cut"])

    def test_recomputed_model_b(self):
        """モデルBの再計算結果が保存済みJSONと完全一致すること"""
        saved = self.saved_models["model_b"]
        recomputed = self._recompute_model("B")

        self.assertEqual(sorted(saved["grounds"]), sorted(recomputed["grounds"]))
        self.assertEqual(sorted(saved["common_premises"]), sorted(recomputed["common_premises"]))
        self.assertEqual(sorted(saved["premise_cuts"]), sorted(recomputed["premise_cuts"]))
        self.assertEqual(sorted(saved["rule_cuts"]), sorted(recomputed["rule_cuts"]))
        self.assertEqual(saved["r_prop_2_cut"], recomputed["r_prop_2_cut"])
        self.assertEqual(saved["r_prop_3_cut"], recomputed["r_prop_3_cut"])

    def test_recomputed_model_c1(self):
        """モデルC1の再計算結果が保存済みJSONと完全一致すること"""
        saved = self.saved_models["model_c1"]
        recomputed = self._recompute_model("C1")

        self.assertEqual(sorted(saved["grounds"]), sorted(recomputed["grounds"]))
        self.assertEqual(sorted(saved["common_premises"]), sorted(recomputed["common_premises"]))
        self.assertEqual(sorted(saved["premise_cuts"]), sorted(recomputed["premise_cuts"]))
        self.assertEqual(sorted(saved["rule_cuts"]), sorted(recomputed["rule_cuts"]))
        self.assertEqual(saved["r_prop_2_cut"], recomputed["r_prop_2_cut"])
        self.assertEqual(saved["r_prop_3_cut"], recomputed["r_prop_3_cut"])

    def test_recomputed_model_c2(self):
        """モデルC2の再計算結果が保存済みJSONと完全一致すること"""
        saved = self.saved_models["model_c2"]
        recomputed = self._recompute_model("C2")

        self.assertEqual(sorted(saved["grounds"]), sorted(recomputed["grounds"]))
        self.assertEqual(sorted(saved["common_premises"]), sorted(recomputed["common_premises"]))
        self.assertEqual(sorted(saved["premise_cuts"]), sorted(recomputed["premise_cuts"]))
        self.assertEqual(sorted(saved["rule_cuts"]), sorted(recomputed["rule_cuts"]))
        self.assertEqual(saved["r_prop_2_cut"], recomputed["r_prop_2_cut"])
        self.assertEqual(saved["r_prop_3_cut"], recomputed["r_prop_3_cut"])

if __name__ == "__main__":
    unittest.main()
