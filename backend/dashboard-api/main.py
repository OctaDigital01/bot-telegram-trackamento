#!/usr/bin/env python3
"""
Dashboard API - Serviço para fornecer dados do PostgreSQL para dashboard
"""

import os
import logging
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Inicialização do Flask
app = Flask(__name__)
CORS(app)

# Configurações
DATABASE_URL = os.getenv('DATABASE_URL')
API_PORT = int(os.getenv('PORT', '8081'))

@contextmanager
def get_connection():
    """Context manager para conexões PostgreSQL"""
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"❌ Erro no database: {e}")
        raise
    finally:
        if conn:
            conn.close()

def check_table_exists(table_name):
    """Verifica se tabela existe"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table_name,))
            return cursor.fetchone()[0]
    except:
        return False

@app.route('/health', methods=['GET'])
def health_check():
    """Health check da API"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/api/overview', methods=['GET'])
def get_overview():
    """Dados para aba Visão Geral"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        data = {}
        
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Base query for date filtering
            date_filter = ""
            date_params = []
            
            if start_date and end_date:
                date_filter = "WHERE created_at::date BETWEEN %s AND %s"
                date_params = [start_date, end_date]
            
            # 1. Entradas na presell (tracking_mapping)
            if check_table_exists('tracking_mapping'):
                cursor.execute(f"""
                    SELECT COUNT(*) as total 
                    FROM tracking_mapping {date_filter}
                """, date_params)
                data['presell_entries'] = cursor.fetchone()['total']
            else:
                data['presell_entries'] = 0
            
            # 2. /start no bot (bot_users)
            if check_table_exists('bot_users'):
                cursor.execute(f"""
                    SELECT COUNT(*) as total 
                    FROM bot_users {date_filter}
                """, date_params)
                data['bot_starts'] = cursor.fetchone()['total']
            else:
                data['bot_starts'] = 0
            
            # 3. PIX gerados (pix_transactions)
            if check_table_exists('pix_transactions'):
                cursor.execute(f"""
                    SELECT COUNT(*) as total 
                    FROM pix_transactions {date_filter}
                """, date_params)
                data['pix_generated'] = cursor.fetchone()['total']
                
                # PIX pagos
                cursor.execute(f"""
                    SELECT COUNT(*) as total 
                    FROM pix_transactions 
                    WHERE status = 'paid' {' AND ' + date_filter.replace('WHERE ', '') if date_filter else ''}
                """, date_params)
                data['pix_paid'] = cursor.fetchone()['total']
            else:
                data['pix_generated'] = 0
                data['pix_paid'] = 0
            
            # 4. Conversões (conversion_logs)
            if check_table_exists('conversion_logs'):
                cursor.execute(f"""
                    SELECT COUNT(*) as total 
                    FROM conversion_logs {date_filter}
                """, date_params)
                data['conversions'] = cursor.fetchone()['total']
            else:
                data['conversions'] = 0
                
        # Etapas do funil (simulado por enquanto)
        data['step_1_welcome'] = data['bot_starts']
        data['step_2_preview'] = int(data['bot_starts'] * 0.8)
        data['step_3_gallery'] = int(data['bot_starts'] * 0.6)
        data['step_4_vip_plans'] = int(data['bot_starts'] * 0.4)
        data['step_5_payment'] = data['pix_generated']
        
        # Dados adicionais
        data['blocked_users'] = 0  # Implementar quando houver tabela
        data['joined_group'] = 0   # Implementar quando houver tabela
        data['left_group'] = 0     # Implementar quando houver tabela
        
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"❌ Erro em get_overview: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales', methods=['GET'])
def get_sales():
    """Dados para aba Vendas"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        data = {
            'total_revenue': 0,
            'total_transactions': 0,
            'conversion_rate': 0,
            'average_ticket': 0,
            'sales_by_date': [],
            'sales_by_plan': []
        }
        
        if not check_table_exists('pix_transactions'):
            return jsonify(data)
        
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Base query for date filtering
            date_filter = ""
            date_params = []
            
            if start_date and end_date:
                date_filter = "WHERE created_at::date BETWEEN %s AND %s"
                date_params = [start_date, end_date]
            
            # Total de vendas
            cursor.execute(f"""
                SELECT 
                    SUM(amount) as total_revenue,
                    COUNT(*) as total_transactions,
                    AVG(amount) as average_ticket
                FROM pix_transactions 
                WHERE status = 'paid' {' AND ' + date_filter.replace('WHERE ', '') if date_filter else ''}
            """, date_params)
            
            result = cursor.fetchone()
            if result:
                data['total_revenue'] = float(result['total_revenue'] or 0)
                data['total_transactions'] = result['total_transactions']
                data['average_ticket'] = float(result['average_ticket'] or 0)
            
            # Taxa de conversão
            cursor.execute(f"""
                SELECT COUNT(*) as total_pix 
                FROM pix_transactions {date_filter}
            """, date_params)
            
            total_pix = cursor.fetchone()['total_pix']
            if total_pix > 0:
                data['conversion_rate'] = (data['total_transactions'] / total_pix) * 100
            
            # Vendas por data (últimos 30 dias ou período selecionado)
            if not start_date or not end_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT 
                    created_at::date as date,
                    SUM(amount) as revenue,
                    COUNT(*) as transactions
                FROM pix_transactions 
                WHERE status = 'paid' 
                AND created_at::date BETWEEN %s AND %s
                GROUP BY created_at::date
                ORDER BY date DESC
            """, [start_date, end_date])
            
            sales_by_date = cursor.fetchall()
            data['sales_by_date'] = [
                {
                    'date': row['date'].strftime('%Y-%m-%d'),
                    'revenue': float(row['revenue']),
                    'transactions': row['transactions']
                } for row in sales_by_date
            ]
            
            # Vendas por plano (se coluna plano_id existir)
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='pix_transactions' AND column_name='plano_id'
            """)
            
            if cursor.fetchone():
                cursor.execute(f"""
                    SELECT 
                        plano_id,
                        SUM(amount) as revenue,
                        COUNT(*) as transactions
                    FROM pix_transactions 
                    WHERE status = 'paid' {' AND ' + date_filter.replace('WHERE ', '') if date_filter else ''}
                    GROUP BY plano_id
                """, date_params)
                
                sales_by_plan = cursor.fetchall()
                data['sales_by_plan'] = [
                    {
                        'plan': row['plano_id'] or 'Sem plano',
                        'revenue': float(row['revenue']),
                        'transactions': row['transactions']
                    } for row in sales_by_plan
                ]
        
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"❌ Erro em get_sales: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Logs detalhados do sistema"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))
        
        logs = []
        
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            date_filter = ""
            date_params = []
            
            if start_date and end_date:
                date_filter = "WHERE created_at::date BETWEEN %s AND %s"
                date_params = [start_date, end_date]
            
            # Logs de conversão
            if check_table_exists('conversion_logs'):
                cursor.execute(f"""
                    SELECT 
                        'conversion' as type,
                        transaction_id,
                        click_id,
                        utm_source,
                        utm_campaign,
                        conversion_value,
                        status,
                        created_at
                    FROM conversion_logs {date_filter}
                    ORDER BY created_at DESC
                    LIMIT %s
                """, date_params + [limit])
                
                conversion_logs = cursor.fetchall()
                logs.extend([
                    {
                        'type': 'Conversão',
                        'message': f"Conversão {row['transaction_id']} - {row['status']}",
                        'details': {
                            'click_id': row['click_id'],
                            'utm_source': row['utm_source'],
                            'utm_campaign': row['utm_campaign'],
                            'value': float(row['conversion_value']) if row['conversion_value'] else 0
                        },
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None
                    } for row in conversion_logs
                ])
            
            # Logs de transações PIX
            if check_table_exists('pix_transactions'):
                cursor.execute(f"""
                    SELECT 
                        transaction_id,
                        telegram_id,
                        amount,
                        status,
                        created_at,
                        updated_at
                    FROM pix_transactions {date_filter}
                    ORDER BY created_at DESC
                    LIMIT %s
                """, date_params + [limit])
                
                pix_logs = cursor.fetchall()
                logs.extend([
                    {
                        'type': 'PIX',
                        'message': f"PIX {row['transaction_id']} - {row['status']} - R$ {float(row['amount'])}",
                        'details': {
                            'telegram_id': row['telegram_id'],
                            'amount': float(row['amount']),
                            'status': row['status'],
                            'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                        },
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None
                    } for row in pix_logs
                ])
        
        # Ordena por data
        logs.sort(key=lambda x: x['created_at'] or '', reverse=True)
        
        return jsonify({'logs': logs[:limit]})
        
    except Exception as e:
        logger.error(f"❌ Erro em get_logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/summary', methods=['GET'])
def get_stats_summary():
    """Resumo estatístico geral"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            stats = {}
            
            # Stats das últimas 24h
            cursor.execute("""
                SELECT 'last_24h' as period,
                    COALESCE(COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END), 0) as new_users,
                    COALESCE(SUM(CASE WHEN status = 'paid' AND created_at > NOW() - INTERVAL '24 hours' THEN amount END), 0) as revenue_24h
                FROM pix_transactions
            """)
            
            last_24h = cursor.fetchone()
            stats['last_24h'] = {
                'new_transactions': last_24h['new_users'],
                'revenue': float(last_24h['revenue_24h'] or 0)
            }
            
            # Stats da última semana
            cursor.execute("""
                SELECT 'last_week' as period,
                    COALESCE(COUNT(CASE WHEN created_at > NOW() - INTERVAL '7 days' THEN 1 END), 0) as new_users,
                    COALESCE(SUM(CASE WHEN status = 'paid' AND created_at > NOW() - INTERVAL '7 days' THEN amount END), 0) as revenue_week
                FROM pix_transactions
            """)
            
            last_week = cursor.fetchone()
            stats['last_week'] = {
                'new_transactions': last_week['new_users'],
                'revenue': float(last_week['revenue_week'] or 0)
            }
            
            return jsonify(stats)
            
    except Exception as e:
        logger.error(f"❌ Erro em get_stats_summary: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Dashboard API iniciando...")
    
    if not DATABASE_URL:
        logger.error("❌ DATABASE_URL não configurado!")
        exit(1)
        
    logger.info(f"✅ Dashboard API rodando na porta {API_PORT}")
    app.run(host='0.0.0.0', port=API_PORT, debug=False)