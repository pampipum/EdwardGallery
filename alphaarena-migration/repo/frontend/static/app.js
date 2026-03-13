const API_BASE = '/api';

// DOM Elements
const loadingState = document.getElementById('loading-state');
const dashboardContent = document.getElementById('dashboard-content');
const signalsTableBody = document.getElementById('signals-table-body');
const noSignalsMsg = document.getElementById('no-signals-msg');
const assetsGrid = document.getElementById('assets-grid');

// Portfolio Elements
const portfolioControls = document.getElementById('portfolio-controls');
const portfolioSection = document.getElementById('portfolio-section');
const totalBalanceEl = document.getElementById('total-balance');
const totalPnlEl = document.getElementById('total-pnl');
const activePositionsCountEl = document.getElementById('active-positions-count');
const managerInsightEl = document.getElementById('manager-insight');
const positionsBody = document.getElementById('positions-body');
const tradeLogBody = document.getElementById('trade-log-body');
let performanceChart = null;

async function init() {
    try {
        // 1. Check Portfolio Status
        // This will determine if we should show the dashboard or just the start screen
        await checkPortfolioStatus();
    } catch (error) {
        console.error('Failed to initialize:', error);
    }
}

async function fetchDashboardData() {
    try {
        loadingState.classList.remove('hidden');
        dashboardContent.classList.add('hidden');

        // Fetch Dashboard Data (Analysis of all assets)
        const response = await fetch(`${API_BASE}/dashboard`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        renderDashboard(data);
    } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
        loadingState.innerHTML = `<p class="text-red-500">Failed to load analysis. Please try again.<br><span class="text-xs text-gray-500">${error.message}</span></p>`;
    }
}

// --- Portfolio Logic ---

async function checkPortfolioStatus() {
    try {
        const response = await fetch(`${API_BASE}/portfolio/status`);
        const data = await response.json();

        renderPortfolioControls(data);

        if (data.is_running) {
            renderPortfolioStats(data);

            // Only fetch dashboard analysis if we haven't already (or if we want to refresh)
            if (dashboardContent.classList.contains('hidden') && !loadingState.classList.contains('hidden')) {
                fetchDashboardData();
            }

            // Start Polling
            setTimeout(checkPortfolioStatus, 5000);
        } else {
            // Ensure loading state is hidden if we are just showing the start screen
            loadingState.classList.add('hidden');
        }
    } catch (error) {
        console.error("Error checking portfolio status:", error);
    }
}

function renderPortfolioControls(data) {
    if (!data.is_running) {
        portfolioControls.innerHTML = `
            <input type="number" id="capital-input" placeholder="Enter Capital ($)" class="bg-gray-800 text-white px-3 py-2 rounded border border-gray-700 focus:border-blue-500 outline-none w-40">
            <button onclick="startPortfolio()" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded font-medium transition-colors">
                Start Portfolio Manager
            </button>
        `;
        portfolioSection.classList.add('hidden');
    } else {
        portfolioControls.innerHTML = `
            <button onclick="triggerMarketCheck()" class="bg-gray-800 hover:bg-gray-700 text-white px-4 py-2 rounded font-medium border border-gray-700 transition-colors flex items-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                Simulate Market Check
            </button>
            <div class="px-3 py-2 bg-green-500/10 text-green-400 rounded border border-green-500/20 text-sm font-bold">
                Running
            </div>
        `;
        portfolioSection.classList.remove('hidden');
    }
}

async function startPortfolio() {
    const capitalInput = document.getElementById('capital-input');
    const capital = parseFloat(capitalInput.value);

    if (!capital || capital <= 0) {
        alert("Please enter a valid starting capital.");
        return;
    }

    try {
        await fetch(`${API_BASE}/portfolio/start?capital=${capital}`, { method: 'POST' });
        // After starting, fetch the dashboard data
        fetchDashboardData();
        checkPortfolioStatus(); // Refresh UI
    } catch (error) {
        alert("Failed to start portfolio: " + error.message);
    }
}

async function triggerMarketCheck() {
    try {
        await fetch(`${API_BASE}/portfolio/tick`, { method: 'POST' });
        alert("Market check triggered! The AI is analyzing assets...");
        // Status will update on next poll
    } catch (error) {
        alert("Failed to trigger market check.");
    }
}

function renderPortfolioStats(data) {
    // 1. Top Cards
    const totalValue = data.history[data.history.length - 1].total_value;
    const pnl = totalValue - data.initial_capital;
    const pnlPercent = (pnl / data.initial_capital) * 100;

    totalBalanceEl.innerText = `$${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    totalPnlEl.innerHTML = `<span class="${pnl >= 0 ? 'text-green-500' : 'text-red-500'}">
        ${pnl >= 0 ? '+' : ''}$${pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })} (${pnlPercent.toFixed(2)}%)
    </span>`;
    activePositionsCountEl.innerText = Object.keys(data.positions).length;

    // 2. Manager Insight
    if (data.manager_log && data.manager_log.length > 0) {
        const latestLog = data.manager_log[data.manager_log.length - 1];
        managerInsightEl.innerHTML = `"${latestLog.message}" <br><span class="text-xs text-gray-500 not-italic mt-1 block text-right">- ${new Date(latestLog.timestamp).toLocaleTimeString()}</span>`;
    } else {
        managerInsightEl.innerText = "Waiting for first market check...";
    }

    // 3. Positions Table
    positionsBody.innerHTML = Object.entries(data.positions).map(([ticker, pos]) => {
        const value = pos.qty * pos.avg_price; // Note: This uses avg_price, ideally use current price if available
        return `
            <tr class="border-b border-gray-800">
                <td class="py-2 font-bold text-white">${ticker}</td>
                <td class="py-2 text-gray-400">${pos.qty.toFixed(4)}</td>
                <td class="py-2 text-gray-400">$${pos.avg_price.toFixed(2)}</td>
                <td class="py-2 text-white font-mono">$${value.toFixed(2)}</td>
            </tr>
        `;
    }).join('') || '<tr><td colspan="4" class="py-4 text-center text-gray-500">No active positions</td></tr>';

    // 4. Trade Log
    tradeLogBody.innerHTML = data.trade_log.slice().reverse().map(trade => {
        const color = trade.action === 'BUY' ? 'text-green-500' : 'text-red-500';
        return `
            <tr class="border-b border-gray-800">
                <td class="py-2 text-gray-500 text-xs">${new Date(trade.timestamp).toLocaleTimeString()}</td>
                <td class="py-2 font-bold ${color}">${trade.action}</td>
                <td class="py-2 text-white">${trade.ticker}</td>
                <td class="py-2 text-gray-400">$${trade.price.toFixed(2)}</td>
            </tr>
        `;
    }).join('') || '<tr><td colspan="4" class="py-4 text-center text-gray-500">No trades executed yet</td></tr>';

    // 5. Chart
    renderChart(data.history);
}

function renderChart(history) {
    const ctx = document.getElementById('performanceChart').getContext('2d');
    const labels = history.map(h => new Date(h.timestamp).toLocaleTimeString());
    const values = history.map(h => h.total_value);

    if (performanceChart) {
        performanceChart.data.labels = labels;
        performanceChart.data.datasets[0].data = values;
        performanceChart.update();
    } else {
        performanceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Portfolio Value',
                    data: values,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { display: false },
                    y: {
                        grid: { color: '#2d2d2d' },
                        ticks: { color: '#9ca3af' }
                    }
                }
            }
        });
    }
}

// --- Dashboard Logic (Existing) ---

function renderDashboard(data) {
    console.log("Rendering dashboard with data:", data);

    // Hide Loading
    loadingState.classList.add('hidden');
    dashboardContent.classList.remove('hidden');

    if (!Array.isArray(data)) {
        console.error("Data is not an array:", data);
        loadingState.innerHTML = `<p class="text-red-500">Invalid data format received.</p>`;
        loadingState.classList.remove('hidden');
        return;
    }

    // Filter High Confidence Signals
    const signals = data.filter(item => {
        if (!item || !item.summary) return false;
        const decision = item.summary.decision;
        // Check if decision is BUY or SELL (ignore WAIT)
        return decision === 'BUY' || decision === 'SELL';
    });

    renderSignals(signals);
    renderAssetGrid(data);
}

function renderSignals(signals) {
    if (signals.length === 0) {
        noSignalsMsg.classList.remove('hidden');
        signalsTableBody.innerHTML = '';
        return;
    }

    noSignalsMsg.classList.add('hidden');

    signalsTableBody.innerHTML = signals.map(item => {
        const { ticker, summary, psychology, technical_context } = item;
        const decisionClass = summary.decision === 'BUY' ? 'text-green-500' : 'text-red-500';
        const reasoning = psychology.deep_reasoning || "No reasoning provided.";
        const priceAction = technical_context && technical_context.price_action ? technical_context.price_action.split(' ')[2] : 'N/A';

        return `
        <tr class="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
            <td class="p-4 font-bold text-white">${ticker}</td>
            <td class="p-4 font-mono text-gray-300">${priceAction}</td>
            <td class="p-4 font-bold ${decisionClass}">${summary.decision}</td>
            <td class="p-4">
                <div class="flex items-center gap-2">
                    <div class="w-16 h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div class="h-full bg-blue-500" style="width: ${summary.confidence_score * 10}%"></div>
                    </div>
                    <span class="text-xs text-gray-400">${summary.confidence_score}/10</span>
                </div>
            </td>
            <td class="p-4 text-sm text-gray-400 italic">"${reasoning}"</td>
        </tr>
        `;
    }).join('');
}

function renderAssetGrid(data) {
    assetsGrid.innerHTML = data.map(item => {
        const { ticker, summary } = item;
        let borderClass = 'border-gray-700';
        let textClass = 'text-gray-400';

        if (summary.decision === 'BUY') {
            borderClass = 'border-green-500/50';
            textClass = 'text-green-500';
        } else if (summary.decision === 'SELL') {
            borderClass = 'border-red-500/50';
            textClass = 'text-red-500';
        }

        return `
        <div class="glass rounded-lg p-4 border ${borderClass} hover:bg-gray-800/50 transition-all">
            <div class="flex justify-between items-center mb-2">
                <h4 class="font-bold text-white">${ticker}</h4>
                <span class="text-xs font-bold px-2 py-1 rounded bg-gray-800 ${textClass}">${summary.decision}</span>
            </div>
            <div class="flex justify-between items-end">
                <div class="text-xs text-gray-500">
                    Trend: <span class="text-gray-300">${summary.current_trend}</span>
                </div>
                <div class="text-xs text-blue-400">
                    Conf: ${summary.confidence_score}/10
                </div>
            </div>
        </div>
        `;
    }).join('');
}

// Expose functions to window for HTML buttons
window.startPortfolio = startPortfolio;
window.triggerMarketCheck = triggerMarketCheck;

// Start
init();
