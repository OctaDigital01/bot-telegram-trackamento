#!/usr/bin/env python3
"""
API Gateway - Serviço para gerar PIX com a TriboPay e receber webhooks.
Versão corrigida com base na documentação oficial da TriboPay.
"""

import os
import logging
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from database import get_db

#======== CONFIGURAÇÃO DE LOGGING E VARIÁVEIS DE AMBIENTE =============
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurações
WEBHOOK_PORT = int(os.getenv('PORT', '8080'))
DATABASE_URL = os.getenv('DATABASE_URL')
TRIBOPAY_API_KEY = os.getenv('TRIBOPAY_API_KEY')
TRIBOPAY_API_URL = "https://api.tribopay.com.br/api/public/v1/transactions"
#================= FECHAMENTO ======================

#======== INICIALIZAÇÃO DO FLASK E BANCO DE DADOS =============
app = Flask(__name__)
CORS(app)

try:
    db = get_db()
    logger.info("✅ Conexão com o PostgreSQL estabelecida com sucesso.")
except Exception as e:
    logger.error(f"❌ Falha crítica ao conectar com o PostgreSQL: {e}")
    db = None
#================= FECHAMENTO ======================

#======== MAPEAMENTO DE OFERTAS TRIBOPAY (LIMPO E OTIMIZADO) =============
def get_tribopay_offer_mapping():
    """Retorna um mapeamento limpo de plano_id para offer_hash."""
    return {
        "plano_1mes": os.getenv('TRIBOPAY_OFFER_VIP_BASICO', 'deq4y2wybn'),   # R$ 24,90
        "plano_3meses": os.getenv('TRIBOPAY_OFFER_VIP_PREMIUM', 'zawit'),     # R$ 49,90
        "plano_1ano": os.getenv('TRIBOPAY_OFFER_VIP_COMPLETO', '8qbmp'),      # R$ 67,00
        "default": os.getenv('TRIBOPAY_OFFER_DEFAULT', 'deq4y2wybn')
    }

def get_offer_hash_by_plano_id(plano_id):
    """Retorna offer_hash baseado no plano_id. Usa 'default' se não encontrar."""
    mapping = get_tribopay_offer_mapping()
    offer_hash = mapping.get(plano_id, mapping["default"])
    logger.info(f"📦 Mapeamento de oferta: {plano_id} -> {offer_hash}")
    return offer_hash
#================= FECHAMENTO ======================

#======== ENDPOINTS DE UTILIDADE (HEALTH CHECK, ETC) =============
@app.route('/health', methods=['GET'])
def health():
    """Endpoint de verificação de saúde do serviço."""
    db_status = 'conectado' if db else 'indisponível'
    return jsonify({
        'status': 'ok',
        'service': 'API Gateway',
        'database': f'PostgreSQL ({db_status})'
    })

@app.route('/', methods=['GET'])
def index():
    """Endpoint raiz com informações básicas."""
    return jsonify({
        'service': 'API Gateway - Integração TriboPay',
        'version': '2.0-corrigida',
        'status': 'online'
    })
#================= FECHAMENTO ======================

#======== LÓGICA PRINCIPAL: GERAÇÃO DE PIX (REFEITA) =============
@app.route('/api/pix/gerar', methods=['POST'])
def gerar_pix():
    """
    Gera uma transação PIX na TriboPay utilizando dados reais do cliente.
    Esta rota agora ESPERA receber os dados do cliente no corpo da requisição.
    """
    try:
        # 1. Validação da entrada de dados
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Corpo da requisição não é um JSON válido'}), 400

        user_id = data.get('user_id')
        valor = data.get('valor')
        plano_id = data.get('plano_id', 'default')
        customer_data = data.get('customer')

        if not all([user_id, valor, plano_id, customer_data]):
            return jsonify({'success': False, 'error': 'Campos obrigatórios ausentes: user_id, valor, plano_id, customer'}), 400

        required_customer_fields = ['name', 'email', 'document', 'phone_number']
        if not all(k in customer_data for k in required_customer_fields):
            return jsonify({'success': False, 'error': f'Dados do cliente incompletos. Obrigatórios: {required_customer_fields}'}), 400

        if not db:
            return jsonify({'success': False, 'error': 'Serviço indisponível (sem conexão com o banco de dados)'}), 503

        # 2. Busca de dados de tracking
        tracking_data = {}
        user_data = db.get_user(int(user_id))
        if user_data:
            tracking_data = user_data.get('tracking_data', {})
            logger.info(f"🎯 Tracking encontrado para usuário {user_id}.")
        else:
            logger.warning(f"⚠️ Usuário {user_id} não encontrado no banco. Tracking não será enviado.")

        # 3. Preparação do Payload para a TriboPay, conforme a documentação
        offer_hash = get_offer_hash_by_plano_id(plano_id)
        postback_url = "https://api-gateway-production-22bb.up.railway.app/webhook/tribopay" # Mova para env var se preferir

        tribopay_payload = {
            "amount": int(float(valor) * 100),
            "offer_hash": offer_hash,
            "payment_method": "pix",
            "postback_url": postback_url,
            "customer": customer_data,
            "cart": [{
                "offer_hash": offer_hash,
                "quantity": 1
            }],
            "tracking": {
                "src": tracking_data.get('click_id'),
                "utm_source": tracking_data.get('utm_source'),
                "utm_campaign": tracking_data.get('utm_campaign'),
                "utm_medium": tracking_data.get('utm_medium'),
                "utm_term": tracking_data.get('utm_term'),
                "utm_content": tracking_data.get('utm_content')
            }
        }

        logger.info(f"🚀 Enviando payload para TriboPay para o cliente {customer_data['email']}.")
        logger.debug(f"Payload: {json.dumps(tribopay_payload, indent=2)}")

        # 4. Requisição à API da TriboPay com tratamento de erro robusto
        response = requests.post(
            f"{TRIBOPAY_API_URL}?api_token={TRIBOPAY_API_KEY}",
            json=tribopay_payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=20
        )
        
        # Lança uma exceção para erros HTTP (4xx ou 5xx), permitindo um catch mais limpo
        response.raise_for_status()

        # 5. Processamento da resposta de sucesso
        tribopay_data = response.json()
        transaction_id = tribopay_data.get('hash')
        pix_data = tribopay_data.get('pix', {})
        pix_code = pix_data.get('code')
        qr_code = pix_data.get('url')

        if not all([transaction_id, pix_code, qr_code]):
            logger.error(f"❌ Resposta da TriboPay bem-sucedida, mas com dados PIX ausentes: {tribopay_data}")
            raise ValueError("Resposta da TriboPay incompleta")

        logger.info(f"✅ PIX gerado com sucesso! Transaction ID: {transaction_id}")

        # 6. Salva a transação no banco de dados local
        db.invalidate_user_pix(int(user_id))
        db.save_pix_transaction(
            transaction_id=transaction_id, telegram_id=int(user_id), amount=float(valor),
            tracking_data=tracking_data, plano_id=plano_id
        )
        db.update_pix_transaction(
            transaction_id=transaction_id, status='waiting_payment', pix_code=pix_code, qr_code=qr_code
        )
        logger.info(f"💾 Transação {transaction_id} salva no banco de dados.")

        return jsonify({
            'success': True,
            'transaction_id': transaction_id,
            'pix_copia_cola': pix_code,
            'qr_code': qr_code
        })

    except requests.exceptions.HTTPError as http_err:
        error_body = http_err.response.text
        logger.error(f"❌ ERRO HTTP da API TriboPay: {http_err.response.status_code} - {error_body}")
        return jsonify({
            'success': False, 'error': 'Erro de comunicação com o gateway de pagamento.',
            'gateway_message': error_body
        }), http_err.response.status_code
    except Exception as e:
        logger.error(f"❌ Erro inesperado em /api/pix/gerar: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Ocorreu um erro interno no servidor.'}), 500
#================= FECHAMENTO ======================

#======== LÓGICA DO WEBHOOK (REFINADA) =============
@app.route('/webhook/tribopay', methods=['POST'])
def tribopay_webhook():
    """Webhook para receber e processar notificações da TriboPay."""
    try:
        webhook_data = request.get_json()
        if not webhook_data:
            return jsonify({'status': 'ignorado', 'reason': 'payload vazio'}), 400

        logger.info(f"📥 Webhook da TriboPay recebido.")
        logger.debug(f"Webhook Payload: {json.dumps(webhook_data)}")

        transaction_data = webhook_data.get('transaction', {})
        transaction_id = transaction_data.get('id')
        
        if not transaction_id:
            logger.warning("⚠️ Webhook recebido sem 'transaction.id'. Ignorando.")
            return jsonify({'status': 'ignorado', 'reason': 'missing transaction.id'}), 200

        status = webhook_data.get('status')
        logger.info(f"🔍 Processando webhook para transação {transaction_id} com status '{status}'.")

        if db:
            db.update_pix_transaction(transaction_id, status=status)
            logger.info(f"💾 Status da transação {transaction_id} atualizado para '{status}' no banco de dados.")
            # Aqui você pode adicionar a lógica de postback para o Xtracky, se o status for 'paid'
        else:
            logger.error("❌ Banco de dados indisponível. Não foi possível processar o webhook.")

        return jsonify({'status': 'recebido'})

    except Exception as e:
        logger.error(f"❌ Erro crítico no processamento do webhook: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
#================= FECHAMENTO ======================

#======== EXECUÇÃO PRINCIPAL =============
if __name__ == '__main__':
    if not TRIBOPAY_API_KEY:
        logger.critical("❌ A variável de ambiente TRIBOPAY_API_KEY não está definida. O serviço não pode iniciar.")
    else:
        logger.info("🚀 === API GATEWAY TRIBOPAY INICIANDO ===")
        logger.info(f"🌐 Escutando em http://0.0.0.0:{WEBHOOK_PORT}")
        # Em um ambiente de produção real, use um servidor WSGI como Gunicorn ou uWSGI
        app.run(host='0.0.0.0', port=WEBHOOK_PORT, debug=False)
#================= FECHAMENTO ======================