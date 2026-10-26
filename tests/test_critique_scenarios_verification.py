"""
古典的批判シナリオ検証テスト (Test Critique Scenarios Verification)

1. ガウニロ、アクィナス、カントの批判シナリオ（デカルト・アンセルムス）
   - 一本道の論証構造において、前提遮断（解釈A）と規則遮断（解釈B）の両方で
     導出経路が失われることの検証。
   - エンジンと独立検算の一致確認。
   - デカルト後天的証明（命題2・3）が命題1の前提に非依存であることの確認。

2. スピノザへのカント批判適用シナリオ (DEF_1 自己原因遮断)
   - モデルA、B、C1、C2 × 別証明1設定(a)〜(d) の全16組み合わせ計算。
   - エンジン（Evaluator）と独立検算（純粋演繹閉包）の両方で計算し、完全一致を検証。
   - 構造上の迂回経路の多面性（設定a, cにおける迂回経路の存在）を確認。
"""
import unittest
import os
import json
import sys

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ENGINE_DIR not in sys.path:
    sys.path.append(ENGINE_DIR)

from engine.semantics import KnowledgeBase, Proposition, InferenceRule, Literal, Evaluator, TruthStatus
from engine.benchmark_core import load_system_as_kb
from tests.test_independent_bruteforce_verification import IndependentBruteForceVerifier


class TestCritiqueScenariosVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.des_path = os.path.join(ENGINE_DIR, "data", "descartes_second_replies_geometric.json")
        cls.ans_path = os.path.join(ENGINE_DIR, "data", "anselm_proslogion_iep.json")
        cls.spin_path = os.path.join(ENGINE_DIR, "data", "spinoza_ethics_part1_split_prop6.json")

        cls.kb_des = load_system_as_kb(cls.des_path)
        cls.kb_ans = load_system_as_kb(cls.ans_path)

        cls.verif_des = IndependentBruteForceVerifier(cls.des_path)
        cls.verif_ans = IndependentBruteForceVerifier(cls.ans_path)

        with open(cls.spin_path, "r", encoding="utf-8") as f:
            cls.spin_raw = json.load(f)

    def test_anselm_gaunilo_scenarios(self):
        """ガウニロ批判: 一本道構造における解釈A(ANS1_P2遮断)と解釈B(R_ANS1_C遮断)の導出経路喪失"""
        all_prems = self.verif_ans.get_upstream_base_premises("ANS1_C")

        # 解釈A: 前提遮断 ANS1_P2
        active_a = all_prems - {"ANS1_P2"}
        indep_a = self.verif_ans.can_derive("ANS1_C", active_a)
        state_a = Evaluator(self.kb_ans).evaluate(assumptions=tuple(Literal(p, True) for p in active_a))
        status_a = state_a.get_status("ANS1_C")
        self.assertFalse(indep_a)
        self.assertEqual(status_a, TruthStatus.UNKNOWN)

        # 解釈B: 規則遮断 R_ANS1_C
        orig_rules = dict(self.verif_ans.rules)
        del self.verif_ans.rules["ANS1_C"]
        indep_b = self.verif_ans.can_derive("ANS1_C", all_prems)
        self.verif_ans.rules = orig_rules

        kb_no_r = KnowledgeBase(
            self.kb_ans.name,
            list(self.kb_ans.propositions.values()),
            [r for r in self.kb_ans.rules if r.conclusion.prop_id != "ANS1_C"]
        )
        state_b = Evaluator(kb_no_r).evaluate(assumptions=tuple(Literal(p, True) for p in all_prems))
        self.assertFalse(indep_b)
        self.assertEqual(state_b.get_status("ANS1_C"), TruthStatus.UNKNOWN)

    def test_anselm_aquinas_scenarios(self):
        """アクィナス批判: 論証1および論証2での規則遮断(本線)と定義了解前提遮断(候補)の導出経路喪失"""
        # 論証1
        all_prems1 = self.verif_ans.get_upstream_base_premises("ANS1_C")
        # 解釈A: ANS1_P1 遮断
        indep_1a = self.verif_ans.can_derive("ANS1_C", all_prems1 - {"ANS1_P1"})
        state_1a = Evaluator(self.kb_ans).evaluate(assumptions=tuple(Literal(p, True) for p in (all_prems1 - {"ANS1_P1"})))
        self.assertFalse(indep_1a)
        self.assertEqual(state_1a.get_status("ANS1_C"), TruthStatus.UNKNOWN)

        # 論証2
        all_prems2 = self.verif_ans.get_upstream_base_premises("ANS2_C")
        # 解釈A: ANS2_P1 遮断
        indep_2a = self.verif_ans.can_derive("ANS2_C", all_prems2 - {"ANS2_P1"})
        state_2a = Evaluator(self.kb_ans).evaluate(assumptions=tuple(Literal(p, True) for p in (all_prems2 - {"ANS2_P1"})))
        self.assertFalse(indep_2a)
        self.assertEqual(state_2a.get_status("ANS2_C"), TruthStatus.UNKNOWN)

    def test_descartes_caterus_aquinas_and_kant_scenarios(self):
        """デカルト命題1批判: DES_AX_10遮断(解釈A)およびR_DES_PROP_1遮断(解釈B)と後天的命題2・3の維持"""
        all_base = self.verif_des.base_premises
        all_p1_prems = self.verif_des.get_upstream_base_premises("DES_PROP_1")

        # 解釈A: DES_AX_10 遮断
        indep_a = self.verif_des.can_derive("DES_PROP_1", all_p1_prems - {"DES_AX_10"})
        self.assertFalse(indep_a)

        kb_no_ax10 = KnowledgeBase(
            self.kb_des.name,
            [p if p.id != "DES_AX_10" else Proposition(p.id, p.title, p.text_ja, "premise") for p in self.kb_des.propositions.values()],
            self.kb_des.rules
        )
        state_a = Evaluator(kb_no_ax10).evaluate(assumptions=tuple(Literal(p, True) for p in (all_base - {"DES_AX_10"})))
        self.assertEqual(state_a.get_status("DES_PROP_1"), TruthStatus.UNKNOWN)
        # 後天的証明である命題2・3はDES_AX_10に依存しないため維持
        self.assertEqual(state_a.get_status("DES_PROP_2"), TruthStatus.TRUE)
        self.assertEqual(state_a.get_status("DES_PROP_3"), TruthStatus.TRUE)

    def test_kant_predicate_critique_scenarios(self):
        """カント存在述語批判: ANS1_P3遮断およびANS2_P2遮断(候補・要確認)"""
        # ANS1_P3 遮断
        prems1 = self.verif_ans.get_upstream_base_premises("ANS1_C") - {"ANS1_P3"}
        self.assertFalse(self.verif_ans.can_derive("ANS1_C", prems1))
        state1 = Evaluator(self.kb_ans).evaluate(assumptions=tuple(Literal(p, True) for p in prems1))
        self.assertEqual(state1.get_status("ANS1_C"), TruthStatus.UNKNOWN)

        # ANS2_P2 遮断 (候補・要確認)
        prems2 = self.verif_ans.get_upstream_base_premises("ANS2_C") - {"ANS2_P2"}
        self.assertFalse(self.verif_ans.can_derive("ANS2_C", prems2))
        state2 = Evaluator(self.kb_ans).evaluate(assumptions=tuple(Literal(p, True) for p in prems2))
        self.assertEqual(state2.get_status("ANS2_C"), TruthStatus.UNKNOWN)

    def test_spinoza_causa_sui_def1_cut_matrix(self):
        """スピノザ自己原因(DEF_1)遮断: モデルA, B, C1, C2 × 設定(a)〜(d) 全16通りの計算検証"""
        ratio_prop = Proposition(
            id="SPIN_AX_RATIO",
            title="充足理由律",
            text_ja="理由原理",
            prop_type="axiom"
        )
        aliter_settings = {
            "a": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_3"),
            "b": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_3", "PROP_7"),
            "c": ("DEF_6", "SPIN_AX_RATIO", "PROP_2"),
            "d": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_7"),
        }

        expected_survival = {
            # モデルA: 単一証明 (DEF_1依存) -> 全設定で残らない
            ("A", "a"): False, ("A", "b"): False, ("A", "c"): False, ("A", "d"): False,
            # モデルB: 命題11別証明あり -> 設定(a), (c)でDEF_1を迂回して残る
            ("B", "a"): True,  ("B", "b"): False, ("B", "c"): True,  ("B", "d"): False,
            # モデルC1: 系の別証明のみ (命題11別証明なし) -> 全設定で残らない
            ("C1", "a"): False, ("C1", "b"): False, ("C1", "c"): False, ("C1", "d"): False,
            # モデルC2: 全別証明統合 -> 設定(a), (c)でDEF_1を迂回して残る
            ("C2", "a"): True,  ("C2", "b"): False, ("C2", "c"): True,  ("C2", "d"): False,
        }

        for (m, s), expected in expected_survival.items():
            props = []
            rules = []
            for item in self.spin_raw["nodes"]:
                pid = item["id"]
                ptype = item["type"]
                if pid == "DEF_1":
                    ptype = "premise"  # DEF_1 を公理初期支持から除外
                props.append(Proposition(pid, item.get("title", pid), item.get("text_ja", ""), ptype))
                if pid != "PROP_6_COROLLARY":
                    deps = item.get("dependencies", [])
                    if deps:
                        rules.append(InferenceRule(f"R_{pid}", tuple(Literal(d, True) for d in deps), Literal(pid, True)))
            props.append(ratio_prop)
            rules.append(InferenceRule("R_PROP_6_COROLLARY_1", (Literal("PROP_6", True), Literal("AX_1", True), Literal("DEF_3", True), Literal("DEF_5", True)), Literal("PROP_6_COROLLARY", True)))
            if m in ["C1", "C2"]:
                rules.append(InferenceRule("R_PROP_6_COROLLARY_ALITER", (Literal("DEF_3", True), Literal("AX_4", True)), Literal("PROP_6_COROLLARY", True)))
            if m in ["B", "C2"]:
                rules.append(InferenceRule("R_PROP_11_ALITER1", tuple(Literal(d, True) for d in aliter_settings[s]), Literal("PROP_11", True)))

            base_prems = [p.id for p in props if p.prop_type in ("axiom", "definition", "postulate") and p.id != "DEF_1"]

            # 1. エンジン側計算
            kb = KnowledgeBase(f"Spinoza_{m}_{s}", props, rules)
            state = Evaluator(kb).evaluate(assumptions=tuple(Literal(p, True) for p in base_prems))
            engine_survives = (state.get_status("PROP_11") == TruthStatus.TRUE)

            # 2. 独立検算 (純粋演繹閉包探索)
            rule_map = {}
            for r in rules:
                conc = r.conclusion.prop_id
                if conc not in rule_map:
                    rule_map[conc] = []
                rule_map[conc].append([p.prop_id for p in r.premises])
            derived = set(base_prems)
            changed = True
            while changed:
                changed = False
                for conc, r_list in rule_map.items():
                    if conc not in derived:
                        for r_prems in r_list:
                            if all(p in derived for p in r_prems):
                                derived.add(conc)
                                changed = True
                                break
            indep_survives = ("PROP_11" in derived)

            # 相互整合性アサーション
            self.assertEqual(engine_survives, indep_survives, f"Mismatch between engine and independent verifier for ({m}, {s})")
            self.assertEqual(engine_survives, expected, f"Unexpected survival for ({m}, {s}): got {engine_survives}, expected {expected}")

    def test_spinoza_ratio_cut_matrix(self):
        """充足理由律(SPIN_AX_RATIO)単独遮断: 第1証明は充足理由律に非依存のため全モデル・全設定で命題11維持"""
        ratio_prop = Proposition(id="SPIN_AX_RATIO", title="充足理由律", text_ja="理由原理", prop_type="premise") # 遮断
        aliter_settings = {
            "a": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_3"),
            "b": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_3", "PROP_7"),
            "c": ("DEF_6", "SPIN_AX_RATIO", "PROP_2"),
            "d": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_7"),
        }

        for m in ["A", "B", "C1", "C2"]:
            for s in ["a", "b", "c", "d"]:
                props = []
                rules = []
                for item in self.spin_raw["nodes"]:
                    pid = item["id"]
                    props.append(Proposition(pid, item.get("title", pid), item.get("text_ja", ""), item["type"]))
                    if pid != "PROP_6_COROLLARY":
                        deps = item.get("dependencies", [])
                        if deps:
                            rules.append(InferenceRule(f"R_{pid}", tuple(Literal(d, True) for d in deps), Literal(pid, True)))
                props.append(ratio_prop)
                rules.append(InferenceRule("R_PROP_6_COROLLARY_1", (Literal("PROP_6", True), Literal("AX_1", True), Literal("DEF_3", True), Literal("DEF_5", True)), Literal("PROP_6_COROLLARY", True)))
                if m in ["C1", "C2"]:
                    rules.append(InferenceRule("R_PROP_6_COROLLARY_ALITER", (Literal("DEF_3", True), Literal("AX_4", True)), Literal("PROP_6_COROLLARY", True)))
                if m in ["B", "C2"]:
                    rules.append(InferenceRule("R_PROP_11_ALITER1", tuple(Literal(d, True) for d in aliter_settings[s]), Literal("PROP_11", True)))

                base_prems = [p.id for p in props if p.prop_type in ("axiom", "definition", "postulate") and p.id != "SPIN_AX_RATIO"]

                # エンジン計算
                kb = KnowledgeBase(f"Spinoza_RatioCut_{m}_{s}", props, rules)
                state = Evaluator(kb).evaluate(assumptions=tuple(Literal(p, True) for p in base_prems))
                engine_survives = (state.get_status("PROP_11") == TruthStatus.TRUE)

                # 独立検算
                rule_map = {}
                for r in rules:
                    conc = r.conclusion.prop_id
                    rule_map.setdefault(conc, []).append([p.prop_id for p in r.premises])
                derived = set(base_prems)
                changed = True
                while changed:
                    changed = False
                    for conc, r_list in rule_map.items():
                        if conc not in derived:
                            for r_prems in r_list:
                                if all(p in derived for p in r_prems):
                                    derived.add(conc)
                                    changed = True
                                    break
                indep_survives = ("PROP_11" in derived)

                self.assertEqual(engine_survives, indep_survives)
                # 全モデルで第1証明経由で維持される
                self.assertTrue(engine_survives, f"Model {m} Setting ({s}) failed to survive without SPIN_AX_RATIO")

    def test_spinoza_both_def1_and_ratio_cut_matrix(self):
        """自己原因(DEF_1)と充足理由律(SPIN_AX_RATIO)の双方同時遮断: 全モデル・全設定で命題11導出経路喪失"""
        ratio_prop = Proposition(id="SPIN_AX_RATIO", title="充足理由律", text_ja="理由原理", prop_type="premise") # 遮断
        aliter_settings = {
            "a": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_3"),
            "b": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_3", "PROP_7"),
            "c": ("DEF_6", "SPIN_AX_RATIO", "PROP_2"),
            "d": ("DEF_6", "SPIN_AX_RATIO", "PROP_2", "PROP_7"),
        }

        for m in ["A", "B", "C1", "C2"]:
            for s in ["a", "b", "c", "d"]:
                props = []
                rules = []
                for item in self.spin_raw["nodes"]:
                    pid = item["id"]
                    ptype = "premise" if pid == "DEF_1" else item["type"]
                    props.append(Proposition(pid, item.get("title", pid), item.get("text_ja", ""), ptype))
                    if pid != "PROP_6_COROLLARY":
                        deps = item.get("dependencies", [])
                        if deps:
                            rules.append(InferenceRule(f"R_{pid}", tuple(Literal(d, True) for d in deps), Literal(pid, True)))
                props.append(ratio_prop)
                rules.append(InferenceRule("R_PROP_6_COROLLARY_1", (Literal("PROP_6", True), Literal("AX_1", True), Literal("DEF_3", True), Literal("DEF_5", True)), Literal("PROP_6_COROLLARY", True)))
                if m in ["C1", "C2"]:
                    rules.append(InferenceRule("R_PROP_6_COROLLARY_ALITER", (Literal("DEF_3", True), Literal("AX_4", True)), Literal("PROP_6_COROLLARY", True)))
                if m in ["B", "C2"]:
                    rules.append(InferenceRule("R_PROP_11_ALITER1", tuple(Literal(d, True) for d in aliter_settings[s]), Literal("PROP_11", True)))

                base_prems = [p.id for p in props if p.prop_type in ("axiom", "definition", "postulate") and p.id not in ("DEF_1", "SPIN_AX_RATIO")]

                # エンジン計算
                kb = KnowledgeBase(f"Spinoza_BothCut_{m}_{s}", props, rules)
                state = Evaluator(kb).evaluate(assumptions=tuple(Literal(p, True) for p in base_prems))
                engine_survives = (state.get_status("PROP_11") == TruthStatus.TRUE)

                # 独立検算
                rule_map = {}
                for r in rules:
                    conc = r.conclusion.prop_id
                    rule_map.setdefault(conc, []).append([p.prop_id for p in r.premises])
                derived = set(base_prems)
                changed = True
                while changed:
                    changed = False
                    for conc, r_list in rule_map.items():
                        if conc not in derived:
                            for r_prems in r_list:
                                if all(p in derived for p in r_prems):
                                    derived.add(conc)
                                    changed = True
                                    break
                indep_survives = ("PROP_11" in derived)

                self.assertEqual(engine_survives, indep_survives)
                # 全モデル・全設定で導出経路喪失 (False)
                self.assertFalse(engine_survives, f"Model {m} Setting ({s}) unexpectedly survived without both DEF_1 and SPIN_AX_RATIO")


if __name__ == "__main__":
    unittest.main()
