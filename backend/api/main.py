#!/usr/bin/env python3
"""
API Gateway - Serviço isolado
Webhooks, APIs REST e integrações
"""

import os
import logging
import json
import asyncio
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Thread
from database import get_db

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações
WEBHOOK_PORT = int(os.getenv('PORT', '8080'))
DATABASE_URL = os.getenv('DATABASE_URL')
TRIBOPAY_API_KEY = os.getenv('TRIBOPAY_API_KEY', 'IzJsCJ0BleuURRzZvrTeigPp6xknO8e9nHT6WZtDpxFQVocwa3E3GYeNXtYq')
XTRACKY_TOKEN = os.getenv('XTRACKY_TOKEN', '72701474-7e6c-4c87-b84f-836d4547a4bd')

# Flask app
app = Flask(__name__)
CORS(app)

# Database PostgreSQL
try:
    db = get_db()
    logger.info("✅ PostgreSQL conectado com sucesso")
except Exception as e:
    logger.error(f"❌ Erro ao conectar PostgreSQL: {e}")
    db = None

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'API Gateway',
        'timestamp': datetime.now().isoformat(),
        'database': 'PostgreSQL' if db else 'Memory',
        'database_url': DATABASE_URL[:50] + '...' if DATABASE_URL else None
    })

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'API Gateway - Bot Telegram Tracking',
        'version': '1.0',
        'endpoints': ['/health', '/api/users', '/api/tracking/get/<id>', '/api/pix/gerar', '/webhook/tribopay']
    })

@app.route('/api/users', methods=['POST'])
def save_user():
    """Salva dados do usuário"""
    try:
        data = request.get_json()
        telegram_id = int(data.get('telegram_id') or data.get('user_id'))
        
        if db:
            db.save_user(
                telegram_id=telegram_id,
                username=data.get('username'),
                first_name=data.get('first_name') or data.get('name'),
                last_name=data.get('last_name'),
                tracking_data=data.get('tracking_data', {})
            )
            logger.info(f"✅ Usuário {telegram_id} salvo no PostgreSQL")
            return jsonify({'success': True, 'user_id': str(telegram_id)})
        else:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
    except Exception as e:
        logger.error(f"❌ Erro salvando usuário: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Recupera dados do usuário"""
    try:
        if db:
            user_data = db.get_user(int(user_id))
            if user_data:
                return jsonify({'success': True, 'user': dict(user_data)})
            else:
                return jsonify({'success': False, 'error': 'User not found'}), 404
        else:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tracking/save', methods=['POST'])
def save_tracking():
    """Salvar mapeamento de tracking"""
    try:
        data = request.get_json()
        safe_id = data.get('safe_id')
        original = data.get('original')
        
        if not safe_id or not original:
            return jsonify({'success': False, 'error': 'safe_id e original são obrigatórios'}), 400
        
        if db:
            db.save_tracking_mapping(safe_id, original)
            logger.info(f"✅ Tracking ID {safe_id} salvo no PostgreSQL")
            return jsonify({'success': True, 'message': 'Tracking salvo'})
        else:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
    except Exception as e:
        logger.error(f'❌ Erro ao salvar tracking: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tracking/get/<safe_id>', methods=['GET'])
def get_tracking(safe_id):
    """Recupera click_id original do mapeamento"""
    try:
        if db:
            mapping_data = db.get_tracking_mapping(safe_id)
            if mapping_data:
                return jsonify({
                    'success': True,
                    'safe_id': safe_id,
                    'original': mapping_data['original_data'],
                    'created': mapping_data['created_at'].isoformat()
                })
            else:
                # Fallback: retorna o próprio ID
                return jsonify({
                    'success': False, 
                    'safe_id': safe_id, 
                    'original': safe_id
                })
        else:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tracking/latest', methods=['GET'])
def get_latest_tracking():
    """Recupera o último tracking salvo (para novos usuários)"""
    try:
        if db:
            latest_data = db.get_latest_tracking(minutes=10)
            if latest_data:
                return jsonify({
                    'success': True,
                    'safe_id': latest_data['safe_id'],
                    'original': latest_data['original_data'],
                    'created': latest_data['created_at'].isoformat()
                })
            else:
                return jsonify({'success': False, 'message': 'No recent tracking found'})
        else:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/pix/gerar', methods=['POST'])
def gerar_pix():
    """Gera PIX via TriboPay"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        valor = data.get('valor', 10.0)
        plano = data.get('plano', 'VIP')
        
        # Busca dados do usuário no PostgreSQL
        if db:
            user_data = db.get_user(int(user_id))
            if user_data:
                tracking_data = {
                    'click_id': user_data.get('click_id'),
                    'utm_source': user_data.get('utm_source'),
                    'utm_medium': user_data.get('utm_medium'),
                    'utm_campaign': user_data.get('utm_campaign'),
                    'utm_term': user_data.get('utm_term'),
                    'utm_content': user_data.get('utm_content')
                }
            else:
                tracking_data = {}
        else:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        logger.info(f"💰 Gerando PIX REAL TriboPay R$ {valor} para usuário {user_id}")
        logger.info(f"📊 Tracking preservado: {tracking_data}")
        
        # Gera PIX REAL via TriboPay API
        tribopay_payload = {
            "amount": valor,
            "description": f"Pagamento {plano} - Sistema Xtracky",
            "external_id": f"user_{user_id}_{int(datetime.now().timestamp())}",
            "payer_name": user_data.get('first_name', 'Cliente') if user_data else 'Cliente',
            "webhook_url": "https://api-gateway-production-22bb.up.railway.app/webhook/tribopay",
            "metadata": {
                "user_id": str(user_id),
                "plano": plano,
                "tracking": tracking_data
            }
        }
        
        tribopay_headers = {
            "Authorization": f"Bearer {TRIBOPAY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Faz requisição para TriboPay
        logger.info(f"🚀 Fazendo requisição TriboPay: {tribopay_payload}")
        
        try:
            response = requests.post(
                "https://api.tribopay.com.br/api/public/v1/transactions",
                json=tribopay_payload,
                headers=tribopay_headers,
                timeout=10
            )
            
            logger.info(f"📡 TriboPay Response Status: {response.status_code}")
            logger.info(f"📡 TriboPay Response: {response.text}")
            
            if response.status_code != 201:
                logger.error(f"❌ Erro TriboPay: {response.status_code} - {response.text}")
                # FALLBACK: Gera PIX local se TriboPay falhar
                logger.warning("⚠️ Usando PIX de fallback")
                transaction_id = f"fallback_{int(datetime.now().timestamp())}"
                pix_code = f"00020126580014BR.GOV.BCB.PIX0136{transaction_id}520400005303986540{valor:.2f}5802BR5925TRIBOPAY FALLBACK6009SAO PAULO62140510{transaction_id}6304"
                qr_code = None
                tribopay_data = {"fallback": True, "error": response.text}
            else:
                tribopay_data = response.json()
                transaction_id = tribopay_data.get('id')
                pix_code = tribopay_data.get('pix_code') or tribopay_data.get('qr_code_text')
                qr_code = tribopay_data.get('qr_code')
                logger.info(f"✅ PIX TriboPay gerado com sucesso: {transaction_id}")
                
        except Exception as tribopay_error:
            logger.error(f"❌ Erro de conexão TriboPay: {tribopay_error}")
            # FALLBACK: Gera PIX local se TriboPay não responder
            logger.warning("⚠️ TriboPay indisponível - usando PIX de fallback")
            transaction_id = f"fallback_{int(datetime.now().timestamp())}"
            pix_code = f"00020126580014BR.GOV.BCB.PIX0136{transaction_id}520400005303986540{valor:.2f}5802BR5925TRIBOPAY ERROR6009SAO PAULO62140510{transaction_id}6304"
            qr_code = None
            tribopay_data = {"fallback": True, "error": str(tribopay_error)}
        
        # Salva transação no PostgreSQL
        if db:
            db.save_pix_transaction(
                transaction_id=transaction_id,
                telegram_id=int(user_id),
                amount=valor,
                tracking_data=tracking_data
            )
            db.update_pix_transaction(
                transaction_id=transaction_id,
                status='pending',
                pix_code=pix_code
            )
        else:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        logger.info(f"✅ PIX TriboPay gerado: {transaction_id}")
        
        return jsonify({
            'success': True,
            'transaction_id': transaction_id,
            'pix_copia_cola': pix_code,
            'qr_code': qr_code,
            'valor': valor,
            'status': 'pending',
            'tracking_preservado': tracking_data,
            'tribopay_response': tribopay_data
        })
        
    except Exception as e:
        logger.error(f"❌ Erro gerando PIX: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/webhook/tribopay', methods=['POST'])
def tribopay_webhook():
    """Webhook REAL para notificações TriboPay"""
    try:
        webhook_data = request.get_json()
        logger.info(f"📥 Webhook TriboPay REAL: {webhook_data}")
        
        # Processa webhook TriboPay real
        transaction_id = webhook_data.get('id') or webhook_data.get('transaction_id')
        status = webhook_data.get('status')
        event_type = webhook_data.get('event_type')
        
        # Validação do webhook TriboPay
        if not transaction_id:
            logger.error("❌ Webhook sem transaction_id")
            return jsonify({'error': 'Missing transaction_id'}), 400
        
        logger.info(f"🔍 Processando: {transaction_id} - Status: {status} - Evento: {event_type}")
        
        if db:
            transaction = db.get_pix_transaction(transaction_id)
            if transaction:
                db.update_pix_transaction(transaction_id, status=status)
                logger.info(f"✅ Status atualizado no PostgreSQL: {transaction_id} -> {status}")
                
                if status in ['paid', 'completed', 'approved']:
                    # Conversão confirmada - Envia para Xtracky
                    tracking_data = {
                        'click_id': transaction.get('click_id'),
                        'utm_source': transaction.get('utm_source'),
                        'utm_medium': transaction.get('utm_medium'),
                        'utm_campaign': transaction.get('utm_campaign'),
                        'utm_term': transaction.get('utm_term'),
                        'utm_content': transaction.get('utm_content')
                    }
                    
                    logger.info(f"🎯 CONVERSÃO REAL CONFIRMADA: {tracking_data}")
                    
                    # Envia conversão para Xtracky API
                    if tracking_data.get('click_id'):
                        xtracky_payload = {
                            "click_id": tracking_data.get('click_id'),
                            "conversion_value": float(transaction.get('amount', 0)),
                            "currency": "BRL",
                            "utm_source": tracking_data.get('utm_source'),
                            "utm_campaign": tracking_data.get('utm_campaign'),
                            "utm_medium": tracking_data.get('utm_medium')
                        }
                        
                        xtracky_headers = {
                            "Authorization": f"Bearer {XTRACKY_TOKEN}",
                            "Content-Type": "application/json"
                        }
                        
                        try:
                            import requests
                            xtracky_response = requests.post(
                                "https://api.xtracky.com/api/integrations/tribopay",
                                json=xtracky_payload,
                                headers=xtracky_headers,
                                timeout=10
                            )
                            
                            logger.info(f"🚀 Xtracky response: {xtracky_response.status_code}")
                            
                            # Log da conversão
                            db.log_conversion(
                                transaction_id=transaction_id,
                                click_id=tracking_data.get('click_id'),
                                utm_source=tracking_data.get('utm_source'),
                                utm_campaign=tracking_data.get('utm_campaign'),
                                conversion_value=transaction.get('amount'),
                                status='sent_to_xtracky',
                                xtracky_response=xtracky_response.text
                            )
                            
                        except Exception as xtracky_error:
                            logger.error(f"❌ Erro enviando para Xtracky: {xtracky_error}")
                            db.log_conversion(
                                transaction_id=transaction_id,
                                click_id=tracking_data.get('click_id'),
                                utm_source=tracking_data.get('utm_source'),
                                utm_campaign=tracking_data.get('utm_campaign'),
                                conversion_value=transaction.get('amount'),
                                status='xtracky_error',
                                xtracky_response=str(xtracky_error)
                            )
            else:
                logger.warning(f"⚠️ Transação não encontrada: {transaction_id}")
        else:
            logger.error("❌ Database não disponível para webhook")
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"❌ Erro webhook: {e}")
        return jsonify({'error': str(e)}), 500

def main():
    """Função principal"""
    logger.info("🔌 === API GATEWAY INICIANDO ===")
    logger.info(f"🌐 Porta: {WEBHOOK_PORT}")
    logger.info(f"🗄️ Database: {'PostgreSQL' if DATABASE_URL else 'Memory'}")
    logger.info(f"📡 Webhook: https://api-gateway.railway.app/webhook/tribopay")
    
    app.run(
        host='0.0.0.0',
        port=WEBHOOK_PORT,
        debug=False
    )

if __name__ == '__main__':
    main()