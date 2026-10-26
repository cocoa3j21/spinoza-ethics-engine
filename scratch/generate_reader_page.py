"""
読者向けページ生成スクリプト (Reader Page Generator)

- 既存データと推論エンジン (Evaluator / IndependentBruteForceVerifier) から動的に計算。
- スマホ幅 (640px以下) で各行を縦に積んだカード表示 (見出し付き、横スクロールなし)。
- 批判シナリオ表で「データの状態」と「解釈の状態」を別バッジ化。
- 「充足理由律のみ遮断」の解釈状態を「AI記載、未照合」に修正。
- 「AI記載、未照合」バッジに目につく橙の枠線・文字色を適用。
- 注記(※)の文字の大きさ・コントラストを向上。
- 先行取り組みリンク・書誌情報・本プロジェクト付番注記を配置。
"""
import os
import json
import sys

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ENGINE_DIR not in sys.path:
    sys.path.append(ENGINE_DIR)

from engine.semantics import KnowledgeBase, Proposition, InferenceRule, Literal, Evaluator, TruthStatus
from engine.benchmark_core import load_system_as_kb
from tests.test_independent_bruteforce_verification import IndependentBruteForceVerifier

ID_LABELS = {
    # デカルト
    "DES_PROP_1": "神の本性からの認知",
    "DES_PROP_2": "神の観念からの後天的証明",
    "DES_PROP_3": "自己の存在からの神の証明",
    "DES_AX_1": "因果律",
    "DES_AX_2": "自己保存",
    "DES_AX_3": "無からの保存不可",
    "DES_AX_4": "持続と保存",
    "DES_AX_5": "観念の客観的実在性",
    "DES_AX_6": "原因の卓越性",
    "DES_AX_7": "原因の完全性",
    "DES_AX_8": "原因の力",
    "DES_AX_9": "第一原因",
    "DES_AX_10": "必然的存在公理",
    "DES_DEF_2": "観念の対象",
    "DES_DEF_8": "無限実体",
    "DES_DEF_9": "神の定義",
    # アンセルムス
    "ANS1_P1": "神の定義",
    "ANS1_P2": "心内存在",
    "ANS1_P3": "実在の優位性",
    "ANS2_P1": "神の定義",
    "ANS2_P2": "必然的存在",
    "ANS2_P6": "非存在思考不可能性",
    # スピノザ
    "DEF_1": "自己原因",
    "DEF_3": "実体",
    "DEF_4": "属性",
    "DEF_5": "変状",
    "DEF_6": "神の定義",
    "AX_1": "実在の帰属",
    "AX_4": "原因の認識",
    "AX_5": "共通性の欠如",
    "AX_6": "真の観念",
    "AX_7": "非存在の思考",
    "SPIN_AX_RATIO": "充足理由律",
}


def format_premise(pid):
    label = ID_LABELS.get(pid)
    if label:
        return f'<span class="node-code">{pid}</span><small>({label})</small>'
    return f'<span class="node-code">{pid}</span>'


def generate_reader_html():
    print("=== 読者向けページ HTML 生成開始 ===")

    des_path = os.path.join(ENGINE_DIR, "data", "descartes_second_replies_geometric.json")
    ans_path = os.path.join(ENGINE_DIR, "data", "anselm_proslogion_iep.json")
    spin_path = os.path.join(ENGINE_DIR, "data", "spinoza_ethics_part1_split_prop6.json")

    verif_des = IndependentBruteForceVerifier(des_path)
    verif_ans = IndependentBruteForceVerifier(ans_path)

    # 1. 基本構造の計算 (デカルト・アンセルムス)
    des_p1_cnt, des_p1_size, des_p1_grounds = verif_des.compute_minimal_support_grounds("DES_PROP_1")
    des_p1_cuts = sorted(verif_des.compute_single_cuts("DES_PROP_1"))

    des_p2_cnt, des_p2_size, des_p2_grounds = verif_des.compute_minimal_support_grounds("DES_PROP_2")
    des_p2_cuts = sorted(verif_des.compute_single_cuts("DES_PROP_2"))

    des_p3_cnt, des_p3_size, des_p3_grounds = verif_des.compute_minimal_support_grounds("DES_PROP_3")
    des_p3_cuts = sorted(verif_des.compute_single_cuts("DES_PROP_3"))

    ans_1_cnt, ans_1_size, ans_1_grounds = verif_ans.compute_minimal_support_grounds("ANS1_C")
    ans_1_cuts = sorted(verif_ans.compute_single_cuts("ANS1_C"))

    ans_2_cnt, ans_2_size, ans_2_grounds = verif_ans.compute_minimal_support_grounds("ANS2_C")
    ans_2_cuts = sorted(verif_ans.compute_single_cuts("ANS2_C"))

    # スピノザの保存済み確定計算値のロード
    spin_findings_path = os.path.join(ENGINE_DIR, "web", "spinoza_findings_v02.json")
    with open(spin_findings_path, "r", encoding="utf-8") as f:
        spin_findings = json.load(f)
    models_info = spin_findings.get("data", {}).get("models") or spin_findings["models"]

    # HTML 構築
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>神の存在をめぐる論証を、部品に分けて眺める | 幾何学的哲学推論エンジン</title>
  <style>
    :root {{
      --bg-color: #0f141c;
      --card-bg: #161e2e;
      --card-border: #233044;
      --text-main: #e2e8f0;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --badge-verified-bg: rgba(56, 189, 248, 0.15);
      --badge-verified-text: #38bdf8;
      --badge-ai-bg: rgba(129, 140, 248, 0.15);
      --badge-ai-text: #818cf8;
      /* 未照合バッジ: 目につく橙の枠線と文字色 */
      --badge-unverified-bg: rgba(245, 158, 11, 0.15);
      --badge-unverified-text: #fbbf24;
      --badge-unverified-border: #f59e0b;
      --table-header-bg: #1e293b;
      --table-row-hover: #1e293b;
      --table-border: #334155;
      /* 中立な色調: 勝敗・優劣（赤/緑）を排除し、落ち着いたインディゴとスレートで表現 */
      --status-survive: #818cf8;
      --status-loss: #94a3b8;
      --status-survive-bg: rgba(129, 140, 248, 0.12);
      --status-loss-bg: rgba(148, 163, 184, 0.12);
    }}

    [data-theme="light"] {{
      --bg-color: #f8fafc;
      --card-bg: #ffffff;
      --card-border: #e2e8f0;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --accent: #0284c7;
      --badge-verified-bg: #e0f2fe;
      --badge-verified-text: #0369a1;
      --badge-ai-bg: #e0e7ff;
      --badge-ai-text: #4338ca;
      --badge-unverified-bg: #fef3c7;
      --badge-unverified-text: #b45309;
      --badge-unverified-border: #d97706;
      --table-header-bg: #f1f5f9;
      --table-row-hover: #f8fafc;
      --table-border: #cbd5e1;
      --status-survive: #4338ca;
      --status-loss: #64748b;
      --status-survive-bg: #eef2ff;
      --status-loss-bg: #f1f5f9;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: var(--bg-color);
      color: var(--text-main);
      line-height: 1.7;
      padding: 24px;
      transition: background-color 0.2s ease, color 0.2s ease;
    }}

    .container {{
      max-width: 1000px;
      margin: 0 auto;
    }}

    header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 16px;
      gap: 16px;
    }}

    .header-title h1 {{
      font-size: 1.65rem;
      font-weight: 700;
      color: var(--text-main);
      line-height: 1.35;
    }}

    .theme-toggle-btn {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text-main);
      padding: 8px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.88rem;
      display: flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
      flex-shrink: 0;
    }}

    section {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 24px;
      margin-bottom: 24px;
    }}

    h2 {{
      font-size: 1.25rem;
      font-weight: 600;
      margin-bottom: 14px;
      color: var(--text-main);
      border-left: 4px solid var(--accent);
      padding-left: 10px;
    }}

    h3 {{
      font-size: 1.02rem;
      font-weight: 600;
      margin: 20px 0 10px 0;
      color: var(--text-main);
    }}

    p, ul, ol {{
      margin-bottom: 12px;
      font-size: 0.95rem;
    }}

    ul, ol {{
      padding-left: 20px;
    }}

    li {{
      margin-bottom: 8px;
    }}

    a {{
      color: var(--accent);
      text-decoration: underline;
    }}

    a:hover {{
      text-decoration: none;
    }}

    .table-responsive {{
      overflow-x: auto;
      margin: 16px 0;
      -webkit-overflow-scrolling: touch;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
      text-align: left;
    }}

    th, td {{
      padding: 10px 12px;
      border: 1px solid var(--table-border);
    }}

    th {{
      background-color: var(--table-header-bg);
      font-weight: 600;
      color: var(--text-main);
      white-space: nowrap;
    }}

    tr:hover td {{
      background-color: var(--table-row-hover);
    }}

    .badge {{
      display: inline-block;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 0.74rem;
      font-weight: 600;
      white-space: nowrap;
    }}

    .badge-verified {{
      background-color: var(--badge-verified-bg);
      color: var(--badge-verified-text);
      border: 1px solid var(--badge-verified-text);
    }}

    .badge-ai {{
      background-color: var(--badge-ai-bg);
      color: var(--badge-ai-text);
      border: 1px solid var(--badge-ai-text);
    }}

    .badge-unverified {{
      background-color: var(--badge-unverified-bg);
      color: var(--badge-unverified-text);
      border: 1px solid var(--badge-unverified-border);
      font-weight: 600;
    }}

    .status-badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 0.8rem;
      font-weight: 600;
      white-space: nowrap;
    }}

    .status-survive {{
      background-color: var(--status-survive-bg);
      color: var(--status-survive);
      border: 1px solid var(--status-survive);
    }}

    .status-loss {{
      background-color: var(--status-loss-bg);
      color: var(--status-loss);
      border: 1px solid var(--status-loss);
    }}

    .node-code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8rem;
      background: var(--card-border);
      padding: 2px 5px;
      border-radius: 4px;
    }}

    .notice-box {{
      background: var(--table-header-bg);
      border-left: 4px solid var(--accent);
      padding: 12px 16px;
      border-radius: 4px;
      margin: 14px 0;
      font-size: 0.92rem;
      color: var(--text-main);
    }}

    .table-note {{
      font-size: 0.92rem;
      color: var(--text-main);
      opacity: 0.95;
      margin-top: 8px;
      line-height: 1.65;
    }}

    /* スマホ幅 (640px以下) のカード化レイアウト */
    @media (max-width: 640px) {{
      body {{
        padding: 12px;
      }}
      .container {{
        width: 100%;
        max-width: 100%;
      }}
      section {{
        padding: 16px 12px;
      }}
      .table-responsive {{
        overflow-x: visible;
        margin: 12px 0;
      }}
      .card-table,
      .card-table thead,
      .card-table tbody,
      .card-table th,
      .card-table td,
      .card-table tr {{
        display: block;
        width: 100%;
      }}
      .card-table thead {{
        display: none;
      }}
      .card-table tr {{
        margin-bottom: 16px;
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 8px;
        padding: 12px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
      }}
      .card-table td {{
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        padding: 8px 0;
        border: none;
        border-bottom: 1px solid var(--table-border);
        font-size: 0.9rem;
        gap: 4px;
        word-break: break-word;
      }}
      .card-table td:last-child {{
        border-bottom: none;
      }}
      .card-table td::before {{
        content: attr(data-label);
        font-weight: 700;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: var(--accent);
        margin-bottom: 2px;
      }}
    }}

    footer {{
      text-align: center;
      font-size: 0.82rem;
      color: var(--text-muted);
      margin-top: 36px;
      padding-top: 18px;
      border-top: 1px solid var(--card-border);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-title">
        <h1>神の存在をめぐる論証を、部品に分けて眺める</h1>
      </div>
      <button class="theme-toggle-btn" id="themeToggleBtn" onclick="toggleTheme()" aria-label="テーマ切り替え">
        <span id="themeIcon">☀️</span>
        <span id="themeText">Light Mode</span>
      </button>
    </header>

    <!-- セクション1: このページについて (免責事項・目的) -->
    <section>
      <h2>このページについて</h2>
      <ul>
        <li><strong>どの宗教・宗派の神であるかを決めるページではありません。神の存在を証明も否定もしません。</strong></li>
        <li>哲学の本にある論証を、「前提」と「結論」の部品に分けます。そして、「この前提が使えなくなったら、結論はどうなるか」を計算して示します。</li>
        <li>計算の対象は、筆者が本文から作ったデータの範囲です。データは、AIの支援を受けて作成しました。人の確認が済んでいない部分は、各行に状態を表示しています。</li>
      </ul>
    </section>

    <!-- セクション2: 3つの論証 -->
    <section>
      <h2>3つの論証</h2>
      <ul>
        <li><strong>アンセルムス (11世紀)</strong>:<br>
          「それより大きいものが考えられない存在」という定義から、神は存在すると導く論証です。前提は3つ (定義、心の中にあること、存在は完全性であること) で、道は一本です。</li>
        <li><strong>デカルト (17世紀)</strong>:<br>
          神の本性を考えるだけで存在を導く道 (命題1) と、自分の中にある神の観念や、自分自身の存在から導く道 (命題2・3) があります。</li>
        <li><strong>スピノザ (17世紀)</strong>:<br>
          命題11を、複数の道で証明しています。登録した範囲では、定義1 (自己原因) を使う道と、充足理由律を使う道があります。</li>
      </ul>

      <h3>論証構造の基本対照表 (計算結果)</h3>
      <div class="notice-box">
        <strong>※ 前提の数に関する注意（粒度の相違）:</strong><br>
        ノード（公理・定義・前提）の分解粒度は体系ごとに異なり、原典の記述密度や形式化の粒度に依存します。したがって、<strong>前提の数（根拠サイズ）の大小を論証の優劣・完成度の順位として解釈することはできません。</strong>
      </div>

      <div class="table-responsive">
        <table class="card-table">
          <thead>
            <tr>
              <th>体系</th>
              <th>対象結論 (目標命題)</th>
              <th>状態</th>
              <th>最小根拠の組の数</th>
              <th>最小根拠の大きさ</th>
              <th>単体遮断の前提 (1つ止めると切れる前提)</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td data-label="体系"><strong>デカルト</strong></td>
              <td data-label="対象結論 (目標命題)">命題1 (<code>DES_PROP_1</code>)<br><small>神の本性からの認知</small></td>
              <td data-label="状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="最小根拠の組の数" style="text-align: center;">{des_p1_cnt}組</td>
              <td data-label="最小根拠の大きさ" style="text-align: center;">{des_p1_size}件</td>
              <td data-label="単体遮断の前提">{", ".join(format_premise(p) for p in des_p1_cuts)} (計{len(des_p1_cuts)}件)</td>
            </tr>
            <tr>
              <td data-label="体系"><strong>デカルト</strong></td>
              <td data-label="対象結論 (目標命題)">命題2 (<code>DES_PROP_2</code>)<br><small>神の観念からの後天的証明</small></td>
              <td data-label="状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="最小根拠の組の数" style="text-align: center;">{des_p2_cnt}組</td>
              <td data-label="最小根拠の大きさ" style="text-align: center;">{des_p2_size}件</td>
              <td data-label="単体遮断の前提">{", ".join(format_premise(p) for p in des_p2_cuts)} (計{len(des_p2_cuts)}件)</td>
            </tr>
            <tr>
              <td data-label="体系"><strong>デカルト</strong></td>
              <td data-label="対象結論 (目標命題)">命題3 (<code>DES_PROP_3</code>)<br><small>自己の存在からの神の証明</small></td>
              <td data-label="状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="最小根拠の組の数" style="text-align: center;">{des_p3_cnt}組</td>
              <td data-label="最小根拠の大きさ" style="text-align: center;">{des_p3_size}件</td>
              <td data-label="単体遮断の前提">{", ".join(format_premise(p) for p in des_p3_cuts)} (計{len(des_p3_cuts)}件)</td>
            </tr>
            <tr>
              <td data-label="体系"><strong>アンセルムス</strong></td>
              <td data-label="対象結論 (目標命題)">論証1 (<code>ANS1_C</code>)<br><small>神の現実的存在 (第2章)</small></td>
              <td data-label="状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="最小根拠の組の数" style="text-align: center;">{ans_1_cnt}組</td>
              <td data-label="最小根拠の大きさ" style="text-align: center;">{ans_1_size}件</td>
              <td data-label="単体遮断の前提">{", ".join(format_premise(p) for p in ans_1_cuts)} (計{len(ans_1_cuts)}件)</td>
            </tr>
            <tr>
              <td data-label="体系"><strong>アンセルムス</strong></td>
              <td data-label="対象結論 (目標命題)">論証2 (<code>ANS2_C</code>)<br><small>神の必然的存在 (第3章)</small></td>
              <td data-label="状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="最小根拠の組の数" style="text-align: center;">{ans_2_cnt}組</td>
              <td data-label="最小根拠の大きさ" style="text-align: center;">{ans_2_size}件</td>
              <td data-label="単体遮断の前提">{", ".join(format_premise(p) for p in ans_2_cuts)} (計{len(ans_2_cuts)}件)</td>
            </tr>
            <tr>
              <td data-label="体系"><strong>スピノザ</strong></td>
              <td data-label="対象結論 (目標命題)">命題11 モデルA<br><small>第1証明のみ</small></td>
              <td data-label="状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="最小根拠の組の数" style="text-align: center;">{len(models_info["model_a"]["grounds"])}組</td>
              <td data-label="最小根拠の大きさ" style="text-align: center;">{len(models_info["model_a"]["grounds"][0])}件</td>
              <td data-label="単体遮断の前提">全{len(models_info["model_a"]["premise_cuts"])}件が単体遮断</td>
            </tr>
            <tr>
              <td data-label="体系"><strong>スピノザ</strong></td>
              <td data-label="対象結論 (目標命題)">命題11 モデルB<br><small>別証明1追加 / 設定a</small></td>
              <td data-label="状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="最小根拠の組の数" style="text-align: center;">{len(models_info["model_b"]["grounds"])}組</td>
              <td data-label="最小根拠の大きさ" style="text-align: center;">5件</td>
              <td data-label="単体遮断の前提">{", ".join(format_premise(p) for p in models_info["model_b"]["common_premises"])} (計{len(models_info["model_b"]["common_premises"])}件)</td>
            </tr>
            <tr>
              <td data-label="体系"><strong>スピノザ</strong></td>
              <td data-label="対象結論 (目標命題)">命題11 モデルC1<br><small>系の別証明追加</small></td>
              <td data-label="状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="最小根拠の組の数" style="text-align: center;">{len(models_info["model_c1"]["grounds"])}組</td>
              <td data-label="最小根拠の大きさ" style="text-align: center;">{len(models_info["model_c1"]["grounds"][0])}件</td>
              <td data-label="単体遮断の前提">{", ".join(format_premise(p) for p in models_info["model_c1"]["common_premises"])} (計{len(models_info["model_c1"]["common_premises"])}件)</td>
            </tr>
            <tr>
              <td data-label="体系"><strong>スピノザ</strong></td>
              <td data-label="対象結論 (目標命題)">命題11 モデルC2<br><small>全別証明統合 / 設定a</small></td>
              <td data-label="状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="最小根拠の組の数" style="text-align: center;">{len(models_info["model_c2"]["grounds"])}組</td>
              <td data-label="最小根拠の大きさ" style="text-align: center;">5件</td>
              <td data-label="単体遮断の前提">{", ".join(format_premise(p) for p in models_info["model_c2"]["common_premises"])} (計{len(models_info["model_c2"]["common_premises"])}件)</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="table-note">
        ※ <strong>括弧内の数字について</strong>: 「計○件」などの数字は、その結論を単独で遮断できる必須前提の総数を示します。<br>
        ※ <strong>アンセルムスの前提内訳について</strong>: 論証1の ANS1_P5 および論証2の ANS2_P4（「神より大きいものは想像できない」）は、神の定義 P1 に依存して導かれる命題（導出）として整理されているため、基礎前提（無前提ノード）は各論証とも3件ずつとなります。<br>
        ※ <strong>スピノザのモデルと設定について</strong>: モデルAは単一証明（第1証明のみ）、モデルBは命題11の別証明1追加、モデルC1は命題6の系の別証明追加、モデルC2は全別証明を統合したモデルです。設定(a)〜(d)は別証明1における命題7や命題3の補完に関する解釈の違いを表します。
      </p>

      <h3>スピノザ『エチカ』第1部 命題11における証明の呼称対応表</h3>
      <div class="table-responsive">
        <table class="card-table">
          <thead>
            <tr>
              <th>本プロジェクトでの呼称</th>
              <th>原典ラテン語表記</th>
              <th>主な論拠・特徴</th>
              <th>モデル化の状態</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td data-label="本プロジェクト呼称"><strong>第1証明</strong></td>
              <td data-label="原典ラテン語表記"><em>Demonstratio</em></td>
              <td data-label="主な論拠・特徴">自己原因 (<code>DEF_1</code>) および命題7 (実体の本性には存在が属する) を経由する本証明</td>
              <td data-label="モデル化の状態"><span class="badge badge-verified">登録済み (全モデル)</span></td>
            </tr>
            <tr>
              <td data-label="本プロジェクト呼称"><strong>別証明1</strong></td>
              <td data-label="原典ラテン語表記"><em>Aliter</em> [1]</td>
              <td data-label="主な論拠・特徴">充足理由律 (<code>SPIN_AX_RATIO</code>: 存在・非存在の理由原理) に基づく背理法論証</td>
              <td data-label="モデル化の状態"><span class="badge badge-verified">登録済み (モデルB, C2)</span></td>
            </tr>
            <tr>
              <td data-label="本プロジェクト呼称"><strong>第3証明</strong></td>
              <td data-label="原典ラテン語表記"><em>Aliter</em> [2]</td>
              <td data-label="主な論拠・特徴">力・能力による論証 (<em>Posse non existere impotentia est...</em> / 存在しうることは力である)</td>
              <td data-label="モデル化の状態"><span class="badge badge-unverified">未登録 (今後の拡張候補)</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="table-note">
        ※ 証明の数え方は、研究者によって異なります(4つと数える研究もあります)。<br>
        ※ 原典ラテン語表記の「Aliter [1]」「Aliter [2]」における括弧の数字 [1], [2] は、原典本文にはなく、区別のために本プロジェクトが付番したものです。
      </p>
    </section>

    <!-- セクション3: 批判を当てるとどうなるか -->
    <section>
      <h2>批判を当てるとどうなるか</h2>
      <p>
        カント (「存在は、ものの性質の一つではない」) の批判を、「批判が向けられる前提」を止める操作として当てます。
      </p>
      <ul>
        <li><strong>アンセルムス</strong>: 結論までの道が切れます。</li>
        <li><strong>デカルト</strong>: 命題1の道が切れます。命題2・3の道は残ります。</li>
        <li><strong>スピノザ</strong>: 定義1だけに批判が向けられる場合、設定によって道が残ります。充足理由律だけの場合も、道が残ります。両方に批判が向けられると、登録した道は残りません。</li>
      </ul>

      <h3>カント批判および各遮断シナリオの計算結果一覧</h3>
      <div class="table-responsive">
        <table class="card-table">
          <thead>
            <tr>
              <th>対象の体系</th>
              <th>遮断する前提</th>
              <th>データの状態</th>
              <th>解釈の状態</th>
              <th>結論への導出経路の状態</th>
              <th>詳細と構造上の理由</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td data-label="対象の体系"><strong>アンセルムス</strong><br>論証1 (<code>ANS1_C</code>)</td>
              <td data-label="遮断する前提">実在の優位性前提<br>(<code>ANS1_P3</code>)</td>
              <td data-label="データの状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="解釈の状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="結論への導出経路"><span class="status-badge status-loss">道が切れる (支持喪失)</span></td>
              <td data-label="詳細と構造上の理由">一本道のため、実在優位性の前提を止めると結論への道が切れます。</td>
            </tr>
            <tr>
              <td data-label="対象の体系"><strong>デカルト</strong><br>命題1 (<code>DES_PROP_1</code>)</td>
              <td data-label="遮断する前提">必然的存在公理<br>(<code>DES_AX_10</code>)</td>
              <td data-label="データの状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="解釈の状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="結論への導出経路"><span class="status-badge status-loss">道が切れる (支持喪失)</span></td>
              <td data-label="詳細と構造上の理由">命題1は必然的存在公理に一本道で依存するため切れます。</td>
            </tr>
            <tr>
              <td data-label="対象の体系"><strong>デカルト</strong><br>命題2・3 (後天的証明)</td>
              <td data-label="遮断する前提">必然的存在公理<br>(<code>DES_AX_10</code>)</td>
              <td data-label="データの状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="解釈の状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="結論への導出経路"><span class="status-badge status-survive">道が残る (維持)</span></td>
              <td data-label="詳細と構造上の理由">命題2・3は必然的存在公理に依存しないため道が残ります (※原因や保存への別批判は未適用)。</td>
            </tr>
            <tr>
              <td data-label="対象の体系"><strong>スピノザ</strong> 命題11<br>定義1 (<code>DEF_1</code>) のみ遮断</td>
              <td data-label="遮断する前提">自己原因の定義<br>(<code>DEF_1</code>)</td>
              <td data-label="データの状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="解釈の状態"><span class="badge badge-unverified">AI記載、未照合</span></td>
              <td data-label="結論への導出経路">
                モデルA, C1: <span class="status-badge status-loss">道が切れる</span><br>
                モデルB, C2 (設定a, c): <span class="status-badge status-survive">道が残る</span><br>
                モデルB, C2 (設定b, d): <span class="status-badge status-loss">道が切れる</span>
              </td>
              <td data-label="詳細と構造上の理由">別証明1に命題7を含めない設定(a)(c)では迂回経路が残ります。含める設定(b)(d)では切れます。<strong>どちらを採るかは解釈によります。</strong></td>
            </tr>
            <tr>
              <td data-label="対象の体系"><strong>スピノザ</strong> 命題11<br>充足理由律のみ遮断</td>
              <td data-label="遮断する前提">充足理由律<br>(<code>SPIN_AX_RATIO</code>)</td>
              <td data-label="データの状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="解釈の状態"><span class="badge badge-unverified">AI記載、未照合</span></td>
              <td data-label="結論への導出経路"><span class="status-badge status-survive">全モデルで道が残る (維持)</span></td>
              <td data-label="詳細と構造上の理由">第1証明は充足理由律に依存しないため、どのモデル・設定でも第1証明経由で道が残ります。</td>
            </tr>
            <tr>
              <td data-label="対象の体系"><strong>スピノザ</strong> 命題11<br>DEF_1 と 充足理由律の両方遮断</td>
              <td data-label="遮断する前提">自己原因 (<code>DEF_1</code>)<br>＋充足理由律 (<code>SPIN_AX_RATIO</code>)</td>
              <td data-label="データの状態"><span class="badge badge-ai">AI照合済み(人の確認前)</span></td>
              <td data-label="解釈の状態"><span class="badge badge-unverified">AI記載、未照合</span></td>
              <td data-label="結論への導出経路"><span class="status-badge status-loss">登録した道はすべて切れる</span></td>
              <td data-label="詳細と構造上の理由">第1証明と別証明1の双方が切れるためです (<strong>※命題11の第3証明は未登録であり、命題11全体の結論ではありません</strong>)。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- セクション4: 今回わかったこと(このモデルの範囲の結果。新規性は未確認) -->
    <section>
      <h2>今回わかったこと(このモデルの範囲の結果。新規性は未確認)</h2>
      <ol style="padding-left: 20px;">
        <li>アンセルムスと、デカルトの命題1〜3の論証は、いずれも一本道です。<br>前提のどれか一つが使えなくなれば、結論までの道が切れます。</li>
        <li>デカルトの論証は、「神の本性を考えるだけ」で導く道(命題1)が、一つの公理(公理10)に依存しています。自分の中の神の観念や、自分自身の存在から導く道(命題2・3)は、この公理に依存しません。</li>
        <li>スピノザの命題11は、登録した範囲で、複数の道をもちます。<br>二つの道が、別々の前提(定義1と充足理由律)に依存するため、片方に批判が向けられても、設定によっては、もう一方の道が残ります。両方に批判が向けられると、登録した道は残りません。</li>
        <li>ただし、このモデルは、本文の明示引用と、モデル作成者が採用した補完前提を区別して登録しています。原典に含まれる暗黙の依存を、すべて網羅したものではありません。<br>スピノザのどの証明も、充足理由律に暗黙に依存すると読む研究もあります。その読み方では、3の結果は変わります。</li>
        <li>作る過程で、AIが作った初期データに、原典にない依存の混入や、本文と系の取り違えが見つかりました。論証の分析より前に、データを原典と照合する作業が必要でした。</li>
      </ol>
    </section>

    <!-- セクション5: 今回の取り組みで目指したこと(新規性は未確認) -->
    <section>
      <h2>今回の取り組みで目指したこと(新規性は未確認)</h2>
      <ul>
        <li><strong>先行する取り組み</strong>: 『エチカ』の依存関係の可視化、第1部の形式化、論証の地図化、ゲーデルの存在論的証明の自動検証などがあります。</li>
        <li><strong>今回試したこと</strong>: 複数の哲学者の論証を、同じ形式で、「前提や規則を止めたら、結論への道が残るか」を計算して並べました。そして、どのデータを人が確認し、どれがAIの記載のままかを、行ごとに示しました。</li>
        <li>先行研究との重なりは、まだ調べ切れていません。</li>
      </ul>

      <h3>参考にした先行の取り組み</h3>
      <ul>
        <li>
          <a href="https://eprints.illc.uva.nl/id/eprint/1537/" target="_blank" rel="noopener noreferrer">
            <strong>Pablo Sierra Márquez (2017)</strong>, <em>A formalization of Spinoza's Ethics, Part 1: Consequences for interpretation</em>
          </a> (アムステルダム大学 Master of Logic 論文、MoL-2017-02)。<br>
          第1部の公理・定義・最初の23命題を、依存関係を軸にした形式言語で扱った。(※直接接続は未確認)
        </li>
        <li>
          <a href="https://philarchive.org/archive/ROSSEA-3" target="_blank" rel="noopener noreferrer">
            <strong>Herbert Roseman (2016)</strong>, <em>Spinoza's Ethics as a Mathematical Object</em>
          </a> (PhilArchive)。<br>
          『エチカ』を有向グラフとして分析し、約1割の命題が冗長になりうると論じた。(※直接接続は未確認)
        </li>
        <li>
          <a href="https://ethica.bc.edu/" target="_blank" rel="noopener noreferrer">
            <strong>ethica.bc.edu</strong> (John Bagby, Boston College)
          </a><br>
          『エチカ』の論証構造の可視化マップ。
        </li>
        <li>
          <a href="https://argdown.org/" target="_blank" rel="noopener noreferrer">
            <strong>Argdown</strong> (Christian Voigt / DebateLab, Karlsruhe Institute of Technology: KIT)
          </a><br>
          論証の記述・地図化のツール。
        </li>
        <li>
          <a href="https://arxiv.org/abs/1308.4526" target="_blank" rel="noopener noreferrer">
            <strong>Christoph Benzmüller &amp; Bruno Woltzenlogel Paleo (2014)</strong>, <em>Formalization, Mechanization and Automation of Gödel's Proof of God's Existence</em>
          </a> (掲載先: ECAI 2014, arXiv:1308.4526)。<br>
          Benzmüller らによるゲーデルの存在論的証明の自動検証。
        </li>
      </ul>
    </section>

    <!-- セクション6: 読むときの注意 -->
    <section>
      <h2>読むときの注意</h2>
      <ul>
        <li>一本道の論証では、前提を一つ止めれば結論が切れるのは、構造上当然です。</li>
        <li>「道が残る」は、その論証が正しいという意味ではありません。「道が切れる」は、その論証が間違いだという意味でもありません。</li>
        <li>どの前提に、どの批判が向けられるかは、解釈です。解釈が分かれる点には、そのように書いています。</li>
        <li>スピノザの命題11の第3証明は、未登録です。上の結果は、命題11全体の結論ではありません。</li>
        <li>経路の多さは、論証の優劣を表しません。</li>
      </ul>
    </section>

    <footer>
      <p>幾何学的哲学推論エンジン | 読者向け検証レポート (v0)</p>
    </footer>
  </div>

  <script>
    function initTheme() {{
      const saved = localStorage.getItem("theme");
      if (saved) {{
        document.documentElement.setAttribute("data-theme", saved);
        updateThemeUI(saved);
      }} else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {{
        document.documentElement.setAttribute("data-theme", "light");
        updateThemeUI("light");
      }} else {{
        document.documentElement.setAttribute("data-theme", "dark");
        updateThemeUI("dark");
      }}
    }}

    function toggleTheme() {{
      const current = document.documentElement.getAttribute("data-theme") || "dark";
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
      updateThemeUI(next);
    }}

    function updateThemeUI(theme) {{
      const icon = document.getElementById("themeIcon");
      const text = document.getElementById("themeText");
      if (theme === "light") {{
        icon.textContent = "🌙";
        text.textContent = "Dark Mode";
      }} else {{
        icon.textContent = "☀️";
        text.textContent = "Light Mode";
      }}
    }}

    if (window.matchMedia) {{
      window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", e => {{
        if (!localStorage.getItem("theme")) {{
          const next = e.matches ? "light" : "dark";
          document.documentElement.setAttribute("data-theme", next);
          updateThemeUI(next);
        }}
      }});
    }}

    initTheme();
  </script>
</body>
</html>
"""

    out_path = os.path.join(ENGINE_DIR, "web", "reader_page_v0.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated {out_path} ({len(html)} bytes)")


if __name__ == "__main__":
    generate_reader_html()
