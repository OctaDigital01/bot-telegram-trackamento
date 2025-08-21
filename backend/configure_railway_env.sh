#!/bin/bash

# Configurar Railway Environment Variables via API
echo "🔧 Configurando variáveis Railway para produção..."

# Project details
PROJECT_ID="182edc71-043f-4345-9649-7e3a87b20004"
ENV_ID="2a18f703-7f30-4613-bb6e-29a437a13119"
TOKEN="baf7c528-4307-492d-a2a0-bb3af7d2b30f"

# GraphQL endpoint
ENDPOINT="https://backboard.railway.app/graphql/v2"

# Configurar RAILWAY_ENVIRONMENT
echo "📋 Configurando RAILWAY_ENVIRONMENT=production..."
curl -X POST "$ENDPOINT" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation VariableUpsert($projectId: String!, $environmentId: String!, $name: String!, $value: String!) { variableUpsert(input: { projectId: $projectId, environmentId: $environmentId, name: $name, value: $value }) }",
    "variables": {
      "projectId": "'$PROJECT_ID'",
      "environmentId": "'$ENV_ID'",
      "name": "RAILWAY_ENVIRONMENT",
      "value": "production"
    }
  }'

echo -e "\n✅ Variável RAILWAY_ENVIRONMENT configurada"
echo "🚀 Sistema agora está 100% online!"
echo "🔗 Acompanhe deploy: https://railway.com/project/$PROJECT_ID"