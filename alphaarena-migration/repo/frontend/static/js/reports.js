// Weekly Reports Service for Frontend
import { getAuthHeaders } from './api.js';

export async function fetchAndRenderReports() {
    const pmId = document.getElementById('pm-badge').getAttribute('data-pm');
    const container = document.getElementById('reports-list-container');
    
    if (pmId === 'all') {
        container.innerHTML = '<div class="text-center text-gray-500 text-xs mt-10">Select a specific PM to view their weekly reports and active learnings.</div>';
        return;
    }

    container.innerHTML = `
        <div class="space-y-6">
            <div id="active-learnings-section" class="mb-6">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-[10px] font-bold text-accent-teal uppercase tracking-widest">Active Strategy Overrides</span>
                    <span id="learning-count" class="text-[10px] text-gray-500">0/7 Slots</span>
                </div>
                <div id="active-learnings-list" class="space-y-2">
                    <!-- Populated by JS -->
                    <div class="text-center text-[10px] text-gray-600 py-4 border border-dashed border-gray-800 rounded">No active overrides.</div>
                </div>
            </div>
            
            <div class="border-t border-glass-border pt-6">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Historical Reports</span>
                </div>
                <div id="reports-list" class="space-y-3">
                    <div class="text-center text-gray-500 text-xs mt-4 animate-pulse">Loading reports...</div>
                </div>
            </div>
        </div>
    `;

    try {
        // Fetch Reports
        const reportsRes = await fetch(`/api/reports/${pmId}`);
        const reports = await reportsRes.json();
        
        // Fetch PM Status for active learnings
        const statusRes = await fetch(`/api/portfolio/status/${pmId}`);
        const status = await statusRes.json();

        renderActiveLearnings(status.active_learnings || [], pmId);
        renderReportsList(reports, pmId);

    } catch (error) {
        console.error('Error fetching data:', error);
        document.getElementById('reports-list').innerHTML = `<div class="text-center text-accent-red text-xs">Error loading analyst data.</div>`;
    }
}

function renderActiveLearnings(learnings, pmId) {
    const container = document.getElementById('active-learnings-list');
    const countEl = document.getElementById('learning-count');
    
    countEl.innerText = `${learnings.length}/7 Slots`;

    if (learnings.length === 0) {
        container.innerHTML = '<div class="text-center text-[10px] text-gray-600 py-4 border border-dashed border-gray-800 rounded">No active overrides.</div>';
        return;
    }

    container.innerHTML = learnings.map(l => `
        <div class="bg-space-800/50 border border-accent-teal/20 p-3 rounded relative group">
            <div class="flex justify-between items-start mb-1">
                <div class="text-[10px] font-bold text-accent-teal uppercase truncate pr-8">${l.parameter}</div>
                <button onclick="window.revertLearning('${pmId}', '${l.id}')" class="text-[9px] text-gray-500 hover:text-accent-red transition-colors uppercase font-bold">Revert</button>
            </div>
            <div class="text-xs text-white font-mono mb-1">${l.new_value}</div>
            <div class="text-[9px] text-gray-400 leading-tight line-clamp-2">${l.reasoning}</div>
            <div class="mt-2 pt-2 border-t border-glass-border flex justify-between items-center">
                <div class="text-[8px] text-gray-500 uppercase">${new Date(l.ingested_at).toLocaleDateString()}</div>
                <button onclick="window.graduateLearning('${pmId}', '${l.id}')" class="text-[8px] text-accent-teal/50 hover:text-accent-teal uppercase font-bold transition-colors">Graduate</button>
            </div>
        </div>
    `).join('');
}

function renderReportsList(reports, pmId) {
    const container = document.getElementById('reports-list');
    
    if (!reports || reports.length === 0) {
        container.innerHTML = '<div class="text-center text-gray-500 text-xs mt-10">No reports generated for this PM yet.</div>';
        return;
    }

    container.innerHTML = reports.map(report => {
        const date = new Date(report.timestamp).toLocaleDateString(undefined, { 
            month: 'short', day: 'numeric', year: 'numeric'
        });
        const pnl = report.performance_summary.pnl_percentage * 100;
        const pnlColor = pnl >= 0 ? 'text-accent-teal' : 'text-accent-red';

        return `
        <div class="glass-card p-3 hover:bg-space-200 transition-all cursor-pointer group border-l-2 ${pnl >= 0 ? 'border-l-accent-teal/50' : 'border-l-accent-red/50'}" 
             onclick="window.openWeeklyReport('${report.report_id}')">
            <div class="flex justify-between items-start">
                <div>
                    <div class="text-xs font-bold text-white">${date}</div>
                    <div class="text-[9px] text-gray-500 uppercase tracking-widest">${report.proposed_overrides?.length || 0} PROPOSED IMPROVEMENTS</div>
                </div>
                <div class="text-right">
                    <div class="text-xs font-mono font-bold ${pnlColor}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}%</div>
                </div>
            </div>
        </div>
        `;
    }).join('');
}

window.openWeeklyReport = async function(reportId) {
    const pmId = document.getElementById('pm-badge').getAttribute('data-pm');
    
    try {
        const response = await fetch(`/api/reports/${pmId}/${reportId}`);
        const report = await response.json();
        
        let content = report.report_markdown;
        
        // Add Proposed Overrides Section to Modal
        if (report.proposed_overrides && report.proposed_overrides.length > 0) {
            content += "\n\n---\n### 🧠 CYBERNETIC OPTIMIZATIONS\n*Numerical proposals based on this week's data. Review carefully before activating.*\n\n";
            
            report.proposed_overrides.forEach((o, i) => {
                // evidence_trades can be an array of strings, a number, or a single string
                let evidenceText = Array.isArray(o.evidence_trades) ? o.evidence_trades.join(', ') : o.evidence_trades;
                let evidenceCount = Array.isArray(o.evidence_trades) ? o.evidence_trades.length : parseInt(o.evidence_trades) || 0;
                
                const confidence = evidenceCount >= 10 || (typeof o.evidence_trades === 'string' && o.evidence_trades.includes('trades')) ? 
                    '<span class="text-accent-teal">[HIGH CONFIDENCE]</span>' : 
                    '<span class="text-yellow-500">[LOW CONFIDENCE - NOISE WARNING]</span>';
                
                content += `#### ${i+1}. ${o.parameter} ${confidence}\n`;
                content += `* **Action:** ${o.action} (${o.old_value} &rarr; **${o.new_value}**)\n`;
                content += `* **Evidence:** ${evidenceText}\n`;
                content += `* **Reasoning:** ${o.reasoning}\n`;
                // We'll inject the button using HTML since marked allows some
                content += `<button onclick="window.ingestLearningFromModal('${pmId}', ${i}, '${report.report_id}')" style="margin-top:10px; background: rgba(20, 184, 166, 0.1); border: 1px solid rgba(20, 184, 166, 0.3); color: #14b8a6; padding: 4px 12px; border-radius: 4px; font-size: 10px; font-weight: bold; cursor: pointer; text-transform: uppercase;">Activate Override</button>\n\n`;
            });
        }
        
        window.openReportModal(
            `LONGITUDINAL: ${pmId.toUpperCase()}`,
            'STRATEGY AUDIT',
            'N/A',
            content,
            'text-accent-teal'
        );
    } catch (error) {
        alert('Error opening report: ' + error.message);
    }
};

window.ingestLearningFromModal = async function(pmId, index, reportId) {
    if (!confirm("Are you sure you want to activate this parameter override? It will immediately change the PM's trading logic.")) return;

    try {
        // Get report to find the specific override data
        const reportRes = await fetch(`/api/reports/${pmId}/${reportId}`);
        const report = await reportRes.json();
        const learningData = report.proposed_overrides[index];

        const response = await fetch(`/api/learnings/ingest/${pmId}`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(learningData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || errorData.error || 'Failed to ingest learning');
        }

        const data = await response.json();
        alert(data.message || 'Learning activated successfully');
        fetchAndRenderReports(); // Refresh list
    } catch (error) {
        alert('Error ingesting learning: ' + error.message);
    }
};

window.revertLearning = async function(pmId, learningId) {
    if (!confirm("Revert this override and return to base strategy logic?")) return;

    try {
        const response = await fetch(`/api/learnings/revert/${pmId}/${learningId}`, {
            method: 'POST',
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || errorData.error || 'Failed to revert learning');
        }

        const data = await response.json();
        alert(data.message || 'Learning reverted');
        fetchAndRenderReports();
    } catch (error) {
        alert('Error reverting: ' + error.message);
    }
};

window.graduateLearning = async function(pmId, learningId) {
    if (!confirm("Graduate this learning? This marks it as permanently validated. (Note: You still need to manually update the base prompt later for permanent archiving).")) return;
    
    try {
        const response = await fetch(`/api/learnings/graduate/${pmId}/${learningId}`, {
            method: 'POST',
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || errorData.error || 'Failed to graduate learning');
        }

        const data = await response.json();
        alert(data.message || 'Learning graduated');
        fetchAndRenderReports();
    } catch (error) {
        alert('Error graduating: ' + error.message);
    }
}

window.triggerWeeklyReport = async function() {
    const pmId = document.getElementById('pm-badge').getAttribute('data-pm');
    if (pmId === 'all') return;

    if (!confirm(`Trigger a fresh longitudinal analysis for ${pmId.toUpperCase()}? This will use Grok-4.1-fast.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/reports/trigger/${pmId}`, { 
            method: 'POST',
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || errorData.error || 'Failed to trigger report');
        }

        const data = await response.json();
        alert(data.message || 'Report triggered successfully');
        setTimeout(() => fetchAndRenderReports(), 45000);
    } catch (error) {
        alert('Error triggering report: ' + error.message);
    }
};

window.fetchAndRenderReports = fetchAndRenderReports;
