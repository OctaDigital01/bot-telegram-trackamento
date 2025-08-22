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
        "ETAPA_1_FALLBACK": 30,         # (30s) Se não clicar para entrar no grupo
        "ETAPA_2_FALLBACK": 60,         # (60s) Se não clicar para ver prévia
        "ETAPA_3_FALLBACK": 200,         # (3m) Se não clicar no "QUERO O VIP", envia remarketing
        "ETAPA_4_FALLBACK": 300,         # (5m) Se não escolher plano, envia desconto
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
async def delete_previous_message(context: ContextTypes.DEFAULT_TYPE, message_key: str, chat_id = None):
    """
    Deleta uma mensagem anterior cujo ID está salvo em context.user_data ou context.bot_data.
    """
    message_id = None
    found_in = None
    
    # Tenta encontrar no user_data primeiro
    if context.user_data and message_key in context.user_data:
        chat_id = chat_id or context.user_data.get('chat_id')
        message_id = context.user_data[message_key]
        found_in = 'user_data'
    # Se não encontrou, tenta no bot_data
    elif chat_id and 'message_ids' in context.bot_data:
        bot_key = f"{message_key}_{chat_id}"
        if bot_key in context.bot_data['message_ids']:
            message_id = context.bot_data['message_ids'][bot_key]
            found_in = 'bot_data'
    
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
            # Remove a chave do local correto
            if found_in == 'user_data' and context.user_data:
                del context.user_data[message_key]
            elif found_in == 'bot_data':
                bot_key = f"{message_key}_{chat_id}"
                del context.bot_data['message_ids'][bot_key]
#================= FECHAMENTO ======================

async def verificar_pix_existente(user_id: int, plano_id: str):
    #======== VERIFICA SE JÁ EXISTE PIX VÁLIDO PARA O PLANO =============
    try:
        logger.info(f"🔍 VERIFICANDO PIX EXISTENTE: user_id={user_id}, plano_id={plano_id}")
        logger.info(f"📡 CHAMANDO API VERIFICAÇÃO: GET {API_GATEWAY_URL}/api/pix/verificar/{user_id}/{plano_id}")
        response = await http_client.get(f"{API_GATEWAY_URL}/api/pix/verificar/{user_id}/{plano_id}")
        logger.info(f"📡 RESPONSE VERIFICAÇÃO: status={response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"📦 RESPONSE DATA VERIFICAÇÃO: {result}")
            
            success = result.get('success')
            pix_valido = result.get('pix_valido')
            logger.info(f"📊 ANÁLISE RESPONSE: success={success}, pix_valido={pix_valido}")
            
            if success and pix_valido:
                pix_data = result.get('pix_data')
                transaction_id = pix_data.get('transaction_id') if pix_data else 'None'
                status = pix_data.get('status') if pix_data else 'None'
                logger.info(f"✅ PIX VÁLIDO ENCONTRADO: transaction_id={transaction_id}, status={status}")
                return pix_data
            else:
                logger.info(f"❌ PIX NÃO VÁLIDO ENCONTRADO: success={success}, pix_valido={pix_valido}")
        else:
            logger.error(f"❌ ERRO HTTP na verificação PIX: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO verificando PIX existente: {e}")
    
    logger.info(f"🚫 RETORNANDO NONE - Nenhum PIX válido para user {user_id}, plano {plano_id}")
    return None
    #================= FECHAMENTO ======================

def calcular_tempo_restante(pix_data: dict) -> int:
    #======== CALCULA TEMPO RESTANTE EM MINUTOS PARA PIX =============
    try:
        from datetime import datetime, timedelta
        
        created_at = pix_data.get('created_at')
        if not created_at:
            logger.warning("⚠️ PIX sem data de criação")
            return 0
            
        logger.info(f"🔍 Processando created_at: '{created_at}' (tipo: {type(created_at)})")
            
        # Converte string para datetime se necessário
        if isinstance(created_at, str):
            try:
                # Método 1: Formato GMT - "Fri, 22 Aug 2025 18:19:40 GMT"
                if 'GMT' in created_at or 'UTC' in created_at:
                    logger.info("🔍 Detectado formato GMT/UTC")
                    from email.utils import parsedate_to_datetime
                    created_at = parsedate_to_datetime(created_at)
                    logger.info(f"✅ GMT convertido para: {created_at}")
                    
                # Método 2: Formato ISO com Z - "2025-08-22T18:19:40Z"
                elif 'Z' in created_at:
                    logger.info("🔍 Detectado formato ISO com Z")
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    logger.info(f"✅ ISO-Z convertido para: {created_at}")
                    
                # Método 3: Formato ISO puro - "2025-08-22T18:19:40"
                elif 'T' in created_at:
                    logger.info("🔍 Detectado formato ISO puro")
                    created_at = datetime.fromisoformat(created_at)
                    # Se não tem timezone, assume UTC
                    if created_at.tzinfo is None:
                        from datetime import timezone
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    logger.info(f"✅ ISO convertido para: {created_at}")
                    
                # Método 4: Outros formatos
                else:
                    logger.warning(f"⚠️ Formato de data não reconhecido: {created_at}")
                    # Tenta parsing genérico
                    created_at = datetime.fromisoformat(created_at)
                    
            except Exception as parse_error:
                logger.error(f"❌ Erro parsing data '{created_at}': {parse_error}")
                # Fallback: retorna 30 min para dar uma chance ao PIX
                logger.warning("🔄 Usando fallback de 30 minutos para PIX com data inválida")
                return 30
        
        # Calcula tempo de expiração (1 hora após criação)
        expire_time = created_at + timedelta(hours=1)
        now = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.now()
        tempo_restante = expire_time - now
        
        # Retorna minutos restantes (0 se expirado)
        minutos_restantes = max(0, int(tempo_restante.total_seconds() / 60))
        
        logger.info(f"⏰ Tempo restante calculado: {minutos_restantes} minutos")
        logger.info(f"🕐 Criado em: {created_at}")
        logger.info(f"🕐 Expira em: {expire_time}")
        logger.info(f"🕐 Agora: {now}")
        
        return minutos_restantes
        
    except Exception as e:
        logger.error(f"❌ Erro CRÍTICO calculando tempo restante: {e}")
        # Fallback inteligente: se der erro, considera que PIX ainda é válido por 30 min
        logger.warning("🔄 Usando fallback de 30 minutos devido ao erro de cálculo")
        return 30
    #================= FECHAMENTO ======================

async def invalidar_pix_usuario(user_id: int):
    #======== INVALIDA TODOS OS PIX PENDENTES DO USUÁRIO =============
    try:
        logger.info(f"📡 CHAMANDO API INVALIDAÇÃO: POST {API_GATEWAY_URL}/api/pix/invalidar/{user_id}")
        response = await http_client.post(f"{API_GATEWAY_URL}/api/pix/invalidar/{user_id}")
        logger.info(f"📡 RESPONSE INVALIDAÇÃO: status={response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"📦 RESPONSE DATA INVALIDAÇÃO: {result}")
            success = result.get('success', False)
            message = result.get('message', 'Sem mensagem')
            logger.info(f"✅ INVALIDAÇÃO PROCESSADA: success={success}, message='{message}'")
            return success
        else:
            logger.error(f"❌ ERRO HTTP na invalidação: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO invalidando PIX do usuário {user_id}: {e}")
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
    #======== DECODIFICA DADOS DE TRACKING (VERSÃO CORRIGIDA) =============
    logger.info(f"🔍 Decodificando tracking: '{encoded_param}' (tipo: {type(encoded_param)}, len: {len(encoded_param) if encoded_param else 'None'})")
    
    if not encoded_param or encoded_param.strip() == '' or encoded_param == 'no_tracking':
        logger.info("⚠️ Parâmetro vazio ou 'no_tracking' - tentando fallback último tracking")
        # Fallback: busca último tracking disponível
        try:
            response = await http_client.get(f"{API_GATEWAY_URL}/api/tracking/latest")
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    fallback_data = json.loads(result['original'])
                    logger.info(f"✅ Fallback tracking recuperado: {fallback_data}")
                    return fallback_data
        except Exception as e:
            logger.warning(f"⚠️ Erro no fallback tracking: {e}")
        return {'utm_source': 'direct_bot', 'click_id': 'direct_access'}
    
    try:
        # Método 1: ID mapeado (começa com M)
        if encoded_param.startswith('M') and len(encoded_param) <= 15:  # Aumentado limite
            logger.info(f"🔍 Método 1: Tentando buscar ID mapeado '{encoded_param}'")
            try:
                response = await http_client.get(f"{API_GATEWAY_URL}/api/tracking/get/{encoded_param}")
                logger.info(f"📡 Response status da API: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"📦 Response JSON: {result}")
                    
                    if result.get('success'):
                        original_data = json.loads(result['original'])
                        logger.info(f"✅ Tracking mapeado recuperado com sucesso: {original_data}")
                        return original_data
                    else:
                        logger.warning(f"⚠️ API retornou success=False para tracking mapeado: {encoded_param}")
                else:
                    logger.error(f"❌ Erro HTTP ao buscar tracking mapeado: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"❌ Erro crítico ao buscar tracking mapeado: {e}")
            
            # Fallback: se o ID mapeado falhou, tenta outras opções
            logger.info(f"🔄 ID mapeado falhou, usando '{encoded_param}' como click_id direto")
            return {'click_id': encoded_param, 'utm_source': 'mapped_id_fallback'}
        
        # Método 2: Base64 JSON
        logger.info(f"🔍 Método 2: Tentando decodificar Base64")
        try:
            decoded_bytes = base64.b64decode(encoded_param.encode('utf-8'))
            tracking_data = json.loads(decoded_bytes.decode('utf-8'))
            logger.info(f"✅ Tracking Base64 decodificado com sucesso: {tracking_data}")
            return tracking_data
        except (json.JSONDecodeError, Exception) as e:
            logger.info(f"⚠️ Base64 decode falhou: {e}")

        # Método 3: Formato :: separado (Xtracky)
        if '::' in encoded_param:
            logger.info(f"🔍 Método 3: Decodificando formato :: separado")
            parts = encoded_param.split('::')
            tracking_data = {
                'utm_source': parts[0] if len(parts) > 0 and parts[0] else None,
                'click_id': parts[1] if len(parts) > 1 and parts[1] else None,
                'utm_medium': parts[2] if len(parts) > 2 and parts[2] else None,
                'utm_campaign': parts[3] if len(parts) > 3 and parts[3] else None
            }
            # Remove valores None
            tracking_data = {k: v for k, v in tracking_data.items() if v}
            logger.info(f"✅ Tracking :: formato decodificado: {tracking_data}")
            return tracking_data
        
        # Método 4: Parâmetro direto como click_id
        logger.info(f"🔍 Método 4: Usando parâmetro direto como click_id")
        tracking_data = {'click_id': encoded_param, 'utm_source': 'direct_param'}
        logger.info(f"✅ Tracking direto processado: {tracking_data}")
        return tracking_data
        
    except Exception as e:
        logger.error(f"❌ Erro crítico na decodificação: {e}")
        return {'click_id': str(encoded_param), 'utm_source': 'decode_error', 'error': str(e)}
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
    
    # NOVA SESSÃO: Invalida TODOS os PIX anteriores do usuário
    # Cada /start deve ser uma sessão completamente independente
    logger.info(f"🔄 NOVA SESSÃO INICIADA: Invalidando TODOS os PIX anteriores para usuário {user.id}")
    
    # STEP 1: Invalida todos os PIX anteriores
    invalidacao_sucesso = await invalidar_pix_usuario(user.id)
    logger.info(f"📊 RESULTADO INVALIDAÇÃO: sucesso={invalidacao_sucesso} para usuário {user.id}")
    
    if invalidacao_sucesso:
        logger.info(f"✅ PIX anteriores INVALIDADOS com sucesso para usuário {user.id}")
    else:
        logger.warning(f"⚠️ Falha ou nenhum PIX encontrado para invalidar do usuário {user.id}")
    
    # STEP 2: Aguarda 100ms para garantir que invalidação foi processada no banco
    import time
    await asyncio.sleep(0.1)
    
    # STEP 3: Armazena flag de nova sessão para garantir que próximos PIX sejam sempre novos
    context.user_data['nova_sessao_start'] = True
    context.user_data['session_id'] = f"{user.id}_{int(time.time())}"
    logger.info(f"🆔 NOVA SESSION_ID criada: {context.user_data['session_id']}")
    
    # Remove jobs de timeout PIX que possam estar ativos
    await remove_job_if_exists(f"timeout_pix_{user.id}", context)
    
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
    
    # Salva no bot_data para jobs que não tem user_data
    if 'message_ids' not in context.bot_data:
        context.bot_data['message_ids'] = {}
    context.bot_data['message_ids'][f'etapa2_msg_{chat_id}'] = msg.message_id
    
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
    
    await job_etapa3_galeria(context, chat_id_manual=chat_id)
    #================= FECHAMENTO ======================

async def job_etapa3_galeria(context: ContextTypes.DEFAULT_TYPE, chat_id_manual=None):
    #======== ENVIA GALERIA DE MÍDIAS E OFERTA VIP =============
    chat_id = chat_id_manual or context.job.data['chat_id']
    logger.info(f"⏰ ETAPA 3: Enviando galeria de mídias para {chat_id}.")
    
    # Comentado para manter mensagem anterior visível
    # await delete_previous_message(context, 'etapa2_msg', chat_id)
    
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
    
    # Salva tanto no user_data quanto no bot_data para funcionar em ambos contextos
    if context.user_data is not None:
        context.user_data['etapa3_msg'] = msg.message_id
    if 'message_ids' not in context.bot_data:
        context.bot_data['message_ids'] = {}
    context.bot_data['message_ids'][f'etapa3_msg_{chat_id}'] = msg.message_id
    
    context.job_queue.run_once(job_etapa3_remarketing, CONFIGURACAO_BOT["DELAYS"]["ETAPA_3_FALLBACK"], chat_id=chat_id, name=f"job_etapa3_remarketing_{chat_id}", data={'chat_id': chat_id})
    #================= FECHAMENTO ======================

async def job_etapa3_remarketing(context: ContextTypes.DEFAULT_TYPE):
    #======== ENVIA MENSAGEM DE REMARKETING (FALLBACK DA ETAPA 3) =============
    chat_id = context.job.data['chat_id']
    logger.info(f"⏰ ETAPA 3 (FALLBACK): Enviando remarketing breve para {chat_id}.")
    
    await delete_previous_message(context, 'etapa3_msg', chat_id)
    
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
    
    # Salva tanto no user_data quanto no bot_data para funcionar em ambos contextos
    if context.user_data is not None:
        context.user_data['etapa4_msg'] = msg.message_id
    if 'message_ids' not in context.bot_data:
        context.bot_data['message_ids'] = {}
    context.bot_data['message_ids'][f'etapa4_msg_{chat_id}'] = msg.message_id
    
    context.job_queue.run_once(job_etapa4_desconto, CONFIGURACAO_BOT["DELAYS"]["ETAPA_4_FALLBACK"], chat_id=chat_id, name=f"job_etapa4_desconto_{chat_id}", data={'chat_id': chat_id})
    #================= FECHAMENTO ======================

async def job_etapa4_desconto(context: ContextTypes.DEFAULT_TYPE):
    #======== OFERECE DESCONTO (FALLBACK DA ETAPA 4) =============
    chat_id = context.job.data['chat_id']
    logger.info(f"⏰ ETAPA 4 (FALLBACK): Oferecendo desconto para {chat_id}.")
    
    await delete_previous_message(context, 'etapa4_msg', chat_id)
    
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

    # VERIFICAÇÃO CRÍTICA: Nova sessão sempre gera PIX novo
    nova_sessao = context.user_data.get('nova_sessao_start', False)
    session_id = context.user_data.get('session_id', 'sem_session')
    
    if nova_sessao:
        logger.info(f"🚨 NOVA SESSÃO DETECTADA ({session_id}): PULANDO verificação de PIX existente")
        logger.info(f"💳 Gerando PIX NOVO obrigatoriamente para usuário {user_id}")
        # Limpa a flag após usar
        context.user_data['nova_sessao_start'] = False
        # PIX completamente novo será gerado abaixo
    else:
        # LÓGICA ANTIGA DE REUTILIZAÇÃO - só se não é nova sessão
        logger.info(f"🔍 VERIFICANDO PIX EXISTENTE (sessão anterior): user_id={user_id}, plano_id={plano_id}")
        pix_existente = await verificar_pix_existente(user_id, plano_id)
        
        if pix_existente:
            logger.info(f"📦 PIX ENCONTRADO (sessão anterior): {pix_existente}")
            
            # Calcula tempo restante com nova função corrigida
            tempo_restante = calcular_tempo_restante(pix_existente)
            logger.info(f"⏰ TEMPO CALCULADO: {tempo_restante} minutos")
            
            if tempo_restante > 0:  # PIX ainda válido
                logger.info(f"✅ PIX VÁLIDO (sessão anterior) - REUTILIZANDO para {user_id}")
                logger.info(f"♻️ Plano: {plano_selecionado['nome']} - Tempo restante: {tempo_restante} min")
                await enviar_mensagem_pix(context, chat_id, user_id, plano_selecionado, pix_existente, is_reused=True)
                return
            else:
                logger.info(f"❌ PIX EXPIRADO (0 minutos) para {user_id} - Gerando novo PIX")
                # PIX expirado, invalida e gera novo
                await invalidar_pix_usuario(user_id)
        else:
            logger.info(f"🚫 NENHUM PIX encontrado para {user_id}, plano {plano_id}")
    
    # Se chegou aqui, precisa GERAR NOVO PIX
    logger.info(f"💳 Gerando PIX NOVO para {user_id} - Plano: {plano_selecionado['nome']}")
    msg_loading = await context.bot.send_message(chat_id=chat_id, text="💎 Gerando seu PIX... aguarde! ⏳")
    context.user_data['loading_msg'] = msg_loading.message_id
    try:
        # Não envia customer - deixa a API gerar dados únicos automaticamente
        pix_data = {
            'user_id': user_id, 
            'valor': plano_selecionado['valor'], 
            'plano_id': plano_id
        }
        response = await http_client.post(f"{API_GATEWAY_URL}/api/pix/gerar", json=pix_data)
        response.raise_for_status()
        result = response.json()
        if not result.get('success') or not result.get('pix_copia_cola'):
            raise Exception(f"API PIX retornou erro ou dados incompletos: {result.get('error', 'Erro desconhecido')}")
        
        await delete_previous_message(context, 'loading_msg', chat_id)
        await enviar_mensagem_pix(context, chat_id, user_id, plano_selecionado, result)
    except Exception as e:
        logger.error(f"❌ Erro CRÍTICO ao processar pagamento para {user_id}: {e}")
        await delete_previous_message(context, 'loading_msg', chat_id)
        await context.bot.send_message(chat_id, "❌ Um erro inesperado ocorreu. Por favor, tente novamente mais tarde.")
    #================= FECHAMENTO ======================

async def enviar_mensagem_pix(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, plano: dict, pix_data: dict, is_reused: bool = False):
    #======== ENVIA A MENSAGEM COM O QR CODE E DADOS DO PIX =============
    pix_copia_cola = pix_data['pix_copia_cola']
    
    # CORREÇÃO CRÍTICA: TriboPay retorna URL incompatível com Telegram
    # Sempre gera QR Code via serviço externo que retorna imagem PNG
    from urllib.parse import quote
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(pix_copia_cola)}"
    logger.info(f"🔲 QR Code gerado: {qr_code_url[:80]}...")
    
    # Mensagem base do PIX
    caption = (
        f"💎 <b>Seu PIX está aqui, meu amor!</b>\n\n"
        f"📸 <b>Pague utilizando o QR Code</b>\n"
        f"💸 <b>Pague por Pix copia e cola:</b>\n"
        f"<blockquote><code>{escape(pix_copia_cola)}</code></blockquote>"
        f"<i>(Clique para copiar)</i>\n\n"
        f"🎯 <b>Plano:</b> {escape(plano['nome'])}\n"
        f"💰 <b>Valor: R$ {plano['valor']:.2f}</b>"
    )
    
    # Se PIX foi reutilizado, adiciona informação de tempo restante
    if is_reused:
        tempo_restante = calcular_tempo_restante(pix_data)
        if tempo_restante > 0:
            caption += f"\n\n⏰ <b>PIX reutilizado - Tempo restante: {tempo_restante} minutos</b>"
            logger.info(f"♻️ Exibindo PIX reutilizado com {tempo_restante} minutos restantes")
        else:
            caption += f"\n\n⚠️ <b>PIX reutilizado - Finalizando em breve</b>"
            logger.warning(f"⚠️ PIX reutilizado mas tempo quase expirado")
    keyboard = [
        [InlineKeyboardButton("✅ JÁ PAGUEI", callback_data=f"ja_paguei:{plano['id']}")],
        [InlineKeyboardButton("🔄 ESCOLHER OUTRO PLANO", callback_data="escolher_outro_plano")]
    ]
    
    try:
        await context.bot.send_photo(chat_id=chat_id, photo=qr_code_url, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        logger.info(f"✅ QR Code PIX enviado com sucesso para {user_id}")
    except Exception as e:
        logger.error(f"❌ Falha ao enviar foto do QR Code para {user_id}: {e}. Enviando fallback com QR Code inline.")
        
        # Fallback: Envia mensagem de texto com QR Code como link
        caption_fallback = (
            f"💎 <b>Seu PIX está aqui, meu amor!</b>\n\n"
            f"📸 <b>QR Code:</b> <a href='{qr_code_url}'>Clique aqui para ver o QR Code</a>\n\n"
            f"💸 <b>Pague por Pix copia e cola:</b>\n"
            f"<blockquote><code>{escape(pix_copia_cola)}</code></blockquote>"
            f"<i>(Clique para copiar)</i>\n\n"
            f"🎯 <b>Plano:</b> {escape(plano['nome'])}\n"
            f"💰 <b>Valor: R$ {plano['valor']:.2f}</b>"
        )
        await context.bot.send_message(chat_id=chat_id, text=caption_fallback, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # Agenda o job de timeout
    await remove_job_if_exists(f"timeout_pix_{user_id}", context)
    
    if is_reused:
        # Para PIX reutilizado, usa o tempo restante real
        tempo_restante_min = calcular_tempo_restante(pix_data)
        timeout_seconds = max(60, tempo_restante_min * 60)  # Mínimo de 1 minuto
        logger.info(f"⏰ PIX reutilizado - Timeout ajustado para {tempo_restante_min} minutos")
    else:
        # Para PIX novo, usa timeout padrão (1 hora)
        timeout_seconds = CONFIGURACAO_BOT["DELAYS"]["PIX_TIMEOUT"]
        logger.info(f"⏰ PIX novo - Timeout padrão de {timeout_seconds/60:.0f} minutos")

    context.job_queue.run_once(job_timeout_pix, timeout_seconds, chat_id=chat_id, user_id=user_id, name=f"timeout_pix_{user_id}")
    logger.info(f"⏰ Job de timeout PIX agendado para {user_id} em {timeout_seconds/60:.1f} minutos.")
    #================= FECHAMENTO ======================

async def callback_ja_paguei(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #======== HANDLER PARA BOTÃO "JÁ PAGUEI" =============
    query = update.callback_query
    await query.answer("🎉 Perfeito, meu amor! Seu pagamento já está sendo processado! ⚡ Assim que for aprovado, você receberá o acesso ao grupo VIP aqui mesmo. Geralmente demora apenas alguns segundos...", show_alert=True)
    user_id = query.from_user.id
    
    await remove_job_if_exists(f"timeout_pix_{user_id}", context)
    logger.info(f"⏰ Job de timeout PIX cancelado para {user_id} após confirmação de pagamento.")
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
    #======== INICIALIZA E EXECUTA O BOT DE FORMA ASSÍNCRONA (CORRIGIDO CONFLITOS) =============
    global _BOT_INSTANCE
    
    # Força encerramento de qualquer instância anterior
    if _BOT_INSTANCE:
        logger.warning("⚠️ Bot já está rodando, encerrando instância anterior...")
        try:
            old_instance = _BOT_INSTANCE
            # Tenta parar de forma gentil primeiro
            if hasattr(old_instance, 'updater') and old_instance.updater:
                if hasattr(old_instance.updater, 'is_running') and old_instance.updater.is_running():
                    logger.info("🛑 Parando updater anterior...")
                    await old_instance.updater.stop()
                    await asyncio.sleep(1)
            
            if hasattr(old_instance, 'stop'):
                logger.info("🛑 Parando aplicação anterior...")
                await old_instance.stop()
                await asyncio.sleep(1)
                
            if hasattr(old_instance, 'shutdown'):
                logger.info("🛑 Fazendo shutdown da aplicação anterior...")
                await old_instance.shutdown()
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"❌ Erro ao encerrar instância anterior: {e}")
        
        _BOT_INSTANCE = None
        # Aguarda mais tempo para garantir que recursos sejam liberados
        logger.info("⏳ Aguardando liberação de recursos...")
        await asyncio.sleep(5)
    
    # Validação rigorosa das variáveis de ambiente
    required_vars = ['TELEGRAM_BOT_TOKEN', 'API_GATEWAY_URL', 'GRUPO_GRATIS_ID', 'GRUPO_GRATIS_INVITE_LINK']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.critical(f"❌ ERRO CRÍTICO: Variáveis de ambiente obrigatórias não configuradas: {missing_vars}")
        return
    
    # Validação adicional do token
    if not BOT_TOKEN or len(BOT_TOKEN) < 40:
        logger.critical("❌ ERRO CRÍTICO: TELEGRAM_BOT_TOKEN inválido")
        return
        
    logger.info("🤖 === BOT COM FUNIL OTIMIZADO E TRACKING CORRIGIDO INICIANDO ===")
    logger.info(f"🔗 API Gateway URL: {API_GATEWAY_URL}")
    logger.info(f"👥 Grupo ID: {GROUP_ID}")
    
    # Configuração mais robusta do bot
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        _BOT_INSTANCE = application
        
        # Registra os handlers na ordem correta
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(ChatJoinRequestHandler(handle_join_request))
        application.add_handler(CallbackQueryHandler(callback_trigger_etapa3, pattern='^trigger_etapa3$'))
        application.add_handler(CallbackQueryHandler(callback_trigger_etapa4, pattern='^trigger_etapa4$'))
        application.add_handler(CallbackQueryHandler(callback_processar_plano, pattern='^plano:'))
        application.add_handler(CallbackQueryHandler(callback_ja_paguei, pattern='^ja_paguei:'))
        application.add_handler(CallbackQueryHandler(callback_escolher_outro_plano, pattern='^escolher_outro_plano$'))
        logger.info("✅ Handlers registrados com sucesso")
    
        # Inicialização mais robusta
        logger.info("🔧 Inicializando aplicação...")
        await application.initialize()
        
        logger.info("▶️ Iniciando aplicação...")
        await application.start()
        
        logger.info("🚀 Iniciando polling...")
        if application.updater:
            await application.updater.start_polling(
                allowed_updates=['message', 'callback_query', 'chat_join_request'],
                drop_pending_updates=True,
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30
            )
        
        logger.info("✅ Bot online e recebendo atualizações - Sistema de tracking corrigido")
        logger.info("📊 Funcionalidades ativas:")
        logger.info("   - Decodificação de tracking com 4 métodos")
        logger.info("   - Fallback inteligente para último tracking")
        logger.info("   - Logs detalhados para debug")
        logger.info("   - Prevenção de conflitos 409")
        logger.info("   - Sistema de reutilização de PIX por plano")
        logger.info("   - Timeout inteligente baseado em tempo restante")
        
        # Mantém o script rodando indefinidamente
        await asyncio.Event().wait()

    except Conflict as e:
        logger.error(f"❌ CONFLITO 409: Múltiplas instâncias detectadas. {e}")
        logger.error("💡 SOLUÇÃO: Verifique se há outras instâncias rodando no Railway")
        logger.error("💡 COMANDO: railway ps para ver processos ativos")
    except Exception as e:
        logger.critical(f"❌ Erro fatal na execução do bot: {e}", exc_info=True)
    finally:
        logger.info("🛑 Iniciando processo de encerramento...")
        try:
            if _BOT_INSTANCE and hasattr(_BOT_INSTANCE, 'updater') and _BOT_INSTANCE.updater:
                if hasattr(_BOT_INSTANCE.updater, 'is_running') and _BOT_INSTANCE.updater.is_running():
                    logger.info("🛑 Parando updater...")
                    await _BOT_INSTANCE.updater.stop()
            
            if _BOT_INSTANCE:
                logger.info("🛑 Parando aplicação...")
                await _BOT_INSTANCE.stop()
                logger.info("🛑 Fazendo shutdown...")
                await _BOT_INSTANCE.shutdown()
            
            if http_client and not http_client.is_closed:
                logger.info("🔒 Fechando cliente HTTP...")
                await http_client.aclose()
        
        except Exception as e:
            logger.error(f"❌ Erro durante encerramento: {e}")
        finally:
            _BOT_INSTANCE = None
            logger.info("✅ Bot encerrado com sucesso.")
#================= FECHAMENTO ======================

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Execução interrompida pelo usuário.")
