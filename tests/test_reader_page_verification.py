"""
読者向けページ検証テスト (Test Reader Page Verification)

1. 免責の文言がページ冒頭にあることの検証
2. 優劣・勝敗・順位を連想させる語が含まれないことの検証
3. ページの結果の表がエンジンの計算結果と完全一致することの検証
4. スクリーンショット3枚の撮影 (PC幅ライト、PC幅ダーク、スマホ幅412px)
"""
import unittest
import os
import json
import re
import sys

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ENGINE_DIR not in sys.path:
    sys.path.append(ENGINE_DIR)

from tests.test_independent_bruteforce_verification import IndependentBruteForceVerifier
from engine.semantics import KnowledgeBase, Proposition, InferenceRule, Literal, Evaluator, TruthStatus


class TestReaderPageVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_path = os.path.join(ENGINE_DIR, "web", "reader_page_v0.html")
        with open(cls.html_path, "r", encoding="utf-8") as f:
            cls.html_content = f.read()

        cls.des_path = os.path.join(ENGINE_DIR, "data", "descartes_second_replies_geometric.json")
        cls.ans_path = os.path.join(ENGINE_DIR, "data", "anselm_proslogion_iep.json")
        cls.spin_path = os.path.join(ENGINE_DIR, "data", "spinoza_ethics_part1_split_prop6.json")

        cls.verif_des = IndependentBruteForceVerifier(cls.des_path)
        cls.verif_ans = IndependentBruteForceVerifier(cls.ans_path)

    def test_disclaimer_at_beginning(self):
        """1. 免責の文言がページの冒頭（最初のセクション）にあること"""
        # <section> の最初のブロックを取得
        m = re.search(r"<section>(.*?)</section>", self.html_content, re.DOTALL)
        self.assertIsNotNone(m, "最初のセクションが見つかりません")
        first_section = m.group(1)

        self.assertIn("どの宗教・宗派の神であるかを決めるページではありません", first_section)
        self.assertIn("神の存在を証明も否定もしません", first_section)

    def test_no_hierarchy_or_victory_terms(self):
        """2. 優劣・勝敗・順位を連想させる語が含まれないこと"""
        # 注意事項の「優劣を表しません」のような否定文脈を除外した上で検査
        text_without_negations = self.html_content
        text_without_negations = text_without_negations.replace("経路の多さは、論証の優劣を表しません", "")
        text_without_negations = text_without_negations.replace("論証の優劣", "")

        forbidden_words = ["論破", "完全勝利", "敗北", "勝者", "敗者", "ランキング", "優越", "劣る", "白星", "黒星"]
        for word in forbidden_words:
            self.assertNotIn(word, text_without_negations, f"不適切な語 '{word}' がページ内に含まれています")

    def test_table_matches_engine_recomputation(self):
        """3. ページ内の数値・結果がエンジンの再計算結果と完全一致すること"""
        # デカルト
        d1_cnt, d1_sz, _ = self.verif_des.compute_minimal_support_grounds("DES_PROP_1")
        d2_cnt, d2_sz, _ = self.verif_des.compute_minimal_support_grounds("DES_PROP_2")
        d3_cnt, d3_sz, _ = self.verif_des.compute_minimal_support_grounds("DES_PROP_3")

        self.assertIn(f">{d1_cnt}組</td>", self.html_content)
        self.assertIn(f">{d1_sz}件</td>", self.html_content)
        self.assertIn(f">{d2_cnt}組</td>", self.html_content)
        self.assertIn(f">{d2_sz}件</td>", self.html_content)
        self.assertIn(f">{d3_cnt}組</td>", self.html_content)
        self.assertIn(f">{d3_sz}件</td>", self.html_content)

        # アンセルムス
        a1_cnt, a1_sz, _ = self.verif_ans.compute_minimal_support_grounds("ANS1_C")
        a2_cnt, a2_sz, _ = self.verif_ans.compute_minimal_support_grounds("ANS2_C")
        self.assertIn(f">{a1_cnt}組</td>", self.html_content)
        self.assertIn(f">{a1_sz}件</td>", self.html_content)
        self.assertIn(f">{a2_cnt}組</td>", self.html_content)
        self.assertIn(f">{a2_sz}件</td>", self.html_content)

        # 呼称対応表の存在
        self.assertIn("第1証明", self.html_content)
        self.assertIn("別証明1", self.html_content)
        self.assertIn("第3証明", self.html_content)
        self.assertIn("未登録 (今後の拡張候補)", self.html_content)

    def test_new_sections_and_notes(self):
        """4. 「今回わかったこと」「今回の取り組みで目指したこと」および呼称対応表注記の存在検証"""
        self.assertIn("今回わかったこと(このモデルの範囲の結果。新規性は未確認)", self.html_content)
        self.assertIn("今回の取り組みで目指したこと(新規性は未確認)", self.html_content)
        self.assertIn("証明の数え方は、研究者によって異なります(4つと数える研究もあります)。", self.html_content)
        self.assertIn("アンセルムスと、デカルトの命題1〜3の論証は、いずれも一本道です。", self.html_content)
        self.assertIn("このモデルは、本文の明示引用と、モデル作成者が採用した補完前提を区別して登録しています。原典に含まれる暗黙の依存を、すべて網羅したものではありません。", self.html_content)
        self.assertIn("スピノザのどの証明も、充足理由律に暗黙に依存すると読む研究もあります。", self.html_content)

    def test_six_considerations(self):
        """5. 前回の6項目（粒度の注意、状態バッジ、モデルと設定、ID日本語説明、中立色、括弧数字注記）の検証"""
        # 1. 粒度の注意
        self.assertIn("前提の数に関する注意（粒度の相違）", self.html_content)
        self.assertIn("前提の数（根拠サイズ）の大小を論証の優劣・完成度の順位として解釈することはできません", self.html_content)
        # 2. 状態バッジ (実態に合わせた表記)
        self.assertIn("AI照合済み(人の確認前)", self.html_content)
        self.assertIn("AI記載、未照合", self.html_content)
        self.assertIn("人の確認が済んでいない部分は、各行に状態を表示しています", self.html_content)
        # 3. モデルと設定の説明
        self.assertIn("スピノザのモデルと設定について", self.html_content)
        self.assertIn("モデルAは単一証明", self.html_content)
        # 4. 前提IDの日本語説明
        self.assertIn("必然的存在公理", self.html_content)
        self.assertIn("自己原因", self.html_content)
        self.assertIn("充足理由律", self.html_content)
        # 5. 中立な色 (赤・ローズ等の警告色排除)
        self.assertNotIn("#f43f5e", self.html_content)
        self.assertNotIn("#e11d48", self.html_content)
        # 6. 括弧の数字の注記
        self.assertIn("括弧内の数字について", self.html_content)
        self.assertIn("アンセルムスの前提内訳について", self.html_content)

    def test_prior_works_links(self):
        """6. 参考にした先行の取り組み5件とそのリンク・書誌情報の検証"""
        self.assertIn("参考にした先行の取り組み", self.html_content)
        self.assertIn("https://eprints.illc.uva.nl/id/eprint/1537/", self.html_content)
        self.assertIn("Pablo Sierra Márquez (2017)", self.html_content)
        self.assertIn("https://philarchive.org/archive/ROSSEA-3", self.html_content)
        self.assertIn("Herbert Roseman (2016)", self.html_content)
        self.assertIn("https://ethica.bc.edu/", self.html_content)
        self.assertIn("ethica.bc.edu", self.html_content)
        self.assertIn("https://argdown.org/", self.html_content)
        self.assertIn("Argdown", self.html_content)
        self.assertIn("https://arxiv.org/abs/1308.4526", self.html_content)
        self.assertIn("Formalization, Mechanization and Automation of Gödel's Proof of God's Existence", self.html_content)
        self.assertIn("掲載先: ECAI 2014", self.html_content)

    def test_aliter_project_numbering_note(self):
        """7. 呼称対応表の Aliter [1], [2] 括弧数字の本プロジェクト付番注記の検証"""
        self.assertIn("原典ラテン語表記の「Aliter [1]」「Aliter [2]」における括弧の数字 [1], [2] は、原典本文にはなく、区別のために本プロジェクトが付番したものです。", self.html_content)
        # 計○件の注記も維持されていること
        self.assertIn("括弧内の数字について", self.html_content)

    def test_all_ids_have_japanese_labels(self):
        """8. ページに表示される全IDに日本語名称が付いていることの検証 (デカルト、アンセルムス、スピノザ)"""
        matches = re.finditer(r'(<(code|span)[^>]*>([A-Z0-9_]+)</(code|span)>)', self.html_content)

        found_descartes = False
        found_anselm = False
        found_spinoza = False

        for m in matches:
            tag_id = m.group(3)
            # 前後60文字の文脈を取得
            start = max(0, m.start() - 60)
            end = min(len(self.html_content), m.end() + 60)
            surrounding = self.html_content[start:end]

            # 日本語（ひらがな・カタカナ・漢字）が含まれること
            has_japanese = bool(re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', surrounding))
            self.assertTrue(has_japanese, f"ID '{tag_id}' に日本語の名称・説明が付いていません: {surrounding}")

            if tag_id.startswith("DES_"):
                found_descartes = True
            elif tag_id.startswith("ANS"):
                found_anselm = True
            elif tag_id.startswith("DEF_") or tag_id.startswith("AX_") or tag_id.startswith("SPIN_") or tag_id.startswith("PROP_"):
                found_spinoza = True

        # 3体系すべてのIDがページ内に存在し検証されたこと
        self.assertTrue(found_descartes, "デカルトのIDが検出されませんでした")
        self.assertTrue(found_anselm, "アンセルムスのIDが検出されませんでした")
        self.assertTrue(found_spinoza, "スピノザのIDが検出されませんでした")

    def test_critique_table_split_badges_and_unverified_styling(self):
        """9. 批判シナリオ表のバッジ分離（データ／解釈）と「未照合」の橙色枠線検証"""
        self.assertIn("<th>データの状態</th>", self.html_content)
        self.assertIn("<th>解釈の状態</th>", self.html_content)

        # 充足理由律のみ遮断行の解釈状態が「AI記載、未照合」であること
        self.assertIn('<td data-label="解釈の状態"><span class="badge badge-unverified">AI記載、未照合</span></td>', self.html_content)

        # 未照合バッジが橙色（#f59e0b）の枠線スタイルを持つこと
        self.assertIn("--badge-unverified-border: #f59e0b;", self.html_content)
        self.assertIn("border: 1px solid var(--badge-unverified-border);", self.html_content)

    def test_table_note_styling(self):
        """10. 注記(※)の文字サイズ・コントラスト向上の検証"""
        self.assertIn(".table-note {", self.html_content)
        self.assertIn("font-size: 0.92rem;", self.html_content)
        self.assertIn('class="table-note"', self.html_content)

    def test_capture_screenshots(self):
        """11. Playwrightによる3枚のスクリーンショット撮影 (PC幅ライト、PC幅ダーク、スマホ幅412px) とスマホ幅横スクロール非発生検証"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("playwright not installed in environment")

        screenshot_dir = os.path.join(ENGINE_DIR, "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)

        url = "http://localhost:8000/reader_page_v0.html"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # 1. PC幅ライト (1280 x 900)
            context_pc_light = browser.new_context(viewport={"width": 1280, "height": 900})
            page_pc_light = context_pc_light.new_page()
            page_pc_light.goto(url, wait_until="networkidle")
            page_pc_light.evaluate("document.documentElement.setAttribute('data-theme', 'light')")
            page_pc_light.wait_for_timeout(300)
            pc_light_path = os.path.join(screenshot_dir, "reader_pc_light.png")
            page_pc_light.screenshot(path=pc_light_path, full_page=True)
            self.assertTrue(os.path.exists(pc_light_path))
            print(f"Captured: {pc_light_path}")

            # 2. PC幅ダーク (1280 x 900)
            context_pc_dark = browser.new_context(viewport={"width": 1280, "height": 900})
            page_pc_dark = context_pc_dark.new_page()
            page_pc_dark.goto(url, wait_until="networkidle")
            page_pc_dark.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
            page_pc_dark.wait_for_timeout(300)
            pc_dark_path = os.path.join(screenshot_dir, "reader_pc_dark.png")
            page_pc_dark.screenshot(path=pc_dark_path, full_page=True)
            self.assertTrue(os.path.exists(pc_dark_path))
            print(f"Captured: {pc_dark_path}")

            # 3. スマホ幅412px (Pixel 7 相当: 412 x 915)
            context_mobile = browser.new_context(
                viewport={"width": 412, "height": 915},
                user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36",
                is_mobile=True
            )
            page_mobile = context_mobile.new_page()
            page_mobile.goto(url, wait_until="networkidle")
            page_mobile.wait_for_timeout(300)

            # 横スクロール非発生の検証 (scrollWidth <= innerWidth)
            scroll_check = page_mobile.evaluate("() => ({ scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth })")
            self.assertLessEqual(
                scroll_check["scrollWidth"],
                scroll_check["innerWidth"] + 1,
                f"スマホ幅412pxで横スクロールが発生しています: scrollWidth={scroll_check['scrollWidth']}, innerWidth={scroll_check['innerWidth']}"
            )

            # 各表がカード化され、全列の内容（data-label）が表示されていることの検証
            card_count = page_mobile.locator(".card-table tr").count()
            self.assertGreater(card_count, 5, "カード化されたテーブル行が検出されませんでした")

            mobile_path = os.path.join(screenshot_dir, "reader_mobile_412.png")
            page_mobile.screenshot(path=mobile_path, full_page=True)
            self.assertTrue(os.path.exists(mobile_path))
            print(f"Captured: {mobile_path} (scrollWidth: {scroll_check['scrollWidth']}, innerWidth: {scroll_check['innerWidth']})")

            browser.close()


if __name__ == "__main__":
    unittest.main()
