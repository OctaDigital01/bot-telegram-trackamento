#!/bin/bash

# Script de configuração Railway
PROJECT_ID="182edc71-043f-4345-9649-7e3a87b20004"
ENV_ID="2a18f703-7f30-4613-bb6e-29a437a13119"
TOKEN="5de61caa-649f-4532-94b2-259be83cd6ac"

echo "🚀 Configurando Railway Bot Telegram..."

# Configurar variáveis uma por uma via curl
echo "📋 Configurando variáveis de ambiente..."

# TELEGRAM_BOT_TOKEN
curl -X POST "https://backboard.railway.app/graphql" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"mutation { variableUpsert(input: { projectId: \\\"$PROJECT_ID\\\", environmentId: \\\"$ENV_ID\\\", name: \\\"TELEGRAM_BOT_TOKEN\\\", value: \\\"8422752874:AAFHBrpN2fXOPvQf0-k_786AooAQevUh4kY\\\" }) }\"
  }" 

echo "✅ Token Telegram configurado"

# TRIBOPAY_API_KEY  
curl -X POST "https://backboard.railway.app/graphql" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"mutation { variableUpsert(input: { projectId: \\\"$PROJECT_ID\\\", environmentId: \\\"$ENV_ID\\\", name: \\\"TRIBOPAY_API_KEY\\\", value: \\\"IzJsCJ0BleuURRzZvrTeigPp6xknO8e9nHT6WZtDpxFQVocwa3E3GYeNXtYq\\\" }) }\"
  }"

echo "✅ TriboPay API configurada"

# XTRACKY_TOKEN
curl -X POST "https://backboard.railway.app/graphql" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"mutation { variableUpsert(input: { projectId: \\\"$PROJECT_ID\\\", environmentId: \\\"$ENV_ID\\\", name: \\\"XTRACKY_TOKEN\\\", value: \\\"72701474-7e6c-4c87-b84f-836d4547a4bd\\\" }) }\"
  }"

echo "✅ Xtracky Token configurado"

# TRIBOPAY_BASE_URL
curl -X POST "https://backboard.railway.app/graphql" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"mutation { variableUpsert(input: { projectId: \\\"$PROJECT_ID\\\", environmentId: \\\"$ENV_ID\\\", name: \\\"TRIBOPAY_BASE_URL\\\", value: \\\"https://api.tribopay.com.br/api/public/v1\\\" }) }\"
  }"

echo "✅ TriboPay URL configurada"

echo "🎯 Todas as variáveis configuradas!"
echo "🚀 Fazendo deploy..."

# Deploy do projeto
export RAILWAY_TOKEN=$TOKEN
railway up --detach

echo "✅ Deploy realizado!"
echo "🔗 Acesse: https://railway.com/project/$PROJECT_ID"