#!/usr/bin/env python3
"""
API Gateway - Serviço para gerar PIX com a TriboPay e receber webhooks.
Versão corrigida com base na documentação oficial da TriboPay.
"""

import os
import logging
import json
import requests
import random
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from database import get_db

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

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

#======== MAPEAMENTO DE OFERTAS TRIBOPAY (CORRIGIDO CONFORME DOCUMENTAÇÃO) =============
def get_tribopay_offer_mapping():
    """Retorna um mapeamento limpo de plano_id para offer_hash com dados completos."""
    return {
        "plano_1mes": {
            "offer_hash": os.getenv('TRIBOPAY_OFFER_VIP_BASICO', 'deq4y2wybn'),
            "price": 2490,  # R$ 24,90
            "title": "Acesso VIP - Ana Cardoso (1 mês)"
        },
        "plano_3meses": {
            "offer_hash": os.getenv('TRIBOPAY_OFFER_VIP_PREMIUM', 'zawit'),
            "price": 4990,  # R$ 49,90
            "title": "Acesso VIP - Ana Cardoso (3 meses)"
        },
        "plano_1ano": {
            "offer_hash": os.getenv('TRIBOPAY_OFFER_VIP_COMPLETO', '8qbmp'),
            "price": 6700,  # R$ 67,00
            "title": "Acesso VIP - Ana Cardoso (1 ano)"
        },
        "default": {
            "offer_hash": os.getenv('TRIBOPAY_OFFER_DEFAULT', 'deq4y2wybn'),
            "price": 2490,  # R$ 24,90
            "title": "Acesso VIP - Ana Cardoso"
        }
    }

def get_offer_data_by_plano_id(plano_id):
    """Retorna dados completos da oferta baseado no plano_id. Usa 'default' se não encontrar."""
    mapping = get_tribopay_offer_mapping()
    offer_data = mapping.get(plano_id, mapping["default"])
    logger.info(f"📦 Mapeamento de oferta: {plano_id} -> {offer_data['offer_hash']} (R$ {offer_data['price']/100:.2f})")
    return offer_data

# Função para backward compatibility
def get_offer_hash_by_plano_id(plano_id):
    """DEPRECATED: Use get_offer_data_by_plano_id() instead."""
    return get_offer_data_by_plano_id(plano_id)["offer_hash"]
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

        if not all([user_id, valor, plano_id]):
            return jsonify({'success': False, 'error': 'Campos obrigatórios ausentes: user_id, valor, plano_id'}), 400

        # Se customer_data não foi fornecido, gera dados únicos realistas
        if not customer_data:
            customer_data = generate_unique_customer_data(user_id)
            logger.info(f"🎲 Dados únicos gerados para user_id {user_id}")
        else:
            # Valida campos obrigatórios apenas se customer_data foi fornecido
            required_customer_fields = ['name', 'email', 'document', 'phone_number']
            if not all(k in customer_data for k in required_customer_fields):
                return jsonify({'success': False, 'error': f'Dados do cliente incompletos. Obrigatórios: {required_customer_fields}'}), 400

        if not db:
            return jsonify({'success': False, 'error': 'Serviço indisponível (sem conexão com o banco de dados)'}), 503

        # 2. Busca de dados de tracking com logs detalhados
        tracking_data = {}
        user_data = db.get_user(int(user_id))
        if user_data:
            tracking_data = user_data.get('tracking_data', {})
            logger.info(f"🎯 Tracking encontrado para usuário {user_id}: {tracking_data}")
            
            # Log detalhado dos dados de tracking para debug PIX
            click_id = tracking_data.get('click_id')
            utm_source = tracking_data.get('utm_source')
            utm_medium = tracking_data.get('utm_medium')
            utm_campaign = tracking_data.get('utm_campaign')
            
            logger.info(f"📊 Dados tracking detalhados PIX:")
            logger.info(f"   - click_id: {click_id}")
            logger.info(f"   - utm_source: {utm_source}")
            logger.info(f"   - utm_medium: {utm_medium}")
            logger.info(f"   - utm_campaign: {utm_campaign}")
            logger.info(f"   - Total campos tracking: {len(tracking_data)}")
        else:
            logger.warning(f"⚠️ Usuário {user_id} não encontrado no banco. Tracking não será enviado.")
            logger.warning(f"💡 Dica: Usuário pode não ter passado pelo /start ou dados não foram salvos corretamente")

        # 3. Preparação do Payload para a TriboPay, EXATAMENTE conforme a documentação oficial
        offer_data = get_offer_data_by_plano_id(plano_id)
        offer_hash = offer_data["offer_hash"]
        offer_price = offer_data["price"]
        offer_title = offer_data["title"]
        product_hash = "a8c1r56cgy"  # Product hash fixo do produto "Acesso VIP - Ana Cardoso"
        postback_url = "https://api-gateway-production-22bb.up.railway.app/webhook/tribopay"

        # Validação crítica: valor solicitado deve coincidir com o preço da oferta
        valor_centavos = int(float(valor) * 100)
        if valor_centavos != offer_price:
            logger.warning(f"⚠️ Valor solicitado ({valor_centavos}) diferente do preço da oferta ({offer_price}). Usando preço da oferta.")
            valor_centavos = offer_price

        tribopay_payload = {
            "amount": valor_centavos,
            "offer_hash": offer_hash,
            "payment_method": "pix",
            "installments": 1,  # CRÍTICO: Campo obrigatório conforme teste da API
            "postback_url": postback_url,
            "customer": customer_data,
            "cart": [{
                "product_hash": product_hash,  # CRÍTICO: Usar product_hash, não offer_hash
                "title": offer_title,          # CRÍTICO: Campo obrigatório
                "price": valor_centavos,       # CRÍTICO: Campo obrigatório
                "quantity": 1,
                "operation_type": 1,           # CRÍTICO: Campo obrigatório (1 = sale)
                "tangible": False              # CRÍTICO: Campo obrigatório (produto digital)
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
        
        # CRÍTICO: A API TriboPay retorna pix_qr_code e pix_url, não 'code' e 'url'
        pix_code = pix_data.get('pix_qr_code')  # Código PIX copia e cola
        qr_code = pix_data.get('pix_url')       # URL para pagamento

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

#======== ENDPOINTS AUSENTES - INVALIDAR PIX =============
@app.route('/api/pix/invalidar/<int:user_id>', methods=['POST'])
def invalidar_pix_usuario(user_id):
    """Invalida todos os PIX pendentes do usuário."""
    try:
        if not db:
            return jsonify({'success': False, 'error': 'Serviço indisponível (sem conexão com o banco de dados)'}), 503
        
        # Chama a função do banco para invalidar
        result = db.invalidate_user_pix(user_id)
        
        if result:
            logger.info(f"🗑️ PIX do usuário {user_id} invalidados com sucesso")
            return jsonify({'success': True, 'message': f'PIX do usuário {user_id} invalidados'})
        else:
            logger.warning(f"⚠️ Nenhum PIX encontrado para invalidar do usuário {user_id}")
            return jsonify({'success': True, 'message': f'Nenhum PIX encontrado para o usuário {user_id}'})
            
    except Exception as e:
        logger.error(f"❌ Erro ao invalidar PIX do usuário {user_id}: {e}")
        return jsonify({'success': False, 'error': 'Erro interno do servidor'}), 500

@app.route('/api/tracking/latest', methods=['GET'])
def get_latest_tracking():
    """Retorna o último tracking disponível."""
    try:
        if not db:
            return jsonify({'success': False, 'error': 'Serviço indisponível (sem conexão com o banco de dados)'}), 503
        
        # Busca último tracking salvo
        latest = db.get_latest_tracking()
        
        if latest:
            logger.info(f"✅ Último tracking encontrado: {latest.get('id')}")
            return jsonify({
                'success': True, 
                'original': latest.get('original_data', '{}'),
                'created_at': latest.get('created_at')
            })
        else:
            logger.warning("⚠️ Nenhum tracking encontrado")
            return jsonify({'success': False, 'error': 'Nenhum tracking encontrado'}), 404
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar último tracking: {e}")
        return jsonify({'success': False, 'error': 'Erro interno do servidor'}), 500

@app.route('/api/users', methods=['POST'])
def save_user():
    """Salva dados do usuário no banco de dados."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Corpo da requisição não é um JSON válido'}), 400
        
        required_fields = ['telegram_id', 'username', 'first_name', 'tracking_data']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'error': f'Campos obrigatórios ausentes: {required_fields}'}), 400
        
        if not db:
            return jsonify({'success': False, 'error': 'Serviço indisponível (sem conexão com o banco de dados)'}), 503
        
        # Salva usuário no banco
        result = db.save_user(
            telegram_id=data['telegram_id'],
            username=data['username'], 
            first_name=data['first_name'],
            last_name=data.get('last_name', ''),
            tracking_data=data['tracking_data']
        )
        
        if result:
            logger.info(f"✅ Usuário {data['telegram_id']} salvo com sucesso")
            return jsonify({'success': True, 'message': 'Usuário salvo com sucesso'})
        else:
            logger.error(f"❌ Falha ao salvar usuário {data['telegram_id']}")
            return jsonify({'success': False, 'error': 'Falha ao salvar usuário'}), 500
            
    except Exception as e:
        logger.error(f"❌ Erro ao salvar usuário: {e}")
        return jsonify({'success': False, 'error': 'Erro interno do servidor'}), 500

@app.route('/api/tracking/save', methods=['POST', 'OPTIONS'])
def save_tracking():
    """Salva dados de tracking (mapeamento de ID)."""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
        
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Corpo da requisição não é um JSON válido'}), 400
        
        safe_id = data.get('safe_id')
        original_data = data.get('original') or data.get('original_data')  # Aceita ambos os formatos
        
        if not all([safe_id, original_data]):
            return jsonify({'success': False, 'error': 'Campos obrigatórios ausentes: safe_id, original|original_data'}), 400
        
        if not db:
            return jsonify({'success': False, 'error': 'Serviço indisponível (sem conexão com o banco de dados)'}), 503
        
        # Salva tracking mapping
        db.save_tracking_mapping(safe_id, original_data)
        logger.info(f"✅ Tracking mapping {safe_id} salvo com sucesso")
        
        return jsonify({
            'success': True, 
            'message': 'Tracking salvo com sucesso',
            'safe_id': safe_id
        })
            
    except Exception as e:
        logger.error(f"❌ Erro ao salvar tracking: {e}")
        return jsonify({'success': False, 'error': 'Erro interno do servidor'}), 500

@app.route('/api/tracking/get/<safe_id>', methods=['GET'])
def get_tracking(safe_id):
    """Busca dados de tracking por safe_id."""
    try:
        if not db:
            return jsonify({'success': False, 'error': 'Serviço indisponível (sem conexão com o banco de dados)'}), 503
        
        # Busca tracking mapping
        tracking = db.get_tracking_mapping(safe_id)
        
        if tracking:
            logger.info(f"✅ Tracking {safe_id} encontrado")
            return jsonify({
                'success': True,
                'original': tracking.get('original_data'),
                'created_at': tracking.get('created_at'),
                'accessed_at': tracking.get('accessed_at')
            })
        else:
            logger.warning(f"⚠️ Tracking {safe_id} não encontrado")
            return jsonify({'success': False, 'error': 'Tracking não encontrado'}), 404
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar tracking {safe_id}: {e}")
        return jsonify({'success': False, 'error': 'Erro interno do servidor'}), 500

@app.route('/api/pix/verificar/<int:user_id>/<plano_id>', methods=['GET'])
def verificar_pix_existente(user_id, plano_id):
    """Verifica se existe PIX válido para o usuário e plano."""
    try:
        logger.info(f"🔍 ENDPOINT VERIFICAR PIX: user_id={user_id}, plano_id={plano_id}")
        
        if not db:
            logger.error("❌ Database não disponível")
            return jsonify({'success': False, 'error': 'Serviço indisponível (sem conexão com o banco de dados)'}), 503
        
        # Busca PIX válido para o usuário e plano
        logger.info(f"📡 Chamando db.get_valid_pix({user_id}, {plano_id})")
        pix_data = db.get_valid_pix(user_id, plano_id)
        logger.info(f"📦 Resultado db.get_valid_pix: {pix_data}")
        
        if pix_data:
            # Calcula tempo restante
            from datetime import datetime, timedelta
            created_at = pix_data.get('created_at')
            logger.info(f"⏰ PIX created_at: {created_at} (tipo: {type(created_at)})")
            
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            if created_at:
                expire_time = created_at + timedelta(minutes=15)
                now = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.now()
                tempo_restante = expire_time - now
                logger.info(f"⏰ Tempo restante calculado: {tempo_restante.total_seconds()} segundos")
                
                if tempo_restante.total_seconds() > 0:
                    tempo_min = int(tempo_restante.total_seconds() / 60)
                    pix_data['tempo_restante'] = f"{tempo_min} minutos"
                    
                    logger.info(f"✅ PIX VÁLIDO encontrado para usuário {user_id}, plano {plano_id} - {tempo_min} min restantes")
                    return jsonify({
                        'success': True,
                        'pix_valido': True,
                        'pix_data': pix_data
                    })
                else:
                    logger.info(f"⏰ PIX EXPIRADO para usuário {user_id}, plano {plano_id}")
            else:
                logger.warning(f"⚠️ PIX sem created_at válido para usuário {user_id}")
        
        logger.info(f"❌ Nenhum PIX válido encontrado para usuário {user_id}, plano {plano_id}")
        return jsonify({
            'success': True,
            'pix_valido': False,
            'pix_data': None
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar PIX do usuário {user_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Erro interno do servidor'}), 500
#================= FECHAMENTO ======================

#======== SISTEMA DE GERAÇÃO DE DADOS ÚNICOS =============
def generate_unique_customer_data(user_id):
    """Gera dados únicos de cliente para PIX - nunca repete"""
    
    # Listas de nomes brasileiros comuns
    primeiros_nomes = [
        "Ana", "Maria", "João", "Pedro", "Lucas", "Gabriel", "Rafael", "Daniel", "Bruno", "Felipe",
        "Fernanda", "Juliana", "Camila", "Amanda", "Beatriz", "Carolina", "Larissa", "Mariana",
        "André", "Diego", "Marcos", "Thiago", "Rodrigo", "Mateus", "Gustavo", "Ricardo",
        "Patrícia", "Renata", "Sandra", "Vanessa", "Claudia", "Mônica", "Silvia", "Adriana",
        "Carlos", "Fernando", "Eduardo", "Marcelo", "Paulo", "Roberto", "Leonardo", "Vinicius"
    ]
    
    sobrenomes = [
        "Silva", "Santos", "Oliveira", "Souza", "Lima", "Ferreira", "Costa", "Pereira", "Almeida",
        "Martins", "Araújo", "Melo", "Barbosa", "Ribeiro", "Monteiro", "Cardoso", "Carvalho",
        "Gomes", "Nascimento", "Moreira", "Reis", "Freitas", "Campos", "Cunha", "Pinto", "Farias",
        "Batista", "Vieira", "Mendes", "Castro", "Rocha", "Dias", "Moura", "Correia", "Teixeira"
    ]
    
    # Usa user_id + timestamp para garantir unicidade
    import time
    seed = int(str(user_id) + str(int(time.time() * 1000))[-6:])
    random.seed(seed)
    
    # Gera nome único
    primeiro = random.choice(primeiros_nomes)
    sobrenome = random.choice(sobrenomes)
    nome_completo = f"{primeiro} {sobrenome}"
    
    # Gera CPF válido único
    def gerar_cpf():
        # Gera 9 primeiros dígitos
        cpf = [random.randint(0, 9) for _ in range(9)]
        
        # Calcula primeiro dígito verificador
        soma = sum(cpf[i] * (10 - i) for i in range(9))
        digito1 = (soma * 10 % 11) % 10
        cpf.append(digito1)
        
        # Calcula segundo dígito verificador
        soma = sum(cpf[i] * (11 - i) for i in range(10))
        digito2 = (soma * 10 % 11) % 10
        cpf.append(digito2)
        
        return ''.join(map(str, cpf))
    
    # Gera telefone celular válido
    def gerar_telefone():
        # DDD válidos brasileiros
        ddds = ['11', '12', '13', '14', '15', '16', '17', '18', '19', '21', '22', '24', '27', '28',
                '31', '32', '33', '34', '35', '37', '38', '41', '42', '43', '44', '45', '46', '47',
                '48', '49', '51', '53', '54', '55', '61', '62', '63', '64', '65', '66', '67', '68',
                '69', '71', '73', '74', '75', '77', '79', '81', '82', '83', '84', '85', '86', '87',
                '88', '89', '91', '92', '93', '94', '95', '96', '97', '98', '99']
        
        ddd = random.choice(ddds)
        # Celular sempre começa com 9
        numero = '9' + ''.join([str(random.randint(0, 9)) for _ in range(8)])
        return f"{ddd}{numero}"
    
    cpf = gerar_cpf()
    telefone = gerar_telefone()
    
    # Gera email seguro removendo acentos e caracteres especiais
    import re
    email_base = re.sub(r'[^a-z]', '', primeiro.lower() + sobrenome.lower())
    if len(email_base) < 3:  # Fallback se nome muito curto
        email_base = f"user{user_id}"
    email = f"{email_base}{random.randint(100, 999)}@gmail.com"
    
    logger.info(f"🎲 Dados únicos gerados para user {user_id}: {nome_completo}, CPF: {cpf[:3]}***")
    
    return {
        'name': nome_completo,
        'email': email,
        'document': cpf,
        'phone_number': telefone
    }
#================= FECHAMENTO ======================

#======== FUNÇÃO DE CONVERSÃO XTRACKY =============
def send_conversion_to_xtracky(transaction_id):
    """Envia conversão para Xtracky quando pagamento é aprovado"""
    try:
        if not db:
            logger.error("❌ Banco indisponível - conversão não enviada")
            return False
            
        # Busca dados da transação
        transaction = db.get_pix_transaction(transaction_id)
        if not transaction:
            logger.error(f"❌ Transação {transaction_id} não encontrada")
            return False
            
        # Busca click_id diretamente da transação (está armazenado como campo separado)
        click_id = transaction.get('click_id')
        tracking_data = transaction.get('tracking_data', {})
        
        # Debug: Log detalhado dos dados de tracking da transação
        logger.info(f"🔍 Dados transação {transaction_id}:")
        logger.info(f"   - click_id direto: {click_id}")
        logger.info(f"   - tracking_data: {tracking_data}")
        logger.info(f"   - tracking_data.click_id: {tracking_data.get('click_id') if isinstance(tracking_data, dict) else 'N/A'}")
        
        # Fallback: se click_id não está direto, tenta extrair do tracking_data
        if not click_id and isinstance(tracking_data, dict):
            click_id = tracking_data.get('click_id')
            logger.info(f"🔄 Usando click_id do tracking_data: {click_id}")
        
        if not click_id:
            logger.warning(f"⚠️ Transação {transaction_id} sem click_id - conversão não enviada")
            logger.warning(f"   Dados disponíveis: {list(transaction.keys())}")
            return False
            
        # Dados da conversão para Xtracky
        conversion_data = {
            'token': '72701474-7e6c-4c87-b84f-836d4547a4bd',
            'click_id': click_id,
            'value': float(transaction.get('amount', 0)),
            'currency': 'BRL',
            'status': 'paid'
        }
        
        # Envia para Xtracky
        response = requests.post(
            'https://api.xtracky.com/api/integrations/tribopay',
            json=conversion_data,
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"✅ Conversão enviada para Xtracky: {click_id} - R$ {transaction.get('amount', 0)}")
            return True
        else:
            logger.error(f"❌ Erro ao enviar conversão para Xtracky: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro crítico ao enviar conversão para Xtracky: {e}")
        return False
#================= FECHAMENTO ======================

#======== LÓGICA DO WEBHOOK (CORRIGIDA) =============
@app.route('/webhook/tribopay', methods=['POST'])
def tribopay_webhook():
    """Webhook para receber e processar notificações da TriboPay."""
    try:
        webhook_data = request.get_json()
        if not webhook_data:
            return jsonify({'status': 'ignorado', 'reason': 'payload vazio'}), 400

        logger.info(f"📥 Webhook da TriboPay recebido.")
        logger.debug(f"Webhook Payload: {json.dumps(webhook_data)}")

        # CORREÇÃO CRÍTICA: Múltiplos formatos de webhook da TriboPay
        transaction_data = webhook_data.get('transaction')
        transaction_id = None
        
        # Formato 1: transaction é objeto com id/hash
        if isinstance(transaction_data, dict):
            transaction_id = transaction_data.get('id') or transaction_data.get('hash')
        # Formato 2: transaction é string JSON
        elif isinstance(transaction_data, str):
            try:
                transaction_data = json.loads(transaction_data)
                transaction_id = transaction_data.get('id') or transaction_data.get('hash')
            except json.JSONDecodeError:
                # Formato 3: transaction é diretamente o hash ID
                if len(transaction_data) > 5:  # Assumindo que hash tem pelo menos 6 caracteres
                    transaction_id = transaction_data
                    logger.info(f"🔍 Transaction data é hash direto: {transaction_data}")
                else:
                    logger.error(f"❌ transaction_data é string mas não é JSON válido nem hash: {transaction_data}")
                    return jsonify({'status': 'erro', 'reason': 'transaction data inválido'}), 400
        # Formato 4: ID direto no root do webhook
        elif not transaction_data:
            transaction_id = webhook_data.get('id') or webhook_data.get('hash')
            
        # Formato 5: Fallback - tenta outros campos comuns da TriboPay
        if not transaction_id:
            transaction_id = webhook_data.get('transaction_id') or webhook_data.get('txn_id')
        
        if not transaction_id:
            logger.warning("⚠️ Webhook recebido sem 'transaction.id' ou 'transaction.hash'. Ignorando.")
            return jsonify({'status': 'ignorado', 'reason': 'missing transaction.id'}), 200

        status = webhook_data.get('status')
        logger.info(f"🔍 Processando webhook para transação {transaction_id} com status '{status}'.")

        if db:
            db.update_pix_transaction(transaction_id, status=status)
            logger.info(f"💾 Status da transação {transaction_id} atualizado para '{status}' no banco de dados.")
            
            # Envia conversão para Xtracky se pagamento foi aprovado
            if status == 'paid' or status == 'approved':
                send_conversion_to_xtracky(transaction_id)
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