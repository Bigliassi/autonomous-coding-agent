# Ollama Installation Script for Windows
# This script downloads and installs Ollama for the Autonomous Coding Agent

Write-Host "🤖 Setting up Ollama for Autonomous Coding Agent..." -ForegroundColor Cyan

# Check if Ollama is already installed
try {
    $ollamaVersion = ollama --version 2>$null
    if ($ollamaVersion) {
        Write-Host "✅ Ollama is already installed: $ollamaVersion" -ForegroundColor Green
        exit 0
    }
} catch {
    Write-Host "📦 Ollama not found, proceeding with installation..." -ForegroundColor Yellow
}

# Download Ollama installer
$ollamaUrl = "https://ollama.ai/download/OllamaSetup.exe"
$installerPath = "$env:TEMP\OllamaSetup.exe"

Write-Host "⬇️  Downloading Ollama installer..." -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri $ollamaUrl -OutFile $installerPath -UseBasicParsing
    Write-Host "✅ Download completed" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to download Ollama installer" -ForegroundColor Red
    Write-Host "Please manually download from: https://ollama.ai/download" -ForegroundColor Yellow
    exit 1
}

# Run installer
Write-Host "🔧 Running Ollama installer..." -ForegroundColor Yellow
try {
    Start-Process -FilePath $installerPath -Wait
    Write-Host "✅ Ollama installation completed" -ForegroundColor Green
} catch {
    Write-Host "❌ Installation failed" -ForegroundColor Red
    exit 1
}

# Clean up
Remove-Item $installerPath -ErrorAction SilentlyContinue

# Wait for Ollama service to start
Write-Host "⏳ Waiting for Ollama service to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Verify installation
try {
    $version = ollama --version
    Write-Host "✅ Ollama installed successfully: $version" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Ollama installed but may need system restart" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎉 Ollama setup complete!" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Restart your terminal/PowerShell" -ForegroundColor White
Write-Host "2. Run: ollama pull codellama:7b-instruct" -ForegroundColor White
Write-Host "3. Run: ollama pull llama2:7b" -ForegroundColor White 