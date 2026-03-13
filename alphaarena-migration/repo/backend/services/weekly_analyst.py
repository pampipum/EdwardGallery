import os
import json
import re
from datetime import datetime, timedelta
from backend.services.portfolio_service import portfolio_manager
from backend.services.pm_strategies import get_strategy
from backend.services.ai_service import generate_text_with_provider, get_config
from backend.utils.logger import logger
from backend.runtime import state_dir

REPORTS_DIR = str(state_dir("reports"))

class WeeklyAnalystService:
    def __init__(self):
        if not os.path.exists(REPORTS_DIR):
            os.makedirs(REPORTS_DIR)

    def generate_weekly_report(self, pm_id: str) -> dict:
        """
        Gathers weekly and lifetime data for a PM, calls LLM for analysis, and saves the report.
        """
        logger.info(f"📊 [Weekly Analyst] Generating report for {pm_id}...")
        
        try:
            # 1. Run Cybernetic Auto-Audit (Autopilot)
            portfolio = portfolio_manager.get_portfolio(pm_id)
            audit_results = portfolio.auto_audit_active_learnings()
            
            # 2. Gather PM Data (Weekly + Lifetime)
            pm_data = self._gather_pm_data(pm_id)
            if not pm_data:
                return {"error": f"No data found for {pm_id}"}
            
            pm_data["audit_results"] = audit_results
            
            # 3. Get Strategy Mandate
            strategy = get_strategy(pm_id)
            strategy_mandate = strategy.get_full_prompt() if hasattr(strategy, 'get_full_prompt') else strategy.description
            
            # 3. Construct Prompt
            prompt = self._construct_prompt(pm_id, pm_data, strategy_mandate)
            
            # 4. Call LLM using the active runtime configuration
            config = get_config()
            provider = config.get("pm_provider", config.get("analyst_provider", "gemini"))
            model_name = config.get("pm_model", config.get("analyst_model", "gemini-2.5-pro"))
            
            logger.info(f"   [LLM] Sending longitudinal analysis request to {provider} ({model_name})...")
            raw_response = generate_text_with_provider(prompt, provider, model_name, purpose=f"Weekly Analysis: {pm_id}", pm_id=pm_id)
            
            # 5. Parse Markdown and JSON
            report_markdown, proposed_overrides = self._parse_llm_response(raw_response)
            
            # 6. Save Report
            report_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"report_{pm_id}_{report_id}.json"
            report_path = os.path.join(REPORTS_DIR, report_filename)
            
            report_content = {
                "pm_id": pm_id,
                "report_id": report_id,
                "timestamp": datetime.now().isoformat(),
                "performance_summary": pm_data["weekly_summary"],
                "lifetime_summary": pm_data["lifetime_summary"],
                "report_markdown": report_markdown,
                "proposed_overrides": proposed_overrides
            }
            
            with open(report_path, 'w') as f:
                json.dump(report_content, f, indent=2)
            
            logger.info(f"✅ [Weekly Analyst] Longitudinal report saved to {report_path}")
            return report_content
            
        except Exception as e:
            logger.error(f"❌ [Weekly Analyst] Error generating report for {pm_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e)}

    def _gather_pm_data(self, pm_id: str) -> dict:
        """
        Extracts weekly and lifetime performance data.
        """
        portfolio = portfolio_manager.get_portfolio(pm_id)
        if not portfolio: return None
        portfolio.load_portfolio()
        
        status = portfolio.get_status()
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        # --- 1. Lifetime Data ---
        ledger = portfolio.data.get("ledger", [])
        trade_log = portfolio.data.get("trade_log", [])
        
        lt_wins = [e for e in ledger if e.get("type") == "REALIZED_PNL" and e.get("amount", 0) > 0]
        lt_losses = [e for e in ledger if e.get("type") == "REALIZED_PNL" and e.get("amount", 0) < 0]
        
        total_realized_pnl = sum([e.get("amount", 0) for e in ledger if e.get("type") == "REALIZED_PNL"])
        
        lifetime_summary = {
            "initial_capital": portfolio.data.get("initial_capital", 0),
            "current_value": status.get("total_value", 0),
            "total_realized_pnl": total_realized_pnl,
            "win_rate": len(lt_wins) / (len(lt_wins) + len(lt_losses)) if (len(lt_wins) + len(lt_losses)) > 0 else 0,
            "total_trades": len([e for e in ledger if e.get("type") in ["TRADE_COST", "TRADE_PROCEEDS"]]),
            "avg_win": sum([e.get("amount", 0) for e in lt_wins]) / len(lt_wins) if lt_wins else 0,
            "avg_loss": sum([e.get("amount", 0) for e in lt_losses]) / len(lt_losses) if lt_losses else 0,
        }

        # --- 2. Weekly Data ---
        weekly_ledger = []
        w_wins = []
        w_losses = []
        for e in ledger:
            try:
                if datetime.fromisoformat(e.get("timestamp")[:19]) >= seven_days_ago:
                    weekly_ledger.append(e)
                    if e.get("type") == "REALIZED_PNL":
                        if e.get("amount", 0) > 0: w_wins.append(e)
                        else: w_losses.append(e)
            except: continue

        weekly_log = []
        for e in trade_log:
            try:
                if datetime.fromisoformat(e.get("timestamp")[:19]) >= seven_days_ago:
                    weekly_log.append(e)
            except: continue
        
        # Weekly performance
        history = portfolio.data.get("history", [])
        start_val = 0
        for h in history:
            try:
                if datetime.fromisoformat(h.get("timestamp")[:19]) >= seven_days_ago:
                    start_val = h.get("total_value", 0)
                    break
            except: continue
        if not start_val and history: start_val = history[0].get("total_value", 0)
        
        weekly_summary = {
            "pnl_percentage": (status.get("total_value", 0) - start_val) / start_val if start_val > 0 else 0,
            "wins": len(w_wins),
            "losses": len(w_losses),
            "trades_count": len([e for e in weekly_ledger if e.get("type") in ["TRADE_COST", "TRADE_PROCEEDS"]])
        }

        return {
            "weekly_summary": weekly_summary,
            "lifetime_summary": lifetime_summary,
            "weekly_ledger": weekly_ledger,
            "weekly_log": weekly_log,
            "current_positions": status.get("positions", {})
        }

    def _construct_prompt(self, pm_id: str, pm_data: dict, strategy_mandate: str) -> str:
        w_sum = pm_data["weekly_summary"]
        l_sum = pm_data["lifetime_summary"]
        
        # Calculate simple profit factor
        gross_profit = l_sum["avg_win"] * (l_sum["total_trades"] * l_sum["win_rate"])
        gross_loss = abs(l_sum["avg_loss"] * (l_sum["total_trades"] * (1 - l_sum["win_rate"])))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Format recent activity
        activity = []
        for e in pm_data["weekly_ledger"]:
            ts = e.get('timestamp', '')[:16].replace('T', ' ')
            activity.append(f"[{ts}] LEDGER {e.get('type')}: {e.get('ticker')} | ${e.get('amount', 0):.2f} | {e.get('description')}")
        for e in pm_data["weekly_log"]:
            ts = e.get('timestamp', '')[:16].replace('T', ' ')
            activity.append(f"[{ts}] ACTION {e.get('action')}: {e.get('ticker')} | {e.get('qty', 0):.4f} @ ${e.get('price', 0):.2f}")
        
        activity.sort()
        activity_text = "\n".join(activity)

        # Format Active Overrides Performance
        overrides_perf = "None active."
        portfolio = portfolio_manager.get_portfolio(pm_id)
        active = portfolio.get_active_learnings()
        if active:
            lines = []
            for l in active:
                lines.append(f"- {l['parameter']}: {l.get('performance_since', 0):+.2%} P&L across {l.get('trades_count_since', 0)} trades (ID: {l['id']})")
            overrides_perf = "\n".join(lines)

        audit_text = "No automatic changes this week."
        if pm_data.get("audit_results"):
            audit_text = "\n".join([f"- {r['id']}: {r['action']} - Reason: {r['reason']}" for r in pm_data["audit_results"]])

        prompt = f"""
ROLE: Lead Quantitative Strategist & Performance Auditor.
TASK: Comprehensive Longitudinal Analysis for Portfolio Manager {pm_id}.

===========================================
▶ STRATEGY MANDATE:
{strategy_mandate}

===========================================
▶ LIFETIME PERFORMANCE (Inception to Now):
- Total Return: ${l_sum['current_value'] - l_sum['initial_capital']:.2f}
- Realized Win Rate: {l_sum['win_rate']:.1%} ({l_sum['total_trades']} total trade actions)
- Avg Win: ${l_sum['avg_win']:.2f} | Avg Loss: ${l_sum['avg_loss']:.2f}
- Profit Factor: {profit_factor:.2f}

▶ WEEKLY PERFORMANCE (Last 7 Days):
- Weekly Return: {w_sum['pnl_percentage']:.2%}
- Weekly Outcome: {w_sum['wins']} Wins / {w_sum['losses']} Losses

▶ ACTIVE OVERRIDES PERFORMANCE:
{overrides_perf}

▶ CYBERNETIC AUDITOR DECISIONS (AUTOPILOT):
{audit_text}

▶ RAW ACTIVITY LOG (Last 7 Days):
{activity_text}

===========================================
▶ ANALYSIS REQUIREMENTS:

1. **Longitudinal Trend Analysis**: 
   - Compare this week's performance against lifetime averages. 
   - Is the "Structural Edge" expanding or decaying? Cite specific realized P&L numbers.

2. **Cybernetic Audit Review**:
   - Review any "Auditor Decisions" (Auto-Reverts/Graduations) above.
   - For currently active overrides, provide a mid-test verdict: Keep testing, or manually Revert/Graduate now?

3. **Numerical Root Cause Analysis**:
   - Analyze realized outcomes. Use the ledger values to prove your points.

4. **Data-Driven Logic Improvements (CRITICAL)**:
   - Proposals MUST be fundamented in numbers.
   - Suggest 1-3 specific prompt/parameter changes wrapped in [JSON] tags.

5. **Executive Summary**:
   - 3-sentence summary. Must include one specific lifetime metric and one weekly metric.

===========================================
OUTPUT FORMAT (CRITICAL):
1. First, provide the full Markdown report.
2. At the VERY END, provide a SINGLE JSON block containing any proposed overrides.
   - Each override MUST include: parameter, action, old_value, new_value, evidence_trades, and reasoning.
   - You MUST wrap the JSON in [JSON] and [/JSON] tags.
   - Example: [JSON] {{ "overrides": [ {{ "parameter": "...", "action": "...", ... }} ] }} [/JSON]
===========================================
"""
        return prompt

    def _parse_llm_response(self, raw_response: str) -> tuple:
        """Parses the LLM response into Markdown and a structured JSON block."""
        # Look for [JSON] ... [/JSON] block
        json_match = re.search(r"\[JSON\]\s*(.*?)\s*\[/JSON\]", raw_response, re.DOTALL)
        proposed_overrides = []
        
        if json_match:
            try:
                json_str = json_match.group(1).strip()
                data = json.loads(json_str)
                proposed_overrides = data.get("overrides", [])
                
                # Strip JSON from markdown
                markdown = raw_response.replace(json_match.group(0), "").strip()
                return markdown, proposed_overrides
            except Exception as e:
                logger.error(f"Failed to parse LLM JSON: {e}")
        
        # Fallback if no block found or parse error
        return raw_response, []

    def get_all_reports(self, pm_id: str) -> list:
        reports = []
        if not os.path.exists(REPORTS_DIR): return []
        for filename in os.listdir(REPORTS_DIR):
            if filename.startswith(f"report_{pm_id}_") and filename.endswith(".json"):
                try:
                    with open(os.path.join(REPORTS_DIR, filename), 'r') as f:
                        reports.append(json.load(f))
                except: continue
        reports.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return reports

    def get_report(self, pm_id: str, report_id: str) -> dict:
        filename = f"report_{pm_id}_{report_id}.json"
        path = os.path.join(REPORTS_DIR, filename)
        if os.path.exists(path):
            with open(path, 'r') as f: return json.load(f)
        return None

weekly_analyst = WeeklyAnalystService()
