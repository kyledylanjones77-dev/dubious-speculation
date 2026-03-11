// Dubious Speculation - Robinhood-style Trading App

let btcChartInstance = null;
let scoreChartInstance = null;
let econChartInstance = null;
let spChartInstance = null;
let mortgageChartInstance = null;

// Store raw data for timeframe switching
let _btcHistoryData = null;
let _econData = null;
let _dashData = null;
let _fcData = null;
let _currentBtcDays = 365;
let _currentEconDays = 365;
let _currentSpDays = 365;
let _sparkDrawn = false;

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
    // Draw sparklines once Assets page is visible (needs offsetWidth > 0)
    if (name === 'assets' && !_sparkDrawn && _dashData) {
        requestAnimationFrame(() => drawAllSparklines(_dashData));
    }
}

// Init
async function init() {
    const [comp, risk, fc, macro, insights, accuracy, history, econ, friday, dash, dpred, bensig] = await Promise.all([
        api('/api/composite-score'),
        api('/api/risk-metric'),
        api('/api/forecasts'),
        api('/api/macro'),
        api('/api/cowen-insights'),
        api('/api/accuracy'),
        api('/api/btc-history'),
        api('/api/macro-economy'),
        api('/api/friday-predictions'),
        api('/api/dashboard'),
        api('/api/daily-predictions'),
        api('/api/ben-signal'),
    ]);

    // Show current date
    const now = new Date();
    const dateEl = $('topDate');
    if (dateEl) dateEl.textContent = now.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' });

    if (comp) renderComposite(comp);
    if (risk) renderRisk(risk);
    _dashData = dash;
    _fcData = fc;
    _sparkDrawn = false;
    if (fc) { renderTicker(fc, dash); renderBtcPage(fc.bitcoin); renderAssets(fc, dash); }
    // BTC Dominance from faster dashboard endpoint, fallback to forecasts
    const domData = fc?.btc_dominance || {};
    if (dash?.btc_dominance) {
        domData.current_dominance = domData.current_dominance || dash.btc_dominance.btc_dominance;
        domData.eth_dominance = domData.eth_dominance || dash.btc_dominance.eth_dominance;
    }
    if (domData.current_dominance) renderDom(domData);

    if (macro) renderMacro(macro);
    if (insights) renderLearn(insights);
    if (accuracy) renderAccuracy(accuracy);
    if (friday) renderFridayPredictions(friday);
    if (dpred) renderDailyPredictions(dpred);
    if (bensig) renderBenSignal(bensig);
    if (history) { _btcHistoryData = history; renderBtcChart(history, _currentBtcDays); }
    if (fc && fc.bitcoin && fc.bitcoin.score_components) renderScoreChart(fc.bitcoin.score_components);
    if (econ) { _econData = econ; renderMacroEconomy(econ); }
}

// Composite
function renderComposite(d) {
    const s = d.composite_score || 0;
    const el = $('heroNum');
    el.textContent = (s > 0 ? '+' : '') + s.toFixed(0);
    el.style.color = s > 20 ? '#00c805' : s > 0 ? '#88cc00' : s > -20 ? '#ff8800' : '#ff5000';
    el.classList.remove('loading-pulse');

    const badge = $('heroBadge');
    badge.classList.remove('loading-pulse');
    const isBull = s > 0;
    badge.textContent = d.interpretation?.split(' - ')[0] || (isBull ? 'BULLISH' : 'BEARISH');
    badge.className = 'hero-badge ' + (isBull ? 'badge-bull' : s === 0 ? 'badge-neutral' : 'badge-bear');

    $('heroSub').textContent = d.interpretation || '';

    // Last updated timestamp
    let ts = $('lastUpdated');
    if (!ts) {
        ts = document.createElement('div');
        ts.id = 'lastUpdated';
        ts.className = 'last-updated';
        $('heroSub').parentElement.appendChild(ts);
    }
    ts.textContent = 'Updated ' + new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
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

// Ticker
function renderTicker(fc, dash) {
    const strip = $('tickerStrip');
    if (!strip) return;
    strip.innerHTML = '';
    const items = [
        { k: 'bitcoin', n: 'BTC', f: 'current_price', dk: 'bitcoin' },
        { k: 'ethereum', n: 'ETH', f: 'current_price', dk: 'ethereum' },
        { k: 'gold', n: 'GOLD', f: 'current_price', dk: 'gold' },
        { k: 'silver', n: 'SILVER', f: 'current_price', dk: 'silver' },
        { k: 'uranium', n: 'URA', f: 'current_price', dk: 'uranium' },
        { k: 'dogecoin', n: 'DOGE', f: 'current_price', dk: 'dogecoin' },
        { k: 'btc_dominance', n: 'BTC.D', f: 'current_dominance', dk: null },
    ];
    for (const a of items) {
        const d = fc[a.k]; if (!d) continue;
        const price = d[a.f] || 0;
        // Pull 24h change from multiple sources
        let change = d.change_24h || d.change_pct || 0;
        // Fallback: compute from dashboard price_history or previous_close
        if (!change && dash && a.dk && dash[a.dk]) {
            const dd = dash[a.dk];
            if (dd.change_24h) { change = dd.change_24h; }
            else if (dd.previous_close && dd.current_price) {
                change = ((dd.current_price / dd.previous_close) - 1) * 100;
            } else if (dd.price_history && dd.price_history.length >= 2) {
                const hist = dd.price_history;
                const now = hist[hist.length - 1].price;
                // Find price ~24h ago
                const cutoff = Date.now() - 86400000;
                let prev = hist[0].price;
                for (const p of hist) { if (p.timestamp < cutoff) prev = p.price; else break; }
                change = ((now / prev) - 1) * 100;
            }
        }
        const hasChange = change !== 0 && a.k !== 'btc_dominance';
        const changeColor = change >= 0 ? '#00c805' : '#ff5000';
        const changeText = hasChange ? `${change >= 0 ? '+' : ''}${change.toFixed(1)}%` : '';

        const div = document.createElement('div');
        div.className = 'tick';
        div.innerHTML = `
            <div class="tick-name">${a.n}</div>
            <div class="tick-price">${a.k === 'btc_dominance' ? price.toFixed(1) + '%' : fp(price)}</div>
            ${hasChange ? `<div style="font-size:11px;font-weight:700;color:${changeColor}">${changeText}</div>` : `<div class="tick-bias">${a.k === 'btc_dominance' ? '' : (d.bias || '').split(' - ')[0].substring(0,15)}</div>`}
        `;
        // Navigate to relevant page on tap
        const pageMap = { bitcoin: 'bitcoin', ethereum: 'assets', gold: 'assets', silver: 'assets', uranium: 'assets', dogecoin: 'assets', btc_dominance: 'home' };
        div.onclick = () => switchPage(pageMap[a.k] || 'home');
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
                    <div class="fc-period">${period.replace(/_/g, ' ')}</div>
                    <div class="fc-range">${fcp(f.low_estimate)}<br>-<br>${fcp(f.high_estimate)}</div>
                    <div class="fc-fair">Fair: ${fcp(f.fair_value_at_date)}</div>
                </div>`;
        }
    }

    // Key Indicators — relevant BTC landscape data
    const ind = $('btcIndicators');
    ind.innerHTML = '';

    // Risk metric & fair value
    const rm = d.risk_metric || {};
    if (rm.risk_score !== undefined) {
        const rColor = rm.risk_score < 0.3 ? '#00c805' : rm.risk_score < 0.55 ? '#ffcc00' : rm.risk_score < 0.75 ? '#ff8800' : '#ff5000';
        ind.innerHTML += `<div class="kv-row"><span class="kv-key">Risk Score</span><span class="kv-val" style="color:${rColor}">${rm.risk_score.toFixed(3)}</span></div>`;
    }
    if (rm.fair_value) ind.innerHTML += `<div class="kv-row"><span class="kv-key">Fair Value (Regression)</span><span class="kv-val">${fp(rm.fair_value)}</span></div>`;
    if (rm.distance_from_fair) ind.innerHTML += `<div class="kv-row"><span class="kv-key">Distance from Fair</span><span class="kv-val">${rm.distance_from_fair}</span></div>`;
    if (rm.zone) ind.innerHTML += `<div class="kv-row"><span class="kv-key">Zone</span><span class="kv-val" style="font-size:11px">${rm.zone}</span></div>`;

    // Bull Market Support Band
    if (d.bull_market_support_band) {
        const bb = d.bull_market_support_band;
        ind.innerHTML += `<div style="margin-top:8px;padding-top:6px;border-top:1px solid var(--border)"></div>`;
        ind.innerHTML += `<div class="kv-row"><span class="kv-key">20W SMA</span><span class="kv-val">${fp(bb.sma_20w)}</span></div>`;
        ind.innerHTML += `<div class="kv-row"><span class="kv-key">21W EMA</span><span class="kv-val">${fp(bb.ema_21w)}</span></div>`;
        const sigClass = /bull/i.test(bb.signal) ? 'sig-bull' : /bear/i.test(bb.signal) ? 'sig-bear' : 'sig-neutral';
        ind.innerHTML += `<div class="kv-signal ${sigClass}">${bb.signal}</div>`;
    }

    // Cycle Position
    const cyc = d.cycle_position || {};
    if (cyc.cycle_progress !== undefined) {
        ind.innerHTML += `<div style="margin-top:8px;padding-top:6px;border-top:1px solid var(--border)"></div>`;
        ind.innerHTML += `<div class="kv-row"><span class="kv-key">Cycle Progress</span><span class="kv-val">${(cyc.cycle_progress * 100).toFixed(1)}%</span></div>`;
        if (cyc.days_since_halving) ind.innerHTML += `<div class="kv-row"><span class="kv-key">Days Since Halving</span><span class="kv-val">${cyc.days_since_halving}</span></div>`;
        if (cyc.cycle_year) ind.innerHTML += `<div class="kv-row"><span class="kv-key">Cycle Phase</span><span class="kv-val" style="font-size:10px">${cyc.cycle_year.split('(')[0].trim()}</span></div>`;
    }

    // Key Levels (only meaningful ones)
    if (d.key_levels) {
        const kl = d.key_levels;
        ind.innerHTML += `<div style="margin-top:8px;padding-top:6px;border-top:1px solid var(--border)"></div>`;
        if (kl.bull_band_support) ind.innerHTML += `<div class="kv-row"><span class="kv-key">Bull Band Support</span><span class="kv-val">${fp(kl.bull_band_support)}</span></div>`;
        if (kl['200w_sma']) ind.innerHTML += `<div class="kv-row"><span class="kv-key">200W SMA</span><span class="kv-val">${fp(kl['200w_sma'])}</span></div>`;
    }

    // Context
    const ctx = $('btcContext');
    ctx.innerHTML = '';
    if (d.cowen_context) {
        ctx.innerHTML = d.cowen_context.map(c => `<p>&#8226; ${c}</p>`).join('');
    }
}

// BTC Price Chart with Regression Bands — supports timeframe filtering
function renderBtcChart(data, days) {
    const canvas = $('btcChart');
    if (!canvas || !data.price_history) return;

    let prices = data.price_history;
    const bands = data.regression_bands || {};

    // Filter by timeframe (ensure minimum 3 data points for a visible line)
    if (days && days < 9999) {
        const cutoff = Date.now() - days * 86400000;
        const startIdx = prices.findIndex(p => p.timestamp >= cutoff);
        if (startIdx > 0) {
            prices = prices.slice(startIdx);
            if (prices.length < 3) prices = data.price_history.slice(-Math.max(3, prices.length));
        }
    }

    // Downsample for performance
    const maxPts = days <= 7 ? prices.length : days <= 30 ? 100 : days <= 90 ? 120 : 100;
    const step = Math.max(1, Math.floor(prices.length / maxPts));
    const labels = [];
    const priceData = [];
    const fairData = [];
    const lowData = [];
    const highData = [];

    // Date format based on timeframe
    const dateFmt = days <= 1 ? { hour: 'numeric', minute: '2-digit' }
        : days <= 7 ? { weekday: 'short', month: 'short', day: 'numeric' }
        : days <= 90 ? { month: 'short', day: 'numeric' }
        : { month: 'short', year: '2-digit' };

    // Calculate offset for band index lookup (prices may be a slice of data.price_history)
    const bandOffset = data.price_history.indexOf(prices[0]);
    for (let i = 0; i < prices.length; i += step) {
        const p = prices[i];
        labels.push(new Date(p.timestamp).toLocaleDateString('en-US', dateFmt));
        priceData.push(p.price);

        // Only show bands for longer timeframes
        if (days > 90 && bands.fair) {
            const origIdx = bandOffset >= 0 ? bandOffset + i : -1;
            if (origIdx >= 0 && bands.fair[origIdx]) fairData.push(bands.fair[origIdx].price);
            else fairData.push(null);
            if (origIdx >= 0 && bands.low && bands.low[origIdx]) lowData.push(bands.low[origIdx].price);
            else lowData.push(null);
            if (origIdx >= 0 && bands.high && bands.high[origIdx]) highData.push(bands.high[origIdx].price);
            else highData.push(null);
        }
    }

    if (btcChartInstance) btcChartInstance.destroy();

    const datasets = [
        {
            label: 'BTC Price',
            data: priceData,
            borderColor: '#ffffff',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: false,
        },
    ];

    // Only show regression bands on longer timeframes
    if (fairData.length > 0 && days > 90) {
        datasets.push({
            label: 'Fair Value',
            data: fairData,
            borderColor: '#5ac8fa',
            borderWidth: 1.5,
            borderDash: [5, 3],
            pointRadius: 0,
            tension: 0.3,
            fill: false,
        });
        if (lowData.length > 0) datasets.push({
            label: 'Low Band',
            data: lowData,
            borderColor: '#00c805',
            borderWidth: 1,
            pointRadius: 0,
            tension: 0.3,
            fill: false,
        });
        if (highData.length > 0) datasets.push({
            label: 'High Band',
            data: highData,
            borderColor: '#ff5000',
            borderWidth: 1,
            pointRadius: 0,
            tension: 0.3,
            fill: false,
        });
    }

    btcChartInstance = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
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
    const values = Object.values(scores).map(v => (typeof v === 'number' ? v : parseFloat(v) || 0) * 100);
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

// Assets
function renderAssets(fc, dash) {
    const container = $('assetSwipe');
    if (!container) return;
    container.innerHTML = '';
    const assets = [
        { k: 'ethereum', n: 'Ethereum (ETH)', dk: 'ethereum' },
        { k: 'gold', n: 'Gold (XAU)', dk: 'gold' },
        { k: 'silver', n: 'Silver (XAG)', dk: 'silver' },
        { k: 'uranium', n: 'Uranium (URA)', dk: 'uranium' },
        { k: 'dogecoin', n: 'Dogecoin (DOGE)', dk: 'dogecoin' },
        { k: 'btc_dominance', n: 'BTC Dominance', dk: null },
    ];

    for (const a of assets) {
        const d = fc[a.k]; if (!d) continue;
        const price = d.current_price || d.current_dominance || 0;
        const bias = d.bias || d.bias_vs_btc || '';
        const biasClass = /bull|long|accum/i.test(bias) ? 'badge-bull' : /bear|cautious/i.test(bias) ? 'badge-bear' : 'badge-neutral';
        const change24h = d.change_24h || (dash && a.dk && dash[a.dk] ? dash[a.dk].change_24h : null);

        let fcHtml = '';
        if (d.forecasts) {
            for (const [period, f] of Object.entries(d.forecasts)) {
                const label = period.replace(/_/g, ' ');
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

        // 24h change badge
        const changeHtml = change24h != null ? `<span class="ac-change" style="color:${change24h >= 0 ? '#00c805' : '#ff5000'};font-size:12px;font-weight:600;margin-left:8px">${change24h >= 0 ? '+' : ''}${change24h.toFixed(2)}%</span>` : '';

        // Sparkline canvas ID
        const sparkId = `spark-${a.k.replace(/_/g, '')}`;

        container.innerHTML += `
            <div class="asset-card">
                <div class="ac-header"><div class="ac-name">${a.n}</div></div>
                <div class="ac-price">${a.k === 'btc_dominance' ? price.toFixed(1) + '%' : fp(price)}${changeHtml}</div>
                <div class="ac-bias ${biasClass}">${(bias.split(' - ')[0] || bias).substring(0, 25)}</div>
                ${a.dk ? `<div class="spark-wrap"><canvas id="${sparkId}"></canvas></div>` : ''}
                ${fcHtml ? `<div class="ac-forecasts">${fcHtml}</div>` : ''}
                ${extra ? `<div class="ac-extra">${extra}</div>` : ''}
                ${ctxHtml}
            </div>`;
    }

    // Sparklines drawn when Assets page becomes visible (needs offsetWidth > 0)
}

function drawAllSparklines(dash) {
    if (!dash) return;
    const map = { ethereum: 'ethereum', gold: 'gold', silver: 'silver', uranium: 'uranium', dogecoin: 'dogecoin' };
    for (const [key, dk] of Object.entries(map)) {
        if (!dash[dk] || !dash[dk].price_history) continue;
        const canvas = $(`spark-${key}`);
        if (!canvas) continue;
        drawSparkline(canvas, dash[dk].price_history);
    }
    _sparkDrawn = true;
}

function drawSparkline(canvas, history) {
    if (!history || history.length < 2) return;
    // Use last 90 days of data
    const cutoff = Date.now() - 90 * 86400000;
    let pts = history.filter(p => p.timestamp >= cutoff);
    if (pts.length < 2) pts = history.slice(-90);
    // Downsample to ~60 points
    const step = Math.max(1, Math.floor(pts.length / 60));
    const prices = [];
    for (let i = 0; i < pts.length; i += step) prices.push(pts[i].price);

    const ctx = canvas.getContext('2d');
    const w = canvas.parentElement.offsetWidth;
    const h = 48;
    canvas.width = w * 2;
    canvas.height = h * 2;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.scale(2, 2);

    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const isUp = prices[prices.length - 1] >= prices[0];
    const color = isUp ? '#00c805' : '#ff5000';

    ctx.beginPath();
    for (let i = 0; i < prices.length; i++) {
        const x = (i / (prices.length - 1)) * w;
        const y = h - ((prices[i] - min) / range) * (h - 4) - 2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Fill gradient
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, isUp ? 'rgba(0,200,5,0.15)' : 'rgba(255,80,0,0.15)');
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.fill();
}

// Macro (DXY, Oil, Treasury - existing)
function renderMacro(d) {
    const el = $('macroList');
    if (!el) return;
    el.innerHTML = '';
    const info = {
        DXY: { n: 'US Dollar Index (DXY)',
            desc: 'Measures the dollar against a basket of major currencies. A strong dollar (above 105) is a headwind for crypto and commodities. A weak dollar (below 95) is a tailwind. Cowen considers DXY one of the most important macro indicators.',
            impact: v => v > 105 ? 'Headwind for crypto' : v < 95 ? 'Tailwind for crypto' : 'Neutral range' },
        Oil_WTI: { n: 'Oil (WTI Crude)',
            desc: 'Crude oil price per barrel. Cowen notes that oil spikes historically end business cycles. Above $100 = recessionary risk. Sustained high oil prices drain consumer spending and can trigger broader market selloffs.',
            impact: v => v > 100 ? 'Business cycle risk!' : v > 80 ? 'Elevated' : 'Normal range' },
        Treasury_10Y: { n: '10Y Treasury Yield',
            desc: 'The yield on 10-year US government bonds. Higher yields mean tighter financial conditions — bad for risk assets. Below 3% = loose conditions favoring stocks/crypto. Above 4.5% = tight, acting as a drag on valuations.',
            impact: v => v > 4.5 ? 'Tight conditions' : v > 3 ? 'Moderate' : 'Loose conditions' },
    };
    for (const [k, meta] of Object.entries(info)) {
        const item = d[k]; if (!item || item.error) continue;
        el.innerHTML += `
            <div class="macro-item">
                <div class="macro-name">${meta.n} <span class="info-toggle" onclick="toggleInfo(this)">i</span></div>
                <div class="info-desc">${meta.desc}</div>
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
    renderEconChart(d, _currentEconDays);

    // S&P 500 chart
    renderSpChart(d, _currentSpDays);

    // Housing market
    if (d.housing) renderHousing(d.housing);
}

function renderEconCards(d) {
    const container = $('econCards');
    if (!container) return;
    container.innerHTML = '';

    const cards = [
        { key: 'unemployment_rate', fmt: v => v.toFixed(1) + '%', label: 'Unemployment Rate',
          desc: 'Percentage of the labor force actively looking for work. Below 4% is strong. Rising above 4.5% signals economic weakness. The Fed watches this closely to set interest rate policy.' },
        { key: 'initial_claims', fmt: v => v.toFixed(0) + 'K', label: 'Initial Claims (Weekly)',
          desc: 'New unemployment filings each week. Below 250K is healthy. A spike above 300K signals sudden layoffs — one of the earliest recession warnings.' },
        { key: 'continuing_claims', fmt: v => (v / 1000).toFixed(2) + 'M', label: 'Continuing Claims',
          desc: 'Total people still receiving unemployment benefits. Rising continuing claims means people are struggling to find new jobs — a sign the labor market is softening.' },
        { key: 'nonfarm_payrolls', fmt: v => (v / 1000).toFixed(1) + 'M jobs', label: 'Total Nonfarm Employment',
          desc: 'Total number of paid workers in the economy (excluding farms). Month-over-month changes show if the economy is adding or losing jobs. Positive = growing economy.' },
        { key: 'vix', fmt: v => v.toFixed(1), label: 'VIX (Fear Index)',
          desc: 'Measures expected market volatility over 30 days. Below 15 = calm/complacent. 15-25 = normal. Above 30 = fear/panic. Cowen notes high VIX often creates buying opportunities for crypto.' },
        { key: 'sp500', fmt: v => v.toLocaleString('en-US', {maximumFractionDigits:0}), label: 'S&P 500',
          desc: 'The benchmark index of 500 largest US companies. Its trend reflects overall market health. Price above 200-day SMA = bullish trend. BTC often correlates with S&P during macro-driven markets.' },
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
                <div class="macro-name">${c.label} <span class="info-toggle" onclick="toggleInfo(this)">i</span></div>
                <div class="info-desc">${c.desc || ''}</div>
                <div class="macro-val">${c.fmt(val)}</div>
                <div style="font-size:11px;color:${changeColor}">${changeStr}</div>
                ${extra}
                ${item.date ? `<div style="font-size:9px;color:var(--t3);margin-top:2px">${item.date}</div>` : ''}
            </div>`;
    }
}

function renderEconChart(d, days) {
    const canvas = $('econChart');
    if (!canvas) return;

    days = days || _currentEconDays;

    // Build dual-axis chart: Unemployment Rate (left) + Initial Claims (right)
    const unemp = d.unemployment_rate;
    const claims = d.initial_claims;
    if ((!unemp || !unemp.history) && (!claims || !claims.history)) return;

    let unempData = unemp && unemp.history ? unemp.history : [];
    let claimsData = claims && claims.history ? claims.history : [];

    // Filter by timeframe
    if (days < 9999) {
        const cutoffDate = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
        unempData = unempData.filter(p => p.date >= cutoffDate);
        claimsData = claimsData.filter(p => p.date >= cutoffDate);
    }

    const dateFmt = days <= 90 ? (d => d.substring(5)) : (d => d.substring(0, 7));

    // Merge both datasets onto a unified date axis
    const dateMap = new Map();
    for (const p of unempData) dateMap.set(p.date, { unemp: p.value });
    for (const p of claimsData) {
        const entry = dateMap.get(p.date) || {};
        entry.claims = p.value;
        dateMap.set(p.date, entry);
    }
    const allDates = [...dateMap.keys()].sort();

    // Downsample for readability
    const step = Math.max(1, Math.floor(allDates.length / 60));
    const labels = [];
    const uValues = [];
    const clValues = [];
    let lastUnemp = null;
    for (let i = 0; i < allDates.length; i += step) {
        const dt = allDates[i];
        const entry = dateMap.get(dt);
        labels.push(dateFmt(dt));
        // Forward-fill unemployment (monthly) across weekly dates
        if (entry.unemp !== undefined) lastUnemp = entry.unemp;
        uValues.push(lastUnemp);
        clValues.push(entry.claims !== undefined ? entry.claims : null);
    }

    if (econChartInstance) econChartInstance.destroy();

    const datasets = [];
    if (uValues.some(v => v !== null)) {
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
            spanGaps: true,
        });
    }
    if (clValues.some(v => v !== null)) {
        datasets.push({
            label: 'Initial Claims (K)',
            data: clValues,
            borderColor: '#5ac8fa',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.3,
            fill: false,
            yAxisID: 'y1',
            spanGaps: true,
        });
    }

    econChartInstance = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
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

function renderSpChart(d, days) {
    const canvas = $('spChart');
    if (!canvas) return;

    const sp = d.sp500;
    if (!sp || !sp.history || sp.history.length === 0) return;

    days = days || _currentSpDays;
    let history = sp.history;

    // Filter by timeframe
    if (days < 9999) {
        const cutoff = Date.now() - days * 86400000;
        const startIdx = history.findIndex(p => p.timestamp >= cutoff);
        if (startIdx > 0) history = history.slice(startIdx);
    }

    const maxPts = days <= 30 ? history.length : 80;
    const step = Math.max(1, Math.floor(history.length / maxPts));
    const labels = [];
    const prices = [];

    const dateFmt = days <= 7 ? { weekday: 'short', month: 'short', day: 'numeric' }
        : days <= 90 ? { month: 'short', day: 'numeric' }
        : { month: 'short', year: '2-digit' };

    for (let i = 0; i < history.length; i += step) {
        const p = history[i];
        labels.push(new Date(p.timestamp).toLocaleDateString('en-US', dateFmt));
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
        { key: 'mortgage_rate', fmt: v => v.toFixed(2) + '%', label: '30-Year Mortgage',
          desc: 'Average interest rate on a 30-year fixed mortgage. Higher rates reduce affordability and slow the housing market. The Fed\'s rate policy directly impacts this — rate cuts eventually push mortgage rates down.' },
        { key: 'median_home_price', fmt: v => '$' + (v/1000).toFixed(0) + 'K', label: 'Median Home Price',
          desc: 'The middle price of all homes sold. Tracks whether housing is getting more or less expensive. Rising prices with falling sales can signal an unaffordable market.' },
        { key: 'housing_starts', fmt: v => v.toFixed(0) + 'K', label: 'Housing Starts (SAAR)',
          desc: 'Annualized rate of new residential construction. Measures builder confidence. Rising starts = builders expect demand. Falling starts = economic caution.' },
        { key: 'building_permits', fmt: v => v.toFixed(0) + 'K', label: 'Building Permits (SAAR)',
          desc: 'Permits issued for new construction — a leading indicator since permits come before building. Declining permits signal a housing slowdown ahead.' },
        { key: 'existing_home_sales', fmt: v => v.toFixed(2) + 'M', label: 'Existing Home Sales',
          desc: 'Annualized rate of previously-owned home sales. The bulk of the housing market. Low sales with high prices = frozen market where buyers can\'t afford and sellers won\'t move.' },
        { key: 'months_supply', fmt: v => v.toFixed(1) + ' mo', label: 'Months of Supply',
          desc: 'How many months it would take to sell all homes on the market at the current sales pace. Below 4 = seller\'s market (prices rise). Above 6 = buyer\'s market (prices may fall). Around 5-6 = balanced.' },
        { key: 'home_price_index', fmt: v => v.toFixed(1), label: 'Case-Shiller Index',
          desc: 'The S&P/Case-Shiller index tracks repeat home sales to measure actual price trends. It\'s the gold standard for housing price data — year-over-year changes show if the housing market is inflating or deflating.' },
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
                <div class="macro-name">${c.label} <span class="info-toggle" onclick="toggleInfo(this)">i</span></div>
                <div class="info-desc">${c.desc || ''}</div>
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
        for (const week of [...d.history].reverse()) {
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

// What Would Ben Do? Buy/Sell Signal
function renderBenSignal(d) {
    if (!d) return;

    const actionEl = $('benAction');
    const detailEl = $('benDetail');
    const scoreEl = $('benScore');
    const reasonEl = $('benReasoning');
    const countEl = $('benCounts');

    if (!actionEl) return;

    // Action badge
    const colorMap = { buy: '#00c805', sell: '#ff5000', hold: '#ff8800' };
    const bgMap = { buy: 'rgba(0,200,5,0.15)', sell: 'rgba(255,80,0,0.15)', hold: 'rgba(255,136,0,0.15)' };
    actionEl.textContent = d.action;
    actionEl.style.color = colorMap[d.color] || '#888';
    actionEl.style.background = bgMap[d.color] || 'rgba(136,136,136,0.15)';

    if (detailEl) detailEl.textContent = d.action_detail;

    // Score
    if (scoreEl) {
        scoreEl.textContent = (d.score > 0 ? '+' : '') + d.score;
        scoreEl.style.color = d.score > 10 ? '#00c805' : d.score > -10 ? '#ff8800' : '#ff5000';
    }

    // Signal counts
    if (countEl) {
        countEl.innerHTML = `
            <span style="color:#00c805">${d.bullish_signals} bullish</span> &bull;
            <span style="color:#888">${d.neutral_signals} neutral</span> &bull;
            <span style="color:#ff5000">${d.bearish_signals} bearish</span>`;
    }

    // Reasoning
    if (reasonEl && d.reasoning) {
        reasonEl.innerHTML = '';
        for (const r of d.reasoning) {
            const scoreColor = r.score > 0.5 ? '#00c805' : r.score < -0.5 ? '#ff5000' : '#888';
            const scoreLabel = r.score > 0.5 ? 'BUY' : r.score < -0.5 ? 'SELL' : 'HOLD';
            const icon = r.score > 0.5 ? '&#9650;' : r.score < -0.5 ? '&#9660;' : '&#9644;';
            reasonEl.innerHTML += `
                <div class="ben-reason">
                    <div class="ben-reason-header">
                        <span class="ben-reason-name">${r.name}</span>
                        <span style="color:${scoreColor};font-size:11px;font-weight:700">${icon} ${scoreLabel}</span>
                    </div>
                    <div class="ben-reason-detail">${r.detail}</div>
                </div>`;
        }
    }
}

// Daily/Weekly Self-Learning Predictions
function renderDailyPredictions(d) {
    if (!d) return;

    const names = { bitcoin: 'BTC', ethereum: 'ETH', gold: 'Gold', silver: 'Silver', uranium: 'URA', dogecoin: 'DOGE' };

    // Daily predictions
    const dailyEl = $('dailyPredictions');
    if (dailyEl && d.daily?.predictions) {
        dailyEl.innerHTML = '';
        const dt = new Date(d.daily.target_date + 'T12:00:00');
        const dateStr = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        for (const [asset, pred] of Object.entries(d.daily.predictions)) {
            if (pred.error) continue;
            const dirColor = pred.direction === 'UP' ? '#00c805' : pred.direction === 'DOWN' ? '#ff5000' : '#888';
            const dirIcon = pred.direction === 'UP' ? '&#9650;' : pred.direction === 'DOWN' ? '&#9660;' : '&#9644;';
            dailyEl.innerHTML += `
                <div class="pred-card">
                    <div class="pred-header">
                        <span class="pred-name">${names[asset] || asset}</span>
                        <span class="pred-dir" style="color:${dirColor}">${dirIcon} ${pred.direction}</span>
                    </div>
                    <div class="pred-prices">
                        <div><span class="dim">Now: </span>${fp(pred.current_price)}</div>
                        <div><span class="dim">${dateStr}: </span><b style="color:${dirColor}">${fp(pred.predicted_price)}</b></div>
                    </div>
                    <div class="pred-meta">
                        <span>${pred.predicted_change_pct > 0 ? '+' : ''}${pred.predicted_change_pct}%</span>
                        <span class="pred-conf">${pred.confidence}% conf</span>
                    </div>
                </div>`;
        }
    }

    // Weekly predictions
    const weeklyEl = $('weeklyPredictions');
    if (weeklyEl && d.weekly?.predictions) {
        weeklyEl.innerHTML = '';
        const dt = new Date(d.weekly.target_date + 'T12:00:00');
        const dateStr = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        for (const [asset, pred] of Object.entries(d.weekly.predictions)) {
            if (pred.error) continue;
            const dirColor = pred.direction === 'UP' ? '#00c805' : pred.direction === 'DOWN' ? '#ff5000' : '#888';
            const dirIcon = pred.direction === 'UP' ? '&#9650;' : pred.direction === 'DOWN' ? '&#9660;' : '&#9644;';
            weeklyEl.innerHTML += `
                <div class="pred-card">
                    <div class="pred-header">
                        <span class="pred-name">${names[asset] || asset}</span>
                        <span class="pred-dir" style="color:${dirColor}">${dirIcon} ${pred.direction}</span>
                    </div>
                    <div class="pred-prices">
                        <div><span class="dim">Now: </span>${fp(pred.current_price)}</div>
                        <div><span class="dim">${dateStr}: </span><b style="color:${dirColor}">${fp(pred.predicted_price)}</b></div>
                    </div>
                    <div class="pred-meta">
                        <span>${pred.predicted_change_pct > 0 ? '+' : ''}${pred.predicted_change_pct}%</span>
                        <span class="pred-conf">${pred.confidence}% conf</span>
                    </div>
                </div>`;
        }
    }

    // Stats
    const stats = d.stats || {};
    const dAccEl = $('dpDailyAcc');
    const wAccEl = $('dpWeeklyAcc');
    const dErrEl = $('dpDailyErr');
    const wErrEl = $('dpWeeklyErr');
    const dCountEl = $('dpDailyCount');
    const wCountEl = $('dpWeeklyCount');
    const streakEl = $('dpStreak');
    const updatesEl = $('dpUpdates');

    if (dAccEl) dAccEl.textContent = stats.daily_accuracy != null ? stats.daily_accuracy + '%' : 'Learning';
    if (wAccEl) wAccEl.textContent = stats.weekly_accuracy != null ? stats.weekly_accuracy + '%' : 'Learning';
    if (dErrEl) dErrEl.textContent = stats.daily_avg_error ? stats.daily_avg_error.toFixed(2) + '%' : '-';
    if (wErrEl) wErrEl.textContent = stats.weekly_avg_error ? stats.weekly_avg_error.toFixed(2) + '%' : '-';
    if (dCountEl) dCountEl.textContent = stats.daily_evaluated || 0;
    if (wCountEl) wCountEl.textContent = stats.weekly_evaluated || 0;
    if (streakEl) streakEl.textContent = stats.current_streak || 0;
    if (updatesEl) updatesEl.textContent = stats.weight_updates || 0;

    // Signal weights with bars
    const swEl = $('dpWeights');
    if (swEl && d.weights) {
        swEl.innerHTML = '';
        const sorted = Object.entries(d.weights).sort((a, b) => b[1] - a[1]);
        for (const [k, v] of sorted) {
            const pct = (v * 100).toFixed(1);
            const barW = Math.min(v * 100 * 3, 100); // scale for visibility
            const isTop = v === sorted[0][1];
            swEl.innerHTML += `
                <div class="kv-row">
                    <span class="kv-key">${fmtName(k)}</span>
                    <div style="flex:1;display:flex;align-items:center;gap:6px">
                        <div style="flex:1;height:4px;background:var(--card);border-radius:2px;overflow:hidden">
                            <div style="width:${barW}%;height:100%;background:${isTop ? '#00c805' : '#5ac8fa'};border-radius:2px"></div>
                        </div>
                        <span class="kv-val" style="min-width:40px;text-align:right">${pct}%</span>
                    </div>
                </div>`;
        }
    }

    // Learning history
    const lhEl = $('dpLearnHistory');
    if (lhEl && d.history && d.history.length > 0) {
        lhEl.innerHTML = '';
        for (const entry of d.history.slice(0, 14)) {
            const typeLabel = entry.type === 'daily' ? '<span style="color:#5ac8fa;font-size:10px">DAILY</span>' : '<span style="color:#ff8800;font-size:10px">WEEKLY</span>';
            let rows = '';
            for (const [asset, r] of Object.entries(entry.results || {})) {
                const icon = r.correct ? '&#10003;' : '&#10007;';
                const color = r.correct ? '#00c805' : '#ff5000';
                rows += `<div class="hist-row"><span>${names[asset] || asset}</span><span style="color:${color}">${icon} ${r.error.toFixed(2)}%</span></div>`;
            }
            lhEl.innerHTML += `
                <div class="hist-week">
                    <div class="hist-date">${entry.date} ${typeLabel}</div>
                    ${rows}
                </div>`;
        }
    } else if (lhEl) {
        lhEl.innerHTML = '<div style="color:var(--t3);font-size:12px;padding:8px">Predictions generated! Results will appear after each target date passes.</div>';
    }

    // Hero badge for daily
    const heroBadge = $('dpHeroBadge');
    if (heroBadge && stats.daily_accuracy != null) {
        heroBadge.textContent = stats.daily_accuracy + '% Accuracy';
        heroBadge.className = 'hero-badge ' + (stats.daily_accuracy >= 60 ? 'badge-bull' : stats.daily_accuracy >= 40 ? 'badge-neutral' : 'badge-bear');
    } else if (heroBadge) {
        heroBadge.textContent = 'Self-Learning';
        heroBadge.className = 'hero-badge badge-neutral';
    }
}

// Timeframe switching
function changeBtcTimeframe(days) {
    _currentBtcDays = days;
    document.querySelectorAll('#btcTfBar .tf-btn').forEach(b => b.classList.toggle('active', parseInt(b.dataset.days) === days));
    if (_btcHistoryData) renderBtcChart(_btcHistoryData, days);
}

function changeSpTimeframe(days) {
    _currentSpDays = days;
    const bar = $('spTfBar');
    if (bar) bar.querySelectorAll('.tf-btn').forEach(b => b.classList.toggle('active', parseInt(b.dataset.days) === days));
    if (_econData) renderSpChart(_econData, days);
}

function changeEconTimeframe(days) {
    _currentEconDays = days;
    const bar = $('econTfBar');
    if (bar) bar.querySelectorAll('.tf-btn').forEach(b => b.classList.toggle('active', parseInt(b.dataset.days) === days));
    if (_econData) renderEconChart(_econData, days);
}

// Actions
async function refreshAll() {
    const btn = $('refreshBtn');
    if (btn) { btn.classList.add('spinning'); btn.style.opacity = '0.5'; }
    try { await init(); } finally {
        if (btn) { btn.classList.remove('spinning'); btn.style.opacity = '1'; }
    }
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

// Refresh Knowledge Base stats (hourly)
async function refreshKnowledgeBase() {
    const insights = await api('/api/cowen-insights');
    if (insights) renderLearn(insights);
}

// =============================================
// ASK BEN AI — Chat Interface
// =============================================
let chatHistory = [];  // {role, content} pairs for context
let chatOpen = false;
let chatReady = false;

function toggleChat() {
    chatOpen = !chatOpen;
    const overlay = document.getElementById('chatOverlay');
    const fab = document.getElementById('chatFab');
    overlay.classList.toggle('open', chatOpen);
    fab.classList.toggle('hidden', chatOpen);

    if (chatOpen) {
        document.getElementById('chatInput').focus();
        // Check LLM status on first open
        if (!chatReady) checkLLMStatus();
    }
}

async function checkLLMStatus() {
    const status = await api('/api/llm-status');
    const dot = document.getElementById('chatStatus');
    if (status && status.ready) {
        chatReady = true;
        dot.textContent = '●';
        dot.className = 'chat-status';
        dot.title = `${status.vector_store.chunks} chunks from ${status.vector_store.transcripts_embedded} videos`;
    } else {
        dot.className = 'chat-status offline';
        dot.title = 'Vector store not built yet';
        // Show build prompt
        addBotMessage('The knowledge base needs to be indexed first. Building now — this takes a few minutes for ' +
            (status?.transcripts_available || '?') + ' transcripts...');
        // Auto-trigger build
        await fetch('/api/llm-build', { method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}' });
        // Poll for readiness
        pollLLMReady();
    }
    // Show suggestions if ready
    if (chatReady) showSuggestions();
}

function pollLLMReady() {
    const interval = setInterval(async () => {
        const s = await api('/api/llm-status');
        if (s && s.ready) {
            chatReady = true;
            clearInterval(interval);
            document.getElementById('chatStatus').className = 'chat-status';
            addBotMessage(`Knowledge base ready! ${s.vector_store.chunks.toLocaleString()} chunks from ${s.vector_store.transcripts_embedded} videos indexed. Ask me anything.`);
            showSuggestions();
        }
    }, 5000);
}

function showSuggestions() {
    const msgs = document.getElementById('chatMessages');
    // Don't duplicate
    if (msgs.querySelector('.chat-suggestions')) return;

    const suggestions = [
        "What's the current BTC risk level?",
        "When does Ben think the cycle bottom will be?",
        "Explain the bull market support band",
        "What does Ben think about ETH vs BTC?",
        "How do macro conditions affect crypto?",
        "What's Ben's view on the 4-year cycle?",
    ];

    const div = document.createElement('div');
    div.className = 'chat-suggestions';
    suggestions.forEach(s => {
        const chip = document.createElement('button');
        chip.className = 'chat-chip';
        chip.textContent = s;
        chip.onclick = () => {
            document.getElementById('chatInput').value = s;
            sendChat();
            div.remove();
        };
        div.appendChild(chip);
    });
    msgs.appendChild(div);
    scrollChat();
}

async function sendChat() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;

    // Remove suggestions if present
    const sugs = document.querySelector('.chat-suggestions');
    if (sugs) sugs.remove();

    // Add user message
    addUserMessage(msg);
    input.value = '';
    input.disabled = true;
    document.getElementById('chatSend').disabled = true;

    // Show typing indicator
    const typing = addTypingIndicator();

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: msg,
                history: chatHistory.slice(-8),  // last 4 exchanges
            }),
        });
        const data = await res.json();

        // Remove typing
        typing.remove();

        if (data.error) {
            addBotMessage('Sorry, something went wrong: ' + data.error);
        } else if (!data.ready) {
            addBotMessage(data.response);
        } else {
            // Format response with sources
            let html = formatMarkdown(data.response);

            if (data.sources && data.sources.length > 0) {
                html += '<div class="chat-sources">Sources: ';
                html += data.sources.map(s =>
                    `<a href="https://youtube.com/watch?v=${s.video_id}" target="_blank">${escHtml(s.title)}</a>`
                ).join(' · ');
                html += '</div>';
            }

            addBotMessageHTML(html);

            // Update conversation history for context
            chatHistory.push({ role: 'user', content: msg });
            chatHistory.push({ role: 'assistant', content: data.response });
        }
    } catch (e) {
        typing.remove();
        addBotMessage('Connection error. Please try again.');
    }

    input.disabled = false;
    document.getElementById('chatSend').disabled = false;
    input.focus();
}

function addUserMessage(text) {
    const msgs = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'chat-msg user';
    div.innerHTML = `<div class="chat-bubble">${escHtml(text)}</div>`;
    msgs.appendChild(div);
    scrollChat();
}

function addBotMessage(text) {
    const msgs = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'chat-msg bot';
    div.innerHTML = `<div class="chat-bubble">${escHtml(text)}</div>`;
    msgs.appendChild(div);
    scrollChat();
}

function addBotMessageHTML(html) {
    const msgs = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'chat-msg bot';
    div.innerHTML = `<div class="chat-bubble">${html}</div>`;
    msgs.appendChild(div);
    scrollChat();
}

function addTypingIndicator() {
    const msgs = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'chat-msg bot';
    div.innerHTML = `<div class="chat-bubble chat-typing"><span></span><span></span><span></span></div>`;
    msgs.appendChild(div);
    scrollChat();
    return div;
}

function scrollChat() {
    const msgs = document.getElementById('chatMessages');
    setTimeout(() => msgs.scrollTop = msgs.scrollHeight, 50);
}

function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatMarkdown(text) {
    // Basic markdown-like formatting
    return escHtml(text)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code style="background:var(--bg2);padding:1px 4px;border-radius:3px;font-size:12px">$1</code>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
}

// Enter key to send
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && chatOpen && document.activeElement === document.getElementById('chatInput')) {
        e.preventDefault();
        sendChat();
    }
    // Escape to close
    if (e.key === 'Escape' && chatOpen) {
        toggleChat();
    }
});

// Close chat on overlay click (outside panel)
document.getElementById('chatOverlay')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) toggleChat();
});

// Boot
document.addEventListener('DOMContentLoaded', init);
setInterval(init, 5 * 60 * 1000);          // Full refresh every 5 min
setInterval(refreshKnowledgeBase, 60 * 60 * 1000); // Knowledge Base every 1 hour
