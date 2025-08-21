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

from ..database.database import db
from .tribopay_service import tribopay_service
from ..config import config

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

@app.route('/api/tracking/get/<mapping_id>', methods=['GET'])
def get_tracking_data(mapping_id):
    """
    Endpoint para recuperar dados de tracking mapeados
    """
    try:
        import os
        click_mapping_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'click_mapping.json')
        
        if not os.path.exists(click_mapping_path):
            return jsonify({'success': False, 'error': 'Arquivo de mapeamento não encontrado'}), 404
        
        with open(click_mapping_path, 'r') as f:
            click_mapping = json.load(f)
        
        if mapping_id not in click_mapping:
            logger.warning(f"ID mapeado não encontrado: {mapping_id}")
            return jsonify({'success': False, 'error': 'ID não encontrado'}), 404
        
        mapping_data = click_mapping[mapping_id]
        original_data = mapping_data.get('original', '{}')
        
        logger.info(f"📥 Recuperando dados para ID {mapping_id}: {original_data}")
        
        return jsonify({
            'success': True,
            'mapping_id': mapping_id,
            'original': original_data,
            'created': mapping_data.get('created')
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao recuperar dados de tracking: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tracking/latest', methods=['GET'])
def get_latest_tracking():
    """
    Endpoint para recuperar o último tracking salvo (para novos usuários)
    """
    try:
        import os
        click_mapping_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'click_mapping.json')
        
        if not os.path.exists(click_mapping_path):
            return jsonify({'success': False, 'error': 'Arquivo de mapeamento não encontrado'}), 404
        
        with open(click_mapping_path, 'r') as f:
            click_mapping = json.load(f)
        
        if not click_mapping:
            return jsonify({'success': False, 'error': 'Nenhum tracking disponível'}), 404
        
        # Encontra o mais recente (por data de criação)
        latest_entry = None
        latest_time = None
        
        for mapping_id, data in click_mapping.items():
            created_time = data.get('created')
            if created_time and (latest_time is None or created_time > latest_time):
                latest_time = created_time
                latest_entry = {
                    'mapping_id': mapping_id,
                    'original': data.get('original', '{}'),
                    'created': created_time
                }
        
        if latest_entry:
            logger.info(f"📥 Recuperando último tracking: {latest_entry}")
            return jsonify({
                'success': True,
                'safe_id': latest_entry['mapping_id'],
                'original': latest_entry['original'],
                'created': latest_entry['created']
            })
        else:
            return jsonify({'success': False, 'error': 'Nenhum tracking válido encontrado'}), 404
            
    except Exception as e:
        logger.error(f"❌ Erro ao recuperar último tracking: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
    import os
    port = config.WEBHOOK_PORT
    logger.info(f"🚀 Iniciando servidor webhook na porta {port}")
    if os.getenv('RAILWAY_ENVIRONMENT'):
        webhook_url = os.getenv('RAILWAY_STATIC_URL', 'railway-app.railway.app')
        logger.info(f"📡 Webhook TriboPay: https://{webhook_url}/webhook/tribopay")
        logger.info(f"📡 API Tracking: https://{webhook_url}/api/tracking/")
        logger.info(f"❤️ Health check: https://{webhook_url}/health")
    else:
        logger.info(f"📡 Webhook TriboPay: http://localhost:{port}/webhook/tribopay")
        logger.info(f"📡 API Tracking: http://localhost:{port}/api/tracking/")
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