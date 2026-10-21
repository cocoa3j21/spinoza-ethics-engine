"""
幾何学的哲学推論エンジン: 形式意味論コア (Formal Semantics Core)

命題、リテラル、推論規則、攻撃・批判関係の分離。
2ビット支持モデル（00=UNKNOWN, 10=TRUE, 01=FALSE, 11=CONFLICT）
ワークリストによる最小不動点計算と TopologicalSorter によるDAG検証。
"""
from dataclasses import dataclass, field
from enum import Enum
import graphlib
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple


class TruthStatus(Enum):
    """
    2ビット支持モデルによる真理値表現
    - 00: UNKNOWN  (正支持なし, 負支持なし)
    - 10: TRUE     (正支持あり, 負支持なし)
    - 01: FALSE    (正支持なし, 負支持あり)
    - 11: CONFLICT (正支持あり, 負支持あり: 固有の矛盾)
    """
    UNKNOWN = (False, False)
    TRUE = (True, False)
    FALSE = (False, True)
    CONFLICT = (True, True)

    @property
    def has_pos(self) -> bool:
        return self.value[0]

    @property
    def has_neg(self) -> bool:
        return self.value[1]

    @classmethod
    def from_bits(cls, pos: bool, neg: bool) -> "TruthStatus":
        val = (bool(pos), bool(neg))
        for member in cls:
            if member.value == val:
                return member
        return cls.UNKNOWN

    def __str__(self) -> str:
        return self.name


class EvaluationStatus(Enum):
    """
    推論エンジンの計算完了・収束ステータス
    - CONVERGED: 不動点に到達して正常に収束
    - CYCLE_DETECTED: 状態反復・非収束ループを検出
    - STEP_LIMIT_EXCEEDED: 最大計算ステップ数を超過
    """
    CONVERGED = "CONVERGED"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    STEP_LIMIT_EXCEEDED = "STEP_LIMIT_EXCEEDED"

    def __str__(self) -> str:
        return self.value


class SemanticsMode(Enum):
    """
    推論意味論の実行モード
    - DIAGNOSTIC_MONOTONE: v0.1 標準意味論（単調蓄積、診断専用Conflict、事前Undercut確定）
    - EXPERIMENTAL: 実験的意味論（Truth Maintenance 完全撤回型、振動検出）
    - LEGACY: 旧方式（幽霊的正当化による固定化、ベンチマーク対象外）
    """
    DIAGNOSTIC_MONOTONE = "diagnostic_monotone"
    EXPERIMENTAL = "experimental"
    LEGACY = "legacy"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Literal:
    """
    符号付き命題リテラル
    - sign=True: 正リテラル (P)
    - sign=False: 負リテラル (¬P)
    """
    prop_id: str
    sign: bool = True

    def negate(self) -> "Literal":
        return Literal(self.prop_id, not self.sign)

    def __repr__(self) -> str:
        return f"{self.prop_id}" if self.sign else f"¬{self.prop_id}"


@dataclass(frozen=True)
class Proposition:
    """命題の定義"""
    id: str
    title: str
    text_ja: str
    prop_type: str  # 'axiom', 'definition', 'proposition', 'critique'
    logical_form: str = ""
    source_system: str = ""
    source_ref: str = ""  # 原典位置 (e.g. "Ethica I, Def. 1")
    is_provisional: bool = False  # 原典未確認・暫定解釈フラグ


@dataclass(frozen=True)
class InferenceRule:
    """
    推論規則 (証明規則)
    premises の全リテラルが満たされた場合に conclusion リテラルを支持する。
    1つの命題に対して複数の InferenceRule（別証明）を登録可能。
    """
    rule_id: str
    premises: Tuple[Literal, ...]
    conclusion: Literal
    name: str = ""
    source_ref: str = ""
    is_provisional: bool = False


@dataclass(frozen=True)
class ConflictPair:
    """
    2つのリテラル間の相互排他（Rebutting Conflict）
    両方が同時に支持された場合、両命題は CONFLICT となる。
    """
    literal_a: Literal
    literal_b: Literal
    reason: str = ""


@dataclass(frozen=True)
class UndercutDefeater:
    """
    推論規則の無効化（Undercutting Defeater）
    critique_literal が成立した際、target_rule_id の適用を阻止する。
    """
    critique_literal: Literal
    target_rule_id: str
    reason: str = ""


class CyclicDependencyError(ValueError):
    """推論規則の前提関係に循環依存が存在する場合のエラー"""
    pass


class UndefinedIdentifierError(KeyError):
    """未定義の命題IDが参照された場合のエラー"""
    pass


class KnowledgeBase:
    """
    不変の哲学知識ベースモデル。
    命題、規則、批判定義を保持し、構築時に循環と未定義IDを厳格に検証する。
    """
    def __init__(
        self,
        name: str,
        propositions: Sequence[Proposition],
        rules: Sequence[InferenceRule] = (),
        conflicts: Sequence[ConflictPair] = (),
        undercuts: Sequence[UndercutDefeater] = (),
    ):
        self.name = name
        self.propositions: Mapping[str, Proposition] = {p.id: p for p in propositions}
        self.rules: Tuple[InferenceRule, ...] = tuple(rules)
        self.conflicts: Tuple[ConflictPair, ...] = tuple(conflicts)
        self.undercuts: Tuple[UndercutDefeater, ...] = tuple(undercuts)

        # 構築時の検証
        self._validate_identifiers()
        self._validate_dag()

    def _validate_identifiers(self):
        """規則・衝突・無効化で参照されるIDがすべて登録済みか検証"""
        known_ids = set(self.propositions.keys())

        for r in self.rules:
            if r.conclusion.prop_id not in known_ids:
                raise UndefinedIdentifierError(f"Rule '{r.rule_id}' conclusion references undefined prop '{r.conclusion.prop_id}'")
            for prem in r.premises:
                if prem.prop_id not in known_ids:
                    raise UndefinedIdentifierError(f"Rule '{r.rule_id}' premise references undefined prop '{prem.prop_id}'")

        for c in self.conflicts:
            if c.literal_a.prop_id not in known_ids:
                raise UndefinedIdentifierError(f"Conflict references undefined prop '{c.literal_a.prop_id}'")
            if c.literal_b.prop_id not in known_ids:
                raise UndefinedIdentifierError(f"Conflict references undefined prop '{c.literal_b.prop_id}'")

        for u in self.undercuts:
            if u.critique_literal.prop_id not in known_ids:
                raise UndefinedIdentifierError(f"Undercut references undefined critique prop '{u.critique_literal.prop_id}'")
            known_rule_ids = {r.rule_id for r in self.rules}
            if u.target_rule_id not in known_rule_ids:
                raise UndefinedIdentifierError(f"Undercut references undefined target rule '{u.target_rule_id}'")

    def _validate_dag(self):
        """
        推論規則による証明依存関係が有向非巡回グラフ (DAG) であることを
        graphlib.TopologicalSorter で検証。
        """
        graph: Dict[str, Set[str]] = {p_id: set() for p_id in self.propositions.keys()}
        for r in self.rules:
            conc = r.conclusion.prop_id
            for prem in r.premises:
                # 結論 conc は 前提 prem に依存
                graph[conc].add(prem.prop_id)

        try:
            ts = graphlib.TopologicalSorter(graph)
            # 循環があれば CycleError が発生
            tuple(ts.static_order())
        except graphlib.CycleError as e:
            raise CyclicDependencyError(f"Circular dependency detected in proof rules: {e.args[1]}") from e


@dataclass(frozen=True)
class ScenarioOptions:
    """シナリオ評価オプション"""
    mode: SemanticsMode = SemanticsMode.DIAGNOSTIC_MONOTONE  # デフォルト: v0.1 標準意味論
    max_steps: int = 1000
    track_cycles: bool = True  # 状態履歴を追跡して無限振動・非収束ループを検出するか
    # 個別設定のオーバーライド用（Noneの場合はmodeのデフォルトに従う）
    require_untainted_premises: Optional[bool] = None
    retract_conflicts_on_premise_loss: Optional[bool] = None

    def get_require_untainted_premises(self) -> bool:
        if self.require_untainted_premises is not None:
            return self.require_untainted_premises
        # 標準モードでは前提汚染による遮断を行わない
        return self.mode in (SemanticsMode.EXPERIMENTAL, SemanticsMode.LEGACY)

    def get_retract_conflicts_on_premise_loss(self) -> bool:
        if self.retract_conflicts_on_premise_loss is not None:
            return self.retract_conflicts_on_premise_loss
        return self.mode == SemanticsMode.EXPERIMENTAL


class EvaluationState:
    """
    シナリオごとの計算結果・派生状態。
    元の KnowledgeBase を一切改変せず、独立して評価を行う。
    """
    def __init__(self, kb: KnowledgeBase, mode: SemanticsMode = SemanticsMode.DIAGNOSTIC_MONOTONE):
        self.kb = kb
        self.mode = mode
        # 各命題IDに対する正支持理由と負支持理由 (rule_id または "assumption:..." 等)
        self.positive_supports: Dict[str, Set[str]] = {p: set() for p in kb.propositions}
        self.negative_supports: Dict[str, Set[str]] = {p: set() for p in kb.propositions}
        self.undercut_rules: Set[str] = set()
        self.fired_rules: Set[str] = set()
        self.status: EvaluationStatus = EvaluationStatus.CONVERGED
        self.is_complete: bool = True
        self.step_count: int = 0
        self.cycle_info: Optional[Dict[str, Any]] = None
        # 診断専用ConflictPairの評価結果
        self.diagnostic_conflicts: List[Dict[str, Any]] = []
        # 現在有効な正当化根拠の十全性検証結果 (停止状態と正当化検証の区別)
        self.justification_validation: Dict[str, Any] = {}

    def get_status(self, prop_id: str) -> TruthStatus:
        """指定命題の現在の2ビット真理状態を取得"""
        pos = len(self.positive_supports.get(prop_id, set())) > 0
        neg = len(self.negative_supports.get(prop_id, set())) > 0
        return TruthStatus.from_bits(pos, neg)

    def is_supported(self, lit: Literal) -> bool:
        """指定リテラルが現在支持されているか"""
        st = self.get_status(lit.prop_id)
        return st.has_pos if lit.sign else st.has_neg

    def is_tainted(self, prop_id: str) -> bool:
        """命題が矛盾 (CONFLICT) しているか"""
        return self.get_status(prop_id) == TruthStatus.CONFLICT

    def summary(self) -> Dict[str, List[str]]:
        """全命題を排他的4値に分類して集計"""
        res = {
            "UNKNOWN": [],
            "TRUE": [],
            "FALSE": [],
            "CONFLICT": []
        }
        for prop_id in sorted(self.kb.propositions.keys()):
            st = self.get_status(prop_id)
            res[st.name].append(prop_id)
        return res


class Evaluator:
    """
    決定論的ワークリスト演繹評価器。
    基本モデルとシナリオ入力を受け取り、新規の EvaluationState を生成・評価する。
    """
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def evaluate(
        self,
        assumptions: Sequence[Literal] = (),
        injected_critiques: Sequence[Literal] = (),
        options: Optional[ScenarioOptions] = None,
    ) -> EvaluationState:
        """
        ワークリストアルゴリズムによる不動点計算。
        1. 初期仮定・公理の支持を登録。
        2. Undercutによる無効規則を確定。
        3. ワークリストで順次伝播。
        4. 不動点到達後、事後診断（ConflictPair等）と正当化検証を実行。
        """
        opts = options or ScenarioOptions()
        mode = opts.mode
        is_diagnostic = (mode == SemanticsMode.DIAGNOSTIC_MONOTONE)
        req_untainted = opts.get_require_untainted_premises()
        retract_conflicts = opts.get_retract_conflicts_on_premise_loss()

        state = EvaluationState(self.kb, mode=mode)

        # ワークリスト: 状態変化があった (prop_id) をキュー管理（決定論的FIFO）
        worklist: List[str] = []
        in_worklist: Set[str] = set()

        def push_worklist(pid: str):
            if pid not in in_worklist:
                in_worklist.add(pid)
                worklist.append(pid)

        # 1. 公理 (axiom) の自動初期支持 (公理はデフォルトで正支持を持つ)
        for p in self.kb.propositions.values():
            if p.prop_type == "axiom":
                state.positive_supports[p.id].add(f"axiom:{p.id}")
                push_worklist(p.id)

        # 2. シナリオの仮定・承認リテラル
        for asm in assumptions:
            if asm.sign:
                state.positive_supports[asm.prop_id].add(f"assumption:{asm.prop_id}")
            else:
                state.negative_supports[asm.prop_id].add(f"assumption:not_{asm.prop_id}")
            push_worklist(asm.prop_id)

        # 3. 注入された批判リテラル
        for crit in injected_critiques:
            if crit.sign:
                state.positive_supports[crit.prop_id].add(f"critique:{crit.prop_id}")
            else:
                state.negative_supports[crit.prop_id].add(f"critique:not_{crit.prop_id}")
            push_worklist(crit.prop_id)

        # 4. Undercutによる無効規則集合の確定 (評価開始前に確定)
        for u in self.kb.undercuts:
            if state.is_supported(u.critique_literal):
                state.undercut_rules.add(u.target_rule_id)

        # ルールの高速逆引きインデックス: premise_prop_id -> rules
        rule_premise_index: Dict[str, List[InferenceRule]] = {p: [] for p in self.kb.propositions}
        for r in self.kb.rules:
            for prem in r.premises:
                rule_premise_index[prem.prop_id].append(r)

        # Undercutの高速逆引きインデックス (動的モード用)
        undercut_index: Dict[str, List[UndercutDefeater]] = {p: [] for p in self.kb.propositions}
        for u in self.kb.undercuts:
            undercut_index[u.critique_literal.prop_id].append(u)

        # 衝突ペアの高速逆引きインデックス (動的モード用)
        conflict_index: Dict[str, List[ConflictPair]] = {p: [] for p in self.kb.propositions}
        for c in self.kb.conflicts:
            conflict_index[c.literal_a.prop_id].append(c)
            conflict_index[c.literal_b.prop_id].append(c)

        steps = 0
        history: Dict[Any, int] = {}

        # ワークリスト反復
        while worklist and steps < opts.max_steps:
            steps += 1

            if opts.track_cycles and not is_diagnostic:
                # 状態シグネチャ: 支持集合、発火規則、Undercut規則、保留キュー
                sig = (
                    tuple((p, tuple(sorted(state.positive_supports[p]))) for p in sorted(state.positive_supports)),
                    tuple((p, tuple(sorted(state.negative_supports[p]))) for p in sorted(state.negative_supports)),
                    tuple(sorted(state.fired_rules)),
                    tuple(sorted(state.undercut_rules)),
                    tuple(sorted(worklist)),
                )
                if sig in history:
                    state.status = EvaluationStatus.CYCLE_DETECTED
                    state.is_complete = False
                    state.cycle_info = {
                        "first_seen_step": history[sig],
                        "cycle_detected_at_step": steps,
                    }
                    break
                history[sig] = steps

            curr_prop_id = worklist.pop(0)
            in_worklist.discard(curr_prop_id)

            # --- 動的撤回・衝突支持生成 (EXPERIMENTAL / LEGACY モードのみ) ---
            if not is_diagnostic:
                # (A) 動的 Undercut の評価
                for u in undercut_index.get(curr_prop_id, []):
                    if u.target_rule_id not in state.undercut_rules:
                        if state.is_supported(u.critique_literal):
                            state.undercut_rules.add(u.target_rule_id)
                            target_rule = next((r for r in self.kb.rules if r.rule_id == u.target_rule_id), None)
                            if target_rule and target_rule.rule_id in state.fired_rules:
                                state.fired_rules.remove(target_rule.rule_id)
                                conc = target_rule.conclusion
                                if conc.sign:
                                    state.positive_supports[conc.prop_id].discard(target_rule.rule_id)
                                else:
                                    state.negative_supports[conc.prop_id].discard(target_rule.rule_id)
                                push_worklist(conc.prop_id)

                # (B) Conflict による否定支持の生成・撤回
                for c in conflict_index.get(curr_prop_id, []):
                    if state.is_supported(c.literal_a) and state.is_supported(c.literal_b):
                        added_a = False
                        added_b = False
                        if c.literal_a.sign:
                            if "conflict:" + c.literal_b.prop_id not in state.negative_supports[c.literal_a.prop_id]:
                                state.negative_supports[c.literal_a.prop_id].add(f"conflict:{c.literal_b.prop_id}")
                                added_a = True
                        else:
                            if "conflict:" + c.literal_b.prop_id not in state.positive_supports[c.literal_a.prop_id]:
                                state.positive_supports[c.literal_a.prop_id].add(f"conflict:{c.literal_b.prop_id}")
                                added_a = True

                        if c.literal_b.sign:
                            if "conflict:" + c.literal_a.prop_id not in state.negative_supports[c.literal_b.prop_id]:
                                state.negative_supports[c.literal_b.prop_id].add(f"conflict:{c.literal_a.prop_id}")
                                added_b = True
                        else:
                            if "conflict:" + c.literal_a.prop_id not in state.positive_supports[c.literal_b.prop_id]:
                                state.positive_supports[c.literal_b.prop_id].add(f"conflict:{c.literal_a.prop_id}")
                                added_b = True

                        if added_a: push_worklist(c.literal_a.prop_id)
                        if added_b: push_worklist(c.literal_b.prop_id)
                    elif retract_conflicts:
                        tag_b = f"conflict:{c.literal_b.prop_id}"
                        tag_a = f"conflict:{c.literal_a.prop_id}"
                        removed_a = False
                        removed_b = False

                        if c.literal_a.sign and tag_b in state.negative_supports[c.literal_a.prop_id]:
                            state.negative_supports[c.literal_a.prop_id].remove(tag_b)
                            removed_a = True
                        elif not c.literal_a.sign and tag_b in state.positive_supports[c.literal_a.prop_id]:
                            state.positive_supports[c.literal_a.prop_id].remove(tag_b)
                            removed_a = True

                        if c.literal_b.sign and tag_a in state.negative_supports[c.literal_b.prop_id]:
                            state.negative_supports[c.literal_b.prop_id].remove(tag_a)
                            removed_b = True
                        elif not c.literal_b.sign and tag_a in state.positive_supports[c.literal_b.prop_id]:
                            state.positive_supports[c.literal_b.prop_id].remove(tag_a)
                            removed_b = True

                        if removed_a: push_worklist(c.literal_a.prop_id)
                        if removed_b: push_worklist(c.literal_b.prop_id)

                # (C) 前提の矛盾 (CONFLICT) に伴う既存発火規則の撤回 (Truth Maintenance)
                if req_untainted and state.is_tainted(curr_prop_id):
                    for rule in rule_premise_index.get(curr_prop_id, []):
                        if rule.rule_id in state.fired_rules:
                            state.fired_rules.remove(rule.rule_id)
                            conc = rule.conclusion
                            if conc.sign:
                                state.positive_supports[conc.prop_id].discard(rule.rule_id)
                            else:
                                state.negative_supports[conc.prop_id].discard(rule.rule_id)
                            push_worklist(conc.prop_id)

            # --- (D) 推論規則の評価 ---
            for rule in rule_premise_index.get(curr_prop_id, []):
                # 既に発火済みならスキップ
                if rule.rule_id in state.fired_rules:
                    continue

                # Undercut されていたら発火しない
                if rule.rule_id in state.undercut_rules:
                    continue

                # 前提の充足判定
                premises_satisfied = True
                for prem in rule.premises:
                    # 指定リテラルの支持の存在だけで判定 (標準モード)
                    if not state.is_supported(prem):
                        premises_satisfied = False
                        break
                    # 前提の健全性 (非標準モードのみ: 前提が CONFLICT している場合は遮断)
                    if req_untainted and state.is_tainted(prem.prop_id):
                        premises_satisfied = False
                        break

                if premises_satisfied:
                    state.fired_rules.add(rule.rule_id)
                    conc = rule.conclusion
                    added = False
                    if conc.sign:
                        if rule.rule_id not in state.positive_supports[conc.prop_id]:
                            state.positive_supports[conc.prop_id].add(rule.rule_id)
                            added = True
                    else:
                        if rule.rule_id not in state.negative_supports[conc.prop_id]:
                            state.negative_supports[conc.prop_id].add(rule.rule_id)
                            added = True

                    if added:
                        push_worklist(conc.prop_id)

        state.step_count = steps
        if worklist and steps >= opts.max_steps and state.status == EvaluationStatus.CONVERGED:
            state.is_complete = False
            state.status = EvaluationStatus.STEP_LIMIT_EXCEEDED
        elif state.status == EvaluationStatus.CONVERGED:
            state.is_complete = True

        # --- 事後診断: ConflictPair の評価 (標準モードでは診断専用) ---
        for c in self.kb.conflicts:
            if state.is_supported(c.literal_a) and state.is_supported(c.literal_b):
                state.diagnostic_conflicts.append({
                    "literal_a": str(c.literal_a),
                    "literal_b": str(c.literal_b),
                    "prop_a": c.literal_a.prop_id,
                    "prop_b": c.literal_b.prop_id,
                    "status_a": state.get_status(c.literal_a.prop_id).name,
                    "status_b": state.get_status(c.literal_b.prop_id).name,
                    "reason": c.reason or "両立不能な命題対が同時に支持されています",
                })

        # --- 事後検証: 現在有効な正当化根拠の十全性 (停止状態と正当化検証結果の区別) ---
        validation: Dict[str, Any] = {}
        rule_map = {r.rule_id: r for r in self.kb.rules}
        for p_id in sorted(self.kb.propositions.keys()):
            pos_supps = set(state.positive_supports[p_id])
            neg_supps = set(state.negative_supports[p_id])
            valid_pos = set()
            valid_neg = set()

            for supp in pos_supps:
                if supp in rule_map:
                    rule = rule_map[supp]
                    if all(state.is_supported(prem) for prem in rule.premises) and rule.rule_id not in state.undercut_rules:
                        valid_pos.add(supp)
                else:
                    valid_pos.add(supp)  # 公理や仮定

            for supp in neg_supps:
                if supp in rule_map:
                    rule = rule_map[supp]
                    if all(state.is_supported(prem) for prem in rule.premises) and rule.rule_id not in state.undercut_rules:
                        valid_neg.add(supp)
                elif supp.startswith("conflict:"):
                    opp_id = supp.replace("conflict:", "")
                    if len(state.positive_supports.get(opp_id, set())) > 0 or len(state.negative_supports.get(opp_id, set())) > 0:
                        valid_neg.add(supp)
                else:
                    valid_neg.add(supp)

            phantom_pos = pos_supps - valid_pos
            phantom_neg = neg_supps - valid_neg
            validation[p_id] = {
                "has_valid_positive_justification": len(valid_pos) > 0,
                "has_valid_negative_justification": len(valid_neg) > 0,
                "is_fully_justified": len(phantom_pos) == 0 and len(phantom_neg) == 0,
                "phantom_positive_supports": list(phantom_pos),
                "phantom_negative_supports": list(phantom_neg),
            }
        state.justification_validation = validation

        return state


def analyze_extended_dependencies(kb: KnowledgeBase) -> Dict[str, Any]:
    """
    推論規則、批判(Undercut)、および衝突(Conflict)を含むマクロ依存グラフを解析。
    閉路（正閉路、および負辺を含む閉路）の存在を検知・分析する。

    【理論的注意事項】
    1. 辺数偶奇と負辺数偶奇の区別:
       「辺数（edge count）」の偶奇と「負辺数（negative edge count: 批判・衝突辺数）」の偶奇は
       明確に区別される。非単調推論の振動・非収束で本質的となるのは「奇数個の負辺を持つ閉路」
       （negative_edge_count % 2 == 1）である。
    2. 総合DAG制約と層化条件の区別:
       グラフ全体が非巡回である「総合DAG制約」と、論理プログラミング等の「層化条件（Stratification）」
       は同義ではない。総合DAG制約は正負すべての依存の閉路を禁じる極めて強い十分条件であり、
       層化条件は否定・攻撃を跨ぐ閉路のみを禁じ、同一層内の正の証明依存は許容する。
    3. Stable Extension の存在性:
       奇数個の負辺を持つ閉路が存在しても、外部からの優勢な攻撃によって閉路構成要素が無効化される
       場合など、Dung の stable extension が存在し得る場合がある。したがって閉路の存在だけで
       直ちに stable extension 不存在と断定することはできない。
    4. Dung 意味論との対応:
       本エンジンの実験モード等の撤回方式と、Dung の抽象論証意味論（Ground/Preferred/Stable等）
       の厳密な数学的対応関係は「未定義（Undefined）」である。
    """
    edges: List[Dict[str, Any]] = []

    # 1. 規則の依存: premise -> conclusion (正の証明依存)
    for r in kb.rules:
        for prem in r.premises:
            edges.append({
                "from": prem.prop_id,
                "to": r.conclusion.prop_id,
                "type": "rule",
                "sign": +1 if r.conclusion.sign == prem.sign else -1,
                "id": r.rule_id,
            })

    # 2. Undercut の依存: critique -> rule.conclusion (批判による規則無効化: 負の依存)
    rule_map = {r.rule_id: r for r in kb.rules}
    for u in kb.undercuts:
        if u.target_rule_id in rule_map:
            conc = rule_map[u.target_rule_id].conclusion.prop_id
            edges.append({
                "from": u.critique_literal.prop_id,
                "to": conc,
                "type": "undercut",
                "sign": -1,
                "id": f"undercut:{u.target_rule_id}",
            })

    # 3. ConflictPair の依存: literal_a <-> literal_b (相互攻撃: 負の依存)
    for c in kb.conflicts:
        edges.append({
            "from": c.literal_a.prop_id,
            "to": c.literal_b.prop_id,
            "type": "conflict",
            "sign": -1,
            "id": f"conflict:{c.literal_a.prop_id}_{c.literal_b.prop_id}",
        })
        edges.append({
            "from": c.literal_b.prop_id,
            "to": c.literal_a.prop_id,
            "type": "conflict",
            "sign": -1,
            "id": f"conflict:{c.literal_b.prop_id}_{c.literal_a.prop_id}",
        })

    # 深さ優先探索による閉路検出 (DFS)
    adj: Dict[str, List[Tuple[str, int, str]]] = {p: [] for p in kb.propositions}
    for e in edges:
        adj[e["from"]].append((e["to"], e["sign"], e["type"]))

    cycles: List[Dict[str, Any]] = []
    visited: Set[str] = set()
    stack: List[Tuple[str, int]] = []

    def dfs(node: str):
        visited.add(node)
        for nxt, sgn, typ in adj.get(node, []):
            for idx, (ancestor, _) in enumerate(stack):
                if ancestor == nxt:
                    cycle_edges = stack[idx:] + [(nxt, sgn)]
                    edge_count = len(cycle_edges)
                    neg_edge_count = sum(1 for _, s in cycle_edges if s < 0)
                    parity = -1 if (neg_edge_count % 2 == 1) else +1

                    cycles.append({
                        "path": [x[0] for x in cycle_edges],
                        "edge_count": edge_count,
                        "is_odd_edge_count": (edge_count % 2 == 1),
                        "negative_edge_count": neg_edge_count,
                        "is_odd_negative_count": (neg_edge_count % 2 == 1),
                        "parity": parity,
                        "type": "odd_negative_parity_cycle" if parity < 0 else "even_or_positive_parity_cycle",
                    })
                    break
            else:
                if nxt not in visited:
                    stack.append((node, sgn))
                    dfs(nxt)
                    stack.pop()

    for p in kb.propositions:
        if p not in visited:
            stack.append((p, +1))
            dfs(p)
            stack.pop()

    has_odd_neg = any(c["parity"] < 0 for c in cycles)
    return {
        "edges_count": len(edges),
        "cycles_found": cycles,
        "has_cycles": len(cycles) > 0,
        "has_odd_negative_cycles": has_odd_neg,  # 後方互換性キー
        "has_odd_negative_parity_cycles": has_odd_neg,
    }
