# Projeto: Bot Telegram com Tracking Xtracky e Gateway TriboPay

## 📋 Estrutura do Projeto

```
/Trackamento Bot Telegram/
├── bot.py                # Bot principal do Telegram
├── config.py            # Configurações (tokens, APIs)
├── database.py          # Sistema de banco de dados JSON
├── tribopay_service.py  # Integração com TriboPay Payment
├── tribopay_webhook.py  # Webhook TriboPay para receber notificações
├── xtracky_webhook.py   # Integração com Xtracky API
├── main.py              # Script principal que roda bot + webhook
├── index.html           # Página de presell para captura de click_id
├── requirements.txt     # Dependências Python
├── persistent_logs.py   # Sistema de logs persistentes
├── bot_database.json    # Arquivo de banco de dados
├── .env                # Variáveis de ambiente
└── xtracky_conversions.log # Logs de conversões Xtracky
```

## 🎯 Objetivo do Projeto

Bot Telegram que:
1. Recebe tráfego do Kwai com click_id via deep link
2. Preserva o click_id durante todo o fluxo
3. Gera PIX via TriboPay Payment Gateway
4. Envia conversão para Xtracky quando PIX é pago
5. Xtracky otimiza e retorna dados ao Kwai

## 🔄 Fluxo Completo

1. **Usuário acessa presell** (index.html) com parâmetros Xtracky
2. **Captura click_id** e outros dados de tracking
3. **Redireciona** para bot Telegram com dados preservados
4. **Bot processa** comando /start e salva tracking data
5. **Usuário gera PIX** (/pix10 ou /pix50)
6. **Sistema cria** cobrança via TriboPay
7. **Usuário paga** PIX no app bancário
8. **TriboPay** envia webhook de confirmação
9. **Sistema processa** pagamento e envia conversão para Xtracky
10. **Xtracky** registra conversão e atribui ao click_id correto

## 🛠️ Credenciais

### Bot Telegram
- Username: @XtrackyApibot
- Token: 7251726481:AAG03mNgEm_-qE0MMRpP7xcRZ2Qlhos-DGc

### TriboPay Payment
- API Key: IzJsCJ0BleuURRzZvrTeigPp6xknO8e9nHT6WZtDpxFQVocwa3E3GYeNXtYq
- Base URL: https://api.tribopay.com.br/api/public/v1

### Xtracky
- Token: 72701474-7e6c-4c87-b84f-836d4547a4bd
- Webhook URL: https://api.xtracky.com/api/integrations/tribopay

## 📏 Regras de Desenvolvimento

### Limpeza e Organização
- ✅ Apenas arquivos essenciais
- ✅ Sem arquivos de teste desnecessários
- ✅ Código limpo e comentado apenas onde necessário
- ✅ Funções bem definidas e separadas por responsabilidade
- ✅ Usar terminal macOS para testes, não criar arquivos temporários

### ⚠️ REGRA CRÍTICA DE DEBUG
- ❌ NUNCA criar novos arquivos quando houver erro
- ✅ SEMPRE editar o arquivo existente que deu erro
- ✅ Analisar CADA DETALHE do erro antes de editar
- ✅ Manter a organização - máximo de arquivos essenciais apenas
- ✅ Resolver problemas no arquivo original, não criar alternativas

### Boas Práticas
- ✅ Variáveis de ambiente para credenciais sensíveis
- ✅ Logging adequado para debug
- ✅ Tratamento de erros em todas as requisições
- ✅ Dados persistentes em JSON para produção
- ✅ Servidor local rodando direto no terminal
- ✅ TESTES REAIS - usar APIs reais sempre
- ✅ Testar pelo terminal macOS sempre

## 💻 Comandos do Bot

- `/start` - Inicia bot e captura tracking
- `/pix10` - Gera PIX de R$ 10
- `/pix50` - Gera PIX de R$ 50  
- `/verificar` - Verifica status do pagamento
- `/dados` - Mostra dados do usuário
- `/status` - Status geral do sistema
- `/logs` - Ver logs detalhados das conversões

## 💻 Comandos de Execução

### Instalação
```bash
pip install -r requirements.txt
```

### Execução
```bash
python bot.py              # Apenas bot
python main.py             # Bot + Webhook completo
```

### Teste Manual
1. Abrir Telegram
2. Acessar: t.me/XtrackyApibot?start=TEST_CLICK_123
3. Usar /pix10 para gerar PIX
4. Usar /verificar para checar status
5. Verificar logs no terminal

## 📊 Status do Projeto

- ✅ Bot Telegram funcionando
- ✅ Integração TriboPay completa
- ✅ Sistema de webhook ativo
- ✅ Tracking Xtracky implementado
- ✅ Presell page funcionando
- ✅ Sistema de logs persistentes
- ✅ Fluxo completo testado
- ✅ Projeto 100% limpo (sem Genesis)

## ⚠️ Notas Importantes

- Sistema em produção com APIs reais
- PIX reais sendo gerados via TriboPay
- Logs detalhados salvos em arquivo
- Webhook configurado para receber confirmações
- Todas as referências Genesis foram removidas