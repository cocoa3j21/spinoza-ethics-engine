"""
幾何学的哲学推論エンジン: 最小支持根拠・最小遮断集合 分析モジュール
(Minimal Support Grounds & Minimal Cut Sets Analyzer)

【設計思想】
推論意味論コア（v0.1 diagnostic_monotone）を一切改変せず、
既存の Evaluator を独立シナリオで繰り返し呼び出す外部分析器。
Python 3.14 標準ライブラリのみで動作。

【混同を排した厳密な3機能分離】
1. 未支持の目標へ仮定を追加する探索 (engine.search.MinimalAssumptionSearch)
2. 既存の前提から必要なものを選ぶ探索 (機能A: find_minimal_support_grounds)
3. 支持を失わせる前提・規則の無効化探索 (機能B: find_minimal_cut_sets)
"""
from dataclasses import dataclass, field
import itertools
import time
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from engine.semantics import (
    Evaluator,
    KnowledgeBase,
    Literal,
    Proposition,
    InferenceRule,
    TruthStatus,
    SemanticsMode,
    ScenarioOptions,
)


@dataclass(frozen=True)
class SupportGround:
    """
    目標リテラルを支持できる包含極小の基礎前提集合
    """
    premises: Tuple[Literal, ...]
    is_cardinality_minimal: bool = False
    is_subset_minimal: bool = True
    fired_rules: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def size(self) -> int:
        return len(self.premises)

    def to_prop_ids(self) -> Tuple[str, ...]:
        return tuple(p.prop_id for p in self.premises)


@dataclass
class SupportGroundsResult:
    """
    最小支持根拠の探索結果サマリー
    """
    target_literal: Literal
    candidate_premises: Tuple[Literal, ...]
    evaluated_count: int
    is_complete: bool
    time_limit_reached: bool = False
    eval_limit_reached: bool = False
    subset_minimal_grounds: List[SupportGround] = field(default_factory=list)
    cardinality_minimal_grounds: List[SupportGround] = field(default_factory=list)
    common_premises: Tuple[Literal, ...] = field(default_factory=tuple)
    model_version: str = "v0.1"
    semantics_mode: str = "diagnostic_monotone"

    def summary_ja(self) -> str:
        lines = [
            f"■ 調べた問い: 目標リテラル {self.target_literal} を成立させる最小支持根拠は何か？",
            f"  - 候補前提数: {len(self.candidate_premises)} 件",
            f"  - 評価回数: {self.evaluated_count} 回",
            f"  - 列挙完了状況: {'完全列挙完了' if self.is_complete else '探索未完了 (上限到達)'}",
        ]
        if self.eval_limit_reached:
            lines.append("    ※ 最大評価試行回数に達したため探索を打ち切りました。")
        if self.time_limit_reached:
            lines.append("    ※ タイムアウト時間の上限に達したため探索を打ち切りました。")

        lines.append(f"  - 発見された包含極小支持根拠: {len(self.subset_minimal_grounds)} 件")
        for idx, g in enumerate(self.subset_minimal_grounds, 1):
            prem_str = ", ".join(str(p) for p in g.premises) or "(前提なしで自明に成立)"
            card_mark = " ★要素数最小" if g.is_cardinality_minimal else ""
            lines.append(f"    [{idx}] {{{prem_str}}} (要素数: {g.size}){card_mark}")

        if self.is_complete:
            if self.common_premises:
                comm_str = ", ".join(str(p) for p in self.common_premises)
                lines.append(f"  - すべての最小支持根拠に共通する前提: {{{comm_str}}}")
            else:
                lines.append("  - すべての最小支持根拠に共通する前提: なし (複数の独立した別証明が存在)")
        else:
            if self.common_premises:
                comm_str = ", ".join(str(p) for p in self.common_premises)
                lines.append(f"  - 暫定的に見つかった範囲での共通前提: {{{comm_str}}} (※完全列挙でないため全体の必須前提とは断定できません)")
            else:
                lines.append("  - 共通前提: 見つかった範囲では共通なし")

        lines.append("  - 留保事項: 本結果はモデル化された有限推論規則の形式的帰結であり、原典の思想的真理性を断定するものではありません。")
        return "\n".join(lines)


@dataclass(frozen=True)
class CutSet:
    """
    目標リテラルの支持を失わせる包含極小の遮断集合
    """
    cut_type: str  # "premises" または "rules"
    elements: Tuple[str, ...]  # 命題IDまたは規則ID
    is_cardinality_minimal: bool = False
    is_subset_minimal: bool = True
    remaining_status: TruthStatus = TruthStatus.UNKNOWN

    @property
    def size(self) -> int:
        return len(self.elements)


@dataclass
class CutSetResult:
    """
    最小遮断集合の探索結果サマリー
    """
    target_literal: Literal
    cut_type: str  # "premises" または "rules"
    initially_unsupported: bool
    candidate_elements: Tuple[str, ...]
    evaluated_count: int
    is_complete: bool
    time_limit_reached: bool = False
    eval_limit_reached: bool = False
    subset_minimal_cuts: List[CutSet] = field(default_factory=list)
    cardinality_minimal_cuts: List[CutSet] = field(default_factory=list)
    model_version: str = "v0.1"
    semantics_mode: str = "diagnostic_monotone"

    def summary_ja(self) -> str:
        lines = [
            f"■ 調べた問い: 目標リテラル {self.target_literal} の支持を失わせる最小遮断集合 ({self.cut_type}) は何か？",
            f"  - 遮断対象タイプ: {'基礎前提の不採用' if self.cut_type == 'premises' else '推論規則の無効化'}",
        ]
        if self.initially_unsupported:
            lines.append("  - 初期状態判定: 目標リテラルはベースライン状態で最初から支持されていません（遮断の必要がありません）。")
            return "\n".join(lines)

        lines.append(f"  - 候補要素数: {len(self.candidate_elements)} 件")
        lines.append(f"  - 評価回数: {self.evaluated_count} 回")
        lines.append(f"  - 列挙完了状況: {'完全列挙完了' if self.is_complete else '探索未完了 (上限到達)'}")
        if self.eval_limit_reached:
            lines.append("    ※ 最大評価試行回数に達したため探索を打ち切りました。")
        if self.time_limit_reached:
            lines.append("    ※ タイムアウト時間の上限に達したため探索を打ち切りました。")

        lines.append(f"  - 発見された包含極小遮断集合: {len(self.subset_minimal_cuts)} 件")
        for idx, c in enumerate(self.subset_minimal_cuts, 1):
            elem_str = ", ".join(c.elements)
            card_mark = " ★要素数最小" if c.is_cardinality_minimal else ""
            lines.append(f"    [{idx}] {{{elem_str}}} (要素数: {c.size}){card_mark} -> 遮断後状態: {c.remaining_status.name}")

        lines.append("  - 留保事項: 「支持喪失」は結論が偽（FALSE）と証明されたことを意味せず、単に根拠が得られなくなった（UNKNOWN）ことを意味します。")
        return "\n".join(lines)


class GroundsAndCutsAnalyzer:
    """
    最小支持根拠（Minimal Support Grounds）および最小遮断集合（Minimal Cut Sets）の分析器。
    推論意味論コアを変更せず、独立シナリオで Evaluator を繰り返し実行する。
    """

    def __init__(self, kb: KnowledgeBase, options: Optional[ScenarioOptions] = None):
        opts = options or ScenarioOptions(mode=SemanticsMode.DIAGNOSTIC_MONOTONE)
        if opts.mode != SemanticsMode.DIAGNOSTIC_MONOTONE:
            raise ValueError(
                f"GroundsAndCutsAnalyzer only supports DIAGNOSTIC_MONOTONE semantics, got {opts.mode}. "
                "Experimental and legacy semantics are strictly excluded."
            )
        self.original_kb = kb
        self.options = opts

    def _make_controllable_kb(self, controllable_prop_ids: Set[str]) -> KnowledgeBase:
        """
        指定された命題群が KnowledgeBase 内で 'axiom' として自動初期支持されないよう、
        prop_type を 'assumption' に一時置換した制御用 KnowledgeBase を生成。
        規則、命題テキスト、DAG関係は100%保持される。
        """
        new_props = []
        for p in self.original_kb.propositions.values():
            if p.id in controllable_prop_ids and p.prop_type == "axiom":
                new_props.append(
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
                new_props.append(p)

        return KnowledgeBase(
            name=f"{self.original_kb.name}_controllable",
            propositions=new_props,
            rules=self.original_kb.rules,
            conflicts=self.original_kb.conflicts,
            undercuts=self.original_kb.undercuts,
        )

    def find_minimal_support_grounds(
        self,
        target_literal: Literal,
        base_premises: Optional[Sequence[Literal]] = None,
        fixed_injected_critiques: Optional[Sequence[Literal]] = None,
        max_evaluations: int = 5000,
        max_size: Optional[int] = None,
        timeout_seconds: Optional[float] = 10.0,
    ) -> SupportGroundsResult:
        """
        【機能A：最小支持根拠】
        指定した目標リテラルについて、支持を導出できる包含極小（subset-minimal）の基礎前提集合を列挙。

        - 目標自身や派生命題を基礎前提に紛れ込ませない。
        - 前提の無効化は否定支持を生成しない（単に不採用にするのみ）。
        - 各候補は新しい評価状態から再計算する。
        - 最小集合に共通する前提を特定する。
        """
        # 1. 基礎前提（変更候補）の特定とバリデーション
        derived_prop_ids = {r.conclusion.prop_id for r in self.original_kb.rules}

        if base_premises is not None:
            raw_candidates = list(base_premises)
        else:
            # 指定なしの場合: 規則の結論になっていない命題、または定義/公理/仮定
            raw_candidates = [
                Literal(p.id, True)
                for p in self.original_kb.propositions.values()
                if p.id not in derived_prop_ids or p.prop_type in ["axiom", "definition", "assumption"]
            ]

        # 目標命題自身、および純粋な派生命題の除外
        valid_candidates: List[Literal] = []
        for lit in raw_candidates:
            if lit.prop_id == target_literal.prop_id:
                continue  # 目標自体の除外
            valid_candidates.append(lit)

        # 重複排除と整列
        valid_candidates = sorted(list(set(valid_candidates)), key=lambda l: (l.prop_id, l.sign))
        candidate_prop_ids = {l.prop_id for l in valid_candidates}

        # 制御用KBの用意（公理の自動発火を抑止し、assumptionsで精密制御）
        eval_kb = self._make_controllable_kb(candidate_prop_ids)
        evaluator = Evaluator(eval_kb)

        critiques = list(fixed_injected_critiques or [])
        limit_size = min(len(valid_candidates), max_size if max_size is not None else len(valid_candidates))

        start_time = time.time()
        eval_count = 0
        is_complete = True
        time_limit_reached = False
        eval_limit_reached = False

        found_grounds_sets: List[FrozenSet[Literal]] = []
        ground_solutions: List[SupportGround] = []
        min_cardinality: Optional[int] = None

        # サイズ 0 (前提なしで自明に成立するか) から探索
        for r in range(0, limit_size + 1):
            if r == 0:
                combos = [()]
            else:
                combos = itertools.combinations(valid_candidates, r)

            for combo in combos:
                eval_count += 1
                if eval_count > max_evaluations:
                    is_complete = False
                    eval_limit_reached = True
                    break

                if timeout_seconds is not None and (time.time() - start_time) > timeout_seconds:
                    is_complete = False
                    time_limit_reached = True
                    break

                combo_set = frozenset(combo)

                # 包含極小性の枝刈り: 既に発見された解の真拡大集合（superset）は極小でないためスキップ
                is_subsumed = False
                for prev_set in found_grounds_sets:
                    if prev_set.issubset(combo_set):
                        is_subsumed = True
                        break
                if is_subsumed:
                    continue

                # 独立シナリオとして評価再計算
                state = evaluator.evaluate(
                    assumptions=combo,
                    injected_critiques=critiques,
                    options=self.options,
                )

                if state.is_supported(target_literal):
                    found_grounds_sets.append(combo_set)
                    if min_cardinality is None:
                        min_cardinality = r

                    ground_solutions.append(
                        SupportGround(
                            premises=tuple(sorted(list(combo), key=lambda x: (x.prop_id, x.sign))),
                            is_cardinality_minimal=False,  # 後で判定
                            is_subset_minimal=True,
                            fired_rules=tuple(sorted(state.fired_rules)),
                        )
                    )

            if not is_complete:
                break

        # 包含極小性 (subset-minimal) と 要素数最小 (cardinality-minimal) の確定
        subset_min_list: List[SupportGround] = []
        cardinality_min_list: List[SupportGround] = []

        for g in ground_solutions:
            g_set = frozenset(g.premises)
            # 他の解の真部分集合が存在しないことを再確認
            is_sub_min = True
            for other_g in ground_solutions:
                other_set = frozenset(other_g.premises)
                if other_set != g_set and other_set.issubset(g_set):
                    is_sub_min = False
                    break

            is_card_min = (min_cardinality is not None and g.size == min_cardinality)

            resolved_g = SupportGround(
                premises=g.premises,
                is_cardinality_minimal=is_card_min,
                is_subset_minimal=is_sub_min,
                fired_rules=g.fired_rules,
            )

            if is_sub_min:
                subset_min_list.append(resolved_g)
            if is_card_min and is_sub_min:
                cardinality_min_list.append(resolved_g)

        # 共通前提 (Intersection) の算出
        if subset_min_list:
            common_set = set(subset_min_list[0].premises)
            for sg in subset_min_list[1:]:
                common_set.intersection_update(sg.premises)
            common_premises = tuple(sorted(list(common_set), key=lambda x: (x.prop_id, x.sign)))
        else:
            common_premises = ()

        return SupportGroundsResult(
            target_literal=target_literal,
            candidate_premises=tuple(valid_candidates),
            evaluated_count=eval_count,
            is_complete=is_complete,
            time_limit_reached=time_limit_reached,
            eval_limit_reached=eval_limit_reached,
            subset_minimal_grounds=subset_min_list,
            cardinality_minimal_grounds=cardinality_min_list,
            common_premises=common_premises,
            model_version="v0.1",
            semantics_mode=self.options.mode.value,
        )

    def find_minimal_cut_sets(
        self,
        target_literal: Literal,
        cut_type: str = "premises",  # "premises" または "rules"
        candidate_elements: Optional[Sequence[str]] = None,
        base_active_premises: Optional[Sequence[Literal]] = None,
        fixed_injected_critiques: Optional[Sequence[Literal]] = None,
        max_evaluations: int = 5000,
        max_cut_size: Optional[int] = None,
        timeout_seconds: Optional[float] = 10.0,
    ) -> CutSetResult:
        """
        【機能B：最小遮断集合】
        変更可能と指定された前提または規則を無効化し、目標リテラルの支持がなくなる包含極小集合を探索。

        - 前提を変える探索と規則を変える探索を区別する。
        - 目標ノードの直接削除は禁止。
        - 「支持喪失」を「否定の証明」と説明しない。
        - 最初から目標が未支持の場合は、その旨を返す。
        - 要素数最小と包含極小を区別する。
        """
        if cut_type not in ["premises", "rules"]:
            raise ValueError(f"cut_type must be 'premises' or 'rules', got {cut_type}")

        critiques = list(fixed_injected_critiques or [])

        # ベースライン有効前提の決定（未指定なら派生でない命題・定義・公理を正リテラルとして承認）
        derived_ids = {r.conclusion.prop_id for r in self.original_kb.rules}
        if base_active_premises is not None:
            active_lits = list(base_active_premises)
        else:
            active_lits = [
                Literal(p.id, True)
                for p in self.original_kb.propositions.values()
                if p.id != target_literal.prop_id and (p.id not in derived_ids or p.prop_type in ["axiom", "definition", "assumption"])
            ]

        # 1. 前提遮断の場合のセットアップ
        if cut_type == "premises":
            if candidate_elements is not None:
                candidates = [cid for cid in candidate_elements if cid != target_literal.prop_id]
            else:
                candidates = [l.prop_id for l in active_lits]
            candidates = sorted(list(set(candidates)))

            # 制御用KB
            eval_kb = self._make_controllable_kb(set(candidates))
            evaluator = Evaluator(eval_kb)

            # ベースライン評価（遮断ゼロ）
            base_state = evaluator.evaluate(assumptions=active_lits, injected_critiques=critiques, options=self.options)
            if not base_state.is_supported(target_literal):
                return CutSetResult(
                    target_literal=target_literal,
                    cut_type="premises",
                    initially_unsupported=True,
                    candidate_elements=tuple(candidates),
                    evaluated_count=1,
                    is_complete=True,
                    subset_minimal_cuts=[],
                    cardinality_minimal_cuts=[],
                    model_version="v0.1",
                    semantics_mode=self.options.mode.value,
                )

        # 2. 規則遮断の場合のセットアップ
        else:
            if candidate_elements is not None:
                candidates = sorted(list(set(candidate_elements)))
            else:
                candidates = sorted([r.rule_id for r in self.original_kb.rules])

            # ベースライン評価（全規則有効）
            evaluator = Evaluator(self.original_kb)
            base_state = evaluator.evaluate(
                assumptions=active_lits,
                injected_critiques=critiques,
                options=self.options,
            )
            if not base_state.is_supported(target_literal):
                return CutSetResult(
                    target_literal=target_literal,
                    cut_type="rules",
                    initially_unsupported=True,
                    candidate_elements=tuple(candidates),
                    evaluated_count=1,
                    is_complete=True,
                    subset_minimal_cuts=[],
                    cardinality_minimal_cuts=[],
                    model_version="v0.1",
                    semantics_mode=self.options.mode.value,
                )

        # 探索ループ
        limit_size = min(len(candidates), max_cut_size if max_cut_size is not None else len(candidates))
        start_time = time.time()
        eval_count = 0
        is_complete = True
        time_limit_reached = False
        eval_limit_reached = False

        found_cut_sets: List[FrozenSet[str]] = []
        raw_cut_solutions: List[Tuple[FrozenSet[str], TruthStatus]] = []
        min_cardinality: Optional[int] = None

        for r in range(1, limit_size + 1):
            for combo in itertools.combinations(candidates, r):
                eval_count += 1
                if eval_count > max_evaluations:
                    is_complete = False
                    eval_limit_reached = True
                    break

                if timeout_seconds is not None and (time.time() - start_time) > timeout_seconds:
                    is_complete = False
                    time_limit_reached = True
                    break

                combo_set = frozenset(combo)

                # 包含極小性の枝刈り: 既に遮断集合となっているものの真拡大集合（superset）は極小遮断でない
                is_subsumed = False
                for prev_cut in found_cut_sets:
                    if prev_cut.issubset(combo_set):
                        is_subsumed = True
                        break
                if is_subsumed:
                    continue

                if cut_type == "premises":
                    # 前提遮断: active_lits から combo に含まれる前提を除外して評価
                    # (否定支持を注入するのではなく、単に不採用にする)
                    remaining_asms = [l for l in active_lits if l.prop_id not in combo_set]
                    state = evaluator.evaluate(
                        assumptions=remaining_asms,
                        injected_critiques=critiques,
                        options=self.options,
                    )
                else:
                    # 規則遮断: combo に含まれる規則を除外した KB で評価
                    cut_rules = [rule for rule in self.original_kb.rules if rule.rule_id not in combo_set]
                    temp_kb = KnowledgeBase(
                        name=f"{self.original_kb.name}_cut",
                        propositions=list(self.original_kb.propositions.values()),
                        rules=cut_rules,
                        conflicts=self.original_kb.conflicts,
                        undercuts=self.original_kb.undercuts,
                    )
                    temp_evaluator = Evaluator(temp_kb)
                    state = temp_evaluator.evaluate(
                        assumptions=active_lits,
                        injected_critiques=critiques,
                        options=self.options,
                    )

                # 目標リテラルの支持が失われたか判定
                if not state.is_supported(target_literal):
                    found_cut_sets.append(combo_set)
                    st = state.get_status(target_literal.prop_id)
                    raw_cut_solutions.append((combo_set, st))
                    if min_cardinality is None:
                        min_cardinality = r

            if not is_complete:
                break

        # 包含極小解と要素数最小解の整理
        subset_min_cuts: List[CutSet] = []
        cardinality_min_cuts: List[CutSet] = []

        for cut_set, st in raw_cut_solutions:
            is_sub_min = True
            for other_set, _ in raw_cut_solutions:
                if other_set != cut_set and other_set.issubset(cut_set):
                    is_sub_min = False
                    break

            is_card_min = (min_cardinality is not None and len(cut_set) == min_cardinality)

            cut_obj = CutSet(
                cut_type=cut_type,
                elements=tuple(sorted(list(cut_set))),
                is_cardinality_minimal=is_card_min,
                is_subset_minimal=is_sub_min,
                remaining_status=st,
            )

            if is_sub_min:
                subset_min_cuts.append(cut_obj)
            if is_card_min and is_sub_min:
                cardinality_min_cuts.append(cut_obj)

        return CutSetResult(
            target_literal=target_literal,
            cut_type=cut_type,
            initially_unsupported=False,
            candidate_elements=tuple(candidates),
            evaluated_count=eval_count,
            is_complete=is_complete,
            time_limit_reached=time_limit_reached,
            eval_limit_reached=eval_limit_reached,
            subset_minimal_cuts=subset_min_cuts,
            cardinality_minimal_cuts=cardinality_min_cuts,
            model_version="v0.1",
            semantics_mode=self.options.mode.value,
        )
