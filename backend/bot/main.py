# ═══════════════════════════════════════════════════════════════
# 🤖 BOT TELEGRAM - ANA CARDOSO
# ═══════════════════════════════════════════════════════════════
# 📝 Bot principal para vendas com PIX integrado
# 🎯 Configurado para captura de tracking completo
# 🔄 Última modificação: 28/08/2025 - Correção de logs e fallbacks
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 📚 IMPORTS OBRIGATÓRIOS (🚫 NÃO MEXER - SISTEMA PADRÃO)
# ═══════════════════════════════════════════════════════════════
import os
import logging
import pathlib
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

import asyncpg
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ═══════════════════════════════════════════════════════════════
# ⚙️ CREDENCIAIS E URLs (🚫 NÃO MEXER - VÊM DAS VARIÁVEIS AMBIENTE)
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT1_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TRIBOPAY_API_URL = os.getenv("TRIBOPAY_API_URL", "https://api-tribopay-production.up.railway.app")

# ═══════════════════════════════════════════════════════════════
# 🎨 SEÇÃO DE PERSONALIZAÇÃO (✅ EDITAR LIVREMENTE PARA NOVOS BOTS)
# ═══════════════════════════════════════════════════════════════

# 💰 CONFIGURAÇÃO DOS COMBOS (✅ PERSONALIZÁVEL)
COMBOS_CONFIG = {
    "combo01": {
        "nome": "Combo 01 🙈",
        "valor": 9.99,
        "descricao": "4 Imagens"
    },
    "combo02": {
        "nome": "Combo 02 🔥", 
        "valor": 14.99,
        "descricao": "6 Imagens + 2 Vídeos bem quentes"
    },
    "combo03": {
        "nome": "Combo 03 🔥😈🥵",
        "valor": 17.00,
        "descricao": "10 Imagens + 4 Vídeos daquele jeito 🤭🔥 + 1 Bônus surpresa 🥵🎁"
    }
}

# 🤖 CONFIGURAÇÃO DO BOT (✅ PERSONALIZÁVEL)
BOT_CONFIG = {
    "nome": "bot1 - anacardoso1bot",
    "emoji_principal": "🔥",
    "cor_tema": "😈",
    "versao": "5.0" # Correção de logs e fallbacks
}

# 📱 MÍDIA E ARQUIVOS (✅ PERSONALIZÁVEL)
MEDIA_FILES = {
    "etapa1_image": os.getenv("ETAPA1_IMAGE_ID", "AgACAgEAAxkBAAPWaLBig-nIDyXjeZ-6RmgeNlPkExUAArCuMRsqZYlF18EJL5RT-fYBAAMCAAN5AAM2BA"),
    "etapa1b_audio": os.getenv("ETAPA1B_AUDIO_ID", "etapa1b.ogg"),
    "etapa2b_audio": os.getenv("ETAPA2B_AUDIO_ID", "etapa2b.ogg"),
    "etapa5_1_audio": "etapa5-1.ogg",
    "etapa5_2_video": "BAACAgEAAxkBAAIBGWiwt5sxZEc4hwhf6QcyZnc0P3X9AAI3CgACKmWJRQK_wfArbLC9NgQ"
}

# 📦 PACOTES PAGOS (✅ PERSONALIZÁVEL)
PAID_PACKS = {
    "videos": {
        "video1": "BAACAgEAAxkBAAPsaLBlTxTlxlQcrrlkUFHJ5rhs45AAAv4JAAIqZYlFT1rOdRS3znE2BA",
        "video2": "BAACAgEAAxkBAAPuaLBlXWixII4y8kUXYuBvUE0pwHMAAv8JAAIqZYlFl9JfTcE8KVc2BA",
        "video3": "BAACAgEAAxkBAAPwaLBlZZJSbYr-E1M6q0QlBvv3kaoAAwoAAipliUV0GIBUE_yU5TYE",
        "video4": "BAACAgEAAxkBAAPyaLBlcXhb9ozu-R4gzw-je0bNzyoAAgEKAAIqZYlFW9qRuILcUes2BA",
    },
    "images": {
        "imagem1": "AgACAgEAAxkBAAPYaLBkQ4jzMHsZV4wBpocptSN5MtYAArKuMRsqZYlF_dqdpO55knsBAAMCAAN5AAM2BA",
        "imagem2": "AgACAgEAAxkBAAPaaLBkd455qsaG2Pb4F2zDEohEQHoAArOuMRsqZYlFAAEgAAFHAAEdeDEBAAMCAAN5AAM2BA",
        "imagem3": "AgACAgEAAxkBAAPcaLBkgjHsSwspcK3MQk1-GeU4pHIAArSuMRsqZYlFyQjNAW3j91cBAAMCAAN5AAM2BA",
        "imagem4": "AgACAgEAAxkBAAPeaLBkjjJL091iwhBjVI0xHenWxC0AArWuMRsqZYlFoyHYqLDFw5wBAAMCAAN5AAM2BA",
        "imagem5": "AgACAgEAAxkBAAPgaLBkmKRgYJHiqRvKuMFDCpyE9EYAArauMRsqZYlF7r8AAdkCTXI6AQADAgADeQADNgQ",
        "imagem6": "AgACAgEAAxkBAAPiaLBksx2fAAHwe_Z91DRosGE1jfL9AAK3rjEbKmWJRY_jHjHKsoMFAQADAgADeQADNgQ",
        "imagem7": "AgACAgEAAxkBAAPkaLBkvN10CpZu6llqag_zSv25r08AAriuMRsqZYlFeq1j2AT44qYBAAMCAAN5AAM2BA",
        "imagem8": "AgACAgEAAxkBAAPmaLBkxJS_426CqGyEhboSYMW-PUAAArmuMRsqZYlFJAmwZnaOMtABAAMCAAN5AAM2BA",
        "imagem9": "AgACAgEAAxkBAAPoaLBkz2QYMiuquWOKXURrpaRnFSAAArquMRsqZYlFeu1KFjqoqXoBAAMCAAN5AAM2BA",
        "imagem10": "AgACAgEAAxkBAAPqaLBk5YrYhSsmxS5NtqNma-F1Jv8AAruuMRsqZYlFWxU7n3AwH4IBAAMCAAN5AAM2BA",
    }
}

# ═══════════════════════════════════════════════════════════════
# 📝 TEXTOS E MENSAGENS (✅ PERSONALIZÁVEL - EDITAR LIVREMENTE)
# ═══════════════════════════════════════════════════════════════
MENSAGEM_ETAPA1 = "Oiiee, quer ver meus conteúdinhos né?🔥\n\nTenho 3 opções, posso te mandar, meu bem?"
MENSAGEM_ETAPA1B = "Posso te manda bb?"
MENSAGEM_ETAPA2 = """Olha só, são esses aqui⬇️:

•⁠  ⁠Combo 01: 4 Imagens + 1 Vídeo | R$9,99
•⁠  ⁠Combo 02: 6 Imagens + 2 Vídeos beem quentes | R$ 14,99
•⁠  ⁠Combo 03: 10 Imagens + 4 Vídeos daquele jeito 🤭🔥 + 1 Bônus surpresa 🥵🎁 | R$ 17,00

E aí meu bem, qual você vai querer: 01, 02 ou 03?
(Tem que escolher um em...)"""
MENSAGEM_ETAPA2B = """Escolhe bb:

•⁠  ⁠Combo 01: 4 Imagens + 1 Vídeo | R$9,99
•⁠  ⁠Combo 02: 6 Imagens + 2 Vídeos beem quentes | R$ 14,99
•⁠  ⁠Combo 03: 10 Imagens + 4 Vídeos daquele jeito 🤭🔥 + 1 Bônus surpresa 🥵🎁 | R$ 17,00

E aí meu bem, qual quer? 01, 02 ou 03?"""

def criar_mensagem_pix(combo_nome: str, valor: float, pix_code: str) -> str:
    return (f"💎 <b>Seu PIX está aqui, meu amor!</b>\n\n" + 
            f"💸 <b>Pague por Pix copia e cola:</b>\n" + 
            f"<blockquote><code>{pix_code}</code></blockquote>" + 
            f"<i>(Clique para copiar)</i>\n\n" + 
            f"🎯 <b>Plano:</b> {combo_nome}\n" + 
            f"💰 <b>Valor: R$ {valor:.2f}</b>")

MENSAGEM_PIX_ERRO = "❌ *Ops! Ocorreu um erro ao gerar o PIX*\n\n🔄 Tente novamente em alguns instantes."

MENSAGEM_ETAPA5 = "E aí meu bem, espero que tenha gostado do que viu. O que achou?"
MENSAGEM_ETAPA5_1 = "Vem bb, desse lado aqui eu te mostro tudinho..."
MENSAGEM_ETAPA5_2 = """Meu bem, to te esperando pra mostrar tudinho, olha essa prévia q te mandei...

💎 Vídeos e fotos do jeitinho que você gosta...
💎 Videos exclusivo pra você, te fazendo go.zar só eu e você
💎 Meu contato pessoal

Sempre posto coisa nova
💎 Chamada de vídeo só nós 2
💎 E muito mais meu bem...

Vem ver bb🥵💦⬇️"""

BOTOES_TEXTO = {
    "etapa1_sim": "SIM, PODE MANDAR ✅",
    "combo01": f"{COMBOS_CONFIG['combo01']['nome']} | R${COMBOS_CONFIG['combo01']['valor']:.2f}",
    "combo02": f"{COMBOS_CONFIG['combo02']['nome']} | R$ {COMBOS_CONFIG['combo02']['valor']:.2f}",
    "combo03": f"{COMBOS_CONFIG['combo03']['nome']} | R$ {COMBOS_CONFIG['combo03']['valor']:.2f}",
    "etapa5_gostei": "GOSTEI, QUERO VER + 🔥🥵",
    "etapa5_1_ver_mais": "VER + 🥵🔥",
    "etapa5_2_ver_agora": "VER AGORA🔥"
}


# ═══════════════════════════════════════════════════════════════
# 🔚 FIM DA SEÇÃO DE PERSONALIZAÇÃO
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 🚫 SISTEMA TÉCNICO - NÃO MEXER (FUNCIONALIDADES INTERNAS)
# ═══════════════════════════════════════════════════════════════

# 🎨 SISTEMA DE LOGS VISUAIS (🚫 NÃO ALTERAR)
def log_card(titulo: str, conteudo: str, tipo: str = "info") -> None:
    emojis = {
        "info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌", "process": "⚙️", 
        "database": "💾", "user": "👤", "plan": "💰", "pix": "💳", "tracking": "📊", 
        "startup": "🚀", "shutdown": "🛑", "fallback": "🔄", "block": "🚫", "delete": "🗑️", 
        "job": "⏰", "audio": "🎤", "button": "🔘", "callback": "🔙"
    }
    emoji = emojis.get(tipo, "ℹ️")
    utc4_tz = timezone(timedelta(hours=-4))
    timestamp = datetime.now(utc4_tz).strftime('%d/%m/%Y %H:%M:%S')
    print(f"\n{'═' * 64}")
    print(f"  {emoji} {titulo.upper()}")
    print(f"  {'═' * 64}")
    print(f"  {conteudo}")
    print(f"  Timestamp: {timestamp}")
    print(f"  {'═' * 64}\n")

def format_user_info(user) -> str:
    if not user: return "[USUÁRIO DESCONHECIDO]"
    parts = []
    if user.first_name: parts.append(f"Nome: {user.first_name}")
    if user.last_name: parts.append(f"Sobrenome: {user.last_name}")
    if user.username: parts.append(f"@{user.username}")
    parts.append(f"ID: {user.id}")
    if user.language_code: parts.append(f"Idioma: {user.language_code}")
    return " | ".join(parts)

def log_user_action(action: str, user, additional_info: str = "") -> None:
    user_info = format_user_info(user)
    content = f"Ação: {action}\n  Usuário: {user_info}"
    if additional_info:
        content += f"\n  Detalhes: {additional_info}"
    log_card("USER ACTION", content, "user")

def log_error_detailed(error_type: str, error: Exception, context_info: str = "") -> None:
    tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
    tb_summary = "".join(tb_lines[-2:]).strip()
    error_details = f"Tipo: {error_type}\n  Erro: {str(error)}\n  Classe: {type(error).__name__}\n  Contexto: {context_info}\n  Stack Trace: {tb_summary}"
    log_card("ERROR DETAILED", error_details, "error")

# 🗄️ FUNÇÕES DE BANCO DE DADOS (🚫 NÃO ALTERAR)
db_pool = None
async def get_db_pool():
    global db_pool
    if db_pool is None:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
            log_card("DATABASE", "Pool de conexões do bot criado", "database")
        except Exception as e:
            log_card("DATABASE ERROR", f"Erro ao conectar: {str(e)}", "error")
            raise
    return db_pool

async def get_tracking_data(short_id: str) -> Optional[Dict[str, Any]]:
    if not short_id: return None
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM user_journey WHERE short_id = $1", short_id)
            if row: return dict(row)
    except Exception as e:
        log_card("DB ERROR", f"Erro ao buscar tracking data: {str(e)}", "error")
    return None

async def update_user_journey(short_id: str, user_data: Dict, journey_data: Dict) -> None:
    if not short_id: return
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            set_clauses, values, param_count = [], [], 0
            for key, value in journey_data.items():
                if value == "NOW()": set_clauses.append(f"{key} = NOW()")
                else: param_count += 1; set_clauses.append(f"{key} = ${param_count}"); values.append(value)
            if user_data:
                telegram_fields = {'id': user_data.get('id'), 'username': user_data.get('username'), 'first_name': user_data.get('first_name'), 'last_name': user_data.get('last_name'), 'language_code': user_data.get('language_code'), 'is_premium': user_data.get('is_premium', False)}
                for key, value in telegram_fields.items():
                    if value is not None: param_count += 1; set_clauses.append(f"{key} = ${param_count}"); values.append(value)
            if set_clauses:
                param_count += 1; values.append(short_id)
                query = f"UPDATE user_journey SET {', '.join(set_clauses)}, updated_at = NOW() WHERE short_id = ${param_count}"
                await conn.execute(query, *values)
    except Exception as e:
        log_card("DB UPDATE ERROR", f"Erro ao atualizar jornada: {str(e)}", "error")

# ═══════════════════════════════════════════════════════════════
# 🔧 FUNÇÕES AUXILIARES E HANDLERS (🚫 NÃO ALTERAR)
# ═══════════════════════════════════════════════════════════════

def cleanup_user_jobs(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user_context = context.application.user_data.get(user_id)
    if not user_context:
        return

    job_keys = [
        "fallback_job", "etapa2_fallback_job", "etapa2_auto_job", 
        "remaketing_job", "etapa5_1_fallback_job", "etapa5_2_fallback_job"
    ]
    for job_key in job_keys:
        if job := user_context.pop(job_key, None):
            try:
                job.schedule_removal()
            except Exception:
                pass

def extract_user_data(user) -> Dict[str, Any]:
    if not user: return {}
    return {'id': user.id, 'username': getattr(user, 'username', None), 'first_name': getattr(user, 'first_name', ''), 'last_name': getattr(user, 'last_name', ''), 'language_code': getattr(user, 'language_code', 'pt'), 'is_premium': getattr(user, 'is_premium', False)}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return

    if user.id not in context.application.user_data:
        context.application.user_data[user.id] = {}
    user_context = context.application.user_data[user.id]

    cleanup_user_jobs(context, user.id)
    log_user_action("Novo /start", user, "Jobs anteriores cancelados, nova sessão iniciada")
    
    # Manter o short_id se um novo não for passado como argumento
    short_id = context.args[0] if context.args else user_context.get("short_id")
    
    if short_id:
        user_context["short_id"] = short_id
        tracking_info = await get_tracking_data(short_id)
        if tracking_info:
            user_context["tracking_data"] = tracking_info
            user_data = extract_user_data(user)
            await update_user_journey(short_id, user_data, {"bot_started": True, "bot_start_at": "NOW()"})
    
    user_context["current_stage"] = "etapa1"
    
    image_id = MEDIA_FILES.get("etapa1_image")
    reply_markup = InlineKeyboardMarkup([[ 
        InlineKeyboardButton(BOTOES_TEXTO["etapa1_sim"], callback_data="etapa1_sim")
    ]])
    
    if image_id and update.message:
        await update.message.reply_photo(photo=image_id, caption=MENSAGEM_ETAPA1, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(MENSAGEM_ETAPA1, reply_markup=reply_markup)

    if context.job_queue:
        user_context["fallback_job"] = context.job_queue.run_once(
            etapa1b_fallback, 30, chat_id=update.effective_chat.id, data={"user_id": user.id}
        )

async def etapa1b_fallback(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    user_id = job.data.get('user_id')
    user_context = context.application.user_data.get(user_id, {})

    if not user_id or user_context.get("current_stage") != "etapa1":
        return

    log_card("FALLBACK", f"Executando fallback 1B | User: {user_id}", "fallback")
    audio_source = MEDIA_FILES.get("etapa1b_audio")
    try:
        if audio_source and not audio_source.endswith('.ogg'):
            await context.bot.send_voice(chat_id=job.chat_id, voice=audio_source)
        elif audio_source:
            audio_path = pathlib.Path(__file__).parent / audio_source
            if audio_path.exists():
                with open(audio_path, 'rb') as audio_file:
                    await context.bot.send_voice(chat_id=job.chat_id, voice=audio_file)
    except Exception as e:
        log_error_detailed("Fallback 1B", e, f"Erro ao enviar áudio | User ID: {user_id}")

    reply_markup = InlineKeyboardMarkup([[ 
        InlineKeyboardButton(BOTOES_TEXTO["etapa1_sim"], callback_data="etapa1_sim")
    ]])
    await context.bot.send_message(chat_id=job.chat_id, text=MENSAGEM_ETAPA1B, reply_markup=reply_markup)
    
    if context.job_queue:
        user_context["etapa2_auto_job"] = context.job_queue.run_once(
            etapa2_auto, 60, chat_id=job.chat_id, data={"user_id": user_id}
        )

async def send_etapa2(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int):
    user_context = context.application.user_data.get(user_id, {})
    if user_context.get("current_stage") == "etapa2": return
    user_context["current_stage"] = "etapa2"

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(BOTOES_TEXTO["combo01"], callback_data="combo01")],
        [InlineKeyboardButton(BOTOES_TEXTO["combo02"], callback_data="combo02")],
        [InlineKeyboardButton(BOTOES_TEXTO["combo03"], callback_data="combo03")],
        [InlineKeyboardButton("🧪 TESTE Pack 2 (Pago)", callback_data="test_combo02")]
    ])
    
    message = await context.bot.send_message(chat_id=chat_id, text=MENSAGEM_ETAPA2, reply_markup=reply_markup)
    user_context['etapa2_message_id'] = message.message_id

    if context.job_queue:
        user_context["etapa2_fallback_job"] = context.job_queue.run_once(
            etapa2b_fallback, 60, chat_id=chat_id, data={"user_id": user_id}
        )

async def etapa2_auto(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    user_id = job.data.get('user_id')
    user_context = context.application.user_data.get(user_id, {})
    if not user_id or user_context.get("current_stage") != "etapa1":
        return
    log_card("FALLBACK", f"Executando etapa 2 automática | User: {user_id}", "fallback")
    await send_etapa2(context, job.chat_id, user_id)

async def etapa2b_fallback(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    user_id = job.data.get('user_id')
    user_context = context.application.user_data.get(user_id, {})
    if not user_id or user_context.get("current_stage") != "etapa2":
        return

    log_card("FALLBACK", f"Executando fallback 2B | User: {user_id}", "fallback")
    if etapa2_msg_id := user_context.get('etapa2_message_id'):
        try: await context.bot.delete_message(chat_id=job.chat_id, message_id=etapa2_msg_id)
        except Exception: pass

    audio_source = MEDIA_FILES.get("etapa2b_audio")
    try:
        if audio_source and not audio_source.endswith('.ogg'):
            await context.bot.send_voice(chat_id=job.chat_id, voice=audio_source)
        elif audio_source:
            audio_path = pathlib.Path(__file__).parent / audio_source
            if audio_path.exists():
                with open(audio_path, 'rb') as audio_file:
                    await context.bot.send_voice(chat_id=job.chat_id, voice=audio_file)
    except Exception as e:
        log_error_detailed("Fallback 2B", e, f"Erro ao enviar áudio | User ID: {user_id}")

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(BOTOES_TEXTO["combo01"], callback_data="combo01")],
        [InlineKeyboardButton(BOTOES_TEXTO["combo02"], callback_data="combo02")],
        [InlineKeyboardButton(BOTOES_TEXTO["combo03"], callback_data="combo03")]
    ])
    await context.bot.send_message(chat_id=job.chat_id, text=MENSAGEM_ETAPA2B, reply_markup=reply_markup)

async def etapa5_remaketing(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    user_id = job.data.get('user_id')
    if not user_id:
        return

    log_card("REMARKETING", f"Enviando Etapa 5 para | User: {user_id}", "job")
    
    reply_markup = InlineKeyboardMarkup([[ 
        InlineKeyboardButton(BOTOES_TEXTO["etapa5_gostei"], callback_data="etapa5_gostei")
    ]])
    
    await context.bot.send_message(chat_id=job.chat_id, text=MENSAGEM_ETAPA5, reply_markup=reply_markup)
    
    if context.job_queue:
        if user_id not in context.application.user_data:
            context.application.user_data[user_id] = {}
        user_context = context.application.user_data[user_id]
        user_context["etapa5_1_fallback_job"] = context.job_queue.run_once(
            etapa5_1_auto, 120, chat_id=job.chat_id, data={"user_id": user_id}
        )

async def etapa5_1_auto(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    user_id = job.data.get('user_id')
    if not user_id:
        return
    
    log_card("FALLBACK", f"Executando fallback para Etapa 5.1 | User: {user_id}", "fallback")
    await send_etapa5_1(context, job.chat_id, user_id)

async def send_etapa5_1(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int):
    log_card("REMARKETING", f"Enviando Etapa 5.1 para | User: {user_id}", "job")
    
    audio_source = MEDIA_FILES.get("etapa5_1_audio")
    try:
        if audio_source and not audio_source.endswith('.ogg'):
            await context.bot.send_voice(chat_id=chat_id, voice=audio_source)
        elif audio_source:
            audio_path = pathlib.Path(__file__).parent / audio_source
            if audio_path.exists():
                with open(audio_path, 'rb') as audio_file:
                    await context.bot.send_voice(chat_id=chat_id, voice=audio_file)
    except Exception as e:
        log_error_detailed("Remarketing 5.1", e, f"Erro ao enviar áudio | User ID: {user_id}")

    reply_markup = InlineKeyboardMarkup([[ 
        InlineKeyboardButton(BOTOES_TEXTO["etapa5_1_ver_mais"], url="https://t.me/anacardoso25_bot?start=TRANSFER")
    ]])
    await context.bot.send_message(chat_id=chat_id, text=MENSAGEM_ETAPA5_1, reply_markup=reply_markup)

    if context.job_queue:
        if user_id not in context.application.user_data:
            context.application.user_data[user_id] = {}
        user_context = context.application.user_data[user_id]
        user_context["etapa5_2_fallback_job"] = context.job_queue.run_once(
            etapa5_2_auto, 120, chat_id=chat_id, data={"user_id": user_id}
        )

async def etapa5_2_auto(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    user_id = job.data.get('user_id')
    if not user_id:
        return
    
    log_card("FALLBACK", f"Executando fallback para Etapa 5.2 | User: {user_id}", "fallback")
    await send_etapa5_2(context, job.chat_id, user_id)

async def send_etapa5_2(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int):
    log_card("REMARKETING", f"Enviando Etapa 5.2 para | User: {user_id}", "job")
    
    video_source = MEDIA_FILES.get("etapa5_2_video")
    if video_source:
        try:
            await context.bot.send_video(chat_id=chat_id, video=video_source)
        except Exception as e:
            log_error_detailed("Remarketing 5.2", e, f"Erro ao enviar vídeo | User ID: {user_id}")

    reply_markup = InlineKeyboardMarkup([[ 
        InlineKeyboardButton(BOTOES_TEXTO["etapa5_2_ver_agora"], url="https://t.me/anacardoso25_bot?start=TRANSFER")
    ]])
    await context.bot.send_message(chat_id=chat_id, text=MENSAGEM_ETAPA5_2, reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if not user: return

    if user.id not in context.application.user_data:
        context.application.user_data[user.id] = {}
    user_context = context.application.user_data[user.id]

    # A limpeza de jobs agora é segura e não apaga o estado do usuário
    cleanup_user_jobs(context, user.id)
    log_user_action(f"Botão: {query.data}", user)

    if query.data == "etapa1_sim":
        await send_etapa2(context, update.effective_chat.id, user.id)
        return

    if query.data in ["combo01", "combo02", "combo03"]:
        user_context["current_stage"] = "combo_selected"
        combo_data = COMBOS_CONFIG[query.data]
        valor = combo_data["valor"]
        log_user_action(f"Seleção de Combo", user, f"Plano: {combo_data['nome']} | Valor: R$ {valor:.2f}")
        if short_id := user_context.get("short_id"):
            user_data = extract_user_data(user)
            await update_user_journey(short_id, user_data, {"selected_plan": combo_data['nome'], "plan_value": valor, "plan_selected_at": "NOW()"})
        await process_pix_generation(query, user, valor, context)
        return

    if query.data == "test_combo02":
        await query.message.delete()
        await send_paid_content(context, update.effective_chat.id, COMBOS_CONFIG["combo02"]["nome"], user)
        return

    if query.data.startswith("verificar_pagamento_"):
        await query.answer("🔄 Verificando pagamento...", show_alert=False)
        return

    if query.data == "voltar_planos":
        user_context["current_stage"] = "etapa2"
        await query.message.delete()
        await send_etapa2(context, update.effective_chat.id, user.id)
        return

    if query.data == "etapa5_gostei":
        await query.message.delete()
        await send_etapa5_1(context, update.effective_chat.id, user.id)
        return

    

async def process_pix_generation(query, user, valor: float, context) -> None:
    if user.id not in context.application.user_data:
        context.application.user_data[user.id] = {}
    user_context = context.application.user_data[user.id]
    user_context["current_stage"] = "pix_generated"
    
    customer_name = f"{user.first_name} {user.last_name or ''}".strip()
    customer_data = {"name": customer_name, "email": f"user{user.id}@telegram.bot", "cpf": str(user.id).zfill(11)[:11], "address": "Brasil"}
    
    tracking_data = user_context.get("tracking_data", {})
    serializable_tracking = {k: str(v) for k, v in tracking_data.items()}
    payload = {"amount": int(valor * 100), "customer": customer_data, "tracking": serializable_tracking}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{TRIBOPAY_API_URL}/pix/create", json=payload, timeout=30.0)
        if response.status_code in [200, 201]:
            pix_response = response.json()
            pix_code, transaction_id = pix_response.get("pix_code"), pix_response.get("transaction_id")
            if pix_code:
                combo_nome = next((c["nome"] for c in COMBOS_CONFIG.values() if c["valor"] == valor), f"Combo R$ {valor:.2f}")
                success_text = criar_mensagem_pix(combo_nome, valor, pix_code)
                pix_buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Já paguei", callback_data=f"verificar_pagamento_{transaction_id}")],
                    [InlineKeyboardButton("🔄 Escolher outro plano", callback_data="voltar_planos")]
                ])
                await query.edit_message_text(success_text, parse_mode="HTML", reply_markup=pix_buttons)
                if short_id := user_context.get("short_id"):
                    await update_user_journey(short_id, extract_user_data(user), {"pix_generated": True, "pix_generated_at": "NOW()", "pix_transaction_id": str(transaction_id)})
                
                # Simulação do envio de conteúdo pago
                await send_paid_content(context, query.message.chat.id, combo_nome, user)

            else:
                await query.edit_message_text(MENSAGEM_PIX_ERRO, parse_mode="Markdown")
        else:
            await query.edit_message_text(MENSAGEM_PIX_ERRO, parse_mode="Markdown")
    except Exception as e:
        log_error_detailed("Geração PIX", e, f"User: {format_user_info(user)}")
        await query.edit_message_text(MENSAGEM_PIX_ERRO, parse_mode="Markdown")

async def send_paid_content(context: ContextTypes.DEFAULT_TYPE, chat_id: int, combo_nome: str, user: Update.effective_user):
    """Envia o conteúdo pago com base no combo selecionado."""
    if user.id not in context.application.user_data:
        context.application.user_data[user.id] = {}
    user_context = context.application.user_data[user.id]
    
    # Mapeia o nome do combo para a configuração do combo
    combo_key = None
    for key, config in COMBOS_CONFIG.items():
        if config["nome"] == combo_nome:
            combo_key = key
            break

    if not combo_key:
        log_card("ERRO DE CONTEÚDO", f"Combo '{combo_nome}' não encontrado nas configurações.", "error")
        return

    # Define o conteúdo a ser enviado para cada combo
    media_to_send = []
    if combo_key == "combo01":
        media_to_send.extend([
            PAID_PACKS["images"]["imagem1"],
            PAID_PACKS["images"]["imagem2"],
            PAID_PACKS["images"]["imagem3"],
            PAID_PACKS["images"]["imagem4"],
        ])
    elif combo_key == "combo02":
        media_to_send.extend([
            PAID_PACKS["videos"]["video1"],
            PAID_PACKS["videos"]["video2"],
            PAID_PACKS["images"]["imagem1"],
            PAID_PACKS["images"]["imagem2"],
            PAID_PACKS["images"]["imagem3"],
            PAID_PACKS["images"]["imagem4"],
            PAID_PACKS["images"]["imagem5"],
            PAID_PACKS["images"]["imagem6"],
        ])
    elif combo_key == "combo03":
        media_to_send.extend([
            PAID_PACKS["videos"]["video1"],
            PAID_PACKS["videos"]["video2"],
            PAID_PACKS["videos"]["video3"],
            PAID_PACKS["videos"]["video4"],
            PAID_PACKS["images"]["imagem1"],
            PAID_PACKS["images"]["imagem2"],
            PAID_PACKS["images"]["imagem3"],
            PAID_PACKS["images"]["imagem4"],
            PAID_PACKS["images"]["imagem5"],
            PAID_PACKS["images"]["imagem6"],
            PAID_PACKS["images"]["imagem7"],
            PAID_PACKS["images"]["imagem8"],
            PAID_PACKS["images"]["imagem9"],
            PAID_PACKS["images"]["imagem10"],
        ])

    # Separa mídias em grupos de imagens e vídeos
    image_group = []
    video_group = []
    for file_id in media_to_send:
        if file_id.startswith("BAAC"): # Vídeo
            video_group.append(InputMediaVideo(media=file_id))
        elif file_id.startswith("AgAC"): # Imagem
            image_group.append(InputMediaPhoto(media=file_id))

    # Envia o grupo de imagens, se houver
    if image_group:
        try:
            await context.bot.send_media_group(chat_id=chat_id, media=image_group)
        except Exception as e:
            log_error_detailed("ENVIO DE MÍDIA PAGA", e, f"Erro ao enviar grupo de imagens")

    # Envia o grupo de vídeos, se houver
    if video_group:
        try:
            await context.bot.send_media_group(chat_id=chat_id, media=video_group)
        except Exception as e:
            log_error_detailed("ENVIO DE MÍDIA PAGA", e, f"Erro ao enviar grupo de vídeos")

    # Envia a mensagem de texto final
    await context.bot.send_message(chat_id=chat_id, text="Ta aqui meu bem\n\nDa uma olhada e me fala se gostou ❤️")

    # Agenda o remarketing da ETAPA 5
    if context.job_queue:
        user_context["remaketing_job"] = context.job_queue.run_once(
            etapa5_remaketing, 20, chat_id=chat_id, data={"user_id": user.id}
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, Exception):
        log_error_detailed("Erro Global", context.error, f"Update: {update}")
    else:
        log_card("GLOBAL ERROR", f"Update {update} causou erro: {context.error}", "error")

# ═══════════════════════════════════════════════════════════════
# 🚀 INICIALIZAÇÃO DO BOT (🚫 NÃO ALTERAR)
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    if not BOT_TOKEN:
        log_card("CONFIG ERROR", "BOT_TOKEN não configurado", "error")
        return
    
    log_card("BOT STARTUP", f"Iniciando {BOT_CONFIG['nome']} v{BOT_CONFIG['versao']}", "startup")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    
    log_card("BOT READY", "Bot configurado e pronto para usar", "success")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
