"""
幾何学的哲学エンジン: 比較・思想進化・耐震性ベンチマークモジュール
デカルト、スピノザ、ライプニッツの三つ巴比較とカント批判耐性
"""
from typing import Dict, List, Tuple, Any
from engine.core import AxiomSystem, TruthValue
from engine.explorer import ThoughtExplorer

class ComparativePhilosophyEngine:
    def __init__(self):
        self.systems: Dict[str, AxiomSystem] = {}

    def register_system(self, key: str, json_path: str):
        sys = AxiomSystem(key)
        sys.load_json(json_path)
        self.systems[key] = sys

    def benchmark_kantian_earthquake(self, kant_json_path: str) -> Dict[str, Any]:
        """
        【耐震性ベンチマーク】
        カントの批判公理（存在論的証明の否定・物自体の不可知・現象論）を各体系にぶつけ、
        各合理論の「崩壊率」「生存率」「致命傷となった箇所」を定量比較する。
        """
        results = {}

        # 思想ごとのカントとの衝突マッピング
        conflict_map = {
            "Descartes": [
                ("KANT_AX_1", "DESC_PROP_2", "カントは完全性から存在を導くデカルトの存在論的証明を否定"),
                ("KANT_AX_3", "DESC_PROP_1", "デカルトの無限完全実体（神）の観念からの実在論証は物自体の認識不可能性と衝突")
            ],
            "Spinoza": [
                ("KANT_AX_1", "DEF_1", "カントは自己原因(本質が存在を含む)を述語規則違反として否定")
            ],
            "Leibniz": [
                ("KANT_AX_3", "LEIB_AX_4", "最善世界の客観的選択は超越的物自体の認識を要するため衝突")
            ]
        }

        for name, system in self.systems.items():
            # 一旦すべての前提を承認して演繹
            for node in system.nodes.values():
                if node.node_type in ["definition", "axiom"]:
                    node.value = TruthValue.TRUE
            system.deduce_all()

            total_props = len([n for n in system.nodes.values() if n.node_type == "proposition"])
            
            # カントを注入
            explorer = ThoughtExplorer(system)
            c_rules = conflict_map.get(name, [])
            report = explorer.diagnose_clash(kant_json_path, c_rules)

            survived_props = [
                n["id"] for n in report["surviving_nodes"]
                if system.nodes[n["id"]].node_type == "proposition"
            ]
            collapsed_props = [n["id"] for n in report["conflicts"] + report["collapsed_theorems"]]

            survival_rate = (len(survived_props) / total_props * 100) if total_props > 0 else 0

            results[name] = {
                "total_theorems": total_props,
                "survived_theorems_count": len(survived_props),
                "collapsed_theorems_count": len(collapsed_props),
                "survival_rate": round(survival_rate, 1),
                "collapsed_theorems": collapsed_props,
                "survived_theorems": survived_props
            }

        return results

    def compare_mind_body_solutions(self) -> Dict[str, Dict[str, str]]:
        """
        【心身問題の幾何学的三叉路】
        同一の対象（心・身体）に対して、3者がどのような公理・定理で着地したかを対比
        """
        return {
            "Descartes": {
                "stance": "実体二元論 (Substance Dualism)",
                "key_node": "DESC_PROP_3",
                "logic": "思惟を持つ心と、延長を持つ身体は完全に別個の実体である。神の誠実さにより両者の実在が保証される。"
            },
            "Spinoza": {
                "stance": "心身平行論 / 一元論 (Mind-Body Parallelism / Monism)",
                "key_node": "PROP_14, PROP_15",
                "logic": "心と身体は別個の実体ではなく、唯一の実体（神＝自然）が持つ二つの異なる属性（思惟と延長）の同じ現れである。"
            },
            "Leibniz": {
                "stance": "予定調和説 / モナド多元論 (Pre-established Harmony)",
                "key_node": "LEIB_PROP_2, LEIB_PROP_3",
                "logic": "物質（身体）は実体ではなく整序された現象にすぎない。心と身体の一致は直接の相互作用ではなく神の事前クロック同調による。"
            }
        }
