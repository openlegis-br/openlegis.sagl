-- Script para criar índices de performance para tramitação
-- Data: 2026-01-11
-- 
-- IMPORTANTE: Fazer backup do banco antes de executar
-- 
-- NOTA: Se algum índice já existir, o script irá falhar. Nesse caso,
-- execute DROP INDEX nome_indice ON nome_tabela antes de rodar este script.
-- 
-- Como executar:
-- mysql -u usuario -p nome_banco < criar_indices_performance.sql
-- 
-- Ou via MySQL client:
-- source /caminho/para/criar_indices_performance.sql

USE openlegis;

-- ============================================
-- ÍNDICES PARA CAIXA DE ENTRADA (MATÉRIAS)
-- ============================================

-- Índice composto para tramitações de matérias (unidades responsáveis)
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_entrada_materia_resp 
-- ON tramitacao (
--     cod_unid_tram_dest, 
--     ind_ult_tramitacao, 
--     dat_encaminha, 
--     dat_recebimento, 
--     ind_excluido
-- );

-- Índice para tramitações de matérias (unidades não responsáveis)
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_entrada_materia_nresp 
-- ON tramitacao (
--     cod_unid_tram_dest, 
--     cod_usuario_dest, 
--     ind_ult_tramitacao, 
--     dat_encaminha, 
--     dat_recebimento, 
--     ind_excluido
-- );

-- Índice para join com status_tramitacao
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_cod_status 
-- ON tramitacao (cod_status);

-- Índice para join com materia_legislativa
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_cod_materia 
-- ON tramitacao (cod_materia);

-- ============================================
-- ÍNDICES PARA CAIXA DE ENTRADA (DOCUMENTOS)
-- ============================================

-- Índice composto para tramitações administrativas (unidades responsáveis)
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_entrada_doc_resp 
-- ON tramitacao_administrativo (
--     cod_unid_tram_dest, 
--     ind_ult_tramitacao, 
--     dat_encaminha, 
--     dat_recebimento, 
--     ind_excluido
-- );

-- Índice para tramitações administrativas (unidades não responsáveis)
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_entrada_doc_nresp 
-- ON tramitacao_administrativo (
--     cod_unid_tram_dest, 
--     cod_usuario_dest, 
--     ind_ult_tramitacao, 
--     dat_encaminha, 
--     dat_recebimento, 
--     ind_excluido
-- );

-- Índice para join com status_tramitacao_administrativo
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_admin_cod_status 
-- ON tramitacao_administrativo (cod_status);

-- Índice para join com documento_administrativo
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_admin_cod_documento 
-- ON tramitacao_administrativo (cod_documento);

-- ============================================
-- ÍNDICES PARA RASCUNHOS
-- ============================================

-- Índice para rascunhos de matérias
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_rascunho_materia 
-- ON tramitacao (
--     cod_usuario_local, 
--     ind_ult_tramitacao, 
--     dat_encaminha, 
--     ind_excluido,
--     dat_tramitacao
-- );

-- Índice para rascunhos de documentos
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_rascunho_doc 
-- ON tramitacao_administrativo (
--     cod_usuario_local, 
--     ind_ult_tramitacao, 
--     dat_encaminha, 
--     ind_excluido,
--     dat_tramitacao
-- );

-- ============================================
-- ÍNDICES PARA ITENS ENVIADOS
-- ============================================

-- Índice para itens enviados de matérias
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_enviado_materia 
-- ON tramitacao (
--     cod_usuario_local, 
--     ind_ult_tramitacao, 
--     dat_encaminha, 
--     dat_recebimento, 
--     ind_excluido
-- );

-- Índice para itens enviados de documentos
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_tramitacao_enviado_doc 
-- ON tramitacao_administrativo (
--     cod_usuario_local, 
--     ind_ult_tramitacao, 
--     dat_encaminha, 
--     dat_recebimento, 
--     ind_excluido
-- );

-- ============================================
-- ÍNDICES PARA AUTORIA (BATCH LOADING)
-- ============================================

-- Índice para autoria (usado no batch loading)
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_autoria_materia 
-- ON autoria (cod_materia, ind_excluido);

-- Índice para join autoria -> autor
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_autoria_cod_autor 
-- ON autoria (cod_autor);

-- ============================================
-- ÍNDICES PARA OUTRAS TABELAS RELACIONADAS
-- ============================================

-- Índice para status_tramitacao (retorno)
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_status_tramitacao_retorno 
-- ON status_tramitacao (ind_retorno_tramitacao);

-- Índice para status_tramitacao_administrativo (retorno)
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_status_tramitacao_admin_retorno 
-- ON status_tramitacao_administrativo (ind_retorno_tramitacao);

-- Índice para materia_legislativa (tramitação e exclusão)
-- ÍNDICE JÁ EXISTE - comentado para evitar erro de duplicação
-- CREATE INDEX idx_materia_tramitacao 
-- ON materia_legislativa (ind_tramitacao, ind_excluido);

-- Índice para documento_administrativo (tramitação e exclusão)
CREATE INDEX idx_documento_tramitacao 
ON documento_administrativo (ind_tramitacao, ind_excluido);

-- Índice para usuario_unid_tram (usado para buscar unidades do usuário)
CREATE INDEX idx_usuario_unid_tram 
ON usuario_unid_tram (cod_usuario, ind_excluido, ind_responsavel);

-- ============================================
-- VERIFICAÇÃO
-- ============================================

-- Verificar índices criados
SHOW INDEX FROM tramitacao WHERE Key_name LIKE 'idx_%';
SHOW INDEX FROM tramitacao_administrativo WHERE Key_name LIKE 'idx_%';
SHOW INDEX FROM autoria WHERE Key_name LIKE 'idx_%';

-- Estatísticas das tabelas (ajuda o MySQL a escolher índices)
ANALYZE TABLE tramitacao;
ANALYZE TABLE tramitacao_administrativo;
ANALYZE TABLE autoria;
ANALYZE TABLE materia_legislativa;
ANALYZE TABLE documento_administrativo;
