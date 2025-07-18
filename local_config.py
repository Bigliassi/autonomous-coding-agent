"""
Local Configuration for Autonomous Coding Agent
This file configures the agent to use both Ollama (primary) and OpenAI (fallback)
"""

import os

# Override config settings for local setup
class LocalConfig:
    """Local configuration overrides."""
    
    # AI Model Configuration - Use Ollama with memory-efficient model
    MODEL_TYPE = "ollama"  # Primary: Use Ollama (local, private, free)
    MODEL_NAME = "phi3:3.8b"  # Memory-efficient model that works on your system
    OLLAMA_BASE_URL = "http://localhost:11434"
    
    # OpenAI as fallback (requires API key)
    OPENAI_API_KEY = "your_openai_api_key_here"  # Replace with your actual key
    
    # Worker Configuration - Conservative for limited RAM
    WORKER_COUNT = 2  # Reduced for memory constraints
    MAX_RETRIES = 3
    TASK_TIMEOUT = 300
    
    # Flask Server
    FLASK_HOST = "127.0.0.1"
    FLASK_PORT = 5000
    FLASK_DEBUG = False
    
    # Git Configuration  
    GIT_BRANCH = "master"  # Using master branch as created
    GIT_AUTO_PUSH = True  # Enable auto-push to GitHub
    GITHUB_USERNAME = "Bigliassi"  # Your GitHub username
    GITHUB_TOKEN = "your_github_token"  # Replace with your Personal Access Token
    
    # System Performance
    CHECKPOINT_DAYS = 7
    STATE_SAVE_INTERVAL = 3600
    LOG_LEVEL = "INFO"

# Apply local configuration
def apply_local_config():
    """Apply local configuration to environment variables."""
    for key, value in LocalConfig.__dict__.items():
        if not key.startswith('_') and isinstance(value, (str, int, bool)):
            os.environ[key] = str(value)

# Auto-apply when imported
apply_local_config()

print("🔧 Local configuration loaded:")
print(f"   Primary Model: {LocalConfig.MODEL_TYPE} ({LocalConfig.MODEL_NAME})")
print(f"   Workers: {LocalConfig.WORKER_COUNT}")
print(f"   Auto-push: {'Enabled' if LocalConfig.GIT_AUTO_PUSH else 'Disabled'}") 