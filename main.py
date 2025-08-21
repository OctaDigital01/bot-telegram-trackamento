#!/usr/bin/env python3
"""
Bot Telegram - Funil de Vendas
"""

import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, ChatJoinRequest
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ChatJoinRequestHandler
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONSTANTES E CONFIGURAÇÕES ---
BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))
GROUP_INVITE_LINK = "https://t.me/+iydDH1RTDPJlNTNh"

# File IDs
START_IMAGE_ID = 'AgACAgEAAxkBAAIikminXIWOkl4Ru-3c7KFTNPmeUA6QAALsrjEbglU4RYKi9nkfTnf8AQADAgADeQADNgQ'
PREVIEW_VIDEO_ID = 'BAACAgEAAxkBAAIilminXJOuWQ9uS_ZNt6seh7JKYoOHAAJtBgACglU4RRTfnPJAqPT3NgQ'
PREVIEW_IMAGE_1_ID = 'AgACAgEAAxkBAAIimminXJm9zlFbOKnhm3NO2CwyYo8kAALtrjEbglU4RfgJ-nP8LfvFAQADAgADeQADNgQ'
PREVIEW_IMAGE_2_ID = 'AgACAgEAAxkBAAIinminXKGMK_ue_HOK0Va36FJWO66vAALurjEbglU4RbhisJEkbnbqAQADAgADeQADNgQ'
PREVIEW_IMAGE_3_ID = 'AgACAgEAAxkBAAIiominXKpBBmO4jkUUhssoYeHj57hUAALvrjEbglU4RYevSIpIW_DuAQADAgADeQADNgQ'

# --- ETAPA 3: PRÉVIAS ---
async def step3_previews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia a galeria de prévias e as mensagens da Etapa 3."""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    logger.info(f"Enviando Etapa 3 (Prévias) para o chat {chat_id}")

    media_group = [
        InputMediaVideo(media=PREVIEW_VIDEO_ID),
        InputMediaPhoto(media=PREVIEW_IMAGE_1_ID),
        InputMediaPhoto(media=PREVIEW_IMAGE_2_ID),
        InputMediaPhoto(media=PREVIEW_IMAGE_3_ID),
    ]
    
    await context.bot.send_media_group(chat_id=chat_id, media=media_group)
    
    # Espera 7 segundos
    await asyncio.sleep(7)

    await context.bot.send_message(
        chat_id=chat_id,
        text="Gostou do que viu, meu bem 🤭?\n\nEssa é só uma PRÉVIA borrada do que te espera bb... 💦"
    )
    
    text2 = ("""
Tenho muito mais no VIP pra você (TOTALMENTE SEM CENSURA):
💎 Vídeos e fotos do jeitinho que você gosta...
💎 Videos exclusivo pra você, te fazendo go.zar só eu e você
💎 Meu contato pessoal
💎 Sempre posto coisa nova lá
💎 E muito mais meu bem...

Vem goz.ar po.rra quentinha pra mim🥵💦⬇️"""
    )

    keyboard = [[InlineKeyboardButton("CONHECER O VIP🔥", callback_data='vip_options')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text2,
        reply_markup=reply_markup
    )

# --- ETAPA 2: BOAS-VINDAS ---
async def send_step2_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Envia a mensagem de boas-vindas da Etapa 2."""
    logger.info(f"Enviando Etapa 2 (Boas-vindas) para o chat {chat_id}")

    text = "Meu bem, já vou te aceitar no meu grupinho, ta bom?\n\nMas neem precisa esperar, clica aqui no botão pra ver um pedacinho do que te espera... 🔥(É DE GRAÇA!!!)⬇️"
    keyboard = [[InlineKeyboardButton("VER CONTEÚDINHO DE GRAÇA 🔥🥵", callback_data='step3_previews')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup
    )

# --- ETAPA 1: COMANDO /START ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerencia o comando /start e o fluxo inicial."""
    user = update.effective_user
    logger.info(f"Usuário {user.id} ({user.first_name}) iniciou o bot.")

    try:
        chat_member = await context.bot.get_chat_member(chat_id=GROUP_ID, user_id=user.id)
        is_in_group = chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.warning(f"Não foi possível verificar o status do usuário {user.id} no grupo {GROUP_ID}: {e}")
        is_in_group = False

    # Alternativa: Usuário já está no grupo
    if is_in_group:
        logger.info(f"Usuário {user.id} já está no grupo.")
        text = "Meu bem, que bom te ver de novo! 🔥 Clica aqui pra não perder as novidades quentes que preparei pra você! ⬇️"
        keyboard = [[InlineKeyboardButton("VER CONTEÚDINHO DE GRAÇA 🔥🥵", callback_data='step3_previews')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_photo(
            photo=START_IMAGE_ID,
            caption=text,
            reply_markup=reply_markup
        )
        return

    # Padrão: Novo usuário ou com parâmetro
    click_id_param = " ".join(context.args) if context.args else None
    if click_id_param:
        logger.info(f"Usuário {user.id} veio com o parâmetro: {click_id_param}")
        text = f"Você veio através do meu KWAI (*{click_id_param}*)\n\nMeu bem, entra no meu *GRUPINHO GRÁTIS* pra ver daquele jeito q vc gosta 🥵⬇️"
    else:
        logger.info(f"Usuário {user.id} é novo.")
        text = "Meu bem, entra no meu *GRUPINHO GRÁTIS* pra ver daquele jeito q vc gosta 🥵⬇️"

    keyboard = [[InlineKeyboardButton("MEU GRUPINHO🥵?", url=GROUP_INVITE_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_photo(
        photo=START_IMAGE_ID,
        caption=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

# --- CALLBACK DO PAGAMENTO (PLACEHOLDER) ---
async def vip_options_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para o botão de conhecer o VIP."""
    query = update.callback_query
    await query.answer()
    # CONFIGURAR PAGAMENTO
    await query.message.reply_text("Aqui serão exibidas as opções de pagamento VIP.")
    logger.info(f"Usuário {query.from_user.id} clicou para conhecer o VIP.")

# --- APROVAÇÃO DE ENTRADA NO GRUPO ---
async def approve_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lida com pedidos de entrada no grupo."""
    join_request: ChatJoinRequest = update.chat_join_request
    user_id = join_request.from_user.id

    if join_request.chat.id == GROUP_ID:
        logger.info(f"Recebido pedido de entrada de {user_id} no grupo {GROUP_ID}.")
        
        # Envia a Etapa 2 imediatamente
        await send_step2_message(context, user_id)
        
        # Espera 30 segundos
        await asyncio.sleep(30)
        
        # Aprova a entrada
        try:
            await context.bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=user_id)
            logger.info(f"Aprovada entrada de {user_id} no grupo.")
        except Exception as e:
            logger.error(f"Falha ao aprovar usuário {user_id}: {e}")

# --- FUNÇÃO PRINCIPAL ---
def main():
    """Inicia o bot e configura os handlers."""
    if not BOT_TOKEN:
        logger.critical("Variável de ambiente TELEGRAM_TOKEN não encontrada.")
        return
    if not GROUP_ID:
        logger.critical("Variável de ambiente GROUP_ID não encontrada.")
        return

    logger.info("🤖 === BOT INICIANDO ===")

    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers de Comando
    application.add_handler(CommandHandler("start", start_command))

    # Handlers de Callback (botões)
    application.add_handler(CallbackQueryHandler(step3_previews, pattern='^step3_previews$'))
    application.add_handler(CallbackQueryHandler(vip_options_callback, pattern='^vip_options$'))

    # Handler de Pedidos de Entrada
    application.add_handler(ChatJoinRequestHandler(approve_join_request))

    logger.info("🚀 Bot iniciado com sucesso!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()