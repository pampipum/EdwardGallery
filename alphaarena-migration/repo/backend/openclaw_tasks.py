import argparse
import json
import os
from pathlib import Path

from backend.runtime import config_path, paper_only_mode, state_dir
from backend.services.data.config_service import get_top_tickers
from backend.services.market_service import get_current_prices
from backend.services.pm_strategies import get_strategy
from backend.services.portfolio_service import portfolio_manager
from backend.services.trading_loop import run_market_analysis, run_risk_check
from backend.services.weekly_analyst import weekly_analyst


def active_pm_ids():
    return ["pm1", "pm2", "pm3", "pm4", "pm5", "pm6"]


def cmd_healthcheck(_: argparse.Namespace) -> int:
    assets = get_top_tickers()
    summary = {
        "paper_only_mode": paper_only_mode(),
        "config_path": str(config_path()),
        "state_root": str(Path(state_dir()).resolve()),
        "assets": {
            "stocks": len(assets.get("stocks", [])),
            "crypto": len(assets.get("crypto", [])),
        },
        "env": {
            "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
            "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY")),
            "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
            "ALPHA_VANTAGE_API_KEY": bool(os.getenv("ALPHA_VANTAGE_API_KEY")),
            "FMP_API_KEY": bool(os.getenv("FMP_API_KEY")),
            "CMC_API_KEY": bool(os.getenv("CMC_API_KEY")),
            "MASSIVE_API_KEY": bool(os.getenv("MASSIVE_API_KEY")),
        },
        "paths": {
            "portfolios": str(state_dir("portfolios")),
            "reports": str(state_dir("reports")),
            "cache": str(state_dir("cache")),
            "logs": str(state_dir("logs")),
        },
    }
    print(json.dumps(summary, indent=2))
    return 0


def cmd_fetch_prices(_: argparse.Namespace) -> int:
    assets = get_top_tickers()
    tickers = assets.get("stocks", []) + assets.get("crypto", [])
    prices = get_current_prices(tickers)
    print(json.dumps({"count": len(prices), "prices": prices}, indent=2))
    return 0


def cmd_start_paper(args: argparse.Namespace) -> int:
    portfolio = portfolio_manager.get_portfolio(args.pm_id)
    result = portfolio.start_portfolio(args.capital)
    print(json.dumps(result, indent=2))
    return 0


def cmd_analyze_pm(args: argparse.Namespace) -> int:
    run_market_analysis(args.pm_id)
    strategy = get_strategy(args.pm_id)
    status = portfolio_manager.get_portfolio(args.pm_id).get_status()
    print(json.dumps({
        "pm_id": args.pm_id,
        "strategy": strategy.name,
        "positions": list(status.get("positions", {}).keys()),
        "analysis_items": len(status.get("latest_analysis", [])),
        "total_value": status.get("total_value"),
    }, indent=2))
    return 0


def cmd_risk_check(args: argparse.Namespace) -> int:
    strategy = get_strategy(args.pm_id)
    run_risk_check(args.pm_id, strategy)
    status = portfolio_manager.get_portfolio(args.pm_id).get_status()
    print(json.dumps({
        "pm_id": args.pm_id,
        "positions": list(status.get("positions", {}).keys()),
        "total_value": status.get("total_value"),
    }, indent=2))
    return 0


def cmd_weekly_report(args: argparse.Namespace) -> int:
    result = weekly_analyst.generate_weekly_report(args.pm_id)
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenClaw task entrypoints for AlphaArena.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    healthcheck = subparsers.add_parser("healthcheck")
    healthcheck.set_defaults(func=cmd_healthcheck)

    fetch_prices = subparsers.add_parser("fetch-prices")
    fetch_prices.set_defaults(func=cmd_fetch_prices)

    start_paper = subparsers.add_parser("start-paper")
    start_paper.add_argument("--pm-id", default="pm1", choices=active_pm_ids())
    start_paper.add_argument("--capital", type=float, default=10000.0)
    start_paper.set_defaults(func=cmd_start_paper)

    analyze_pm = subparsers.add_parser("analyze-pm")
    analyze_pm.add_argument("--pm-id", default="pm1", choices=active_pm_ids())
    analyze_pm.set_defaults(func=cmd_analyze_pm)

    risk_check = subparsers.add_parser("risk-check")
    risk_check.add_argument("--pm-id", default="pm1", choices=active_pm_ids())
    risk_check.set_defaults(func=cmd_risk_check)

    weekly_report = subparsers.add_parser("weekly-report")
    weekly_report.add_argument("--pm-id", default="pm1", choices=active_pm_ids())
    weekly_report.set_defaults(func=cmd_weekly_report)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
