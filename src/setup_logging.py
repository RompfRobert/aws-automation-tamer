import logging
import logging.handlers
import os
import sys
import getpass
import socket
import json
from pathlib import Path
from typing import Optional

class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured logs with audit information."""
    
    def format(self, record):
        # Get user information
        username = self._get_username()
        
        # Create structured log entry
        log_entry = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'user': username,
            'hostname': socket.gethostname(),
            'process_id': os.getpid(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage()
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add any extra fields from LogRecord
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'exc_info', 'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry)
    
    def _get_username(self) -> str:
        """Get the current username with proper fallbacks."""
        # Check for the original user if using sudo
        username = (os.environ.get("SUDO_USER") or 
                   os.environ.get("USER") or 
                   os.environ.get("USERNAME") or 
                   os.environ.get("LOGNAME"))
        
        if not username:
            try:
                username = getpass.getuser()
            except Exception:
                username = "unknown"
        
        return username

class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter for console output."""
    
    def __init__(self):
        self.username = self._get_username()
        super().__init__(
            fmt=f"%(asctime)s - %(levelname)s - {self.username} - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    def _get_username(self) -> str:
        """Get the current username with proper fallbacks."""
        username = (os.environ.get("SUDO_USER") or 
                   os.environ.get("USER") or 
                   os.environ.get("USERNAME") or 
                   os.environ.get("LOGNAME"))
        
        if not username:
            try:
                username = getpass.getuser()
            except Exception:
                username = "unknown"
        
        return username

def setup_logging(log_level: Optional[str] = None, log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up comprehensive logging configuration for CLI automation tool.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Custom log file path (optional)
    
    Returns:
        Configured logger instance
    """
    
    # Determine log level
    if log_level:
        level = getattr(logging, log_level.upper(), logging.INFO)
    else:
        # Check environment variable for log level
        env_level = os.environ.get('AWS_AUTOMATION_LOG_LEVEL', 'INFO')
        level = getattr(logging, env_level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger('aws-automation-tamer')
    logger.setLevel(level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Console handler with human-readable format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)
    
    # File handler with structured logging and rotation
    log_dir = Path.home() / '.aws-automation-tamer' / 'logs'
    if log_file:
        log_path = Path(log_file)
    else:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'aws-automation-tamer.log'
    
    # Rotating file handler (10MB per file, keep 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)  # Always log INFO and above to file
    file_handler.setFormatter(StructuredFormatter())
    logger.addHandler(file_handler)
    
    # System log handler (for production environments)
    try:
        # On macOS, use syslog
        if sys.platform == 'darwin':
            syslog_handler = logging.handlers.SysLogHandler(address='/var/run/syslog')
            syslog_handler.setLevel(logging.WARNING)  # Only warnings and errors to syslog
            syslog_handler.setFormatter(ConsoleFormatter())
            logger.addHandler(syslog_handler)
        # On Linux, try to use journald if available, fallback to syslog
        elif sys.platform.startswith('linux'):
            try:
                from systemd import journal
                syslog_handler = journal.JournalHandler()
                syslog_handler.setLevel(logging.WARNING)
                syslog_handler.setFormatter(ConsoleFormatter())
                logger.addHandler(syslog_handler)
            except ImportError:
                # Fallback to regular syslog
                syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
                syslog_handler.setLevel(logging.WARNING)
                syslog_handler.setFormatter(ConsoleFormatter())
                logger.addHandler(syslog_handler)
    except Exception as e:
        # If system logging fails, just continue with file and console logging
        logger.warning(f"Could not set up system logging: {e}")
    
    # Configure third-party loggers
    logging.getLogger("botocore.credentials").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # Log startup information
    logger.info("AWS Automation Tamer started", extra={
        'action': 'startup',
        'version': _get_version(),
        'python_version': sys.version,
        'platform': sys.platform
    })
    
    return logger

def _get_version() -> str:
    """Get the application version."""
    try:
        # Try to read from setup.py or version file
        setup_py = Path(__file__).parent.parent / 'setup.py'
        if setup_py.exists():
            with open(setup_py, 'r') as f:
                content = f.read()
                import re
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
    except Exception:
        pass
    return "unknown"

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance for the specified module.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f'aws-automation-tamer.{name}')
    return logging.getLogger('aws-automation-tamer')

def log_command_execution(command: str, **kwargs):
    """
    Log command execution with audit trail.
    
    Args:
        command: The command being executed
        **kwargs: Additional context (account, region, resource_ids, etc.)
    """
    logger = get_logger('audit')
    logger.info(f"Executing command: {command}", extra={
        'action': 'command_execution',
        'command': command,
        **kwargs
    })

def log_aws_api_call(service: str, operation: str, **kwargs):
    """
    Log AWS API calls for audit purposes.
    
    Args:
        service: AWS service name (ec2, rds, etc.)
        operation: API operation name
        **kwargs: Additional context
    """
    logger = get_logger('audit')
    logger.info(f"AWS API call: {service}.{operation}", extra={
        'action': 'aws_api_call',
        'service': service,
        'operation': operation,
        **kwargs
    })