#!/usr/bin/env python3
import asyncio
import logging
import json
import base64
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import config
from database import db
from api_gateway.tribopay_service import tribopay_service

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def decode_tracking_data(encoded_param):
    """Decodifica dados usando sistema híbrido - Base64 ou mapeamento servidor"""
    try:
        # Verifica se é um ID mapeado (começa com 'M')
        if encoded_param.startswith('M') and len(encoded_param) <= 12:
            print(f"🔍 ID mapeado detectado: {encoded_param}")
            
            # Tenta recuperar dados do servidor
            try:
                import requests
                response = requests.get(f"http://localhost:8080/api/tracking/get/{encoded_param}", timeout=5)
                if response.status_code == 200:
                    api_data = response.json()
                    if api_data.get('success') and api_data.get('original'):
                        original_data = json.loads(api_data['original'])
                        print(f"✅ Dados recuperados do servidor: {original_data}")
                        return original_data
                    else:
                        print(f"⚠️ Servidor não encontrou dados para {encoded_param}")
                else:
                    print(f"⚠️ Servidor retornou erro: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"❌ Erro ao acessar servidor: {e}")
            
            # Fallback se servidor falhar
            return {'click_id': 'server_error'}
        
        # Método Base64 (para compatibilidade)
        if len(encoded_param) > 20:  # Provavelmente Base64
            # Decodifica Base64 URL-Safe
            base64_str = encoded_param.replace('-', '+').replace('_', '/')
            padding = 4 - len(base64_str) % 4
            if padding != 4:
                base64_str += '=' * padding
            
            decoded_bytes = base64.b64decode(base64_str)
            decoded_json = decoded_bytes.decode('utf-8')
            tracking_data = json.loads(decoded_json)
            
            print(f"✅ Base64 decodificado: {tracking_data}")
            return tracking_data
        
        # Fallback: ID simples
        print(f"⚠️ Usando como click_id direto: {encoded_param}")
        return {'click_id': encoded_param}
        
    except Exception as e:
        print(f"❌ Erro na decodificação: {e}")
        return {'click_id': encoded_param}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler do comando /start - decodifica parâmetros completos"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    print(f"\n🚀 === START COMANDO EXECUTADO ===")
    print(f"👤 User: {user_id} - {user_name}")
    print(f"🔍 Args: {context.args}")
    print(f"📱 Message: {update.message.text}")
    print("=" * 40)
    
    if context.args and len(context.args) > 0:
        encoded_param = context.args[0]
        print(f"🔐 Parâmetro codificado recebido: '{encoded_param}'")
        
        # DECODIFICA dados completos ANTES de salvar
        tracking_data = decode_tracking_data(encoded_param)
        
        # FORÇA mostrar o que foi decodificado
        print(f"📊 DADOS DECODIFICADOS: {tracking_data}")
        
        # Salva dados DECODIFICADOS no banco
        click_id = tracking_data.get('click_id', 'decode_error')
        print(f"💾 Salvando dados completos: {tracking_data}")
        
        # PRIMEIRO: Garante que existe entrada no banco
        if user_id not in db.tracking_data:
            db.tracking_data[user_id] = {}
        
        # SEGUNDO: Salva TODOS os dados completos (incluindo utm_source)
        db.tracking_data[user_id] = tracking_data.copy()
        
        # TERCEIRO: Adiciona metadados necessários
        db.tracking_data[user_id]['created_at'] = datetime.now().isoformat()
        db.tracking_data[user_id]['status'] = 'active'
        
        # Salva no arquivo
        db.save_data()
        
        print(f"✅ DADOS FINAIS SALVOS para user {user_id}: {db.tracking_data[user_id]}")
        
        # Mostra dados capturados
        param_text = "\n".join([f"{k}: {v}" for k, v in tracking_data.items()])
        
        await update.message.reply_text(
            f"🎯 Olá {user_name}!\n\n"
            f"✅ Tracking decodificado:\n{param_text}\n\n"
            f"Use /pix para gerar PIX com dados completos!"
        )
        
    else:
        print(f"⚠️ Nenhum parâmetro recebido - possível novo usuário")
        
        # Tenta buscar tracking recente para novos usuários
        try:
            import requests
            response = requests.get("http://localhost:8080/api/tracking/latest", timeout=5)
            if response.status_code == 200:
                api_data = response.json()
                if api_data.get('success') and api_data.get('original'):
                    tracking_data = json.loads(api_data['original'])
                    safe_id = api_data.get('safe_id')
                    
                    print(f"🔄 TRACKING RECUPERADO para novo usuário: {tracking_data}")
                    
                    # Salva dados recuperados COMPLETOS
                    click_id = tracking_data.get('click_id', 'recovered')
                    print(f"💾 Salvando dados recuperados completos: {tracking_data}")
                    
                    # Salva TODOS os dados recuperados (incluindo utm_source)
                    db.tracking_data[user_id] = tracking_data.copy()
                    
                    # Adiciona metadados necessários
                    db.tracking_data[user_id]['created_at'] = datetime.now().isoformat()
                    db.tracking_data[user_id]['status'] = 'active'
                    
                    # Salva no arquivo
                    db.save_data()
                    
                    param_text = "\n".join([f"{k}: {v}" for k, v in tracking_data.items()])
                    
                    await update.message.reply_text(
                        f"🎯 Olá {user_name}!\n\n"
                        f"✅ Tracking recuperado automaticamente:\n{param_text}\n\n"
                        f"🔄 Sistema inteligente para novos usuários!\n"
                        f"Use /pix para gerar PIX com dados completos!"
                    )
                    return
                    
        except Exception as e:
            print(f"❌ Erro ao recuperar tracking recente: {e}")
        
        # Fallback se não conseguiu recuperar
        await update.message.reply_text(
            f"👋 Olá {user_name}!\n\n"
            f"⚠️ Nenhum tracking detectado.\n"
            f"💡 Se você veio de um link, tente acessar novamente o link da presell.\n\n"
            f"Use /pix para gerar PIX de teste."
        )

async def gerar_pix_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gera PIX de R$ 10 com tracking completo"""
    await gerar_pix(update, context, 10.00)

async def gerar_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float):
    """Função para gerar PIX com tracking completo preservado"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    await update.message.reply_text("⏳ Gerando PIX com tracking completo...")
    
    # Recupera TODOS os dados de tracking preservados
    user_data = db.get_user_data(user_id)
    print(f"🔍 USER_DATA COMPLETO: {user_data}")
    
    # Garante que o tracking data esteja no formato correto para TriboPay
    tracking_data = {}
    if user_data:
        # Preserva exatamente como veio da presell
        tracking_data = user_data.copy()
        
        # Log dos dados que serão enviados
        print("📊 DADOS ENVIADOS PARA TRIBOPAY:")
        print(f"   click_id: {tracking_data.get('click_id')}")
        print(f"   utm_source: {tracking_data.get('utm_source')}")
        print(f"   utm_campaign: {tracking_data.get('utm_campaign')}")
        print(f"   utm_medium: {tracking_data.get('utm_medium')}")
    
    # Cria PIX REAL via TriboPay com TODOS os dados preservados
    pix_result = await tribopay_service.criar_cobranca_pix(
        user_id=user_id,
        plano="VIP",
        valor=amount,
        nome_cliente=user_name,
        cpf="12345678900",
        tracking_data=tracking_data
    )
    
    if pix_result['success']:
        # Salva transação
        db.save_pix_transaction(user_id, pix_result['transaction_id'], pix_result)
        
        message = (
            f"✅ PIX REAL Gerado!\n\n"
            f"💰 Valor: R$ {amount:.2f}\n"
            f"📱 Código PIX:\n`{pix_result['pix_copia_cola']}`\n\n"
            f"🆔 ID: `{pix_result['transaction_id']}`\n"
            f"📊 Tracking preservado: ✅\n\n"
            f"✅ Todos os parâmetros UTM foram enviados para TriboPay!"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Erro: {pix_result.get('error')}")


def main():
    """Função principal"""
    print("\n🚀 === XTRACKY BOT SIMPLIFICADO ===")
    print(f"📱 Bot: @XtrackyApibot")
    print(f"🔗 Teste via presell: http://localhost:9000")
    print("=====================================\n")
    
    # Cria aplicação
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Adiciona handlers essenciais
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pix", gerar_pix_cmd))
    
    print("✅ Bot iniciado!")
    print("📌 Comandos: /start (com parâmetros) e /pix")
    print("🔥 Sistema completo de tracking preservado!")
    
    # Executa bot
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()