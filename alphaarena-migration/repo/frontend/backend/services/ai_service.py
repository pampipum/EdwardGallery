import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure API Key (User must set this env var)
API_KEY = os.getenv("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)

def get_ai_analysis(ticker: str, technical_data: dict, news: list = [], macro_data: dict = {}, trade_setup: dict = None, current_position: str = "None") -> dict:
    """
    Generates psychological analysis and deep reasoning using Gemini, considering technicals, news, and macro data.
    """
    if not API_KEY:
        return {
            "reasoning": "AI Analysis Unavailable: Please set GEMINI_API_KEY environment variable.",
            "psychology": "Market psychology requires AI integration."
        }

    # Using gemini-2.5-pro as requested by user
    model = genai.GenerativeModel('gemini-2.5-pro')
    
    news_text = "\n".join([f"- {n['title']} ({n['publisher']})" for n in news]) if news else "No recent news available."
    macro_text = "\n".join([f"- {k}: {v}" for k, v in macro_data.items()]) if macro_data else "No macro data available."
    
    setup_text = "No specific trade setup identified."
    if trade_setup:
        setup_text = f"""
        Proposed Trade:
        - Entry Zone: {trade_setup.get('entry_zone')}
        - Stop Loss: {trade_setup.get('stop_loss')}
        - Targets: {trade_setup.get('target_1')} / {trade_setup.get('target_2')}
        """

    prompt = f"""
    ROLE: Hedge Fund Portfolio Manager (DeepSeek Persona).
    
    ASSET: {ticker}
    CURRENT HOLDING: {current_position}
    
    DATA:
    [Technicals] {technical_data}
    [Macro] {macro_text}
    [News] {news_text}
    [Trade Setup] {setup_text}
    
    MARKET TURN DETECTION CHECKLIST:
    1. MARKET REGIME: Is the market Trending or Ranging?
       - If Trending: Look for continuation OR exhaustion (divergence).
       - If Ranging: Look for reversals at boundaries.
    2. MOMENTUM: Check RSI and MACD. Are they aligned with price?
    3. DIVERGENCE: Is there a Bullish/Bearish divergence? (Strong Reversal Signal)
    4. VOLUME: Is there a Volume Spike? (Confirmation of breakout/reversal)
    5. MULTI-TIMEFRAME: Do 1H and 1D charts agree?
    
    STYLE GUIDELINES:
    - Use FIRST PERSON ("I'm holding...", "I'm shorting...", "I'm staying put...").
    - Be DECISIVE but RISK-AWARE.
    - Cite SPECIFIC data points (e.g., "RSI is 72", "price failed at 175").
    - Explain WHY you are taking an action or waiting.
    - Mention your INVALIDATION conditions (e.g., "if it breaks 189...").
    - If holding a position, mention if it's profitable and why you are keeping it.
    - Tone: Professional, analytical, slightly cautious but confident when acting.
    
    SIZING GUIDELINES (Dynamic Risk Management):
    - You must decide the `allocation_percentage` based on your CONFIDENCE.
    - Low Confidence (< 70): 0.0 (Do not trade)
    - Medium Confidence (70-85): 0.05 - 0.08 (5-8%)
    - High Confidence (> 85): 0.10 - 0.15 (10-15%)
    - Max Cap: 0.20 (20%) for extreme conviction only.
    - **CRITICAL**: For REVERSAL/TURN trades (Counter-trend), reduce allocation by 50% (Max 0.08).
    
    CRITICAL INSTRUCTIONS ON ACTION TYPE:
    - You must specify the exact "action_type" based on your decision and current holding.
    - Valid "action_type" values: 
      - "OPEN_LONG" (If holding None and Bullish)
      - "ADD_LONG" (If holding Long and Bullish)
      - "CLOSE_LONG" (If holding Long and Bearish/Taking Profit)
      - "OPEN_SHORT" (If holding None and Bearish)
      - "ADD_SHORT" (If holding Short and Bearish)
      - "COVER_SHORT" (If holding Short and Bullish/Taking Profit)
      - "WAIT" (If uncertain or holding)
    
    EXAMPLES:
    - "I'm holding my short position on NVDA..." -> action_type: "WAIT" or "ADD_SHORT"
    - "I'm taking a short position on GOOGL..." -> action_type: "OPEN_SHORT"
    - "I'm closing my long on AAPL..." -> action_type: "CLOSE_LONG"
    
    OUTPUT (JSON ONLY):
    {{
      "decision": "BUY" | "SELL" | "WAIT",
      "action_type": "OPEN_LONG" | "CLOSE_LONG" | "OPEN_SHORT" | "COVER_SHORT" | "WAIT" | "ADD_LONG" | "ADD_SHORT",
      "confidence": <int 0-100>,
      "allocation_percentage": <float 0.0-0.20>,
      "turn_probability": <int 0-100>,
      "exit_plan": {{
        "stop_loss": <float or null>,
        "target_price": <float or null>,
        "invalidation_condition": "<Specific condition that invalidates this trade idea, e.g. 'Close above 200 EMA'>"
      }},
      "reasoning": "<The full first-person narrative>",
      "psychology": "<Short bullet point on market sentiment/psychology>"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        # Simple cleanup to ensure we get a dict (in a real app, use robust parsing)
        import json
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except Exception as e:
        print(f"AI Error: {e}")
        return {
            "reasoning": "AI Analysis failed to generate.",
            "psychology": "Caution: AI unavailable."
        }
