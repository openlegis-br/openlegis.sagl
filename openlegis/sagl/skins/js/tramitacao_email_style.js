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
    async     checkForUpdates() {
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
            url += `&forcar_atualizacao=true`;
            
            
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
        if (this.unidadesUsuario.length === 0) {
            await this.carregarUnidadesUsuario();
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
        
        // Para rascunhos, usa dat_tramitacao; para outros, usa dat_encaminha
        const dataTramitacao = this.filtroAtual === 'rascunhos' ? 
            (processo.dat_tramitacao || processo.dat_encaminha) : 
            processo.dat_encaminha;
        const dataFormatada = this.formatarData(dataTramitacao);
        const status = processo.des_status || 'Sem status';
        
        // Data de fim de prazo (apenas data, sem horário)
        let prazoHtml = '';
        if (processo.dat_fim_prazo) {
            const dataFimPrazo = new Date(processo.dat_fim_prazo);
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
        
        // ✅ MELHORADO: Checkbox com melhor posicionamento e acessibilidade
        const checkboxHtml = podeSelecionar 
            ? `<div class="form-check mt-2 flex-shrink-0" style="margin-top: 0.25rem !important;">
                   <input class="form-check-input checkbox-processo" 
                          type="checkbox" 
                          data-cod-entidade="${codEntidade}" 
                          ${isSelecionado ? 'checked' : ''}
                          aria-label="Selecionar processo ${codEntidade}">
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
        // Prioriza totalItens (da lista carregada) se disponível, senão usa contador da sidebar
        let contador;
        if (this.totalItens !== undefined && this.totalItens !== null) {
            // Usa totalItens se estiver disponível (mais confiável - vem do backend)
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
    mostrarToast(mensagem, tipo = 'info', duracao = 2500) {
        const tipos = {
            success: { icon: 'mdi-check-circle', bg: 'bg-success' },
            error: { icon: 'mdi-alert-circle', bg: 'bg-danger' },
            warning: { icon: 'mdi-alert', bg: 'bg-warning' },
            info: { icon: 'mdi-information', bg: 'bg-info' }
        };
        
        const config = tipos[tipo] || tipos.info;
        
        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header ${config.bg} text-white">
                    <i class="mdi ${config.icon} me-2"></i>
                    <strong class="me-auto">${tipo.charAt(0).toUpperCase() + tipo.slice(1)}</strong>
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
    
    /**
     * Abre sidebar de tramitação individual
     * IMPORTANTE: Formulário sempre é renderizado no sidebar (offcanvas)
     */
    abrirModalTramitacaoIndividual(codEntidade, tipo, codTramitacaoRecebida = null) {
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
        // Sempre usa sidebar (offcanvas), nunca modal
        if (this.sidebarManager) {
            this.sidebarManager.abrirTramitacaoLote();
        } else {
            this.mostrarToast('Erro', 'Sidebar manager não inicializado', 'error');
        }
    }
    
    /**
     * Formata data
     */
    formatarData(dataISO) {
        if (!dataISO) return '';
        try {
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
        this.init();
    }
    
    /**
     * Verifica se um elemento tem Select2 inicializado
     */
    _temSelect2(selector) {
        if (typeof $ === 'undefined' || typeof $().select2 === 'undefined') {
            return false;
        }
        const $el = $(selector);
        if ($el.length === 0) {
            return false;
        }
        // Verifica cada elemento individualmente
        let temSelect2 = false;
        $el.each(function() {
            const $this = $(this);
            // Select2 pode armazenar dados de várias formas
            // Verifica se tem a classe select2-hidden-accessible ou data-select2-id
            if ($this.hasClass('select2-hidden-accessible') || 
                $this.data('select2-id') !== undefined ||
                $this.next('.select2-container').length > 0) {
                temSelect2 = true;
                return false; // Para o loop
            }
        });
        return temSelect2;
    }
    
    /**
     * Destrói Select2 de forma segura (só se estiver inicializado)
     */
    _destruirSelect2(selector) {
        if (typeof $ === 'undefined' || typeof $().select2 === 'undefined') {
            return; // Select2 não está disponível
        }
        const $el = $(selector);
        if ($el.length === 0) {
            return; // Elementos não existem
        }
        
        // Destrói cada elemento individualmente de forma segura
        $el.each(function() {
            const $this = $(this);
            // Verifica se tem Select2 antes de tentar destruir
            if ($this.hasClass('select2-hidden-accessible') || 
                $this.data('select2-id') !== undefined ||
                $this.next('.select2-container').length > 0) {
                try {
                    $this.select2('destroy');
                } catch (e) {
                    // Ignora erro se houver algum problema
                    // Não loga para evitar poluição do console
                }
            }
        });
    }
    
    /**
     * Inicializa Select2 de forma padronizada
     */
    _inicializarSelect2(selector, placeholder) {
        if (typeof $ === 'undefined' || typeof $().select2 === 'undefined') {
            return; // Select2 não está disponível
        }
        const $el = $(selector);
        if ($el.length === 0) {
            return; // Elemento não encontrado
        }
        
        // Adiciona opção vazia "Selecione" apenas se não existir
        if ($el.find('option[value=""]').length === 0) {
            $el.prepend($('<option>').val('').text('Selecione'));
        }
        
        // Anexa o dropdown ao body para evitar problemas com offcanvas do Bootstrap
        // O offcanvas pode bloquear eventos de clique no dropdown
        const dropdownParent = $(document.body);
        
        // Desabilita mensagem de validação HTML5 padrão antes de inicializar Select2
        $el.each(function() {
            const $select = $(this);
            
            // Remove mensagem de validação HTML5 padrão
            $select.on('invalid', function(e) {
                e.preventDefault();
                this.setCustomValidity('');
                return false;
            });
            
            // Limpa mensagem customizada quando o campo é alterado
            $select.on('input change', function() {
                this.setCustomValidity('');
            });
        });
        
        $el.select2({
            width: '100%',
            language: 'pt-BR',
            placeholder: placeholder,
            allowClear: false,
            // Desabilita busca (Infinity = nunca mostrar)
            minimumResultsForSearch: Infinity,
            // Anexa o dropdown ao sidebar para funcionar corretamente dentro do offcanvas
            dropdownParent: dropdownParent,
            // Não oculta opção vazia - pode causar problemas de seleção
            // templateResult removido para evitar problemas de clique
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
    
    init() {
        // Inicializa sidebars Bootstrap Offcanvas
        // Nota: Se elementos não existirem ainda, serão inicializados quando necessário
        // Usa setTimeout para garantir que o DOM está completamente renderizado
        setTimeout(() => {
            const sidebarIndividualEl = document.getElementById('tramitacaoIndividualOffcanvas');
            if (sidebarIndividualEl && typeof bootstrap !== 'undefined') {
                try {
                    this.sidebarIndividual = new bootstrap.Offcanvas(sidebarIndividualEl);
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
        // IMPORTANTE: data-bs-focus="false" é OBRIGATÓRIO para que Select2, TinyMCE e Bootstrap Datepicker funcionem corretamente
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
            aria-label="Fechar"></button>
  </div>
  <div class="offcanvas-body" id="tramitacaoIndividualOffcanvasBody">
    <!-- Conteúdo carregado via AJAX -->
  </div>
  <div class="offcanvas-footer border-top p-3 bg-light">
    <div class="d-flex gap-2 justify-content-between">
      <button type="button" 
              class="btn btn-secondary" 
              id="btnCancelarIndividual">
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
        // IMPORTANTE: data-bs-focus="false" é OBRIGATÓRIO para que Select2, TinyMCE e Bootstrap Datepicker funcionem corretamente
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
                id="btnCancelarLote">
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
        const campoDataFimPrazo = body.querySelector('#field_txt_dat_fim_prazo');
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
        const normalizar = (valor) => {
            if (valor === null || valor === undefined) return null;
            const str = String(valor).trim();
            if (str === '' || str === '0') return null;
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
        
        // Monitora mudanças em Select2 (se existir)
        // Select2 não usa data-select2, então monitoramos pelos IDs conhecidos
        if (typeof $ !== 'undefined' && typeof $().select2 !== 'undefined') {
            const select2Ids = isIndividual 
                ? ['#field_lst_cod_unid_tram_dest', '#field_lst_cod_status', '#field_lst_cod_usuario_dest']
                : ['#field_lst_cod_unid_tram_dest', '#field_lst_cod_status', '#field_lst_cod_usuario_dest'];
            
            select2Ids.forEach(selector => {
                const $select = $(selector);
                if ($select.length > 0) {
                    // Remove listeners anteriores
                    $select.off('change.backdrop select2:select.backdrop');
                    // Adiciona listeners para mudanças no Select2
                    $select.on('change.backdrop', () => {
                        console.log(`Select2 alterado: ${selector}, atualizando backdrop...`);
                        setTimeout(() => {
                            sidebarManager._atualizarBackdropProtecao(tipo);
                        }, 0);
                    });
                    $select.on('select2:select.backdrop', () => {
                        console.log(`Select2 selecionado: ${selector}, atualizando backdrop...`);
                        setTimeout(() => {
                            sidebarManager._atualizarBackdropProtecao(tipo);
                        }, 0);
                    });
                }
            });
        }
    }
    
    /**
     * Tenta fechar o sidebar com verificação de proteção
     * @param {string} tipo - 'individual' ou 'lote'
     */
    _tentarFecharSidebar(tipo) {
        const isIndividual = tipo === 'individual';
        const sidebar = isIndividual ? this.sidebarIndividual : this.sidebarLote;
        const protecao = isIndividual ? this.protecaoFechamentoIndividual : this.protecaoFechamentoLote;
        
        if (!sidebar) {
            return;
        }
        
        // Se a proteção estiver desativada, fecha diretamente
        if (!protecao) {
            sidebar.hide();
            return;
        }
        
        // Verifica se há dados não salvos
        if (this._temDadosNaoSalvos(tipo)) {
            // Mostra modal de confirmação
            this._mostrarConfirmacaoFechamento(tipo, () => {
                // Usuário confirmou - desativa proteção e fecha
                if (isIndividual) {
                    this.protecaoFechamentoIndividual = false;
                } else {
                    this.protecaoFechamentoLote = false;
                }
                sidebar.hide();
            });
        } else {
            // Não há dados, pode fechar diretamente
            sidebar.hide();
        }
    }
    
    setupEventListeners() {
        // Listener global para fechar Datepicker ao clicar fora
        $(document).on('mousedown', (e) => {
            // Pequeno delay para permitir que o Datepicker processe primeiro
            setTimeout(() => {
                this.forcarFechamentoFlatpickr(e);
            }, 10);
        });
        
        // Intercepta cliques no backdrop usando captura de eventos
        // Usa addEventListener com capture: true para interceptar ANTES do Bootstrap processar
        const sidebarManager = this;
        document.addEventListener('click', function(e) {
            // Verifica se o clique foi no backdrop
            const backdrop = e.target;
            if (!backdrop || !backdrop.classList || !backdrop.classList.contains('offcanvas-backdrop')) {
                return;
            }
            
            // Verifica qual sidebar está aberto
            const sidebarIndividual = document.getElementById('tramitacaoIndividualOffcanvas');
            const sidebarLote = document.getElementById('tramitacaoLoteOffcanvas');
            
            let tipo = null;
            let sidebar = null;
            let sidebarInstance = null;
            
            if (sidebarIndividual && sidebarIndividual.classList.contains('show')) {
                tipo = 'individual';
                sidebar = sidebarIndividual;
                sidebarInstance = sidebarManager.sidebarIndividual;
            } else if (sidebarLote && sidebarLote.classList.contains('show')) {
                tipo = 'lote';
                sidebar = sidebarLote;
                sidebarInstance = sidebarManager.sidebarLote;
            } else {
                return; // Nenhum sidebar está aberto
            }
            
            console.log(`Clique no backdrop detectado (${tipo}), verificando dados não salvos...`);
            
            // Previne múltiplos cliques simultâneos
            if (sidebarManager.processandoCliqueBackdrop) {
                console.log('Clique no backdrop já está sendo processado, ignorando...');
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
            
            // Verifica proteção baseado no tipo
            const protecao = tipo === 'individual' 
                ? sidebarManager.protecaoFechamentoIndividual 
                : sidebarManager.protecaoFechamentoLote;
            
            if (!protecao) {
                return; // Proteção desativada, permite fechamento normal
            }
            
            // Verifica se há dados não salvos
            if (sidebarManager._temDadosNaoSalvos(tipo)) {
                // Marca que está processando
                sidebarManager.processandoCliqueBackdrop = true;
                
                // Previne o fechamento ANTES do Bootstrap processar
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                
                // IMPORTANTE: Previne que o Bootstrap processe o clique no backdrop
                const backdropEl = document.querySelector('.offcanvas-backdrop');
                if (backdropEl) {
                    backdropEl.style.pointerEvents = 'none';
                    setTimeout(() => {
                        if (backdropEl && backdropEl.parentNode) {
                            backdropEl.style.pointerEvents = '';
                        }
                    }, 100);
                }
                
                // Mostra modal de confirmação IMEDIATAMENTE (sem delay)
                sidebarManager._mostrarConfirmacaoFechamento(tipo, () => {
                    // Usuário confirmou - permite fechamento
                    sidebarManager.processandoCliqueBackdrop = false; // Libera flag
                    if (tipo === 'individual') {
                        sidebarManager.protecaoFechamentoIndividual = false;
                        if (sidebarManager.sidebarIndividual) {
                            sidebarManager.sidebarIndividual.hide();
                        }
                    } else {
                        sidebarManager.protecaoFechamentoLote = false;
                        if (sidebarManager.sidebarLote) {
                            sidebarManager.sidebarLote.hide();
                        }
                    }
                });
                
                // Libera flag após um tempo caso o modal não seja mostrado
                setTimeout(() => {
                    sidebarManager.processandoCliqueBackdrop = false;
                }, 1000);
                
                return false;
            }
        }, true); // true = capture phase (antes do bubbling)
        
        // Proteção contra fechamento acidental - Sidebar Individual
        if (this.sidebarIndividual) {
            const sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
            
            // Intercepta tentativa de fechamento para verificar se há dados não salvos
            // IMPORTANTE: Este evento é disparado ANTES do fechamento visual, então podemos prevenir
            // Usa múltiplos listeners para garantir interceptação
            const handlerHide = (e) => {
                console.log('Sidebar fechando, verificando se há dados não salvos...');
                
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
                        // Usuário confirmou - permite fechamento
                        this.protecaoFechamentoIndividual = false; // Desativa proteção temporariamente
                        // Atualiza backdrop antes de fechar
                        this._atualizarBackdropProtecao('individual');
                        if (this.sidebarIndividual) {
                            this.sidebarIndividual.hide();
                        }
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
                        // Usuário confirmou - permite fechamento
                        this.protecaoFechamentoLote = false; // Desativa proteção temporariamente
                        // Atualiza backdrop antes de fechar
                        this._atualizarBackdropProtecao('lote');
                        if (this.sidebarLote) {
                            this.sidebarLote.hide();
                        }
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
        $(document).on('click', '#btnFecharSidebarIndividual, #btnCancelarIndividual', function(e) {
            e.preventDefault();
            e.stopPropagation();
            // Usa a referência armazenada para garantir contexto correto
            const manager = sidebarManagerButtons || (window.tramitacaoApp && window.tramitacaoApp.sidebarManager);
            if (manager && typeof manager._tentarFecharSidebar === 'function') {
                manager._tentarFecharSidebar('individual');
            } else {
                console.error('_tentarFecharSidebar não é uma função ou manager não encontrado');
                // Fallback: fecha diretamente se a função não estiver disponível
                if (manager && manager.sidebarIndividual) {
                    manager.sidebarIndividual.hide();
                }
            }
        });
        
        $(document).on('click', '#btnFecharSidebarLote, #btnCancelarLote', function(e) {
            e.preventDefault();
            e.stopPropagation();
            // Usa a referência armazenada para garantir contexto correto
            const manager = sidebarManagerButtons || (window.tramitacaoApp && window.tramitacaoApp.sidebarManager);
            if (manager && typeof manager._tentarFecharSidebar === 'function') {
                manager._tentarFecharSidebar('lote');
            } else {
                console.error('_tentarFecharSidebar não é uma função ou manager não encontrado');
                // Fallback: fecha diretamente se a função não estiver disponível
                if (manager && manager.sidebarLote) {
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
        this.obterDadosTramitacao(cod_tramitacao, tipo, (dados) => {
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
            this.sidebarLote.show();
            // Atualiza backdrop após mostrar o sidebar
            setTimeout(() => {
                this._atualizarBackdropProtecao('lote');
            }, 100);
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
                this.obterDadosTramitacao(cod_tramitacao, tipo, (dados) => {
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
                
            // Popula unidade de destino (aguarda carregamento das unidades via AJAX)
            if (dados.cod_unid_tram_dest) {
                setTimeout(() => {
                    // Aguarda Select2 estar pronto
                    const selectDest = $('#field_lst_cod_unid_tram_dest');
                    if (selectDest.length && selectDest.data('select2')) {
                        selectDest.val(dados.cod_unid_tram_dest).trigger('change.select2');
                    } else {
                        // Se Select2 ainda não foi inicializado, tenta novamente
                        setTimeout(() => {
                            $('#field_lst_cod_unid_tram_dest').val(dados.cod_unid_tram_dest).trigger('change.select2');
                        }, 500);
                    }
                    
                    // Carrega usuários da unidade de destino diretamente (se já estiver selecionada)
                    // Isso garante que os usuários sejam carregados mesmo que o evento change não dispare corretamente
                    const carregarUsuariosDaUnidade = () => {
                        const unidDest = dados.cod_unid_tram_dest;
                        if (!unidDest) return;
                        
                        $.ajax({
                            url: `${PORTAL_URL}/tramitacao_usuarios_json`,
                            method: 'POST',
                            data: { svalue: unidDest },
                            success: (response) => {
                                const usuarios = typeof response === 'string' ? JSON.parse(response) : response;
                                const $selectUsuario = $('#field_lst_cod_usuario_dest');
                                $selectUsuario.empty();
                                // Adiciona opção vazia "Selecione" no início
                                $selectUsuario.append($('<option>').val('').text('Selecione'));
                                usuarios.forEach(usr => {
                                    if (usr.id && usr.name) {
                                        $selectUsuario.append(
                                            $('<option>').val(usr.id).text(usr.name)
                                        );
                                    }
                                });
                                
                                // Atualiza Select2 se já foi inicializado
                                if ($selectUsuario.data('select2')) {
                                    $selectUsuario.trigger('change.select2');
                                } else {
                                    $selectUsuario.trigger('change');
                                }
                                
                                // Popula usuário de destino após carregar os usuários
                                if (dados.cod_usuario_dest) {
                                    setTimeout(() => {
                                        const selectUsuario = $('#field_lst_cod_usuario_dest');
                                        if (selectUsuario.length) {
                                            if (selectUsuario.data('select2')) {
                                                selectUsuario.val(dados.cod_usuario_dest).trigger('change.select2');
                                            } else {
                                                selectUsuario.val(dados.cod_usuario_dest).trigger('change');
                                            }
                                        }
                                    }, 200);
                                }
                            },
                            error: (xhr, status, error) => {
                                console.error('Erro ao carregar usuários da unidade:', error);
                            }
                        });
                    };
                    
                    // Carrega usuários após um pequeno delay para garantir que o Select2 está pronto
                    setTimeout(carregarUsuariosDaUnidade, 400);
                }, 800);
            }
            
            // Popula status (aguarda carregamento dos status via AJAX)
            if (dados.cod_status) {
                setTimeout(() => {
                    const selectStatus = $('#field_lst_cod_status');
                    if (selectStatus.length && selectStatus.data('select2')) {
                        selectStatus.val(dados.cod_status).trigger('change.select2');
                    } else {
                        setTimeout(() => {
                            $('#field_lst_cod_status').val(dados.cod_status).trigger('change.select2');
                        }, 500);
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
                $('#txt_dat_fim_prazo').val(dados.dat_fim_prazo);
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
                // (aguarda Select2 e outros componentes serem inicializados)
                setTimeout(() => {
                    this._salvarEstadoInicialFormulario('individual');
                }, 2000);
            }
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
            
            // Select2 para campos do formulário individual
            if (typeof $().select2 !== 'undefined') {
                // Remove Select2 existente se houver (para evitar duplicação)
                this._destruirSelect2('#field_lst_cod_unid_tram_dest, #field_lst_cod_usuario_dest, #field_lst_cod_status');
                
                // NÃO inicializa Select2 aqui - será inicializado após carregar os dados via AJAX
                // Apenas inicializa o select de usuário de destino (que não depende de dados externos)
                // Anexa o dropdown ao body para evitar problemas com offcanvas do Bootstrap
                const dropdownParentUsuario = $(document.body);
                
                const $selectUsuario = $('#field_lst_cod_usuario_dest');
                
                // Adiciona opção vazia "Selecione" se não existir
                if ($selectUsuario.find('option[value=""]').length === 0) {
                    $selectUsuario.prepend($('<option>').val('').text('Selecione'));
                }
                
                // Remove mensagem de validação HTML5 padrão
                $selectUsuario.on('invalid', function(e) {
                    e.preventDefault();
                    this.setCustomValidity('');
                    return false;
                });
                
                // Limpa mensagem customizada quando o campo é alterado
                $selectUsuario.on('input change', function() {
                    this.setCustomValidity('');
                });
                
                $selectUsuario.select2({
                    width: '100%',
                    language: 'pt-BR',
                    placeholder: 'Selecione o usuário de destino...',
                    allowClear: false,
                    // Desabilita busca (Infinity = nunca mostrar)
                    minimumResultsForSearch: Infinity,
                    // Anexa o dropdown ao sidebar para funcionar corretamente dentro do offcanvas
                    dropdownParent: dropdownParentUsuario
                });
                
                // Garante que nenhum valor está selecionado após inicializar
                $selectUsuario.val(null).trigger('change');
                
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
            this._configurarCampoPdf();
            
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
                    this.configurarCarregamentoDinamico(tipo);
                }, 300);
            }
            
            // Configura validação em tempo real para campos obrigatórios
            this._configurarValidacaoTempoReal();
        }, 100);
    }
    
    /**
     * Configura campo de arquivo PDF para mostrar/ocultar baseado na opção selecionada
     */
    _configurarCampoPdf() {
        // Tenta encontrar o campo pelo ID com prefixo field_ ou sem prefixo
        const campoArquivoInput = $('#field_file_nom_arquivo, #file_nom_arquivo');
        if (!campoArquivoInput.length) {
            return;
        }
        
        const campoArquivo = campoArquivoInput.closest('.col-12, .col-md-8');
        const campoArquivoLabel = campoArquivo.find('label');
        
        // Função para mostrar/ocultar campo
        const atualizarVisibilidade = () => {
            const opcaoSelecionada = $('input[name="radTI"]:checked').val();
            if (opcaoSelecionada === 'S') {
                // Mostra campo e habilita
                campoArquivo.slideDown(200);
                campoArquivoInput.prop('disabled', false).attr('required', true);
                campoArquivoLabel.find('span.text-danger').remove();
                if (!campoArquivoLabel.find('span.text-danger').length) {
                    campoArquivoLabel.append(' <span class="text-danger" aria-label="obrigatório">*</span>');
                }
            } else {
                // Oculta campo e desabilita
                campoArquivo.slideUp(200);
                campoArquivoInput.prop('disabled', true).removeAttr('required').val('');
                campoArquivoLabel.find('span.text-danger').remove();
            }
        };
        
        // Inicializa estado
        setTimeout(() => {
            atualizarVisibilidade();
        }, 100);
        
        // Listener para mudanças nos radio buttons
        $(document).off('change', 'input[name="radTI"]').on('change', 'input[name="radTI"]', atualizarVisibilidade);
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
    configurarCarregamentoDinamico(tipo) {
        const self = this; // Define self para usar nos callbacks
        
        // Função para verificar e inicializar se as opções já estão presentes
        const verificarEInicializarOpcoesJaPresentes = () => {
            // Verifica se os selects existem no DOM
            const selectDest = $('#field_lst_cod_unid_tram_dest');
            const selectStatus = $('#field_lst_cod_status');
            
            if (selectDest.length === 0 || selectStatus.length === 0) {
                return false; // Selects ainda não estão no DOM
            }
            
            const temOpcoesDestino = selectDest.find('option').length > 0;
            const temOpcoesStatus = selectStatus.find('option').length > 0;
            
            // Se as opções já estão presentes, inicializa Select2 diretamente
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
                    // Inicializa Select2 se ainda não foi inicializado
                    if (!selectDest.data('select2')) {
                        const dropdownParent = $(document.body);
                        selectDest.select2({
                            width: '100%',
                            language: 'pt-BR',
                            placeholder: 'Selecione a unidade de destino...',
                            allowClear: false,
                            minimumResultsForSearch: Infinity,
                            dropdownParent: dropdownParent
                        });
                        
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
                    // Inicializa Select2 se ainda não foi inicializado
                    if (!selectStatus.data('select2')) {
                        const dropdownParent = $(document.body);
                        selectStatus.select2({
                            width: '100%',
                            language: 'pt-BR',
                            placeholder: 'Selecione o status...',
                            allowClear: false,
                            minimumResultsForSearch: Infinity,
                            dropdownParent: dropdownParent
                        });
                        
                        // Garante que nenhum valor está selecionado após inicializar
                        selectStatus.val(null).trigger('change');
                    }
                }
                
                // Configura listeners para mudanças na unidade de origem (caso mude)
                // Nota: A unidade de origem é readonly, mas mantemos o listener caso isso mude no futuro
                const unidOrigem = $('#field_lst_cod_unid_tram_local').val() || 
                                  document.getElementById('field_lst_cod_unid_tram_local')?.value ||
                                  document.querySelector('input[name="lst_cod_unid_tram_local"]')?.value;
                
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
                // Limpa os campos sem adicionar opção vazia - o Select2 usa o placeholder
                $('#field_lst_cod_unid_tram_dest').empty();
                $('#field_lst_cod_status').empty();
                // Destrói e recria Select2 para limpar seleção
                this._destruirSelect2('#field_lst_cod_unid_tram_dest');
                this._destruirSelect2('#field_lst_cod_status');
                this._inicializarSelect2('#field_lst_cod_unid_tram_dest', 'Selecione a unidade de destino...');
                this._inicializarSelect2('#field_lst_cod_status', 'Selecione o status...');
                return;
            }
            
            // Carrega unidades de destino
            $.ajax({
                url: `${PORTAL_URL}/tramitacao_unidades_json`,
                method: 'POST',
                data: { svalue: unidOrigem, tipo: tipo },
                success: (response) => {
                    const unidades = typeof response === 'string' ? JSON.parse(response) : response;
                    // Usa o ID correto com prefixo field_
                    const selectDestId = '#field_lst_cod_unid_tram_dest';
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
                    // Atualiza Select2 após adicionar options
                    const selectDest = $(selectDestId);
                    if (selectDest.length) {
                        // Destrói Select2 se já existir
                        if (selectDest.data('select2')) {
                            try {
                                selectDest.select2('destroy');
                            } catch (e) {
                                console.warn('Erro ao destruir Select2 de unidades de destino:', e);
                            }
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
                            
                            // Inicializa/recria Select2 com os novos options
                            selectDest.select2({
                                width: '100%',
                                language: 'pt-BR',
                                placeholder: 'Selecione a unidade de destino...',
                                allowClear: false,
                                // Desabilita busca (Infinity = nunca mostrar)
                                minimumResultsForSearch: Infinity,
                                // Anexa o dropdown ao sidebar para funcionar corretamente dentro do offcanvas
                                dropdownParent: dropdownParent
                            });
                            
                            // Adiciona listener para validação em tempo real (com namespace para evitar conflitos)
                            // Usa arrow function para manter o contexto correto
                            selectDest.off('change.select2-validation').on('change.select2-validation', () => {
                                const valor = selectDest.val();
                                if (valor && valor !== '') {
                                    self._marcarCampoValido('#field_lst_cod_unid_tram_dest');
                                }
                            });
                            // Garante que nenhum valor está selecionado após inicializar
                            selectDest.val(null).trigger('change');
                        }, 100);
                    } else {
                        console.error('TramitacaoSidebarManager - Select #field_lst_cod_unid_tram_dest não encontrado no DOM');
                    }
                },
                error: (xhr, status, error) => {
                    console.error('TramitacaoSidebarManager - Erro ao carregar unidades de destino:', status, error, xhr.responseText);
                    $('#field_lst_cod_unid_tram_dest').empty();
                    // Não adiciona opção vazia - o Select2 mostrará o placeholder
                    this._destruirSelect2('#field_lst_cod_unid_tram_dest');
                    this._inicializarSelect2('#field_lst_cod_unid_tram_dest', 'Erro ao carregar unidades de destino');
                }
            });
            
            // Carrega status
            $.ajax({
                url: `${PORTAL_URL}/tramitacao_status_json`,
                method: 'POST',
                data: { svalue: unidOrigem, tipo: tipo },
                success: (response) => {
                    const status = typeof response === 'string' ? JSON.parse(response) : response;
                    // Usa o ID correto com prefixo field_
                    const selectStatusId = '#field_lst_cod_status';
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
                    // Atualiza Select2 após adicionar options
                    const selectStatus = $(selectStatusId);
                    if (selectStatus.length) {
                        // Destrói Select2 se já existir
                        if (selectStatus.data('select2')) {
                            try {
                                selectStatus.select2('destroy');
                            } catch (e) {
                                console.warn('Erro ao destruir Select2 de status:', e);
                            }
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
                            
                            // Inicializa/recria Select2 com os novos options
                            selectStatus.select2({
                                width: '100%',
                                language: 'pt-BR',
                                placeholder: 'Selecione o status...',
                                allowClear: false,
                                // Desabilita busca (Infinity = nunca mostrar)
                                minimumResultsForSearch: Infinity,
                                // Anexa o dropdown ao sidebar para funcionar corretamente dentro do offcanvas
                                dropdownParent: dropdownParent
                            });
                            
                            // Adiciona listener para validação em tempo real (com namespace para evitar conflitos)
                            // Usa arrow function para manter o contexto correto
                            selectStatus.off('change.select2-validation').on('change.select2-validation', () => {
                                const valor = selectStatus.val();
                                if (valor && valor !== '') {
                                    self._marcarCampoValido('#field_lst_cod_status');
                                }
                            });
                            // Garante que nenhum valor está selecionado após inicializar
                            selectStatus.val(null).trigger('change');
                        }, 100);
                    } else {
                        console.error('TramitacaoSidebarManager - Select #field_lst_cod_status não encontrado no DOM');
                    }
                },
                error: (xhr, status, error) => {
                    console.error('TramitacaoSidebarManager - Erro ao carregar status:', status, error, xhr.responseText);
                    $('#field_lst_cod_status').empty();
                    // Não adiciona opção vazia - o Select2 mostrará o placeholder
                    this._destruirSelect2('#field_lst_cod_status');
                    this._inicializarSelect2('#field_lst_cod_status', 'Erro ao carregar status');
                }
            });
        };
        
        // Como a unidade de origem agora é readonly (sempre a da caixa de entrada),
        // não precisa de listener de change. Carrega automaticamente quando o formulário é inicializado
        // Verifica se há unidade de origem já definida e carrega destino/status automaticamente
        const tentarCarregarUnidadesEStatus = () => {
            // Primeiro verifica se os selects existem no DOM (com prefixo field_)
            const selectDest = $('#field_lst_cod_unid_tram_dest');
            const selectStatus = $('#field_lst_cod_status');
            
            if (selectDest.length === 0 || selectStatus.length === 0) {
                return false;
            }
            
            // Tenta obter do campo hidden (novo renderizador usa field_ prefix)
            let unidOrigemInput = document.getElementById('field_lst_cod_unid_tram_local');
            // Se não encontrou, tenta sem prefixo (método antigo)
            if (!unidOrigemInput || !unidOrigemInput.value) {
                unidOrigemInput = document.getElementById('lst_cod_unid_tram_local');
            }
            // Se ainda não encontrou, tenta buscar por name (mais confiável)
            // Tenta primeiro no formulário individual, depois no lote
            if (!unidOrigemInput || !unidOrigemInput.value) {
                let form = document.getElementById('tramitacao_individual_form');
                if (!form) {
                    form = document.getElementById('tramitacao_lote_form');
                }
                if (form) {
                    unidOrigemInput = form.querySelector('input[name="lst_cod_unid_tram_local"]');
                }
            }
            
            if (unidOrigemInput && unidOrigemInput.value) {
                // Carrega unidades de destino e status automaticamente
                carregarDestinoEStatus(unidOrigemInput.value);
                return true;
            }
            return false;
        };
        
        // A função tentarCarregarUnidadesEStatus agora é chamada apenas quando as opções não estão presentes
        // (chamada dentro do callback de tentarVerificarOpcoes acima)
        
        $(document).off('change', '#field_lst_cod_unid_tram_dest').on('change', '#field_lst_cod_unid_tram_dest', () => {
            const unidDest = $('#field_lst_cod_unid_tram_dest').val();
            if (!unidDest) return;
            
            $.ajax({
                url: `${PORTAL_URL}/tramitacao_usuarios_json`,
                method: 'POST',
                data: { svalue: unidDest },
                success: (response) => {
                    const usuarios = typeof response === 'string' ? JSON.parse(response) : response;
                    const $selectUsuario = $('#field_lst_cod_usuario_dest');
                    $selectUsuario.empty();
                    // Adiciona opção vazia "Selecione" no início
                    $selectUsuario.append($('<option>').val('').text('Selecione'));
                    usuarios.forEach(usr => {
                        $selectUsuario.append(
                            $('<option>').val(usr.id).text(usr.name)
                        );
                    });
                    // Atualiza Select2 se já foi inicializado
                    if ($selectUsuario.data('select2')) {
                        $selectUsuario.trigger('change.select2');
                    } else {
                        $selectUsuario.trigger('change');
                    }
                }
            });
        });
    }
    
    /**
     * Inicializa Trumbowyg para o editor de texto do despacho
     * Suporta tramitação individual e em lote
     * IMPORTANTE: Formulário sempre está no sidebar
     */
    inicializarTrumbowyg(textareaId = null, tentativas = 0) {
        const MAX_TENTATIVAS = 10;
        
        if (typeof jQuery === 'undefined' || typeof jQuery.fn.trumbowyg === 'undefined') {
            if (tentativas < MAX_TENTATIVAS) {
                setTimeout(() => {
                    this.inicializarTrumbowyg(textareaId, tentativas + 1);
                }, 200);
            }
            return;
        }
        
        // Detecta qual textarea inicializar
        // IMPORTANTE: Se não houver ID específico, verifica apenas os textareas dentro de offcanvas ABERTO
        let idsParaTestar = [];
        
        if (textareaId) {
            // Se há ID específico, usa apenas ele
            idsParaTestar = [textareaId];
        } else {
            // Detecção automática: verifica qual offcanvas está aberto e busca o textarea correspondente
            const offcanvasIndividual = document.getElementById('tramitacaoIndividualOffcanvas');
            const offcanvasLote = document.getElementById('tramitacaoLoteOffcanvas');
            
            const individualAberto = offcanvasIndividual && offcanvasIndividual.classList.contains('show');
            const loteAberto = offcanvasLote && offcanvasLote.classList.contains('show');
            
            if (individualAberto) {
                // Se o offcanvas individual está aberto, busca apenas textarea individual
                idsParaTestar = ['field_txa_txt_tramitacao', 'txa_txt_tramitacao'];
            } else if (loteAberto) {
                // Se o offcanvas lote está aberto, busca apenas textarea lote
                idsParaTestar = ['field_txa_txt_tramitacao_lote', 'txa_txt_tramitacao_lote'];
            } else {
                // Se nenhum está aberto, tenta todos (fallback)
                idsParaTestar = ['field_txa_txt_tramitacao', 'txa_txt_tramitacao', 
                               'field_txa_txt_tramitacao_lote', 'txa_txt_tramitacao_lote'];
            }
        }
        
        let textarea = null;
        let idFinal = null;
        
        for (const id of idsParaTestar) {
            const elemento = document.getElementById(id);
            if (elemento) {
                // Se um ID específico foi passado, confia nele e não verifica offcanvas
                // A verificação do offcanvas só é necessária na detecção automática
                if (textareaId) {
                    // ID específico passado - usa diretamente
                    textarea = elemento;
                    idFinal = id;
                    break;
                } else {
                    // Detecção automática - verifica se o elemento está dentro de um offcanvas aberto
                    // Isso evita usar um textarea de um offcanvas fechado
                    const offcanvasPai = elemento.closest('.offcanvas');
                    const offcanvasTemShow = offcanvasPai && offcanvasPai.classList.contains('show');
                    const elementoVisivel = elemento.offsetParent !== null;
                    
                    // Aceita o elemento se:
                    // 1. Não está dentro de um offcanvas (não deveria acontecer, mas aceita por segurança)
                    // 2. Está dentro de um offcanvas que tem a classe 'show' (aberto)
                    // 3. Está dentro de um offcanvas que está visível (offsetParent !== null)
                    if (!offcanvasPai || offcanvasTemShow || elementoVisivel) {
                        textarea = elemento;
                        idFinal = id;
                        break;
                    }
                }
            }
        }
        
        if (!textarea) {
            if (tentativas < MAX_TENTATIVAS) {
                setTimeout(() => {
                    this.inicializarTrumbowyg(textareaId, tentativas + 1);
                }, 200);
            } else {
                console.error(`Elemento textarea não encontrado após ${MAX_TENTATIVAS} tentativas`);
            }
            return;
        }
        
        // IMPORTANTE: Remove instância existente de Trumbowyg no elemento específico ANTES de criar nova
        // Isso evita conflitos quando o formulário é reaberto
        const $editor = jQuery('#' + idFinal);
        if ($editor.length > 0) {
            // Destrói instância existente se houver
            if ($editor.data('trumbowyg')) {
                try {
                    $editor.trumbowyg('destroy');
                    // Aguarda um pequeno delay após destruir para garantir que foi processado
                    setTimeout(() => {
                        this._criarInstanciaTrumbowyg(idFinal);
                    }, 150);
                } catch (e) {
                    // Em caso de erro, tenta criar a instância mesmo assim
                    this._criarInstanciaTrumbowyg(idFinal);
                }
            } else {
                // Não há instância existente, cria nova diretamente
                this._criarInstanciaTrumbowyg(idFinal);
            }
        } else {
            // Se o elemento não existe ainda, tenta novamente
            if (tentativas < MAX_TENTATIVAS) {
                setTimeout(() => {
                    this.inicializarTrumbowyg(textareaId, tentativas + 1);
                }, 200);
            }
        }
    }
    
    /**
     * Cria a instância do Trumbowyg no elemento especificado
     * Método auxiliar para separar a criação da instância da lógica de detecção
     */
    _criarInstanciaTrumbowyg(idFinal) {
        const $editor = jQuery('#' + idFinal);
        if ($editor.length === 0) {
            return;
        }
        
        // Verifica se já existe uma instância (não deveria, mas verifica por segurança)
        if ($editor.data('trumbowyg')) {
            return;
        }
        
        // Inicializa Trumbowyg com configurações otimizadas para offcanvas
        $editor.trumbowyg({
            lang: 'pt_br',
            btns: [
                ['undo', 'redo'],
                ['formatting'],
                ['strong', 'em', 'underline'],
                ['link'],
                ['unorderedList', 'orderedList'],
                ['alignLeft', 'alignCenter', 'alignRight'],
                ['viewHTML']
            ],
            semantic: true,
            removeformatPasted: true,
            autogrow: false, // Desabilitado para melhor compatibilidade
            resetCss: true, // Reset CSS para evitar conflitos
            minimalLinks: true // Modal de link mais simples
        });
        
        // Configura eventos para lidar com modais do Trumbowyg dentro do offcanvas
        $editor.on('tbwopenfullscreen', function() {
            // Quando abre fullscreen, remove bloqueio do offcanvas
            const offcanvas = document.querySelector('.offcanvas.show');
            if (offcanvas && offcanvas.hasAttribute('data-bs-focus')) {
                offcanvas._originalFocus = offcanvas.getAttribute('data-bs-focus');
                offcanvas.removeAttribute('data-bs-focus');
            }
        }).on('tbwclosefullscreen', function() {
            // Restaura bloqueio quando fecha fullscreen
            const offcanvas = document.querySelector('.offcanvas.show');
            if (offcanvas && offcanvas._originalFocus !== undefined) {
                offcanvas.setAttribute('data-bs-focus', offcanvas._originalFocus);
                delete offcanvas._originalFocus;
            }
        });
        
        // Intercepta quando o modal de link é aberto
        // Usa MutationObserver + verificação periódica para garantir detecção
        let offcanvasFocusBackup = null;
        let focusTrapDesativado = false; // Flag para evitar desativar múltiplas vezes
        let checkInterval = null;
        
        function habilitarModalTrumbowyg() {
            const modal = document.querySelector('.trumbowyg-modal-box');
            if (modal && modal.offsetParent !== null) {
                // Remove data-bs-focus do offcanvas para permitir interação (apenas uma vez)
                const offcanvas = document.querySelector('.offcanvas.show');
                if (offcanvas && offcanvas.hasAttribute('data-bs-focus')) {
                    if (offcanvasFocusBackup === null) {
                        offcanvasFocusBackup = offcanvas.getAttribute('data-bs-focus');
                    }
                    offcanvas.removeAttribute('data-bs-focus');
                }
                
                // Remove focus trap do Bootstrap se houver (apenas uma vez)
                if (!focusTrapDesativado) {
                    try {
                        const offcanvasInstance = bootstrap?.Offcanvas?.getInstance(offcanvas);
                        if (offcanvasInstance && offcanvasInstance._focustrap) {
                            offcanvasInstance._focustrap.deactivate();
                            focusTrapDesativado = true;
                        }
                    } catch (e) {
                        // Ignora erro
                    }
                }
                
                // Remove backdrop que possa estar bloqueando
                const backdrop = document.querySelector('.offcanvas-backdrop');
                if (backdrop) {
                    backdrop.style.pointerEvents = 'none';
                    backdrop.style.zIndex = '1040'; // Abaixo do modal
                }
                
                // Ajusta z-index e pointer-events (correspondente ao CSS)
                modal.style.zIndex = '99999';
                modal.style.pointerEvents = 'auto';
                modal.style.position = 'fixed'; // Garante posicionamento fixo
                modal.style.transform = 'none'; // Remove transformações conflitantes
                
                // Garante que inputs dentro do modal podem receber eventos
                const inputs = modal.querySelectorAll('input, textarea');
                inputs.forEach(function(input) {
                    // Apenas processa se ainda não foi processado
                    if (input.dataset.trumbowygProcessed) {
                        return;
                    }
                    input.dataset.trumbowygProcessed = 'true';
                    
                    input.style.pointerEvents = 'auto';
                    input.style.cursor = 'text';
                    input.style.userSelect = 'text';
                    input.style.webkitUserSelect = 'text';
                    input.disabled = false;
                    input.readOnly = false;
                    input.removeAttribute('disabled');
                    input.removeAttribute('readonly');
                    input.tabIndex = 0;
                    
                    // Adiciona listeners que garantem que eventos cheguem ao input
                    input.addEventListener('mousedown', function(e) {
                        e.stopPropagation();
                        e.stopImmediatePropagation();
                        this.focus();
                    }, true);
                    
                    input.addEventListener('click', function(e) {
                        e.stopPropagation();
                        e.stopImmediatePropagation();
                        this.focus();
                    }, true);
                    
                    input.addEventListener('focus', function(e) {
                        e.stopPropagation();
                    }, true);
                });
                
                // Força focus no primeiro input após um pequeno delay
                setTimeout(function() {
                    const firstInput = modal.querySelector('input[type="text"], input[type="url"], textarea');
                    if (firstInput && document.activeElement !== firstInput) {
                        try {
                            firstInput.focus();
                            firstInput.click();
                        } catch (e) {
                            // Ignora erro
                        }
                    }
                }, 100);
                
                return true;
            }
            return false;
        }
        
        function restaurarOffcanvas() {
            // Restaura data-bs-focus e focus trap quando modal fecha
            if (offcanvasFocusBackup !== null) {
                const offcanvas = document.querySelector('.offcanvas.show');
                if (offcanvas) {
                    offcanvas.setAttribute('data-bs-focus', offcanvasFocusBackup);
                }
                offcanvasFocusBackup = null;
            }
            
            if (focusTrapDesativado) {
                try {
                    const offcanvas = document.querySelector('.offcanvas.show');
                    const offcanvasInstance = bootstrap?.Offcanvas?.getInstance(offcanvas);
                    if (offcanvasInstance && offcanvasInstance._focustrap) {
                        offcanvasInstance._focustrap.activate();
                    }
                } catch (e) {
                    // Ignora erro
                }
                focusTrapDesativado = false;
            }
        }
        
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) {
                        // Verifica se é o modal do Trumbowyg
                        const modal = node.classList?.contains('trumbowyg-modal-box') 
                            ? node 
                            : (node.querySelector?.('.trumbowyg-modal-box') || 
                               (node.parentElement?.querySelector?.('.trumbowyg-modal-box')));
                        
                        if (modal) {
                            // Aguarda um pouco para garantir que modal está totalmente renderizado
                            setTimeout(function() {
                                if (habilitarModalTrumbowyg()) {
                                    // Inicia verificação periódica enquanto modal estiver aberto
                                    if (!checkInterval) {
                                        checkInterval = setInterval(function() {
                                            const modalAindaAberto = document.querySelector('.trumbowyg-modal-box');
                                            if (!modalAindaAberto || modalAindaAberto.offsetParent === null) {
                                                // Modal fechou, restaura e limpa intervalo
                                                restaurarOffcanvas();
                                                clearInterval(checkInterval);
                                                checkInterval = null;
                                            }
                                        }, 500); // Verifica a cada 500ms (menos frequente)
                                    }
                                }
                            }, 100);
                        }
                    }
                });
                
                // Verifica se modais foram removidos (fechados)
                mutation.removedNodes.forEach(function(node) {
                    if (node.nodeType === 1) {
                        const modal = node.classList?.contains('trumbowyg-modal-box') 
                            ? node 
                            : null;
                        
                        if (modal) {
                            // Modal foi removido, restaura configurações
                            restaurarOffcanvas();
                            if (checkInterval) {
                                clearInterval(checkInterval);
                                checkInterval = null;
                            }
                        }
                    }
                });
            });
        });
        
        // Observa mudanças no body para detectar modais do Trumbowyg
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        // Verificação inicial após um delay (caso modal já esteja aberto)
        setTimeout(function() {
            habilitarModalTrumbowyg();
        }, 500);
    }
    
    /**
     * Obtém conteúdo do editor Trumbowyg
     */
    obterConteudoEditor(textareaId = null) {
        const idsParaTestar = textareaId 
            ? [textareaId]
            : ['field_txa_txt_tramitacao', 'txa_txt_tramitacao', 
               'field_txa_txt_tramitacao_lote', 'txa_txt_tramitacao_lote'];
        
        for (const id of idsParaTestar) {
            const $editor = jQuery('#' + id);
            if ($editor.length && $editor.data('trumbowyg')) {
                return $editor.trumbowyg('html') || '';
            }
        }
        
        // Fallback: retorna valor do textarea diretamente
        for (const id of idsParaTestar) {
            const textarea = document.getElementById(id);
            if (textarea) {
                return textarea.value || '';
            }
        }
        
        return '';
    }
    
    /**
     * Define conteúdo do editor Trumbowyg
     */
    definirConteudoEditor(conteudo, textareaId = null) {
        const idsParaTestar = textareaId 
            ? [textareaId]
            : ['field_txa_txt_tramitacao', 'txa_txt_tramitacao', 
               'field_txa_txt_tramitacao_lote', 'txa_txt_tramitacao_lote'];
        
        for (const id of idsParaTestar) {
            const $editor = jQuery('#' + id);
            if ($editor.length && $editor.data('trumbowyg')) {
                $editor.trumbowyg('html', conteudo || '');
                return;
            }
        }
        
        // Fallback: define valor do textarea diretamente
        for (const id of idsParaTestar) {
            const textarea = document.getElementById(id);
            if (textarea) {
                textarea.value = conteudo || '';
                return;
            }
        }
    }
    
    /**
     * Inicializa TinyMCE para o editor de texto do despacho
     * IMPORTANTE: Formulário sempre está no sidebar
     * @deprecated Use inicializarTrumbowyg() ao invés desta função
     */
    inicializarTinyMCE(tentativas = 0) {
        const MAX_TENTATIVAS = 10; // Limita a 10 tentativas (2 segundos no total)
        
        if (typeof tinymce === 'undefined') {
            console.warn('TinyMCE não está disponível');
            return;
        }
        
        // O ID do campo é gerado como field_{name}, então é field_txa_txt_tramitacao
        const textareaId = 'field_txa_txt_tramitacao';
        const textarea = document.getElementById(textareaId);
        
        if (!textarea) {
            if (tentativas < MAX_TENTATIVAS) {
                // Tenta novamente após um pequeno delay
                setTimeout(() => {
                    this.inicializarTinyMCE(tentativas + 1);
                }, 200);
            } else {
                console.error(`Elemento #${textareaId} não encontrado após ${MAX_TENTATIVAS} tentativas. Verifique se o campo está sendo renderizado corretamente.`);
            }
            return;
        }
        
        // Remove editor existente se houver
        const existingEditor = tinymce.get(textareaId);
        if (existingEditor) {
            tinymce.remove('#' + textareaId);
        }
        
        // Inicializa TinyMCE com toolbar compacta
        tinymce.init({
            selector: '#' + textareaId,
            language: 'pt_BR',
            browser_spellcheck: true,
            contextmenu: false,
            height: 200,
            paste_as_text: true,
            plugins: [
                'advlist autolink link lists hr',
                'searchreplace wordcount code',
                'table paste'
            ],
            toolbar: 'undo redo | bold italic underline | alignleft aligncenter alignright | bullist numlist | link | code',
            menubar: false, // Remove a barra de menu para deixar mais compacto
            toolbar_mode: 'sliding', // Toolbar compacta que expande quando necessário
            content_style: 'body {font-size:14px }',
            // Garante que funciona dentro do sidebar/offcanvas
            inline: false,
            fixed_toolbar_container: null,
            // IMPORTANTE: Configura TinyMCE para anexar modais ao body ao invés do container pai
            // Isso resolve problemas com offcanvas do Bootstrap que bloqueia interação
            body_class: 'tox-dialog-open',
            // Força modais a serem anexados ao body (fora do offcanvas)
            dialog_type: 'modal',
            // Remove qualquer restrição de container
            target: null,
            // Configuração para garantir que modais (como link dialog) funcionem dentro do offcanvas
            setup: function(editor) {
                // Armazena referência ao offcanvas para restaurar depois
                let offcanvasElement = null;
                let originalFocusValue = null;
                let observer = null;
                
                // Intercepta quando um diálogo do TinyMCE está para abrir
                editor.on('OpenDialog', function(e) {
                    // Armazena referência ao offcanvas para remover data-bs-focus depois
                    offcanvasElement = document.querySelector('.offcanvas.show');
                    if (offcanvasElement && offcanvasElement.hasAttribute('data-bs-focus')) {
                        originalFocusValue = offcanvasElement.getAttribute('data-bs-focus');
                    }
                    
                    // Aguarda o modal ser criado e renderizado ANTES de fazer qualquer modificação
                    setTimeout(function() {
                        const modal = document.querySelector('.tox-dialog');
                        if (modal && modal.offsetParent !== null) {
                            // Modal está visível, agora pode remover data-bs-focus
                            // Isso permite que os inputs dentro do modal recebam eventos normalmente
                            if (offcanvasElement && offcanvasElement.hasAttribute('data-bs-focus')) {
                                offcanvasElement.removeAttribute('data-bs-focus');
                                console.log('[TinyMCE] Removido data-bs-focus do offcanvas para permitir interação com modal');
                            }
                            // Habilita inputs (remove disabled/readonly e ajusta estilos)
                            habilitarInputsTinyMCE();
                        } else {
                            // Modal ainda não está visível, tenta novamente
                            setTimeout(function() {
                                habilitarInputsTinyMCE();
                            }, 100);
                        }
                    }, 250); // Aguarda 250ms para garantir que TinyMCE criou o modal completamente
                });
                
                // Quando o diálogo é fechado, restaura data-bs-focus
                editor.on('CloseDialog', function(e) {
                    if (offcanvasElement && originalFocusValue !== null) {
                        offcanvasElement.setAttribute('data-bs-focus', originalFocusValue);
                        offcanvasElement = null;
                        originalFocusValue = null;
                    }
                });
                
                // Função para habilitar inputs do modal TinyMCE
                function habilitarInputsTinyMCE() {
                    const modal = document.querySelector('.tox-dialog');
                    if (!modal) {
                        // Tenta novamente após delay se modal ainda não estiver pronto
                        setTimeout(habilitarInputsTinyMCE, 100);
                        return;
                    }
                    
                    // IMPORTANTE: NÃO move o modal - apenas ajusta z-index e remove data-bs-focus
                    // Mover o modal pode fazer o TinyMCE detectar a mudança e fechá-lo
                    const offcanvas = document.querySelector('.offcanvas.show');
                    
                    // Remove data-bs-focus do offcanvas se ainda estiver (isso permite interação)
                    if (offcanvas && offcanvas.hasAttribute('data-bs-focus')) {
                        offcanvas.removeAttribute('data-bs-focus');
                    }
                    
                    // Ajusta z-index para garantir que o modal fique acima do offcanvas
                    // Mas NÃO move o modal do lugar onde o TinyMCE o colocou
                    modal.style.zIndex = '10050';
                    
                    // Garante que o modal e seus elementos podem receber eventos
                    modal.style.pointerEvents = 'auto';
                    
                    // Remove qualquer overlay que possa estar bloqueando
                    const backdrop = modal.querySelector('.tox-dialog__backdrop');
                    if (backdrop) {
                        backdrop.style.pointerEvents = 'none';
                    }
                    
                    // Encontra todos os inputs e textareas no modal
                    const inputs = modal.querySelectorAll('input:not([type="hidden"]):not([type="button"]):not([type="submit"]), textarea, select');
                    
                    inputs.forEach(function(input) {
                        // Remove disabled e readonly
                        input.disabled = false;
                        input.readOnly = false;
                        input.removeAttribute('disabled');
                        input.removeAttribute('readonly');
                        
                        // Remove estilos que podem bloquear interação
                        input.style.pointerEvents = 'auto';
                        input.style.opacity = '1';
                        input.style.cursor = 'text';
                        input.style.userSelect = 'text';
                        input.style.webkitUserSelect = 'text';
                        
                        // Garante tabIndex
                        input.tabIndex = 0;
                        
                        // Remove qualquer overlay ou elemento bloqueando
                        const inputParent = input.parentElement;
                        if (inputParent) {
                            inputParent.style.pointerEvents = 'auto';
                            // Remove qualquer elemento que possa estar sobrepondo
                            const siblings = Array.from(inputParent.children);
                            siblings.forEach(function(sibling) {
                                if (sibling !== input && sibling.style.position === 'absolute' && sibling.style.zIndex > input.style.zIndex) {
                                    sibling.style.pointerEvents = 'none';
                                }
                            });
                        }
                        
                        // NÃO adiciona interceptadores de eventos - apenas garante que os inputs estão habilitados
                        // Deixar o navegador lidar normalmente com os eventos deve funcionar
                        // Apenas garante que disabled/readonly foram removidos e estilos estão corretos
                    });
                    
                    // Garante que TODO o modal pode receber eventos
                    modal.style.pointerEvents = 'auto';
                    const todosElementos = modal.querySelectorAll('*');
                    todosElementos.forEach(function(el) {
                        el.style.pointerEvents = 'auto';
                    });
                    
                    // Remove qualquer backdrop ou overlay que possa estar bloqueando
                    const backdrops = document.querySelectorAll('.tox-dialog__backdrop, .tox-dialog__overlay, .offcanvas-backdrop');
                    backdrops.forEach(function(backdrop) {
                        backdrop.style.pointerEvents = 'none';
                        backdrop.style.display = 'none';
                    });
                    
                    // Tenta focar no primeiro input
                    setTimeout(function() {
                        const firstInput = modal.querySelector('input[type="text"], input[type="url"], input[type="email"]');
                        if (firstInput) {
                            try {
                                firstInput.focus();
                                firstInput.click();
                            } catch (e) {
                                console.warn('Erro ao focar primeiro input:', e);
                            }
                        }
                    }, 150);
                }
                
                // Usa MutationObserver APENAS como backup para detectar quando modal é adicionado
                // O evento OpenDialog já deve ter movido o modal, mas o observer garante que não perde
                observer = new MutationObserver(function(mutations) {
                    mutations.forEach(function(mutation) {
                        mutation.addedNodes.forEach(function(node) {
                            if (node.nodeType === 1) {
                                const modal = node.classList?.contains('tox-dialog') 
                                    ? node 
                                    : node.querySelector?.('.tox-dialog');
                                // Verifica se é realmente um modal do TinyMCE
                                if (modal && modal.classList && modal.classList.contains('tox-dialog')) {
                                    // Aguarda mais tempo para garantir que TinyMCE terminou de criar o modal
                                    setTimeout(function() {
                                        // Verifica se o modal ainda existe e está no DOM
                                        if (!modal || !modal.parentElement) {
                                            return; // Modal foi removido
                                        }
                                        
                                        // IMPORTANTE: NÃO move o modal - apenas remove data-bs-focus e ajusta z-index
                                        // Mover o modal pode fazer o TinyMCE detectar a mudança e fechá-lo
                                        const offcanvas = document.querySelector('.offcanvas.show');
                                        
                                        // Remove data-bs-focus do offcanvas (isso permite interação)
                                        if (offcanvas && offcanvas.hasAttribute('data-bs-focus')) {
                                            offcanvas.removeAttribute('data-bs-focus');
                                        }
                                        
                                        // Ajusta z-index para garantir que o modal fique acima do offcanvas
                                        // Mas NÃO move o modal do lugar onde o TinyMCE o colocou
                                        modal.style.zIndex = '10050';
                                        modal.style.pointerEvents = 'auto';
                                        
                                        // Remove backdrop que pode estar bloqueando
                                        const backdrop = modal.querySelector('.tox-dialog__backdrop');
                                        if (backdrop) {
                                            backdrop.style.pointerEvents = 'none';
                                        }
                                        
                                        // Habilita inputs (só se modal estiver visível)
                                        if (modal.offsetParent !== null) {
                                            setTimeout(habilitarInputsTinyMCE, 50);
                                        }
                                    }, 200); // Aguarda 200ms antes de mover (mais tempo para TinyMCE terminar)
                                }
                            }
                        });
                    });
                });
                
                // Observa mudanças no body
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
                
                // Limpa quando editor é removido
                editor.on('remove', function() {
                    if (observer) {
                        observer.disconnect();
                    }
                    // Restaura data-bs-focus se ainda estiver alterado
                    if (offcanvasElement && originalFocusValue !== null) {
                        offcanvasElement.setAttribute('data-bs-focus', originalFocusValue);
                    }
                });
            }
        });
        
        console.log(`TinyMCE inicializado para #${textareaId}`);
    }
    
    /**
     * Inicializa formulário em lote
     * IMPORTANTE: Formulário sempre está no sidebar
     */
    inicializarFormularioLote() {
        // Aguarda um pouco para garantir que o DOM foi atualizado
        setTimeout(() => {
            // Select2 para campos do formulário em lote
            if (typeof $().select2 !== 'undefined') {
                // Remove Select2 existente se houver (para evitar duplicação)
                this._destruirSelect2('#field_lst_cod_unid_tram_dest, #field_lst_cod_usuario_dest, #field_lst_cod_status');
                
                // NÃO inicializa Select2 aqui - será inicializado após carregar os dados via AJAX
                // Apenas inicializa o select de usuário de destino (que não depende de dados externos)
                // Anexa o dropdown ao body para evitar problemas com offcanvas do Bootstrap
                const dropdownParentUsuario = $(document.body);
                
                const $selectUsuario = $('#field_lst_cod_usuario_dest');
                
                // Adiciona opção vazia "Selecione" se não existir
                if ($selectUsuario.find('option[value=""]').length === 0) {
                    $selectUsuario.prepend($('<option>').val('').text('Selecione'));
                }
                
                // Remove mensagem de validação HTML5 padrão
                $selectUsuario.on('invalid', function(e) {
                    e.preventDefault();
                    this.setCustomValidity('');
                    return false;
                });
                
                // Limpa mensagem customizada quando o campo é alterado
                $selectUsuario.on('input change', function() {
                    this.setCustomValidity('');
                });
                
                $selectUsuario.select2({
                    width: '100%',
                    language: 'pt-BR',
                    placeholder: 'Selecione o usuário de destino...',
                    allowClear: false,
                    // Desabilita busca (Infinity = nunca mostrar)
                    minimumResultsForSearch: Infinity,
                    // Anexa o dropdown ao sidebar para funcionar corretamente dentro do offcanvas
                    dropdownParent: dropdownParentUsuario
                });
                
                // Garante que nenhum valor está selecionado após inicializar
                $selectUsuario.val(null).trigger('change');
                
                // Os selects de unidade de destino e status serão inicializados após carregar os dados
                // em configurarCarregamentoDinamico()
            }
            
            // Trumbowyg para formulário em lote
            // IMPORTANTE: Aguarda um pouco mais para garantir que o elemento está no DOM após innerHTML
            // Salva referência do this para usar dentro do setTimeout
            const self = this;
            setTimeout(() => {
                // Tenta encontrar o textarea do formulário em lote
                let textareaEl = document.getElementById('field_txa_txt_tramitacao_lote');
                let textareaId = null;
                
                // Se não encontrou com prefixo field_, tenta sem prefixo
                if (!textareaEl) {
                    textareaEl = document.getElementById('txa_txt_tramitacao_lote');
                    if (textareaEl) {
                        textareaId = 'txa_txt_tramitacao_lote';
                    }
                } else {
                    textareaId = 'field_txa_txt_tramitacao_lote';
                }
                
                // IMPORTANTE: NÃO tenta usar textarea do formulário individual como fallback
                // Isso causaria conflito entre os dois formulários
                
                if (textareaEl && textareaId) {
                    if (typeof jQuery !== 'undefined' && typeof jQuery.fn.trumbowyg !== 'undefined') {
                        self.inicializarTrumbowyg(textareaId);
                    }
                } else {
                    // Tenta novamente após um delay adicional, sem especificar ID (deixa o método detectar automaticamente)
                    setTimeout(() => {
                        // Passa null para deixar o método detectar automaticamente qual textarea inicializar
                        self.inicializarTrumbowyg(null);
                    }, 300);
                }
            }, 500); // Delay para garantir que DOM está pronto
            
            // Bootstrap Datepicker para data de fim de prazo - inicialização robusta
            setTimeout(() => {
                // Tenta múltiplos seletores
                const seletores = [
                    '#field_txt_dat_fim_prazo',
                    '#txt_dat_fim_prazo',
                    'input[name="txt_dat_fim_prazo"]',
                    'input.datepicker'
                ];
                
                let campoData = null;
                
                for (const seletor of seletores) {
                    campoData = document.querySelector(seletor);
                    if (campoData) break;
                }
                
                if (campoData) {
                    console.log('📅 Campo de data encontrado (lote):', campoData.id || campoData.name);
                    // Usa inicialização com timeout para garantir DOM pronto
                    this._inicializarFlatpickrComTimeout(campoData);
                } else {
                    console.warn('❌ Nenhum campo de data encontrado com os seletores (lote):', seletores);
                }
            }, 500); // Aumentado para 500ms
            
            // Controla exibição do campo de arquivo PDF baseado na opção selecionada
            this._configurarCampoPdf();
            
            // Configura carregamento dinâmico de unidades e status
            const tipo = this.obterTipoDoFormularioLote();
            if (tipo) {
                this.configurarCarregamentoDinamico(tipo);
            }
            
            // Configura validação em tempo real para campos obrigatórios
            this._configurarValidacaoTempoReal();
            
            this.atualizarContadorProcessosLote();
        }, 100);
    }
    
    /**
     * Obtém tipo do processo do formulário em lote
     */
    obterTipoDoFormularioLote() {
        const form = document.getElementById('tramitacao_lote_form');
        if (!form) return null;
        
        const tipoInput = form.querySelector('input[name="hdn_tipo_tramitacao"]');
        if (tipoInput && tipoInput.value) {
            return tipoInput.value;
        }
        
        return null;
    }
    
    /**
     * Atualiza contador de processos selecionados
     */
    atualizarContadorProcessosLote() {
        if (this.app && this.app.processosSelecionados) {
            const selecionados = this.app.processosSelecionados.size;
            $('#num-processos-selecionados-lote').text(selecionados);
            if (selecionados === 0) {
                $('#contador-processos-selecionados-lote').hide();
            } else {
                $('#contador-processos-selecionados-lote').show();
            }
        }
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
    
    /**
     * Retoma tramitação enviada
     */
    retomarTramitacao(cod_tramitacao, tipo) {
        this.obterDadosTramitacao(cod_tramitacao, tipo, (dados) => {
            if (!dados.dat_encaminha) {
                this.app.mostrarToast('Erro', 'Tramitação não foi enviada', 'error');
                return;
            }
            
            if (dados.dat_visualizacao) {
                this.app.mostrarToast('Erro', `Tramitação já foi visualizada. Não é possível retomá-la.`, 'error');
                return;
            }
            
            if (dados.dat_recebimento) {
                this.app.mostrarToast('Erro', `Tramitação já foi recebida. Não é possível retomá-la.`, 'error');
                return;
            }
            
            if (!confirm('Deseja retomar esta tramitação? Ela voltará para rascunhos e poderá ser editada novamente.')) {
                return;
            }
            
            $.ajax({
                url: `${PORTAL_URL}/tramitacao_retomar_json`,
                method: 'POST',
                data: { cod_tramitacao: cod_tramitacao, tipo: tipo },
                success: (response) => {
                    const dados = typeof response === 'string' ? JSON.parse(response) : response;
                    if (dados.erro) {
                        this.app.mostrarToast('Erro', dados.erro, 'error');
                    } else {
                        this.app.mostrarToast('Sucesso', 'Tramitação retomada com sucesso!', 'success');
                        if (this.app.carregarTramitacoes) {
                            this.app.carregarTramitacoes();
                        }
                    }
                },
                error: (xhr) => {
                    const erro = xhr.responseJSON?.erro || 'Erro ao retomar tramitação';
                    this.app.mostrarToast('Erro', erro, 'error');
                }
            });
        });
    }
    
    /**
     * Ver detalhes do despacho (abre PDF em modal e registra visualização/recebimento se necessário)
     */
    verDetalhesTramitacao(cod_tramitacao, tipo) {
        if (!cod_tramitacao || !tipo) {
            this.app.mostrarToast('Erro', 'Dados incompletos para visualizar detalhes', 'error');
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
                    this.app.mostrarToast('Erro', dados.erro, 'error');
                    return;
                }
                
                // Verifica se já foi visualizada e recebida
                jaVisualizada = dados.dat_visualizacao && String(dados.dat_visualizacao).trim() !== '';
                jaRecebida = dados.dat_recebimento && String(dados.dat_recebimento).trim() !== '';
                
                // Se já foi visualizada E recebida, apenas abre o PDF sem registrar
                if (jaVisualizada && jaRecebida) {
                    this._abrirPDFDespacho(cod_tramitacao, tipo);
                } else {
                    // Se ainda não foi visualizada/recebida, registra antes de abrir
                    this._registrarVisualizacaoERecebimento(cod_tramitacao, tipo, () => {
                        this._abrirPDFDespacho(cod_tramitacao, tipo);
                    });
                }
            });
        } else {
            // Já tem os dados do processo, usa diretamente
            if (jaVisualizada && jaRecebida) {
                this._abrirPDFDespacho(cod_tramitacao, tipo);
            } else {
                // Se ainda não foi visualizada/recebida, registra antes de abrir
                this._registrarVisualizacaoERecebimento(cod_tramitacao, tipo, () => {
                    this._abrirPDFDespacho(cod_tramitacao, tipo);
                });
            }
        }
    }
    
    /**
     * Abre PDF do despacho no modal
     */
    _abrirPDFDespacho(cod_tramitacao, tipo) {
        // Obtém link do PDF e abre no modal
        $.ajax({
            url: `${PORTAL_URL}/tramitacao_obter_pdf_despacho_json`,
            method: 'GET',
            data: { cod_tramitacao: cod_tramitacao, tipo: tipo },
            success: (response) => {
                const dados = typeof response === 'string' ? JSON.parse(response) : response;
                if (dados.erro) {
                    this.app.mostrarToast('Erro', dados.erro, 'error');
                } else if (dados.link_pdf) {
                    // Abre PDF no modal iFrameModal
                    const $modal = $('#iFrameModal');
                    if ($modal.length === 0) {
                        this.app.mostrarToast('Erro', 'Modal não encontrado no DOM', 'error');
                        return;
                    }
                    
                    // Define título do modal
                    $modal.find('.modal-title').text('Despacho da Tramitação');
                    
                    // Define src do iframe
                    const $iframe = $modal.find('.modal-body iframe');
                    if ($iframe.length === 0) {
                        this.app.mostrarToast('Erro', 'Iframe não encontrado no modal', 'error');
                        return;
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
                    
                    // Mostra modal usando Bootstrap 5
                    const modalElement = $modal[0];
                    let modalInstance = bootstrap.Modal.getInstance(modalElement);
                    if (!modalInstance) {
                        modalInstance = new bootstrap.Modal(modalElement, {
                            backdrop: 'static',
                            keyboard: false
                        });
                    }
                    modalInstance.show();
                } else {
                    this.app.mostrarToast('Atenção', dados.mensagem || 'PDF do despacho não encontrado', 'warning');
                }
            },
            error: (xhr) => {
                const erro = xhr.responseJSON?.erro || 'Erro ao obter PDF do despacho';
                this.app.mostrarToast('Erro', erro, 'error');
            }
        });
    }
    
    /**
     * Registra visualização e recebimento de tramitação
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
     * Valida formulário individual completo
     */
    validarFormularioIndividual() {
        const form = document.getElementById('tramitacao_individual_form');
        if (!form) return false;
        
        form.classList.remove('was-validated');
        $('.is-invalid').removeClass('is-invalid');
        $('.invalid-feedback').remove();
        $('[aria-invalid="true"]').attr('aria-invalid', 'false');
        
        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            // Marca campos HTML5 inválidos
            form.querySelectorAll(':invalid').forEach(campo => {
                $(campo).attr('aria-invalid', 'true');
            });
            return false;
        }
        
        // Valida Select2 - Unidade de Destino
        const unidDest = $('#field_lst_cod_unid_tram_dest').val();
        if (!unidDest || unidDest === '') {
            this._marcarCampoInvalido('#field_lst_cod_unid_tram_dest', 'Unidade de destino é obrigatória');
            return false;
        } else {
            this._marcarCampoValido('#field_lst_cod_unid_tram_dest');
        }
        
        // Valida Select2 - Status
        const status = $('#field_lst_cod_status').val();
        if (!status || status === '') {
            this._marcarCampoInvalido('#field_lst_cod_status', 'Status é obrigatório');
            return false;
        } else {
            this._marcarCampoValido('#field_lst_cod_status');
        }
        
        // Valida data de fim de prazo (se preenchida, deve ser >= hoje)
        const dataFimPrazo = $('#txt_dat_fim_prazo').val();
        if (dataFimPrazo && dataFimPrazo.trim() !== '') {
            const validacaoData = this._validarDataFimPrazo(dataFimPrazo);
            if (!validacaoData.valido) {
                this._marcarCampoInvalido('#txt_dat_fim_prazo', validacaoData.erro);
                return false;
            } else {
                this._marcarCampoValido('#txt_dat_fim_prazo');
            }
        }
        
        return true;
    }
    
    /**
     * Marca campo como inválido (adiciona classe e mensagem de erro)
     * @param {string} seletor - Seletor jQuery do campo
     * @param {string} mensagem - Mensagem de erro
     */
    _marcarCampoInvalido(seletor, mensagem) {
        console.log(`🔴 Marcando campo como inválido: ${seletor}`);
        const $campo = $(seletor);
        if (!$campo.length) {
            console.error(`❌ Campo não encontrado: ${seletor}`);
            return;
        }
        
        console.log(`✅ Campo encontrado: ${seletor}`, {
            elemento: $campo[0],
            temSelect2: $campo.data('select2') ? 'sim' : 'não'
        });
        
        // Adiciona classe is-invalid no campo select original (hidden pelo Select2)
        $campo.addClass('is-invalid');
        $campo.attr('aria-invalid', 'true');
        console.log(`✅ Classe is-invalid adicionada ao campo: ${seletor}`);
        
        // Para Select2, marca o container visível
        const $select2Container = $campo.next('.select2-container');
        console.log(`Procurando container Select2:`, {
            encontrado: $select2Container.length > 0,
            container: $select2Container[0]
        });
        
        if ($select2Container.length) {
            $select2Container.addClass('is-invalid');
            console.log(`✅ Classe is-invalid adicionada ao container Select2`);
            
            // Adiciona estilo inline para garantir que a borda vermelha apareça
            const $selection = $select2Container.find('.select2-selection');
            console.log(`Aplicando estilos ao .select2-selection:`, {
                encontrado: $selection.length > 0,
                elemento: $selection[0]
            });
            
            // Força aplicação do estilo usando setProperty com important
            $selection.each(function() {
                this.style.setProperty('border-color', '#dc3545', 'important');
                this.style.setProperty('box-shadow', '0 0 0 0.2rem rgba(220, 53, 69, 0.25)', 'important');
                this.style.setProperty('border-width', '1px', 'important');
                this.style.setProperty('border-style', 'solid', 'important');
            });
            
            // Também aplica no container para garantir
            $select2Container.each(function() {
                this.style.setProperty('border', '1px solid #dc3545', 'important');
                this.style.setProperty('border-radius', '0.375rem', 'important');
            });
            
            // Adiciona um pequeno delay e reaplica para garantir que não seja sobrescrito pelo Select2
            setTimeout(() => {
                $selection.each(function() {
                    this.style.setProperty('border-color', '#dc3545', 'important');
                    this.style.setProperty('box-shadow', '0 0 0 0.2rem rgba(220, 53, 69, 0.25)', 'important');
                });
                $select2Container.each(function() {
                    this.style.setProperty('border', '1px solid #dc3545', 'important');
                });
            }, 100);
            
            // MutationObserver removido - pode estar interferindo com cliques no Select2
            
            console.log(`✅ Estilos aplicados ao Select2`);
        } else {
            console.warn(`⚠️ Container Select2 não encontrado para: ${seletor}`);
        }
        
        // Remove feedback anterior se existir
        const $parent = $campo.closest('.col-12, .col-md-6, .col-md-4, .col-md-3, .form-group, .mb-3');
        console.log(`Procurando parent para feedback:`, {
            encontrado: $parent.length > 0,
            parent: $parent[0]
        });
        
        if ($parent.length) {
            $parent.find('.invalid-feedback').remove();
            
            // Adiciona mensagem de feedback
            const feedback = $('<div>').addClass('invalid-feedback d-block').text(mensagem);
            $parent.append(feedback);
            console.log(`✅ Mensagem de feedback adicionada: "${mensagem}"`);
        } else {
            // Se não encontrou container, adiciona após o campo ou container Select2
            const $target = $select2Container.length ? $select2Container : $campo;
            $target.closest('div').find('.invalid-feedback').remove();
            const feedback = $('<div>').addClass('invalid-feedback d-block').text(mensagem);
            $target.after(feedback);
            console.log(`✅ Mensagem de feedback adicionada após elemento: "${mensagem}"`);
        }
        
        console.log(`✅ Campo marcado como inválido: ${seletor}`);
    }
    
    /**
     * Marca campo como válido (remove classe e mensagem de erro)
     * @param {string} seletor - Seletor jQuery do campo
     */
    _marcarCampoValido(seletor) {
        const $campo = $(seletor);
        if (!$campo.length) return;
        
        // Remove classe is-invalid
        $campo.removeClass('is-invalid');
        $campo.attr('aria-invalid', 'false');
        
        // Para Select2, remove do container e estilos inline
        const $select2Container = $campo.next('.select2-container');
        if ($select2Container.length) {
            $select2Container.removeClass('is-invalid');
            $select2Container.find('.select2-selection').css({
                'border-color': '',
                'box-shadow': ''
            });
        }
        
        // Remove mensagem de feedback
        const $parent = $campo.closest('.col-12, .col-md-6, .col-md-4, .col-md-3, .form-group, .mb-3');
        if ($parent.length) {
            $parent.find('.invalid-feedback').remove();
        } else {
            $campo.closest('div').find('.invalid-feedback').remove();
        }
    }
    
    /**
     * Remove marcação de campo inválido (alias para _marcarCampoValido)
     * @param {string} seletor - Seletor jQuery do campo
     */
    _removerMarcacaoInvalida(seletor) {
        this._marcarCampoValido(seletor);
    }
    
    /**
     * Fecha todos os calendários Bootstrap Datepicker abertos
     */
    _fecharCalendarioFlatpickr() {
        if (typeof $ === 'undefined' || typeof $.fn.datepicker === 'undefined') {
            return;
        }
        
        console.log('🔒 Fechando todos os calendários Datepicker...');
        
        try {
            // Fecha todos os datepickers abertos
            $('.datepicker, input[id*="dat_fim_prazo"]').each(function() {
                const $input = $(this);
                if ($input.data('datepicker')) {
                    $input.datepicker('hide');
                }
            });
        } catch (e) {
            console.warn('Erro ao fechar Datepicker:', e);
        }
    }
    
    /**
     * Força fechamento de todos os Datepickers (útil para eventos de clique fora)
     * @param {Event} event - Evento de clique
     */
    forcarFechamentoFlatpickr(event) {
        if (typeof $ === 'undefined' || typeof $.fn.datepicker === 'undefined') {
            return;
        }
        
        const target = event.target;
        
        // Verifica se há algum datepicker aberto
        const datepickerOpen = $('.datepicker-dropdown:visible').length > 0;
        
        if (!datepickerOpen) {
            return; // Nenhum calendário aberto
        }
        
        // Verifica se o clique foi dentro do datepicker ou no input
        const isClickInDatepicker = $(target).closest('.datepicker-dropdown, .datepicker, input[id*="dat_fim_prazo"]').length > 0;
        
        // Se o clique foi fora, fecha
        if (!isClickInDatepicker) {
            this._fecharCalendarioFlatpickr();
        }
    }
    
    /**
     * Re-posiciona todos os calendários Datepicker abertos
     * Útil quando a janela é redimensionada ou quando o sidebar se move
     */
    reposicionarCalendariosFlatpickr() {
        // Bootstrap Datepicker reposiciona automaticamente
        // Este método é mantido para compatibilidade, mas não é necessário
    }
    
    /**
     * Inicializa Bootstrap Datepicker para campo de data
     * @param {HTMLElement} campoData - Elemento do campo de data
     */
    _inicializarFlatpickr(campoData) {
        // Verifica se jQuery e bootstrap-datepicker estão disponíveis
        if (typeof $ === 'undefined' || typeof $.fn.datepicker === 'undefined') {
            console.warn('Bootstrap Datepicker não está disponível. Verifique se a biblioteca foi carregada.');
            return;
        }
        
        const self = this;
        const $campo = $(campoData);
        const seletor = '#' + campoData.id;
        
        try {
            // Remove datepicker anterior se existir
            if ($campo.data('datepicker')) {
                $campo.datepicker('destroy');
            }
            
            // Verifica se está dentro de um offcanvas
            const isInOffcanvas = campoData.closest('.offcanvas') !== null;
            
            // Configura o datepicker
            const datepickerOptions = {
                language: 'pt-BR',
                format: 'dd/mm/yyyy',
                autoclose: true,
                todayHighlight: true,
                startDate: new Date(), // Não permite datas no passado
                orientation: 'bottom auto', // Posiciona abaixo, ajusta automaticamente
                zIndexOffset: 1056, // Acima do offcanvas (z-index 1055)
                templates: {
                    leftArrow: '<i class="mdi mdi-chevron-left"></i>',
                    rightArrow: '<i class="mdi mdi-chevron-right"></i>'
                }
            };
            
            // Se estiver em offcanvas, anexa ao body para evitar problemas de z-index
            if (isInOffcanvas) {
                datepickerOptions.container = 'body';
            }
            
            $campo.datepicker(datepickerOptions);
            
            // Garante que o datepicker abre ao clicar no campo
            $campo.on('click focus', function() {
                if ($campo.data('datepicker')) {
                    $campo.datepicker('show');
                }
            });
            
            // Evento de mudança de data
            $campo.on('changeDate', function(e) {
                const dateStr = e.format('dd/mm/yyyy');
                const validacao = self._validarDataFimPrazo(dateStr);
                if (validacao.valido) {
                    self._marcarCampoValido(seletor);
                } else {
                    self._marcarCampoInvalido(seletor, validacao.erro);
                }
            });
            
            // Evento de mudança manual (digitação)
            $campo.on('change', function() {
                const dateStr = $(this).val();
                if (dateStr) {
                    const validacao = self._validarDataFimPrazo(dateStr);
                    if (validacao.valido) {
                        self._marcarCampoValido(seletor);
                    } else {
                        self._marcarCampoInvalido(seletor, validacao.erro);
                    }
                }
            });
            
            console.log('✅ Bootstrap Datepicker inicializado com sucesso para:', seletor);
            
        } catch (e) {
            console.error('❌ Erro ao inicializar Bootstrap Datepicker:', e);
        }
    }
    
    /**
     * Inicialização alternativa do Datepicker com timeout
     * Útil quando o DOM ainda não está completamente pronto
     * @param {HTMLElement} campoData - Elemento do campo de data
     * @param {number} tentativa - Número da tentativa atual
     */
    _inicializarFlatpickrComTimeout(campoData, tentativa = 0) {
        const MAX_TENTATIVAS = 3;
        
        if (tentativa >= MAX_TENTATIVAS) {
            console.error('❌ Falha após múltiplas tentativas de inicializar Datepicker');
            return;
        }
        
        setTimeout(() => {
            if (!campoData || !campoData.isConnected) {
                console.warn(`Tentativa ${tentativa + 1}: Campo não encontrado no DOM`);
                this._inicializarFlatpickrComTimeout(campoData, tentativa + 1);
                return;
            }
            
            try {
                this._inicializarFlatpickr(campoData);
            } catch (e) {
                console.warn(`Tentativa ${tentativa + 1} falhou:`, e);
                this._inicializarFlatpickrComTimeout(campoData, tentativa + 1);
            }
        }, tentativa * 300); // Aumenta delay a cada tentativa
    }
    
    /**
     * Configura validação em tempo real para campos obrigatórios
     * Atualiza a validação imediatamente quando o usuário preenche ou seleciona um campo
     */
    _configurarValidacaoTempoReal() {
        const self = this;
        
        // Validação para campos Select2 obrigatórios
        // Usa delegação de eventos diretamente nos elementos, não no document
        // para evitar interferência com cliques no Select2
        
        // Unidade de Destino
        $('#field_lst_cod_unid_tram_dest').off('change.select2-validation').on('change.select2-validation', function() {
            const valor = $(this).val();
            if (valor && valor !== '') {
                self._marcarCampoValido('#field_lst_cod_unid_tram_dest');
            }
        });
        
        // Status
        $('#field_lst_cod_status').off('change.select2-validation').on('change.select2-validation', function() {
            const valor = $(this).val();
            if (valor && valor !== '') {
                self._marcarCampoValido('#field_lst_cod_status');
            }
        });
        
        // Usuário de Destino (opcional, mas valida se preenchido)
        $('#field_lst_cod_usuario_dest').off('change.select2-validation').on('change.select2-validation', function() {
            const valor = $(this).val();
            if (valor && valor !== '') {
                self._marcarCampoValido('#field_lst_cod_usuario_dest');
            }
        });
        
        // Validação para campo de data de fim de prazo (usa ID com prefixo field_)
        $('#field_txt_dat_fim_prazo, #txt_dat_fim_prazo').off('change blur').on('change blur', function() {
            const valor = $(this).val();
            const seletor = '#' + $(this).attr('id');
            if (valor && valor.trim() !== '') {
                const validacao = self._validarDataFimPrazo(valor);
                if (validacao.valido) {
                    self._marcarCampoValido(seletor);
                } else {
                    self._marcarCampoInvalido(seletor, validacao.erro);
                }
            } else {
                // Se estiver vazio, remove marcação (campo é opcional)
                self._marcarCampoValido(seletor);
            }
        });
        
        // Validação para outros campos obrigatórios (inputs, textareas)
        $(document).off('input change blur', '#tramitacao_individual_form [required], #tramitacao_lote_form [required]').on('input change blur', '#tramitacao_individual_form [required], #tramitacao_lote_form [required]', function() {
            const $campo = $(this);
            
            // Ignora campos Select2 que já têm validação específica
            if ($campo.hasClass('select2') || $campo.data('select2') || $campo.attr('id') === 'field_lst_cod_unid_tram_dest' || 
                $campo.attr('id') === 'field_lst_cod_status' || $campo.attr('id') === 'field_lst_cod_usuario_dest') {
                return;
            }
            
            // Ignora campo de data que já tem validação específica
            if ($campo.attr('id') === 'txt_dat_fim_prazo' || $campo.attr('id') === 'field_txt_dat_fim_prazo') {
                return;
            }
            
            // Valida campo
            if (this.checkValidity && this.checkValidity()) {
                self._marcarCampoValido('#' + $campo.attr('id'));
            } else if ($campo.val() && $campo.val().trim() !== '') {
                // Se o campo tem valor, considera válido
                self._marcarCampoValido('#' + $campo.attr('id'));
            }
        });
    }
    
    /**
     * Valida data de fim de prazo
     * @param {string} dataFimPrazo - Data no formato dd/mm/aaaa
     * @returns {Object} - {valido: boolean, erro?: string}
     */
    _validarDataFimPrazo(dataFimPrazo) {
        if (!dataFimPrazo || dataFimPrazo.trim() === '') {
            return { valido: true }; // Opcional
        }
        
        // Valida formato
        const regexData = /^(\d{2})\/(\d{2})\/(\d{4})$/;
        if (!regexData.test(dataFimPrazo)) {
            return { valido: false, erro: 'Data de fim de prazo deve estar no formato dd/mm/aaaa' };
        }
        
        // Valida data válida
        const partes = dataFimPrazo.split('/');
        const dia = parseInt(partes[0], 10);
        const mes = parseInt(partes[1], 10) - 1; // Mês é 0-indexed
        const ano = parseInt(partes[2], 10);
        const data = new Date(ano, mes, dia);
        
        if (data.getDate() !== dia || data.getMonth() !== mes || data.getFullYear() !== ano) {
            return { valido: false, erro: 'Data de fim de prazo inválida' };
        }
        
        // Valida que não é no passado
        const hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        if (data < hoje) {
            return { valido: false, erro: 'Data de fim de prazo não pode ser anterior à data atual' };
        }
        
        return { valido: true };
    }
    
    /**
     * Valida formulário para salvar rascunho
     */
    validarFormularioRascunho() {
        console.log('=== INICIANDO VALIDAÇÃO DO FORMULÁRIO ===');
        const form = document.getElementById('tramitacao_individual_form');
        if (!form) {
            console.error('Formulário não encontrado!');
            return false;
        }
        
        // Limpa validações anteriores
        form.classList.remove('was-validated');
        $('.is-invalid').removeClass('is-invalid');
        $('.invalid-feedback').remove();
        $('[aria-invalid="true"]').attr('aria-invalid', 'false');
        $('.select2-container.is-invalid').removeClass('is-invalid');
        $('.select2-container .select2-selection').css({
            'border-color': '',
            'box-shadow': ''
        });
        
        let camposInvalidos = [];
        
        // Valida campos hidden obrigatórios
        // Os campos hidden usam prefixo field_ no ID, mas o name é o original
        let unidOrigem = $('#field_lst_cod_unid_tram_local').val() || $('input[name="lst_cod_unid_tram_local"]').val();
        let codUsuario = $('#field_hdn_cod_usuario_local').val() || $('#hdn_cod_usuario_local').val() || $('input[name="hdn_cod_usuario_local"]').val();
        let codEntidade = $('#field_hdn_cod_materia').val() || $('#hdn_cod_materia').val() || $('input[name="hdn_cod_materia"]').val() || 
                         $('#field_hdn_cod_documento').val() || $('#hdn_cod_documento').val() || $('input[name="hdn_cod_documento"]').val();
        let tipo = $('#field_hdn_tipo_tramitacao').val() || $('#hdn_tipo_tramitacao').val() || $('input[name="hdn_tipo_tramitacao"]').val();
        
        // Se não encontrou pelos seletores, tenta pelo form diretamente
        if (!codEntidade && form) {
            const inputMateria = form.querySelector('input[name="hdn_cod_materia"]') || form.querySelector('#field_hdn_cod_materia') || form.querySelector('#hdn_cod_materia');
            const inputDocumento = form.querySelector('input[name="hdn_cod_documento"]') || form.querySelector('#field_hdn_cod_documento') || form.querySelector('#hdn_cod_documento');
            if (inputMateria && inputMateria.value) {
                codEntidade = inputMateria.value;
            } else if (inputDocumento && inputDocumento.value) {
                codEntidade = inputDocumento.value;
            }
        }
        
        if (!tipo && form) {
            const inputTipo = form.querySelector('input[name="hdn_tipo_tramitacao"]') || form.querySelector('#field_hdn_tipo_tramitacao') || form.querySelector('#hdn_tipo_tramitacao');
            if (inputTipo && inputTipo.value) {
                tipo = inputTipo.value;
            }
        }
        
        if (!codUsuario && form) {
            const inputUsuario = form.querySelector('input[name="hdn_cod_usuario_local"]') || form.querySelector('#field_hdn_cod_usuario_local') || form.querySelector('#hdn_cod_usuario_local');
            if (inputUsuario && inputUsuario.value) {
                codUsuario = inputUsuario.value;
            }
        }
        
        if (!unidOrigem && form) {
            const inputUnid = form.querySelector('input[name="lst_cod_unid_tram_local"]') || form.querySelector('#field_lst_cod_unid_tram_local') || form.querySelector('#lst_cod_unid_tram_local');
            if (inputUnid && inputUnid.value) {
                unidOrigem = inputUnid.value;
            }
        }
        
        console.log('Campos hidden encontrados:', { 
            unidOrigem, 
            codUsuario, 
            codEntidade, 
            tipo
        });
        
        if (!unidOrigem || !codUsuario || !codEntidade || !tipo) {
            console.error('❌ Campos obrigatórios não encontrados:', {
                unidOrigem: !!unidOrigem,
                codUsuario: !!codUsuario,
                codEntidade: !!codEntidade,
                tipo: !!tipo,
                formHTML: form ? form.innerHTML.substring(0, 500) : 'form não encontrado'
            });
            this.app.mostrarToast('Erro', 'Erro interno: dados do formulário incompletos', 'error');
            return false;
        }
        
        // Valida Select2 - Unidade de Destino (obrigatório)
        const $unidDest = $('#field_lst_cod_unid_tram_dest');
        const unidDest = $unidDest.val();
        console.log('Validando Unidade de Destino:', {
            elemento: $unidDest.length > 0 ? 'encontrado' : 'NÃO ENCONTRADO',
            valor: unidDest,
            temSelect2: $unidDest.data('select2') ? 'sim' : 'não'
        });
        
        if (!unidDest || unidDest === '' || unidDest === null) {
            console.log('❌ Unidade de Destino - campo vazio, marcando como inválido');
            this._marcarCampoInvalido('#field_lst_cod_unid_tram_dest', 'Unidade de destino é obrigatória');
            camposInvalidos.push('Unidade de Destino');
        } else {
            console.log('✅ Unidade de Destino - válido');
            this._marcarCampoValido('#field_lst_cod_unid_tram_dest');
        }
        
        // Valida Select2 - Status (obrigatório)
        const $status = $('#field_lst_cod_status');
        const status = $status.val();
        console.log('Validando Status:', {
            elemento: $status.length > 0 ? 'encontrado' : 'NÃO ENCONTRADO',
            valor: status,
            temSelect2: $status.data('select2') ? 'sim' : 'não'
        });
        
        if (!status || status === '' || status === null) {
            console.log('❌ Status - campo vazio, marcando como inválido');
            this._marcarCampoInvalido('#field_lst_cod_status', 'Status é obrigatório');
            camposInvalidos.push('Status');
        } else {
            console.log('✅ Status - válido');
            this._marcarCampoValido('#field_lst_cod_status');
        }
        
        // Valida data de fim de prazo (se preenchida, deve ser >= hoje)
        const dataFimPrazo = $('#txt_dat_fim_prazo').val();
        if (dataFimPrazo && dataFimPrazo.trim() !== '') {
            const validacaoData = this._validarDataFimPrazo(dataFimPrazo);
            if (!validacaoData.valido) {
                this._marcarCampoInvalido('#txt_dat_fim_prazo', validacaoData.erro);
                camposInvalidos.push('Data de Fim de Prazo');
            } else {
                this._marcarCampoValido('#txt_dat_fim_prazo');
            }
        }
        
        // Valida campos HTML5 obrigatórios (exceto Select2 que já foi validado acima)
        form.querySelectorAll('[required]:not(.select2)').forEach(campo => {
            // Ignora campos Select2 que já foram validados
            if ($(campo).hasClass('select2') || $(campo).data('select2')) {
                return;
            }
            
            // Remove mensagem de validação HTML5 padrão
            campo.setCustomValidity('');
            
            if (!campo.checkValidity()) {
                $(campo).addClass('is-invalid');
                $(campo).attr('aria-invalid', 'true');
                
                // Adiciona mensagem de feedback se não existir
                if (!$(campo).next('.invalid-feedback').length) {
                    const feedback = document.createElement('div');
                    feedback.className = 'invalid-feedback d-block';
                    feedback.textContent = 'Este campo é obrigatório';
                    $(campo).after(feedback);
                }
                
                // Adiciona ao array de campos inválidos
                const label = $(campo).closest('.col-12, .col-md-6, .col-md-4, .col-md-3').find('label').text().trim();
                if (label && !camposInvalidos.includes(label)) {
                    camposInvalidos.push(label);
                }
            } else {
                $(campo).removeClass('is-invalid');
                $(campo).attr('aria-invalid', 'false');
            }
        });
        
        // Se há campos inválidos, mostra mensagem e marca formulário como validado
        if (camposInvalidos.length > 0) {
            form.classList.add('was-validated');
            
            console.log(`❌ Validação falhou. Campos inválidos: ${camposInvalidos.join(', ')}`);
            
            // Scroll para o primeiro campo inválido
            const primeiroInvalido = form.querySelector('.select2-container.is-invalid, .is-invalid[aria-invalid="true"]');
            if (primeiroInvalido) {
                console.log('Fazendo scroll para primeiro campo inválido:', primeiroInvalido);
                primeiroInvalido.scrollIntoView({ behavior: 'smooth', block: 'center' });
                
                // Tenta abrir o Select2 se for um container Select2
                if (primeiroInvalido.classList.contains('select2-container')) {
                    const selectOriginal = primeiroInvalido.previousElementSibling;
                    if (selectOriginal && $(selectOriginal).data('select2')) {
                        try {
                            $(selectOriginal).select2('open');
                        } catch (e) {
                            console.warn('Erro ao abrir Select2:', e);
                        }
                    }
                } else {
                    // Se não for Select2, apenas foca
                    primeiroInvalido.focus();
                }
            } else {
                console.warn('Nenhum campo inválido encontrado para scroll, mas há campos inválidos:', camposInvalidos);
            }
            
            return false;
        }
        
        console.log('✅ Validação passou - todos os campos estão válidos');
        return true;
    }
    
    /**
     * Salva tramitação como rascunho
     */
    salvarRascunho() {
        const form = document.getElementById('tramitacao_individual_form');
        if (!form) {
            this.app.mostrarToast('Erro', 'Formulário não encontrado', 'error');
            return;
        }
        
        // Valida campos obrigatórios antes de salvar
        if (!this.validarFormularioRascunho()) {
            form.classList.add('was-validated');
            return;
        }
        
        // ✅ IMPORTANTE: Sincroniza conteúdo do TinyMCE com o textarea antes de criar FormData
        // Se o TinyMCE estiver ativo, precisa copiar o conteúdo para o textarea original
        if (typeof tinymce !== 'undefined') {
            // Tenta ambos os IDs possíveis (com e sem prefixo field_)
            const editorIds = ['field_txa_txt_tramitacao', 'txa_txt_tramitacao'];
            for (const editorId of editorIds) {
                const editor = tinymce.get(editorId);
                if (editor) {
                    // Sincroniza conteúdo do editor com o textarea
                    editor.save();
                    break; // Para no primeiro editor encontrado
                }
            }
        }
        
        const formData = new FormData(form);
        formData.append('acao', 'salvar_rascunho');
        
        // Adiciona código do usuário ao FormData (passado pelo template como COD_USUARIO_CORRENTE)
        if (COD_USUARIO_CORRENTE && COD_USUARIO_CORRENTE !== 0 && COD_USUARIO_CORRENTE !== '0' && COD_USUARIO_CORRENTE !== 'None') {
            formData.append('cod_usuario', COD_USUARIO_CORRENTE);
            formData.append('cod_usuario_corrente', COD_USUARIO_CORRENTE);
        }
        
        // Mostra indicador de processamento padronizado
        const btnSalvar = document.getElementById('btnSalvarRascunho');
        const estadoOriginal = btnSalvar ? this._ativarLoadingBotao(btnSalvar, 'Salvando...') : null;
        
        $.ajax({
            url: `${PORTAL_URL}/tramitacao_individual_salvar_json`,
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: (response) => {
                const dados = typeof response === 'string' ? JSON.parse(response) : response;
                if (dados.erro) {
                    this.app.mostrarToast('Erro', dados.erro, 'error');
                } else {
                    this.app.mostrarToast('Sucesso', 'Rascunho salvo com sucesso!', 'success');
                    
                    // Processa tasks de PDF/anexo se disponíveis
                    if (dados.cod_tramitacao && typeof processarRespostaSalvarTramitacao === 'function') {
                        processarRespostaSalvarTramitacao(dados, dados.cod_tramitacao);
                    }
                    
                    // ✅ CORRETO: Atualiza contadores e listas de forma sincronizada após salvar rascunho
                    // Isso garante que sidebar, breadcrumb e paginação fiquem consistentes
                    if (dados.reload_contadores || dados.reload_listas) {
                        if (this.app && typeof this.app.atualizarContadores === 'function') {
                            // atualizarContadores sincroniza contadores + lista se necessário
                            this.app.atualizarContadores(dados.reload_listas === true);
                        } else {
                            // Fallback: atualiza individualmente se a função não existir
                            if (dados.reload_contadores && this.app && typeof this.app.carregarContadores === 'function') {
                                this.app.carregarContadores();
                            }
                            if (dados.reload_listas && this.app && typeof this.app.carregarTramitacoes === 'function') {
                                this.app.carregarTramitacoes();
                            }
                        }
                    }
                    
                    // Marca que rascunho foi salvo (para atualizar lista ao fechar)
                    this.rascunhoSalvo = true;
                    
                    // Desativa proteção contra fechamento acidental após salvar com sucesso
                    this.protecaoFechamentoIndividual = false;
                    // Atualiza backdrop para permitir fechamento
                    this._atualizarBackdropProtecao('individual');
                    
                    // Se há dados da tramitação salva, carrega no formulário
                    if (dados.dados_tramitacao && dados.cod_tramitacao) {
                        // Adiciona/atualiza campo hidden com cod_tramitacao
                        let inputCodTramitacao = form.querySelector('input[name="hdn_cod_tramitacao"]');
                        if (!inputCodTramitacao) {
                            inputCodTramitacao = document.createElement('input');
                            inputCodTramitacao.type = 'hidden';
                            inputCodTramitacao.name = 'hdn_cod_tramitacao';
                            form.appendChild(inputCodTramitacao);
                        }
                        inputCodTramitacao.value = dados.cod_tramitacao;
                        
                        // Popula formulário com os dados da tramitação salva
                        this.popularFormularioComDados(dados.dados_tramitacao);
                        
                        // Atualiza estado inicial para o estado atual (após salvar, não há mais alterações não salvas)
                        setTimeout(() => {
                            this._salvarEstadoInicialFormulario('individual');
                        }, 1500);
                        
                        // Mostra botão "Enviar Tramitação" agora que há cod_tramitacao
                        this._atualizarBotoesFormulario(true);
                    } else {
                        // Mesmo sem dados_tramitacao, atualiza estado inicial (formulário foi salvo)
                        setTimeout(() => {
                            this._salvarEstadoInicialFormulario('individual');
                        }, 500);
                    }
                }
            },
            error: (xhr) => {
                const erro = xhr.responseJSON?.erro || 'Erro ao salvar rascunho';
                this.app.mostrarToast('Erro', erro, 'error');
            },
            complete: () => {
                if (btnSalvar && estadoOriginal) {
                    this._desativarLoadingBotao(btnSalvar, estadoOriginal);
                }
            }
        });
    }
    
    /**
     * Envia tramitação
     */
    enviarTramitacao() {
        const form = document.getElementById('tramitacao_individual_form');
        if (!form) {
            this.app.mostrarToast('Erro', 'Formulário não encontrado', 'error');
            return;
        }
        
        if (!this.validarFormularioIndividual()) {
            form.classList.add('was-validated');
            return;
        }
        
        // Valida PDF se opção "Anexar" estiver selecionada
        const opcaoPdf = $('input[name="radTI"]:checked').val();
        const arquivoPdf = document.getElementById('file_nom_arquivo');
        
        if (opcaoPdf === 'S' && arquivoPdf) {
            if (!arquivoPdf.files || arquivoPdf.files.length === 0) {
                this.app.mostrarToast('Erro', 'É necessário anexar um arquivo PDF quando a opção "Anexar" está selecionada', 'error');
                return;
            }
            
            const arquivo = arquivoPdf.files[0];
            
            // Valida tipo de arquivo
            if (!arquivo.name.toLowerCase().endsWith('.pdf')) {
                this.app.mostrarToast('Erro', 'O arquivo anexado deve ser um PDF (.pdf)', 'error');
                return;
            }
            
            // Valida tamanho máximo (10MB)
            const TAMANHO_MAXIMO = 10 * 1024 * 1024; // 10MB
            if (arquivo.size > TAMANHO_MAXIMO) {
                const tamanhoMB = (arquivo.size / (1024 * 1024)).toFixed(2);
                this.app.mostrarToast('Erro', `O arquivo PDF é muito grande (${tamanhoMB}MB). Tamanho máximo permitido: 10MB`, 'error');
                return;
            }
            
            if (arquivo.size === 0) {
                this.app.mostrarToast('Erro', 'O arquivo PDF está vazio', 'error');
                return;
            }
        }
        
        // ✅ IMPORTANTE: Sincroniza conteúdo do TinyMCE com o textarea antes de criar FormData
        // Se o TinyMCE estiver ativo, precisa copiar o conteúdo para o textarea original
        if (typeof tinymce !== 'undefined') {
            // Tenta ambos os IDs possíveis (com e sem prefixo field_)
            const editorIds = ['field_txa_txt_tramitacao', 'txa_txt_tramitacao'];
            for (const editorId of editorIds) {
                const editor = tinymce.get(editorId);
                if (editor) {
                    // Sincroniza conteúdo do editor com o textarea
                    editor.save();
                    break; // Para no primeiro editor encontrado
                }
            }
        }
        
        const formData = new FormData(form);
        formData.append('acao', 'enviar');
        
        // Adiciona código do usuário ao FormData (passado pelo template como COD_USUARIO_CORRENTE)
        if (COD_USUARIO_CORRENTE && COD_USUARIO_CORRENTE !== 0 && COD_USUARIO_CORRENTE !== '0' && COD_USUARIO_CORRENTE !== 'None') {
            formData.append('cod_usuario', COD_USUARIO_CORRENTE);
            formData.append('cod_usuario_corrente', COD_USUARIO_CORRENTE);
        }
        
        // Mostra indicador de processamento padronizado
        const btnEnviar = document.getElementById('btnEnviarTramitacao');
        const estadoOriginal = btnEnviar ? this._ativarLoadingBotao(btnEnviar, 'Enviando...') : null;
        
        $.ajax({
            url: `${PORTAL_URL}/tramitacao_individual_salvar_json`,
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: (response) => {
                const dados = typeof response === 'string' ? JSON.parse(response) : response;
                if (dados.erro) {
                    this.app.mostrarToast('Erro', dados.erro, 'error');
                } else {
                    // Verifica se foi realmente um ENVIO (não salvar)
                    const foiEnviado = dados.tramitacao_enviada === true || dados.acao === 'tramitacao_enviada';
                    
                    if (foiEnviado) {
                    this.app.mostrarToast('Sucesso', 'Tramitação enviada com sucesso!', 'success');
                    
                    // Processa tasks de PDF/anexo se disponíveis
                        // IMPORTANTE: Passa true como terceiro parâmetro para indicar que foi ENVIADO
                        // Isso evita que o formulário seja recarregado após o envio
                    if (dados.cod_tramitacao && typeof processarRespostaSalvarTramitacao === 'function') {
                            processarRespostaSalvarTramitacao(dados, dados.cod_tramitacao, true);
                    }
                    
                    // Desativa proteção antes de fechar (já foi enviado, não precisa proteger)
                    this.protecaoFechamentoIndividual = false;
                    // Atualiza backdrop para permitir fechamento
                    this._atualizarBackdropProtecao('individual');
                        
                        // IMPORTANTE: Fecha o formulário imediatamente quando é envio
                        // Não recarrega, não popula formulário, apenas fecha e atualiza interface
                    this.fecharSidebarIndividual(true);
                        
                        // ✅ CORRETO: Atualiza contadores e listas de forma sincronizada
                        // Se reload_contadores E/OU reload_listas, atualiza tudo de uma vez
                        if ((dados.reload_contadores || dados.reload_listas) && this.app && typeof this.app.atualizarContadores === 'function') {
                            // atualizarContadores sincroniza contadores + lista se necessário
                            this.app.atualizarContadores(dados.reload_listas === true);
                        } else {
                            // Fallback: atualiza individualmente se a função não existir
                            if (dados.reload_contadores && this.app && typeof this.app.carregarContadores === 'function') {
                                this.app.carregarContadores();
                            }
                            if (dados.reload_listas && this.app && typeof this.app.carregarTramitacoes === 'function') {
                                this.app.carregarTramitacoes();
                            }
                        }
                    } else {
                        // Se não foi enviado, trata como salvar (comportamento antigo)
                        this.app.mostrarToast('Sucesso', 'Tramitação enviada com sucesso!', 'success');
                        
                        if (dados.cod_tramitacao && typeof processarRespostaSalvarTramitacao === 'function') {
                            processarRespostaSalvarTramitacao(dados, dados.cod_tramitacao, true);
                        }
                        
                        this.protecaoFechamentoIndividual = false;
                        this._atualizarBackdropProtecao('individual');
                        this.fecharSidebarIndividual(true);
                    }
                }
            },
            error: (xhr) => {
                const erro = xhr.responseJSON?.erro || 'Erro ao enviar tramitação';
                this.app.mostrarToast('Erro', erro, 'error');
            },
            complete: () => {
                if (btnEnviar && estadoOriginal) {
                    this._desativarLoadingBotao(btnEnviar, estadoOriginal);
                }
            }
        });
    }
    
    /**
     * Valida formulário em lote completo
     */
    validarFormularioLote() {
        const form = document.getElementById('tramitacao_lote_form');
        if (!form) return false;
        
        form.classList.remove('was-validated');
        $('.is-invalid').removeClass('is-invalid');
        $('.invalid-feedback').remove();
        
        // Valida que há processos selecionados
        if (!this.app || !this.app.processosSelecionados || this.app.processosSelecionados.size === 0) {
            this.app.mostrarToast('Erro', 'Selecione pelo menos um processo para tramitar', 'error');
            return false;
        }
        
        // Valida HTML5
        if (!form.checkValidity()) {
            form.classList.add('was-validated');
            return false;
        }
        
        // Valida Select2 - Unidade de Destino
        const unidDest = $('#field_lst_cod_unid_tram_dest').val();
        if (!unidDest || unidDest === '') {
            $('#field_lst_cod_unid_tram_dest').next('.select2-container').addClass('is-invalid');
            if (!$('#field_lst_cod_unid_tram_dest').next('.select2-container').next('.invalid-feedback').length) {
                $('#field_lst_cod_unid_tram_dest').after('<div class="invalid-feedback">Unidade de destino é obrigatória</div>');
            }
            return false;
        }
        
        // Valida Select2 - Status
        const status = $('#field_lst_cod_status').val();
        if (!status || status === '') {
            $('#field_lst_cod_status').next('.select2-container').addClass('is-invalid');
            if (!$('#field_lst_cod_status').next('.select2-container').next('.invalid-feedback').length) {
                $('#field_lst_cod_status').after('<div class="invalid-feedback">Status é obrigatório</div>');
            }
            return false;
        }
        
        // Valida tipo único (todos os processos devem ser do mesmo tipo)
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
            this.app.mostrarToast('Erro', 'Não foi possível determinar o tipo dos processos selecionados', 'error');
            return false;
        }
        
        if (tiposProcessos.size > 1) {
            this.app.mostrarToast('Erro', 'Não é possível tramitar processos de tipos diferentes em lote. Selecione apenas processos do mesmo tipo.', 'error');
            return false;
        }
        
        return true;
    }
    
    /**
     * Tramita processos em lote
     * IMPORTANTE: Formulário sempre está no sidebar
     */
    tramitarLote() {
        const form = document.getElementById('tramitacao_lote_form');
        if (!form) {
            this.app.mostrarToast('Erro', 'Formulário não encontrado', 'error');
            return;
        }
        
        // Validação completa
        if (!this.validarFormularioLote()) {
            return;
        }
        
        // Valida PDF se opção "Anexar" estiver selecionada
        const opcaoPdf = $('input[name="radTI"]:checked').val();
        const arquivoPdf = document.getElementById('file_nom_arquivo_lote');
        
        if (opcaoPdf === 'S' && arquivoPdf) {
            if (!arquivoPdf.files || arquivoPdf.files.length === 0) {
                this.app.mostrarToast('Erro', 'É necessário anexar um arquivo PDF quando a opção "Anexar" está selecionada', 'error');
                return;
            }
            
            const arquivo = arquivoPdf.files[0];
            
            // Valida tipo de arquivo
            if (!arquivo.name.toLowerCase().endsWith('.pdf')) {
                this.app.mostrarToast('Erro', 'O arquivo anexado deve ser um PDF (.pdf)', 'error');
                return;
            }
            
            // Valida tamanho máximo (10MB)
            const TAMANHO_MAXIMO = 10 * 1024 * 1024; // 10MB
            if (arquivo.size > TAMANHO_MAXIMO) {
                const tamanhoMB = (arquivo.size / (1024 * 1024)).toFixed(2);
                this.app.mostrarToast('Erro', `O arquivo PDF é muito grande (${tamanhoMB}MB). Tamanho máximo permitido: 10MB`, 'error');
                return;
            }
            
            if (arquivo.size === 0) {
                this.app.mostrarToast('Erro', 'O arquivo PDF está vazio', 'error');
                return;
            }
        }
        
        // Prepara FormData
        const formData = new FormData(form);
        
        // Adiciona processos selecionados
        Array.from(this.app.processosSelecionados).forEach(codEntidade => {
            formData.append('check_tram', codEntidade);
        });
        
        // Mostra indicador de processamento
        const btnTramitar = document.getElementById('btnTramitarLote');
        const btnOriginal = btnTramitar ? btnTramitar.innerHTML : '';
        if (btnTramitar) {
            btnTramitar.disabled = true;
            btnTramitar.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processando...';
        }
        
        $.ajax({
            url: `${PORTAL_URL}/tramitacao_lote_salvar_json`,
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: (response) => {
                const dados = typeof response === 'string' ? JSON.parse(response) : response;
                if (dados.erro) {
                    this.app.mostrarToast('Erro', dados.erro, 'error');
                } else {
                    const total = dados.total || this.app.processosSelecionados.size;
                    this.app.mostrarToast('Sucesso', `Tramitação em lote realizada! ${total} processo(s) tramitado(s) com sucesso.`, 'success');
                    // Desativa proteção antes de fechar (já foi enviado, não precisa proteger)
                    this.protecaoFechamentoLote = false;
                    // Atualiza backdrop para permitir fechamento
                    this._atualizarBackdropProtecao('lote');
                    this.fecharSidebarLote(true);
                }
            },
            error: (xhr) => {
                const erro = xhr.responseJSON?.erro || 'Erro ao processar tramitação em lote';
                this.app.mostrarToast('Erro', erro, 'error');
            },
            complete: () => {
                if (btnTramitar) {
                    btnTramitar.disabled = false;
                    btnTramitar.innerHTML = btnOriginal;
                }
            }
        });
    }
    
    /**
     * Fecha sidebar individual
     */
    fecharSidebarIndividual(atualizarLista = true) {
        // Se vai atualizar a lista, marca que já foi atualizado para evitar duplicação
        if (atualizarLista) {
            this.rascunhoSalvo = false; // Reseta flag para evitar atualização duplicada
        }
        
        if (this.sidebarIndividual) {
            this.sidebarIndividual.hide();
        }
        if (atualizarLista && this.app && this.app.carregarTramitacoes) {
            this.app.carregarTramitacoes();
        }
    }
    
    /**
     * Fecha sidebar lote
     */
    fecharSidebarLote(atualizarLista = true) {
        if (this.sidebarLote) {
            this.sidebarLote.hide();
        }
        if (atualizarLista && this.app) {
            if (this.app.carregarTramitacoes) {
                this.app.carregarTramitacoes();
            }
            if (this.app.processosSelecionados) {
                this.app.processosSelecionados.clear();
            }
            if (this.app.atualizarContadorSelecionados) {
                this.app.atualizarContadorSelecionados();
            }
        }
    }
    
    /**
     * Limpa formulário individual
     * IMPORTANTE: Destrói componentes antes de limpar para evitar memory leaks
     */
    limparFormularioIndividual() {
        // IMPORTANTE: Destrói componentes ANTES de limpar o HTML do sidebar
        
        // Remove Select2 se existir
        this._destruirSelect2('#field_lst_cod_unid_tram_dest, #field_lst_cod_usuario_dest, #field_lst_cod_status');
        
        // Remove Trumbowyg se existir - tenta todos os IDs possíveis
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
        
        // Remove Flatpickr se existir
        if (typeof flatpickr !== 'undefined') {
            try {
                const fp = flatpickr("#txt_dat_fim_prazo");
                if (fp) {
                    fp.destroy();
                }
            } catch (e) {
                // Ignora erro se Flatpickr não foi inicializado
            }
        }
        
        // Limpa HTML do sidebar (DEPOIS de destruir componentes)
        const sidebarBody = document.getElementById('tramitacaoIndividualOffcanvasBody');
        if (sidebarBody) {
            sidebarBody.innerHTML = '';
        }
        
        // Remove event listeners
        $(document).off('change', '#field_lst_cod_unid_tram_local');
        $(document).off('change', '#field_lst_cod_unid_tram_dest');
    }
    
    /**
     * Limpa formulário lote
     * IMPORTANTE: Destrói componentes antes de limpar para evitar memory leaks
     */
    limparFormularioLote() {
        // IMPORTANTE: Destrói componentes ANTES de limpar o HTML do sidebar
        
        // Remove Select2 se existir
        this._destruirSelect2('#field_lst_cod_unid_tram_dest, #field_lst_cod_usuario_dest, #field_lst_cod_status');
        
        // Remove Trumbowyg se existir - tenta todos os IDs possíveis do formulário em lote
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
        
        // Remove Bootstrap Datepicker se existir
        if (typeof $ !== 'undefined' && typeof $.fn.datepicker !== 'undefined') {
            try {
                $('#field_txt_dat_fim_prazo, #txt_dat_fim_prazo').each(function() {
                    const $input = $(this);
                    if ($input.data('datepicker')) {
                        $input.datepicker('destroy');
                    }
                });
            } catch (e) {
                // Ignora erro se Datepicker não foi inicializado
            }
        }
        
        // Limpa HTML do sidebar (DEPOIS de destruir componentes)
        const sidebarBody = document.getElementById('tramitacaoLoteOffcanvasBody');
        if (sidebarBody) {
            sidebarBody.innerHTML = '';
        }
        
        // Remove event listeners
        $(document).off('change', '#field_lst_cod_unid_tram_local');
        $(document).off('change', '#field_lst_cod_unid_tram_dest');
    }
    
    /**
     * Atualiza visibilidade dos botões do formulário individual
     * @param {boolean} temCodTramitacao - Se há cod_tramitacao (rascunho salvo)
     */
    _atualizarBotoesFormulario(temCodTramitacao) {
        const btnSalvar = document.getElementById('btnSalvarRascunho');
        const btnEnviar = document.getElementById('btnEnviarTramitacao');
        
        if (btnSalvar && btnEnviar) {
            if (temCodTramitacao) {
                // Quando há cod_tramitacao, mostra ambos os botões
                btnSalvar.style.display = '';
                btnEnviar.style.display = '';
                // Muda texto do botão salvar para "Salvar Alterações"
                btnSalvar.innerHTML = '<i class="mdi mdi-content-save-outline" aria-hidden="true"></i> Salvar Alterações';
            } else {
                // Quando não há cod_tramitacao, mostra apenas "Salvar"
                btnSalvar.style.display = '';
                btnEnviar.style.display = 'none';
                // Texto original do botão salvar
                btnSalvar.innerHTML = '<i class="mdi mdi-content-save-outline" aria-hidden="true"></i> Salvar';
            }
        }
    }
}

// Inicializa quando o DOM estiver pronto
let tramitacaoApp;
$(document).ready(function() {
    tramitacaoApp = new TramitacaoEmailStyle();
    window.tramitacaoApp = tramitacaoApp; // Expõe globalmente para uso em onclick
    
    // Inicializa sidebar manager
    if (tramitacaoApp) {
        tramitacaoApp.sidebarManager = new TramitacaoSidebarManager(tramitacaoApp);
    }
});

// ============================================================================
// Monitoramento de Tasks Celery (PDF e Anexos)
// ============================================================================

/**
 * Classe para monitorar tarefas Celery assíncronas
 * Baseada no padrão de processo_adm (polling adaptativo)
 */
class TaskMonitor {
    constructor(options = {}) {
        this.pollIntervalInitial = options.pollIntervalInitial || 300;  // 300ms primeiros polls
        this.pollIntervalNormal = options.pollIntervalNormal || 1000;   // 1000ms depois
        this.maxPollTime = options.maxPollTime || 300000;              // 5 minutos
        this.startTime = null;
        this.pollTimer = null;
        this.pollCount = 0;
        this.shouldStopPolling = false;
        this.processamentoConcluido = false;
        this.currentTaskId = null;
        this.onProgress = options.onProgress || null;
        this.onSuccess = options.onSuccess || null;
        this.onError = options.onError || null;
        this.onComplete = options.onComplete || null;
    }
    
    /**
     * Inicia monitoramento de uma task
     * @param {string} taskId - ID da task Celery
     * @param {string} statusUrl - URL para consultar status
     */
    start(taskId, statusUrl) {
        if (!taskId || !statusUrl) {
            console.error('[TaskMonitor] taskId e statusUrl são obrigatórios');
            return;
        }
        
        // Evita múltiplos polling para o mesmo task_id (padrão processo_adm)
        if (this.currentTaskId === taskId && this.pollTimer) {
            console.log('[TaskMonitor] Polling já ativo para task_id:', taskId);
            return;
        }
        
        // Limpa qualquer polling anterior
        this.stop();
        
        this.taskId = taskId;
        this.statusUrl = statusUrl;
        this.startTime = Date.now();
        this.currentTaskId = taskId;
        this.shouldStopPolling = false;
        this.processamentoConcluido = false;
        this.pollCount = 0;
        
        // Primeira verificação imediata (padrão processo_adm)
        console.log('[TaskMonitor] Iniciando polling imediato para task_id:', taskId);
        this.checkStatusOnce();
        
        // Agenda polling adaptativo
        this.scheduleNextPoll();
    }
    
    /**
     * Para o monitoramento
     */
    stop() {
        this.shouldStopPolling = true;
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }
    }
    
    /**
     * Consulta status da task (uma vez)
     */
    async checkStatusOnce() {
        // Verifica se deve parar (padrão processo_adm)
        if (this.shouldStopPolling || this.processamentoConcluido || 
            this.currentTaskId !== this.taskId || this.currentTaskId === null) {
            if (this.pollTimer) {
                clearTimeout(this.pollTimer);
                this.pollTimer = null;
            }
            return;
        }
        
        // Verifica timeout
        if (Date.now() - this.startTime > this.maxPollTime) {
            this.stop();
            if (this.onError) {
                this.onError({
                    message: 'Timeout ao monitorar task',
                    taskId: this.taskId
                });
            }
            return;
        }
        
        try {
            // Adiciona timestamp para evitar cache (padrão processo_adm)
            const url = `${this.statusUrl}&_=${Date.now()}`;
            console.log('[TaskMonitor] Consultando status:', url);
            const response = await fetch(url);
            
            if (!response.ok) {
                console.error('[TaskMonitor] Erro HTTP:', response.status, response.statusText);
                throw new Error('HTTP ' + response.status);
            }
            
            const data = await response.json();
            console.log('[TaskMonitor] Status recebido:', data);
            
            // Atualiza UI
            if (this.onProgress) {
                this.onProgress({
                    status: data.status || 'PENDING',
                    progress: data.current || 0,
                    total: data.total || 0,
                    processadas: data.processadas || 0,
                    sucesso: data.sucesso || 0,
                    erro: data.erro || 0,
                    tramitacao_atual: data.tramitacao_atual,
                    message: data.status_text || data.message || 'Processando...',
                    stage: data.stage,
                    taskId: this.taskId
                });
            }
            
            // Verifica conclusão (padrão processo_adm)
            const isSuccess = data.ready === true && (
                data.status === 'SUCCESS' || 
                (data.status && data.status.toLowerCase().includes('sucesso'))
            );
            const isFailure = data.ready === true && (
                data.status === 'FAILURE' || 
                (data.status && data.status.toLowerCase().includes('failure')) ||
                (data.error && data.error.length > 0)
            );
            
            if (isFailure) {
                this.stop();
                this.currentTaskId = null;
                if (this.onError) {
                    this.onError({
                        status: 'FAILURE',
                        error: data.error || data.message || 'Erro desconhecido',
                        resultados: data.resultados || [],
                        taskId: this.taskId
                    });
                }
                if (this.onComplete) {
                    this.onComplete({
                        status: 'FAILURE',
                        taskId: this.taskId
                    });
                }
            } else if (isSuccess) {
                // Evita processamento duplicado de SUCCESS (padrão processo_adm)
                if (this.processamentoConcluido) {
                    console.log('[TaskMonitor] SUCCESS já foi processado, ignorando para evitar loop');
                    return;
                }
                
                this.processamentoConcluido = true;
                this.stop();
                this.currentTaskId = null;
                
                if (this.onSuccess) {
                    this.onSuccess({
                        status: 'SUCCESS',
                        result: data,
                        taskId: this.taskId
                    });
                }
                if (this.onComplete) {
                    this.onComplete({
                        status: 'SUCCESS',
                        taskId: this.taskId
                    });
                }
            }
            // Se status é PENDING, PROGRESS ou STARTED, continua o polling
            
        } catch (error) {
            console.error('[TaskMonitor] Erro ao consultar status:', error);
            console.error('[TaskMonitor] URL que falhou:', this.statusUrl);
            console.error('[TaskMonitor] Stack:', error.stack);
            // Não para o polling em caso de erro de rede temporário (padrão processo_adm)
            // Mas loga o erro para debug
        }
    }
    
    /**
     * Agenda próximo poll (polling adaptativo - padrão processo_adm)
     */
    scheduleNextPoll() {
        this.pollCount++;
        
        // Polling adaptativo: primeiros 5 polls com 300ms, depois 1000ms
        const currentInterval = this.pollCount <= 5 
            ? this.pollIntervalInitial 
            : this.pollIntervalNormal;
        
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
        }
        
        // Verifica se deve parar
        if (this.shouldStopPolling || this.processamentoConcluido) {
            this.pollTimer = null;
            return;
        }
        
        if (this.currentTaskId === this.taskId && this.currentTaskId !== null && !this.processamentoConcluido) {
            this.pollTimer = setTimeout(() => {
                // Verifica novamente se deve parar
                if (this.shouldStopPolling || this.processamentoConcluido || 
                    this.currentTaskId !== this.taskId || this.currentTaskId === null) {
                    this.pollTimer = null;
                    return;
                }
                this.checkStatusOnce();
                this.scheduleNextPoll();
            }, currentInterval);
        } else {
            this.pollTimer = null;
        }
    }
}

/**
 * Cria modal de progresso para processamento individual
 */
function criarModalProgresso(modalId, titulo) {
    console.log('[criarModalProgresso] Criando modal:', { modalId, titulo });
    
    // Remove modal existente se houver
    const existingModal = document.getElementById(modalId);
    if (existingModal) {
        console.log('[criarModalProgresso] Removendo modal existente');
        existingModal.remove();
    }
    
    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal fade show';
    modal.style.display = 'block';
    modal.style.zIndex = '9999';
    modal.setAttribute('data-backdrop', 'static');
    modal.setAttribute('data-keyboard', 'false');
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">${titulo}</h5>
                </div>
                <div class="modal-body">
                    <div class="progress mb-3">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" 
                             style="width: 0%"
                             id="${modalId}-progress">
                            0%
                        </div>
                    </div>
                    <p id="${modalId}-message" class="text-center mb-0">Processando...</p>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    console.log('[criarModalProgresso] Modal adicionado ao DOM:', document.getElementById(modalId));
    
    // Adiciona backdrop
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop fade show';
    backdrop.style.zIndex = '9998';
    backdrop.id = `${modalId}-backdrop`;
    document.body.appendChild(backdrop);
    console.log('[criarModalProgresso] Backdrop adicionado ao DOM');
}

/**
 * Atualiza modal de progresso individual
 */
function atualizarModalProgresso(modalId, data) {
    const progressBar = document.getElementById(`${modalId}-progress`);
    const messageEl = document.getElementById(`${modalId}-message`);
    
    if (progressBar) {
        const progress = data.progress || 0;
        progressBar.style.width = `${progress}%`;
        progressBar.textContent = `${progress}%`;
    }
    
    if (messageEl && data.message) {
        messageEl.textContent = data.message;
    }
}

/**
 * Fecha modal de progresso individual
 */
function fecharModalProgresso(modalId) {
    const modal = document.getElementById(modalId);
    const backdrop = document.getElementById(`${modalId}-backdrop`);
    
    // Remove classes de exibição imediatamente
    if (modal) {
        modal.classList.remove('show', 'fade');
        modal.style.display = 'none';
        // Remove do DOM após animação
        setTimeout(() => {
            if (modal.parentNode) {
                modal.remove();
            }
        }, 300);
    }
    
    // Remove backdrop imediatamente para desbloquear interface
    if (backdrop) {
        backdrop.classList.remove('show', 'fade');
        backdrop.style.display = 'none';
        // Remove do DOM após animação
        setTimeout(() => {
            if (backdrop.parentNode) {
                backdrop.remove();
            }
        }, 300);
    }
    
    // Remove qualquer backdrop do Bootstrap que possa ter ficado
    const allBackdrops = document.querySelectorAll('.modal-backdrop');
    allBackdrops.forEach(bd => {
        if (bd.id === `${modalId}-backdrop` || !bd.id) {
            bd.classList.remove('show', 'fade');
            bd.style.display = 'none';
            setTimeout(() => {
                if (bd.parentNode) {
                    bd.remove();
                }
            }, 300);
        }
    });
    
    // Remove classe modal-open do body se não houver outros modais
    const body = document.body;
    const otherModals = document.querySelectorAll('.modal.show, .modal[style*="display: block"]');
    if (otherModals.length === 0) {
        body.classList.remove('modal-open');
        body.style.overflow = '';
        body.style.paddingRight = '';
    }
}

/**
 * Cria modal de progresso para processamento em lote
 */
function criarModalProgressoLote(modalId, titulo, total) {
    // Remove modal existente se houver
    const existingModal = document.getElementById(modalId);
    if (existingModal) {
        existingModal.remove();
    }
    
    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal fade show';
    modal.style.display = 'block';
    modal.setAttribute('data-backdrop', 'static');
    modal.setAttribute('data-keyboard', 'false');
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">${titulo}</h5>
                </div>
                <div class="modal-body">
                    <div class="progress mb-3">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" 
                             style="width: 0%"
                             id="${modalId}-progress">
                            0%
                        </div>
                    </div>
                    <div class="row mb-2">
                        <div class="col-md-4">
                            <small class="text-muted">Total: <strong id="${modalId}-total">${total}</strong></small>
                        </div>
                        <div class="col-md-4">
                            <small class="text-success">Sucesso: <strong id="${modalId}-sucesso">0</strong></small>
                        </div>
                        <div class="col-md-4">
                            <small class="text-danger">Erro: <strong id="${modalId}-erro">0</strong></small>
                        </div>
                    </div>
                    <p id="${modalId}-message" class="text-center mb-0">Processando...</p>
                    <p id="${modalId}-atual" class="text-center text-muted small mt-2 mb-0"></p>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Adiciona backdrop
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop fade show';
    backdrop.id = `${modalId}-backdrop`;
    document.body.appendChild(backdrop);
}

/**
 * Atualiza modal de progresso em lote
 */
function atualizarModalProgressoLote(modalId, data) {
    const progressBar = document.getElementById(`${modalId}-progress`);
    const messageEl = document.getElementById(`${modalId}-message`);
    const atualEl = document.getElementById(`${modalId}-atual`);
    const totalEl = document.getElementById(`${modalId}-total`);
    const sucessoEl = document.getElementById(`${modalId}-sucesso`);
    const erroEl = document.getElementById(`${modalId}-erro`);
    
    if (progressBar) {
        const progress = data.progress || 0;
        progressBar.style.width = `${progress}%`;
        progressBar.textContent = `${progress}%`;
    }
    
    if (messageEl && data.message) {
        messageEl.textContent = data.message;
    }
    
    if (atualEl && data.tramitacao_atual) {
        atualEl.textContent = `Processando tramitação: ${data.tramitacao_atual}`;
    }
    
    if (totalEl && data.total !== undefined) {
        totalEl.textContent = data.total;
    }
    
    if (sucessoEl && data.sucesso !== undefined) {
        sucessoEl.textContent = data.sucesso;
    }
    
    if (erroEl && data.erro !== undefined) {
        erroEl.textContent = data.erro;
    }
}

/**
 * Fecha modal de progresso em lote
 */
function fecharModalProgressoLote(modalId) {
    const modal = document.getElementById(modalId);
    const backdrop = document.getElementById(`${modalId}-backdrop`);
    
    if (modal) {
        modal.classList.remove('show');
        modal.style.display = 'none';
        setTimeout(() => modal.remove(), 300);
    }
    
    if (backdrop) {
        backdrop.classList.remove('show');
        setTimeout(() => backdrop.remove(), 300);
    }
}

/**
 * Monitora geração de PDF para tramitação individual
 */
function monitorarGeracaoPDF(taskInfo, codTramitacao, naoRecarregarFormulario = false) {
    console.log('[monitorarGeracaoPDF] Iniciando com:', { taskInfo, codTramitacao, naoRecarregarFormulario });
    
    if (!taskInfo || !taskInfo.task_id || !taskInfo.monitor_url) {
        console.error('[monitorarGeracaoPDF] taskInfo inválido:', taskInfo);
        return;
    }
    
    // Cria modal de progresso
    const modalId = `modal-pdf-${codTramitacao}`;
    console.log('[monitorarGeracaoPDF] Criando modal:', modalId);
    
    if (typeof criarModalProgresso === 'function') {
        criarModalProgresso(modalId, 'Gerando PDF do despacho...');
        console.log('[monitorarGeracaoPDF] Modal criado');
    } else {
        console.error('[monitorarGeracaoPDF] Função criarModalProgresso não encontrada!');
    }
    
    // Cria monitor (padrão processo_adm: polling adaptativo)
    console.log('[monitorarGeracaoPDF] Criando TaskMonitor');
    const monitor = new TaskMonitor({
        pollIntervalInitial: 300,  // 300ms primeiros polls
        pollIntervalNormal: 1000,  // 1000ms depois
        maxPollTime: 300000,       // 5 minutos
        onProgress: (data) => {
            console.log('[monitorarGeracaoPDF] onProgress:', data);
            if (typeof atualizarModalProgresso === 'function') {
                atualizarModalProgresso(modalId, {
                    progress: data.progress || 0,
                    message: data.message || 'Gerando PDF...'
                });
            }
        },
        onSuccess: (data) => {
            console.log('[monitorarGeracaoPDF] onSuccess:', data);
            
            // Salva PDF no repositório Zope
            const taskId = data.task_id || taskInfo.task_id;
            if (taskId) {
                const portalUrl = window.location.origin + (window.location.pathname.includes('/sagl/') ? '' : '/sagl');
                const salvarUrl = `${portalUrl}/@@tramitacao_despacho_pdf_salvar?task_id=${taskId}`;
                
                console.log('[monitorarGeracaoPDF] Salvando PDF:', salvarUrl);
                
                fetch(salvarUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    credentials: 'include'
                })
                .then(response => response.json())
                .then(result => {
                    console.log('[monitorarGeracaoPDF] PDF salvo:', result);
                    
                    // Fecha modal imediatamente para desbloquear interface
                    if (typeof fecharModalProgresso === 'function') {
                        fecharModalProgresso(modalId);
                    }
                    
                    if (typeof mostrarToast === 'function') {
                        if (result.success || result.sucesso) {
                            mostrarToast('PDF gerado e salvo com sucesso!', 'success');
                        } else {
                            mostrarToast('PDF gerado, mas houve erro ao salvar: ' + (result.erro || result.error || 'Erro desconhecido'), 'warning');
                        }
                    }
                    
                    // Recarrega formulário para mostrar link do PDF
                    if (result.cod_tramitacao && typeof window.tramitacaoApp !== 'undefined' && window.tramitacaoApp) {
                        const sidebarManager = window.tramitacaoApp.sidebarManager;
                        const tipo = result.tipo || 'MATERIA';
                        
                        // Verifica se o formulário individual está aberto (com verificações de segurança)
                        // Verifica tanto se o sidebar está visível quanto se há um formulário carregado
                        let isFormOpen = false;
                        let hasFormLoaded = false;
                        let isSameTramitacao = false;
                        
                        try {
                            // Verifica o elemento DOM do sidebar diretamente (não o objeto Bootstrap)
                            const sidebarEl = document.getElementById('tramitacaoIndividualOffcanvas');
                            
                            if (sidebarEl) {
                                // Verifica se o sidebar está visível
                                isFormOpen = sidebarEl.classList && sidebarEl.classList.contains('show');
                                
                                // Verifica se há um formulário carregado no sidebar
                                const sidebarBody = document.getElementById('tramitacaoIndividualOffcanvasBody');
                                if (sidebarBody) {
                                    const form = sidebarBody.querySelector('#tramitacao_individual_form');
                                    hasFormLoaded = !!form;
                                    
                                    // Verifica se o formulário tem o mesmo cod_tramitacao
                                    if (form) {
                                        const hdnCodTramitacao = form.querySelector('input[name="hdn_cod_tramitacao"]');
                                        if (hdnCodTramitacao && hdnCodTramitacao.value) {
                                            const currentCodTramitacao = parseInt(hdnCodTramitacao.value);
                                            isSameTramitacao = (currentCodTramitacao === parseInt(result.cod_tramitacao));
                                        } else {
                                            // Se não tem cod_tramitacao no formulário, pode ser uma nova tramitação
                                            // Nesse caso, verifica se o formulário está aberto mesmo assim
                                            isSameTramitacao = true; // Considera como mesma se o formulário está aberto
                                        }
                                    }
                                }
                            }
                        } catch (e) {
                            console.warn('[monitorarGeracaoPDF] Erro ao verificar se formulário está aberto:', e);
                            isFormOpen = false;
                            hasFormLoaded = false;
                            isSameTramitacao = false;
                        }
                        
                        // Se naoRecarregarFormulario for true (envio), não recarrega o formulário
                        const shouldReload = !naoRecarregarFormulario && isFormOpen && hasFormLoaded && isSameTramitacao;
                        
                        console.log('[monitorarGeracaoPDF] Verificando se deve recarregar formulário:', {
                            cod_tramitacao: result.cod_tramitacao,
                            tipo: tipo,
                            sidebarManager: !!sidebarManager,
                            sidebarIndividual: sidebarManager ? !!sidebarManager.sidebarIndividual : false,
                            isOpen: isFormOpen,
                            hasFormLoaded: hasFormLoaded,
                            isSameTramitacao: isSameTramitacao,
                            naoRecarregarFormulario: naoRecarregarFormulario,
                            shouldReload: shouldReload
                        });
                        
                        if (shouldReload && sidebarManager) {
                            // Se o formulário individual está aberto e carregado com a mesma tramitação, recarrega
                            console.log('[monitorarGeracaoPDF] Recarregando formulário para mostrar link do PDF');
                            
                            // Aguarda um pouco para garantir que:
                            // 1. O modal foi fechado completamente
                            // 2. O PDF foi salvo no repositório Zope
                            // 3. O repositório está atualizado
                            setTimeout(() => {
                                if (typeof sidebarManager.abrirEdicao === 'function') {
                                    console.log('[monitorarGeracaoPDF] Chamando abrirEdicao para recarregar formulário:', {
                                        cod_tramitacao: result.cod_tramitacao,
                                        tipo: tipo
                                    });
                                    sidebarManager.abrirEdicao(result.cod_tramitacao, tipo);
                                } else {
                                    console.error('[monitorarGeracaoPDF] Função abrirEdicao não encontrada no sidebarManager');
                                }
                            }, 1000); // Aumentado para 1 segundo para garantir que o PDF foi salvo
                        } else {
                            // Se o formulário não está aberto, apenas loga (usuário pode abrir depois)
                            console.log('[monitorarGeracaoPDF] Formulário não está aberto ou não é a mesma tramitação, link do PDF estará disponível quando abrir');
                        }
                    } else {
                        console.warn('[monitorarGeracaoPDF] Não foi possível recarregar formulário:', {
                            temCodTramitacao: !!result.cod_tramitacao,
                            temTramitacaoApp: typeof window.tramitacaoApp !== 'undefined' && !!window.tramitacaoApp
                        });
                    }
                })
                .catch(error => {
                    console.error('[monitorarGeracaoPDF] Erro ao salvar PDF:', error);
                    if (typeof fecharModalProgresso === 'function') {
                        fecharModalProgresso(modalId);
                    }
                    if (typeof mostrarToast === 'function') {
                        mostrarToast('PDF gerado, mas houve erro ao salvar: ' + (error.message || 'Erro desconhecido'), 'warning');
                    }
                });
            } else {
                // Fallback: apenas fecha modal se não houver task_id
                if (typeof fecharModalProgresso === 'function') {
                    fecharModalProgresso(modalId);
                }
                if (typeof mostrarToast === 'function') {
                    mostrarToast('PDF gerado com sucesso!', 'success');
                }
            }
        },
        onError: (error) => {
            console.error('[monitorarGeracaoPDF] onError:', error);
            
            // Fecha modal imediatamente para desbloquear interface
            if (typeof fecharModalProgresso === 'function') {
                fecharModalProgresso(modalId);
            }
            
            if (typeof mostrarToast === 'function') {
                mostrarToast('Erro ao gerar PDF: ' + (error.error || error.message || 'Erro desconhecido'), 'error');
            }
        }
    });
    
    console.log('[monitorarGeracaoPDF] Iniciando monitor.start com:', { task_id: taskInfo.task_id, monitor_url: taskInfo.monitor_url });
    monitor.start(taskInfo.task_id, taskInfo.monitor_url);
    console.log('[monitorarGeracaoPDF] Monitor iniciado');
}

/**
 * Monitora junção de anexo para tramitação individual
 */
function monitorarJuncaoAnexo(taskInfo, codTramitacao, naoRecarregarFormulario = false) {
    // naoRecarregarFormulario: parâmetro para compatibilidade (esta função não recarrega formulário)
    if (!taskInfo || !taskInfo.task_id || !taskInfo.monitor_url) {
        console.error('[monitorarJuncaoAnexo] taskInfo inválido:', taskInfo);
        return;
    }
    
    // Cria modal de progresso
    const modalId = `modal-anexo-${codTramitacao}`;
    criarModalProgresso(modalId, 'Juntando anexo ao PDF...');
    
    // Cria monitor
    const monitor = new TaskMonitor({
        pollIntervalInitial: 300,
        pollIntervalNormal: 1000,
        maxPollTime: 300000,
        onProgress: (data) => {
            atualizarModalProgresso(modalId, {
                progress: data.progress || 0,
                message: data.message || 'Juntando anexo...'
            });
        },
        onSuccess: (data) => {
            console.log('[monitorarJuncaoAnexo] onSuccess:', data);
            
            // Salva PDF juntado no repositório Zope
            const taskId = data.task_id || taskInfo.task_id;
            if (taskId) {
                const portalUrl = window.location.origin + (window.location.pathname.includes('/sagl/') ? '' : '/sagl');
                const salvarUrl = `${portalUrl}/@@tramitacao_anexar_arquivo_salvar?task_id=${taskId}`;
                
                console.log('[monitorarJuncaoAnexo] Salvando PDF juntado:', salvarUrl);
                
                fetch(salvarUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    credentials: 'include'
                })
                .then(response => response.json())
                .then(result => {
                    console.log('[monitorarJuncaoAnexo] PDF juntado salvo:', result);
                    if (typeof fecharModalProgresso === 'function') {
                        fecharModalProgresso(modalId);
                    }
                    if (typeof mostrarToast === 'function') {
                        if (result.success || result.sucesso) {
                            mostrarToast('Anexo juntado e salvo com sucesso!', 'success');
                        } else {
                            mostrarToast('Anexo juntado, mas houve erro ao salvar: ' + (result.erro || result.error || 'Erro desconhecido'), 'warning');
                        }
                    }
                })
                .catch(error => {
                    console.error('[monitorarJuncaoAnexo] Erro ao salvar PDF juntado:', error);
                    if (typeof fecharModalProgresso === 'function') {
                        fecharModalProgresso(modalId);
                    }
                    if (typeof mostrarToast === 'function') {
                        mostrarToast('Anexo juntado, mas houve erro ao salvar: ' + (error.message || 'Erro desconhecido'), 'warning');
                    }
                });
            } else {
                // Fallback: apenas fecha modal se não houver task_id
                if (typeof fecharModalProgresso === 'function') {
                    fecharModalProgresso(modalId);
                }
                if (typeof mostrarToast === 'function') {
                    mostrarToast('Anexo juntado com sucesso!', 'success');
                }
            }
        },
        onError: (error) => {
            fecharModalProgresso(modalId);
            mostrarToast('Erro ao juntar anexo: ' + (error.error || error.message || 'Erro desconhecido'), 'error');
        }
    });
    
    monitor.start(taskInfo.task_id, taskInfo.monitor_url);
}

/**
 * Monitora geração de PDF em lote
 */
function monitorarGeracaoPDFLote(taskInfo, codTramitacoes) {
    if (!taskInfo || !taskInfo.task_id || !taskInfo.monitor_url) {
        console.error('[monitorarGeracaoPDFLote] taskInfo inválido:', taskInfo);
        return;
    }
    
    const total = codTramitacoes ? codTramitacoes.length : taskInfo.total || 0;
    
    // Cria modal de progresso em lote
    const modalId = 'modal-pdf-lote';
    criarModalProgressoLote(modalId, 'Gerando PDFs em lote...', total);
    
    // Cria monitor
    const monitor = new TaskMonitor({
        pollIntervalInitial: 300,
        pollIntervalNormal: 1000,
        maxPollTime: 600000,  // 10 minutos para lote
        onProgress: (data) => {
            atualizarModalProgressoLote(modalId, {
                progress: data.progress || 0,
                message: data.message || 'Gerando PDFs...',
                total: data.total || total,
                sucesso: data.sucesso || 0,
                erro: data.erro || 0,
                tramitacao_atual: data.tramitacao_atual
            });
        },
        onSuccess: (data) => {
            console.log('[monitorarGeracaoPDFLote] onSuccess:', data);
            
            // Salva PDFs no repositório Zope
            const taskId = data.task_id || taskInfo.task_id;
            if (taskId) {
                const portalUrl = window.location.origin + (window.location.pathname.includes('/sagl/') ? '' : '/sagl');
                const salvarUrl = `${portalUrl}/@@tramitacao_despacho_pdf_salvar_lote?task_id=${taskId}`;
                
                console.log('[monitorarGeracaoPDFLote] Salvando PDFs em lote:', salvarUrl);
                
                fetch(salvarUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    credentials: 'include'
                })
                .then(response => response.json())
                .then(result => {
                    console.log('[monitorarGeracaoPDFLote] PDFs salvos:', result);
                    if (typeof fecharModalProgressoLote === 'function') {
                        fecharModalProgressoLote(modalId);
                    }
                    const sucesso = data.result?.sucesso || result.salvos || 0;
                    const erro = data.result?.erro || result.erros || 0;
                    if (typeof mostrarToast === 'function') {
                        if (result.success || result.sucesso) {
                            mostrarToast(`PDFs gerados e salvos: ${sucesso} sucesso, ${erro} erro(s)`, sucesso > 0 ? 'success' : 'warning');
                        } else {
                            mostrarToast(`PDFs gerados, mas houve erro ao salvar: ${result.erro || result.error || 'Erro desconhecido'}`, 'warning');
                        }
                    }
                })
                .catch(error => {
                    console.error('[monitorarGeracaoPDFLote] Erro ao salvar PDFs:', error);
                    if (typeof fecharModalProgressoLote === 'function') {
                        fecharModalProgressoLote(modalId);
                    }
                    const sucesso = data.result?.sucesso || 0;
                    const erro = data.result?.erro || 0;
                    if (typeof mostrarToast === 'function') {
                        mostrarToast(`PDFs gerados, mas houve erro ao salvar: ${error.message || 'Erro desconhecido'} (${sucesso} sucesso, ${erro} erro(s))`, 'warning');
                    }
                });
            } else {
                // Fallback: apenas fecha modal se não houver task_id
                if (typeof fecharModalProgressoLote === 'function') {
                    fecharModalProgressoLote(modalId);
                }
                const sucesso = data.result?.sucesso || 0;
                const erro = data.result?.erro || 0;
                if (typeof mostrarToast === 'function') {
                    mostrarToast(`PDFs gerados: ${sucesso} sucesso, ${erro} erro(s)`, sucesso > 0 ? 'success' : 'warning');
                }
            }
        },
        onError: (error) => {
            fecharModalProgressoLote(modalId);
            mostrarToast('Erro ao gerar PDFs em lote: ' + (error.error || error.message || 'Erro desconhecido'), 'error');
        }
    });
    
    monitor.start(taskInfo.task_id, taskInfo.monitor_url);
}

/**
 * Monitora junção de anexo em lote
 */
function monitorarJuncaoAnexoLote(taskInfo, codTramitacoes) {
    if (!taskInfo || !taskInfo.task_id || !taskInfo.monitor_url) {
        console.error('[monitorarJuncaoAnexoLote] taskInfo inválido:', taskInfo);
        return;
    }
    
    const total = codTramitacoes ? codTramitacoes.length : taskInfo.total || 0;
    
    // Cria modal de progresso em lote
    const modalId = 'modal-anexo-lote';
    criarModalProgressoLote(modalId, 'Juntando anexo em lote...', total);
    
    // Cria monitor
    const monitor = new TaskMonitor({
        pollIntervalInitial: 300,
        pollIntervalNormal: 1000,
        maxPollTime: 600000,  // 10 minutos para lote
        onProgress: (data) => {
            atualizarModalProgressoLote(modalId, {
                progress: data.progress || 0,
                message: data.message || 'Juntando anexos...',
                total: data.total || total,
                sucesso: data.sucesso || 0,
                erro: data.erro || 0,
                tramitacao_atual: data.tramitacao_atual
            });
        },
        onSuccess: (data) => {
            console.log('[monitorarJuncaoAnexoLote] onSuccess:', data);
            
            // Salva PDFs juntados no repositório Zope
            const taskId = data.task_id || taskInfo.task_id;
            if (taskId) {
                const portalUrl = window.location.origin + (window.location.pathname.includes('/sagl/') ? '' : '/sagl');
                const salvarUrl = `${portalUrl}/@@tramitacao_anexar_arquivo_lote_salvar?task_id=${taskId}`;
                
                console.log('[monitorarJuncaoAnexoLote] Salvando PDFs juntados em lote:', salvarUrl);
                
                fetch(salvarUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    credentials: 'include'
                })
                .then(response => response.json())
                .then(result => {
                    console.log('[monitorarJuncaoAnexoLote] PDFs juntados salvos:', result);
                    if (typeof fecharModalProgressoLote === 'function') {
                        fecharModalProgressoLote(modalId);
                    }
                    const sucesso = data.result?.sucesso || result.salvos || 0;
                    const erro = data.result?.erro || result.erros || 0;
                    if (typeof mostrarToast === 'function') {
                        if (result.success || result.sucesso) {
                            mostrarToast(`Anexos juntados e salvos: ${sucesso} sucesso, ${erro} erro(s)`, sucesso > 0 ? 'success' : 'warning');
                        } else {
                            mostrarToast(`Anexos juntados, mas houve erro ao salvar: ${result.erro || result.error || 'Erro desconhecido'}`, 'warning');
                        }
                    }
                })
                .catch(error => {
                    console.error('[monitorarJuncaoAnexoLote] Erro ao salvar PDFs juntados:', error);
                    if (typeof fecharModalProgressoLote === 'function') {
                        fecharModalProgressoLote(modalId);
                    }
                    const sucesso = data.result?.sucesso || 0;
                    const erro = data.result?.erro || 0;
                    if (typeof mostrarToast === 'function') {
                        mostrarToast(`Anexos juntados, mas houve erro ao salvar: ${error.message || 'Erro desconhecido'} (${sucesso} sucesso, ${erro} erro(s))`, 'warning');
                    }
                });
            } else {
                // Fallback: apenas fecha modal se não houver task_id
                if (typeof fecharModalProgressoLote === 'function') {
                    fecharModalProgressoLote(modalId);
                }
                const sucesso = data.result?.sucesso || 0;
                const erro = data.result?.erro || 0;
                if (typeof mostrarToast === 'function') {
                    mostrarToast(`Anexos juntados: ${sucesso} sucesso, ${erro} erro(s)`, sucesso > 0 ? 'success' : 'warning');
                }
            }
        },
        onError: (error) => {
            fecharModalProgressoLote(modalId);
            mostrarToast('Erro ao juntar anexos em lote: ' + (error.error || error.message || 'Erro desconhecido'), 'error');
        }
    });
    
    monitor.start(taskInfo.task_id, taskInfo.monitor_url);
}

/**
 * Função auxiliar para mostrar toast/notificação
 * Se não existir uma função global mostrarToast, cria uma simples
 */
if (typeof mostrarToast === 'undefined') {
    function mostrarToast(mensagem, tipo = 'info') {
        // Tipos: success, error, warning, info
        const tipos = {
            success: { bg: 'bg-success', icon: '✓' },
            error: { bg: 'bg-danger', icon: '✗' },
            warning: { bg: 'bg-warning', icon: '⚠' },
            info: { bg: 'bg-info', icon: 'ℹ' }
        };
        
        const config = tipos[tipo] || tipos.info;
        
        // Remove toast existente
        const existingToast = document.getElementById('tramitacao-toast');
        if (existingToast) {
            existingToast.remove();
        }
        
        // Cria toast
        const toast = document.createElement('div');
        toast.id = 'tramitacao-toast';
        toast.className = `toast ${config.bg} text-white`;
        toast.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="toast-body d-flex align-items-center">
                <span class="me-2">${config.icon}</span>
                <span>${mensagem}</span>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Mostra toast
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Remove após 3 segundos
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// ============================================================================
// Funções de Integração - Salvar Tramitação com Monitoramento
// ============================================================================

/**
 * Salva tramitação individual e monitora geração de PDF/anexo se necessário
 * Esta função deve ser chamada após o backend retornar sucesso com task_id
 * 
 * @param {Object} responseData - Dados da resposta do backend após salvar tramitação
 * @param {number} codTramitacao - Código da tramitação salva
 * 
 * Exemplo de responseData esperado:
 * {
 *   sucesso: true,
 *   cod_tramitacao: 123,
 *   task_pdf: { task_id: 'xxx', monitor_url: '...' },  // Opcional
 *   task_anexo: { task_id: 'yyy', monitor_url: '...' } // Opcional
 * }
 */
function processarRespostaSalvarTramitacao(responseData, codTramitacao, naoRecarregarFormulario = false) {
    console.log('[processarRespostaSalvarTramitacao] Chamado com:', {
        responseData: responseData,
        codTramitacao: codTramitacao,
        naoRecarregarFormulario: naoRecarregarFormulario,
        temSucesso: responseData && responseData.sucesso,
        temTaskPdf: responseData && responseData.task_pdf,
        temTaskAnexo: responseData && responseData.task_anexo
    });
    
    // Aceita resposta com sucesso:true OU sem erro (compatibilidade)
    if (!responseData || (responseData.erro && !responseData.sucesso)) {
        console.warn('[processarRespostaSalvarTramitacao] Resposta inválida ou com erro:', responseData);
        return;
    }
    
    // ✅ Atualiza link do botão PDF se presente na resposta
    if (responseData.link_pdf_despacho && responseData.update_pdf_link) {
        console.log('[processarRespostaSalvarTramitacao] Atualizando link PDF:', responseData.link_pdf_despacho);
        if (typeof window.atualizarLinkPdfTramitacao === 'function') {
            window.atualizarLinkPdfTramitacao(responseData.link_pdf_despacho);
        } else {
            // Fallback: atualiza diretamente se função não existir
            var btnPdf = document.getElementById('btn_visualizar_pdf_tramitacao');
            if (btnPdf) {
                btnPdf.href = responseData.link_pdf_despacho;
                btnPdf.setAttribute('data-link-pdf', responseData.link_pdf_despacho);
                console.log('[processarRespostaSalvarTramitacao] Link PDF atualizado diretamente:', responseData.link_pdf_despacho);
            } else {
                console.warn('[processarRespostaSalvarTramitacao] Botão PDF não encontrado (id: btn_visualizar_pdf_tramitacao)');
                // Tenta novamente após um pequeno delay (caso o botão ainda não exista)
                setTimeout(function() {
                    var btnPdf = document.getElementById('btn_visualizar_pdf_tramitacao');
                    if (btnPdf) {
                        btnPdf.href = responseData.link_pdf_despacho;
                        btnPdf.setAttribute('data-link-pdf', responseData.link_pdf_despacho);
                        console.log('[processarRespostaSalvarTramitacao] Link PDF atualizado (retry):', responseData.link_pdf_despacho);
                    }
                }, 200);
            }
        }
        
        // Executa script inline se presente
        if (responseData.exec_script) {
            try {
                console.log('[processarRespostaSalvarTramitacao] Executando script inline de atualização');
                eval(responseData.exec_script);
            } catch (e) {
                console.error('[processarRespostaSalvarTramitacao] Erro ao executar script inline:', e);
            }
        }
    }
    
    // Se houver task de PDF, monitora
    if (responseData.task_pdf && responseData.task_pdf.task_id) {
        console.log('[processarRespostaSalvarTramitacao] Iniciando monitoramento de PDF:', responseData.task_pdf);
        if (typeof monitorarGeracaoPDF === 'function') {
            monitorarGeracaoPDF(responseData.task_pdf, codTramitacao, naoRecarregarFormulario);
        } else {
            console.error('[processarRespostaSalvarTramitacao] Função monitorarGeracaoPDF não encontrada!');
        }
    } else {
        console.log('[processarRespostaSalvarTramitacao] Nenhuma task_pdf encontrada na resposta');
    }
    
    // Se houver task de anexo, monitora
    if (responseData.task_anexo && responseData.task_anexo.task_id) {
        console.log('[processarRespostaSalvarTramitacao] Iniciando monitoramento de anexo:', responseData.task_anexo);
        if (typeof monitorarJuncaoAnexo === 'function') {
            monitorarJuncaoAnexo(responseData.task_anexo, codTramitacao, naoRecarregarFormulario);
        } else {
            console.error('[processarRespostaSalvarTramitacao] Função monitorarJuncaoAnexo não encontrada!');
        }
    }
    
    // Se não houver tasks, apenas mostra sucesso (mas não sobrescreve toast já mostrado)
    if (!responseData.task_pdf && !responseData.task_anexo) {
        console.log('[processarRespostaSalvarTramitacao] Nenhuma task encontrada, apenas log (toast já foi mostrado)');
    }
}

/**
 * Processa resposta de tramitação em lote e monitora geração de PDFs/anexos
 * 
 * @param {Object} responseData - Dados da resposta do backend após tramitar em lote
 * @param {Array<number>} codTramitacoes - Lista de códigos de tramitações processadas
 * 
 * Exemplo de responseData esperado:
 * {
 *   sucesso: true,
 *   total: 10,
 *   task_pdf_lote: { task_id: 'xxx', monitor_url: '...' },  // Opcional
 *   task_anexo_lote: { task_id: 'yyy', monitor_url: '...' } // Opcional
 * }
 */
function processarRespostaTramitarEmLote(responseData, codTramitacoes) {
    if (!responseData || !responseData.sucesso) {
        return;
    }
    
    // Se houver task de PDF em lote, monitora
    if (responseData.task_pdf_lote && responseData.task_pdf_lote.task_id) {
        monitorarGeracaoPDFLote(responseData.task_pdf_lote, codTramitacoes);
    }
    
    // Se houver task de anexo em lote, monitora
    if (responseData.task_anexo_lote && responseData.task_anexo_lote.task_id) {
        monitorarJuncaoAnexoLote(responseData.task_anexo_lote, codTramitacoes);
    }
    
    // Se não houver tasks, apenas mostra sucesso
    if (!responseData.task_pdf_lote && !responseData.task_anexo_lote) {
        mostrarToast(`Tramitações processadas: ${responseData.total || codTramitacoes.length}`, 'success');
    }
}

/**
 * Exemplo de função para salvar tramitação individual (integração)
 * Esta função deve ser adaptada conforme a implementação real do sistema
 * 
 * @param {FormData|Object} formData - Dados do formulário
 * @returns {Promise<Object>} Resposta do servidor
 */
async function salvarTramitacaoIndividualExemplo(formData) {
    try {
        // Mostra loading (se houver função)
        if (typeof mostrarLoading === 'function') {
            mostrarLoading('Salvando tramitação...');
        }
        
        // Envia requisição
        const response = await fetch(`${PORTAL_URL}/@@tramitacao_salvar`, {
            method: 'POST',
            body: formData instanceof FormData ? formData : new FormData(Object.entries(formData))
        });
        
        const data = await response.json();
        
        if (data.sucesso) {
            const codTramitacao = data.cod_tramitacao;
            
            // Processa resposta e inicia monitoramento se houver tasks
            processarRespostaSalvarTramitacao(data, codTramitacao);
            
            return data;
        } else {
            mostrarToast(data.mensagem || 'Erro ao salvar tramitação', 'error');
            throw new Error(data.mensagem || 'Erro ao salvar tramitação');
        }
    } catch (error) {
        console.error('Erro ao salvar tramitação:', error);
        mostrarToast('Erro ao salvar tramitação', 'error');
        throw error;
    } finally {
        // Esconde loading (se houver função)
        if (typeof esconderLoading === 'function') {
            esconderLoading();
        }
    }
}

/**
 * Exemplo de função para tramitar em lote (integração)
 * Esta função deve ser adaptada conforme a implementação real do sistema
 * 
 * @param {Array<number>} codTramitacoes - Lista de códigos de tramitações
 * @param {FormData|Object} formData - Dados adicionais do formulário
 * @returns {Promise<Object>} Resposta do servidor
 */
async function tramitarEmLoteExemplo(codTramitacoes, formData) {
    try {
        // Mostra loading (se houver função)
        if (typeof mostrarLoading === 'function') {
            mostrarLoading(`Tramitando ${codTramitacoes.length} tramitações...`);
        }
        
        // Prepara dados
        const dataToSend = formData instanceof FormData ? formData : new FormData();
        if (!(formData instanceof FormData)) {
            Object.entries(formData || {}).forEach(([key, value]) => {
                dataToSend.append(key, value);
            });
        }
        dataToSend.append('cod_tramitacoes', JSON.stringify(codTramitacoes));
        
        // Envia requisição
        const response = await fetch(`${PORTAL_URL}/@@tramitacao_lote_salvar`, {
            method: 'POST',
            body: dataToSend
        });
        
        const data = await response.json();
        
        if (data.sucesso) {
            // Processa resposta e inicia monitoramento se houver tasks
            processarRespostaTramitarEmLote(data, codTramitacoes);
            
            return data;
        } else {
            mostrarToast(data.mensagem || 'Erro ao tramitar em lote', 'error');
            throw new Error(data.mensagem || 'Erro ao tramitar em lote');
        }
    } catch (error) {
        console.error('Erro ao tramitar em lote:', error);
        mostrarToast('Erro ao tramitar em lote', 'error');
        throw error;
    } finally {
        // Esconde loading (se houver função)
        if (typeof esconderLoading === 'function') {
            esconderLoading();
        }
    }
}

// ============================================================================
// Funções para disparar geração de PDF/anexo manualmente (se necessário)
// ============================================================================

/**
 * Dispara geração de PDF para uma tramitação individual
 * 
 * @param {string} tipo - 'MATERIA' ou 'DOCUMENTO'
 * @param {number} codTramitacao - Código da tramitação
 * @param {boolean} gerarNovo - Se true, força geração de novo PDF
 * @returns {Promise<Object>} Resposta com task_id e monitor_url
 */
async function dispararGeracaoPDF(tipo, codTramitacao, gerarNovo = false) {
    try {
        const url = new URL(`${PORTAL_URL}/@@tramitacao_despacho_pdf`);
        url.searchParams.append('tipo', tipo);
        url.searchParams.append('cod_tramitacao', codTramitacao);
        if (gerarNovo) {
            url.searchParams.append('gerar_novo', 'true');
        }
        
        const response = await fetch(url.toString());
        const data = await response.json();
        
        if (data.task_id && data.monitor_url) {
            monitorarGeracaoPDF(data, codTramitacao);
            return data;
        } else if (data.erro) {
            mostrarToast('Erro ao gerar PDF: ' + data.erro, 'error');
            throw new Error(data.erro);
        } else {
            // PDF já existe ou não precisa gerar
            mostrarToast('PDF disponível', 'info');
            return data;
        }
    } catch (error) {
        console.error('Erro ao disparar geração de PDF:', error);
        mostrarToast('Erro ao gerar PDF', 'error');
        throw error;
    }
}

/**
 * Dispara junção de anexo para uma tramitação individual
 * 
 * @param {string} tipo - 'MATERIA' ou 'DOCUMENTO'
 * @param {number} codTramitacao - Código da tramitação
 * @param {File} arquivo - Arquivo PDF a ser anexado
 * @returns {Promise<Object>} Resposta com task_id e monitor_url
 */
async function dispararJuncaoAnexo(tipo, codTramitacao, arquivo) {
    try {
        if (!arquivo || !arquivo.name) {
            throw new Error('Arquivo não fornecido');
        }
        
        // Valida se é PDF
        if (!arquivo.name.toLowerCase().endsWith('.pdf')) {
            throw new Error('Apenas arquivos PDF são permitidos');
        }
        
        const formData = new FormData();
        formData.append('tipo', tipo);
        formData.append('cod_tramitacao', codTramitacao);
        formData.append('arquivo', arquivo);
        
        const response = await fetch(`${PORTAL_URL}/@@tramitacao_anexar_arquivo`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.task_id && data.monitor_url) {
            monitorarJuncaoAnexo(data, codTramitacao);
            return data;
        } else if (data.erro) {
            mostrarToast('Erro ao anexar arquivo: ' + data.erro, 'error');
            throw new Error(data.erro);
        } else {
            mostrarToast('Anexo processado', 'info');
            return data;
        }
    } catch (error) {
        console.error('Erro ao disparar junção de anexo:', error);
        mostrarToast('Erro ao anexar arquivo', 'error');
        throw error;
    }
}
