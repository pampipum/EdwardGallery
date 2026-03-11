export const API_BASE = window.location.origin;

// API Key for authentication - Use session-based or environment configuration
// Get the API key from localStorage, or prompt the user if it's not set
let API_KEY = localStorage.getItem('API_KEY');

// Helper function to get headers with API key
export function getAuthHeaders() {
    if (!API_KEY) {
        API_KEY = prompt("Enter your API Key for authentication:");
        if (API_KEY) {
            localStorage.setItem('API_KEY', API_KEY);
        }
    }
    
    return {
        'X-API-Key': API_KEY || '',
        'Content-Type': 'application/json'
    };
}

// Reset API Key if needed
window.resetApiKey = () => {
    localStorage.removeItem('API_KEY');
    API_KEY = null;
    alert("API Key cleared from local storage.");
};

export async function fetchDashboardData() {
    const response = await fetch(`${API_BASE}/api/dashboard`);
    if (!response.ok) throw new Error('Failed to fetch dashboard data');
    return response.json();
}

export async function checkPortfolioStatus(pmId = 'pm1') {
    const response = await fetch(`${API_BASE}/api/portfolio/status/${pmId}`);
    if (!response.ok) throw new Error('Failed to check portfolio status');
    return response.json();
}

export async function startPortfolio(pmId, capital) {
    const response = await fetch(`${API_BASE}/api/portfolio/start/${pmId}?capital=${capital}`, {
        method: 'POST',
        headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Failed to start portfolio');
    return response.json();
}

export async function triggerMarketCheck(pmId) {
    const response = await fetch(`/api/portfolio/tick/${pmId}`, {
        method: 'POST',
        headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Failed to trigger market check');
    return response.json();
}

export async function restartPortfolio(pmId) {
    const response = await fetch(`/api/portfolio/restart/${pmId}`, {
        method: 'POST',
        headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Failed to restart portfolio');
    return response.json();
}

export async function getAllPMsStatus() {
    const response = await fetch(`${API_BASE}/api/portfolio/all`);
    if (!response.ok) throw new Error('Failed to fetch all PMs status');
    return response.json();
}

export async function startAllPortfolios(capital) {
    const response = await fetch(`${API_BASE}/api/portfolio/start-all?capital=${capital}`, {
        method: 'POST',
        headers: getAuthHeaders()
    });
    if (!response.ok) throw new Error('Failed to start all portfolios');
    return response.json();
}

export async function getCROStatus() {
    const response = await fetch(`${API_BASE}/api/risk/cro`);
    if (!response.ok) throw new Error('Failed to fetch CRO status');
    return response.json();
}

export async function fetchLLMLogs() {
    const response = await fetch(`${API_BASE}/api/llm/logs`);
    if (!response.ok) throw new Error('Failed to fetch LLM logs');
    return response.json();
}

export async function fetchLiveOverview(lines = 60) {
    const response = await fetch(`${API_BASE}/api/live/overview?lines=${lines}`);
    if (!response.ok) throw new Error('Failed to fetch live overview');
    return response.json();
}


