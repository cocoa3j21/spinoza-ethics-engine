"""
幾何学的思考エンジン コアモジュール
公理・定義・定理の論理グラフ（DAG）と真偽値伝播
"""
import json
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

class TruthValue(Enum):
    FALSE = "FALSE"
    TRUE = "TRUE"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"

    def __repr__(self):
        return self.value


class LogicNode:
    def __init__(self, node_id: str, node_type: str, title: str, text_ja: str, logical_form: str, dependencies: Optional[List[str]] = None):
        self.id = node_id
        self.node_type = node_type  # 'definition', 'axiom', 'proposition'
        self.title = title
        self.text_ja = text_ja
        self.logical_form = logical_form
        self.dependencies = dependencies or []
        self.value: TruthValue = TruthValue.UNKNOWN
        self.source_system = ""
        self.override_value: Optional[TruthValue] = None

    def reset(self):
        """値を初期状態に戻す"""
        if self.override_value is not None:
            self.value = self.override_value
        elif self.node_type == "axiom":
            # 公理は原則としてその公理系の中では TRUE
            self.value = TruthValue.TRUE
        else:
            self.value = TruthValue.UNKNOWN

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.node_type,
            "title": self.title,
            "value": self.value.value,
            "dependencies": self.dependencies
        }


class AxiomSystem:
    def __init__(self, name: str):
        self.name = name
        self.nodes: Dict[str, LogicNode] = {}
        # 衝突ルール（思想間の対立定義: 例: KANT_AX_1 と SPINOZA_DEF_1 は両立しない）
        self.conflicts: List[Tuple[str, str, str]] = []

    def load_json(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        system_name = data.get("system", self.name)
        for item in data.get("nodes", []):
            node = LogicNode(
                node_id=item["id"],
                node_type=item["type"],
                title=item["title"],
                text_ja=item["text_ja"],
                logical_form=item.get("logical_form", ""),
                dependencies=item.get("dependencies", [])
            )
            node.source_system = system_name
            node.reset()
            self.nodes[node.id] = node

    def add_conflict_rule(self, node_id_a: str, node_id_b: str, reason: str):
        """2つの命題・公理が排他的（両立不能）であることを登録"""
        self.conflicts.append((node_id_a, node_id_b, reason))

    def evaluate_node(self, node_id: str, visited: Optional[Set[str]] = None) -> TruthValue:
        """依存関係を再帰的に評価して真理値を計算"""
        if visited is None:
            visited = set()

        if node_id in visited:
            # 循環依存防止
            return self.nodes[node_id].value

        visited.add(node_id)
        node = self.nodes[node_id]

        # 既に上書きされている場合や、公理で変更がない場合はそのまま
        if node.override_value is not None:
            node.value = node.override_value
            return node.value

        # 既に矛盾(CONFLICT)としてマークされている場合はそれを維持
        if node.value == TruthValue.CONFLICT:
            return node.value

        if node.node_type == "axiom":
            return node.value

        # 定義（definition）: ユーザーが前提として認めるかどうかに依存
        if node.node_type == "definition":
            return node.value

        # 定理（proposition）: 依存する全ての前提が TRUE であれば TRUE
        if not node.dependencies:
            return node.value

        # 未定義IDの安全ガード
        dep_values = []
        for dep_id in node.dependencies:
            if dep_id not in self.nodes:
                # 未定義ノードへの依存は成立不能 (UNKNOWN)
                dep_values.append(TruthValue.UNKNOWN)
            else:
                dep_values.append(self.evaluate_node(dep_id, visited.copy()))

        # 依存先に CONFLICT があれば CONFLICT
        if any(v == TruthValue.CONFLICT for v in dep_values):
            node.value = TruthValue.CONFLICT
        # 全ての前提が TRUE なら証明完了（TRUE）
        elif all(v == TruthValue.TRUE for v in dep_values):
            node.value = TruthValue.TRUE
        else:
            # 前提が不足している場合や FALSE が含まれる場合は未解決 (UNKNOWN)
            # 前件否定から結論の否定を導いてはならない
            node.value = TruthValue.UNKNOWN

        return node.value

    def _check_conflicts(self) -> bool:
        """衝突ルールの適用。状態変更があれば True を返す"""
        changed = False
        for id_a, id_b, reason in self.conflicts:
            if id_a in self.nodes and id_b in self.nodes:
                val_a = self.nodes[id_a].value
                val_b = self.nodes[id_b].value
                if val_a == TruthValue.TRUE and val_b == TruthValue.TRUE:
                    self.nodes[id_a].value = TruthValue.CONFLICT
                    self.nodes[id_b].value = TruthValue.CONFLICT
                    changed = True
        return changed

    def deduce_all(self):
        """システム全体の全命題を演繹・評価する（不動点反復）"""
        # 1. 初期対立チェック
        self._check_conflicts()

        # 2. 定理の演繹と衝突チェックの連動反復
        changed = True
        iterations = 0
        while changed and iterations < 100:
            changed = False
            iterations += 1
            for node_id, node in self.nodes.items():
                if node.node_type == "proposition":
                    prev = node.value
                    new_val = self.evaluate_node(node_id)
                    if new_val != prev:
                        changed = True

            # 演繹によって新たに成立した命題の衝突も検知
            if self._check_conflicts():
                changed = True

    def get_status_summary(self) -> Dict[str, List[str]]:
        """真理値ごとのノード一覧を集計"""
        summary = {
            "TRUE": [],
            "FALSE": [],
            "UNKNOWN": [],
            "CONFLICT": []
        }
        for node_id, node in self.nodes.items():
            summary[node.value.value].append(node_id)
        return summary
