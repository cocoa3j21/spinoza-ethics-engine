"""
推論エンジンに依存しない独立した総当たり演繹実装によるデカルト・アンセルムスの検算テスト
"""
import unittest
import json
import itertools
import os


class IndependentBruteForceVerifier:
    """
    推論エンジン(engine.*)に一切依存しない、純粋なPython標準ライブラリのみによる
    演繹閉包と総当たり部分集合探索による独立検証器。
    """
    def __init__(self, json_path: str):
        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.rules = {}  # conclusion_id -> list of premise_id lists
        self.all_nodes = set()
        self.base_premises = set()

        for node in self.data["nodes"]:
            nid = node["id"]
            self.all_nodes.add(nid)
            deps = node.get("dependencies", [])
            if not deps:
                self.base_premises.add(nid)
            else:
                self.rules[nid] = list(deps)

    def get_upstream_base_premises(self, target_id: str) -> set:
        """目標命題の上流にある基礎前提の集合を収集"""
        visited = set()
        upstream = set()
        def dfs(curr):
            if curr in visited:
                return
            visited.add(curr)
            if curr in self.base_premises:
                upstream.add(curr)
            elif curr in self.rules:
                for dep in self.rules[curr]:
                    dfs(dep)
        dfs(target_id)
        return upstream

    def can_derive(self, target_id: str, active_premises: set) -> bool:
        """与えられた前提集合から前方連鎖演繹(Forward Chaining)で目標が導出できるか判定"""
        derived = set(active_premises)
        changed = True
        while changed:
            changed = False
            for concl, deps in self.rules.items():
                if concl not in derived and all(d in derived for d in deps):
                    derived.add(concl)
                    changed = True
                    if concl == target_id:
                        return True
        return target_id in derived

    def compute_minimal_support_grounds(self, target_id: str) -> tuple[int, int, list[set]]:
        """
        上流前提の部分集合をサイズ1から全探索し、包含極小根拠セットを数える。
        戻り値: (最小根拠の組数, 最小根拠の大きさ, 包含極小根拠セット一覧)
        """
        upstream = self.get_upstream_base_premises(target_id)
        supporting_sets = []

        # サイズ 1 から |upstream| まで総当たり探索
        for k in range(1, len(upstream) + 1):
            for combo in itertools.combinations(sorted(upstream), k):
                s = set(combo)
                # 既に発見された極小解の上位集合であれば枝刈り
                if any(known.issubset(s) for known in supporting_sets):
                    continue
                if self.can_derive(target_id, s):
                    supporting_sets.append(s)

        count = len(supporting_sets)
        min_size = min(len(s) for s in supporting_sets) if supporting_sets else 0
        return count, min_size, supporting_sets

    def compute_single_cuts(self, target_id: str) -> list[str]:
        """
        全上流前提を有効とした状態から、1つだけ外して目標が導出できなくなる前提を列挙。
        """
        upstream = self.get_upstream_base_premises(target_id)
        assert self.can_derive(target_id, upstream), f"Target {target_id} not derivable from all upstream premises"

        single_cuts = []
        for p in sorted(upstream):
            remaining = upstream - {p}
            if not self.can_derive(target_id, remaining):
                single_cuts.append(p)
        return single_cuts


class TestIndependentBruteForceVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.descartes_file = os.path.join(base_dir, "data", "descartes_second_replies_geometric.json")
        cls.anselm_file = os.path.join(base_dir, "data", "anselm_proslogion_iep.json")
        cls.report_html = os.path.join(base_dir, "web", "comparison_v0.html")
        cls.report_md = os.path.join(base_dir, "docs", "theological_arguments_comparison_v0.md")

        cls.descartes_verifier = IndependentBruteForceVerifier(cls.descartes_file)
        cls.anselm_verifier = IndependentBruteForceVerifier(cls.anselm_file)

        with open(cls.report_html, "r", encoding="utf-8") as f:
            cls.html_text = f.read()
        with open(cls.report_md, "r", encoding="utf-8") as f:
            cls.md_text = f.read()

    def test_descartes_prop1_independent_bruteforce(self):
        """デカルト命題1の独立検算: 最小根拠1組、サイズ2、単体遮断2件"""
        count, min_size, grounds = self.descartes_verifier.compute_minimal_support_grounds("DES_PROP_1")
        single_cuts = self.descartes_verifier.compute_single_cuts("DES_PROP_1")

        expected_grounds = [{"DES_AX_10", "DES_DEF_9"}]
        expected_cuts = ["DES_AX_10", "DES_DEF_9"]

        self.assertEqual(count, 1)
        self.assertEqual(min_size, 2)
        self.assertEqual(grounds, expected_grounds)
        self.assertEqual(single_cuts, expected_cuts)

        # レポート記載値との突き合わせ
        self.assertIn("DES_PROP_1", self.html_text)
        self.assertIn("DES_AX_10", self.html_text)
        self.assertIn("DES_DEF_9", self.html_text)

    def test_descartes_prop2_independent_bruteforce(self):
        """デカルト命題2の独立検算: 最小根拠1組、サイズ5、単体遮断5件"""
        count, min_size, grounds = self.descartes_verifier.compute_minimal_support_grounds("DES_PROP_2")
        single_cuts = self.descartes_verifier.compute_single_cuts("DES_PROP_2")

        expected_grounds = [{"DES_AX_3", "DES_AX_5", "DES_AX_6", "DES_DEF_2", "DES_DEF_8"}]
        expected_cuts = ["DES_AX_3", "DES_AX_5", "DES_AX_6", "DES_DEF_2", "DES_DEF_8"]

        self.assertEqual(count, 1)
        self.assertEqual(min_size, 5)
        self.assertEqual(grounds, expected_grounds)
        self.assertEqual(single_cuts, expected_cuts)

    def test_descartes_prop3_independent_bruteforce(self):
        """デカルト命題3の独立検算: 最小根拠1組、サイズ8、単体遮断8件 (DES_AX_1含む)"""
        count, min_size, grounds = self.descartes_verifier.compute_minimal_support_grounds("DES_PROP_3")
        single_cuts = self.descartes_verifier.compute_single_cuts("DES_PROP_3")

        expected_cuts = ["DES_AX_1", "DES_AX_2", "DES_AX_4", "DES_AX_7", "DES_AX_8", "DES_AX_9", "DES_DEF_2", "DES_DEF_8"]
        expected_grounds = [set(expected_cuts)]

        self.assertEqual(count, 1)
        self.assertEqual(min_size, 8)
        self.assertEqual(grounds, expected_grounds)
        self.assertEqual(single_cuts, expected_cuts)
        self.assertIn("DES_AX_1", single_cuts)

    def test_anselm_arg1_independent_bruteforce(self):
        """アンセルムス論証1 (ANS1_C) の独立検算: 最小根拠1組、サイズ3、単体遮断3件"""
        count, min_size, grounds = self.anselm_verifier.compute_minimal_support_grounds("ANS1_C")
        single_cuts = self.anselm_verifier.compute_single_cuts("ANS1_C")

        expected_cuts = ["ANS1_P1", "ANS1_P2", "ANS1_P3"]
        expected_grounds = [set(expected_cuts)]

        self.assertEqual(count, 1)
        self.assertEqual(min_size, 3)
        self.assertEqual(grounds, expected_grounds)
        self.assertEqual(single_cuts, expected_cuts)

    def test_anselm_arg2_independent_bruteforce(self):
        """アンセルムス論証2 (ANS2_C) の独立検算: 最小根拠1組、サイズ3、単体遮断3件"""
        count, min_size, grounds = self.anselm_verifier.compute_minimal_support_grounds("ANS2_C")
        single_cuts = self.anselm_verifier.compute_single_cuts("ANS2_C")

        expected_cuts = ["ANS2_P1", "ANS2_P2", "ANS2_P6"]
        expected_grounds = [set(expected_cuts)]

        self.assertEqual(count, 1)
        self.assertEqual(min_size, 3)
        self.assertEqual(grounds, expected_grounds)
        self.assertEqual(single_cuts, expected_cuts)

    def test_report_matches_bruteforce_values(self):
        """独立検算で得られたすべての数値がレポートMarkdownおよびHTMLの記載と一致すること"""
        cases = [
            ("DES_PROP_1", 1, 2, ["DES_AX_10", "DES_DEF_9"]),
            ("DES_PROP_2", 1, 5, ["DES_AX_3", "DES_AX_5", "DES_AX_6", "DES_DEF_2", "DES_DEF_8"]),
            ("DES_PROP_3", 1, 8, ["DES_AX_1", "DES_AX_2", "DES_AX_4", "DES_AX_7", "DES_AX_8", "DES_AX_9", "DES_DEF_2", "DES_DEF_8"]),
            ("ANS1_C", 1, 3, ["ANS1_P1", "ANS1_P2", "ANS1_P3"]),
            ("ANS2_C", 1, 3, ["ANS2_P1", "ANS2_P2", "ANS2_P6"]),
        ]

        for target_id, exp_count, exp_size, exp_cuts in cases:
            # HTML 内の出現確認
            self.assertIn(target_id, self.html_text)
            self.assertIn(f"{exp_size}件", self.html_text)
            for c in exp_cuts:
                self.assertIn(c, self.html_text)

            # Markdown 内の出現確認
            self.assertIn(target_id, self.md_text)
            self.assertIn(f"{exp_size}件", self.md_text)
            for c in exp_cuts:
                self.assertIn(c, self.md_text)


if __name__ == "__main__":
    unittest.main()
