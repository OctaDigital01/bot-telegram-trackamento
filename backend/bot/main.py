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

# Configurações dos grupos
GROUP_ID = int(os.getenv('GRUPO_GRATIS_ID', '-1002777277040'))  # Grupo Grátis
GROUP_VIP_ID = int(os.getenv('GRUPO_VIP_ID', '-1002727792561'))  # Grupo VIP
GROUP_INVITE_LINK = os.getenv('GRUPO_GRATIS_INVITE_LINK', 'https://t.me/+iydDH1RTDPJlNTNh')
GROUP_VIP_INVITE_LINK = os.getenv('GRUPO_VIP_INVITE_LINK', 'hevG7NzA27YyNzgx')

# Admin e configurações gerais
ADMIN_ID = int(os.getenv('ADMIN_ID', '908005914'))
SITE_ANA_CARDOSO = os.getenv('SITE_ANA_CARDOSO', 'https://ana-cardoso.shop')

# File IDs das mídias - NOVOS (21/08/2025)
MEDIA_VIDEO_QUENTE = os.getenv('MEDIA_VIDEO_QUENTE', 'BAACAgEAAxkDAAIOLWinfTqfJ4SEWvCrHda68K9h70KKAAIbBwACMQFBRR_rsl9biH1zNgQ')
MEDIA_APRESENTACAO = os.getenv('MEDIA_APRESENTACAO', 'AgACAgEAAxkDAAIOLminfTr7EFz35tBWIMbepmJyuBDDAAIyrTEbMQFBRYIVHNrbPu82AQADAgADeQADNgQ')
MEDIA_PREVIA_SITE = os.getenv('MEDIA_PREVIA_SITE', 'AgACAgEAAxkDAAIOL2infTsn8XIZPi9hbE1NpNIaKXiMAAIzrTEbMQFBRR63yONsxlHEAQADAgADeQADNgQ')
MEDIA_PROVOCATIVA = os.getenv('MEDIA_PROVOCATIVA', 'AgACAgEAAxkDAAIOMGinfTyHJB6WxE3A09JJOsfrAonRAAI4rTEbMQFBRVDGNhpvLgs0AQADAgADeQADNgQ')
MEDIA_VIDEO_SEDUCAO = os.getenv('MEDIA_VIDEO_SEDUCAO', 'BAACAgEAAxkDAAIOLWinfTqfJ4SEWvCrHda68K9h70KKAAIbBwACMQFBRR_rsl9biH1zNgQ')  # Mesmo vídeo do QUENTE

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
    user_id = query.from_user.id

    # Marca que usuário viu prévias manualmente (cancela envio automático)
    usuarios_viram_previews.add(user_id)

    logger.info(f"Enviando Etapa 3 (Prévias) manualmente para o chat {chat_id}")

    # Tenta enviar media group, se falhar envia mensagens individuais
    try:
        media_group = [
            InputMediaVideo(media=MEDIA_VIDEO_QUENTE),
            InputMediaPhoto(media=MEDIA_APRESENTACAO),
            InputMediaPhoto(media=MEDIA_PREVIA_SITE),
            InputMediaPhoto(media=MEDIA_PROVOCATIVA),
        ]
        
        await context.bot.send_media_group(chat_id=chat_id, media=media_group)
        logger.info(f"✅ Media group enviado com sucesso")
    except Exception as e:
        logger.warning(f"⚠️ Erro enviando media group: {e}")
        await context.bot.send_message(chat_id, "🔥 Galeria de prévias (mídias não disponíveis)")
    
    # Espera 7 segundos
    await asyncio.sleep(7)

    await context.bot.send_message(
        chat_id=chat_id,
        text="Gostou do que viu, meu bem 🤭?"
    )
    
    text2 = """
Tenho muito mais no VIP pra você (TOTALMENTE SEM CENSURA):
💎 Vídeos e fotos do jeitinho que você gosta...
💎 Videos exclusivo pra você, te fazendo go.zar só eu e você
💎 Meu contato pessoal
💎 Sempre posto coisa nova lá
💎 E muito mais meu bem...

Vem goz.ar po.rra quentinha pra mim🥵💦⬇️"""

    keyboard = [[InlineKeyboardButton("CONHECER O VIP🔥", callback_data='quero_vip')]]
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
        
        # Tracking preservado silenciosamente (não envia mensagem para o usuário)
        if tracking_data:
            logger.info(f"✅ Tracking preservado silenciosamente para usuário {user.id}: {tracking_data}")
        
        text = "Meu bem, que bom te ver de novo! 🔥 Clica aqui pra não perder as novidades quentes que preparei pra você! ⬇️"
        keyboard = [[InlineKeyboardButton("VER CONTEÚDINHO DE GRAÇA 🔥🥵", callback_data='step3_previews')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Tenta enviar com foto, se falhar envia só texto
        try:
            await update.message.reply_photo(
                photo=MEDIA_APRESENTACAO,
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
        # Tracking preservado silenciosamente (não envia detalhes para o usuário)
        if tracking_data:
            logger.info(f"✅ Tracking capturado silenciosamente para usuário {user.id}: {tracking_data}")
        text = "Meu bem, entra no meu *GRUPINHO GRÁTIS* pra ver daquele jeito q vc gosta 🥵⬇️"
    else:
        logger.info(f"Usuário {user.id} é novo.")
        text = "Meu bem, entra no meu *GRUPINHO GRÁTIS* pra ver daquele jeito q vc gosta 🥵⬇️"

    keyboard = [[InlineKeyboardButton("MEU GRUPINHO🥵?", url=GROUP_INVITE_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Tenta enviar com foto, se falhar envia só texto
    try:
        await update.message.reply_photo(
            photo=MEDIA_APRESENTACAO,
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
    
    # Inicia timer de 15s para enviar prévias automaticamente
    asyncio.create_task(enviar_previews_automatico(context, update.effective_chat.id, user.id))
    logger.info(f"⏰ Timer de 15s iniciado para usuário {user.id}")

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

# ===== SISTEMA VIP COMPLETO - BASEADO NO SCRIPT FORNECIDO =====

# Caches para controle do fluxo
usuarios_viram_midias = set()
usuarios_viram_previews = set()  # Controla quem já viu as prévias automaticamente
pix_cache = {}
mensagens_pix = {}

async def enviar_previews_automatico(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int):
    """Envia prévias automaticamente após 15s se usuário não entrou no grupo"""
    try:
        # Aguarda 15 segundos
        await asyncio.sleep(15)
        
        # Verifica se usuário já viu as prévias (manual ou automaticamente)
        if user_id in usuarios_viram_previews:
            logger.info(f"⏭️ Usuário {user_id} já viu prévias, cancelando envio automático")
            return
            
        # Verifica se usuário entrou no grupo durante os 15s
        try:
            chat_member = await context.bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
            is_in_group = chat_member.status in ['member', 'administrator', 'creator']
            if is_in_group:
                logger.info(f"⏭️ Usuário {user_id} entrou no grupo, cancelando envio automático")
                return
        except Exception:
            pass  # Usuário não está no grupo, continua com o envio
            
        # Marca que usuário viu prévias automaticamente
        usuarios_viram_previews.add(user_id)
        
        logger.info(f"⏰ Enviando prévias automaticamente para usuário {user_id} após 15s")
        
        # Envia as 4 mídias
        try:
            media_group = [
                InputMediaVideo(media=MEDIA_VIDEO_QUENTE),
                InputMediaPhoto(media=MEDIA_APRESENTACAO),
                InputMediaPhoto(media=MEDIA_PREVIA_SITE),
                InputMediaPhoto(media=MEDIA_PROVOCATIVA),
            ]
            
            await context.bot.send_media_group(chat_id=chat_id, media=media_group)
            logger.info(f"✅ Media group automático enviado para {user_id}")
        except Exception as e:
            logger.warning(f"⚠️ Erro enviando media group automático: {e}")
            await context.bot.send_message(chat_id, "🔥 Galeria de prévias (mídias não disponíveis)")
        
        # Espera 7 segundos
        await asyncio.sleep(7)

        await context.bot.send_message(
            chat_id=chat_id,
            text="Gostou do que viu, meu bem 🤭?"
        )
        
        text2 = """
Tenho muito mais no VIP pra você (TOTALMENTE SEM CENSURA):
💎 Vídeos e fotos do jeitinho que você gosta...
💎 Videos exclusivo pra você, te fazendo go.zar só eu e você
💎 Meu contato pessoal
💎 Sempre posto coisa nova lá
💎 E muito mais meu bem...

Vem goz.ar po.rra quentinha pra mim🥵💦⬇️"""

        keyboard = [[InlineKeyboardButton("CONHECER O VIP🔥", callback_data='quero_vip')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=chat_id,
            text=text2,
            reply_markup=reply_markup
        )
        
        logger.info(f"✅ Sequência completa de prévias automáticas enviada para {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro no envio automático de prévias para {user_id}: {e}")

async def callback_quero_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para quando o usuário clica em 'QUERO ACESSO VIP' - mostra planos"""
    query = update.callback_query
    await query.answer()
    
    if not query.from_user:
        logger.error("❌ callback_quero_vip: query.from_user é None")
        return
    
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    
    logger.info(f"💎 INÍCIO callback_quero_vip para usuário {user_id}")
    
    try:
        # Apaga a mensagem atual (botão CONHECER O VIP)
        try:
            await query.message.delete()
            logger.info(f"🗑️ Mensagem anterior apagada para {user_id}")
        except Exception as del_err:
            logger.warning(f"⚠️ Erro ao deletar mensagem atual: {del_err}")

        # Envio da mensagem com os planos VIP (sem mídias)
        texto_planos = """Essas são só PRÉVIAS borradas do que te espera bb... 😈💦

No VIP você vai ver TUDO sem censura, vídeos completos de mim gozando, chamadas privadas e muito mais!

<b>Escolhe o seu acesso especial:</b>

📢 <b>ATENÇÃO:</b> Apenas 5 vagas restantes! Depois que esgotar, só na próxima semana!"""
        
        keyboard = [
            [InlineKeyboardButton("💦 R$ 24,90 - ACESSO VIP", callback_data="plano_1mes")],
            [InlineKeyboardButton("🔥 R$ 49,90 - VIP + BRINDES", callback_data="plano_3meses")],
            [InlineKeyboardButton("💎 R$ 67,00 - TUDO + CONTATO DIRETO", callback_data="plano_1ano")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=texto_planos,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        logger.info(f"✅ Mensagem de planos enviada para {user_id}")
            
    except Exception as e:
        logger.error(f"❌ ERRO GERAL em callback_quero_vip para {user_id}: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Ops, algo deu errado! Tente novamente.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 TENTAR NOVAMENTE", callback_data="quero_vip")]])
        )

async def processar_pagamento_plano(update: Update, context: ContextTypes.DEFAULT_TYPE, plano: str, valor: float):
    """Processa a geração de PIX para um plano VIP específico"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    chat_id = query.message.chat_id
    
    logger.info(f"💳 Gerando PIX para {user_name} ({user_id}) - Plano: {plano} - R$ {valor}")
    
    # Deleta a mensagem anterior (dos planos) e mostra um aviso de carregamento
    await query.message.delete()
    msg_loading = await context.bot.send_message(chat_id=chat_id, text="💎 Gerando seu PIX... aguarde! ⏳")
    
    try:
        # Geração do PIX via API Gateway (mantém integração existente)
        pix_data = {
            'user_id': user_id,
            'valor': valor,
            'plano': plano
        }
        
        response = requests.post(f"{API_GATEWAY_URL}/api/pix/gerar", json=pix_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                await msg_loading.delete()  # Apaga a mensagem "Gerando PIX..."
                
                pix_copia_cola = result['pix_copia_cola']
                qr_code = result.get('qr_code')  # URL do QR Code da TriboPay
                transaction_id = result.get('transaction_id', f"tx_{user_id}_{int(datetime.now().timestamp())}")
                
                # Monta o texto da mensagem (igual ao script fornecido)
                from html import escape
                codigo_html_seguro = escape(pix_copia_cola)
                info_plano = f"💎 <b><u>Plano VIP</u></b> ({plano})\n💰 Valor: <b>R$ {valor:.2f}</b>"
                
                caption_completa = f"""📸 <b>Pague utilizando o QR Code</b>
💸 <b>Pague por Pix copia e cola:</b>
<blockquote><code>{codigo_html_seguro}</code></blockquote><i>(Clique no código para copiar)</i>
🎯 <b>Detalhes do Plano:</b>
{info_plano}
<b>Promoção Válida por 15 minutos!</b>"""
                
                # Monta os botões de ação
                keyboard_botoes = [
                    [InlineKeyboardButton("✅ Já Paguei", callback_data=f"ja_paguei:{transaction_id}")],
                    [InlineKeyboardButton("🔄 Escolher Outro Plano", callback_data="quero_vip")]
                ]
                reply_markup_botoes = InlineKeyboardMarkup(keyboard_botoes)

                # Envia com QR Code como imagem se disponível
                if qr_code:
                    try:
                        logger.info(f"🎯 Tentando enviar QR Code: {qr_code}")
                        msg_enviada = await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=qr_code,
                            caption=caption_completa,
                            parse_mode='HTML',
                            reply_markup=reply_markup_botoes
                        )
                        logger.info(f"✅ PIX enviado com QR Code como imagem para {user_id}")
                    except Exception as photo_err:
                        logger.warning(f"⚠️ Erro enviando QR Code como foto: {photo_err}")
                        # Fallback para mensagem de texto
                        msg_enviada = await context.bot.send_message(
                            chat_id=chat_id,
                            text=caption_completa,
                            parse_mode='HTML',
                            reply_markup=reply_markup_botoes
                        )
                        logger.info(f"✅ PIX enviado como texto (fallback) para {user_id}")
                else:
                    # Gera QR Code a partir do PIX copia e cola usando API externa
                    try:
                        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_copia_cola}"
                        logger.info(f"🎯 Gerando QR Code externo: {qr_url}")
                        msg_enviada = await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=qr_url,
                            caption=caption_completa,
                            parse_mode='HTML',
                            reply_markup=reply_markup_botoes
                        )
                        logger.info(f"✅ PIX enviado com QR Code gerado externamente para {user_id}")
                    except Exception as qr_err:
                        logger.warning(f"⚠️ Erro gerando QR Code externo: {qr_err}")
                        # Fallback final para mensagem de texto
                        msg_enviada = await context.bot.send_message(
                            chat_id=chat_id,
                            text=caption_completa,
                            parse_mode='HTML',
                            reply_markup=reply_markup_botoes
                        )
                        logger.info(f"✅ PIX enviado como texto (fallback final) para {user_id}")
                
                # Armazena o ID da mensagem para controle
                if user_id not in mensagens_pix: 
                    mensagens_pix[user_id] = []
                mensagens_pix[user_id].append(msg_enviada.message_id)
                logger.info(f"💎 Mensagem PIX enviada para {user_id}")
                
            else:
                await msg_loading.delete()
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Erro ao gerar seu PIX. Por favor, tente novamente.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 TENTAR NOVAMENTE", callback_data="quero_vip")]])
                )
        else:
            await msg_loading.delete()
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Erro na comunicação com gateway de pagamento",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 TENTAR NOVAMENTE", callback_data="quero_vip")]])
            )
            
    except Exception as e:
        logger.error(f"❌ Erro CRÍTICO ao processar pagamento para {user_id}: {e}")
        try:
            await msg_loading.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Um erro inesperado ocorreu. Tente novamente.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 TENTAR NOVAMENTE", callback_data="quero_vip")]])
        )

# Handlers para cada plano específico
async def callback_plano_1mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await processar_pagamento_plano(update, context, "ACESSO VIP", 24.90)

async def callback_plano_3meses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await processar_pagamento_plano(update, context, "VIP + BRINDES", 49.90)

async def callback_plano_1ano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await processar_pagamento_plano(update, context, "TUDO + CONTATO DIRETO", 67.00)

# Handler para "Já Paguei"
async def callback_ja_paguei(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    # Extrai o transaction_id do callback_data
    transaction_id = query.data.split(":")[1] if ":" in query.data else "unknown"
    
    logger.info(f"✅ Usuário {user_id} clicou 'Já Paguei' - Transaction: {transaction_id}")
    
    await query.edit_message_text(
        "✅ Obrigada! Estou verificando seu pagamento...\n\n"
        "📱 Você receberá uma mensagem assim que o pagamento for confirmado!\n\n"
        "💎 Em poucos minutos você terá acesso ao VIP completo!"
    )

# Função para old callback (compatibilidade)
async def vip_options_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback compatibilidade - redireciona para novo sistema"""
    await callback_quero_vip(update, context)

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
    
    # Novos handlers do sistema VIP
    application.add_handler(CallbackQueryHandler(callback_quero_vip, pattern='^quero_vip$'))
    application.add_handler(CallbackQueryHandler(callback_plano_1mes, pattern='^plano_1mes$'))
    application.add_handler(CallbackQueryHandler(callback_plano_3meses, pattern='^plano_3meses$'))
    application.add_handler(CallbackQueryHandler(callback_plano_1ano, pattern='^plano_1ano$'))
    application.add_handler(CallbackQueryHandler(callback_ja_paguei, pattern='^ja_paguei:'))
    
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