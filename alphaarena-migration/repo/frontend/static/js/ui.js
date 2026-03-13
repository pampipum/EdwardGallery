import { findCompletedTrades, calculateHoldingTime } from './utils.js';
import { renderChart } from './chart.js';

// Helper to safely get element
const getEl = (id) => document.getElementById(id);

// Shared icon helper for tickers
const getTickerIcon = (ticker, size = 'w-5 h-5', textSize = 'text-[10px]') => {
    const icons = {
        'BTC': { char: '₿', bg: '#f7931a', shadow: 'rgba(247,147,26,0.4)', text: 'text-white' },
        'ETH': { char: 'Ξ', bg: '#627eea', shadow: 'rgba(98,126,234,0.4)', text: 'text-white' },
        'SOL': { char: 'S', bg: '#14f195', shadow: 'rgba(20,241,149,0.4)', text: 'text-black' },
        'TSLA': { char: 'T', bg: '#e82127', shadow: 'rgba(232,33,39,0.4)', text: 'text-white' },
        'GOOG': { char: 'G', bg: '#4285f4', shadow: 'rgba(66,133,244,0.4)', text: 'text-white' },
        'GOOGL': { char: 'G', bg: '#4285f4', shadow: 'rgba(66,133,244,0.4)', text: 'text-white' },
        'NVDA': { char: 'N', bg: '#76b900', shadow: 'rgba(118,185,0,0.4)', text: 'text-white' },
        'META': { char: 'M', bg: '#0668e1', shadow: 'rgba(6,104,225,0.4)', text: 'text-white' },
        'AAPL': { char: 'A', bg: '#a3aaae', shadow: 'rgba(163,170,174,0.4)', text: 'text-white' },
        'AMD': { char: 'A', bg: '#ed1c24', shadow: 'rgba(237,28,36,0.4)', text: 'text-white' },
        'TSM': { char: 'T', bg: '#00599f', shadow: 'rgba(0,89,159,0.4)', text: 'text-white' },
        'ASML': { char: 'A', bg: '#00a1e0', shadow: 'rgba(0,161,224,0.4)', text: 'text-white' },
        'MU': { char: 'M', bg: '#007cc3', shadow: 'rgba(0,124,195,0.4)', text: 'text-white' },
        'MRVL': { char: 'M', bg: '#000000', shadow: 'rgba(255,255,255,0.2)', text: 'text-white' },
        'ARM': { char: 'A', bg: '#0091bd', shadow: 'rgba(0,145,189,0.4)', text: 'text-white' },
        'AVGO': { char: 'B', bg: '#cc092f', shadow: 'rgba(204,9,47,0.4)', text: 'text-white' },
        'ALAB': { char: 'A', bg: '#3944bc', shadow: 'rgba(57,68,188,0.4)', text: 'text-white' },
        'PLTR': { char: 'P', bg: '#101111', shadow: 'rgba(255,255,255,0.2)', text: 'text-white' }
    };

    const entry = Object.entries(icons).find(([key]) => ticker.includes(key));
    if (entry) {
        const { char, bg, shadow, text } = entry[1];
        return `<div class="${size} rounded-full bg-[${bg}] flex items-center justify-center ${textSize} font-bold ${text} shadow-[0_0_8px_${shadow}]">${char}</div>`;
    }
    return `<div class="${size} rounded-full bg-gray-600 flex items-center justify-center ${textSize} font-bold text-white shadow-[0_0_8px_rgba(156,163,175,0.4)]">?</div>`;
};

export function renderTickerTape(data) {
    const tickerTape = getEl('ticker-tape');
    if (!tickerTape || !Array.isArray(data)) return;

    const items = data.map(item => {
        const { ticker, summary, technical_context } = item;
        let price = '0.00';
        if (item.price !== undefined && item.price !== null) {
            price = typeof item.price === 'number' ? item.price.toFixed(2) : item.price;
        } else if (technical_context && technical_context.price_action) {
            price = technical_context.price_action.match(/Price is (\d+\.\d+)/)?.[1] || '0.00';
        }
        const trendIcon = summary.current_trend.includes('Bullish') ? '▲' : (summary.current_trend.includes('Bearish') ? '▼' : '▬');
        const colorClass = summary.current_trend.includes('Bullish') ? 'text-accent-teal' : (summary.current_trend.includes('Bearish') ? 'text-accent-red' : 'text-gray-500');
        return `
            <div class="ticker-pill !inline-flex flex-row items-center whitespace-nowrap align-middle h-8">
                ${getTickerIcon(ticker)}
                <span class="font-bold text-white tracking-widest text-xs ml-2">${ticker.replace('-USD', '')}</span>
                <span class="font-mono text-gray-300 ml-2">$${price}</span>
                <span class="${colorClass} font-mono font-bold ml-1 text-[10px]">${trendIcon}</span>
            </div>
        `;
    }).join('');
    tickerTape.innerHTML = items + items + items;
}

export function switchTab(tabName) {
    const contentCompletedTrades = getEl('content-completed-trades');
    const contentModelchat = getEl('content-modelchat');
    const contentPositions = getEl('content-positions');
    const contentStrategy = getEl('content-strategy');
    const contentReports = getEl('content-reports');

    ['tab-completed-trades', 'tab-modelchat', 'tab-positions', 'tab-strategy', 'tab-reports'].forEach(id => {
        const el = getEl(id);
        if (el) {
            el.classList.remove('sub-tab-active');
            el.classList.add('sub-tab-inactive');
        }
    });

    if (contentCompletedTrades) contentCompletedTrades.classList.add('hidden');
    if (contentModelchat) contentModelchat.classList.add('hidden');
    if (contentPositions) contentPositions.classList.add('hidden');
    if (contentStrategy) contentStrategy.classList.add('hidden');
    if (contentReports) contentReports.classList.add('hidden');

    const selectedContent = getEl(`content-${tabName}`);
    if (selectedContent) selectedContent.classList.remove('hidden');

    const selectedTab = getEl(`tab-${tabName}`);
    if (selectedTab) {
        selectedTab.classList.remove('sub-tab-inactive');
        selectedTab.classList.add('sub-tab-active');
    }
}

export function renderLLMMonitorModal(logs) {
    const modal = getEl('report-modal');
    const modalTitle = getEl('modal-report-title');
    const modalType = getEl('modal-report-type');
    const modalPM = getEl('modal-report-pm');
    const modalContent = getEl('modal-report-content');

    if (!modal || !modalContent) return;

    modalTitle.textContent = "LLM API SUPERVISION";
    modalType.textContent = "Cost Monitoring";
    modalType.className = "text-[10px] font-black text-amber-500 tracking-widest uppercase";
    modalPM.textContent = "SYSTEM";

    let totalCost = logs.reduce((sum, log) => sum + (log.cost || 0), 0);

    const logRows = [...logs].reverse().map((log, index) => {
        const date = new Date(log.timestamp).toLocaleTimeString();
        return `
            <tr class="border-b border-glass-border hover:bg-white/5 transition-colors group text-[11px]">
                <td class="py-3 text-gray-400 font-mono">${date}</td>
                <td class="py-3 font-bold">${log.pm_id}</td>
                <td class="py-3 text-gray-300 truncate max-w-[100px]">${log.model}</td>
                <td class="py-3 text-amber-500 font-bold">${log.purpose}</td>
                <td class="py-3 text-gray-400 font-mono">${log.tokens_in}/${log.tokens_out}</td>
                <td class="py-3 text-accent-teal font-mono font-bold">$${(log.cost || 0).toFixed(6)}</td>
                <td class="py-3 text-right">
                    <button onclick="window.viewLogDetail(${logs.length - 1 - index})" class="text-[9px] text-gray-500 hover:text-white border border-glass-border px-2 py-0.5 rounded">VIEW</button>
                </td>
            </tr>
        `;
    }).join('');

    modalContent.innerHTML = `
        <div class="flex flex-col gap-6">
            <div class="bg-black/20 p-4 rounded-xl border border-glass-border flex justify-between items-center">
                <div>
                    <p class="text-[10px] text-gray-500 font-mono uppercase">Total Est. Session Cost</p>
                    <p class="text-3xl font-black text-amber-500 font-mono">$${totalCost.toFixed(6)}</p>
                </div>
                <div class="text-right text-gray-500 font-mono text-xs">${logs.length} Requests</div>
            </div>
            <table class="w-full text-left">
                <thead>
                    <tr class="text-[10px] text-gray-500 uppercase border-b border-glass-border">
                        <th class="pb-2">Time</th><th class="pb-2">PM</th><th class="pb-2">Model</th><th class="pb-2">Purpose</th><th class="pb-2">Tokens</th><th class="pb-2">Cost</th><th class="pb-2"></th>
                    </tr>
                </thead>
                <tbody>${logRows}</tbody>
            </table>
        </div>
    `;

    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.body.style.overflow = 'hidden';
    window._llmLogs = logs;
}

window.viewLogDetail = function(index) {
    const log = window._llmLogs[index];
    if (!log) return;
    const modalContent = `
        <div class="space-y-6">
            <div class="grid grid-cols-2 gap-4">
                <div class="bg-space-200 p-3 rounded border border-glass-border">
                    <p class="text-[10px] text-gray-500 font-mono uppercase">Model</p>
                    <p class="text-sm font-bold text-white">${log.model}</p>
                </div>
                <div class="bg-space-200 p-3 rounded border border-glass-border">
                    <p class="text-[10px] text-gray-500 font-mono uppercase">Estimated Cost</p>
                    <p class="text-sm font-bold text-accent-teal">$${(log.cost || 0).toFixed(6)}</p>
                </div>
            </div>
            <div>
                <p class="text-xs font-bold text-amber-500 mb-2 uppercase tracking-widest">Prompt</p>
                <div class="bg-black/40 p-4 rounded border border-glass-border text-xs font-mono text-gray-300 whitespace-pre-wrap max-h-60 overflow-y-auto">${log.prompt_preview}</div>
            </div>
            <div>
                <p class="text-xs font-bold text-accent-teal mb-2 uppercase tracking-widest">Response</p>
                <div class="bg-black/40 p-4 rounded border border-glass-border text-xs font-mono text-gray-300 whitespace-pre-wrap max-h-60 overflow-y-auto">${log.response_preview}</div>
            </div>
        </div>
    `;
    document.getElementById('modal-report-content').innerHTML = modalContent;
};

export function renderStrategyInfo(strategyInfo) {
    const strategyContent = getEl('strategy-content');
    if (!strategyContent || !strategyInfo) return;
    
    strategyContent.innerHTML = `
        <div class="space-y-4 text-white">
            <div class="border-b border-glass-border pb-2">
                <h3 class="text-lg font-bold tracking-wide">${strategyInfo.name}</h3>
                <p class="text-sm text-gray-400 mt-1">${strategyInfo.description}</p>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div class="p-3 bg-space-200 border border-glass-border rounded">
                    <div class="text-[10px] font-bold text-gray-500 uppercase mb-1">Confidence Threshold</div>
                    <div class="text-xl font-mono text-accent-teal">${strategyInfo.confidence_threshold}/10</div>
                </div>
                <div class="p-3 bg-space-200 border border-glass-border rounded">
                    <div class="text-[10px] font-bold text-gray-500 uppercase mb-1">Max Position</div>
                    <div class="text-xl font-mono">${(strategyInfo.max_position_size * 100).toFixed(0)}%</div>
                </div>
            </div>
            ${strategyInfo.prompt_modifier ? `
            <div class="border-t border-glass-border pt-4">
                <h4 class="text-[10px] font-bold text-gray-500 uppercase mb-2">AI Instructions</h4>
                <div class="p-3 bg-black/20 border border-glass-border rounded text-xs font-mono text-accent-teal/80 whitespace-pre-wrap leading-relaxed">
                    ${strategyInfo.prompt_modifier.trim()}
                </div>
            </div>
            ` : ''}
        </div>
    `;
}

let currentModelChatData = { manager_log: [], latest_analysis: [] };
let currentFilterMode = 'manager';
let currentAssetFilter = 'ALL';

export function renderModelChat(logs, latestAnalysis = []) {
    const modelchatFeed = getEl('modelchat-feed');
    if (!modelchatFeed) return;
    currentModelChatData = { manager_log: logs || [], latest_analysis: latestAnalysis || [] };
    applyModelChatFilter();
}

function applyModelChatFilter() {
    const modelchatFeed = getEl('modelchat-feed');
    const assetFilterEl = getEl('modelchat-asset-filter');
    if (!modelchatFeed) return;
    if (currentFilterMode === 'manager') {
        if (assetFilterEl) assetFilterEl.style.display = 'none';
        const recentLogs = currentModelChatData.manager_log.slice().reverse();
        if (recentLogs.length === 0) {
            modelchatFeed.innerHTML = '<div class="text-center text-gray-400 text-xs mt-10 uppercase tracking-widest">No Intelligence Data</div>';
            return;
        }
        modelchatFeed.innerHTML = recentLogs.map(log => `<div class="glass-card p-4 mb-3 border border-glass-border bg-white/5"><div class="flex justify-between mb-2"><span class="text-[10px] font-black text-accent-teal uppercase tracking-widest">PM REASONING</span><span class="text-[10px] text-gray-500 font-mono">${new Date(log.timestamp).toLocaleTimeString()}</span></div><p class="text-sm text-gray-300 leading-relaxed">${log.message}</p></div>`).join('');
    } else {
        if (assetFilterEl) {
            assetFilterEl.style.display = 'inline-block';
            const tickers = ['ALL', ...new Set(currentModelChatData.latest_analysis.map(item => item.ticker))];
            assetFilterEl.innerHTML = tickers.map(t => `<option value="${t}">${t}</option>`).join('');
            assetFilterEl.value = currentAssetFilter;
        }
        let analysis = currentModelChatData.latest_analysis;
        if (currentAssetFilter !== 'ALL') analysis = analysis.filter(item => item.ticker === currentAssetFilter);
        if (!analysis || analysis.length === 0) {
            modelchatFeed.innerHTML = '<div class="text-center text-gray-400 text-xs mt-10 uppercase tracking-widest">No Reports</div>';
            return;
        }
        window._analysisData = analysis;
        modelchatFeed.innerHTML = analysis.map((item, index) => `<div class="glass-card p-4 mb-3 border border-glass-border bg-white/5"><div class="flex justify-between items-center mb-3 pb-2 border-b border-glass-border"><span class="text-lg font-black text-white font-mono">${item.ticker}</span><button onclick="window.openReportByIndex(${index})" class="text-[10px] font-bold text-accent-teal border border-accent-teal/30 px-2 py-1 rounded hover:bg-accent-teal/10 transition-all uppercase">Open Report</button></div><div class="text-xs text-gray-400 line-clamp-3">${item.analyst_report}</div></div>`).join('');
    }
}

window.filterModelChat = function (mode) { currentFilterMode = mode; applyModelChatFilter(); }
window.filterModelChatAsset = function (asset) { currentAssetFilter = asset; applyModelChatFilter(); }

export function renderCompletedTrades(trades, pmName = 'Unknown PM') {
    const completedTradesList = getEl('completed-trades-list');
    if (!completedTradesList) return;
    const completedTrades = findCompletedTrades(trades);
    if (completedTrades.length === 0) {
        completedTradesList.innerHTML = '<div class="text-center text-gray-400 text-xs mt-10 uppercase tracking-widest">No History</div>';
        return;
    }
    completedTradesList.innerHTML = completedTrades.map(trade => `<div class="border-b border-glass-border pb-4 mb-4 last:border-0"><div class="flex items-center justify-between mb-2"><div class="flex items-center gap-2">${getTickerIcon(trade.ticker, 'w-5 h-5', 'text-[10px]')}<span class="font-black text-white">${trade.ticker}</span><span class="text-[10px] font-bold uppercase ${trade.side === 'SHORT' ? 'text-accent-red' : 'text-accent-teal'}">${trade.side}</span></div><span class="text-[10px] text-gray-500 font-mono">${new Date(trade.exit_time).toLocaleTimeString()}</span></div><div class="grid grid-cols-3 gap-2 text-[11px] bg-white/5 p-2 rounded border border-glass-border"><div><p class="text-gray-500 uppercase text-[9px] font-bold">P&L</p><p class="${trade.pnl >= 0 ? 'text-accent-teal' : 'text-accent-red'} font-bold">$${trade.pnl.toFixed(2)}</p></div><div><p class="text-gray-500 uppercase text-[9px] font-bold">QTY</p><p class="text-white">${Math.abs(trade.qty).toFixed(4)}</p></div><div><p class="text-gray-500 uppercase text-[9px] font-bold">PRICE</p><p class="text-white">$${trade.exit_price.toFixed(2)}</p></div></div></div>`).join('');
}

export function renderPositionsTab(positions, balance, totalUnrealizedPnL) {
    const positionsContent = getEl('positions-content');
    if (!positionsContent) return;
    const tickers = Object.keys(positions);
    const posHTML = tickers.length === 0 ? '<div class="text-center text-gray-400 text-xs mt-10 uppercase tracking-widest">No Open Positions</div>' : tickers.map(ticker => {
        const pos = positions[ticker];
        const unrealizedPnL = pos.unrealized_pnl || 0;
        return `<div class="border-b border-glass-border pb-4 mb-4 last:border-0"><div class="flex items-center justify-between mb-2"><div class="flex items-center gap-2">${getTickerIcon(ticker, 'w-5 h-5', 'text-[10px]')}<span class="font-black text-white">${ticker}</span><span class="text-[10px] font-bold uppercase ${pos.qty > 0 ? 'text-accent-teal' : 'text-accent-red'}">${pos.qty > 0 ? 'LONG' : 'SHORT'}</span></div></div><div class="grid grid-cols-3 gap-2 text-[11px] bg-white/5 p-2 rounded border border-glass-border"><div><p class="text-gray-500 uppercase text-[9px] font-bold">UNREALIZED</p><p class="${unrealizedPnL >= 0 ? 'text-accent-teal' : 'text-accent-red'} font-bold">$${unrealizedPnL.toFixed(2)}</p></div><div><p class="text-gray-500 uppercase text-[9px] font-bold">QTY</p><p class="text-white">${Math.abs(pos.qty).toFixed(4)}</p></div><div><p class="text-gray-500 uppercase text-[9px] font-bold">AVG PRICE</p><p class="text-white">$${pos.avg_price.toFixed(2)}</p></div></div></div>`;
    }).join('');
    positionsContent.innerHTML = `<div class="mb-4 p-3 bg-white/5 border border-glass-border rounded-xl"><div class="flex justify-between items-center mb-1"><span class="text-[10px] font-bold text-gray-500 uppercase">Unrealized P&L</span><span class="text-lg font-black font-mono ${totalUnrealizedPnL >= 0 ? 'text-accent-teal' : 'text-accent-red'}">${totalUnrealizedPnL >= 0 ? '+' : ''}$${totalUnrealizedPnL.toFixed(2)}</span></div><div class="flex justify-between items-center"><span class="text-[10px] font-bold text-gray-500 uppercase">Available Cash</span><span class="text-sm font-mono text-white">$${balance.toFixed(2)}</span></div></div>${posHTML}`;
}

export function renderPortfolioControls(data, pmId = 'pm1') {
    const portfolioControls = getEl('portfolio-controls');
    if (!portfolioControls) return;
    if (pmId === 'all' || data.is_running) { portfolioControls.classList.add('hidden'); return; }
    portfolioControls.classList.remove('hidden');
    portfolioControls.innerHTML = `<div class="text-sm font-bold mb-3 border-b border-glass-border pb-2 text-white uppercase">${pmId} INITIALIZATION</div><div class="flex gap-2"><input type="number" id="initial-capital" value="10000" class="flex-1 bg-space-800 border border-glass-border px-2 py-1 text-sm font-mono rounded text-white"><button onclick="setInitialCapital()" class="bg-accent-teal/20 border border-accent-teal/50 text-accent-teal px-3 py-1 text-xs font-bold rounded hover:bg-accent-teal hover:text-black transition-all">START</button></div>`;
}

export function renderPortfolioStats(data) {
    const balanceDisplay = getEl('balance-display');
    const totalValueDisplay = getEl('total-value-display');
    const unrealizedPnlDisplay = getEl('unrealized-pnl-display');
    const realizedPnlDisplay = getEl('realized-pnl-display');
    if (balanceDisplay) balanceDisplay.textContent = `$${(data.balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
    if (totalValueDisplay) totalValueDisplay.textContent = `$${(data.total_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
    if (unrealizedPnlDisplay) {
        const upnl = data.total_unrealized_pnl || 0;
        unrealizedPnlDisplay.textContent = `${upnl >= 0 ? '+' : ''}$${upnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
        unrealizedPnlDisplay.className = `text-lg md:text-2xl font-bold font-mono ${upnl >= 0 ? 'text-accent-teal' : 'text-accent-red'}`;
    }
    if (realizedPnlDisplay) {
        const rpnl = data.total_realized_pnl || 0;
        realizedPnlDisplay.textContent = `${rpnl >= 0 ? '+' : ''}$${rpnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
        realizedPnlDisplay.className = `text-lg md:text-2xl font-bold font-mono ${rpnl >= 0 ? 'text-accent-teal' : 'text-accent-red'}`;
    }
    renderChart(data.history, data.total_value);
}

export function focusModelChat() {
    const chatFeed = getEl('modelchat-feed');
    if (!chatFeed) return;
    chatFeed.scrollIntoView({ behavior: 'smooth' });
}
