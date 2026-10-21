# 幾何学的推論エンジン 監査メモ (Audit Notes)

**作成日時**: 2026-10-21  
**担当**: 推論コア改修・形式意味論設計担当  
**対象**: `engine/core.py`, `engine/explorer.py`, `engine/comparative.py`, および `data/*.json`

---

## 1. 再現テストで確認した問題 (Confirmed Issues via Reproduction Tests)

以下の問題は、検証スクリプト（検証スクリプト）により実際の動作として再現・確認済みである。

### (1) 前件否定の誤謬 (Denying the antecedent / Fallacy of inverse)
* **現象**: 前提が `FALSE` である場合に、結論定理の真理値が `TruthValue.FALSE` に設定される。
* **コード箇所**: `engine/core.py:118-119`
  ```python
  elif any(v == TruthValue.FALSE for v in dep_values):
      node.value = TruthValue.FALSE
  ```
* **論理的誤謬**: 含意 $P \to Q$ において、前提 $P$ が偽（FALSE）であるとき、結論 $Q$ の真偽は不定（`UNKNOWN` / `UNPROVEN`）である。結論の否定 $\neg Q$ が証明されたわけではない。
* **実際の影響**: カント批判等によって前提が一つ崩壊した際、後続の定理群が「偽であることが証明された（否定支持）」としてドミノ倒しに FALSE 伝播し、過大な崩壊率（Descartes 0.0%など）を算出していた。

### (2) 演繹ループ中に後から成立した命題の衝突検出漏れ (Missed Post-Deduction Conflicts)
* **現象**: 初期状態で `UNKNOWN` であった命題が演繹ループ内で `TRUE` に遷移した際、それらが衝突ペアとして登録されていても `TruthValue.CONFLICT` に遷移せず、両者とも `TRUE` のまま残る。
* **コード箇所**: `engine/core.py:132-152`
  ```python
  def deduce_all(self):
      # 衝突チェックがループの前に1度だけ実行される
      for id_a, id_b, reason in self.conflicts:
          if val_a == TruthValue.TRUE and val_b == TruthValue.TRUE:
              self.nodes[id_a].value = TruthValue.CONFLICT
      # その後の演繹ループで真になった命題間の衝突は二度と検査されない
      while changed and iterations < 20: ...
  ```
* **実際の影響**: 定理同士の対立（例: スピノザの定理とカントの定理）を衝突ルールとして設定しても、演繹によって後から導出された場合は衝突が無視される。

### (3) 未定義ID依存によるクラッシュ (KeyError on Undefined ID)
* **現象**: `dependencies` に定義されていないノードIDが含まれている場合、事前検証なしに辞書参照して `KeyError` で即時クラッシュする。
* **コード箇所**: `engine/core.py:112`
  ```python
  dep_values = [self.evaluate_node(dep_id, visited.copy()) for dep_id in node.dependencies]
  ```
* **実際の影響**: データのタイポや外部シナリオからの断片的な入力に対して脆弱である。

### (4) 複数証明（別証明）の表現不能
* **現象**: `LogicNode` は単一の `dependencies: List[str]` しか持てず、論理積（AND）のみを前提としている。
* **実際の影響**: スピノザ『エチカ』の命題11のように複数の独立した証明（Demonstratio 1, 2, 3...）が存在する場合、一方の前提が遮断されても別の証明が生きていれば定理は成立するはずだが、現行モデルでは表現できず、単一の証明経路遮断で即座に不成立となる。

### (5) 破壊的状態変更によるシナリオ相互汚染
* **現象**: `ThoughtExplorer.what_if` や `diagnose_clash` において、`self.system.nodes` を直接変更し、相手システムの命題を同一辞書にロード・削除している。
* **実際の影響**: 処理途中の例外発生時や、並行して異なる仮定シミュレーションを実行した際に、基本モデルが破壊され相互汚染する。

---

## 2. コード上の設計リスク (Code Architectural & Design Risks)

### (1) 無根拠な20回反復打ち切り (`iterations < 20`)
* **リスク**: `engine/core.py:143` の `iterations < 20` は上限の根拠がなく、推論深さが20を超える正当なDAGであっても静かに打ち切られる。未収束（未完了）である事実も呼び出し元に通知されない。
* **対策**: ワークリストアルゴリズム（Worklist Algorithm）を採用し、状態変化があったノードの依存先のみをキューイングして不動点に到達させる。計算上限を設ける場合は「未完了 (incomplete)」フラグを明示的に返す。

### (2) 循環依存の未検証
* **リスク**: `evaluate_node` 内の `visited` チェックは単に無限再帰を止めているだけであり、論理的な循環依存（循環論証）を構文段階で拒否していない。循環がある場合、どの値になるかがノード走査順序に依存する非決定性を持つ。
* **対策**: モデル構築・検証時に `graphlib.TopologicalSorter` を用いて証明依存グラフが厳密なDAG（有向非巡回グラフ）であることを検証し、循環がある場合は明示的なエラーとする。

### (3) 真理値モデルの意味論的混同（汚染 vs 固有の矛盾）
* **リスク**: 「前提が矛盾しているために導出が無効化された（tainted/unsupported）」状態と、「その命題自身について肯定支持と否定支持の双方が証明された（固有の矛盾 self-conflict）」状態が、同一の `TruthValue.CONFLICT` で扱われている。
* **対策**: 命題の支持を positive / negative の2ビット（00=UNKNOWN, 10=TRUE, 01=FALSE, 11=CONFLICT）として明確に分離し、前提の矛盾は「規則の不発（不適用）」として扱う。

### (4) 探索における「包含極小」と「要素数最小」の未区別
* **リスク**: `engine/explorer.py:84` の `find_key_assumptions_for_frontier` は、単に組み合わせサイズ $r$ が最小のもの（cardinality-minimal）を求めているだけであり、部分集合としての包含極小（subset-minimal）との区別がない。また、目標命題自身を仮定候補から除外するガードがない。
* **対策**: 両者の定義を分離し、目標命題そのものの仮定を初期設定で禁止する。

---

## 3. データ不足・哲学的モデリング上で判断できない事項 (Data Limitations & Philosophical Modeling Gaps)

### (1) カント批判の過剰単純化とカテゴリ・ミステイク
* **現状のデータ**: `kant_critique.json` の公理とスピノザ・デカルトの命題が「命題対立（AとBは両立しない）」としてハードコードされている。
* **哲学的問題**:
  * カントの批判（例: 存在は実在的述語ではない、現象と物自体の絶対的分離）は、「神は実在しない」という命題的主張ではない。
  * それは「概念の分析から客観的実在性を導出する推論規則の無効化（Undercutting Defeater）」および「純粋理性の超越的適用に対する認識的制約」である。
  * これを単なる排他衝突（CONFLICT）として扱うと、カントが無神論的主張を行ったかのような歪曲を生む。
* **判断保留事項**: 各批判がどの推論規則（Rule）を具体的に無効化するのかについて、原典の文脈（『純粋理性批判』先験的弁証論「純粋理性の二律背反」「神の現存在の証明批判」）に即した厳密な規則レベルの対応付けが必要。

### (2) スピノザ『エチカ』第1部の証明構造の欠落
* **現状のデータ**:
  * 命題5（同属性実体単一性）から命題14（実体の神唯一性）への導出において、属性と実体の厳密な区別、様態の差異の扱いが粗い。
  * 命題11（神の必然的実在）には原典において複数の別証明（代数式のような別論証、充足理由律からの論証、無限の能力論証）が存在するが、データには単一の依存先しか登録されていない。
* **判断保留事項**: 原典の別証明（Demonstratio aliter）を別個の証明規則として登録し、どの証明がカント批判に耐え、どの証明が無効化されるのかを原典に即して精緻化する必要がある。

### (3) デカルトとライプニッツの存在証明および認識的主張の欠落
* **デカルト**:
  * 第五省察の存在論的証明（`DESC_PROP_2`）と第三省察の観念の原因論証（`DESC_PROP_1`）はあるが、自己の存続（維持・継続的創造）からの証明や、明晰判明な知覚の根拠づけの循環論争（デカルトの円環）に関する論理構造が未モデル化。
* **ライプニッツ**:
  * モナドロジーの3命題のみであり、神の存在証明（可能的存在から必然的存在への推論、永遠の真理の根拠としての神）が欠落しており、予定調和（`LEIB_PROP_2`）の前提が充足理由律と最善世界選択公理に直結しすぎている。

### (4) 属性と様態の論理的階層の未分離
* **哲学的問題**:
  * スピノザにおいて「思惟（Cogitatio）」と「延長（Extensio）」は神の属性であり、個々の「心（Mens）」や「身体（Corpus）」はその属性の有限な様態（Modus）である。
  * デカルトにおいては「心」と「身体」はそれぞれ思惟と延長を主属性とする不完全な被造実体である。
  * 現状の論理式テキスト（`logical_form`）はこの存在論的階層（実体・属性・様態）を厳密に型付けしておらず、単なる文字列コメントに留まっている。

### (5) 原典位置・典拠の保証
* **方針**: 原典位置（Gebhardt版ページ、章節節番号、Latin/French/German表記）を明記し、確定的なものと暫定的（provisional）な解釈メモを明確に峻別する。推論や引用文を創作してはならない。

---

## 4. 第二次監査メモ (Second Audit Notes)

### (1) 最小モデルによる矛盾前提遮断の不整合検証
* **モデル**: 初期支持 $+P, +S$、規則 $r1: +P \to +Q$, $r2: +S \to +R$, $r3: +R \to -P$。
* **確認事実**:
  * 改修前は、ワークリストで $P$ が先に処理された際に $r1$ が先行発火し、後から $R \to -P$ により $P$ が `CONFLICT` になっても $r1$ の支持が撤回されず、汚染前提依存の $Q$ が `TRUE` として残存していた。
  * `Evaluator` に前提汚染時の発火規則撤回機構（Truth Maintenance）を組み込み、最終的に $P$ が `CONFLICT` の場合、$r1$ の支持が正しく破棄され、$Q$ が `UNKNOWN`（別証明 $r4$ があれば $r4$ のみで `TRUE`）に正しく遷移することを確認。

### (2) 評価方式の厳密な定義
* 現実装は単純な「単調累積」ではなく、**「正当化根拠に基づく整合的真理維持意味論 (Justification-consistent Truth Maintenance Semantics)」** である。
* タルスキの「最小不動点」は純粋な単調写像においてのみ無条件に成立するが、非単調な前提矛盾遮断（`require_untainted_premises=True`）を含む本システムでは、有限DAG制約と正当化撤回により、決定論的かつ一意な整合不動点に収束する。

### (3) ConflictPairの性質と循環性
* `ConflictPair` は診断専用ではなく、相互に否定支持を生成する。
* 推論規則DAGとは異なり $A \leftrightarrow \neg B$ という循環的攻撃関係を持つが、否定支持付与に伴う撤回処理がワークリスト上で整合的に連鎖することを確認。

### (4) 最小前提探索における単調性の仮定
* `engine/search.py` の `is_subsumed` による上位集合枝刈りは、「包含極小解」を求める目的に関しては正当（$S_1$ で成立するなら $S_2 \supset S_1$ は極小解の定義を満たさないため）。
* ただし、非単調な前提系において成立解そのものを判定する際には、下位集合の成立判定が偽陽性でないこと（真理維持の完全性）が前提となる。

### (5) 哲学的説明の修正
* デカルトの第三省察（神の観念の原因論証）と第六省察（物質的物体の実在証明）を峻別。
* スピノザ命題1〜6の残存を「普遍的耐性」と説明せず、カント批判のモデル化範囲（命題7無効化）の局所的帰結として厳密に記述。
* ライプニッツにおいて批判対象としなかった命題（単子の単純性、窓なきモナド、充足理由律、現象性）の選定理由と、カント『反省概念の多義性』等における実質的批判の未モデル化に関する留保を明記。

---

## 5. 使用底本・出典およびラテン語テキスト校訂記録 (Philological Sources & Collation)

### (1) 参照底本・出典 (Editions & Digital Facsimiles)
1. **1677年初版 (Opera Posthuma)**:
   - 書誌: *B. d. S. Opera Posthuma, quorum series post Praefationem exhibetur.* [Amsterdam: Jan Rieuwertsz], 1677.
   - 参照デジタルファクシミリ: Herzog August Bibliothek Wolfenbüttel 所蔵本デジタルアーカイブ、および Google Books 収載の初版スキャン。
2. **Gebhardt 学術標準版 (Gebhardt Edition)**:
   - 書誌: *Spinoza Opera*, Im Auftrag der Heidelberger Akademie der Wissenschaften hrsg. von Carl Gebhardt. Heidelberg: Carl Winters Universitätsbuchhandlung, 1925, 4 Bände (Ethica は Band II 所収).
3. **ラテン語電子テキスト対照底本**:
   - The Latin Library および Wikisource (Spinoza, *Ethica in linguam latinam*)。Gebhardt版および初版スキャンとの照合底本として利用。

### (2) AI記憶生成に伴う初期ラテン語誤記の校訂記録
AIが記憶からラテン語テキストを出力した初期データにおいて、以下の誤記・語順転倒が確認され、原本と対照して訂正された：
* **定義3 (`DEF_3`) の語写**:
  - AI初期出力: `cujus conceptus non eget conceptu alterius rei`（*non eget*）
  - 原本確定テキスト: `cujus conceptus non indiget conceptu alterius rei`（*non indiget* / Gebhardt II, S. 45; OP 1677, p. 1）
  - 修正: スピノザの実際の語彙用法である *non indiget* に訂正。
* **命題2 (`PROP_2`) の語順転倒**:
  - AI初期出力: `Duae substantiae diversas habentes attributa, nihil inter se commune habent.`
  - 原本確定テキスト: `Duae substantiae, diversa attributa habentes, nihil inter se commune habent.`（Gebhardt II, S. 48; OP 1677, p. 3）
  - 修正: 格変化（*diversa* 中性複数対格）および原本の語順に訂正。
* **命題5 (`PROP_5`) の前提配線訂正**:
  - 原典本文（Gebhardt II, S. 48）の「*Demonstr. Si darentur plures distinctae, deberent inter se distingui, vel ex diversitate attributorum (per Prop. 4), vel ex diversitate affectionum (per Prop. 1). Si tantum ex diversitate attributorum, dabitur ergo tantum una ejusdem attributi (per Ax. 6)...*」に対照し、初期データに混入していた `DEF_6` を除外し、本文が明示引用する `PROP_4, PROP_1, DEF_3, AX_6` に完全準拠させて再配線。
