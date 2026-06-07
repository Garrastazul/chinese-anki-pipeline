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

Write-Host "Make sure Ollama is running (start Ollama from Start Menu if not)."
Write-Host "Downloading/verifying model $Model ..."
try {
    $result = & ollama pull "$Model" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error downloading model $Model. Verify that Ollama is installed and running." -ForegroundColor Yellow
        Write-Host $result -ForegroundColor DarkYellow
    }
} catch {
    Write-Host "Ollama not found. Download from https://ollama.com and install." -ForegroundColor Yellow
}

Write-Host "Setup complete."
Write-Host ""
Write-Host "To run tests: pytest tests/"
Write-Host "To generate the deck: python src/main.py --level A1"
