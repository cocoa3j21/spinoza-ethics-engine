"""
幾何学および哲学体系シナリオ検証層 (Scenario Validator)
(engine/scenario_validator.py)

【目的】
圧縮推論規則が依存する固定背景公理（結合・順序・合同・アルキメデス公理等）が、
評価時に確実に満たされているかを受動的・能動的に検証する。

【仕様】
1. 背景条件を満たさない場合は BackgroundPreconditionError を送出。
   UNKNOWNへの置換や規則の黙認削除は行わない。
2. required_background_axioms を実行時の固定背景公理として一元処理。
3. 不足公理の自動補完や自動TRUE化は行わない。
4. 固定背景公理は「初期肯定支持が有効」「否定支持がない」「シナリオで不採用・撤回されていない」
   ことを要求（派生証明による充足は現版では対象外）。
5. 固定背景公理と探索候補公理の分離。重複時は BackgroundConfigError。
   探索候補が外されたことを固定背景不足と誤判定しない。
6. 不適切なシナリオを評価結果として集計しない。
"""
from typing import Dict, List, Optional, Set, Tuple, Any, Union
import json
import os

from engine.semantics import KnowledgeBase, Proposition, Literal, TruthStatus


class BackgroundPreconditionError(Exception):
    """固定背景公理の前提条件が満たされない場合に送出される例外"""
    pass


class BackgroundConfigError(Exception):
    """固定背景公理と探索候補公理の重複など、設定が不正な場合に送出される例外"""
    pass


class ScenarioPreconditionChecker:
    """
    固定背景公理の整合性およびシナリオ適用条件チェッカー
    """

    @staticmethod
    def extract_required_background_axioms(source: Union[str, Dict[str, Any]]) -> Dict[str, Set[str]]:
        """
        JSONファイルまたは辞書から各命題の required_background_axioms を抽出。
        (旧キー background_axioms も互換サポート)
        戻り値: {target_prop_id: {background_axiom_id, ...}}
        """
        if isinstance(source, str):
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = source

        req_map: Dict[str, Set[str]] = {}
        for node in data.get("nodes", []):
            prop_id = node.get("id")
            # required_background_axioms を最優先、旧 background_axioms もフォールバック
            bg = node.get("required_background_axioms") or node.get("background_axioms") or []
            if bg and prop_id:
                req_map[prop_id] = set(bg)
        return req_map

    @classmethod
    def validate_knowledge_base(
        cls,
        kb: KnowledgeBase,
        required_bg_axioms: Dict[str, Set[str]],
        candidate_axioms: Optional[Set[str]] = None,
    ) -> None:
        """
        KnowledgeBase 全体の固定背景公理の静的整合性を検証。
        - 探索候補との重複検査 (仕様5)
        - 定義・存在検査 (仕様4)
        - 公理タイプ・初期肯定支持検査 (仕様4)
        - 否定支持・対立検査 (仕様4)
        """
        candidate_set = set(candidate_axioms or set())

        all_bg_axioms: Set[str] = set()
        for target_id, bg_set in required_bg_axioms.items():
            # 1. 仕様5: 固定背景と探索候補の分離
            overlap = bg_set & candidate_set
            if overlap:
                raise BackgroundConfigError(
                    f"設定エラー: 命題 '{target_id}' の固定背景公理と探索候補公理に重複があります: {overlap}"
                )
            all_bg_axioms.update(bg_set)

        # 2. 仕様3 & 4: 各背景公理の定義・採用・初期支持の検証
        for axiom_id in all_bg_axioms:
            # (A) 定義検査: KBに存在するか
            if axiom_id not in kb.propositions:
                raise BackgroundPreconditionError(
                    f"背景前提エラー: 要求された固定背景公理 '{axiom_id}' が知識ベースに定義されていません。"
                )

            prop = kb.propositions[axiom_id]

            # (B) 採用検査: prop_type が 'axiom' で初期肯定支持を持つか
            # (派生証明による背景充足は非対応)
            if prop.prop_type != "axiom":
                raise BackgroundPreconditionError(
                    f"背景前提エラー: 固定背景公理 '{axiom_id}' は公理 (axiom) として採用されていません "
                    f"(現種別: '{prop.prop_type}')。派生証明による充足は対象外です。"
                )

            # (C) 否定支持・批判の検査: 初期状態で否定支持やUndercut/Conflictが存在しないか
            # 批判公理から直接反対支持を受けていないか
            for crit in kb.undercuts:
                if crit.critique_literal.prop_id == axiom_id:
                    raise BackgroundPreconditionError(
                        f"背景前提エラー: 固定背景公理 '{axiom_id}' は批判規則の標的になっています。"
                    )

            for conf in kb.conflicts:
                if (conf.literal_a.prop_id == axiom_id and not conf.literal_a.sign) or \
                   (conf.literal_b.prop_id == axiom_id and not conf.literal_b.sign):
                    raise BackgroundPreconditionError(
                        f"背景前提エラー: 固定背景公理 '{axiom_id}' に否定支持を与える対立ペアが存在します。"
                    )

    @classmethod
    def validate_scenario(
        cls,
        kb: KnowledgeBase,
        target_prop_id: str,
        active_premise_ids: Set[str],
        required_bg_axioms: Dict[str, Set[str]],
        candidate_axioms: Optional[Set[str]] = None,
    ) -> None:
        """
        特定シナリオ（特定の active_premise_ids を有効とする評価）の実効条件を検証。
        - 知識ベース全体の整合性を確認
        - target_prop_id の論理依存パス上で必要とされる固定背景公理が
          active_premise_ids に 100% 含まれているかを検査 (仕様4, 6)。
        - 固定背景公理が外されている場合は BackgroundPreconditionError。
        - 探索候補が外されている場合は正常 (仕様5)。
        """
        # まずKB全体の静的検証
        cls.validate_knowledge_base(kb, required_bg_axioms, candidate_axioms)

        # target_prop_id に直接または推移的に必要な背景公理を特定
        needed_bg_axioms = cls._collect_needed_background_axioms(kb, target_prop_id, required_bg_axioms)

        candidate_set = set(candidate_axioms or set())

        for bg_id in needed_bg_axioms:
            # 探索候補の除外は正常
            if bg_id in candidate_set:
                continue

            # 固定背景がシナリオから外されている（不採用・撤回）
            if bg_id not in active_premise_ids:
                raise BackgroundPreconditionError(
                    f"背景前提エラー: シナリオにおいて固定背景公理 '{bg_id}' が不採用・撤回されています。"
                    f"固定背景を満たさないシナリオでは命題 '{target_prop_id}' を評価できません。"
                )

    @classmethod
    def _collect_needed_background_axioms(
        cls,
        kb: KnowledgeBase,
        target_prop_id: str,
        required_bg_axioms: Dict[str, Set[str]],
    ) -> Set[str]:
        """target_prop_id およびその前提ノードが必要とするすべての背景公理を再帰的に収集"""
        needed: Set[str] = set()
        visited: Set[str] = set()

        def dfs(pid: str):
            if pid in visited:
                return
            visited.add(pid)
            if pid in required_bg_axioms:
                needed.update(required_bg_axioms[pid])
            # 推論規則の前提を再帰
            for r in kb.rules:
                if r.conclusion.prop_id == pid:
                    for prem in r.premises:
                        dfs(prem.prop_id)

        dfs(target_prop_id)
        return needed
