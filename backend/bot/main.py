#!/usr/bin/env python3
"""
Bot Telegram - Funil de Vendas com Tracking Completo
Conecta com API Gateway e PostgreSQL
Sistema híbrido: funciona com e sem grupo
"""

import os
import logging
import asyncio
import json
import base64
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    Application, CommandHandler, ContextTypes, 
    ChatJoinRequestHandler, CallbackQueryHandler
)
from database import get_db

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================================
# CONFIGURAÇÕES E CONSTANTES
# ================================

# Configurações do bot
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8422752874:AAFHBrpN2fXOPvQf0-k_786AooAQevUh4kY')
API_GATEWAY_URL = os.getenv('API_GATEWAY_URL', 'https://api-gateway.railway.app')
DATABASE_URL = os.getenv('DATABASE_URL')

# Configurações do grupo (variáveis de ambiente Railway)
GROUP_ID = os.getenv('GROUP_ID', '-1002342384678')  # Placeholder - configurar no Railway
GROUP_INVITE_LINK = os.getenv('GROUP_INVITE_LINK', 'https://t.me/+exemplo')  # Placeholder
GROUP_NAME = os.getenv('GROUP_NAME', 'Grupo VIP')  # Nome do grupo

# Delays estratégicos (em segundos) - facilmente editáveis
DELAY_BEFORE_APPROVAL = int(os.getenv('DELAY_BEFORE_APPROVAL', '30'))  # Delay antes de aprovar entrada
DELAY_BETWEEN_PREVIEWS = int(os.getenv('DELAY_BETWEEN_PREVIEWS', '7'))  # Delay entre envio de prévias

# File IDs das mídias (placeholders - serão configurados depois)
PREVIEW_MEDIA = {
    'video1': os.getenv('PREVIEW_VIDEO1_ID', 'BAACAgIAAxkBAAIBYGZ1234567890abcdef'),  # Placeholder
    'photo1': os.getenv('PREVIEW_PHOTO1_ID', 'AgACAgIAAxkBAAIBYGZ1234567890abcdef'),  # Placeholder
    'photo2': os.getenv('PREVIEW_PHOTO2_ID', 'AgACAgIAAxkBAAIBYGZ1234567890abcdef'),  # Placeholder
    'video2': os.getenv('PREVIEW_VIDEO2_ID', 'BAACAgIAAxkBAAIBYGZ1234567890abcdef'),  # Placeholder
}

# Textos do funil
WELCOME_GROUP_MESSAGE = """🎉 SEJA BEM-VINDA AO NOSSO GRUPO VIP!

Você acabou de entrar em um lugar especial...

Aqui você vai encontrar conteúdos EXCLUSIVOS que vão te ajudar a transformar sua vida! ✨

📸 Vou te mostrar algumas prévias do que te aguarda...

Prepare-se para descobrir todos os segredos! 🔥"""

VIP_INVITATION_MESSAGE = """🔥 GOSTOU DAS PRÉVIAS?

Isso é apenas o começo! No nosso VIP você vai ter acesso a:

🎯 Conteúdos completos e exclusivos
💎 Material que não existe em lugar nenhum
🚀 Acesso imediato a tudo
✨ Suporte direto comigo

💰 Por apenas R$ 10,00 você garante acesso TOTAL!

👇 CLIQUE AQUI PARA GARANTIR SEU VIP:"""

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

# ================================
# FUNÇÕES DO FUNIL DE VENDAS
# ================================

async def check_user_in_group(context, user_id):
    """Verifica se usuário é membro do grupo"""
    try:
        if not GROUP_ID or GROUP_ID.startswith('-100234'):  # Placeholder detectado
            logger.info(f"🔧 Grupo não configurado - modo híbrido ativado")
            return False
            
        member = await context.bot.get_chat_member(GROUP_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"❌ Erro verificando membro: {e}")
        return False

async def send_group_invite(update, user_name):
    """Envia convite para o grupo"""
    try:
        if not GROUP_INVITE_LINK or 'exemplo' in GROUP_INVITE_LINK:
            # Modo híbrido: sem grupo configurado
            message = f"👋 Olá {user_name}!\n\n"
            message += "✅ Sistema de tracking ativo e funcionando!\n\n"
            message += "Use /pix para gerar PIX com tracking completo!"
            
            await update.message.reply_text(message)
            return
            
        # Convite para grupo configurado
        keyboard = [
            [InlineKeyboardButton(f"🚀 ENTRAR NO {GROUP_NAME}", url=GROUP_INVITE_LINK)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"👋 Olá {user_name}!\n\n"
        message += f"Para acessar todo o conteúdo VIP, você precisa entrar no nosso grupo exclusivo!\n\n"
        message += f"🎯 Clique no botão abaixo para entrar:"
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"❌ Erro enviando convite: {e}")

async def send_preview_gallery(context, user_id):
    """Envia galeria de prévias com delays estratégicos"""
    try:
        # Mensagem de boas-vindas
        await context.bot.send_message(user_id, WELCOME_GROUP_MESSAGE)
        
        # Aguarda antes de começar as prévias
        await asyncio.sleep(DELAY_BETWEEN_PREVIEWS)
        
        # Envia primeira prévia (vídeo)
        try:
            await context.bot.send_video(
                user_id, 
                PREVIEW_MEDIA['video1'],
                caption="🔥 Primeira prévia exclusiva!"
            )
        except Exception as e:
            logger.warning(f"⚠️ Erro enviando vídeo 1: {e}")
            await context.bot.send_message(user_id, "🔥 Primeira prévia (vídeo não disponível)")
        
        await asyncio.sleep(DELAY_BETWEEN_PREVIEWS)
        
        # Envia fotos em grupo
        media_group = []
        try:
            media_group.append(InputMediaPhoto(PREVIEW_MEDIA['photo1'], caption="📸 Prévias exclusivas!"))
            media_group.append(InputMediaPhoto(PREVIEW_MEDIA['photo2']))
            
            await context.bot.send_media_group(user_id, media_group)
        except Exception as e:
            logger.warning(f"⚠️ Erro enviando fotos: {e}")
            await context.bot.send_message(user_id, "📸 Galeria de fotos (não disponível)")
        
        await asyncio.sleep(DELAY_BETWEEN_PREVIEWS)
        
        # Segunda prévia (vídeo)
        try:
            await context.bot.send_video(
                user_id, 
                PREVIEW_MEDIA['video2'],
                caption="🎬 Mais conteúdo incrível!"
            )
        except Exception as e:
            logger.warning(f"⚠️ Erro enviando vídeo 2: {e}")
            await context.bot.send_message(user_id, "🎬 Segunda prévia (vídeo não disponível)")
        
        await asyncio.sleep(DELAY_BETWEEN_PREVIEWS)
        
        # Convite para VIP
        keyboard = [
            [InlineKeyboardButton("💎 QUERO ACESSO VIP - R$ 10", callback_data="buy_vip")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            user_id,
            VIP_INVITATION_MESSAGE,
            reply_markup=reply_markup
        )
        
        logger.info(f"✅ Galeria de prévias enviada para usuário {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro enviando galeria: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start do bot - Etapa 1 do funil"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Usuário"
    
    logger.info(f"👤 Usuário {user_name} ({user_id}) iniciou conversa")
    
    # Processa parâmetro de tracking (mantém funcionalidade existente)
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
    
    # Salva dados do usuário via API (mantém funcionalidade existente)
    try:
        user_data = {
            'telegram_id': user_id,
            'username': user_name,
            'first_name': update.effective_user.first_name or user_name,
            'last_name': update.effective_user.last_name or '',
            'tracking_data': tracking_data
        }
        
        logger.info(f"📤 Enviando dados do usuário para API: {user_data}")
        response = requests.post(f"{API_GATEWAY_URL}/api/users", json=user_data, timeout=5)
        if response.status_code == 200:
            logger.info(f"✅ Usuário salvo no banco via API")
        else:
            logger.warning(f"⚠️ Erro salvando usuário: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Erro comunicação API: {e}")
    
    # NOVA FUNCIONALIDADE: Verificação de membro do grupo
    is_member = await check_user_in_group(context, user_id)
    
    if is_member:
        # Usuário já é membro - envia galeria imediatamente
        logger.info(f"✅ Usuário {user_id} já é membro do grupo")
        
        # Resposta com tracking preservado
        if tracking_data:
            message = f"👋 Bem-vinda de volta, {user_name}!\n\n"
            message += "✅ Tracking preservado:\n"
            if tracking_data.get('click_id'):
                message += f"🎯 Click ID: {tracking_data.get('click_id')}\n"
            if tracking_data.get('utm_source'):
                message += f"📡 UTM Source: {tracking_data.get('utm_source')}\n"
            message += "\n🎯 Enviando conteúdo exclusivo..."
            await update.message.reply_text(message)
        
        # Envia galeria de prévias
        await send_preview_gallery(context, user_id)
    else:
        # Usuário não é membro - convida para grupo ou modo híbrido
        logger.info(f"🔍 Usuário {user_id} não é membro - enviando convite")
        
        # Mostra tracking se disponível
        if tracking_data:
            tracking_msg = f"✅ Tracking capturado:\n"
            if tracking_data.get('click_id'):
                tracking_msg += f"🎯 Click ID: {tracking_data.get('click_id')}\n"
            if tracking_data.get('utm_source'):
                tracking_msg += f"📡 UTM Source: {tracking_data.get('utm_source')}\n"
            tracking_msg += "\n"
            await update.message.reply_text(tracking_msg)
        
        # Envia convite para grupo ou continua em modo híbrido
        await send_group_invite(update, user_name)

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

# ================================
# HANDLERS DO FUNIL DE VENDAS
# ================================

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para aprovação de entrada no grupo - Etapa 2 do funil"""
    try:
        chat_join_request = update.chat_join_request
        user_id = chat_join_request.from_user.id
        user_name = chat_join_request.from_user.first_name or "Usuário"
        
        logger.info(f"📥 Solicitação de entrada: {user_name} ({user_id})")
        
        # Delay estratégico antes de aprovar
        logger.info(f"⏳ Aguardando {DELAY_BEFORE_APPROVAL}s antes de aprovar...")
        await asyncio.sleep(DELAY_BEFORE_APPROVAL)
        
        # Aprova entrada no grupo
        await chat_join_request.approve()
        logger.info(f"✅ Usuário {user_id} aprovado no grupo")
        
        # Envia mensagem de boas-vindas imediata no privado
        try:
            await context.bot.send_message(
                user_id,
                f"🎉 Parabéns {user_name}!\n\nVocê foi aprovada no grupo!\n\n⏳ Em instantes vou te enviar conteúdos exclusivos..."
            )
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível enviar mensagem privada: {e}")
        
        # Aguarda um pouco e envia galeria de prévias
        await asyncio.sleep(3)
        await send_preview_gallery(context, user_id)
        
    except Exception as e:
        logger.error(f"❌ Erro processando entrada no grupo: {e}")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para callbacks dos botões - Sistema VIP"""
    try:
        query = update.callback_query
        user_id = query.from_user.id
        user_name = query.from_user.first_name or "Usuário"
        
        await query.answer()
        
        if query.data == "buy_vip":
            logger.info(f"💎 Usuário {user_id} clicou em comprar VIP")
            
            # Integra com sistema PIX existente
            try:
                # Solicita PIX via API Gateway (mantém funcionalidade existente)
                pix_data = {
                    'user_id': user_id,
                    'valor': 10.0,
                    'plano': 'VIP'
                }
                
                response = requests.post(f"{API_GATEWAY_URL}/api/pix/gerar", json=pix_data, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        message = f"💰 PIX VIP de R$ {result['valor']} gerado!\n\n"
                        message += f"📋 PIX Copia e Cola:\n`{result['pix_copia_cola']}`\n\n"
                        message += "🔥 Após o pagamento você terá acesso TOTAL ao conteúdo VIP!\n\n"
                        message += "✅ Tracking preservado - sua conversão será computada!"
                        
                        await query.edit_message_text(message)
                        logger.info(f"✅ PIX VIP gerado para usuário {user_id}")
                    else:
                        await query.edit_message_text(f"❌ Erro: {result.get('error')}")
                else:
                    await query.edit_message_text("❌ Erro na comunicação com gateway de pagamento")
                    
            except Exception as e:
                logger.error(f"❌ Erro gerando PIX VIP: {e}")
                await query.edit_message_text("❌ Erro interno do sistema")
        
    except Exception as e:
        logger.error(f"❌ Erro processando callback: {e}")

def main():
    """Função principal do bot"""
    logger.info("🤖 === BOT TELEGRAM - FUNIL DE VENDAS INICIANDO ===")
    logger.info(f"🔗 API Gateway: {API_GATEWAY_URL}")
    logger.info(f"🗄️ Database: {'PostgreSQL' if DATABASE_URL else 'API Gateway'}")
    logger.info(f"👥 Grupo ID: {GROUP_ID}")
    logger.info(f"⏰ Delay aprovação: {DELAY_BEFORE_APPROVAL}s")
    logger.info(f"📸 Delay prévias: {DELAY_BETWEEN_PREVIEWS}s")
    
    # Cria aplicação
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Adiciona handlers existentes (mantém funcionalidade)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("pix", pix_command))
    
    # Adiciona novos handlers do funil
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Executa bot
    logger.info("🚀 Bot do funil iniciado com sucesso!")
    logger.info("📱 Funcionalidades ativas:")
    logger.info("   ✅ Tracking UTM preservado")
    logger.info("   ✅ Sistema PIX TriboPay")
    logger.info("   ✅ PostgreSQL integrado")
    logger.info("   ✅ Verificação de grupo")
    logger.info("   ✅ Aprovação automática")
    logger.info("   ✅ Galeria de prévias")
    logger.info("   ✅ Botões VIP")
    logger.info("   ✅ Modo híbrido (com/sem grupo)")
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()