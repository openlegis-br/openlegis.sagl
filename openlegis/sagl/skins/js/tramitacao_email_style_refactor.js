/**
 * Tramitação Estilo Email - JavaScript Modular
 * Gerencia toda a lógica de interação da interface de tramitação
 */

// Variável global para código do usuário (será injetada via DTML)
const COD_USUARIO_CORRENTE = typeof window.COD_USUARIO_CORRENTE !== 'undefined' 
    ? window.COD_USUARIO_CORRENTE 
    : 0;

// Variável global para portal_url (será injetada via DTML, ou usa window.location.origin como fallback)
const PORTAL_URL = typeof window.PORTAL_URL !== 'undefined' 
    ? window.PORTAL_URL 
    : window.location.origin;

/**
 * Classe para gerenciar verificação periódica de novos processos na caixa de entrada
 */
class PeriodicUpdater {
    constructor(tramitacaoApp) {
        this.app = tramitacaoApp;
        this.intervalId = null;
        
        // ✅ Configurações de intervalo
        this.checkIntervalActive = 60000;      // 60s quando tab ativa
        this.checkIntervalInactive = 300000;    // 5 minutos quando tab inativa
        this.currentInterval = this.checkIntervalActive;
        
        this.lastContadorEntrada = null;   // Último contador de entrada conhecido
        
        // ✅ Notificação
        this.notificationShown = false;    // Flag para evitar notificações duplicadas
        this.pendingNotification = null;   // Notificação pendente quando tab estava inativa
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // ✅ Page Visibility API - ajusta intervalo baseado na visibilidade
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                // Tab inativa: aumenta intervalo
                this.setCheckInterval(this.checkIntervalInactive);
            } else {
                // Tab ativa: diminui intervalo
                this.setCheckInterval(this.checkIntervalActive);
                
                // Se havia notificação pendente, mostra agora
                if (this.pendingNotification) {
                    this.app.mostrarNotificacaoAtualizacao(this.pendingNotification.novosEntrada);
                    this.notificationShown = true;
                    this.pendingNotification = null;
                    
                    // Permite nova notificação após 5 minutos
                    setTimeout(() => {
                        this.notificationShown = false;
                    }, 300000);
                }
                
                // Se não estava rodando, inicia
                if (!this.intervalId) {
                    this.start();
                }
            }
        });
    }
    
    // ✅ Define intervalo baseado na visibilidade da tab
    setCheckInterval(interval) {
        // Limpa verificação anterior se existir
        if (this.intervalId) {
            clearTimeout(this.intervalId);
            this.intervalId = null;
        }
        
        this.currentInterval = interval;
        
        // Agenda próxima verificação com o intervalo atual
        this.scheduleNextCheck();
    }
    
    // ✅ Agenda próxima verificação
    scheduleNextCheck() {
        // Limpa verificação anterior se existir
        if (this.intervalId) {
            clearTimeout(this.intervalId);
            this.intervalId = null;
        }
        
        // Agenda próxima verificação com intervalo atual
        this.intervalId = setTimeout(() => {
            this.checkForUpdates();
        }, this.currentInterval);
    }
    
    start() {
        this.lastContadorEntrada = null; // Reseta para primeira verificação
        
        // Define intervalo inicial baseado na visibilidade atual
        const initialInterval = document.hidden 
            ? this.checkIntervalInactive 
            : this.checkIntervalActive;
        
        this.setCheckInterval(initialInterval);
        
        // Inicia verificação imediatamente (primeira vez)
        this.checkForUpdates();
    }
    
    // ✅ Verifica mudanças na caixa de entrada (não atualiza automaticamente)
    async checkForUpdates() {
        try {
            // ✅ Apenas verifica contador de entrada (requisição leve)
            // Funciona mesmo com tab inativa (apenas com intervalo maior)
            const novoContadorEntrada = await this.fetchContadorEntrada();
            
            if (novoContadorEntrada === null) {
                console.warn('[PeriodicUpdater] Erro ao buscar contador, agendando próxima verificação');
                // Erro na requisição, agenda próxima verificação
                this.scheduleNextCheck();
                return;
            }
            
            
            // ✅ Compara com contador anterior
            if (this.lastContadorEntrada !== null) {
                const mudou = this.compararContadorEntrada(this.lastContadorEntrada, novoContadorEntrada);
                
                if (mudou) {
                    // ✅ Detectou novos processos na caixa de entrada
                    const novosProcessos = novoContadorEntrada - this.lastContadorEntrada;
                    this.mostrarNotificacaoNovosProcessos(novosProcessos);
                    this.lastContadorEntrada = novoContadorEntrada;
                } else {
                }
            } else {
                // Primeira verificação, apenas armazena
                this.lastContadorEntrada = novoContadorEntrada;
            }
            
            // Agenda próxima verificação (com intervalo atual baseado na visibilidade)
            this.scheduleNextCheck();
            
        } catch (error) {
            console.error('[PeriodicUpdater] Erro ao verificar contador de entrada:', error);
            // Em caso de erro, agenda próxima verificação com delay maior
            setTimeout(() => this.scheduleNextCheck(), this.currentInterval * 2);
        }
    }
    
    // ✅ Busca apenas contador de entrada (caixa de entrada)
    // IMPORTANTE: Busca contador GERAL (todas as unidades), não específico de unidade
    // Isso permite detectar novos processos em qualquer unidade, mesmo que o usuário
    // esteja visualizando uma unidade específica
    async fetchContadorEntrada() {
        return new Promise((resolve) => {
            $.ajax({
                url: `${PORTAL_URL}/tramitacao_contadores_json`,
                data: { cod_usuario: COD_USUARIO_CORRENTE },
                // Não envia cod_unid_tramitacao - busca contador geral de todas as unidades
                dataType: 'json',
                success: (response) => {
                    // Retorna apenas o contador de entrada (geral)
                    const entrada = response.entrada || 0;
                    resolve(entrada);
                },
                error: (xhr, status, error) => {
                    console.error('[PeriodicUpdater] Erro ao buscar contador:', status, error);
                    resolve(null);
                }
            });
        });
    }
    
    // ✅ Compara contador de entrada
    compararContadorEntrada(antigo, novo) {
        // Retorna true apenas se entrada aumentou (novos processos)
        return novo !== null && antigo !== null && novo > antigo;
    }
    
    // ✅ Mostra notificação de novos processos
    mostrarNotificacaoNovosProcessos(novosEntrada) {
        // Evita notificações duplicadas
        if (this.notificationShown) return;
        
        if (novosEntrada > 0) {
            // Mostra notificação (será exibida quando tab voltar a ficar ativa se estiver inativa)
            // Se tab estiver ativa, mostra imediatamente
            if (!document.hidden) {
                this.app.mostrarNotificacaoAtualizacao(novosEntrada);
                this.notificationShown = true;
                
                // Permite nova notificação após 5 minutos
                setTimeout(() => {
                    this.notificationShown = false;
                }, 300000);
            } else {
                // Tab está inativa: marca para mostrar quando voltar a ficar ativa
                this.pendingNotification = {
                    novosEntrada: novosEntrada
                };
            }
        }
    }
    
    stop() {
        if (this.intervalId) {
            clearTimeout(this.intervalId);
            this.intervalId = null;
        }
    }
}

/**
 * Classe principal para gerenciar a interface de tramitação
 */
class TramitacaoEmailStyle {
    // Performance: Limite máximo de resultados quando há filtros
    static MAX_RESULTADOS_COM_FILTROS = 2000;
    
    // Chave para localStorage
    static STORAGE_KEY = 'tramitacao_email_style_state';
    static FILTROS_SALVOS_KEY = 'tramitacao_email_style_filtros_salvos';
    
    constructor() {
        // Estado da aplicação
        this.filtroAtual = 'entrada'; // entrada, rascunhos, enviados
        this.filtroTipo = 'TODOS'; // TODOS, MATERIA, DOCUMENTO
        this.unidadeSelecionada = null;
        this.processosSelecionados = new Set();
        this.todosSelecionados = false;
        this.processos = [];
        this.paginaAtual = 1;
        this.itensPorPagina = 10;
        this.totalItens = 0;
        this.totalFiltrado = 0; // Total de resultados após aplicar filtros
        this.processosFiltrados = []; // Cache dos processos filtrados (para paginação)
        this.ordenacaoData = 'desc'; // 'asc' ou 'desc' - ordenação por data de tramitação
        
        // Cache de unidades do usuário
        this.unidadesUsuario = [];
        this.carregandoUnidades = false;
        this.preenchendoDropdownUnidades = false; // Flag para evitar preenchimento duplicado do dropdown
        
        // Flag para evitar loops de eventos
        this.ignorarChangeUnidade = false;
        
        // Busca rápida
        this.termoBusca = '';
        
        // Virtual scrolling (para listas grandes)
        this.itemsPorPaginaVirtual = 100; // Quantos items renderizar por vez no virtual scrolling
        this.itemsRenderizadosVirtual = 0; // Quantos items foram renderizados
        this.observerVirtualScrolling = null; // Intersection Observer para virtual scrolling
        
        // Cache de filtros (memoização)
        this.cacheFiltros = new Map();
        this.ultimaChaveFiltro = null;
        this.processosCompletos = []; // Armazena TODOS os processos para extrair status disponíveis
        
        // ✅ Verificação periódica de novos processos
        this.periodicUpdater = new PeriodicUpdater(this);
        
        // Inicialização
        this.inicializar();
    }
    
    /**
     * Inicializa a aplicação
     */
    inicializar() {
        
        // Configura event listeners primeiro
        this.configurarEventListeners();
        
        // Carrega unidades do usuário
        this.carregarUnidadesUsuario();
        
        // Carrega filtros salvos
        this.carregarFiltrosSalvos();
        
        // Verifica se há unidade na URL ou estado (isso carregará contadores se necessário)
        this.verificarEstadoInicial();
        
        // Carrega contadores iniciais (apenas se não foi carregado pelo verificarEstadoInicial)
        // Isso garante que sempre temos contadores, mesmo se não houver estado salvo
        if (!this.unidadeSelecionada) {
            this.carregarContadores();
        }
        
        // ✅ Inicia verificação periódica de novos processos na caixa de entrada
        this.periodicUpdater.start();
    }
    
    /**
     * Configura todos os event listeners
     */
    configurarEventListeners() {
        const self = this;
        
        // Navegação de caixas (sidebar)
        $(document).on('click', '.contador-item[data-filtro]', function(e) {
            e.preventDefault();
            const filtro = $(this).data('filtro');
            self.alterarFiltro(filtro);
        });
        
        // Seleção de unidade (hidden select - mantido para compatibilidade)
        $('#lst_cod_unid_tram_local').on('change', function() {
            if (!self.ignorarChangeUnidade) {
                const codUnidade = $(this).val();
                self.selecionarUnidadeEAbrirCaixa(codUnidade || null, 'entrada');
            }
        });
        
        // Busca rápida
        let buscaTimeout;
        $('#busca-rapida').on('input', function() {
            const termo = $(this).val();
            clearTimeout(buscaTimeout);
            buscaTimeout = setTimeout(function() {
                self.filtrarPorBusca(termo);
            }, 300);
        });
        
        // Botão "Filtros Avançados"
        $('#btn-toggle-filtros-rapido').on('click', function(e) {
            e.preventDefault();
            self.toggleFiltrosAvancados();
        });
        
        // Seleção de unidade no breadcrumb dropdown
        $(document).on('click', '#breadcrumb-unidade-dropdown .dropdown-item', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const codUnidade = $(this).data('cod-unidade');
            self.selecionarUnidadeEAbrirCaixa(codUnidade || null, 'entrada');
        });
        
        // Clique no breadcrumb de caixa
        $(document).on('click', '#breadcrumb-caixa', function(e) {
            e.preventDefault();
            if (self.filtroAtual !== 'entrada') {
                self.alterarFiltro('entrada');
            }
        });
        
        // Clique em card de unidade
        $(document).on('click', '.unidade-card', function() {
            const codUnidade = $(this).data('cod-unidade');
            if (codUnidade) {
                self.selecionarUnidadeEAbrirCaixa(codUnidade, 'entrada');
            }
        });
        
        // Seleção de processos (apenas na caixa de entrada)
        $(document).on('change', '#selecionar-todos', function() {
            if (self.filtroAtual !== 'entrada') {
                $(this).prop('checked', false);
                return;
            }
            self.todosSelecionados = $(this).prop('checked');
            
            // Obtém os processos filtrados (resultados visíveis)
            const processosFiltrados = self.obterProcessosFiltrados();
            
            // Limpa seleções anteriores dos processos filtrados
            processosFiltrados.forEach(p => {
                self.processosSelecionados.delete(p.cod_entidade);
            });
            
            // Seleciona ou desseleciona todos os processos filtrados
            if (self.todosSelecionados) {
                processosFiltrados.forEach(p => {
                    self.processosSelecionados.add(p.cod_entidade);
                });
            }
            
            self.atualizarContadorSelecionados();
            self.renderizarLista();
        });
        
        $(document).on('change', '.checkbox-processo', function() {
            if (self.filtroAtual !== 'entrada') {
                $(this).prop('checked', false);
                return;
            }
            const codEntidade = $(this).data('cod-entidade');
            const $card = $(this).closest('.processo-card');
            
            if ($(this).prop('checked')) {
                self.processosSelecionados.add(codEntidade);
                $card.addClass('selecionado');
            } else {
                self.processosSelecionados.delete(codEntidade);
                $card.removeClass('selecionado');
                self.todosSelecionados = false;
                $('#selecionar-todos').prop('checked', false);
            }
            self.atualizarContadorSelecionados();
        });
        
        // Botão "Tramitar Selecionados"
        $(document).on('click', '#btn-tramitar-lote', function() {
            if (self.processosSelecionados.size > 0) {
                self.abrirModalTramitacaoLote();
            }
        });
        
        // Botão "Editar Rascunho"
        $(document).on('click', '.btn-editar-rascunho', function(e) {
            e.preventDefault();
            const codTramitacao = $(this).data('cod-tramitacao');
            const tipo = $(this).data('tipo');
            
            if (!codTramitacao || !tipo) {
                console.error('Erro ao editar rascunho: dados incompletos', { codTramitacao, tipo });
                self.mostrarToast('Erro', 'Não foi possível editar o rascunho. Dados incompletos.', 'error');
                return;
            }
            
            // Garante que sidebarManager está inicializado
            if (!self.sidebarManager) {
                console.warn('sidebarManager não está inicializado. Tentando inicializar...');
                // Tenta inicializar se ainda não foi feito
                if (typeof TramitacaoSidebarManager !== 'undefined' && self) {
                    try {
                        self.sidebarManager = new TramitacaoSidebarManager(self);
                        console.log('sidebarManager inicializado com sucesso');
                    } catch (err) {
                        console.error('Erro ao inicializar sidebarManager:', err);
                        self.mostrarToast('Erro', 'Não foi possível inicializar o formulário. Tente recarregar a página.', 'error');
                        return;
                    }
                } else {
                    console.error('Erro: TramitacaoSidebarManager ou tramitacaoApp não está disponível', { 
                        TramitacaoSidebarManager: typeof TramitacaoSidebarManager,
                        self: self 
                    });
                    self.mostrarToast('Erro', 'Aplicação não está inicializada. Recarregue a página.', 'error');
                    return;
                }
            }
            
            // Chama abrirEdicao
            if (self.sidebarManager && typeof self.sidebarManager.abrirEdicao === 'function') {
                try {
                    self.sidebarManager.abrirEdicao(codTramitacao, tipo);
                } catch (err) {
                    console.error('Erro ao chamar abrirEdicao:', err);
                    self.mostrarToast('Erro', 'Não foi possível abrir o formulário de edição: ' + err.message, 'error');
                }
            } else {
                console.error('Erro: sidebarManager.abrirEdicao não está disponível', { 
                    sidebarManager: self.sidebarManager,
                    temAbrirEdicao: self.sidebarManager && typeof self.sidebarManager.abrirEdicao
                });
                self.mostrarToast('Erro', 'Não foi possível abrir o formulário de edição. Tente recarregar a página.', 'error');
            }
        });
        
        // Botão "Ver Detalhes"
        $(document).on('click', '.btn-ver-detalhes-tramitacao', function(e) {
            e.preventDefault();
            const codTramitacao = $(this).data('cod-tramitacao');
            const tipo = $(this).data('tipo');
            
            if (!codTramitacao || !tipo) {
                console.error('Erro ao ver detalhes: dados incompletos', { codTramitacao, tipo });
                self.mostrarToast('Erro', 'Não foi possível visualizar detalhes. Dados incompletos.', 'error');
                return;
            }
            
            // Chama a função para ver detalhes
            self.verDetalhesTramitacao(codTramitacao, tipo);
        });
        
        // Ordenação por data
        $(document).on('click', '#btn-ordenar-data', function(e) {
            e.preventDefault();
            self.alterarOrdenacaoData();
        });
        
        // Paginação
        $(document).on('click', '.paginacao-btn', function(e) {
            e.preventDefault();
            const acao = $(this).data('acao');
            self.alterarPagina(acao);
        });
        
        $(document).on('change', '#itens-por-pagina', function() {
            self.itensPorPagina = parseInt($(this).val());
            self.paginaAtual = 1;
            self.carregarTramitacoes();
        });
        
        // Filtros avançados
        $(document).on('change', '#filtro-tipo-processo', function() {
            self.filtroTipo = $(this).val();
            self.aplicarFiltros();
        });
        
        // Aplicar filtros ao mudar campos
        $(document).on('change input', '#filtro-tipo-documento, #filtro-numero, #filtro-ano, #filtro-interessado, #filtro-status, #filtro-data-inicial, #filtro-data-final', function() {
            self.aplicarFiltros();
        });
        
        // Limpar filtros
        $(document).on('click', '#btn-limpar-filtros', function() {
            self.limparCamposFiltros();
            self.aplicarFiltros();
        });
        
        // Salvar filtros
        $(document).on('click', '#btn-salvar-filtros', function() {
            self.salvarFiltroAtual();
        });
        
        // Carregar filtro salvo
        $(document).on('click', '.filtro-salvo-item', function(e) {
            e.preventDefault();
            e.stopPropagation();
            // Se o clique foi no botão de remover, não processa
            if ($(e.target).closest('.remover-filtro-salvo').length > 0) {
                return;
            }
            const id = $(this).data('filtro-id');
            if (id) {
                self.carregarFiltroSalvo(id);
            }
        });
        
        // Remover filtro salvo
        $(document).on('click', '.remover-filtro-salvo', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const id = $(this).data('filtro-id');
            self.removerFiltroSalvo(id);
        });
        
        // Recalcula alturas dos cards quando a janela é redimensionada (usando throttle)
        $(window).on('resize', self.throttle(function() {
            self.igualarAlturasCards();
        }, 250));
        
        // Chips removíveis de filtros
        $(document).on('click', '.filtro-chip', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const tipoFiltro = $(this).data('filtro-tipo');
            self.removerFiltroPorTipo(tipoFiltro);
        });
        
        $(document).on('keydown', '.filtro-chip', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();
                const tipoFiltro = $(this).data('filtro-tipo');
                self.removerFiltroPorTipo(tipoFiltro);
            }
        });
    }
    
    /**
     * Verifica estado inicial (URL, localStorage, etc)
     */
    verificarEstadoInicial() {
        // Verifica se há unidade na URL (prioridade sobre localStorage)
        const urlParams = new URLSearchParams(window.location.search);
        const unidadeUrl = urlParams.get('unidade');
        if (unidadeUrl) {
            this.selecionarUnidadeEAbrirCaixa(unidadeUrl, 'entrada');
            return;
        }
        
        // Tenta restaurar estado do localStorage
        this.restaurarEstado();
    }
    
    /**
     * Salva estado atual no localStorage
     */
    salvarEstado() {
        try {
            const estado = {
                filtroAtual: this.filtroAtual,
                filtroTipo: this.filtroTipo,
                unidadeSelecionada: this.unidadeSelecionada,
                termoBusca: this.termoBusca,
                filtroTipoDoc: $('#filtro-tipo-documento').val() || '',
                filtroNumero: $('#filtro-numero').val() || '',
                filtroAno: $('#filtro-ano').val() || '',
                filtroInteressado: $('#filtro-interessado').val() || '',
                filtroStatus: $('#filtro-status').val() || '',
                filtroDataInicial: $('#filtro-data-inicial').val() || '',
                filtroDataFinal: $('#filtro-data-final').val() || '',
                itensPorPagina: this.itensPorPagina,
                ordenacaoData: this.ordenacaoData
            };
            localStorage.setItem(TramitacaoEmailStyle.STORAGE_KEY, JSON.stringify(estado));
        } catch (e) {
            console.warn('Erro ao salvar estado no localStorage:', e);
        }
    }
    
    /**
     * Restaura estado do localStorage
     */
    restaurarEstado() {
        try {
            const estadoSalvo = localStorage.getItem(TramitacaoEmailStyle.STORAGE_KEY);
            if (!estadoSalvo) {
                // Se não há estado salvo, limpa tudo
                this.limparCamposFiltros();
                this.termoBusca = '';
                $('#busca-rapida').val('');
                this.paginaAtual = 1;
                // Atualiza ícone de ordenação com valor padrão
                this.atualizarIconeOrdenacao();
                return;
            }
            
            const estado = JSON.parse(estadoSalvo);
            
            // Restaura valores
            if (estado.filtroAtual) {
                this.filtroAtual = estado.filtroAtual;
            }
            if (estado.filtroTipo) {
                this.filtroTipo = estado.filtroTipo;
                $('#filtro-tipo-processo').val(estado.filtroTipo);
            }
            if (estado.unidadeSelecionada) {
                this.unidadeSelecionada = estado.unidadeSelecionada;
            }
            if (estado.termoBusca) {
                this.termoBusca = estado.termoBusca;
                $('#busca-rapida').val(estado.termoBusca);
            }
            if (estado.filtroTipoDoc) {
                $('#filtro-tipo-documento').val(estado.filtroTipoDoc);
            }
            if (estado.filtroNumero) {
                $('#filtro-numero').val(estado.filtroNumero);
            }
            if (estado.filtroAno) {
                $('#filtro-ano').val(estado.filtroAno);
            }
            if (estado.filtroInteressado) {
                $('#filtro-interessado').val(estado.filtroInteressado);
            }
            if (estado.filtroStatus) {
                $('#filtro-status').val(estado.filtroStatus);
            }
            if (estado.filtroDataInicial) {
                $('#filtro-data-inicial').val(estado.filtroDataInicial);
            }
            if (estado.filtroDataFinal) {
                $('#filtro-data-final').val(estado.filtroDataFinal);
            }
            if (estado.itensPorPagina) {
                this.itensPorPagina = estado.itensPorPagina;
                $('#itens-por-pagina').val(estado.itensPorPagina);
            }
            if (estado.ordenacaoData) {
                this.ordenacaoData = estado.ordenacaoData;
            }
            
            // Atualiza ícone de ordenação
            this.atualizarIconeOrdenacao();
            
            // Atualiza sidebar
            $('.contador-item').removeClass('ativo');
            $(`.contador-item[data-filtro="${this.filtroAtual}"]`).addClass('ativo');
            
            // Se há unidade selecionada, mostra elementos da interface e carrega dados
            if (this.unidadeSelecionada && this.filtroAtual === 'entrada') {
                // Atualiza select hidden (para compatibilidade)
                this.ignorarChangeUnidade = true;
                $('#lst_cod_unid_tram_local').val(this.unidadeSelecionada);
                setTimeout(() => {
                    this.ignorarChangeUnidade = false;
                }, 100);
                
                // Mostra elementos da interface
                $('#breadcrumb-contexto').show();
                $('#search-bar-rapida').show();
                
                // Carrega contadores com a unidade selecionada e depois os processos
                this.carregarContadores().then(() => {
                    this.carregarTramitacoes();
                });
            } else if (this.filtroAtual === 'rascunhos' || this.filtroAtual === 'enviados') {
                // Para rascunhos e enviados, mostra elementos da interface
                $('#breadcrumb-contexto').show();
                $('#search-bar-rapida').show();
                // Carrega contadores (sem unidade) e processos
                this.carregarContadores().then(() => {
                    this.carregarTramitacoes();
                });
            }
        } catch (e) {
            console.warn('Erro ao restaurar estado do localStorage:', e);
            // Em caso de erro, limpa tudo
            this.limparCamposFiltros();
        }
    }
    
    /**
     * Carrega unidades do usuário
     */
    async carregarUnidadesUsuario() {
        // Evita carregar múltiplas vezes simultaneamente
        if (this.carregandoUnidades) {
            return new Promise((resolve) => {
                const checkInterval = setInterval(() => {
                    if (!this.carregandoUnidades) {
                        clearInterval(checkInterval);
                        resolve(this.unidadesUsuario);
                    }
                }, 100);
                setTimeout(() => {
                    clearInterval(checkInterval);
                    resolve(this.unidadesUsuario);
                }, 5000);
            });
        }
        
        // Se já tem unidades carregadas, retorna imediatamente
        if (this.unidadesUsuario.length > 0) {
            this.renderizarUnidadesUsuario(this.unidadesUsuario);
            return Promise.resolve(this.unidadesUsuario);
        }
        
        const codUsuario = COD_USUARIO_CORRENTE;
        
        if (!codUsuario || codUsuario === 0 || codUsuario === '0' || codUsuario === 'None') {
            console.warn('cod_usuario não disponível para carregar unidades');
            this.mostrarMensagemUnidades();
            return Promise.resolve([]);
        }
        
        this.carregandoUnidades = true;
        
        try {
            const url = `${PORTAL_URL}/tramitacao_unidades_usuario_json?cod_usuario=${codUsuario}`;
            
            
            const xhr = $.ajax({
                url: url,
                dataType: 'json'
            });
            
            const unidades = await xhr;
            
            
            if (!unidades || unidades.length === 0) {
                console.warn('Nenhuma unidade encontrada para o usuário');
                this.mostrarMensagemUnidades();
                this.carregandoUnidades = false;
                return Promise.resolve([]);
            }
            
            this.unidadesUsuario = unidades;
            this.renderizarUnidadesUsuario(unidades);
            this.carregandoUnidades = false;
            return Promise.resolve(unidades);
        } catch (error) {
            console.error('Erro ao carregar unidades do usuário:', error);
            this.mostrarMensagemUnidades();
            this.carregandoUnidades = false;
            return Promise.resolve([]);
        }
    }
    
    /**
     * Renderiza cards de unidades
     */
    renderizarUnidadesUsuario(unidades) {
        const container = $('.processos-container');
        
        if (!unidades || unidades.length === 0) {
            this.mostrarMensagemUnidades();
            return;
        }
        
        // Garante que o container use grid quando há unidades (mesmo comportamento dos cards de processos)
        container.css({
            'display': 'grid',
            'grid-template-columns': 'repeat(auto-fill, minmax(320px, 1fr))',
            'grid-auto-rows': '1fr',
            'gap': '1.5rem',
            'align-content': 'start',
            'align-items': 'stretch',
            'padding': '1.5rem',
            'justify-content': 'unset',
            'min-height': 'auto',
            'flex-direction': 'unset'
        });
        
        // Remove classes que podem interferir
        container.removeClass('unidades-grid');
        
        const html = unidades.map(unidade => {
            const codUnidade = unidade.id || unidade.cod_unid_tramitacao;
            const nomeUnidade = unidade.name || unidade.nom_unidade || 'Unidade';
            const contador = unidade.entrada || 0;
            
            return `
                <div class="card unidade-card" data-cod-unidade="${codUnidade}" style="display: flex; flex-direction: column; height: 100%;">
                    <div class="card-body" style="display: flex; flex-direction: column; flex: 1;">
                        <div class="d-flex align-items-start justify-content-between gap-3" style="flex: 1;">
                            <div class="flex-grow-1 d-flex flex-column">
                                <h5 class="card-title">
                                    <i class="mdi mdi-office-building-outline me-2"></i>
                                    <span>${this.escapeHtml(nomeUnidade)}</span>
                                </h5>
                                <p class="text-muted mb-0 small mt-2 mt-auto">Clique para ver processos</p>
                            </div>
                            <div class="text-end flex-shrink-0">
                                <span class="badge bg-primary">${contador}</span>
                                <p class="text-muted mb-0 small mt-1">processos</p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        container.html(html);
    }
    
    /**
     * Mostra mensagem quando não há unidades
     */
    mostrarMensagemUnidades() {
        const container = $('.processos-container');
        container.removeClass('unidades-grid');
        container.html(`
            <div class="empty-state">
                <i class="mdi mdi-office-building-outline"></i>
                <h3>Você não está vinculado a nenhuma unidade</h3>
                <p>Entre em contato com o administrador do sistema para ser vinculado a uma unidade de tramitação.</p>
            </div>
        `);
    }
    
    /**
     * Seleciona unidade e abre caixa
     */
    selecionarUnidadeEAbrirCaixa(unidade, filtro) {
        
        // Normaliza unidade (null se vazio)
        const unidadeNormalizada = (unidade && unidade !== '' && unidade !== '0') ? unidade : null;
        
        // Limpa filtros e seleções
        this.limparCamposFiltros();
        this.limparProcessosCompletos(); // Limpa processos completos para recarregar status
        this.termoBusca = '';
        $('#busca-rapida').val('');
        this.processosSelecionados.clear();
        this.todosSelecionados = false;
        $('#selecionar-todos').prop('checked', false);
        this.paginaAtual = 1;
        
        // Se unidade é null e filtro é entrada, mostra cards de unidades
        if (!unidadeNormalizada && filtro === 'entrada') {
            this.unidadeSelecionada = null;
            this.filtroAtual = filtro;
            
            // Salva estado no localStorage (unidade null também é salva)
            this.salvarEstado();
            
            $('#breadcrumb-contexto').hide();
            $('#search-bar-rapida').hide();
            $('#controles-lista').hide();
            $('#secao-filtros').hide();
            this.carregarContadores().then(() => {
                this.carregarUnidadesUsuario();
            });
            return;
        }
        
        // Atualiza estado
        this.unidadeSelecionada = unidadeNormalizada;
        this.filtroAtual = filtro;
        
        // Salva estado no localStorage (sempre salva a última unidade selecionada)
        this.salvarEstado();
        
        // Atualiza select hidden (para compatibilidade)
        this.ignorarChangeUnidade = true;
        $('#lst_cod_unid_tram_local').val(unidadeNormalizada || '');
        setTimeout(() => {
            this.ignorarChangeUnidade = false;
        }, 100);
        
        // Mostra elementos da interface
        $('#breadcrumb-contexto').show();
        $('#search-bar-rapida').show();
        
        // Atualiza breadcrumb
        this.atualizarBreadcrumb();
        
        // Carrega contadores e tramitações
        this.carregarContadores().then(() => {
            this.carregarTramitacoes();
        });
    }
    
    /**
     * Altera filtro (caixa)
     */
    alterarFiltro(filtro) {
        // Limpa filtros e seleções
        this.limparCamposFiltros();
        this.limparProcessosCompletos(); // Limpa processos completos para recarregar status
        this.termoBusca = '';
        $('#busca-rapida').val('');
        this.processosSelecionados.clear();
        this.todosSelecionados = false;
        $('#selecionar-todos').prop('checked', false);
        this.paginaAtual = 1;
        
        this.filtroAtual = filtro;
        
        // Atualiza sidebar
        $('.contador-item').removeClass('ativo');
        $(`.contador-item[data-filtro="${filtro}"]`).addClass('ativo');
        
        // Atualiza breadcrumb
        this.atualizarBreadcrumb();
        
        // Salva estado no localStorage
        this.salvarEstado();
        
        // Carrega dados
        this.carregarContadores();
        this.carregarTramitacoes();
    }
    
    /**
     * Carrega contadores
     */
    async carregarContadores() {
        const codUsuario = COD_USUARIO_CORRENTE;
        if (!codUsuario || codUsuario === 0) {
            return Promise.resolve();
        }
        
        try {
            let url = `${PORTAL_URL}/tramitacao_contadores_json?cod_usuario=${codUsuario}`;
            if (this.unidadeSelecionada) {
                url += `&cod_unid_tramitacao=${this.unidadeSelecionada}`;
            }
            // ✅ ADICIONADO: Força atualização do cache para garantir contadores corretos
            // Isso é necessário porque o cache pode estar desatualizado após mudanças nos filtros
            // Usa timestamp para garantir que não use cache do navegador
            url += `&forcar_atualizacao=true&_t=${Date.now()}`;
            
            
            const xhr = $.ajax({
                url: url,
                dataType: 'json'
            });
            
            const dados = await xhr;
            
            
            if (dados.erro) {
                console.error('Erro ao carregar contadores:', dados.erro);
                return;
            }
            
            // Atualiza contadores na sidebar
            const entrada = dados.entrada || 0;
            const rascunhos = dados.rascunhos || 0;
            const enviados = dados.enviados || 0;
            
            
            $('#contador-entrada .contador-valor').text(entrada);
            $('#contador-rascunhos .contador-valor').text(rascunhos);
            $('#contador-enviados .contador-valor').text(enviados);
            
            // Atualiza breadcrumb (que também atualiza o contador do breadcrumb)
            this.atualizarBreadcrumb();
            
            // Se está na caixa de entrada e não tem unidade selecionada, busca contadores por unidade
            if (this.filtroAtual === 'entrada' && !this.unidadeSelecionada) {
                this.buscarContadoresUnidades();
            }
        } catch (error) {
            console.error('Erro ao carregar contadores:', error);
        }
    }
    
    /**
     * ✅ FUNÇÃO CRIADA: Atualiza TODOS os contadores de forma sincronizada
     * 
     * Esta função garante que todos os contadores sejam atualizados ao mesmo tempo:
     * - Sidebar (entrada, rascunhos, enviados)
     * - Breadcrumb (contador de processos)
     * - Paginação (total de itens)
     * - Lista de processos (se necessário)
     * 
     * @param {boolean} recarregarLista - Se true, também recarrega a lista de processos
     */
    async atualizarContadores(recarregarLista = false) {
        try {
            // 1. Primeiro atualiza contadores (sidebar e breadcrumb)
            await this.carregarContadores();
            
            // 2. Se solicitado, recarrega lista de processos (atualiza paginação)
            if (recarregarLista) {
                await this.carregarTramitacoes();
            }
            
            console.log('[atualizarContadores] Todos os contadores foram atualizados com sucesso');
        } catch (error) {
            console.error('[atualizarContadores] Erro ao atualizar contadores:', error);
        }
    }
    
    /**
     * Busca contadores por unidade (para exibir nos cards)
     */
    async buscarContadoresUnidades() {
        if (!this.unidadesUsuario || this.unidadesUsuario.length === 0) {
            await this.carregarUnidadesUsuario();
        }
        
        if (!this.unidadesUsuario || this.unidadesUsuario.length === 0) {
            console.warn('Nenhuma unidade disponível para buscar contadores');
            return;
        }
        
        const codUsuario = COD_USUARIO_CORRENTE;
        if (!codUsuario || codUsuario === 0) {
            return;
        }
        
        // Mostra loading (centralizado)
        const container = $('.processos-container');
        // Remove todas as classes que podem interferir
        container.removeClass('unidades-grid');
        // Aplica estilos inline para garantir centralização
        container.attr('style', 'display: flex !important; flex-direction: column !important; justify-content: center !important; align-items: center !important; min-height: 300px !important; grid-template-columns: none !important; gap: 0 !important; padding: 1rem !important;');
        container.html(`
            <div class="d-flex flex-column align-items-center justify-content-center">
                <span class="spinner-border spinner-border-sm mb-3" role="status" aria-hidden="true" style="width: 3rem; height: 3rem;"></span>
                <p class="text-muted mb-0 text-center fs-6">Carregando unidades...</p>
            </div>
        `);
        
        try {
            // Busca contador para cada unidade
            const promessas = this.unidadesUsuario.map(async (unidade) => {
                const codUnidade = unidade.id || unidade.cod_unid_tramitacao;
                const url = `/tramitacao_contadores_json?cod_usuario=${codUsuario}&cod_unid_tramitacao=${codUnidade}`;
                
                try {
                    const url = `${PORTAL_URL}/tramitacao_contadores_json?cod_usuario=${codUsuario}&cod_unid_tramitacao=${codUnidade}`;
                    
                    
                    const xhr = $.ajax({
                        url: url,
                        dataType: 'json'
                    });
                    
                    const dados = await xhr;
                    
                    
                    return {
                        ...unidade,
                        entrada: dados.entrada || 0,
                        entradaRaw: dados
                    };
                } catch (error) {
                    console.error(`Erro ao buscar contador para unidade ${codUnidade}:`, error);
                    return {
                        ...unidade,
                        entrada: 0,
                        entradaRaw: {}
                    };
                }
            });
            
            const unidadesComContadores = await Promise.all(promessas);
            
            // Calcula soma total
            const somaTotal = unidadesComContadores.reduce((acc, u) => acc + (u.entrada || 0), 0);
            
            // Renderiza cards
            this.renderizarUnidadesUsuario(unidadesComContadores);
        } catch (error) {
            console.error('Erro ao buscar contadores por unidade:', error);
            this.mostrarMensagemUnidades();
        }
    }
    
    /**
     * Carrega tramitações
     */
    async carregarTramitacoes() {
        // Validações
        if (this.filtroAtual === 'entrada' && !this.unidadeSelecionada) {
            // Mostra cards de unidades
            this.carregarUnidadesUsuario();
            return;
        }
        
        const codUsuario = COD_USUARIO_CORRENTE;
        if (!codUsuario || codUsuario === 0) {
            this.mostrarEstadoVazio('erro');
            return;
        }
        
        // Mostra loading (centralizado)
        const container = $('.processos-container');
        // Remove todas as classes que podem interferir
        container.removeClass('unidades-grid');
        // Aplica estilos inline para garantir centralização
        container.attr('style', 'display: flex !important; flex-direction: column !important; justify-content: center !important; align-items: center !important; min-height: 300px !important; grid-template-columns: none !important; gap: 0 !important; padding: 1rem !important;');
        container.html(`
            <div class="d-flex flex-column align-items-center justify-content-center">
                <span class="spinner-border spinner-border-sm mb-3" role="status" style="width: 3rem; height: 3rem;"></span>
                <p class="text-muted mb-0 text-center fs-6">Carregando processos...</p>
            </div>
        `);
        
        try {
            // Verifica se há filtros ativos - se houver, carrega todos os resultados sem paginação
            const temFiltros = this.temFiltrosAtivos() || (this.termoBusca && this.termoBusca.trim() !== '');
            
            // Monta URL
            let url = '';
            const params = new URLSearchParams();
            params.append('cod_usuario', codUsuario);
            
            // Envia parâmetro de ordenação para o backend
            params.append('ordenacao', this.ordenacaoData || 'asc');
            
            // Quando há filtros, desabilita paginação no backend para aplicar filtros em todos os resultados
            // Quando não há filtros, aplica paginação normalmente
            if (!temFiltros) {
                // Aplica paginação no backend (mais eficiente)
                params.append('limit', this.itensPorPagina.toString());
                params.append('offset', ((this.paginaAtual - 1) * this.itensPorPagina).toString());
            }
            
            if (this.filtroTipo !== 'TODOS') {
                params.append('tipo', this.filtroTipo);
            }
            
            // Envia parâmetros de busca e filtros avançados ao backend
            // IMPORTANTE: Filtros devem ser processados no backend para aplicar em todos os resultados
            if (this.termoBusca && this.termoBusca.trim() !== '') {
                params.append('busca', this.termoBusca.trim());
            }
            
            const filtroTipoDoc = $('#filtro-tipo-documento').val() || '';
            if (filtroTipoDoc.trim() !== '') {
                // Usa tipo_materia ou tipo_documento dependendo do filtro tipo
                if (this.filtroTipo === 'MATERIA' || !this.filtroTipo || this.filtroTipo === 'TODOS') {
                    params.append('tipo_materia', filtroTipoDoc.trim());
                }
                if (this.filtroTipo === 'DOCUMENTO' || !this.filtroTipo || this.filtroTipo === 'TODOS') {
                    params.append('tipo_documento', filtroTipoDoc.trim());
                }
            }
            
            const filtroNumero = $('#filtro-numero').val() || '';
            if (filtroNumero.trim() !== '') {
                params.append('numero', filtroNumero.trim());
            }
            
            const filtroAno = $('#filtro-ano').val() || '';
            if (filtroAno.trim() !== '') {
                params.append('ano', filtroAno.trim());
            }
            
            const filtroInteressado = $('#filtro-interessado').val() || '';
            if (filtroInteressado.trim() !== '') {
                params.append('interessado', filtroInteressado.trim());
            }
            
            const filtroStatus = $('#filtro-status').val() || '';
            if (filtroStatus.trim() !== '') {
                params.append('status', filtroStatus.trim());
            }
            
            const filtroDataInicial = $('#filtro-data-inicial').val() || '';
            if (filtroDataInicial) {
                params.append('data_inicial', filtroDataInicial);
            }
            
            const filtroDataFinal = $('#filtro-data-final').val() || '';
            if (filtroDataFinal) {
                params.append('data_final', filtroDataFinal);
            }
            
            if (this.filtroAtual === 'entrada') {
                url = `${PORTAL_URL}/tramitacao_caixa_entrada_unificada_json`;
                if (this.unidadeSelecionada) {
                    params.append('cod_unid_tramitacao', this.unidadeSelecionada);
                }
            } else if (this.filtroAtual === 'rascunhos') {
                url = `${PORTAL_URL}/tramitacao_rascunhos_json`;
            } else if (this.filtroAtual === 'enviados') {
                url = `${PORTAL_URL}/tramitacao_itens_enviados_json`;
            }
            
            
            url += '?' + params.toString();
            
            
            const xhr = $.ajax({
                url: url,
                dataType: 'json'
            });
            
            const dados = await xhr;
            
            
            if (dados.erro) {
                this.mostrarToast('Erro ao carregar processos: ' + dados.erro, 'error');
                this.mostrarEstadoVazio('erro');
                return;
            }
            
            this.processos = dados.tramitacoes || [];
            this.totalItens = dados.total || 0;
            
            // Atualiza nome da unidade no breadcrumb se fornecido pela API
            // (apenas para caixa de entrada quando há filtro por unidade)
            if (dados.mostrar_unidade_breadcrumb && dados.nome_unidade_filtro) {
                // Atualiza o nome da unidade no array de unidades se necessário
                if (this.unidadeSelecionada && dados.cod_unid_tramitacao_filtro) {
                    const unidadeIndex = this.unidadesUsuario.findIndex(u => u.id == dados.cod_unid_tramitacao_filtro);
                    if (unidadeIndex >= 0) {
                        // Atualiza nome da unidade no array
                        this.unidadesUsuario[unidadeIndex].name = dados.nome_unidade_filtro;
                        this.unidadesUsuario[unidadeIndex].nom_unidade = dados.nome_unidade_filtro;
                    }
                }
            }
            
            // Ordenação agora é feita no backend - não precisa ordenar aqui
            
            // Debug: verifica se autoria/interessado estão nos dados
            if (this.processos.length > 0) {
            }
            
            // Carrega status disponíveis após carregar processos
            setTimeout(() => { this.carregarStatusDisponiveis(); }, 100);
            
            // Se há filtros, os resultados já vêm filtrados do backend
            // Se não há filtros, renderiza normalmente
            if (!temFiltros) {
                // Sem filtros: renderiza normalmente com paginação do backend
                this.atualizarControlesPagina();
                this.renderizarLista();
                // Atualiza breadcrumb para remover badges de filtros
                this.atualizarBreadcrumb();
            } else {
                // Com filtros: resultados já vêm filtrados do backend
                // Processos filtrados são todos os resultados retornados
                this.processosFiltrados = this.processos;
                this.totalFiltrado = this.totalItens;
                
                // Aplica paginação frontend nos resultados filtrados (já que não há paginação backend quando há filtros)
                this.paginaAtual = 1;
                this.renderizarListaFiltrada();
                this.atualizarControlesPagina();
                this.atualizarBreadcrumb();
            }
            
        } catch (error) {
            console.error('Erro ao carregar tramitações:', error);
            this.mostrarToast('Erro ao carregar processos', 'error');
            this.mostrarEstadoVazio('erro');
        }
    }
    
    /**
     * Renderiza lista de processos
     */
    renderizarLista() {
        const container = $('.processos-container');
        
        if (this.processos.length === 0) {
            this.mostrarEstadoVazio('sem-processos');
            $('#container-selecao').hide();
            this.destruirVirtualScrolling();
            return;
        }
        
        // Garante que status estão carregados (caso não tenha sido chamado antes)
        this.carregarStatusDisponiveis();
        
        // Verifica se há filtros ativos para usar processos filtrados ou todos
        const temFiltros = this.temFiltrosAtivos() || (this.termoBusca && this.termoBusca.trim() !== '');
        
        // Ordenação agora é feita no backend - processos já vêm ordenados
        const processosParaRenderizar = temFiltros ? this.obterProcessosFiltrados() : this.processos;
        const numProcessosPagina = processosParaRenderizar.length;
        const numProcessosTotal = this.totalItens; // Total vem do backend
        
        // Ajusta estilo do container quando há apenas 1 resultado na página
        if (numProcessosPagina === 1) {
            container.css({
                'display': 'grid',
                'grid-template-columns': 'minmax(min(100%, 380px), 600px)',
                'grid-auto-rows': 'auto',
                'gap': '1.25rem',
                'align-content': 'start',
                'align-items': 'start',
                'justify-content': 'start',
                'padding': '1.5rem',
                'min-height': 'auto',
                'flex-direction': 'unset'
            });
        } else {
            // Garante que o container use grid normal quando há múltiplos resultados
            container.css({
                'display': 'grid',
                'grid-template-columns': 'repeat(auto-fill, minmax(min(100%, 280px), 1fr))',
                'grid-auto-rows': '1fr',
                'gap': '1.25rem',
                'align-content': 'start',
                'align-items': 'stretch',
                'padding': '1.5rem',
                'justify-content': 'unset',
                'min-height': 'auto',
                'flex-direction': 'unset'
            });
        }
        
        // Mostra/oculta controles de seleção baseado na view atual
        const podeSelecionar = this.filtroAtual === 'entrada';
        if (podeSelecionar) {
            $('#container-selecao').show();
        } else {
            $('#container-selecao').hide();
            // Limpa seleções quando não está na caixa de entrada
            this.processosSelecionados.clear();
            this.todosSelecionados = false;
        }
        
        // Usa virtual scrolling se houver muitos processos totais (>= 500)
        // Nota: Com paginação no backend, virtual scrolling pode não ser necessário
        // Mas mantemos para compatibilidade com grandes volumes
        if (numProcessosTotal >= 500 && !temFiltros) {
            // Para virtual scrolling, precisamos carregar todos os dados
            // Isso pode ser otimizado no futuro
            this.renderizarComVirtualScrolling(container, processosParaRenderizar, temFiltros);
        } else {
            // Renderização normal
            this.destruirVirtualScrolling();
            const html = processosParaRenderizar.map(processo => this.criarCardProcesso(processo)).join('');
            container.html(html);
            
            // Atualiza estado de seleção
            this.atualizarContadorSelecionados();
            
            // Atualiza breadcrumb para mostrar filtros ativos (se houver)
            if (temFiltros) {
                this.atualizarBreadcrumb();
            }
            
            // Iguala alturas dos cards na mesma linha
            this.igualarAlturasCards();
        }
    }
    
    /**
     * Renderiza lista usando virtual scrolling (para listas grandes)
     */
    renderizarComVirtualScrolling(container, processosParaRenderizar, temFiltros) {
        // Reseta contador
        this.itemsRenderizadosVirtual = 0;
        
        // Renderiza primeiros items
        const processosIniciais = processosParaRenderizar.slice(0, this.itemsPorPaginaVirtual);
        const html = processosIniciais.map(processo => this.criarCardProcesso(processo)).join('');
        container.html(html);
        
        this.itemsRenderizadosVirtual = processosIniciais.length;
        
        // Adiciona sentinel para detectar quando carregar mais
        if (this.itemsRenderizadosVirtual < processosParaRenderizar.length) {
            const sentinel = $('<div class="virtual-scrolling-sentinel" style="grid-column: 1 / -1; height: 20px; margin-top: 1rem;"></div>');
            container.append(sentinel);
            
            // Configura Intersection Observer
            this.configurarVirtualScrollingObserver(container, processosParaRenderizar, temFiltros);
        }
        
        // Atualiza estado de seleção
        this.atualizarContadorSelecionados();
        
        // Atualiza breadcrumb
        if (temFiltros) {
            this.atualizarBreadcrumb();
        }
        
        // Iguala alturas dos cards
        this.igualarAlturasCards();
    }
    
    /**
     * Configura Intersection Observer para virtual scrolling
     */
    configurarVirtualScrollingObserver(container, processosParaRenderizar, temFiltros) {
        // Destroi observer anterior se existir
        this.destruirVirtualScrolling();
        
        const sentinel = container.find('.virtual-scrolling-sentinel')[0];
        if (!sentinel) return;
        
        const self = this;
        
        this.observerVirtualScrolling = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && self.itemsRenderizadosVirtual < processosParaRenderizar.length) {
                    // Carrega mais items
                    const inicio = self.itemsRenderizadosVirtual;
                    const fim = Math.min(inicio + self.itemsPorPaginaVirtual, processosParaRenderizar.length);
                    const processosNovos = processosParaRenderizar.slice(inicio, fim);
                    
                    // Remove sentinel temporariamente
                    const sentinelEl = container.find('.virtual-scrolling-sentinel');
                    sentinelEl.remove();
                    
                    // Adiciona novos cards
                    const htmlNovos = processosNovos.map(processo => self.criarCardProcesso(processo)).join('');
                    container.append(htmlNovos);
                    
                    self.itemsRenderizadosVirtual = fim;
                    
                    // Se ainda há mais items, adiciona sentinel novamente
                    if (self.itemsRenderizadosVirtual < processosParaRenderizar.length) {
                        const novoSentinel = $('<div class="virtual-scrolling-sentinel" style="grid-column: 1 / -1; height: 20px; margin-top: 1rem;"></div>');
                        container.append(novoSentinel);
                        
                        // Observa o novo sentinel
                        self.observerVirtualScrolling.observe(novoSentinel[0]);
                    }
                    
                    // Atualiza alturas e seleção
                    self.igualarAlturasCards();
                    self.atualizarContadorSelecionados();
                }
            });
        }, {
            rootMargin: '100px' // Carrega quando está a 100px de entrar no viewport
        });
        
        this.observerVirtualScrolling.observe(sentinel);
    }
    
    /**
     * Destroi o observer de virtual scrolling
     */
    destruirVirtualScrolling() {
        if (this.observerVirtualScrolling) {
            this.observerVirtualScrolling.disconnect();
            this.observerVirtualScrolling = null;
        }
        $('.virtual-scrolling-sentinel').remove();
    }
    
    /**
     * Cria card de processo
     */
    criarCardProcesso(processo) {
        const tipo = processo.tipo || 'MATERIA';
        const codEntidade = processo.cod_entidade || processo.cod_materia || processo.cod_documento;
        const podeSelecionar = this.filtroAtual === 'entrada';
        const isSelecionado = podeSelecionar && this.processosSelecionados.has(codEntidade);
        
        // Dados específicos por tipo
        let numero, ementa, sigla, tipoBadge, autoriaInteressado;
        if (tipo === 'MATERIA') {
            numero = `${processo.materia_num || ''}/${processo.materia_ano || ''}`;
            ementa = processo.materia_ementa || '';
            sigla = processo.materia_sigla || '';
            tipoBadge = '<span class="badge bg-primary">Legislativo</span>';
            // ✅ MELHORADO: Autoria da matéria com truncamento e tooltip para listas longas
            const autoria = processo.materia_autoria || '';
            if (autoria && autoria.trim() !== '') {
                // Trunca autoria se muito longa (mais de 100 caracteres)
                const autoriaTruncada = autoria.length > 100 
                    ? autoria.substring(0, 100) + '...' 
                    : autoria;
                autoriaInteressado = `<div class="text-secondary small mt-1 mb-1 autoria-texto" 
                                          style="word-wrap: break-word; line-height: 1.4;" 
                                          ${autoria.length > 100 ? `title="${this.escapeHtml(autoria)}" data-bs-toggle="tooltip" data-bs-placement="top"` : ''}>
                                          <i class="mdi mdi-account-multiple me-1"></i><strong>Autor:</strong> ${this.escapeHtml(autoriaTruncada)}
                                      </div>`;
            } else {
                autoriaInteressado = '';
            }
        } else {
            numero = `${processo.documento_num || ''}/${processo.documento_ano || ''}`;
            ementa = processo.documento_assunto || '';
            sigla = processo.documento_sigla || '';
            tipoBadge = '<span class="badge bg-success">Administrativo</span>';
            // Interessado do documento
            const interessado = processo.documento_interessado || '';
            if (interessado && interessado.trim() !== '') {
                autoriaInteressado = `<div class="text-secondary small mt-1 mb-1"><i class="mdi mdi-account me-1"></i><strong>Interessado:</strong> ${this.escapeHtml(interessado)}</div>`;
            } else {
                autoriaInteressado = '';
            }
        }
        
        // Trunca ementa/assunto se muito longo e prepara tooltip
        const ementaCompleta = ementa || '';
        // ✅ MELHORADO: Usa CSS line-clamp para truncar em 3 linhas com tooltip e melhor legibilidade
        const ementaHtml = ementaCompleta.trim() !== ''
            ? `<p class="text-muted mb-2 small ementa-texto" 
                   style="display: -webkit-box; 
                          -webkit-line-clamp: 3; 
                          -webkit-box-orient: vertical; 
                          overflow: hidden; 
                          text-overflow: ellipsis; 
                          line-height: 1.5; 
                          word-wrap: break-word;
                          hyphens: auto;" 
                   title="${this.escapeHtml(ementaCompleta)}"
                   data-bs-toggle="tooltip"
                   data-bs-placement="top">${this.escapeHtml(ementaCompleta)}</p>`
            : `<p class="text-muted mb-2 small"></p>`;
        
        // ✅ CORRIGIDO: Lógica de data baseada no contexto
        // - Rascunhos: usa apenas dat_tramitacao (ainda não foi encaminhada)
        // - Entrada/Enviados: usa dat_tramitacao se disponível, senão dat_encaminha
        // Isso garante que os cards mostrem a mesma data que o formulário
        let dataTramitacao;
        if (this.filtroAtual === 'rascunhos') {
            // Rascunhos ainda não foram encaminhados, então dat_encaminha pode ser null
            dataTramitacao = processo.dat_tramitacao;
        } else {
            // Para entrada/enviados, prioriza dat_tramitacao mas aceita dat_encaminha como fallback
            dataTramitacao = processo.dat_tramitacao || processo.dat_encaminha;
        }
        const dataFormatada = this.formatarData(dataTramitacao);
        const status = processo.des_status || 'Sem status';
        
        // ✅ CORRIGIDO: Data de fim de prazo (apenas data, sem horário)
        // Trata datas sem timezone como local para evitar diferença de 1 dia
        let prazoHtml = '';
        if (processo.dat_fim_prazo) {
            let dataFimPrazo;
            const prazoStr = String(processo.dat_fim_prazo).trim();
            
            // Se não tem timezone info (não tem Z, + ou - após a hora)
            if (!prazoStr.includes('Z') && !prazoStr.match(/[+-]\d{2}:\d{2}$/)) {
                // Para formato ISO sem timezone (ex: '2026-01-23' ou '2026-01-23T00:00:00'), trata como local
                const partes = prazoStr.replace('T', ' ').split(' ');
                if (partes.length >= 1) {
                    const dataPart = partes[0];
                    const [ano, mes, dia] = dataPart.split('-');
                    // Cria Date usando valores locais (não UTC) - usa meio-dia para evitar problemas de timezone
                    dataFimPrazo = new Date(parseInt(ano), parseInt(mes) - 1, parseInt(dia), 12, 0, 0);
                } else {
                    dataFimPrazo = new Date(prazoStr);
                }
            } else {
                // Se já tem timezone info, usa normalmente
                dataFimPrazo = new Date(prazoStr);
            }
            
            const hoje = new Date();
            hoje.setHours(0, 0, 0, 0); // Zera horas para comparar apenas datas
            dataFimPrazo.setHours(0, 0, 0, 0);
            const estaVencido = dataFimPrazo < hoje;
            // Formata apenas a data (sem horário) para o prazo
            const dataFimPrazoFormatada = dataFimPrazo.toLocaleDateString('pt-BR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
            const corClasse = estaVencido ? 'text-danger' : 'text-muted';
            const iconeClasse = estaVencido ? 'mdi-alert-circle' : 'mdi-calendar-clock';
            prazoHtml = `<span class="${corClasse}"><i class="mdi ${iconeClasse} me-1"></i>Prazo: ${dataFimPrazoFormatada}</span>`;
        }
        
        // Origem e destino da tramitação
        const unidadeOrigem = processo.unidade_origem || '';
        const unidadeDestino = processo.unidade_destino || '';
        let origemDestinoHtml = '';
        if (unidadeOrigem || unidadeDestino) {
            const partes = [];
            if (unidadeOrigem) {
                partes.push(`<span><i class="mdi mdi-arrow-right-circle-outline me-1"></i><strong>De:</strong> ${this.escapeHtml(unidadeOrigem)}</span>`);
            }
            if (unidadeDestino) {
                partes.push(`<span class="ms-2"><i class="mdi mdi-arrow-left-circle-outline me-1"></i><strong>Para:</strong> ${this.escapeHtml(unidadeDestino)}</span>`);
            }
            origemDestinoHtml = `<div class="text-secondary small mt-1 mb-1">${partes.join('')}</div>`;
        }
        
        // ✅ Checkbox: garante id único + label associado (evita mismatch de labels/checkboxes)
        const checkboxId = `chk_proc_${String(tipo || 'PROC').toLowerCase()}_${String(codEntidade)}`;
        const checkboxHtml = podeSelecionar
            ? `<div class="form-check mt-2 flex-shrink-0" style="margin-top: 0.25rem !important;">
                   <input class="form-check-input checkbox-processo"
                          type="checkbox"
                          id="${checkboxId}"
                          name="check_tram"
                          value="${String(codEntidade)}"
                          data-cod-entidade="${codEntidade}"
                          ${isSelecionado ? 'checked' : ''}
                          aria-label="Selecionar processo ${codEntidade}">
                   <label class="form-check-label visually-hidden" for="${checkboxId}">
                       Selecionar processo ${String(codEntidade)}
                   </label>
               </div>`
            : '';
        
        // Extrai cod_tramitacao antes de usar
        const codTramitacao = processo.cod_tramitacao;
        
        // Botão para caixa de entrada (Tramitar)
        // Se houver cod_tramitacao, passa também para registrar visualização
        const botaoTramitarHtml = podeSelecionar
            ? codTramitacao
                ? `<button class="btn btn-sm btn-outline-primary flex-shrink-0" onclick="tramitacaoApp.abrirModalTramitacaoIndividual(${codEntidade}, '${tipo}', ${codTramitacao})">
                       <i class="mdi mdi-send"></i> Tramitar
                   </button>`
                : `<button class="btn btn-sm btn-outline-primary flex-shrink-0" onclick="tramitacaoApp.abrirModalTramitacaoIndividual(${codEntidade}, '${tipo}')">
                   <i class="mdi mdi-send"></i> Tramitar
               </button>`
            : '';
        
        // Botão para rascunhos (Editar)
        const isRascunho = this.filtroAtual === 'rascunhos' && codTramitacao;
        const botaoEditarHtml = isRascunho
            ? `<button class="btn btn-sm btn-outline-warning flex-shrink-0 btn-editar-rascunho" 
                      data-cod-tramitacao="${codTramitacao}" 
                      data-tipo="${tipo}"
                      title="Editar rascunho">
                   <i class="mdi mdi-pencil"></i> Editar
               </button>`
            : '';
        
        // Botão "Ver Despacho" para caixa de entrada (abre PDF e registra visualização/recebimento)
        const botaoVerDetalhesHtml = (podeSelecionar && codTramitacao)
            ? `<button class="btn btn-sm btn-outline-info flex-shrink-0 btn-ver-detalhes-tramitacao" 
                      data-cod-tramitacao="${codTramitacao}" 
                      data-tipo="${tipo}"
                      title="Ver despacho (registra visualização e recebimento)">
                   <i class="mdi mdi-eye"></i> Ver Despacho
               </button>`
            : '';
        
        // Botão "Retomar" para tramitações enviadas (apenas se não foram visualizadas/recebidas)
        const isEnviada = this.filtroAtual === 'enviados' && codTramitacao;
        // Converte ambos para número para comparação correta (evita problemas de tipo string vs número)
        const codUsuarioLocalRaw = processo.cod_usuario_local != null ? parseInt(processo.cod_usuario_local, 10) : null;
        const codUsuarioCorrenteRaw = COD_USUARIO_CORRENTE != null ? parseInt(COD_USUARIO_CORRENTE, 10) : null;
        // Valida que as conversões foram bem-sucedidas (não são NaN) e são números válidos (> 0)
        const codUsuarioLocal = (codUsuarioLocalRaw != null && !isNaN(codUsuarioLocalRaw) && codUsuarioLocalRaw > 0) ? codUsuarioLocalRaw : null;
        const codUsuarioCorrente = (codUsuarioCorrenteRaw != null && !isNaN(codUsuarioCorrenteRaw) && codUsuarioCorrenteRaw > 0) ? codUsuarioCorrenteRaw : null;
        // Verifica se dat_visualizacao e dat_recebimento estão vazias (null, undefined ou string vazia)
        const naoVisualizada = !processo.dat_visualizacao || String(processo.dat_visualizacao).trim() === '';
        const naoRecebida = !processo.dat_recebimento || String(processo.dat_recebimento).trim() === '';
        const podeRetomar = isEnviada && 
            processo.dat_encaminha && 
            naoVisualizada && 
            naoRecebida &&
            codUsuarioLocal !== null &&
            codUsuarioCorrente !== null &&
            codUsuarioLocal === codUsuarioCorrente; // Verifica se é do mesmo usuário
        
        const botaoRetomarHtml = podeRetomar
            ? `<button class="btn btn-sm btn-outline-danger flex-shrink-0 btn-retomar-tramitacao" 
                      data-cod-tramitacao="${codTramitacao}" 
                      data-tipo="${tipo}"
                      title="Retomar tramitação (volta para rascunhos)">
                   <i class="mdi mdi-undo"></i> Retomar
               </button>`
            : '';
        
        // Usa botão de editar se for rascunho, senão usa botão de tramitar
        const botaoAcaoHtml = isRascunho ? botaoEditarHtml : botaoTramitarHtml;
        
        // ✅ CORRETO: Botões sempre lado a lado (nunca em coluna)
        // Em desktop ficam à direita do conteúdo, em mobile o container inteiro fica abaixo
        // IMPORTANTE: Usa flex-wrap: nowrap para garantir que botões nunca fiquem em coluna
        let botoesAcaoCompleto = '';
        if (podeSelecionar && !isRascunho && codTramitacao) {
            // Botões para caixa de entrada: Ver Despacho + Tramitar (sempre lado a lado, nunca em coluna)
            botoesAcaoCompleto = `<div class="d-flex gap-2 flex-shrink-0 align-self-start botoes-acao" style="gap: 0.5rem !important; flex-wrap: nowrap !important; flex-direction: row !important;">${botaoVerDetalhesHtml}${botaoTramitarHtml}</div>`;
        } else if (botaoRetomarHtml) {
            // Botão Retomar para tramitações enviadas
            botoesAcaoCompleto = `<div class="flex-shrink-0 align-self-start botoes-acao">${botaoRetomarHtml}</div>`;
        } else if (botaoAcaoHtml) {
            // Um botão: Editar ou Tramitar (quando não há dois botões)
            botoesAcaoCompleto = `<div class="flex-shrink-0 align-self-start botoes-acao">${botaoAcaoHtml}</div>`;
        }
        
        // URL da pasta digital baseada no tipo
        // portal_url pode não incluir o caminho base (ex: http://localhost:8080)
        // Precisamos adicionar o caminho base extraído de window.location.pathname
        let baseUrl = PORTAL_URL.replace(/\/$/, ''); // Remove barra final se existir
        
        // Se portal_url não inclui o caminho base, extrai do window.location.pathname
        // Exemplo: /sagl/cadastros/tramitacao/tramitacao_email_style_html -> /sagl
        if (window.location.pathname) {
            const pathParts = window.location.pathname.split('/').filter(p => p);
            if (pathParts.length > 0) {
                const basePath = '/' + pathParts[0]; // Primeiro segmento (ex: /sagl)
                // Se baseUrl não termina com o caminho base, adiciona
                if (!baseUrl.endsWith(basePath)) {
                    baseUrl = baseUrl + basePath;
                }
            }
        }
        
        let pastaDigitalUrl = '';
        if (tipo === 'MATERIA') {
            // URL para pasta digital legislativa
            // Formato: http://localhost:8080/sagl/@@pasta_digital?cod_materia=XXX&action=pasta
            pastaDigitalUrl = `${baseUrl}/@@pasta_digital?cod_materia=${codEntidade}&action=pasta`;
        } else {
            // URL para pasta digital administrativa
            // Formato: http://localhost:8080/sagl/consultas/documento_administrativo/pasta_digital_adm?cod_documento=XXX&action=pasta
            pastaDigitalUrl = `${baseUrl}/consultas/documento_administrativo/pasta_digital_adm?cod_documento=${codEntidade}&action=pasta`;
        }
        
        // ✅ CORRETO: Título clicável - h6 com flex para alinhar badge e texto na mesma linha
        const tituloHtml = `<a href="${pastaDigitalUrl}" 
                                  target="_blank" 
                                  class="text-decoration-none text-dark titulo-processo-link d-inline-block"
                                  title="Abrir pasta digital em nova aba"
                                  style="transition: color 0.2s ease; width: 100%;">
                                <h6 class="mb-2 d-flex align-items-center" style="margin-bottom: 0.5rem !important; line-height: 1.5;">
                                    ${tipoBadge}
                                    <span class="ms-2">${this.escapeHtml(sigla)} Nº ${this.escapeHtml(numero)}</span>
                                    <i class="mdi mdi-open-in-new ms-1 small text-muted"></i>
                                </h6>
                            </a>`;
        
        // ✅ MELHORADO: Layout do card - botões alinhados com o título (não com todo o conteúdo)
        // Estrutura: Checkbox | [Título + Botões (mesma linha)] | [Conteúdo abaixo]
        return `
            <div class="card processo-card ${isSelecionado ? 'selecionado' : ''}" 
                 data-cod-entidade="${codEntidade}"
                 style="display: flex; flex-direction: column; height: 100%; transition: box-shadow 0.2s ease;">
                <div class="card-body" style="display: flex; flex-direction: column; flex: 1; padding: 1rem;">
                    <div class="d-flex align-items-start gap-2 gap-md-3" style="flex: 1;">
                        ${checkboxHtml}
                        <div class="flex-grow-1 d-flex flex-column" style="min-width: 0; height: 100%;">
                            <!-- ✅ CORRETO: Título e botões na mesma linha (flex row) -->
                            <!-- Em desktop: título à esquerda, botões à direita (alinhados verticalmente ao centro) -->
                            <!-- Em mobile: título em cima, botões embaixo -->
                            <div class="d-flex flex-column flex-md-row align-items-start flex-md-items-center mb-2 gap-2 gap-md-3">
                                <div class="flex-grow-1 titulo-processo-link-container" style="min-width: 0; display: flex; align-items: center;">
                                    ${tituloHtml}
                                </div>
                                <div class="flex-shrink-0 botoes-titulo-container" style="display: flex; align-items: center;">
                                    ${botoesAcaoCompleto}
                                </div>
                            </div>
                            <!-- Conteúdo abaixo do título (ementa, autor, origem/destino) -->
                            <div class="flex-grow-1" style="min-width: 0;">
                                    ${ementaHtml}
                                    ${autoriaInteressado}
                                    ${origemDestinoHtml}
                                </div>
                            <!-- Rodapé com metadados -->
                            <div class="d-flex flex-wrap gap-2 gap-md-3 text-muted small mt-auto pt-2 border-top" 
                                 style="margin-top: auto; padding-top: 0.75rem;">
                                <span class="d-flex align-items-center"><i class="mdi mdi-calendar me-1"></i>${dataFormatada}</span>
                                <span class="d-flex align-items-center"><i class="mdi mdi-tag me-1"></i>${this.escapeHtml(status)}</span>
                                ${prazoHtml ? `<span class="d-flex align-items-center">${prazoHtml}</span>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * Atualiza breadcrumb
     * IMPORTANTE: Rascunhos e Enviados são do usuário, não da unidade.
     * Apenas Caixa de Entrada deve mostrar a unidade no breadcrumb.
     */
    atualizarBreadcrumb() {
        const breadcrumb = $('#breadcrumb-contexto');
        const caixaMap = {
            entrada: 'Caixa de Entrada',
            rascunhos: 'Rascunhos',
            enviados: 'Enviados'
        };
        
        const tipoMap = {
            TODOS: 'Todos',
            MATERIA: 'Legislativo',
            DOCUMENTO: 'Administrativo'
        };
        
        // Atualiza link da caixa
        const $breadcrumbCaixa = $('#breadcrumb-caixa');
        $breadcrumbCaixa.text(caixaMap[this.filtroAtual] || 'Caixa de Entrada');
        
        // Atualiza dropdown de unidade
        const $breadcrumbUnidade = $('#breadcrumb-unidade');
        const $breadcrumbUnidadeDropdown = $('#breadcrumb-unidade-dropdown');
        
        // Dispose de qualquer instância de dropdown existente antes de manipular
        let existingDropdownInstance = bootstrap.Dropdown.getInstance($breadcrumbUnidade[0]);
        if (existingDropdownInstance) {
            existingDropdownInstance.dispose();
        }
        
        // IMPORTANTE: Só mostra unidade no breadcrumb para Caixa de Entrada
        // Rascunhos e Enviados são do usuário, não da unidade
        const deveMostrarUnidade = this.filtroAtual === 'entrada';
        
        if (deveMostrarUnidade && this.unidadeSelecionada) {
            // Busca o nome da unidade no array this.unidadesUsuario
            const unidadeEncontrada = this.unidadesUsuario.find(u => u.id == this.unidadeSelecionada);
            const unidadeNome = unidadeEncontrada ? (unidadeEncontrada.name || unidadeEncontrada.nom_unidade || 'Unidade selecionada') : 'Unidade selecionada';
            $breadcrumbUnidade.text(unidadeNome)
                .removeClass('bg-secondary')
                .addClass('bg-primary')
                .show(); // Garante que está visível
        } else if (deveMostrarUnidade && !this.unidadeSelecionada) {
            // Caixa de entrada sem unidade selecionada
            $breadcrumbUnidade.text('Todas as unidades')
                .removeClass('bg-primary')
                .addClass('bg-secondary')
                .show(); // Garante que está visível
        } else {
            // Rascunhos ou Enviados: oculta a unidade do breadcrumb
            $breadcrumbUnidade.hide();
        }
        
        // Preenche dropdown com unidades (apenas para entrada)
        if (this.filtroAtual === 'entrada') {
            if (this.unidadesUsuario.length > 0) {
                // Tem unidades carregadas - preenche o dropdown com contadores
                this.preencherDropdownUnidadesComContadores($breadcrumbUnidadeDropdown, $breadcrumbUnidade);
            } else {
                // Não tem unidades carregadas - tenta carregar e depois atualiza
                const self = this;
                this.carregarUnidadesUsuario().then(() => {
                    self.atualizarBreadcrumb();
                }).catch(() => {
                    // Se falhar, deixa dropdown desabilitado
                    const existingDropdown = bootstrap.Dropdown.getInstance($breadcrumbUnidade[0]);
                    if (existingDropdown) {
                        existingDropdown.dispose();
                    }
                    
                    $breadcrumbUnidade.removeClass('dropdown-toggle')
                        .removeAttr('data-bs-toggle')
                        .removeAttr('title')
                        .css('cursor', 'default');
                });
                // Enquanto carrega, deixa dropdown desabilitado temporariamente
                $breadcrumbUnidade.removeClass('dropdown-toggle')
                    .removeAttr('data-bs-toggle')
                    .css('cursor', 'wait');
            }
        } else {
            // Para rascunhos e enviados, não mostra dropdown (não usam unidade)
            const existingDropdown = bootstrap.Dropdown.getInstance($breadcrumbUnidade[0]);
            if (existingDropdown) {
                existingDropdown.dispose();
            }
            
            $breadcrumbUnidade.removeClass('dropdown-toggle')
                .removeAttr('data-bs-toggle')
                .removeAttr('aria-expanded')
                .removeAttr('title')
                .css('cursor', 'default');
        }
        
        // ✅ CORRETO: Atualiza contador do breadcrumb
        let contador;
        
        // Se estamos em "Todas as unidades" (entrada sem unidade selecionada), soma contadores das unidades
        if (this.filtroAtual === 'entrada' && !this.unidadeSelecionada && this.unidadesUsuario && this.unidadesUsuario.length > 0) {
            // Soma todos os contadores das unidades (mais preciso que totalItens quando há cards)
            const somaUnidades = this.unidadesUsuario.reduce((acc, u) => acc + (u.entrada || 0), 0);
            if (somaUnidades > 0) {
                contador = somaUnidades;
            } else {
                // Se soma deu zero mas há unidades, usa contador da sidebar (pode estar mais atualizado)
                const contadorId = `#contador-${this.filtroAtual}`;
                contador = parseInt($(contadorId + ' .contador-valor').text()) || 0;
            }
        } else if (this.totalItens !== undefined && this.totalItens !== null && this.totalItens > 0) {
            // Usa totalItens se estiver disponível e válido (mais confiável - vem do backend)
            contador = this.totalItens;
        } else {
            // Fallback: lê da sidebar (pode estar desatualizado temporariamente)
            const contadorId = `#contador-${this.filtroAtual}`;
            contador = parseInt($(contadorId + ' .contador-valor').text()) || 0;
        }
        
        $('#breadcrumb-contador').text(`${contador} processo${contador != 1 ? 's' : ''}`);
        
        // Atualiza filtros ativos (melhor visualização)
        const temFiltrosAtivos = this.temFiltrosAtivos() || (this.termoBusca && this.termoBusca.trim() !== '');
        const filtrosHtml = [];
        
        // Filtro de tipo
        if (this.filtroTipo !== 'TODOS') {
            filtrosHtml.push(`<span class="badge bg-warning text-dark me-1 filtro-chip" data-filtro-tipo="tipo-processo" role="button" tabindex="0" style="cursor: pointer;" title="Clique para remover filtro: Tipo ${tipoMap[this.filtroTipo]}"><i class="mdi mdi-filter-variant" aria-hidden="true"></i> ${tipoMap[this.filtroTipo]} <i class="mdi mdi-close ms-1" aria-hidden="true"></i></span>`);
        }
        
        // Busca rápida
        if (this.termoBusca && this.termoBusca.trim() !== '') {
            filtrosHtml.push(`<span class="badge bg-info text-dark me-1 filtro-chip" data-filtro-tipo="busca" role="button" tabindex="0" style="cursor: pointer;" title="Clique para remover busca"><i class="mdi mdi-magnify" aria-hidden="true"></i> "${this.escapeHtml(this.termoBusca.substring(0, 20))}${this.termoBusca.length > 20 ? '...' : ''}" <i class="mdi mdi-close ms-1" aria-hidden="true"></i></span>`);
        }
        
        // Filtros avançados
        const filtroTipoDoc = $('#filtro-tipo-documento').val() || '';
        const filtroNumero = $('#filtro-numero').val() || '';
        const filtroAno = $('#filtro-ano').val() || '';
        const filtroInteressado = $('#filtro-interessado').val() || '';
        
        if (filtroTipoDoc.trim() !== '') {
            filtrosHtml.push(`<span class="badge bg-secondary me-1 filtro-chip" data-filtro-tipo="tipo-documento" role="button" tabindex="0" style="cursor: pointer;" title="Clique para remover filtro: Tipo ${this.escapeHtml(filtroTipoDoc)}"><i class="mdi mdi-file-document-outline" aria-hidden="true"></i> ${this.escapeHtml(filtroTipoDoc)} <i class="mdi mdi-close ms-1" aria-hidden="true"></i></span>`);
        }
        if (filtroNumero.trim() !== '') {
            filtrosHtml.push(`<span class="badge bg-secondary me-1 filtro-chip" data-filtro-tipo="numero" role="button" tabindex="0" style="cursor: pointer;" title="Clique para remover filtro: Número ${this.escapeHtml(filtroNumero)}">#${this.escapeHtml(filtroNumero)} <i class="mdi mdi-close ms-1" aria-hidden="true"></i></span>`);
        }
        if (filtroAno.trim() !== '') {
            filtrosHtml.push(`<span class="badge bg-secondary me-1 filtro-chip" data-filtro-tipo="ano" role="button" tabindex="0" style="cursor: pointer;" title="Clique para remover filtro: Ano ${this.escapeHtml(filtroAno)}">Ano: ${this.escapeHtml(filtroAno)} <i class="mdi mdi-close ms-1" aria-hidden="true"></i></span>`);
        }
        if (filtroInteressado.trim() !== '') {
            filtrosHtml.push(`<span class="badge bg-secondary me-1 filtro-chip" data-filtro-tipo="interessado" role="button" tabindex="0" style="cursor: pointer;" title="Clique para remover filtro: Interessado ${this.escapeHtml(filtroInteressado)}"><i class="mdi mdi-account" aria-hidden="true"></i> ${this.escapeHtml(filtroInteressado.substring(0, 15))}${filtroInteressado.length > 15 ? '...' : ''} <i class="mdi mdi-close ms-1" aria-hidden="true"></i></span>`);
        }
        
        // NOVOS FILTROS: Status e Data
        const filtroStatus = $('#filtro-status').val() || '';
        const filtroDataInicial = $('#filtro-data-inicial').val() || '';
        const filtroDataFinal = $('#filtro-data-final').val() || '';
        
        if (filtroStatus.trim() !== '') {
            filtrosHtml.push(`<span class="badge bg-info text-dark me-1 filtro-chip" data-filtro-tipo="status" role="button" tabindex="0" style="cursor: pointer;" title="Clique para remover filtro: Status ${this.escapeHtml(filtroStatus)}"><i class="mdi mdi-flag" aria-hidden="true"></i> ${this.escapeHtml(filtroStatus)} <i class="mdi mdi-close ms-1" aria-hidden="true"></i></span>`);
        }
        
        if (filtroDataInicial || filtroDataFinal) {
            let periodoTexto = '';
            if (filtroDataInicial && filtroDataFinal) {
                periodoTexto = `${filtroDataInicial} a ${filtroDataFinal}`;
            } else if (filtroDataInicial) {
                periodoTexto = `A partir de ${filtroDataInicial}`;
            } else {
                periodoTexto = `Até ${filtroDataFinal}`;
            }
            filtrosHtml.push(`<span class="badge bg-info text-dark me-1 filtro-chip" data-filtro-tipo="data" role="button" tabindex="0" style="cursor: pointer;" title="Clique para remover filtro de data"><i class="mdi mdi-calendar-range" aria-hidden="true"></i> ${this.escapeHtml(periodoTexto)} <i class="mdi mdi-close ms-1" aria-hidden="true"></i></span>`);
        }
        
        // Atualiza o container de filtros no breadcrumb
        const $breadcrumbFiltros = $('#breadcrumb-filtros');
        if (filtrosHtml.length > 0) {
            $breadcrumbFiltros.html(filtrosHtml.join('')).css('display', 'inline-flex');
        } else {
            $breadcrumbFiltros.html('').css('display', 'none');
        }
        
        // Garante que o breadcrumb está visível
        if (breadcrumb.length > 0) {
            breadcrumb.show();
        }
    }
    
    /**
     * Verifica se há filtros ativos
     */
    temFiltrosAtivos() {
        const val = (id) => {
            const el = document.getElementById(id);
            return el ? (el.value || '').trim() : '';
        };
        
        return val('filtro-tipo-processo') !== 'TODOS' ||
               val('filtro-tipo-documento') !== '' ||
               val('filtro-numero') !== '' ||
               val('filtro-ano') !== '' ||
               val('filtro-interessado') !== '' ||
               val('filtro-status') !== '' ||
               val('filtro-data-inicial') !== '' ||
               val('filtro-data-final') !== '';
    }
    
    /**
     * Remove um filtro específico por tipo
     */
    removerFiltroPorTipo(tipo) {
        switch(tipo) {
            case 'tipo-processo':
                $('#filtro-tipo-processo').val('TODOS');
                this.filtroTipo = 'TODOS';
                break;
            case 'busca':
                $('#busca-rapida').val('');
                this.termoBusca = '';
                break;
            case 'tipo-documento':
                $('#filtro-tipo-documento').val('');
                break;
            case 'numero':
                $('#filtro-numero').val('');
                break;
            case 'ano':
                $('#filtro-ano').val('');
                break;
            case 'interessado':
                $('#filtro-interessado').val('');
                break;
            case 'status':
                $('#filtro-status').val('');
                break;
            case 'data':
                $('#filtro-data-inicial').val('');
                $('#filtro-data-final').val('');
                break;
        }
        this.aplicarFiltros();
    }
    
    /**
     * Limpa campos de filtros
     */
    limparCamposFiltros() {
        $('#filtro-tipo-processo').val('TODOS');
        $('#filtro-tipo-documento').val('');
        $('#filtro-numero').val('');
        $('#filtro-ano').val('');
        $('#filtro-interessado').val('');
        $('#filtro-status').val('');
        $('#filtro-data-inicial').val('');
        $('#filtro-data-final').val('');
        $('#busca-rapida').val('');
        this.filtroTipo = 'TODOS';
        this.termoBusca = '';
        
        // Limpa cache de filtros
        this.cacheFiltros.clear();
        this.ultimaChaveFiltro = null;
        
        // Atualiza breadcrumb para limpar badges de filtros
        this.atualizarBreadcrumb();
    }
    
    /**
     * Limpa processos completos (chamado quando muda unidade ou caixa)
     */
    limparProcessosCompletos() {
        this.processosCompletos = [];
    }
    
    /**
     * Toggle filtros avançados
     */
    toggleFiltrosAvancados() {
        const secao = $('#secao-filtros');
        const painel = $('#painel-filtros');
        const self = this; // Captura o contexto para uso dentro dos callbacks
        
        if (!this.unidadeSelecionada && this.filtroAtual === 'entrada') {
            this.mostrarToast('Selecione uma unidade primeiro', 'warning');
            return;
        }
        
        // Verifica se o painel está expandido usando classes do Bootstrap
        const isExpanded = painel.hasClass('show');
        
        if (isExpanded && secao.is(':visible')) {
            // Está expandido e visível, colapsa
            $('#btn-toggle-filtros-rapido').attr('aria-expanded', 'false');
            const bsCollapse = bootstrap.Collapse.getInstance(painel[0]);
            if (bsCollapse) {
                bsCollapse.hide();
            } else {
                painel.collapse('hide');
            }
            
            // Aguarda o colapso terminar e depois oculta a seção
            painel.one('hidden.bs.collapse', function() {
                secao.hide();
            });
        } else {
            // Está colapsado ou oculto, mostra e expande
            $('#btn-toggle-filtros-rapido').attr('aria-expanded', 'true');
            secao.show();
            
            // Aguarda um frame para garantir que a seção esteja visível antes de expandir
            setTimeout(() => {
                const bsCollapse = bootstrap.Collapse.getInstance(painel[0]);
                if (bsCollapse) {
                    bsCollapse.show();
                } else {
                    painel.collapse('show');
                }
                
                // Quando os filtros são abertos, garante que status estão carregados
                // Aguarda um pouco mais para garantir que o DOM está pronto
                setTimeout(() => {
                    self.carregarStatusDisponiveis();
                }, 100);
            }, 10);
            
            // Scroll suave até a seção
            $('html, body').animate({
                scrollTop: secao.offset().top - 100
            }, 300);
        }
    }
    
    /**
     * Filtra por busca rápida e filtros avançados
     */
    filtrarPorBusca(termo) {
        this.termoBusca = (termo || '').trim();
        this.aplicarFiltros();
    }
    
    /**
     * Aplica filtros avançados e busca
     */
    aplicarFiltros() {
        // Limpa cache de filtros quando aplica novos filtros
        this.cacheFiltros.clear();
        this.ultimaChaveFiltro = null;
        
        // Verifica se há filtros ativos
        const temFiltros = this.temFiltrosAtivos() || (this.termoBusca && this.termoBusca.trim() !== '');
        
        // Salva estado no localStorage
        this.salvarEstado();
        
        // Se há filtros, precisa recarregar todos os processos (sem paginação)
        // para aplicar os filtros em todos os resultados, não apenas na página atual
        if (temFiltros) {
            // Reseta para primeira página quando aplica novos filtros
            this.paginaAtual = 1;
            // Recarrega todos os processos (vai chamar aplicarFiltrosAosProcessos quando terminar)
            this.carregarTramitacoes();
            return;
        }
        
        // Se não há filtros, limpa cache de processos filtrados e recarrega com paginação normal
        this.processosFiltrados = [];
        this.totalFiltrado = 0;
        this.paginaAtual = 1; // Reseta para a primeira página
        this.carregarTramitacoes();
    }
    
    /**
     * Obtém os processos filtrados com base nos filtros ativos (com memoização)
     */
    obterProcessosFiltrados() {
        // Se não há processos carregados, retorna array vazio
        if (!this.processos || this.processos.length === 0) {
            return [];
        }
        
        // Gera chave de cache baseada nos filtros ativos
        const chaveFiltro = this.gerarChaveFiltro();
        
        // Se a chave não mudou e temos cache, retorna resultado em cache
        if (chaveFiltro === this.ultimaChaveFiltro && this.cacheFiltros.has(chaveFiltro)) {
            return this.cacheFiltros.get(chaveFiltro);
        }
        
        // Limpa cache se mudou a chave (novos filtros)
        if (chaveFiltro !== this.ultimaChaveFiltro) {
            this.cacheFiltros.clear();
            this.ultimaChaveFiltro = chaveFiltro;
        }
        
        let processosFiltrados = [...this.processos];
        
        // Filtro por tipo de processo (deve ser aplicado primeiro)
        if (this.filtroTipo && this.filtroTipo !== 'TODOS') {
            processosFiltrados = processosFiltrados.filter(p => p.tipo === this.filtroTipo);
        }
        
        
        // Filtro por tipo de documento (sigla) - funciona para matérias e documentos
        const filtroTipoDoc = $('#filtro-tipo-documento').val() || '';
        if (filtroTipoDoc.trim() !== '') {
            const filtroTipoDocLower = filtroTipoDoc.toLowerCase();
            const antes = processosFiltrados.length;
            processosFiltrados = processosFiltrados.filter(p => {
                if (p.tipo === 'MATERIA') {
                    const sigla = (p.materia_sigla || '').toLowerCase();
                    return sigla === filtroTipoDocLower || sigla.includes(filtroTipoDocLower);
                } else if (p.tipo === 'DOCUMENTO') {
                    const sigla = (p.documento_sigla || '').toLowerCase();
                    return sigla === filtroTipoDocLower || sigla.includes(filtroTipoDocLower);
                }
                return false;
            });
        }
        
        // Filtro por número
        const filtroNumero = $('#filtro-numero').val() || '';
        if (filtroNumero.trim() !== '') {
            const antes = processosFiltrados.length;
            processosFiltrados = processosFiltrados.filter(p => {
                const num = p.tipo === 'MATERIA' ? p.materia_num : p.documento_num;
                return num && num.toString().includes(filtroNumero);
            });
        }
        
        // Filtro por ano
        const filtroAno = $('#filtro-ano').val() || '';
        if (filtroAno.trim() !== '') {
            const antes = processosFiltrados.length;
            processosFiltrados = processosFiltrados.filter(p => {
                const ano = p.tipo === 'MATERIA' ? p.materia_ano : p.documento_ano;
                return ano && ano.toString().includes(filtroAno);
            });
        }
        
        // Filtro por interessado - funciona para matérias (autoria) e documentos (interessado)
        const filtroInteressado = $('#filtro-interessado').val() || '';
        if (filtroInteressado.trim() !== '') {
            const antes = processosFiltrados.length;
            processosFiltrados = processosFiltrados.filter(p => {
                const autoria = (p.tipo === 'MATERIA' ? p.materia_autoria : '').toLowerCase();
                const interessado = (p.tipo === 'DOCUMENTO' ? p.documento_interessado : '').toLowerCase();
                return autoria.includes(filtroInteressado.toLowerCase()) || interessado.includes(filtroInteressado.toLowerCase());
            });
        }
        
        // NOVO: Filtro por status de tramitação
        // ⚠️ IMPORTANTE: Status são diferentes para MATERIA (StatusTramitacao) e DOCUMENTO (StatusTramitacaoAdministrativo)
        // Mas no JSON ambos vêm como 'des_status', então a filtragem funciona igual
        const filtroStatus = $('#filtro-status').val() || '';
        if (filtroStatus.trim() !== '') {
            const antes = processosFiltrados.length;
            processosFiltrados = processosFiltrados.filter(p => {
                const status = p.des_status || '';
                // Busca exata (case-insensitive) para evitar falsos positivos
                return status.toLowerCase() === filtroStatus.toLowerCase();
            });
        }
        
        // NOVO: Filtro por data de tramitação (range)
        const dataInicial = $('#filtro-data-inicial').val();
        const dataFinal = $('#filtro-data-final').val();
        
        if (dataInicial) {
            const antes = processosFiltrados.length;
            const dataInicialObj = new Date(dataInicial + 'T00:00:00');
            processosFiltrados = processosFiltrados.filter(p => {
                if (!p.dat_encaminha) return false;
                const dataProcesso = new Date(p.dat_encaminha);
                return dataProcesso >= dataInicialObj;
            });
        }
        
        if (dataFinal) {
            const antes = processosFiltrados.length;
            const dataFinalObj = new Date(dataFinal + 'T23:59:59');
            processosFiltrados = processosFiltrados.filter(p => {
                if (!p.dat_encaminha) return false;
                const dataProcesso = new Date(p.dat_encaminha);
                return dataProcesso <= dataFinalObj;
            });
        }
        
        // Busca rápida
        if (this.termoBusca && this.termoBusca.trim() !== '') {
            const termoLower = this.termoBusca.toLowerCase();
            processosFiltrados = processosFiltrados.filter(p => {
                const ementa = (p.tipo === 'MATERIA' ? p.materia_ementa : p.documento_assunto) || '';
                const numero = (p.tipo === 'MATERIA' 
                    ? `${p.materia_num || ''}/${p.materia_ano || ''}` 
                    : `${p.documento_num || ''}/${p.documento_ano || ''}`) || '';
                const autoria = (p.tipo === 'MATERIA' ? p.materia_autoria : '') || '';
                const interessado = (p.tipo === 'DOCUMENTO' ? p.documento_interessado : '') || '';
                
                return ementa.toLowerCase().includes(termoLower) || 
                       numero.toLowerCase().includes(termoLower) ||
                       autoria.toLowerCase().includes(termoLower) ||
                       interessado.toLowerCase().includes(termoLower);
            });
        }
        
        // Salva resultado no cache (limita cache a 5 entradas para não usar muita memória)
        if (this.cacheFiltros.size >= 5) {
            const primeiraChave = this.cacheFiltros.keys().next().value;
            this.cacheFiltros.delete(primeiraChave);
        }
        this.cacheFiltros.set(chaveFiltro, processosFiltrados);
        
        return processosFiltrados;
    }
    
    /**
     * Gera chave única para cache de filtros
     */
    gerarChaveFiltro() {
        const filtroTipoDoc = $('#filtro-tipo-documento').val() || '';
        const filtroNumero = $('#filtro-numero').val() || '';
        const filtroAno = $('#filtro-ano').val() || '';
        const filtroInteressado = $('#filtro-interessado').val() || '';
        const filtroStatus = $('#filtro-status').val() || '';
        const filtroDataInicial = $('#filtro-data-inicial').val() || '';
        const filtroDataFinal = $('#filtro-data-final').val() || '';
        
        return JSON.stringify({
            filtroTipo: this.filtroTipo || 'TODOS',
            termoBusca: (this.termoBusca || '').trim(),
            filtroTipoDoc: filtroTipoDoc.trim(),
            filtroNumero: filtroNumero.trim(),
            filtroAno: filtroAno.trim(),
            filtroInteressado: filtroInteressado.trim(),
            filtroStatus: filtroStatus.trim(),
            filtroDataInicial: filtroDataInicial.trim(),
            filtroDataFinal: filtroDataFinal.trim(),
            totalProcessos: this.processos.length // Inclui total para invalidar cache se processos mudarem
        });
    }
    
    /**
     * Carrega status disponíveis de TODOS os processos (não apenas da página atual)
     */
    async carregarStatusDisponiveis() {
        try {
            // Verifica se o select existe no DOM
            const select = $('#filtro-status');
            if (select.length === 0) {
                console.warn('Select #filtro-status não encontrado no DOM. Tentando novamente em 200ms...');
                // Tenta novamente após um delay (pode estar colapsado)
                setTimeout(() => {
                    this.carregarStatusDisponiveis();
                }, 200);
                return;
            }
            
            // Se já temos processos completos carregados (todos, sem paginação), usa eles
            if (this.processosCompletos && this.processosCompletos.length > 0) {
                const statusUnicos = new Set();
                this.processosCompletos.forEach(p => {
                    if (p.des_status && p.des_status.trim() !== '') {
                        statusUnicos.add(p.des_status);
                    }
                });
                const statusArray = Array.from(statusUnicos).sort();
                this.popularSelectStatus(statusArray);
                return;
            }
            
            // Caso contrário, busca TODOS os processos do backend (limit=0) para extrair status
            if (!this.unidadeSelecionada && this.filtroAtual === 'entrada') {
                // Se não há unidade selecionada, não pode carregar
                select.empty();
                select.append('<option value="">Todos os status</option>');
                return;
            }
            
            
            const codUsuario = COD_USUARIO_CORRENTE;
            if (!codUsuario || codUsuario === 0) {
                console.warn('cod_usuario não disponível para carregar status');
                select.empty();
                select.append('<option value="">Todos os status</option>');
                return;
            }
            
            // Monta URL para buscar TODOS os processos (limit=0 ou um valor muito alto)
            const params = new URLSearchParams({
                cod_usuario: codUsuario.toString(),
                limit: '0', // 0 = sem limite, busca todos
                offset: '0'
            });
            
            if (this.unidadeSelecionada) {
                params.append('cod_unid_tramitacao', this.unidadeSelecionada.toString());
            }
            
            const url = `${PORTAL_URL}/tramitacao_caixa_entrada_unificada_json?${params.toString()}`;
            
            
            const xhr = $.ajax({
                url: url,
                dataType: 'json'
            });
            
            const dados = await xhr;
            const todosProcessos = dados.tramitacoes || [];
            
            
            // Extrai status únicos de TODOS os processos
            const statusUnicos = new Set();
            todosProcessos.forEach(p => {
                if (p.des_status && p.des_status.trim() !== '') {
                    statusUnicos.add(p.des_status);
                }
            });
            
            const statusArray = Array.from(statusUnicos).sort();
            
            
            // Armazena processos completos para uso futuro (evita recarregar)
            this.processosCompletos = todosProcessos;
            
            if (statusArray.length > 0) {
                this.popularSelectStatus(statusArray);
            } else {
                select.empty();
                select.append('<option value="">Todos os status</option>');
            }
        } catch (e) {
            console.error('Erro ao carregar status:', e);
            // Em caso de erro, pelo menos mostra a opção padrão
            const select = $('#filtro-status');
            if (select.length > 0) {
                select.empty();
                select.append('<option value="">Todos os status</option>');
            }
        }
    }
    
    /**
     * Popula o select de status com os valores disponíveis
     */
    popularSelectStatus(statusArray) {
        const select = $('#filtro-status');
        if (select.length === 0) {
            console.warn('Select #filtro-status não encontrado no DOM');
            return;
        }
        
        const valorAtual = select.val(); // Preserva valor atual se existir
        select.empty();
        select.append('<option value="">Todos os status</option>');
        
        if (statusArray && statusArray.length > 0) {
            statusArray.forEach(status => {
                const option = $(`<option value="${this.escapeHtml(status)}">${this.escapeHtml(status)}</option>`);
                select.append(option);
            });
            // Restaura valor se ainda existir nas opções
            if (valorAtual && statusArray.includes(valorAtual)) {
                select.val(valorAtual);
            }
        }
    }
    
    /**
     * Aplica filtros aos processos já carregados (chamado após carregarTramitacoes quando há filtros)
     */
    aplicarFiltrosAosProcessos() {
        // Se não há processos carregados, não faz nada
        if (!this.processos || this.processos.length === 0) {
            this.mostrarEstadoVazio('sem-processos');
            $('#container-selecao').hide();
            return;
        }
        
        // Garante que status estão carregados (caso não tenha sido chamado antes)
        this.carregarStatusDisponiveis();
        
        // Obtém processos filtrados usando a função auxiliar
        const processosFiltrados = this.obterProcessosFiltrados();
        
        // Aplica ordenação por data aos processos filtrados
        const processosFiltradosOrdenados = this.ordenarProcessosPorData([...processosFiltrados]);
        
        // Ordenação agora é feita no backend - não precisa ordenar aqui
        // Armazena processos filtrados e total para paginação
        this.processosFiltrados = processosFiltrados;
        this.totalFiltrado = processosFiltrados.length;
        
        // Reseta para primeira página quando aplica filtros
        this.paginaAtual = 1;
        
        // Renderiza resultados paginados
        this.renderizarListaFiltrada();
        
        // Atualiza controles de paginação
        this.atualizarControlesPagina();
        
        // Atualiza breadcrumb para mostrar filtros ativos
        this.atualizarBreadcrumb();
    }
    
    /**
     * Renderiza lista de processos filtrados com paginação
     */
    renderizarListaFiltrada() {
        const container = $('.processos-container');
        
        if (this.totalFiltrado === 0) {
            container.html(`
                <div class="empty-state">
                    <i class="mdi mdi-magnify"></i>
                    <h3>Nenhum resultado encontrado</h3>
                    <p>Não encontramos processos que correspondam aos filtros aplicados.</p>
                </div>
            `);
            $('#container-selecao').hide();
            this.destruirVirtualScrolling();
            return;
        }
        
        // Calcula índices para paginação
        const inicio = (this.paginaAtual - 1) * this.itensPorPagina;
        const fim = Math.min(inicio + this.itensPorPagina, this.totalFiltrado);
        const processosPagina = this.processosFiltrados.slice(inicio, fim);
        const numProcessosPagina = processosPagina.length;
        
        // Ajusta estilo do container quando há apenas 1 resultado na página
        if (numProcessosPagina === 1) {
            container.css({
                'display': 'grid',
                'grid-template-columns': 'minmax(min(100%, 380px), 600px)',
                'grid-auto-rows': 'auto',
                'gap': '1.25rem',
                'align-content': 'start',
                'align-items': 'start',
                'justify-content': 'start',
                'padding': '1.5rem',
                'min-height': 'auto',
                'flex-direction': 'unset'
            });
        } else {
            // Garante que o container use grid normal quando há múltiplos resultados
            container.css({
                'display': 'grid',
                'grid-template-columns': 'repeat(auto-fill, minmax(min(100%, 280px), 1fr))',
                'grid-auto-rows': '1fr',
                'gap': '1.25rem',
                'align-content': 'start',
                'align-items': 'stretch',
                'padding': '1.5rem',
                'justify-content': 'unset',
                'min-height': 'auto',
                'flex-direction': 'unset'
            });
        }
        
        // Mostra/oculta controles de seleção baseado na view atual
        const podeSelecionar = this.filtroAtual === 'entrada';
        if (podeSelecionar) {
            $('#container-selecao').show();
        } else {
            $('#container-selecao').hide();
            this.processosSelecionados.clear();
            this.todosSelecionados = false;
        }
        
        // Usa virtual scrolling se houver muitos processos filtrados (>= 500)
        if (this.totalFiltrado >= 500) {
            this.renderizarComVirtualScrolling(container, this.processosFiltrados, true);
        } else {
            // Renderização normal com paginação
            this.destruirVirtualScrolling();
            const html = processosPagina.map(p => this.criarCardProcesso(p)).join('');
            container.html(html);
            
            // Atualiza estado de seleção
            this.atualizarContadorSelecionados();
            
            // Iguala alturas dos cards na mesma linha
            this.igualarAlturasCards();
        }
    }
    
    /**
     * Preenche dropdown de unidades com contadores de entrada
     */
    async preencherDropdownUnidadesComContadores($breadcrumbUnidadeDropdown, $breadcrumbUnidade) {
        // Evita execução simultânea
        if (this.preenchendoDropdownUnidades) {
            return;
        }
        
        this.preenchendoDropdownUnidades = true;
        
        try {
            const codUsuario = COD_USUARIO_CORRENTE;
            if (!codUsuario || codUsuario === 0) {
                return;
            }
            
            // Limpa dropdown completamente
            $breadcrumbUnidadeDropdown.empty();
            
            // Adiciona item "Todas as unidades"
            $breadcrumbUnidadeDropdown.append('<li><a class="dropdown-item" href="#" data-cod-unidade=""><i class="mdi mdi-view-grid-outline me-2"></i>Todas as unidades</a></li>');
            
            // Remove unidades duplicadas usando Set com código da unidade
            const unidadesUnicas = [];
            const codigosUnicos = new Set();
            
            this.unidadesUsuario.forEach(unidade => {
                const codUnidade = unidade.id || unidade.cod_unid_tramitacao;
                if (!codigosUnicos.has(codUnidade)) {
                    codigosUnicos.add(codUnidade);
                    unidadesUnicas.push(unidade);
                }
            });
            
            // Busca contadores para cada unidade
            const promessas = unidadesUnicas.map(async (unidade) => {
                const codUnidade = unidade.id || unidade.cod_unid_tramitacao;
                const url = `${PORTAL_URL}/tramitacao_contadores_json?cod_usuario=${codUsuario}&cod_unid_tramitacao=${codUnidade}`;
                
                    try {
                    
                    const xhr = $.ajax({
                        url: url,
                        dataType: 'json'
                    });
                    
                    const dados = await xhr;
                    return {
                        ...unidade,
                        entrada: dados.entrada || 0
                    };
                } catch (error) {
                    console.error(`Erro ao buscar contador para unidade ${codUnidade}:`, error);
                    return {
                        ...unidade,
                        entrada: 0
                    };
                }
            });
            
            try {
                const unidadesComContadores = await Promise.all(promessas);
                
                // Preenche dropdown com unidades e contadores (apenas uma vez)
                unidadesComContadores.forEach(unidade => {
                    const codUnidade = unidade.id || unidade.cod_unid_tramitacao;
                    const nomeUnidade = unidade.name || unidade.nom_unidade_join || unidade.nom_unidade || 'Unidade';
                    const contador = unidade.entrada || 0;
                    
                    // Cria item com contador (mais discreto)
                    const $item = $('<li><a class="dropdown-item d-flex justify-content-between align-items-center" href="#" data-cod-unidade="' + codUnidade + '"><span><i class="mdi mdi-office-building-outline me-2"></i>' + this.escapeHtml(nomeUnidade) + '</span><span class="text-muted small ms-2" style="font-weight: 400;">' + contador + '</span></a></li>');
                    
                    if (this.unidadeSelecionada == codUnidade) {
                        $item.find('a').addClass('active');
                    }
                    $breadcrumbUnidadeDropdown.append($item);
                });
                
                // Garante que o dropdown está habilitado e visível
                $breadcrumbUnidade.addClass('dropdown-toggle')
                    .attr('data-bs-toggle', 'dropdown')
                    .attr('aria-expanded', 'false')
                    .attr('title', 'Clique para selecionar uma unidade')
                    .css('cursor', 'pointer');
            } catch (error) {
                console.error('Erro ao buscar contadores para dropdown:', error);
                // Em caso de erro, preenche sem contadores (apenas unidades únicas)
                unidadesUnicas.forEach(unidade => {
                    const codUnidade = unidade.id || unidade.cod_unid_tramitacao;
                    const nomeUnidade = unidade.name || unidade.nom_unidade_join || unidade.nom_unidade || 'Unidade';
                    const $item = $('<li><a class="dropdown-item" href="#" data-cod-unidade="' + codUnidade + '"><i class="mdi mdi-office-building-outline me-2"></i>' + this.escapeHtml(nomeUnidade) + '</a></li>');
                    if (this.unidadeSelecionada == codUnidade) {
                        $item.find('a').addClass('active');
                    }
                    $breadcrumbUnidadeDropdown.append($item);
                });
            }
        } finally {
            this.preenchendoDropdownUnidades = false;
        }
    }
    
    /**
     * Iguala as alturas dos cards que estão na mesma linha do grid
     */
    igualarAlturasCards() {
        const container = $('.processos-container');
        const cards = container.find('.processo-card');
        
        if (cards.length === 0) return;
        
        // Se houver apenas 1 card, não iguala alturas (deixa altura automática)
        if (cards.length === 1) {
            cards.css('height', 'auto');
            return;
        }
        
        // Reset alturas primeiro - remove height e min-height fixas
        cards.css('height', '');
        cards.css('height', 'auto');
        cards.css('min-height', ''); // Remove min-height do CSS para permitir controle do grid
        
        // Aguarda dois frames para garantir que o layout foi totalmente aplicado
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                // Usa getBoundingClientRect para identificar cards na mesma linha
                const cardsData = cards.map((index, card) => {
                    const $card = $(card);
                    const rect = card.getBoundingClientRect();
                    return {
                        $card: $card,
                        top: rect.top,
                        left: rect.left,
                        height: rect.height
                    };
                }).get();
                
                // Agrupa cards por linha (mesmo top)
                const linhas = {};
                cardsData.forEach(cardData => {
                    const topKey = Math.round(cardData.top);
                    if (!linhas[topKey]) {
                        linhas[topKey] = [];
                    }
                    linhas[topKey].push(cardData);
                });
                
                // Se há exatamente 1 linha com exatamente 2 cards, aplica mesma técnica de 1 card
                const linhasArray = Object.values(linhas);
                if (linhasArray.length === 1 && linhasArray[0].length === 2) {
                    // IMPORTANTE: Ajusta grid-auto-rows do container para 'auto' (mesma técnica de 1 card)
                    // Isso faz com que o grid não force altura 1fr, deixando altura natural do conteúdo
                    container.css('grid-auto-rows', 'auto');
                    container.css('align-items', 'start'); // Muda de stretch para start (como quando há 1 card)
                    
                    // Aplica a mesma técnica de quando há apenas 1 card: height: auto
                    // Deixa o CSS limitar naturalmente, sem forçar altura igual
                    linhasArray[0].forEach(cardData => {
                        cardData.$card.css('height', 'auto');
                        cardData.$card.css('min-height', '');
                        cardData.$card.css('max-height', '');
                        cardData.$card.css('overflow-y', '');
                    });
                    return; // Retorna aqui, sem igualar alturas (deixa CSS controlar)
                } else {
                    // Para múltiplas linhas, garante grid-auto-rows: 1fr (comportamento normal)
                    container.css('grid-auto-rows', '1fr');
                    container.css('align-items', 'stretch');
                }
                
                // Para cada linha, encontra a altura máxima e aplica a todos os cards
                Object.values(linhas).forEach(linha => {
                    if (linha.length <= 1) return; // Não precisa igualar se há apenas 1 card
                    
                    let alturaMaxima = 0;
                    
                    // Remove todas as restrições de altura de TODOS os cards da linha
                    linha.forEach(cardData => {
                        const card = cardData.$card[0];
                        card.style.height = '';
                        card.style.minHeight = '';
                        card.style.maxHeight = '';
                    });
                    
                    // Aguarda o grid recalcular com altura automática
                    requestAnimationFrame(() => {
                        // Mede a altura natural de cada card (sem restrições)
                        linha.forEach(cardData => {
                            const altura = cardData.$card[0].getBoundingClientRect().height;
                            if (altura > alturaMaxima) {
                                alturaMaxima = altura;
                            }
                        });
                        
                        // Aplica altura máxima a todos os cards da linha
                        linha.forEach(cardData => {
                            cardData.$card.css('min-height', '');
                            cardData.$card.css('height', alturaMaxima + 'px');
                        });
                    });
                });
            });
        });
    }
    
    /**
     * Atualiza contador de selecionados
     */
    atualizarContadorSelecionados() {
        const count = this.processosSelecionados.size;
        $('#contador-selecionados').text(count);
        
        if (count > 0) {
            $('#btn-tramitar-lote').show();
            $('#contador-selecionados').show();
        } else {
            $('#btn-tramitar-lote').hide();
            $('#contador-selecionados').hide();
        }
    }
    
    /**
     * Atualiza contadores quando há filtros aplicados
     */
    atualizarContadoresFiltrados(totalFiltrado, totalOriginal) {
        // Atualiza informação de paginação
        const inicio = 1;
        const fim = totalFiltrado;
        
        if (totalFiltrado === 0) {
            $('#info-paginacao').text(`0 de ${totalOriginal}`);
            $('#total-paginas').text('1');
            $('#pagina-atual').val(1);
            // Desabilita botões de navegação
            $('.paginacao-btn[data-acao="anterior"]').prop('disabled', true);
            $('.paginacao-btn[data-acao="proxima"]').prop('disabled', true);
            $('.paginacao-btn[data-acao="primeira"]').prop('disabled', true);
            $('.paginacao-btn[data-acao="ultima"]').prop('disabled', true);
        } else {
            $('#info-paginacao').text(`${inicio}-${fim} de ${totalFiltrado}`);
            $('#total-paginas').text('1');
            $('#pagina-atual').val(1);
            // Desabilita botões de navegação (pois todos os resultados filtrados são mostrados)
            $('.paginacao-btn[data-acao="anterior"]').prop('disabled', true);
            $('.paginacao-btn[data-acao="proxima"]').prop('disabled', true);
            $('.paginacao-btn[data-acao="primeira"]').prop('disabled', true);
            $('.paginacao-btn[data-acao="ultima"]').prop('disabled', true);
        }
        
        // Atualiza contador no breadcrumb
        $('#breadcrumb-contador').text(`${totalFiltrado} processo${totalFiltrado !== 1 ? 's' : ''}`);
    }
    
    /**
     * Atualiza controles de paginação
     */
    atualizarControlesPagina() {
        // Verifica se há filtros ativos
        const temFiltros = this.temFiltrosAtivos() || (this.termoBusca && this.termoBusca.trim() !== '');
        
        let totalPaginas, inicio, fim, total;
        
        if (temFiltros) {
            // Paginação baseada em resultados filtrados
            total = this.totalFiltrado;
            totalPaginas = Math.ceil(total / this.itensPorPagina);
            inicio = (this.paginaAtual - 1) * this.itensPorPagina + 1;
            fim = Math.min(this.paginaAtual * this.itensPorPagina, total);
        } else {
            // Paginação normal quando não há filtros
            total = this.totalItens;
            totalPaginas = Math.ceil(total / this.itensPorPagina);
            inicio = (this.paginaAtual - 1) * this.itensPorPagina + 1;
            fim = Math.min(this.paginaAtual * this.itensPorPagina, total);
        }
        
        // Atualiza controles de página
        $('#info-paginacao').text(`${inicio}-${fim} de ${total}`);
        $('#pagina-atual').val(this.paginaAtual);
        $('#total-paginas').text(totalPaginas);
        
        // Habilita/desabilita botões
        $('.paginacao-btn[data-acao="anterior"]').prop('disabled', this.paginaAtual <= 1);
        $('.paginacao-btn[data-acao="proxima"]').prop('disabled', this.paginaAtual >= totalPaginas);
        $('.paginacao-btn[data-acao="primeira"]').prop('disabled', this.paginaAtual <= 1);
        $('.paginacao-btn[data-acao="ultima"]').prop('disabled', this.paginaAtual >= totalPaginas);
        
        // Mostra/oculta controles baseado em regras
        const deveMostrar = this.filtroAtual !== null && 
                           (this.filtroAtual !== 'entrada' || this.unidadeSelecionada) &&
                           total > 0;
        
        if (deveMostrar) {
            $('#controles-lista').show();
        } else {
            $('#controles-lista').hide();
        }
    }
    
    /**
     * Altera página
     */
    alterarPagina(acao) {
        // Verifica se há filtros ativos
        const temFiltros = this.temFiltrosAtivos() || (this.termoBusca && this.termoBusca.trim() !== '');
        
        let totalPaginas;
        if (temFiltros) {
            // Paginação baseada em resultados filtrados
            totalPaginas = Math.ceil(this.totalFiltrado / this.itensPorPagina);
        } else {
            // Paginação normal
            totalPaginas = Math.ceil(this.totalItens / this.itensPorPagina);
        }
        
        if (acao === 'anterior' && this.paginaAtual > 1) {
            this.paginaAtual--;
        } else if (acao === 'proxima' && this.paginaAtual < totalPaginas) {
            this.paginaAtual++;
        } else if (acao === 'primeira') {
            this.paginaAtual = 1;
        } else if (acao === 'ultima') {
            this.paginaAtual = totalPaginas;
        }
        
        if (temFiltros) {
            // Se há filtros, renderiza apenas a página atual dos resultados filtrados
            this.renderizarListaFiltrada();
            this.atualizarControlesPagina();
        } else {
            // Se não há filtros, recarrega do backend
            this.carregarTramitacoes();
        }
    }
    
    /**
     * Alterna ordenação por data de tramitação
     */
    alterarOrdenacaoData() {
        // Alterna entre 'asc' e 'desc'
        this.ordenacaoData = this.ordenacaoData === 'desc' ? 'asc' : 'desc';
        
        // Atualiza ícone
        this.atualizarIconeOrdenacao();
        
        // Salva estado
        this.salvarEstado();
        
        // Verifica se há filtros ativos
        const temFiltros = this.temFiltrosAtivos() || (this.termoBusca && this.termoBusca.trim() !== '');
        
        if (temFiltros) {
            // Se há filtros, reordena processos filtrados e renderiza
            this.processosFiltrados = this.ordenarProcessosPorData([...this.processosFiltrados]);
            this.renderizarListaFiltrada();
            this.atualizarControlesPagina();
        } else {
            // Se não há filtros, reordena processos e renderiza
            this.processos = this.ordenarProcessosPorData([...this.processos]);
            this.renderizarLista();
            this.atualizarControlesPagina();
        }
    }
    
    /**
     * Atualiza ícone do botão de ordenação baseado na ordenação atual
     */
    atualizarIconeOrdenacao() {
        const icone = $('#icone-ordenar-data');
        const btn = $('#btn-ordenar-data');
        
        if (this.ordenacaoData === 'desc') {
            icone.removeClass('mdi-sort-calendar-ascending').addClass('mdi-sort-calendar-descending');
            btn.attr('title', 'Ordenar por data (mais recentes primeiro)');
        } else {
            icone.removeClass('mdi-sort-calendar-descending').addClass('mdi-sort-calendar-ascending');
            btn.attr('title', 'Ordenar por data (mais antigos primeiro)');
        }
    }
    
    /**
     * Ordena processos por data de tramitação (dat_encaminha)
     * Quando as datas/horários são iguais, agrupa por tipo e ordena por número/ano
     */
    ordenarProcessosPorData(processos) {
        return processos.sort((a, b) => {
            // Ordenação primária: por data/horário
            const dataA = a.dat_encaminha ? new Date(a.dat_encaminha).getTime() : 0;
            const dataB = b.dat_encaminha ? new Date(b.dat_encaminha).getTime() : 0;
            
            // Compara datas - se forem exatamente iguais (ou muito próximas), usa ordenação secundária
            let comparacaoData = 0;
            if (this.ordenacaoData === 'desc') {
                comparacaoData = dataB - dataA; // Descendente: mais recentes primeiro
            } else {
                comparacaoData = dataA - dataB; // Ascendente: mais antigos primeiro
            }
            
            // Se as datas são diferentes, retorna a comparação de data
            if (comparacaoData !== 0) {
                return comparacaoData;
            }
            
            // Ordenação secundária: quando as datas/horários são iguais (ou muito próximas)
            // 1. Agrupa por tipo (MATERIA primeiro, depois DOCUMENTO)
            const tipoA = (a.tipo || 'MATERIA').toUpperCase();
            const tipoB = (b.tipo || 'MATERIA').toUpperCase();
            
            // Ordem: MATERIA antes de DOCUMENTO
            const ordemTipo = { 'MATERIA': 1, 'DOCUMENTO': 2 };
            const ordemA = ordemTipo[tipoA] || 99;
            const ordemB = ordemTipo[tipoB] || 99;
            
            if (ordemA !== ordemB) {
                return ordemA - ordemB; // MATERIA primeiro (1 < 2)
            }
            
            // 2. Dentro do mesmo tipo, ordena por número e ano (seguindo a ordem da data)
            let numA = 0, anoA = 0, numB = 0, anoB = 0;
            
            if (tipoA === 'MATERIA') {
                // Lê campos de matéria - tenta diferentes variações de nome
                const numRawA = a.materia_num !== undefined && a.materia_num !== null ? a.materia_num : 
                               (a.num_materia !== undefined && a.num_materia !== null ? a.num_materia : '0');
                const anoRawA = a.materia_ano !== undefined && a.materia_ano !== null ? a.materia_ano : 
                               (a.ano_materia !== undefined && a.ano_materia !== null ? a.ano_materia : '0');
                numA = parseInt(String(numRawA).trim(), 10) || 0;
                anoA = parseInt(String(anoRawA).trim(), 10) || 0;
            } else {
                // Lê campos de documento
                const numRawA = a.documento_num !== undefined && a.documento_num !== null ? a.documento_num : 
                               (a.num_documento !== undefined && a.num_documento !== null ? a.num_documento : '0');
                const anoRawA = a.documento_ano !== undefined && a.documento_ano !== null ? a.documento_ano : 
                               (a.ano_documento !== undefined && a.ano_documento !== null ? a.ano_documento : '0');
                numA = parseInt(String(numRawA).trim(), 10) || 0;
                anoA = parseInt(String(anoRawA).trim(), 10) || 0;
            }
            
            if (tipoB === 'MATERIA') {
                const numRawB = b.materia_num !== undefined && b.materia_num !== null ? b.materia_num : 
                               (b.num_materia !== undefined && b.num_materia !== null ? b.num_materia : '0');
                const anoRawB = b.materia_ano !== undefined && b.materia_ano !== null ? b.materia_ano : 
                               (b.ano_materia !== undefined && b.ano_materia !== null ? b.ano_materia : '0');
                numB = parseInt(String(numRawB).trim(), 10) || 0;
                anoB = parseInt(String(anoRawB).trim(), 10) || 0;
            } else {
                const numRawB = b.documento_num !== undefined && b.documento_num !== null ? b.documento_num : 
                               (b.num_documento !== undefined && b.num_documento !== null ? b.num_documento : '0');
                const anoRawB = b.documento_ano !== undefined && b.documento_ano !== null ? b.documento_ano : 
                               (b.ano_documento !== undefined && b.ano_documento !== null ? b.ano_documento : '0');
                numB = parseInt(String(numRawB).trim(), 10) || 0;
                anoB = parseInt(String(anoRawB).trim(), 10) || 0;
            }
            
            // Ordena por ano primeiro, depois por número
            // Usa a mesma direção da ordenação de data (ascendente ou descendente)
            if (this.ordenacaoData === 'desc') {
                // Descendente: ano maior primeiro, depois número maior primeiro
                if (anoB !== anoA) {
                    return anoB - anoA;
                }
                return numB - numA;
            } else {
                // Ascendente: ano menor primeiro, depois número menor primeiro
                if (anoA !== anoB) {
                    return anoA - anoB;
                }
                return numA - numB;
            }
        });
    }
    
    /**
     * Mostra estado vazio
     */
    mostrarEstadoVazio(tipo) {
        const container = $('.processos-container');
        $('#controles-lista').hide();
        $('#container-selecao').hide();
        
        // Garante que o container está centralizado
        container.css({
            'display': 'flex',
            'flex-direction': 'column',
            'justify-content': 'center',
            'align-items': 'center',
            'min-height': '300px',
            'grid-template-columns': 'none',
            'gap': '0',
            'padding': '1rem'
        });
        
        let html = '';
        
        if (tipo === 'inicial') {
            html = `
                <div class="empty-state">
                    <i class="mdi mdi-view-grid-outline"></i>
                    <h3>Selecione uma unidade</h3>
                    <p>Escolha uma unidade acima para ver os processos disponíveis.</p>
                </div>
            `;
        } else if (tipo === 'sem-processos') {
            html = `
                <div class="empty-state">
                    <i class="mdi mdi-inbox-outline"></i>
                    <h3>Nenhum processo encontrado</h3>
                    <p>Não há processos nesta caixa no momento.</p>
                </div>
            `;
        } else if (tipo === 'filtros') {
            html = `
                <div class="empty-state">
                    <i class="mdi mdi-filter-remove"></i>
                    <h3>Nenhum resultado</h3>
                    <p>Nenhum processo corresponde aos filtros aplicados.</p>
                    <button class="btn btn-primary mt-3" onclick="tramitacaoApp.limparCamposFiltros(); tramitacaoApp.carregarTramitacoes();">
                        Limpar Filtros
                    </button>
                </div>
            `;
        } else {
            html = `
                <div class="empty-state">
                    <i class="mdi mdi-alert-circle"></i>
                    <h3>Erro ao carregar</h3>
                    <p>Ocorreu um erro ao carregar os processos. Tente novamente.</p>
                </div>
            `;
        }
        
        container.html(html);
    }
    
    /**
     * Mostra toast notification
     * Duração padrão reduzida para 2.5 segundos (antes era 5 segundos)
     */
    mostrarToast(...args) {
        const tipos = {
            success: { icon: 'mdi-check-circle', bg: 'bg-success' },
            error: { icon: 'mdi-alert-circle', bg: 'bg-danger' },
            warning: { icon: 'mdi-alert', bg: 'bg-warning' },
            info: { icon: 'mdi-information', bg: 'bg-info' }
        };

        // Suporta assinaturas antigas e novas:
        // - mostrarToast(mensagem, tipo?, duracao?)
        // - mostrarToast(titulo, mensagem, tipo, duracao?)
        let titulo = null;
        let mensagem = '';
        let tipo = 'info';
        let duracao = 2500;

        if (args.length === 1) {
            mensagem = args[0];
        } else if (args.length === 2) {
            // (mensagem, tipo) OU (titulo, mensagem)
            if (typeof args[1] === 'string' && Object.prototype.hasOwnProperty.call(tipos, args[1])) {
                mensagem = args[0];
                tipo = args[1];
            } else {
                titulo = args[0];
                mensagem = args[1];
            }
        } else if (args.length >= 3) {
            // (titulo, mensagem, tipo, duracao?)
            if (typeof args[2] === 'string' && Object.prototype.hasOwnProperty.call(tipos, args[2])) {
                titulo = args[0];
                mensagem = args[1];
                tipo = args[2];
                if (args.length >= 4) duracao = args[3];
            } else {
                // fallback: (mensagem, tipo, duracao)
                mensagem = args[0];
                tipo = args[1];
                duracao = args[2];
            }
        }

        const config = tipos[tipo] || tipos.info;
        const textoHeader = titulo ? String(titulo) : (tipo.charAt(0).toUpperCase() + tipo.slice(1));
        
        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header ${config.bg} text-white">
                    <i class="mdi ${config.icon} me-2"></i>
                    <strong class="me-auto">${this.escapeHtml(textoHeader)}</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Fechar"></button>
                </div>
                <div class="toast-body">
                    ${this.escapeHtml(mensagem)}
                </div>
            </div>
        `;
        
        let container = $('.toast-container');
        if (container.length === 0) {
            container = $('<div class="toast-container position-fixed top-0 end-0 p-3"></div>');
            $('body').append(container);
        }
        
        container.append(toastHtml);
        
        const toastElement = document.getElementById(toastId);
        // Passa delay como número nas opções, não como atributo data
        // Duração padrão reduzida para 2.5 segundos
        const toast = new bootstrap.Toast(toastElement, {
            delay: parseInt(duracao, 10) || 2500
        });
        toast.show();
        
        // Remove após esconder
        $(toastElement).on('hidden.bs.toast', function() {
            $(this).remove();
        });
    }

    _obterFormularioIndividualNoSidebar() {
        const body = document.getElementById('tramitacaoIndividualOffcanvasBody');
        if (!body) return null;
        return body.querySelector('form') || document.getElementById('tramitacao_individual_form') || null;
    }

    _submeterTramitacaoIndividual(acao /* 'salvar_rascunho' | 'enviar' */) {
        if (!this._ensureSidebarManager()) return;

        const form = this._obterFormularioIndividualNoSidebar();
        if (!form) {
            this.mostrarToast('Erro', 'Formulário individual não encontrado.', 'error');
            return;
        }

        const btnId = acao === 'salvar_rascunho' ? 'btnSalvarRascunho' : 'btnEnviarTramitacao';
        const btn = document.getElementById(btnId);
        const btnHtmlOriginal = btn ? btn.innerHTML : null;
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processando...';
        }

        try {
            const fd = new FormData(form);
            fd.set('acao', acao);

            // Unidade local é obrigatória; usa a unidade da caixa de entrada (readonly)
            if (!fd.get('lst_cod_unid_tram_local')) {
                fd.set('lst_cod_unid_tram_local', this.unidadeSelecionada || '');
            }

            // Garante texto do despacho (Trumbowyg)
            try {
                if (this.sidebarManager && typeof this.sidebarManager.obterConteudoEditor === 'function') {
                    fd.set('txa_txt_tramitacao', this.sidebarManager.obterConteudoEditor('individual') || '');
                }
            } catch (_) {}

            $.ajax({
                url: `${PORTAL_URL}/tramitacao_individual_salvar_json`,
                method: 'POST',
                dataType: 'json',
                data: fd,
                processData: false,
                contentType: false,
                success: (response) => {
                    const dados = typeof response === 'string' ? JSON.parse(response) : response;
                    if (dados && dados.erro) {
                        this.mostrarToast('Erro', dados.erro, 'error');
                        return;
                    }

                    // Atualiza cod_tramitacao no form (para habilitar botão Enviar depois do primeiro "salvar")
                    const codTramitacao = dados?.cod_tramitacao || dados?.dados?.cod_tramitacao || null;
                    if (codTramitacao) {
                        let input = form.querySelector('input[name="hdn_cod_tramitacao"]');
                        if (!input) {
                            input = document.createElement('input');
                            input.type = 'hidden';
                            input.name = 'hdn_cod_tramitacao';
                            form.appendChild(input);
                        }
                        input.value = String(codTramitacao);
                    }

                    // Marca estado inicial como "salvo" para não bloquear fechamento
                    try {
                        if (this.sidebarManager && typeof this.sidebarManager._salvarEstadoInicialFormulario === 'function') {
                            this.sidebarManager._salvarEstadoInicialFormulario('individual');
                        }
                        if (this.sidebarManager) {
                            this.sidebarManager.rascunhoSalvo = true;
                        }
                    } catch (_) {}

                    if (acao === 'salvar_rascunho') {
                        // Após salvar, habilita botão "Enviar"
                        try {
                            if (this.sidebarManager && typeof this.sidebarManager._atualizarBotoesFormulario === 'function') {
                                this.sidebarManager._atualizarBotoesFormulario(!!codTramitacao);
                            } else {
                                const btnEnviar = document.getElementById('btnEnviarTramitacao');
                                if (btnEnviar) btnEnviar.style.display = '';
                            }
                        } catch (_) {}

                        this.mostrarToast('Atenção', dados?.mensagem || 'Rascunho salvo com sucesso', 'success');
                    } else {
                        this.mostrarToast('Atenção', dados?.mensagem || 'Tramitação enviada com sucesso', 'success');

                        // Fecha formulário se backend indicar
                        const deveFechar = !!dados?.fechar_formulario || !!dados?.tramitacao_enviada;
                        if (deveFechar && this.sidebarManager && typeof this.sidebarManager._forceFecharSidebar === 'function') {
                            this.sidebarManager._forceFecharSidebar('individual');
                        }
                    }
                },
                error: (xhr) => {
                    const msg = xhr?.responseJSON?.erro || xhr?.responseText || 'Erro ao salvar tramitação.';
                    this.mostrarToast('Erro', msg, 'error');
                },
                complete: () => {
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = btnHtmlOriginal || (acao === 'salvar_rascunho'
                            ? '<i class="mdi mdi-content-save-outline" aria-hidden="true"></i> Salvar'
                            : '<i class="mdi mdi-send" aria-hidden="true"></i> Enviar Tramitação');
                    }
                }
            });
        } catch (e) {
            console.error('Erro ao submeter tramitação individual:', e);
            this.mostrarToast('Erro', 'Erro ao preparar dados do formulário.', 'error');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = btnHtmlOriginal || (acao === 'salvar_rascunho'
                    ? '<i class="mdi mdi-content-save-outline" aria-hidden="true"></i> Salvar'
                    : '<i class="mdi mdi-send" aria-hidden="true"></i> Enviar Tramitação');
            }
        }
    }

    salvarRascunho() {
        return this._submeterTramitacaoIndividual('salvar_rascunho');
    }

    enviarTramitacao() {
        return this._submeterTramitacaoIndividual('enviar');
    }

    /**
     * Retoma uma tramitação enviada (move de "enviados" para "rascunhos").
     */
    retomarTramitacao(codTramitacao, tipo = 'MATERIA') {
        const cod = codTramitacao ? String(codTramitacao) : '';
        if (!cod) {
            this.mostrarToast('Atenção', 'Código da tramitação não informado.', 'warning');
            return;
        }

        // Botão na lista (enviados)
        const $btn = jQuery(`.btn-retomar-tramitacao[data-cod-tramitacao="${cod}"]`);
        const htmlOriginal = $btn.length ? $btn.html() : null;
        if ($btn.length) {
            $btn.prop('disabled', true);
            $btn.html('<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Retomando...');
        }

        jQuery.ajax({
            url: `${PORTAL_URL}/tramitacao_retomar_json`,
            method: 'POST',
            dataType: 'json',
            data: { cod_tramitacao: cod, tipo: tipo || 'MATERIA' },
            success: (resp) => {
                const dados = (typeof resp === 'string') ? JSON.parse(resp) : resp;
                if (dados && dados.erro) {
                    this.mostrarToast('Erro', dados.erro, 'error');
                    return;
                }

                this.mostrarToast('Sucesso', (dados && dados.mensagem) ? dados.mensagem : 'Tramitação retomada com sucesso', 'success');

                // Atualiza UI: volta para rascunhos e recarrega
                try {
                    if (typeof this.alterarFiltro === 'function') {
                        this.alterarFiltro('rascunhos');
                    } else if (typeof this.carregarTramitacoes === 'function') {
                        this.carregarTramitacoes();
                    }
                } catch (_) {}

                // Recarrega contadores em segundo plano (se existir)
                try {
                    if (typeof this.carregarContadores === 'function') {
                        this.carregarContadores();
                    }
                } catch (_) {}
            },
            error: (xhr) => {
                const msg = xhr?.responseJSON?.erro || xhr?.responseText || 'Erro ao retomar tramitação.';
                this.mostrarToast('Erro', msg, 'error');
            },
            complete: () => {
                if ($btn.length) {
                    $btn.prop('disabled', false);
                    if (htmlOriginal != null) $btn.html(htmlOriginal);
                }
            }
        });
    }

    /**
     * Garante que o sidebar manager exista antes de abrir offcanvas.
     * (Algumas ações como "tramitar em lote" podem ocorrer antes de qualquer abertura individual.)
     */
    _ensureSidebarManager() {
        if (this.sidebarManager) return true;

        if (typeof TramitacaoSidebarManager === 'undefined') {
            console.error('TramitacaoSidebarManager não está disponível no escopo global.');
            this.mostrarToast('Erro', 'Não foi possível inicializar o formulário. Recarregue a página.', 'error');
            return false;
        }

        try {
            this.sidebarManager = new TramitacaoSidebarManager(this);
            return true;
        } catch (e) {
            console.error('Erro ao inicializar sidebarManager:', e);
            this.mostrarToast('Erro', 'Não foi possível inicializar o formulário. Tente recarregar a página.', 'error');
            return false;
        }
    }
    
    /**
     * Abre sidebar de tramitação individual
     * IMPORTANTE: Formulário sempre é renderizado no sidebar (offcanvas)
     */
    abrirModalTramitacaoIndividual(codEntidade, tipo, codTramitacaoRecebida = null) {
        if (!this._ensureSidebarManager()) return;

        // Se há cod_tramitacao_recebida e estamos na caixa de entrada, registra visualização antes de abrir
        if (codTramitacaoRecebida && this.filtroAtual === 'entrada') {
            this._registrarVisualizacaoTramitacao(codTramitacaoRecebida, tipo, () => {
                // Após registrar visualização, abre o formulário
                if (this.sidebarManager) {
                    this.sidebarManager.abrirNovaTramitacao(codEntidade, tipo);
                } else {
                    this.mostrarToast('Erro', 'Sidebar manager não inicializado', 'error');
                }
            });
        } else {
            // Sem registro de visualização, abre diretamente
            if (this.sidebarManager) {
                this.sidebarManager.abrirNovaTramitacao(codEntidade, tipo);
            } else {
                this.mostrarToast('Erro', 'Sidebar manager não inicializado', 'error');
            }
        }
    }
    
    /**
     * Registra visualização de tramitação recebida pelo destinatário
     */
    _registrarVisualizacaoTramitacao(cod_tramitacao, tipo, callback) {
        $.ajax({
            url: `${PORTAL_URL}/tramitacao_visualizar_json`,
            method: 'POST',
            data: { cod_tramitacao: cod_tramitacao, tipo: tipo },
            success: (response) => {
                const dados = typeof response === 'string' ? JSON.parse(response) : response;
                if (dados.erro) {
                    // Se houver erro, loga mas continua com abertura do formulário
                    console.warn('Erro ao registrar visualização:', dados.erro);
                } else {
                    console.debug('Visualização registrada com sucesso para tramitação', cod_tramitacao);
                }
                // Sempre chama callback (abre formulário mesmo se não registrar visualização)
                if (callback) callback();
            },
            error: (xhr) => {
                // Se falhar, loga mas continua com abertura do formulário (não é crítico)
                const erro = xhr.responseJSON?.erro || 'Erro ao registrar visualização';
                console.warn('Erro ao registrar visualização (continuando mesmo assim):', erro);
                // Chama callback mesmo com erro (visualização não é bloqueante)
                if (callback) callback();
            }
        });
    }
    
    /**
     * Abre sidebar de tramitação em lote
     * IMPORTANTE: Formulário sempre é renderizado no sidebar (offcanvas)
     */
    abrirModalTramitacaoLote() {
        if (!this._ensureSidebarManager()) return;

        // Sempre usa sidebar (offcanvas), nunca modal
        if (this.sidebarManager) {
            this.sidebarManager.abrirTramitacaoLote();
        } else {
            this.mostrarToast('Erro', 'Sidebar manager não inicializado', 'error');
        }
    }

    /**
     * Envia a tramitação em lote (POST) para o backend.
     */
    tramitarLote() {
        if (!this._ensureSidebarManager()) return;

        if (!this.processosSelecionados || this.processosSelecionados.size === 0) {
            this.mostrarToast('Atenção', 'Nenhum processo selecionado para tramitar em lote.', 'warning');
            return;
        }

        const body = document.getElementById('tramitacaoLoteOffcanvasBody');
        const form = body ? (body.querySelector('form') || document.getElementById('tramitacao_lote_tramitar_proc')) : null;
        if (!form) {
            this.mostrarToast('Erro', 'Formulário de lote não encontrado.', 'error');
            return;
        }

        // Desabilita botão para evitar duplo clique
        const btn = document.getElementById('btnTramitarLote');
        const btnHtmlOriginal = btn ? btn.innerHTML : null;
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Tramitando...';
        }

        try {
            const fd = new FormData(form);

            // Garante unidade local (backend exige lst_cod_unid_tram_local)
            if (!fd.get('lst_cod_unid_tram_local')) {
                fd.set('lst_cod_unid_tram_local', this.unidadeSelecionada || '');
            }

            // Anexa processos selecionados no formato esperado pelo backend: check_tram (multi)
            fd.delete('check_tram');
            Array.from(this.processosSelecionados).forEach((cod) => fd.append('check_tram', cod));

            // Garante texto do despacho (Trumbowyg pode não manter textarea sincronizado)
            if (body) {
                const textarea = body.querySelector('textarea[name="txa_txt_tramitacao"]');
                if (textarea) {
                    let html = (textarea.value || '');
                    if (typeof jQuery !== 'undefined' && typeof jQuery.fn.trumbowyg !== 'undefined') {
                        const $ta = jQuery(textarea);
                        if ($ta.length && $ta.data('trumbowyg')) {
                            try { html = $ta.trumbowyg('html') || ''; } catch (_) {}
                        }
                    }
                    fd.set('txa_txt_tramitacao', html);
                }
            }

            $.ajax({
                url: `${PORTAL_URL}/tramitacao_lote_salvar_json`,
                method: 'POST',
                data: fd,
                processData: false,
                contentType: false,
                success: (response) => {
                    const dados = typeof response === 'string' ? JSON.parse(response) : response;
                    if (dados && dados.erro) {
                        this.mostrarToast('Erro', dados.erro, 'error');
                        return;
                    }

                    const total = dados?.total || dados?.total_tramitado || null;
                    this.mostrarToast('Sucesso', total ? `Tramitação em lote concluída (${total}).` : 'Tramitação em lote concluída.', 'success');

                    // Limpa seleção e fecha sidebar (a página já tem interceptor para recarregar contadores/lista)
                    this.processosSelecionados.clear();
                    this.todosSelecionados = false;
                    try { this.atualizarContadorSelecionados(); } catch (_) {}

                    try {
                        // ✅ Sempre prefere o fechamento robusto do manager (bypass de guards/backdrop).
                        if (this.sidebarManager && typeof this.sidebarManager._forceFecharSidebar === 'function') {
                            this.sidebarManager._forceFecharSidebar('lote');
                        } else {
                            const sidebarEl = document.getElementById('tramitacaoLoteOffcanvas');
                            if (sidebarEl && typeof bootstrap !== 'undefined') {
                                bootstrap.Offcanvas.getOrCreateInstance(sidebarEl).hide();
                            }
                        }
                    } catch (_) {}
                },
                error: (xhr) => {
                    const msg = xhr?.responseJSON?.erro || xhr?.responseText || 'Erro ao tramitar em lote.';
                    this.mostrarToast('Erro', msg, 'error');
                },
                complete: () => {
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = btnHtmlOriginal || '<i class="mdi mdi-send-multiple" aria-hidden="true"></i> Tramitar Processos';
                    }
                }
            });
        } catch (e) {
            console.error('Erro ao tramitar em lote:', e);
            this.mostrarToast('Erro', 'Erro ao preparar tramitação em lote.', 'error');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = btnHtmlOriginal || '<i class="mdi mdi-send-multiple" aria-hidden="true"></i> Tramitar Processos';
            }
        }
    }
    
    /**
     * Formata data
     */
    formatarData(dataISO) {
        if (!dataISO) return '';
        try {
            // ✅ CORRIGIDO: Suporta múltiplos formatos de data
            // 1. Formato já formatado do formulário: 'DD/MM/YYYY HH:MM' (retorna direto)
            // 2. Formato ISO sem timezone: 'YYYY-MM-DDTHH:MM:SS' (trata como local)
            // 3. Formato ISO com timezone: 'YYYY-MM-DDTHH:MM:SS+HH:MM' (usa timezone)
            
            let dataStr = String(dataISO).trim();
            
            // Se já está no formato do formulário (DD/MM/YYYY HH:MM), retorna direto
            if (/^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}$/.test(dataStr)) {
                return dataStr;
            }
            
            // Se não tem timezone info (não tem Z, + ou - após a hora)
            if (!dataStr.includes('Z') && !dataStr.match(/[+-]\d{2}:\d{2}$/)) {
                // Para formato ISO sem timezone, trata como local
                // Remove o 'T' e cria Date manualmente para evitar interpretação como UTC
                const partes = dataStr.replace('T', ' ').split(' ');
                if (partes.length === 2) {
                    const [dataPart, horaPart] = partes;
                    const [ano, mes, dia] = dataPart.split('-');
                    const [hora, minuto, segundo = '00'] = horaPart.split(':');
                    // Cria Date usando valores locais (não UTC)
                    const data = new Date(parseInt(ano), parseInt(mes) - 1, parseInt(dia), 
                                         parseInt(hora), parseInt(minuto), parseInt(segundo));
                    
                    const dataFormatada = data.toLocaleDateString('pt-BR', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric'
                    });
                    const horaFormatada = data.toLocaleTimeString('pt-BR', {
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                    return dataFormatada + ' ' + horaFormatada;
                }
            }
            
            // Se já tem timezone info ou formato diferente, usa normalmente
            const data = new Date(dataISO);
            const dataFormatada = data.toLocaleDateString('pt-BR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
            const horaFormatada = data.toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit'
            });
            return dataFormatada + ' ' + horaFormatada;
        } catch (e) {
            return dataISO;
        }
    }
    
    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Debounce helper
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Throttle helper (para eventos como resize)
     */
    throttle(func, wait) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => {
                    inThrottle = false;
                }, wait);
            }
        };
    }
    
    /**
     * Mostra notificação de novos processos na caixa de entrada
     */
    mostrarNotificacaoAtualizacao(novosProcessos) {
        // Remove notificação anterior se existir
        $('#notificacao-atualizacao').remove();
        
        // Cria notificação
        const notificacao = $(`
            <div id="notificacao-atualizacao" class="alert alert-info alert-dismissible fade show" 
                 role="alert" style="position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <i class="mdi mdi-information-outline me-2"></i>
                <strong>Novos processos disponíveis!</strong>
                <p class="mb-2 mt-2">Há ${novosProcessos} novo(s) processo(s) na caixa de entrada.</p>
                <button type="button" class="btn btn-sm btn-primary" onclick="tramitacaoApp.atualizarLista()">
                    <i class="mdi mdi-refresh me-1"></i>Atualizar
                </button>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `);
        
        $('body').append(notificacao);
        
        // Auto-fecha após 10 segundos
        setTimeout(() => {
            notificacao.fadeOut(() => notificacao.remove());
        }, 10000);
    }
    
    /**
     * Atualiza lista quando usuário clica no botão "Atualizar"
     */
    atualizarLista() {
        // Remove notificação
        $('#notificacao-atualizacao').remove();
        
        // Atualiza contadores e lista
        this.carregarContadores();
        this.carregarTramitacoes();
        
        // Reseta último contador de entrada conhecido para evitar notificação imediata
        if (this.periodicUpdater) {
            this.periodicUpdater.lastContadorEntrada = null;
        }
    }
    
    /**
     * Carrega filtros salvos do localStorage e atualiza o dropdown
     */
    carregarFiltrosSalvos() {
        try {
            const filtrosSalvos = localStorage.getItem(TramitacaoEmailStyle.FILTROS_SALVOS_KEY);
            if (!filtrosSalvos) {
                this.atualizarDropdownFiltrosSalvos([]);
                return;
            }
            
            const filtros = JSON.parse(filtrosSalvos);
            this.atualizarDropdownFiltrosSalvos(filtros);
        } catch (e) {
            console.warn('Erro ao carregar filtros salvos:', e);
            this.atualizarDropdownFiltrosSalvos([]);
        }
    }
    
    /**
     * Atualiza o dropdown de filtros salvos
     */
    atualizarDropdownFiltrosSalvos(filtros) {
        const dropdown = $('#dropdown-filtros-salvos');
        dropdown.empty();
        
        if (!filtros || filtros.length === 0) {
            dropdown.append('<li><span class="dropdown-item-text small text-muted">Nenhum filtro salvo</span></li>');
            return;
        }
        
        filtros.forEach(filtro => {
            const item = $(`
                <li>
                    <div class="dropdown-item d-flex justify-content-between align-items-center filtro-salvo-item" 
                         data-filtro-id="${filtro.id}" role="menuitem">
                        <div class="flex-grow-1">
                            <div class="fw-semibold">${this.escapeHtml(filtro.nome)}</div>
                            <small class="text-muted">${this.escapeHtml(this.descreverFiltro(filtro))}</small>
                        </div>
                        <button class="btn btn-sm btn-link text-danger p-0 ms-2 remover-filtro-salvo" 
                                data-filtro-id="${filtro.id}" 
                                title="Remover filtro salvo"
                                aria-label="Remover filtro salvo">
                            <i class="mdi mdi-delete"></i>
                        </button>
                    </div>
                </li>
            `);
            dropdown.append(item);
        });
    }
    
    /**
     * Descreve um filtro para exibição
     */
    descreverFiltro(filtro) {
        const partes = [];
        if (filtro.filtroTipo && filtro.filtroTipo !== 'TODOS') {
            partes.push(filtro.filtroTipo === 'MATERIA' ? 'Legislativo' : 'Administrativo');
        }
        if (filtro.termoBusca) partes.push(`Busca: "${filtro.termoBusca}"`);
        if (filtro.filtroTipoDoc) partes.push(`Doc: ${filtro.filtroTipoDoc}`);
        if (filtro.filtroNumero) partes.push(`Nº: ${filtro.filtroNumero}`);
        if (filtro.filtroAno) partes.push(`Ano: ${filtro.filtroAno}`);
        if (filtro.filtroInteressado) partes.push(`Interessado: ${filtro.filtroInteressado}`);
        return partes.length > 0 ? partes.join(', ') : 'Filtro básico';
    }
    
    /**
     * Salva o filtro atual como favorito
     */
    salvarFiltroAtual() {
        // Verifica se há filtros ativos
        const temFiltros = this.temFiltrosAtivos() || (this.termoBusca && this.termoBusca.trim() !== '');
        
        if (!temFiltros) {
            this.mostrarToast('Nenhum filtro aplicado para salvar', 'warning');
            return;
        }
        
        // Solicita nome do filtro
        const nomeFiltro = prompt('Digite um nome para este filtro:');
        if (!nomeFiltro || nomeFiltro.trim() === '') {
            return;
        }
        
        try {
            // Carrega filtros existentes
            const filtrosSalvos = localStorage.getItem(TramitacaoEmailStyle.FILTROS_SALVOS_KEY);
            let filtros = filtrosSalvos ? JSON.parse(filtrosSalvos) : [];
            
            // Cria novo filtro
            const novoFiltro = {
                id: Date.now().toString(),
                nome: nomeFiltro.trim(),
                dataCriacao: new Date().toISOString(),
                filtroTipo: this.filtroTipo || 'TODOS',
                termoBusca: this.termoBusca || '',
                filtroTipoDoc: $('#filtro-tipo-documento').val() || '',
                filtroNumero: $('#filtro-numero').val() || '',
                filtroAno: $('#filtro-ano').val() || '',
                filtroInteressado: $('#filtro-interessado').val() || ''
            };
            
            // Adiciona no início da lista (mais recente primeiro)
            filtros.unshift(novoFiltro);
            
            // Limita a 20 filtros salvos
            if (filtros.length > 20) {
                filtros = filtros.slice(0, 20);
            }
            
            // Salva no localStorage
            localStorage.setItem(TramitacaoEmailStyle.FILTROS_SALVOS_KEY, JSON.stringify(filtros));
            
            // Atualiza dropdown
            this.atualizarDropdownFiltrosSalvos(filtros);
            
            this.mostrarToast(`Filtro "${nomeFiltro.trim()}" salvo com sucesso`, 'success');
        } catch (e) {
            console.error('Erro ao salvar filtro:', e);
            this.mostrarToast('Erro ao salvar filtro', 'error');
        }
    }
    
    /**
     * Carrega um filtro salvo
     */
    carregarFiltroSalvo(id) {
        try {
            if (!id) {
                console.error('ID do filtro não fornecido');
                this.mostrarToast('Erro ao carregar filtro: ID não fornecido', 'error');
                return;
            }
            
            const filtrosSalvos = localStorage.getItem(TramitacaoEmailStyle.FILTROS_SALVOS_KEY);
            if (!filtrosSalvos) {
                this.mostrarToast('Nenhum filtro salvo encontrado', 'warning');
                return;
            }
            
            const filtros = JSON.parse(filtrosSalvos);
            // Converte ID para string para comparação (pode vir como número ou string)
            const idStr = String(id);
            const filtro = filtros.find(f => String(f.id) === idStr);
            
            if (!filtro) {
                console.error('Filtro não encontrado. ID:', id, 'Filtros disponíveis:', filtros.map(f => f.id));
                this.mostrarToast('Filtro não encontrado', 'error');
                // Recarrega o dropdown caso tenha sido removido externamente
                this.carregarFiltrosSalvos();
                return;
            }
            
            // Aplica os valores do filtro
            this.filtroTipo = filtro.filtroTipo || 'TODOS';
            $('#filtro-tipo-processo').val(this.filtroTipo);
            
            this.termoBusca = filtro.termoBusca || '';
            $('#busca-rapida').val(this.termoBusca);
            
            $('#filtro-tipo-documento').val(filtro.filtroTipoDoc || '');
            $('#filtro-numero').val(filtro.filtroNumero || '');
            $('#filtro-ano').val(filtro.filtroAno || '');
            $('#filtro-interessado').val(filtro.filtroInteressado || '');
            
            // Fecha o dropdown
            const dropdown = bootstrap.Dropdown.getInstance(document.getElementById('btn-filtros-salvos'));
            if (dropdown) {
                dropdown.hide();
            }
            
            // Aplica os filtros
            this.aplicarFiltros();
            
            this.mostrarToast(`Filtro "${filtro.nome}" carregado`, 'success');
        } catch (e) {
            console.error('Erro ao carregar filtro:', e);
            this.mostrarToast('Erro ao carregar filtro', 'error');
        }
    }
    
    /**
     * Remove um filtro salvo
     */
    removerFiltroSalvo(id) {
        try {
            const filtrosSalvos = localStorage.getItem(TramitacaoEmailStyle.FILTROS_SALVOS_KEY);
            if (!filtrosSalvos) return;
            
            const filtros = JSON.parse(filtrosSalvos);
            const filtroRemovido = filtros.find(f => f.id === id);
            
            if (!filtroRemovido) return;
            
            // Remove o filtro
            const novosFiltros = filtros.filter(f => f.id !== id);
            
            // Salva no localStorage
            localStorage.setItem(TramitacaoEmailStyle.FILTROS_SALVOS_KEY, JSON.stringify(novosFiltros));
            
            // Atualiza dropdown
            this.atualizarDropdownFiltrosSalvos(novosFiltros);
            
            this.mostrarToast(`Filtro "${filtroRemovido.nome}" removido`, 'success');
        } catch (e) {
            console.error('Erro ao remover filtro:', e);
            this.mostrarToast('Erro ao remover filtro', 'error');
        }
    }
    
    /**
     * Ver detalhes do despacho (abre PDF em modal e registra visualização/recebimento se necessário)
     * IMPORTANTE: Só registra visualização/recebimento APÓS o PDF abrir com sucesso
     */
    verDetalhesTramitacao(cod_tramitacao, tipo) {
        if (!cod_tramitacao || !tipo) {
            this.mostrarToast('Erro', 'Dados incompletos para visualizar detalhes', 'error');
            return;
        }
        
        // Tenta obter dados do processo atual (se disponível) para evitar chamada extra
        const processo = this.processos.find(p => p.cod_tramitacao == cod_tramitacao);
        let jaVisualizada = false;
        let jaRecebida = false;
        
        if (processo) {
            // Usa dados do processo se disponível
            jaVisualizada = processo.dat_visualizacao && String(processo.dat_visualizacao).trim() !== '';
            jaRecebida = processo.dat_recebimento && String(processo.dat_recebimento).trim() !== '';
        }
        
        // Se não encontrou no processo ou precisa verificar, busca dados da tramitação
        if (!processo || (!jaVisualizada && !jaRecebida)) {
            this.obterDadosTramitacao(cod_tramitacao, tipo, (dados) => {
                if (dados.erro) {
                    this.mostrarToast('Erro', dados.erro, 'error');
                    return;
                }
                
                // Verifica se já foi visualizada e recebida
                jaVisualizada = dados.dat_visualizacao && String(dados.dat_visualizacao).trim() !== '';
                jaRecebida = dados.dat_recebimento && String(dados.dat_recebimento).trim() !== '';
                
                // Se já foi visualizada E recebida, apenas abre o PDF sem registrar
                if (jaVisualizada && jaRecebida) {
                    this._abrirPDFDespacho(cod_tramitacao, tipo, false); // false = não precisa registrar
                } else {
                    // Se ainda não foi visualizada/recebida, abre PDF primeiro e registra APÓS sucesso
                    this._abrirPDFDespacho(cod_tramitacao, tipo, true); // true = precisa registrar após abrir
                }
            });
        } else {
            // Já tem os dados do processo, usa diretamente
            if (jaVisualizada && jaRecebida) {
                this._abrirPDFDespacho(cod_tramitacao, tipo, false); // false = não precisa registrar
            } else {
                // Se ainda não foi visualizada/recebida, abre PDF primeiro e registra APÓS sucesso
                this._abrirPDFDespacho(cod_tramitacao, tipo, true); // true = precisa registrar após abrir
            }
        }
    }
    
    /**
     * Abre PDF do despacho no modal
     * @param {number} cod_tramitacao - Código da tramitação
     * @param {string} tipo - Tipo da tramitação (MATERIA ou DOCUMENTO)
     * @param {boolean} registrarAposSucesso - Se true, registra visualização/recebimento APÓS o PDF abrir com sucesso
     */
    _abrirPDFDespacho(cod_tramitacao, tipo, registrarAposSucesso = false) {
        // Obtém link do PDF e abre no modal
        $.ajax({
            url: `${PORTAL_URL}/tramitacao_obter_pdf_despacho_json`,
            method: 'GET',
            data: { cod_tramitacao: cod_tramitacao, tipo: tipo },
            success: (response) => {
                const dados = typeof response === 'string' ? JSON.parse(response) : response;
                if (dados.erro) {
                    this.mostrarToast('Erro', dados.erro, 'error');
                    return; // Não registra se houver erro
                } else if (dados.link_pdf && dados.pdf_existe) {
                    // Abre PDF no modal iFrameModal
                    const $modal = $('#iFrameModal');
                    if ($modal.length === 0) {
                        this.mostrarToast('Erro', 'Modal não encontrado no DOM', 'error');
                        return; // Não registra se modal não existir
                    }
                    
                    // Define título do modal
                    $modal.find('.modal-title').text('Despacho da Tramitação');
                    
                    // Define src do iframe
                    const $iframe = $modal.find('.modal-body iframe');
                    if ($iframe.length === 0) {
                        this.mostrarToast('Erro', 'Iframe não encontrado no modal', 'error');
                        return; // Não registra se iframe não existir
                    }
                    
                    $iframe.attr('src', dados.link_pdf);
                    
                    // ✅ IMPORTANTE: Remove TODOS os handlers do evento hidden.bs.modal ANTES de adicionar o nosso
                    // Isso garante que handlers globais (como o do js_slot.dtml) não executem e causem reload
                    $modal.off('hidden.bs.modal');
                    
                    // ✅ IMPORTANTE: Event handler para limpar iframe ao fechar, SEM recarregar a página
                    // Usa prioridade alta (primeiro handler) para garantir que execute antes de qualquer outro
                    $modal.on('hidden.bs.modal', function(e) {
                        // Limpa o src do iframe para evitar que ele continue carregando em background
                        $iframe.attr('src', '');
                        // IMPORTANTE: Impede que outros handlers sejam executados e causem reload
                        e.stopImmediatePropagation();
                        e.preventDefault();
                        return false;
                    });
                    
                    // Abre modal usando Bootstrap
                    let modalInstance = null;
                    if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                        modalInstance = new bootstrap.Modal($modal[0]);
                        modalInstance.show();
                    } else {
                        $modal.modal('show');
                    }
                    
                    // ✅ CORRETO: Só registra visualização/recebimento APÓS o PDF abrir com sucesso
                    if (registrarAposSucesso) {
                        // Aguarda um pequeno delay para garantir que o modal abriu
                        setTimeout(() => {
                            this._registrarVisualizacaoERecebimento(cod_tramitacao, tipo, () => {
                                // Após registrar, atualiza a lista para refletir as mudanças
                                // Mas mantém o processo visível até que o usuário feche o modal ou recarregue
                                console.debug('Visualização e recebimento registrados para tramitação', cod_tramitacao);
                            });
                        }, 500); // 500ms de delay para garantir que o modal abriu
                    }
                } else {
                    // PDF não existe ou não está disponível
                    const mensagem = dados.mensagem || 'PDF do despacho não está disponível';
                    this.mostrarToast('Informação', mensagem, 'info');
                    return; // Não registra se PDF não existir
                }
            },
            error: (xhr) => {
                const erro = xhr.responseJSON?.erro || 'Erro ao obter PDF do despacho';
                this.mostrarToast('Erro', erro, 'error');
                return; // Não registra se houver erro na requisição
            }
        });
    }
    
    /**
     * Registra visualização e recebimento da tramitação
     * IMPORTANTE: Não atualiza a lista automaticamente para evitar que o processo desapareça
     * A lista será atualizada apenas quando o usuário fechar o modal ou recarregar a página
     */
    _registrarVisualizacaoERecebimento(cod_tramitacao, tipo, callback) {
        // Registra visualização
        this._registrarVisualizacaoTramitacao(cod_tramitacao, tipo, () => {
            // Após visualização, registra recebimento
            $.ajax({
                url: `${PORTAL_URL}/tramitacao_receber_json`,
                method: 'POST',
                data: { cod_tramitacao: cod_tramitacao, tipo: tipo },
                success: (response) => {
                    const dados = typeof response === 'string' ? JSON.parse(response) : response;
                    if (dados.erro) {
                        // Se houver erro, loga mas continua (não é crítico)
                        console.warn('Erro ao registrar recebimento:', dados.erro);
                    } else {
                        console.debug('Recebimento registrado com sucesso para tramitação', cod_tramitacao);
                        // Atualiza o processo local para refletir as mudanças (mas não remove da lista)
                        const processo = this.processos.find(p => p.cod_tramitacao == cod_tramitacao);
                        if (processo) {
                            processo.dat_visualizacao = dados.dat_visualizacao || new Date().toISOString().split('T')[0];
                            processo.dat_recebimento = dados.dat_recebimento || new Date().toISOString().split('T')[0];
                        }
                    }
                    // Sempre chama callback (continua mesmo se não registrar recebimento)
                    if (callback) callback();
                },
                error: (xhr) => {
                    // Se falhar, loga mas continua (não é crítico)
                    const erro = xhr.responseJSON?.erro || 'Erro ao registrar recebimento';
                    console.warn('Erro ao registrar recebimento (continuando mesmo assim):', erro);
                    // Chama callback mesmo com erro (recebimento não é bloqueante)
                    if (callback) callback();
                }
            });
        });
    }
    
    /**
     * Obtém dados completos de uma tramitação
     */
    obterDadosTramitacao(cod_tramitacao, tipo, callback) {
        $.ajax({
            url: `${PORTAL_URL}/tramitacao_individual_obter_json`,
            method: 'GET',
            data: { cod_tramitacao: cod_tramitacao, tipo: tipo },
            success: (response) => {
                const dados = typeof response === 'string' ? JSON.parse(response) : response;
                callback(dados);
            },
            error: () => {
                callback({});
            }
        });
    }
}

/**
 * Gerencia sidebars de tramitação (individual e lote)
 * Integrado com TramitacaoEmailStyle
 */
class TramitacaoSidebarManager {
    constructor(tramitacaoApp) {
        this.app = tramitacaoApp;
        this.sidebarIndividual = null;
        this.sidebarLote = null;
        // Flags para controlar proteção contra fechamento acidental
        this.protecaoFechamentoIndividual = true;
        this.protecaoFechamentoLote = true;
        // Flag para prevenir múltiplos cliques no backdrop
        this.processandoCliqueBackdrop = false;
        // Flag para indicar se rascunho foi salvo (para atualizar lista ao fechar)
        this.rascunhoSalvo = false;
        // Estado inicial do formulário para comparação (detectar alterações)
        this.estadoInicialFormulario = {
            individual: null,
            lote: null
        };
        // Flag para permitir fechamento programático sem bloqueios/recursão
        this._bypassCloseGuard = {
            individual: false,
            lote: false
        };

        // Handlers (para evitar duplicação): carregar usuários quando unidade destino muda
        this._handlerUnidadeDestinoChange = {
            individual: null,
            lote: null
        };
        this.init();
    }

    /**
     * Fecha o offcanvas de forma "forçada", desarmando proteções temporariamente.
     * Isso evita loops onde o próprio handler de hide impede o hide().
     */
    _forceFecharSidebar(tipo) {
        const isIndividual = tipo === 'individual';
        const sidebarId = isIndividual ? 'tramitacaoIndividualOffcanvas' : 'tramitacaoLoteOffcanvas';
        const sidebarEl = document.getElementById(sidebarId);
        if (!sidebarEl || typeof bootstrap === 'undefined') return;

        this._bypassCloseGuard[tipo] = true;
        if (isIndividual) this.protecaoFechamentoIndividual = false;
        else this.protecaoFechamentoLote = false;

        try {
            bootstrap.Offcanvas.getOrCreateInstance(sidebarEl).hide();
        } catch (e) {
            const inst = isIndividual ? this.sidebarIndividual : this.sidebarLote;
            if (inst && typeof inst.hide === 'function') {
                try { inst.hide(); } catch (_) {}
            }
        }

        // Fallback duro: se por algum motivo o Bootstrap não fechar, fecha manualmente.
        setTimeout(() => {
            if (sidebarEl.classList && sidebarEl.classList.contains('show')) {
                this._fecharOffcanvasManual(sidebarEl);
            }
        }, 50);
    }

    _fecharOffcanvasManual(sidebarEl) {
        // Evita warning do Chrome: não pode aplicar aria-hidden num ancestral com foco dentro
        this._moverFocoParaForaDoOffcanvas(sidebarEl);

        try {
            // Remove classes/transições e volta ao estado "hidden" (sem usar display:none).
            // IMPORTANTE: `display:none` impede o Bootstrap de reabrir em alguns casos.
            sidebarEl.classList.remove('show', 'showing', 'hiding');
            sidebarEl.style.visibility = 'hidden';
            sidebarEl.style.removeProperty('display');
            sidebarEl.setAttribute('aria-hidden', 'true');
            sidebarEl.removeAttribute('aria-modal');
            sidebarEl.removeAttribute('role');
        } catch (_) {}

        // Remove backdrop(s)
        try {
            document.querySelectorAll('.offcanvas-backdrop').forEach((b) => b.remove());
        } catch (_) {}

        // Restaura body
        try {
            document.body.classList.remove('offcanvas-open');
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
        } catch (_) {}
    }

    /**
     * Normaliza o elemento do offcanvas antes de reabrir (recupera de estados quebrados).
     * Ex.: quando um fechamento manual deixou estilos/classes residuais.
     */
    _prepararOffcanvasParaShow(sidebarEl) {
        if (!sidebarEl) return;
        try {
            sidebarEl.classList.remove('show', 'showing', 'hiding');
            sidebarEl.style.removeProperty('display');
            sidebarEl.style.removeProperty('visibility');
            sidebarEl.removeAttribute('aria-hidden');
        } catch (_) {}

        // ✅ Evita conflitos por IDs duplicados entre individual e lote:
        // os formulários do backend usam ids fixos (ex.: field_radTI_G, field_file_nom_arquivo),
        // então o HTML do outro sidebar NÃO pode ficar no DOM.
        this._limparOutroSidebarSeNecessario(sidebarEl);

        // Remove backdrops órfãos e restaura body, se necessário
        try {
            document.querySelectorAll('.offcanvas-backdrop').forEach((b) => b.remove());
        } catch (_) {}
        try {
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
        } catch (_) {}
    }

    /**
     * Limpa o HTML do outro sidebar (se estiver fechado) para evitar IDs duplicados no DOM.
     */
    _limparOutroSidebarSeNecessario(sidebarEl) {
        try {
            const isIndividual = sidebarEl && sidebarEl.id === 'tramitacaoIndividualOffcanvas';
            const otherId = isIndividual ? 'tramitacaoLoteOffcanvas' : 'tramitacaoIndividualOffcanvas';
            const otherBodyId = isIndividual ? 'tramitacaoLoteOffcanvasBody' : 'tramitacaoIndividualOffcanvasBody';
            const otherEl = document.getElementById(otherId);
            const otherBody = document.getElementById(otherBodyId);
            if (!otherBody) return;

            // Só limpa se o outro offcanvas NÃO estiver visível.
            if (otherEl && otherEl.classList && otherEl.classList.contains('show')) return;

            if ((otherBody.innerHTML || '').trim() !== '') {
                if (isIndividual) this.limparFormularioLote();
                else this.limparFormularioIndividual();
            }
        } catch (_) {}
    }

    limparFormularioIndividual() {
        this._limparFormulario('individual');
    }

    limparFormularioLote() {
        this._limparFormulario('lote');
    }

    _limparFormulario(tipo) {
        const isIndividual = tipo === 'individual';
        const bodyId = isIndividual ? 'tramitacaoIndividualOffcanvasBody' : 'tramitacaoLoteOffcanvasBody';
        const body = document.getElementById(bodyId);

        // Reseta estado inicial (evita "dados não salvos" na próxima abertura)
        try { this.estadoInicialFormulario[tipo] = null; } catch (_) {}

        if (!body) return;

        // Destrói TomSelect dentro do container
        try {
            Array.from(body.querySelectorAll('select')).forEach((sel) => {
                try { if (sel && sel.tomselect) sel.tomselect.destroy(); } catch (_) {}
            });
        } catch (_) {}

        // Destrói Bootstrap Datepicker dentro do container
        try {
            if (typeof jQuery !== 'undefined' && typeof jQuery.fn.datepicker !== 'undefined') {
                jQuery(body).find('input.datepicker, input[name*="txt_dat_fim_prazo"]').each(function () {
                    try { jQuery(this).datepicker('destroy'); } catch (_) {}
                });
            }
        } catch (_) {}

        // Destrói Trumbowyg dentro do container
        try {
            if (typeof jQuery !== 'undefined' && typeof jQuery.fn.trumbowyg !== 'undefined') {
                jQuery(body).find('textarea').each(function () {
                    try {
                        const $ta = jQuery(this);
                        if ($ta.data('trumbowyg')) $ta.trumbowyg('destroy');
                    } catch (_) {}
                });
            }
        } catch (_) {}

        // Remove HTML do formulário (remove IDs duplicados do DOM)
        try { body.innerHTML = ''; } catch (_) {}
    }

    /**
     * Move o foco para fora do offcanvas antes de marcá-lo como aria-hidden.
     * Isso evita: "Blocked aria-hidden on an element because its descendant retained focus".
     */
    _moverFocoParaForaDoOffcanvas(sidebarEl) {
        try {
            if (!sidebarEl) return;
            const active = document.activeElement;
            if (!active || active === document.body) return;
            if (!sidebarEl.contains(active)) return;

            // Cria (uma vez) um alvo focável fora do offcanvas
            let sentinel = document.getElementById('tramitacao-offcanvas-focus-sentinel');
            if (!sentinel) {
                sentinel = document.createElement('div');
                sentinel.id = 'tramitacao-offcanvas-focus-sentinel';
                sentinel.tabIndex = -1;
                sentinel.setAttribute('aria-hidden', 'true');
                // mantém fora do fluxo visual
                sentinel.style.position = 'fixed';
                sentinel.style.left = '-9999px';
                sentinel.style.top = '0';
                document.body.appendChild(sentinel);
            }

            // Tenta blur e foca o sentinel
            try { active.blur(); } catch (_) {}
            try { sentinel.focus({ preventScroll: true }); } catch (_) { try { sentinel.focus(); } catch (__) {} }
        } catch (_) {}
    }

    // ---------------------------------------------------------------------
    // Carregamento dinâmico de usuários (dependente da unidade de destino)
    // ---------------------------------------------------------------------

    _obterBodyFormulario(tipoSidebar) {
        const bodyId = tipoSidebar === 'lote' ? 'tramitacaoLoteOffcanvasBody' : 'tramitacaoIndividualOffcanvasBody';
        return document.getElementById(bodyId);
    }

    _obterSelectUnidadeDestino(body) {
        if (!body) return null;
        return body.querySelector('#field_lst_cod_unid_tram_dest, #lst_cod_unid_tram_dest');
    }

    _obterSelectUsuarioDestino(body) {
        if (!body) return null;
        return body.querySelector('#field_lst_cod_usuario_dest, #lst_cod_usuario_dest');
    }

    _bindCarregamentoUsuariosDestino(tipoSidebar, tentativa = 0) {
        const body = this._obterBodyFormulario(tipoSidebar);
        const selectUnidDest = this._obterSelectUnidadeDestino(body);
        if (!selectUnidDest) {
            if (tentativa < 8) {
                setTimeout(() => this._bindCarregamentoUsuariosDestino(tipoSidebar, tentativa + 1), 250);
            }
            return;
        }

        // Remove handler anterior para evitar duplicação
        const handlerAnterior = this._handlerUnidadeDestinoChange?.[tipoSidebar] || null;
        if (handlerAnterior) {
            try { selectUnidDest.removeEventListener('change', handlerAnterior); } catch (_) {}
        }

        const handler = () => {
            const unidDest = (selectUnidDest.value || '').toString();
            this.carregarUsuariosDestino(tipoSidebar, unidDest);
        };

        this._handlerUnidadeDestinoChange[tipoSidebar] = handler;
        selectUnidDest.addEventListener('change', handler);

        // Se já há valor selecionado, dispara carregamento imediatamente
        if (selectUnidDest.value) {
            handler();
        } else {
            // Se não há unidade selecionada, garante que o usuário destino esteja limpo/desabilitado
            this.carregarUsuariosDestino(tipoSidebar, '');
        }
    }

    carregarUsuariosDestino(tipoSidebar, unidDest, codUsuarioSelecionado = null) {
        const body = this._obterBodyFormulario(tipoSidebar);
        const selectUsuarioEl = this._obterSelectUsuarioDestino(body);
        if (!selectUsuarioEl) return;

        const resetUsuarioSelect = () => {
            try {
                if (selectUsuarioEl.tomselect) {
                    selectUsuarioEl.tomselect.destroy();
                }
            } catch (_) {}
            try {
                selectUsuarioEl.innerHTML = '';
                const opt = document.createElement('option');
                opt.value = '';
                // Não exibe "Selecione" como opção; placeholder do TomSelect cobre isso
                opt.textContent = '';
                selectUsuarioEl.appendChild(opt);
                selectUsuarioEl.disabled = true;
            } catch (_) {}
        };

        if (!unidDest) {
            resetUsuarioSelect();
            return;
        }

        // Estado "carregando" (sem inserir opção visível "Selecione")
        resetUsuarioSelect();

        $.ajax({
            url: `${PORTAL_URL}/tramitacao_usuarios_json`,
            method: 'POST',
            data: { svalue: unidDest },
            success: (response) => {
                const usuarios = typeof response === 'string' ? JSON.parse(response) : response;

                try {
                    if (selectUsuarioEl.tomselect) {
                        selectUsuarioEl.tomselect.destroy();
                    }
                } catch (_) {}

                selectUsuarioEl.innerHTML = '';

                // Opção vazia no início
                const optVazio = document.createElement('option');
                optVazio.value = '';
                // mantém vazio para não aparecer "Selecione" na lista
                optVazio.textContent = '';
                selectUsuarioEl.appendChild(optVazio);

                if (Array.isArray(usuarios)) {
                    usuarios.forEach((usr) => {
                        const val = (usr && usr.id != null) ? String(usr.id) : '';
                        const txt = (usr && usr.name) ? String(usr.name) : 'Selecione';
                        if (!val) return;
                        const opt = document.createElement('option');
                        opt.value = val;
                        opt.textContent = txt;
                        selectUsuarioEl.appendChild(opt);
                    });
                }

                selectUsuarioEl.disabled = false;

                if (typeof TomSelect !== 'undefined') {
                    selectUsuarioEl.tomselect = new TomSelect(selectUsuarioEl, {
                        placeholder: 'Selecione o usuário de destino...',
                        allowEmptyOption: true,
                        create: false,
                        sortField: { field: 'text', direction: 'asc' },
                        plugins: ['clear_button']
                    });

                    if (codUsuarioSelecionado) {
                        selectUsuarioEl.tomselect.setValue(codUsuarioSelecionado, false);
                    } else {
                        selectUsuarioEl.tomselect.setValue('', true);
                    }
                }
            },
            error: (xhr, status, error) => {
                console.error('Erro ao carregar usuários da unidade:', status, error);
                resetUsuarioSelect();
            }
        });
    }
    
    /**
     * Força fechamento de calendários (flatpickr/datepicker) quando o usuário clica fora.
     * Evita que o calendário "prenda" o foco dentro do offcanvas.
     */
    forcarFechamentoFlatpickr(e = null) {
        try {
            // Se o clique foi dentro de um calendário/datepicker, não fecha
            const target = e?.target || null;
            if (target) {
                const dentroDeFlatpickr = !!(target.closest && target.closest('.flatpickr-calendar'));
                const dentroDeDatepicker = !!(target.closest && (target.closest('.datepicker') || target.closest('.ui-datepicker')));
                if (dentroDeFlatpickr || dentroDeDatepicker) {
                    return;
                }
            }
            
            // Fecha flatpickr em inputs conhecidos
            const ids = [
                'field_txt_dat_fim_prazo',
                'txt_dat_fim_prazo',
                'field_txt_dat_fim_prazo_lote',
                'txt_dat_fim_prazo_lote'
            ];
            
            ids.forEach((id) => {
                const el = document.getElementById(id);
                if (!el) return;
                
                // flatpickr mantém referência em el._flatpickr
                if (el._flatpickr && typeof el._flatpickr.close === 'function') {
                    try { el._flatpickr.close(); } catch (_) {}
                }
                
                // bootstrap-datepicker / jquery-ui datepicker (se existir)
                if (typeof $ !== 'undefined') {
                    try {
                        const $el = $(el);
                        if (typeof $el.datepicker === 'function') {
                            $el.datepicker('hide');
                        }
                    } catch (_) {}
                }
            });
        } catch (err) {
            // Não quebra o fluxo do usuário por causa do fechamento
            console.warn('Falha ao forçar fechamento do calendário:', err);
        }
    }

    /**
     * Fecha calendários antes de fechar o offcanvas.
     * Mantém compatibilidade com chamadas antigas do código.
     */
    _fecharCalendarioFlatpickr() {
        // Chama o método mais robusto (não depende do evento)
        this.forcarFechamentoFlatpickr(null);
    }
    
    // ---------------------------------------------------------------------
    // Ações de formulário (wrappers). Evitam TypeError e delegam ao app quando existir.
    // ---------------------------------------------------------------------
    salvarRascunho() {
        if (this.app && typeof this.app.salvarRascunho === 'function') {
            return this.app.salvarRascunho();
        }
        if (this.app && typeof this.app.mostrarToast === 'function') {
            this.app.mostrarToast('Atenção', 'Ação "Salvar rascunho" ainda não está disponível neste contexto.', 'warning');
        }
    }
    
    enviarTramitacao() {
        if (this.app && typeof this.app.enviarTramitacao === 'function') {
            return this.app.enviarTramitacao();
        }
        if (this.app && typeof this.app.mostrarToast === 'function') {
            this.app.mostrarToast('Atenção', 'Ação "Enviar tramitação" ainda não está disponível neste contexto.', 'warning');
        }
    }
    
    retomarTramitacao(codTramitacao, tipo) {
        if (this.app && typeof this.app.retomarTramitacao === 'function') {
            return this.app.retomarTramitacao(codTramitacao, tipo);
        }
        if (this.app && typeof this.app.mostrarToast === 'function') {
            this.app.mostrarToast('Atenção', 'Ação "Retomar tramitação" ainda não está disponível neste contexto.', 'warning');
        }
    }
    
    tramitarLote() {
        if (this.app && typeof this.app.tramitarLote === 'function') {
            return this.app.tramitarLote();
        }
        if (this.app && typeof this.app.mostrarToast === 'function') {
            this.app.mostrarToast('Atenção', 'Ação "Tramitar em lote" ainda não está disponível neste contexto.', 'warning');
        }
    }
    
    // TomSelect: seletor único usado pelo sistema.
    
    /**
     * Inicializa TomSelect em um elemento
     * @param {string} selector - Seletor do elemento
     * @param {string} placeholder - Texto do placeholder
     * @param {jQuery} dropdownParent - Elemento pai para o dropdown (ignorado, mantido para compatibilidade)
     * @param {boolean} allowEmptyOption - Permite opção em branco (padrão: true)
     */
    _inicializarTomSelect(selector, placeholder = 'Selecione...', dropdownParent = null, allowEmptyOption = true) {
        const $el = $(selector);
        if (!$el.length) {
            console.warn(`Elemento não encontrado: ${selector}`);
            return null;
        }
        
        const el = $el[0];
        
        // Destrói TomSelect existente
        if (el.tomselect) {
            el.tomselect.destroy();
        }
        
        // Usa TomSelect (obrigatório)
        if (typeof TomSelect === 'undefined') {
            console.error('TomSelect não está disponível! Certifique-se de que o script foi carregado.');
            return null;
        }
        
        const options = {
            placeholder: placeholder,
            allowEmptyOption: allowEmptyOption,
            create: false,
            sortField: {
                field: 'text',
                direction: 'asc'
            }
        };
        
        if (allowEmptyOption) {
            options.plugins = ['clear_button'];
        }
        
        el.tomselect = new TomSelect(el, options);
        return el.tomselect;
    }
    
    // TomSelect: não existe inicializador alternativo.

    /**
     * Atualiza visibilidade dos botões do formulário individual
     * @param {boolean} isEdicao - true quando existe cod_tramitacao (edição/rascunho)
     */
    _atualizarBotoesFormulario(isEdicao) {
        const btnSalvar = document.getElementById('btnSalvarRascunho');
        const btnEnviar = document.getElementById('btnEnviarTramitacao');
        if (!btnSalvar || !btnEnviar) return;
        
        // Em edição/rascunho, habilita botão de envio; em novo, mantém como fluxo "salvar rascunho"
        if (isEdicao) {
            btnEnviar.style.display = '';
        } else {
            btnEnviar.style.display = 'none';
        }
    }

    /**
     * Formata data para o formato de input (dd/mm/yyyy)
     */
    formatarDataParaInput(dataISO) {
        if (!dataISO) return '';
        
        try {
            const data = new Date(dataISO);
            if (isNaN(data.getTime())) {
                return dataISO; // Retorna original se não for uma data válida
            }
            
            const dia = data.getDate().toString().padStart(2, '0');
            const mes = (data.getMonth() + 1).toString().padStart(2, '0');
            const ano = data.getFullYear();
            
            return `${dia}/${mes}/${ano}`;
        } catch (e) {
            return dataISO;
        }
    }
    
    /**
     * Obtém conteúdo do editor (Trumbowyg) com fallback para textarea
     * @param {string} tipo - 'individual' ou 'lote'
     */
    obterConteudoEditor(tipo = 'individual') {
        const ids = tipo === 'lote'
            ? ['#field_txa_txt_tramitacao_lote', '#txa_txt_tramitacao_lote']
            : ['#field_txa_txt_tramitacao', '#txa_txt_tramitacao'];
        
        for (const id of ids) {
            try {
                const $el = $(id);
                if (!$el.length) continue;
                
                // Se Trumbowyg estiver disponível, tenta obter HTML do editor
                if (typeof jQuery !== 'undefined' && typeof jQuery.fn.trumbowyg !== 'undefined') {
                    try {
                        const html = $el.trumbowyg('html');
                        if (typeof html === 'string') return html;
                    } catch (e) {
                        // Se não estiver inicializado, cai no fallback .val()
                    }
                }
                
                const v = $el.val();
                if (typeof v === 'string') return v;
            } catch (e) {
                // continua tentando próximo id
            }
        }
        return '';
    }
    
    /**
     * Define conteúdo do editor (Trumbowyg) com fallback para textarea
     */
    definirConteudoEditor(html, tipo = 'individual') {
        const ids = tipo === 'lote'
            ? ['#field_txa_txt_tramitacao_lote', '#txa_txt_tramitacao_lote']
            : ['#field_txa_txt_tramitacao', '#txa_txt_tramitacao'];
        
        for (const id of ids) {
            const $el = $(id);
            if (!$el.length) continue;
            
            if (typeof jQuery !== 'undefined' && typeof jQuery.fn.trumbowyg !== 'undefined') {
                try {
                    $el.trumbowyg('html', html || '');
                    return;
                } catch (e) {
                    // fallback
                }
            }
            
            try {
                $el.val(html || '');
                return;
            } catch (e) {
                // tenta próximo
            }
        }
    }
    
    /**
     * Inicializa Trumbowyg no textarea do formulário individual/lote
     * @param {string|null} textareaId - id do textarea (sem '#'); se null, autodetect
     */
    inicializarTrumbowyg(textareaId = null, tipo = 'individual') {
        if (typeof jQuery === 'undefined' || typeof jQuery.fn.trumbowyg === 'undefined') {
            console.warn('Trumbowyg não está disponível para inicialização.');
            return;
        }
        
        const ids = textareaId
            ? [`#${textareaId}`]
            : (tipo === 'lote'
                ? ['#field_txa_txt_tramitacao_lote', '#txa_txt_tramitacao_lote']
                : ['#field_txa_txt_tramitacao', '#txa_txt_tramitacao']);
        
        for (const id of ids) {
            const $el = jQuery(id);
            if (!$el.length) continue;
            
            // destrói se já estiver inicializado
            try { $el.trumbowyg('destroy'); } catch (e) {}
            
            try {
                $el.trumbowyg({
                    lang: 'pt_br',
                    btns: [
                        ['strong', 'em', 'del'],
                        ['unorderedList', 'orderedList'],
                        ['link'],
                        ['removeformat'],
                        ['viewHTML']
                    ],
                    autogrow: true
                });
                return;
            } catch (e) {
                console.warn('Falha ao inicializar Trumbowyg em', id, e);
            }
        }
    }
    
    /**
     * Inicializa o datepicker (Bootstrap Datepicker) no campo de data com retry simples.
     *
     * Observação: mantemos o nome do método por compatibilidade com chamadas antigas,
     * porém **não usamos Flatpickr** (pedido do projeto).
     */
    _inicializarFlatpickrComTimeout(inputEl, tentativa = 0) {
        if (!inputEl) return;
        
        // aguarda DOM ficar estável
        if (!document.body.contains(inputEl) && tentativa < 5) {
            setTimeout(() => this._inicializarFlatpickrComTimeout(inputEl, tentativa + 1), 100);
            return;
        }
        
        // ✅ Bootstrap Datepicker (se existir) — padrão oficial do projeto
        if (typeof $ !== 'undefined' && typeof $().datepicker !== 'undefined') {
            try {
                const hoje = new Date();
                hoje.setHours(0, 0, 0, 0);

                const $el = $(inputEl);
                // Destrói instância anterior (se houver)
                $el.datepicker('destroy');
                $el.datepicker({
                    format: 'dd/mm/yyyy',
                    startDate: hoje, // ✅ bloqueia datas retroativas
                    autoclose: true,
                    todayHighlight: true,
                    language: 'pt-BR',
                    // Em offcanvas, o calendário pode ficar "atrás" se o z-index for baixo.
                    // container no body + zIndexOffset alto evita isso.
                    container: 'body',
                    zIndexOffset: 2000
                });

                // ✅ Garante validação também para digitação manual (não apenas pelo calendário)
                const parseBr = (s) => {
                    const m = String(s || '').trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
                    if (!m) return null;
                    const dd = parseInt(m[1], 10);
                    const mm = parseInt(m[2], 10);
                    const yyyy = parseInt(m[3], 10);
                    if (!dd || !mm || !yyyy) return null;
                    const d = new Date(yyyy, mm - 1, dd);
                    d.setHours(0, 0, 0, 0);
                    // valida round-trip (ex: 31/02 vira março)
                    if (d.getFullYear() !== yyyy || d.getMonth() !== (mm - 1) || d.getDate() !== dd) return null;
                    return d;
                };

                const validarNaoRetroativa = () => {
                    const val = $el.val();
                    const d = parseBr(val);
                    if (!d) return;
                    if (d < hoje) {
                        $el.val('');
                        try { $el.datepicker('update'); } catch (_) {}
                        if (this.app && typeof this.app.mostrarToast === 'function') {
                            this.app.mostrarToast('Atenção', 'A data de fim de prazo não pode ser retroativa.', 'warning');
                        } else {
                            console.warn('Data retroativa bloqueada:', val);
                        }
                    }
                };

                $el.off('.tramitacao-date');
                $el.on('changeDate.tramitacao-date', validarNaoRetroativa);
                $el.on('change.tramitacao-date', validarNaoRetroativa);
                return;
            } catch (e) {
                console.warn('Falha ao inicializar bootstrap-datepicker:', e);
            }
        }
    }
    
    _marcarCampoValido(selector) {
        const el = document.querySelector(selector);
        if (!el) return;
        el.classList.remove('is-invalid');
        el.classList.add('is-valid');
    }
    
    _marcarCampoInvalido(selector) {
        const el = document.querySelector(selector);
        if (!el) return;
        el.classList.remove('is-valid');
        el.classList.add('is-invalid');
    }
    
    /**
     * Configura validação simples em tempo real dos campos obrigatórios
     */
    _configurarValidacaoTempoReal() {
        const campos = [
            '#field_lst_cod_unid_tram_dest',
            '#field_lst_cod_status',
            '#field_txt_dat_fim_prazo'
        ];
        
        campos.forEach((sel) => {
            const el = document.querySelector(sel);
            if (!el) return;
            
            const validar = () => {
                const valor = (el.value ?? '').toString().trim();
                if (valor && valor !== '0') this._marcarCampoValido(sel);
                else this._marcarCampoInvalido(sel);
            };
            
            el.removeEventListener('change', validar);
            el.addEventListener('change', validar);
            el.removeEventListener('input', validar);
            el.addEventListener('input', validar);
        });
    }
    
    /**
     * Ativa estado de loading em um botão
     * @param {HTMLElement} botao - Elemento do botão
     * @param {string} textoLoading - Texto a ser exibido durante o loading
     * @returns {Object} Estado original do botão para restauração posterior
     */
    _ativarLoadingBotao(botao, textoLoading) {
        if (!botao) {
            return null;
        }
        
        const $botao = $(botao);
        const estadoOriginal = {
            disabled: $botao.prop('disabled'),
            html: $botao.html(),
            texto: $botao.text()
        };
        
        // Desabilita o botão
        $botao.prop('disabled', true);
        
        // Adiciona spinner e texto de loading
        $botao.html(`
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            ${textoLoading}
        `);
        
        return estadoOriginal;
    }
    
    /**
     * Desativa estado de loading em um botão, restaurando seu estado original
     * @param {HTMLElement} botao - Elemento do botão
     * @param {Object} estadoOriginal - Estado original retornado por _ativarLoadingBotao
     */
    _desativarLoadingBotao(botao, estadoOriginal) {
        if (!botao || !estadoOriginal) {
            return;
        }
        
        const $botao = $(botao);
        
        // Restaura estado original
        $botao.prop('disabled', estadoOriginal.disabled);
        $botao.html(estadoOriginal.html);
    }

    /**
     * Liga listeners do elemento Offcanvas (mesmo quando criado dinamicamente).
     * Isso garante que o fechamento via botão X/Cancelar dispare o fluxo correto.
     */
    _bindOffcanvasElementListeners(tipo) {
        if (typeof bootstrap === 'undefined') return;
        
        const isIndividual = tipo === 'individual';
        const sidebarId = isIndividual ? 'tramitacaoIndividualOffcanvas' : 'tramitacaoLoteOffcanvas';
        const sidebarEl = document.getElementById(sidebarId);
        if (!sidebarEl) return;
        
        if (sidebarEl.dataset && sidebarEl.dataset.tramitacaoBound === '1') return;
        if (sidebarEl.dataset) sidebarEl.dataset.tramitacaoBound = '1';
        
        const handlerHide = (e) => {
            // Se estamos fechando programaticamente, não bloqueia
            if (this._bypassCloseGuard && this._bypassCloseGuard[tipo]) {
                return;
            }
            const protecao = isIndividual ? this.protecaoFechamentoIndividual : this.protecaoFechamentoLote;
            if (!protecao) return;
            
            this._fecharCalendarioFlatpickr();
            
            if (this._temDadosNaoSalvos(tipo)) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                
                this._mostrarConfirmacaoFechamento(tipo, () => {
                    this._forceFecharSidebar(tipo);
                });
                
                return false;
            }
        };
        
        // Captura primeiro para conseguir prevenir
        sidebarEl.addEventListener('hide.bs.offcanvas', handlerHide, { capture: true, passive: false });
        // Backup
        sidebarEl.addEventListener('hide.bs.offcanvas', handlerHide, { passive: false });
        
        sidebarEl.addEventListener('hidden.bs.offcanvas', () => {
            if (isIndividual) {
                if (typeof this.limparFormularioIndividual === 'function') this.limparFormularioIndividual();
                this.protecaoFechamentoIndividual = true;
            } else {
                if (typeof this.limparFormularioLote === 'function') this.limparFormularioLote();
                this.protecaoFechamentoLote = true;
            }
        });
    }
    
    init() {
        // Inicializa sidebars Bootstrap Offcanvas
        // Nota: Se elementos não existirem ainda, serão inicializados quando necessário
        // Usa setTimeout para garantir que o DOM está completamente renderizado
        setTimeout(() => {
            const sidebarIndividualEl = document.getElementById('tramitacaoIndividualOffcanvas');
            if (sidebarIndividualEl && typeof bootstrap !== 'undefined') {
                try {
                    this.sidebarIndividual = new bootstrap.Offcanvas(sidebarIndividualEl);
                    this._bindOffcanvasElementListeners('individual');
                } catch (e) {
                    console.warn('Não foi possível inicializar sidebar individual na inicialização:', e);
                    // Tenta novamente quando necessário
                }
            } else {
                // Elemento será inicializado quando necessário
                if (typeof bootstrap === 'undefined') {
                    console.warn('Bootstrap não está disponível na inicialização. Será verificado quando necessário.');
                }
            }
            
            const sidebarLoteEl = document.getElementById('tramitacaoLoteOffcanvas');
            if (sidebarLoteEl && typeof bootstrap !== 'undefined') {
                try {
                    this.sidebarLote = new bootstrap.Offcanvas(sidebarLoteEl);
                    this._bindOffcanvasElementListeners('lote');
                } catch (e) {
                    console.warn('Não foi possível inicializar sidebar lote na inicialização:', e);
                    // Tenta novamente quando necessário
                }
            } else {
                // Elemento será inicializado quando necessário
            }
        }, 100); // Aguarda 100ms para garantir que o DOM está renderizado
        
        // Event listeners para fechamento
        this.setupEventListeners();
    }
    
    /**
     * Cria sidebar individual dinamicamente se não existir no DOM
     */
    _criarSidebarIndividual() {
        // Verifica novamente se o elemento existe
        let sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
        if (sidebarEl) {
            return sidebarEl;
        }
        
        // Cria o elemento dinamicamente
        console.warn('Criando sidebar individual dinamicamente');
        // IMPORTANTE: data-bs-focus="false" é OBRIGATÓRIO para que TomSelect, TinyMCE e Bootstrap Datepicker funcionem corretamente
        // dentro do offcanvas. Sem isso, o Bootstrap força o foco de volta para dentro do offcanvas,
        // impedindo que esses componentes recebam eventos de blur e causando bugs de foco.
        const sidebarHtml = `
       <div class="offcanvas offcanvas-end" 
            tabindex="-1" 
            id="tramitacaoIndividualOffcanvas"
            aria-labelledby="tramitacaoIndividualOffcanvasLabel"
            data-bs-scroll="true"
            data-bs-backdrop="static"
            data-bs-focus="false"
            style="width: 700px; max-width: 90vw;">
  <div class="offcanvas-header border-bottom bg-light">
    <h5 class="offcanvas-title fw-bold" id="tramitacaoIndividualOffcanvasLabel">
      <i class="mdi mdi-send text-primary" aria-hidden="true"></i>
      Tramitação de Processo
    </h5>
    <button type="button" 
            class="btn-close" 
            id="btnFecharSidebarIndividual"
            data-bs-dismiss="offcanvas"
            aria-label="Fechar"></button>
  </div>
  <div class="offcanvas-body" id="tramitacaoIndividualOffcanvasBody">
    <!-- Conteúdo carregado via AJAX -->
  </div>
  <div class="offcanvas-footer border-top p-3 bg-light">
    <div class="d-flex gap-2 justify-content-between">
      <button type="button" 
              class="btn btn-secondary" 
              id="btnCancelarIndividual"
              data-bs-dismiss="offcanvas">
        <i class="mdi mdi-close" aria-hidden="true"></i> Cancelar
      </button>
      <div class="d-flex gap-2">
        <button type="button" 
                class="btn btn-outline-primary" 
                id="btnSalvarRascunho">
          <i class="mdi mdi-content-save-outline" aria-hidden="true"></i> 
          Salvar
        </button>
        <button type="button" 
                class="btn btn-primary" 
                id="btnEnviarTramitacao"
                style="display: none;">
          <i class="mdi mdi-send" aria-hidden="true"></i> 
          Enviar Tramitação
        </button>
      </div>
    </div>
  </div>
</div>`;
        
        // Adiciona ao body
        try {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = sidebarHtml.trim();
            sidebarEl = tempDiv.firstElementChild;
            
            if (!sidebarEl) {
                console.error('Erro ao criar sidebar individual: firstElementChild é null');
                return null;
            }
            
            document.body.appendChild(sidebarEl);
            console.log('Sidebar individual criado dinamicamente com sucesso');
            return sidebarEl;
        } catch (e) {
            console.error('Erro ao criar sidebar individual dinamicamente:', e);
            return null;
        }
    }
    
    /**
     * Inicializa sidebar individual (método auxiliar)
     */
    _inicializarSidebarIndividual(sidebarEl) {
        if (typeof bootstrap === 'undefined') {
            console.error('Bootstrap não está disponível');
            this.app.mostrarToast('Erro', 'Bootstrap não está carregado. Verifique se o script está incluído.', 'error');
            return false;
        }
        try {
            this.sidebarIndividual = new bootstrap.Offcanvas(sidebarEl);
            this._bindOffcanvasElementListeners('individual');
            return true;
        } catch (e) {
            console.error('Erro ao inicializar sidebar:', e);
            this.app.mostrarToast('Erro', 'Erro ao inicializar sidebar: ' + e.message, 'error');
            return false;
        }
    }
    
    /**
     * Cria sidebar lote dinamicamente se não existir no DOM
     */
    _criarSidebarLote() {
        // Verifica novamente se o elemento existe
        let sidebarEl = document.getElementById('tramitacaoLoteOffcanvas');
        if (sidebarEl) {
            return sidebarEl;
        }
        
        // Cria o elemento dinamicamente
        console.warn('Criando sidebar lote dinamicamente');
        // IMPORTANTE: data-bs-focus="false" é OBRIGATÓRIO para que TomSelect, TinyMCE e Bootstrap Datepicker funcionem corretamente
        // dentro do offcanvas. Sem isso, o Bootstrap força o foco de volta para dentro do offcanvas,
        // impedindo que esses componentes recebam eventos de blur e causando bugs de foco.
        const sidebarHtml = `
       <div class="offcanvas offcanvas-end" 
            tabindex="-1" 
            id="tramitacaoLoteOffcanvas"
            aria-labelledby="tramitacaoLoteOffcanvasLabel"
            data-bs-scroll="true"
            data-bs-backdrop="static"
            data-bs-focus="false"
            style="width: 700px; max-width: 90vw;">
  <div class="offcanvas-header border-bottom bg-light">
    <h5 class="offcanvas-title fw-bold" id="tramitacaoLoteOffcanvasLabel">
      <i class="mdi mdi-send-multiple text-primary" aria-hidden="true"></i>
      Tramitação em Lote
    </h5>
    <button type="button" 
            class="btn-close" 
            id="btnFecharSidebarLote"
            data-bs-dismiss="offcanvas"
            aria-label="Fechar"></button>
  </div>
  <div class="offcanvas-body" id="tramitacaoLoteOffcanvasBody">
    <!-- Formulário de tramitação em lote -->
  </div>
  <div class="offcanvas-footer border-top p-3 bg-light">
    <div class="d-flex gap-2 justify-content-between align-items-center">
      <div>
        <span class="badge bg-primary" id="contador-processos-selecionados-lote">
          <i class="mdi mdi-check-circle" aria-hidden="true"></i>
          <span id="num-processos-selecionados-lote">0</span> processo(s) selecionado(s)
        </span>
      </div>
      <div class="d-flex gap-2">
        <button type="button" 
                class="btn btn-secondary" 
                id="btnCancelarLote"
                data-bs-dismiss="offcanvas">
          <i class="mdi mdi-close" aria-hidden="true"></i> Cancelar
        </button>
        <button type="button" 
                class="btn btn-primary" 
                id="btnTramitarLote">
          <i class="mdi mdi-send-multiple" aria-hidden="true"></i> Tramitar Processos
        </button>
      </div>
    </div>
  </div>
</div>`;
        
        // Adiciona ao body
        try {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = sidebarHtml.trim();
            sidebarEl = tempDiv.firstElementChild;
            
            if (!sidebarEl) {
                console.error('Erro ao criar sidebar lote: firstElementChild é null');
                return null;
            }
            
            document.body.appendChild(sidebarEl);
            console.log('Sidebar lote criado dinamicamente com sucesso');
            return sidebarEl;
        } catch (e) {
            console.error('Erro ao criar sidebar lote dinamicamente:', e);
            return null;
        }
    }
    
    /**
     * Inicializa sidebar lote (método auxiliar)
     */
    _inicializarSidebarLote(sidebarEl) {
        if (typeof bootstrap === 'undefined') {
            console.error('Bootstrap não está disponível');
            this.app.mostrarToast('Erro', 'Bootstrap não está carregado. Verifique se o script está incluído.', 'error');
            return false;
        }
        try {
            this.sidebarLote = new bootstrap.Offcanvas(sidebarEl);
            this._bindOffcanvasElementListeners('lote');
            return true;
        } catch (e) {
            console.error('Erro ao inicializar sidebar:', e);
            this.app.mostrarToast('Erro', 'Erro ao inicializar sidebar: ' + e.message, 'error');
            return false;
        }
    }
    
    /**
     * Normaliza e verifica se o conteúdo do TinyMCE está vazio
     * @param {string} conteudo - Conteúdo do editor
     * @returns {boolean} - true se estiver vazio
     */
    _conteudoTinyMCEEstaVazio(conteudo) {
        if (!conteudo) {
            return true;
        }
        
        // Converte para string se não for
        const conteudoStr = String(conteudo).trim();
        
        // Verifica se está vazio após trim
        if (!conteudoStr) {
            return true;
        }
        
        // Remove tags HTML e normaliza espaços
        const textoLimpo = conteudoStr
            .replace(/<[^>]+>/g, '') // Remove tags HTML (<p>, <br>, etc.)
            .replace(/&nbsp;/gi, ' ') // Substitui &nbsp; (case insensitive) por espaço
            .replace(/&amp;/gi, '&') // Decodifica &amp;
            .replace(/&lt;/gi, '<') // Decodifica &lt;
            .replace(/&gt;/gi, '>') // Decodifica &gt;
            .replace(/&quot;/gi, '"') // Decodifica &quot;
            .replace(/&#39;/gi, "'") // Decodifica &#39;
            .replace(/\s+/g, ' ') // Normaliza múltiplos espaços em um único espaço
            .trim(); // Remove espaços do início e fim
        
        // Retorna true se o texto limpo estiver vazio
        return textoLimpo === '';
    }
    
    /**
     * Obtém o estado atual do formulário
     * @param {string} tipo - 'individual' ou 'lote'
     * @returns {Object} Estado atual do formulário
     */
    _obterEstadoAtualFormulario(tipo) {
        const isIndividual = tipo === 'individual';
        const prefixo = isIndividual ? 'tramitacaoIndividualOffcanvasBody' : 'tramitacaoLoteOffcanvasBody';
        const body = document.getElementById(prefixo);
        
        if (!body) {
            return null;
        }
        
        const estado = {
            unidadeDestino: null,
            status: null,
            dataFimPrazo: null,
            textoDespacho: null,
            arquivoPdf: false
        };
        
        // Unidade de destino
        const campoUnidadeDest = body.querySelector('#field_lst_cod_unid_tram_dest');
        if (campoUnidadeDest) {
            estado.unidadeDestino = campoUnidadeDest.value || $(campoUnidadeDest).val() || null;
        }
        
        // Status
        const campoStatus = body.querySelector('#field_lst_cod_status');
        if (campoStatus) {
            estado.status = campoStatus.value || $(campoStatus).val() || null;
        }
        
        // Data de fim de prazo
        const campoDataFimPrazo = isIndividual
            ? body.querySelector('#field_txt_dat_fim_prazo, #txt_dat_fim_prazo, input[name="txt_dat_fim_prazo"]')
            : body.querySelector('#field_txt_dat_fim_prazo_lote, #txt_dat_fim_prazo_lote, #field_txt_dat_fim_prazo, #txt_dat_fim_prazo, input[name="txt_dat_fim_prazo_lote"], input[name="txt_dat_fim_prazo"]');
        if (campoDataFimPrazo) {
            estado.dataFimPrazo = campoDataFimPrazo.value || $(campoDataFimPrazo).val() || null;
        }
        
        // Texto do despacho (Trumbowyg)
        const conteudo = this.obterConteudoEditor();
        // Normaliza conteúdo vazio (remove apenas espaços e tags vazias)
        const conteudoLimpo = conteudo ? conteudo.trim().replace(/^<p><\/p>$/i, '').replace(/^<p>\s*<\/p>$/i, '') : '';
        estado.textoDespacho = conteudoLimpo === '' ? null : conteudo;
        
        // Arquivo PDF
        const arquivoPdf = body.querySelector('#file_nom_arquivo' + (isIndividual ? '' : '_lote'));
        if (arquivoPdf && arquivoPdf.files && arquivoPdf.files.length > 0) {
            estado.arquivoPdf = true;
        }
        
        return estado;
    }
    
    /**
     * Salva o estado inicial do formulário (chamado após popular os campos)
     * @param {string} tipo - 'individual' ou 'lote'
     */
    _salvarEstadoInicialFormulario(tipo) {
        const estado = this._obterEstadoAtualFormulario(tipo);
        if (estado) {
            this.estadoInicialFormulario[tipo] = estado;
            console.log(`✅ Estado inicial do formulário (${tipo}) salvo:`, estado);
        }
    }
    
    /**
     * Verifica se há dados não salvos no formulário (comparando com estado inicial)
     * @param {string} tipo - 'individual' ou 'lote'
     * @returns {boolean} - true se houver dados não salvos ou alterações
     */
    _temDadosNaoSalvos(tipo) {
        const estadoAtual = this._obterEstadoAtualFormulario(tipo);
        const estadoInicial = this.estadoInicialFormulario[tipo];
        
        // Se não há estado inicial salvo, verifica se há dados preenchidos
        // (caso de novo formulário, não rascunho existente)
        if (!estadoInicial) {
            // Para novo formulário, verifica se há dados preenchidos
            const temDados = estadoAtual && (
                (estadoAtual.unidadeDestino && estadoAtual.unidadeDestino !== '' && estadoAtual.unidadeDestino !== '0') ||
                (estadoAtual.status && estadoAtual.status !== '' && estadoAtual.status !== '0') ||
                (estadoAtual.dataFimPrazo && estadoAtual.dataFimPrazo.trim() !== '') ||
                (estadoAtual.textoDespacho && !this._conteudoTinyMCEEstaVazio(estadoAtual.textoDespacho)) ||
                estadoAtual.arquivoPdf
            );
            return temDados || false;
        }
        
        // Compara estado atual com estado inicial para detectar alterações
        if (!estadoAtual) {
            return false;
        }
        
        // Normaliza valores para comparação (converte para string e trata valores vazios/nulos)
        // Inclui normalização de datas (dd/mm/yyyy <-> yyyy-mm-dd) para evitar falsos positivos.
        const normalizar = (valor) => {
            if (valor === null || valor === undefined) return null;
            const str = String(valor).trim();
            if (str === '' || str === '0') return null;
            
            // Normaliza datas para ISO (yyyy-mm-dd) quando possível
            // Aceita "dd/mm/yyyy" ou "yyyy-mm-dd"
            const mBr = str.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
            if (mBr) {
                const [, dd, mm, yyyy] = mBr;
                return `${yyyy}-${mm}-${dd}`;
            }
            const mIso = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
            if (mIso) {
                return str;
            }
            return str;
        };
        
        // Compara cada campo
        const unidadeDestAtual = normalizar(estadoAtual.unidadeDestino);
        const unidadeDestInicial = normalizar(estadoInicial.unidadeDestino);
        if (unidadeDestAtual !== unidadeDestInicial) {
            return true;
        }
        
        const statusAtual = normalizar(estadoAtual.status);
        const statusInicial = normalizar(estadoInicial.status);
        if (statusAtual !== statusInicial) {
            return true;
        }
        
        const dataFimPrazoAtual = normalizar(estadoAtual.dataFimPrazo);
        const dataFimPrazoInicial = normalizar(estadoInicial.dataFimPrazo);
        if (dataFimPrazoAtual !== dataFimPrazoInicial) {
            return true;
        }
        
        // Para texto do despacho, normaliza conteúdo TinyMCE antes de comparar
        const textoDespachoAtual = estadoAtual.textoDespacho ? 
            (this._conteudoTinyMCEEstaVazio(estadoAtual.textoDespacho) ? null : estadoAtual.textoDespacho) : null;
        const textoDespachoInicial = estadoInicial.textoDespacho ? 
            (this._conteudoTinyMCEEstaVazio(estadoInicial.textoDespacho) ? null : estadoInicial.textoDespacho) : null;
        if (textoDespachoAtual !== textoDespachoInicial) {
            return true;
        }
        
        // Verifica arquivo PDF (se foi anexado novo arquivo)
        if (estadoAtual.arquivoPdf !== estadoInicial.arquivoPdf) {
            return true;
        }
        
        // Não há alterações
        return false;
    }
    
    /**
     * Mostra modal de confirmação antes de fechar o sidebar
     * @param {string} tipo - 'individual' ou 'lote'
     * @param {Function} callback - Função a ser executada se o usuário confirmar
     */
    _mostrarConfirmacaoFechamento(tipo, callback) {
        const titulo = tipo === 'individual' ? 'Tramitação Individual' : 'Tramitação em Lote';
        
        // Refatoração: usa confirm nativo (sempre funciona) e evita problemas de Modal não abrir.
        const ok = window.confirm(
            `Você tem dados não salvos no formulário de ${titulo}.\n\nDeseja realmente fechar? Todas as alterações serão perdidas.`
        );
        if (ok && callback) callback();
        return;
        
        // Cria modal de confirmação usando Bootstrap
        const modalHtml = `
            <div class="modal fade" id="modalConfirmacaoFechamento" tabindex="-1" aria-labelledby="modalConfirmacaoFechamentoLabel" aria-hidden="true" data-bs-backdrop="static" data-bs-keyboard="false">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header border-bottom">
                            <h5 class="modal-title" id="modalConfirmacaoFechamentoLabel">
                                <i class="mdi mdi-alert-circle text-warning me-2" aria-hidden="true"></i>
                                Confirmar Fechamento
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>
                        </div>
                        <div class="modal-body">
                            <p class="mb-0">
                                Você tem dados não salvos no formulário de <strong>${titulo}</strong>.
                            </p>
                            <p class="mb-0 mt-2">
                                Deseja realmente fechar? Todas as alterações serão perdidas.
                            </p>
                        </div>
                        <div class="modal-footer border-top">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                <i class="mdi mdi-close" aria-hidden="true"></i> Cancelar
                            </button>
                            <button type="button" class="btn btn-danger" id="btnConfirmarFechamento">
                                <i class="mdi mdi-check" aria-hidden="true"></i> Sim, Fechar
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove modal anterior se existir
        const modalAnterior = document.getElementById('modalConfirmacaoFechamento');
        if (modalAnterior) {
            modalAnterior.remove();
        }
        
        // Adiciona modal ao body
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Inicializa modal
        const modalEl = document.getElementById('modalConfirmacaoFechamento');
        const modal = new bootstrap.Modal(modalEl, {
            backdrop: 'static',
            keyboard: false
        });
        
        // Evento de confirmação
        $('#btnConfirmarFechamento').off('click').on('click', () => {
            modal.hide();
            setTimeout(() => {
                modalEl.remove();
                if (callback) {
                    callback();
                }
            }, 300);
        });
        
        // Remove modal quando fechar sem confirmar
        modalEl.addEventListener('hidden.bs.modal', () => {
            setTimeout(() => {
                modalEl.remove();
                // Libera flag quando modal é fechado
                this.processandoCliqueBackdrop = false;
            }, 300);
        });
        
        // Remove aria-hidden antes de mostrar (corrige problema de acessibilidade)
        modalEl.removeAttribute('aria-hidden');
        modalEl.setAttribute('aria-modal', 'true');
        
        // Mostra modal
        modal.show();
        
        // Garante que aria-hidden seja removido após mostrar
        setTimeout(() => {
            if (modalEl) {
                modalEl.removeAttribute('aria-hidden');
                modalEl.setAttribute('aria-modal', 'true');
            }
        }, 50);
    }
    
    /**
     * Reseta flag de dados não salvos (usado após salvar ou fechar)
     * @param {string} tipo - 'individual' ou 'lote'
     */
    _resetarFlagDadosNaoSalvos(tipo) {
        // Esta função pode ser usada para resetar flags se necessário no futuro
        // Por enquanto, a verificação é feita em tempo real
    }
    
    /**
     * Atualiza o atributo data-bs-backdrop dinamicamente baseado em dados não salvos
     * Quando há dados não salvos, muda para "static" para prevenir fechamento pelo backdrop
     * @param {string} tipo - 'individual' ou 'lote'
     */
    _atualizarBackdropProtecao(tipo) {
        const isIndividual = tipo === 'individual';
        const sidebarId = isIndividual ? 'tramitacaoIndividualOffcanvas' : 'tramitacaoLoteOffcanvas';
        const sidebarEl = document.getElementById(sidebarId);
        
        if (!sidebarEl) {
            return;
        }
        
        // Verifica se há dados não salvos
        const temDados = this._temDadosNaoSalvos(tipo);
        const protecao = isIndividual ? this.protecaoFechamentoIndividual : this.protecaoFechamentoLote;
        
        // IMPORTANTE: Inicializamos com "static" por padrão para proteger dados
        // Só muda para "true" quando NÃO há dados não salvos E proteção está desativada
        if (!temDados && !protecao) {
            // Sem dados E proteção desativada: permite fechamento pelo backdrop
            sidebarEl.setAttribute('data-bs-backdrop', 'true');
            console.log(`🔓 Backdrop alterado para "true" (${tipo}) - sem dados não salvos e proteção desativada`);
        } else {
            // Com dados OU proteção ativa: mantém "static" para prevenir fechamento
            sidebarEl.setAttribute('data-bs-backdrop', 'static');
            if (temDados && protecao) {
                console.log(`🔒 Backdrop mantido como "static" (${tipo}) - há dados não salvos`);
            } else {
                console.log(`🔒 Backdrop mantido como "static" (${tipo}) - proteção ativa`);
            }
        }
        
        // Atualiza a instância do Bootstrap se existir
        // IMPORTANTE: Precisa atualizar tanto o atributo quanto a configuração da instância
        const sidebarInstance = isIndividual ? this.sidebarIndividual : this.sidebarLote;
        if (sidebarInstance) {
            // Atualiza a configuração da instância
            if (sidebarInstance._config) {
                // Mantém "static" se há dados OU proteção está ativa
                sidebarInstance._config.backdrop = (!temDados && !protecao) ? true : 'static';
            }
            // Também atualiza diretamente no elemento se a instância tiver método update
            if (typeof sidebarInstance._setBackdrop === 'function') {
                sidebarInstance._setBackdrop(temDados && protecao ? 'static' : true);
            }
            // Força atualização do backdrop usando a API do Bootstrap
            try {
                const backdropValue = temDados && protecao ? 'static' : true;
                // Remove backdrop atual se existir
                const backdropEl = document.querySelector('.offcanvas-backdrop');
                if (backdropEl && temDados && protecao) {
                    // Se precisa ser static, garante que o backdrop não fecha
                    backdropEl.style.pointerEvents = 'none';
                    setTimeout(() => {
                        if (backdropEl && backdropEl.parentNode) {
                            backdropEl.style.pointerEvents = '';
                        }
                    }, 50);
                }
            } catch (e) {
                console.warn('Erro ao atualizar backdrop:', e);
            }
        }
    }
    
    /**
     * Configura monitoramento de mudanças nos campos do formulário para atualizar backdrop
     * @param {string} tipo - 'individual' ou 'lote'
     */
    _configurarMonitoramentoBackdrop(tipo) {
        const isIndividual = tipo === 'individual';
        const bodyId = isIndividual ? 'tramitacaoIndividualOffcanvasBody' : 'tramitacaoLoteOffcanvasBody';
        const body = document.getElementById(bodyId);
        
        if (!body) {
            return;
        }
        
        const sidebarManager = this;
        
        // Atualiza backdrop inicialmente
        sidebarManager._atualizarBackdropProtecao(tipo);
        
        // Monitora mudanças em todos os campos do formulário
        const campos = body.querySelectorAll('input, select, textarea');
        campos.forEach(campo => {
            // Remove listeners anteriores para evitar duplicação
            campo.removeEventListener('change', sidebarManager._handlerBackdropUpdate);
            campo.removeEventListener('input', sidebarManager._handlerBackdropUpdate);
            
            // Adiciona novos listeners
            campo.addEventListener('change', function() {
                // Atualiza backdrop IMEDIATAMENTE quando campo muda
                setTimeout(() => {
                    sidebarManager._atualizarBackdropProtecao(tipo);
                }, 0);
            });
            campo.addEventListener('input', function() {
                // Atualiza backdrop IMEDIATAMENTE quando campo é digitado
                setTimeout(() => {
                    sidebarManager._atualizarBackdropProtecao(tipo);
                }, 0);
            });
        });
        
        // Monitora mudanças no Trumbowyg (se existir)
        if (typeof jQuery !== 'undefined' && typeof jQuery.fn.trumbowyg !== 'undefined') {
            // Tenta ambos os IDs possíveis (com e sem prefixo field_)
            const editorIds = isIndividual 
                ? ['field_txa_txt_tramitacao', 'txa_txt_tramitacao']
                : ['field_txa_txt_tramitacao_lote', 'txa_txt_tramitacao_lote'];
            
            for (const editorId of editorIds) {
                const $editor = jQuery('#' + editorId);
                if ($editor.length && $editor.data('trumbowyg')) {
                    // Remove listeners anteriores para evitar duplicação
                    $editor.off('tbwchange.backdrop tbwfocus.backdrop tbwblur.backdrop keyup.backdrop');
                    
                    // Adiciona listeners para mudanças no Trumbowyg
                    $editor.on('tbwchange.backdrop', () => {
                        setTimeout(() => {
                            sidebarManager._atualizarBackdropProtecao(tipo);
                        }, 0);
                    });
                    $editor.on('tbwfocus.backdrop tbwblur.backdrop keyup.backdrop', () => {
                        setTimeout(() => {
                            sidebarManager._atualizarBackdropProtecao(tipo);
                        }, 0);
                    });
                    break; // Para no primeiro editor encontrado
                }
            }
        }
        
        // Monitora mudanças em TomSelect
        const tomselectIds = isIndividual 
            ? ['#field_lst_cod_unid_tram_dest', '#field_lst_cod_status', '#field_lst_cod_usuario_dest']
            : ['#field_lst_cod_unid_tram_dest', '#field_lst_cod_status', '#field_lst_cod_usuario_dest'];
        
        tomselectIds.forEach(selector => {
            const selectEl = document.querySelector(selector);
            if (selectEl) {
                // Para TomSelect
                if (selectEl.tomselect) {
                    selectEl.tomselect.off('change');
                    selectEl.tomselect.on('change', () => {
                        console.log(`TomSelect alterado: ${selector}, atualizando backdrop...`);
                        setTimeout(() => {
                            sidebarManager._atualizarBackdropProtecao(tipo);
                        }, 0);
                    });
                }
                // Fallback para eventos padrão do DOM
                const $select = $(selector);
                if ($select.length > 0) {
                    $select.off('change.backdrop').on('change.backdrop', () => {
                        console.log(`Select alterado: ${selector}, atualizando backdrop...`);
                        setTimeout(() => {
                            sidebarManager._atualizarBackdropProtecao(tipo);
                        }, 0);
                    });
                }
            }
        });
    }
    
    /**
     * Tenta fechar o sidebar com verificação de proteção
     * @param {string} tipo - 'individual' ou 'lote'
     */
    _tentarFecharSidebar(tipo) {
        // Fecha via fluxo unificado (com bypass de guardas).
        this._forceFecharSidebar(tipo);
    }
    
    setupEventListeners() {
        // Refatoração: garante clique no X/Cancelar sempre fecha (handler nativo, independente do jQuery)
        document.addEventListener('click', (e) => {
            const t = e.target;
            if (!t || !t.closest) return;
            if (t.closest('#btnFecharSidebarIndividual, #btnCancelarIndividual')) {
                e.preventDefault();
                this._forceFecharSidebar('individual');
            }
            if (t.closest('#btnFecharSidebarLote, #btnCancelarLote')) {
                e.preventDefault();
                this._forceFecharSidebar('lote');
            }
        }, true);

        // Listener global para fechar Datepicker ao clicar fora
        $(document).on('mousedown', (e) => {
            // Pequeno delay para permitir que o Datepicker processe primeiro
            setTimeout(() => {
                this.forcarFechamentoFlatpickr(e);
            }, 10);
        });
        
        // Refatoração: NÃO intercepta clique no backdrop.
        // O fechamento/backdrop/ESC é tratado exclusivamente via `hide.bs.offcanvas`,
        // para evitar deadlocks e recursão com múltiplos handlers.
        
        // Proteção contra fechamento acidental - Sidebar Individual
        if (this.sidebarIndividual) {
            const sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
            
            // Intercepta tentativa de fechamento para verificar se há dados não salvos
            // IMPORTANTE: Este evento é disparado ANTES do fechamento visual, então podemos prevenir
            // Usa múltiplos listeners para garantir interceptação
            const handlerHide = (e) => {
                console.log('Sidebar fechando, verificando se há dados não salvos...');
                if (this._bypassCloseGuard.individual) {
                    return;
                }
                
                // Fecha calendário
                this._fecharCalendarioFlatpickr();
                
                // Se a proteção estiver desativada (após salvar/enviar), permite fechamento
                if (!this.protecaoFechamentoIndividual) {
                    console.log('Proteção desativada, permitindo fechamento');
                    return;
                }
                
                // IMPORTANTE: Atualiza backdrop ANTES de verificar dados
                // Isso garante que está configurado corretamente
                this._atualizarBackdropProtecao('individual');
                
                // Verifica se há dados preenchidos no formulário
                if (this._temDadosNaoSalvos('individual')) {
                    // Previne o fechamento ANTES que o Bootstrap feche visualmente
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    
                    // Garante que o backdrop está como "static"
                    sidebarEl.setAttribute('data-bs-backdrop', 'static');
                    if (this.sidebarIndividual && this.sidebarIndividual._config) {
                        this.sidebarIndividual._config.backdrop = 'static';
                    }
                    
                    // Mostra modal de confirmação IMEDIATAMENTE (síncrono)
                    // Não usa setTimeout para garantir que aparece antes do fechamento
                    this._mostrarConfirmacaoFechamento('individual', () => {
                        // Usuário confirmou - fecha forçando bypass
                        this._forceFecharSidebar('individual');
                    });
                    
                    return false;
                }
            };
            
            // Adiciona listener na fase de captura (ANTES do bubbling)
            sidebarEl.addEventListener('hide.bs.offcanvas', handlerHide, { capture: true, passive: false });
            // Também adiciona listener normal como backup
            sidebarEl.addEventListener('hide.bs.offcanvas', handlerHide, { passive: false });
            
            // IMPORTANTE: Destrói Trumbowyg ANTES do offcanvas fechar
            // Isso garante que o editor seja destruído enquanto o elemento ainda está no DOM
            // Usa listener com baixa prioridade (sem capture) para executar DEPOIS do handlerHide
            sidebarEl.addEventListener('hide.bs.offcanvas', (e) => {
                // Verifica se o fechamento NÃO foi prevenido (ou seja, não há dados não salvos)
                // Se defaultPrevented for true, significa que handlerHide preveniu o fechamento
                if (!e.defaultPrevented) {
                    // Destrói Trumbowyg imediatamente, antes do elemento ser removido do DOM
                    if (typeof jQuery !== 'undefined' && typeof jQuery.fn.trumbowyg !== 'undefined') {
                        const idsTrumbowyg = ['#field_txa_txt_tramitacao', '#txa_txt_tramitacao'];
                        idsTrumbowyg.forEach(id => {
                            try {
                                const $editor = jQuery(id);
                                if ($editor.length > 0 && $editor.data('trumbowyg')) {
                                    $editor.trumbowyg('destroy');
                                }
                            } catch (e) {
                                // Ignora erro se Trumbowyg não foi inicializado
                            }
                        });
                    }
                }
            }, { capture: false, once: false });
            
            // Limpa formulário quando o sidebar estiver completamente fechado
            sidebarEl.addEventListener('hidden.bs.offcanvas', () => {
                this._bypassCloseGuard.individual = false;
                // Se rascunho foi salvo ou tramitação foi enviada, atualiza lista
                if (this.rascunhoSalvo) {
                    if (this.app && this.app.carregarTramitacoes) {
                        this.app.carregarTramitacoes();
                    }
                    this.rascunhoSalvo = false; // Reseta flag
                }
                
                this.limparFormularioIndividual();
                // Reativa proteção para próxima abertura
                this.protecaoFechamentoIndividual = true;
            });
        }
        
        // Proteção contra fechamento acidental - Sidebar Lote
        if (this.sidebarLote) {
            const sidebarEl = document.getElementById('tramitacaoLoteOffcanvas');
            
            
            // Intercepta tentativa de fechamento para verificar se há dados não salvos
            // IMPORTANTE: Este evento é disparado ANTES do fechamento visual, então podemos prevenir
            // Usa múltiplos listeners para garantir interceptação
            const handlerHideLote = (e) => {
                console.log('Sidebar lote fechando, verificando se há dados não salvos...');
                if (this._bypassCloseGuard.lote) {
                    return;
                }
                
                // Fecha calendário
                this._fecharCalendarioFlatpickr();
                
                // Se a proteção estiver desativada (após salvar/enviar), permite fechamento
                if (!this.protecaoFechamentoLote) {
                    console.log('Proteção desativada, permitindo fechamento');
                    return;
                }
                
                // IMPORTANTE: Atualiza backdrop ANTES de verificar dados
                // Isso garante que está configurado corretamente
                this._atualizarBackdropProtecao('lote');
                
                // Verifica se há dados preenchidos no formulário
                if (this._temDadosNaoSalvos('lote')) {
                    // Previne o fechamento ANTES que o Bootstrap feche visualmente
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    
                    // Garante que o backdrop está como "static"
                    sidebarEl.setAttribute('data-bs-backdrop', 'static');
                    if (this.sidebarLote && this.sidebarLote._config) {
                        this.sidebarLote._config.backdrop = 'static';
                    }
                    
                    // Mostra modal de confirmação IMEDIATAMENTE (síncrono)
                    // Não usa setTimeout para garantir que aparece antes do fechamento
                    this._mostrarConfirmacaoFechamento('lote', () => {
                        // Usuário confirmou - fecha forçando bypass
                        this._forceFecharSidebar('lote');
                    });
                    
                    return false;
                }
            };
            
            // Adiciona listener na fase de captura (ANTES do bubbling)
            sidebarEl.addEventListener('hide.bs.offcanvas', handlerHideLote, { capture: true, passive: false });
            // Também adiciona listener normal como backup
            sidebarEl.addEventListener('hide.bs.offcanvas', handlerHideLote, { passive: false });
            
            // IMPORTANTE: Destrói Trumbowyg ANTES do offcanvas fechar
            // Isso garante que o editor seja destruído enquanto o elemento ainda está no DOM
            // Usa listener com baixa prioridade (sem capture) para executar DEPOIS do handlerHideLote
            sidebarEl.addEventListener('hide.bs.offcanvas', (e) => {
                // Verifica se o fechamento NÃO foi prevenido (ou seja, não há dados não salvos)
                // Se defaultPrevented for true, significa que handlerHideLote preveniu o fechamento
                if (!e.defaultPrevented) {
                    // Destrói Trumbowyg imediatamente, antes do elemento ser removido do DOM
                    if (typeof jQuery !== 'undefined' && typeof jQuery.fn.trumbowyg !== 'undefined') {
                        const idsTrumbowyg = ['#field_txa_txt_tramitacao_lote', '#txa_txt_tramitacao_lote'];
                        idsTrumbowyg.forEach(id => {
                            try {
                                const $editor = jQuery(id);
                                if ($editor.length > 0 && $editor.data('trumbowyg')) {
                                    $editor.trumbowyg('destroy');
                                }
                            } catch (e) {
                                // Ignora erro se Trumbowyg não foi inicializado
                            }
                        });
                    }
                }
            }, { capture: false, once: false });
            
            // Limpa formulário quando o sidebar estiver completamente fechado
            sidebarEl.addEventListener('hidden.bs.offcanvas', () => {
                this._bypassCloseGuard.lote = false;
                this.limparFormularioLote();
                // Reativa proteção para próxima abertura
                this.protecaoFechamentoLote = true;
            });
        }
        
        // Bootstrap Datepicker reposiciona automaticamente, não precisa de listener
        
        // Botão salvar rascunho
        $(document).on('click', '#btnSalvarRascunho', () => {
            this.salvarRascunho();
        });
        
        // Botão enviar tramitação
        $(document).on('click', '#btnEnviarTramitacao', () => {
            this.enviarTramitacao();
        });
        
        // Botão retomar tramitação (na visualização de tramitação enviada)
        $(document).on('click', '.btn-retomar-tramitacao', (e) => {
            e.preventDefault();
            const codTramitacao = $(e.currentTarget).data('cod-tramitacao');
            const tipo = $(e.currentTarget).data('tipo');
            this.retomarTramitacao(codTramitacao, tipo);
        });
        
        // Botão tramitar lote
        $(document).on('click', '#btnTramitarLote', () => {
            this.tramitarLote();
        });
        
        // Botões de cancelar/fechar com proteção
        // Usa referência da instância através do app para garantir contexto correto
        const sidebarManagerButtons = this;
        $(document).on('click', '#btnFecharSidebarIndividual, #btnCancelarIndividual', function() {
            // Usa a referência armazenada para garantir contexto correto
            const manager = sidebarManagerButtons || (window.tramitacaoApp && window.tramitacaoApp.sidebarManager);
            if (manager && typeof manager._forceFecharSidebar === 'function') {
                manager._forceFecharSidebar('individual');
            } else {
                console.error('_forceFecharSidebar não é uma função ou manager não encontrado');
                // Fallback: fecha diretamente se a função não estiver disponível
                try {
                    const sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
                    if (sidebarEl && typeof bootstrap !== 'undefined') {
                        bootstrap.Offcanvas.getOrCreateInstance(sidebarEl).hide();
                        return;
                    }
                } catch (_) {}
                if (manager && manager.sidebarIndividual && typeof manager.sidebarIndividual.hide === 'function') {
                    manager.sidebarIndividual.hide();
                }
            }
        });
        
        $(document).on('click', '#btnFecharSidebarLote, #btnCancelarLote', function() {
            // Usa a referência armazenada para garantir contexto correto
            const manager = sidebarManagerButtons || (window.tramitacaoApp && window.tramitacaoApp.sidebarManager);
            if (manager && typeof manager._forceFecharSidebar === 'function') {
                manager._forceFecharSidebar('lote');
            } else {
                console.error('_forceFecharSidebar não é uma função ou manager não encontrado');
                // Fallback: fecha diretamente se a função não estiver disponível
                try {
                    const sidebarEl = document.getElementById('tramitacaoLoteOffcanvas');
                    if (sidebarEl && typeof bootstrap !== 'undefined') {
                        bootstrap.Offcanvas.getOrCreateInstance(sidebarEl).hide();
                        return;
                    }
                } catch (_) {}
                if (manager && manager.sidebarLote && typeof manager.sidebarLote.hide === 'function') {
                    manager.sidebarLote.hide();
                }
            }
        });
    }
    
    /**
     * Abre sidebar de nova tramitação individual
     */
    abrirNovaTramitacao(cod_entidade, tipo) {
        if (tipo !== 'MATERIA' && tipo !== 'DOCUMENTO') {
            this.app.mostrarToast('Erro', 'Tipo de processo inválido', 'error');
            return;
        }
        
        // Valida se há unidade selecionada na caixa de entrada
        if (!this.app.unidadeSelecionada) {
            this.app.mostrarToast('Atenção', 'Selecione uma unidade na caixa de entrada antes de tramitar', 'warning');
            return;
        }
        
        // Garante que sidebar está inicializado
        if (!this.sidebarIndividual) {
            // Tenta encontrar o elemento, aguardando um pouco se necessário
            let sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
            if (!sidebarEl) {
                // Tenta criar o elemento dinamicamente se não existir
                sidebarEl = this._criarSidebarIndividual();
                if (!sidebarEl) {
                    // Se não conseguiu criar, aguarda um pouco e tenta novamente
                    let tentativas = 0;
                    const maxTentativas = 20; // Aumentado para 2 segundos
                    const intervalo = 100; // 100ms
                    
                    const aguardarElemento = setInterval(() => {
                        tentativas++;
                        sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
                        if (sidebarEl || tentativas >= maxTentativas) {
                            clearInterval(aguardarElemento);
                            if (!sidebarEl) {
                                // Última tentativa: cria dinamicamente
                                sidebarEl = this._criarSidebarIndividual();
                                if (!sidebarEl) {
                                    console.error('Elemento tramitacaoIndividualOffcanvas não encontrado após ' + (maxTentativas * intervalo) + 'ms e não foi possível criar dinamicamente');
                                    this.app.mostrarToast('Erro', 'Elemento do sidebar não encontrado. Verifique se o template está carregado corretamente.', 'error');
                                    return;
                                }
                            }
                            // Continua com a inicialização
                            if (!this._inicializarSidebarIndividual(sidebarEl)) {
                                return;
                            }
                            // Continua com o fluxo após inicializar
                            this.carregarFormularioIndividual(cod_entidade, tipo, null);
                            if (this.sidebarIndividual) {
                                this._prepararOffcanvasParaShow(sidebarEl);
                                this.sidebarIndividual.show();
                            }
                        }
                    }, intervalo);
                    return; // Retorna e aguarda o elemento
                }
            }
            
            // Elemento encontrado ou criado, inicializa
            if (!this._inicializarSidebarIndividual(sidebarEl)) {
                return;
            }
        }
        
        // IMPORTANTE: Reativa proteção antes de abrir o sidebar
        this.protecaoFechamentoIndividual = true;
        
        this.carregarFormularioIndividual(cod_entidade, tipo, null);
        if (this.sidebarIndividual) {
            const sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
            this._prepararOffcanvasParaShow(sidebarEl);
            this.sidebarIndividual.show();
            // Atualiza backdrop após mostrar o sidebar
            setTimeout(() => {
                this._atualizarBackdropProtecao('individual');
            }, 100);
        }
    }
    
    /**
     * Abre sidebar de edição de tramitação individual ou rascunho
     * 
     * @param {number} cod_tramitacao - Código da tramitação
     * @param {string} tipo - 'MATERIA' ou 'DOCUMENTO'
     */
    abrirEdicao(cod_tramitacao, tipo) {
        if (tipo !== 'MATERIA' && tipo !== 'DOCUMENTO') {
            this.app.mostrarToast('Erro', 'Tipo de processo inválido', 'error');
            return;
        }
        
        // Garante que sidebar está inicializado
        if (!this.sidebarIndividual) {
            // Tenta encontrar o elemento
            let sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
            
            // Se não encontrou, tenta criar dinamicamente imediatamente
            if (!sidebarEl && typeof this._criarSidebarIndividual === 'function') {
                try {
                    sidebarEl = this._criarSidebarIndividual();
                    // Se foi criado dinamicamente, aguarda um frame para garantir que está no DOM
                    if (sidebarEl) {
                        // Usa requestAnimationFrame para garantir que o DOM foi atualizado
                        requestAnimationFrame(() => {
                            // Inicializa após o frame
                            if (this._inicializarSidebarIndividual(sidebarEl)) {
                                this._continuarAbrirEdicao(cod_tramitacao, tipo);
                            }
                        });
                        return; // Retorna e aguarda o frame
                    }
                } catch (e) {
                    console.error('Erro ao criar sidebar individual:', e);
                }
            }
            
            // Se ainda não encontrou, aguarda um pouco (elemento pode estar sendo renderizado)
            if (!sidebarEl) {
                let tentativas = 0;
                const maxTentativas = 30; // 3 segundos
                const intervalo = 100; // 100ms
                
                const aguardarElemento = setInterval(() => {
                    tentativas++;
                    sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
                    
                    // Se ainda não encontrou e a função existe, tenta criar
                    if (!sidebarEl && typeof this._criarSidebarIndividual === 'function') {
                        sidebarEl = this._criarSidebarIndividual();
                    }
                    
                    if (sidebarEl || tentativas >= maxTentativas) {
                        clearInterval(aguardarElemento);
                        if (!sidebarEl) {
                            console.error('Elemento tramitacaoIndividualOffcanvas não encontrado após ' + (maxTentativas * intervalo) + 'ms');
                            this.app.mostrarToast('Erro', 'Elemento do sidebar não encontrado. Verifique se o template está carregado corretamente.', 'error');
                            return;
                        }
                        // Inicializa o sidebar
                        if (!this._inicializarSidebarIndividual(sidebarEl)) {
                            return;
                        }
                        // Continua com o fluxo
                        this._continuarAbrirEdicao(cod_tramitacao, tipo);
                    }
                }, intervalo);
                return; // Retorna e aguarda o elemento
            }
            
            // Elemento encontrado ou criado, inicializa
            if (!this._inicializarSidebarIndividual(sidebarEl)) {
                return;
            }
        }
        
        // Sidebar já está inicializado, continua com o fluxo
        this._continuarAbrirEdicao(cod_tramitacao, tipo);
    }
    
    /**
     * Continua o fluxo de abrir edição após sidebar estar inicializado
     */
    _continuarAbrirEdicao(cod_tramitacao, tipo) {
        // Obtém cod_entidade da tramitação
        this.app.obterDadosTramitacao(cod_tramitacao, tipo, (dados) => {
            if (!dados || dados.erro) {
                this.app.mostrarToast('Erro', dados?.erro || 'Erro ao carregar dados da tramitação', 'error');
                return;
            }
            
            // Obtém cod_entidade baseado no tipo
            const cod_entidade = tipo === 'MATERIA' ? dados.cod_materia : dados.cod_documento;
            if (!cod_entidade) {
                this.app.mostrarToast('Erro', 'Não foi possível identificar o processo', 'error');
                return;
            }
            
            // Carrega formulário com dados da tramitação
            this.carregarFormularioIndividual(cod_entidade, tipo, cod_tramitacao);
            if (this.sidebarIndividual) {
                const sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
                this._prepararOffcanvasParaShow(sidebarEl);
                this.sidebarIndividual.show();
            }
        });
    }
    
    /**
     * Abre sidebar de tramitação em lote
     */
    abrirTramitacaoLote() {
        // Valida se há unidade selecionada na caixa de entrada
        if (!this.app.unidadeSelecionada) {
            this.app.mostrarToast('Atenção', 'Selecione uma unidade na caixa de entrada antes de tramitar', 'warning');
            return;
        }
        
        // Garante que sidebar está inicializado
        if (!this.sidebarLote) {
            // Tenta encontrar o elemento, aguardando um pouco se necessário
            let sidebarEl = document.getElementById('tramitacaoLoteOffcanvas');
            if (!sidebarEl) {
                // Tenta criar o elemento dinamicamente se não existir
                sidebarEl = this._criarSidebarLote();
                if (!sidebarEl) {
                    // Se não conseguiu criar, aguarda um pouco e tenta novamente
                    let tentativas = 0;
                    const maxTentativas = 20; // Aumentado para 2 segundos
                    const intervalo = 100; // 100ms
                    
                    const aguardarElemento = setInterval(() => {
                        tentativas++;
                        sidebarEl = document.getElementById('tramitacaoLoteOffcanvas');
                        if (sidebarEl || tentativas >= maxTentativas) {
                            clearInterval(aguardarElemento);
                            if (!sidebarEl) {
                                // Última tentativa: cria dinamicamente
                                sidebarEl = this._criarSidebarLote();
                                if (!sidebarEl) {
                                    console.error('Elemento tramitacaoLoteOffcanvas não encontrado após ' + (maxTentativas * intervalo) + 'ms e não foi possível criar dinamicamente');
                                    this.app.mostrarToast('Erro', 'Elemento do sidebar não encontrado. Verifique se o template está carregado corretamente.', 'error');
                                    return;
                                }
                            }
                            // Continua com a inicialização
                            if (!this._inicializarSidebarLote(sidebarEl)) {
                                return;
                            }
                            // Continua com o fluxo após inicializar
                            this.carregarFormularioLote();
                            if (this.sidebarLote) {
                                this._prepararOffcanvasParaShow(sidebarEl);
                                this.sidebarLote.show();
                            }
                        }
                    }, intervalo);
                    return; // Retorna e aguarda o elemento
                }
            }
            
            // Elemento encontrado ou criado, inicializa
            if (!this._inicializarSidebarLote(sidebarEl)) {
                return;
            }
        }
        
        // IMPORTANTE: Reativa proteção antes de abrir o sidebar
        this.protecaoFechamentoLote = true;
        
        this.carregarFormularioLote();
        if (this.sidebarLote) {
            const sidebarEl = document.getElementById('tramitacaoLoteOffcanvas');
            this._prepararOffcanvasParaShow(sidebarEl);
            this.sidebarLote.show();
            // Atualiza backdrop após mostrar o sidebar
            setTimeout(() => {
                this._atualizarBackdropProtecao('lote');
            }, 100);
        }
    }

    /**
     * Atualiza contador visual de processos selecionados no rodapé do lote.
     */
    atualizarContadorProcessosLote() {
        const count = (this.app && this.app.processosSelecionados)
            ? this.app.processosSelecionados.size
            : 0;

        const numEl = document.getElementById('num-processos-selecionados-lote');
        if (numEl) {
            numEl.textContent = String(count);
        }

        const badgeEl = document.getElementById('contador-processos-selecionados-lote');
        if (badgeEl) {
            // Mantém visível, mas pode ocultar se não houver seleção
            badgeEl.style.display = count > 0 ? '' : 'none';
        }

        const btnTramitar = document.getElementById('btnTramitarLote');
        if (btnTramitar) {
            btnTramitar.disabled = count === 0;
        }
    }
    
    /**
     * Carrega formulário individual via AJAX
     * 
     * IMPORTANTE: Se cod_tramitacao fornecido, carrega dados da tramitação para edição/retomada
     */
    carregarFormularioIndividual(cod_entidade, tipo, cod_tramitacao) {
        if (tipo !== 'MATERIA' && tipo !== 'DOCUMENTO') {
            return;
        }
        
        const sidebarBody = document.getElementById('tramitacaoIndividualOffcanvasBody');
        const sidebarTitle = document.getElementById('tramitacaoIndividualOffcanvasLabel');
        
        // Valida se elementos existem
        if (!sidebarBody) {
            console.error('Elemento tramitacaoIndividualOffcanvasBody não encontrado');
            this.app.mostrarToast('Erro', 'Erro ao carregar formulário: elemento não encontrado', 'error');
            return;
        }
        
        if (!sidebarTitle) {
            console.error('Elemento tramitacaoIndividualOffcanvasLabel não encontrado');
            // Continua mesmo sem título, mas loga o erro
        }
        
        const tipoLabel = tipo === 'MATERIA' ? 'Processo Legislativo' : 'Processo Administrativo';
        
        // Atualiza título inicial (será atualizado com informações do processo após carregar)
        if (sidebarTitle) {
            if (cod_tramitacao) {
                // Se editando, obtém dados para atualizar título
                this.app.obterDadosTramitacao(cod_tramitacao, tipo, (dados) => {
                    if (!sidebarTitle) return; // Verifica novamente (pode ter sido removido)
                    const isRascunho = !dados.dat_encaminha || dados.ind_ult_tramitacao === 0;
                    const titulo = isRascunho
                        ? `<i class="mdi mdi-file-edit text-warning"></i> Editar Rascunho - ${tipoLabel}`
                        : `<i class="mdi mdi-pencil text-primary"></i> Editar Tramitação - ${tipoLabel}`;
                    sidebarTitle.innerHTML = titulo;
                });
            } else {
                sidebarTitle.innerHTML = `<i class="mdi mdi-send text-primary"></i> Nova Tramitação - ${tipoLabel}`;
            }
        }
        
        sidebarBody.innerHTML = `
            <div class="text-center p-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Carregando...</span>
                </div>
                <p class="mt-2 text-muted">Carregando formulário...</p>
            </div>
        `;
        
        // Obtém unidade selecionada da caixa de entrada (sempre será a unidade de origem)
        const cod_unid_tram_local = this.app.unidadeSelecionada || null;
        
        // Obtém código do usuário do template (injetado via DTML como COD_USUARIO_CORRENTE)
        const cod_usuario = (COD_USUARIO_CORRENTE && COD_USUARIO_CORRENTE !== 0 && COD_USUARIO_CORRENTE !== '0' && COD_USUARIO_CORRENTE !== 'None') 
            ? parseInt(COD_USUARIO_CORRENTE)
            : null;
        
        
        // Carrega formulário (que já incluirá dados se cod_tramitacao fornecido)
        $.ajax({
            url: `${PORTAL_URL}/tramitacao_individual_form_json`,
            method: 'GET',
            data: {
                cod_entidade: cod_entidade,
                tipo: tipo,
                cod_tramitacao: cod_tramitacao || '',
                cod_unid_tram_local: cod_unid_tram_local || '',  // Passa unidade da caixa de entrada
                cod_usuario: cod_usuario || ''  // Passa código do usuário do template (COD_USUARIO_CORRENTE)
            },
            success: (response) => {
                const dados = typeof response === 'string' ? JSON.parse(response) : response;
                if (dados.erro) {
                    sidebarBody.innerHTML = `
                        <div class="alert alert-danger" role="alert">
                            <i class="mdi mdi-alert-circle"></i>
                            ${dados.erro}
                        </div>
                    `;
                    return;
                }
                if (dados.tipo && dados.tipo !== tipo) {
                    this.app.mostrarToast('Erro', 'Inconsistência no tipo de processo', 'error');
                    return;
                }
                
                // Atualiza título (sem número do processo)
                if (sidebarTitle) {
                    const tipoLabel = tipo === 'MATERIA' ? 'Processo Legislativo' : 'Processo Administrativo';
                    if (cod_tramitacao) {
                        sidebarTitle.innerHTML = `<i class="mdi mdi-file-edit text-warning"></i> Editar Tramitação - ${tipoLabel}`;
                    } else {
                        sidebarTitle.innerHTML = `<i class="mdi mdi-send text-primary"></i> Nova Tramitação - ${tipoLabel}`;
                    }
                }
                
                // Renderiza formulário (que já inclui dados se cod_tramitacao fornecido)
                this.renderizarFormularioIndividual(dados);
                
                // Atualiza visibilidade dos botões baseado na presença de cod_tramitacao
                const codTramitacao = dados.dados?.cod_tramitacao || null;
                this._atualizarBotoesFormulario(!!codTramitacao);
            },
            error: () => {
                sidebarBody.innerHTML = `
                    <div class="alert alert-danger" role="alert">
                        <i class="mdi mdi-alert-circle"></i>
                        Erro ao carregar formulário. Tente novamente.
                    </div>
                `;
            }
        });
    }
    
    /**
     * Carrega formulário em lote
     */
    carregarFormularioLote() {
        const sidebarBody = document.getElementById('tramitacaoLoteOffcanvasBody');
        const sidebarTitle = document.getElementById('tramitacaoLoteOffcanvasLabel');
        
        // Valida se elementos existem
        if (!sidebarBody) {
            console.error('Elemento tramitacaoLoteOffcanvasBody não encontrado');
            this.app.mostrarToast('Erro', 'Erro ao carregar formulário: elemento não encontrado', 'error');
            return;
        }
        
        if (!sidebarTitle) {
            console.error('Elemento tramitacaoLoteOffcanvasLabel não encontrado');
            // Continua mesmo sem título, mas loga o erro
        }
        
        if (!this.app || !this.app.processosSelecionados || this.app.processosSelecionados.size === 0) {
            sidebarBody.innerHTML = `
                <div class="alert alert-warning" role="alert">
                    <i class="mdi mdi-alert"></i>
                    Nenhum processo selecionado. Selecione pelo menos um processo para tramitar em lote.
                </div>
            `;
            return;
        }
        
        // Valida que todos os processos são do mesmo tipo
        const processosSelecionados = Array.from(this.app.processosSelecionados);
        const tiposProcessos = new Set();
        
        processosSelecionados.forEach(codEntidade => {
            const processo = this.app.processos.find(p => 
                (p.cod_entidade || p.cod_materia || p.cod_documento) == codEntidade
            );
            if (processo && processo.tipo) {
                tiposProcessos.add(processo.tipo);
            }
        });
        
        if (tiposProcessos.size === 0) {
            sidebarBody.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    <i class="mdi mdi-alert-circle"></i>
                    Erro: Não foi possível determinar o tipo dos processos selecionados.
                </div>
            `;
            return;
        }
        
        if (tiposProcessos.size > 1) {
            sidebarBody.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    <i class="mdi mdi-alert-circle"></i>
                    <strong>Erro:</strong> Não é possível tramitar processos de tipos diferentes em lote.
                    <br><br>
                    Por favor, selecione apenas processos do mesmo tipo (todos legislativos OU todos administrativos).
                </div>
            `;
            return;
        }
        
        const tipoUnico = Array.from(tiposProcessos)[0];
        const tipoLabel = tipoUnico === 'MATERIA' ? 'Processos Legislativos' : 'Processos Administrativos';
        
        // Atualiza título se elemento existir
        if (sidebarTitle) {
            sidebarTitle.innerHTML = `<i class="mdi mdi-send-multiple text-primary"></i> Tramitação em Lote - ${tipoLabel}`;
        }
        
        sidebarBody.innerHTML = `
            <div class="text-center p-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Carregando...</span>
                </div>
                <p class="mt-2 text-muted">Carregando formulário...</p>
            </div>
        `;
        
        this.atualizarContadorProcessosLote();
        
        // Obtém unidade selecionada da caixa de entrada (sempre será a unidade de origem)
        const cod_unid_tram_local = this.app.unidadeSelecionada || null;
        
        // Obtém código do usuário do template (injetado via DTML como COD_USUARIO_CORRENTE)
        const cod_usuario = (COD_USUARIO_CORRENTE && COD_USUARIO_CORRENTE !== 0 && COD_USUARIO_CORRENTE !== '0' && COD_USUARIO_CORRENTE !== 'None') 
            ? parseInt(COD_USUARIO_CORRENTE) 
            : null;
        
        $.ajax({
            url: `${PORTAL_URL}/tramitacao_lote_form_json`,
            method: 'GET',
            data: {
                processos: processosSelecionados.join(','),
                tipo: tipoUnico,
                cod_unid_tram_local: cod_unid_tram_local || '',  // Passa unidade da caixa de entrada
                cod_usuario: cod_usuario || ''  // Passa código do usuário do template
            },
            success: (response) => {
                const dados = typeof response === 'string' ? JSON.parse(response) : response;
                
                // IMPORTANTE: Reativa proteção antes de renderizar o formulário
                this.protecaoFechamentoLote = true;
                
                sidebarBody.innerHTML = dados.html || dados;
                
                // Aguarda um pouco para garantir que o DOM foi atualizado antes de inicializar componentes
                setTimeout(() => {
                this.inicializarFormularioLote();
                
                // Configura monitoramento de mudanças para atualizar backdrop
                    this._configurarMonitoramentoBackdrop('lote');
                }, 200);
            },
            error: () => {
                sidebarBody.innerHTML = `
                    <div class="alert alert-danger" role="alert">
                        <i class="mdi mdi-alert-circle"></i>
                        Erro ao carregar formulário. Tente novamente.
                    </div>
                `;
            }
        });
    }
    
    /**
     * Renderiza formulário individual
     */
    renderizarFormularioIndividual(dados) {
        const sidebarBody = document.getElementById('tramitacaoIndividualOffcanvasBody');
        if (!sidebarBody) {
            console.error('TramitacaoSidebarManager - sidebarBody não encontrado');
            return;
        }
        
        sidebarBody.innerHTML = dados.html || dados;
        
        // Verifica se os selects existem no HTML inserido
        setTimeout(() => {
            const selectDest = document.getElementById('lst_cod_unid_tram_dest');
            const selectStatus = document.getElementById('lst_cod_status');
            
            // IMPORTANTE: Reativa proteção antes de inicializar o formulário
            this.protecaoFechamentoIndividual = true;
            
            // Inicializa formulário após o HTML estar no DOM
            this.inicializarFormularioIndividual();
            
            // Configura monitoramento de mudanças para atualizar backdrop
            this._configurarMonitoramentoBackdrop('individual');
        }, 200);
        
        // Se há dados da tramitação, popula os campos do formulário
        // O estado inicial será salvo dentro de popularFormularioComDados() após todos os campos serem populados
        if (dados.dados) {
            this.popularFormularioComDados(dados.dados);
        } else {
            // Para novo formulário, salva estado inicial vazio após inicializar componentes
            setTimeout(() => {
                this._salvarEstadoInicialFormulario('individual');
            }, 1000);
            // Como a unidade de origem agora é sempre a da caixa de entrada (readonly),
            // não precisa fazer nada aqui - o configurarCarregamentoDinamico já carrega automaticamente
            // Garante apenas que o campo de usuário de origem está preenchido
            setTimeout(() => {
                const txtNomUsuario = document.getElementById('txt_nom_usuario');
                if (txtNomUsuario && !txtNomUsuario.value) {
                    // Se o campo está vazio, tenta obter do hidden field ou do backend
                    const hdnCodUsuario = document.getElementById('hdn_cod_usuario_local');
                    if (hdnCodUsuario && hdnCodUsuario.value) {
                        // O nome já deveria vir do backend, mas se não veio, loga para debug
                        console.warn('Campo de usuário de origem vazio. Código do usuário:', hdnCodUsuario.value);
                    }
                }
            }, 500);
        }
    }
    
    /**
     * Popula formulário com dados da tramitação (para edição/retomada)
     */
    popularFormularioComDados(dados) {
        // Aguarda um pouco para garantir que o formulário foi renderizado
        setTimeout(() => {
            // Popula campos hidden
            if (dados.cod_tramitacao) {
                const inputCodTramitacao = document.querySelector('#tramitacao_individual_form input[name="hdn_cod_tramitacao"]');
                if (!inputCodTramitacao) {
                    const form = document.getElementById('tramitacao_individual_form');
                    if (form) {
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'hdn_cod_tramitacao';
                        input.value = dados.cod_tramitacao;
                        form.appendChild(input);
                    }
                } else {
                    inputCodTramitacao.value = dados.cod_tramitacao;
                }
            }
            
            // Unidade de origem não pode ser alterada (sempre é a da caixa de entrada)
            // O configurarCarregamentoDinamico já carrega automaticamente unidades de destino e status
            // Aqui apenas aguarda o carregamento e popula os valores se necessário
                
            // Popula unidade de destino (aguarda carregamento via TomSelect)
            if (dados.cod_unid_tram_dest) {
                setTimeout(() => {
                    const selectDest = $('#field_lst_cod_unid_tram_dest');
                    const selectDestEl = selectDest[0];
                    if (selectDest.length && selectDestEl && selectDestEl.tomselect) {
                        selectDestEl.tomselect.setValue(dados.cod_unid_tram_dest, false);
                    }
                    
                    // Carrega usuários da unidade destino (robusto; aceita IDs com e sem prefixo `field_`)
                    setTimeout(() => {
                        this.carregarUsuariosDestino('individual', dados.cod_unid_tram_dest, dados.cod_usuario_dest || null);
                    }, 300);
                }, 800);
            }
            
            // Popula status (aguarda carregamento dos status via AJAX)
            if (dados.cod_status) {
                setTimeout(() => {
                    const selectStatus = $('#field_lst_cod_status');
                    const selectStatusEl = selectStatus[0];
                    if (selectStatus.length && selectStatusEl && selectStatusEl.tomselect) {
                        selectStatusEl.tomselect.setValue(dados.cod_status, false);
                    }
                }, 800);
            }
            
            // Popula urgência (apenas para processos legislativos - MATERIA)
            const tipo = this.obterTipoDoFormulario();
            if (tipo === 'MATERIA' && dados.ind_urgencia !== undefined) {
                const radioUrgencia = document.querySelector(`input[name="rad_ind_urgencia"][value="${dados.ind_urgencia}"]`);
                if (radioUrgencia) {
                    radioUrgencia.checked = true;
                }
            }
            
            // Popula data de fim de prazo
            if (dados.dat_fim_prazo) {
                // Normaliza data (aceita ISO ou já formatada)
                $('#txt_dat_fim_prazo').val(this.formatarDataParaInput(dados.dat_fim_prazo));
            }
            
            // Popula texto da tramitação (Trumbowyg)
            if (dados.txt_tramitacao) {
                setTimeout(() => {
                    this.definirConteudoEditor(dados.txt_tramitacao);
                    // Salva estado inicial após popular editor (aguarda editor processar)
                            setTimeout(() => {
                                this._salvarEstadoInicialFormulario('individual');
                            }, 500);
                                    }, 500);
            } else {
                // Se não há texto, salva estado inicial após todos os campos serem populados
                // (aguarda componentes serem inicializados)
                setTimeout(() => {
                    this._salvarEstadoInicialFormulario('individual');
                }, 2000);
            }
        }, 100);
    }
    
    /**
     * Inicializa componentes do formulário em lote.
     *
     * Observação: o backend pode gerar selects do lote com id="lst_cod_*" (sem prefixo `field_`).
     * Aqui inicializamos TomSelect/Trumbowyg procurando elementos dentro do container do lote,
     * sem depender de IDs globais.
     */
    inicializarFormularioLote() {
        // Aguarda um pouco para garantir que o DOM foi atualizado
        setTimeout(() => {
            const body = document.getElementById('tramitacaoLoteOffcanvasBody');
            if (!body) {
                console.warn('❌ Container do formulário em lote não encontrado (#tramitacaoLoteOffcanvasBody)');
                return;
            }
            
            // TomSelect (todos os selects do lote gerados pelo backend)
            if (typeof TomSelect === 'undefined') {
                console.warn('TomSelect não está disponível para inicialização no lote.');
            } else {
                const selects = Array.from(
                    body.querySelectorAll('select[id^="lst_cod_"], select[id^="field_lst_cod_"]')
                );
                
                selects.forEach((selectEl) => {
                    try {
                        // Destrói TomSelect existente se houver
                        if (selectEl.tomselect) {
                            selectEl.tomselect.destroy();
                        }
                        
                        const id = selectEl.id || '';
                        let placeholder = 'Selecione...';
                        let allowEmptyOption = false;
                        
                        if (id.includes('unid_tram_dest')) {
                            placeholder = 'Selecione a unidade de destino...';
                            allowEmptyOption = false;
                        } else if (id.includes('usuario_dest')) {
                            placeholder = 'Selecione o usuário de destino...';
                            allowEmptyOption = true;
                        } else if (id.includes('status')) {
                            placeholder = 'Selecione o status...';
                            allowEmptyOption = false;
                        }
                        
                        // Garante opção vazia (placeholder) no início
                        if (!selectEl.querySelector('option[value=""]')) {
                            const opt = document.createElement('option');
                            opt.value = '';
                            // Para usuário, não exibe "Selecione" como item; para demais mantém "Selecione"
                            opt.textContent = id.includes('usuario_dest') ? '' : 'Selecione';
                            selectEl.insertBefore(opt, selectEl.firstChild);
                        } else if (id.includes('usuario_dest')) {
                            // Se já existe opção vazia, remove texto "Selecione" para não aparecer no dropdown
                            try {
                                const optVazia = selectEl.querySelector('option[value=""]');
                                if (optVazia) optVazia.textContent = '';
                            } catch (_) {}
                        }
                        
                        // Remove mensagem de validação HTML5 padrão
                        selectEl.addEventListener('invalid', function(e) {
                            e.preventDefault();
                            this.setCustomValidity('');
                            return false;
                        });
                        // Limpa mensagem customizada quando o campo é alterado
                        selectEl.addEventListener('input', function() { this.setCustomValidity(''); });
                        selectEl.addEventListener('change', function() { this.setCustomValidity(''); });
                        
                        selectEl.tomselect = new TomSelect(selectEl, {
                            placeholder,
                            allowEmptyOption,
                            create: false,
                            sortField: { field: 'text', direction: 'asc' },
                            plugins: allowEmptyOption ? ['clear_button'] : []
                        });
                    } catch (e) {
                        console.warn('Falha ao inicializar TomSelect no lote para', selectEl, e);
                    }
                });
            }

            // Listener: unidade de destino -> carregar usuários de destino (lote)
            this._bindCarregamentoUsuariosDestino('lote');

            // Carrega unidades de destino e status conforme permissões da unidade de origem (lote)
            try {
                const tipoLote = body.querySelector('input[name="hdn_tipo_tramitacao"]')?.value || null;
                if (tipoLote) {
                    this.configurarCarregamentoDinamico(tipoLote, 'lote');
                }
            } catch (_) {}
            
            // Trumbowyg (textarea do lote)
            const self = this;
            setTimeout(() => {
                // O backend do lote costuma usar `textarea[name="txa_txt_tramitacao"]` (sem sufixo _lote).
                // Para evitar colisão de IDs com o formulário individual, garante um id único no textarea do lote.
                try {
                    const textarea = body.querySelector('textarea[name="txa_txt_tramitacao"], textarea[id="txa_txt_tramitacao"]');
                    if (textarea) {
                        if (!textarea.id || textarea.id === 'txa_txt_tramitacao') {
                            textarea.id = 'txa_txt_tramitacao_lote';
                        }
                        self.inicializarTrumbowyg(textarea.id, 'lote');
                        return;
                    }
                } catch (_) {}

                // Fallback: tenta autodetect (mantém compatibilidade)
                self.inicializarTrumbowyg(null, 'lote');
            }, 300);

            // ✅ Controla exibição do campo de arquivo PDF (Despacho em PDF) no lote
            // (mesma lógica do individual, mas escopada ao offcanvas do lote)
            this._configurarCampoPdf('lote');

            // ✅ Bootstrap Datepicker: fim de prazo no lote (dentro do offcanvas)
            setTimeout(() => {
                const seletoresData = [
                    '#field_txt_dat_fim_prazo_lote',
                    '#txt_dat_fim_prazo_lote',
                    'input[name="txt_dat_fim_prazo_lote"]',
                    // alguns templates reaproveitam o mesmo nome/id do individual
                    '#field_txt_dat_fim_prazo',
                    '#txt_dat_fim_prazo',
                    'input[name="txt_dat_fim_prazo"]',
                    'input.datepicker'
                ];

                let campoData = null;
                for (const sel of seletoresData) {
                    campoData = body.querySelector(sel);
                    if (campoData) break;
                }

                if (campoData) {
                    this._inicializarFlatpickrComTimeout(campoData);
                } else {
                    console.warn('❌ Campo de data (fim de prazo) não encontrado no lote. Seletores:', seletoresData);
                }
            }, 200);
        }, 100);
    }
    
    /**
     * Inicializa componentes do formulário individual
     * IMPORTANTE: Formulário sempre está no sidebar
     */
    inicializarFormularioIndividual() {
        // Aguarda um pouco para garantir que o DOM foi atualizado
        setTimeout(() => {
            // Garante que o campo de usuário de origem está preenchido
            const txtNomUsuario = document.getElementById('txt_nom_usuario');
            const hdnCodUsuario = document.getElementById('hdn_cod_usuario_local');
            if (txtNomUsuario && !txtNomUsuario.value && hdnCodUsuario && hdnCodUsuario.value) {
                // Se o campo está vazio mas há código de usuário, busca o nome
                // (normalmente já vem preenchido do backend, mas garante)
                const codUsuario = hdnCodUsuario.value;
                if (codUsuario) {
                    // Tenta obter do backend se necessário
                    // Por enquanto, apenas loga (o valor já deve vir do backend)
                    console.warn('Campo de usuário de origem vazio, mas há código de usuário:', codUsuario);
                }
            }
            
            // TomSelect (unidade destino / usuário destino / status)
            if (typeof TomSelect !== 'undefined') {
                // TomSelect para usuário de destino
                const body = document.getElementById('tramitacaoIndividualOffcanvasBody');
                const selectUsuario = body
                    ? body.querySelector('#field_lst_cod_usuario_dest, #lst_cod_usuario_dest')
                    : (document.getElementById('field_lst_cod_usuario_dest') || document.getElementById('lst_cod_usuario_dest'));
                if (selectUsuario) {
                    // Remove texto "Selecione" da opção vazia para não aparecer no dropdown
                    try {
                        const optVazia = selectUsuario.querySelector('option[value=""]');
                        if (optVazia) optVazia.textContent = '';
                    } catch (_) {}

                    // Destrói TomSelect existente se houver
                    if (selectUsuario.tomselect) {
                        selectUsuario.tomselect.destroy();
                    }
                    
                    // Remove mensagem de validação HTML5 padrão
                    selectUsuario.addEventListener('invalid', function(e) {
                        e.preventDefault();
                        this.setCustomValidity('');
                        return false;
                    });
                    
                    // Limpa mensagem customizada quando o campo é alterado
                    selectUsuario.addEventListener('input', function() {
                        this.setCustomValidity('');
                    });
                    selectUsuario.addEventListener('change', function() {
                        this.setCustomValidity('');
                    });
                    
                    const tomselectUsuario = new TomSelect(selectUsuario, {
                        placeholder: 'Selecione o usuário de destino...',
                        allowEmptyOption: true,
                        create: false,
                        sortField: {
                            field: 'text',
                            direction: 'asc'
                        },
                        plugins: ['clear_button'],
                        render: {
                            no_results: function() {
                                return '<div class="no-results">Nenhum resultado encontrado</div>';
                            }
                        }
                    });
                    
                    // Garante que opção em branco está selecionada inicialmente
                    if (!selectUsuario.value) {
                        tomselectUsuario.setValue('', true);
                    }
                }
                
                // Os selects de unidade de destino e status serão inicializados após carregar os dados
                // em configurarCarregamentoDinamico()
            }
            
            // Trumbowyg - aguarda um pouco mais para garantir que o elemento está no DOM
            // Salva referência do this para usar dentro do setTimeout
            const selfIndividual = this;
            setTimeout(() => {
                // Tenta encontrar o textarea do formulário individual
                let textareaEl = document.getElementById('field_txa_txt_tramitacao');
                let textareaId = null;
                
                // Se não encontrou com prefixo field_, tenta sem prefixo
                if (!textareaEl) {
                    textareaEl = document.getElementById('txa_txt_tramitacao');
                    if (textareaEl) {
                        textareaId = 'txa_txt_tramitacao';
                    }
                } else {
                    textareaId = 'field_txa_txt_tramitacao';
                }
                
                if (textareaEl && textareaId) {
                    if (typeof jQuery !== 'undefined' && typeof jQuery.fn.trumbowyg !== 'undefined') {
                        selfIndividual.inicializarTrumbowyg(textareaId);
                    }
                } else {
                    // Tenta novamente após um delay adicional, sem especificar ID (deixa o método detectar automaticamente)
                    setTimeout(() => {
                        if (typeof jQuery !== 'undefined' && typeof jQuery.fn.trumbowyg !== 'undefined') {
                            selfIndividual.inicializarTrumbowyg(null);
                        }
                    }, 300);
                }
            }, 300);
            
            // Controla exibição do campo de arquivo PDF baseado na opção selecionada
            this._configurarCampoPdf('individual');
            
            // Bootstrap Datepicker para data de fim de prazo - inicialização robusta
            setTimeout(() => {
                // Tenta múltiplos seletores dentro do formulário individual
                const form = document.getElementById('tramitacao_individual_form');
                if (!form) {
                    console.warn('❌ Formulário individual não encontrado');
                    return;
                }
                
                const seletores = [
                    '#field_txt_dat_fim_prazo',
                    '#txt_dat_fim_prazo',
                    'input[name="txt_dat_fim_prazo"]',
                    'input.datepicker'
                ];
                
                let campoData = null;
                
                // Primeiro tenta buscar dentro do formulário
                for (const seletor of seletores) {
                    campoData = form.querySelector(seletor);
                    if (campoData) break;
                }
                
                // Se não encontrou no formulário, tenta no documento inteiro
                if (!campoData) {
                    for (const seletor of seletores) {
                        campoData = document.querySelector(seletor);
                        if (campoData) break;
                    }
                }
                
                if (campoData) {
                    console.log('📅 Campo de data encontrado:', campoData.id || campoData.name);
                    // Usa inicialização com timeout para garantir DOM pronto
                    this._inicializarFlatpickrComTimeout(campoData);
                } else {
                    console.warn('❌ Nenhum campo de data encontrado com os seletores:', seletores);
                    // Tenta novamente após mais um delay
                    setTimeout(() => {
                        for (const seletor of seletores) {
                            campoData = document.querySelector(seletor);
                            if (campoData) {
                                console.log('📅 Campo de data encontrado na segunda tentativa:', campoData.id || campoData.name);
                                this._inicializarFlatpickrComTimeout(campoData);
                                return;
                            }
                        }
                    }, 500);
                }
            }, 500); // Aumentado para 500ms
            
            // Configura carregamento dinâmico de unidades e status
            // Aguarda um pouco mais para garantir que o HTML foi completamente renderizado
            const tipo = this.obterTipoDoFormulario();
            if (tipo) {
                // Aguarda um pouco mais para garantir que os selects estão no DOM
                setTimeout(() => {
                    this.configurarCarregamentoDinamico(tipo, 'individual');
                    // Listener: unidade de destino -> carregar usuários de destino (individual)
                    this._bindCarregamentoUsuariosDestino('individual');
                }, 300);
            }
            
            // Configura validação em tempo real para campos obrigatórios
            this._configurarValidacaoTempoReal();
        }, 100);
    }
    
    /**
     * Configura campo de arquivo PDF para mostrar/ocultar baseado na opção selecionada
     */
    _configurarCampoPdf(tipoSidebar = 'individual', tentativa = 0) {
        const bodyId = (tipoSidebar === 'lote') ? 'tramitacaoLoteOffcanvasBody' : 'tramitacaoIndividualOffcanvasBody';
        const body = document.getElementById(bodyId);
        if (!body) {
            if (tentativa < 5) setTimeout(() => this._configurarCampoPdf(tipoSidebar, tentativa + 1), 150);
            return;
        }

        const $body = (typeof jQuery !== 'undefined') ? jQuery(body) : null;
        if (!$body) return;

        // Radios podem vir com o mesmo name do individual (radTI) ou com sufixo (_lote), dependendo do template.
        const radiosSelector = 'input[name="radTI"], input[name="radTI_lote"]';

        // Input file pode existir com e sem prefixo field_ e com e sem sufixo _lote.
        const fileSelector = [
            '#field_file_nom_arquivo_lote',
            '#file_nom_arquivo_lote',
            'input[name="file_nom_arquivo_lote"]',
            '#field_file_nom_arquivo',
            '#file_nom_arquivo',
            'input[name="file_nom_arquivo"]'
        ].join(', ');

        const $campoArquivoInput = $body.find(fileSelector).first();
        if (!$campoArquivoInput.length) {
            if (tentativa < 5) setTimeout(() => this._configurarCampoPdf(tipoSidebar, tentativa + 1), 150);
            return;
        }

        // Container do campo: no renderizador atual, o input é filho direto do wrapper do campo.
        // Usar o `closest('div')` aqui evita pegar `.row` (que não é o wrapper do campo).
        const $campoArquivo = $campoArquivoInput.closest('div').first();
        const $campoArquivoLabel = $campoArquivo.find('label.form-label').first();

        const obterOpcaoSelecionada = () => {
            // ⚠️ Importante: não use `${radiosSelector}:checked` com seletores separados por vírgula,
            // senão o `:checked` só aplica ao último seletor.
            const $radioMarcado = $body.find(radiosSelector).filter(':checked').first();
            if (!$radioMarcado.length) return { valor: null, label: '' };

            const valor = $radioMarcado.val();
            let labelText = '';
            try {
                const id = $radioMarcado.attr('id');
                if (id) {
                    const $lblFor = $body.find(`label[for="${id}"]`).first();
                    if ($lblFor.length) labelText = $lblFor.text() || '';
                }
                if (!labelText) {
                    const $lblParent = $radioMarcado.closest('label');
                    if ($lblParent.length) labelText = $lblParent.text() || '';
                }
            } catch (_) {}

            return { valor, label: String(labelText || '').trim() };
        };

        const atualizarVisibilidade = () => {
            const { valor, label } = obterOpcaoSelecionada();

            // ✅ Aceita múltiplos formatos de "sim/anexar" vindos do backend
            const v = (valor == null) ? '' : String(valor).trim().toLowerCase();
            const labelNorm = String(label || '').trim().toLowerCase();
            const labelIndicaNao = /\b(não|nao)\b/.test(labelNorm);
            const labelIndicaAnexar = /\banex/.test(labelNorm) && !labelIndicaNao;

            const valorIndicaSim = (v === 's' || v === '1' || v === 'true' || v === 't' || v === 'a' || v === 'y' || v === 'sim');
            const valorIndicaNao = (v === 'n' || v === '0' || v === 'false' || v === 'f' || v === 'nao' || v === 'não');

            const habilitarPdf = (valorIndicaSim || (labelIndicaAnexar && !valorIndicaNao));

            if (habilitarPdf) {
                // Mostra e habilita (garante remoção de display:none e d-none)
                $campoArquivo.removeClass('d-none');
                $campoArquivo.css('display', 'block');
                $campoArquivoInput.prop('disabled', false).attr('required', true);
                if ($campoArquivoLabel.length) {
                    $campoArquivoLabel.find('span.text-danger').remove();
                    $campoArquivoLabel.append(' <span class="text-danger" aria-label="obrigatório">*</span>');
                }
            } else {
                // Oculta e desabilita
                $campoArquivo.addClass('d-none').css('display', 'none');
                $campoArquivoInput.prop('disabled', true).removeAttr('required');
                // limpar arquivo (quando possível)
                try { $campoArquivoInput.val(''); } catch (_) {}
                if ($campoArquivoLabel.length) {
                    $campoArquivoLabel.find('span.text-danger').remove();
                }
            }
        };

        // Inicializa estado (após HTML/render)
        setTimeout(atualizarVisibilidade, 50);

        // Listener direto nos radios do formulário (evita interferência entre individual/lote)
        // e evita problemas de delegation quando algum handler interrompe bubbling.
        const $radios = $body.find(radiosSelector);
        $radios.off('.tramitacao-pdf');
        $radios.on('change.tramitacao-pdf click.tramitacao-pdf', atualizarVisibilidade);
    }
    
    /**
     * Obtém tipo do processo do formulário
     */
    obterTipoDoFormulario() {
        const form = document.getElementById('tramitacao_individual_form');
        if (!form) return null;
        
        const tipoInput = form.querySelector('input[name="hdn_tipo_tramitacao"]');
        if (tipoInput && tipoInput.value) {
            return tipoInput.value;
        }
        
        return null;
    }
    
    /**
     * Configura carregamento dinâmico de unidades e status
     */
    configurarCarregamentoDinamico(tipo, tipoSidebar = 'individual') {
        const self = this; // Define self para usar nos callbacks
        const body = this._obterBodyFormulario(tipoSidebar) || document;
        const selectDestElDom = (body.querySelector && body.querySelector('#field_lst_cod_unid_tram_dest, #lst_cod_unid_tram_dest')) || null;
        const selectStatusElDom = (body.querySelector && body.querySelector('#field_lst_cod_status, #lst_cod_status')) || null;
        const selectDestIdResolved = (selectDestElDom && selectDestElDom.id) ? `#${selectDestElDom.id}` : '#field_lst_cod_unid_tram_dest';
        const selectStatusIdResolved = (selectStatusElDom && selectStatusElDom.id) ? `#${selectStatusElDom.id}` : '#field_lst_cod_status';
        
        // Função para verificar e inicializar se as opções já estão presentes
        const verificarEInicializarOpcoesJaPresentes = () => {
            // Verifica se os selects existem no DOM
            const selectDest = $(selectDestIdResolved);
            const selectStatus = $(selectStatusIdResolved);
            
            if (selectDest.length === 0 || selectStatus.length === 0) {
                return false; // Selects ainda não estão no DOM
            }
            
            const temOpcoesDestino = selectDest.find('option').length > 0;
            const temOpcoesStatus = selectStatus.find('option').length > 0;
            
            // Se as opções já estão presentes, inicializa TomSelect diretamente
            if (temOpcoesDestino || temOpcoesStatus) {
                
                
                if (temOpcoesDestino) {
                    // Remove opção vazia se existir e adiciona "Selecione"
                    selectDest.find('option[value=""]').remove();
                    // Adiciona opção vazia "Selecione" no início se não existir
                    if (selectDest.find('option[value=""]').length === 0) {
                        selectDest.prepend($('<option>').val('').text('Selecione'));
                    }
                    // Remove qualquer seleção pré-existente
                    selectDest.find('option[selected]').removeAttr('selected');
                    // Garante que nenhum valor está selecionado
                    selectDest.val(null);
                    // Inicializa TomSelect se ainda não foi inicializado
                    const selectDestEl = selectDest[0];
                    if (!selectDestEl.tomselect) {
                        const dropdownParent = $(document.body);
                        this._inicializarTomSelect(selectDestIdResolved, 'Selecione a unidade de destino...', dropdownParent, false);
                        
                        // Garante que nenhum valor está selecionado após inicializar
                        selectDest.val(null).trigger('change');
                    }
                }
                
                if (temOpcoesStatus) {
                    // Remove opção vazia se existir e adiciona "Selecione"
                    selectStatus.find('option[value=""]').remove();
                    // Adiciona opção vazia "Selecione" no início se não existir
                    if (selectStatus.find('option[value=""]').length === 0) {
                        selectStatus.prepend($('<option>').val('').text('Selecione'));
                    }
                    // Remove qualquer seleção pré-existente
                    selectStatus.find('option[selected]').removeAttr('selected');
                    // Garante que nenhum valor está selecionado
                    selectStatus.val(null);
                    const selectStatusEl = selectStatus[0];
                    if (!selectStatusEl.tomselect) {
                        const dropdownParent = $(document.body);
                        this._inicializarTomSelect(selectStatusIdResolved, 'Selecione o status...', dropdownParent, false);
                        
                        // Garante que nenhum valor está selecionado após inicializar
                        selectStatus.val(null).trigger('change');
                    }
                }
                
                // Configura listeners para mudanças na unidade de origem (caso mude)
                // Nota: A unidade de origem é readonly, mas mantemos o listener caso isso mude no futuro
                const unidOrigem =
                                  (body.querySelector && (body.querySelector('#field_lst_cod_unid_tram_local, #lst_cod_unid_tram_local')?.value ||
                                  body.querySelector('input[name="lst_cod_unid_tram_local"]')?.value)) ||
                                  $('#field_lst_cod_unid_tram_local').val() ||
                                  document.getElementById('field_lst_cod_unid_tram_local')?.value ||
                                  document.getElementById('lst_cod_unid_tram_local')?.value ||
                                  document.querySelector('input[name="lst_cod_unid_tram_local"]')?.value ||
                                  (this.app && this.app.unidadeSelecionada) ||
                                  null;
                
                // Listener será configurado após carregarDestinoEStatus ser definido
                
                return true; // Opções já estavam presentes e foram inicializadas
            }
            
            return false; // Opções não estão presentes, precisa carregar via AJAX
        };
        
        // Tenta verificar se as opções já estão presentes (com retry)
        const tentarVerificarOpcoes = (tentativa = 0, callback) => {
            if (verificarEInicializarOpcoesJaPresentes()) {
                if (callback) callback(true); // Opções já estavam presentes, não precisa carregar via AJAX
                return true;
            }
            
            // Se não encontrou os selects ou as opções, tenta novamente após um delay
            if (tentativa < 3) {
                setTimeout(() => {
                    tentarVerificarOpcoes(tentativa + 1, callback);
                }, 300);
                return false;
            } else {
                // Após 3 tentativas, se ainda não encontrou, continua com o carregamento via AJAX
                if (callback) callback(false); // Não encontrou, precisa carregar via AJAX
                return false;
            }
        };
        
        // Inicia verificação após um pequeno delay para garantir que o DOM está pronto
        setTimeout(() => {
            tentarVerificarOpcoes(0, (opcoesJaPresentes) => {
                // Se as opções não estiverem presentes, carrega via AJAX
                if (!opcoesJaPresentes) {
                    // Aguarda um pouco mais para garantir que o HTML foi inserido no DOM
                    setTimeout(() => {
                        tentarCarregarUnidadesEStatus();
                    }, 500);
                }
            });
        }, 100);
        
        // Função para carregar unidades de destino e status baseado na unidade de origem
        const carregarDestinoEStatus = (unidOrigem) => {
            if (!unidOrigem) {
                // Limpa os campos e reinicializa TomSelect
                $(selectDestIdResolved).empty();
                $(selectStatusIdResolved).empty();
                // Destrói e recria TomSelect para limpar seleção
                const selectDestEl = document.querySelector(selectDestIdResolved);
                const selectStatusEl = document.querySelector(selectStatusIdResolved);
                if (selectDestEl && selectDestEl.tomselect) {
                    selectDestEl.tomselect.destroy();
                }
                if (selectStatusEl && selectStatusEl.tomselect) {
                    selectStatusEl.tomselect.destroy();
                }
                this._inicializarTomSelect(selectDestIdResolved, 'Selecione a unidade de destino...');
                this._inicializarTomSelect(selectStatusIdResolved, 'Selecione o status...');
                return;
            }
            
            // Carrega unidades de destino
            $.ajax({
                url: `${PORTAL_URL}/tramitacao_unidades_json`,
                method: 'POST',
                data: { svalue: unidOrigem, tipo: tipo },
                success: (response) => {
                    const unidades = typeof response === 'string' ? JSON.parse(response) : response;
                    const selectDestId = selectDestIdResolved;
                    $(selectDestId).empty();
                    if (unidades.length === 0 || (unidades.length === 1 && !unidades[0].id)) {
                        $(selectDestId).append(
                            $('<option>').val('').text('Nenhuma unidade de destino permitida. Configure permissões na unidade de origem.')
                        );
                        $(selectDestId).prop('disabled', true);
                    } else {
                        $(selectDestId).prop('disabled', false);
                        // Remove qualquer opção vazia antes de adicionar as opções reais
                        $(selectDestId).find('option[value=""]').remove();
                        // Adiciona opção vazia "Selecione" no início
                        $(selectDestId).prepend($('<option>').val('').text('Selecione'));
                        unidades.forEach(unid => {
                            $(selectDestId).append(
                                $('<option>').val(unid.id).text(unid.name)
                            );
                        });
                    }
                    const selectDest = $(selectDestId);
                    if (selectDest.length) {
                        const selectDestEl = selectDest[0];
                        if (selectDestEl.tomselect) {
                            selectDestEl.tomselect.destroy();
                        }
                        // Garante que nenhum valor está selecionado antes de inicializar
                        selectDest.val('').trigger('change');
                        // Aguarda um pouco para garantir que o DOM foi atualizado
                        setTimeout(() => {
                            // Adiciona opção vazia "Selecione" apenas se não existir
                            if (selectDest.find('option[value=""]').length === 0) {
                                selectDest.prepend($('<option>').val('').text('Selecione'));
                            }
                            // Anexa o dropdown ao body para evitar problemas com offcanvas do Bootstrap
                            const dropdownParent = $(document.body);
                            
                            // Remove mensagem de validação HTML5 padrão
                            selectDest.off('invalid').on('invalid', function(e) {
                                e.preventDefault();
                                this.setCustomValidity('');
                                return false;
                            });
                            selectDest.off('input change').on('input change', function() {
                                this.setCustomValidity('');
                            });
                            
                            // Inicializa/recria TomSelect com os novos options
                            const selectDestEl = selectDest[0];
                            if (selectDestEl.tomselect) {
                                selectDestEl.tomselect.destroy();
                            }
                            self._inicializarTomSelect(selectDestId, 'Selecione a unidade de destino...', dropdownParent, false);
                            
                            // Adiciona listener para validação em tempo real (com namespace para evitar conflitos)
                            // Usa arrow function para manter o contexto correto
                            if (selectDestEl.tomselect) {
                                selectDestEl.tomselect.off('change');
                                selectDestEl.tomselect.on('change', () => {
                                    const valor = selectDestEl.tomselect.getValue();
                                    if (valor && valor !== '') {
                                        self._marcarCampoValido('#field_lst_cod_unid_tram_dest');
                                    }
                                });
                            }
                            // Garante que nenhum valor está selecionado após inicializar
                            selectDest.val(null).trigger('change');
                        }, 100);
                    } else {
                        console.error('TramitacaoSidebarManager - Select #field_lst_cod_unid_tram_dest não encontrado no DOM');
                    }
                },
                error: (xhr, status, error) => {
                    console.error('TramitacaoSidebarManager - Erro ao carregar unidades de destino:', status, error, xhr.responseText);
                    $(selectDestIdResolved).empty();
                    this._inicializarTomSelect(selectDestIdResolved, 'Erro ao carregar unidades de destino');
                }
            });
            
            // Carrega status
            $.ajax({
                url: `${PORTAL_URL}/tramitacao_status_json`,
                method: 'POST',
                data: { svalue: unidOrigem, tipo: tipo },
                success: (response) => {
                    const status = typeof response === 'string' ? JSON.parse(response) : response;
                    const selectStatusId = selectStatusIdResolved;
                    $(selectStatusId).empty();
                    if (status.length === 0 || (status.length === 1 && !status[0].id)) {
                        $(selectStatusId).append(
                            $('<option>').val('').text('Nenhum status permitido. Configure permissões na unidade de origem.')
                        );
                        $(selectStatusId).prop('disabled', true);
                    } else {
                        $(selectStatusId).prop('disabled', false);
                        // Remove qualquer opção vazia antes de adicionar as opções reais
                        $(selectStatusId).find('option[value=""]').remove();
                        // Adiciona opção vazia "Selecione" no início
                        $(selectStatusId).prepend($('<option>').val('').text('Selecione'));
                        status.forEach(st => {
                            $(selectStatusId).append(
                                $('<option>').val(st.id).text(st.name)
                            );
                        });
                    }
                    const selectStatus = $(selectStatusId);
                    if (selectStatus.length) {
                        const selectStatusEl = selectStatus[0];
                        if (selectStatusEl.tomselect) {
                            selectStatusEl.tomselect.destroy();
                        }
                        // Garante que nenhum valor está selecionado antes de inicializar
                        selectStatus.val('').trigger('change');
                        // Aguarda um pouco para garantir que o DOM foi atualizado
                        setTimeout(() => {
                            // Adiciona opção vazia "Selecione" apenas se não existir
                            if (selectStatus.find('option[value=""]').length === 0) {
                                selectStatus.prepend($('<option>').val('').text('Selecione'));
                            }
                            // Anexa o dropdown ao body para evitar problemas com offcanvas do Bootstrap
                            const dropdownParent = $(document.body);
                            
                            // Remove mensagem de validação HTML5 padrão
                            selectStatus.off('invalid').on('invalid', function(e) {
                                e.preventDefault();
                                this.setCustomValidity('');
                                return false;
                            });
                            selectStatus.off('input change').on('input change', function() {
                                this.setCustomValidity('');
                            });
                            
                            // Inicializa/recria TomSelect com os novos options
                            const selectStatusEl = selectStatus[0];
                            if (selectStatusEl.tomselect) {
                                selectStatusEl.tomselect.destroy();
                            }
                            self._inicializarTomSelect(selectStatusIdResolved, 'Selecione o status...', dropdownParent, false);
                            
                            // Adiciona listener para validação em tempo real (com namespace para evitar conflitos)
                            // Usa arrow function para manter o contexto correto
                            if (selectStatusEl.tomselect) {
                                selectStatusEl.tomselect.off('change');
                                selectStatusEl.tomselect.on('change', () => {
                                    const valor = selectStatusEl.tomselect.getValue();
                                    if (valor && valor !== '') {
                                        self._marcarCampoValido('#field_lst_cod_status');
                                    }
                                });
                            }
                            // Garante que nenhum valor está selecionado após inicializar
                            selectStatus.val(null).trigger('change');
                        }, 100);
                    } else {
                        console.error('TramitacaoSidebarManager - Select #field_lst_cod_status não encontrado no DOM');
                    }
                },
                error: (xhr, status, error) => {
                    console.error('TramitacaoSidebarManager - Erro ao carregar status:', status, error, xhr.responseText);
                    $(selectStatusIdResolved).empty();
                    this._inicializarTomSelect(selectStatusIdResolved, 'Erro ao carregar status');
                }
            });
        };
        
        // Função para tentar carregar unidades/status após inserir HTML
        const tentarCarregarUnidadesEStatus = (tentativa = 0) => {
            const unidOrigem =
                              (body.querySelector && (body.querySelector('#field_lst_cod_unid_tram_local, #lst_cod_unid_tram_local')?.value ||
                              body.querySelector('input[name="lst_cod_unid_tram_local"]')?.value)) ||
                              $('#field_lst_cod_unid_tram_local').val() ||
                              document.getElementById('field_lst_cod_unid_tram_local')?.value ||
                              document.getElementById('lst_cod_unid_tram_local')?.value ||
                              document.querySelector('input[name="lst_cod_unid_tram_local"]')?.value ||
                              (this.app && this.app.unidadeSelecionada) ||
                              null;
            
            if (unidOrigem) {
                carregarDestinoEStatus(unidOrigem);
                return;
            }
            
            if (tentativa < 5) {
                setTimeout(() => tentarCarregarUnidadesEStatus(tentativa + 1), 300);
            } else {
                console.warn('TramitacaoSidebarManager - Unidade de origem não encontrada para carregar destino/status');
            }
        };
        
        // Listener para mudanças na unidade de origem (caso mude)
        $('#field_lst_cod_unid_tram_local, #lst_cod_unid_tram_local')
            .off('change.tramitacao-dinamico')
            .on('change.tramitacao-dinamico', function() {
                const unidOrigem = $(this).val();
                carregarDestinoEStatus(unidOrigem);
            });
    }
}

// -----------------------------------------------------------------------------
// Integração com tasks (PDF/anexo) após salvar tramitação
// O DTML (`tramitacao_digital.dtml`) chama `processarRespostaSalvarTramitacao(...)`.
// -----------------------------------------------------------------------------
(function() {
    if (typeof window === 'undefined') return;
    if (typeof window.processarRespostaSalvarTramitacao === 'function') return;

    function obterTipoAtual() {
        try {
            const form = document.getElementById('tramitacao_individual_form');
            const tipoEl = form ? form.querySelector('input[name="hdn_tipo_tramitacao"]') : null;
            const tipo = (tipoEl && tipoEl.value) ? String(tipoEl.value) : null;
            return tipo || 'MATERIA';
        } catch (_) {
            return 'MATERIA';
        }
    }

    function atualizarLinkPdf(codTramitacao, tipo) {
        try {
            const cod = String(codTramitacao);
            const isMateria = String(tipo) === 'MATERIA';
            const pdfPath = isMateria
                ? `/sapl_documentos/materia/tramitacao/${cod}_tram.pdf`
                : `/sapl_documentos/administrativo/tramitacao/${cod}_tram.pdf`;
            const baseUrl = `${PORTAL_URL}${pdfPath}`;
            const ts = Date.now();
            const sep = baseUrl.includes('?') ? '&' : '?';
            const link = `${baseUrl}${sep}_t=${ts}`;

            const btnPdf = document.getElementById('btn_visualizar_pdf_tramitacao');
            if (btnPdf) {
                btnPdf.href = link;
                btnPdf.setAttribute('data-link-pdf', link);
            }
            if (typeof window.atualizarLinkPdfTramitacao === 'function') {
                try { window.atualizarLinkPdfTramitacao(link); } catch (_) {}
            }
            return link;
        } catch (_) {
            return null;
        }
    }

    function pollStatus(task, onDone) {
        const taskId = task && (task.task_id || task.taskId || task.id);
        const monitorUrl = task && task.monitor_url;
        if (!taskId || !monitorUrl) return;

        let tentativas = 0;
        const maxTentativas = 120; // ~2 min (1s)

        const tick = () => {
            tentativas += 1;
            jQuery.ajax({
                url: monitorUrl,
                method: 'GET',
                dataType: 'json',
                success: (status) => {
                    const st = status && status.status ? String(status.status) : 'UNKNOWN';
                    if (st === 'SUCCESS') {
                        onDone(null, status);
                        return;
                    }
                    if (st === 'FAILURE') {
                        onDone(status || { error: 'FAILURE' }, null);
                        return;
                    }
                    if (tentativas >= maxTentativas) {
                        onDone({ error: 'timeout', status }, null);
                        return;
                    }
                    setTimeout(tick, 1000);
                },
                error: (xhr) => {
                    if (tentativas >= maxTentativas) {
                        onDone({ error: 'timeout', xhr }, null);
                        return;
                    }
                    setTimeout(tick, 1000);
                }
            });
        };
        tick();
    }

    window.processarRespostaSalvarTramitacao = function(response, codTramitacao /*, naoRecarregarFormulario */) {
        try {
            if (typeof jQuery === 'undefined') return;

            const cod = codTramitacao || (response && response.cod_tramitacao);
            if (!cod) return;

            // Task de anexo: precisa salvar no repositório via @@tramitacao_anexar_arquivo_salvar
            const taskAnexo = response && response.task_anexo;
            if (taskAnexo && taskAnexo.task_id && taskAnexo.monitor_url) {
                const tipo = obterTipoAtual();

                pollStatus(taskAnexo, (err, statusOk) => {
                    if (err) {
                        if (window.tramitacaoApp && window.tramitacaoApp.mostrarToast) {
                            window.tramitacaoApp.mostrarToast('Erro', 'Falha ao anexar PDF (task). Verifique o worker de tasks.', 'error');
                        }
                        console.error('[Tramitação] Task anexo falhou/timeout:', err);
                        return;
                    }

                    // Task terminou: salva o PDF juntado no repositório Zope
                    jQuery.ajax({
                        url: `${PORTAL_URL}/@@tramitacao_anexar_arquivo_salvar`,
                        method: 'GET',
                        dataType: 'json',
                        data: { task_id: taskAnexo.task_id },
                        success: (resp) => {
                            if (resp && resp.erro) {
                                if (window.tramitacaoApp && window.tramitacaoApp.mostrarToast) {
                                    window.tramitacaoApp.mostrarToast('Erro', resp.erro, 'error');
                                }
                                console.error('[Tramitação] Erro ao salvar PDF juntado:', resp);
                                return;
                            }

                            // Atualiza link do PDF com cache-buster
                            atualizarLinkPdf(cod, tipo);

                            if (window.tramitacaoApp && window.tramitacaoApp.mostrarToast) {
                                window.tramitacaoApp.mostrarToast('Sucesso', 'PDF anexado ao despacho com sucesso.', 'success');
                            }
                        },
                        error: (xhr) => {
                            console.error('[Tramitação] Erro ao chamar @@tramitacao_anexar_arquivo_salvar:', xhr);
                            if (window.tramitacaoApp && window.tramitacaoApp.mostrarToast) {
                                window.tramitacaoApp.mostrarToast('Erro', 'Falha ao salvar PDF anexado (view salvar).', 'error');
                            }
                        }
                    });
                });
            }
        } catch (e) {
            console.error('[Tramitação] Erro em processarRespostaSalvarTramitacao:', e);
        }
    };
})();

// Inicializa aplicativo global (script é incluído no final do DTML)
(function() {
    try {
        if (!window.tramitacaoApp) {
            window.tramitacaoApp = new TramitacaoEmailStyle();
        }
    } catch (e) {
        console.error('[Tramitação] Falha ao inicializar tramitacaoApp:', e);
    }
})();
