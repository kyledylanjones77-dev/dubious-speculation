// Dubious Speculation - Robinhood-style Trading App

let btcChartInstance = null;
let scoreChartInstance = null;
let econChartInstance = null;
let spChartInstance = null;
let mortgageChartInstance = null;

async function api(path) {
    try { const r = await fetch(path); return r.ok ? await r.json() : null; }
    catch(e) { console.error(path, e); return null; }
}

// Nav
function switchPage(name) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.bnav').forEach(b => b.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    document.querySelector(`.bnav[data-page="${name}"]`).classList.add('active');
    window.scrollTo(0, 0);
}

// Init
async function init() {
    const [comp, risk, fc, bands, macro, insights, accuracy, history, econ, friday, dash] = await Promise.all([
        api('/api/composite-score'),
        api('/api/risk-metric'),
        api('/api/forecasts'),
        api('/api/regression-bands/bitcoin'),
        api('/api/macro'),
        api('/api/cowen-insights'),
        api('/api/accuracy'),
        api('/api/btc-history'),
        api('/api/macro-economy'),
        api('/api/friday-predictions'),
        api('/api/dashboard'),
    ]);

    if (comp) renderComposite(comp);
    if (risk) renderRisk(risk);
    if (fc) { renderTicker(fc); renderBtcPage(fc.bitcoin); renderAssets(fc); }
    // BTC Dominance from faster dashboard endpoint, fallback to forecasts
    const domData = fc?.btc_dominance || {};
    if (dash?.btc_dominance) {
        domData.current_dominance = domData.current_dominance || dash.btc_dominance.btc_dominance;
        domData.eth_dominance = domData.eth_dominance || dash.btc_dominance.eth_dominance;
    }
    if (domData.current_dominance) renderDom(domData);

    if (bands) renderBands(bands);
    if (macro) renderMacro(macro);
    if (insights) renderLearn(insights);
    if (accuracy) renderAccuracy(accuracy);
    if (friday) renderFridayPredictions(friday);
    if (history) renderBtcChart(history);
    if (fc && fc.bitcoin && fc.bitcoin.score_components) renderScoreChart(fc.bitcoin.score_components);
    if (econ) renderMacroEconomy(econ);
}

// Composite
function renderComposite(d) {
    const s = d.composite_score || 0;
    const el = $('heroNum');
    el.textContent = (s > 0 ? '+' : '') + s.toFixed(0);
    el.style.color = s > 20 ? '#00c805' : s > 0 ? '#88cc00' : s > -20 ? '#ff8800' : '#ff5000';

    const badge = $('heroBadge');
    const isBull = s > 0;
    badge.textContent = d.interpretation?.split(' - ')[0] || (isBull ? 'BULLISH' : 'BEARISH');
    badge.className = 'hero-badge ' + (isBull ? 'badge-bull' : s === 0 ? 'badge-neutral' : 'badge-bear');

    $('heroSub').textContent = d.interpretation || '';
}

// Risk
function renderRisk(d) {
    const s = d.risk_score || 0.5;
    const el = $('riskNum');
    el.textContent = s.toFixed(3);
    el.style.color = s < 0.3 ? '#00c805' : s < 0.55 ? '#ffcc00' : s < 0.75 ? '#ff8800' : '#ff5000';

    $('riskDot').style.left = `calc(${s * 100}% - 7px)`;
    $('riskZone').textContent = d.zone || '';
    $('cPrice').textContent = fp(d.current_price);
    $('cFair').textContent = fp(d.fair_value);
    $('cDist').textContent = d.distance_from_fair || '';
    $('actionBar').textContent = d.action || '';
}

// Cycle
function renderCycle(d) {
    const pos = d.current_position;
    if (!pos) return;
    const pct = (pos.cycle_progress || 0) * 100;
    $('cycleNum').textContent = pct.toFixed(0) + '%';
    $('cycleFill').style.width = pct + '%';
    $('cycleDesc').textContent = (pos.cycle_year || '').split('(')[0].trim();
}

// Ticker
function renderTicker(fc) {
    const strip = $('tickerStrip');
    strip.innerHTML = '';
    const items = [
        { k: 'bitcoin', n: 'BTC', f: 'current_price' },
        { k: 'ethereum', n: 'ETH', f: 'current_price' },
        { k: 'gold', n: 'GOLD', f: 'current_price' },
        { k: 'silver', n: 'SILVER', f: 'current_price' },
        { k: 'uranium', n: 'URA', f: 'current_price' },
        { k: 'dogecoin', n: 'DOGE', f: 'current_price' },
        { k: 'btc_dominance', n: 'BTC.D', f: 'current_dominance' },
    ];
    for (const a of items) {
        const d = fc[a.k]; if (!d) continue;
        const price = d[a.f] || 0;
        const bias = d.bias || d.bias_vs_btc || '';
        const bull = /bull|long|accum/i.test(bias);
        const bear = /bear|cautious/i.test(bias);

        const div = document.createElement('div');
        div.className = 'tick';
        div.innerHTML = `
            <div class="tick-name">${a.n}</div>
            <div class="tick-price">${a.k === 'btc_dominance' ? price.toFixed(1) + '%' : fp(price)}</div>
            <div class="tick-bias ${bull ? 'up' : bear ? 'down' : 'flat'}">${(bias.split(' - ')[0] || '').substring(0, 15)}</div>
        `;
        strip.appendChild(div);
    }
}

// Dominance
function renderDom(d) {
    if (!d) return;
    $('domNum').textContent = (d.current_dominance || 0).toFixed(1) + '%';
    $('eDom').textContent = (d.eth_dominance || 0).toFixed(1) + '%';
    $('aSeason').textContent = d.alt_season_indicator || '-';
}

// BTC Page
function renderBtcPage(d) {
    if (!d) return;
    $('btcHeroPrice').textContent = fp(d.current_price);
    const bias = d.bias || '';
    const badge = $('btcHeroBias');
    badge.textContent = bias.split(' - ')[0] || bias;
    badge.className = 'hero-badge ' + (/bull/i.test(bias) ? 'badge-bull' : /bear|cautious/i.test(bias) ? 'badge-bear' : 'badge-neutral');

    // Forecasts
    const grid = $('btcFcGrid');
    grid.innerHTML = '';
    if (d.forecasts) {
        for (const [period, f] of Object.entries(d.forecasts)) {
            if (!f.low_estimate) continue;
            grid.innerHTML += `
                <div class="fc-cell">
                    <div class="fc-period">${period.replace('_', ' ')}</div>
                    <div class="fc-range">${fcp(f.low_estimate)}<br>-<br>${fcp(f.high_estimate)}</div>
                    <div class="fc-fair">Fair: ${fcp(f.fair_value_at_date)}</div>
                </div>`;
        }
    }

    // Indicators
    const ind = $('btcIndicators');
    ind.innerHTML = '';
    if (d.key_levels) {
        for (const [k, v] of Object.entries(d.key_levels)) {
            if (v) ind.innerHTML += `<div class="kv-row"><span class="kv-key">${fmtName(k)}</span><span class="kv-val">${fp(v)}</span></div>`;
        }
    }
    if (d.bull_market_support_band) {
        const bb = d.bull_market_support_band;
        ind.innerHTML += `<div class="kv-row"><span class="kv-key">20W SMA</span><span class="kv-val">${fp(bb.sma_20w)}</span></div>`;
        ind.innerHTML += `<div class="kv-row"><span class="kv-key">21W EMA</span><span class="kv-val">${fp(bb.ema_21w)}</span></div>`;
        const sigClass = /bull/i.test(bb.signal) ? 'sig-bull' : /bear/i.test(bb.signal) ? 'sig-bear' : 'sig-neutral';
        ind.innerHTML += `<div class="kv-signal ${sigClass}">${bb.signal}</div>`;
    }

    // Context
    const ctx = $('btcContext');
    ctx.innerHTML = '';
    if (d.cowen_context) {
        ctx.innerHTML = d.cowen_context.map(c => `<p>&#8226; ${c}</p>`).join('');
    }
}

// BTC Price Chart with Regression Bands
function renderBtcChart(data) {
    const canvas = $('btcChart');
    if (!canvas || !data.price_history) return;

    const prices = data.price_history;
    const bands = data.regression_bands || {};

    // Downsample for performance (every 7th point)
    const step = Math.max(1, Math.floor(prices.length / 100));
    const labels = [];
    const priceData = [];
    const fairData = [];
    const lowData = [];
    const highData = [];

    for (let i = 0; i < prices.length; i += step) {
        const p = prices[i];
        labels.push(new Date(p.timestamp).toLocaleDateString('en-US', { month: 'short', year: '2-digit' }));
        priceData.push(p.price);

        if (bands.fair && bands.fair[i]) fairData.push(bands.fair[i].price);
        if (bands.low && bands.low[i]) lowData.push(bands.low[i].price);
        if (bands.high && bands.high[i]) highData.push(bands.high[i].price);
    }

    if (btcChartInstance) btcChartInstance.destroy();

    btcChartInstance = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'BTC Price',
                    data: priceData,
                    borderColor: '#ffffff',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false,
                },
                {
                    label: 'Fair Value',
                    data: fairData,
                    borderColor: '#5ac8fa',
                    borderWidth: 1.5,
                    borderDash: [5, 3],
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false,
                },
                {
                    label: 'Low Band',
                    data: lowData,
                    borderColor: '#00c805',
                    borderWidth: 1,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false,
                },
                {
                    label: 'High Band',
                    data: highData,
                    borderColor: '#ff5000',
                    borderWidth: 1,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    display: true,
                    labels: { color: '#888', font: { size: 10 }, boxWidth: 12, padding: 8 },
                    position: 'top',
                },
                tooltip: {
                    backgroundColor: '#1e1e1e',
                    titleColor: '#fff',
                    bodyColor: '#c8c8c8',
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${fp(ctx.raw)}`,
                    },
                },
            },
            scales: {
                x: {
                    display: true,
                    ticks: { color: '#555', font: { size: 9 }, maxTicksLimit: 8 },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    display: true,
                    type: 'logarithmic',
                    ticks: {
                        color: '#555',
                        font: { size: 9 },
                        callback: v => v >= 1000 ? '$' + (v/1000).toFixed(0) + 'K' : '$' + v,
                    },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
            },
        },
    });
}

// Score Breakdown Radar/Bar Chart
function renderScoreChart(scores) {
    const canvas = $('scoreChart');
    if (!canvas || !scores) return;

    const labels = Object.keys(scores).map(fmtName);
    const values = Object.values(scores).map(v => (typeof v === 'number' ? v : v) * 100);
    const colors = values.map(v => v > 0 ? 'rgba(0,200,5,0.7)' : 'rgba(255,80,0,0.7)');

    if (scoreChartInstance) scoreChartInstance.destroy();

    scoreChartInstance = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderColor: colors.map(c => c.replace('0.7', '1')),
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1e1e1e',
                    callbacks: { label: ctx => `${ctx.raw > 0 ? '+' : ''}${ctx.raw.toFixed(0)}` },
                },
            },
            scales: {
                x: {
                    min: -100,
                    max: 100,
                    ticks: { color: '#555', font: { size: 9 } },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    ticks: { color: '#aaa', font: { size: 10 } },
                    grid: { display: false },
                },
            },
        },
    });
}

// Bands
function renderBands(d) {
    const el = $('btcBands');
    if (!el || !d.bands) return;
    el.innerHTML = '';
    const colors = { bottom: '#00c805', low: '#44dd44', mid_low: '#88cc00', fair: '#5ac8fa', mid_high: '#ffcc00', high: '#ff8800', top: '#ff5000' };
    for (const [name, price] of Object.entries(d.bands)) {
        const isActive = d.current_band?.toLowerCase().includes(name);
        el.innerHTML += `
            <div class="band-row ${isActive ? 'active' : ''}">
                <div class="band-dot" style="background:${colors[name] || '#fff'}"></div>
                <span class="band-name">${name.replace('_', ' ')}</span>
                <span class="band-price" style="color:${colors[name] || '#fff'}">${fp(price)}</span>
            </div>`;
    }
    el.innerHTML += `
        <div class="band-row" style="background:rgba(255,255,255,0.05)">
            <div class="band-dot" style="background:#fff"></div>
            <span class="band-name" style="color:#fff;font-weight:700">Current</span>
            <span class="band-price">${fp(d.current_price)}</span>
        </div>`;
}

// Assets
function renderAssets(fc) {
    const container = $('assetSwipe');
    container.innerHTML = '';
    const assets = [
        { k: 'ethereum', n: 'Ethereum (ETH)' },
        { k: 'gold', n: 'Gold (XAU)' },
        { k: 'silver', n: 'Silver (XAG)' },
        { k: 'uranium', n: 'Uranium (URA)' },
        { k: 'dogecoin', n: 'Dogecoin (DOGE)' },
        { k: 'btc_dominance', n: 'BTC Dominance' },
    ];

    for (const a of assets) {
        const d = fc[a.k]; if (!d) continue;
        const price = d.current_price || d.current_dominance || 0;
        const bias = d.bias || d.bias_vs_btc || '';
        const biasClass = /bull|long|accum/i.test(bias) ? 'badge-bull' : /bear|cautious/i.test(bias) ? 'badge-bear' : 'badge-neutral';

        let fcHtml = '';
        if (d.forecasts) {
            for (const [period, f] of Object.entries(d.forecasts)) {
                const label = period.replace('_', ' ');
                if (f.low_estimate) {
                    fcHtml += `<div class="ac-fc"><div style="color:var(--t3)">${label}</div><div class="fc-val">${fcp(f.low_estimate)}-${fcp(f.high_estimate)}</div></div>`;
                } else if (f.note) {
                    fcHtml += `<div class="ac-fc"><div style="color:var(--t3)">${label}</div><div style="font-size:9px;color:var(--t2)">${f.note.substring(0, 50)}</div></div>`;
                }
            }
        }

        let extra = '';
        if (d.gold_silver_ratio) extra += `<div>Gold/Silver Ratio: <b>${d.gold_silver_ratio.toFixed(1)}</b></div>`;
        if (d.eth_btc_ratio) extra += `<div>ETH/BTC: <b>${d.eth_btc_ratio.toFixed(6)}</b></div>`;
        if (d.alt_season_indicator) extra += `<div>Alt Season: <b>${d.alt_season_indicator}</b></div>`;

        // Add Cowen context if available
        let ctxHtml = '';
        if (d.cowen_context && d.cowen_context.length > 0) {
            ctxHtml = `<div class="ac-extra" style="margin-top:8px;border-top:1px solid var(--border);padding-top:8px">${d.cowen_context.slice(0, 2).map(c => `<div style="font-size:11px;color:var(--t2);margin-bottom:4px">&#8226; ${c}</div>`).join('')}</div>`;
        }

        container.innerHTML += `
            <div class="asset-card">
                <div class="ac-header"><div class="ac-name">${a.n}</div></div>
                <div class="ac-price">${a.k === 'btc_dominance' ? price.toFixed(1) + '%' : fp(price)}</div>
                <div class="ac-bias ${biasClass}">${(bias.split(' - ')[0] || bias).substring(0, 25)}</div>
                ${fcHtml ? `<div class="ac-forecasts">${fcHtml}</div>` : ''}
                ${extra ? `<div class="ac-extra">${extra}</div>` : ''}
                ${ctxHtml}
            </div>`;
    }
}

// Macro (DXY, Oil, Treasury - existing)
function renderMacro(d) {
    const el = $('macroList');
    if (!el) return;
    el.innerHTML = '';
    const info = {
        DXY: { n: 'US Dollar Index (DXY)', impact: v => v > 105 ? 'Headwind for crypto' : v < 95 ? 'Tailwind for crypto' : 'Neutral range' },
        Oil_WTI: { n: 'Oil (WTI Crude)', impact: v => v > 100 ? 'Business cycle risk!' : v > 80 ? 'Elevated' : 'Normal range' },
        Treasury_10Y: { n: '10Y Treasury Yield', impact: v => v > 4.5 ? 'Tight conditions' : v > 3 ? 'Moderate' : 'Loose conditions' },
    };
    for (const [k, meta] of Object.entries(info)) {
        const item = d[k]; if (!item || item.error) continue;
        el.innerHTML += `
            <div class="macro-item">
                <div class="macro-name">${meta.n}</div>
                <div class="macro-val">${(item.current || 0).toFixed(2)}</div>
                <div class="macro-impact">${meta.impact(item.current)}</div>
            </div>`;
    }
}

// ── Macro Economy (Unemployment, Claims, S&P, VIX) ──
function renderMacroEconomy(d) {
    // Hero: economy health score
    const assessment = d.assessment || {};
    const score = assessment.score || 0;
    const scoreEl = $('macroScore');
    if (scoreEl) {
        scoreEl.textContent = (score > 0 ? '+' : '') + score;
        scoreEl.style.color = score > 20 ? '#00c805' : score > 0 ? '#88cc00' : score > -20 ? '#ff8800' : '#ff5000';
    }
    const outlookEl = $('macroOutlook');
    if (outlookEl) {
        const outlook = assessment.outlook || 'UNKNOWN';
        outlookEl.textContent = outlook;
        const isGood = outlook.includes('HEALTHY') || outlook.includes('POSITIVE');
        outlookEl.className = 'hero-badge ' + (isGood ? 'badge-bull' : outlook.includes('MIXED') ? 'badge-neutral' : 'badge-bear');
    }

    // Signals list
    const sigEl = $('macroSignals');
    if (sigEl && assessment.signals) {
        sigEl.innerHTML = assessment.signals.map(s => `<p>&#8226; ${s}</p>`).join('');
    }

    // Economy indicator cards
    renderEconCards(d);

    // Unemployment + Claims chart
    renderEconChart(d);

    // S&P 500 chart
    renderSpChart(d);

    // Housing market
    if (d.housing) renderHousing(d.housing);
}

function renderEconCards(d) {
    const container = $('econCards');
    if (!container) return;
    container.innerHTML = '';

    const cards = [
        { key: 'unemployment_rate', fmt: v => v.toFixed(1) + '%', label: 'Unemployment Rate' },
        { key: 'initial_claims', fmt: v => v.toFixed(0) + 'K', label: 'Initial Claims (Weekly)' },
        { key: 'continuing_claims', fmt: v => (v / 1000).toFixed(2) + 'M', label: 'Continuing Claims' },
        { key: 'nonfarm_payrolls', fmt: v => (v / 1000).toFixed(1) + 'M jobs', label: 'Total Nonfarm Employment' },
        { key: 'vix', fmt: v => v.toFixed(1), label: 'VIX (Fear Index)' },
        { key: 'sp500', fmt: v => v.toLocaleString('en-US', {maximumFractionDigits:0}), label: 'S&P 500' },
    ];

    for (const c of cards) {
        const item = d[c.key];
        if (!item || item.error) continue;

        const val = item.current;
        const change = item.change !== undefined ? item.change : (item.change_pct !== undefined ? item.change_pct : null);
        const changeStr = change !== null ? (change > 0 ? '+' : '') + (c.key === 'sp500' ? change.toFixed(2) + '%' : c.key === 'nonfarm_payrolls' ? change.toFixed(0) + 'K jobs' : typeof change === 'number' ? change.toFixed(1) : change) : '';
        const changeColor = c.key === 'unemployment_rate' || c.key === 'initial_claims' || c.key === 'continuing_claims' || c.key === 'vix'
            ? (change > 0 ? '#ff5000' : change < 0 ? '#00c805' : '#888')  // higher = bad
            : (change > 0 ? '#00c805' : change < 0 ? '#ff5000' : '#888'); // higher = good

        let extra = '';
        if (item.ma_4week) extra = `<div style="font-size:10px;color:var(--t3)">4wk MA: ${item.ma_4week.toFixed(0)}K</div>`;
        if (item.signal) extra = `<div style="font-size:10px;color:var(--t3)">${item.signal}</div>`;
        if (item.above_sma_200 !== undefined) extra = `<div style="font-size:10px;color:${item.above_sma_200 ? '#00c805' : '#ff5000'}">${item.above_sma_200 ? 'Above' : 'Below'} 200-day SMA</div>`;

        container.innerHTML += `
            <div class="macro-item">
                <div class="macro-name">${c.label}</div>
                <div class="macro-val">${c.fmt(val)}</div>
                <div style="font-size:11px;color:${changeColor}">${changeStr}</div>
                ${extra}
                ${item.date ? `<div style="font-size:9px;color:var(--t3);margin-top:2px">${item.date}</div>` : ''}
            </div>`;
    }
}

function renderEconChart(d) {
    const canvas = $('econChart');
    if (!canvas) return;

    // Build dual-axis chart: Unemployment Rate (left) + Initial Claims (right)
    const unemp = d.unemployment_rate;
    const claims = d.initial_claims;
    if ((!unemp || !unemp.history) && (!claims || !claims.history)) return;

    // Use unemployment history as primary timeline
    const unempData = unemp && unemp.history ? unemp.history : [];
    const claimsData = claims && claims.history ? claims.history : [];

    // Downsample claims to ~60 points for readability
    const clStep = Math.max(1, Math.floor(claimsData.length / 60));
    const clLabels = [];
    const clValues = [];
    for (let i = 0; i < claimsData.length; i += clStep) {
        clLabels.push(claimsData[i].date.substring(5)); // MM-DD
        clValues.push(claimsData[i].value);
    }

    // Unemployment is monthly — use all points
    const uLabels = unempData.map(d => d.date.substring(0, 7)); // YYYY-MM
    const uValues = unempData.map(d => d.value);

    // Use claims timeline if more points, else unemployment
    const primaryLabels = clLabels.length > uLabels.length ? clLabels : uLabels;

    if (econChartInstance) econChartInstance.destroy();

    const datasets = [];
    if (uValues.length > 0) {
        datasets.push({
            label: 'Unemployment %',
            data: uValues,
            borderColor: '#ff8800',
            backgroundColor: 'rgba(255,136,0,0.1)',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: true,
            yAxisID: 'y',
        });
    }
    if (clValues.length > 0) {
        datasets.push({
            label: 'Initial Claims (K)',
            data: clValues,
            borderColor: '#5ac8fa',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.3,
            fill: false,
            yAxisID: 'y1',
        });
    }

    econChartInstance = new Chart(canvas, {
        type: 'line',
        data: {
            labels: datasets.length > 1 ? (clLabels.length >= uLabels.length ? clLabels : uLabels) : (uLabels.length ? uLabels : clLabels),
            datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    display: true,
                    labels: { color: '#888', font: { size: 10 }, boxWidth: 12, padding: 8 },
                },
                tooltip: {
                    backgroundColor: '#1e1e1e',
                    titleColor: '#fff',
                    bodyColor: '#c8c8c8',
                },
            },
            scales: {
                x: {
                    ticks: { color: '#555', font: { size: 9 }, maxTicksLimit: 8 },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    type: 'linear',
                    display: uValues.length > 0,
                    position: 'left',
                    title: { display: true, text: 'Unemployment %', color: '#ff8800', font: { size: 10 } },
                    ticks: { color: '#ff8800', font: { size: 9 } },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y1: {
                    type: 'linear',
                    display: clValues.length > 0,
                    position: 'right',
                    title: { display: true, text: 'Claims (K)', color: '#5ac8fa', font: { size: 10 } },
                    ticks: { color: '#5ac8fa', font: { size: 9 } },
                    grid: { drawOnChartArea: false },
                },
            },
        },
    });
}

function renderSpChart(d) {
    const canvas = $('spChart');
    if (!canvas) return;

    const sp = d.sp500;
    if (!sp || !sp.history || sp.history.length === 0) return;

    const history = sp.history;
    const step = Math.max(1, Math.floor(history.length / 80));
    const labels = [];
    const prices = [];

    for (let i = 0; i < history.length; i += step) {
        const p = history[i];
        labels.push(new Date(p.timestamp).toLocaleDateString('en-US', { month: 'short', year: '2-digit' }));
        prices.push(p.price);
    }

    // Calculate 200-day SMA overlay
    const smaData = [];
    if (history.length >= 200) {
        const allPrices = history.map(h => h.price);
        for (let i = 0; i < history.length; i += step) {
            if (i >= 199) {
                const slice = allPrices.slice(i - 199, i + 1);
                smaData.push(slice.reduce((a, b) => a + b, 0) / slice.length);
            } else {
                smaData.push(null);
            }
        }
    }

    if (spChartInstance) spChartInstance.destroy();

    const datasets = [
        {
            label: 'S&P 500',
            data: prices,
            borderColor: '#00c805',
            backgroundColor: 'rgba(0,200,5,0.08)',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: true,
        },
    ];

    if (smaData.length > 0) {
        datasets.push({
            label: '200-day SMA',
            data: smaData,
            borderColor: '#ff8800',
            borderWidth: 1.5,
            borderDash: [5, 3],
            pointRadius: 0,
            tension: 0.3,
            fill: false,
        });
    }

    spChartInstance = new Chart(canvas, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    display: true,
                    labels: { color: '#888', font: { size: 10 }, boxWidth: 12, padding: 8 },
                },
                tooltip: {
                    backgroundColor: '#1e1e1e',
                    titleColor: '#fff',
                    bodyColor: '#c8c8c8',
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${ctx.raw ? ctx.raw.toLocaleString('en-US', {maximumFractionDigits:0}) : '-'}`,
                    },
                },
            },
            scales: {
                x: {
                    ticks: { color: '#555', font: { size: 9 }, maxTicksLimit: 8 },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
                y: {
                    ticks: {
                        color: '#555',
                        font: { size: 9 },
                        callback: v => v >= 1000 ? (v/1000).toFixed(1) + 'K' : v,
                    },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                },
            },
        },
    });
}

// Housing Market
function renderHousing(housing) {
    if (!housing) return;

    // Score & outlook
    const assessment = housing.assessment || {};
    const scoreEl = $('housingScore');
    if (scoreEl) {
        const s = assessment.score || 0;
        scoreEl.textContent = (s > 0 ? '+' : '') + s;
        scoreEl.style.color = s > 10 ? '#00c805' : s > -5 ? '#ff8800' : '#ff5000';
    }
    const outlookEl = $('housingOutlook');
    if (outlookEl) {
        outlookEl.textContent = assessment.outlook || '-';
        outlookEl.style.color = assessment.outlook === 'HEALTHY' ? '#00c805' : assessment.outlook === 'MIXED' ? '#ffcc00' : '#ff5000';
    }

    // Signals
    const sigEl = $('housingSignals');
    if (sigEl && assessment.signals) {
        sigEl.innerHTML = assessment.signals.map(s => `<p>&#8226; ${s}</p>`).join('');
    }

    // Mortgage rate chart
    const mr = housing.mortgage_rate;
    if (mr && mr.history) {
        const canvas = $('mortgageChart');
        if (canvas) {
            const step = Math.max(1, Math.floor(mr.history.length / 80));
            const labels = [];
            const values = [];
            for (let i = 0; i < mr.history.length; i += step) {
                labels.push(mr.history[i].date.substring(0, 7));
                values.push(mr.history[i].value);
            }

            if (mortgageChartInstance) mortgageChartInstance.destroy();
            mortgageChartInstance = new Chart(canvas, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: '30-Year Mortgage Rate %',
                        data: values,
                        borderColor: '#ff8800',
                        backgroundColor: 'rgba(255,136,0,0.08)',
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.3,
                        fill: true,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: true, labels: { color: '#888', font: { size: 10 }, boxWidth: 12 } },
                        tooltip: { backgroundColor: '#1e1e1e', titleColor: '#fff', bodyColor: '#c8c8c8' },
                    },
                    scales: {
                        x: { ticks: { color: '#555', font: { size: 9 }, maxTicksLimit: 8 }, grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { ticks: { color: '#555', font: { size: 9 }, callback: v => v.toFixed(1) + '%' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    },
                },
            });
        }
    }

    // Housing indicator cards
    const container = $('housingCards');
    if (!container) return;
    container.innerHTML = '';

    const cards = [
        { key: 'mortgage_rate', fmt: v => v.toFixed(2) + '%', label: '30-Year Mortgage' },
        { key: 'median_home_price', fmt: v => '$' + (v/1000).toFixed(0) + 'K', label: 'Median Home Price' },
        { key: 'housing_starts', fmt: v => v.toFixed(0) + 'K', label: 'Housing Starts (SAAR)' },
        { key: 'building_permits', fmt: v => v.toFixed(0) + 'K', label: 'Building Permits (SAAR)' },
        { key: 'existing_home_sales', fmt: v => v.toFixed(2) + 'M', label: 'Existing Home Sales' },
        { key: 'months_supply', fmt: v => v.toFixed(1) + ' mo', label: 'Months of Supply' },
        { key: 'home_price_index', fmt: v => v.toFixed(1), label: 'Case-Shiller Index' },
    ];

    for (const c of cards) {
        const item = housing[c.key];
        if (!item || item.error) continue;

        const changeStr = item.change !== undefined ? (item.change > 0 ? '+' : '') + item.change.toFixed(2) : '';
        const yoyStr = item.yoy_pct !== null && item.yoy_pct !== undefined ? `YoY: ${item.yoy_pct > 0 ? '+' : ''}${item.yoy_pct}%` : '';
        // For mortgage/supply: higher = worse. For starts/sales/permits/prices: higher = better
        const invertColor = c.key === 'mortgage_rate' || c.key === 'months_supply';
        const changeColor = invertColor
            ? (item.change > 0 ? '#ff5000' : item.change < 0 ? '#00c805' : '#888')
            : (item.change > 0 ? '#00c805' : item.change < 0 ? '#ff5000' : '#888');

        container.innerHTML += `
            <div class="macro-item">
                <div class="macro-name">${c.label}</div>
                <div class="macro-val">${c.fmt(item.current)}</div>
                <div style="font-size:11px;color:${changeColor}">${changeStr}</div>
                ${yoyStr ? `<div style="font-size:10px;color:var(--t3);margin-top:2px">${yoyStr}</div>` : ''}
                ${item.date ? `<div style="font-size:9px;color:var(--t3);margin-top:2px">${item.date}</div>` : ''}
            </div>`;
    }
}

// Learn
function renderLearn(d) {
    if (d.transcript_stats) {
        const s = d.transcript_stats;
        $('kVideos').textContent = s.total_transcripts || '-';
        $('kWords').textContent = fn(s.total_words || 0);
        $('kHours').textContent = (s.estimated_hours || 0).toFixed(1);
    }
    if (d.key_themes) {
        $('principles').innerHTML = d.key_themes.map(p => `<div class="principle-item">${p}</div>`).join('');
    }
}

// Accuracy / Adaptive Intelligence
function renderAccuracy(d) {
    const total = $('accTotal');
    const pct = $('accPct');
    const err = $('accErr');
    if (!total) return;

    total.textContent = d.total_predictions || 0;
    pct.textContent = d.evaluated > 0 ? d.accuracy_pct + '%' : 'Learning';
    err.textContent = d.evaluated > 0 ? d.mean_error_pct + '%' : '-';

    // Confidence adjustments
    const list = $('confidenceList');
    if (list && d.confidence_adjustments) {
        list.innerHTML = '<div style="font-size:11px;color:var(--t3);margin-bottom:6px">INDICATOR CONFIDENCE</div>';
        for (const [k, v] of Object.entries(d.confidence_adjustments)) {
            const pctVal = ((v - 1) * 100).toFixed(0);
            const color = v > 1.05 ? '#00c805' : v < 0.95 ? '#ff5000' : '#888';
            list.innerHTML += `<div class="kv-row"><span class="kv-key">${fmtName(k)}</span><span class="kv-val" style="color:${color}">${v > 1 ? '+' : ''}${pctVal}%</span></div>`;
        }
    }
}

// Friday Predictions
function renderFridayPredictions(d) {
    if (!d) return;

    // Hero: target Friday + BTC predicted price
    const btcPred = d.predictions?.bitcoin;
    if (btcPred && !btcPred.error) {
        $('funTarget').textContent = fp(btcPred.predicted_price);
    }

    // Streak badge
    const stats = d.learning_stats || {};
    const streakEl = $('funStreak');
    if (streakEl) {
        if (stats.evaluated > 0) {
            const pct = stats.correct_direction > 0 ? ((stats.correct_direction / stats.evaluated) * 100).toFixed(0) : '0';
            streakEl.textContent = `${pct}% Accuracy`;
            streakEl.className = 'hero-badge ' + (pct >= 60 ? 'badge-bull' : pct >= 40 ? 'badge-neutral' : 'badge-bear');
        } else {
            streakEl.textContent = 'Learning';
            streakEl.className = 'hero-badge badge-neutral';
        }
    }

    // Target date subtitle
    const heroLabel = document.querySelector('#page-fun .hero-label');
    if (heroLabel && d.target_friday) {
        const dt = new Date(d.target_friday + 'T12:00:00');
        heroLabel.textContent = `Friday ${dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
    }

    // Prediction cards for each asset
    const predEl = $('fridayPredictions');
    if (predEl && d.predictions) {
        predEl.innerHTML = '';
        const names = { bitcoin: 'BTC', ethereum: 'ETH', gold: 'Gold', silver: 'Silver', uranium: 'URA', dogecoin: 'DOGE', sp500: 'S&P 500' };
        for (const [asset, pred] of Object.entries(d.predictions)) {
            if (pred.error) continue;
            const dirClass = pred.direction === 'UP' ? 'up' : pred.direction === 'DOWN' ? 'down' : 'flat';
            const dirIcon = pred.direction === 'UP' ? '&#9650;' : pred.direction === 'DOWN' ? '&#9660;' : '&#9644;';
            const dirColor = pred.direction === 'UP' ? '#00c805' : pred.direction === 'DOWN' ? '#ff5000' : '#888';
            predEl.innerHTML += `
                <div class="pred-card">
                    <div class="pred-header">
                        <span class="pred-name">${names[asset] || asset}</span>
                        <span class="pred-dir" style="color:${dirColor}">${dirIcon} ${pred.direction}</span>
                    </div>
                    <div class="pred-prices">
                        <div><span class="dim">Now: </span>${fp(pred.current_price)}</div>
                        <div><span class="dim">Pred: </span><b style="color:${dirColor}">${fp(pred.predicted_price)}</b></div>
                    </div>
                    <div class="pred-meta">
                        <span>${pred.predicted_change_pct > 0 ? '+' : ''}${pred.predicted_change_pct}%</span>
                        <span class="pred-conf">${pred.confidence}% conf</span>
                    </div>
                </div>`;
        }
    }

    // Track record stats
    $('funTotal').textContent = stats.total_predictions || 0;
    $('funCorrect').textContent = stats.evaluated > 0 ? ((stats.correct_direction / stats.evaluated) * 100).toFixed(0) + '%' : '-';
    $('funError').textContent = stats.avg_error_pct ? stats.avg_error_pct.toFixed(1) + '%' : '-';

    // Indicator weights
    const wEl = $('funWeights');
    if (wEl && d.weights) {
        wEl.innerHTML = '';
        for (const [k, v] of Object.entries(d.weights)) {
            const pct = (v * 100).toFixed(1);
            const barW = Math.min(pct, 100);
            wEl.innerHTML += `
                <div class="kv-row">
                    <span class="kv-key">${fmtName(k)}</span>
                    <div style="flex:1;display:flex;align-items:center;gap:6px">
                        <div style="flex:1;height:4px;background:var(--card);border-radius:2px;overflow:hidden">
                            <div style="width:${barW}%;height:100%;background:#5ac8fa;border-radius:2px"></div>
                        </div>
                        <span class="kv-val" style="min-width:40px;text-align:right">${pct}%</span>
                    </div>
                </div>`;
        }
    }

    // Past results history
    const hEl = $('funHistory');
    if (hEl && d.history && d.history.length > 0) {
        hEl.innerHTML = '';
        for (const week of d.history.reverse()) {
            let rows = '';
            for (const [asset, r] of Object.entries(week.results)) {
                const icon = r.correct ? '&#10003;' : '&#10007;';
                const color = r.correct ? '#00c805' : '#ff5000';
                rows += `<div class="hist-row"><span>${asset}</span><span style="color:${color}">${icon} ${r.error_pct.toFixed(1)}% err</span></div>`;
            }
            hEl.innerHTML += `
                <div class="hist-week">
                    <div class="hist-date">${week.date}</div>
                    ${rows}
                </div>`;
        }
    } else if (hEl) {
        hEl.innerHTML = '<div style="color:var(--t3);font-size:12px;padding:8px">No evaluated predictions yet. Check back after Friday!</div>';
    }
}

// Actions
async function refreshAll() {
    $('refreshBtn').style.opacity = '0.3';
    await init();
    $('refreshBtn').style.opacity = '1';
}

async function checkNewVideos() {
    const btn = $('newVidBtn');
    btn.textContent = 'Checking...';
    btn.disabled = true;
    const r = await api('/api/update-videos');
    alert(r?.new_videos_found > 0 ? `Found ${r.new_videos_found} new videos!` : 'No new videos.');
    btn.textContent = 'Check New Videos';
    btn.disabled = false;
}

// Helpers
function $(id) { return document.getElementById(id); }
function fp(p) { if (!p) return '-'; if (p < 0.01) return '$' + p.toFixed(6); if (p < 1) return '$' + p.toFixed(4); return p >= 1000 ? '$' + p.toLocaleString('en-US', {maximumFractionDigits:0}) : '$' + p.toFixed(2); }
function fcp(p) { if (!p) return '-'; if (p < 0.01) return '$' + p.toFixed(4); if (p < 1) return '$' + p.toFixed(3); return p >= 1e6 ? '$' + (p/1e6).toFixed(1)+'M' : p >= 1e3 ? '$' + (p/1e3).toFixed(1)+'K' : '$' + p.toFixed(2); }
function fn(n) { return n ? n.toLocaleString('en-US') : '0'; }
function fmtName(s) { return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()); }

// Info toggle
function toggleInfo(el) {
    // Find the .info-desc that follows the parent label element
    const parent = el.parentElement;
    let desc = parent.nextElementSibling;
    if (!desc || !desc.classList.contains('info-desc')) {
        desc = el.closest('.card')?.querySelector('.info-desc') || el.closest('.hero-section')?.querySelector('.info-desc');
    }
    if (!desc) return;
    const open = desc.classList.toggle('open');
    el.classList.toggle('open', open);
}

// Boot
document.addEventListener('DOMContentLoaded', init);
setInterval(init, 5 * 60 * 1000);
