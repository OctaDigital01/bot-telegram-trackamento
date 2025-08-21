from datetime import datetime
import json
import os

class Database:
    def __init__(self):
        # Para Railway, usa arquivo na raiz ou pasta /tmp se disponível
        import os
        if os.getenv('RAILWAY_ENVIRONMENT'):
            # Railway - usar pasta temporária ou raiz
            self.data_file = "/tmp/bot_database.json" if os.path.exists('/tmp') else "bot_database.json"
        else:
            # Local - usar pasta data
            self.data_file = "data/bot_database.json"
        self.tracking_data = {}
        self.pix_transactions = {}
        self.load_data()
    
    def save_click_id(self, user_id, click_id):
        """Salva o click_id do Kwai associado ao usuário"""
        # Preserva apenas dados essenciais, não herda dados antigos desnecessários
        base_data = {
            'click_id': click_id,
            'created_at': datetime.now().isoformat(),
            'status': 'active'
        }
        
        # Se já existe dados, preserva apenas transaction_id e pix_status se existirem
        if user_id in self.tracking_data:
            existing = self.tracking_data[user_id]
            if 'transaction_id' in existing:
                base_data['transaction_id'] = existing['transaction_id']
            if 'pix_status' in existing:
                base_data['pix_status'] = existing['pix_status']
        
        self.tracking_data[user_id] = base_data
        print(f"✅ Click ID salvo: User {user_id} -> {click_id}")
        self.save_data()
        return True
    
    def get_click_id(self, user_id):
        """Recupera o click_id do usuário"""
        if user_id in self.tracking_data:
            return self.tracking_data[user_id].get('click_id')
        return None
    
    def save_pix_transaction(self, user_id, transaction_id, pix_data):
        """Salva dados da transação PIX"""
        self.pix_transactions[transaction_id] = {
            'user_id': user_id,
            'pix_data': pix_data,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        
        if user_id in self.tracking_data:
            self.tracking_data[user_id]['transaction_id'] = transaction_id
            self.tracking_data[user_id]['pix_status'] = 'pending'
        
        print(f"💳 PIX salvo: Transaction {transaction_id}")
        self.save_data()
        return True
    
    def update_payment_status(self, transaction_id, status):
        """Atualiza status do pagamento"""
        if transaction_id in self.pix_transactions:
            self.pix_transactions[transaction_id]['status'] = status
            user_id = self.pix_transactions[transaction_id]['user_id']
            
            if user_id in self.tracking_data:
                self.tracking_data[user_id]['pix_status'] = status
            
            print(f"✅ Status atualizado: {transaction_id} -> {status}")
            self.save_data()
            return True
        return False
    
    def get_user_data(self, user_id):
        """Retorna todos os dados do usuário"""
        return self.tracking_data.get(user_id, {})
    
    def get_transaction(self, transaction_id):
        """Retorna dados de uma transação"""
        return self.pix_transactions.get(transaction_id, {})
    
    def show_all_data(self):
        """Mostra todos os dados (para debug)"""
        print("\n📊 === DATABASE STATUS ===")
        print(f"Tracking Data: {json.dumps(self.tracking_data, indent=2)}")
        print(f"PIX Transactions: {json.dumps(self.pix_transactions, indent=2)}")
        print("========================\n")
    
    def load_data(self):
        """Carrega dados do arquivo"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.tracking_data = data.get('tracking_data', {})
                    self.pix_transactions = data.get('pix_transactions', {})
                    print(f"📂 Dados carregados: {len(self.tracking_data)} usuários, {len(self.pix_transactions)} transações")
            else:
                print("📂 Arquivo de dados não encontrado, criando novo database")
        except Exception as e:
            print(f"⚠️ Erro ao carregar dados: {e}")
    
    def save_data(self):
        """Salva dados no arquivo"""
        try:
            data = {
                'tracking_data': self.tracking_data,
                'pix_transactions': self.pix_transactions,
                'last_update': datetime.now().isoformat()
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Erro ao salvar dados: {e}")
    
    def backup_data(self):
        """Cria backup dos dados"""
        try:
            import shutil
            backup_name = f"bot_database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(self.data_file, backup_name)
            print(f"💾 Backup criado: {backup_name}")
            return backup_name
        except Exception as e:
            print(f"⚠️ Erro ao criar backup: {e}")
            return None

# Instância global
db = Database()