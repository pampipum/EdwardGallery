export function renderLayout() {
    const app = document.getElementById('app');
    if (!app) return;

    app.innerHTML = `
    <!-- Top Nav -->
    <header class="h-16 border-b border-glass-border flex items-center px-4 md:px-6 justify-between bg-space-900/50 backdrop-blur-md sticky top-0 z-50 shrink-0">
        <div class="flex items-center gap-4">
            <div class="flex flex-col">
                <h1 class="text-xl md:text-2xl font-black tracking-tighter italic text-white leading-none uppercase">Attikon <span class="text-accent-teal">Lab</span></h1>
                <p class="text-[10px] text-gray-500 font-mono tracking-[0.2em] uppercase leading-none mt-1">Autonomous Intelligence</p>
            </div>
        </div>

        <div class="flex-1 max-w-2xl mx-4 md:mx-12 overflow-hidden relative">
            <div id="ticker-tape" class="ticker font-mono text-[10px] whitespace-nowrap py-1">
                <!-- Ticker items injected here -->
            </div>
        </div>

        <div class="flex items-center gap-2 md:gap-4">
            <div id="trading-mode-badge" class="px-2 py-0.5 text-[10px] md:text-xs font-bold tracking-widest text-white border border-glass-border bg-space-200 rounded">
                PAPER MODE
            </div>
            <button onclick="window.triggerMarketCheck()" class="bg-white/5 hover:bg-white/10 text-white p-2 rounded-lg border border-glass-border transition-all">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
            </button>
        </div>
    </header>

    <div class="flex flex-col md:flex-row flex-1 overflow-hidden bg-space-950 relative">
        <!-- Sidebar -->
        <aside class="w-full md:w-64 border-r border-glass-border bg-space-900/30 flex md:flex-col overflow-x-auto md:overflow-y-auto no-scrollbar shrink-0">
            <div class="flex md:flex-col w-full p-2 md:p-4 gap-2">
                <button onclick="window.switchPM('all')" id="pm-tab-all" class="pm-tab-active p-3 flex flex-col justify-center items-center gap-1 min-w-[100px]">
                    <span class="text-[10px] text-gray-400 font-bold tracking-widest uppercase">Overview</span>
                    <span class="text-xs font-black text-white italic tracking-tighter">ALL PORTFOLIOS</span>
                </button>
                
                <div class="hidden md:block h-px bg-glass-border my-2"></div>

                <button onclick="window.switchPM('pm1')" id="pm-tab-pm1" class="pm-tab-inactive p-3 flex flex-col justify-between gap-2 min-w-[140px] text-left">
                    <span class="text-xs md:text-sm text-gray-300 font-bold tracking-wide">PM1 Adaptive</span>
                    <div class="flex items-center justify-between w-full mt-1">
                        <canvas id="sparkline-pm1" class="h-6 w-16 opacity-75"></canvas>
                        <span id="badge-pm1" class="text-[10px] bg-space-200 border border-glass-border px-1.5 py-0.5 rounded-full text-gray-400 font-mono">-</span>
                    </div>
                </button>

                <button onclick="window.switchPM('pm2')" id="pm-tab-pm2" class="pm-tab-inactive p-3 flex flex-col justify-between gap-2 min-w-[140px] text-left">
                    <span class="text-xs md:text-sm text-gray-300 font-bold tracking-wide">PM2 Sentient</span>
                    <div class="flex items-center justify-between w-full mt-1">
                        <canvas id="sparkline-pm2" class="h-6 w-16 opacity-75"></canvas>
                        <span id="badge-pm2" class="text-[10px] bg-space-200 border border-glass-border px-1.5 py-0.5 rounded-full text-gray-400 font-mono">-</span>
                    </div>
                </button>

                <button onclick="window.switchPM('pm3')" id="pm-tab-pm3" class="pm-tab-inactive p-3 flex flex-col justify-between gap-2 min-w-[140px] text-left">
                    <span class="text-xs md:text-sm text-gray-300 font-bold tracking-wide">PM3 Vacuum</span>
                    <div class="flex items-center justify-between w-full mt-1">
                        <canvas id="sparkline-pm3" class="h-6 w-16 opacity-75"></canvas>
                        <span id="badge-pm3" class="text-[10px] bg-space-200 border border-glass-border px-1.5 py-0.5 rounded-full text-gray-400 font-mono">-</span>
                    </div>
                </button>

                <button onclick="window.switchPM('pm4')" id="pm-tab-pm4" class="pm-tab-inactive p-3 flex flex-col justify-between gap-2 min-w-[140px] text-left">
                    <span class="text-xs md:text-sm text-gray-300 font-bold tracking-wide">PM4 Leverage</span>
                    <div class="flex items-center justify-between w-full mt-1">
                        <canvas id="sparkline-pm4" class="h-6 w-16 opacity-75"></canvas>
                        <span id="badge-pm4" class="text-[10px] bg-space-200 border border-glass-border px-1.5 py-0.5 rounded-full text-gray-400 font-mono">-</span>
                    </div>
                </button>

                <button onclick="window.switchPM('pm5')" id="pm-tab-pm5" class="pm-tab-inactive p-3 flex flex-col justify-between gap-2 min-w-[140px] text-left">
                    <span class="text-xs md:text-sm text-gray-300 font-bold tracking-wide">PM5 Survivor</span>
                    <div class="flex items-center justify-between w-full mt-1">
                        <canvas id="sparkline-pm5" class="h-6 w-16 opacity-75"></canvas>
                        <span id="badge-pm5" class="text-[10px] bg-space-200 border border-glass-border px-1.5 py-0.5 rounded-full text-gray-400 font-mono">-</span>
                    </div>
                </button>

                <button onclick="window.switchPM('pm6')" id="pm-tab-pm6" class="pm-tab-inactive p-3 flex flex-col justify-between gap-2 min-w-[140px] border-accent-teal/30 text-left">
                    <span class="text-xs md:text-sm text-accent-teal font-bold tracking-wide uppercase">PM6 Shadow Live</span>
                    <div class="flex items-center justify-between w-full mt-1">
                        <canvas id="sparkline-pm6" class="h-6 w-16 opacity-75"></canvas>
                        <span id="badge-pm6" class="text-[10px] bg-space-200 border border-glass-border px-1.5 py-0.5 rounded-full text-accent-teal font-mono tracking-widest">LIVE</span>
                    </div>
                </button>
            </div>

            <!-- Sidebar Footer -->
            <div class="hidden md:flex flex-col mt-auto p-4 border-t border-glass-border bg-black/20">
                <div class="flex justify-between items-center mb-3">
                    <span class="text-[10px] font-bold text-gray-500 tracking-wider uppercase">Risk Exposure</span>
                    <div id="cro-status-badge" class="w-2 h-2 rounded-full bg-accent-teal"></div>
                </div>
                <div id="cro-gauges-container" class="flex justify-around items-center mb-4 min-h-[40px]">
                    <!-- Gauges injected here -->
                </div>
                <button onclick="window.openLLMMonitor()" class="text-center py-2 border border-amber-500/20 hover:border-amber-500/40 rounded bg-amber-500/5 transition-all group">
                    <span class="text-[9px] font-black text-amber-500/60 group-hover:text-amber-500 tracking-[0.2em] uppercase">LLM API SUPERVISION</span>
                </button>
            </div>
        </aside>

        <!-- Main Layout Container -->
        <main id="dashboard-layout" class="flex-1 flex flex-col md:flex-row overflow-y-auto md:overflow-hidden p-4 gap-4">
            
            <!-- Left Column: Chart & Stats (60%) -->
            <div class="w-full md:w-3/5 flex flex-col gap-4 relative overflow-y-auto md:overflow-y-hidden shrink-0">
                
                <!-- Stats Grid -->
                <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 shrink-0">
                    <div class="glass-card p-3 md:p-4 rounded-xl border border-glass-border relative overflow-hidden group">
                        <div class="absolute top-0 left-0 w-1 h-full bg-accent-teal opacity-50"></div>
                        <p class="text-[10px] font-bold text-gray-500 tracking-widest uppercase mb-1">CASH BALANCE</p>
                        <p id="balance-display" class="text-lg md:text-2xl font-black text-white font-mono tracking-tighter italic">$0.00</p>
                    </div>
                    <div class="glass-card p-3 md:p-4 rounded-xl border border-glass-border relative overflow-hidden">
                        <div class="absolute top-0 left-0 w-1 h-full bg-white/20"></div>
                        <p class="text-[10px] font-bold text-gray-500 tracking-widest uppercase mb-1">TOTAL ASSETS</p>
                        <p id="total-value-display" class="text-lg md:text-2xl font-black text-white font-mono tracking-tighter italic">$0.00</p>
                    </div>
                    <div class="glass-card p-3 md:p-4 rounded-xl border border-glass-border relative overflow-hidden">
                        <div id="unrealized-bar" class="absolute top-0 left-0 w-1 h-full bg-accent-teal opacity-50"></div>
                        <p class="text-[10px] font-bold text-gray-500 tracking-widest uppercase mb-1">UNREALIZED</p>
                        <p id="unrealized-pnl-display" class="text-lg md:text-2xl font-bold font-mono text-accent-teal tracking-tighter">+ $0.00</p>
                    </div>
                    <div class="glass-card p-3 md:p-4 rounded-xl border border-glass-border relative overflow-hidden">
                        <div id="realized-bar" class="absolute top-0 left-0 w-1 h-full bg-accent-teal opacity-50"></div>
                        <p class="text-[10px] font-bold text-gray-500 tracking-widest uppercase mb-1">REALIZED</p>
                        <p id="realized-pnl-display" class="text-lg md:text-2xl font-bold font-mono text-accent-teal tracking-tighter">+ $0.00</p>
                    </div>
                </div>

                <!-- Performance Chart -->
                <div class="flex-1 glass-card rounded-2xl border border-glass-border p-4 md:p-6 relative flex flex-col min-h-[300px] md:min-h-0 overflow-hidden bg-space-900/40 backdrop-blur-sm">
                    <div class="flex justify-between items-center mb-6">
                        <h2 id="pm-badge" class="text-xl md:text-2xl font-black text-white tracking-tighter italic uppercase">ALL PORTFOLIOS</h2>
                        <div id="benchmark-bar" class="hidden">
                            <div id="vs-benchmark-container" class="flex items-center gap-3 bg-accent-teal/10 border border-accent-teal/30 px-3 py-1 rounded-full">
                                <span class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Alpha</span>
                                <span id="vs-benchmark-display" class="text-sm md:text-lg font-bold font-mono text-accent-teal">+0.00%</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex-1 relative">
                        <canvas id="performance-chart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Right Column: Tabs & Intelligence (40%) -->
            <div class="w-full md:w-2/5 flex flex-col gap-4 min-h-[500px] md:min-h-0 flex-1 md:flex-initial md:h-full shrink-0 md:shrink overflow-hidden">

                <!-- Live Monitor -->
                <div class="glass-card rounded-2xl border border-glass-border bg-space-900/40 backdrop-blur-sm p-3">
                    <div class="flex items-center justify-between mb-2">
                        <h3 class="text-[10px] font-black tracking-[0.2em] uppercase text-accent-teal">Live Monitor</h3>
                        <span id="live-monitor-updated" class="text-[10px] font-mono text-gray-500">--:--:--</span>
                    </div>
                    <div id="live-pm-strip" class="grid grid-cols-3 gap-2 text-[10px] mb-2"></div>
                    <div id="live-pm-detail" class="text-[10px] text-gray-300 bg-black/20 border border-glass-border rounded p-2 mb-2">Select a PM for details…</div>
                    <div id="live-trades-feed" class="h-16 overflow-y-auto custom-scrollbar font-mono text-[10px] leading-4 text-gray-300 bg-black/20 border border-glass-border rounded p-2 mb-2"></div>
                    <div id="live-log-tail" class="h-16 overflow-y-auto custom-scrollbar font-mono text-[10px] leading-4 text-gray-300 bg-black/20 border border-glass-border rounded p-2"></div>
                </div>

                <div class="glass-card flex-1 rounded-2xl border border-glass-border flex flex-col overflow-hidden bg-space-900/40 backdrop-blur-sm">
                    <!-- Tabs Header -->
                    <div class="flex border-b border-glass-border bg-black/20 overflow-x-auto no-scrollbar shrink-0">
                        <button onclick="window.switchTab('modelchat')" id="tab-modelchat" class="sub-tab-active flex-1 py-3 px-4 text-[10px] font-black uppercase tracking-[0.2em] whitespace-nowrap transition-all border-r border-glass-border">Intelligence</button>
                        <button onclick="window.switchTab('positions')" id="tab-positions" class="sub-tab-inactive flex-1 py-3 px-4 text-[10px] font-black uppercase tracking-[0.2em] whitespace-nowrap transition-all border-r border-glass-border text-gray-500">Positions</button>
                        <button onclick="window.switchTab('completed-trades')" id="tab-completed-trades" class="sub-tab-inactive flex-1 py-3 px-4 text-[10px] font-black uppercase tracking-[0.2em] whitespace-nowrap transition-all border-r border-glass-border text-gray-500">History</button>
                        <button onclick="window.switchTab('strategy')" id="tab-strategy" class="sub-tab-inactive flex-1 py-3 px-4 text-[10px] font-black uppercase tracking-[0.2em] whitespace-nowrap transition-all border-r border-glass-border text-gray-500">Strategy</button>
                        <button onclick="window.switchTab('reports')" id="tab-reports" class="sub-tab-inactive flex-1 py-3 px-4 text-[10px] font-black uppercase tracking-[0.2em] whitespace-nowrap transition-all text-gray-500">Reports</button>
                    </div>

                    <!-- Context Controls (Filters) -->
                    <div id="modelchat-controls" class="p-3 border-b border-glass-border bg-black/10 flex justify-between items-center shrink-0">
                        <div class="flex gap-2">
                            <button onclick="window.filterModelChat('manager')" class="text-[9px] font-bold px-2 py-1 rounded bg-accent-teal/10 text-accent-teal border border-accent-teal/20">PM LOG</button>
                            <button onclick="window.filterModelChat('analyst')" class="text-[9px] font-bold px-2 py-1 rounded bg-white/5 text-gray-400 border border-glass-border uppercase">Asset Reports</button>
                        </div>
                        <select id="modelchat-asset-filter" onchange="window.filterModelChatAsset(this.value)" class="bg-space-200 border border-glass-border text-[9px] font-bold text-white rounded px-2 py-1 outline-none hidden">
                            <option value="ALL">All Assets</option>
                        </select>
                    </div>

                    <!-- Tab Viewports -->
                    <div class="flex-1 overflow-y-auto p-4 custom-scrollbar relative">
                        <div id="content-modelchat" class="space-y-4">
                            <div id="modelchat-feed" class="flex flex-col gap-3">
                                <div class="text-center text-gray-500 text-[10px] uppercase tracking-widest mt-10">Select a portfolio to see live intelligence</div>
                            </div>
                        </div>
                        <div id="content-positions" class="hidden">
                            <div id="positions-content" class="space-y-4"></div>
                        </div>
                        <div id="content-completed-trades" class="hidden">
                            <div id="completed-trades-list" class="space-y-4"></div>
                        </div>
                        <div id="content-strategy" class="hidden">
                            <div id="strategy-content"></div>
                        </div>
                        <div id="content-reports" class="hidden">
                            <div id="reports-list-container" class="space-y-4"></div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Modal Overlay -->
    <div id="report-modal" class="fixed inset-0 bg-black/80 backdrop-blur-md z-[100] hidden items-center justify-center p-4">
        <div class="glass-card w-full max-w-4xl max-h-[90vh] rounded-3xl border border-glass-border flex flex-col overflow-hidden shadow-2xl relative">
            
            <!-- Modal Header -->
            <div class="flex items-center justify-between p-6 border-b border-glass-border bg-white/5 shrink-0">
                <div class="flex items-center gap-4">
                    <div id="modal-ticker-icon"></div>
                    <div>
                        <h2 id="modal-report-title" class="text-2xl font-black text-white tracking-tighter italic uppercase">ASSET REPORT</h2>
                        <div class="flex gap-3 items-center mt-1">
                            <span id="modal-report-type" class="text-[10px] font-black text-accent-teal tracking-widest uppercase">Deep Analysis</span>
                            <span class="w-1 h-1 rounded-full bg-gray-600"></span>
                            <span id="modal-report-pm" class="text-[10px] font-mono text-gray-400 uppercase">SYSTEM</span>
                        </div>
                    </div>
                </div>
                <button onclick="window.closeReportModal()" class="text-gray-500 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-full">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>

            <!-- Modal Content (Dynamic) -->
            <div id="modal-report-content" class="flex-1 overflow-y-auto p-8 custom-scrollbar prose prose-invert max-w-none prose-pre:bg-black/50 prose-pre:border prose-pre:border-glass-border">
                <!-- Text injected here -->
            </div>
        </div>
    </div>

    <!-- Hidden Controls -->
    <div id="portfolio-controls" class="fixed bottom-4 right-4 glass-card p-4 rounded-lg md:w-80 z-50 shadow-2xl border-accent-teal/30 hidden">
        <!-- JS Populated -->
    </div>
    `;
}
