Write-Host "Instalando dependencias..."
pip install -e .

Write-Host "Iniciando Ollama en WSL..."
wsl bash -c "ollama serve > /dev/null 2>&1 &"

Write-Host "Descargando modelo qwen2.5:7b..."
wsl ollama pull qwen2.5:7b

Write-Host "Todo listo. Ejecuta: python src/main.py"
