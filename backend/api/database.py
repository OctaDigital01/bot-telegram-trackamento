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
                plano_id VARCHAR(100),
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
            """,
            
            # Tabela de cache de produtos TriboPay
            """
            CREATE TABLE IF NOT EXISTS tribopay_products_cache (
                id SERIAL PRIMARY KEY,
                cache_key VARCHAR(100) UNIQUE NOT NULL,
                product_hash VARCHAR(255) NOT NULL,
                plano VARCHAR(50),
                valor DECIMAL(10,2),
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
        try:
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
                logger.info(f"✅ Usuário {telegram_id} salvo/atualizado com sucesso no PostgreSQL")
                return True
        except Exception as e:
            logger.error(f"❌ Erro salvando usuário {telegram_id}: {e}")
            return False

    def get_user(self, telegram_id):
        """Buscar usuário por telegram_id"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("SELECT * FROM bot_users WHERE telegram_id = %s", (telegram_id,))
                user = cursor.fetchone()
                
                if user:
                    # Converte para formato esperado pela API com tracking_data
                    tracking_data = {
                        'click_id': user.get('click_id'),
                        'utm_source': user.get('utm_source'),
                        'utm_medium': user.get('utm_medium'),
                        'utm_campaign': user.get('utm_campaign'),
                        'utm_term': user.get('utm_term'),
                        'utm_content': user.get('utm_content')
                    }
                    # Remove valores None do tracking_data
                    tracking_data = {k: v for k, v in tracking_data.items() if v is not None}
                    
                    return {
                        'id': user.get('id'),
                        'telegram_id': user.get('telegram_id'),
                        'username': user.get('username'),
                        'first_name': user.get('first_name'),
                        'last_name': user.get('last_name'),
                        'tracking_data': tracking_data,
                        'created_at': user.get('created_at'),
                        'updated_at': user.get('updated_at')
                    }
                return None
        except Exception as e:
            logger.error(f"❌ Erro buscando usuário {telegram_id}: {e}")
            return None

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

    def save_pix_transaction(self, transaction_id, telegram_id, amount, tracking_data, plano_id=None):
        """Salvar transação PIX"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Verifica se a coluna plano_id existe
            try:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='pix_transactions' AND column_name='plano_id'
                """)
                plano_id_exists = cursor.fetchone()
                
                if plano_id_exists:
                    # Se a coluna existe, insere com plano_id
                    cursor.execute("""
                        INSERT INTO pix_transactions 
                        (transaction_id, telegram_id, amount, plano_id, click_id, utm_source, utm_medium, utm_campaign, utm_term, utm_content)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        transaction_id, telegram_id, amount, plano_id,
                        tracking_data.get('click_id'),
                        tracking_data.get('utm_source'),
                        tracking_data.get('utm_medium'),
                        tracking_data.get('utm_campaign'),
                        tracking_data.get('utm_term'),
                        tracking_data.get('utm_content')
                    ))
                else:
                    # Fallback: insere sem plano_id
                    logger.warning("⚠️ Coluna plano_id não existe - inserindo sem plano_id")
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
                    
            except Exception as e:
                logger.error(f"❌ Erro em save_pix_transaction: {e}")
                raise

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

    def get_active_pix(self, telegram_id, plano_id):
        """Buscar PIX ativo para usuário e plano específico (válido por 1h)"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Primeiro verifica se a coluna plano_id existe
            try:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='pix_transactions' AND column_name='plano_id'
                """)
                plano_id_exists = cursor.fetchone()
                
                if plano_id_exists:
                    # CORREÇÃO: Busca PIX válidos (pending OU waiting_payment) para plano específico
                    cursor.execute("""
                        SELECT * FROM pix_transactions 
                        WHERE telegram_id = %s 
                        AND plano_id = %s 
                        AND status IN ('pending', 'waiting_payment') 
                        AND created_at > NOW() - INTERVAL '1 hour'
                        ORDER BY created_at DESC 
                        LIMIT 1
                    """, (telegram_id, plano_id))
                    logger.info(f"🔍 Buscando PIX para user {telegram_id}, plano {plano_id} (com coluna plano_id)")
                else:
                    # CORREÇÃO: Mesmo sem coluna plano_id, busca status corretos
                    logger.warning("⚠️ Coluna plano_id não existe - usando fallback SEM filtro de plano")
                    cursor.execute("""
                        SELECT * FROM pix_transactions 
                        WHERE telegram_id = %s 
                        AND status IN ('pending', 'waiting_payment') 
                        AND created_at > NOW() - INTERVAL '1 hour'
                        ORDER BY created_at DESC 
                        LIMIT 1
                    """, (telegram_id,))
                
                result = cursor.fetchone()
                if result:
                    logger.info(f"✅ PIX ativo encontrado: {result.get('transaction_id')} - Status: {result.get('status')}")
                else:
                    logger.info(f"❌ Nenhum PIX ativo encontrado para user {telegram_id}, plano {plano_id}")
                
                return result
                
            except Exception as e:
                logger.error(f"❌ Erro em get_active_pix: {e}")
                # Fallback final: retorna None
                return None

    def get_valid_pix(self, telegram_id, plano_id):
        """Alias para get_active_pix - mantém compatibilidade"""
        result = self.get_active_pix(telegram_id, plano_id)
        if result:
            # Converte para formato esperado pela API
            return {
                'pix_copia_cola': result.get('pix_code'),
                'qr_code': result.get('qr_code'),
                'transaction_id': result.get('transaction_id'),
                'created_at': result.get('created_at'),
                'status': result.get('status')
            }
        return None
    
    def invalidate_user_pix(self, telegram_id):
        """Invalida todos os PIX pendentes do usuário"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pix_transactions 
                SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP 
                WHERE telegram_id = %s AND status = 'pending'
            """, (telegram_id,))
            return cursor.rowcount

    def log_conversion(self, transaction_id, click_id, utm_source, utm_campaign, conversion_value, status, xtracky_response):
        """Log de conversão para Xtracky"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversion_logs 
                (transaction_id, click_id, utm_source, utm_campaign, conversion_value, status, xtracky_response)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (transaction_id, click_id, utm_source, utm_campaign, conversion_value, status, xtracky_response))
    
    def save_cached_product(self, cache_key, product_hash, plano, valor):
        """Salva produto no cache TriboPay"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tribopay_products_cache (cache_key, product_hash, plano, valor)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (cache_key) 
                DO UPDATE SET product_hash = EXCLUDED.product_hash
            """, (cache_key, product_hash, plano, valor))
    
    def get_cached_product(self, cache_key):
        """Busca produto no cache TriboPay"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM tribopay_products_cache 
                WHERE cache_key = %s
            """, (cache_key,))
            return cursor.fetchone()

# Instância global do database
db = None

def get_db():
    """Getter para instância do database"""
    global db
    if db is None:
        db = DatabaseManager()
    return db