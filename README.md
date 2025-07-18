# 🤖 Autonomous Coding Agent

A sophisticated AI-powered coding assistant that operates continuously on your local machine, automatically generating code, running tests, and committing changes to Git. The agent maintains multiple parallel workers, provides a web dashboard for monitoring, and includes comprehensive logging and crash recovery features.

## ✨ Features

### 🔄 Continuous Operation
- **Parallel Workers**: Configurable number of asyncio worker coroutines
- **Never Idle**: Automatically pulls tasks from a persistent queue
- **Crash Recovery**: Hourly state saves and automatic restoration
- **Weekly Checkpoints**: Automated pause with comprehensive reports

### 📝 Task Management
- **Multiple Input Methods**: Flask API, CLI, and file watcher
- **Priority Queues**: Tasks can be prioritized for urgent work
- **Retry Logic**: Failed tasks automatically retry with backoff
- **Persistent Storage**: SQLite-backed queue survives restarts

### 🧠 AI Integration
- **Multi-Model Support**: Ollama, OpenAI API, and GPT4All
- **Graceful Fallbacks**: Automatic switching between available models
- **Performance Tracking**: Token usage and response time monitoring

### 🧪 Testing & Quality
- **Automatic Testing**: pytest integration with every code generation
- **Syntax Validation**: Pre-test syntax checking
- **Test Generation**: Creates basic tests when none provided

### 📦 Git Integration
- **Automatic Commits**: Every successful task becomes a commit
- **Granular History**: Each task is individually tracked
- **Auto-push**: Optional automatic pushing to remote repositories

### 🌐 Web Dashboard
- **Real-time Monitoring**: Live worker status and queue metrics
- **Interactive Control**: Pause/resume, task injection
- **Log Streaming**: Server-sent events for live log updates
- **Settings Management**: Configure models, workers, and Git

### 📊 Reporting & Analytics
- **Weekly Summaries**: Comprehensive markdown reports
- **Performance Metrics**: Success rates, throughput analysis
- **Error Analysis**: Common failure patterns and suggestions

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Git installed and configured
- At least one AI model backend (see [AI Model Setup](#ai-model-setup))

### Installation

1. **Clone and setup**:
```bash
git clone <your-repo-url>
cd autonomous-coding-agent
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
# Copy and edit configuration
cp config.py config_local.py  # Optional: for local overrides

# Set environment variables (optional, defaults in config.py)
export MODEL_TYPE=ollama
export MODEL_NAME=codellama:7b-instruct
export WORKER_COUNT=3
```

3. **Initialize and run**:
```bash
# Start the agent
python main.py
```

4. **Access the dashboard**:
   - Open http://127.0.0.1:5000 in your browser
   - View logs at http://127.0.0.1:5000/logs
   - Configure settings at http://127.0.0.1:5000/settings

## 🔧 Configuration

### AI Model Setup

#### Ollama (Recommended for Local)
```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull a coding model
ollama pull codellama:7b-instruct

# Configure agent
export MODEL_TYPE=ollama
export MODEL_NAME=codellama:7b-instruct
export OLLAMA_BASE_URL=http://localhost:11434
```

#### OpenAI API
```bash
# Configure agent
export MODEL_TYPE=openai
export OPENAI_API_KEY=your_api_key_here
```

#### GPT4All (Local)
```bash
# Download model file
# Configure path
export MODEL_TYPE=gpt4all
export GPT4ALL_MODEL_PATH=./models/your-model.bin
```

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKER_COUNT` | 3 | Number of parallel workers |
| `MAX_RETRIES` | 3 | Task retry attempts |
| `TASK_TIMEOUT` | 300 | Max seconds per task |
| `FLASK_PORT` | 5000 | Web dashboard port |
| `GIT_AUTO_PUSH` | True | Auto-push to remote |
| `CHECKPOINT_DAYS` | 7 | Days between checkpoints |

## 💼 Usage

### Adding Tasks

#### 1. Web Dashboard
Navigate to http://127.0.0.1:5000 and use the task form.

#### 2. Command Line
```bash
# Simple task
python cli.py "Create a FastAPI health check endpoint"

# High priority task
python cli.py --priority 5 "Fix critical authentication bug"

# Check status
python cli.py --status

# View logs
python cli.py --logs 50
```

#### 3. File Watcher (tasks.yaml)
```yaml
tasks:
  - description: "Create a user registration API with email validation"
    priority: 2
    metadata:
      category: "api"
  
  - description: "Add unit tests for the payment processing module"
    priority: 1
```

#### 4. API Endpoint
```bash
# JSON task
curl -X POST http://127.0.0.1:5000/api/task \
  -H "Content-Type: application/json" \
  -d '{"description": "Optimize database queries", "priority": 3}'

# Plain text task
curl -X POST http://127.0.0.1:5000/api/task \
  -H "Content-Type: text/plain" \
  -d "Create a data validation utility"
```

### Managing the Agent

#### CLI Commands
```bash
# Control
python cli.py --pause    # Pause workers
python cli.py --resume   # Resume workers

# Monitoring
python cli.py --status   # Show system status
python cli.py --logs 100 # Show recent logs

# Task management
python cli.py --load-tasks tasks.yaml  # Load tasks from file
```

#### Web Dashboard
- **Real-time Monitoring**: Worker status, queue size, model availability
- **Interactive Control**: Pause/resume buttons, worker restart
- **Settings**: Change model, worker count, timeouts
- **Logs**: Live streaming logs with filtering

### Weekly Checkpoints

Every 7 days (configurable), the agent automatically:
1. **Pauses** all workers
2. **Generates** a comprehensive markdown report
3. **Waits** for manual resume confirmation
4. **Continues** operation after approval

Resume via:
- Web dashboard "Resume" button
- CLI: `python cli.py --resume`

## 📁 Project Structure

```
autonomous-coding-agent/
├── main.py                 # Main application entry point
├── cli.py                  # Command-line interface
├── config.py               # Configuration management
├── requirements.txt        # Python dependencies
├── tasks.yaml             # Task definitions (watched for changes)
├── state.json             # Crash recovery state
│
├── queue_manager.py       # Persistent task queue
├── task_executor.py       # Worker coroutines
├── model_handler.py       # AI model integration
├── test_runner.py         # Testing infrastructure
├── git_manager.py         # Git operations
├── logger.py              # Database logging
├── weekly_summary.py      # Checkpoint reporting
│
├── server/
│   ├── app.py             # Flask web application
│   └── templates/         # HTML templates
│       ├── index.html     # Dashboard
│       ├── logs.html      # Log viewer
│       └── settings.html  # Configuration
│
├── db/
│   └── agent_logs.sqlite  # SQLite database
│
├── reports/               # Weekly summary reports
│
└── demo files...          # Example code and tests
```

## 🔍 Monitoring & Debugging

### Dashboard Features
- **System Status**: Agent state, uptime, next checkpoint
- **Workers**: Individual worker status, task counts, restart controls
- **Queue**: Current size, task breakdown by status
- **Models**: Availability status for each AI backend
- **Git**: Repository status, recent commits, auto-push status

### Log Analysis
The agent provides comprehensive logging with multiple levels:
- **INFO**: Normal operations, task completions
- **WARNING**: Recoverable issues, retries
- **ERROR**: Failed tasks, component errors
- **DEBUG**: Detailed execution information

### Performance Metrics
Weekly reports include:
- Task completion rates and timing
- AI model usage statistics
- Git activity summary
- Error frequency analysis
- Recommendations for improvement

## 🛠️ Development & Extension

### Adding New Task Types
1. Modify prompt templates in `model_handler.py`
2. Add task type detection in `weekly_summary.py`
3. Update test patterns in `test_runner.py`

### Custom Models
Implement new model handlers by extending `BaseModelHandler`:
```python
class CustomModelHandler(BaseModelHandler):
    def is_available(self) -> bool:
        # Check model availability
        
    async def generate_code(self, prompt: str, task_id: str):
        # Generate code and return (code, stats)
```

### Database Schema
The SQLite database includes tables for:
- `tasks`: Task queue and status
- `execution_logs`: Detailed operation logs
- `git_commits`: Git activity tracking
- `model_stats`: AI model usage metrics
- `system_state`: Crash recovery data

## 🐛 Troubleshooting

### Common Issues

#### Agent Won't Start
```bash
# Check dependencies
pip install -r requirements.txt

# Verify model availability
python cli.py --status

# Check logs
python cli.py --logs 20
```

#### No Tasks Processing
1. **Check model availability**: Ensure your AI model is running
2. **Verify queue**: `python cli.py --status`
3. **Check workers**: Look for error messages in logs
4. **Test manually**: Add a simple task via CLI

#### High Failure Rate
1. **Review error patterns**: Check weekly reports
2. **Adjust complexity**: Start with simpler tasks
3. **Model performance**: Try different models
4. **Timeout settings**: Increase `TASK_TIMEOUT`

#### Git Issues
```bash
# Check Git configuration
git config --list

# Verify repository status
git status

# Test Git manager
python -c "from git_manager import git_manager; print(git_manager.get_repository_stats())"
```

### Recovery Procedures

#### Corrupt Database
```bash
# Backup current database
cp db/agent_logs.sqlite db/agent_logs.sqlite.backup

# Reinitialize (will lose history)
rm db/agent_logs.sqlite
python main.py  # Will recreate database
```

#### Lost State
```bash
# Check for state backup
ls -la state.json

# Manual restart (will reset uptime)
rm state.json
python main.py
```

## 📈 Performance Tuning

### Optimal Settings
- **Workers**: Start with 2-3, monitor CPU usage
- **Model**: Local models (Ollama) for consistency
- **Timeout**: 300s for most tasks, 600s for complex ones
- **Retries**: 3 attempts with exponential backoff

### Scaling Considerations
- **Memory**: ~500MB base + 200MB per worker
- **Storage**: ~10MB per day of logs
- **Network**: Varies by model (local vs API)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Ollama** for excellent local AI model serving
- **Flask** for the web framework
- **pytest** for testing infrastructure
- **GitPython** for Git integration
- **SQLite** for reliable data persistence

---

## 🚨 Important Notes

### ⚠️ Security Considerations
- The agent executes generated code in isolated environments
- Review generated code before deploying to production
- Use appropriate API key security for cloud models
- The web dashboard is local-only by default

### 💡 TODOs for Production Use
- [ ] Connect to your specific GitHub repository
- [ ] Configure your preferred AI model and API keys
- [ ] Adjust worker count based on your hardware
- [ ] Set up monitoring and alerting
- [ ] Configure backup strategies for the database
- [ ] Review and customize the task prompts for your domain

### 🎯 Getting Started Checklist
- [ ] Install Python dependencies: `pip install -r requirements.txt`
- [ ] Set up an AI model (Ollama recommended)
- [ ] Configure Git repository connection
- [ ] Run the demo: `python main.py`
- [ ] Access dashboard: http://127.0.0.1:5000
- [ ] Add your first task via CLI or web interface
- [ ] Monitor task execution in real-time

**Ready to deploy your autonomous coding assistant! 🚀** 