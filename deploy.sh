#!/bin/bash
echo "🚀 Iniciando deploy manual do Telegram PromoPulse..."

# 1. Puxa os últimos commits do GitHub
echo "📥 Puxando commits do master..."
git pull origin master

# 2. Reconstrói o contêiner do Docker
echo "🐳 Reconstruindo contêiner Docker..."
docker compose up -d --build

echo "✅ Deploy concluído com sucesso!"
