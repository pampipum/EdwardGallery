"""
Butler Signal Service

Provides an interface for PM6 to consume Morning Butler briefing data.
Parses the daily briefing JSON and returns structured tradeable signals.
"""
import os
import json
from datetime import datetime, timedelta
from backend.utils.logger import logger
from backend.runtime import state_dir


class ButlerSignalService:
    """
    Parses Morning Butler briefings into tradeable signals for PM6.
    Reads from the daily_briefing.json file saved by MorningButlerService.
    """
    
    def __init__(self):
        self.briefing_file = str(state_dir("briefings") / "daily_briefing.json")
        self._cached_briefing = None
        self._cache_timestamp = None
        self._cache_duration = 300  # 5 minutes
    
    def _load_briefing(self) -> dict:
        """Load the latest briefing from disk with caching."""
        now = datetime.now()
        
        # Use cache if fresh
        if (self._cached_briefing and self._cache_timestamp and 
            (now - self._cache_timestamp).total_seconds() < self._cache_duration):
            return self._cached_briefing
        
        if not os.path.exists(self.briefing_file):
            logger.warning("No Morning Butler briefing file found")
            return {}
        
        try:
            with open(self.briefing_file, 'r') as f:
                self._cached_briefing = json.load(f)
                self._cache_timestamp = now
                return self._cached_briefing
        except Exception as e:
            logger.error(f"Error loading Butler briefing: {e}")
            return {}
    
    def get_briefing_age_hours(self) -> float:
        """Returns how many hours old the briefing is."""
        briefing = self._load_briefing()
        if not briefing or 'generated_at' not in briefing:
            return float('inf')
        
        try:
            generated_at = datetime.fromisoformat(briefing['generated_at'])
            age = datetime.now() - generated_at
            return age.total_seconds() / 3600
        except:
            return float('inf')
    
    def is_briefing_fresh(self, max_age_hours: float = 18) -> bool:
        """Check if the briefing is fresh enough to trade on."""
        return self.get_briefing_age_hours() < max_age_hours
    
    def get_todays_signals(self) -> list:
        """
        Returns tradeable opportunities from the latest Butler briefing.
        
        Returns:
            List of dicts with structure:
            {
                'symbol': 'WVE',
                'signal_strength': 'High',
                'entry_zone': '18.50 - 18.60',
                'stop_zone': 'below SMA20 at 8.35',
                'targets': 'T1: 21.60, T2: 24.00',
                'breakout_level': '19.75',
                'timeframe': 'swing',
                'thesis': 'Wave Life Sciences surges on positive interim data...',
                'risks': ['Overbought risk...', 'Low RVOL...']
            }
        """
        briefing = self._load_briefing()
        
        if not briefing:
            logger.info("No Butler briefing available")
            return []
        
        # Check freshness
        if not self.is_briefing_fresh():
            logger.warning(f"Butler briefing is stale ({self.get_briefing_age_hours():.1f}h old)")
            return []
        
        opportunities = briefing.get('top_opportunities', [])
        
        signals = []
        for opp in opportunities:
            action_plan = opp.get('action_plan', {})
            
            signal = {
                'symbol': opp.get('symbol', ''),
                'signal_strength': opp.get('signal_strength', 'Medium'),
                'entry_zone': action_plan.get('entry_zone', ''),
                'stop_zone': action_plan.get('stop_zone', ''),
                'targets': action_plan.get('profit_targets', ''),
                'breakout_level': action_plan.get('breakout_level', ''),
                'timeframe': opp.get('timeframe', 'swing'),
                'thesis': opp.get('why_it_matters', opp.get('headline', '')),
                'risks': opp.get('risks', [])
            }
            
            # Only include signals with valid symbols
            if signal['symbol']:
                signals.append(signal)
        
        logger.info(f"Butler signals loaded: {len(signals)} opportunities")
        return signals
    
    def get_signal_for_ticker(self, ticker: str) -> dict:
        """
        Get specific signal data for a ticker if it exists in today's briefing.
        
        Returns empty dict if ticker not in briefing.
        """
        signals = self.get_todays_signals()
        
        # Strip -USD suffix if present for comparison
        clean_ticker = ticker.replace('-USD', '')
        
        for signal in signals:
            if signal['symbol'].upper() == clean_ticker.upper():
                return signal
        
        return {}
    
    def get_high_priority_tickers(self) -> list:
        """Returns list of tickers with High signal strength."""
        signals = self.get_todays_signals()
        return [s['symbol'] for s in signals if s.get('signal_strength') == 'High']
    
    def get_market_temperature(self) -> dict:
        """Returns the market temperature from the briefing."""
        briefing = self._load_briefing()
        return briefing.get('market_temperature', {})
    
    def get_gameplan(self) -> dict:
        """Returns the gameplan from the briefing."""
        briefing = self._load_briefing()
        return briefing.get('gameplan', {})
    
    def should_trade_today(self) -> bool:
        """
        Determines if PM6 should actively trade today based on market conditions.
        
        Uses market temperature to decide:
        - Risk Appetite < 2: Skip trading (too risky)
        - No fresh briefing: Skip trading
        """
        if not self.is_briefing_fresh():
            return False
        
        temp = self.get_market_temperature()
        risk_appetite = temp.get('risk_appetite', 3)
        
        # If risk appetite is too low, skip
        if risk_appetite < 2:
            logger.info("Butler says: Risk appetite too low, skipping trades today")
            return False
        
        return True


# Global instance
butler_signal_service = ButlerSignalService()
