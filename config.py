import os
from typing import Optional

class Config:
    """Configuration class for the autonomous coding agent."""
    
    # AI Model Configuration
    MODEL_TYPE: str = os.getenv('MODEL_TYPE', 'ollama')  # ollama, gpt4all, openai
    MODEL_NAME: str = os.getenv('MODEL_NAME', 'codellama:7b-instruct')
    OLLAMA_BASE_URL: str = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    GPT4ALL_MODEL_PATH: str = os.getenv('GPT4ALL_MODEL_PATH', './models/gpt4all-model.bin')
    
    # Worker Configuration
    WORKER_COUNT: int = int(os.getenv('WORKER_COUNT', '3'))
    MAX_RETRIES: int = int(os.getenv('MAX_RETRIES', '3'))
    TASK_TIMEOUT: int = int(os.getenv('TASK_TIMEOUT', '300'))
    
    # Flask Server Configuration
    FLASK_HOST: str = os.getenv('FLASK_HOST', '127.0.0.1')
    FLASK_PORT: int = int(os.getenv('FLASK_PORT', '5000'))
    FLASK_DEBUG: bool = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Database Configuration
    DB_PATH: str = os.getenv('DB_PATH', './db/agent_logs.sqlite')
    
    # Git Configuration
    GIT_BRANCH: str = os.getenv('GIT_BRANCH', 'main')
    GIT_AUTO_PUSH: bool = os.getenv('GIT_AUTO_PUSH', 'True').lower() == 'true'
    GITHUB_USERNAME: Optional[str] = os.getenv('GITHUB_USERNAME')
    GITHUB_TOKEN: Optional[str] = os.getenv('GITHUB_TOKEN')
    
    # Checkpoint Configuration
    CHECKPOINT_DAYS: int = int(os.getenv('CHECKPOINT_DAYS', '7'))
    STATE_SAVE_INTERVAL: int = int(os.getenv('STATE_SAVE_INTERVAL', '3600'))  # 1 hour
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    MAX_LOG_ENTRIES: int = int(os.getenv('MAX_LOG_ENTRIES', '10000'))
    
    # Tireless Reviewer Configuration (24/7 Code Quality Guardian)
    TIRELESS_REVIEWER_WORKERS: int = int(os.getenv('TIRELESS_REVIEWER_WORKERS', '2'))
    REVIEW_INTERVAL: int = int(os.getenv('REVIEW_INTERVAL', '300'))  # 5 minutes
    DEEP_REVIEW_INTERVAL: int = int(os.getenv('DEEP_REVIEW_INTERVAL', '1800'))  # 30 minutes
    TIRELESS_REVIEWER_ENABLED: bool = os.getenv('TIRELESS_REVIEWER_ENABLED', 'True').lower() == 'true'
    CREATE_FOLLOWUP_TASKS: bool = os.getenv('CREATE_FOLLOWUP_TASKS', 'True').lower() == 'true'
    MAJOR_TASK_GRACE_PERIOD_DAYS: int = int(os.getenv('MAJOR_TASK_GRACE_PERIOD_DAYS', '7'))
    
    # Repository Management Configuration
    REPOS_BASE_DIR: str = os.getenv('REPOS_BASE_DIR', './connected_repositories')
    MAX_CONNECTED_REPOS: int = int(os.getenv('MAX_CONNECTED_REPOS', '10'))
    AUTO_PULL_UPDATES: bool = os.getenv('AUTO_PULL_UPDATES', 'False').lower() == 'true'
    AUTO_SCAN_REPOS: bool = os.getenv('AUTO_SCAN_REPOS', 'True').lower() == 'true'

# Global config instance
config = Config() 