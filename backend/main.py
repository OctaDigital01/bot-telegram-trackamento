#!/usr/bin/env python3
"""
Ponto de entrada principal para o deploy no Railway
Inicia tanto o bot Telegram quanto o servidor webhook
"""

import logging
import signal
import sys
import time

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handler para sinais do sistema"""
    logger.info("Recebido sinal de interrupção. Finalizando aplicação...")
    sys.exit(0)

def main():
    """Função principal que inicia bot + webhook"""
    
    # Configura handlers de sinal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 === XTRACKY BOT + WEBHOOK INICIANDO ===")
    logger.info("📡 Railway Deploy - Bot Telegram com TriboPay e Xtracky")
    logger.info("=" * 50)
    
    try:
        # Importa e inicia webhook server
        from src.api_gateway.tribopay_webhook import start_webhook_server
        logger.info("📡 Iniciando servidor webhook...")
        start_webhook_server()
        
        # Aguarda um momento para webhook inicializar
        time.sleep(2)
        logger.info("✅ Servidor webhook iniciado com sucesso!")
        
        # Importa e inicia bot Telegram
        from src.bot.bot import main as bot_main
        logger.info("🤖 Iniciando Bot Telegram...")
        
        # Executa bot (blocking)
        bot_main()
        
    except KeyboardInterrupt:
        logger.info("Aplicação interrompida pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal na aplicação: {e}")
        raise
    finally:
        logger.info("Aplicação finalizada")

if __name__ == '__main__':
    main()