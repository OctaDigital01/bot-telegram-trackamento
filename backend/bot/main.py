#!/usr/bin/env python3
"""
Bot Telegram - Funil de Vendas com Tracking Completo
Conecta com API Gateway
Versão com Fluxo de Funil, Remarketing e Aprovação Automática no Grupo
"""

import os
import logging
import asyncio
import json
import base64
import httpx
from datetime import datetime
from cachetools import TTLCache
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, ChatJoinRequest
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ChatJoinRequestHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest
from html import escape

# ==============================================================================
# 1. CONFIGURAÇÃO GERAL E INICIALIZAÇÃO
# ==============================================================================

# ======== CONFIGURAÇÃO DE LOGGING =============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
# ==============================================

# ======== VARIÁVEIS DE AMBIENTE (CRÍTICAS) =============
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_GATEWAY_URL = os.getenv('API_GATEWAY_URL')
GROUP_ID = int(os.getenv('GRUPO_GRATIS_ID')) if os.getenv('GRUPO_GRATIS_ID') else None # ID numérico do grupo grátis
GROUP_INVITE_LINK = os.getenv('GRUPO_GRATIS_INVITE_LINK')
# =======================================================

# ======== FILE IDs DAS MÍDIAS =============
MEDIA_APRESENTACAO = os.getenv('MEDIA_APRESENTACAO')
MEDIA_VIDEO_QUENTE = os.getenv('MEDIA_VIDEO_QUENTE')
MEDIA_PREVIA_SITE = os.getenv('MEDIA_PREVIA_SITE')
MEDIA_PROVOCATIVA = os.getenv('MEDIA_PROVOCATIVA')
# ==========================================

# ======== CONFIGURAÇÃO DOS PLANOS VIP =============
VIP_PLANS = {
    "plano_1": {"id": "plano_1mes", "nome": "ACESSO VIP", "valor": 24.90, "botao_texto": "💦 R$ 24,90 - ACESSO VIP"},
    "plano_2": {"id": "plano_3meses", "nome": "VIP + BRINDES", "valor": 49.90, "botao_texto": "🔥 R$ 49,90 - VIP + BRINDES"},
    "plano_3": {"id": "plano_1ano", "nome": "TUDO + CONTATO DIRETO", "valor": 67.00, "botao_texto": "💎 R$ 67,00 - TUDO + CONTATO DIRETO"}
}
# ==================================================

# ======== CONFIGURAÇÃO DE REMARKETING =============
REMARKETING_PLAN = {
    "plano_desc": {"id": "plano_desc", "nome": "VIP com Desconto", "valor": 19.90, "botao_texto": "🤑 QUERO O VIP COM DESCONTO DE R$19,90"}
}
# ==================================================

# ======== CONFIGURAÇÃO DE DELAYS E TIMEOUTS =============
CONFIGURACAO_BOT = {
    "DELAYS": {
        "ETAPA_2_PROMPT_PREVIA": 2,       # (2s) Tempo para enviar o prompt de prévia (fallback)
        "ETAPA_3_GALERIA": 5,             # (5s) Tempo para enviar a galeria de mídias
        "ETAPA_4_PLANOS_VIP": 30,         # (30s) Tempo para enviar os planos VIP
        "ETAPA_5_REMARKETING": 300,       # (5min) Tempo para enviar a oferta de remarketing
        "APROVACAO_GRUPO_BG": 5,          # (5s) Tempo para aprovar a entrada no grupo em background
    }
}
# ========================================================

# ======== INICIALIZAÇÃO DE CACHES =============
tracking_cache = TTLCache(maxsize=1000, ttl=14400)
usuarios_salvos = TTLCache(maxsize=2000, ttl=7200)
# ===============================================

# ======== CLIENTE HTTP ASSÍNCRONO =============
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(10.0, read=30.0),
    limits=httpx.Limits(max_keepalive_connections=3, max_connections=5, keepalive_expiry=30.0)
)
# ==============================================

# ==============================================================================
# 2. FUNÇÕES AUXILIARES E DE LÓGICA REUTILIZÁVEL
# ==============================================================================

async def decode_tracking_data(encoded_param: str):
    #======== DECODIFICA DADOS DE TRACKING =============
    if encoded_param in tracking_cache: return tracking_cache[encoded_param]
    try:
        if encoded_param.startswith('M') and len(encoded_param) <= 12:
            try:
                response = await http_client.get(f"{API_GATEWAY_URL}/api/tracking/get/{encoded_param}")
                if response.status_code == 200 and response.json().get('success'):
                    original_data = json.loads(response.json()['original'])
                    tracking_cache[encoded_param] = original_data
                    return original_data
            except Exception as e: logger.error(f"❌ Erro API tracking: {e}")
            result = {'click_id': encoded_param}; tracking_cache[encoded_param] = result; return result
        try:
            decoded_bytes = base64.b64decode(encoded_param.encode('utf-8'))
            tracking_data = json.loads(decoded_bytes.decode('utf-8'))
            tracking_cache[encoded_param] = tracking_data
            return tracking_data
        except Exception:
            if '::' in encoded_param:
                parts = encoded_param.split('::')
                tracking_data = {k: v for k, v in {'utm_source': parts[0] if len(parts) > 0 else None, 'click_id': parts[1] if len(parts) > 1 else None, 'utm_medium': parts[2] if len(parts) > 2 else None, 'utm_campaign': parts[3] if len(parts) > 3 else None, 'utm_term': parts[4] if len(parts) > 4 else None, 'utm_content': parts[5] if len(parts) > 5 else None}.items() if v}
                tracking_cache[encoded_param] = tracking_data
                return tracking_data
        result = {'click_id': encoded_param}; tracking_cache[encoded_param] = result; return result
    except Exception as e:
        logger.error(f"❌ Erro decodificação: {e}")
        return {'click_id': encoded_param}
    #================= FECHAMENTO ======================

async def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    #======== REMOVE UM JOB AGENDADO =============
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs: return False
    for job in current_jobs:
        job.schedule_removal()
    return True
    #================= FECHAMENTO ======================

async def delete_message_if_exists(context: ContextTypes.DEFAULT_TYPE, key: str):
    #======== DELETA MENSAGEM ANTERIOR =============
    if key in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data['chat_id'], message_id=context.user_data[key])
        except BadRequest as e:
            logger.warning(f"Não foi possível deletar a mensagem {context.user_data[key]}: {e}")
        del context.user_data[key]
    #================= FECHAMENTO ======================

# ==============================================================================
# 3. LÓGICA DO FUNIL DE VENDAS (POR ETAPA)
# ==============================================================================

# ------------------------- ETAPA 1: BEM-VINDO -------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GERENCIA O COMANDO /START =============
    user = update.effective_user
    chat_id = update.effective_chat.id
    context.user_data['chat_id'] = chat_id
    
    # Armazena o mapeamento de user_id para chat_id para uso posterior
    if 'user_chat_map' not in context.bot_data:
        context.bot_data['user_chat_map'] = {}
    context.bot_data['user_chat_map'][user.id] = chat_id
    
    logger.info(f"👤 ETAPA 1: Usuário {user.first_name} ({user.id}) iniciou o bot.")
    
    tracking_data = await decode_tracking_data(' '.join(context.args)) if context.args else {'utm_source': 'direct_bot', 'click_id': 'direct'}
    if f"user_{user.id}" not in usuarios_salvos:
        try:
            user_data = {'telegram_id': user.id, 'username': user.username or user.first_name, 'first_name': user.first_name, 'last_name': user.last_name or '', 'tracking_data': tracking_data}
            await http_client.post(f"{API_GATEWAY_URL}/api/users", json=user_data)
            usuarios_salvos[f"user_{user.id}"] = True
        except Exception as e: logger.error(f"❌ Erro ao salvar usuário {user.id}: {e}")

    text = "Meu bem, entra no meu *GRUPINHO GRÁTIS* pra ver daquele jeito q vc gosta 🥵⬇️"
    keyboard = [[InlineKeyboardButton("ENTRAR NO GRUPO 🥵", url=GROUP_INVITE_LINK)]]
    await context.bot.send_photo(chat_id=chat_id, photo=MEDIA_APRESENTACAO, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

    # Agenda a próxima etapa caso o usuário não solicite entrada no grupo
    context.job_queue.run_once(job_etapa2_prompt_previa, CONFIGURACAO_BOT["DELAYS"]["ETAPA_2_PROMPT_PREVIA"], chat_id=chat_id, name=f"job_etapa2_{chat_id}")
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 1.5: PEDIDO DE ENTRADA NO GRUPO (HANDLER) -------------------------
async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GERENCIA PEDIDOS DE ENTRADA NO GRUPO =============
    if update.chat_join_request.chat.id != GROUP_ID: return

    user_id = update.chat_join_request.from_user.id
    logger.info(f"🤝 Pedido de entrada recebido de {user_id}.")

    user_chat_map = context.bot_data.get('user_chat_map', {})
    chat_id = user_chat_map.get(user_id)

    if chat_id:
        logger.info(f"Avançando funil para {user_id} (chat_id: {chat_id}) após pedido de entrada.")
        
        # 1. Cancela o job de fallback de 15 segundos
        await remove_job_if_exists(f"job_etapa2_{chat_id}", context)
        
        # 2. Dispara a próxima etapa do funil imediatamente
        context.job_queue.run_once(job_etapa2_prompt_previa, 0, chat_id=chat_id, name=f"job_etapa2_{chat_id}_imediato")
        
        # 3. Agenda a aprovação para ocorrer em background
        context.job_queue.run_once(
            approve_user_callback, 
            CONFIGURACAO_BOT["DELAYS"]["APROVACAO_GRUPO_BG"],
            chat_id=GROUP_ID, 
            user_id=user_id,
            name=f"approve_{user_id}"
        )
    else:
        logger.warning(f"Não foi possível encontrar o chat_id para o usuário {user_id}. A aprovação deverá ser manual.")
    #================= FECHAMENTO ======================

async def approve_user_callback(context: ContextTypes.DEFAULT_TYPE):
    #======== APROVA O USUÁRIO (JOB) =============
    job = context.job
    try:
        await context.bot.approve_chat_join_request(chat_id=job.chat_id, user_id=job.user_id)
        logger.info(f"✅ Aprovada entrada de {job.user_id} no grupo {job.chat_id}.")
    except Exception as e:
        logger.error(f"❌ Falha ao aprovar usuário {job.user_id} no grupo {job.chat_id}: {e}")
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 2: PROMPT DE PRÉVIA -------------------------
async def job_etapa2_prompt_previa(context: ContextTypes.DEFAULT_TYPE):
    #======== ENVIA PERGUNTA SOBRE PRÉVIAS =============
    chat_id = context.job.chat_id
    logger.info(f"⏰ ETAPA 2: Enviando prompt de prévia para {chat_id}.")
    text = "Quer ver um pedacinho do que te espera... 🔥 (É DE GRAÇA!!!) ⬇️"
    keyboard = [[InlineKeyboardButton("QUERO VER UMA PRÉVIA 🔥🥵", callback_data='trigger_etapa3')]]
    msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['etapa2_msg_id'] = msg.message_id
    
    context.job_queue.run_once(job_etapa3_galeria, CONFIGURACAO_BOT["DELAYS"]["ETAPA_3_GALERIA"], chat_id=chat_id, name=f"job_etapa3_{chat_id}")
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 3: GALERIA DE MÍDIAS E OFERTA VIP -------------------------
async def callback_trigger_etapa3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GATILHO MANUAL DA ETAPA 3 =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    logger.info(f"👤 ETAPA 3: Usuário {chat_id} clicou para ver prévias.")
    await remove_job_if_exists(f"job_etapa3_{chat_id}", context)
    await delete_message_if_exists(context, 'etapa2_msg_id')
    await job_etapa3_galeria(context, chat_id_manual=chat_id)
    #================= FECHAMENTO ======================

async def job_etapa3_galeria(context: ContextTypes.DEFAULT_TYPE, chat_id_manual=None):
    #======== ENVIA GALERIA DE MÍDIAS E OFERTA VIP =============
    chat_id = chat_id_manual or context.job.chat_id
    logger.info(f"⏰ ETAPA 3: Enviando galeria de mídias para {chat_id}.")
    await delete_message_if_exists(context, 'etapa2_msg_id')
    
    media_group = [InputMediaVideo(media=MEDIA_VIDEO_QUENTE), InputMediaPhoto(media=MEDIA_APRESENTACAO), InputMediaPhoto(media=MEDIA_PREVIA_SITE), InputMediaPhoto(media=MEDIA_PROVOCATIVA)]
    await context.bot.send_media_group(chat_id=chat_id, media=media_group)
    
    text_vip = "Gostou do que viu, meu bem 🤭?\n\nTenho muito mais no VIP pra você (TOTALMENTE SEM CENSURA).\n\nVem gozar porra quentinha pra mim🥵💦⬇️"
    keyboard = [[InlineKeyboardButton("CONHECER O VIP🔥", callback_data='trigger_etapa4')]]
    msg = await context.bot.send_message(chat_id=chat_id, text=text_vip, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['etapa3_msg_id'] = msg.message_id

    context.job_queue.run_once(job_etapa4_planos_vip, CONFIGURACAO_BOT["DELAYS"]["ETAPA_4_PLANOS_VIP"], chat_id=chat_id, name=f"job_etapa4_{chat_id}")
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 4: PLANOS VIP -------------------------
async def callback_trigger_etapa4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GATILHO MANUAL DA ETAPA 4 =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    logger.info(f"👤 ETAPA 4: Usuário {chat_id} clicou para conhecer o VIP.")
    await remove_job_if_exists(f"job_etapa4_{chat_id}", context)
    await delete_message_if_exists(context, 'etapa3_msg_id')
    await job_etapa4_planos_vip(context, chat_id_manual=chat_id)
    #================= FECHAMENTO ======================
    
async def job_etapa4_planos_vip(context: ContextTypes.DEFAULT_TYPE, chat_id_manual=None):
    #======== MOSTRA OS PLANOS VIP =============
    chat_id = chat_id_manual or context.job.chat_id
    logger.info(f"⏰ ETAPA 4: Enviando planos VIP para {chat_id}.")
    await delete_message_if_exists(context, 'etapa3_msg_id')

    texto_planos = "No VIP você vai ver TUDO sem censura, vídeos completos de mim gozando, chamadas privadas e muito mais!\n\n<b>Escolhe o seu acesso especial:</b>"
    keyboard = [[InlineKeyboardButton(p["botao_texto"], callback_data=f"plano:{p['id']}")] for p in VIP_PLANS.values()]
    msg = await context.bot.send_message(chat_id=chat_id, text=texto_planos, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    context.user_data['etapa4_msg_id'] = msg.message_id

    context.job_queue.run_once(job_etapa5_remarketing, CONFIGURACAO_BOT["DELAYS"]["ETAPA_5_REMARKETING"], chat_id=chat_id, name=f"job_etapa5_{chat_id}")
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 5: REMARKETING E PAGAMENTO -------------------------
async def job_etapa5_remarketing(context: ContextTypes.DEFAULT_TYPE):
    #======== ENVIA OFERTA DE REMARKETING =============
    chat_id = context.job.chat_id
    logger.info(f"⏰ ETAPA 5: Enviando remarketing para {chat_id}.")
    await delete_message_if_exists(context, 'etapa4_msg_id')
    
    texto_remarketing = "Ei, meu bem... vi que você ficou na dúvida. 🤔\n\nPra te ajudar a decidir, liberei um <b>desconto especial SÓ PRA VOCÊ</b>. Mas corre que é por tempo limitado! 👇"
    plano_desc = list(REMARKETING_PLAN.values())[0]
    keyboard = [[InlineKeyboardButton(plano_desc["botao_texto"], callback_data=f"plano:{plano_desc['id']}")] ]
    await context.bot.send_message(chat_id=chat_id, text=texto_remarketing, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    #================= FECHAMENTO ======================

async def callback_processar_plano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== PROCESSA PAGAMENTO DO PLANO =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    await remove_job_if_exists(f"job_etapa5_{chat_id}", context)
    await delete_message_if_exists(context, 'etapa4_msg_id')
    
    plano_id = query.data.split(":")[1]
    plano = next((p for p in list(VIP_PLANS.values()) + list(REMARKETING_PLAN.values()) if p["id"] == plano_id), None)
    if not plano: return

    logger.info(f"💳 Gerando PIX para {user_id} - Plano: {plano['nome']}")
    msg_loading = await context.bot.send_message(chat_id=chat_id, text="💎 Gerando seu PIX... aguarde! ⏳")
    
    try:
        pix_data = {'user_id': user_id, 'valor': plano['valor'], 'plano': plano['nome']}
        response = await http_client.post(f"{API_GATEWAY_URL}/api/pix/gerar", json=pix_data)
        if not (response.status_code == 200 and response.json().get('success')):
            raise Exception(f"API PIX falhou: {response.status_code}")
        
        result = response.json()
        await msg_loading.delete()
        
        pix_copia_cola = result['pix_copia_cola']
        qr_code_url = result.get('qr_code') or f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_copia_cola}"
        
        caption = f"📸 <b>Pague utilizando o QR Code</b>\n💸 <b>Pague por Pix copia e cola:</b>\n<blockquote><code>{escape(pix_copia_cola)}</code></blockquote><i>(Clique para copiar)</i>\n🎯 <b>Plano:</b> {escape(plano['nome'])}\n💰 <b>Valor: R$ {plano['valor']:.2f}</b>"
        await context.bot.send_photo(chat_id=chat_id, photo=qr_code_url, caption=caption, parse_mode='HTML')
    except Exception as e:
        logger.error(f"❌ Erro CRÍTICO ao processar pagamento para {user_id}: {e}")
        await msg_loading.edit_text("❌ Um erro inesperado ocorreu. Tente novamente mais tarde.")
    #================= FECHAMENTO ======================

# ==============================================================================
# 4. FUNÇÃO PRINCIPAL E EXECUÇÃO DO BOT
# ==============================================================================

def main():
    #======== INICIALIZA E EXECUTA O BOT =============
    required_vars = ['TELEGRAM_BOT_TOKEN', 'API_GATEWAY_URL', 'GRUPO_GRATIS_ID', 'GRUPO_GRATIS_INVITE_LINK', 'MEDIA_APRESENTACAO', 'MEDIA_VIDEO_QUENTE', 'MEDIA_PREVIA_SITE', 'MEDIA_PROVOCATIVA']
    if any(not os.getenv(var) for var in required_vars):
        logger.critical(f"❌ ERRO CRÍTICO: Variáveis de ambiente obrigatórias não configuradas.")
        return

    logger.info("🤖 === BOT COM FLUXO COMPLETO E APROVAÇÃO AUTOMÁTICA INICIANDO ===")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Registra os handlers de comando, callbacks e pedidos de entrada
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(CallbackQueryHandler(callback_trigger_etapa3, pattern='^trigger_etapa3$'))
    application.add_handler(CallbackQueryHandler(callback_trigger_etapa4, pattern='^trigger_etapa4$'))
    application.add_handler(CallbackQueryHandler(callback_processar_plano, pattern='^plano:'))
    
    logger.info("🚀 Bot iniciado com sucesso!")
    
    try:
        # Adicionado 'chat_join_request' aos updates permitidos
        application.run_polling(allowed_updates=['message', 'callback_query', 'chat_join_request'])
    finally:
        asyncio.run(http_client.aclose())
        logger.info("🔒 Cliente HTTP fechado.")
    #================= FECHAMENTO ======================

if __name__ == '__main__':
    main()
