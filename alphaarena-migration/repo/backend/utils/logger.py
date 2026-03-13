import logging
import os
from logging.handlers import RotatingFileHandler
import sys
from backend.runtime import state_dir

def setup_logger(name: str = "app", log_file: str = "app.log", level=logging.INFO):
    """
    Sets up a logger with both file and console handlers.
    
    Args:
        name: Name of the logger
        log_file: Filename for the log (will be placed in 'logs' directory)
        level: Logging level
    """
    # Create logs directory if it doesn't exist
    log_dir = str(state_dir("logs"))
        
    log_path = os.path.join(log_dir, log_file)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times if logger is already configured
    if logger.handlers:
        return logger
        
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File Handler (Rotating)
    # Max size 10MB, keep 5 backups
    file_handler = RotatingFileHandler(
        log_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create a default logger instance
logger = setup_logger()
