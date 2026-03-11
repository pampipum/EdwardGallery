import { fetchDashboardData, checkPortfolioStatus, startPortfolio, triggerMarketCheck, getAllPMsStatus, startAllPortfolios, getCROStatus, fetchLiveOverview } from './api.js';
import * as UI from './ui.js';
import { renderLayout } from './layout.js';
import './reports.js';

// Markdown preview helper - exposed globally for use in ui.js template literals
window.renderMarkdownPreview = function (markdown) {
    if (typeof marked !== 'undefined') {
        return marked.parse(markdown);
    }
    // Fallback: basic markdown rendering
    return markdown
        .replace(/^## (.+)$/gm, '<h2 class="text-base font-bold mt-3 mb-1 text-gray-900">$1</h2>')
        .replace(/^### (.+)$/gm, '<h3 class="text-sm font-bold mt-2 mb-1 text-gray-800">$1</h3>')
        .replace(/\*\*(.+?)\*\*/g, '<strong class="font-bold">$1</strong>')
        .replace(/---/g, '<hr class="my-2 border-gray-200">')
        .replace(/- (.+)/g, '<li class="ml-3 list-disc text-xs">$1</li>')
        .replace(/\n/g, '<br>');
};

// --- PM State Management ---
let currentPM = 'all'; // Default to ALL PMs so user sees the big picture on load
let selectedLivePM = 'pm1';

const PM_INFO = {
    'pm1': { name: '1: ADAPTIVE STRUCTURAL ALPHA', label: '1: Adaptive Structural Alpha', strategy: 'current' },
    'pm2': { name: '2: THE SENTIENT STRUCTURIST', label: '2: The Sentient Structurist', strategy: 'hybrid' },
    'pm3': { name: '3: LIQUIDITY VACUUM ALPHA', label: '3: Liquidity Vacuum Alpha', strategy: 'sentiment' },
    'pm4': { name: '4: MAX LEVERAGE', label: '4: Max Leverage', strategy: 'leverage' },
    'pm5': { name: '5: THE SURVIVOR', label: '5: The Survivor', strategy: 'survival' },
    'pm6': { name: '6: SHADOW LIVE (PM4 MIRROR)', label: '6: Shadow Live', strategy: 'leverage' },
    'all': { name: 'ALL PMs', label: 'All Portfolios', strategy: 'all' }
};

// --- Initialization ---

async function init() {
    try {
        // 1. Render the static layout
        renderLayout();

        // 2. Update market status
        await updateMarketStatus();

        // 3. Auto-select All PMs view on load
        window.switchPM('all');

        // 4. Initial data fetch (PM1 data + dashboard ticker)
        await checkPortfolioStatusWrapper();
        fetchDashboardDataWrapper();

        // 5. Start market status polling (every 60 seconds)
        setInterval(updateMarketStatus, 60000);

        // 6. Start live monitor polling
        updateLiveMonitor();
        setInterval(updateLiveMonitor, 10000);
    } catch (error) {
        console.error('Failed to initialize:', error);
    }
}

async function updateMarketStatus() {
    try {
        const response = await fetch('/api/market/status');
        if (!response.ok) return;

        const data = await response.json();
        const statusLabel = document.getElementById('market-status-label');
        const statusDot = document.getElementById('market-status-dot');
        const statusContainer = document.getElementById('market-status');

        if (!statusLabel || !statusDot || !statusContainer) return;

        statusLabel.textContent = data.label;

        // Update colors based on status
        const colorMap = {
            'green': { text: 'text-accent-teal', bg: 'bg-accent-teal', pulse: true },
            'yellow': { text: 'text-[#fcca46]', bg: 'bg-[#fcca46]', pulse: true },
            'gray': { text: 'text-gray-500', bg: 'bg-gray-500', pulse: false }
        };

        const colors = colorMap[data.color] || colorMap['gray'];

        statusContainer.className = `text-[10px] font-bold ${colors.text} flex items-center gap-2 px-2 py-0.5 bg-glass-bg border border-glass-border rounded-full w-fit`;
        statusDot.className = `w-2 h-2 ${colors.bg} rounded-full ${colors.pulse ? 'animate-pulse' : ''}`;

    } catch (error) {
        console.error('Failed to fetch market status:', error);
    }
}

async function fetchDashboardDataWrapper() {
    try {
        const data = await fetchDashboardData();
        UI.renderTickerTape(data);
    } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
    }
}

async function checkPortfolioStatusWrapper() {
    try {
        // Always fetch all PMs data for sparklines, regardless of selected PM
        const allData = await getAllPMsStatus();
        drawAllSparklines(allData);

        if (currentPM === 'all') {
            const comparisonData = {};
            let totalBalance = 0;
            let totalValue = 0;
            let totalUnrealized = 0;
            let totalRealized = 0;

            for (const [pmId, data] of Object.entries(allData)) {
                comparisonData[pmId] = data.history;
                totalBalance += (data.available_cash !== undefined ? data.available_cash : data.balance) || 0;
                totalValue += data.total_value || 0;
                totalUnrealized += data.total_unrealized_pnl || 0;
                totalRealized += data.total_realized_pnl || 0;
            }

            const currentValues = {};
            for (const [pmId, data] of Object.entries(allData)) {
                currentValues[pmId] = data.total_value || 0;
            }

            const { renderChart } = await import('./chart.js');
            renderChart(comparisonData, currentValues, true);

            UI.renderPortfolioStats({
                balance: totalBalance,
                total_value: totalValue,
                total_unrealized_pnl: totalUnrealized,
                total_realized_pnl: totalRealized
            });

            UI.renderModelChat([]);
            UI.renderCompletedTrades([], 'All Portfolios');
            UI.renderPositionsTab({}, totalBalance, totalUnrealized);
            UI.renderStrategyInfo({ name: "All Portfolios", description: "Comparison of all active strategies." });
            UI.renderPortfolioControls({}, 'all');

            // For ALL PMs view, Trades makes the most sense as default
            window.switchTab('completed-trades');

        } else {
            const data = await checkPortfolioStatus(currentPM);

            UI.renderPortfolioControls(data, currentPM);

            if (data.history && data.history.length > 0) {
                const { renderChart } = await import('./chart.js');
                renderChart(data.history, data.total_value, false);
            }
            UI.renderPortfolioStats(data);
            UI.renderModelChat(data.manager_log || [], data.latest_analysis || []);

            // Switch to analyst view if manager_log is empty but latest_analysis exists
            if ((!data.manager_log || data.manager_log.length === 0) && data.latest_analysis && data.latest_analysis.length > 0) {
                window.filterModelChat('analyst');
            }

            UI.renderCompletedTrades(data.trade_log || [], (PM_INFO[currentPM] ? PM_INFO[currentPM].name : 'Unknown PM'));
            UI.renderPositionsTab(data.positions || {}, (data.available_cash !== undefined ? data.available_cash : data.balance) || 0, data.total_unrealized_pnl || 0);
            UI.renderStrategyInfo(data.strategy_info);

            // If we just clicked a PM tab (or on initial PM1 load), default to ModelChat as it has the juiciest data
            if (currentPM !== 'all' && !window._hasSetInitialTab) {
                window.switchTab('modelchat');
                window._hasSetInitialTab = true;
            }
        }

        // Always render CRO at the end
        updateCROStatus();

        // Continue polling if we are in a running state (or just always poll for now)
        // For 'all', we might want to poll too
        setTimeout(checkPortfolioStatusWrapper, 30000); // Poll every 30 seconds

    } catch (error) {
        console.error("Error checking portfolio status:", error);
    }
}

function drawAllSparklines(allData) {
    for (const [pmId, data] of Object.entries(allData)) {
        const canvas = document.getElementById(`sparkline-${pmId}`);
        const badge = document.getElementById(`badge-${pmId}`);
        if (!canvas) continue;

        const history = data.history || [];
        const initialCapital = data.initial_capital || 100000;
        const totalValue = data.total_value || initialCapital;

        // Update badge with return %
        if (badge) {
            const ret = ((totalValue - initialCapital) / initialCapital) * 100;
            badge.textContent = `${ret >= 0 ? '+' : ''}${ret.toFixed(1)}%`;
            badge.className = `text-[10px] px-1 rounded font-mono border ${ret >= 0 ? 'text-accent-teal border-accent-teal/30 bg-accent-teal/10' : 'text-accent-red border-accent-red/30 bg-accent-red/10'}`;
        }

        if (history.length < 2) continue;

        const ctx = canvas.getContext('2d');
        const w = canvas.offsetWidth || 48;
        const h = canvas.offsetHeight || 16;
        canvas.width = w;
        canvas.height = h;
        ctx.clearRect(0, 0, w, h);

        const values = history.map(p => p.total_value);
        if (values.length > 0 && Math.abs(totalValue - values[values.length - 1]) > 0.01) {
            values.push(totalValue);
        }

        const min = Math.min(...values);
        const max = Math.max(...values);
        const range = max - min || 1;

        const isUp = values[values.length - 1] >= values[0];
        ctx.strokeStyle = isUp ? '#00e5a0' : '#ff4d6d';
        ctx.lineWidth = 1.5;
        ctx.beginPath();

        values.forEach((v, i) => {
            const x = (i / (values.length - 1)) * w;
            const y = h - ((v - min) / range) * h;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });

        ctx.stroke();
    }
}

async function updateCROStatus() {
    try {
        const croData = await getCROStatus();
        const container = document.getElementById('cro-gauges-container');
        if (!container) return;

        if (croData.status === 'idle') {
            container.innerHTML = '<div class="text-[10px] text-gray-500">Waiting for CRO limits... (Active)</div>';
            return;
        }

        const limits = croData.limits || {};

        // Parse gauge percent values
        const parseGauge = (current, limit) => {
            if (!limit) return 0;
            return (current / limit) * 100;
        };

        const maxAssetPct = parseGauge(croData.max_asset_pct || 0, limits.max_asset_pct || 1);
        const longPct = parseGauge(croData.long_beta_pct || 0, limits.max_long_beta_pct || 1);
        const shortPct = parseGauge(croData.short_beta_pct || 0, limits.max_short_beta_pct || 1);

        // Colors mapping logic matching CSS gauge-* filters
        const getColor = (pct) => pct > 80 ? 'gauge-red' : (pct > 50 ? 'gauge-amber' : 'gauge-teal');

        const assetColor = getColor(maxAssetPct);
        const longColor = getColor(longPct);
        const shortColor = getColor(shortPct);

        // Circumference for stroke dasharray logic
        const r = 14;
        const c = 2 * Math.PI * r;

        const makeGauge = (current, limit, pct, color, label) => {
            const valDisplay = (current * 100).toFixed(0);
            return `
            <div class="flex flex-col items-center gap-1 relative group cursor-pointer">
                <div class="relative w-10 h-10 flex items-center justify-center">
                    <svg class="w-full h-full transform -rotate-90" viewBox="0 0 32 32">
                        <circle cx="16" cy="16" r="${r}" fill="none" class="gauge-bg" stroke-width="3"></circle>
                        <circle cx="16" cy="16" r="${r}" fill="none" class="gauge-progress ${color}" stroke-width="3" 
                            stroke-dasharray="${c}" stroke-dashoffset="${c - (Math.min(pct, 100) / 100) * c}"></circle>
                    </svg>
                    <span class="absolute text-[10px] font-mono text-white" style="line-height:1;">${valDisplay}%</span>
                </div>
                <span class="text-[9px] font-bold text-gray-500 uppercase tracking-wider">${label}</span>
                
                <!-- Tooltip -->
                <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-32 bg-space-900 border border-glass-border p-2 rounded shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all text-center z-50">
                    <div class="text-[10px] text-gray-400 font-bold uppercase mb-1">${label} Limit</div>
                    <div class="text-xs text-white font-mono">${(current * 100).toFixed(1)}% / ${(limit * 100).toFixed(0)}%</div>
                </div>
            </div>
            `;
        };

        container.innerHTML = `
            ${makeGauge(croData.max_asset_pct || 0, limits.max_asset_pct || 0.4, maxAssetPct, assetColor, 'ASSET')}
            ${makeGauge(croData.long_beta_pct || 0, limits.max_long_beta_pct || 0.7, longPct, longColor, 'LONG')}
            ${makeGauge(croData.short_beta_pct || 0, limits.max_short_beta_pct || 0.4, shortPct, shortColor, 'SHORT')}
        `;
    } catch (e) {
        console.error("CRO status fetch failed", e);
    }
}

async function updateLiveMonitor() {
    try {
        const data = await fetchLiveOverview(50);
        const strip = document.getElementById('live-pm-strip');
        const detail = document.getElementById('live-pm-detail');
        const trades = document.getElementById('live-trades-feed');
        const tail = document.getElementById('live-log-tail');
        const updated = document.getElementById('live-monitor-updated');
        if (!strip || !tail || !updated || !detail || !trades) return;

        const pmIds = ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6'];
        strip.innerHTML = pmIds.map((pmId) => {
            const p = data.pm?.[pmId] || {};
            const running = p.is_running ? '🟢' : '⚪';
            const pos = p.positions_count ?? 0;
            const val = Number(p.total_value || 0).toFixed(0);
            const activeCls = pmId === selectedLivePM ? 'border-accent-teal text-accent-teal' : 'border-glass-border text-gray-300';
            return `<button onclick="window.selectLivePM('${pmId}')" class="bg-black/20 border ${activeCls} rounded px-2 py-1 text-left">${running} <span class="font-bold uppercase">${pmId}</span> | $${val} | ${pos} pos</button>`;
        }).join('');

        const pm = data.pm?.[selectedLivePM] || {};
        const lm = pm.last_manager?.message || 'No manager insight yet';
        const lt = pm.last_trade;
        const tradeText = lt ? `${lt.action || '?'} ${lt.ticker || '?'} @ ${lt.price || '?'} (${lt.timestamp || ''})` : 'No trades yet';
        detail.innerHTML = `<div><span class="text-gray-500">${selectedLivePM.toUpperCase()}:</span> ${lm}</div><div class="text-gray-400 mt-1">Last trade: ${tradeText}</div>`;

        trades.innerHTML = (data.recent_trades || []).map((t) => {
            const cls = /BUY|COVER/i.test(t.action || '') ? 'text-accent-teal' : (/SELL|SHORT/i.test(t.action || '') ? 'text-accent-red' : 'text-gray-300');
            const price = typeof t.price === 'number' ? t.price.toFixed(2) : (t.price || '?');
            return `<div class="${cls}">[${t.pm_id}] ${t.action || '?'} ${t.ticker || '?'} @ $${price}</div>`;
        }).join('') || '<div class="text-gray-500">No trades yet</div>';

        tail.innerHTML = (data.log_tail || []).slice(-50).map((line) => {
            const safe = line
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            const cls = /ERROR|Traceback/i.test(line) ? 'text-accent-red' : (/Phase [123]/.test(line) ? 'text-accent-teal' : 'text-gray-300');
            return `<div class="${cls}">${safe}</div>`;
        }).join('');

        tail.scrollTop = tail.scrollHeight;
        updated.textContent = new Date().toLocaleTimeString();
    } catch (error) {
        console.error('Live monitor update failed:', error);
    }
}

window.selectLivePM = function(pmId) {
    selectedLivePM = pmId;
    updateLiveMonitor();
};

// --- PM Switching ---
window.switchPM = function (pmId) {
    if (currentPM === pmId) return; // Already on this PM

    currentPM = pmId;

    // Update PM tabs styling
    ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6'].forEach(id => {
        const tab = document.getElementById(`pm-tab-${id}`);
        if (!tab) return;

        if (id === pmId) {
            // Active tab
            tab.className = 'pm-tab-active p-3 flex flex-col justify-between gap-2 min-w-[140px] text-left';
        } else {
            // Inactive tab
            tab.className = 'pm-tab-inactive p-3 flex flex-col justify-between gap-2 min-w-[140px] text-left';
        }
    });

    // Handle 'all' case for tabs (deselect all)
    if (pmId === 'all') {
        ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6'].forEach(id => {
            const tab = document.getElementById(`pm-tab-${id}`);
            if (tab) tab.className = 'pm-tab-inactive p-3 flex flex-col justify-between gap-2 min-w-[140px] text-left';
        });
    }

    // Update PM badge
    const badge = document.getElementById('pm-badge');
    if (badge) {
        badge.textContent = PM_INFO[pmId].name;
        badge.setAttribute('data-pm', pmId);
    }

    // Update trading mode badge
    updateTradingModeBadge(pmId);

    // Refresh data for the new PM
    checkPortfolioStatusWrapper();
};

window.switchTab = function (tabId) {
    const tabs = ['completed-trades', 'positions', 'modelchat', 'strategy', 'reports', 'llm-monitor'];
    
    // Toggle main layout vs monitor view
    const dashboardLayout = document.getElementById('dashboard-layout');
    const monitorContent = document.getElementById('llm-monitor-content');
    
    if (tabId === 'llm-monitor') {
        if (dashboardLayout) dashboardLayout.classList.add('hidden');
        if (monitorContent) monitorContent.classList.remove('hidden');
        window.refreshLLMLogs();
        
        // Update tab styling (sidebar button)
        const monitorTab = document.getElementById('tab-llm-monitor');
        if (monitorTab) {
            monitorTab.classList.remove('pm-tab-inactive');
            monitorTab.classList.add('pm-tab-active', 'ring-1', 'ring-amber-500/50');
        }
    } else {
        if (dashboardLayout) dashboardLayout.classList.remove('hidden');
        if (monitorContent) monitorContent.classList.add('hidden');
        
        // Reset monitor tab styling
        const monitorTab = document.getElementById('tab-llm-monitor');
        if (monitorTab) {
            monitorTab.classList.remove('pm-tab-active', 'ring-1', 'ring-amber-500/50');
            monitorTab.classList.add('pm-tab-inactive');
        }

        // Call standard UI switch tab for the right column
        UI.switchTab(tabId);
        
        // Fetch reports if the reports tab is selected
        if (tabId === 'reports' && typeof window.fetchAndRenderReports === 'function') {
            window.fetchAndRenderReports();
        }
    }
};

window.openLLMMonitor = async function () {
    try {
        const { fetchLLMLogs } = await import('./api.js');
        const logs = await fetchLLMLogs();
        UI.renderLLMMonitorModal(logs);
    } catch (error) {
        console.error('Failed to fetch LLM logs:', error);
    }
};

window.refreshLLMLogs = async function () {
    try {
        const { fetchLLMLogs } = await import('./api.js');
        const logs = await fetchLLMLogs();
        UI.renderLLMLogs(logs);
    } catch (error) {
        console.error('Failed to fetch LLM logs:', error);
    }
};

// Update trading mode badge based on config
async function updateTradingModeBadge(pmId) {
    const modeBadge = document.getElementById('trading-mode-badge');
    if (!modeBadge) return;

    if (pmId === 'all') {
        // For "all" view, show PAPER by default
        modeBadge.textContent = 'PAPER MODE';
        modeBadge.setAttribute('data-mode', 'PAPER');
        modeBadge.className = 'px-2 py-0.5 text-[10px] md:text-xs font-bold tracking-widest text-white border border-glass-border bg-space-200 rounded';
        return;
    }

    try {
        // Fetch trading mode from backend
        const response = await fetch(`/api/trading-mode/${pmId}`);
        if (response.ok) {
            const data = await response.json();
            const mode = data.mode || 'PAPER';

            modeBadge.setAttribute('data-mode', mode);

            if (mode === 'LIVE') {
                // Red pulsing badge for LIVE
                modeBadge.className = 'px-2 py-0.5 text-[10px] md:text-xs font-bold bg-accent-red/30 border border-accent-red text-accent-red rounded animate-pulse tracking-widest';
                modeBadge.textContent = '🔴 LIVE';
            } else {
                // Subtle badge for PAPER
                modeBadge.className = 'px-2 py-0.5 text-[10px] md:text-xs font-bold tracking-widest text-white border border-glass-border bg-space-200 rounded';
                modeBadge.textContent = 'PAPER MODE';
            }
        }
    } catch (error) {
        console.error('Failed to fetch trading mode:', error);
        // Default to PAPER on error
        modeBadge.textContent = 'PAPER MODE';
        modeBadge.className = 'px-2 py-0.5 text-[10px] md:text-xs font-bold tracking-widest text-white border border-glass-border bg-space-200 rounded';
    }
}

// --- Event Listeners & Global Exports ---

// Expose functions to window for HTML onclick attributes
// We don't overwrite window.switchTab here, it's defined above properly.

window.setInitialCapital = async function () {
    const capitalInput = document.getElementById('initial-capital');
    const capital = parseFloat(capitalInput.value);

    if (!capital || capital <= 0) {
        alert("Please enter a valid capital amount.");
        return;
    }

    try {
        await startPortfolio(currentPM, capital);
        alert(`${PM_INFO[currentPM].label} initialized with $${capital.toFixed(2)}`);
        fetchDashboardDataWrapper();
        checkPortfolioStatusWrapper();
    } catch (error) {
        alert(error.message);
    }
};

window.startAllPortfolios = async function () {
    const capitalInput = document.getElementById('initial-capital-all');
    const capital = parseFloat(capitalInput.value);

    if (!capital || capital <= 0) {
        alert("Please enter a valid capital amount.");
        return;
    }

    if (!confirm(`Start ALL portfolios (PM1-PM5) with $${capital.toFixed(2)} each?`)) {
        return;
    }

    try {
        await startAllPortfolios(capital);
        alert(`All portfolios initialized with $${capital.toFixed(2)}`);
        fetchDashboardDataWrapper();
        checkPortfolioStatusWrapper();
    } catch (error) {
        alert(error.message);
    }
};

window.simulateMarketCheck = async function () {
    try {
        const lastCheckTime = document.getElementById('last-check-time');
        await triggerMarketCheck(currentPM);
        if (lastCheckTime) {
            lastCheckTime.textContent = new Date().toLocaleTimeString();
        }
        alert("Market check triggered successfully for " + PM_INFO[currentPM].label);
        setTimeout(() => checkPortfolioStatusWrapper(), 2000);
    } catch (error) {
        alert("Failed to trigger market check: " + error.message);
    }
};

window.restartPortfolio = async function () {
    const pmLabel = PM_INFO[currentPM].label;
    if (!confirm(`Are you sure you want to stop ${pmLabel}? This will end the current run and you can start a new one.`)) {
        return;
    }

    try {
        const { restartPortfolio: restartAPI } = await import('./api.js');
        await restartAPI(currentPM);
        alert(`${pmLabel} has been stopped. You can now start a new run.`);
        checkPortfolioStatusWrapper();
    } catch (error) {
        alert("Failed to restart portfolio: " + error.message);
    }
};

window.startPortfolio = window.setInitialCapital; // Alias if needed
window.triggerMarketCheck = window.simulateMarketCheck; // Alias if needed



// Open full-screen report modal (primarily for mobile)
window.openReportModal = function (ticker, action, confidence, reportContent, actionColor) {
    const modal = document.getElementById('report-modal');
    const modalTicker = document.getElementById('modal-report-title');
    const modalAction = document.getElementById('modal-report-type');
    const modalConfidence = document.getElementById('modal-report-pm');
    const modalContent = document.getElementById('modal-report-content');

    if (!modal || !modalTicker || !modalAction || !modalConfidence || !modalContent) return;

    // Set content
    modalTicker.textContent = ticker;
    modalAction.textContent = action;
    modalAction.className = `text-xs font-bold px-3 py-1 rounded-full uppercase tracking-widest bg-space-200 border border-glass-border ${actionColor}`;
    modalConfidence.textContent = confidence;
    // Render markdown content as HTML
    if (typeof marked !== 'undefined') {
        modalContent.innerHTML = reportContent ? marked.parse(reportContent) : 'No content available.';
    } else {
        // Fallback: basic markdown-like rendering
        modalContent.innerHTML = reportContent
            .replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold mt-4 mb-2 text-gray-900">$1</h2>')
            .replace(/^### (.+)$/gm, '<h3 class="text-base font-bold mt-3 mb-1 text-gray-800">$1</h3>')
            .replace(/\*\*(.+?)\*\*/g, '<strong class="font-bold">$1</strong>')
            .replace(/---/g, '<hr class="my-3 border-gray-200">')
            .replace(/\|(.+)\|/g, (match) => {
                const cells = match.split('|').filter(c => c.trim());
                return '<div class="flex gap-4 py-1">' + cells.map(c => `<span class="flex-1">${c.trim()}</span>`).join('') + '</div>';
            })
            .replace(/- (.+)/g, '<li class="ml-4 list-disc">$1</li>')
            .replace(/\n/g, '<br>');
    }

    // Show modal
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    // Prevent body scroll
    document.body.style.overflow = 'hidden';
};

// Open report modal by index (safe method that avoids escaping issues)
window.openReportByIndex = function (index) {
    if (!window._analysisData || !window._analysisData[index]) {
        console.error('Report data not found at index:', index);
        return;
    }

    const item = window._analysisData[index];
    const ticker = item.ticker || 'Unknown';
    const analystReport = item.analyst_report || 'No report available';
    const summary = item.summary || {};
    const action = summary.action_type || 'WAIT';
    const confidence = summary.confidence_score || 0;
    const actionColor = action.includes('BUY') || action.includes('LONG') ? 'text-green-600' : (action.includes('SELL') || action.includes('SHORT') ? 'text-red-600' : 'text-gray-600');

    // Now call the original modal function with the safely retrieved data
    const modal = document.getElementById('report-modal');
    const modalTicker = document.getElementById('modal-report-title');
    const modalAction = document.getElementById('modal-report-type');
    const modalConfidence = document.getElementById('modal-report-pm');
    const modalContent = document.getElementById('modal-report-content');

    if (!modal || !modalTicker || !modalAction || !modalConfidence || !modalContent) return;

    // Set content
    modalTicker.textContent = ticker;
    modalAction.textContent = action;
    modalAction.className = `text-xs font-bold px-3 py-1 rounded-full uppercase tracking-widest bg-space-200 border border-glass-border ${actionColor}`;
    modalConfidence.textContent = confidence;

    // Render markdown content as HTML
    if (typeof marked !== 'undefined') {
        modalContent.innerHTML = marked.parse(analystReport);
    } else {
        // Fallback: basic markdown-like rendering
        modalContent.innerHTML = analystReport
            .replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold mt-4 mb-2 text-gray-900">$1</h2>')
            .replace(/^### (.+)$/gm, '<h3 class="text-base font-bold mt-3 mb-1 text-gray-800">$1</h3>')
            .replace(/\*\*(.+?)\*\*/g, '<strong class="font-bold">$1</strong>')
            .replace(/---/g, '<hr class="my-3 border-gray-200">')
            .replace(/- (.+)/g, '<li class="ml-4 list-disc">$1</li>')
            .replace(/\n/g, '<br>');
    }

    // Show modal
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    // Prevent body scroll
    document.body.style.overflow = 'hidden';
};

// Close report modal
window.closeReportModal = function () {
    const modal = document.getElementById('report-modal');
    if (!modal) return;

    modal.classList.add('hidden');
    modal.classList.remove('flex');

    // Restore body scroll
    document.body.style.overflow = '';
};

// Start
init();
