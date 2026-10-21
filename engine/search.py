"""
幾何学的哲学推論エンジン: 最小前提探索モジュール (Minimal Assumption Search)

包含極小 (subset-minimal) と要素数最小 (cardinality-minimal) の厳密な区別。
目標命題の自己仮定禁止、矛盾解の許容フラグ、探索打ち切り時の最小性未確認フラグを完備。
"""
from dataclasses import dataclass, field
import itertools
from typing import FrozenSet, List, Optional, Sequence, Set, Tuple

from engine.semantics import (
    Evaluator,
    KnowledgeBase,
    Literal,
    TruthStatus,
    SemanticsMode,
    ScenarioOptions,
)


@dataclass(frozen=True)
class AssumptionSolution:
    """発見された前提セット"""
    assumptions: Tuple[Literal, ...]
    target_status: TruthStatus
    is_cardinality_minimal: bool = False
    is_subset_minimal: bool = False


@dataclass
class SearchResult:
    """探索結果サマリー"""
    target_prop_id: str
    target_sign: bool
    candidate_count: int
    evaluated_combinations_count: int
    is_complete: bool
    unverified_minimality: bool
    cardinality_minimal_solutions: List[AssumptionSolution] = field(default_factory=list)
    subset_minimal_solutions: List[AssumptionSolution] = field(default_factory=list)
    model_version: str = "v0.1"
    semantics_mode: str = "diagnostic_monotone"


class MinimalAssumptionSearch:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self.evaluator = Evaluator(kb)

    def find_assumptions_for_target(
        self,
        target_prop_id: str,
        target_sign: bool = True,
        candidate_prop_ids: Optional[Sequence[str]] = None,
        allow_target_as_assumption: bool = False,
        allow_conflict: bool = False,
        max_assumptions_size: int = 5,
        max_evaluations: int = 5000,
        options: Optional[ScenarioOptions] = None,
    ) -> SearchResult:
        """
        目標命題を成立させるための最小前提セットを探索。

        Parameters:
        - target_prop_id: 成立させたい命題ID
        - target_sign: Trueなら正支持 (TRUE)、Falseなら負支持 (FALSE)
        - candidate_prop_ids: 仮定として許可された命題ID一覧（指定なしなら全 definition / axiom）
        - allow_target_as_assumption: 目標命題そのものを仮定に含めることを許すか (初期値: False)
        - allow_conflict: 目標命題が CONFLICT になる解を許すか (初期値: False)
        - max_assumptions_size: 探索する前提セットの最大要素数
        - max_evaluations: 最大評価試行回数
        - options: 評価オプション (legacy モードは除外)
        """
        opts = options or ScenarioOptions(mode=SemanticsMode.DIAGNOSTIC_MONOTONE)
        if opts.mode == SemanticsMode.LEGACY:
            raise ValueError("Legacy semantics is excluded from minimal assumption search. Use DIAGNOSTIC_MONOTONE.")

        target_lit = Literal(target_prop_id, target_sign)

        # 候補命題の決定
        if candidate_prop_ids is not None:
            candidates = list(candidate_prop_ids)
        else:
            # デフォルトは定義 (definition) と、必要に応じて公理
            candidates = [
                p.id for p in self.kb.propositions.values()
                if p.prop_type in ["definition", "axiom"]
            ]

        # 目標命題自体の除外
        if not allow_target_as_assumption and target_prop_id in candidates:
            candidates = [cid for cid in candidates if cid != target_prop_id]

        candidates = sorted(list(set(candidates)))

        eval_count = 0
        is_complete = True
        unverified_minimality = False
        raw_solutions: List[Tuple[FrozenSet[Literal], TruthStatus]] = []

        # 既に前提なしで成立しているか確認
        base_state = self.evaluator.evaluate(options=opts)
        base_status = base_state.get_status(target_prop_id)
        if (target_sign and base_status.has_pos) or (not target_sign and base_status.has_neg):
            if allow_conflict or base_status != TruthStatus.CONFLICT:
                sol = AssumptionSolution(
                    assumptions=(),
                    target_status=base_status,
                    is_cardinality_minimal=True,
                    is_subset_minimal=True,
                )
                return SearchResult(
                    target_prop_id=target_prop_id,
                    target_sign=target_sign,
                    candidate_count=len(candidates),
                    evaluated_combinations_count=1,
                    is_complete=True,
                    unverified_minimality=False,
                    cardinality_minimal_solutions=[sol],
                    subset_minimal_solutions=[sol],
                    model_version="v0.1",
                    semantics_mode=opts.mode.value,
                )

        # サイズ 1 から max_assumptions_size までの組み合わせを探索
        found_any = False
        min_cardinality: Optional[int] = None

        # 仮定リテラル候補 (正リテラルを基本とする)
        candidate_lits = [Literal(cid, True) for cid in candidates]

        for r in range(1, min(len(candidate_lits), max_assumptions_size) + 1):
            for combo in itertools.combinations(candidate_lits, r):
                eval_count += 1
                if eval_count > max_evaluations:
                    is_complete = False
                    unverified_minimality = True
                    break

                combo_set = frozenset(combo)

                # 既に真部分集合で成立しているなら、この superset は極小ではない
                # (包含極小性の枝刈り)
                is_subsumed = False
                for prev_set, _ in raw_solutions:
                    if prev_set.issubset(combo_set):
                        is_subsumed = True
                        break
                if is_subsumed:
                    continue

                state = self.evaluator.evaluate(assumptions=combo, options=opts)
                status = state.get_status(target_prop_id)

                satisfied = False
                if target_sign and status.has_pos:
                    satisfied = True
                elif not target_sign and status.has_neg:
                    satisfied = True

                if satisfied:
                    if not allow_conflict and status == TruthStatus.CONFLICT:
                        satisfied = False

                if satisfied:
                    raw_solutions.append((combo_set, status))
                    if min_cardinality is None:
                        min_cardinality = r

            if not is_complete:
                break

        # 包含極小解 (subset-minimal) と 要素数最小解 (cardinality-minimal) の分類
        subset_min_solutions: List[AssumptionSolution] = []
        cardinality_min_solutions: List[AssumptionSolution] = []

        for sol_set, st in raw_solutions:
            # sol_set の真部分集合が raw_solutions に存在しないことを確認
            is_subset_min = True
            for other_set, _ in raw_solutions:
                if other_set != sol_set and other_set.issubset(sol_set):
                    is_subset_min = False
                    break

            is_card_min = (min_cardinality is not None and len(sol_set) == min_cardinality)

            solution_obj = AssumptionSolution(
                assumptions=tuple(sorted(list(sol_set), key=lambda x: x.prop_id)),
                target_status=st,
                is_cardinality_minimal=is_card_min,
                is_subset_minimal=is_subset_min,
            )

            if is_subset_min:
                subset_min_solutions.append(solution_obj)
            if is_card_min:
                cardinality_min_solutions.append(solution_obj)

        return SearchResult(
            target_prop_id=target_prop_id,
            target_sign=target_sign,
            candidate_count=len(candidates),
            evaluated_combinations_count=eval_count,
            is_complete=is_complete,
            unverified_minimality=unverified_minimality,
            cardinality_minimal_solutions=cardinality_min_solutions,
            subset_minimal_solutions=subset_min_solutions,
            model_version="v0.1",
            semantics_mode=opts.mode.value,
        )
