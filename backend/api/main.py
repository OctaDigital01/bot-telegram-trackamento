#!/usr/bin/env python3
"""
API Gateway - Serviço isolado
Webhooks, APIs REST e integrações
"""

import os
import logging
import json
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Thread

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

# Simular database temporário (migrar para PostgreSQL depois)
users_db = {}
pix_transactions = {}
tracking_mapping = {}

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'API Gateway',
        'timestamp': datetime.now().isoformat(),
        'database': 'PostgreSQL' if DATABASE_URL else 'Memory'
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
        user_id = data.get('user_id')
        
        users_db[user_id] = {
            'name': data.get('name'),
            'tracking_data': data.get('tracking_data', {}),
            'created_at': datetime.now().isoformat(),
            'status': 'active'
        }
        
        logger.info(f"👤 Usuário {user_id} salvo: {data.get('name')}")
        return jsonify({'success': True, 'user_id': user_id})
        
    except Exception as e:
        logger.error(f"❌ Erro salvando usuário: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Recupera dados do usuário"""
    try:
        user_data = users_db.get(int(user_id))
        if user_data:
            return jsonify({'success': True, 'user': user_data})
        else:
            return jsonify({'success': False, 'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tracking/get/<safe_id>', methods=['GET'])
def get_tracking(safe_id):
    """Recupera click_id original do mapeamento"""
    try:
        if safe_id in tracking_mapping:
            mapping_data = tracking_mapping[safe_id]
            return jsonify({
                'success': True,
                'safe_id': safe_id,
                'original': mapping_data['original'],
                'created': mapping_data['created']
            })
        
        # Fallback: retorna o próprio ID
        return jsonify({
            'success': False, 
            'safe_id': safe_id, 
            'original': safe_id
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tracking/latest', methods=['GET'])
def get_latest_tracking():
    """Recupera o último tracking salvo (para novos usuários)"""
    try:
        if not tracking_mapping:
            return jsonify({'success': False, 'message': 'No tracking found'})
        
        # Busca o mais recente (últimos 10 minutos)
        now = datetime.now()
        recent_mappings = []
        
        for safe_id, data in tracking_mapping.items():
            created = datetime.fromisoformat(data['created'])
            if (now - created).total_seconds() < 600:  # 10 minutos
                recent_mappings.append({
                    'safe_id': safe_id,
                    'original': data['original'],
                    'created': data['created']
                })
        
        if recent_mappings:
            # Ordena por data (mais recente primeiro)
            recent_mappings.sort(key=lambda x: x['created'], reverse=True)
            latest = recent_mappings[0]
            return jsonify({
                'success': True,
                'safe_id': latest['safe_id'],
                'original': latest['original'],
                'created': latest['created']
            })
        
        return jsonify({'success': False, 'message': 'No recent tracking found'})
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
        
        # Busca dados do usuário
        user_data = users_db.get(user_id, {})
        tracking_data = user_data.get('tracking_data', {})
        
        logger.info(f"💰 Gerando PIX R$ {valor} para usuário {user_id}")
        logger.info(f"📊 Tracking preservado: {tracking_data}")
        
        # Simula geração PIX (integrar TriboPay depois)
        transaction_id = f"pix_{int(datetime.now().timestamp())}"
        pix_code = f"00020126580014BR.GOV.BCB.PIX0136{transaction_id}520400005303986540{valor:.2f}5802BR5925SISTEMA XTRACKY6009SAO PAULO62140510{transaction_id}6304"
        
        # Salva transação
        pix_transactions[transaction_id] = {
            'user_id': user_id,
            'valor': valor,
            'plano': plano,
            'tracking_data': tracking_data,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'transaction_id': transaction_id,
            'pix_copia_cola': pix_code,
            'valor': valor,
            'status': 'pending',
            'tracking_preservado': tracking_data
        })
        
    except Exception as e:
        logger.error(f"❌ Erro gerando PIX: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/webhook/tribopay', methods=['POST'])
def tribopay_webhook():
    """Webhook para notificações TriboPay"""
    try:
        webhook_data = request.get_json()
        logger.info(f"📥 Webhook TriboPay: {webhook_data}")
        
        # Processa webhook (implementar lógica específica)
        transaction_id = webhook_data.get('transaction_id')
        status = webhook_data.get('status', 'unknown')
        
        if transaction_id in pix_transactions:
            pix_transactions[transaction_id]['status'] = status
            logger.info(f"✅ Status atualizado: {transaction_id} -> {status}")
            
            if status == 'paid':
                # Envia conversão para Xtracky
                tracking_data = pix_transactions[transaction_id].get('tracking_data', {})
                logger.info(f"🎯 Conversão confirmada com tracking: {tracking_data}")
        
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