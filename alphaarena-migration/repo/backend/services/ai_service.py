import os
import json
import shutil
from dotenv import load_dotenv
from datetime import datetime, timedelta
import threading
from backend.utils.logger import logger
from backend.runtime import config_path, state_dir

# Load environment variables from .env file
load_dotenv()

# Configure API Keys

def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip()

GEMINI_API_KEY = _clean_env(os.getenv("GEMINI_API_KEY"))
OPENAI_API_KEY = _clean_env(os.getenv("OPENAI_API_KEY") or os.getenv("ALIBABA_API_KEY"))
OPENROUTER_API_KEY = _clean_env(os.getenv("OPENROUTER_API_KEY"))
OPENCLAW_AVAILABLE = shutil.which("openclaw") is not None

if not GEMINI_API_KEY and not OPENAI_API_KEY and not OPENROUTER_API_KEY and not OPENCLAW_AVAILABLE:
    logger.warning("No AI runtime configured. Set GEMINI_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, or use the local OpenClaw CLI.")

# Persistent Cache Configuration
CACHE_FILE = str(state_dir("cache") / "analyst_cache.json")
CACHE_DURATION_HOURS = 4
PRICE_DEVIATION_THRESHOLD = 0.03  # 3%

# Load cache from file
def load_analyst_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                # Convert timestamp strings back to datetime objects
                for ticker, content in data.items():
                    if "timestamp" in content:
                        content["timestamp"] = datetime.fromisoformat(content["timestamp"])
                return data
        except Exception as e:
            logger.error(f"Error loading analyst cache: {e}")
    return {}

def save_analyst_cache(cache):
    try:
        # Create a serializable copy
        serializable_cache = {}
        for ticker, content in cache.items():
            serializable_cache[ticker] = content.copy()
            if "timestamp" in content and isinstance(content["timestamp"], datetime):
                serializable_cache[ticker]["timestamp"] = content["timestamp"].isoformat()
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(serializable_cache, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving analyst cache: {e}")

# Initialize cache
analyst_cache = load_analyst_cache()

# Lock to prevent concurrent generation for the same ticker
cache_locks = {}
cache_locks_lock = threading.Lock()

def get_config():
    """Loads configuration from config.json"""
    config = {
        "analyst_provider": "openclaw",
        "analyst_model": "main",
        "pm_provider": "openclaw",
        "pm_model": "main"
    }
    runtime_config = config_path()
    if runtime_config.exists():
        try:
            with open(runtime_config, 'r') as f:
                loaded_config = json.load(f)
                config.update(loaded_config)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    return config

def generate_text_with_provider(prompt: str, provider: str, model_name: str, purpose: str = "Unknown", pm_id: str = "N/A") -> str:
    """
    Helper to generate text using the specified provider via llm_provider abstraction.
    Includes exponential backoff retry logic for rate limit errors.
    """
    from backend.services.llm_provider import get_llm_provider
    
    # Select the appropriate API key based on provider
    provider_lower = provider.lower()
    provider_map = {
        "openai": (OPENAI_API_KEY, "gpt-4.1-mini"),
        "openrouter": (OPENROUTER_API_KEY, "openai/gpt-4.1-mini"),
        "gemini": (GEMINI_API_KEY, "gemini-2.5-pro"),
        "openclaw": ("OPENCLAW", "main"),
    }
    api_key, default_model = provider_map.get(provider_lower, (None, "gemini-2.5-pro"))

    if provider_lower == "openclaw" and OPENCLAW_AVAILABLE:
        api_key = "OPENCLAW"
        model_name = model_name or default_model
    elif not api_key:
        fallback_chain = [
            ("openclaw", "OPENCLAW" if OPENCLAW_AVAILABLE else None, "main"),
            ("gemini", GEMINI_API_KEY, "gemini-2.5-pro"),
            ("openai", OPENAI_API_KEY, "gpt-4.1-mini"),
            ("openrouter", OPENROUTER_API_KEY, "openai/gpt-4.1-mini"),
        ]
        for fallback_provider, fallback_key, fallback_model in fallback_chain:
            if fallback_key:
                logger.warning(
                    f"{provider.upper()}_API_KEY not set. Falling back to {fallback_provider} for {purpose}."
                )
                provider_lower = fallback_provider
                provider = fallback_provider
                api_key = fallback_key
                model_name = fallback_model
                break
        else:
            raise ValueError(f"{provider.upper()}_API_KEY not set")

    if provider_lower == "gemini" and "gpt" in model_name.lower():
        logger.warning(
            f"Model '{model_name}' is not valid for Gemini. Falling back to '{default_model}'."
        )
        model_name = default_model
    
    logger.debug(f"   [DEBUG] Sending request to {provider} (Model: {model_name}) | Purpose: {purpose}...")
    start_time = datetime.now()
    
    # Get the LLM provider (retry logic is built into the provider)
    llm = get_llm_provider(provider_lower, api_key, model_name)
    result = llm.generate_text(prompt, purpose=purpose, pm_id=pm_id)
    
    duration = (datetime.now() - start_time).total_seconds()
    logger.debug(f"   [{provider}] Completed in {duration:.2f}s")
    
    return result

def generate_analyst_report(ticker: str, technical_data: dict, news: list, macro_data: dict, fundamentals: dict, insider_data: dict = {}, deep_dive_data: dict = {}) -> str:
    """
    Stage 1: The Analyst
    Generates a factual, data-driven briefing.
    Uses persistent smart caching (Time + Price Deviation) to reduce API calls.
    Thread-safe to handle concurrent requests from multiple PMs.
    """
    current_price = technical_data.get("price")
    
    # Quick cache check (no lock needed for read)
    if ticker in analyst_cache:
        cached_data = analyst_cache[ticker]
        cache_time = cached_data.get("timestamp")
        cached_price = cached_data.get("price")
        
        is_fresh = False
        if cache_time and (datetime.now() - cache_time < timedelta(hours=CACHE_DURATION_HOURS)):
            is_fresh = True
            
        # Check price deviation if we have price data
        if is_fresh and current_price and cached_price:
            price_diff_pct = abs(current_price - cached_price) / cached_price
            if price_diff_pct > PRICE_DEVIATION_THRESHOLD:
                logger.info(f"   [CACHE INVALID] Price moved {price_diff_pct:.1%} for {ticker} (Threshold: {PRICE_DEVIATION_THRESHOLD:.1%})")
                is_fresh = False
        
        if is_fresh:
            logger.info(f"   [CACHE HIT] Using cached Analyst Report for {ticker} (Age: {datetime.now() - cache_time})")
            return cached_data["report"]
    
    # Get or create a lock for this ticker
    with cache_locks_lock:
        if ticker not in cache_locks:
            cache_locks[ticker] = threading.Lock()
        ticker_lock = cache_locks[ticker]
    
    # Acquire the ticker-specific lock
    with ticker_lock:
        # Double-check cache after acquiring lock
        if ticker in analyst_cache:
            cached_data = analyst_cache[ticker]
            cache_time = cached_data.get("timestamp")
            cached_price = cached_data.get("price")
            
            is_fresh = False
            if cache_time and (datetime.now() - cache_time < timedelta(hours=CACHE_DURATION_HOURS)):
                is_fresh = True
                
            if is_fresh and current_price and cached_price:
                price_diff_pct = abs(current_price - cached_price) / cached_price
                if price_diff_pct > PRICE_DEVIATION_THRESHOLD:
                    is_fresh = False
            
            if is_fresh:
                logger.info(f"   [CACHE HIT] Using cached Analyst Report for {ticker} (after lock)")
                return cached_data["report"]
        
        logger.info(f"   [CACHE MISS] Generating new Analyst Report for {ticker}...")
        
        config = get_config()
        provider = config.get("analyst_provider", "gemini")
        model_name = config.get("analyst_model", "gemini-2.5-pro")
        
        news_text = "\n".join([f"- {n['title']} ({n['publisher']})" for n in news]) if news else "No recent news available."
        macro_text = "\n".join([f"- {k}: {v}" for k, v in macro_data.items()]) if macro_data else "No macro data available."
        fundamentals_text = "\n".join([f"- {k}: {v}" for k, v in fundamentals.items()]) if fundamentals else "No fundamental data available."
        
        insider_text = "No recent insider activity."
        if insider_data:
            insider_text = ""
            if insider_data.get('senate'):
                insider_text += "SENATE DISCLOSURES:\n" + "\n".join([f"- {d['senator']} ({d['type']}): {d['amount']} on {d['date']}" for d in insider_data['senate']]) + "\n"
            if insider_data.get('insider'):
                insider_text += "CORPORATE INSIDERS:\n" + "\n".join([f"- {d['reportingName']} ({d['transactionType']}): {d['securitiesTransacted']} shares" for d in insider_data['insider']])

        # --- DEEP DIVE / DOG vs TAIL LOGIC ---
        # Only add derivative analysis section when we have the data
        deep_dive_section = ""
        deep_dive_data_text = "Not available for this asset."
        
        if deep_dive_data:
            funding_rate = deep_dive_data.get("funding", {}).get("funding_rate", "N/A")
            open_interest = deep_dive_data.get("open_interest", {}).get("open_interest", "N/A")
            options_oi = deep_dive_data.get("options_oi", {}).get("options_oi", "N/A")
            
            deep_dive_data_text = f"""
- Funding Rate: {funding_rate} (Positive = Longs Paying Shorts, Negative = Shorts Paying Longs)
- Open Interest: {open_interest}
- Options OI: {options_oi}
"""
            # Add optional Dog vs Tail analysis section when derivative data exists
            deep_dive_section = """
### 5. Derivative Divergence Analysis (Dog vs. Tail)
*Only include this section when derivative data is available*

- **Global Structure (Dog):** [Price trend direction from technicals]
- **Local Positioning (Tail):** [What does funding rate + OI tell us about crowd positioning?]
- **Divergence Verdict:** [BULLISH DIVERGENCE | BEARISH DIVERGENCE | ALIGNED | NO EDGE]
  - Interpretation: [e.g., "Price bearish but funding negative = shorts crowded = potential squeeze"]
"""
            
        # ===========================================
        # HYBRID PROMPT: Clean Institutional Format + Optional Derivative Analysis
        # Static instructions first for OpenAI prefix caching
        # ===========================================
        prompt = f"""
ROLE: Senior Quantitative Analyst & Market Strategist (Institutional Level).
TASK: Produce a professional "Deep Dive Market Briefing" comparable to top-tier investment bank research.

CRITICAL RULES:
- **NO FLUFF**: Every sentence must contain data or specific insight.
- **DO NOT HALLUCINATE**: Only reference events explicitly in [News] section. If news is generic, state that.
- **BE SPECIFIC**: Cite exact price levels, percentages, indicator values.
- **Technicals**: Don't just list values. Interpret them. Look for patterns, divergences, key levels.
- **Sentiment**: Analyze the nuance of news. Is market ignoring bad news? (Bullish). Selling on good news? (Bearish).

===========================================
OUTPUT FORMAT (Markdown):
===========================================

## Institutional Market Briefing: {ticker}

### 1. Technical Deep Dive
- **Price Structure**: Analyze market structure (HH/HL or LL/LH). Identify key support/resistance zones.
- **Indicator Confluence**: Cite specific values with interpretation (e.g., "RSI at 72 showing bearish divergence").
- **Chart Patterns**: Identify any developing patterns (Flags, Wedges, H&S).
- **Volatility**: Comment on Bollinger Bands, ATR. Is a big move imminent?

### 2. Macro & Fundamental Landscape
- **Macro Correlation**: How is DXY/VIX/broader market impacting this asset?
- **Fundamental Health**: Comment on valuation metrics relative to price action.

### 3. Sentiment & Narrative Analysis
- **Dominant Narrative**: What story is driving price? (e.g., "ETF Inflows", "Regulatory Fear")
- **News Reaction**: How is price reacting to headlines? Confirm or deny the narrative.
- **Insider Activity**: Any significant insider/institutional moves?

### 4. Key Levels & Setup Identification (Data Only — No Opinion)

**⚠️ IMPORTANT: This section must be FACTUAL ONLY. Do NOT include verdicts, probabilities, or directional calls.**

- **Key Resistance Levels**:
  - 🔴 $[Level 1] — [Technical justification, e.g., "200 EMA confluence with prior swing high"]
  - 🔴 $[Level 2] — [Technical justification]

- **Key Support Levels**:
  - 🟢 $[Level 1] — [Technical justification, e.g., "Weekly demand zone + 0.618 Fib"]
  - 🟢 $[Level 2] — [Technical justification]

- **Potential Long Setup** (IF conditions met):
  - Trigger: [e.g., "Break above $X with volume"]
  - Target: $[Level]
  - Invalidation: $[Level]

- **Potential Short Setup** (IF conditions met):
  - Trigger: [e.g., "Rejection at $X"]
  - Target: $[Level]
  - Invalidation: $[Level]

- **Risk Factors to Monitor**: [List specific risks, e.g., "Fed announcement Wednesday", "Approaching earnings"]

🚫 DO NOT INCLUDE: Verdicts (BULLISH/BEARISH), probability estimates, conviction levels, or trading recommendations. The Portfolio Manager will make those decisions.
{deep_dive_section}
===========================================
DATA INGESTION:
===========================================
[Ticker] {ticker}
[Technicals] {json.dumps(technical_data, indent=2)}
[Fundamentals] {fundamentals_text}
[Macro Context] {macro_text}
[News] {news_text}
[Insider Data] {insider_text}
[Derivative Data] {deep_dive_data_text}
"""
        
        try:
            report_text = generate_text_with_provider(prompt, provider, model_name, purpose=f"Analyst Report: {ticker}", pm_id="ALL")
            
            # Update Cache (still inside lock)
            analyst_cache[ticker] = {
                "timestamp": datetime.now(),
                "price": current_price,
                "report": report_text
            }
            save_analyst_cache(analyst_cache)
            
            return report_text
        except Exception as e:
            logger.error(f"Analyst Error: {e}")
            return f"Analyst Report Unavailable. Error: {e}"
def generate_pm_decision(ticker: str, analyst_report: str, trade_setup: dict, current_position: str, strategy) -> dict:
    """
    Stage 2: The Portfolio Manager
    Makes the final decision based on the Analyst's report and Strategy Mandate.
    """
    config = get_config()
    provider = config.get("pm_provider", "gemini")
    model_name = config.get("pm_model", "gemini-2.5-pro")
    
    setup_text = "No specific trade setup identified."
    if trade_setup:
        setup_text = f"""
        Proposed Trade Setup (Algorithmic):
        - Entry Zone: {trade_setup.get('entry_zone')}
        - Stop Loss: {trade_setup.get('stop_loss')}
        - Targets: {trade_setup.get('target_1')} / {trade_setup.get('target_2')}
        """
    
    strategy_modifier = ""
    if strategy:
        strategy_modifier = f"\nSTRATEGY MANDATE:\n{strategy.get_full_prompt()}\n"

    # ===========================================
    # PROMPT STRUCTURE OPTIMIZED FOR OPENAI PREFIX CACHING
    # Static instructions first (~1200 tokens), dynamic data last
    # ===========================================
    prompt = f"""
▶ STATIC_SYSTEM_CONTEXT (DO NOT MODIFY - CACHED)
===========================================
ROLE: Elite Portfolio Manager.
OBJECTIVE: Evaluate the Analyst Report and execute the best risk-adjusted trade.

---------------------------------------------------
▶ CHAIN_OF_THOUGHT (Required - Think Step by Step)

Before outputting your decision, you MUST explicitly reason through:

1. **Setup Selection**: Based on the analyst's key levels and potential setups, which setup (Long or Short) aligns with your strategy?
2. **Invalidation Condition**: What specific price level or structural break proves you wrong?
3. **Steel Man Risk**: What is the STRONGEST argument AGAINST this trade? Why are you still taking it?
4. **Edge Quality**: DEEP (structural tailwind) | MODERATE (tactical) | SHALLOW (speculative) | NO EDGE
5. **Fee Hurdle Check**: Expected move > 0.3% to cover ~0.15% fees? If not, WAIT.
6. **Risk USD**: How many dollars are you risking if stop loss hits? (Entry - Stop) * Position Size
7. **Sizing Logic**: Based on confidence and edge depth. DEEP = 15-20%, MODERATE = 10-15%, SHALLOW = 5-10%

---------------------------------------------------
▶ TRADING_DECISIONS (Final Output - JSON Only, No Markdown)

FORMAT:
{{
    "decision": "BUY" | "SELL" | "HOLD" | "WAIT",
    "action_type": "OPEN_LONG" | "OPEN_SHORT" | "CLOSE_LONG" | "CLOSE_SHORT" | "ADD_LONG" | "ADD_SHORT" | "WAIT",
    "setup_type": "LONG" | "SHORT" | "NONE",
    "confidence": 0-10, (Your derived confidence score from the rubric)
    "allocation_percentage": 0.0-1.0, (e.g., 0.15 for 15%)
    "risk_usd": 0.0, (Dollar amount at risk if stop hit)
    "is_add": true | false, (Are you adding to existing position?)
    "leverage": 1.0, (Default 1x for spot, higher per strategy constraints)
    "reasoning": "Explain: (1) Which setup you chose and why, (2) Edge Depth, (3) Invalidation Level, (4) Steel Man Risk, (5) Why the edge exceeds fee hurdle.",
    "psychology": "Comment on crowd positioning (Fear/Greed) vs your contrarian/aligned stance.",
    "stop_loss": price_level,
    "take_profit": price_level,
    "exit_plan": {{
        "invalidation_condition": "Describe the exact structural break that invalidates the trade",
        "partial_targets": [
            {{"price": price1, "percentage": 0.5, "reasoning": "Take 50% at first resistance"}}
        ]
    }}
}}

CRITICAL RULES:
- If Edge Depth is SHALLOW or NO EDGE, set decision to "WAIT"
- If expected move < 0.3%, set decision to "WAIT" (fee hurdle not met)
- Confidence must be an integer between 0 and 10

===========================================
▶ USER_DATA (DYNAMIC - Your specific context)
===========================================
[Strategy Name] {strategy.name if strategy else "General"}
[Strategy Mandate] {strategy.get_full_prompt() if strategy else "Maximize alpha with controlled risk. Position sizing is handled externally by the Python Risk Engine."}
[Ticker] {ticker}
[Current Position] {current_position}
[Portfolio Risk Status] Assumed Normal

[Analyst Briefing & Deep Dive]
{analyst_report}

[Algorithmic Setup]
{setup_text}
"""
    
    try:
        purpose = f"PM Decision: {ticker}"
        pm_id_val = strategy.pm_id if hasattr(strategy, 'pm_id') else "Unknown"
        text = generate_text_with_provider(prompt, provider, model_name, purpose=purpose, pm_id=pm_id_val)
        
        # Strip potential markdown formatting that the AI might add despite instructions
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
             text = text.split("```")[0] # Aggressive strip if json tag missing but code block exists
             
        text = text.strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"PM Error: {e}")
        return {
            "decision": "WAIT",
            "action_type": "WAIT",
            "confidence": 0,
            "reasoning": f"PM Decision failed: {e}",
            "psychology": "Error"
        }

def get_ai_analysis(ticker: str, technical_data: dict, news: list = [], macro_data: dict = {}, trade_setup: dict = None, current_position: str = "None", strategy = None, fundamentals: dict = {}, insider_data: dict = {}, skip_pm: bool = False, deep_dive_data: dict = {}) -> dict:
    """
    Orchestrates the Two-Stage AI Analysis.
    If skip_pm is True, only generates the Analyst Report and returns a placeholder decision.
    """
    if not GEMINI_API_KEY and not OPENAI_API_KEY and not OPENROUTER_API_KEY and not OPENCLAW_AVAILABLE:
        return {
            "reasoning": "AI Analysis Unavailable: Please set GEMINI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY environment variable.",
            "psychology": "Market psychology requires AI integration."
        }

    logger.info(f"   [AI] Stage 1: Analyst generating report for {ticker}...")
    analyst_report = generate_analyst_report(ticker, technical_data, news, macro_data, fundamentals, insider_data, deep_dive_data)
    
    if skip_pm:
        return {
            "decision": "WAIT",
            "action_type": "WAIT",
            "confidence": None,
            "allocation_percentage": 0.0,
            "reasoning": "Pending Portfolio Level Decision",
            "psychology": "Pending",
            "analyst_report": analyst_report
        }

    logger.info(f"   [AI] Stage 2: PM making decision for {ticker}...")
    pm_decision = generate_pm_decision(ticker, analyst_report, trade_setup, current_position, strategy)
    
    # Embed the analyst report into the reasoning for full context in the UI
    pm_decision["analyst_report"] = analyst_report
    
    return pm_decision

def generate_portfolio_decisions(all_reports: list, portfolio_state: dict, strategy, competitor_data: dict = None, is_weekend: bool = False) -> dict:
    """
    NEW: Portfolio-Level Decision Making
    PM reviews ALL analyst reports together and makes portfolio-aware decisions.
    
    Args:
        all_reports: List of {ticker, price, analysis, current_position}
        portfolio_state: Current portfolio status from portfolio_service.get_status()
        strategy: PM strategy configuration
        competitor_data: Optional dict containing status of other PMs (for PM5)
        is_weekend: True if it's currently a weekend (stocks markets closed)
    
    Returns:
        {
            "trades": [
                {
                    "ticker": "BTC-USD",
                    "action": "ADD_LONG",
                    "confidence": 9.0,
                    "allocation_percentage": 0.10,
                    "reasoning": "...",
                    "exit_plan": {...}
                },
                ...
            ],
            "manager_summary": "Overall portfolio assessment..."
        }
    """
    if not GEMINI_API_KEY and not OPENAI_API_KEY and not OPENROUTER_API_KEY and not OPENCLAW_AVAILABLE:
        return {
            "trades": [],
            "manager_summary": "AI Analysis Unavailable: Please set GEMINI_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY environment variable."
        }
    
    config = get_config()
    provider = config.get("pm_provider", "gemini")
    model_name = config.get("pm_model", "gemini-2.5-pro")
    
    # Build comprehensive portfolio context
    current_positions = portfolio_state.get("positions", {})
    available_cash = portfolio_state.get("available_cash", 0)
    total_value = portfolio_state.get("total_value", 0)
    balance = portfolio_state.get("balance", 0)
    
    # --- SURVIVAL MODE CHECK (Kill-Switch) ---
    # If strategy has a defined drawdown limit (e.g., PM5), check if we breached it.
    forced_defensive_mode = False
    drawdown_pct = 0.0
    
    if hasattr(strategy, 'get_drawdown_limit'):
        limit = strategy.get_drawdown_limit()
        
        # Calculate current drawdown from history
        history = portfolio_state.get("history", [])
        max_val = 0
        if history:
            max_val = max(h["total_value"] for h in history)
            
        # Also ensure we check current total_value against max
        if total_value > max_val: 
            max_val = total_value
            
        if max_val > 0:
            drawdown_pct = (total_value - max_val) / max_val
            
            if drawdown_pct <= -limit: # e.g., -0.15 <= -0.12
                forced_defensive_mode = True
                logger.warning(f"🚨 [SURVIVAL ALERT] Drawdown {drawdown_pct:.1%} exceeds limit {-limit:.1%}. FORCING DEFENSIVE MODE.")

    # Format current positions with P&L
    positions_summary = []
    for ticker, pos in current_positions.items():
        positions_summary.append({
            "ticker": ticker,
            "side": "LONG" if pos["qty"] > 0 else "SHORT",
            "qty": abs(pos["qty"]),
            "entry_price": pos["avg_price"],
            "current_price": pos.get("current_price"),
            "unrealized_pnl": pos.get("unrealized_pnl"),
            "exit_plan": pos.get("exit_plan", {})
        })
    
    # Format competitor data if available (for PM5 "The Survivor")
    competitor_context = "Not applicable for this strategy"
    if competitor_data:
        competitor_lines = ["Your rivals' current standings:"]
        for pm_id, pm_status in competitor_data.items():
            # Handle positions being either a dict or a list
            positions = pm_status.get('positions', {})
            if isinstance(positions, dict):
                position_tickers = list(positions.keys())
            elif isinstance(positions, list):
                position_tickers = [p.get('ticker', str(p)) for p in positions if isinstance(p, dict)]
            else:
                position_tickers = []
            
            competitor_lines.append(f"- {pm_id}: Total Value ${pm_status.get('total_value', 0):.2f}, "
                                    f"Positions: {position_tickers or 'None'}")
        competitor_context = "\n".join(competitor_lines)
    
    # Format all analyst reports
    reports_text = []
    for i, report in enumerate(all_reports, 1):
        ticker = report["ticker"]
        analysis = report["analysis"]
        current_pos = report.get("current_position", "None")
        
        analyst_report = analysis.get("psychology", {}).get("deep_reasoning", "N/A")
        if "analyst_report" in analysis:
            analyst_report = analysis["analyst_report"]
        
        reports_text.append(f"""
[REPORT {i}: {ticker}]
Current Position: {current_pos}
Price: ${report["price"]:.2f}

Analyst Report:
{analyst_report}

Technical Context (Raw Data — Derive Your Own Signals):
- Trend Direction: {analysis["summary"]["current_trend"]}
- Price vs EMAs: {analysis["technical_context"]["price_action"]}
- Momentum: {analysis["technical_context"]["momentum"]}
- Volume: {analysis["technical_context"]["volume"]}
- Bollinger Bands: {analysis["technical_context"]["bollinger_bands"]}

Exit Plan (If Applicable):
{json.dumps(analysis.get("exit_plan", {}), indent=2)}
""")
    
    # ===========================================
    # PROMPT STRUCTURE OPTIMIZED FOR OPENAI PREFIX CACHING
    # Static instructions first (~1400 tokens), dynamic data last
    # ===========================================
    prompt = f"""
▶ STATIC_SYSTEM_CONTEXT (DO NOT MODIFY - CACHED)
===========================================
ROLE: Hedge Fund Portfolio Manager

YOUR TASK:
Review ALL analyst reports and your current portfolio. Make decisions considering:

1. **Portfolio Analysis**:
   - Analyze current holdings and PnL.
   - Are we over-exposed? Are we winning/losing?
   - Comment on the overall health of the portfolio.

2. **Position Management**:
   - Should you ADD to existing positions if the setup has strengthened?
   - Should you CLOSE positions if the thesis has weakened?
   - Should you OPEN new positions in better opportunities?

3. **Capital Allocation**:
   - Prioritize the BEST setups across all opportunities
   - Consider portfolio balance and diversification
   - Respect your strategy's max position size
   - Maintain minimum cash buffer

4. **Risk Management**:
   - Don't over-concentrate in similar assets
   - Consider correlation between positions
   - Ensure exit plans are in place

COMPETITOR ANALYSIS INSTRUCTIONS:
- Analyze the rivals' positions if provided.
- If they are heavily invested in an asset you dislike, use that as a contrarian signal.
- If they are winning, consider if you should follow or fade.
- Your goal is to beat their Total Value.

RETURN FORMAT (JSON ONLY, NO MARKDOWN):
{{
    "portfolio_analysis": "Commentary on current holdings, PnL, and overall exposure.",
    "trades": [
        {{
            "ticker": "BTC-USD",
            "action": "ADD_LONG",
            "confidence": 9.0,
            "allocation_percentage": 0.10,
            "reasoning": "BTC setup has strengthened since entry. RSI pulled back to 45 from 72, price held above EMA21 support at $95,200. Adding 10% to scale into the move.",
            "exit_plan": {{
                "stop_loss": 94500,
                "target_price": 98000,
                "trailing_stop": {{
                    "enabled": true,
                    "value": 0.05
                }},
                "partial_targets": [
                    {{"price": 97000, "percentage": 0.5, "reasoning": "Take 50% at resistance"}}
                ],
                "invalidation_condition": "Break below EMA50 at $94,200"
            }}
        }}
    ],
    "manager_summary": "Reviewed X assets. [Specific actions taken and reasoning]"
}}

ACTION TYPES:
- OPEN_LONG: Open new long position
- ADD_LONG: Add to existing long position
- CLOSE_LONG: Close existing long position
- OPEN_SHORT: Open new short position
- ADD_SHORT: Add to existing short position
- COVER_SHORT: Close existing short position

CRITICAL RULES:
- Only recommend trades with confidence >= your strategy's threshold
- Prioritize trades by opportunity quality (best first)
- For ADD_LONG/ADD_SHORT: explain why you're scaling in
- For CLOSE_LONG/COVER_SHORT: explain what invalidated the thesis
- Be specific with price levels and technical reasons
- Return ONLY valid JSON, no markdown formatting

⚠️ SANITY CHECK (MANDATORY):
- The "Price:" shown for each asset is the CURRENT LIVE price. Use THIS as your reference.
- If the analyst report mentions a trigger level (e.g., "break above $X"), verify it's realistic:
  - Entry triggers more than 3% away from current price should be treated as CONDITIONAL, not immediate.
  - DO NOT propose "OPEN_LONG" if the trigger level is significantly above current price — that's a WAIT scenario.
- If current price is $91,000 and trigger is $99,400, that's an 9% gap — NOT an immediate trade. WAIT instead.

{strategy.get_confidence_rubric()}

===========================================
▶ USER_DATA (DYNAMIC - Your specific context)
===========================================
[Strategy Name] {strategy.name}
[Strategy Description] {strategy.description}
[Strategy Mandate] {strategy.get_full_prompt()}
[Max Position Size] {strategy.get_max_position_size():.0%}
[Min Cash Buffer] {strategy.get_min_cash_buffer():.0%}
[Confidence Threshold] {strategy.get_confidence_threshold()}/10

[URGENT RISK STATUS]
{"🚨 CRITICAL: MAX DRAWDOWN BREACHED. YOU ARE IN FORCED DEFENSIVE MODE. DO NOT OPEN NEW POSITIONS. FOCUS ON REDUCING RISK AND PRESERVING CASH." if forced_defensive_mode else "Normal Operations."}

[Portfolio State]
- Total Account Value: ${total_value:.2f}
- Cash Balance: ${balance:.2f}
- Available Cash (after collateral): ${available_cash:.2f}
- Cash Utilization: {((total_value - available_cash) / total_value * 100) if total_value > 0 else 0:.1f}%

[Market Status]
- Day Type: {"WEEKEND (Stock markets CLOSED - Crypto only)" if is_weekend else "WEEKDAY (All markets active)"}
- Note: {"Only cryptocurrency positions can be traded today. Stock positions will resume Monday." if is_weekend else "All asset classes available for trading."}

[Existing Positions ({len(positions_summary)})]
{json.dumps(positions_summary, indent=2)}

[Competitor Intelligence]
{competitor_context}

[Analyst Reports ({len(all_reports)} assets analyzed)]
{''.join(reports_text)}
"""
    
    try:
        purpose = "Portfolio Decision (Multi-Asset)"
        pm_id_val = strategy.pm_id if hasattr(strategy, 'pm_id') else "Unknown"
        text = generate_text_with_provider(prompt, provider, model_name, purpose=purpose, pm_id=pm_id_val)
        
        # Strip potential markdown formatting
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        text = text.strip()
        result = json.loads(text)
        
        # Ensure required fields exist
        if "trades" not in result:
            result["trades"] = []
        if "manager_summary" not in result:
            result["manager_summary"] = "Portfolio review complete."
            
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"PM JSON Parse Error: {e}")
        logger.error(f"Raw response: {text[:500]}...")
        return {
            "trades": [],
            "manager_summary": f"Error parsing PM response: {e}"
        }
    except Exception as e:
        logger.error(f"PM Decision Error: {e}")
        return {
            "trades": [],
            "manager_summary": f"Portfolio decision unavailable: {e}"
        }
