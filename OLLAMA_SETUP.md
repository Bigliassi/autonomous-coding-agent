# 🤖 Ollama Setup for Autonomous Coding Agent

## Quick Installation

### Method 1: Direct Download (Recommended)
1. Visit https://ollama.ai/download
2. Download the Windows installer
3. Run the installer as administrator
4. Restart your terminal/PowerShell

### Method 2: Command Line (if execution policies allow)
```powershell
# Download and run installer
Invoke-WebRequest -Uri "https://ollama.ai/download/OllamaSetup.exe" -OutFile "$env:TEMP\OllamaSetup.exe"
Start-Process -FilePath "$env:TEMP\OllamaSetup.exe" -Wait
```

## After Installation

### 1. Verify Ollama is installed
```bash
ollama --version
```

### 2. Start Ollama service (if not running)
```bash
ollama serve
```

### 3. Download models for coding
```bash
# Primary coding model (recommended)
ollama pull codellama:7b-instruct

# Alternative models (optional)
ollama pull llama2:7b
ollama pull mistral:7b
```

### 4. Test the installation
```bash
# Test basic functionality
ollama run codellama:7b-instruct "Write a Python function to add two numbers"
```

## Configuration for the Agent

After installing Ollama, the agent will automatically detect and use it with these default settings:
- Model: `codellama:7b-instruct`
- Base URL: `http://localhost:11434`
- Timeout: 300 seconds

You can change these in the web dashboard at http://127.0.0.1:5000/settings

## Troubleshooting

### Ollama service not starting
```bash
# Kill any existing processes
taskkill /f /im ollama.exe

# Start service manually
ollama serve
```

### Model download fails
- Check internet connection
- Ensure enough disk space (7B models need ~4GB)
- Try pulling one model at a time

### Can't connect to Ollama
- Verify service is running: `ollama ps`
- Check firewall settings
- Restart Ollama service

## Models Explained

| Model | Size | Best For | Speed |
|-------|------|----------|-------|
| codellama:7b-instruct | ~4GB | Code generation | Fast |
| llama2:7b | ~4GB | General text | Fast |
| mistral:7b | ~4GB | Balanced performance | Fast |

The agent is configured to work best with `codellama:7b-instruct` for code generation tasks. 