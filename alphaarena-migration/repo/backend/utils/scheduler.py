from datetime import datetime, time, timedelta
import pytz

# US Eastern Time Zone
ET_TIMEZONE = pytz.timezone('US/Eastern')

# Scheduled Times (ET)
MORNING_RUN_TIME = time(9, 40)  # 10 mins after open (09:30)
AFTERNOON_RUN_TIME = time(15, 45) # 15 mins before close (16:00)

def get_next_scheduled_run_time(current_dt: datetime = None) -> datetime:
    """
    Calculates the next scheduled run time (09:40 ET or 15:45 ET).
    Returns a datetime object in the local system timezone (or whatever timezone current_dt is in).
    """
    if current_dt is None:
        current_dt = datetime.now(pytz.utc) # Default to UTC if not provided
        
    # Convert current time to ET for calculation
    current_et = current_dt.astimezone(ET_TIMEZONE)
    
    # Candidates for today
    today_morning = current_et.replace(hour=MORNING_RUN_TIME.hour, minute=MORNING_RUN_TIME.minute, second=0, microsecond=0)
    today_afternoon = current_et.replace(hour=AFTERNOON_RUN_TIME.hour, minute=AFTERNOON_RUN_TIME.minute, second=0, microsecond=0)
    
    candidates = []
    
    if today_morning > current_et:
        candidates.append(today_morning)
        
    if today_afternoon > current_et:
        candidates.append(today_afternoon)
        
    # If no candidates today, add tomorrow's morning run
    if not candidates:
        tomorrow = current_et + timedelta(days=1)
        tomorrow_morning = tomorrow.replace(hour=MORNING_RUN_TIME.hour, minute=MORNING_RUN_TIME.minute, second=0, microsecond=0)
        candidates.append(tomorrow_morning)
        
    # Return the earliest candidate converted back to the original timezone (or UTC if input was naive/UTC)
    next_run_et = min(candidates)
    
    return next_run_et

def is_market_open_day(dt: datetime) -> bool:
    """
    Checks if the given date is a weekday (Mon-Fri).
    Does not account for holidays for simplicity, as requested.
    """
    # 0 = Monday, 4 = Friday, 5 = Saturday, 6 = Sunday
    return dt.weekday() < 5


def get_market_status() -> dict:
    """
    Returns the current US stock market status.
    Includes status (open/closed/pre-market/after-hours), label, and color.
    
    Market Hours (Eastern Time):
    - Pre-Market: 4:00 AM - 9:30 AM
    - Regular: 9:30 AM - 4:00 PM
    - After-Hours: 4:00 PM - 8:00 PM
    - Closed: 8:00 PM - 4:00 AM (and weekends)
    """
    now_et = datetime.now(ET_TIMEZONE)
    current_time = now_et.time()
    is_weekday = now_et.weekday() < 5
    
    # Define market hours
    pre_market_start = time(4, 0)
    market_open = time(9, 30)
    market_close = time(16, 0)
    after_hours_end = time(20, 0)
    
    if not is_weekday:
        return {
            "status": "closed",
            "label": "WEEKEND",
            "color": "gray"
        }
    
    if current_time < pre_market_start:
        return {
            "status": "closed",
            "label": "CLOSED",
            "color": "gray"
        }
    elif current_time < market_open:
        return {
            "status": "pre-market",
            "label": "PRE-MARKET",
            "color": "yellow"
        }
    elif current_time < market_close:
        return {
            "status": "open",
            "label": "OPEN",
            "color": "green"
        }
    elif current_time < after_hours_end:
        return {
            "status": "after-hours",
            "label": "AFTER-HOURS",
            "color": "yellow"
        }
    else:
        return {
            "status": "closed",
            "label": "CLOSED",
            "color": "gray"
        }
