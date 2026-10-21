/**
 * PHILOSOPHY GEOMETRIC ENGINE - FRONTEND APPLICATION
 * 初心者向け「今回わかったこと」まとめ画面 ＆ 論理グラフ詳細ビューア
 */

// グローバル状態
const state = {
  currentView: 'graph', // デフォルト初期画面: 'insights' (今回わかったこと)
  currentSystem: 'Spinoza', // デフォルト選択体系: デカルト
  currentScenario: null,
  insightsData: null,
  systems: [],
  graphData: null,
  selectedNodeId: null,
  visNetwork: null,
  useVis: typeof vis !== 'undefined'
};

// DOM要素参照
const elements = {
  // Mode Tabs
  modeTabs: document.getElementById('modeTabs'),
  tabViewInsights: document.getElementById('tabViewInsights'),
  tabViewGraph: document.getElementById('tabViewGraph'),
  tabViewBenchmark: document.getElementById('tabViewBenchmark'),
  tabViewResearch: document.getElementById('tabViewResearch'),
  viewInsights: document.getElementById('viewInsights'),
  viewGraph: document.getElementById('viewGraph'),
  viewResearch: document.getElementById('viewResearch'),
  spinozaResearchContainer: document.getElementById('spinozaResearchContainer'),
  geometryResearchContainer: document.getElementById('geometryResearchContainer'),

  // Insights View Elements
  insightsSystemButtons: document.getElementById('insightsSystemButtons'),
  scenarioSelect: document.getElementById('scenarioSelect'),
  btnSwitchToGraph: document.getElementById('btnSwitchToGraph'),
  insightsWarningStrip: document.getElementById('insightsWarningStrip'),
  cardsContainer: document.getElementById('cardsContainer'),
  comparisonNote: document.getElementById('comparisonNote'),
  appliedChangesList: document.getElementById('appliedChangesList'),
  countLost: document.getElementById('countLost'),
  countRetained: document.getElementById('countRetained'),
  countConflict: document.getElementById('countConflict'),
  listLost: document.getElementById('listLost'),
  listRetained: document.getElementById('listRetained'),
  listConflict: document.getElementById('listConflict'),
  whyRoutesContainer: document.getElementById('whyRoutesContainer'),
  evidenceDetails: document.getElementById('evidenceDetails'),
  evidenceContent: document.getElementById('evidenceContent'),

  // Graph View Elements
  graphSystemTabs: document.getElementById('graphSystemTabs'),
  currentSystemTitle: document.getElementById('currentSystemTitle'),
  currentSystemDesc: document.getElementById('currentSystemDesc'),
  btnApproveDefs: document.getElementById('btnApproveDefs'),
  btnInjectKant: document.getElementById('btnInjectKant'),
  btnReset: document.getElementById('btnReset'),
  
  // Status Bar
  statTotalNodes: document.getElementById('statTotalNodes'),
  statTrueCount: document.getElementById('statTrueCount'),
  statUnknownCount: document.getElementById('statUnknownCount'),
  statFalseCount: document.getElementById('statFalseCount'),
  statConflictCount: document.getElementById('statConflictCount'),
  statSurvivalBar: document.getElementById('statSurvivalBar'),
  statSurvivalRate: document.getElementById('statSurvivalRate'),

  // Semantics & Scenario Strip
  graphSemanticsMode: document.getElementById('graphSemanticsMode'),
  graphEvalStatus: document.getElementById('graphEvalStatus'),
  graphScenarioName: document.getElementById('graphScenarioName'),

  // Graph Canvases
  graphContainer: document.getElementById('graphContainer'),
  visNetworkCanvas: document.getElementById('visNetwork'),
  svgFallback: document.getElementById('svgFallback'),

  // Inspector
  inspectorEmpty: document.getElementById('inspectorEmpty'),
  nodeDetails: document.getElementById('nodeDetails'),
  detailType: document.getElementById('detailType'),
  detailId: document.getElementById('detailId'),
  detailValueBadge: document.getElementById('detailValueBadge'),
  detailTitle: document.getElementById('detailTitle'),
  detailTextJa: document.getElementById('detailTextJa'),
  detailLogicalForm: document.getElementById('detailLogicalForm'),
  detailDependencies: document.getElementById('detailDependencies'),

  // Actions & Premise Toggle
  premiseToggleBlock: document.getElementById('premiseToggleBlock'),
  premiseStatusText: document.getElementById('premiseStatusText'),
  btnTogglePremise: document.getElementById('btnTogglePremise'),
  propositionNoticeBlock: document.getElementById('propositionNoticeBlock'),
  btnWhatIfFalse: document.getElementById('btnWhatIfFalse'),
  btnFindFrontier: document.getElementById('btnFindFrontier'),
  frontierBlock: document.getElementById('frontierBlock'),
  simulationResult: document.getElementById('simulationResult'),
  simResultTitle: document.getElementById('simResultTitle'),
  simResultBody: document.getElementById('simResultBody'),
  btnCloseSimResult: document.getElementById('btnCloseSimResult'),

  // Modal
  benchmarkModal: document.getElementById('benchmarkModal'),
  benchmarkModalBody: document.getElementById('benchmarkModalBody'),
  btnCloseModal: document.getElementById('btnCloseModal'),

  // Toast
  toastContainer: document.getElementById('toastContainer')
};

// ==========================================================================
// TOAST NOTIFICATION
// ==========================================================================
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ==========================================================================
// VIEW SWITCHING (今回わかったこと ↔ 論理グラフ ↔ 耐震性比較)
// ==========================================================================
function switchView(viewName) {
  state.currentView = viewName;

  // タブボタンのアクティブ更新
  document.querySelectorAll('.mode-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewName);
  });

if (viewName === 'insights') {
    if (elements.viewInsights) elements.viewInsights.classList.add('active');
    if (elements.viewGraph) elements.viewGraph.classList.remove('active');
    if (elements.viewResearch) elements.viewResearch.classList.remove('active');
    // If cards container exists, show note if no other systems
    if (elements.cardsContainer) {
      elements.cardsContainer.innerHTML = '<div class="info-box">※カント批判や他哲学体系との比較カードは、統合版パッケージにて提供されます。Spinozaの幾何学的演繹は「幾何学グラフ」および「研究成果」タブをご参照ください。</div>';
    }
    return;
  } else if (viewName === 'graph') {
    elements.viewInsights.classList.remove('active');
    elements.viewGraph.classList.add('active');
    if (elements.viewResearch) elements.viewResearch.classList.remove('active');
    loadGraphData(state.currentSystem);
  } else if (viewName === 'research') {
    elements.viewInsights.classList.remove('active');
    elements.viewGraph.classList.remove('active');
    if (elements.viewResearch) elements.viewResearch.classList.add('active');
    loadResearchData();
  } else if (viewName === 'benchmark') {
    openBenchmarkModal();
  }
}

// ==========================================================================
// API HELPER (Robust JSON Fetcher)
// ==========================================================================

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const contentType = res.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    if (res.status === 404) {
      throw new Error(`APIエンドポイント (${url}) が見つかりません (404)。server.py が最新か確認してください。`);
    }
    throw new Error(`サーバから予期しないレスポンス形式が返されました (HTTP ${res.status})`);
  }
  const json = await res.json();
  if (json.status !== 'success') {
    throw new Error(json.message || 'APIリクエストに失敗しました');
  }
  return json.data;
}

// ==========================================================================
// INSIGHTS VIEW LOGIC (今回わかったこと)
// ==========================================================================

async function loadInsights() {
  try {
    elements.cardsContainer.innerHTML = '<div class="loading-box">検証結果を集計中...</div>';

    let url = `/api/insights?system=${encodeURIComponent(state.currentSystem)}`;
    if (state.currentScenario) {
      url += `&scenario=${encodeURIComponent(state.currentScenario)}`;
    }

    const data = await fetchJson(url);
    state.insightsData = data;
    renderInsights(data);
  } catch (err) {
    showToast(`エラー: ${err.message}`, 'error');
    elements.cardsContainer.innerHTML = `<div class="error-box">データの読み込みに失敗しました: ${err.message}</div>`;
  }
}

function renderInsights(data) {
  // 1. 体系ボタンのアクティブ更新
  document.querySelectorAll('#insightsSystemButtons .sys-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.sys === data.system_id);
  });

  // 2. シナリオドロップダウンの更新
  elements.scenarioSelect.innerHTML = '';
  data.available_scenarios.forEach(sc => {
    const opt = document.createElement('option');
    opt.value = sc.id;
    opt.textContent = sc.label;
    if (sc.id === data.selected_scenario.id) {
      opt.selected = true;
    }
    elements.scenarioSelect.appendChild(opt);
  });
  state.currentScenario = data.selected_scenario.id;

  // 3. 警告ストリップ (未収束・計算未完了)
  if (data.status_warning) {
    elements.insightsWarningStrip.textContent = data.status_warning;
    elements.insightsWarningStrip.style.display = 'flex';
  } else {
    elements.insightsWarningStrip.style.display = 'none';
  }

  // 4. SECTION A: 重要結果カード (最大3件)
  renderCards(data.cards);

  // 5. SECTION B: 変更前と変更後
  renderBeforeAfter(data.before_after);

  // 6. SECTION C: なぜそうなった？ (証明経路)
  renderWhyRoutes(data.why_it_happened);

  // 7. SECTION D: 詳しい証拠
  renderDetailedEvidence(data.detailed_evidence);
}

function renderCards(cards) {
  if (!cards || cards.length === 0) {
    elements.cardsContainer.innerHTML = `
      <div class="no-diff-box">
        <div style="font-size: 24px; margin-bottom: 8px;">ℹ️</div>
        <strong>重要な差分は見つかりませんでした</strong>
        <p style="margin-top: 6px; font-size: 13px;">この批判シナリオに対して、対象体系内の推論規則や定理の支持状態は影響を受けませんでした。</p>
      </div>
    `;
    return;
  }

  elements.cardsContainer.innerHTML = cards.map(c => `
    <div class="result-card">
      <div class="card-top-meta">
        <span class="card-type-tag">${escapeHtml(c.card_type)}</span>
        <span class="card-reason-tag">${escapeHtml(c.selection_reason)}</span>
      </div>

      <h3 class="card-headline">${escapeHtml(c.headline)}</h3>

      <div class="card-body-items">
        <div class="card-item">
          <span class="card-item-label">何を試したか</span>
          <span class="card-item-text">${escapeHtml(c.tested)}</span>
        </div>

        <div class="card-item">
          <span class="card-item-label">観測された変化</span>
          <span class="card-item-text">${escapeHtml(c.observed)}</span>
        </div>

        <div class="card-item">
          <span class="card-item-label">なぜ重要か</span>
          <span class="card-item-text">${escapeHtml(c.why_important)}</span>
        </div>

        <div class="card-cannot-say">
          <span class="card-item-label">⚠️ この結果から言えないこと</span>
          <span class="card-item-text">${escapeHtml(c.cannot_say)}</span>
        </div>
      </div>

      <div class="card-footer-meta">
        <span class="card-scope">確認範囲: ${escapeHtml(c.scope)}</span>
        <button class="card-link-btn" onclick="jumpToEvidence('${escapeHtml(c.evidence_link_id)}')">
          根拠データを見る ➔
        </button>
      </div>
    </div>
  `).join('');
}

function renderBeforeAfter(ba) {
  elements.comparisonNote.textContent = ba.comparison_note;

  // 適用された変更内容
  if (ba.changes_applied && ba.changes_applied.length > 0) {
    elements.appliedChangesList.innerHTML = ba.changes_applied.map(ch => `
      <div class="change-item">
        <span class="change-tag">${escapeHtml(ch.type)}</span>
        <strong style="color: #ffffff;">${escapeHtml(ch.title)}</strong>:
        <span class="change-text">${escapeHtml(ch.description)}</span>
      </div>
    `).join('');
  } else {
    elements.appliedChangesList.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">変更なし（ベースライン）</div>';
  }

  // 件数
  elements.countLost.textContent = ba.counts.lost_count;
  elements.countRetained.textContent = ba.counts.retained_count;
  elements.countConflict.textContent = ba.counts.rebutted_count;

  // 1. 支持喪失リスト
  elements.listLost.innerHTML = renderDiffListItems(ba.lost_theorems, 'lost');

  // 2. 支持残存リスト
  elements.listRetained.innerHTML = renderDiffListItems(ba.retained_theorems, 'retained');

  // 3. 衝突リスト
  elements.listConflict.innerHTML = renderDiffListItems(ba.rebutted_theorems, 'conflict');
}

function renderDiffListItems(items, type) {
  if (!items || items.length === 0) {
    return '<div style="color: var(--text-muted); font-size: 12px; padding: 4px;">該当する命題はありません</div>';
  }

  return items.map(item => `
    <div class="diff-item">
      <div class="diff-item-head">
        <span class="diff-item-title">${escapeHtml(item.title)}</span>
        <span class="diff-item-id">${escapeHtml(item.id)}</span>
      </div>
      <div class="diff-item-status">
        変更前: <span style="color: #a5b4fc;">${escapeHtml(item.status_before_short)}</span> ➔
        変更後: <span style="font-weight: 700; color: ${type === 'lost' ? '#f87171' : (type === 'retained' ? '#4ade80' : '#fbbf24')};">${escapeHtml(item.status_after)}</span>
      </div>
    </div>
  `).join('');
}

function toggleDiffList(listId) {
  const el = document.getElementById(listId);
  if (!el) return;
  const isHidden = el.style.display === 'none';
  el.style.display = isHidden ? 'flex' : 'none';
  const header = el.previousElementSibling.previousElementSibling;
  const arrow = header ? header.querySelector('.diff-toggle-arrow') : null;
  if (arrow) {
    arrow.textContent = isHidden ? '▲' : '▼';
  }
}

function renderWhyRoutes(why) {
  if (!why || !why.routes || why.routes.length === 0) {
    elements.whyRoutesContainer.innerHTML = `
      <div class="no-diff-box">
        推論経路に変化のあった定理はありません。
      </div>
    `;
    return;
  }

  elements.whyRoutesContainer.innerHTML = why.routes.map(r => `
    <div class="route-card">
      <div class="route-header">
        <span class="route-title">${escapeHtml(r.theorem_title)} (${escapeHtml(r.theorem_id)})</span>
        <span class="route-status-tag" style="background: rgba(99, 102, 241, 0.2); color: #c7d2fe;">
          最終状態: ${escapeHtml(r.final_status)}
        </span>
      </div>

      <div class="route-paths-grid">
        <!-- 止まった経路 -->
        <div class="path-column">
          <div class="path-col-title blocked">
            <span>❌ 止まった証明経路 (${r.blocked_paths.length}件)</span>
          </div>
          ${r.blocked_paths.length === 0 ? '<div style="color: var(--text-muted); font-size: 12px;">遮断された経路はありません</div>' : ''}
          ${r.blocked_paths.map(p => `
            <div class="path-box blocked">
              <span class="path-rule-name">${escapeHtml(p.rule_name)} [${escapeHtml(p.rule_id)}]</span>
              <span class="path-reason">${escapeHtml(p.reason)}</span>
            </div>
          `).join('')}
        </div>

        <!-- 残った経路 -->
        <div class="path-column">
          <div class="path-col-title surviving">
            <span>✅ 生き残った別証明経路 (${r.surviving_paths.length}件)</span>
          </div>
          ${r.surviving_paths.length === 0 ? '<div style="color: var(--text-muted); font-size: 12px;">有効な証明経路は残存していません</div>' : ''}
          ${r.surviving_paths.map(p => `
            <div class="path-box surviving">
              <span class="path-rule-name">${escapeHtml(p.rule_name)} [${escapeHtml(p.rule_id)}]</span>
              <span class="path-reason">${escapeHtml(p.reason)}</span>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `).join('');
}

function renderDetailedEvidence(ev) {
  if (!ev) return;

  elements.evidenceContent.innerHTML = `
    <div class="evidence-meta-grid">
      <div class="evidence-meta-item">
        <span class="evidence-meta-label">形式意味論バージョン</span>
        <span class="evidence-meta-val">${escapeHtml(ev.model_version)}</span>
      </div>
      <div class="evidence-meta-item">
        <span class="evidence-meta-label">意味論タイプ</span>
        <span class="evidence-meta-val">${escapeHtml(ev.semantics_type)}</span>
      </div>
      <div class="evidence-meta-item">
        <span class="evidence-meta-label">評価完了ステータス</span>
        <span class="evidence-meta-val" style="color: #4ade80;">${escapeHtml(ev.evaluation_status)} (ステップ数: ${ev.step_count})</span>
      </div>
    </div>

    <!-- 命題証拠テーブル -->
    <div>
      <h4 class="sub-heading">📋 対象命題と原典位置・導出根拠</h4>
      <div style="overflow-x: auto;">
        <table class="evidence-table">
          <thead>
            <tr>
              <th>命題ID</th>
              <th>日本語タイトル</th>
              <th>原典位置 (Source Ref)</th>
              <th>肯定支持理由 (Positive Supports)</th>
              <th>真理値</th>
            </tr>
          </thead>
          <tbody>
            ${ev.propositions.map(p => `
              <tr id="ev_prop_${escapeHtml(p.id)}">
                <td style="font-family: var(--font-mono); font-weight: 600;">${escapeHtml(p.id)}</td>
                <td style="color: #ffffff;">${escapeHtml(p.title)}</td>
                <td style="font-style: italic;">${escapeHtml(p.source_ref)}</td>
                <td style="font-family: var(--font-mono); font-size: 11px;">${escapeHtml(p.positive_supports.join(', ') || 'なし')}</td>
                <td><span style="font-weight: 600; color: ${p.status_name === 'TRUE' ? '#4ade80' : (p.status_name === 'UNKNOWN' ? '#94a3b8' : '#f87171')};">${escapeHtml(p.status_label)}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <!-- 再現用コード -->
    <div>
      <h4 class="sub-heading">💻 Python による再現検証コード</h4>
      <pre class="repro-code-box"><code>${escapeHtml(ev.reproduction_code)}</code></pre>
    </div>
  `;
}

function jumpToEvidence(propId) {
  elements.evidenceDetails.open = true;
  setTimeout(() => {
    const target = document.getElementById(`ev_prop_${propId}`);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      target.style.backgroundColor = 'rgba(99, 102, 241, 0.3)';
      target.style.transition = 'background-color 0.5s ease';
      setTimeout(() => {
        target.style.backgroundColor = 'transparent';
      }, 2500);
    }
  }, 100);
}

// ==========================================================================
// GRAPH VIEW LOGIC (論理グラフ詳細画面)
// ==========================================================================

async function loadGraphData(systemKey) {
  try {
    const data = await fetchJson(`/api/system?id=${systemKey}`);
    state.graphData = data;
    state.currentSystem = systemKey;

    // ヘッダー情報更新
    elements.currentSystemTitle.textContent = data.system_name;
    elements.currentSystemDesc.textContent = data.description;

    // グラフ用システムピルのアクティブ更新
    document.querySelectorAll('#graphSystemTabs .pill-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.system === systemKey);
    });

    // ステータスストリップ更新
    updateStatusBar(data.summary, data.survival_rate, data.scenario_info);

    // グラフ描画
    renderGraph(data);

    // インスペクタをクリア
    clearInspector();
  } catch (err) {
    showToast(`グラフ読み込み失敗: ${err.message}`, 'error');
  }
}

function updateStatusBar(summary, survivalRate, scenarioInfo) {
  elements.statTotalNodes.textContent = (summary.TRUE + summary.FALSE + summary.UNKNOWN + summary.CONFLICT) || 0;
  elements.statTrueCount.textContent = summary.TRUE || 0;
  elements.statUnknownCount.textContent = summary.UNKNOWN || 0;
  elements.statFalseCount.textContent = summary.FALSE || 0;
  elements.statConflictCount.textContent = summary.CONFLICT || 0;
  elements.statSurvivalRate.textContent = `${survivalRate}%`;
  elements.statSurvivalBar.style.width = `${Math.min(survivalRate, 100)}%`;

  if (scenarioInfo) {
    if (elements.graphSemanticsMode) {
      elements.graphSemanticsMode.textContent = `${scenarioInfo.model_version} ${scenarioInfo.semantics_mode}`;
    }
    if (elements.graphEvalStatus) {
      elements.graphEvalStatus.textContent = scenarioInfo.evaluation_status;
      elements.graphEvalStatus.style.color = scenarioInfo.evaluation_status === 'CONVERGED' ? '#34d399' : '#f59e0b';
    }
    if (elements.graphScenarioName) {
      if (scenarioInfo.is_baseline) {
        elements.graphScenarioName.textContent = 'ベースライン (全前提採用)';
        elements.graphScenarioName.style.color = '#f1f5f9';
      } else {
        const parts = [];
        if (scenarioInfo.omitted_premises && scenarioInfo.omitted_premises.length > 0) {
          parts.push(`不採用: [${scenarioInfo.omitted_premises.join(', ')}]`);
        }
        if (scenarioInfo.injected_critiques && scenarioInfo.injected_critiques.length > 0) {
          parts.push(`批判注入: [${scenarioInfo.injected_critiques.join(', ')}]`);
        }
        elements.graphScenarioName.textContent = parts.join(' / ') || 'カスタムシナリオ';
        elements.graphScenarioName.style.color = '#f59e0b';
      }
    }
  }
}

function renderGraph(data) {
  if (state.useVis) {
    renderVisNetwork(data);
  } else {
    renderSvgFallback(data);
  }
}

function renderVisNetwork(data) {
  elements.visNetworkCanvas.style.display = 'block';
  elements.svgFallback.style.display = 'none';

  const nodes = data.nodes.map(n => {
    let colorBg = '#334155';
    let colorBorder = '#64748b';
    let shape = 'box';

    if (n.type === 'axiom') shape = 'ellipse';
    else if (n.type === 'definition') shape = 'box';
    else if (n.type === 'proposition') shape = 'diamond';

    if (n.value === 'TRUE') {
      colorBg = 'rgba(16, 185, 129, 0.25)';
      colorBorder = '#10b981';
    } else if (n.value === 'FALSE') {
      colorBg = 'rgba(239, 68, 68, 0.25)';
      colorBorder = '#ef4444';
    } else if (n.value === 'CONFLICT') {
      colorBg = 'rgba(245, 158, 11, 0.25)';
      colorBorder = '#f59e0b';
    }

    // 前提ノードが不採用の場合は枠線を破線または薄く強調
    return {
      id: n.id,
      label: `${n.title}\n[${n.id}]`,
      shape: shape,
      color: {
        background: colorBg,
        border: colorBorder,
        highlight: { background: colorBg, border: '#ffffff' }
      },
      font: { color: '#ffffff', size: 12, face: 'Noto Serif JP, sans-serif' },
      margin: 10,
      borderWidth: (n.is_premise && n.is_active_premise === false) ? 1 : 1.5,
      nodeData: n
    };
  });

  const edges = data.edges.map(e => ({
    from: e.from,
    to: e.to,
    arrows: 'to',
    color: {
      color: e.status === 'broken' ? '#ef4444' : (e.status === 'conflict' ? '#f59e0b' : (e.status === 'unsupported' ? '#64748b' : '#10b981')),
      highlight: '#ffffff'
    },
    dashes: e.status === 'broken' || e.status === 'unsupported',
    width: (e.status === 'broken' || e.status === 'conflict') ? 2 : 1
  }));

  const container = elements.visNetworkCanvas;
  const graphData = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
  const options = {
    layout: {
      hierarchical: {
        direction: 'LR',
        sortMethod: 'directed',
        levelSeparation: 180,
        nodeSpacing: 100
      }
    },
    physics: false,
    interaction: { hover: true, tooltipDelay: 200 }
  };

  if (state.visNetwork) {
    state.visNetwork.destroy();
  }

  state.visNetwork = new vis.Network(container, graphData, options);

  state.visNetwork.on('click', params => {
    if (params.nodes.length > 0) {
      selectNode(params.nodes[0]);
    } else {
      clearInspector();
    }
  });
}

function renderSvgFallback(data) {
  elements.visNetworkCanvas.style.display = 'none';
  elements.svgFallback.style.display = 'block';
  elements.svgFallback.innerHTML = '';

  const svg = elements.svgFallback;
  const width = svg.clientWidth || 800;
  const height = svg.clientHeight || 600;

  let y = 40;
  data.nodes.forEach(n => {
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', '30');
    text.setAttribute('y', y.toString());
    text.setAttribute('fill', n.value === 'TRUE' ? '#10b981' : (n.value === 'FALSE' ? '#ef4444' : '#94a3b8'));
    text.textContent = `[${n.value}] ${n.title} (${n.id})`;
    text.style.cursor = 'pointer';
    text.onclick = () => selectNode(n.id);
    svg.appendChild(text);
    y += 28;
  });
}

function selectNode(nodeId) {
  if (!state.graphData) return;
  const node = state.graphData.nodes.find(n => n.id === nodeId);
  if (!node) return;

  state.selectedNodeId = nodeId;
  elements.inspectorEmpty.style.display = 'none';
  elements.nodeDetails.style.display = 'block';

  elements.detailType.textContent = node.type.toUpperCase();
  elements.detailId.textContent = node.id;
  elements.detailTitle.textContent = node.title;
  elements.detailTextJa.textContent = node.text_ja || '（テキスト未登録）';
  elements.detailLogicalForm.textContent = node.logical_form || 'N/A';

  elements.detailValueBadge.textContent = node.value;
  elements.detailValueBadge.className = `node-value-badge val-${node.value.toLowerCase()}`;

  // 前提ノードリスト
  elements.detailDependencies.innerHTML = '';
  if (node.dependencies && node.dependencies.length > 0) {
    node.dependencies.forEach(depId => {
      const depNode = state.graphData.nodes.find(n => n.id === depId);
      const tag = document.createElement('span');
      tag.className = 'dep-tag';
      tag.textContent = depNode ? `${depNode.title} [${depId}]` : depId;
      tag.onclick = () => selectNode(depId);
      elements.detailDependencies.appendChild(tag);
    });
  } else {
    elements.detailDependencies.innerHTML = '<span style="color: var(--text-muted); font-size: 12px;">なし（公理または定義）</span>';
  }

  // 前提トグルUI制御 (公理・定義 vs 定理)
  const isPremise = (node.type === 'axiom' || node.type === 'definition' || node.is_premise);
  if (isPremise) {
    elements.premiseToggleBlock.style.display = 'block';
    elements.propositionNoticeBlock.style.display = 'none';

    const isActive = (node.is_active_premise !== false);
    if (isActive) {
      elements.premiseStatusText.textContent = '採用中 (ACTIVE)';
      elements.premiseStatusText.style.color = '#10b981';
      elements.btnTogglePremise.textContent = 'この前提を採用しない';
      elements.btnTogglePremise.className = 'btn btn-secondary btn-sm';
    } else {
      elements.premiseStatusText.textContent = '不採用 (OMITTED / 未支持)';
      elements.premiseStatusText.style.color = '#94a3b8';
      elements.btnTogglePremise.textContent = 'この前提を採用する';
      elements.btnTogglePremise.className = 'btn btn-primary btn-sm';
    }
  } else {
    elements.premiseToggleBlock.style.display = 'none';
    elements.propositionNoticeBlock.style.display = 'block';
  }

  // フロンティア探索ボタンの表示制御 (UNKNOWN の proposition のみ)
  if (node.type === 'proposition' && node.value === 'UNKNOWN') {
    elements.frontierBlock.style.display = 'block';
  } else {
    elements.frontierBlock.style.display = 'none';
  }

  // シミュレーション結果を非表示
  elements.simulationResult.style.display = 'none';
}

function clearInspector() {
  state.selectedNodeId = null;
  elements.inspectorEmpty.style.display = 'flex';
  elements.nodeDetails.style.display = 'none';
}

// ==========================================================================
// ACTIONS & WHAT-IF SIMULATION
// ==========================================================================

async function toggleCurrentPremise() {
  if (!state.selectedNodeId || !state.graphData) return;
  const node = state.graphData.nodes.find(n => n.id === state.selectedNodeId);
  if (!node) return;

  const currentActive = (node.is_active_premise !== false);
  const newActive = !currentActive;

  try {
    const data = await fetchJson('/api/toggle-premise', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        system: state.currentSystem,
        node_id: state.selectedNodeId,
        active: newActive
      })
    });

    state.graphData = data;
    updateStatusBar(data.summary, data.survival_rate, data.scenario_info);
    renderGraph(data);
    selectNode(state.selectedNodeId);
    showToast(`前提 ${state.selectedNodeId} を「${newActive ? '採用' : '不採用'}」に変更しました`, 'success');
  } catch (err) {
    showToast(`前提トグル失敗: ${err.message}`, 'error');
  }
}

async function toggleNodeValue(newVal) {
  if (!state.selectedNodeId) return;
  try {
    const isPremiseActive = (newVal === 'TRUE');
    const data = await fetchJson('/api/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        system: state.currentSystem,
        node_id: state.selectedNodeId,
        value: newVal,
        active: isPremiseActive
      })
    });

    state.graphData = data;
    updateStatusBar(data.summary, data.survival_rate, data.scenario_info);
    renderGraph(data);
    selectNode(state.selectedNodeId);
    showToast(`命題 ${state.selectedNodeId} を更新しました`, 'success');
  } catch (err) {
    showToast(`更新失敗: ${err.message}`, 'error');
  }
}

async function runWhatIfFalse() {
  if (!state.selectedNodeId) return;
  try {
    const data = await fetchJson('/api/what-if', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ system: state.currentSystem, node_id: state.selectedNodeId, value: 'FALSE' })
    });

    elements.simulationResult.style.display = 'block';
    elements.simResultTitle.textContent = `💭 もし「${state.selectedNodeId}」を否定(FALSE)したら？`;

    elements.simResultBody.innerHTML = `
      <div style="font-size: 13px; line-height: 1.6;">
        <p><strong>意味論モード:</strong> ${data.model_version} ${data.semantics_mode}</p>
        <p><strong>影響を受ける定理数:</strong> ${data.total_affected} 件 (全体の ${data.impact_percentage}%)</p>
        <p><strong>生存定理:</strong> ${data.survived_theorems} / ${data.total_theorems} 件</p>
        <div style="margin-top: 8px;">
          <strong>支持を失った・変化した定理一覧:</strong>
          <ul style="padding-left: 20px; color: #fca5a5; margin-top: 4px;">
            ${data.affected_theorems.length > 0
              ? data.affected_theorems.map(t => `<li>${t.title} [${t.id}] (${t.previous_status} → ${t.new_status})</li>`).join('')
              : '<li>なし（他への波及なし）</li>'}
          </ul>
        </div>
      </div>
    `;
  } catch (err) {
    showToast(`シミュレーション失敗: ${err.message}`, 'error');
  }
}

async function findFrontier() {
  if (!state.selectedNodeId) return;
  try {
    const solutions = await fetchJson('/api/frontier', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ system: state.currentSystem, target_id: state.selectedNodeId })
    });

    elements.simulationResult.style.display = 'block';
    elements.simResultTitle.textContent = `🎯 定理「${state.selectedNodeId}」の最小成立要件`;

    if (!solutions || solutions.length === 0) {
      elements.simResultBody.innerHTML = '<p style="color: var(--text-muted);">成立解が見つかりませんでした。</p>';
      return;
    }

    elements.simResultBody.innerHTML = `
      <div style="font-size: 13px; line-height: 1.6;">
        <p>以下の定義・仮定を追加承認することでこの定理が成立します：</p>
        ${solutions.map((sol, idx) => `
          <div style="background: var(--bg-surface); padding: 8px 12px; border-radius: 4px; margin-top: 6px;">
            <strong>解候補 ${idx + 1} (${sol.total_assumptions_needed}個の仮定):</strong>
            <ul style="padding-left: 20px; color: #a5b4fc; margin-top: 4px;">
              ${sol.required_assumptions.map(a => `<li>${a.title} [${a.id}]</li>`).join('')}
            </ul>
          </div>
        `).join('')}
      </div>
    `;
  } catch (err) {
    showToast(`逆算探索失敗: ${err.message}`, 'error');
  }
}

async function approveAllDefinitions() {
  try {
    const data = await fetchJson('/api/approve_defs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ system: state.currentSystem })
    });

    state.graphData = data;
    updateStatusBar(data.summary, data.survival_rate, data.scenario_info);
    renderGraph(data);
    showToast('すべての定義を一括承認しました', 'success');
  } catch (err) {
    showToast(`一括承認失敗: ${err.message}`, 'error');
  }
}

async function injectKantCritique() {
  try {
    const data = await fetchJson('/api/clash', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ system: state.currentSystem })
    });

    state.graphData = data;
    updateStatusBar(data.summary, data.survival_rate, data.scenario_info);
    renderGraph(data);
    showToast('カント批判公理を注入しました', 'warning');
  } catch (err) {
    showToast(`カント注入失敗: ${err.message}`, 'error');
  }
}

async function resetSystem() {
  try {
    const data = await fetchJson('/api/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ system: state.currentSystem })
    });

    state.graphData = data;
    updateStatusBar(data.summary, data.survival_rate, data.scenario_info);
    renderGraph(data);
    clearInspector();
    showToast('初期状態にリセットしました', 'info');
  } catch (err) {
    showToast(`リセット失敗: ${err.message}`, 'error');
  }
}

function openBenchmarkModal() {
  showToast('耐震性ベンチマーク（デカルト・ライプニッツ・カントとの比較）は統合版パッケージの機能です。', 'info');
}

function renderBenchmarkResults(benchmarks) {
  let html = `
    <div style="margin-bottom: 20px; font-size: 13px; color: var(--text-secondary); line-height: 1.6;">
      イマヌエル・カント『純粋理性批判』による概念分析的証明批判・認識限界批判を各哲学体系に注入した際の、
      定理（Proposition）の生存率と崩壊度を新形式意味論（2ビット支持・排他的4分類）で定量比較します。
    </div>
  `;

  for (const [sysKey, data] of Object.entries(benchmarks)) {
    const scSim = data.scenarios['Kant_Simultaneous (カント批判全同時注入)'] || Object.values(data.scenarios)[0];
    const trueRate = scSim ? scSim.true_rate : 0;

    html += `
      <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 16px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
          <h3 style="color: #ffffff; font-size: 16px;">${escapeHtml(data.system)}</h3>
          <span style="font-weight: 700; font-size: 18px; color: ${trueRate > 50 ? '#10b981' : (trueRate > 20 ? '#f59e0b' : '#ef4444')};">
            生存率: ${trueRate}%
          </span>
        </div>
        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 10px;">
          定理総数: ${data.total_theorems} 件 | 確定真: ${scSim ? scSim.true_count : 0} 件 | 支持あり: ${scSim ? scSim.supported_count : 0} 件
        </div>
        <div style="font-size: 12px; color: var(--text-secondary);">
          <strong>失われた定理:</strong> ${scSim && scSim.lost_support_ids.length > 0 ? escapeHtml(scSim.lost_support_ids.join(', ')) : 'なし'}
        </div>
      </div>
    `;
  }

  elements.benchmarkModalBody.innerHTML = html;
}

// ==========================================================================
// UTILITIES & EVENT LISTENERS
// ==========================================================================

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ==========================================================================
// RESEARCH VIEW: SAVED EXPERIMENTAL RESULTS
// ==========================================================================

async function loadResearchData() {
  if (!elements.spinozaResearchContainer || !elements.geometryResearchContainer) return;

  // 1. スピノザ命題11別証明データ読み込み (v0.2 確定版を優先取得)
  try {
    elements.spinozaResearchContainer.innerHTML = '<div style="color: var(--text-muted); padding: 16px;">スピノザ実験データを読み込み中...</div>';
    let dataSpinoza = null;
    try {
      dataSpinoza = await fetchJson('/spinoza_findings_v02.json');
    } catch (e) {
      dataSpinoza = await fetchJson('/api/research/spinoza');
    }
    if (dataSpinoza && (dataSpinoza.models || (dataSpinoza.data && dataSpinoza.data.models))) {
      renderSpinozaResearch(dataSpinoza);
    } else {
      elements.spinozaResearchContainer.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 6px; padding: 14px; color: #fca5a5;">
          ⚠️ データ不足または未登録です (docs/spinoza_alternative_proofs_results.json が見つかりません)
        </div>
      `;
    }
  } catch (err) {
    elements.spinozaResearchContainer.innerHTML = `
      <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 6px; padding: 14px; color: #fca5a5;">
        ⚠️ データ不足または読み込み失敗: ${escapeHtml(err.message)}
      </div>
    `;
  }

  // 2. 幾何学再現実験データ読み込み
  try {
    elements.geometryResearchContainer.innerHTML = '<div style="color: var(--text-muted); padding: 16px;">幾何学実験データを読み込み中...</div>';
    const dataGeom = await fetchJson('/api/research/geometry');
    if (dataGeom && dataGeom.triangle) {
      renderGeometryResearch(dataGeom);
    } else {
      elements.geometryResearchContainer.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 6px; padding: 14px; color: #fca5a5;">
          ⚠️ データ不足または未登録です (docs/geometry_reproduction_results.json が見つかりません)
        </div>
      `;
    }
  } catch (err) {
    elements.geometryResearchContainer.innerHTML = `
      <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 6px; padding: 14px; color: #fca5a5;">
        ⚠️ 幾何学データ不足または読み込み失敗: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function renderSpinozaResearch(rawPayload) {
  const data = (rawPayload && rawPayload.data) ? rawPayload.data : rawPayload;
  const models = data.models || {};
  const mA = models.model_a || {};
  const mB = models.model_b || {};
  const mC1 = models.model_c1 || {};
  const mC2 = models.model_c2 || {};

  const modelList = [
    { key: 'A', name: 'モデルA (基準: 単一証明)', model: mA, desc: '原典本文の基本証明経路のみ' },
    { key: 'B', name: 'モデルB (命題11別証明 Aliter 1 追加)', model: mB, desc: '命題11の別証明 (R_PROP_11_ALITER1) を追加' },
    { key: 'C1', name: 'モデルC1 (命題6系別証明 追加)', model: mC1, desc: '命題6の系の別証明 (R_PROP_6_COROLLARY_ALITER) を追加' },
    { key: 'C2', name: 'モデルC2 (全別証明統合)', model: mC2, desc: '命題11別証明と命題6系別証明の両方を統合' },
  ];

  const findings = data.findings_classification || {};
  const robustFindings = findings.robust_findings || [];
  const interpFindings = findings.interpretation_dependent_findings || [];
  const methodProperties = findings.methodological_properties || [];

  let html = `
    <!-- バージョンと設定依存性注記 -->
    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid #3b82f6; border-radius: 8px; padding: 12px 18px; margin-bottom: 20px; font-size: 13px; line-height: 1.6;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
        <span style="font-weight: 700; color: #60a5fa;">📊 形式化データバージョン: v0.2 正式候補版 (26命題体系・系ノード分離済)</span>
        <span style="background: #1e3a8a; color: #93c5fd; padding: 2px 8px; border-radius: 4px; font-size: 11px;">学術的新規性: 未確認</span>
      </div>
      <div style="color: #cbd5e1; font-size: 12px;">
        ⚠️ <strong>表示条件・注記:</strong> 本画面の件数・数値は<strong>【設定(a)・DEF_6補完あり】</strong>における計算結果です。モデル化の範囲（全26命題体系か縮約パイロットか）や解釈設定により件数や成否は変動します。
      </div>
    </div>

    <!-- モデル比較テーブル (計算結果から自動判定) -->
    <div style="overflow-x: auto; margin-bottom: 24px;">
      <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left;" id="spinozaComparisonTable">
        <thead>
          <tr style="border-bottom: 2px solid var(--border-subtle); background: rgba(30, 41, 59, 0.5);">
            <th style="padding: 10px 12px;">モデル</th>
            <th style="padding: 10px 12px; text-align: center;">最小支持根拠数</th>
            <th style="padding: 10px 12px;">共通前提</th>
            <th style="padding: 10px 12px; text-align: center;">前提遮断数</th>
            <th style="padding: 10px 12px; text-align: center;">規則遮断数</th>
            <th style="padding: 10px 12px; text-align: center;">R_PROP_2 単体遮断</th>
            <th style="padding: 10px 12px; text-align: center;">R_PROP_3 単体遮断</th>
          </tr>
        </thead>
        <tbody>
  `;

  modelList.forEach(item => {
    const m = item.model;
    const groundsList = m.grounds || [];
    const groundsCount = groundsList.length;
    const commPremises = m.common_premises || [];
    const premCutsCount = (m.premise_cuts || []).length;
    const ruleCutsList = m.rule_cuts || [];
    const ruleCutsCount = ruleCutsList.length;

    // 単体遮断の自動判定 (手書きではなく計算結果集合 rule_cuts から直接判定)
    const isR2Cut = ruleCutsList.some(c => (Array.isArray(c) && c.length === 1 && c[0] === 'R_PROP_2'));
    const isR3Cut = ruleCutsList.some(c => (Array.isArray(c) && c.length === 1 && c[0] === 'R_PROP_3'));

    // 表示文言の自動生成
    const r2StatusHtml = !isR2Cut
      ? '<span class="bypass-badge bypass-yes" style="color: #34d399; font-weight: 700;">★迂回可能</span>'
      : '<span class="bypass-badge bypass-no" style="color: #f87171;">不可欠 (単体遮断)</span>';

    let r3StatusHtml = !isR3Cut
      ? '<span class="bypass-badge bypass-yes" style="color: #34d399; font-weight: 700;">★迂回可能</span>'
      : '<span class="bypass-badge bypass-no" style="color: #f87171;">不可欠 (単体遮断)</span>';

    if (item.key === 'B' && isR3Cut) {
      r3StatusHtml += '<div style="font-size: 10px; color: #fbbf24; margin-top: 2px;">※設定(c)のみ迂回可</div>';
    }

    html += `
      <tr data-model="${item.key}" style="border-bottom: 1px solid var(--border-subtle); background: ${item.key === 'C2' ? 'rgba(16, 185, 129, 0.08)' : 'transparent'};">
        <td style="padding: 10px 12px;">
          <strong class="model-name">${escapeHtml(item.name)}</strong>
          <div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(item.desc)}</div>
        </td>
        <td style="padding: 10px 12px; text-align: center; font-weight: 700;" class="cell-grounds">${groundsCount} 組</td>
        <td style="padding: 10px 12px;" class="cell-comm-prems">
          <span style="font-weight: 600;">${commPremises.length}件</span>
          <div style="font-size: 11px; color: #94a3b8;">${commPremises.join(', ')}</div>
        </td>
        <td style="padding: 10px 12px; text-align: center; font-weight: 600;" class="cell-prem-cuts">${premCutsCount} 件</td>
        <td style="padding: 10px 12px; text-align: center; font-weight: 600;" class="cell-rule-cuts">${ruleCutsCount} 件</td>
        <td style="padding: 10px 12px; text-align: center;" class="cell-r2-cut">
          ${r2StatusHtml}
        </td>
        <td style="padding: 10px 12px; text-align: center;" class="cell-r3-cut">
          ${r3StatusHtml}
        </td>
      </tr>
    `;
  });

  html += `
        </tbody>
      </table>
    </div>

    <!-- 2大分類パネル: 安定した知見 vs 解釈に依存する知見 -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
      <!-- 安定した知見 -->
      <div style="background: rgba(16, 185, 129, 0.06); border: 1px solid #10b981; border-radius: 10px; padding: 18px;" id="panelRobustFindings">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
          <span style="background: #10b981; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">普遍的成立</span>
          <h4 style="font-size: 15px; color: #6ee7b7; margin: 0;">🛡️ 安定した知見 (モデル内結果)</h4>
        </div>
        <p style="font-size: 12px; color: #cbd5e1; margin-bottom: 14px; line-height: 1.5;">
          登録済みモデル・複数解釈設定を通じて頑健に成立する論理構造です。<br>
          <span style="font-size: 11px; color: #94a3b8;">※「迂回経路の存在」は証明を追加しても崩れませんが、「単体遮断」「共通前提」は証明を足すと弱まりえます。</span>
        </p>
        <div style="display: flex; flex-direction: column; gap: 12px;">
  `;

  robustFindings.forEach(rf => {
    html += `
      <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 10px 12px;">
        <div style="font-weight: 700; color: #a7f3d0; font-size: 13px; margin-bottom: 4px;">${escapeHtml(rf.title)}</div>
        <div style="font-size: 12px; color: #e2e8f0; line-height: 1.5; margin-bottom: 6px;">${escapeHtml(rf.detail)}</div>
        <div style="font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between;">
          <span>📌 根拠: ${escapeHtml(rf.models)}</span>
          <span>📖 原典: ${escapeHtml(rf.source_ref)}</span>
        </div>
      </div>
    `;
  });

  html += `
        </div>
      </div>

      <!-- 解釈に依存する知見 -->
      <div style="background: rgba(245, 158, 11, 0.06); border: 1px solid #f59e0b; border-radius: 10px; padding: 18px;" id="panelInterpFindings">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
          <span style="background: #f59e0b; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">解釈依存</span>
          <h4 style="font-size: 15px; color: #fcd34d; margin: 0;">⚖️ 解釈に依存する知見 (モデル内結果)</h4>
        </div>
        <p style="font-size: 12px; color: #cbd5e1; margin-bottom: 14px; line-height: 1.5;">
          形式化における前提補完の採用基準や解釈設定によって成否・件数が変動する知見です。
        </p>
        <div style="display: flex; flex-direction: column; gap: 12px;">
  `;

  interpFindings.forEach(inf => {
    html += `
      <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 6px; padding: 10px 12px;">
        <div style="font-weight: 700; color: #fde68a; font-size: 13px; margin-bottom: 4px;">${escapeHtml(inf.title)}</div>
        <div style="font-size: 12px; color: #e2e8f0; line-height: 1.5; margin-bottom: 6px;">${escapeHtml(inf.detail)}</div>
        <div style="font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between;">
          <span>📌 根拠: ${escapeHtml(inf.models)}</span>
          <span>📖 原典: ${escapeHtml(inf.source_ref)}</span>
        </div>
      </div>
    `;
  });

  html += `
        </div>
      </div>
    </div>

    <!-- 手法の性質 (推論エンジンの前提条件) -->
    <div style="background: rgba(59, 130, 246, 0.06); border: 1px solid #3b82f6; border-radius: 10px; padding: 16px 18px; margin-bottom: 24px;" id="panelMethodProperties">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
        <span style="background: #2563eb; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">エンジンの前提</span>
        <h4 style="font-size: 14px; color: #93c5fd; margin: 0;">⚙️ 手法の性質 (推論エンジンの前提条件)</h4>
      </div>
      <p style="font-size: 12px; color: #cbd5e1; margin-bottom: 10px; line-height: 1.5;">
        スピノザの論証についての結果ではなく、<strong>推論エンジンの意味論（単調性診断意味論）自体の公理的性質</strong>です。
      </p>
      <div style="display: flex; flex-direction: column; gap: 10px;">
  `;

  methodProperties.forEach(mp => {
    html += `
      <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 6px; padding: 10px 12px;">
        <div style="font-weight: 700; color: #bfdbfe; font-size: 13px; margin-bottom: 4px;">${escapeHtml(mp.title)}</div>
        <div style="font-size: 12px; color: #e2e8f0; line-height: 1.5; margin-bottom: 4px;">${escapeHtml(mp.detail)}</div>
        <div style="font-size: 11px; color: #94a3b8;">
          <span>📌 位置づけ: ${escapeHtml(mp.models)} | ${escapeHtml(mp.source_ref)}</span>
        </div>
      </div>
    `;
  });

  html += `
      </div>
    </div>

    <!-- 詳しい集合一覧 (折りたたみ展開) -->
    <details style="background: rgba(15, 23, 42, 0.4); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;">
      <summary style="cursor: pointer; font-size: 13px; font-weight: 600; color: #cbd5e1;">
        📁 各モデルの最小支持根拠・遮断集合の全リストを展開する (v0.2 正式候補版)
      </summary>
      <div style="margin-top: 12px; font-size: 12px;">
  `;

  modelList.forEach(item => {
    const m = item.model;
    const gList = m.grounds || [];
    const pCuts = m.premise_cuts || [];
    const rCuts = m.rule_cuts || [];

    html += `
      <div style="margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--border-subtle);">
        <h5 style="color: #f1f5f9; font-size: 13px; margin-bottom: 6px;">${escapeHtml(item.name)}:</h5>
        <div><strong>最小支持根拠 (${gList.length}組):</strong></div>
        <ul style="padding-left: 20px; color: #93c5fd; margin: 4px 0 8px;">
          ${gList.map((g, idx) => `
            <li>[組 ${idx + 1}] {${g.join(', ')}} (前提数: ${g.length})</li>
          `).join('')}
        </ul>
        <div style="margin-bottom: 4px;"><strong>前提最小遮断集合 (${pCuts.length}件):</strong> ${pCuts.map(c => `{${c.join(', ')}}`).join(', ') || 'なし'}</div>
        <div><strong>規則最小遮断集合 (${rCuts.length}件):</strong> ${rCuts.map(c => `{${c.join(', ')}}`).join(', ') || 'なし'}</div>
      </div>
    `;
  });

  html += `
      </div>
    </details>

    <!-- 免責・注意事項 -->
    <div style="font-size: 12px; color: var(--text-muted); line-height: 1.5; padding: 10px 14px; background: rgba(15, 23, 42, 0.3); border-radius: 6px;">
      ⚠️ <strong>留保事項:</strong>
      本画面に掲載された結果は、モデル化された有限推論規則の形式的計算結果であり、「新発見」を主張するものではありません。学術的新規性は未確認です。
    </div>
  `;

  elements.spinozaResearchContainer.innerHTML = html;
}

function renderGeometryResearch(data) {
  const tri = data.triangle || {};
  const angles = tri.angles || {};
  const thetaO = angles.theta_O || {};
  const thetaP = angles.theta_P || {};
  const thetaQ = angles.theta_Q || {};
  const angleSum = angles.angle_sum || {};
  const defect = angles.defect || {};
  const conds = data.conditions_breakdown || {};

  let html = `
    <!-- 頂点と厳密式サマリー -->
    <div style="display: grid; grid-template-columns: 320px 1fr; gap: 24px; align-items: start; margin-bottom: 24px;">
      
      <!-- SVG描画 -->
      <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid var(--border-subtle); border-radius: 10px; padding: 16px; text-align: center;">
        <svg viewBox="0 0 300 300" style="width: 100%; max-width: 280px; height: auto; display: block; margin: 0 auto;">
          <!-- 単位開円板 -->
          <circle cx="150" cy="150" r="120" stroke="#475569" stroke-width="2" fill="rgba(15, 23, 42, 0.6)" />
          
          <!-- 直交座標軸 (参考) -->
          <line x1="30" y1="150" x2="270" y2="150" stroke="#334155" stroke-width="1" stroke-dasharray="3,3" />
          <line x1="150" y1="30" x2="150" y2="270" stroke="#334155" stroke-width="1" stroke-dasharray="3,3" />

          <!-- 三角形 OPQ 領域 (塗りつぶし) -->
          <path d="M 150,150 L 210,150 A 174.9 174.9 0 0 0 150,90 Z" fill="rgba(16, 185, 129, 0.2)" />

          <!-- 辺 OP (直線) -->
          <line x1="150" y1="150" x2="210" y2="150" stroke="#10b981" stroke-width="2.5" />
          <!-- 辺 OQ (直線) -->
          <line x1="150" y1="150" x2="150" y2="90" stroke="#10b981" stroke-width="2.5" />
          <!-- 辺 PQ (直交円弧: 半径174.9) -->
          <path d="M 210,150 A 174.9 174.9 0 0 0 150,90" fill="none" stroke="#38bdf8" stroke-width="2.5" />

          <!-- 頂点マーカー -->
          <circle cx="150" cy="150" r="4.5" fill="#f8fafc" />
          <circle cx="210" cy="150" r="4.5" fill="#f8fafc" />
          <circle cx="150" cy="90" r="4.5" fill="#f8fafc" />

          <!-- 頂点ラベル -->
          <text x="135" y="168" fill="#f8fafc" font-size="12" font-weight="700">O(0,0)</text>
          <text x="215" y="168" fill="#f8fafc" font-size="12" font-weight="700">P(1/2,0)</text>
          <text x="110" y="86" fill="#f8fafc" font-size="12" font-weight="700">Q(0,1/2)</text>
        </svg>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 10px;">
          ポアンカレ円板モデル $\\mathbb{D}$ 上の測地三角形 $\\triangle OPQ$<br>
          (OP, OQ: 直径線分, PQ: 境界直交円弧)
        </div>
      </div>

      <!-- 厳密式と参考値 -->
      <div>
        <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 16px; margin-bottom: 16px;">
          <h4 style="font-size: 14px; color: #34d399; margin-bottom: 12px;">📐 固定三点と内角の厳密値</h4>
          <ul style="list-style: none; padding: 0; font-size: 13px; line-height: 1.8;">
            <li><strong>固定三点:</strong> O = (0, 0), P = (1/2, 0), Q = (0, 1/2)</li>
            <li><strong>内角 $\\theta_O$:</strong> <code>${escapeHtml(thetaO.exact || 'π/2')}</code> (${thetaO.deg_approx || 90.0}°)</li>
            <li><strong>内角 $\\theta_P$:</strong> <code>${escapeHtml(thetaP.exact || 'arctan(3/5)')}</code> (約 ${thetaP.deg_approx || 30.9638}°)</li>
            <li><strong>内角 $\\theta_Q$:</strong> <code>${escapeHtml(thetaQ.exact || 'arctan(3/5)')}</code> (約 ${thetaQ.deg_approx || 30.9638}°)</li>
          </ul>
        </div>

        <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid #10b981; border-radius: 8px; padding: 16px;">
          <h4 style="font-size: 14px; color: #6ee7b7; margin-bottom: 8px;">✨ 内角和と欠損角 (Defect)</h4>
          <div style="font-size: 15px; font-weight: 700; color: #ffffff; margin-bottom: 4px;">
            内角和の厳密式: <code>${escapeHtml(angleSum.exact_form || 'pi/2 + 2*arctan(3/5)')}</code>
          </div>
          <div style="font-size: 16px; color: #34d399; font-weight: 700; margin-bottom: 8px;">
            参考値: <strong>${escapeHtml(angleSum.deg_reference_label || '約151.9275度')}</strong> (&lt; 180°)
          </div>
          <div style="font-size: 13px; color: var(--text-secondary);">
            欠損角 (Defect $\\delta$): <code>${escapeHtml(defect.exact_form || 'arctan(8/15)')}</code> (約 ${defect.deg_approx || 28.0725}° &gt; 0)
          </div>
        </div>
      </div>
    </div>

    <!-- 条件の区別 (コード検査条件 vs 文献依拠条件) -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
      <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 16px;">
        <h4 style="font-size: 13px; color: #38bdf8; margin-bottom: 10px;">🧪 コードで検査した条件 (有理数論的検証)</h4>
        <ul style="font-size: 12px; color: var(--text-secondary); line-height: 1.6; padding-left: 18px;">
          ${(conds.code_verified_conditions || []).map(c => `<li>${escapeHtml(c)}</li>`).join('')}
        </ul>
      </div>
      <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 16px;">
        <h4 style="font-size: 13px; color: #fbbf24; margin-bottom: 10px;">📚 文献に依拠する条件 (数学的理論保証)</h4>
        <ul style="font-size: 12px; color: var(--text-secondary); line-height: 1.6; padding-left: 18px;">
          ${(conds.literature_reliant_conditions || []).map(c => `<li>${escapeHtml(c)}</li>`).join('')}
        </ul>
      </div>
    </div>

    <div style="font-size: 12px; color: var(--text-muted); line-height: 1.5; padding: 10px 14px; background: rgba(15, 23, 42, 0.3); border-radius: 6px;">
      📌 <strong>検証の意義:</strong>
      本実験は、双曲幾何モデルにおいて内角和が180度を下回る具体的反例を有理数厳密論理で確認した「既知の結果の再現」です。
      固定背景公理（合同・順序・アルキメデス公理）の成立を前提としており、幾何学の数学的真理性を本エンジン独自で新規証明したものではありません。
    </div>
  `;

  elements.geometryResearchContainer.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', () => {
  // Mode Tabs
  elements.tabViewInsights.addEventListener('click', () => switchView('insights'));
  elements.tabViewGraph.addEventListener('click', () => switchView('graph'));
  elements.tabViewBenchmark.addEventListener('click', () => switchView('benchmark'));
  if (elements.tabViewResearch) {
    elements.tabViewResearch.addEventListener('click', () => switchView('research'));
  }

  // Insights System Select
  elements.insightsSystemButtons.addEventListener('click', e => {
    const btn = e.target.closest('.sys-btn');
    if (!btn) return;
    state.currentSystem = btn.dataset.sys;
    state.currentScenario = null;
    loadInsights();
  });

  // Insights Scenario Select
  elements.scenarioSelect.addEventListener('change', e => {
    state.currentScenario = e.target.value;
    loadInsights();
  });

  // Switch to graph button from insights
  elements.btnSwitchToGraph.addEventListener('click', () => {
    switchView('graph');
  });

  // Graph System Pills
  elements.graphSystemTabs.addEventListener('click', e => {
    const btn = e.target.closest('.pill-btn');
    if (!btn) return;
    loadGraphData(btn.dataset.system);
  });

  // Graph Action buttons
  elements.btnApproveDefs.addEventListener('click', approveAllDefinitions);
  elements.btnInjectKant.addEventListener('click', injectKantCritique);
  elements.btnReset.addEventListener('click', resetSystem);

  // Inspector Buttons
  if (elements.btnTogglePremise) {
    elements.btnTogglePremise.addEventListener('click', toggleCurrentPremise);
  }
  document.querySelectorAll('.btn-toggle').forEach(btn => {
    btn.addEventListener('click', () => toggleNodeValue(btn.dataset.val));
  });
  elements.btnWhatIfFalse.addEventListener('click', runWhatIfFalse);
  elements.btnFindFrontier.addEventListener('click', findFrontier);
  elements.btnCloseSimResult.addEventListener('click', () => {
    elements.simulationResult.style.display = 'none';
  });

  // Modal
  elements.btnCloseModal.addEventListener('click', () => {
    elements.benchmarkModal.style.display = 'none';
  });

  // 初期画面の起動 (要件: 初期画面は「今回わかったこと」)
  switchView('graph');
});
