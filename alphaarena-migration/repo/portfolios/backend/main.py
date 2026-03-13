from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.services.data_service import get_top_tickers
from backend.services.analysis_service import analyze_ticker, get_dashboard_summary
from backend.services.portfolio_service import portfolio_manager
from backend.services.trading_loop import start_trading_loop, run_market_analysis
import asyncio

app = FastAPI(title="Market Analyst API", description="Senior Technical Analyst Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup Event to launch Background Loop
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_trading_loop())

# API Routes
@app.get("/api/dashboard")
def get_dashboard():
    # Return cached analysis from portfolio service
    # For now, return PM1's analysis as the default
    pm1_portfolio = portfolio_manager.get_portfolio('pm1')
    return pm1_portfolio.get_latest_analysis()

@app.get("/api/analyze/{ticker}")
def get_analysis(ticker: str):
    return analyze_ticker(ticker)

# Portfolio Routes - PM Specific
@app.post("/api/portfolio/start/{pm_id}")
def start_portfolio(pm_id: str, capital: float, background_tasks: BackgroundTasks):
    portfolio = portfolio_manager.get_portfolio(pm_id)
    result = portfolio.start_portfolio(capital)
    # Trigger immediate market analysis in background for this PM
    background_tasks.add_task(run_market_analysis, pm_id)
    return result

from backend.services.pm_strategies import get_strategy

@app.get("/api/portfolio/status/{pm_id}")
def get_portfolio_status(pm_id: str):
    portfolio = portfolio_manager.get_portfolio(pm_id)
    status = portfolio.get_status()
    
    # Inject active strategy details
    strategy = get_strategy(pm_id)
    status["strategy_info"] = {
        "name": strategy.name,
        "description": strategy.description,
        "confidence_threshold": strategy.get_confidence_threshold(),
        "check_interval": strategy.get_check_interval(),
        "max_position_size": strategy.get_max_position_size(),
        "min_cash_buffer": strategy.get_min_cash_buffer(),
        "prompt_modifier": strategy.get_prompt_modifier()
    }
    return status

@app.post("/api/portfolio/tick/{pm_id}")
async def trigger_market_check(pm_id: str, background_tasks: BackgroundTasks):
    """Manually trigger a market analysis for a specific PM"""
    background_tasks.add_task(run_market_analysis, pm_id)
    return {"message": f"Market analysis triggered for {pm_id}"}

@app.post("/api/portfolio/restart/{pm_id}")
def restart_portfolio(pm_id: str):
    """Stop the current portfolio run"""
    portfolio = portfolio_manager.get_portfolio(pm_id)
    portfolio.data["is_running"] = False
    portfolio.save_portfolio()
    return {"message": f"Portfolio {pm_id} stopped. You can now start a new run."}


@app.get("/api/portfolio/all")
def get_all_portfolios():
    """Get status of all active PMs"""
    return portfolio_manager.get_all_status()

@app.get("/api/market/prices")
def get_market_prices():
    """Get current market prices for all tickers in portfolio"""
    from backend.services.market_service import get_current_prices
    
    # Get all unique tickers across all PMs
    all_tickers = set()
    for pm_id in ['pm1', 'pm2', 'pm3', 'pm4']:
        portfolio = portfolio_manager.get_portfolio(pm_id)
        status = portfolio.get_status()
        all_tickers.update(status.get("positions", {}).keys())
    
    if not all_tickers:
        return {}
    
    prices = get_current_prices(list(all_tickers))
    return prices

@app.get("/api/portfolio/ledger/{pm_id}")
def get_portfolio_ledger(pm_id: str):
    """Get portfolio ledger (all transactions) for a specific PM"""
    portfolio = portfolio_manager.get_portfolio(pm_id)
    status = portfolio.get_status()
    return {"ledger": status.get("ledger", [])}

# Static Files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("frontend/static/index.html")
