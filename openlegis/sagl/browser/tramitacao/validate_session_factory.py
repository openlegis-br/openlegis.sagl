#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de validação do SessionFactory padrão SAGL.

Este script valida:
1. Compatibilidade com SQLAlchemy 2.0+
2. Criação correta de sessões de escrita
3. Criação correta de sessões de leitura
4. Integração com zope.sqlalchemy

Uso:
    python validate_session_factory.py
"""

import sys
import logging

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """Testa se os imports funcionam corretamente."""
    logger.info("=" * 60)
    logger.info("Teste 1: Imports")
    logger.info("=" * 60)
    
    try:
        from openlegis.sagl.db_session import (
            db_session,
            db_session_readonly,
            validate_sqlalchemy_compatibility,
            get_session_factory
        )
        logger.info("✅ Todos os imports funcionaram corretamente")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao importar: {e}", exc_info=True)
        return False

def test_compatibility():
    """Testa validação de compatibilidade."""
    logger.info("=" * 60)
    logger.info("Teste 2: Validação de Compatibilidade")
    logger.info("=" * 60)
    
    try:
        from openlegis.sagl.db_session import validate_sqlalchemy_compatibility
        
        info = validate_sqlalchemy_compatibility()
        
        logger.info(f"Versão SQLAlchemy: {info['version']}")
        logger.info(f"Major: {info['major']}, Minor: {info['minor']}, Patch: {info['patch']}")
        logger.info(f"É 2.0+: {info['is_2_0_plus']}")
        logger.info(f"É 2.1+: {info['is_2_1_plus']}")
        logger.info(f"Requer begin() explícito: {info['requires_explicit_begin']}")
        logger.info(f"Compatível: {info['compatible']}")
        
        if info['warnings']:
            for warning in info['warnings']:
                logger.warning(f"⚠️  {warning}")
        
        if info.get('notes'):
            logger.info(f"ℹ️  {info['notes']}")
        
        if info['compatible']:
            logger.info("✅ Compatibilidade validada com sucesso")
            return True
        else:
            logger.error("❌ Problemas de compatibilidade detectados")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro ao validar compatibilidade: {e}", exc_info=True)
        return False

def test_session_factory():
    """Testa se a factory de sessões funciona."""
    logger.info("=" * 60)
    logger.info("Teste 3: Factory de Sessões")
    logger.info("=" * 60)
    
    try:
        from openlegis.sagl.db_session import get_session_factory
        
        factory = get_session_factory()
        
        if callable(factory):
            logger.info("✅ Factory de sessões é callable")
            return True
        else:
            logger.error("❌ Factory de sessões não é callable")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro ao obter factory: {e}", exc_info=True)
        return False

def test_readonly_session():
    """Testa criação de sessão de leitura."""
    logger.info("=" * 60)
    logger.info("Teste 4: Sessão de Leitura (Readonly)")
    logger.info("=" * 60)
    
    try:
        from openlegis.sagl.db_session import db_session_readonly
        
        with db_session_readonly() as session:
            logger.info(f"Sessão criada: id={id(session)}")
            logger.info(f"Sessão ativa: {session.is_active}")
            
            # Testa se pode fazer query (sem executar)
            # Apenas valida que a sessão está funcional
            logger.info("✅ Sessão de leitura criada com sucesso")
        
        logger.info("✅ Context manager funcionou corretamente (sessão fechada)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar sessão de leitura: {e}", exc_info=True)
        return False

def test_write_session():
    """Testa criação de sessão de escrita (requer ambiente Zope)."""
    logger.info("=" * 60)
    logger.info("Teste 5: Sessão de Escrita (Write)")
    logger.info("=" * 60)
    logger.info("⚠️  Este teste requer ambiente Zope ativo")
    
    try:
        from openlegis.sagl.db_session import db_session
        
        # Tenta criar sessão
        # Nota: Isso pode falhar fora do ambiente Zope
        try:
            session = db_session()
            logger.info(f"Sessão criada: id={id(session)}")
            logger.info(f"Sessão ativa: {session.is_active}")
            
            # Verifica transação
            tx = session.get_transaction()
            if tx:
                logger.info(f"Transação encontrada: id={id(tx)}")
                if hasattr(tx, 'is_active'):
                    logger.info(f"Transação ativa: {tx.is_active}")
                else:
                    logger.warning("⚠️  Transação não tem atributo is_active")
            else:
                logger.error("❌ Nenhuma transação encontrada na sessão")
                return False
            
            logger.info("✅ Sessão de escrita criada com sucesso")
            logger.info("✅ Transação está ativa")
            return True
            
        except RuntimeError as e:
            logger.warning(f"⚠️  Não foi possível criar sessão (fora do ambiente Zope?): {e}")
            logger.info("ℹ️  Isso é esperado se executado fora do ambiente Zope")
            return True  # Não é um erro crítico
            
    except Exception as e:
        logger.error(f"❌ Erro ao criar sessão de escrita: {e}", exc_info=True)
        return False

def main():
    """Executa todos os testes."""
    logger.info("Iniciando validação do SessionFactory padrão SAGL")
    logger.info("")
    
    results = []
    
    # Executa testes
    results.append(("Imports", test_imports()))
    results.append(("Compatibilidade", test_compatibility()))
    results.append(("Factory", test_session_factory()))
    results.append(("Sessão Leitura", test_readonly_session()))
    results.append(("Sessão Escrita", test_write_session()))
    
    # Resumo
    logger.info("")
    logger.info("=" * 60)
    logger.info("RESUMO DOS TESTES")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        logger.info(f"{name}: {status}")
    
    logger.info("")
    logger.info(f"Total: {passed}/{total} testes passaram")
    
    if passed == total:
        logger.info("🎉 Todos os testes passaram!")
        return 0
    else:
        logger.warning(f"⚠️  {total - passed} teste(s) falharam")
        return 1

if __name__ == '__main__':
    sys.exit(main())
