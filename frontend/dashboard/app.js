// Dashboard Ana Cardoso Bot Analytics
// JavaScript para gerenciar dados e interface

class Dashboard {
    constructor() {
        this.apiUrl = 'https://api-gateway-production-22bb.up.railway.app'; // API Gateway correta - atualizada 22/08/2025
        this.currentTab = 'overview';
        this.lastUpdate = null;
        this.refreshInterval = null;
        this.timezone = 'America/Sao_Paulo';
        
        this.initializeApp();
    }
    
    async initializeApp() {
        console.log('🚀 Inicializando Dashboard v2.0...');
        
        // Configurar dates default (últimos 7 dias)
        this.setDefaultDates();
        
        // Carregar dados iniciais
        await this.loadAllData();
        
        // Auto-refresh a cada 5 minutos
        this.startAutoRefresh();
        
        console.log('✅ Dashboard inicializada');
    }
    
    setDefaultDates() {
        const today = new Date();
        const weekAgo = new Date(today);
        weekAgo.setDate(weekAgo.getDate() - 7);
        
        document.getElementById('startDate').value = this.formatDate(weekAgo);
        document.getElementById('endDate').value = this.formatDate(today);
    }
    
    formatDate(date) {
        return date.toISOString().split('T')[0];
    }
    
    formatCurrency(value) {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(value);
    }
    
    formatNumber(value) {
        return new Intl.NumberFormat('pt-BR').format(value);
    }
    
    formatDateTime(dateString) {
        if (!dateString) return '-';
        
        const date = new Date(dateString);
        return date.toLocaleString('pt-BR', {
            timeZone: this.timezone,
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    async apiRequest(endpoint, params = {}) {
        try {
            const url = new URL(`${this.apiUrl}${endpoint}`);
            Object.keys(params).forEach(key => {
                if (params[key]) {
                    url.searchParams.append(key, params[key]);
                }
            });
            
            console.log(`📡 API Request: ${url.toString()}`);
            
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log(`✅ API Response:`, data);
            return data;
            
        } catch (error) {
            console.error(`❌ Erro na API ${endpoint}:`, error);
            this.showError(`Erro ao carregar dados: ${error.message}`);
            return null;
        }
    }
    
    getDateFilters() {
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        
        return {
            start_date: startDate || null,
            end_date: endDate || null
        };
    }
    
    async loadOverviewData() {
        console.log('📊 Carregando dados da visão geral...');
        
        const filters = this.getDateFilters();
        const data = await this.apiRequest('/api/overview', filters);
        
        if (!data) return;
        
        // Atualizar cards principais
        this.updateElement('presell-entries', this.formatNumber(data.presell_entries || 0));
        this.updateElement('bot-starts', this.formatNumber(data.bot_starts || 0));
        this.updateElement('pix-generated', this.formatNumber(data.pix_generated || 0));
        this.updateElement('pix-paid', this.formatNumber(data.pix_paid || 0));
        
        // Etapas do funil
        this.updateElement('step-1', this.formatNumber(data.step_1_welcome || 0));
        this.updateElement('step-2', this.formatNumber(data.step_2_preview || 0));
        this.updateElement('step-3', this.formatNumber(data.step_3_gallery || 0));
        this.updateElement('step-4', this.formatNumber(data.step_4_vip_plans || 0));
        this.updateElement('step-5', this.formatNumber(data.step_5_payment || 0));
        
        // Dados adicionais
        this.updateElement('blocked-users', this.formatNumber(data.blocked_users || 0));
        this.updateElement('joined-group', this.formatNumber(data.joined_group || 0));
        this.updateElement('left-group', this.formatNumber(data.left_group || 0));
        this.updateElement('conversions', this.formatNumber(data.conversions || 0));
        
        // Atualizar quick stats
        const conversionRate = data.pix_generated > 0 ? 
            ((data.pix_paid / data.pix_generated) * 100).toFixed(1) : '0';
        this.updateElement('quick-conversion', `${conversionRate}%`);
        this.updateElement('quick-users', this.formatNumber(data.bot_starts || 0));
        
        console.log('✅ Dados da visão geral carregados');
    }
    
    async loadSalesData() {
        console.log('💰 Carregando dados de vendas...');
        
        const filters = this.getDateFilters();
        const data = await this.apiRequest('/api/sales', filters);
        
        if (!data) return;
        
        // Atualizar cards de vendas
        this.updateElement('total-revenue', this.formatCurrency(data.total_revenue || 0));
        this.updateElement('total-transactions', this.formatNumber(data.total_transactions || 0));
        this.updateElement('conversion-rate', `${(data.conversion_rate || 0).toFixed(1)}%`);
        this.updateElement('average-ticket', this.formatCurrency(data.average_ticket || 0));
        
        // Atualizar receita total no quick stats
        this.updateElement('quick-revenue', this.formatCurrency(data.total_revenue || 0));
        
        // Vendas por data (gráfico placeholder)
        this.updateSalesChart(data.sales_by_date || []);
        
        // Vendas por plano
        this.updateSalesByPlan(data.sales_by_plan || []);
        
        console.log('✅ Dados de vendas carregados');
    }
    
    updateSalesChart(salesData) {
        const chartData = document.getElementById('sales-chart-data');
        if (!chartData) return;
        
        if (salesData.length === 0) {
            chartData.innerHTML = '<p style="color: #94a3b8; margin-top: 1rem;">Nenhum dado de vendas encontrado para o período selecionado</p>';
            return;
        }
        
        let chartHtml = '<div style="font-size: 0.875rem; color: #cbd5e1; margin-top: 1rem;">';
        chartHtml += '<div style="display: grid; gap: 0.5rem;">';
        
        salesData.slice(0, 10).forEach(item => {
            const date = new Date(item.date).toLocaleDateString('pt-BR');
            chartHtml += `
                <div style="display: flex; justify-content: space-between; padding: 0.5rem; background: rgba(45, 45, 90, 0.3); border-radius: 4px;">
                    <span>${date}</span>
                    <div>
                        <span style="color: #10b981;">${this.formatCurrency(item.revenue)}</span>
                        <span style="color: #94a3b8; margin-left: 0.5rem;">(${item.transactions} vendas)</span>
                    </div>
                </div>
            `;
        });
        
        chartHtml += '</div></div>';
        chartData.innerHTML = chartHtml;
    }
    
    updateSalesByPlan(planData) {
        const tbody = document.getElementById('sales-by-plan');
        if (!tbody) return;
        
        if (planData.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; color: #94a3b8; padding: 2rem;">
                        Nenhuma venda encontrada para o período selecionado
                    </td>
                </tr>
            `;
            return;
        }
        
        const totalRevenue = planData.reduce((sum, item) => sum + item.revenue, 0);
        
        let html = '';
        planData.forEach(item => {
            const percentage = totalRevenue > 0 ? 
                ((item.revenue / totalRevenue) * 100).toFixed(1) : '0';
                
            html += `
                <tr>
                    <td>${item.plan || 'Sem plano'}</td>
                    <td>${this.formatCurrency(item.revenue)}</td>
                    <td>${this.formatNumber(item.transactions)}</td>
                    <td>${percentage}%</td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
    }
    
    async loadLogsData() {
        console.log('📋 Carregando logs do sistema...');
        
        const filters = this.getDateFilters();
        const data = await this.apiRequest('/api/logs', { ...filters, limit: 50 });
        
        if (!data || !data.logs) return;
        
        const tbody = document.getElementById('logs-data');
        if (!tbody) return;
        
        if (data.logs.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; color: #94a3b8; padding: 2rem;">
                        Nenhum log encontrado para o período selecionado
                    </td>
                </tr>
            `;
            return;
        }
        
        let html = '';
        data.logs.forEach(log => {
            const statusClass = this.getLogStatusClass(log.type);
            const details = this.formatLogDetails(log.details);
            
            html += `
                <tr>
                    <td>
                        <span class="status-badge ${statusClass}">${log.type}</span>
                    </td>
                    <td>${log.message}</td>
                    <td>${this.formatDateTime(log.created_at)}</td>
                    <td>${details}</td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
        console.log('✅ Logs carregados');
    }
    
    getLogStatusClass(type) {
        switch (type.toLowerCase()) {
            case 'conversão':
                return 'success';
            case 'pix':
                return 'info';
            case 'error':
                return 'error';
            default:
                return 'info';
        }
    }
    
    formatLogDetails(details) {
        if (!details || typeof details !== 'object') return '-';
        
        const items = Object.entries(details)
            .filter(([key, value]) => value !== null && value !== undefined)
            .map(([key, value]) => `${key}: ${value}`)
            .slice(0, 3);
            
        return items.join('<br>') || '-';
    }
    
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        } else {
            console.warn(`⚠️ Elemento não encontrado: ${id}`);
        }
    }
    
    showError(message) {
        // Criar notificação de erro
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.innerHTML = `
            <strong>Erro:</strong> ${message}
            <br><small>Verifique a conexão com a API e tente novamente.</small>
        `;
        
        // Inserir no topo da main
        const main = document.querySelector('.main .container');
        if (main) {
            main.insertBefore(errorDiv, main.firstChild);
            
            // Remover após 10 segundos
            setTimeout(() => {
                if (errorDiv.parentNode) {
                    errorDiv.parentNode.removeChild(errorDiv);
                }
            }, 10000);
        }
    }
    
    async loadAllData() {
        console.log('🔄 Carregando todos os dados...');
        
        this.setRefreshButtonLoading(true);
        
        try {
            // Carregar dados baseado na aba ativa
            switch (this.currentTab) {
                case 'overview':
                    await this.loadOverviewData();
                    break;
                case 'sales':
                    await this.loadSalesData();
                    break;
                case 'logs':
                    await this.loadLogsData();
                    break;
            }
            
            this.lastUpdate = new Date();
            console.log('✅ Todos os dados carregados');
            
        } catch (error) {
            console.error('❌ Erro carregando dados:', error);
            this.showError('Falha ao carregar dados da dashboard');
        } finally {
            this.setRefreshButtonLoading(false);
        }
    }
    
    setRefreshButtonLoading(loading) {
        const btn = document.querySelector('.refresh-btn');
        if (!btn) return;
        
        if (loading) {
            btn.classList.add('loading');
            btn.disabled = true;
        } else {
            btn.classList.remove('loading');
            btn.disabled = false;
        }
    }
    
    startAutoRefresh() {
        // Auto-refresh a cada 5 minutos
        this.refreshInterval = setInterval(() => {
            console.log('🔄 Auto-refresh executando...');
            this.loadAllData();
        }, 5 * 60 * 1000);
        
        console.log('⏰ Auto-refresh configurado para 5 minutos');
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
}

// Funções globais para interface
function switchTab(tabName) {
    console.log(`🔄 Mudando para aba: ${tabName}`);
    
    // Atualizar botões
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[onclick="switchTab('${tabName}')"]`).classList.add('active');
    
    // Atualizar conteúdo
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    // Atualizar aba atual na instância
    if (window.dashboard) {
        window.dashboard.currentTab = tabName;
        window.dashboard.loadAllData();
    }
}

function refreshData() {
    console.log('🔄 Refresh manual solicitado');
    if (window.dashboard) {
        window.dashboard.loadAllData();
    }
}

function applyFilters() {
    console.log('🎯 Aplicando filtros...');
    if (window.dashboard) {
        window.dashboard.loadAllData();
    }
}

// Inicializar quando DOM carregar
document.addEventListener('DOMContentLoaded', () => {
    console.log('🌐 DOM carregado, inicializando dashboard...');
    window.dashboard = new Dashboard();
});

// Cleanup quando sair da página
window.addEventListener('beforeunload', () => {
    if (window.dashboard) {
        window.dashboard.stopAutoRefresh();
    }
});

// Health check da API
async function checkApiHealth() {
    try {
        const response = await fetch('https://api-gateway-production-22bb.up.railway.app/health');
        const data = await response.json();
        
        if (data.status === 'ok') {
            console.log('✅ API Health Check: OK');
        } else {
            console.warn('⚠️ API Health Check: Degraded');
        }
    } catch (error) {
        console.error('❌ API Health Check: Failed', error);
    }
}

// Executar health check inicial
setTimeout(checkApiHealth, 1000);