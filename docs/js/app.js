/**
 * App.js - Controlador de Interface para Atuária Quant (Mack & Chain Ladder)
 * Gerencia eventos de UI, tabelas dinâmicas, gráficos Plotly.js e exportação CSV.
 */

// Datasets pré-configurados
const PRESET_DATASETS = {
  default_5x5: {
    name: "Carteira Padrão (2020-2024)",
    description: "Triângulo simulado de 5 safras e 5 períodos de desenvolvimento (R$ mil)",
    originYears: ["2020", "2021", "2022", "2023", "2024"],
    devPeriods: ["Ano 1", "Ano 2", "Ano 3", "Ano 4", "Ano 5"],
    triangle: [
      [1000.0, 1450.0, 1740.0, 1914.0, 2010.0],
      [1150.0, 1690.0, 2030.0, 2235.0, null],
      [1220.0, 1805.0, 2185.0, null, null],
      [1350.0, 1990.0, null, null, null],
      [1480.0, null, null, null, null],
    ],
  },
  analytic_3x3: {
    name: "Benchmark Analítico 3x3",
    description: "Triângulo do artigo teórico e testes unitários para verificação exata",
    originYears: ["2022", "2023", "2024"],
    devPeriods: ["Dev 1", "Dev 2", "Dev 3"],
    triangle: [
      [1000.0, 1500.0, 1800.0],
      [1200.0, 1860.0, null],
      [1400.0, null, null],
    ],
  },
};

// Estado da Aplicação
let currentTriangle = JSON.parse(JSON.stringify(PRESET_DATASETS.default_5x5.triangle));
let currentOriginYears = [...PRESET_DATASETS.default_5x5.originYears];
let currentDevPeriods = [...PRESET_DATASETS.default_5x5.devPeriods];
let currentResults = null;
let activeTab = "triangle";

// Formatadores Numéricos
const formatCurrency = (val) => {
  if (val === null || val === undefined || isNaN(val)) return "-";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val);
};

const formatNumber = (val, decimals = 2) => {
  if (val === null || val === undefined || isNaN(val)) return "-";
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(val);
};

const formatPercent = (val) => {
  if (val === null || val === undefined || isNaN(val)) return "-";
  return `${formatNumber(val, 2)}%`;
};

// Inicialização ao carregar a página
document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();
  setupEventListeners();
  recalculateAndRender();
});

function setupEventListeners() {
  // Seletor de Dataset
  document.getElementById("dataset-select").addEventListener("change", (e) => {
    const val = e.target.value;
    if (val === "default_5x5") {
      loadPreset(PRESET_DATASETS.default_5x5);
    } else if (val === "analytic_3x3") {
      loadPreset(PRESET_DATASETS.analytic_3x3);
    } else if (val === "manual") {
      openManualEditor();
    }
  });

  // Parâmetros do Modelo
  document.getElementById("tail-factor-input").addEventListener("change", () => recalculateAndRender());
  document.getElementById("extrapolation-method").addEventListener("change", (e) => {
    const manualInput = document.getElementById("manual-sigma-wrapper");
    if (e.target.value === "manual") {
      manualInput.classList.remove("hidden");
    } else {
      manualInput.classList.add("hidden");
    }
    recalculateAndRender();
  });
  document.getElementById("manual-sigma-input").addEventListener("change", () => recalculateAndRender());
  document.getElementById("confidence-level").addEventListener("change", () => recalculateAndRender());

  // Abas de visualização
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => {
        b.classList.remove("border-blue-500", "text-blue-400", "bg-blue-600/10");
        b.classList.add("border-transparent", "text-slate-400");
      });
      btn.classList.add("border-blue-500", "text-blue-400", "bg-blue-600/10");
      btn.classList.remove("border-transparent", "text-slate-400");

      activeTab = btn.dataset.tab;
      document.querySelectorAll(".tab-pane").forEach((p) => p.classList.add("hidden"));
      document.getElementById(`tab-content-${activeTab}`).classList.remove("hidden");

      if (activeTab === "charts") {
        setTimeout(renderCharts, 50);
      }
    });
  });

  // Upload CSV
  const fileInput = document.getElementById("csv-file-input");
  fileInput.addEventListener("change", handleCsvUpload);

  // Botões de Ação
  document.getElementById("btn-export-csv").addEventListener("click", exportResultsCsv);
  document.getElementById("btn-copy-summary").addEventListener("click", copyExecutiveSummary);
  document.getElementById("btn-save-manual").addEventListener("click", saveManualTable);
}

function loadPreset(preset) {
  currentTriangle = JSON.parse(JSON.stringify(preset.triangle));
  currentOriginYears = [...preset.originYears];
  currentDevPeriods = [...preset.devPeriods];
  document.getElementById("manual-editor-container").classList.add("hidden");
  recalculateAndRender();
}

function recalculateAndRender() {
  const tailFactor = parseFloat(document.getElementById("tail-factor-input").value) || 1.0;
  const extrapMethod = document.getElementById("extrapolation-method").value;
  const manualSigma = extrapMethod === "manual" ? parseFloat(document.getElementById("manual-sigma-input").value) : null;

  try {
    const engine = new MackChainLadderEngine(currentTriangle, currentOriginYears, currentDevPeriods, tailFactor);
    currentResults = engine.calculateFullResults(extrapMethod, manualSigma);

    // Ajuste de nível de confiança (Z-score)
    const confLevel = document.getElementById("confidence-level").value;
    let zScore = 1.96;
    if (confLevel === "90") zScore = 1.645;
    else if (confLevel === "95") zScore = 1.96;
    else if (confLevel === "99") zScore = 2.576;

    currentResults.totals.zScore = zScore;
    currentResults.totals.ciLower = Math.max(0, currentResults.totals.totalIbnr - zScore * currentResults.totals.totalSe);
    currentResults.totals.ciUpper = currentResults.totals.totalIbnr + zScore * currentResults.totals.totalSe;

    renderKpiCards();
    renderTables();
    if (activeTab === "charts") {
      renderCharts();
    }
    lucide.createIcons();
  } catch (err) {
    console.error("Erro no cálculo atuarial:", err);
    alert(`Erro ao calcular modelo atuarial: ${err.message}`);
  }
}

// Renderização dos KPIs Atuariais
function renderKpiCards() {
  const totals = currentResults.totals;

  document.getElementById("kpi-ultimate").innerText = formatCurrency(totals.totalUltimate);
  document.getElementById("kpi-ibnr").innerText = formatCurrency(totals.totalIbnr);
  document.getElementById("kpi-se").innerText = formatCurrency(totals.totalSe);
  document.getElementById("kpi-cv").innerText = formatPercent(totals.totalCv);

  // Subdetalhes
  const obsGrowth = totals.totalObserved > 0 ? ((totals.totalUltimate / totals.totalObserved - 1) * 100).toFixed(1) : "0.0";
  document.getElementById("kpi-ultimate-sub").innerText = `Observado: ${formatCurrency(totals.totalObserved)} (+${obsGrowth}%)`;
  document.getElementById("kpi-ibnr-sub").innerText = `Reserva Requerida da Carteira`;
  document.getElementById("kpi-se-sub").innerText = `MSE: ${formatNumber(totals.totalMse, 1)}`;
  document.getElementById("kpi-cv-sub").innerText = totals.totalCv < 5 ? "Baixa Incerteza Relativa" : "Volatilidade Moderada/Alta";

  // Decomposição de Risco
  document.getElementById("kpi-proc-pct").innerText = `${formatNumber(totals.procVarPct, 1)}%`;
  document.getElementById("kpi-param-pct").innerText = `${formatNumber(totals.paramVarPct, 1)}%`;
  document.getElementById("kpi-proc-bar").style.width = `${Math.min(100, totals.procVarPct)}%`;
  document.getElementById("kpi-param-bar").style.width = `${Math.min(100, totals.paramVarPct)}%`;

  // Intervalo de Confiança / VaR
  document.getElementById("kpi-ci-range").innerText = `[ ${formatCurrency(totals.ciLower)} ; ${formatCurrency(totals.ciUpper)} ]`;
  document.getElementById("kpi-var-amount").innerText = formatCurrency(totals.ciUpper);
}

// Renderização das Tabelas
function renderTables() {
  renderRunOffTriangleTable();
  renderFactorsTable();
  renderIbnrMackSummaryTable();
  renderCovarianceTable();
}

function renderRunOffTriangleTable() {
  const container = document.getElementById("triangle-table-container");
  const orig = currentResults.triangleOriginal;
  const proj = currentResults.projectedTriangle;
  const origins = currentResults.originYears;
  const devs = currentResults.devPeriods;

  let html = `<table class="w-full text-left table-actuarial border-collapse font-mono-num text-xs">`;
  html += `<thead><tr><th class="sticky left-0 bg-slate-900 z-10">Ano Ocorrência</th>`;
  devs.forEach((d) => (html += `<th class="text-right">${d}</th>`));
  html += `</tr></thead><tbody>`;

  origins.forEach((ano, i) => {
    html += `<tr><td class="font-semibold text-slate-200 sticky left-0 bg-slate-900/90 z-10">${ano}</td>`;
    devs.forEach((_, j) => {
      const origVal = orig[i][j];
      const projVal = proj[i][j];

      if (origVal !== null) {
        html += `<td class="text-right cell-observed">${formatNumber(origVal, 2)}</td>`;
      } else if (projVal !== null) {
        html += `<td class="text-right cell-projected" title="Valor Projetado via Chain Ladder">
                  ${formatNumber(projVal, 2)} <span class="badge-proj">proj</span>
                 </td>`;
      } else {
        html += `<td class="text-right cell-empty">-</td>`;
      }
    });
    html += `</tr>`;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

function renderFactorsTable() {
  const container = document.getElementById("factors-table-container");
  const ind = currentResults.individualFactors;
  const cum = currentResults.cumulativeFactors;
  const sig = currentResults.sigmaSquared;

  let html = `<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">`;

  // Tabela 1: Transições Individuais
  html += `<div class="glass-panel p-4 rounded-xl">
    <h4 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
      <i data-lucide="git-commit" class="w-4 h-4 text-blue-400"></i> Fatores Individuais de Desenvolvimento (f_j) e Variância de Mack
    </h4>
    <table class="w-full text-left table-actuarial font-mono-num text-xs">
      <thead>
        <tr>
          <th>Transição</th>
          <th class="text-right">Fator f_j</th>
          <th class="text-right">sigma_j^2</th>
          <th class="text-right">sigma_j (DP)</th>
        </tr>
      </thead>
      <tbody>`;

  ind.names.forEach((name, idx) => {
    html += `<tr>
      <td class="text-slate-300 font-semibold">${name}</td>
      <td class="text-right text-blue-400 font-bold">${formatNumber(ind.values[idx], 4)}</td>
      <td class="text-right text-slate-300">${formatNumber(sig.values[idx], 4)}</td>
      <td class="text-right text-amber-400">${formatNumber(sig.stdDevs[idx], 4)}</td>
    </tr>`;
  });

  html += `</tbody></table></div>`;

  // Tabela 2: Fatores Acumulados (CDF)
  html += `<div class="glass-panel p-4 rounded-xl">
    <h4 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
      <i data-lucide="layers" class="w-4 h-4 text-emerald-400"></i> Fatores Acumulados até o Ultimate (CDF - F_j)
    </h4>
    <table class="w-full text-left table-actuarial font-mono-num text-xs">
      <thead>
        <tr>
          <th>Período</th>
          <th class="text-right">Fator CDF (F_j)</th>
          <th class="text-right">% Incorrido Implícito</th>
        </tr>
      </thead>
      <tbody>`;

  cum.periods.forEach((period, idx) => {
    const Fj = cum.values[idx];
    const pctIncurred = Fj > 0 ? (1.0 / Fj) * 100 : 0;
    html += `<tr>
      <td class="text-slate-300 font-semibold">${period}</td>
      <td class="text-right text-emerald-400 font-bold">${formatNumber(Fj, 4)}</td>
      <td class="text-right text-slate-400">${formatPercent(pctIncurred)}</td>
    </tr>`;
  });

  html += `</tbody></table></div></div>`;
  container.innerHTML = html;
}

function renderIbnrMackSummaryTable() {
  const container = document.getElementById("ibnr-mack-table-container");
  const records = currentResults.originSummary;
  const totals = currentResults.totals;

  let html = `<table class="w-full text-left table-actuarial font-mono-num text-xs border-collapse">`;
  html += `<thead>
    <tr>
      <th class="sticky left-0 bg-slate-900 z-10">Safra</th>
      <th class="text-right">Último Obs.</th>
      <th class="text-right">Fator F_j</th>
      <th class="text-right">Ultimate (Final)</th>
      <th class="text-right">Provisão IBNR</th>
      <th class="text-right">Risco Processo</th>
      <th class="text-right">Risco Parâmetro</th>
      <th class="text-right">Erro Padrão (s.e.)</th>
      <th class="text-right">CV (%)</th>
    </tr>
  </thead><tbody>`;

  records.forEach((r) => {
    html += `<tr>
      <td class="font-semibold text-slate-200 sticky left-0 bg-slate-900/90 z-10">${r.originYear}</td>
      <td class="text-right">${formatCurrency(r.lastObserved)}</td>
      <td class="text-right text-slate-300">${formatNumber(r.factorF, 4)}</td>
      <td class="text-right text-blue-300 font-medium">${formatCurrency(r.ultimate)}</td>
      <td class="text-right text-emerald-400 font-bold">${formatCurrency(r.ibnr)}</td>
      <td class="text-right text-slate-400">${formatNumber(r.processVar, 1)}</td>
      <td class="text-right text-slate-400">${formatNumber(r.parameterVar, 1)}</td>
      <td class="text-right text-amber-300 font-semibold">${formatCurrency(r.se)}</td>
      <td class="text-right text-slate-300">${formatPercent(r.cv)}</td>
    </tr>`;
  });

  // Linha de Totais da Carteira
  html += `<tr class="bg-blue-950/40 border-t-2 border-blue-500/50 font-bold">
    <td class="text-blue-300 sticky left-0 bg-blue-950 z-10 uppercase tracking-wider">TOTAL CARTEIRA</td>
    <td class="text-right text-slate-100">${formatCurrency(totals.totalObserved)}</td>
    <td class="text-right text-blue-300">${formatNumber(totals.avgFactorF, 4)}</td>
    <td class="text-right text-blue-400">${formatCurrency(totals.totalUltimate)}</td>
    <td class="text-right text-emerald-400 text-sm">${formatCurrency(totals.totalIbnr)}</td>
    <td class="text-right text-slate-300">${formatNumber(totals.totalProcVar, 1)}</td>
    <td class="text-right text-slate-300">${formatNumber(totals.totalParamVar, 1)}</td>
    <td class="text-right text-amber-400 text-sm">${formatCurrency(totals.totalSe)}</td>
    <td class="text-right text-blue-300">${formatPercent(totals.totalCv)}</td>
  </tr>`;

  html += `</tbody></table>`;
  container.innerHTML = html;
}

function renderCovarianceTable() {
  const container = document.getElementById("covariance-table-container");
  const cov = currentResults.covarianceMatrix;
  const origins = currentResults.originYears;

  let html = `<div class="p-3 bg-slate-900/60 rounded-lg mb-3 text-xs text-slate-400">
    <i data-lucide="info" class="w-3.5 h-3.5 inline mr-1 text-blue-400"></i>
    A diagonal principal exibe o <strong>MSE individual</strong> de cada safra. Os elementos fora da diagonal representam as <strong>covariâncias induzidas pelo risco de parâmetro compartilhado</strong> (Mack 1993, Teorema 2).
  </div>`;

  html += `<table class="w-full text-left table-actuarial font-mono-num text-xs border-collapse">`;
  html += `<thead><tr><th class="sticky left-0 bg-slate-900 z-10">Safra</th>`;
  origins.forEach((ano) => (html += `<th class="text-right">${ano}</th>`));
  html += `</tr></thead><tbody>`;

  origins.forEach((anoI, i) => {
    html += `<tr><td class="font-semibold text-slate-200 sticky left-0 bg-slate-900/90 z-10">${anoI}</td>`;
    origins.forEach((_, k) => {
      const val = cov[i][k];
      const isDiag = i === k;
      const textClass = isDiag ? "text-amber-400 font-bold bg-amber-950/20" : val > 0 ? "text-blue-300" : "text-slate-500";
      html += `<td class="text-right ${textClass}">${formatNumber(val, 2)}</td>`;
    });
    html += `</tr>`;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

// Renderização dos Gráficos com Plotly.js
function renderCharts() {
  renderDevelopmentCurvesChart();
  renderIbnrDistributionChart();
  renderRiskDecompositionChart();
}

function renderDevelopmentCurvesChart() {
  const origins = currentResults.originYears;
  const devs = currentResults.devPeriods;
  const orig = currentResults.triangleOriginal;
  const proj = currentResults.projectedTriangle;

  const traces = [];
  const palette = ["#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4"];

  origins.forEach((ano, i) => {
    const color = palette[i % palette.length];
    const xHist = [];
    const yHist = [];
    const xProj = [];
    const yProj = [];

    let lastHistX = null;
    let lastHistY = null;

    devs.forEach((devLabel, j) => {
      if (orig[i][j] !== null) {
        xHist.push(devLabel);
        yHist.push(orig[i][j]);
        lastHistX = devLabel;
        lastHistY = orig[i][j];
      }
    });

    if (lastHistX !== null) {
      xProj.push(lastHistX);
      yProj.push(lastHistY);
    }

    devs.forEach((devLabel, j) => {
      if (orig[i][j] === null && proj[i][j] !== null) {
        xProj.push(devLabel);
        yProj.push(proj[i][j]);
      }
    });

    // Curva histórica observada (linha sólida)
    traces.push({
      x: xHist,
      y: yHist,
      name: `${ano} (Obs)`,
      mode: "lines+markers",
      line: { color: color, width: 2.5 },
      marker: { size: 6, color: color },
      hoverinfo: "name+x+y",
    });

    // Curva projetada Chain Ladder (linha tracejada)
    if (xProj.length > 1) {
      traces.push({
        x: xProj,
        y: yProj,
        name: `${ano} (Proj)`,
        mode: "lines+markers",
        line: { color: color, width: 2, dash: "dot" },
        marker: { size: 5, symbol: "diamond-open", color: color },
        hoverinfo: "name+x+y",
      });
    }
  });

  const layout = {
    title: { text: "Curvas de Desenvolvimento de Sinistros por Safra", font: { color: "#f8fafc", size: 14 } },
    paper_bgcolor: "#080c14",
    plot_bgcolor: "#0f172a",
    font: { color: "#94a3b8", family: "Plus Jakarta Sans, sans-serif" },
    xaxis: { gridcolor: "#1e293b", zerolinecolor: "#334155" },
    yaxis: {
      gridcolor: "#1e293b",
      zerolinecolor: "#334155",
      title: { text: "Sinistros Acumulados (R$)" },
      tickformat: ",.2f",
    },
    legend: { orientation: "h", y: -0.2, font: { size: 10, color: "#94a3b8" } },
    margin: { l: 60, r: 20, t: 40, b: 60 },
  };

  Plotly.react("chart-development-curves", traces, layout, { responsive: true, displayModeBar: false });
}

function renderIbnrDistributionChart() {
  const totals = currentResults.totals;
  const mean = totals.totalIbnr;
  const se = totals.totalSe;

  if (mean <= 0 || se <= 0) {
    document.getElementById("chart-ibnr-distribution").innerHTML =
      "<div class='p-8 text-center text-slate-500'>Sem dispersão calculável (se = 0 ou IBNR = 0).</div>";
    return;
  }

  // Gera pontos da curva normal
  const nPoints = 120;
  const xMin = Math.max(0, mean - 3.5 * se);
  const xMax = mean + 3.5 * se;
  const step = (xMax - xMin) / (nPoints - 1);

  const xVals = [];
  const yVals = [];
  const normalPdf = (x, mu, sigma) => {
    return (1 / (sigma * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * Math.pow((x - mu) / sigma, 2));
  };

  for (let i = 0; i < nPoints; i++) {
    const x = xMin + i * step;
    xVals.push(x);
    yVals.push(normalPdf(x, mean, se));
  }

  const traces = [
    {
      x: xVals,
      y: yVals,
      name: "Densidade de Mack",
      type: "scatter",
      mode: "lines",
      line: { color: "#3b82f6", width: 2.5 },
      fill: "tozeroy",
      fillcolor: "rgba(59, 130, 246, 0.15)",
    },
    {
      x: [mean, mean],
      y: [0, normalPdf(mean, mean, se) * 1.05],
      name: `IBNR Pontual: ${formatCurrency(mean)}`,
      mode: "lines",
      line: { color: "#10b981", width: 2.5, dash: "dash" },
    },
    {
      x: [totals.ciLower, totals.ciLower],
      y: [0, normalPdf(totals.ciLower, mean, se)],
      name: `Limite Inf (${totals.zScore === 1.96 ? "95%" : "IC"}): ${formatCurrency(totals.ciLower)}`,
      mode: "lines",
      line: { color: "#f59e0b", width: 1.5, dash: "dot" },
    },
    {
      x: [totals.ciUpper, totals.ciUpper],
      y: [0, normalPdf(totals.ciUpper, mean, se)],
      name: `VaR (${totals.zScore === 1.96 ? "95%" : "IC"}): ${formatCurrency(totals.ciUpper)}`,
      mode: "lines",
      line: { color: "#f59e0b", width: 1.5, dash: "dot" },
    },
  ];

  const layout = {
    title: { text: "Distribuição Estocástica de Incerteza da Provisão de IBNR", font: { color: "#f8fafc", size: 14 } },
    paper_bgcolor: "#080c14",
    plot_bgcolor: "#0f172a",
    font: { color: "#94a3b8", family: "Plus Jakarta Sans, sans-serif" },
    xaxis: { gridcolor: "#1e293b", title: { text: "Provisão de IBNR Requerida (R$)" }, tickformat: ",.0f" },
    yaxis: { gridcolor: "#1e293b", showticklabels: false, title: { text: "Densidade Probabilística" } },
    legend: { orientation: "h", y: -0.25, font: { size: 10, color: "#94a3b8" } },
    margin: { l: 40, r: 20, t: 40, b: 65 },
  };

  Plotly.react("chart-ibnr-distribution", traces, layout, { responsive: true, displayModeBar: false });
}

function renderRiskDecompositionChart() {
  const records = currentResults.originSummary.filter((r) => r.ibnr > 0);
  const origins = records.map((r) => r.originYear);
  const procVar = records.map((r) => r.processVar);
  const paramVar = records.map((r) => r.parameterVar);

  const traces = [
    {
      x: origins,
      y: procVar,
      name: "Risco de Processo (Aleatoriedade)",
      type: "bar",
      marker: { color: "#3b82f6" },
    },
    {
      x: origins,
      y: paramVar,
      name: "Risco de Parâmetro (Erro de Estimação)",
      type: "bar",
      marker: { color: "#f59e0b" },
    },
  ];

  const layout = {
    title: { text: "Decomposição da Variância de Predição por Safra", font: { color: "#f8fafc", size: 14 } },
    barmode: "stack",
    paper_bgcolor: "#080c14",
    plot_bgcolor: "#0f172a",
    font: { color: "#94a3b8", family: "Plus Jakarta Sans, sans-serif" },
    xaxis: { gridcolor: "#1e293b" },
    yaxis: { gridcolor: "#1e293b", title: { text: "Variância de Predição (MSE)" }, tickformat: ",.0f" },
    legend: { orientation: "h", y: -0.2, font: { size: 10, color: "#94a3b8" } },
    margin: { l: 60, r: 20, t: 40, b: 60 },
  };

  Plotly.react("chart-risk-decomposition", traces, layout, { responsive: true, displayModeBar: false });
}

// Editor Manual
function openManualEditor() {
  const container = document.getElementById("manual-editor-container");
  container.classList.remove("hidden");

  let html = `<div class="glass-panel p-5 rounded-xl border border-blue-500/30">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-bold text-white flex items-center gap-2">
        <i data-lucide="edit-3" class="w-4 h-4 text-blue-400"></i> Edição Manual de Triângulo de Sinistros
      </h3>
      <div class="flex gap-2">
        <button onclick="addOriginRow()" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700">+ Safra</button>
        <button onclick="addDevCol()" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700">+ Coluna</button>
      </div>
    </div>
    <div class="overflow-x-auto">
      <table id="table-manual-edit" class="w-full text-xs font-mono-num border-collapse">
        <thead><tr><th>Safra</th>`;

  currentDevPeriods.forEach((d, j) => {
    html += `<th class="p-1"><input type="text" value="${d}" class="w-20 bg-slate-900 border border-slate-700 rounded px-1 py-0.5 text-center text-slate-300 dev-header-input" data-col="${j}"></th>`;
  });
  html += `</tr></thead><tbody>`;

  currentTriangle.forEach((row, i) => {
    html += `<tr><td class="p-1"><input type="text" value="${currentOriginYears[i]}" class="w-20 bg-slate-900 border border-slate-700 rounded px-1 py-0.5 text-slate-300 origin-header-input" data-row="${i}"></td>`;
    row.forEach((val, j) => {
      const valStr = val !== null ? val : "";
      html += `<td class="p-1"><input type="number" step="any" value="${valStr}" placeholder="-" class="w-24 bg-slate-900 border border-slate-700 rounded px-1 py-0.5 text-right text-slate-100 cell-edit-input" data-row="${i}" data-col="${j}"></td>`;
    });
    html += `</tr>`;
  });

  html += `</tbody></table></div></div>`;
  document.getElementById("manual-table-slot").innerHTML = html;
  lucide.createIcons();
}

function addOriginRow() {
  const nextYear = currentOriginYears.length > 0 
    ? (parseInt(currentOriginYears[currentOriginYears.length - 1]) + 1 || `Ano ${currentOriginYears.length + 1}`) 
    : "Novo Ano";
  currentOriginYears.push(String(nextYear));
  const newRow = new Array(currentDevPeriods.length).fill(null);
  currentTriangle.push(newRow);
  openManualEditor();
}

function addDevCol() {
  const nextDev = `Dev ${currentDevPeriods.length + 1}`;
  currentDevPeriods.push(nextDev);
  currentTriangle.forEach(row => row.push(null));
  openManualEditor();
}

function saveManualTable() {
  const originInputs = document.querySelectorAll(".origin-header-input");
  const devInputs = document.querySelectorAll(".dev-header-input");
  const cellInputs = document.querySelectorAll(".cell-edit-input");

  const newOrigins = Array.from(originInputs).map((inp) => inp.value || `Ano`);
  const newDevs = Array.from(devInputs).map((inp) => inp.value || `Dev`);

  const nRows = newOrigins.length;
  const nCols = newDevs.length;
  const newTri = Array.from({ length: nRows }, () => new Array(nCols).fill(null));

  cellInputs.forEach((inp) => {
    const r = parseInt(inp.dataset.row);
    const c = parseInt(inp.dataset.col);
    const val = inp.value.trim();
    newTri[r][c] = val === "" ? null : parseFloat(val);
  });

  currentOriginYears = newOrigins;
  currentDevPeriods = newDevs;
  currentTriangle = newTri;

  recalculateAndRender();
}

// Upload CSV
function handleCsvUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (event) => {
    try {
      const content = event.target.result;
      parseCsvData(content);
      document.getElementById("dataset-select").value = "manual";
      recalculateAndRender();
    } catch (err) {
      alert(`Falha ao ler CSV: ${err.message}`);
    }
  };
  reader.readAsText(file);
}

function parseCsvData(text) {
  const lines = text
    .split(/\r\n|\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
  if (lines.length < 2) throw new Error("O CSV deve conter pelo menos 1 linha de cabeçalho e 1 linha de dados.");

  // Detecta separador (vírgula ou ponto-e-vírgula)
  const sep = lines[0].includes(";") ? ";" : ",";
  const headerParts = lines[0].split(sep).map((p) => p.replace(/"/g, "").trim());
  const devPeriods = headerParts.slice(1);

  const origins = [];
  const triangle = [];

  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(sep).map((p) => p.replace(/"/g, "").trim());
    origins.push(parts[0]);
    const row = [];
    for (let j = 1; j < parts.length; j++) {
      let rawVal = parts[j].replace(/\s/g, "");
      // Trata números brasileiros com vírgula decimal
      if (rawVal.includes(",") && !rawVal.includes(".")) {
        rawVal = rawVal.replace(",", ".");
      }
      const num = parseFloat(rawVal);
      row.push(isNaN(num) ? null : num);
    }
    // Garante comprimento
    while (row.length < devPeriods.length) row.push(null);
    triangle.push(row);
  }

  currentOriginYears = origins;
  currentDevPeriods = devPeriods;
  currentTriangle = triangle;
}

// Exportação CSV
function exportResultsCsv() {
  if (!currentResults) return;

  let csv = "RELATÓRIO ATUARIAL - MÉTODO CHAIN LADDER & MACK (1993)\r\n";
  csv += `Data de Emissão: ${new Date().toLocaleDateString("pt-BR")}\r\n\r\n`;

  // 1. Resumo de IBNR e Mack
  csv += "1. QUADRO RESUMO DE IBNR E INCERTEZA DE MACK\r\n";
  csv += "Safra;Ultimo Observado;Fator Fj;Sinistro Final Ultimate;Provisao IBNR;Risco Processo;Risco Parametro;Erro Padrao (se);CV (%)\r\n";
  currentResults.originSummary.forEach((r) => {
    csv += `${r.originYear};${r.lastObserved.toFixed(2)};${r.factorF.toFixed(4)};${r.ultimate.toFixed(2)};${r.ibnr.toFixed(2)};${r.processVar.toFixed(2)};${r.parameterVar.toFixed(2)};${r.se.toFixed(2)};${r.cv.toFixed(2)}%\r\n`;
  });
  const t = currentResults.totals;
  csv += `TOTAL;${t.totalObserved.toFixed(2)};${t.avgFactorF.toFixed(4)};${t.totalUltimate.toFixed(2)};${t.totalIbnr.toFixed(2)};${t.totalProcVar.toFixed(2)};${t.totalParamVar.toFixed(2)};${t.totalSe.toFixed(2)};${t.totalCv.toFixed(2)}%\r\n\r\n`;

  // 2. Fatores de Desenvolvimento
  csv += "2. FATORES DE DESENVOLVIMENTO INDIVIDUAIS (f_j)\r\n";
  csv += "Transicao;Fator f_j;sigma_j^2;sigma_j\r\n";
  currentResults.individualFactors.names.forEach((name, idx) => {
    csv += `${name};${currentResults.individualFactors.values[idx].toFixed(4)};${currentResults.sigmaSquared.values[idx].toFixed(4)};${currentResults.sigmaSquared.stdDevs[idx].toFixed(4)}\r\n`;
  });
  csv += "\r\n";

  // 3. Triângulo Projetado Completo
  csv += "3. TRIÂNGULO PROJETADO COMPLETO\r\n";
  csv += "Safra;" + currentResults.devPeriods.join(";") + "\r\n";
  currentResults.originYears.forEach((ano, i) => {
    const rowVals = currentResults.projectedTriangle[i].map((v) => (v !== null ? v.toFixed(2) : "-"));
    csv += `${ano};${rowVals.join(";")}\r\n`;
  });

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `relatorio_ibnr_mack_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Copiar Resumo Executivo
function copyExecutiveSummary() {
  if (!currentResults) return;
  const t = currentResults.totals;
  const text = `=== RESUMO ATUARIAL EXECUTIVO (MACK 1993) ===
• Sinistros Observados: R$ ${t.totalObserved.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
• Sinistros Finais Projetados (Ultimate): R$ ${t.totalUltimate.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
• Provisão de IBNR Requerida: R$ ${t.totalIbnr.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
• Erro Padrão Global (s.e.): R$ ${t.totalSe.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
• Coeficiente de Variação (CV): ${t.totalCv.toFixed(2)}%
• Decomposição: ${t.procVarPct.toFixed(1)}% Risco Processo | ${t.paramVarPct.toFixed(1)}% Risco Parâmetro
• Intervalo de Confiança Atuarial (95%): R$ ${t.ciLower.toLocaleString("pt-BR", { minimumFractionDigits: 2 })} a R$ ${t.ciUpper.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;

  navigator.clipboard.writeText(text).then(() => {
    alert("Resumo executivo copiado para a área de transferência!");
  });
}
