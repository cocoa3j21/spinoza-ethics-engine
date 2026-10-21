"""
スピノザ『エチカ』第1部 命題6本文・系・命題7の配線と原典明示引用の整合性検査テスト
"""
import unittest
import json
import os

class TestSpinozaSplitProp6Wiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "spinoza_ethics_part1_split_prop6.json"
        )
        with open(cls.data_path, "r", encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.nodes = {n["id"]: n for n in cls.data["nodes"]}

    def test_prop6_wiring(self):
        """命題6本文 (PROP_6) の前提が原典引用 [PROP_5, PROP_2, PROP_3] と一致すること"""
        self.assertIn("PROP_6", self.nodes)
        p6 = self.nodes["PROP_6"]
        expected = ["PROP_5", "PROP_2", "PROP_3"]
        self.assertEqual(sorted(p6["dependencies"]), sorted(expected))
        for dep in p6.get("dependencies_detailed", []):
            self.assertTrue(dep["explicit_in_text"], f"{dep['premise_id']} should be explicit")

    def test_prop6_corollary_demonstratio_1(self):
        """命題6系 (PROP_6_COROLLARY) の第1証明が [PROP_6, AX_1, DEF_3, DEF_5] と一致すること"""
        self.assertIn("PROP_6_COROLLARY", self.nodes)
        coroll = self.nodes["PROP_6_COROLLARY"]
        expected = ["PROP_6", "AX_1", "DEF_3", "DEF_5"]
        self.assertEqual(sorted(coroll["dependencies"]), sorted(expected))
        
        # 命題6本文 (PROP_6) が前提に含まれていることを確認
        self.assertIn("PROP_6", coroll["dependencies"])
        
        variants = coroll.get("proof_variants", {})
        self.assertIn("demonstratio_1", variants)
        self.assertEqual(sorted(variants["demonstratio_1"]["dependencies"]), sorted(expected))

    def test_prop6_corollary_demonstratio_aliter(self):
        """命題6系の別証明 (Demonstratio aliter) が [DEF_3, AX_4] のみ引用し、命題6本文を含まないこと"""
        coroll = self.nodes["PROP_6_COROLLARY"]
        variants = coroll.get("proof_variants", {})
        self.assertIn("demonstratio_aliter", variants)
        aliter = variants["demonstratio_aliter"]
        expected = ["DEF_3", "AX_4"]
        self.assertEqual(sorted(aliter["dependencies"]), sorted(expected))
        
        # 命題6本文 (PROP_6) を使用しないことの検証
        self.assertNotIn("PROP_6", aliter["dependencies"])
        # AX_2 や AX_5, DEF_4 が混入していないことの検証
        self.assertNotIn("AX_2", aliter["dependencies"])
        self.assertNotIn("AX_5", aliter["dependencies"])
        self.assertNotIn("DEF_4", aliter["dependencies"])

    def test_prop7_wiring(self):
        """命題7 (PROP_7) が命題6本文ではなく系 (PROP_6_COROLLARY) と DEF_1 に依存すること"""
        self.assertIn("PROP_7", self.nodes)
        p7 = self.nodes["PROP_7"]
        expected = ["PROP_6_COROLLARY", "DEF_1"]
        self.assertEqual(sorted(p7["dependencies"]), sorted(expected))
        self.assertNotIn("PROP_6", p7["dependencies"])
        self.assertIn("PROP_6_COROLLARY", p7["dependencies"])

if __name__ == "__main__":
    unittest.main()
