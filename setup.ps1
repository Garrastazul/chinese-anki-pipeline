param(
    [string]$Model
)

$ErrorActionPreference = "Stop"

if (-not $Model) {
    $configPath = "$PSScriptRoot\config.json"
    if (Test-Path -LiteralPath $configPath) {
        $config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
        $Model = $config.ollama.model
    }
}
if (-not $Model) {
    $Model = "qwen2.5:7b"
}

Write-Host "Installing Python dependencies..."
try {
    pip install -e .
} catch {
    Write-Host "pip install failed. Try running as administrator or use: python -m venv .venv"
    exit 1
}

$wslAvailable = Get-Command wsl -ErrorAction SilentlyContinue
if (-not $wslAvailable) {
    Write-Host "WSL not found. Make sure Ollama is running natively."
} else {
    Write-Host "Starting Ollama in WSL..."
    $stderrLog = Join-Path -Path $env:TEMP -ChildPath "ollama_wsl_stderr.log"
    $null = Start-Process -WindowStyle Hidden -FilePath wsl -ArgumentList "ollama","serve" -RedirectStandardError $stderrLog
    Start-Sleep -Seconds 2
    if ((Get-Item -LiteralPath $stderrLog -ErrorAction SilentlyContinue).Length -gt 0) {
        Write-Host "Ollama WSL stderr output (may be benign):" -ForegroundColor Yellow
        Get-Content -LiteralPath $stderrLog | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
    }

    Write-Host "Downloading model $Model ..."
    wsl ollama pull "$Model"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error downloading model $Model. Verify that ollama is installed in WSL." -ForegroundColor Yellow
    }
}

Write-Host "Setup complete."
Write-Host ""
Write-Host "To run tests: pytest tests/"
Write-Host "To generate the deck: python src/main.py --level A1"
