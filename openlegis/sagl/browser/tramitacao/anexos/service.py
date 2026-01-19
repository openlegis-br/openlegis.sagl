# -*- coding: utf-8 -*-
"""Serviço para gerenciar anexos de tramitação usando SQLAlchemy"""

from typing import Optional
from io import BytesIO
from sqlalchemy.orm import Session
import pymupdf
import logging

from openlegis.sagl.models.models import Tramitacao, TramitacaoAdministrativo

logger = logging.getLogger(__name__)


class FileValidationError(Exception):
    """Exceção para erros de validação de arquivo"""
    pass


class TramitacaoAnexoService:
    """Gerencia anexos de tramitação"""
    
    # Tamanho máximo: 10MB
    TAMANHO_MAXIMO = 10 * 1024 * 1024
    
    def __init__(self, session: Session, contexto_zope=None):
        """
        Args:
            session: Sessão SQLAlchemy
            contexto_zope: Contexto Zope para acessar repositório de arquivos
        """
        self.session = session
        self.contexto_zope = contexto_zope
    
    def verificar_tramitacao_existe(
        self,
        tipo: str,
        cod_tramitacao: int
    ) -> bool:
        """Verifica se tramitação existe"""
        if tipo == 'MATERIA':
            tram = self.session.query(Tramitacao).filter(
                Tramitacao.cod_tramitacao == cod_tramitacao,
                Tramitacao.ind_excluido == 0
            ).first()
        else:
            tram = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                TramitacaoAdministrativo.ind_excluido == 0
            ).first()
        
        return tram is not None
    
    def anexar_e_juntar_pdf(
        self,
        tipo: str,
        cod_tramitacao: int,
        arquivo_pdf: BytesIO,
        nome_arquivo: str
    ) -> bool:
        """
        Anexa PDF e junta ao PDF principal da tramitação
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            arquivo_pdf: BytesIO com conteúdo do PDF
            nome_arquivo: Nome original do arquivo
            
        Returns:
            True se sucesso
            
        Raises:
            FileValidationError: Se validação falhar
            ValueError: Se tramitação não existir
        """
        # Valida que tramitação existe
        if not self.verificar_tramitacao_existe(tipo, cod_tramitacao):
            raise ValueError(f"Tramitação {cod_tramitacao} não encontrada")
        
        # Valida que é PDF
        arquivo_pdf.seek(0)
        try:
            # Tenta abrir com PyMuPDF para validar
            pdf_doc = pymupdf.open(stream=arquivo_pdf)
            pdf_doc.close()
            arquivo_pdf.seek(0)
        except Exception as e:
            raise FileValidationError(f"Arquivo não é um PDF válido: {e}")
        
        # Valida tamanho
        arquivo_pdf.seek(0, 2)  # Vai para o fim
        tamanho = arquivo_pdf.tell()
        arquivo_pdf.seek(0)
        
        if tamanho > self.TAMANHO_MAXIMO:
            raise FileValidationError(f"Arquivo muito grande. Tamanho máximo: {self.TAMANHO_MAXIMO / (1024*1024)}MB")
        
        if not self.contexto_zope:
            raise ValueError("Contexto Zope necessário para salvar arquivos")
        
        # Nome do arquivo anexo (temporário)
        anexo_filename = f"{cod_tramitacao}_tram_anexo1.pdf"
        
        # Repositório
        if tipo == 'MATERIA':
            repo = self.contexto_zope.sapl_documentos.materia.tramitacao
        else:
            repo = self.contexto_zope.sapl_documentos.administrativo.tramitacao
        
        # Remove anexo anterior se existir
        if hasattr(repo, anexo_filename):
            repo.manage_delObjects([anexo_filename])
        
        # Salva anexo temporário
        arquivo_pdf.seek(0)
        repo.manage_addFile(
            id=anexo_filename,
            file=arquivo_pdf.read(),
            content_type='application/pdf',
            title=f'Anexo da tramitação {cod_tramitacao}'
        )
        
        # Junta PDFs usando PyMuPDF diretamente
        try:
            self._juntar_pdfs(tipo, cod_tramitacao, repo, anexo_filename)
            
            # Configura permissões se documento for público (apenas para documentos administrativos)
            if tipo == 'DOCUMENTO':
                self._configurar_permissoes_publico(cod_tramitacao, repo)
            
            return True
        except Exception as e:
            logger.error(f"Erro ao juntar PDF: {e}", exc_info=True)
            # Remove anexo temporário em caso de erro
            try:
                if hasattr(repo, anexo_filename):
                    repo.manage_delObjects([anexo_filename])
            except Exception:
                pass
            raise
    
    def _juntar_pdfs(
        self,
        tipo: str,
        cod_tramitacao: int,
        repo,
        anexo_filename: str
    ) -> None:
        """
        Junta PDF principal com anexo usando PyMuPDF
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            repo: Repositório Zope (materia.tramitacao ou administrativo.tramitacao)
            anexo_filename: Nome do arquivo anexo temporário
        """
        base_filename = f"{cod_tramitacao}_tram.pdf"
        
        # Verifica se PDF principal existe
        if not hasattr(repo, base_filename):
            raise ValueError(f"PDF principal {base_filename} não encontrado")
        
        # Cria merger PyMuPDF
        merger = pymupdf.open()
        
        try:
            # Lista de arquivos para juntar (principal primeiro, depois anexo)
            filenames = [base_filename, anexo_filename]
            
            for filename in filenames:
                if not hasattr(repo, filename):
                    logger.warning(f"Arquivo {filename} não encontrado, pulando...")
                    continue
                
                # Obtém arquivo do repositório
                arq = getattr(repo, filename)
                if not hasattr(arq, 'data'):
                    logger.warning(f"Arquivo {filename} não possui atributo 'data', pulando...")
                    continue
                
                # Converte para BytesIO
                arquivo = BytesIO(bytes(arq.data))
                arquivo.seek(0)
                
                # Abre PDF com PyMuPDF
                try:
                    pdf_doc = pymupdf.open(stream=arquivo)
                    logger.debug(f"Arquivo {filename} aberto - Páginas: {pdf_doc.page_count}")
                    # Bake garante que o PDF está processado corretamente
                    pdf_doc.bake()
                    merger.insert_pdf(pdf_doc)
                    pdf_doc.close()
                    logger.debug(f"Arquivo {filename} inserido no merger")
                except Exception as e:
                    logger.error(f"Falha ao processar arquivo {filename} com PyMuPDF: {e}")
                    raise
            
            # Salva PDF mesclado
            output_stream = BytesIO()
            merger.save(output_stream)
            output_stream.seek(0)
            content = output_stream.getvalue()
            logger.debug(f"PDF mesclado gerado - Tamanho: {len(content)} bytes")
            
            # Atualiza arquivo principal no repositório
            pdf_principal = getattr(repo, base_filename)
            pdf_principal.update_data(content)
            logger.info(f"PDF mesclado atualizado: {base_filename}")
            
        finally:
            merger.close()
            
            # Remove anexo temporário após junção bem-sucedida
            try:
                if hasattr(repo, anexo_filename):
                    repo.manage_delObjects([anexo_filename])
                    logger.debug(f"Anexo temporário {anexo_filename} removido")
            except Exception as e:
                logger.warning(f"Falha ao remover anexo temporário: {e}")
    
    def _configurar_permissoes_publico(
        self,
        cod_tramitacao: int,
        repo
    ) -> None:
        """
        Configura permissões de visualização para documento público
        
        Args:
            cod_tramitacao: Código da tramitação
            repo: Repositório Zope (administrativo.tramitacao)
        """
        try:
            # Verifica se documento é público usando SQLAlchemy
            from openlegis.sagl.models.models import TramitacaoAdministrativo, DocumentoAdministrativo
            
            tram = self.session.query(TramitacaoAdministrativo).filter(
                TramitacaoAdministrativo.cod_tramitacao == cod_tramitacao,
                TramitacaoAdministrativo.ind_excluido == 0
            ).first()
            
            if not tram:
                return
            
            doc = self.session.query(DocumentoAdministrativo).filter(
                DocumentoAdministrativo.cod_documento == tram.cod_documento,
                DocumentoAdministrativo.ind_excluido == 0
            ).first()
            
            # Verifica se é público (ajustar conforme modelo real)
            # Exemplo: if doc and doc.ind_publico == 1:
            if doc and hasattr(doc, 'ind_publico') and doc.ind_publico:
                pdf_filename = f"{cod_tramitacao}_tram.pdf"
                if hasattr(repo, pdf_filename):
                    pdf_obj = getattr(repo, pdf_filename)
                    pdf_obj.manage_permission(
                        'View',
                        roles=['Manager', 'Authenticated', 'Anonymous'],
                        acquire=1
                    )
                    logger.debug(f"Permissões públicas configuradas para {pdf_filename}")
        except Exception as e:
            logger.warning(f"Erro ao configurar permissões públicas: {e}")
    
    def obter_pdf_tramitacao(
        self,
        tipo: str,
        cod_tramitacao: int
    ) -> Optional[BytesIO]:
        """
        Obtém PDF da tramitação (com anexos já juntados)
        
        Args:
            tipo: 'MATERIA' ou 'DOCUMENTO'
            cod_tramitacao: Código da tramitação
            
        Returns:
            BytesIO com PDF ou None se não encontrado
        """
        if not self.contexto_zope:
            return None
        
        pdf_filename = f"{cod_tramitacao}_tram.pdf"
        
        if tipo == 'MATERIA':
            repo = self.contexto_zope.sapl_documentos.materia.tramitacao
        else:
            repo = self.contexto_zope.sapl_documentos.administrativo.tramitacao
        
        if not hasattr(repo, pdf_filename):
            return None
        
        pdf_obj = getattr(repo, pdf_filename)
        return BytesIO(bytes(pdf_obj.data))
