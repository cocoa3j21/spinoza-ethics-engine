"""
新規照合済み哲学体系（デカルト・アンセルムス）および未照合台帳の整合性検証テスト
"""
import unittest
import json
import os
import sys

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ENGINE_DIR not in sys.path:
    sys.path.append(ENGINE_DIR)

from engine.benchmark_core import load_system_as_kb


class TestNewVerifiedTheories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = os.path.join(ENGINE_DIR, "data")
        cls.docs_dir = os.path.join(ENGINE_DIR, "docs")

        # 1. デカルトデータロード
        cls.descartes_path = os.path.join(cls.data_dir, "descartes_second_replies_geometric.json")
        with open(cls.descartes_path, "r", encoding="utf-8") as f:
            cls.descartes_data = json.load(f)
        cls.descartes_nodes = {n["id"]: n for n in cls.descartes_data["nodes"]}

        # 2. アンセルムスデータロード
        cls.anselm_path = os.path.join(cls.data_dir, "anselm_proslogion_iep.json")
        with open(cls.anselm_path, "r", encoding="utf-8") as f:
            cls.anselm_data = json.load(f)
        cls.anselm_nodes = {n["id"]: n for n in cls.anselm_data["nodes"]}

        # 3. 未照合台帳ロード
        cls.unverified_path = os.path.join(cls.data_dir, "unverified_theories_registry.json")
        with open(cls.unverified_path, "r", encoding="utf-8") as f:
            cls.unverified_data = json.load(f)

    def test_descartes_node_counts(self):
        """デカルト体系のノード総数(26)および内訳(定義10, 要請1, 公理10, 命題4, 系1)を検証"""
        nodes = self.descartes_data["nodes"]
        self.assertEqual(len(nodes), 26, f"Descartes nodes total must be 26, got {len(nodes)}")

        type_counts = {}
        for n in nodes:
            t = n["type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        self.assertEqual(type_counts.get("definition", 0), 10, "Definitions count must be 10")
        self.assertEqual(type_counts.get("postulate", 0), 1, "Postulates count must be 1")
        self.assertEqual(type_counts.get("axiom", 0), 10, "Axioms count must be 10")
        self.assertEqual(type_counts.get("proposition", 0), 4, "Propositions count must be 4")
        self.assertEqual(type_counts.get("corollary", 0), 1, "Corollaries count must be 1")

    def test_anselm_node_counts(self):
        """アンセルムス体系のノード総数(13)および内訳(前提6, 導出5, 結論2)を検証"""
        nodes = self.anselm_data["nodes"]
        self.assertEqual(len(nodes), 13, f"Anselm nodes total must be 13, got {len(nodes)}")

        type_counts = {}
        for n in nodes:
            t = n["type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        self.assertEqual(type_counts.get("premise", 0), 6, "Premises count must be 6 (P1, P2, P3, P1, P2, P6)")
        self.assertEqual(type_counts.get("derived", 0), 5, "Derived count must be 5 (P4, P5, P3, P4, P5)")
        self.assertEqual(type_counts.get("conclusion", 0), 2, "Conclusions count must be 2 (ANS1_C, ANS2_C)")

        # 論証1 (第2章: 6ノード) と 論証2 (第3章: 7ノード) の内訳検証
        arg1_nodes = [n for n in nodes if n["id"].startswith("ANS1_")]
        arg2_nodes = [n for n in nodes if n["id"].startswith("ANS2_")]
        self.assertEqual(len(arg1_nodes), 6, "Arg 1 nodes count must be 6 (3 premises, 2 derived, 1 conclusion)")
        self.assertEqual(len(arg2_nodes), 7, "Arg 2 nodes count must be 7 (3 premises, 3 derived, 1 conclusion)")

        # P5 (論証1) および P4 (論証2) が導出(derived)であることの検証
        self.assertEqual(self.anselm_nodes["ANS1_P5"]["type"], "derived")
        self.assertEqual(self.anselm_nodes["ANS2_P4"]["type"], "derived")

    def test_descartes_at_vii_verification(self):
        """デカルト体系がAT VII 160-170のラテン語照合結果に完全準拠していること"""
        self.assertEqual(self.descartes_data["status"], "verified_against_at_vii")

        # 命題2 (DES_PROP_2) の依存関係の厳密検証: Def 2 & 8 が正しく、Def 7 (物体) が除外されていること
        self.assertIn("DES_PROP_2", self.descartes_nodes)
        p2 = self.descartes_nodes["DES_PROP_2"]
        expected_p2_deps = ["DES_AX_5", "DES_DEF_2", "DES_DEF_8", "DES_AX_6", "DES_AX_3"]
        self.assertEqual(sorted(p2["dependencies"]), sorted(expected_p2_deps))
        self.assertNotIn("DES_DEF_7", p2["dependencies"], "DES_DEF_7 (corpus) must NOT be in DES_PROP_2 dependencies")
        self.assertIn("DES_DEF_8", p2["dependencies"], "DES_DEF_8 (Deus) must be in DES_PROP_2 dependencies per AT VII 167")

        # 命題1 (DES_PROP_1) の依存関係検証: Def 9 & Ax 10
        p1 = self.descartes_nodes["DES_PROP_1"]
        self.assertEqual(sorted(p1["dependencies"]), sorted(["DES_DEF_9", "DES_AX_10"]))

        # 命題3 (DES_PROP_3) の依存関係検証
        p3 = self.descartes_nodes["DES_PROP_3"]
        expected_p3_deps = ["DES_AX_1", "DES_AX_2", "DES_AX_4", "DES_AX_7", "DES_AX_8", "DES_AX_9", "DES_DEF_2", "DES_DEF_8"]
        self.assertEqual(sorted(p3["dependencies"]), sorted(expected_p3_deps))

        # 命題3の系 (DES_COR_3) の依存関係検証
        cor3 = self.descartes_nodes["DES_COR_3"]
        self.assertEqual(cor3["dependencies"], ["DES_PROP_3"])

        # 命題4 (DES_PROP_4) の依存関係検証
        p4 = self.descartes_nodes["DES_PROP_4"]
        expected_p4_deps = ["DES_COR_3", "DES_POST_2", "DES_DEF_10", "DES_DEF_5", "DES_DEF_6", "DES_DEF_7"]
        self.assertEqual(sorted(p4["dependencies"]), sorted(expected_p4_deps))

    def test_descartes_knowledge_base_loading(self):
        """デカルト体系が推論エンジン KnowledgeBase としてロード可能で推論ルールが正しく生成されること"""
        kb = load_system_as_kb(self.descartes_path)
        self.assertEqual(kb.name, "Descartes_2R")

        # 命題・系から推論ルールが生成されていること
        rule_conclusions = {r.conclusion.prop_id for r in kb.rules}
        self.assertIn("DES_PROP_1", rule_conclusions)
        self.assertIn("DES_PROP_2", rule_conclusions)
        self.assertIn("DES_PROP_3", rule_conclusions)
        self.assertIn("DES_COR_3", rule_conclusions)
        self.assertIn("DES_PROP_4", rule_conclusions)

    def test_anselm_proslogion_verification(self):
        """アンセルムス体系（IEP標準形再構成）がプロスロギオン2-3章の論証構造を正しく定式化していること"""
        self.assertEqual(self.anselm_data["status"], "verified_reconstruction_with_proslogion_diff")

        # 論証1 (第2章): ANS1_C の導出構造
        self.assertIn("ANS1_C", self.anselm_nodes)
        c1 = self.anselm_nodes["ANS1_C"]
        self.assertEqual(sorted(c1["dependencies"]), sorted(["ANS1_P4", "ANS1_P5"]))

        p4 = self.anselm_nodes["ANS1_P4"]
        self.assertEqual(sorted(p4["dependencies"]), sorted(["ANS1_P2", "ANS1_P3"]))

        p5 = self.anselm_nodes["ANS1_P5"]
        self.assertEqual(p5["dependencies"], ["ANS1_P1"])

        # 論証2 (第3章): ANS2_C の導出構造
        self.assertIn("ANS2_C", self.anselm_nodes)
        c2 = self.anselm_nodes["ANS2_C"]
        self.assertEqual(sorted(c2["dependencies"]), sorted(["ANS2_P5", "ANS2_P6"]))

        p5_2 = self.anselm_nodes["ANS2_P5"]
        self.assertEqual(sorted(p5_2["dependencies"]), sorted(["ANS2_P3", "ANS2_P4"]))

        p3 = self.anselm_nodes["ANS2_P3"]
        self.assertEqual(sorted(p3["dependencies"]), sorted(["ANS2_P1", "ANS2_P2"]))

        p4_2 = self.anselm_nodes["ANS2_P4"]
        self.assertEqual(p4_2["dependencies"], ["ANS2_P1"])

    def test_anselm_knowledge_base_loading(self):
        """アンセルムス体系が推論エンジン KnowledgeBase としてロード可能であること"""
        kb = load_system_as_kb(self.anselm_path)
        self.assertEqual(kb.name, "Anselm_Proslogion_IEP")

        rule_conclusions = {r.conclusion.prop_id for r in kb.rules}
        self.assertIn("ANS1_C", rule_conclusions)
        self.assertIn("ANS1_P4", rule_conclusions)
        self.assertIn("ANS2_C", rule_conclusions)
        self.assertIn("ANS2_P3", rule_conclusions)

    def test_unverified_theories_isolated(self):
        """未照合体系（MAL_PLA, CLK_DEM）が隔離台帳に登録され、照合済みデータに混入していないこと"""
        self.assertEqual(self.unverified_data["status"], "draft_unverified")
        unverified_ids = [w["work_id"] for w in self.unverified_data["unverified_works"]]
        self.assertIn("MAL_PLA", unverified_ids)
        self.assertIn("CLK_DEM", unverified_ids)

        for work in self.unverified_data["unverified_works"]:
            self.assertIn("未確認", work["verification_status"])

        # 照合済みデータ内に未照合プレフィックスが含まれていないこと
        for nid in self.descartes_nodes.keys():
            self.assertFalse(nid.startswith("MAL_") or nid.startswith("PLA_") or nid.startswith("CLK_"))
        for nid in self.anselm_nodes.keys():
            self.assertFalse(nid.startswith("MAL_") or nid.startswith("PLA_") or nid.startswith("CLK_"))

    def test_cross_theory_interpretations_doc(self):
        """X1〜X4の比較候補が解釈として明記されたドキュメントが存在し要件を満たすこと"""
        doc_path = os.path.join(self.docs_dir, "cross_theory_interpretations.md")
        self.assertTrue(os.path.exists(doc_path), "cross_theory_interpretations.md must exist")
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("解釈", content)
        self.assertIn("X1", content)
        self.assertIn("X2", content)
        self.assertIn("X3", content)
        self.assertIn("X4", content)
        self.assertIn("SPIN_AX_RATIO", content)
        self.assertTrue("DES_PROP_2" in content or "DES_AX_1" in content)


if __name__ == "__main__":
    unittest.main()
