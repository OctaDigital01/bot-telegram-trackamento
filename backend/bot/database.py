#!/usr/bin/env python3
"""
Módulo de Database PostgreSQL para Bot Telegram
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

    def get_user(self, telegram_id):
        """Buscar usuário por telegram_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM bot_users WHERE telegram_id = %s", (telegram_id,))
            return cursor.fetchone()

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

    def get_pix_transaction(self, transaction_id):
        """Buscar transação PIX"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM pix_transactions WHERE transaction_id = %s", (transaction_id,))
            return cursor.fetchone()

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

# Instância global do database
db = None

def get_db():
    """Getter para instância do database"""
    global db
    if db is None:
        db = DatabaseManager()
    return db