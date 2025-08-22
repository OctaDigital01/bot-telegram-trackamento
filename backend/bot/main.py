#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bot Telegram - Funil de Vendas com Tracking Completo
Conecta com API Gateway
Versão com Fluxo de Funil Otimizado, Remarketing e Aprovação em Background
Token Fix: 22/08/2025
"""
import os
import logging
import asyncio
import json
import base64
import httpx
from html import escape
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ChatJoinRequestHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest, Conflict

# Carregar variáveis do arquivo .env
load_dotenv()

# ==============================================================================
# 1. CONFIGURAÇÃO GERAL E INICIALIZAÇÃO
# ==============================================================================

# Variável global para controlar instância única
_BOT_INSTANCE = None

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
ADMIN_ID = int(os.getenv('ADMIN_ID', '0')) if os.getenv('ADMIN_ID') else None
GROUP_ID = int(os.getenv('GRUPO_GRATIS_ID', '0')) if os.getenv('GRUPO_GRATIS_ID') else None
GROUP_INVITE_LINK = os.getenv('GRUPO_GRATIS_INVITE_LINK')
GROUP_VIP_ID = int(os.getenv('GRUPO_VIP_ID', '0')) if os.getenv('GRUPO_VIP_ID') else None
GROUP_VIP_INVITE_LINK = os.getenv('GRUPO_VIP_INVITE_LINK')
SITE_ANA_CARDOSO = os.getenv('SITE_ANA_CARDOSO')
# =======================================================

# ======== FILE IDs DAS MÍDIAS ATUALIZADOS =============
MEDIA_APRESENTACAO = os.getenv('MEDIA_APRESENTACAO')
MEDIA_VIDEO_QUENTE = os.getenv('MEDIA_VIDEO_QUENTE')
MEDIA_PREVIA_SITE = os.getenv('MEDIA_PREVIA_SITE')
MEDIA_PROVOCATIVA = os.getenv('MEDIA_PROVOCATIVA')
# ====================================================

# ======== CONFIGURAÇÃO DOS PLANOS VIP =============
VIP_PLANS = {
    "plano_1": {"id": "plano_1mes", "nome": "ACESSO VIP COMPLETO", "valor": 24.90, "botao_texto": "💦 R$ 24,90 - ME VER SEM CENSURA"},
    "plano_2": {"id": "plano_3meses", "nome": "VIP + PACK ESPECIAL", "valor": 49.90, "botao_texto": "🔥 R$ 49,90 - TUDO + PACK EXCLUSIVO"},
    "plano_3": {"id": "plano_1ano", "nome": "ACESSO TOTAL + EU SÓ PRA VOCÊ", "valor": 67.00, "botao_texto": "💎 R$ 67,00 - SER MEU NAMORADO VIP"}
}
# ==================================================

# ======== CONFIGURAÇÃO DE REMARKETING E DESCONTO =============
REMARKETING_PLANS = {
    "plano_desc_etapa5": {"id": "plano_desc_etapa5", "nome": "VIP com Desconto (Remarketing)", "valor": 19.90, "botao_texto": "🤑 QUERO O VIP COM DESCONTO DE R$19,90"},
    "plano_desc_20_off": {"id": "plano_desc_20_off", "nome": "VIP com 20% OFF", "valor": 19.90, "botao_texto": "🤑 QUERO MEU DESCONTO DE 20% AGORA"}
}
# ==================================================

# ======== JUNÇÃO DE TODOS OS PLANOS PARA ACESSO RÁPIDO =============
TODOS_OS_PLANOS = {**VIP_PLANS, **REMARKETING_PLANS}
# =================================================================

# ======== CONFIGURAÇÃO DE DELAYS (NOVOS TEMPOS) =============
CONFIGURACAO_BOT = {
    "DELAYS": {
        "ETAPA_1_FALLBACK": 20,         # (20s) Se não clicar para entrar no grupo
        "ETAPA_2_FALLBACK": 20,         # (20s) Se não clicar para ver prévia
        "ETAPA_3_FALLBACK": 40,         # (40s) Se não clicar no "QUERO O VIP", envia remarketing
        "ETAPA_4_FALLBACK": 60,         # (1min) Se não escolher plano, envia desconto
        "APROVACAO_GRUPO_BG": 40,       # (40s) Tempo para aprovar a entrada no grupo em background
        "PIX_TIMEOUT": 3600,            # (60min) Tempo para expirar o PIX
    }
}
# ========================================================

# ======== CLIENTE HTTP ASSÍNCRONO =============
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(10.0, read=30.0),
    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
)
# ==============================================

# ==============================================================================
# 2. FUNÇÕES AUXILIARES E DE LÓGICA REUTILIZÁVEL
# ==============================================================================

#======== DELETA MENSAGEM ANTERIOR USANDO user_data (UNIFICADO) =============
async def delete_previous_message(context: ContextTypes.DEFAULT_TYPE, message_key: str):
    """
    Deleta uma mensagem anterior cujo ID está salvo em context.user_data.
    """
    if message_key in context.user_data:
        chat_id = context.user_data.get('chat_id')
        message_id = context.user_data[message_key]
        if chat_id and message_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"🗑️ Mensagem '{message_key}' (ID: {message_id}) deletada com sucesso.")
            except BadRequest as e:
                if "message to delete not found" in str(e).lower():
                    logger.warning(f"⚠️ Mensagem '{message_key}' (ID: {message_id}) já havia sido deletada.")
                else:
                    logger.warning(f"⚠️ Erro ao deletar mensagem '{message_key}' (ID: {message_id}): {e}")
            except Exception as e:
                logger.error(f"❌ Erro crítico ao deletar mensagem '{message_key}' (ID: {message_id}): {e}")
            finally:
                # Remove a chave independentemente do resultado para evitar tentativas futuras
                del context.user_data[message_key]
#================= FECHAMENTO ======================

async def verificar_pix_existente(user_id: int, plano_id: str):
    #======== VERIFICA SE JÁ EXISTE PIX VÁLIDO PARA O PLANO =============
    try:
        response = await http_client.get(f"{API_GATEWAY_URL}/api/pix/verificar/{user_id}/{plano_id}")
        if response.status_code == 200:
            result = response.json()
            if result.get('success') and result.get('pix_valido'):
                return result.get('pix_data')
    except Exception as e:
        logger.error(f"❌ Erro verificando PIX existente: {e}")
    return None
    #================= FECHAMENTO ======================

async def invalidar_pix_usuario(user_id: int):
    #======== INVALIDA TODOS OS PIX PENDENTES DO USUÁRIO =============
    try:
        response = await http_client.post(f"{API_GATEWAY_URL}/api/pix/invalidar/{user_id}")
        if response.status_code == 200:
            result = response.json()
            return result.get('success', False)
    except Exception as e:
        logger.error(f"❌ Erro invalidando PIX do usuário: {e}")
    return False
    #================= FECHAMENTO ======================

async def check_if_user_is_member(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    #======== VERIFICA SE USUÁRIO JÁ É MEMBRO DO GRUPO =============
    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.warning(f"⚠️ Erro verificando se usuário {user_id} é membro do grupo: {e}")
        return False
    #================= FECHAMENTO ======================

async def decode_tracking_data(encoded_param: str):
    #======== DECODIFICA DADOS DE TRACKING =============
    logger.info(f"🔍 Decodificando tracking: {encoded_param}")
    if not encoded_param or encoded_param.strip() == '':
        return {'utm_source': 'direct_bot', 'click_id': 'direct_access'}
    
    try:
        # Método 1: Base64 JSON
        try:
            decoded_bytes = base64.b64decode(encoded_param.encode('utf-8'))
            tracking_data = json.loads(decoded_bytes.decode('utf-8'))
            logger.info(f"✅ Tracking Base64 decodificado: {tracking_data}")
            return tracking_data
        except (json.JSONDecodeError, Exception):
            pass # Tenta o próximo método

        # Método 2: Formato :: separado
        if '::' in encoded_param:
            parts = encoded_param.split('::')
            tracking_data = {
                'utm_source': parts[0] if len(parts) > 0 and parts[0] else None,
                'click_id': parts[1] if len(parts) > 1 and parts[1] else None
            }
            tracking_data = {k: v for k, v in tracking_data.items() if v}
            logger.info(f"✅ Tracking :: formato decodificado: {tracking_data}")
            return tracking_data
        
        # Fallback: usa como click_id direto
        logger.info(f"⚠️ Usando fallback - click_id direto: {encoded_param}")
        return {'click_id': encoded_param}
        
    except Exception as e:
        logger.error(f"❌ Erro crítico decodificação: {e}")
        return {'click_id': encoded_param, 'utm_source': 'decode_error'}
    #================= FECHAMENTO ======================

async def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    #======== REMOVE UM JOB AGENDADO =============
    if not context.job_queue: return False
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs: return False
    for job in current_jobs:
        job.schedule_removal()
    return True
    #================= FECHAMENTO ======================

async def job_timeout_pix(context: ContextTypes.DEFAULT_TYPE):
    #======== JOB EXECUTADO APÓS TIMEOUT SEM PAGAMENTO =============
    job = context.job
    chat_id = job.chat_id
    user_id = job.user_id
    
    logger.info(f"⏰ TIMEOUT PIX: Executando para usuário {user_id}")
    
    try:
        if await invalidar_pix_usuario(user_id):
            logger.info(f"🗑️ PIX expirado invalidado para usuário {user_id}")
        
        texto_desconto_timeout = (
            "😳 <b>Opa, meu amor... vi que você não finalizou o pagamento!</b>\n\n"
            "💔 Sei que às vezes a gente fica na dúvida, né?\n\n"
            "🎁 <b>ÚLTIMA CHANCE:</b> Vou liberar um <b>DESCONTO ESPECIAL</b> só pra você!\n\n"
            "⚡ <b>20% OFF + Bônus Exclusivos!</b>\n\n"
            "🔥 <b>É AGORA OU NUNCA, amor...</b> 👇"
        )
        
        plano_desc = REMARKETING_PLANS["plano_desc_20_off"]
        keyboard = [[InlineKeyboardButton(plano_desc["botao_texto"], callback_data=f"plano:{plano_desc['id']}")]]
        
        await context.bot.send_message(
            chat_id=chat_id, 
            text=texto_desconto_timeout, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='HTML'
        )
        logger.info(f"✅ Mensagem de desconto especial enviada para {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro no timeout PIX para usuário {user_id}: {e}")
    #================= FECHAMENTO ======================

# ==============================================================================
# 3. LÓGICA DO FUNIL DE VENDAS (POR ETAPA)
# ==============================================================================

# ------------------------- ETAPA 1: BEM-VINDO E CONVITE GRUPO -------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GERENCIA O COMANDO /START =============
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    context.user_data.clear()
    context.user_data['chat_id'] = chat_id
    
    if await invalidar_pix_usuario(user.id):
        logger.info(f"🗑️ PIX anteriores do usuário {user.id} invalidados no /start")
    
    if 'user_chat_map' not in context.bot_data:
        context.bot_data['user_chat_map'] = {}
    context.bot_data['user_chat_map'][user.id] = chat_id
    
    logger.info(f"👤 ETAPA 1: Usuário {user.first_name} ({user.id}) iniciou o bot.")
    
    tracking_param = ' '.join(context.args) if context.args else ''
    tracking_data = await decode_tracking_data(tracking_param)
    logger.info(f"🎯 Tracking processado: {tracking_data}")
    
    try:
        user_data_payload = {
            'telegram_id': user.id,
            'username': user.username or user.first_name,
            'first_name': user.first_name,
            'last_name': user.last_name or '',
            'tracking_data': tracking_data
        }
        response = await http_client.post(f"{API_GATEWAY_URL}/api/users", json=user_data_payload)
        if response.status_code == 200 and response.json().get('success'):
            logger.info(f"✅ Usuário {user.id} salvo/atualizado na API")
        else:
            logger.error(f"❌ Erro salvando usuário {user.id}: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"❌ Erro crítico ao salvar usuário {user.id}: {e}")

    if await check_if_user_is_member(context, user.id):
        text = "Que bom te ver de volta, meu bem! 😍\n\nJá que você já tá no grupinho, que tal ver uns conteúdinhos especiais que preparei pra você? 🔥"
        keyboard = [[InlineKeyboardButton("VER CONTEÚDINHO 🥵", callback_data='trigger_etapa3')]]
        await context.bot.send_photo(chat_id=chat_id, photo=MEDIA_APRESENTACAO, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        context.job_queue.run_once(job_etapa3_galeria, CONFIGURACAO_BOT["DELAYS"]["ETAPA_2_FALLBACK"], chat_id=chat_id, name=f"job_etapa3_{chat_id}", data={'chat_id': chat_id})
    else:
        text = "Meu bem, entra no meu *GRUPINHO GRÁTIS* pra ver daquele jeito q vc gosta 🥵⬇️"
        keyboard = [[InlineKeyboardButton("ENTRAR NO GRUPO 🥵", url=GROUP_INVITE_LINK)]]
        await context.bot.send_photo(chat_id=chat_id, photo=MEDIA_APRESENTACAO, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        context.job_queue.run_once(job_etapa2_prompt_previa, CONFIGURACAO_BOT["DELAYS"]["ETAPA_1_FALLBACK"], chat_id=chat_id, name=f"job_etapa2_{chat_id}", data={'chat_id': chat_id})
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 1.5: PEDIDO DE ENTRADA NO GRUPO -------------------------
async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GERENCIA PEDIDOS DE ENTRADA NO GRUPO =============
    if update.chat_join_request.chat.id != GROUP_ID: return
    
    user_id = update.chat_join_request.from_user.id
    logger.info(f"🤝 Pedido de entrada no grupo recebido de {user_id}.")
    
    chat_id = context.bot_data.get('user_chat_map', {}).get(user_id)
    if not chat_id:
        logger.warning(f"⚠️ Chat_id não encontrado para {user_id}. Aprovação manual necessária.")
        return

    await remove_job_if_exists(f"job_etapa2_{chat_id}", context)
    
    text = "Jaja te aceito meu amor, mas antes que tal ver uns conteudinhos meus?? 👀"
    keyboard = [[InlineKeyboardButton("VER CONTEUDINHOS 🔥", callback_data='trigger_etapa3')]]
    msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['etapa2_msg'] = msg.message_id
    
    context.job_queue.run_once(job_etapa3_galeria, CONFIGURACAO_BOT["DELAYS"]["ETAPA_2_FALLBACK"], chat_id=chat_id, name=f"job_etapa3_{chat_id}", data={'chat_id': chat_id})
    context.job_queue.run_once(approve_user_callback, CONFIGURACAO_BOT["DELAYS"]["APROVACAO_GRUPO_BG"], user_id=user_id, name=f"approve_{user_id}", data={'user_id': user_id, 'chat_id': GROUP_ID})
    #================= FECHAMENTO ======================

async def approve_user_callback(context: ContextTypes.DEFAULT_TYPE):
    #======== APROVA O USUÁRIO NO GRUPO (JOB) =============
    job_data = context.job.data
    user_id = job_data['user_id']
    group_chat_id = job_data['chat_id']
    try:
        await context.bot.approve_chat_join_request(chat_id=group_chat_id, user_id=user_id)
        logger.info(f"✅ Aprovada entrada de {user_id} no grupo {group_chat_id}.")
    except Exception as e:
        logger.error(f"❌ Falha ao aprovar {user_id} no grupo {group_chat_id}: {e}")
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 2: PROMPT DE PRÉVIA -------------------------
async def job_etapa2_prompt_previa(context: ContextTypes.DEFAULT_TYPE):
    #======== ENVIA PERGUNTA SOBRE PRÉVIAS (FALLBACK) =============
    chat_id = context.job.data['chat_id']
    logger.info(f"⏰ ETAPA 2: Enviando prompt de prévia para {chat_id}.")
    
    text = "Quer ver um pedacinho do que te espera... 🔥 (É DE GRAÇA!!!) ⬇️"
    keyboard = [[InlineKeyboardButton("QUERO VER UMA PRÉVIA 🔥🥵", callback_data='trigger_etapa3')]]
    msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['etapa2_msg'] = msg.message_id
    
    context.job_queue.run_once(job_etapa3_galeria, CONFIGURACAO_BOT["DELAYS"]["ETAPA_2_FALLBACK"], chat_id=chat_id, name=f"job_etapa3_{chat_id}", data={'chat_id': chat_id})
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 3: GALERIA DE MÍDIAS E OFERTA VIP -------------------------
async def callback_trigger_etapa3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GATILHO MANUAL DA ETAPA 3 (CLIQUE NO BOTÃO) =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    
    logger.info(f"👤 ETAPA 3: Usuário {chat_id} clicou para ver prévias.")
    
    await remove_job_if_exists(f"job_etapa3_{chat_id}", context)
    await query.delete_message()
    
    await job_etapa3_galeria(context, chat_id_manual=chat_id)
    #================= FECHAMENTO ======================

async def job_etapa3_galeria(context: ContextTypes.DEFAULT_TYPE, chat_id_manual=None):
    #======== ENVIA GALERIA DE MÍDIAS E OFERTA VIP =============
    chat_id = chat_id_manual or context.job.data['chat_id']
    logger.info(f"⏰ ETAPA 3: Enviando galeria de mídias para {chat_id}.")
    
    await delete_previous_message(context, 'etapa2_msg')
    
    media_group = [
        InputMediaVideo(media=MEDIA_VIDEO_QUENTE),
        InputMediaPhoto(media=MEDIA_APRESENTACAO),
        InputMediaPhoto(media=MEDIA_PREVIA_SITE),
        InputMediaPhoto(media=MEDIA_PROVOCATIVA)
    ]
    await context.bot.send_media_group(chat_id=chat_id, media=media_group)
    
    text_vip = "Gostou do que viu, meu bem 🤭?\n\nTenho muito mais no VIP pra você (TOTALMENTE SEM CENSURA).\n\nVem gozar porra quentinha pra mim🥵💦⬇️"
    keyboard = [[InlineKeyboardButton("QUERO O VIP🔥", callback_data='trigger_etapa4')]]
    msg = await context.bot.send_message(chat_id=chat_id, text=text_vip, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['etapa3_msg'] = msg.message_id
    
    context.job_queue.run_once(job_etapa3_remarketing, CONFIGURACAO_BOT["DELAYS"]["ETAPA_3_FALLBACK"], chat_id=chat_id, name=f"job_etapa3_remarketing_{chat_id}", data={'chat_id': chat_id})
    #================= FECHAMENTO ======================

async def job_etapa3_remarketing(context: ContextTypes.DEFAULT_TYPE):
    #======== ENVIA MENSAGEM DE REMARKETING (FALLBACK DA ETAPA 3) =============
    chat_id = context.job.data['chat_id']
    logger.info(f"⏰ ETAPA 3 (FALLBACK): Enviando remarketing breve para {chat_id}.")
    
    await delete_previous_message(context, 'etapa3_msg')
    
    texto_remarketing = "Ei, amor... não some não. Tenho uma surpresinha pra você. Clica aqui pra gente continuar 🔥"
    keyboard = [[InlineKeyboardButton("CONTINUAR CONVERSANDO 🔥", callback_data='trigger_etapa4')]]
    await context.bot.send_message(chat_id=chat_id, text=texto_remarketing, reply_markup=InlineKeyboardMarkup(keyboard))
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 4: PLANOS VIP E DESCONTO -------------------------
async def callback_trigger_etapa4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GATILHO MANUAL DA ETAPA 4 (CLIQUE NO BOTÃO) =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    
    logger.info(f"👤 ETAPA 4: Usuário {chat_id} clicou para conhecer o VIP.")
    
    await remove_job_if_exists(f"job_etapa3_remarketing_{chat_id}", context)
    await query.delete_message()
    
    await job_etapa4_planos_vip(context, chat_id_manual=chat_id)
    #================= FECHAMENTO ======================
    
async def job_etapa4_planos_vip(context: ContextTypes.DEFAULT_TYPE, chat_id_manual=None):
    #======== MOSTRA OS PLANOS VIP =============
    chat_id = chat_id_manual or context.job.data['chat_id']
    logger.info(f"⏰ ETAPA 4: Enviando planos VIP para {chat_id}.")
    
    texto_planos = (
        "💋 <b>Agora vem a parte gostosa, meu amor...</b>\n\n"
        "🔥 No meu VIP você vai ter:\n"
        "• Vídeos completos SEM CENSURA\n"
        "• Fotos íntimas que só meus namorados veem\n"
        "• Chamadas privadas só eu e você\n"
        "• Meu WhatsApp pessoal (plano premium)\n\n"
        "😈 <b>Escolhe como você quer me ter:</b>"
    )
    keyboard = [[InlineKeyboardButton(p["botao_texto"], callback_data=f"plano:{p['id']}")] for p in VIP_PLANS.values()]
    msg = await context.bot.send_message(chat_id=chat_id, text=texto_planos, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    context.user_data['etapa4_msg'] = msg.message_id
    
    context.job_queue.run_once(job_etapa4_desconto, CONFIGURACAO_BOT["DELAYS"]["ETAPA_4_FALLBACK"], chat_id=chat_id, name=f"job_etapa4_desconto_{chat_id}", data={'chat_id': chat_id})
    #================= FECHAMENTO ======================

async def job_etapa4_desconto(context: ContextTypes.DEFAULT_TYPE):
    #======== OFERECE DESCONTO (FALLBACK DA ETAPA 4) =============
    chat_id = context.job.data['chat_id']
    logger.info(f"⏰ ETAPA 4 (FALLBACK): Oferecendo desconto para {chat_id}.")
    
    await delete_previous_message(context, 'etapa4_msg')
    
    texto_desconto = "Ei, meu bem... vi que você ficou na dúvida. 🤔\n\nPra te ajudar a decidir, liberei um <b>desconto especial SÓ PRA VOCÊ</b>. Mas corre que é por tempo limitado! 👇"
    plano_desc = REMARKETING_PLANS["plano_desc_20_off"]
    keyboard = [[InlineKeyboardButton(plano_desc["botao_texto"], callback_data=f"plano:{plano_desc['id']}")]]
    await context.bot.send_message(chat_id=chat_id, text=texto_desconto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 5: PROCESSAMENTO DO PAGAMENTO -------------------------
async def callback_processar_plano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== PROCESSA PAGAMENTO DO PLANO SELECIONADO =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    await remove_job_if_exists(f"job_etapa4_desconto_{chat_id}", context)
    await query.delete_message()
    
    plano_id = query.data.split(":")[1]
    plano_selecionado = next((p for p in TODOS_OS_PLANOS.values() if p["id"] == plano_id), None)

    if not plano_selecionado: 
        logger.warning(f"⚠️ Plano '{plano_id}' não encontrado para {user_id}.")
        await context.bot.send_message(chat_id, "❌ Ops! Ocorreu um erro. Por favor, tente novamente.")
        return

    # Lógica para reutilizar ou gerar novo PIX
    pix_existente = await verificar_pix_existente(user_id, plano_id)
    if pix_existente:
        logger.info(f"♻️ Reutilizando PIX para {user_id} - Plano: {plano_selecionado['nome']}")
        await enviar_mensagem_pix(context, chat_id, user_id, plano_selecionado, pix_existente, is_reused=True)
    else:
        logger.info(f"💳 Gerando PIX NOVO para {user_id} - Plano: {plano_selecionado['nome']}")
        msg_loading = await context.bot.send_message(chat_id=chat_id, text="💎 Gerando seu PIX... aguarde! ⏳")
        context.user_data['loading_msg'] = msg_loading.message_id
        try:
            pix_data = {
                'user_id': user_id, 'valor': plano_selecionado['valor'], 'plano_id': plano_id,
                'customer': {'name': query.from_user.full_name, 'email': f'user{user_id}@telegram.bot'}
            }
            response = await http_client.post(f"{API_GATEWAY_URL}/api/pix/gerar", json=pix_data)
            response.raise_for_status()
            result = response.json()
            if not result.get('success') or not result.get('pix_copia_cola'):
                raise Exception(f"API PIX retornou erro ou dados incompletos: {result.get('error', 'Erro desconhecido')}")
            
            await delete_previous_message(context, 'loading_msg')
            await enviar_mensagem_pix(context, chat_id, user_id, plano_selecionado, result)
        except Exception as e:
            logger.error(f"❌ Erro CRÍTICO ao processar pagamento para {user_id}: {e}")
            await delete_previous_message(context, 'loading_msg')
            await context.bot.send_message(chat_id, "❌ Um erro inesperado ocorreu. Por favor, tente novamente mais tarde.")
    #================= FECHAMENTO ======================

async def enviar_mensagem_pix(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, plano: dict, pix_data: dict, is_reused: bool = False):
    #======== ENVIA A MENSAGEM COM O QR CODE E DADOS DO PIX =============
    pix_copia_cola = pix_data['pix_copia_cola']
    qr_code_url = pix_data.get('qr_code') or f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_copia_cola}"
    
    caption = (
        f"💎 <b>Seu PIX está aqui, meu amor!</b>\n\n"
        f"📸 <b>Pague utilizando o QR Code</b>\n"
        f"💸 <b>Pague por Pix copia e cola:</b>\n"
        f"<blockquote><code>{escape(pix_copia_cola)}</code></blockquote>"
        f"<i>(Clique para copiar)</i>\n\n"
        f"🎯 <b>Plano:</b> {escape(plano['nome'])}\n"
        f"💰 <b>Valor: R$ {plano['valor']:.2f}</b>"
    )
    keyboard = [
        [InlineKeyboardButton("✅ JÁ PAGUEI", callback_data=f"ja_paguei:{plano['id']}")],
        [InlineKeyboardButton("🔄 ESCOLHER OUTRO PLANO", callback_data="escolher_outro_plano")]
    ]
    
    try:
        await context.bot.send_photo(chat_id=chat_id, photo=qr_code_url, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    except Exception as e:
        logger.error(f"❌ Falha ao enviar foto do QR Code para {user_id}: {e}. Enviando fallback.")
        await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # Agenda o job de timeout
    await remove_job_if_exists(f"timeout_pix_{user_id}", context)
    timeout_seconds = CONFIGURACAO_BOT["DELAYS"]["PIX_TIMEOUT"]
    if is_reused:
        try:
            tempo_restante_str = pix_data.get('tempo_restante', '60')
            timeout_seconds = int(tempo_restante_str.split()[0]) * 60 if tempo_restante_str != '??' else timeout_seconds
        except (ValueError, IndexError):
            logger.warning("Não foi possível parsear o tempo restante do PIX reutilizado.")

    context.job_queue.run_once(job_timeout_pix, timeout_seconds, chat_id=chat_id, user_id=user_id, name=f"timeout_pix_{user_id}")
    logger.info(f"⏰ Job de timeout PIX agendado para {user_id} em {timeout_seconds/60:.0f} minutos.")
    #================= FECHAMENTO ======================

async def callback_ja_paguei(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== HANDLER PARA BOTÃO "JÁ PAGUEI" =============
    query = update.callback_query
    await query.answer("Ótimo! Estamos processando seu pagamento.", show_alert=False)
    user_id = query.from_user.id
    
    await remove_job_if_exists(f"timeout_pix_{user_id}", context)
    logger.info(f"⏰ Job de timeout PIX cancelado para {user_id} após confirmação de pagamento.")
    
    texto_confirmacao = (
        "🎉 <b>Perfeito, meu amor!</b>\n\n"
        "Seu pagamento já está sendo processado! ⚡\n\n"
        "📱 <b>Assim que for aprovado, você receberá o acesso ao grupo VIP aqui mesmo.</b>\n\n"
        "⏰ <i>Geralmente demora apenas alguns segundos...</i>"
    )
    await query.message.edit_caption(caption=texto_confirmacao, parse_mode='HTML')
    #================= FECHAMENTO ======================

async def callback_escolher_outro_plano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== HANDLER PARA BOTÃO "ESCOLHER OUTRO PLANO" =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    logger.info(f"🔄 Usuário {user_id} quer escolher outro plano")
    
    await query.delete_message()
    
    if await invalidar_pix_usuario(user_id):
        logger.info(f"🗑️ PIX anterior invalidado para {user_id}.")
    
    await remove_job_if_exists(f"timeout_pix_{user_id}", context)
    
    texto_upgrade = (
        "💎 <b>Ótima escolha, amor!</b>\n\n"
        "🔥 <b>Quem pega o plano mais completo sempre agradece depois!</b>\n"
        "• Muito mais conteúdo exclusivo\n"
        "• Contato direto e prioridade\n\n"
        "💰 <b>E o custo-benefício é MUITO melhor!</b>\n\n"
        "<b>Qual você quer escolher agora?</b> 👇"
    )
    keyboard = [[InlineKeyboardButton(p["botao_texto"], callback_data=f"plano:{p['id']}")] for p in VIP_PLANS.values()]
    await context.bot.send_message(chat_id=chat_id, text=texto_upgrade, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    #================= FECHAMENTO ======================

# ==============================================================================
# 4. FUNÇÃO PRINCIPAL E EXECUÇÃO DO BOT
# ==============================================================================
async def main():
    #======== INICIALIZA E EXECUTA O BOT DE FORMA ASSÍNCRONA =============
    global _BOT_INSTANCE
    
    if _BOT_INSTANCE:
        logger.warning("⚠️ Bot já está rodando, abortando nova instância.")
        return
    
    required_vars = ['TELEGRAM_BOT_TOKEN', 'API_GATEWAY_URL', 'GRUPO_GRATIS_ID', 'GRUPO_GRATIS_INVITE_LINK']
    if any(not os.getenv(var) for var in required_vars):
        logger.critical("❌ ERRO CRÍTICO: Variáveis de ambiente obrigatórias não configuradas.")
        return
        
    logger.info("🤖 === BOT COM FUNIL OTIMIZADO INICIANDO ===")
    
    application = Application.builder().token(BOT_TOKEN).build()
    _BOT_INSTANCE = application
    
    # Registra os handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(CallbackQueryHandler(callback_trigger_etapa3, pattern='^trigger_etapa3$'))
    application.add_handler(CallbackQueryHandler(callback_trigger_etapa4, pattern='^trigger_etapa4$'))
    application.add_handler(CallbackQueryHandler(callback_processar_plano, pattern='^plano:'))
    application.add_handler(CallbackQueryHandler(callback_ja_paguei, pattern='^ja_paguei:'))
    application.add_handler(CallbackQueryHandler(callback_escolher_outro_plano, pattern='^escolher_outro_plano$'))
    
    try:
        logger.info("🚀 Bot pronto para iniciar o polling...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            allowed_updates=['message', 'callback_query', 'chat_join_request'],
            drop_pending_updates=True
        )
        logger.info("✅ Bot online e recebendo atualizações.")
        # Mantém o script rodando indefinidamente
        await asyncio.Event().wait()

    except Conflict as e:
        logger.error(f"❌ CONFLITO: Outra instância do bot pode estar rodando. {e}")
    except Exception as e:
        logger.critical(f"❌ Erro fatal na execução do bot: {e}", exc_info=True)
    finally:
        logger.info("🛑 Encerrando o bot...")
        if application.updater and application.updater.is_running():
            await application.updater.stop()
        if application:
            await application.stop()
            await application.shutdown()
        if http_client:
            await http_client.aclose()
            logger.info("🔒 Cliente HTTP encerrado.")
        _BOT_INSTANCE = None
        logger.info("✅ Bot encerrado com sucesso.")
#================= FECHAMENTO ======================

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Execução interrompida pelo usuário.")
