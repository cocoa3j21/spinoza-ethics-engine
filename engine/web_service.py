"""
幾何学的哲学エンジン: Web UI バックエンドサービス層 (v0.1 diagnostic_monotone 統一版)
哲学体系の状態管理、APIリクエストのディスパッチ、DAGグラフデータ変換

【推論意味論の統一仕様】
- 推論コアは v0.1 diagnostic_monotone の Evaluator を全機能で一元使用。
- 旧 engine/core.py は互換用途として温存するが、標準Web操作からは完全排除。
- グラフ描画用データ変換と推論処理を厳密に分離。
- 前提トグルごとに独立シナリオとして再計算し、他シナリオを汚染しない。
- 「前提の不採用」と「否定支持の追加」を明確に区別。
- 背景条件検証層（ScenarioPreconditionChecker）によるガードを保持。
"""
import os
import json
from typing import Dict, Any, List, Optional, Set, Tuple

from engine.semantics import (
    KnowledgeBase,
    Proposition,
    InferenceRule,
    ConflictPair,
    UndercutDefeater,
    Literal,
    TruthStatus,
    SemanticsMode,
    ScenarioOptions,
    EvaluationStatus,
    Evaluator,
    EvaluationState,
)
from engine.benchmark_core import load_system_as_kb
from engine.scenario_validator import ScenarioPreconditionChecker, BackgroundPreconditionError
from engine.search import MinimalAssumptionSearch


class PhilosophyWebService:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.data_dir = os.path.join(base_dir, "data")
        self.kant_file = os.path.join(self.data_dir, "kant_critique.json")

        self.system_files = {
            "Spinoza": {
                "name": "スピノザ 『エチカ』第1部「神について」",
                "file": os.path.join(self.data_dir, "spinoza_ethics_part1_split_prop6.json"),
                "description": "実体一元論・心身平行論・幾何学的演繹の金字塔"
            },
            "Descartes": {
                "name": "デカルト 『幾何学的順序による論証』",
                "file": os.path.join(self.data_dir, "descartes_geometric.json"),
                "description": "実体二元論（思惟と延長）・神の誠実さによる物質世界の実在証明"
            },
            "Leibniz": {
                "name": "ライプニッツ 『モナドロジー』",
                "file": os.path.join(self.data_dir, "leibniz_monadology.json"),
                "description": "単子（モナド）多元論・充足理由律・予定調和説"
            },
            "Kant": {
                "name": "カント 『純粋理性批判』",
                "file": self.kant_file,
                "description": "存在論的証明批判・物自体の不可知・先験的感性論"
            }
        }

        # カント批判公理と各体系の無効化（Undercut）規則
        self.undercut_map = {
            "Descartes": [
                UndercutDefeater(
                    Literal("KANT_AX_1", True),
                    "R_DESC_PROP_2",
                    "カントの存在論的証明批判 -> 神の必然的存在論証規則 R_DESC_PROP_2 を無効化"
                ),
            ],
            "Spinoza": [
                UndercutDefeater(
                    Literal("KANT_AX_1", True),
                    "R_PROP_7",
                    "カントの存在論的証明批判 -> 実体の自己存在性規則 R_PROP_7 を無効化"
                ),
            ],
            "Leibniz": [
                UndercutDefeater(
                    Literal("KANT_AX_3", True),
                    "R_LEIB_PROP_2",
                    "カントは超越的知性による可能世界選択の認識妥当性を無効化"
                ),
            ],
        }

        # 生データとシナリオ状態のキャッシュ
        self.raw_data: Dict[str, Dict[str, Any]] = {}
        self.kant_props: List[Proposition] = []
        self.system_scenarios: Dict[str, Dict[str, Any]] = {}

        self._init_systems()

    def _init_systems(self):
        """全体系の初期ロードおよびベースラインシナリオの初期化"""
        self.raw_data.clear()
        self.system_scenarios.clear()

        # カント批判命題のロード
        if os.path.exists(self.kant_file):
            with open(self.kant_file, "r", encoding="utf-8") as f:
                k_data = json.load(f)
            self.kant_props = [
                Proposition(
                    id=item["id"],
                    title=item["title"],
                    text_ja=item.get("text_ja", ""),
                    prop_type=item["type"],
                    logical_form=item.get("logical_form", ""),
                    source_system=k_data.get("system", "Kant"),
                )
                for item in k_data.get("nodes", [])
            ]

        # 各体系の生データロードと初期シナリオ設定
        for key, info in self.system_files.items():
            if not os.path.exists(info["file"]):
                self.raw_data[key] = {"system": key, "nodes": []}
                self.system_scenarios[key] = {
                    "active_premises": set(),
                    "injected_critiques": set(),
                    "is_kant_injected": False,
                }
                continue

            with open(info["file"], "r", encoding="utf-8") as f:
                data = json.load(f)
            self.raw_data[key] = data

            # 初期ベースライン: 全公理・全定義を採用、批判なし
            all_premises = set()
            for node in data.get("nodes", []):
                if node.get("type") in ("axiom", "definition"):
                    all_premises.add(node["id"])

            self.system_scenarios[key] = {
                "active_premises": set(all_premises),
                "injected_critiques": set(),
                "is_kant_injected": False,
            }

    def _get_all_premises(self, key: str) -> Set[str]:
        """指定体系のすべての前提（公理・定義）IDセットを取得"""
        if key not in self.raw_data:
            return set()
        premises = set()
        for node in self.raw_data[key].get("nodes", []):
            if node.get("type") in ("axiom", "definition"):
                premises.add(node["id"])
        return premises

    def _evaluate_scenario(
        self,
        key: str,
        active_premises: Set[str],
        injected_critiques: Set[str]
    ) -> Tuple[EvaluationState, KnowledgeBase, Dict[str, Any]]:
        """
        指定シナリオ（採用前提・注入批判）に基づき、
        v0.1 diagnostic_monotone の Evaluator で独立評価を実行する。
        （副作用なし・純粋計算）
        """
        if key not in self.system_files:
            raise ValueError(f"System not found: {key}")

        file_path = self.system_files[key]["file"]

        # 1. 背景公理前提条件チェック (ScenarioPreconditionChecker)
        req_bg = ScenarioPreconditionChecker.extract_required_background_axioms(file_path)
        if req_bg:
            for target_id, bg_set in req_bg.items():
                missing = bg_set - active_premises
                if missing:
                    raise BackgroundPreconditionError(
                        f"背景前提エラー: 命題 '{target_id}' に必要な固定背景公理 {missing} が採用されていません。"
                    )

        # 2. KnowledgeBase の構築
        raw_kb = load_system_as_kb(file_path)
        propositions = list(raw_kb.propositions.values())
        undercuts = list(raw_kb.undercuts)

        # カント批判が注入されている場合、カント命題と該当体系の Undercut 規則を追加
        if injected_critiques and key != "Kant":
            propositions.extend(self.kant_props)
            system_undercuts = self.undercut_map.get(key, [])
            undercuts.extend(system_undercuts)

        # 公理の制御性 (Controllability) を担保:
        # 不採用にされた公理は、自動初期支持されないよう prop_type を 'assumption' に一時置換
        controlled_props = []
        for p in propositions:
            if p.prop_type == "axiom" and p.source_system == raw_kb.name:
                if p.id not in active_premises:
                    controlled_props.append(
                        Proposition(
                            id=p.id,
                            title=p.title,
                            text_ja=p.text_ja,
                            prop_type="assumption",
                            logical_form=p.logical_form,
                            source_system=p.source_system,
                            source_ref=p.source_ref,
                            is_provisional=p.is_provisional,
                        )
                    )
                else:
                    controlled_props.append(p)
            else:
                controlled_props.append(p)

        kb = KnowledgeBase(
            name=raw_kb.name,
            propositions=controlled_props,
            rules=raw_kb.rules,
            conflicts=raw_kb.conflicts,
            undercuts=undercuts,
        )

        # 3. 採用前提リテラルの準備 (定義のうち採用されているものを assumptions として渡す)
        # ※採用公理は prop_type == 'axiom' のため Evaluator が自動で正支持を付与
        def_assumptions = [
            Literal(p.id, True) for p in kb.propositions.values()
            if p.prop_type == "definition" and p.id in active_premises
        ]

        # 4. 批判リテラルの準備
        critique_literals = [Literal(cid, True) for cid in injected_critiques]

        # 5. v0.1 diagnostic_monotone による不動点評価
        evaluator = Evaluator(kb)
        opts = ScenarioOptions(mode=SemanticsMode.DIAGNOSTIC_MONOTONE)
        state = evaluator.evaluate(
            assumptions=def_assumptions,
            injected_critiques=critique_literals,
            options=opts
        )

        all_premises = self._get_all_premises(key)
        omitted_premises = sorted(list(all_premises - active_premises))
        is_baseline = (len(injected_critiques) == 0 and len(omitted_premises) == 0)

        scenario_info = {
            "system": key,
            "model_version": "v0.1",
            "semantics_mode": "diagnostic_monotone",
            "evaluation_status": state.status.value,
            "is_complete": state.is_complete,
            "total_premises": len(all_premises),
            "active_premises_count": len(active_premises),
            "omitted_premises": omitted_premises,
            "injected_critiques": sorted(list(injected_critiques)),
            "is_baseline": is_baseline,
        }

        return state, kb, scenario_info

    def _convert_to_graph_data(
        self,
        key: str,
        state: EvaluationState,
        kb: KnowledgeBase,
        scenario_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        推論結果 EvaluationState と KnowledgeBase から
        UIグラフ描画用の辞書データ（ノード・エッジ・サマリー）を生成する。
        （推論処理と描画データ変換の厳密な分離）
        """
        nodes_data = []
        edges_data = []

        summary = {
            "TRUE": 0,
            "FALSE": 0,
            "UNKNOWN": 0,
            "CONFLICT": 0,
            "total_theorems": 0,
            "survived_theorems": 0,
            "collapsed_theorems": 0,
            "unsupported_theorems": 0,
        }

        raw_sys_data = self.raw_data.get(key, {})
        raw_node_map = {n["id"]: n for n in raw_sys_data.get("nodes", [])}
        active_premises = self.system_scenarios[key]["active_premises"]

        # ノード変換
        for p in kb.propositions.values():
            # カント命題が注入されている場合も含め処理
            status = state.get_status(p.id)
            val_str = status.name
            raw_meta = raw_node_map.get(p.id, {})

            # 元のタイプ（公理、定義、定理）を保持
            orig_type = raw_meta.get("type", p.prop_type)
            is_premise = orig_type in ("axiom", "definition")
            is_active = p.id in active_premises if is_premise else True

            # 体系内の命題について集計
            if p.source_system == raw_sys_data.get("system", key):
                summary[val_str] = summary.get(val_str, 0) + 1
                if orig_type == "proposition":
                    summary["total_theorems"] += 1
                    if status == TruthStatus.TRUE:
                        summary["survived_theorems"] += 1
                    elif status in (TruthStatus.FALSE, TruthStatus.CONFLICT):
                        summary["collapsed_theorems"] += 1
                    else:
                        summary["unsupported_theorems"] += 1

            deps = raw_meta.get("dependencies", [])
            nodes_data.append({
                "id": p.id,
                "type": orig_type,
                "title": p.title,
                "text_ja": p.text_ja,
                "logical_form": p.logical_form,
                "value": val_str,
                "is_premise": is_premise,
                "is_active_premise": is_active,
                "dependencies": deps,
                "source_system": p.source_system,
            })

            # エッジ生成 (前提 -> 結論)
            for dep_id in deps:
                dep_status = state.get_status(dep_id)
                dep_val = dep_status.name

                # エッジステータス判定:
                # - 前提がFALSE: broken
                # - 前提がCONFLICT: conflict
                # - 前提がUNKNOWN: unsupported (支持未達)
                # - 前提がTRUE: normal (有効)
                if dep_val == "FALSE":
                    edge_status = "broken"
                elif dep_val == "CONFLICT":
                    edge_status = "conflict"
                elif dep_val == "UNKNOWN":
                    edge_status = "unsupported"
                else:
                    edge_status = "normal"

                # もし結論に至る規則が Undercut されている場合
                target_rule_id = f"R_{p.id}"
                if target_rule_id in state.undercut_rules:
                    edge_status = "broken"

                edges_data.append({
                    "from": dep_id,
                    "to": p.id,
                    "status": edge_status,
                })

        theorems_count = summary["total_theorems"]
        survival_rate = (summary["survived_theorems"] / theorems_count * 100) if theorems_count > 0 else 0.0

        return {
            "system_id": key,
            "system_name": self.system_files[key]["name"],
            "description": self.system_files[key]["description"],
            "nodes": nodes_data,
            "edges": edges_data,
            "summary": summary,
            "survival_rate": round(survival_rate, 1),
            "model_version": "v0.1",
            "semantics_mode": "diagnostic_monotone",
            "scenario_info": scenario_info,
        }

    def get_systems_list(self) -> List[Dict[str, Any]]:
        """利用可能な哲学体系のメタ情報リストを返す"""
        result = []
        for key, info in self.system_files.items():
            raw = self.raw_data.get(key, {})
            nodes = raw.get("nodes", [])
            nodes_count = len(nodes)
            axioms_count = len([n for n in nodes if n.get("type") == "axiom"])
            defs_count = len([n for n in nodes if n.get("type") == "definition"])
            props_count = len([n for n in nodes if n.get("type") == "proposition"])

            result.append({
                "id": key,
                "name": info["name"],
                "description": info["description"],
                "total_nodes": nodes_count,
                "axioms_count": axioms_count,
                "definitions_count": defs_count,
                "propositions_count": props_count,
            })
        return result

    def get_graph(self, key: str) -> Dict[str, Any]:
        """指定体系の現在のシナリオにおけるDAGグラフ構造と評価結果を返す"""
        if key not in self.system_scenarios:
            raise ValueError(f"System not found: {key}")

        sc = self.system_scenarios[key]
        state, kb, sc_info = self._evaluate_scenario(key, sc["active_premises"], sc["injected_critiques"])
        return self._convert_to_graph_data(key, state, kb, sc_info)

    def toggle_premise(self, key: str, prop_id: str, active: Optional[bool] = None) -> Dict[str, Any]:
        """
        基礎前提（公理または定義）の採用／不採用を切り替え、独立シナリオとして再計算する。
        「前提の不採用」と「否定支持の追加」を混同せず、不採用は正支持の停止（UNKNOWN化）として扱う。
        """
        if key not in self.system_scenarios:
            raise ValueError(f"System not found: {key}")

        all_premises = self._get_all_premises(key)
        if prop_id not in all_premises:
            raise ValueError(f"命題 '{prop_id}' は体系 '{key}' の基礎前提（公理・定義）ではないため直接トグルできません。")

        active_premises = self.system_scenarios[key]["active_premises"]
        if active is None:
            # トグル反転
            if prop_id in active_premises:
                active_premises.remove(prop_id)
            else:
                active_premises.add(prop_id)
        else:
            if active:
                active_premises.add(prop_id)
            else:
                active_premises.discard(prop_id)

        return self.get_graph(key)

    def toggle_node(self, key: str, node_id: str, new_value: str) -> Dict[str, Any]:
        """後方互換用: UIまたはAPIからのノード操作を新前提トグルへマッピング"""
        if key not in self.system_scenarios:
            raise ValueError(f"System not found: {key}")

        all_premises = self._get_all_premises(key)
        if node_id in all_premises:
            # 前提の採用 (TRUE) または不採用 (FALSE / UNKNOWN)
            is_active = (new_value == "TRUE")
            return self.toggle_premise(key, node_id, is_active)
        else:
            # 定理（proposition）は前提ではないため直接トグル不可
            # 現在のグラフを返却
            return self.get_graph(key)

    def reset_system(self, key: Optional[str] = None):
        """指定体系（または全体系）をベースライン（全前提採用・批判なし）へリセット"""
        targets = [key] if key and key in self.system_files else list(self.system_files.keys())
        for k in targets:
            all_premises = self._get_all_premises(k)
            self.system_scenarios[k] = {
                "active_premises": set(all_premises),
                "injected_critiques": set(),
                "is_kant_injected": False,
            }

    def approve_all_definitions(self, key: str) -> Dict[str, Any]:
        """指定体系のすべての定義（definition）を採用前提に追加して再演繹"""
        if key not in self.system_scenarios:
            raise ValueError(f"System not found: {key}")

        raw = self.raw_data.get(key, {})
        for node in raw.get("nodes", []):
            if node.get("type") == "definition":
                self.system_scenarios[key]["active_premises"].add(node["id"])

        return self.get_graph(key)

    def inject_kant(self, key: str) -> Dict[str, Any]:
        """
        カント批判公理群を体系に注入し、批判耐性崩壊シミュレーションを実行。
        （全前提を採用とした上で批判公理を注入）
        """
        if key not in self.system_scenarios:
            raise ValueError(f"System not found: {key}")
        if key == "Kant":
            return self.get_graph(key)

        # 全前提を採用
        all_premises = self._get_all_premises(key)
        self.system_scenarios[key]["active_premises"] = set(all_premises)

        # カント批判公理の注入
        kant_critique_ids = {"KANT_AX_1", "KANT_AX_2", "KANT_AX_3"}
        self.system_scenarios[key]["injected_critiques"] = set(kant_critique_ids)
        self.system_scenarios[key]["is_kant_injected"] = True

        return self.get_graph(key)

    def what_if(self, key: str, node_id: str, assume_value: str) -> Dict[str, Any]:
        """
        反実仮想シミュレーション（What-If）。
        現在のシナリオを汚染せず、独立した仮想シナリオとして Evaluator で評価する。
        - assume_value == 'FALSE': node_id を不採用にし、否定支持 (Literal(node_id, False)) を注入
        """
        if key not in self.system_scenarios:
            raise ValueError(f"System not found: {key}")

        current_sc = self.system_scenarios[key]
        base_state, base_kb, _ = self._evaluate_scenario(
            key,
            current_sc["active_premises"],
            current_sc["injected_critiques"]
        )

        # 仮想シナリオの前提と批判
        sim_premises = set(current_sc["active_premises"])
        sim_premises.discard(node_id)
        sim_critiques = set(current_sc["injected_critiques"])

        # 否定支持の注入
        file_path = self.system_files[key]["file"]
        raw_kb = load_system_as_kb(file_path)

        # node_id を assumption 化
        controlled_props = []
        for p in raw_kb.propositions.values():
            if p.id == node_id and p.prop_type == "axiom":
                controlled_props.append(
                    Proposition(
                        id=p.id,
                        title=p.title,
                        text_ja=p.text_ja,
                        prop_type="assumption",
                        logical_form=p.logical_form,
                        source_system=p.source_system,
                    )
                )
            else:
                controlled_props.append(p)

        sim_kb = KnowledgeBase(
            name=raw_kb.name,
            propositions=controlled_props,
            rules=raw_kb.rules,
            conflicts=raw_kb.conflicts,
            undercuts=raw_kb.undercuts,
        )

        # 定義の採用リテラル
        def_assumptions = [
            Literal(p.id, True) for p in sim_kb.propositions.values()
            if p.prop_type == "definition" and p.id in sim_premises
        ]

        # 否定の注入
        if assume_value == "FALSE":
            neg_lit = Literal(node_id, False)
            injected = [neg_lit] + [Literal(c, True) for c in sim_critiques]
        else:
            injected = [Literal(c, True) for c in sim_critiques]

        evaluator = Evaluator(sim_kb)
        opts = ScenarioOptions(mode=SemanticsMode.DIAGNOSTIC_MONOTONE)
        sim_state = evaluator.evaluate(assumptions=def_assumptions, injected_critiques=injected, options=opts)

        # 影響を受けた定理の集計
        raw = self.raw_data.get(key, {})
        theorems = [n for n in raw.get("nodes", []) if n.get("type") == "proposition"]
        total_theorems = len(theorems)

        affected = []
        survived = 0
        for t in theorems:
            tid = t["id"]
            old_st = base_state.get_status(tid)
            new_st = sim_state.get_status(tid)

            if new_st == TruthStatus.TRUE:
                survived += 1

            if old_st != new_st:
                affected.append({
                    "id": tid,
                    "title": t["title"],
                    "previous_status": old_st.name,
                    "new_status": new_st.name,
                })

        impact_percentage = round(len(affected) / total_theorems * 100, 1) if total_theorems > 0 else 0.0

        return {
            "target_node": node_id,
            "assumed_value": assume_value,
            "total_theorems": total_theorems,
            "survived_theorems": survived,
            "total_affected": len(affected),
            "impact_percentage": impact_percentage,
            "affected_theorems": affected,
            "model_version": "v0.1",
            "semantics_mode": "diagnostic_monotone",
        }

    def find_frontier(self, key: str, target_id: str) -> List[Dict[str, Any]]:
        """未解決命題の最小成立要件を逆算 (新意味論: MinimalAssumptionSearch)"""
        if key not in self.system_files:
            raise ValueError(f"System not found: {key}")

        kb = load_system_as_kb(self.system_files[key]["file"])
        searcher = MinimalAssumptionSearch(kb)
        res = searcher.find_assumptions_for_target(target_id, target_sign=True)

        output = []
        for sol in res.subset_minimal_solutions:
            output.append({
                "required_assumptions": [
                    {"id": lit.prop_id, "title": kb.propositions[lit.prop_id].title}
                    for lit in sol.assumptions
                ],
                "total_assumptions_needed": len(sol.assumptions),
                "is_cardinality_minimal": sol.is_cardinality_minimal,
                "is_subset_minimal": sol.is_subset_minimal,
            })
        return output

    def get_benchmark(self) -> Dict[str, Any]:
        """耐震性ベンチマークデータを取得 (新意味論: v0.1 diagnostic_monotone)"""
        from engine.benchmark_core import PhilosophicalBenchmark
        bench = PhilosophicalBenchmark(self.base_dir)
        return bench.run_all_benchmarks()

    def get_insights(self, key: str, scenario: Optional[str] = None) -> Dict[str, Any]:
        """初心者向け「今回わかったこと」データを取得 (新意味論: v0.1 diagnostic_monotone)"""
        from engine.insights_generator import InsightsGenerator
        generator = InsightsGenerator(self.base_dir)
        return generator.generate_system_insights(key, scenario)

    def get_research_spinoza(self) -> Dict[str, Any]:
        """
        スピノザ命題11別証明比較実験の保存済み構造化結果を読み込む。
        （固定パス: docs/spinoza_alternative_proofs_results.json）
        """
        file_path = os.path.join(self.base_dir, "docs", "spinoza_alternative_proofs_results.json")
        if not os.path.exists(file_path):
            return {
                "status": "missing_data",
                "message": "保存済み実験結果ファイル (docs/spinoza_alternative_proofs_results.json) が見つかりません。",
                "data": None,
            }
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "status": "success",
                "message": "保存済み実験結果の読み込みに成功しました。",
                "data": data,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"実験結果データの読み込み中にエラーが発生しました: {str(e)}",
                "data": None,
            }

    def get_research_geometry(self) -> Dict[str, Any]:
        """
        ポアンカレ円板モデル固定三角形反例の保存済み幾何学再現実験結果を読み込む。
        （固定パス: docs/geometry_reproduction_results.json）
        """
        file_path = os.path.join(self.base_dir, "docs", "geometry_reproduction_results.json")
        if not os.path.exists(file_path):
            return {
                "status": "missing_data",
                "message": "保存済み幾何学実験結果ファイル (docs/geometry_reproduction_results.json) が見つかりません。",
                "data": None,
            }
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "status": "success",
                "message": "保存済み幾何学実験結果の読み込みに成功しました。",
                "data": data,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"幾何学実験結果データの読み込み中にエラーが発生しました: {str(e)}",
                "data": None,
            }
