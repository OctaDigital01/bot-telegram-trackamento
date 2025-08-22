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
from datetime import datetime, timedelta
from html import escape
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ChatJoinRequestHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest

# Carregar variáveis do arquivo .env
load_dotenv()

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
    "plano_1": {"id": "plano_1mes", "nome": "ACESSO VIP", "valor": 24.90, "botao_texto": "💦 R$ 24,90 - ACESSO VIP"},
    "plano_2": {"id": "plano_3meses", "nome": "VIP + BRINDES", "valor": 49.90, "botao_texto": "🔥 R$ 49,90 - VIP + BRINDES"},
    "plano_3": {"id": "plano_1ano", "nome": "TUDO + CONTATO DIRETO", "valor": 67.00, "botao_texto": "💎 R$ 67,00 - TUDO + CONTATO DIRETO"}
}
# ==================================================

# ======== CONFIGURAÇÃO DE REMARKETING E DESCONTO =============
REMARKETING_PLANS = {
    "plano_desc_etapa5": {"id": "plano_desc_etapa5", "nome": "VIP com Desconto (Remarketing)", "valor": 19.90, "botao_texto": "🤑 QUERO O VIP COM DESCONTO DE R$19,90"},
    "plano_desc_20_off": {"id": "plano_desc_20_off", "nome": "VIP com 20% OFF", "valor": 19.90, "botao_texto": "🤑 QUERO MEU DESCONTO DE 20% AGORA"}
}
# ==================================================

# ======== CONFIGURAÇÃO DE DELAYS (NOVOS TEMPOS) =============
CONFIGURACAO_BOT = {
    "DELAYS": {
        "ETAPA_1_FALLBACK": 20,         # (20s) Se não clicar para entrar no grupo
        "ETAPA_2_FALLBACK": 20,         # (20s) Se não clicar para ver prévia
        "ETAPA_3_FALLBACK": 40,         # (40s) Se não clicar no "QUERO O VIP", envia remarketing
        "ETAPA_4_FALLBACK": 60,         # (1min) Se não escolher plano, envia desconto
        "APROVACAO_GRUPO_BG": 40,       # (40s) Tempo para aprovar a entrada no grupo em background
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
        # Verifica se o usuário é membro ativo (não foi removido ou saiu)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.warning(f"⚠️ Erro verificando se usuário {user_id} é membro do grupo: {e}")
        return False
    #================= FECHAMENTO ======================

async def decode_tracking_data(encoded_param: str):
    #======== DECODIFICA DADOS DE TRACKING =============
    logger.info(f"🔍 Decodificando tracking: {encoded_param}")
    
    # Se o parâmetro estiver vazio, tenta buscar último tracking disponível
    if not encoded_param or encoded_param.strip() == '':
        try:
            response = await http_client.get(f"{API_GATEWAY_URL}/api/tracking/latest")
            if response.status_code == 200 and response.json().get('success'):
                latest_data = json.loads(response.json()['original'])
                logger.info(f"✅ Usando último tracking disponível: {latest_data}")
                return latest_data
        except Exception as e:
            logger.error(f"❌ Erro buscando último tracking: {e}")
        return {'utm_source': 'direct_bot', 'click_id': 'direct_access'}
    
    try:
        # Método 1: ID mapeado (começa com M e tem até 12 caracteres)
        if encoded_param.startswith('M') and len(encoded_param) <= 12:
            try:
                response = await http_client.get(f"{API_GATEWAY_URL}/api/tracking/get/{encoded_param}")
                if response.status_code == 200 and response.json().get('success'):
                    original_data = json.loads(response.json()['original'])
                    logger.info(f"✅ Tracking mapeado recuperado: {original_data}")
                    return original_data
                else:
                    logger.warning(f"⚠️ Tracking mapeado não encontrado: {encoded_param}")
            except Exception as e:
                logger.error(f"❌ Erro API tracking mapeado: {e}")
            return {'click_id': encoded_param}
        
        # Método 2: Base64 JSON
        try:
            decoded_bytes = base64.b64decode(encoded_param.encode('utf-8'))
            tracking_data = json.loads(decoded_bytes.decode('utf-8'))
            logger.info(f"✅ Tracking Base64 decodificado: {tracking_data}")
            return tracking_data
        except Exception:
            # Método 3: Formato :: separado (Xtracky)
            if '::' in encoded_param:
                parts = encoded_param.split('::')
                tracking_data = {
                    'utm_source': parts[0] if len(parts) > 0 and parts[0] else None,
                    'click_id': parts[1] if len(parts) > 1 and parts[1] else None,
                    'utm_medium': parts[2] if len(parts) > 2 and parts[2] else None,
                    'utm_campaign': parts[3] if len(parts) > 3 and parts[3] else None,
                    'utm_term': parts[4] if len(parts) > 4 and parts[4] else None,
                    'utm_content': parts[5] if len(parts) > 5 and parts[5] else None
                }
                # Remove valores None ou vazios
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

async def delete_message_if_exists(context: ContextTypes.DEFAULT_TYPE, key: str, allow_delete: bool = True):
    #======== DELETA MENSAGEM ANTERIOR USANDO user_data =============
    if not allow_delete:
        # Se não é permitido deletar, apenas limpa a chave
        if key in context.user_data:
            del context.user_data[key]
        return
        
    if key in context.user_data:
        chat_id = context.user_data.get('chat_id')
        message_id = context.user_data[key]
        if chat_id and message_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except BadRequest as e:
                logger.warning(f"⚠️ Não foi possível deletar a mensagem {message_id} no chat {chat_id}: {e}")
            finally:
                del context.user_data[key] # Limpa a chave após a tentativa
    #================= FECHAMENTO ======================

async def delete_message_if_exists_bot_data(context: ContextTypes.DEFAULT_TYPE, key: str, chat_id: int, allow_delete: bool = True):
    #======== DELETA MENSAGEM ANTERIOR USANDO bot_data =============
    if not allow_delete:
        # Se não é permitido deletar, apenas limpa a chave
        if 'message_ids' in context.bot_data and key in context.bot_data['message_ids']:
            del context.bot_data['message_ids'][key]
        return
        
    if 'message_ids' in context.bot_data and key in context.bot_data['message_ids']:
        message_id = context.bot_data['message_ids'][key]
        if message_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except BadRequest as e:
                logger.warning(f"⚠️ Não foi possível deletar a mensagem {message_id} no chat {chat_id}: {e}")
            finally:
                del context.bot_data['message_ids'][key] # Limpa a chave após a tentativa
    #================= FECHAMENTO ======================

# ==============================================================================
# 3. LÓGICA DO FUNIL DE VENDAS (POR ETAPA)
# ==============================================================================

# ------------------------- ETAPA 1: BEM-VINDO E CONVITE GRUPO -------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GERENCIA O COMANDO /START =============
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Limpa dados de um fluxo anterior para garantir um começo novo
    context.user_data.clear()
    context.user_data['chat_id'] = chat_id
    
    # Mapeia user_id para chat_id para o ChatJoinRequestHandler
    if 'user_chat_map' not in context.bot_data:
        context.bot_data['user_chat_map'] = {}
    context.bot_data['user_chat_map'][user.id] = chat_id
    
    logger.info(f"👤 ETAPA 1: Usuário {user.first_name} ({user.id}) iniciou o bot.")
    
    # Decodifica e salva dados de tracking
    tracking_param = ' '.join(context.args) if context.args else ''
    tracking_data = await decode_tracking_data(tracking_param)
    
    logger.info(f"🎯 Tracking processado: {tracking_data}")
    
    # Verifica se o usuário já é membro do grupo
    is_member = await check_if_user_is_member(context, user.id)
    logger.info(f"👥 Usuário {user.id} já é membro do grupo: {is_member}")
    
    try:
        user_data_payload = {
            'telegram_id': user.id,
            'username': user.username or user.first_name,
            'first_name': user.first_name,
            'last_name': user.last_name or '',
            'tracking_data': tracking_data
        }
        
        logger.info(f"📤 Enviando dados para API: {user_data_payload}")
        response = await http_client.post(f"{API_GATEWAY_URL}/api/users", json=user_data_payload)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                logger.info(f"✅ Usuário {user.id} salvo com sucesso na API")
            else:
                logger.error(f"❌ API retornou erro: {result}")
        else:
            logger.error(f"❌ Erro HTTP salvando usuário {user.id}: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Erro crítico salvando usuário {user.id}: {e}")

    if is_member:
        # Usuário já é membro - fluxo alternativo
        text = "Que bom te ver de volta, meu bem! 😍\n\nJá que você já tá no grupinho, que tal ver uns conteúdinhos especiais que preparei pra você? 🔥"
        keyboard = [[InlineKeyboardButton("VER CONTEÚDINHO 🥵", callback_data='trigger_etapa3')]]
        await context.bot.send_photo(chat_id=chat_id, photo=MEDIA_APRESENTACAO, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        
        # Agenda direto a Etapa 3 como fallback
        context.job_queue.run_once(job_etapa3_galeria, CONFIGURACAO_BOT["DELAYS"]["ETAPA_2_FALLBACK"], chat_id=chat_id, name=f"job_etapa3_{chat_id}")
    else:
        # Usuário novo - fluxo normal
        text = "Meu bem, entra no meu *GRUPINHO GRÁTIS* pra ver daquele jeito q vc gosta 🥵⬇️"
        keyboard = [[InlineKeyboardButton("ENTRAR NO GRUPO 🥵", url=GROUP_INVITE_LINK)]]
        await context.bot.send_photo(chat_id=chat_id, photo=MEDIA_APRESENTACAO, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        
        # Agenda a próxima etapa (fallback) caso o usuário não solicite entrada no grupo
        context.job_queue.run_once(job_etapa2_prompt_previa, CONFIGURACAO_BOT["DELAYS"]["ETAPA_1_FALLBACK"], chat_id=chat_id, name=f"job_etapa2_{chat_id}")
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 1.5: PEDIDO DE ENTRADA NO GRUPO (HANDLER) -------------------------
async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GERENCIA PEDIDOS DE ENTRADA NO GRUPO =============
    if update.chat_join_request.chat.id != GROUP_ID: return
    
    user_id = update.chat_join_request.from_user.id
    logger.info(f"🤝 Pedido de entrada no grupo recebido de {user_id}.")
    
    chat_id = context.bot_data.get('user_chat_map', {}).get(user_id)
    if not chat_id:
        logger.warning(f"⚠️ Não foi possível encontrar o chat_id para o usuário {user_id}. A aprovação deverá ser manual.")
        return

    logger.info(f"✅ Avançando funil para {user_id} (chat_id: {chat_id}) após pedido de entrada.")
    
    # 1. Cancela o job de fallback da Etapa 1, que chamaria a Etapa 2 padrão.
    await remove_job_if_exists(f"job_etapa2_{chat_id}", context)
    
    # 2. Envia a nova mensagem personalizada com o botão para ver os conteúdos.
    text = "Jaja te aceito meu amor, mas antes que tal ver uns conteudinhos meus?? 👀"
    keyboard = [[InlineKeyboardButton("VER CONTEUDINHOS 🔥", callback_data='trigger_etapa3')]]
    msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['etapa2_msg_id'] = msg.message_id # Salva ID para poder deletar depois
    
    # 3. Agenda a Etapa 3 (Galeria) como fallback, caso o usuário não clique no botão em 20s.
    context.job_queue.run_once(job_etapa3_galeria, CONFIGURACAO_BOT["DELAYS"]["ETAPA_2_FALLBACK"], chat_id=chat_id, name=f"job_etapa3_{chat_id}")

    # 4. Agenda a aprovação no grupo para ocorrer em background.
    context.job_queue.run_once(
        approve_user_callback, 
        CONFIGURACAO_BOT["DELAYS"]["APROVACAO_GRUPO_BG"],
        chat_id=GROUP_ID, 
        user_id=user_id,
        name=f"approve_{user_id}"
    )
    #================= FECHAMENTO ======================

async def approve_user_callback(context: ContextTypes.DEFAULT_TYPE):
    #======== APROVA O USUÁRIO NO GRUPO (JOB) =============
    job = context.job
    try:
        await context.bot.approve_chat_join_request(chat_id=job.chat_id, user_id=job.user_id)
        logger.info(f"✅ Aprovada entrada de {job.user_id} no grupo {job.chat_id}.")
    except Exception as e:
        logger.error(f"❌ Falha ao aprovar usuário {job.user_id} no grupo {job.chat_id}: {e}")
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 2: PROMPT DE PRÉVIA ("VER CONTEUDINHO") -------------------------
async def job_etapa2_prompt_previa(context: ContextTypes.DEFAULT_TYPE):
    #======== ENVIA PERGUNTA SOBRE PRÉVIAS =============
    chat_id = context.job.chat_id
    
    logger.info(f"⏰ ETAPA 2: Enviando prompt de prévia para {chat_id}.")
    text = "Quer ver um pedacinho do que te espera... 🔥 (É DE GRAÇA!!!) ⬇️"
    keyboard = [[InlineKeyboardButton("QUERO VER UMA PRÉVIA 🔥🥵", callback_data='trigger_etapa3')]]
    
    msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Salva o ID da mensagem no bot_data para poder deletar depois
    if 'message_ids' not in context.bot_data:
        context.bot_data['message_ids'] = {}
    context.bot_data['message_ids'][f'etapa2_{chat_id}'] = msg.message_id
    
    # Agenda a próxima etapa (fallback)
    context.job_queue.run_once(job_etapa3_galeria, CONFIGURACAO_BOT["DELAYS"]["ETAPA_2_FALLBACK"], chat_id=chat_id, name=f"job_etapa3_{chat_id}")
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 3: GALERIA DE MÍDIAS E OFERTA VIP -------------------------
async def callback_trigger_etapa3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== GATILHO MANUAL DA ETAPA 3 (CLIQUE NO BOTÃO) =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    
    logger.info(f"👤 ETAPA 3: Usuário {chat_id} clicou para ver prévias.")
    
    # Remove o fallback e a mensagem anterior, depois avança
    await remove_job_if_exists(f"job_etapa3_{chat_id}", context)
    await delete_message_if_exists(context, 'etapa2_msg_id')
    await job_etapa3_galeria(context, chat_id_manual=chat_id)
    #================= FECHAMENTO ======================

async def job_etapa3_galeria(context: ContextTypes.DEFAULT_TYPE, chat_id_manual=None):
    #======== ENVIA GALERIA DE MÍDIAS E OFERTA VIP =============
    chat_id = chat_id_manual or context.job.chat_id

    logger.info(f"⏰ ETAPA 3: Enviando galeria de mídias para {chat_id}.")
    
    # Deleta mensagem anterior se existir
    await delete_message_if_exists_bot_data(context, f'etapa2_{chat_id}', chat_id)
    
    # Envia as 4 mídias
    media_group = [
        InputMediaVideo(media=MEDIA_VIDEO_QUENTE),
        InputMediaPhoto(media=MEDIA_APRESENTACAO),
        InputMediaPhoto(media=MEDIA_PREVIA_SITE),
        InputMediaPhoto(media=MEDIA_PROVOCATIVA)
    ]
    await context.bot.send_media_group(chat_id=chat_id, media=media_group)
    
    # Envia o texto da oferta VIP
    text_vip = "Gostou do que viu, meu bem 🤭?\n\nTenho muito mais no VIP pra você (TOTALMENTE SEM CENSURA).\n\nVem gozar porra quentinha pra mim🥵💦⬇️"
    keyboard = [[InlineKeyboardButton("QUERO O VIP🔥", callback_data='trigger_etapa4')]]
    msg = await context.bot.send_message(chat_id=chat_id, text=text_vip, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Salva o ID da mensagem no bot_data
    if 'message_ids' not in context.bot_data:
        context.bot_data['message_ids'] = {}
    context.bot_data['message_ids'][f'etapa3_{chat_id}'] = msg.message_id
    
    # Agenda o remarketing (fallback)
    context.job_queue.run_once(job_etapa3_remarketing, CONFIGURACAO_BOT["DELAYS"]["ETAPA_3_FALLBACK"], chat_id=chat_id, name=f"job_etapa3_remarketing_{chat_id}")
    #================= FECHAMENTO ======================

async def job_etapa3_remarketing(context: ContextTypes.DEFAULT_TYPE):
    #======== ENVIA MENSAGEM DE REMARKETING (FALLBACK DA ETAPA 3) =============
    chat_id = context.job.chat_id
    logger.info(f"⏰ ETAPA 3 (FALLBACK): Enviando remarketing breve para {chat_id}.")
    
    # NÃO deleta a oferta anterior (mantém histórico das primeiras etapas)
    await delete_message_if_exists_bot_data(context, f'etapa3_{chat_id}', chat_id, allow_delete=False)
    
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
    
    # Remove o fallback mas NÃO deleta mensagem anterior (mantém histórico)
    await remove_job_if_exists(f"job_etapa3_remarketing_{chat_id}", context)
    await delete_message_if_exists_bot_data(context, f'etapa3_{chat_id}', chat_id, allow_delete=False)
    await job_etapa4_planos_vip(context, chat_id_manual=chat_id)
    #================= FECHAMENTO ======================
    
async def job_etapa4_planos_vip(context: ContextTypes.DEFAULT_TYPE, chat_id_manual=None):
    #======== MOSTRA OS PLANOS VIP =============
    chat_id = chat_id_manual or context.job.chat_id

    logger.info(f"⏰ ETAPA 4: Enviando planos VIP para {chat_id}.")
    
    texto_planos = "No VIP você vai ver TUDO sem censura, vídeos completos de mim gozando, chamadas privadas e muito mais!\n\n<b>Escolhe o seu acesso especial:</b>"
    keyboard = [[InlineKeyboardButton(p["botao_texto"], callback_data=f"plano:{p['id']}")] for p in VIP_PLANS.values()]
    
    msg = await context.bot.send_message(chat_id=chat_id, text=texto_planos, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    # Salva o ID da mensagem no bot_data
    if 'message_ids' not in context.bot_data:
        context.bot_data['message_ids'] = {}
    context.bot_data['message_ids'][f'etapa4_{chat_id}'] = msg.message_id
    
    # Agenda a oferta de desconto (fallback)
    context.job_queue.run_once(job_etapa4_desconto, CONFIGURACAO_BOT["DELAYS"]["ETAPA_4_FALLBACK"], chat_id=chat_id, name=f"job_etapa4_desconto_{chat_id}")
    #================= FECHAMENTO ======================

async def job_etapa4_desconto(context: ContextTypes.DEFAULT_TYPE):
    #======== OFERECE DESCONTO DE 20% (FALLBACK DA ETAPA 4) =============
    chat_id = context.job.chat_id
    logger.info(f"⏰ ETAPA 4 (FALLBACK): Oferecendo desconto de 20% para {chat_id}.")
    
    # NÃO deleta mensagem anterior (mantém histórico das primeiras etapas)
    await delete_message_if_exists_bot_data(context, f'etapa4_{chat_id}', chat_id, allow_delete=False)
    
    texto_desconto = "Ei, meu bem... vi que você ficou na dúvida. 🤔\n\nPra te ajudar a decidir, liberei um <b>desconto especial de 20% SÓ PRA VOCÊ</b>. Mas corre que é por tempo limitado! 👇"
    plano_desc = REMARKETING_PLANS["plano_desc_20_off"]
    keyboard = [[InlineKeyboardButton(plano_desc["botao_texto"], callback_data=f"plano:{plano_desc['id']}")] ]
    
    await context.bot.send_message(chat_id=chat_id, text=texto_desconto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    #================= FECHAMENTO ======================

# ------------------------- ETAPA 5: PROCESSAMENTO DO PAGAMENTO -------------------------
async def callback_processar_plano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== PROCESSA PAGAMENTO DO PLANO SELECIONADO =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    # Remove o job de desconto, pois o usuário já escolheu um plano
    await remove_job_if_exists(f"job_etapa4_desconto_{chat_id}", context)
    # AGORA SIM deleta mensagens anteriores - chegamos na etapa VIP!
    await delete_message_if_exists_bot_data(context, f'etapa4_{chat_id}', chat_id, allow_delete=True)
    
    plano_id = query.data.split(":")[1]
    
    # Junta todos os planos disponíveis (normais e de remarketing) para procurar
    todos_os_planos = {**VIP_PLANS, **REMARKETING_PLANS}
    plano_selecionado = next((p for p in todos_os_planos.values() if p["id"] == plano_id), None)

    if not plano_selecionado: 
        logger.warning(f"⚠️ Plano com id '{plano_id}' não encontrado para o usuário {user_id}.")
        return

    # Verificar se já existe PIX válido para este plano (dentro de 1h)
    pix_existente = await verificar_pix_existente(user_id, plano_id)
    if pix_existente:
        logger.info(f"♻️ Reutilizando PIX existente para {user_id} - Plano: {plano_selecionado['nome']}")
        
        pix_copia_cola = pix_existente['pix_copia_cola']
        qr_code_url = pix_existente.get('qr_code') or f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_copia_cola}"
        
        caption = (
            f"♻️ <b>PIX Reutilizado (Válido por mais {pix_existente.get('tempo_restante', '??')} min)</b>\n\n"
            f"📸 <b>Pague utilizando o QR Code</b>\n"
            f"💸 <b>Pague por Pix copia e cola:</b>\n"
            f"<blockquote><code>{escape(pix_copia_cola)}</code></blockquote>"
            f"<i>(Clique para copiar)</i>\n"
            f"🎯 <b>Plano:</b> {escape(plano_selecionado['nome'])}\n"
            f"💰 <b>Valor: R$ {plano_selecionado['valor']:.2f}</b>"
        )
        
        # Botões de ação
        keyboard = [
            [InlineKeyboardButton("✅ JÁ PAGUEI", callback_data=f"ja_paguei:{plano_id}")],
            [InlineKeyboardButton("🔄 ESCOLHER OUTRO PLANO", callback_data="escolher_outro_plano")]
        ]
        
        await context.bot.send_photo(chat_id=chat_id, photo=qr_code_url, caption=caption, 
                                   reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return

    logger.info(f"💳 Gerando PIX NOVO para {user_id} - Plano: {plano_selecionado['nome']}")
    msg_loading = await context.bot.send_message(chat_id=chat_id, text="💎 Gerando seu PIX... aguarde! ⏳")
    
    try:
        pix_data = {
            'user_id': user_id, 
            'valor': plano_selecionado['valor'], 
            'plano': plano_selecionado['nome'],
            'plano_id': plano_id
        }
        logger.info(f"🚀 Enviando dados PIX para API: {pix_data}")
        
        response = await http_client.post(f"{API_GATEWAY_URL}/api/pix/gerar", json=pix_data)
        logger.info(f"📡 Resposta API PIX: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"❌ Erro HTTP gerando PIX: {response.status_code} - {response.text}")
            raise Exception(f"API PIX falhou: {response.status_code} - {response.text}")
        
        result = response.json()
        logger.info(f"✅ PIX gerado com sucesso: {result.get('transaction_id', 'N/A')}")
        
        if not result.get('success'):
            logger.error(f"❌ API PIX retornou erro: {result}")
            raise Exception(f"API PIX retornou erro: {result.get('error', 'Unknown error')}")
        
        await msg_loading.delete()
        
        pix_copia_cola = result['pix_copia_cola']
        qr_code_url = result.get('qr_code') or f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_copia_cola}"
        
        caption = (
            f"🆕 <b>PIX Gerado (Válido por 60 minutos)</b>\n\n"
            f"📸 <b>Pague utilizando o QR Code</b>\n"
            f"💸 <b>Pague por Pix copia e cola:</b>\n"
            f"<blockquote><code>{escape(pix_copia_cola)}</code></blockquote>"
            f"<i>(Clique para copiar)</i>\n"
            f"🎯 <b>Plano:</b> {escape(plano_selecionado['nome'])}\n"
            f"💰 <b>Valor: R$ {plano_selecionado['valor']:.2f}</b>"
        )
        
        # Botões de ação
        keyboard = [
            [InlineKeyboardButton("✅ JÁ PAGUEI", callback_data=f"ja_paguei:{plano_id}")],
            [InlineKeyboardButton("🔄 ESCOLHER OUTRO PLANO", callback_data="escolher_outro_plano")]
        ]
        
        await context.bot.send_photo(chat_id=chat_id, photo=qr_code_url, caption=caption, 
                                   reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"❌ Erro CRÍTICO ao processar pagamento para {user_id}: {e}")
        await msg_loading.edit_text("❌ Um erro inesperado ocorreu. Por favor, tente novamente mais tarde ou escolha outro plano.")
    #================= FECHAMENTO ======================

async def callback_ja_paguei(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== HANDLER PARA BOTÃO "JÁ PAGUEI" =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    plano_id = query.data.split(":")[1] if ":" in query.data else "desconhecido"
    
    logger.info(f"✅ Usuário {user_id} confirmou pagamento do plano {plano_id}")
    
    # Mensagem de confirmação
    texto_confirmacao = (
        "🎉 <b>Perfeito, meu amor!</b>\n\n"
        "Seu pagamento já está sendo processado! ⚡\n\n"
        "📱 <b>Assim que for aprovado, você receberá:</b>\n"
        "• Link do grupo VIP\n"
        "• Acesso completo ao conteúdo\n"
        "• Instruções para baixar tudo\n\n"
        "⏰ <i>Geralmente demora apenas alguns minutos...</i>\n\n"
        "💕 <b>Muito obrigada pela confiança!</b>"
    )
    
    await context.bot.send_message(chat_id=chat_id, text=texto_confirmacao, parse_mode='HTML')
    #================= FECHAMENTO ======================

async def callback_escolher_outro_plano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== HANDLER PARA BOTÃO "ESCOLHER OUTRO PLANO" =============
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    logger.info(f"🔄 Usuário {user_id} quer escolher outro plano")
    
    # Invalida PIX atual do usuário
    invalidou = await invalidar_pix_usuario(user_id)
    if invalidou:
        logger.info(f"🗑️ PIX anterior do usuário {user_id} invalidado com sucesso")
    
    # Texto motivacional para upgrade
    texto_upgrade = (
        "💎 <b>Ótima escolha, amor!</b>\n\n"
        "Vou te mostrar as opções novamente... mas deixa eu te falar uma coisa: 😏\n\n"
        "🔥 <b>Quem pega o plano mais completo sempre agradece depois!</b>\n"
        "• Muito mais conteúdo exclusivo\n"
        "• Chamadas privadas comigo\n"
        "• Contato direto no WhatsApp\n"
        "• Prioridade em tudo\n\n"
        "💰 <b>E o custo-benefício é MUITO melhor!</b>\n\n"
        "<b>Qual você quer escolher agora?</b> 👇"
    )
    
    # Mostra todos os planos novamente com texto persuasivo
    keyboard = [[InlineKeyboardButton(p["botao_texto"], callback_data=f"plano:{p['id']}")] for p in VIP_PLANS.values()]
    
    await context.bot.send_message(chat_id=chat_id, text=texto_upgrade, 
                                 reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    #================= FECHAMENTO ======================


# ==============================================================================
# 4. FUNÇÃO PRINCIPAL E EXECUÇÃO DO BOT
# ==============================================================================
def main():
    #======== INICIALIZA E EXECUTA O BOT =============
    required_vars = ['TELEGRAM_BOT_TOKEN', 'API_GATEWAY_URL', 'GRUPO_GRATIS_ID', 'GRUPO_GRATIS_INVITE_LINK', 'MEDIA_APRESENTACAO', 'MEDIA_VIDEO_QUENTE', 'MEDIA_PREVIA_SITE', 'MEDIA_PROVOCATIVA']
    if any(not os.getenv(var) for var in required_vars):
        logger.critical("❌ ERRO CRÍTICO: Variáveis de ambiente obrigatórias não configuradas. Verifique o arquivo .env")
        return
        
    logger.info("🤖 === BOT COM FUNIL OTIMIZADO INICIANDO ===")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Registra os handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(CallbackQueryHandler(callback_trigger_etapa3, pattern='^trigger_etapa3$'))
    application.add_handler(CallbackQueryHandler(callback_trigger_etapa4, pattern='^trigger_etapa4$'))
    application.add_handler(CallbackQueryHandler(callback_processar_plano, pattern='^plano:'))
    application.add_handler(CallbackQueryHandler(callback_ja_paguei, pattern='^ja_paguei:'))
    application.add_handler(CallbackQueryHandler(callback_escolher_outro_plano, pattern='^escolher_outro_plano$'))
    
    logger.info("🚀 Bot iniciado com sucesso! Aguardando interações...")
    
    try:
        # Adicionado 'chat_join_request' aos updates permitidos
        application.run_polling(allowed_updates=['message', 'callback_query', 'chat_join_request'])
    finally:
        # Garante que o cliente HTTP seja fechado corretamente ao encerrar o bot
        asyncio.run(http_client.aclose())
        logger.info("🔒 Cliente HTTP e bot encerrados.")
    #================= FECHAMENTO ======================

if __name__ == '__main__':
    main()
