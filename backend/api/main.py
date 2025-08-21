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
        logger.info(f"📥 Dados recebidos no API: {data}")
        
        telegram_id = int(data.get('telegram_id') or data.get('user_id'))
        tracking_data = data.get('tracking_data', {})

        # Normaliza tracking_data: aceita dict, JSON string, ou wrappers ({ original: '...', tracking: {...}})
        try:
            # Se tracking_data for string JSON, desserializa
            if isinstance(tracking_data, str):
                try:
                    tracking_data = json.loads(tracking_data)
                except Exception:
                    # deixa como objeto vazio se não for JSON
                    tracking_data = {}

            # Se veio um wrapper com 'original' (string JSON), tenta desserializar
            if isinstance(tracking_data, dict) and 'original' in tracking_data:
                original = tracking_data.get('original')
                if isinstance(original, str):
                    try:
                        parsed = json.loads(original)
                        # se o parsed tiver campo 'tracking', usa ele
                        if isinstance(parsed, dict) and 'tracking' in parsed:
                            tracking_data = parsed.get('tracking') or {}
                        else:
                            # parsed pode já ser o objeto de tracking
                            tracking_data = parsed or {}
                    except Exception:
                        # não é JSON, mantém como estava
                        tracking_data = {}

            # Se veio wrapper com 'tracking' como chave
            if isinstance(tracking_data, dict) and 'tracking' in tracking_data and isinstance(tracking_data.get('tracking'), dict):
                tracking_data = tracking_data.get('tracking')

        except Exception as e:
            logger.warning(f"⚠️ Falha ao normalizar tracking_data: {e}")
            tracking_data = {}

        logger.info(f"🔍 tracking_data normalizado: {tracking_data}")

        if db:
            db.save_user(
                telegram_id=telegram_id,
                username=data.get('username'),
                first_name=data.get('first_name') or data.get('name'),
                last_name=data.get('last_name'),
                tracking_data=tracking_data or {}
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
            logger.info(f"👤 Dados do usuário encontrados: {dict(user_data) if user_data else 'None'}")
            
            if user_data:
                tracking_data = {
                    'click_id': user_data.get('click_id'),
                    'utm_source': user_data.get('utm_source'),
                    'utm_medium': user_data.get('utm_medium'),
                    'utm_campaign': user_data.get('utm_campaign'),
                    'utm_term': user_data.get('utm_term'),
                    'utm_content': user_data.get('utm_content')
                }
                logger.info(f"🎯 Tracking extraído do banco: {tracking_data}")
            else:
                tracking_data = {}
                logger.warning(f"⚠️ Usuário {user_id} não encontrado no banco")
        else:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
        
        logger.info(f"💰 Gerando PIX REAL TriboPay R$ {valor} para usuário {user_id}")
        logger.info(f"📊 Tracking preservado: {tracking_data}")
        
        # Primeiro, criar produto na TriboPay (OBRIGATÓRIO)
        logger.info(f"📦 Criando produto na TriboPay")
        product_payload = {
            "title": f"Plano VIP - {plano}",
            "cover": "https://ana-cardoso.shop/icon-check.png",
            "sale_page": "https://ana-cardoso.shop",
            "payment_type": 1,
            "product_type": "digital",
            "delivery_type": 1,
            "id_category": 1,
            "amount": int(valor * 100)
        }
        
        # Headers apenas com Content-Type (api_token vai na URL)
        tribopay_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            # Criar produto primeiro
            product_response = requests.post(
                f"https://api.tribopay.com.br/api/public/v1/products?api_token={TRIBOPAY_API_KEY}",
                json=product_payload,
                headers=tribopay_headers,
                timeout=10
            )
            
            if product_response.status_code != 201:
                logger.error(f"❌ Erro ao criar produto: {product_response.status_code} - {product_response.text}")
                raise Exception(f"Erro ao criar produto: {product_response.text}")
            
            product_data = product_response.json()
            product_hash = product_data.get('hash', '')
            logger.info(f"✅ Produto criado: {product_hash}")
            
            # Agora criar a transação PIX com o formato CORRETO
            valor_centavos = int(valor * 100)
            
            # Adicionar parâmetros de tracking UTM ao payload
            tribopay_payload = {
                "amount": valor_centavos,
                "offer_hash": product_hash,  # OBRIGATÓRIO - hash do produto criado
                "payment_method": "pix",  # OBRIGATÓRIO
                "customer": {
                    "name": user_data.get('first_name', 'Cliente') if user_data else 'Cliente',
                    "email": f"user{user_id}@telegram.com",
                    "phone_number": "11999999999",
                    "document": "00000000000"
                },
                "cart": [
                    {
                        "product_hash": product_hash,
                        "title": f"Plano VIP - {plano}",
                        "price": valor_centavos,
                        "quantity": 1,
                        "operation_type": 1,
                        "tangible": False
                    }
                ],
                "expire_in_days": 1,  # Mínimo da API
                "transaction_origin": "api",
                "installments": 1,  # OBRIGATÓRIO para PIX
                "postback_url": "https://api-gateway-production-22bb.up.railway.app/webhook/tribopay",
                # TRACKING UTM - Formato correto para TriboPay (baseado no webhook)
                "tracking": {
                    "src": user_data.get('click_id') if user_data else None,
                    "utm_source": user_data.get('utm_source') if user_data else None,
                    "utm_campaign": user_data.get('utm_campaign') if user_data else None,
                    "utm_medium": user_data.get('utm_medium') if user_data else None,
                    "utm_term": user_data.get('utm_term') if user_data else None,
                    "utm_content": user_data.get('utm_content') if user_data else None
                }
            }
            
            tracking_payload = tribopay_payload.get('tracking', {})
            logger.info(f"🎯 Objeto tracking enviado para TriboPay: {tracking_payload}")
            logger.info(f"🚀 Payload completo TriboPay (tracking): {json.dumps(tracking_payload, indent=2)}")
            
            logger.info(f"🚀 Criando transação PIX na TriboPay")
            
            # Fazer requisição para criar transação (api_token na URL)
            response = requests.post(
                f"https://api.tribopay.com.br/api/public/v1/transactions?api_token={TRIBOPAY_API_KEY}",
                json=tribopay_payload,
                headers=tribopay_headers,
                timeout=10
            )
            
            logger.info(f"📡 TriboPay Response Status: {response.status_code}")
            logger.info(f"📡 TriboPay Response: {response.text}")
            
            if response.status_code == 201:
                tribopay_data = response.json()
                transaction_id = tribopay_data.get('hash', str(int(datetime.now().timestamp())))
                pix_data = tribopay_data.get('pix', {})
                pix_code = pix_data.get('pix_qr_code', '')
                qr_code = pix_data.get('qr_code', '')
                
                logger.info(f"✅ PIX TriboPay REAL gerado: {transaction_id}")
                logger.info(f"💳 PIX Code: {pix_code[:50]}..." if pix_code else "Sem PIX code")
            else:
                logger.error(f"❌ Erro TriboPay: {response.status_code} - {response.text}")
                # FALLBACK: Gera PIX local se TriboPay falhar
                logger.warning("⚠️ Usando PIX de fallback")
                transaction_id = f"fallback_{int(datetime.now().timestamp())}"
                pix_code = f"00020126580014BR.GOV.BCB.PIX0136{transaction_id}520400005303986540{valor:.2f}5802BR5925TRIBOPAY FALLBACK6009SAO PAULO62140510{transaction_id}6304"
                qr_code = None
                tribopay_data = {"fallback": True, "error": response.text}
                
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
        
        # Processa webhook TriboPay real (formato atualizado)
        transaction_data = webhook_data.get('transaction', {})
        transaction_id = (transaction_data.get('id') or 
                         webhook_data.get('token') or 
                         webhook_data.get('transaction_id') or
                         webhook_data.get('id'))
        status = webhook_data.get('status') or transaction_data.get('status')
        event_type = webhook_data.get('event')
        
        # Extrair dados de tracking do webhook
        tracking_webhook = webhook_data.get('tracking', {})
        
        logger.info(f"🎯 Tracking recebido no webhook:")
        logger.info(f"   utm_source: {tracking_webhook.get('utm_source')}")
        logger.info(f"   utm_campaign: {tracking_webhook.get('utm_campaign')}")
        logger.info(f"   utm_medium: {tracking_webhook.get('utm_medium')}")
        logger.info(f"   src: {tracking_webhook.get('src')}")
        
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
                    # Usa dados do webhook TriboPay como prioridade, fallback para dados do banco
                    tracking_data = {
                        'click_id': tracking_webhook.get('src') or transaction.get('click_id'),
                        'utm_source': tracking_webhook.get('utm_source') or transaction.get('utm_source'),
                        'utm_medium': tracking_webhook.get('utm_medium') or transaction.get('utm_medium'),
                        'utm_campaign': tracking_webhook.get('utm_campaign') or transaction.get('utm_campaign'),
                        'utm_term': tracking_webhook.get('utm_term') or transaction.get('utm_term'),
                        'utm_content': tracking_webhook.get('utm_content') or transaction.get('utm_content')
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