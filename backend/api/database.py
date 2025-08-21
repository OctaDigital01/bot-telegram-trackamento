#!/usr/bin/env python3
"""
Módulo de Database PostgreSQL para API Gateway
"""

import os
import psycopg2
import psycopg2.extras
import logging
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            logger.error("❌ DATABASE_URL não configurado!")
            raise ValueError("DATABASE_URL é obrigatório")
        
        # Criar tabelas se não existirem
        self.init_tables()
        logger.info("✅ Database PostgreSQL inicializado")

    @contextmanager
    def get_connection(self):
        """Context manager para conexões PostgreSQL"""
        conn = None
        try:
            conn = psycopg2.connect(self.database_url, sslmode='require')
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

    def init_tables(self):
        """Criar tabelas necessárias"""
        tables_sql = [
            # Tabela de usuários do bot
            """
            CREATE TABLE IF NOT EXISTS bot_users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                click_id VARCHAR(255),
                utm_source TEXT,
                utm_medium VARCHAR(255),
                utm_campaign VARCHAR(255),
                utm_term VARCHAR(255),
                utm_content VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            
            # Tabela de transações PIX
            """
            CREATE TABLE IF NOT EXISTS pix_transactions (
                id SERIAL PRIMARY KEY,
                transaction_id VARCHAR(255) UNIQUE NOT NULL,
                telegram_id BIGINT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                pix_code TEXT,
                qr_code TEXT,
                click_id VARCHAR(255),
                utm_source TEXT,
                utm_medium VARCHAR(255),
                utm_campaign VARCHAR(255),
                utm_term VARCHAR(255),
                utm_content VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES bot_users(telegram_id)
            );
            """,
            
            # Tabela de mapeamento de tracking IDs
            """
            CREATE TABLE IF NOT EXISTS tracking_mapping (
                id SERIAL PRIMARY KEY,
                safe_id VARCHAR(50) UNIQUE NOT NULL,
                original_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accessed_at TIMESTAMP
            );
            """,
            
            # Tabela de logs de conversões
            """
            CREATE TABLE IF NOT EXISTS conversion_logs (
                id SERIAL PRIMARY KEY,
                transaction_id VARCHAR(255),
                click_id VARCHAR(255),
                utm_source TEXT,
                utm_campaign VARCHAR(255),
                conversion_value DECIMAL(10,2),
                status VARCHAR(50),
                xtracky_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        ]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for table_sql in tables_sql:
                cursor.execute(table_sql)
            logger.info("✅ Tabelas PostgreSQL criadas/verificadas")

    def save_user(self, telegram_id, username, first_name, last_name, tracking_data):
        """Salvar/atualizar usuário"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_users 
                (telegram_id, username, first_name, last_name, click_id, utm_source, utm_medium, utm_campaign, utm_term, utm_content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (telegram_id) 
                DO UPDATE SET 
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    click_id = EXCLUDED.click_id,
                    utm_source = EXCLUDED.utm_source,
                    utm_medium = EXCLUDED.utm_medium,
                    utm_campaign = EXCLUDED.utm_campaign,
                    utm_term = EXCLUDED.utm_term,
                    utm_content = EXCLUDED.utm_content,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                telegram_id, username, first_name, last_name,
                tracking_data.get('click_id'),
                tracking_data.get('utm_source'),
                tracking_data.get('utm_medium'),
                tracking_data.get('utm_campaign'),
                tracking_data.get('utm_term'),
                tracking_data.get('utm_content')
            ))

    def get_user(self, telegram_id):
        """Buscar usuário por telegram_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM bot_users WHERE telegram_id = %s", (telegram_id,))
            return cursor.fetchone()

    def save_tracking_mapping(self, safe_id, original_data):
        """Salvar mapeamento de tracking ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tracking_mapping (safe_id, original_data)
                VALUES (%s, %s)
                ON CONFLICT (safe_id) 
                DO UPDATE SET original_data = EXCLUDED.original_data
            """, (safe_id, original_data))

    def get_tracking_mapping(self, safe_id):
        """Buscar dados por safe_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                UPDATE tracking_mapping 
                SET accessed_at = CURRENT_TIMESTAMP 
                WHERE safe_id = %s
            """, (safe_id,))
            
            cursor.execute("SELECT * FROM tracking_mapping WHERE safe_id = %s", (safe_id,))
            return cursor.fetchone()

    def get_latest_tracking(self, minutes=10):
        """Buscar último tracking criado nos últimos X minutos"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM tracking_mapping 
                WHERE created_at > NOW() - INTERVAL '%s minutes'
                ORDER BY created_at DESC 
                LIMIT 1
            """, (minutes,))
            return cursor.fetchone()

    def save_pix_transaction(self, transaction_id, telegram_id, amount, tracking_data):
        """Salvar transação PIX"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pix_transactions 
                (transaction_id, telegram_id, amount, click_id, utm_source, utm_medium, utm_campaign, utm_term, utm_content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                transaction_id, telegram_id, amount,
                tracking_data.get('click_id'),
                tracking_data.get('utm_source'),
                tracking_data.get('utm_medium'),
                tracking_data.get('utm_campaign'),
                tracking_data.get('utm_term'),
                tracking_data.get('utm_content')
            ))

    def update_pix_transaction(self, transaction_id, status=None, pix_code=None, qr_code=None):
        """Atualizar transação PIX"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            
            if status:
                updates.append("status = %s")
                params.append(status)
            if pix_code:
                updates.append("pix_code = %s")
                params.append(pix_code)
            if qr_code:
                updates.append("qr_code = %s")
                params.append(qr_code)
            
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(transaction_id)
                
                sql = f"UPDATE pix_transactions SET {', '.join(updates)} WHERE transaction_id = %s"
                cursor.execute(sql, params)

    def get_pix_transaction(self, transaction_id):
        """Buscar transação PIX"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM pix_transactions WHERE transaction_id = %s", (transaction_id,))
            return cursor.fetchone()

    def log_conversion(self, transaction_id, click_id, utm_source, utm_campaign, conversion_value, status, xtracky_response):
        """Log de conversão para Xtracky"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversion_logs 
                (transaction_id, click_id, utm_source, utm_campaign, conversion_value, status, xtracky_response)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (transaction_id, click_id, utm_source, utm_campaign, conversion_value, status, xtracky_response))

# Instância global do database
db = None

def get_db():
    """Getter para instância do database"""
    global db
    if db is None:
        db = DatabaseManager()
    return db