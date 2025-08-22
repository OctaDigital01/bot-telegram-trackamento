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

# HASHES TRIBOPAY VÁLIDOS (CONFIRMADOS VIA API 22/08/2025)
def get_tribopay_offer_mapping():
    """Retorna mapeamento de ofertas válidas - Product: a8c1r56cgy (Acesso VIP - Ana Cardoso)"""
    return {
        # Ofertas principais (produto a8c1r56cgy)
        "plano_1mes": os.getenv('TRIBOPAY_OFFER_VIP_BASICO', 'deq4y2wybn'),      # R$ 24,90 - Oferta 24,90
        "plano_3meses": os.getenv('TRIBOPAY_OFFER_VIP_PREMIUM', 'zawit'),        # R$ 49,90 - 49.90  
        "plano_1ano": os.getenv('TRIBOPAY_OFFER_VIP_COMPLETO', '8qbmp'),         # R$ 67,00 - 67.00
        
        # Mapeamentos adicionais para compatibilidade
        "plano_desc_etapa5": os.getenv('TRIBOPAY_OFFER_VIP_BASICO', 'deq4y2wybn'),  # R$ 24,90
        "plano_desc_20_off": os.getenv('TRIBOPAY_OFFER_VIP_BASICO', 'deq4y2wybn'),   # R$ 24,90
        
        # Fallback padrão
        "default": os.getenv('TRIBOPAY_OFFER_DEFAULT', 'deq4y2wybn')             # R$ 24,90 - oferta padrão
    }

def get_offer_hash_by_plano_id(plano_id):
    """Retorna offer_hash baseado no plano_id via env vars"""
    mapping = get_tribopay_offer_mapping()
    offer_hash = mapping.get(plano_id, mapping["default"])
    logger.info(f"📦 Offer hash mapeado: {plano_id} -> {offer_hash}")
    return offer_hash

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
        'endpoints': ['/health', '/api/users', '/api/tracking/get/<id>', '/api/pix/gerar', '/api/pix/verificar/<user_id>/<plano_id>', '/api/pix/invalidar/<user_id>', '/webhook/tribopay']
    })

@app.route('/migrate/add_plano_id', methods=['POST'])
def migrate_add_plano_id():
    """Migração para adicionar coluna plano_id na tabela pix_transactions"""
    try:
        if not db:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
            
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Verifica se a coluna já existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='pix_transactions' AND column_name='plano_id'
            """)
            
            exists = cursor.fetchone()
            
            if not exists:
                # Adiciona a coluna plano_id
                cursor.execute("ALTER TABLE pix_transactions ADD COLUMN plano_id VARCHAR(100)")
                logger.info("✅ Coluna plano_id adicionada com sucesso")
                return jsonify({
                    'success': True, 
                    'message': 'Coluna plano_id adicionada com sucesso',
                    'migration': 'add_plano_id_column'
                })
            else:
                return jsonify({
                    'success': True, 
                    'message': 'Coluna plano_id já existe',
                    'migration': 'already_exists'
                })
                
    except Exception as e:
        logger.error(f"❌ Erro na migração: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
            logger.info(f"⚠️ TESTE LOCAL: Usuário {telegram_id} simulado como salvo (DB desabilitado)")
            return jsonify({'success': True, 'user_id': str(telegram_id), 'test_mode': True})
        
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

@app.route('/api/pix/verificar/<user_id>/<plano_id>', methods=['GET'])
def verificar_pix_existente(user_id, plano_id):
    """Verifica se existe PIX válido para o usuário e plano"""
    try:
        if db:
            # Busca PIX ativo do usuário para o plano específico (válido por 1h)
            pix_data = db.get_active_pix(int(user_id), plano_id)
            if pix_data:
                # Calcula tempo restante
                from datetime import datetime, timedelta
                created_at = pix_data.get('created_at')
                if created_at:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    
                    expire_time = created_at + timedelta(hours=1)
                    now = datetime.now()
                    if isinstance(created_at, datetime) and created_at.tzinfo:
                        now = datetime.now(created_at.tzinfo)
                    
                    if now < expire_time:
                        tempo_restante = int((expire_time - now).total_seconds() / 60)
                        return jsonify({
                            'success': True,
                            'pix_valido': True,
                            'tempo_restante': max(tempo_restante, 1),
                            'pix_data': {
                                'pix_copia_cola': pix_data.get('pix_code'),
                                'qr_code': pix_data.get('qr_code'),
                                'transaction_id': pix_data.get('transaction_id')
                            }
                        })
            
            return jsonify({'success': True, 'pix_valido': False})
        else:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
    except Exception as e:
        logger.error(f"❌ Erro verificando PIX existente: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/pix/invalidar/<user_id>', methods=['POST'])
def invalidar_pix_usuario(user_id):
    """Invalida todos os PIX pendentes do usuário"""
    try:
        if db:
            result = db.invalidate_user_pix(int(user_id))
            logger.info(f"🗑️ PIX do usuário {user_id} invalidados: {result}")
            return jsonify({'success': True, 'invalidated': result})
        else:
            return jsonify({'success': False, 'error': 'Database not available'}), 500
    except Exception as e:
        logger.error(f"❌ Erro invalidando PIX do usuário: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/pix/gerar', methods=['POST'])
def gerar_pix():
    """Gera PIX via TriboPay com cache de produtos"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        valor = data.get('valor', 10.0)
        plano_id = data.get('plano_id', 'default')  # ID do plano para mapeamento
        
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
        
        logger.info(f"💰 Gerando PIX R$ {valor} para usuário {user_id} (Deploy: c2025d8)")
        logger.info(f"📊 Tracking preservado: {tracking_data}")
        
        # Obtém offer_hash fixo baseado no plano_id
        offer_hash = get_offer_hash_by_plano_id(plano_id)
        
        if not offer_hash:
            logger.error("❌ Falha ao obter offer_hash para o plano")
            return jsonify({'success': False, 'error': 'Plano inválido'}), 500
        
        logger.info(f"✅ Offer TriboPay: {offer_hash} (plano: {plano_id})")
        
        # Headers para requisições TriboPay
        tribopay_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # FOCO EXCLUSIVO TRIBOPAY - Resolver problema real da API
        logger.info(f"🎯 TENTATIVA TRIBOPAY REAL - Conta: OCTA DIGITAL LTDA")
        logger.info(f"💰 Valor: R$ {valor} | Plano: {plano_id} | Offer: {offer_hash}")
        
        # Gera dados randomizados do cliente baseado no Telegram user
        def generate_customer_data(telegram_user_id):
            import random
            names = ['Ana Silva', 'João Santos', 'Maria Oliveira', 'Pedro Costa', 'Carla Lima', 'Bruno Souza', 'Julia Ferreira']
            cities = ['São Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Salvador', 'Fortaleza', 'Brasília', 'Curitiba']
            states = ['SP', 'RJ', 'MG', 'BA', 'CE', 'DF', 'PR']
            
            # Seed baseado no user_id para consistência
            random.seed(telegram_user_id)
            
            name = random.choice(names)
            city = random.choice(cities)
            state = random.choice(states)
            
            # CPF fake baseado no user_id (para testes)
            cpf_base = str(telegram_user_id)[-8:].zfill(8)
            cpf = f"{cpf_base}001"
            
            return {
                'name': name,
                'email': f"user{telegram_user_id}@telegram.com",
                'phone_number': f"+5511{random.randint(90000, 99999)}{random.randint(1000, 9999)}",
                'document': cpf,
                'zip_code': f"{random.randint(10000, 99999):05d}000",
                'street_name': 'Rua Principal',
                'number': str(random.randint(100, 9999)),
                'complement': '',
                'neighborhood': 'Centro',
                'city': city,
                'state': state,
                'country': 'BR'
            }
        
        # Dados do cliente randomizados
        customer_data = generate_customer_data(int(user_id))
        logger.info(f"👤 Cliente: {customer_data['name']} ({customer_data['email']})")
        
        # PAYLOAD TRIBOPAY COMPLETO
        tribopay_payload = {
            "amount": int(valor * 100),
            "offer_hash": offer_hash,
            "payment_method": "pix",
            "installments": 1,
            "customer": customer_data,
            "cart": [{
                "offer_hash": offer_hash,
                "quantity": 1
            }],
            "expire_in_days": 1,
            "postback_url": "https://api-gateway-production-22bb.up.railway.app/webhook/tribopay",
            "tracking": {
                "src": tracking_data.get('click_id'),
                "utm_source": tracking_data.get('utm_source'),
                "utm_campaign": tracking_data.get('utm_campaign'),
                "utm_medium": tracking_data.get('utm_medium'),
                "utm_term": tracking_data.get('utm_term'),
                "utm_content": tracking_data.get('utm_content')
            }
        }
        
        logger.info(f"🚀 Enviando para TriboPay:")
        logger.info(json.dumps(tribopay_payload, indent=2, default=str))
        
        try:
            response = requests.post(
                f"https://api.tribopay.com.br/api/public/v1/transactions?api_token={TRIBOPAY_API_KEY}",
                json=tribopay_payload,
                headers=tribopay_headers,
                timeout=15
            )
            
            logger.info(f"📡 TriboPay Response Status: {response.status_code}")
            logger.info(f"📡 TriboPay Response Body: {response.text}")
            
            if response.status_code == 201:
                # SUCESSO TRIBOPAY!
                tribopay_data = response.json()
                transaction_id = tribopay_data.get('hash')
                pix_data = tribopay_data.get('pix', {})
                pix_code = pix_data.get('code', '')
                qr_code = pix_data.get('url', '')
                
                logger.info(f"🎉 SUCESSO TRIBOPAY! Transaction: {transaction_id}")
                logger.info(f"💳 PIX Code: {pix_code[:50]}..." if pix_code else "❌ Sem PIX code")
                logger.info(f"🔗 QR Code URL: {qr_code}")
                
            else:
                # ERRO TRIBOPAY - PROBLEMA DE CONFIGURAÇÃO DA CONTA
                error_msg = response.text
                logger.error(f"❌ ERRO TRIBOPAY: {response.status_code}")
                logger.error(f"❌ Detalhes: {error_msg}")
                
                # Erro específico de configuração da conta
                if "minimo 5 reais" in error_msg.lower():
                    logger.error("🚨 PROBLEMA IDENTIFICADO: Configuração da conta TriboPay")
                    logger.error("📞 AÇÃO NECESSÁRIA: Contatar suporte TriboPay")
                    logger.error("🏢 Conta: OCTA DIGITAL LTDA (vouwzzz7gk)")
                    logger.error("📧 Email: contato.octadigital@gmail.com")
                
                return jsonify({
                    'success': False,
                    'error': 'Configuração TriboPay: PIX/Boleto não habilitado na conta',
                    'details': error_msg,
                    'status_code': response.status_code,
                    'action_required': 'Contatar suporte TriboPay para habilitar PIX/Boleto',
                    'account': 'OCTA DIGITAL LTDA (vouwzzz7gk)',
                    'api_key_used': TRIBOPAY_API_KEY[:20] + '...',
                    'payload_sent': tribopay_payload
                }), 500
                
        except Exception as e:
            logger.error(f"❌ ERRO DE CONEXÃO TRIBOPAY: {e}")
            return jsonify({
                'success': False,
                'error': f'Conexão TriboPay falhou: {str(e)}',
                'payload_sent': tribopay_payload
            }), 500
        
        # Salva transação no PostgreSQL com fallback robusto para plano_id
        if db:
            try:
                db.save_pix_transaction(
                    transaction_id=transaction_id,
                    telegram_id=int(user_id),
                    amount=valor,
                    tracking_data=tracking_data,
                    plano_id=plano_id  # Sistema inteligente: funciona com/sem coluna
                )
                db.update_pix_transaction(
                    transaction_id=transaction_id,
                    status='pending',
                    pix_code=pix_code,
                    qr_code=qr_code
                )
                logger.info(f"✅ Transação salva no PostgreSQL: {transaction_id}")
            except Exception as db_error:
                logger.error(f"❌ Erro salvando no database: {db_error}")
                # Continua mesmo se falhar o save - PIX foi gerado
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