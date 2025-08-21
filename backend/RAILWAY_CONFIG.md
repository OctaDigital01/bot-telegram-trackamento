# 🚀 CONFIGURAÇÃO RAILWAY - BOT TELEGRAM

## 📋 VARIÁVEIS DE AMBIENTE NECESSÁRIAS

**Copie e cole essas variáveis no Railway:**

```
TELEGRAM_BOT_TOKEN=8422752874:AAFHBrpN2fXOPvQf0-k_786AooAQevUh4kY
TRIBOPAY_API_KEY=IzJsCJ0BleuURRzZvrTeigPp6xknO8e9nHT6WZtDpxFQVocwa3E3GYeNXtYq
XTRACKY_TOKEN=72701474-7e6c-4c87-b84f-836d4547a4bd
TRIBOPAY_BASE_URL=https://api.tribopay.com.br/api/public/v1
WEBHOOK_PORT=8080
```

## 🔗 LINKS DO PROJETO

- **Railway Project**: https://railway.com/project/182edc71-043f-4345-9649-7e3a87b20004?environmentId=2a18f703-7f30-4613-bb6e-29a437a13119
- **GitHub Repo**: https://github.com/OctaDigital01/bot-telegram-trackamento

## ⚙️ CONFIGURAÇÃO DE SERVIÇO

**Configurações necessárias no Railway:**

1. **Build Command**: Automaticamente detectado (requirements.txt)
2. **Start Command**: `python main.py`
3. **Root Directory**: `/backend`
4. **Port**: `8080` (variável WEBHOOK_PORT)

## 📁 ESTRUTURA BACKEND

```
backend/
├── main.py              # 🚀 Entrada principal (START COMMAND)
├── requirements.txt     # 📦 Dependências Python
├── railway.toml         # ⚙️ Configuração Railway
├── data/               # 💾 Banco de dados JSON
│   ├── bot_database.json
│   └── click_mapping.json
└── src/                # 📂 Código fonte
    ├── bot/            # 🤖 Bot Telegram
    ├── api_gateway/    # 💳 TriboPay + Webhook
    ├── database/       # 🗄️ Sistema de dados
    ├── config/         # ⚙️ Configurações
    └── utils/          # 🛠️ Utilitários
```

## 🔄 FLUXO DE FUNCIONAMENTO

1. **Entrada**: `main.py` inicia bot + webhook
2. **Bot**: Recebe usuários do Telegram  
3. **Webhook**: Processa pagamentos TriboPay
4. **Tracking**: Envia conversões para Xtracky
5. **Database**: Salva dados em JSON persistente

## ✅ DEPLOY AUTOMÁTICO

- **Trigger**: Push para branch `main` 
- **Build**: Instala requirements.txt
- **Start**: Executa main.py
- **Logs**: Visíveis no painel Railway
- **URL**: Gerada automaticamente para webhook