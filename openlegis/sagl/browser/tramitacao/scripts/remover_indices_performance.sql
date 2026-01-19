-- Script para remover índices de performance para tramitação
-- Data: 2026-01-11
-- 
-- IMPORTANTE: Fazer backup do banco antes de executar
-- 
-- Este script remove todos os índices criados por criar_indices_performance.sql
-- Útil quando você precisa recriar os índices do zero
-- 
-- Como executar:
-- mysql -u usuario -p nome_banco < remover_indices_performance.sql
-- 
-- Ou via MySQL client:
-- source /caminho/para/remover_indices_performance.sql

USE openlegis;

-- ============================================
-- REMOVER ÍNDICES DA CAIXA DE ENTRADA (MATÉRIAS)
-- ============================================

DROP INDEX idx_tramitacao_entrada_materia_resp ON tramitacao;
DROP INDEX idx_tramitacao_entrada_materia_nresp ON tramitacao;
DROP INDEX idx_tramitacao_cod_status ON tramitacao;
DROP INDEX idx_tramitacao_cod_materia ON tramitacao;

-- ============================================
-- REMOVER ÍNDICES DA CAIXA DE ENTRADA (DOCUMENTOS)
-- ============================================

DROP INDEX idx_tramitacao_entrada_doc_resp ON tramitacao_administrativo;
DROP INDEX idx_tramitacao_entrada_doc_nresp ON tramitacao_administrativo;
DROP INDEX idx_tramitacao_admin_cod_status ON tramitacao_administrativo;
DROP INDEX idx_tramitacao_admin_cod_documento ON tramitacao_administrativo;

-- ============================================
-- REMOVER ÍNDICES DE RASCUNHOS
-- ============================================

DROP INDEX idx_tramitacao_rascunho_materia ON tramitacao;
DROP INDEX idx_tramitacao_rascunho_doc ON tramitacao_administrativo;

-- ============================================
-- REMOVER ÍNDICES DE ITENS ENVIADOS
-- ============================================

DROP INDEX idx_tramitacao_enviado_materia ON tramitacao;
DROP INDEX idx_tramitacao_enviado_doc ON tramitacao_administrativo;

-- ============================================
-- REMOVER ÍNDICES DE AUTORIA (BATCH LOADING)
-- ============================================

DROP INDEX idx_autoria_materia ON autoria;
DROP INDEX idx_autoria_cod_autor ON autoria;

-- ============================================
-- REMOVER ÍNDICES DE OUTRAS TABELAS RELACIONADAS
-- ============================================

DROP INDEX idx_status_tramitacao_retorno ON status_tramitacao;
DROP INDEX idx_status_tramitacao_admin_retorno ON status_tramitacao_administrativo;
DROP INDEX idx_materia_tramitacao ON materia_legislativa;
DROP INDEX idx_documento_tramitacao ON documento_administrativo;
DROP INDEX idx_usuario_unid_tram ON usuario_unid_tram;
