from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.services.data_service import get_top_tickers
from backend.services.analysis_service import analyze_ticker, get_dashboard_summary
from backend.services.portfolio_service import portfolio_service
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
    # If empty, it means no run has happened yet.
    return portfolio_service.get_latest_analysis()

@app.get("/api/analyze/{ticker}")
def get_analysis(ticker: str):
    return analyze_ticker(ticker)

# Portfolio Routes
@app.post("/api/portfolio/start")
def start_portfolio(capital: float, background_tasks: BackgroundTasks):
    result = portfolio_service.start_portfolio(capital)
    # Trigger immediate market analysis in background
    background_tasks.add_task(run_market_analysis)
    return result

@app.get("/api/portfolio/status")
def get_portfolio_status():
    return portfolio_service.get_status()

@app.post("/api/portfolio/tick")
async def trigger_market_check(background_tasks: BackgroundTasks):
    """Manually trigger a market analysis (Slow Loop)"""
    background_tasks.add_task(run_market_analysis)
    return {"message": "Market analysis triggered"}

@app.get("/api/market/prices")
def get_market_prices():
    """Get current market prices for all tickers in portfolio"""
    from backend.services.market_service import get_current_prices
    
    status = portfolio_service.get_status()
    tickers = list(status.get("positions", {}).keys())
    
    if not tickers:
        return {}
    
    prices = get_current_prices(tickers)
    return prices

@app.get("/api/portfolio/ledger")
def get_portfolio_ledger():
    """Get portfolio ledger (all transactions)"""
    status = portfolio_service.get_status()
    return {"ledger": status.get("ledger", [])}

# Static Files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("frontend/static/index.html")

