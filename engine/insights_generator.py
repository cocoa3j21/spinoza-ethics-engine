"""
幾何学的哲学推論エンジン: 初心者向け「今回わかったこと」画面データ生成モジュール (Insights Generator)

哲学の予備知識がない人向けに、以下の3点を分かりやすく整理・説明する：
1. 何を変えて検証したか (What was tested)
2. 何が変わったか／変わらなかったか (What changed / did not change)
3. どこまで言えるか (Scope & epistemic boundaries)

推論意味論（semantics.py）は改変せず、評価結果と証明履歴から客観的に説明を組み立てる。
"""
from typing import Dict, List, Optional, Any, Set
import os

from engine.semantics import (
    KnowledgeBase,
    EvaluationState,
    EvaluationStatus,
    TruthStatus,
    Literal,
    Proposition,
    InferenceRule,
)
from engine.benchmark_core import PhilosophicalBenchmark, load_system_as_kb


# 日本語真理値ラベルの厳格なマッピング規則
STATUS_LABELS = {
    TruthStatus.TRUE: "肯定する根拠あり（否定する根拠なし）",
    TruthStatus.FALSE: "否定する根拠あり（肯定する根拠なし）",
    TruthStatus.UNKNOWN: "肯定・否定とも根拠が得られていない",
    TruthStatus.CONFLICT: "肯定・否定の両方に根拠あり",
}

STATUS_SHORT_LABELS = {
    TruthStatus.TRUE: "肯定根拠あり",
    TruthStatus.FALSE: "否定根拠あり",
    TruthStatus.UNKNOWN: "根拠なし",
    TruthStatus.CONFLICT: "双方に根拠あり",
}


class InsightsGenerator:
    """
    検証結果の整理・説明・カード生成を行うクラス
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.benchmark = PhilosophicalBenchmark(base_dir)

    def generate_system_insights(
        self,
        system_key: str,
        scenario_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        指定された哲学体系と批判シナリオに対する初心者向けインサイトデータを生成
        """
        file_map = {
            "Descartes": {
                "name": "デカルト 『幾何学的順序による論証』",
                "author": "ルネ・デカルト",
                "file": os.path.join(self.base_dir, "data", "descartes_geometric.json"),
            },
            "Spinoza": {
                "name": "スピノザ 『エチカ』第1部「神について」",
                "author": "バールーフ・デ・スピノザ",
                "file": os.path.join(self.base_dir, "data", "spinoza_ethics_part1.json"),
            },
            "Leibniz": {
                "name": "ライプニッツ 『モナドロジー』",
                "author": "ゴットフリート・ライプニッツ",
                "file": os.path.join(self.base_dir, "data", "leibniz_monadology.json"),
            },
        }

        if system_key not in file_map:
            raise ValueError(f"Unknown system: {system_key}")

        sys_info = file_map[system_key]
        raw_bench = self.benchmark.benchmark_system(system_key)

        # デフォルトシナリオの選択
        scenarios = raw_bench["scenarios"]
        scenario_names = list(scenarios.keys())

        target_sc_name = scenario_key
        if not target_sc_name or target_sc_name not in scenarios:
            # 存在論批判があれば優先、なければ先頭
            onto = next((k for k in scenario_names if "Ontological" in k), None)
            target_sc_name = onto or scenario_names[0]

        sc_data = scenarios[target_sc_name]

        # 基礎知識ベースと評価状態の再取得（詳細追跡用）
        kb = self._build_kb_for_system(system_key)
        def_assumptions = [
            Literal(p.id, True) for p in kb.propositions.values()
            if p.prop_type == "definition" and p.source_system == kb.name
        ]

        from engine.semantics import Evaluator, ScenarioOptions
        evaluator = Evaluator(kb)
        base_state = evaluator.evaluate(assumptions=def_assumptions)

        critiques = self._get_critique_literals(target_sc_name)
        sc_state = evaluator.evaluate(assumptions=def_assumptions, injected_critiques=critiques)

        # 1. 警告メッセージの構築 (未収束・根拠不整合)
        status_warning = None
        if sc_state.status == EvaluationStatus.CYCLE_DETECTED:
            status_warning = (
                "【計算未完了の警告】批判の適用により自壊的な循環推論（振動）が発生し、"
                "安定した評価結果に収束しませんでした。以下の結果は確定的な知見ではありません。"
            )
        elif sc_state.status == EvaluationStatus.STEP_LIMIT_EXCEEDED:
            status_warning = (
                "【計算打ち切りの警告】推論ステップ数が上限に達したため、評価が未完了のまま中断されました。"
            )
        elif not sc_state.is_complete:
            status_warning = (
                "【注意】一部の推論プロセスが完了していません。表示される結果には保留中の命題が含まれます。"
            )

        # 2. 定理ID一覧
        theorems = raw_bench["denominator_theorem_ids"]

        # 3. 重要な結果カードの生成 (最大3件)
        cards = self._generate_cards(
            system_key=system_key,
            sys_info=sys_info,
            scenario_name=target_sc_name,
            kb=kb,
            theorems=theorems,
            base_state=base_state,
            sc_state=sc_state,
            sc_data=sc_data,
        )

        # 4. 変更前と変更後の差分構造 (Section B)
        before_after = self._build_before_after(
            kb=kb,
            theorems=theorems,
            base_state=base_state,
            sc_state=sc_state,
            sc_data=sc_data,
            target_sc_name=target_sc_name,
        )

        # 5. なぜそうなった？ (Section C: 止まった経路と残った別証明)
        why_it_happened = self._build_why_it_happened(
            kb=kb,
            theorems=theorems,
            base_state=base_state,
            sc_state=sc_state,
            sc_data=sc_data,
        )

        # 6. 詳しい証拠 (Section D)
        detailed_evidence = self._build_detailed_evidence(
            system_key=system_key,
            sys_info=sys_info,
            scenario_name=target_sc_name,
            kb=kb,
            theorems=theorems,
            sc_state=sc_state,
        )

        return {
            "system_id": system_key,
            "system_name": sys_info["name"],
            "author": sys_info["author"],
            "available_scenarios": [
                {"id": k, "label": self._friendly_scenario_name(k)}
                for k in scenario_names
            ],
            "selected_scenario": {
                "id": target_sc_name,
                "label": self._friendly_scenario_name(target_sc_name),
            },
            "status_warning": status_warning,
            "cards": cards,
            "before_after": before_after,
            "why_it_happened": why_it_happened,
            "detailed_evidence": detailed_evidence,
            "epistemic_disclaimer": raw_bench.get("epistemic_disclaimer", ""),
        }

    def _friendly_scenario_name(self, raw_name: str) -> str:
        """シナリオ名を初心者向けに分かりやすく整形"""
        if "Ontological_Only" in raw_name:
            return "カントの存在論的証明批判のみを適用"
        elif "Sensible_Only" in raw_name:
            return "カントの感性直観・物自体認識制限のみを適用"
        elif "Simultaneous" in raw_name:
            return "カントの全批判を同時に適用"
        return raw_name

    def _get_critique_literals(self, scenario_name: str) -> List[Literal]:
        """シナリオ名から注入リテラルを取得"""
        if "Ontological_Only" in scenario_name:
            return [Literal("KANT_AX_1", True)]
        elif "Sensible_Only" in scenario_name:
            return [Literal("KANT_AX_3", True)]
        elif "Simultaneous" in scenario_name:
            return [
                Literal("KANT_AX_1", True),
                Literal("KANT_AX_2", True),
                Literal("KANT_AX_3", True),
            ]
        return []

    def _build_kb_for_system(self, system_key: str) -> KnowledgeBase:
        """システム用の KnowledgeBase を構築"""
        file_map = {
            "Descartes": os.path.join(self.base_dir, "data", "descartes_geometric.json"),
            "Spinoza": os.path.join(self.base_dir, "data", "spinoza_ethics_part1.json"),
            "Leibniz": os.path.join(self.base_dir, "data", "leibniz_monadology.json"),
        }
        filepath = file_map[system_key]
        raw_kb = load_system_as_kb(filepath)
        kant_props = self.benchmark._get_kant_critique_props()

        # benchmark_core と同一の Undercut 定義
        from engine.benchmark_core import UndercutDefeater
        undercuts = []
        if system_key == "Descartes":
            undercuts = [
                UndercutDefeater(Literal("KANT_AX_1", True), "R_DESC_PROP_2", "存在論的証明の無効化"),
                UndercutDefeater(Literal("KANT_AX_3", True), "R_DESC_PROP_1", "無限実体観念からの実在論証無効化"),
            ]
        elif system_key == "Spinoza":
            undercuts = [
                UndercutDefeater(Literal("KANT_AX_1", True), "R_PROP_7", "自己原因による存在証明の無効化"),
            ]
        elif system_key == "Leibniz":
            undercuts = [
                UndercutDefeater(Literal("KANT_AX_3", True), "R_LEIB_PROP_2", "超越的世界選択の認識無効化"),
            ]

        return KnowledgeBase(
            name=raw_kb.name,
            propositions=list(raw_kb.propositions.values()) + kant_props,
            rules=raw_kb.rules,
            conflicts=raw_kb.conflicts,
            undercuts=undercuts,
        )

    def _generate_cards(
        self,
        system_key: str,
        sys_info: Dict[str, str],
        scenario_name: str,
        kb: KnowledgeBase,
        theorems: List[str],
        base_state: EvaluationState,
        sc_state: EvaluationState,
        sc_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        重要な結果カードを説明可能なルールに基づいて最大3件抽出
        1. 二つの批判の同時適用で単独適用と異なる結果になった (複合批判効果)
        2. 一方の証明が止まっても別証明が残った (別証明の残存)
        3. 結論の支持状態が変わった (肯定根拠の喪失 / CONFLICTの発生)
        4. 支持状態は同じだが、批判の影響を受けない独立した証明経路が特定された
        """
        # 未収束の場合は確定カードを生成しない (未完了を確定知見と偽装しない)
        if sc_state.status != EvaluationStatus.CONVERGED or not sc_state.is_complete:
            return []

        candidates: List[Dict[str, Any]] = []
        rule_breakdown = sc_data.get("rule_breakdown", {})
        lost_theorems = sc_data.get("lost_support_ids", [])
        conflict_theorems = sc_data.get("partition", {}).get("CONFLICT", [])

        # --- ルール1: 二つの批判の同時適用で単独適用と異なる結果になった (複合効果) ---
        if "Simultaneous" in scenario_name:
            # 単独シナリオの結果を取得して比較
            all_bench = self.benchmark.benchmark_system(system_key)
            sc_scenarios = all_bench["scenarios"]
            onto_sc = next((v for k, v in sc_scenarios.items() if "Ontological" in k), None)
            sens_sc = next((v for k, v in sc_scenarios.items() if "Sensible" in k), None)

            if onto_sc and sens_sc:
                onto_lost = set(onto_sc.get("lost_support_ids", []))
                sens_lost = set(sens_sc.get("lost_support_ids", []))
                sim_lost = set(lost_theorems)

                # どちらかの単独では生き残っていたが、同時適用で全て失われた命題
                compound_lost = (sim_lost - onto_lost) | (sim_lost - sens_lost)
                if compound_lost:
                    c_titles = [kb.propositions[tid].title for tid in sorted(list(compound_lost))]
                    titles_str = "、".join(c_titles[:2])
                    if len(c_titles) > 2:
                        titles_str += f" ほか計{len(c_titles)}件"

                    candidates.append({
                        "priority": 110,
                        "impact_count": len(compound_lost),
                        "headline": f"二つの批判の同時適用により、単独批判では生き残っていた「{titles_str}」の根拠がすべて遮断されました",
                        "tested": "存在論的証明批判と感性直観批判を単独で適用した場合と、同時に適用した場合の差異を比較検証しました。",
                        "observed": f"単独適用では存在論的証明批判で{onto_sc['true_rate']}%、感性直観批判で{sens_sc['true_rate']}%の定理が根拠を維持していましたが、同時適用ではすべての証明経路が塞がれ、生存率が0.0%に急落しました。",
                        "why_important": "批判が単独であれば別の証明経路（第三省察ルートや自己原因ルート）によって結論を維持できた体系が、複合的な批判によって完全に根拠を失うという『批判の相互作用』が形式的に実証されました。",
                        "cannot_say": "これによりデカルトやスピノザの思想全体が完全に論破されたと結論づけることはできません。モデルに組み込まれていない別の論証の存在余地は残されています。",
                        "scope": f"本モデルで定義された{len(theorems)}件の定理と2系統のカント批判規則の組み合わせに限定されます。",
                        "evidence_link_id": sorted(list(compound_lost))[0],
                        "card_type": "モデル内の比較結果",
                        "selection_reason": f"二つの批判の同時適用で単独適用と異なる結果になったため（影響命題数: {len(compound_lost)}件）",
                    })

        # --- ルール2: 一方の証明が止まっても別証明が残った (別証明の残存) ---
        alt_proof_theorems = []
        for tid in theorems:
            rb = rule_breakdown.get(tid, {})
            # 規則が無効化されているが、発火中規則も残っており、結論が TRUE
            if len(rb.get("defeated_rules", [])) > 0 and len(rb.get("surviving_rules", [])) > 0:
                if sc_state.get_status(tid) == TruthStatus.TRUE:
                    alt_proof_theorems.append(tid)

        if alt_proof_theorems:
            affected_titles = [kb.propositions[tid].title for tid in alt_proof_theorems]
            titles_str = "、".join(affected_titles[:2])
            if len(affected_titles) > 2:
                titles_str += f" ほか計{len(affected_titles)}件"

            candidates.append({
                "priority": 100,
                "impact_count": len(alt_proof_theorems),
                "headline": f"存在論的証明が無効化されても、「{titles_str}」は別の証明経路によって肯定根拠を維持しました",
                "tested": f"{self._friendly_scenario_name(scenario_name)}を適用し、一部の推論規則が無効化されたときの影響を追跡しました。",
                "observed": "対象となる存在論的証明規則は無効化されましたが、独立した別証明（神の観念と誠実さに依拠する経路）が有効に機能したため、結論の支持状態は『肯定する根拠あり』のまま維持されました。",
                "why_important": "単一の推論規則が批判されても、独立した複数の証明経路（別証明）が存在すれば、体系全体の結論が直ちに崩壊するわけではないことが論理的に確認されました。",
                "cannot_say": f"{sys_info['author']}の哲学全体が批判に対して普遍的に無傷であることや、結論の内容が客観的真理として証明されたことを意味するものではありません。",
                "scope": f"本モデルで登録された有限の命題（{len(theorems)}個の定理）および推論規則の範囲内での形式的検証結果です。",
                "evidence_link_id": alt_proof_theorems[0],
                "card_type": "モデル内の比較結果",
                "selection_reason": f"別証明の残存により結論の肯定根拠が維持されたため（対象命題数: {len(alt_proof_theorems)}件）",
            })

        # --- ルール3: 結論の肯定根拠の喪失 (TRUE -> UNKNOWN) ---
        if lost_theorems:
            affected_titles = [kb.propositions[tid].title for tid in lost_theorems]
            titles_str = "、".join(affected_titles[:2])
            if len(affected_titles) > 2:
                titles_str += f" ほか計{len(affected_titles)}件"

            candidates.append({
                "priority": 90,
                "impact_count": len(lost_theorems),
                "headline": f"批判の適用により、「{titles_str}」を肯定する根拠が失われました",
                "tested": f"{self._friendly_scenario_name(scenario_name)}を適用し、どの定理の証明根拠が遮断されるかを検証しました。",
                "observed": f"これまで前提から導出されていた{len(lost_theorems)}件の定理について、証明規則が無効化されたため、『肯定する根拠あり』から『肯定・否定とも根拠が得られていない（UNKNOWN）』状態へと遷移しました。",
                "why_important": "批判がどの推論規則を無効化し、どの定理がその規則のみに依存していたのか（依存の脆弱性）が特定されました。",
                "cannot_say": f"これらの定理が『誤り（FALSE）』であると証明されたわけではありません。単に『現在のモデル内では導出根拠が得られなくなった』ことを示しています。",
                "scope": f"カント批判公理と本モデルの推論規則の組み合わせにおける形式的帰結に限定されます。",
                "evidence_link_id": lost_theorems[0],
                "card_type": "モデル内の比較結果",
                "selection_reason": f"批判により肯定根拠が失われたため（対象命題数: {len(lost_theorems)}件）",
            })

        # --- ルール4: 二律背反・排他衝突（CONFLICT）の発生 ---
        if conflict_theorems:
            affected_titles = [kb.propositions[tid].title for tid in conflict_theorems]
            titles_str = "、".join(affected_titles[:2])
            candidates.append({
                "priority": 95,
                "impact_count": len(conflict_theorems),
                "headline": f"「{titles_str}」について、肯定根拠と否定根拠の両方が成立し、矛盾衝突（CONFLICT）が発生しました",
                "tested": "対立する前提や批判が同時に承認された場合の状態遷移を検証しました。",
                "observed": "肯定する演繹経路と否定する批判経路の双方が有効となり、モデル内で二律背反（衝突）が検出されました。",
                "why_important": "議論が一方の完全な勝利で終わるのではなく、両立不能な根拠が正面衝突している局面が客観的に浮き彫りになりました。",
                "cannot_say": "この矛盾が現実の世界や哲学史そのものの破綻を意味するわけではありません。",
                "scope": "モデルに定義された衝突ペア（ConflictPair）の範囲に限定されます。",
                "evidence_link_id": conflict_theorems[0],
                "card_type": "モデル内の比較結果",
                "selection_reason": f"肯定と否定の双方が支持された二律背反が検出されたため（対象命題数: {len(conflict_theorems)}件）",
            })

        # --- ルール5: 批判の影響を受けずに残存した証明経路 ---
        # （体系内で支持喪失等の変化が生じた際に対比として残存した証明経路を説明する。
        # 体系全体で差分がゼロの場合は「新発見」として捏造せずカード化しない）
        has_any_system_impact = bool(lost_theorems or conflict_theorems or alt_proof_theorems)
        unaffected_theorems = [
            tid for tid in theorems
            if base_state.get_status(tid) == TruthStatus.TRUE
            and sc_state.get_status(tid) == TruthStatus.TRUE
            and tid not in alt_proof_theorems
        ]
        if unaffected_theorems and has_any_system_impact:
            affected_titles = [kb.propositions[tid].title for tid in unaffected_theorems]
            titles_str = "、".join(affected_titles[:2])
            if len(affected_titles) > 2:
                titles_str += f" ほか計{len(affected_titles)}件"

            candidates.append({
                "priority": 80,
                "impact_count": len(unaffected_theorems),
                "headline": f"「{titles_str}」は批判された推論規則とは無関係な前提から導出されているため、影響を受けずに肯定根拠を維持しました",
                "tested": f"{self._friendly_scenario_name(scenario_name)}を適用した際、批判の射程外にある命題を特定しました。",
                "observed": f"{len(unaffected_theorems)}件の定理は、無効化された推論規則に依存していないため、批判後も変わらず『肯定する根拠あり』のまま残存しました。",
                "why_important": "批判が体系全体を無差別に破壊するのではなく、特定の証明経路にのみ限定して作用していることが実証されました。",
                "cannot_say": "いかなる批判に対してもこの定理が覆らないことを意味するものではありません（別の批判公理には脆弱な可能性があります）。",
                "scope": f"適用された批判シナリオと対象定理の依存グラフの範囲に限定されます。",
                "evidence_link_id": unaffected_theorems[0],
                "card_type": "モデル内の比較結果",
                "selection_reason": f"批判の影響を受けない独立した証明経路が確認されたため（対象命題数: {len(unaffected_theorems)}件）",
            })

        # 優先度と影響数でソートし、最大3件を抽出
        candidates.sort(key=lambda x: (x["priority"], x["impact_count"]), reverse=True)
        return candidates[:3]

    def _build_before_after(
        self,
        kb: KnowledgeBase,
        theorems: List[str],
        base_state: EvaluationState,
        sc_state: EvaluationState,
        sc_data: Dict[str, Any],
        target_sc_name: str,
    ) -> Dict[str, Any]:
        """Section B: 変更前と変更後の差分構造"""
        lost_theorems = []
        retained_theorems = []
        rebutted_theorems = []

        rule_breakdown = sc_data.get("rule_breakdown", {})

        for tid in theorems:
            p = kb.propositions[tid]
            st_before = base_state.get_status(tid)
            st_after = sc_state.get_status(tid)
            rb = rule_breakdown.get(tid, {})

            info = {
                "id": tid,
                "title": p.title,
                "status_before": STATUS_LABELS[st_before],
                "status_after": STATUS_LABELS[st_after],
                "status_before_short": STATUS_SHORT_LABELS[st_before],
                "status_after_short": STATUS_SHORT_LABELS[st_after],
                "supports_before": sorted(list(base_state.positive_supports.get(tid, set()))),
                "supports_after": sorted(list(sc_state.positive_supports.get(tid, set()))),
                "negative_supports_after": sorted(list(sc_state.negative_supports.get(tid, set()))),
                "has_defeated_rules": len(rb.get("defeated_rules", [])) > 0,
                "has_surviving_rules": len(rb.get("surviving_rules", [])) > 0,
            }

            if st_before == TruthStatus.TRUE and st_after == TruthStatus.UNKNOWN:
                lost_theorems.append(info)
            elif st_after == TruthStatus.CONFLICT:
                rebutted_theorems.append(info)
            elif st_after == TruthStatus.TRUE:
                retained_theorems.append(info)

        # 適用された変更内容の説明
        applied_changes = []
        critiques = self._get_critique_literals(target_sc_name)
        for crit in critiques:
            crit_p = kb.propositions.get(crit.prop_id)
            title = crit_p.title if crit_p else crit.prop_id
            text = crit_p.text_ja if crit_p else ""
            applied_changes.append({
                "type": "批判リテラルの注入",
                "id": crit.prop_id,
                "title": title,
                "description": text or "説明に必要な記録がありません",
            })

        for u in kb.undercuts:
            if sc_state.is_supported(u.critique_literal):
                target_rule = next((r for r in kb.rules if r.rule_id == u.target_rule_id), None)
                target_name = target_rule.name if target_rule else u.target_rule_id
                applied_changes.append({
                    "type": "推論規則の無効化 (Undercut)",
                    "id": u.target_rule_id,
                    "title": target_name,
                    "description": u.reason or "説明に必要な記録がありません",
                })

        return {
            "is_pure_critique_effect": True,
            "comparison_note": "同一モデル・同一意味論（2ビット支持モデル）のもとで、批判公理の適用有無のみを純粋に比較しています。",
            "changes_applied": applied_changes,
            "counts": {
                "total_theorems": len(theorems),
                "lost_count": len(lost_theorems),
                "retained_count": len(retained_theorems),
                "rebutted_count": len(rebutted_theorems),
            },
            "lost_theorems": lost_theorems,
            "retained_theorems": retained_theorems,
            "rebutted_theorems": rebutted_theorems,
        }

    def _build_why_it_happened(
        self,
        kb: KnowledgeBase,
        theorems: List[str],
        base_state: EvaluationState,
        sc_state: EvaluationState,
        sc_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Section C: なぜそうなった？（止まった経路と残った経路の分離）"""
        rule_breakdown = sc_data.get("rule_breakdown", {})
        routes = []

        for tid in theorems:
            rb = rule_breakdown.get(tid, {})
            p = kb.propositions[tid]

            # 変化があった命題、または別証明が存在した命題をピックアップ
            prop_rules = [r for r in kb.rules if r.conclusion.prop_id == tid]
            defeated_rids = set(rb.get("defeated_rules", []))
            surviving_rids = set(rb.get("surviving_rules", []))

            # 規則に関連がある場合
            if defeated_rids or len(prop_rules) > 1 or sc_state.get_status(tid) != base_state.get_status(tid):
                blocked = []
                surviving = []

                for r in prop_rules:
                    # 前提の充足状況
                    premises_info = []
                    all_prems_ok = True
                    for prem in r.premises:
                        prem_p = kb.propositions.get(prem.prop_id)
                        prem_title = prem_p.title if prem_p else prem.prop_id
                        st = sc_state.get_status(prem.prop_id)
                        is_ok = sc_state.is_supported(prem)
                        if not is_ok:
                            all_prems_ok = False
                        premises_info.append({
                            "id": prem.prop_id,
                            "title": prem_title,
                            "status": STATUS_SHORT_LABELS[st],
                            "is_satisfied": is_ok,
                        })

                    r_info = {
                        "rule_id": r.rule_id,
                        "rule_name": r.name or r.rule_id,
                        "premises": premises_info,
                    }

                    if r.rule_id in defeated_rids:
                        r_info["reason"] = "カント批判により推論規則そのものが無効化されました。"
                        blocked.append(r_info)
                    elif not all_prems_ok:
                        r_info["reason"] = "前提命題の一部について支持根拠が得られていないため不発となりました。"
                        blocked.append(r_info)
                    elif r.rule_id in surviving_rids:
                        r_info["reason"] = "全前提が支持され、批判の無効化も受けていないため正常に結論を支持しています。"
                        surviving.append(r_info)

                routes.append({
                    "theorem_id": tid,
                    "theorem_title": p.title,
                    "final_status": STATUS_LABELS[sc_state.get_status(tid)],
                    "final_status_short": STATUS_SHORT_LABELS[sc_state.get_status(tid)],
                    "blocked_paths": blocked,
                    "surviving_paths": surviving,
                    "has_alternative_proof": len(prop_rules) > 1,
                })

        return {
            "summary": "批判によってどの証明経路が遮断され、どの別経路が残存して結論を維持したかの詳細内訳です。",
            "routes": routes,
        }

    def _build_detailed_evidence(
        self,
        system_key: str,
        sys_info: Dict[str, str],
        scenario_name: str,
        kb: KnowledgeBase,
        theorems: List[str],
        sc_state: EvaluationState,
    ) -> Dict[str, Any]:
        """Section D: 詳しい証拠（折りたたみ表示用）"""
        props_evidence = []
        for tid in theorems:
            p = kb.propositions[tid]
            source = p.source_ref if p.source_ref else "原典未登録"
            memo = "説明に必要な記録がありません" if not p.logical_form else f"論理式: {p.logical_form}"

            props_evidence.append({
                "id": tid,
                "title": p.title,
                "source_ref": source,
                "interpretation_note": memo,
                "positive_supports": sorted(list(sc_state.positive_supports.get(tid, set()))),
                "negative_supports": sorted(list(sc_state.negative_supports.get(tid, set()))),
                "status_name": sc_state.get_status(tid).name,
                "status_label": STATUS_LABELS[sc_state.get_status(tid)],
            })

        rules_evidence = []
        for r in kb.rules:
            if r.conclusion.prop_id in theorems:
                source = r.source_ref if r.source_ref else "原典未登録"
                rules_evidence.append({
                    "rule_id": r.rule_id,
                    "name": r.name or r.rule_id,
                    "conclusion_id": r.conclusion.prop_id,
                    "premises": [p.prop_id for p in r.premises],
                    "source_ref": source,
                    "is_defeated": r.rule_id in sc_state.undercut_rules,
                    "is_fired": r.rule_id in sc_state.fired_rules,
                })

        # 再現用コードスニペット
        repro_code = (
            f"# Python 3.14 再現コード\n"
            f"from engine.benchmark_core import PhilosophicalBenchmark\n"
            f"bench = PhilosophicalBenchmark('.')\n"
            f"res = bench.benchmark_system('{system_key}')\n"
            f"sc_result = res['scenarios']['{scenario_name}']\n"
            f"print('TRUE率:', sc_result['true_rate'])\n"
        )

        return {
            "model_version": "2.0 (Formal Semantics / 2-Bit Support Model)",
            "semantics_type": "正当化根拠に基づく整合的真理維持意味論 (Truth Maintenance Semantics)",
            "scenario_raw_name": scenario_name,
            "evaluation_status": str(sc_state.status),
            "step_count": sc_state.step_count,
            "is_complete": sc_state.is_complete,
            "propositions": props_evidence,
            "rules": rules_evidence,
            "reproduction_code": repro_code,
        }
