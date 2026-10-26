"""
神の存在をめぐる論証 比較レポート(v0)の数値再計算・免責表示・中立性検証テスト
"""
import unittest
import json
import os
import sys

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ENGINE_DIR not in sys.path:
    sys.path.append(ENGINE_DIR)

from engine.benchmark_core import load_system_as_kb
from engine.grounds_and_cuts import GroundsAndCutsAnalyzer
from engine.semantics import Literal


class TestComparisonReportConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_path = os.path.join(ENGINE_DIR, "web", "comparison_v0.html")
        cls.md_path = os.path.join(ENGINE_DIR, "docs", "theological_arguments_comparison_v0.md")
        cls.spinoza_json_path = os.path.join(ENGINE_DIR, "web", "spinoza_findings_v02.json")
        cls.descartes_path = os.path.join(ENGINE_DIR, "data", "descartes_second_replies_geometric.json")
        cls.anselm_path = os.path.join(ENGINE_DIR, "data", "anselm_proslogion_iep.json")

        with open(cls.html_path, "r", encoding="utf-8") as f:
            cls.html_content = f.read()

        with open(cls.md_path, "r", encoding="utf-8") as f:
            cls.md_content = f.read()

        with open(cls.spinoza_json_path, "r", encoding="utf-8") as f:
            cls.spinoza_data = json.load(f)

    def _get_upstream_premises(self, kb, target_id):
        visited = set()
        premises = set()
        def dfs(nid):
            if nid in visited:
                return
            visited.add(nid)
            rules = [r for r in kb.rules if r.conclusion.prop_id == nid]
            if not rules:
                premises.add(nid)
            else:
                for r in rules:
                    for p in r.premises:
                        dfs(p.prop_id)
        dfs(target_id)
        return sorted(list(premises - {target_id}))

    def test_recomputation_descartes_theories(self):
        """デカルト体系(命題1, 2, 3)の最小根拠数・サイズ・単体遮断前提を再計算し検証"""
        kb = load_system_as_kb(self.descartes_path)
        analyzer = GroundsAndCutsAnalyzer(kb)

        # 命題1: 組数1, サイズ2, 単体遮断 [DES_AX_10, DES_DEF_9]
        up1 = [Literal(x, True) for x in self._get_upstream_premises(kb, "DES_PROP_1")]
        g1 = analyzer.find_minimal_support_grounds(Literal("DES_PROP_1", True), base_premises=up1)
        c1 = analyzer.find_minimal_cut_sets(Literal("DES_PROP_1", True), cut_type="premises")
        single_c1 = sorted([c.elements[0] for c in c1.subset_minimal_cuts if len(c.elements) == 1])
        self.assertEqual(len(g1.subset_minimal_grounds), 1)
        self.assertEqual(min(g.size for g in g1.subset_minimal_grounds), 2)
        self.assertEqual(single_c1, ["DES_AX_10", "DES_DEF_9"])

        # 命題2: 組数1, サイズ5, 単体遮断 [DES_AX_3, DES_AX_5, DES_AX_6, DES_DEF_2, DES_DEF_8]
        up2 = [Literal(x, True) for x in self._get_upstream_premises(kb, "DES_PROP_2")]
        g2 = analyzer.find_minimal_support_grounds(Literal("DES_PROP_2", True), base_premises=up2)
        c2 = analyzer.find_minimal_cut_sets(Literal("DES_PROP_2", True), cut_type="premises")
        single_c2 = sorted([c.elements[0] for c in c2.subset_minimal_cuts if len(c.elements) == 1])
        self.assertEqual(len(g2.subset_minimal_grounds), 1)
        self.assertEqual(min(g.size for g in g2.subset_minimal_grounds), 5)
        self.assertEqual(single_c2, ["DES_AX_3", "DES_AX_5", "DES_AX_6", "DES_DEF_2", "DES_DEF_8"])

        # 命題3: 組数1, サイズ8, 単体遮断 8件 (DES_AX_1 を含む)
        up3 = [Literal(x, True) for x in self._get_upstream_premises(kb, "DES_PROP_3")]
        g3 = analyzer.find_minimal_support_grounds(Literal("DES_PROP_3", True), base_premises=up3)
        c3 = analyzer.find_minimal_cut_sets(Literal("DES_PROP_3", True), cut_type="premises")
        single_c3 = sorted([c.elements[0] for c in c3.subset_minimal_cuts if len(c.elements) == 1])
        self.assertEqual(len(g3.subset_minimal_grounds), 1)
        self.assertEqual(min(g.size for g in g3.subset_minimal_grounds), 8)
        self.assertIn("DES_AX_1", single_c3)
        self.assertEqual(len(single_c3), 8)

    def test_recomputation_anselm_theories(self):
        """アンセルムス体系(論証1, 2)の最小根拠数・サイズ・単体遮断前提を再計算し検証"""
        kb = load_system_as_kb(self.anselm_path)
        analyzer = GroundsAndCutsAnalyzer(kb)

        # 論証1 (ANS1_C): 組数1, サイズ3, 単体遮断 [ANS1_P1, ANS1_P2, ANS1_P3]
        up1 = [Literal(x, True) for x in self._get_upstream_premises(kb, "ANS1_C")]
        g1 = analyzer.find_minimal_support_grounds(Literal("ANS1_C", True), base_premises=up1)
        c1 = analyzer.find_minimal_cut_sets(Literal("ANS1_C", True), cut_type="premises")
        single_c1 = sorted([c.elements[0] for c in c1.subset_minimal_cuts if len(c.elements) == 1])
        self.assertEqual(len(g1.subset_minimal_grounds), 1)
        self.assertEqual(min(g.size for g in g1.subset_minimal_grounds), 3)
        self.assertEqual(single_c1, ["ANS1_P1", "ANS1_P2", "ANS1_P3"])

        # 論証2 (ANS2_C): 組数1, サイズ3, 単体遮断 [ANS2_P1, ANS2_P2, ANS2_P6]
        up2 = [Literal(x, True) for x in self._get_upstream_premises(kb, "ANS2_C")]
        g2 = analyzer.find_minimal_support_grounds(Literal("ANS2_C", True), base_premises=up2)
        c2 = analyzer.find_minimal_cut_sets(Literal("ANS2_C", True), cut_type="premises")
        single_c2 = sorted([c.elements[0] for c in c2.subset_minimal_cuts if len(c.elements) == 1])
        self.assertEqual(len(g2.subset_minimal_grounds), 1)
        self.assertEqual(min(g.size for g in g2.subset_minimal_grounds), 3)
        self.assertEqual(single_c2, ["ANS2_P1", "ANS2_P2", "ANS2_P6"])

    def test_spinoza_models_numbers_consistency(self):
        """スピノザ各モデルの計算値がレポートと一致していること"""
        models = self.spinoza_data.get("data", {}).get("models") or self.spinoza_data["models"]

        # モデルA: 組数1, サイズ10, 単体遮断10件
        self.assertEqual(len(models["model_a"]["grounds"]), 1)
        self.assertEqual(min(len(g) for g in models["model_a"]["grounds"]), 10)
        self.assertEqual(len([c for c in models["model_a"]["premise_cuts"] if len(c) == 1]), 10)

        # モデルB: 組数2, 最小サイズ5, 単体遮断4件
        self.assertEqual(len(models["model_b"]["grounds"]), 2)
        self.assertEqual(min(len(g) for g in models["model_b"]["grounds"]), 5)
        self.assertEqual(len([c for c in models["model_b"]["premise_cuts"] if len(c) == 1]), 4)

        # モデルC1: 組数1, サイズ5, 単体遮断5件
        self.assertEqual(len(models["model_c1"]["grounds"]), 1)
        self.assertEqual(min(len(g) for g in models["model_c1"]["grounds"]), 5)
        self.assertEqual(len([c for c in models["model_c1"]["premise_cuts"] if len(c) == 1]), 5)

        # モデルC2: 組数2, 最小サイズ5, 単体遮断3件
        self.assertEqual(len(models["model_c2"]["grounds"]), 2)
        self.assertEqual(min(len(g) for g in models["model_c2"]["grounds"]), 5)
        self.assertEqual(len([c for c in models["model_c2"]["premise_cuts"] if len(c) == 1]), 3)

    def test_html_disclaimer_and_status_display(self):
        """HTMLに免責文言、各行の状態表示、3段階充足理由律、補完脚注が存在することを検証"""
        # 1. 冒頭免責事項
        self.assertIn("どの宗教・宗派の神であるかを決めるものではなく", self.html_content)
        self.assertIn("神の存在を論証的に証明あるいは否定するものでもありません", self.html_content)

        # 2. 各行の状態バッジ
        self.assertIn("AI照合済み (人の確認前)", self.html_content)

        # 3. 充足理由律の3段階表示
        self.assertIn("すべての根拠に含む", self.html_content)
        self.assertIn("一部の根拠に含む", self.html_content)
        self.assertIn("含まない", self.html_content)

        # 4. SPIN_AX_RATIO の作者補完脚注
        self.assertIn("SPIN_AX_RATIO について", self.html_content)
        self.assertIn("作者が補完した前提", self.html_content)
        self.assertIn("別証明1", self.html_content)
        self.assertIn("番号付きの公理ではない", self.html_content)

    def test_html_neutrality_no_ranking_or_defeat_words(self):
        """HTMLに優劣・勝敗・順位を連想させる語が含まれないことを検証"""
        forbidden_words = [
            "論破",
            "否定された",
            "ランキング",
            "優劣",
            "勝敗",
            "敗北",
            "勝利",
            "標的"
        ]
        for word in forbidden_words:
            self.assertNotIn(
                word,
                self.html_content,
                f"Forbidden word '{word}' found in HTML report!"
            )


if __name__ == "__main__":
    unittest.main()
