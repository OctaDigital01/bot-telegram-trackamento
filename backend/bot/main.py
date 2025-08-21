#!/usr/bin/env python3
"""
Bot Telegram - Funil de Vendas com Tracking Completo
Conecta com API Gateway e PostgreSQL
"""

import os
import logging
import asyncio
import json
import base64
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, ChatJoinRequest
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ChatJoinRequestHandler
from telegram.constants import ParseMode
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

# Configurações do grupo
GROUP_ID = int(os.getenv('GROUP_ID', '-1002342384678'))
GROUP_INVITE_LINK = os.getenv('GROUP_INVITE_LINK', 'https://t.me/+iydDH1RTDPJlNTNh')

# File IDs das mídias
START_IMAGE_ID = os.getenv('START_IMAGE_ID', 'AgACAgEAAxkBAAIikminXIWOkl4Ru-3c7KFTNPmeUA6QAALsrjEbglU4RYKi9nkfTnf8AQADAgADeQADNgQ')
PREVIEW_VIDEO_ID = os.getenv('PREVIEW_VIDEO_ID', 'BAACAgEAAxkBAAIilminXJOuWQ9uS_ZNt6seh7JKYoOHAAJtBgACglU4RRTfnPJAqPT3NgQ')
PREVIEW_IMAGE_1_ID = os.getenv('PREVIEW_IMAGE_1_ID', 'AgACAgEAAxkBAAIimminXJm9zlFbOKnhm3NO2CwyYo8kAALtrjEbglU4RfgJ-nP8LfvFAQADAgADeQADNgQ')
PREVIEW_IMAGE_2_ID = os.getenv('PREVIEW_IMAGE_2_ID', 'AgACAgEAAxkBAAIinminXKGMK_ue_HOK0Va36FJWO66vAALurjEbglU4RbhisJEkbnbqAQADAgADeQADNgQ')
PREVIEW_IMAGE_3_ID = os.getenv('PREVIEW_IMAGE_3_ID', 'AgACAgEAAxkBAAIiominXKpBBmO4jkUUhssoYeHj57hUAALvrjEbglU4RYevSIpIW_DuAQADAgADeQADNgQ')

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

# ===== ETAPA 3: PRÉVIAS =====
async def step3_previews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia a galeria de prévias e as mensagens da Etapa 3"""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    logger.info(f"Enviando Etapa 3 (Prévias) para o chat {chat_id}")

    # Tenta enviar media group, se falhar envia mensagens individuais
    try:
        media_group = [
            InputMediaVideo(media=PREVIEW_VIDEO_ID),
            InputMediaPhoto(media=PREVIEW_IMAGE_1_ID),
            InputMediaPhoto(media=PREVIEW_IMAGE_2_ID),
            InputMediaPhoto(media=PREVIEW_IMAGE_3_ID),
        ]
        
        await context.bot.send_media_group(chat_id=chat_id, media=media_group)
    except Exception as e:
        logger.warning(f"⚠️ Erro enviando media group: {e}")
        await context.bot.send_message(chat_id, "🔥 Galeria de prévias (mídias não disponíveis)")
    
    # Espera 7 segundos
    await asyncio.sleep(7)

    await context.bot.send_message(
        chat_id=chat_id,
        text="Gostou do que viu, meu bem 🤭?\n\nEssa é só uma PRÉVIA borrada do que te espera bb... 💦"
    )
    
    text2 = """
Tenho muito mais no VIP pra você (TOTALMENTE SEM CENSURA):
💎 Vídeos e fotos do jeitinho que você gosta...
💎 Videos exclusivo pra você, te fazendo go.zar só eu e você
💎 Meu contato pessoal
💎 Sempre posto coisa nova lá
💎 E muito mais meu bem...

Vem goz.ar po.rra quentinha pra mim🥵💦⬇️"""

    keyboard = [[InlineKeyboardButton("CONHECER O VIP🔥", callback_data='vip_options')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text2,
        reply_markup=reply_markup
    )

# ===== ETAPA 2: BOAS-VINDAS =====
async def send_step2_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Envia a mensagem de boas-vindas da Etapa 2"""
    logger.info(f"Enviando Etapa 2 (Boas-vindas) para o chat {chat_id}")

    text = "Meu bem, já vou te aceitar no meu grupinho, ta bom?\n\nMas neem precisa esperar, clica aqui no botão pra ver um pedacinho do que te espera... 🔥(É DE GRAÇA!!!)⬇️"
    keyboard = [[InlineKeyboardButton("VER CONTEÚDINHO DE GRAÇA 🔥🥵", callback_data='step3_previews')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup
    )

# ===== ETAPA 1: COMANDO /START =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerencia o comando /start e o fluxo inicial"""
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or "Usuário"
    
    logger.info(f"👤 Usuário {user_name} ({user_id}) iniciou conversa")
    
    # Processa parâmetro de tracking (MANTÉM FUNCIONALIDADE EXISTENTE)
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
    
    # Salva dados do usuário via API (MANTÉM FUNCIONALIDADE EXISTENTE)
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

    # NOVO: Verificação de membro do grupo
    try:
        chat_member = await context.bot.get_chat_member(chat_id=GROUP_ID, user_id=user.id)
        is_in_group = chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.warning(f"Não foi possível verificar o status do usuário {user.id} no grupo {GROUP_ID}: {e}")
        is_in_group = False

    # Usuário já está no grupo - envia prévias direto
    if is_in_group:
        logger.info(f"Usuário {user.id} já está no grupo.")
        
        # Mostra tracking se disponível
        if tracking_data:
            tracking_msg = f"✅ Tracking preservado:\n"
            if tracking_data.get('click_id'):
                tracking_msg += f"🎯 Click ID: {tracking_data.get('click_id')}\n"
            if tracking_data.get('utm_source'):
                tracking_msg += f"📡 UTM Source: {tracking_data.get('utm_source')}\n"
            await update.message.reply_text(tracking_msg)
        
        text = "Meu bem, que bom te ver de novo! 🔥 Clica aqui pra não perder as novidades quentes que preparei pra você! ⬇️"
        keyboard = [[InlineKeyboardButton("VER CONTEÚDINHO DE GRAÇA 🔥🥵", callback_data='step3_previews')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Tenta enviar com foto, se falhar envia só texto
        try:
            await update.message.reply_photo(
                photo=START_IMAGE_ID,
                caption=text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.warning(f"⚠️ Erro enviando foto para membro: {e}")
            await update.message.reply_text(
                text=text,
                reply_markup=reply_markup
            )
        return

    # Novo usuário ou com parâmetro - convida para grupo
    click_id_param = " ".join(context.args) if context.args else None
    if click_id_param:
        logger.info(f"Usuário {user.id} veio com o parâmetro: {click_id_param}")
        text = f"Você veio através do meu KWAI (*{click_id_param}*)\n\nMeu bem, entra no meu *GRUPINHO GRÁTIS* pra ver daquele jeito q vc gosta 🥵⬇️"
        
        # Mostra tracking detalhado
        if tracking_data:
            tracking_msg = f"✅ Tracking capturado:\n"
            if tracking_data.get('click_id'):
                tracking_msg += f"🎯 Click ID: {tracking_data.get('click_id')}\n"
            if tracking_data.get('utm_source'):
                tracking_msg += f"📡 UTM Source: {tracking_data.get('utm_source')}\n"
            text = tracking_msg + "\n" + text
    else:
        logger.info(f"Usuário {user.id} é novo.")
        text = "Meu bem, entra no meu *GRUPINHO GRÁTIS* pra ver daquele jeito q vc gosta 🥵⬇️"

    keyboard = [[InlineKeyboardButton("MEU GRUPINHO🥵?", url=GROUP_INVITE_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Tenta enviar com foto, se falhar envia só texto
    try:
        await update.message.reply_photo(
            photo=START_IMAGE_ID,
            caption=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.warning(f"⚠️ Erro enviando foto de start: {e}")
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

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

# ===== CALLBACK DO PAGAMENTO VIP =====
async def vip_options_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para o botão de conhecer o VIP - integra com PIX existente"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    logger.info(f"💎 Usuário {user_id} clicou para conhecer o VIP")
    
    # Integra com sistema PIX existente (MANTÉM FUNCIONALIDADE)
    try:
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
                message += "✅ Todos os dados de tracking foram preservados!"
                
                await query.edit_message_text(message)
                logger.info(f"✅ PIX VIP gerado para usuário {user_id}")
            else:
                await query.edit_message_text(f"❌ Erro: {result.get('error')}")
        else:
            await query.edit_message_text("❌ Erro na comunicação com gateway de pagamento")
            
    except Exception as e:
        logger.error(f"❌ Erro gerando PIX VIP: {e}")
        await query.edit_message_text("❌ Erro interno do sistema")

# ===== APROVAÇÃO DE ENTRADA NO GRUPO =====
async def approve_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lida com pedidos de entrada no grupo"""
    join_request: ChatJoinRequest = update.chat_join_request
    user_id = join_request.from_user.id

    if join_request.chat.id == GROUP_ID:
        logger.info(f"Recebido pedido de entrada de {user_id} no grupo {GROUP_ID}")
        
        # Envia a Etapa 2 imediatamente
        await send_step2_message(context, user_id)
        
        # Espera 40 segundos
        await asyncio.sleep(40)
        
        # Aprova a entrada
        try:
            await context.bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=user_id)
            logger.info(f"Aprovada entrada de {user_id} no grupo")
        except Exception as e:
            logger.error(f"Falha ao aprovar usuário {user_id}: {e}")

def main():
    """Função principal do bot"""
    if not BOT_TOKEN:
        logger.critical("Variável de ambiente TELEGRAM_BOT_TOKEN não encontrada.")
        return
    if not GROUP_ID:
        logger.critical("Variável de ambiente GROUP_ID não encontrada.")
        return

    logger.info("🤖 === BOT FUNIL DE VENDAS INICIANDO ===")
    logger.info(f"🔗 API Gateway: {API_GATEWAY_URL}")
    logger.info(f"🗄️ Database: {'PostgreSQL' if DATABASE_URL else 'API Gateway'}")
    logger.info(f"👥 Grupo ID: {GROUP_ID}")
    
    # Cria aplicação
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers de Comando
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("pix", pix_command))
    
    # Handlers de Callback (botões)
    application.add_handler(CallbackQueryHandler(step3_previews, pattern='^step3_previews$'))
    application.add_handler(CallbackQueryHandler(vip_options_callback, pattern='^vip_options$'))
    
    # Handler de Pedidos de Entrada
    application.add_handler(ChatJoinRequestHandler(approve_join_request))
    
    # Executa bot
    logger.info("🚀 Bot do funil iniciado com sucesso!")
    logger.info("📱 Funcionalidades ativas:")
    logger.info("   ✅ Tracking UTM completo")
    logger.info("   ✅ Sistema PIX TriboPay")
    logger.info("   ✅ PostgreSQL integrado")
    logger.info("   ✅ Verificação de grupo")
    logger.info("   ✅ Aprovação automática (40s)")
    logger.info("   ✅ Galeria de prévias (7s delay)")
    logger.info("   ✅ Botões VIP integrados")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()