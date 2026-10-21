"""
Web研究成果パネルの表示内容と計算結果（単体遮断・支持根拠・共通前提）の完全一致検証テスト
（再発防止テスト: 誤記や手書きによる不整合を機械的に検出・排除する）
"""
import unittest
import json
import os
import sys

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ENGINE_DIR not in sys.path:
    sys.path.append(ENGINE_DIR)

class TestResearchUIConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        json_path = os.path.join(ENGINE_DIR, "web", "spinoza_findings_v02.json")
        with open(json_path, "r", encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.models = cls.data.get("data", {}).get("models") or cls.data["models"]

    def test_json_bypass_consistency_with_rule_cuts(self):
        """JSONデータ内の単体遮断判定フラグが、rule_cuts（規則遮断集合）の真値と完全一致すること"""
        for m_key, m_info in self.models.items():
            rule_cuts = m_info["rule_cuts"]
            
            # 単体遮断の厳密判定 (手書きフラグの誤りを防止)
            actual_r2_single_cut = any(len(c) == 1 and c[0] == "R_PROP_2" for c in rule_cuts)
            actual_r3_single_cut = any(len(c) == 1 and c[0] == "R_PROP_3" for c in rule_cuts)
            
            self.assertEqual(
                m_info["r_prop_2_cut"],
                actual_r2_single_cut,
                f"r_prop_2_cut flag inconsistent for {m_key}"
            )
            self.assertEqual(
                m_info["r_prop_3_cut"],
                actual_r3_single_cut,
                f"r_prop_3_cut flag inconsistent for {m_key}"
            )

    def test_specific_model_bypass_expectations(self):
        """モデルA, B, C1, C2のR_PROP_2, R_PROP_3単体遮断状態の数学的・意味論的検証"""
        # モデルA: R2, R3ともに単体遮断 (迂回不可)
        self.assertTrue(self.models["model_a"]["r_prop_2_cut"])
        self.assertTrue(self.models["model_a"]["r_prop_3_cut"])

        # モデルB (設定a): R2, R3ともに単体遮断 (命題2は全設定不可、命題3は設定aで不可)
        self.assertTrue(self.models["model_b"]["r_prop_2_cut"])
        self.assertTrue(self.models["model_b"]["r_prop_3_cut"])
        self.assertIsNotNone(self.models["model_b"]["model_b_r3_bypass_note"])

        # モデルC1: 系の別証明により命題6本文(および命題2, 3)を迂回できるため、R2, R3ともに単体遮断なし (迂回可能)
        self.assertFalse(self.models["model_c1"]["r_prop_2_cut"])
        self.assertFalse(self.models["model_c1"]["r_prop_3_cut"])

        # モデルC2: 全別証明統合により、R2, R3ともに単体遮断なし (迂回可能)
        self.assertFalse(self.models["model_c2"]["r_prop_2_cut"])
        self.assertFalse(self.models["model_c2"]["r_prop_3_cut"])

    def test_dom_rendering_matches_computed_results(self):
        """PlaywrightによるDOM検査: 画面の各セルのテキストが計算結果と100%一致すること"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("playwright not installed in environment")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            
            try:
                page.goto("http://localhost:8000/", timeout=10000)
            except Exception:
                browser.close()
                self.skipTest("Local web server (port 8000) is not running")

            page.wait_for_load_state("networkidle")
            
            # 研究成果タブを開く
            page.locator("#tabViewResearch").click()
            page.wait_for_selector("#spinozaComparisonTable", timeout=5000)
            
            # 画面の前提注記の検証
            container_text = page.locator("#spinozaResearchContainer").inner_text()
            self.assertIn("【設定(a)・DEF_6補完あり】", container_text)
            
            # 各モデル行のセル値の厳密照合
            mapping = {
                "A": "model_a",
                "B": "model_b",
                "C1": "model_c1",
                "C2": "model_c2"
            }
            
            for key, json_key in mapping.items():
                row = page.locator(f'#spinozaComparisonTable tr[data-model="{key}"]')
                m_info = self.models[json_key]
                
                # 1. 最小支持根拠数
                grounds_text = row.locator(".cell-grounds").inner_text()
                expected_grounds = f"{len(m_info['grounds'])} 組"
                self.assertEqual(grounds_text.strip(), expected_grounds, f"Grounds mismatch for Model {key}")
                
                # 2. 共通前提数
                comm_text = row.locator(".cell-comm-prems span").inner_text()
                expected_comm = f"{len(m_info['common_premises'])}件"
                self.assertEqual(comm_text.strip(), expected_comm, f"Common premises count mismatch for Model {key}")
                
                # 3. 前提遮断数
                prem_cuts_text = row.locator(".cell-prem-cuts").inner_text()
                expected_prem_cuts = f"{len(m_info['premise_cuts'])} 件"
                self.assertEqual(prem_cuts_text.strip(), expected_prem_cuts, f"Premise cuts count mismatch for Model {key}")
                
                # 4. 規則遮断数
                rule_cuts_text = row.locator(".cell-rule-cuts").inner_text()
                expected_rule_cuts = f"{len(m_info['rule_cuts'])} 件"
                self.assertEqual(rule_cuts_text.strip(), expected_rule_cuts, f"Rule cuts count mismatch for Model {key}")
                
                # 5. R_PROP_2 単体遮断 / 迂回可否
                r2_cell_text = row.locator(".cell-r2-cut").inner_text()
                if m_info["r_prop_2_cut"]:
                    self.assertIn("不可欠 (単体遮断)", r2_cell_text)
                    self.assertNotIn("★迂回可能", r2_cell_text)
                else:
                    self.assertIn("★迂回可能", r2_cell_text)
                    self.assertNotIn("不可欠", r2_cell_text)

                # 6. R_PROP_3 単体遮断 / 迂回可否
                r3_cell_text = row.locator(".cell-r3-cut").inner_text()
                if m_info["r_prop_3_cut"]:
                    self.assertIn("不可欠 (単体遮断)", r3_cell_text)
                    self.assertNotIn("★迂回可能", r3_cell_text)
                    if key == "B":
                        self.assertIn("※設定(c)のみ迂回可", r3_cell_text)
                else:
                    self.assertIn("★迂回可能", r3_cell_text)
                    self.assertNotIn("不可欠", r3_cell_text)

            browser.close()

if __name__ == "__main__":
    unittest.main()
