"""
Serviço de integração com a TriboPay para pagamentos PIX
"""
import os
import aiohttp
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
import qrcode
import io
import base64

logger = logging.getLogger(__name__)

class TribopayService:
    """Gerencia integração com API da TriboPay para pagamentos PIX"""
    
    def __init__(self):
        self.api_key = os.getenv('TRIBOPAY_API_KEY', 'IzJsCJ0BleuURRzZvrTeigPp6xknO8e9nHT6WZtDpxFQVocwa3E3GYeNXtYq')
        # URL Base oficial da TriboPay
        self.base_url = os.getenv('TRIBOPAY_BASE_URL', 'https://api.tribopay.com.br/api/public/v1')
        # Importa WEBHOOK_URL do config
        from ..config.config import WEBHOOK_URL
        self.webhook_url = WEBHOOK_URL
        
        # Headers padrão (sem Authorization - será na URL)
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Cache de transações pendentes
        self.pending_transactions = {}
        
    async def criar_cobranca_pix(self, user_id: int, plano: str, valor: float, 
                                  nome_cliente: str = None, cpf: str = None, 
                                  tracking_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Cria uma transação PIX usando o formato oficial da TriboPay
        FORMATO CORRETO TESTADO E FUNCIONANDO!
        """
        try:
            # Primeiro, criar produto (necessário para a TriboPay)
            product_hash = await self.criar_produto_vip(plano, valor)
            if not product_hash:
                return {'success': False, 'error': 'Erro ao criar produto'}
            
            # Converter valor para centavos
            valor_centavos = int(valor * 100)
            
            # Dados da transação no formato CORRETO da TriboPay
            payload = {
                "amount": valor_centavos,
                "offer_hash": product_hash,  # OBRIGATÓRIO
                "payment_method": "pix",
                "customer": {
                    "name": nome_cliente or f"Cliente {user_id}",
                    "email": f"user{user_id}@telegram.com",
                    "phone_number": "11999999999", 
                    "document": cpf or "00000000000"
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
                # Nota: TriboPay pode usar expire_in_days como mínimo 1 dia
                # Se expire_in_minutes não funcionar, a validação será feita pelo bot (15 min)
                "expire_in_days": 1,  # Mínimo da API (controle real via bot)
                "transaction_origin": "api",
                "installments": 1  # OBRIGATÓRIO para PIX
            }
            
            # Adicionar webhook se configurado
            if self.webhook_url:
                payload["postback_url"] = f"{self.webhook_url}/webhook/tribopay"
            
            # Adicionar dados de tracking se disponível
            if tracking_data:
                logger.info(f"🔍 DADOS DE TRACKING RECEBIDOS: {tracking_data}")
                
                # Adiciona campo de tracking na estrutura correta da TriboPay
                tracking_info = {}
                
                # Mapeia os campos para os nomes esperados pela TriboPay
                if 'click_id' in tracking_data:
                    tracking_info['src'] = tracking_data['click_id']
                    tracking_info['tracking_code'] = tracking_data['click_id']  # Adiciona em campo adicional
                    
                if 'utm_source' in tracking_data:
                    tracking_info['utm_source'] = tracking_data['utm_source']
                    
                if 'utm_medium' in tracking_data:
                    tracking_info['utm_medium'] = tracking_data['utm_medium']
                    
                if 'utm_campaign' in tracking_data:
                    tracking_info['utm_campaign'] = tracking_data['utm_campaign']
                    
                if 'utm_term' in tracking_data:
                    tracking_info['utm_term'] = tracking_data['utm_term']
                    
                if 'utm_content' in tracking_data:
                    tracking_info['utm_content'] = tracking_data['utm_content']
                
                # Adiciona objeto tracking ao payload
                if tracking_info:
                    payload['tracking'] = tracking_info
                    logger.info(f"✅ TRACKING ADICIONADO: {tracking_info}")
                
                # Adiciona também no customer como campos personalizados
                if 'click_id' in tracking_data:
                    payload['customer']['click_id'] = tracking_data['click_id']
                    payload['customer']['custom_fields'] = {
                        'click_id': tracking_data['click_id'],
                        'utm_source': tracking_data.get('utm_source', ''),
                        'utm_campaign': tracking_data.get('utm_campaign', '')
                    }
                    
                logger.info(f"🚀 PAYLOAD FINAL COM TRACKING: {payload}")
            else:
                logger.warning("⚠️ NENHUM DADO DE TRACKING RECEBIDO!")
            
            # Fazer requisição
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/transactions?api_token={self.api_key}"
                
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 201:
                        data = await response.json()
                        
                        # Extrair informações da resposta
                        transaction_hash = data.get('hash', 'temp_' + str(int(datetime.now().timestamp())))
                        pix_data = data.get('pix', {})
                        pix_code = pix_data.get('pix_qr_code', '')
                        
                        # Armazenar transação
                        self.pending_transactions[transaction_hash] = {
                            'user_id': user_id,
                            'plano': plano,
                            'valor': valor,
                            'status': data.get('payment_status', 'waiting_payment'),
                            'created_at': datetime.now().isoformat(),
                            'expires_at': (datetime.now() + timedelta(days=1)).isoformat()
                        }
                        
                        logger.info(f"✅ PIX criado com sucesso: {transaction_hash} - {pix_code[:50]}...")
                        
                        return {
                            'success': True,
                            'transaction_id': transaction_hash,
                            'pix_copia_cola': pix_code,
                            'qr_code_base64': await self.gerar_qr_code(pix_code) if pix_code else '',
                            'valor': valor,
                            'plano': plano,
                            'expires_at': (datetime.now() + timedelta(days=1)).isoformat(),
                            'charge_id': transaction_hash
                        }
                    else:
                        response_text = await response.text()
                        logger.error(f"Erro TriboPay: {response.status} - {response_text}")
                        return {
                            'success': False,
                            'error': f"Erro {response.status}",
                            'details': response_text
                        }
                        
        except Exception as e:
            logger.error(f"Erro ao criar cobrança PIX: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def criar_produto_vip(self, plano: str, valor: float) -> str:
        """
        Cria um produto VIP para a transação (necessário para TriboPay)
        """
        try:
            payload = {
                "title": f"Plano VIP - {plano}",
                "cover": "https://ana-cardoso.shop/icon-check.png",
                "sale_page": "https://ana-cardoso.shop", 
                "payment_type": 1,
                "product_type": "digital",
                "delivery_type": 1,
                "id_category": 1,
                "amount": int(valor * 100)
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/products?api_token={self.api_key}"
                
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 201:
                        data = await response.json()
                        return data.get('hash', '')
                    else:
                        logger.error(f"Erro ao criar produto: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Erro ao criar produto: {e}")
            return None
    
    async def gerar_qr_code(self, pix_code: str) -> str:
        """
        Gera QR Code em base64 a partir do código PIX
        
        Args:
            pix_code: Código PIX copia e cola
            
        Returns:
            String base64 da imagem do QR Code
        """
        try:
            if not pix_code:
                return ""
                
            # Criar QR Code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(pix_code)
            qr.make(fit=True)
            
            # Gerar imagem
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Converter para base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"Erro ao gerar QR Code: {e}")
            return ""
    
    async def gerar_qr_code_bytes(self, pix_code: str) -> bytes:
        """
        Gera QR Code como bytes PNG a partir do código PIX
        
        Args:
            pix_code: Código PIX copia e cola
            
        Returns:
            Bytes da imagem PNG do QR Code
        """
        try:
            if not pix_code:
                return b""
                
            # Criar QR Code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(pix_code)
            qr.make(fit=True)
            
            # Gerar imagem
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Converter para bytes
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Erro ao gerar QR Code bytes: {e}")
            return b""
    
    async def verificar_status_pagamento(self, transaction_hash: str) -> Dict[str, Any]:
        """
        Verifica o status de uma transação na TriboPay
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/transactions/{transaction_hash}?api_token={self.api_key}"
                
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        status = data.get('status', 'pending')
                        
                        # 🔥 VERIFICAR PAYMENT_STATUS (campo correto para pagamento confirmado)
                        payment_status = data.get('payment_status', 'pending')
                        is_paid = payment_status == 'paid'
                        
                        # Atualizar cache local
                        if transaction_hash in self.pending_transactions:
                            self.pending_transactions[transaction_hash]['status'] = status
                        
                        logger.info(f"🔍 Status verificação - Status: {status}, Payment Status: {payment_status}, Paid: {is_paid}")
                        
                        return {
                            'success': True,
                            'status': status,
                            'payment_status': payment_status,
                            'paid': is_paid,
                            'data': data
                        }
                    else:
                        return {
                            'success': False,
                            'error': f"Erro {response.status}"
                        }
                        
        except Exception as e:
            logger.error(f"Erro ao verificar status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def processar_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa webhook de confirmação de pagamento
        
        Args:
            webhook_data: Dados recebidos do webhook
            
        Returns:
            Dicionário com resultado do processamento
        """
        try:
            # Extrair informações do webhook
            transaction_id = webhook_data.get('correlationID', webhook_data.get('id'))
            status = webhook_data.get('status', '')
            
            # Verificar se temos essa transação
            if transaction_id in self.pending_transactions:
                transaction = self.pending_transactions[transaction_id]
                transaction['status'] = status
                
                if status in ['COMPLETED', 'PAID', 'ACTIVE']:
                    # Pagamento confirmado
                    logger.info(f"Pagamento confirmado: {transaction_id}")
                    return {
                        'success': True,
                        'user_id': transaction['user_id'],
                        'plano': transaction['plano'],
                        'valor': transaction['valor'],
                        'paid': True
                    }
                elif status in ['EXPIRED', 'CANCELED', 'FAILED']:
                    # Pagamento falhou
                    logger.info(f"Pagamento falhou: {transaction_id} - {status}")
                    return {
                        'success': True,
                        'user_id': transaction['user_id'],
                        'plano': transaction['plano'],
                        'paid': False,
                        'reason': status
                    }
            
            return {
                'success': False,
                'error': 'Transação não encontrada'
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar webhook: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    

# Instância global do serviço
tribopay_service = TribopayService()