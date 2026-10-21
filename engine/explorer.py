"""
幾何学的思考エンジン 探索モジュール (Explorer)
未判明な思考領域の探索、反実仮想シミュレーション、思想対立分析
"""
from typing import Dict, List, Tuple
import itertools
from engine.core import AxiomSystem, TruthValue

class ThoughtExplorer:
    def __init__(self, system: AxiomSystem):
        self.system = system

    def snapshot(self) -> Dict[str, TruthValue]:
        return {node_id: node.value for node_id, node in self.system.nodes.items()}

    def restore(self, snap: Dict[str, TruthValue]):
        for node_id, val in snap.items():
            self.system.nodes[node_id].value = val

    def what_if(self, target_node_id: str, assume_value: TruthValue) -> Dict[str, any]:
        """
        【思考実験: 反実仮想】
        「もし命題Xの真偽値をYと仮定したら、世界全体はどう変わるか？」
        """
        before_snap = self.snapshot()

        # 仮定を注入
        target_node = self.system.nodes[target_node_id]
        target_node.override_value = assume_value
        target_node.value = assume_value

        # 全体を再演繹
        self.system.deduce_all()
        after_snap = self.snapshot()

        # 差分（影響を受けた命題群）を抽出
        impacted_nodes = []
        for node_id, new_val in after_snap.items():
            old_val = before_snap[node_id]
            if old_val != new_val:
                impacted_nodes.append({
                    "id": node_id,
                    "title": self.system.nodes[node_id].title,
                    "type": self.system.nodes[node_id].node_type,
                    "from": old_val.value,
                    "to": new_val.value
                })

        # 元に戻す
        target_node.override_value = None
        self.restore(before_snap)

        return {
            "hypothesis": {
                "id": target_node_id,
                "title": target_node.title,
                "assumed_value": assume_value.value
            },
            "impact_count": len(impacted_nodes),
            "impacted_nodes": impacted_nodes
        }

    def find_key_assumptions_for_frontier(self, frontier_prop_id: str) -> List[Dict[str, any]]:
        """
        【未判明思考のフロンティア探索】
        現在 UNKNOWN な定理 frontier_prop_id を TRUE にするために、
        どの定義・前提（UNKNOWNノード）を TRUE にすれば導出可能かを全探索する。
        """
        frontier_node = self.system.nodes.get(frontier_prop_id)
        if not frontier_node:
            return []

        # 現在 UNKNOWN の定義や前提ノードを抽出
        unknown_inputs = [
            node_id for node_id, node in self.system.nodes.items()
            if node.node_type in ["definition", "axiom"] and node.value == TruthValue.UNKNOWN
        ]

        valid_combinations = []
        base_snap = self.snapshot()

        # 1個から全個数までの組み合わせをテスト
        for r in range(1, len(unknown_inputs) + 1):
            for combo in itertools.combinations(unknown_inputs, r):
                # 選択したノードを仮に TRUE に設定
                for node_id in combo:
                    self.system.nodes[node_id].value = TruthValue.TRUE

                self.system.deduce_all()

                if self.system.nodes[frontier_prop_id].value == TruthValue.TRUE:
                    valid_combinations.append({
                        "required_assumptions": [
                            {"id": nid, "title": self.system.nodes[nid].title}
                            for nid in combo
                        ],
                        "total_assumptions_needed": len(combo)
                    })

                # 復元
                self.restore(base_snap)

            # 最小の仮定セットが見つかれば探索を早期終了
            if valid_combinations:
                break

        return valid_combinations

    def diagnose_clash(self, opponent_system_file: str, conflict_mappings: List[Tuple[str, str, str]]) -> Dict[str, any]:
        """
        【思想対立・批判の注入シミュレーション】
        スピノザの体系にカントの公理を注入したとき、
        どの定理が「自己原因の否定」により連鎖的に崩壊（FALSE / CONFLICT）するかを診断する。
        """
        before_snap = self.snapshot()
        before_nodes = list(self.system.nodes.keys())
        before_conflicts = list(self.system.conflicts)

        # 相手の公理系をロード
        self.system.load_json(opponent_system_file)
        for a, b, reason in conflict_mappings:
            self.system.add_conflict_rule(a, b, reason)

        # 演繹を実行
        self.system.deduce_all()

        collapsed_theorems = []
        conflicted_nodes = []
        surviving_nodes = []

        # 元のシステムのノードのみを評価
        for node_id in before_nodes:
            node = self.system.nodes[node_id]
            if node.value == TruthValue.CONFLICT:
                conflicted_nodes.append({"id": node_id, "title": node.title})
            elif node.value == TruthValue.FALSE:
                collapsed_theorems.append({"id": node_id, "title": node.title})
            elif node.value == TruthValue.TRUE:
                surviving_nodes.append({"id": node_id, "title": node.title})

        report = {
            "conflicts": conflicted_nodes,
            "collapsed_theorems": collapsed_theorems,
            "surviving_nodes": surviving_nodes
        }

        # 復元（追加された相手ノードを削除、conflicts復元、値復元）
        for node_id in list(self.system.nodes.keys()):
            if node_id not in before_nodes:
                del self.system.nodes[node_id]
        self.system.conflicts = before_conflicts
        self.restore(before_snap)
        return report
