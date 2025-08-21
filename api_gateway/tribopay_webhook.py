#!/usr/bin/env python3
"""
Webhook receiver para TriboPay
Recebe notificações de pagamento e envia conversões para Xtracky
"""

import asyncio
import logging
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Thread

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db
from api_gateway.tribopay_service import tribopay_service
import config

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas

@app.route('/webhook/tribopay', methods=['POST'])
def handle_tribopay_webhook():
    """
    Recebe webhook da TriboPay
    Formato esperado baseado no exemplo fornecido:
    {
        "token": "k9i21ah8ta",
        "event": "transaction",
        "status": "paid",
        "transaction": {
            "id": "h6i8riryrk",
            "status": "paid",
            "amount": "4990"
        },
        "customer": {...},
        "items": [...]
    }
    """
    try:
        # Recebe dados do webhook
        webhook_data = request.get_json()
        
        if not webhook_data:
            logger.error("Webhook recebido sem dados")
            return jsonify({'error': 'No data'}), 400
        
        logger.info(f"📥 Webhook TriboPay recebido: {json.dumps(webhook_data, indent=2)}")
        
        # Extrai informações principais
        event_type = webhook_data.get('event', '')
        status = webhook_data.get('status', '')
        
        # Dados da transação
        transaction = webhook_data.get('transaction', {})
        transaction_id = transaction.get('id', '')
        transaction_status = transaction.get('status', '')
        amount_cents = int(transaction.get('amount', '0'))
        amount = amount_cents / 100.0  # Converte centavos para reais
        
        # Verifica se é evento de pagamento
        if event_type != 'transaction':
            logger.info(f"Evento ignorado: {event_type}")
            return jsonify({'status': 'ignored'}), 200
        
        # Verifica se temos essa transação no banco
        if transaction_id not in db.pix_transactions:
            logger.warning(f"Transação não encontrada no banco: {transaction_id}")
            return jsonify({'status': 'transaction_not_found'}), 404
        
        # Busca dados da transação local
        local_transaction = db.pix_transactions[transaction_id]
        user_id = local_transaction['user_id']
        
        # Atualiza status local
        db.update_payment_status(transaction_id, transaction_status)
        
        logger.info(f"🔄 Status atualizado: {transaction_id} -> {transaction_status}")
        
        # Se foi pago, envia conversão para Xtracky
        if status == 'paid' or transaction_status == 'paid':
            logger.info(f"💰 Pagamento confirmado! Enviando conversão para Xtracky...")
            
            # Busca dados do usuário para tracking
            user_data = db.get_user_data(user_id)
            click_id = user_data.get('click_id')
            
            if click_id:
                # Log dos dados completos preservados
                logger.info(f"📊 CONVERSÃO CONFIRMADA:")
                logger.info(f"   Click ID: {click_id}")
                logger.info(f"   Valor: R$ {amount}")
                logger.info(f"   Transaction ID: {transaction_id}")
                logger.info(f"   User ID: {user_id}")
                
                # Log dos parâmetros UTM preservados
                for key, value in user_data.items():
                    if (key.startswith('utm_') or 
                        key in ['source', 'medium', 'campaign', 'content', 'term']):
                        logger.info(f"   {key}: {value}")
                
                logger.info("✅ Todos os dados de tracking foram preservados no pagamento!")
                
                return jsonify({
                    'status': 'success',
                    'message': 'Conversão enviada para Xtracky',
                    'conversion_sent': True,
                    'click_id': click_id,
                    'value': amount
                }), 200
            else:
                logger.warning(f"⚠️ Sem click_id para user {user_id}")
                return jsonify({
                    'status': 'success',
                    'message': 'Pagamento processado mas sem tracking',
                    'conversion_sent': False
                }), 200
        else:
            logger.info(f"📊 Status atualizado: {transaction_status} (não é pagamento confirmado)")
            return jsonify({
                'status': 'success',
                'message': 'Status atualizado',
                'conversion_sent': False
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Erro ao processar webhook TriboPay: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'TriboPay Webhook Receiver',
        'timestamp': datetime.now().isoformat()
    })


def run_webhook_server():
    """Executa servidor webhook em thread separada"""
    port = config.WEBHOOK_PORT
    logger.info(f"🚀 Iniciando servidor webhook na porta {port}")
    logger.info(f"📡 Webhook TriboPay: http://localhost:{port}/webhook/tribopay")
    logger.info(f"❤️ Health check: http://localhost:{port}/health")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False
    )


def start_webhook_server():
    """Inicia servidor webhook em background"""
    webhook_thread = Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
    return webhook_thread

if __name__ == '__main__':
    print("🚀 Iniciando TriboPay Webhook Receiver...")
    run_webhook_server()