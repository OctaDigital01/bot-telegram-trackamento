import os
from dotenv import load_dotenv

load_dotenv()

# Bot Telegram
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8422752874:AAFHBrpN2fXOPvQf0-k_786AooAQevUh4kY')

# TriboPay Payment
TRIBOPAY_API_KEY = os.getenv('TRIBOPAY_API_KEY', 'IzJsCJ0BleuURRzZvrTeigPp6xknO8e9nHT6WZtDpxFQVocwa3E3GYeNXtYq')
TRIBOPAY_BASE_URL = os.getenv('TRIBOPAY_BASE_URL', 'https://api.tribopay.com.br/api/public/v1')

# Xtracky
XTRACKY_TOKEN = os.getenv('XTRACKY_TOKEN', '72701474-7e6c-4c87-b84f-836d4547a4bd')
XTRACKY_WEBHOOK_URL = 'https://api.xtracky.com/api/integrations/tribopay'

# Server
WEBHOOK_PORT = int(os.getenv('PORT', os.getenv('WEBHOOK_PORT', '8080')))

# URL do webhook - Railway vs Local
if os.getenv('RAILWAY_ENVIRONMENT'):
    # Railway - usar domínio gerado automaticamente
    RAILWAY_SERVICE_DOMAIN = os.getenv('RAILWAY_STATIC_URL', os.getenv('RAILWAY_PUBLIC_DOMAIN'))
    if RAILWAY_SERVICE_DOMAIN:
        WEBHOOK_URL = f"https://{RAILWAY_SERVICE_DOMAIN}"
    else:
        # Fallback usando a estrutura padrão Railway
        PROJECT_ID = "182edc71-043f-4345-9649-7e3a87b20004" 
        WEBHOOK_URL = f"https://web-production-{PROJECT_ID[:8]}.up.railway.app"
else:
    # Local
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', f'http://localhost:{WEBHOOK_PORT}')