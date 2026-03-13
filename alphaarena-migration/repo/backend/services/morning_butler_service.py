import os
import json
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
from backend.utils.logger import logger
from backend.services import data_service
from backend.services.llm_provider import get_llm_provider
from backend.runtime import config_path, state_dir

# Load environment variables from .env file
load_dotenv()


class MorningButlerService:
    def __init__(self):
        # Load config to get model settings
        self.model_name = "gpt-5-nano" # Default
        self.provider = "openai"
        self.briefing_file = str(state_dir("briefings") / "daily_briefing.json")
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.briefing_file), exist_ok=True)

        
        runtime_config = config_path()
        if runtime_config.exists():
            try:
                with open(runtime_config, 'r') as f:
                    config = json.load(f)
                    self.model_name = config.get("butler_model", "gpt-5-nano")
                    self.provider = config.get("butler_provider", "openai")
            except Exception as e:
                logger.error(f"Error loading config: {e}")

        # Get API Key based on provider
        api_key = None
        if self.provider.lower() == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif self.provider.lower() == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            
        if not api_key:
            logger.error(f"API Key for {self.provider} not found in environment variables.")
            # We don't raise here to allow the service to be instantiated, but run_briefing might fail or handle it.
        
        try:
            self.llm_provider = get_llm_provider(self.provider, api_key, self.model_name)
        except Exception as e:
            logger.error(f"Failed to initialize LLM Provider: {e}")
            self.llm_provider = None
        
    def run_briefing(self):
        """
        Orchestrates the morning briefing pipeline:
        1. Fetch market data
        2. Score and rank tickers
        3. Generate LLM summary
        4. Send email
        5. Return summary for UI
        """
        print("\n" + "="*50)
        print("🎩 MORNING BUTLER: Starting Briefing Protocol")
        print("="*50)
        logger.info("Starting Morning Butler briefing...")
        
        if not self.llm_provider:
             print("❌ ERROR: LLM Provider not initialized. Check API keys.")
             return {"headlines": [], "overall_summary": "Error: LLM Provider not initialized."}

        # 1. Fetch Data
        print("📡 Fetching market data from Yahoo Finance & Alpha Vantage...")
        data = self._fetch_data()
        print("✅ Market data received.")
        
        # 2. Score and Rank
        print("📊 Scoring and ranking tickers...")
        top_tickers = self._score_and_rank(data)
        print(f"🏆 Top Tickers identified: {', '.join([t['symbol'] for t in top_tickers])}")
        
        # 3. Generate Summary (with macro context for richer reports)
        print(f"🧠 Generating Intelligence Briefing using {self.provider}/{self.model_name}...")
        macro_context = {
            "macro": data.get("macro", {}),
            "fear_greed": data.get("fear_greed", {})
        }
        summary_json = self._generate_summary(top_tickers, macro_context)
        print("✅ Briefing generated.")
        
        # 4. Send Email
        print("📧 Dispatching email via Gmail SMTP...")
        self._send_email(summary_json)
        
        print("="*50)
        print("🎩 MORNING BUTLER: Mission Accomplished")
        print("="*50 + "\n")
        
        # 5. Save Briefing
        print("💾 Saving briefing to disk...")
        self._save_briefing(summary_json)
        
        return summary_json

    def _save_briefing(self, summary):
        """Saves the briefing to a JSON file."""
        try:
            # Add timestamp
            summary['generated_at'] = datetime.now().isoformat()
            with open(self.briefing_file, 'w') as f:
                json.dump(summary, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving briefing: {e}")

    def get_latest_briefing(self):
        """Retrieves the latest saved briefing."""
        if os.path.exists(self.briefing_file):
            try:
                with open(self.briefing_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading briefing file: {e}")
        return {"overall_summary": "No briefing generated yet today."}


    def _fetch_data(self):
        """Fetches data from all FMP endpoints including predictive sources."""
        logger.info("Fetching market data...")
        
        # Coiled Spring Screener Filters
        coiled_spring_filters = {
            'priceLowerThan': 5,
            'marketCapLowerThan': 100000000, # 100M
            'volumeMoreThan': 200000,
            'betaMoreThan': 1, # Volatile
            'limit': 20
        }

        # Fetch macro context for enhanced report quality
        macro_data = data_service.get_macro_data()
        fear_greed = data_service.get_crypto_fear_greed()

        return {
            "actives": data_service.get_market_actives(),
            "gainers": data_service.get_market_gainers(),
            "losers": data_service.get_market_losers(),
            "pre_market": data_service.get_pre_market_gainers(),
            "after_hours": data_service.get_after_hours_gainers(),
            "general_news": data_service.get_general_stock_news(limit=50),
            "coiled_springs": data_service.get_stock_screener(filters=coiled_spring_filters),
            "earnings": data_service.get_earnings_calendar(),
            "macro": macro_data,
            "fear_greed": fear_greed,
        }

    # _detect_unusual_volume removed - logic moved to data_service.get_technical_summary


    def _score_and_rank(self, data):
        """
        Scores tickers based on predictive signals:
        1. Pre-market/After-hours moves
        2. Unusual Volume
        3. News Catalysts
        4. Coiled Spring setups
        """
        candidates = {}
        
        def add_candidate(ticker, source, data_point, score_boost=0):
            if ticker not in candidates:
                candidates[ticker] = {
                    "symbol": ticker,
                    "tags": set(),
                    "score": 0,
                    "price": data_point.get('price', 0),
                    "volume": data_point.get('volume', 0),
                    "catalyst": None
                }
            
            candidates[ticker]["tags"].add(source)
            candidates[ticker]["score"] += score_boost
            
            # Update volume if higher
            if data_point.get('volume', 0) > candidates[ticker]["volume"]:
                candidates[ticker]["volume"] = data_point.get('volume', 0)

        # 1. Process Pre-Market (High Priority)
        for item in data.get("pre_market", []):
            add_candidate(item['symbol'], "Pre-Market Mover", item, score_boost=5)
            
        # 2. Process After-Hours
        for item in data.get("after_hours", []):
            add_candidate(item['symbol'], "After-Hours Mover", item, score_boost=3)
            
        # 3. Process Coiled Springs (Screener)
        for item in data.get("coiled_springs", []):
            add_candidate(item['symbol'], "Coiled Spring", item, score_boost=2)
            
        # 4. Process Actives (Volume Check)
        for item in data.get("actives", []):
            add_candidate(item['symbol'], "High Volume", item, score_boost=3)

        # Sort candidates by initial score to limit technical fetching
        sorted_candidates = sorted(candidates.values(), key=lambda x: x['score'], reverse=True)
        top_candidates = sorted_candidates[:12] # Take top 12 for deep dive
        
        final_list = []
        for cand in top_candidates:
            ticker = cand['symbol']
            
            # Fetch Technicals (The "Brain" Upgrade)
            technicals = data_service.get_technical_summary(ticker)
            cand['technicals'] = technicals
            
            if technicals:
                # RVOL Boost
                rvol = technicals.get('rvol', 1.0)
                if rvol > 1.5:
                    cand['score'] += 3
                    cand['tags'].add(f"RVOL {rvol}x")
                elif rvol > 3.0:
                    cand['score'] += 5
                    cand['tags'].add("Volume Explosion")
                    
                # RSI Boosts
                rsi = technicals.get('rsi', 50)
                if rsi < 30:
                    cand['score'] += 2
                    cand['tags'].add("Oversold")
                elif rsi > 70:
                    cand['score'] += 2
                    cand['tags'].add("Overbought Momentum")
                    
                # Trend Boost
                if technicals.get('trend') == "Bullish":
                    cand['score'] += 2
            
            # Fetch specific news
            news = data_service.get_ticker_news(ticker)
            cand['recent_news'] = news[:2] if news else []
            
            # Check for News Catalyst tag
            if news:
                # Simple keyword check
                keywords = ['FDA', 'Approval', 'Merger', 'Acquisition', 'Earnings', 'Contract', 'Patent', 'Partnership']
                for n in news:
                    if any(k.lower() in n.get('title', '').lower() for k in keywords):
                        cand['tags'].add("News Catalyst")
                        cand['score'] += 3
                        break
            
            # Fetch Analyst Recs
            recs = data_service.get_analyst_recommendations(ticker)
            cand['analyst_recs'] = recs
            
            cand['tags'] = list(cand['tags']) # Convert to list
            final_list.append(cand)
            
        # Re-sort with new scores
        final_list.sort(key=lambda x: x['score'], reverse=True)
        return final_list[:8] # Return top 8

    def _generate_summary(self, top_tickers, macro_context=None):
        """
        Generates the comprehensive Morning Butler briefing using LLM.
        Includes retry logic with exponential backoff for API timeouts.
        """
        logger.info("Generating LLM summary...")
        
        # Format macro context for the prompt
        macro_text = ""
        if macro_context:
            macro = macro_context.get("macro", {})
            fg = macro_context.get("fear_greed", {})
            macro_text = f"""

MACRO ENVIRONMENT:
- S&P 500: {macro.get('SP500', 'N/A')}
- VIX (Fear Gauge): {macro.get('VIX', 'N/A')}
- 10Y Treasury: {macro.get('US_10Y_YIELD', 'N/A')}%
- Dollar (DXY): {macro.get('DXY', 'N/A')}
- Gold: ${macro.get('GOLD', 'N/A')}
- Crypto Fear & Greed: {fg.get('value', 'N/A')} ({fg.get('classification', 'N/A')})
"""
        
        prompt = f"""You are Morning Butler, a world-class market-intelligence assistant used by hedge funds, algorithmic traders, and elite private investors.
Your mission: deliver a concise, confident, actionable daily briefing that gives the user a clear plan for attacking the best stock opportunities today.
{macro_text}
INPUT DATA (Structured Market Intelligence):
{json.dumps(top_tickers, indent=2)}

CRITICAL INSTRUCTIONS:
1. **USE THE TECHNICALS**: You have real data now (RSI, RVOL, EMAs). Use it.
   - If RSI > 70, mention "Overbought".
   - If Price > SMA200, mention "Long-term Uptrend".
   - If RVOL > 2.0, mention "Heavy Volume Interest".
2. **Define Precise Levels**: Use the SMA levels and Price provided to define logical Entry/Stop zones.
   - e.g. "Stop below SMA20 at $145.20"


Transform this data into clarity → conviction → action.

🔥 OUTPUT FORMAT (Follow EXACTLY)

Return a JSON object with this structure:
{{
    "market_overview": "50-120 word summary of macro backdrop, overnight sentiment, futures direction, major catalysts today. Calm, authoritative, no noise.",
    
    "market_temperature": {{
        "momentum": 3,
        "volatility": 4,
        "risk_appetite": 2,
        "interpretation": "One sentence explaining what these 1-5 ratings imply for today's trading conditions."
    }},
    
    "top_opportunities": [
        {{
            "symbol": "TICKER",
            "headline": "One-line summary of why it matters today",
            "why_it_matters": "Explain the catalyst, volume anomaly, rotation trend, or technical setup",
            "action_plan": {{
                "entry_zone": "Price range for entry",
                "breakout_level": "Key breakout price",
                "stop_zone": "Stop loss area",
                "profit_targets": "T1: $X, T2: $Y"
            }},
            "risks": ["Risk 1", "Risk 2"],
            "timeframe": "scalp / day trade / swing",
            "signal_strength": "High/Medium/Low"
        }}
    ],
    
    "high_risk_corner": [
        {{
            "symbol": "TICKER",
            "catalyst": "Exact reason this is worth watching",
            "warning": "Why this is speculative"
        }}
    ],
    
    "news_that_matters": [
        {{
            "headline": "Headline text",
            "why_it_matters": "One sentence impact"
        }}
    ],
    
    "gameplan": {{
        "priority_setups": "Top 2-3 tickers to focus on",
        "avoid": "What to stay away from today",
        "key_levels": "Critical S/R levels to monitor",
        "risk_sizing": "Position sizing guidance based on market temperature"
    }},
    
    "overall_summary": "2-sentence summary: the #1 setup to watch and today's trading stance."
}}

🔒 REQUIREMENTS:
- Zero hype. Zero fluff.
- Never invent tickers not in the input data.
- If data is weak, SAY SO honestly.
- Keep outputs tight, structured, immediately useful.
- Goal: user finishes reading and knows exactly what to do."""
        
        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 10  # seconds
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff: 10s, 20s, 40s
                    logger.info(f"⏳ Retry attempt {attempt + 1}/{max_retries} after {delay}s delay...")
                    print(f"⏳ Retrying LLM generation (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                
                response = self.llm_provider.generate_text(prompt, purpose="Daily Morning Briefing", pm_id="ALL")
                
                # Clean response if it contains markdown code blocks
                clean_response = response.replace("```json", "").replace("```", "").strip()
                result = json.loads(clean_response)
                
                # Success! Log and return
                if attempt > 0:
                    logger.info(f"✅ LLM generation succeeded on retry {attempt + 1}")
                    print(f"✅ LLM generation succeeded on retry {attempt + 1}")
                
                return result
                
            except Exception as e:
                error_msg = str(e)
                is_timeout = "timeout" in error_msg.lower() or "timed out" in error_msg.lower()
                
                if attempt < max_retries - 1:
                    # More retries available
                    logger.warning(f"⚠️ LLM generation failed (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    print(f"⚠️ LLM error: {error_msg}. Retrying...")
                else:
                    # Final attempt failed
                    logger.error(f"❌ LLM generation failed after {max_retries} attempts: {error_msg}")
                    print(f"❌ Error generating summary after {max_retries} attempts: {error_msg}")
                    return {"top_opportunities": [], "overall_summary": f"Failed to generate summary after {max_retries} retries: {error_msg}"}

    def _send_email(self, summary_json):
        """Sends the comprehensive briefing via Gmail SMTP."""
        gmail_user = os.getenv('GMAIL_USER')
        gmail_password = os.getenv('GMAIL_PASSWORD')
        
        # Detailed validation with clear error messages
        if not gmail_user:
            logger.error("❌ GMAIL_USER not set in .env file")
            print("❌ Email skipped: GMAIL_USER not set in .env")
            return
        if not gmail_password:
            logger.error("❌ GMAIL_PASSWORD not set in .env file")
            print("❌ Email skipped: GMAIL_PASSWORD not set in .env")
            return
        
        # Get recipients: use BUTLER_EMAIL_RECIPIENTS if set, otherwise send to GMAIL_USER
        # Format: comma-separated list, e.g., "user1@email.com,user2@email.com"
        # NOTE: Make sure env var is spelled correctly as BUTLER_EMAIL_RECIPIENTS (not UTLER_EMAIL_RECIPIENTS)
        recipients_str = os.getenv('BUTLER_EMAIL_RECIPIENTS', '')
        
        if not recipients_str:
            logger.warning("⚠️ BUTLER_EMAIL_RECIPIENTS not set, falling back to GMAIL_USER")
            print("⚠️ BUTLER_EMAIL_RECIPIENTS not set, sending to GMAIL_USER only")
            recipients_str = gmail_user
            
        recipients = [email.strip() for email in recipients_str.split(',') if email.strip()]
        
        if not recipients:
            recipients = [gmail_user]

        logger.info(f"📧 Sending email to {len(recipients)} recipient(s): {', '.join(recipients)}")
        print(f"📧 Recipients: {', '.join(recipients)}")
        
        # Format Email Body
        date_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"🎩 Morning Butler Brief — {date_str}"
        
        # Get market temperature
        temp = summary_json.get('market_temperature', {})
        gameplan = summary_json.get('gameplan', {})
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 700px; margin: auto; padding: 20px;">
        <h1 style="color: #1a1a2e;">🎩 Morning Butler Brief — {date_str}</h1>
        
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h2 style="margin-top: 0;">⏰ Market Overview</h2>
            <p>{summary_json.get('market_overview', 'No overview available.')}</p>
        </div>
        
        <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h2 style="margin-top: 0;">🌡️ Market Temperature</h2>
            <table style="width: 100%;">
                <tr>
                    <td><strong>Momentum:</strong> {'🟢' * temp.get('momentum', 0)}{'⚪' * (5 - temp.get('momentum', 0))} ({temp.get('momentum', 'N/A')}/5)</td>
                </tr>
                <tr>
                    <td><strong>Volatility:</strong> {'🟡' * temp.get('volatility', 0)}{'⚪' * (5 - temp.get('volatility', 0))} ({temp.get('volatility', 'N/A')}/5)</td>
                </tr>
                <tr>
                    <td><strong>Risk Appetite:</strong> {'🔴' * temp.get('risk_appetite', 0)}{'⚪' * (5 - temp.get('risk_appetite', 0))} ({temp.get('risk_appetite', 'N/A')}/5)</td>
                </tr>
            </table>
            <p><em>{temp.get('interpretation', '')}</em></p>
        </div>
        
        <h2>🏆 Top Opportunities</h2>
        """
        
        for item in summary_json.get('top_opportunities', []):
            signal = item.get('signal_strength', 'Medium')
            color = "#28a745" if signal == "High" else "#ffc107" if signal == "Medium" else "#dc3545"
            action = item.get('action_plan', {})
            
            html_content += f"""
            <div style="border-left: 4px solid {color}; padding: 10px 15px; margin-bottom: 15px; background: #fafafa;">
                <h3 style="margin: 0;">{item.get('symbol', 'N/A')} <span style="color: {color}; font-size: 0.8em;">({signal})</span></h3>
                <p><strong>{item.get('headline', '')}</strong></p>
                <p>{item.get('why_it_matters', '')}</p>
                <table style="font-size: 0.9em; background: #fff; padding: 10px; width: 100%;">
                    <tr><td>📍 Entry: {action.get('entry_zone', 'N/A')}</td><td>🚀 Breakout: {action.get('breakout_level', 'N/A')}</td></tr>
                    <tr><td>🛑 Stop: {action.get('stop_zone', 'N/A')}</td><td>🎯 Targets: {action.get('profit_targets', 'N/A')}</td></tr>
                </table>
                <p style="font-size: 0.85em; color: #666;">⚠️ Risks: {', '.join(item.get('risks', ['N/A']))}</p>
                <p style="font-size: 0.85em;"><strong>Timeframe:</strong> {item.get('timeframe', 'N/A')}</p>
            </div>
            """
        
        # High Risk Corner
        high_risk = summary_json.get('high_risk_corner', [])
        if high_risk:
            html_content += """<h2>🚀 High-Risk High-Reward Corner</h2>"""
            for item in high_risk:
                html_content += f"""
                <div style="border-left: 4px solid #dc3545; padding: 10px 15px; margin-bottom: 10px; background: #fff5f5;">
                    <strong>{item.get('symbol', 'N/A')}</strong>: {item.get('catalyst', '')}
                    <br><em style="color: #666;">⚠️ {item.get('warning', '')}</em>
                </div>
                """
        
        # News That Matters
        news = summary_json.get('news_that_matters', [])
        if news:
            html_content += """<h2>📰 News That Actually Matters</h2><ul>"""
            for item in news:
                html_content += f"<li><strong>{item.get('headline', '')}</strong> — {item.get('why_it_matters', '')}</li>"
            html_content += "</ul>"
        
        # Gameplan
        html_content += f"""
        <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin-top: 20px;">
            <h2 style="margin-top: 0;">🧭 Today's Gameplan</h2>
            <p><strong>🎯 Priority:</strong> {gameplan.get('priority_setups', 'N/A')}</p>
            <p><strong>🚫 Avoid:</strong> {gameplan.get('avoid', 'N/A')}</p>
            <p><strong>📊 Key Levels:</strong> {gameplan.get('key_levels', 'N/A')}</p>
            <p><strong>💰 Risk Sizing:</strong> {gameplan.get('risk_sizing', 'N/A')}</p>
        </div>
        
        <div style="background: #1a1a2e; color: white; padding: 15px; border-radius: 8px; margin-top: 20px;">
            <strong>Bottom Line:</strong> {summary_json.get('overall_summary', '')}
        </div>
        
        <p style="color: #999; font-size: 0.8em; margin-top: 30px;">Generated by Morning Butler 🎩</p>
        </body>
        </html>
        """
            
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = ', '.join(recipients)  # Multiple recipients
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))
        
        try:
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.login(gmail_user, gmail_password)
            # Send to all recipients
            server.sendmail(gmail_user, recipients, msg.as_string())
            server.quit()
            logger.info(f"✅ Email sent successfully to {len(recipients)} recipient(s).")
            print(f"✅ Email sent successfully to {len(recipients)} recipient(s).")
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP Authentication failed. Check GMAIL_PASSWORD (use App Password, not regular password): {e}")
            print(f"❌ SMTP Auth Error: Use Gmail App Password, not your regular password. Error: {e}")
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"❌ Recipients refused: {e}")
            print(f"❌ Invalid recipient emails: {e}")
        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            print(f"❌ Error sending email: {e}")
