#!/usr/bin/env python3
"""
Script temporário para capturar File IDs das mídias
"""

import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

async def handle_media(update: Update, context):
    """Captura File IDs de mídias enviadas"""
    message = update.message
    
    if message.photo:
        # Pega a foto de maior resolução
        photo = message.photo[-1]
        logger.info(f"📸 FOTO FILE_ID: {photo.file_id}")
        await message.reply_text(f"📸 **FOTO CAPTURADA:**\n`{photo.file_id}`", parse_mode='Markdown')
    
    elif message.video:
        logger.info(f"🎥 VIDEO FILE_ID: {message.video.file_id}")
        await message.reply_text(f"🎥 **VÍDEO CAPTURADO:**\n`{message.video.file_id}`", parse_mode='Markdown')
    
    elif message.document:
        logger.info(f"📄 DOCUMENT FILE_ID: {message.document.file_id}")
        await message.reply_text(f"📄 **DOCUMENTO CAPTURADO:**\n`{message.document.file_id}`", parse_mode='Markdown')

def main():
    logger.info("🎯 === BOT CAPTURADOR DE FILE IDs INICIANDO ===")
    logger.info("📋 Envie fotos, vídeos ou documentos para capturar os File IDs")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handler para capturar todas as mídias
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL, 
        handle_media
    ))
    
    logger.info("🚀 Bot capturador iniciado! Envie mídias para obter os File IDs")
    application.run_polling()

if __name__ == '__main__':
    main()