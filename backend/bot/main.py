#!/usr/bin/env python3
"""
Bot Telegram - Serviço isolado
Conecta com API Gateway e PostgreSQL
"""

import os
import logging
import asyncio
import json
import base64
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from database import get_db

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configurações do bot
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8422752874:AAFHBrpN2fXOPvQf0-k_786AooAQevUh4kY')
API_GATEWAY_URL = os.getenv('API_GATEWAY_URL', 'https://api-gateway.railway.app')
DATABASE_URL = os.getenv('DATABASE_URL')

# Database PostgreSQL
try:
    db = get_db()
    logger.info("✅ Bot conectado ao PostgreSQL")
except Exception as e:
    logger.error(f"❌ Erro ao conectar PostgreSQL: {e}")
    db = None

def decode_tracking_data(encoded_param):
    """Decodifica dados de tracking do Xtracky"""
    try:
        # Verifica se é um ID mapeado (começa com 'M')
        if encoded_param.startswith('M') and len(encoded_param) <= 12:
            logger.info(f"🔍 ID mapeado detectado: {encoded_param}")
            
            # Tenta recuperar dados do API Gateway
            try:
                response = requests.get(f"{API_GATEWAY_URL}/api/tracking/get/{encoded_param}", timeout=5)
                if response.status_code == 200:
                    api_data = response.json()
                    if api_data.get('success') and api_data.get('original'):
                        original_data = json.loads(api_data['original'])
                        logger.info(f"✅ Dados recuperados do servidor: {original_data}")
                        return original_data
                    else:
                        logger.warning(f"⚠️ Dados não encontrados no servidor para ID: {encoded_param}")
                else:
                    logger.warning(f"⚠️ API retornou status {response.status_code}")
            except Exception as e:
                logger.error(f"❌ Erro ao consultar API: {e}")
            
            # Fallback: usar ID como click_id
            return {'click_id': encoded_param}
        
        # Tenta decodificar Base64
        try:
            decoded_bytes = base64.b64decode(encoded_param.encode('utf-8'))
            decoded_str = decoded_bytes.decode('utf-8')
            tracking_data = json.loads(decoded_str)
            logger.info(f"✅ Base64 decodificado: {tracking_data}")
            return tracking_data
        except:
            logger.info(f"ℹ️ Não é Base64 válido: {encoded_param}")
        
        # Processa formato Xtracky concatenado
        return process_xtracky_data(encoded_param)
        
    except Exception as e:
        logger.error(f"❌ Erro na decodificação: {e}")
        return {'click_id': encoded_param}

def process_xtracky_data(data_string):
    """Processa dados do Xtracky no formato concatenado"""
    try:
        # Formato esperado: "token::click_id::medium::campaign::term::content"
        if '::' in data_string:
            parts = data_string.split('::')
            
            tracking_data = {}
            
            # Mapeia as partes para os campos corretos
            if len(parts) >= 1 and parts[0]:
                tracking_data['utm_source'] = parts[0]  # Token Xtracky
            if len(parts) >= 2 and parts[1]:
                tracking_data['click_id'] = parts[1]
            if len(parts) >= 3 and parts[2]:
                tracking_data['utm_medium'] = parts[2]
            if len(parts) >= 4 and parts[3]:
                tracking_data['utm_campaign'] = parts[3]
            if len(parts) >= 5 and parts[4]:
                tracking_data['utm_term'] = parts[4]
            if len(parts) >= 6 and parts[5]:
                tracking_data['utm_content'] = parts[5]
            
            logger.info(f"✅ Xtracky processado: {tracking_data}")
            return tracking_data
        
        # Fallback: usar como click_id
        return {'click_id': data_string}
        
    except Exception as e:
        logger.error(f"❌ Erro processando Xtracky: {e}")
        return {'click_id': data_string}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start do bot"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Usuário"
    
    logger.info(f"👤 Usuário {user_name} ({user_id}) iniciou conversa")
    
    # Processa parâmetro de tracking
    tracking_data = {}
    if context.args:
        encoded_param = ' '.join(context.args)
        logger.info(f"🔍 Parâmetro recebido: {encoded_param}")
        tracking_data = decode_tracking_data(encoded_param)
    else:
        # Busca último tracking disponível
        try:
            response = requests.get(f"{API_GATEWAY_URL}/api/tracking/latest", timeout=5)
            if response.status_code == 200:
                api_data = response.json()
                if api_data.get('success') and api_data.get('original'):
                    tracking_data = json.loads(api_data['original'])
                    logger.info(f"📋 Tracking recente aplicado: {tracking_data}")
        except Exception as e:
            logger.error(f"❌ Erro buscando tracking: {e}")
    
    # Salva dados do usuário via API
    try:
        user_data = {
            'user_id': user_id,
            'name': user_name,
            'tracking_data': tracking_data
        }
        response = requests.post(f"{API_GATEWAY_URL}/api/users", json=user_data, timeout=5)
        if response.status_code == 200:
            logger.info(f"✅ Usuário salvo no banco via API")
        else:
            logger.warning(f"⚠️ Erro salvando usuário: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Erro comunicação API: {e}")
    
    # Resposta ao usuário
    if tracking_data:
        message = f"👋 Olá {user_name}!\n\n"
        message += "✅ Tracking decodificado:\n"
        for key, value in tracking_data.items():
            message += f"{key}: {value}\n"
        message += "\nUse /pix para gerar PIX com dados completos!"
    else:
        message = f"👋 Olá {user_name}!\n\n❌ Nenhum dado de tracking detectado.\nTente acessar via presell primeiro."
    
    await update.message.reply_text(message)

async def pix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /pix - gera PIX via API Gateway"""
    user_id = update.effective_user.id
    
    try:
        # Solicita PIX via API Gateway
        pix_data = {
            'user_id': user_id,
            'valor': 10.0,
            'plano': 'VIP'
        }
        
        response = requests.post(f"{API_GATEWAY_URL}/api/pix/gerar", json=pix_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                message = f"💰 PIX de R$ {result['valor']} gerado!\n\n"
                message += f"📋 PIX Copia e Cola:\n`{result['pix_copia_cola']}`\n\n"
                message += "✅ Todos os dados de tracking foram preservados!"
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(f"❌ Erro: {result.get('error')}")
        else:
            await update.message.reply_text("❌ Erro na comunicação com gateway de pagamento")
            
    except Exception as e:
        logger.error(f"❌ Erro comando PIX: {e}")
        await update.message.reply_text("❌ Erro interno do sistema")

def main():
    """Função principal do bot"""
    logger.info("🤖 === BOT TELEGRAM INICIANDO ===")
    logger.info(f"🔗 API Gateway: {API_GATEWAY_URL}")
    logger.info(f"🗄️ Database: {'PostgreSQL' if DATABASE_URL else 'API Gateway'}")
    
    # Cria aplicação
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Adiciona handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("pix", pix_command))
    
    # Executa bot
    logger.info("🚀 Bot iniciado com sucesso!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()