"""
モデルB・C1・C2 × 別証明1の設定(a)〜(d) 全12組み合わせのエンジン再計算と、
文書（web/spinoza_findings_v02.json, docs/spinoza_p11_findings_v02.md, README.md）との
完全整合性自動検証テスト
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


class TestAllSensitivityCombinations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. split_prop6.json のロード
        split_data_path = os.path.join(ENGINE_DIR, "data", "spinoza_ethics_part1_split_prop6.json")
        with open(split_data_path, "r", encoding="utf-8") as f:
            cls.raw_data = json.load(f)

        # 2. 保存済み JSON のロード
        saved_json_path = os.path.join(ENGINE_DIR, "web", "spinoza_findings_v02.json")
        with open(saved_json_path, "r", encoding="utf-8") as f:
            cls.saved_json = json.load(f)

        # 3. docs および README のロード
        docs_path = os.path.join(ENGINE_DIR, "docs", "spinoza_p11_findings_v02.md")
        with open(docs_path, "r", encoding="utf-8") as f:
            cls.docs_text = f.read()

        readme_path = os.path.join(ENGINE_DIR, "README.md")
        with open(readme_path, "r", encoding="utf-8") as f:
            cls.readme_text = f.read()

        cls.target = Literal("PROP_11", True)

        cls.ratio_prop = Proposition(
            id="SPIN_AX_RATIO",
            title="存在と非存在の理由原理 (充足理由律)",
            text_ja="いかなる事物についても、それが存在する理由・原因とともに、存在しない理由・原因が示されなければならない。",
            prop_type="principle_in_proof",
            logical_form="",
            source_system="Spinoza_26_Props",
            source_ref="",
        )

        cls.aliter_settings = {
            "a": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_3"),
            "b": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_3", "PROP_7"),
            "c": ("DEF_6", "SPIN_AX_RATIO", "PROP_2"),
            "d": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_7"),
        }

        # 全12組み合わせの再計算を実行してキャッシュ
        cls.results = {}
        for m in ["B", "C1", "C2"]:
            for s in ["a", "b", "c", "d"]:
                cls.results[(m, s)] = cls._compute_combination(m, s)

    @classmethod
    def _compute_combination(cls, model_key: str, setting_key: str):
        propositions = []
        rules = []

        for item in cls.raw_data["nodes"]:
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

        # 系の第1証明
        r_coroll_1 = InferenceRule(
            "R_PROP_6_COROLLARY_1",
            (Literal("PROP_6", True), Literal("AX_1", True), Literal("DEF_3", True), Literal("DEF_5", True)),
            Literal("PROP_6_COROLLARY", True),
        )
        rules.append(r_coroll_1)

        # 系の別証明 (DEF_3, AX_4 -> PROP_6_COROLLARY)
        if model_key in ["C1", "C2"]:
            r_coroll_aliter = InferenceRule(
                "R_PROP_6_COROLLARY_ALITER",
                (Literal("DEF_3", True), Literal("AX_4", True)),
                Literal("PROP_6_COROLLARY", True),
            )
            rules.append(r_coroll_aliter)

        # 命題11別証明 (R_PROP_11_ALITER1)
        if model_key in ["B", "C2"]:
            propositions.append(cls.ratio_prop)
            prems = tuple(Literal(p, True) for p in cls.aliter_settings[setting_key])
            r_aliter1 = InferenceRule("R_PROP_11_ALITER1", prems, Literal("PROP_11", True))
            rules.append(r_aliter1)

        kb = KnowledgeBase(f"KB_{model_key}_{setting_key}", propositions, rules)
        analyzer = GroundsAndCutsAnalyzer(kb)

        base_prems = [
            Literal(p.id, True)
            for p in kb.propositions.values()
            if p.prop_type in ["axiom", "definition", "assumption", "principle_in_proof"]
        ]
        grounds_res = analyzer.find_minimal_support_grounds(
            cls.target, base_premises=base_prems, max_evaluations=100000, timeout_seconds=30.0
        )
        prem_cuts = analyzer.find_minimal_cut_sets(cls.target, cut_type="premises")
        rule_cuts = analyzer.find_minimal_cut_sets(cls.target, cut_type="rules")

        common_prems = sorted([p.prop_id for p in grounds_res.common_premises])
        single_prem_cuts = sorted([c.elements[0] for c in prem_cuts.subset_minimal_cuts if len(c.elements) == 1])
        single_rule_cuts = sorted([c.elements[0] for c in rule_cuts.subset_minimal_cuts if len(c.elements) == 1])

        return {
            "common_premises": common_prems,
            "single_premise_cuts": single_prem_cuts,
            "single_rule_cuts": single_rule_cuts,
            "r2_bypassed": "R_PROP_2" not in single_rule_cuts,
            "r3_bypassed": "R_PROP_3" not in single_rule_cuts,
            "ax5_bypassed": "AX_5" not in single_prem_cuts,
        }

    def test_model_b_combinations(self):
        """モデルB（命題11別証明追加）の4設定(a〜d)における再計算結果の検証"""
        # (a) 現行設定: 4共通前提、迂回不可
        res_a = self.results[("B", "a")]
        self.assertEqual(res_a["common_premises"], ["AX_4", "AX_5", "DEF_3", "DEF_6"])
        self.assertEqual(res_a["single_premise_cuts"], ["AX_4", "AX_5", "DEF_3", "DEF_6"])
        self.assertFalse(res_a["r2_bypassed"])
        self.assertFalse(res_a["r3_bypassed"])
        self.assertFalse(res_a["ax5_bypassed"])

        # (b) 命題7追加: 9共通前提、迂回不可
        res_b = self.results[("B", "b")]
        expected_9 = ["AX_1", "AX_4", "AX_5", "AX_6", "DEF_1", "DEF_3", "DEF_4", "DEF_5", "DEF_6"]
        self.assertEqual(res_b["common_premises"], expected_9)
        self.assertEqual(res_b["single_premise_cuts"], expected_9)
        self.assertFalse(res_b["r2_bypassed"])
        self.assertFalse(res_b["r3_bypassed"])
        self.assertFalse(res_b["ax5_bypassed"])

        # (c) 命題3補完なし: 2共通前提、P3・AX5のみ迂回可（P2は迂回不可）
        res_c = self.results[("B", "c")]
        self.assertEqual(res_c["common_premises"], ["DEF_3", "DEF_6"])
        self.assertEqual(res_c["single_premise_cuts"], ["DEF_3", "DEF_6"])
        self.assertFalse(res_c["r2_bypassed"])
        self.assertTrue(res_c["r3_bypassed"])
        self.assertTrue(res_c["ax5_bypassed"])

        # (d) 命題7追加＋命題3補完なし: 9共通前提、迂回不可
        res_d = self.results[("B", "d")]
        self.assertEqual(res_d["common_premises"], expected_9)
        self.assertEqual(res_d["single_premise_cuts"], expected_9)
        self.assertFalse(res_d["r2_bypassed"])
        self.assertFalse(res_d["r3_bypassed"])
        self.assertFalse(res_d["ax5_bypassed"])

    def test_model_c1_combinations(self):
        """モデルC1（系の別証明のみ）は別証明1を含まないため全設定で一定"""
        expected_prems = ["AX_4", "AX_7", "DEF_1", "DEF_3", "DEF_6"]
        for s in ["a", "b", "c", "d"]:
            res = self.results[("C1", s)]
            self.assertEqual(res["common_premises"], expected_prems)
            self.assertEqual(res["single_premise_cuts"], expected_prems)
            self.assertTrue(res["r2_bypassed"])
            self.assertTrue(res["r3_bypassed"])
            self.assertTrue(res["ax5_bypassed"])

    def test_model_c2_combinations(self):
        """モデルC2（全別証明統合）の4設定(a〜d)における再計算結果の検証"""
        # 全設定で P2, P3, AX5 は迂回可能
        for s in ["a", "b", "c", "d"]:
            res = self.results[("C2", s)]
            self.assertTrue(res["r2_bypassed"], f"C2({s}) で R_PROP_2 が迂回可能であること")
            self.assertTrue(res["r3_bypassed"], f"C2({s}) で R_PROP_3 が迂回可能であること")
            self.assertTrue(res["ax5_bypassed"], f"C2({s}) で AX_5 が迂回可能であること")
            self.assertIn("DEF_3", res["common_premises"], f"C2({s}) で DEF_3 が共通前提であること")
            self.assertIn("DEF_6", res["common_premises"], f"C2({s}) で DEF_6 が共通前提であること")

        # (a) 現行設定: 3共通前提
        res_a = self.results[("C2", "a")]
        self.assertEqual(res_a["common_premises"], ["AX_4", "DEF_3", "DEF_6"])
        self.assertEqual(res_a["single_premise_cuts"], ["AX_4", "DEF_3", "DEF_6"])

        # (b) 命題7追加: 4共通前提 (DEF_1 が入る)
        res_b = self.results[("C2", "b")]
        self.assertEqual(res_b["common_premises"], ["AX_4", "DEF_1", "DEF_3", "DEF_6"])
        self.assertEqual(res_b["single_premise_cuts"], ["AX_4", "DEF_1", "DEF_3", "DEF_6"])

        # (c) 命題3補完なし: 2共通前提
        res_c = self.results[("C2", "c")]
        self.assertEqual(res_c["common_premises"], ["DEF_3", "DEF_6"])
        self.assertEqual(res_c["single_premise_cuts"], ["DEF_3", "DEF_6"])

        # (d) 命題7追加＋命題3補完なし: 4共通前提 (DEF_1 が入る)
        res_d = self.results[("C2", "d")]
        self.assertEqual(res_d["common_premises"], ["AX_4", "DEF_1", "DEF_3", "DEF_6"])
        self.assertEqual(res_d["single_premise_cuts"], ["AX_4", "DEF_1", "DEF_3", "DEF_6"])

    def test_cross_consistency_with_saved_json(self):
        """再計算結果と web/spinoza_findings_v02.json の完全一致検証"""
        models_dict = self.saved_json.get("data", {}).get("models") or self.saved_json["models"]

        # JSONの静的保存値 (設定aベース) との一致
        self.assertEqual(models_dict["model_b"]["common_premises"], self.results[("B", "a")]["common_premises"])
        self.assertEqual(models_dict["model_c1"]["common_premises"], self.results[("C1", "a")]["common_premises"])
        self.assertEqual(models_dict["model_c2"]["common_premises"], self.results[("C2", "a")]["common_premises"])

        # 単体遮断の一致
        saved_c2_cuts = [c[0] for c in models_dict["model_c2"]["premise_cuts"] if len(c) == 1]
        self.assertEqual(sorted(saved_c2_cuts), self.results[("C2", "a")]["single_premise_cuts"])

    def test_cross_consistency_with_docs_and_readme(self):
        """再計算結果と docs/spinoza_p11_findings_v02.md および README.md の数値一致検証"""
        # 1. C2の共通前提数 (設定c: 2件, 設定a: 3件, 設定b/d: 4件) がdocs/READMEに含まれること
        self.assertEqual(len(self.results[("C2", "c")]["common_premises"]), 2)
        self.assertEqual(len(self.results[("C2", "a")]["common_premises"]), 3)
        self.assertEqual(len(self.results[("C2", "b")]["common_premises"]), 4)
        self.assertEqual(len(self.results[("C2", "d")]["common_premises"]), 4)

        # docs 側の表記確認 (設定(c): 2件 または 設定c: 2件)
        self.assertTrue("設定(c): 2件" in self.docs_text or "設定c: 2件" in self.docs_text)
        self.assertTrue("設定(a): 3件" in self.docs_text or "設定a: 3件" in self.docs_text)
        self.assertTrue("設定(b): 4件" in self.docs_text or "設定b: 4件" in self.docs_text)
        self.assertTrue("設定(d): 4件" in self.docs_text or "設定d: 4件" in self.docs_text)

        # readme 側の表記確認
        self.assertTrue("設定(c): 2件" in self.readme_text or "設定c: 2件" in self.readme_text)
        self.assertTrue("設定(a): 3件" in self.readme_text or "設定a: 3件" in self.readme_text)

        # 2. DEF_3 が全12組み合わせで共通前提かつ単体遮断に含まれること
        for m in ["B", "C1", "C2"]:
            for s in ["a", "b", "c", "d"]:
                self.assertIn("DEF_3", self.results[(m, s)]["common_premises"])
                self.assertIn("DEF_3", self.results[(m, s)]["single_premise_cuts"])

        # 3. DEF_6 が全12組み合わせで共通前提かつ単体遮断に含まれること (DEF_6補完あり版の事実)
        for m in ["B", "C1", "C2"]:
            for s in ["a", "b", "c", "d"]:
                self.assertIn("DEF_6", self.results[(m, s)]["common_premises"])
                self.assertIn("DEF_6", self.results[(m, s)]["single_premise_cuts"])


if __name__ == "__main__":
    unittest.main()
