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
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '8080'))
WEBHOOK_URL = os.getenv('WEBHOOK_URL', f'http://localhost:{WEBHOOK_PORT}')