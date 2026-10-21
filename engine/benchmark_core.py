"""
幾何学的哲学推論エンジン: ベンチマーク・コアモジュール (Benchmark Core)

- 排他的4分類 (TRUE, FALSE, UNKNOWN, CONFLICT) の厳密集計
- 分母命題ID一覧の出力
- TRUE率 と 支持あり率 (TRUE+CONFLICT) の区別
- 批判前未支持命題と、批判により支持が失われた命題の区別
- 批判の単独注入 vs 同時注入の比較
- 命題ごとの失われた推論規則と残存証明規則の明示
- 哲学者の優劣ではなく、形式的議論モデルの耐震性分析に限定した中立的記述
"""
import json
import os
from typing import Dict, List, Optional, Set, Tuple, Any

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


def load_system_as_kb(
    filepath: str,
    extra_rules: Optional[List[InferenceRule]] = None,
    extra_conflicts: Optional[List[ConflictPair]] = None,
    extra_undercuts: Optional[List[UndercutDefeater]] = None,
) -> KnowledgeBase:
    """既存JSONファイルを新意味論 KnowledgeBase に変換"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    sys_name = data.get("system", "UnknownSystem")
    propositions: List[Proposition] = []
    rules: List[InferenceRule] = list(extra_rules or [])

    for item in data.get("nodes", []):
        p = Proposition(
            id=item["id"],
            title=item["title"],
            text_ja=item.get("text_ja", ""),
            prop_type=item["type"],
            logical_form=item.get("logical_form", ""),
            source_system=sys_name,
            source_ref=item.get("source_ref", ""),
            is_provisional=item.get("is_provisional", False),
        )
        propositions.append(p)

        # dependencies から基本推論規則を生成
        deps = item.get("dependencies", [])
        if deps:
            rule_id = f"R_{item['id']}"
            premises = tuple(Literal(dep_id, True) for dep_id in deps)
            rule = InferenceRule(
                rule_id=rule_id,
                premises=premises,
                conclusion=Literal(item["id"], True),
                name=f"Derivation of {item['id']}",
                source_ref=item.get("source_ref", ""),
                is_provisional=item.get("is_provisional", False),
            )
            rules.append(rule)

    conflicts = list(extra_conflicts or [])
    undercuts = list(extra_undercuts or [])

    return KnowledgeBase(
        name=sys_name,
        propositions=propositions,
        rules=rules,
        conflicts=conflicts,
        undercuts=undercuts,
    )


class PhilosophicalBenchmark:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.data_dir = os.path.join(base_dir, "data")
        self.kant_file = os.path.join(self.data_dir, "kant_critique.json")

    def _get_kant_critique_props(self) -> List[Proposition]:
        """カントの批判公理命題を取得"""
        with open(self.kant_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        props = []
        for item in data.get("nodes", []):
            props.append(
                Proposition(
                    id=item["id"],
                    title=item["title"],
                    text_ja=item.get("text_ja", ""),
                    prop_type="critique",
                    logical_form=item.get("logical_form", ""),
                    source_system="Kant_Critique",
                    source_ref="Kritik der reinen Vernunft",
                )
            )
        return props

    def benchmark_system(self, system_key: str) -> Dict[str, Any]:
        """
        単一の哲学体系に対し、ベースラインと各種批判シナリオ（単独・同時）を評価
        """
        file_map = {
            "Descartes": os.path.join(self.data_dir, "descartes_geometric.json"),
            "Spinoza": os.path.join(self.data_dir, "spinoza_ethics_part1.json"),
            "Leibniz": os.path.join(self.data_dir, "leibniz_monadology.json"),
        }
        if system_key not in file_map:
            raise ValueError(f"Unknown system: {system_key}")

        filepath = file_map[system_key]
        kant_props = self._get_kant_critique_props()

        # 批判規則の定義 (Undercutting Defeaters: 推論規則の無効化)
        undercut_map: Dict[str, List[UndercutDefeater]] = {
            "Descartes": [
                # カントの存在論的証明批判 -> デカルトの神の本質からの存在証明規則 R_DESC_PROP_2 を無効化
                UndercutDefeater(
                    Literal("KANT_AX_1", True),
                    "R_DESC_PROP_2",
                    "カントは存在を述語とする概念分析的証明を無効化"
                ),
                # カントの物自体・認識限界批判 -> デカルトの無限実体観念からの実在論証 R_DESC_PROP_1 を無効化
                UndercutDefeater(
                    Literal("KANT_AX_3", True),
                    "R_DESC_PROP_1",
                    "カントは超越的実体の観念から客観的実在性を推論する規則を無効化"
                ),
            ],
            "Spinoza": [
                # カントの自己原因・存在述語批判 -> スピノザの実体存在証明規則 R_PROP_7 を無効化
                UndercutDefeater(
                    Literal("KANT_AX_1", True),
                    "R_PROP_7",
                    "カントは本質が存在を含むとする自己原因からの存在証明を無効化"
                ),
            ],
            "Leibniz": [
                # カントの超越的選択批判 -> 最善世界の客観的同調規則 R_LEIB_PROP_2 を無効化
                UndercutDefeater(
                    Literal("KANT_AX_3", True),
                    "R_LEIB_PROP_2",
                    "カントは超越的知性による可能世界選択の認識妥当性を無効化"
                ),
            ],
        }

        # KnowledgeBase の構築 (体系命題 + カント批判命題 + 批判無効化規則)
        raw_kb = load_system_as_kb(filepath)
        all_props = list(raw_kb.propositions.values()) + kant_props
        system_undercuts = undercut_map.get(system_key, [])

        kb = KnowledgeBase(
            name=system_key,
            propositions=all_props,
            rules=raw_kb.rules,
            conflicts=raw_kb.conflicts,
            undercuts=system_undercuts,
        )

        evaluator = Evaluator(kb)
        # v0.1 標準意味論 (diagnostic_monotone): legacy モードはベンチマークから完全除外
        opts = ScenarioOptions(mode=SemanticsMode.DIAGNOSTIC_MONOTONE)

        # 定理 (proposition) の分母ID一覧
        theorems = [
            p.id for p in kb.propositions.values()
            if p.prop_type == "proposition" and p.source_system == raw_kb.name
        ]
        theorems.sort()
        total_theorems = len(theorems)

        # ベースライン評価: 全ての定義 (definition) を承認
        def_assumptions = [
            Literal(p.id, True) for p in kb.propositions.values()
            if p.prop_type == "definition" and p.source_system == raw_kb.name
        ]
        base_state = evaluator.evaluate(assumptions=def_assumptions, options=opts)
        base_summary = {
            cat: [tid for tid in ids if tid in theorems]
            for cat, ids in base_state.summary().items()
        }

        # 各批判シナリオの定義
        scenarios = {
            "Kant_Ontological_Only (存在論的証明批判のみ)": [Literal("KANT_AX_1", True)],
            "Kant_Sensible_Only (感性直観・物自体認識制限のみ)": [Literal("KANT_AX_3", True)],
            "Kant_Simultaneous (カント批判全同時注入)": [
                Literal("KANT_AX_1", True),
                Literal("KANT_AX_2", True),
                Literal("KANT_AX_3", True),
            ],
        }

        scenario_results = {}
        for sc_name, critiques in scenarios.items():
            sc_state = evaluator.evaluate(assumptions=def_assumptions, injected_critiques=critiques, options=opts)
            sc_summary = {
                cat: [tid for tid in ids if tid in theorems]
                for cat, ids in sc_state.summary().items()
            }

            true_count = len(sc_summary["TRUE"])
            conflict_count = len(sc_summary["CONFLICT"])
            supported_count = true_count + conflict_count

            # 批判前から未支持だった定理 (ベースラインで UNKNOWN だったもの)
            pre_unsupported = [tid for tid in theorems if tid in base_summary["UNKNOWN"]]

            # 批判によって支持が失われた定理 (ベースライン TRUE -> 批判後 UNKNOWN)
            lost_support = [
                tid for tid in theorems
                if tid in base_summary["TRUE"] and tid in sc_summary["UNKNOWN"]
            ]

            # 命題ごとの規則詳細 (失われた証明、残存した証明)
            rule_breakdown = {}
            for tid in theorems:
                prop_rules = [r for r in kb.rules if r.conclusion.prop_id == tid]
                defeated_rules = [r.rule_id for r in prop_rules if r.rule_id in sc_state.undercut_rules]
                surviving_rules = [r.rule_id for r in prop_rules if r.rule_id in sc_state.fired_rules]
                rule_breakdown[tid] = {
                    "status": sc_state.get_status(tid).name,
                    "total_proof_rules": len(prop_rules),
                    "defeated_rules": defeated_rules,
                    "surviving_rules": surviving_rules,
                }

            scenario_results[sc_name] = {
                "evaluation_status": sc_state.status.value,
                "is_complete": sc_state.is_complete,
                "partition": sc_summary,
                "true_count": true_count,
                "true_rate": round(true_count / total_theorems * 100, 1) if total_theorems > 0 else 0.0,
                "supported_count": supported_count,
                "supported_rate": round(supported_count / total_theorems * 100, 1) if total_theorems > 0 else 0.0,
                "pre_unsupported_ids": pre_unsupported,
                "lost_support_ids": lost_support,
                "rule_breakdown": rule_breakdown,
                "diagnostic_conflicts_count": len(sc_state.diagnostic_conflicts),
            }

        return {
            "model_version": "v0.1",
            "semantics_mode": SemanticsMode.DIAGNOSTIC_MONOTONE.value,
            "system": system_key,
            "denominator_theorem_ids": theorems,
            "total_theorems": total_theorems,
            "baseline": {
                "evaluation_status": base_state.status.value,
                "is_complete": base_state.is_complete,
                "partition": base_summary,
                "diagnostic_conflicts_count": len(base_state.diagnostic_conflicts),
            },
            "scenarios": scenario_results,
            "epistemic_disclaimer": "本結果はモデル化された有限の推論規則と批判無効化規則の形式的帰結であり、哲学体系の優劣や真理性を決定するものではありません。",
        }

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """全体系のベンチマークを実行"""
        results = {}
        for key in ["Descartes", "Spinoza", "Leibniz"]:
            results[key] = self.benchmark_system(key)
        return results
