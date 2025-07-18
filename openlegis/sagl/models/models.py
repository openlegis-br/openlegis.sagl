from typing import List, Optional

from sqlalchemy import Column, DECIMAL, Date, DateTime, ForeignKeyConstraint, Index, Integer, TIMESTAMP, Time, text
from sqlalchemy.dialects.mysql import CHAR, INTEGER, LONGTEXT, MEDIUMTEXT, TEXT, TINYINT, TINYTEXT, VARCHAR
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship
from sqlalchemy.orm.base import Mapped

Base = declarative_base()


class AcompMateria(Base):
    __tablename__ = 'acomp_materia'
    __table_args__ = (
        Index('cod_materia', 'cod_materia'),
        Index('fk_{CCECA63D-5992-437B-BCD3-D7C98DA3E926}', 'cod_materia', 'end_email', unique=True)
    )

    cod_cadastro = mapped_column(Integer, primary_key=True)
    cod_materia = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    end_email = mapped_column(VARCHAR(100))
    txt_hash = mapped_column(VARCHAR(8))


class ArquivoArmario(Base):
    __tablename__ = 'arquivo_armario'
    __table_args__ = (
        Index('cod_corredor', 'cod_corredor'),
        Index('cod_unidade', 'cod_unidade')
    )

    cod_armario = mapped_column(Integer, primary_key=True)
    cod_unidade = mapped_column(Integer, nullable=False)
    nom_armario = mapped_column(VARCHAR(80), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_corredor = mapped_column(Integer)
    txt_observacao = mapped_column(TEXT)


class ArquivoCorredor(Base):
    __tablename__ = 'arquivo_corredor'
    __table_args__ = (
        Index('cod_unidade', 'cod_unidade'),
    )

    cod_corredor = mapped_column(Integer, primary_key=True)
    cod_unidade = mapped_column(Integer, nullable=False)
    nom_corredor = mapped_column(VARCHAR(80), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    txt_observacao = mapped_column(TEXT)


class ArquivoItem(Base):
    __tablename__ = 'arquivo_item'
    __table_args__ = (
        Index('cod_documento', 'cod_documento'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_norma', 'cod_norma'),
        Index('cod_protocolo', 'cod_protocolo'),
        Index('cod_recipiente', 'cod_recipiente'),
        Index('tip_suporte', 'tip_suporte')
    )

    cod_item = mapped_column(Integer, primary_key=True)
    cod_recipiente = mapped_column(Integer, nullable=False)
    tip_suporte = mapped_column(Integer, nullable=False)
    dat_arquivamento = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_materia = mapped_column(Integer)
    cod_norma = mapped_column(Integer)
    cod_documento = mapped_column(Integer)
    cod_protocolo = mapped_column(INTEGER(7))
    des_item = mapped_column(TEXT)
    txt_observacao = mapped_column(TEXT)


class ArquivoPrateleira(Base):
    __tablename__ = 'arquivo_prateleira'
    __table_args__ = (
        Index('cod_armario', 'cod_armario'),
        Index('cod_corredor', 'cod_corredor'),
        Index('cod_unidade', 'cod_unidade')
    )

    cod_prateleira = mapped_column(Integer, primary_key=True)
    cod_unidade = mapped_column(Integer, nullable=False)
    nom_prateleira = mapped_column(VARCHAR(80), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_armario = mapped_column(Integer)
    cod_corredor = mapped_column(Integer)
    txt_observacao = mapped_column(TEXT)


class ArquivoRecipiente(Base):
    __tablename__ = 'arquivo_recipiente'
    __table_args__ = (
        Index('num_tipo_recipiente', 'num_recipiente', 'tip_recipiente', 'ano_recipiente', 'ind_excluido', unique=True),
        Index('tip_recipiente', 'tip_recipiente'),
        Index('tip_tit_documental', 'tip_tit_documental')
    )

    cod_recipiente = mapped_column(Integer, primary_key=True)
    tip_recipiente = mapped_column(Integer, nullable=False)
    num_recipiente = mapped_column(VARCHAR(11), nullable=False)
    tip_tit_documental = mapped_column(Integer, nullable=False)
    ano_recipiente = mapped_column(Integer, nullable=False)
    dat_recipiente = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_corredor = mapped_column(Integer)
    cod_armario = mapped_column(Integer)
    cod_prateleira = mapped_column(Integer)
    txt_observacao = mapped_column(TEXT)
    num_folha_recipiente = mapped_column(VARCHAR(10))


class ArquivoTipoRecipiente(Base):
    __tablename__ = 'arquivo_tipo_recipiente'

    tip_recipiente = mapped_column(Integer, primary_key=True)
    des_tipo_recipiente = mapped_column(VARCHAR(50), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)


class ArquivoTipoSuporte(Base):
    __tablename__ = 'arquivo_tipo_suporte'

    tip_suporte = mapped_column(Integer, primary_key=True)
    des_tipo_suporte = mapped_column(VARCHAR(50), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)


class ArquivoTipoTitDocumental(Base):
    __tablename__ = 'arquivo_tipo_tit_documental'

    tip_tit_documental = mapped_column(Integer, primary_key=True)
    sgl_tip_tit_documental = mapped_column(VARCHAR(3), nullable=False)
    des_tipo_tit_documental = mapped_column(VARCHAR(50), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)


class ArquivoUnidade(Base):
    __tablename__ = 'arquivo_unidade'

    cod_unidade = mapped_column(Integer, primary_key=True)
    tip_extensao_atuacao = mapped_column(Integer, nullable=False)
    tip_estagio_evolucao = mapped_column(Integer, nullable=False)
    nom_unidade = mapped_column(VARCHAR(200), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    txt_localizacao = mapped_column(VARCHAR(200))
    txt_observacao = mapped_column(TEXT)


class AssinaturaStorage(Base):
    __tablename__ = 'assinatura_storage'
    __table_args__ = (
        Index('tip_documento', 'tip_documento'),
    )

    id = mapped_column(Integer, primary_key=True)
    tip_documento = mapped_column(VARCHAR(20), nullable=False)
    pdf_location = mapped_column(VARCHAR(50), nullable=False)
    storage_path = mapped_column(VARCHAR(50), nullable=False)
    pdf_file = mapped_column(VARCHAR(50), nullable=False)
    pdf_signed = mapped_column(VARCHAR(50), nullable=False)


class AssuntoMateria(Base):
    __tablename__ = 'assunto_materia'

    cod_assunto = mapped_column(Integer, primary_key=True)
    des_assunto = mapped_column(VARCHAR(50), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    des_estendida = mapped_column(VARCHAR(250))


class AssuntoNorma(Base):
    __tablename__ = 'assunto_norma'

    cod_assunto = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    des_assunto = mapped_column(VARCHAR(50))
    des_estendida = mapped_column(VARCHAR(250))


class CargoBancada(Base):
    __tablename__ = 'cargo_bancada'

    cod_cargo = mapped_column(Integer, primary_key=True)
    ind_unico = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    des_cargo = mapped_column(VARCHAR(50))

    composicao_bancada: Mapped[List['ComposicaoBancada']] = relationship('ComposicaoBancada', uselist=True, back_populates='cargo_bancada')


class CargoComissao(Base):
    __tablename__ = 'cargo_comissao'

    cod_cargo = mapped_column(Integer, primary_key=True)
    ind_unico = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    des_cargo = mapped_column(VARCHAR(50))

    composicao_comissao: Mapped[List['ComposicaoComissao']] = relationship('ComposicaoComissao', uselist=True, back_populates='cargo_comissao')


class CargoExecutivo(Base):
    __tablename__ = 'cargo_executivo'

    cod_cargo = mapped_column(TINYINT, primary_key=True)
    des_cargo = mapped_column(VARCHAR(50), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))

    composicao_executivo: Mapped[List['ComposicaoExecutivo']] = relationship('ComposicaoExecutivo', uselist=True, back_populates='cargo_executivo')


class CargoMesa(Base):
    __tablename__ = 'cargo_mesa'

    cod_cargo = mapped_column(Integer, primary_key=True)
    ind_unico = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    des_cargo = mapped_column(VARCHAR(50))

    composicao_mesa: Mapped[List['ComposicaoMesa']] = relationship('ComposicaoMesa', uselist=True, back_populates='cargo_mesa')
    mesa_sessao_plenaria: Mapped[List['MesaSessaoPlenaria']] = relationship('MesaSessaoPlenaria', uselist=True, back_populates='cargo_mesa')


class CategoriaInstituicao(Base):
    __tablename__ = 'categoria_instituicao'
    __table_args__ = (
        Index('tip_instituicao', 'tip_instituicao'),
    )

    tip_instituicao = mapped_column(Integer, primary_key=True, nullable=False)
    cod_categoria = mapped_column(Integer, primary_key=True, nullable=False)
    des_categoria = mapped_column(VARCHAR(80), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))


class Legislatura(Base):
    __tablename__ = 'legislatura'
    __table_args__ = (
        Index('idx_legislatura_datas', 'dat_inicio', 'dat_fim', 'dat_eleicao', 'ind_excluido'),
        Index('num_legislatura', 'num_legislatura', unique=True),
        Index('num_legislatura_2', 'num_legislatura')
    )

    id = mapped_column(Integer, primary_key=True)
    num_legislatura = mapped_column(Integer, nullable=False)
    dat_inicio = mapped_column(Date, nullable=False)
    dat_fim = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_eleicao = mapped_column(Date)

    bancada: Mapped[List['Bancada']] = relationship('Bancada', uselist=True, back_populates='legislatura')
    coligacao: Mapped[List['Coligacao']] = relationship('Coligacao', uselist=True, back_populates='legislatura')
    composicao_executivo: Mapped[List['ComposicaoExecutivo']] = relationship('ComposicaoExecutivo', uselist=True, back_populates='legislatura')
    periodo_comp_bancada: Mapped[List['PeriodoCompBancada']] = relationship('PeriodoCompBancada', uselist=True, back_populates='legislatura')
    periodo_comp_mesa: Mapped[List['PeriodoCompMesa']] = relationship('PeriodoCompMesa', uselist=True, back_populates='legislatura')
    sessao_legislativa: Mapped[List['SessaoLegislativa']] = relationship('SessaoLegislativa', uselist=True, back_populates='legislatura')
    mandato: Mapped[List['Mandato']] = relationship('Mandato', uselist=True, back_populates='legislatura')
    periodo_sessao: Mapped[List['PeriodoSessao']] = relationship('PeriodoSessao', uselist=True, back_populates='legislatura')
    afastamento: Mapped[List['Afastamento']] = relationship('Afastamento', uselist=True, back_populates='legislatura')
    sessao_plenaria: Mapped[List['SessaoPlenaria']] = relationship('SessaoPlenaria', uselist=True, back_populates='legislatura')


class LexmlRegistroProvedor(Base):
    __tablename__ = 'lexml_registro_provedor'

    cod_provedor = mapped_column(Integer, primary_key=True)
    id_provedor = mapped_column(Integer, nullable=False)
    nom_provedor = mapped_column(VARCHAR(255))
    sgl_provedor = mapped_column(VARCHAR(15))
    adm_email = mapped_column(VARCHAR(50))
    nom_responsavel = mapped_column(VARCHAR(255))
    tipo = mapped_column(VARCHAR(50))
    id_responsavel = mapped_column(Integer)
    xml_provedor = mapped_column(LONGTEXT)


class LexmlRegistroPublicador(Base):
    __tablename__ = 'lexml_registro_publicador'

    cod_publicador = mapped_column(Integer, primary_key=True)
    id_publicador = mapped_column(Integer, nullable=False)
    id_responsavel = mapped_column(Integer, nullable=False)
    nom_publicador = mapped_column(VARCHAR(255))
    adm_email = mapped_column(VARCHAR(50))
    sigla = mapped_column(VARCHAR(255))
    nom_responsavel = mapped_column(VARCHAR(255))
    tipo = mapped_column(VARCHAR(50))


class Localidade(Base):
    __tablename__ = 'localidade'
    __table_args__ = (
        Index('nom_localidade', 'nom_localidade'),
        Index('nom_localidade_pesq', 'nom_localidade_pesq'),
        Index('sgl_uf', 'sgl_uf'),
        Index('tip_localidade', 'tip_localidade')
    )

    cod_localidade = mapped_column(Integer, primary_key=True, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    nom_localidade = mapped_column(VARCHAR(50))
    nom_localidade_pesq = mapped_column(VARCHAR(50))
    tip_localidade = mapped_column(CHAR(1))
    sgl_uf = mapped_column(CHAR(2))
    sgl_regiao = mapped_column(CHAR(2))

    instituicao: Mapped[List['Instituicao']] = relationship('Instituicao', uselist=True, back_populates='localidade')
    parlamentar: Mapped[List['Parlamentar']] = relationship('Parlamentar', uselist=True, back_populates='localidade')
    usuario: Mapped[List['Usuario']] = relationship('Usuario', uselist=True, back_populates='localidade')
    logradouro: Mapped[List['Logradouro']] = relationship('Logradouro', uselist=True, back_populates='localidade')


class NivelInstrucao(Base):
    __tablename__ = 'nivel_instrucao'

    cod_nivel_instrucao = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    des_nivel_instrucao = mapped_column(VARCHAR(50))

    parlamentar: Mapped[List['Parlamentar']] = relationship('Parlamentar', uselist=True, back_populates='nivel_instrucao')


class Orgao(Base):
    __tablename__ = 'orgao'

    cod_orgao = mapped_column(Integer, primary_key=True)
    nom_orgao = mapped_column(VARCHAR(100), nullable=False)
    ind_unid_deliberativa = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    sgl_orgao = mapped_column(VARCHAR(10))
    end_orgao = mapped_column(VARCHAR(100))
    num_tel_orgao = mapped_column(VARCHAR(50))
    end_email = mapped_column(VARCHAR(100))

    unidade_tramitacao: Mapped[List['UnidadeTramitacao']] = relationship('UnidadeTramitacao', uselist=True, back_populates='orgao')


class Origem(Base):
    __tablename__ = 'origem'

    cod_origem = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    sgl_origem = mapped_column(VARCHAR(10))
    nom_origem = mapped_column(VARCHAR(50))

    materia_legislativa: Mapped[List['MateriaLegislativa']] = relationship('MateriaLegislativa', uselist=True, back_populates='origem')


class Partido(Base):
    __tablename__ = 'partido'

    cod_partido = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    sgl_partido = mapped_column(VARCHAR(30))
    nom_partido = mapped_column(VARCHAR(50))
    dat_criacao = mapped_column(Date)
    dat_extincao = mapped_column(Date)

    bancada: Mapped[List['Bancada']] = relationship('Bancada', uselist=True, back_populates='partido')
    composicao_coligacao: Mapped[List['ComposicaoColigacao']] = relationship('ComposicaoColigacao', uselist=True, back_populates='partido')
    composicao_executivo: Mapped[List['ComposicaoExecutivo']] = relationship('ComposicaoExecutivo', uselist=True, back_populates='partido')
    autor: Mapped[List['Autor']] = relationship('Autor', uselist=True, back_populates='partido')
    filiacao: Mapped[List['Filiacao']] = relationship('Filiacao', uselist=True, back_populates='partido')
    liderancas_partidarias: Mapped[List['LiderancasPartidarias']] = relationship('LiderancasPartidarias', uselist=True, back_populates='partido')


class PeriodoCompComissao(Base):
    __tablename__ = 'periodo_comp_comissao'
    __table_args__ = (
        Index('ind_percompcom_datas', 'dat_inicio_periodo', 'dat_fim_periodo', 'ind_excluido'),
    )

    cod_periodo_comp = mapped_column(Integer, primary_key=True)
    dat_inicio_periodo = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_fim_periodo = mapped_column(Date)

    composicao_comissao: Mapped[List['ComposicaoComissao']] = relationship('ComposicaoComissao', uselist=True, back_populates='periodo_comp_comissao')


class Pessoa(Base):
    __tablename__ = 'pessoa'
    __table_args__ = (
        Index('cod_logradouro', 'cod_logradouro'),
        Index('dat_nascimento', 'dat_nascimento'),
        Index('des_estado_civil', 'des_estado_civil'),
        Index('des_profissao', 'des_profissao'),
        Index('doc_identidade', 'doc_identidade'),
        Index('end_residencial', 'end_residencial'),
        Index('idx_busca', 'doc_identidade'),
        Index('nom_bairro', 'nom_bairro'),
        Index('nom_cidade', 'nom_cidade'),
        Index('nom_conjuge', 'nom_conjuge'),
        Index('nom_pessoa', 'nom_pessoa'),
        Index('num_cep', 'num_cep'),
        Index('sex_visitante', 'sex_pessoa')
    )

    cod_pessoa = mapped_column(Integer, primary_key=True)
    nom_pessoa = mapped_column(VARCHAR(255), nullable=False)
    doc_identidade = mapped_column(VARCHAR(50), nullable=False)
    end_residencial = mapped_column(VARCHAR(255), nullable=False)
    num_imovel = mapped_column(VARCHAR(10), nullable=False)
    nom_bairro = mapped_column(VARCHAR(50), nullable=False)
    num_cep = mapped_column(VARCHAR(15), nullable=False)
    nom_cidade = mapped_column(VARCHAR(50), nullable=False)
    dat_atualizacao = mapped_column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_nascimento = mapped_column(Date)
    sex_pessoa = mapped_column(CHAR(1))
    des_estado_civil = mapped_column(VARCHAR(15))
    nom_conjuge = mapped_column(VARCHAR(50))
    num_dependentes = mapped_column(TINYTEXT)
    num_tit_eleitor = mapped_column(VARCHAR(15))
    cod_logradouro = mapped_column(Integer)
    txt_complemento = mapped_column(VARCHAR(50))
    sgl_uf = mapped_column(VARCHAR(2))
    des_tempo_residencia = mapped_column(VARCHAR(25))
    num_telefone = mapped_column(VARCHAR(40))
    num_celular = mapped_column(VARCHAR(20))
    end_email = mapped_column(VARCHAR(100))
    des_profissao = mapped_column(VARCHAR(50))
    des_local_trabalho = mapped_column(VARCHAR(100))
    txt_observacao = mapped_column(TEXT)

    visita: Mapped[List['Visita']] = relationship('Visita', uselist=True, back_populates='pessoa')


class QuorumVotacao(Base):
    __tablename__ = 'quorum_votacao'

    cod_quorum = mapped_column(Integer, primary_key=True)
    des_quorum = mapped_column(VARCHAR(50), nullable=False)
    txt_formula = mapped_column(VARCHAR(30), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    materia_legislativa: Mapped[List['MateriaLegislativa']] = relationship('MateriaLegislativa', uselist=True, back_populates='quorum_votacao')
    expediente_materia: Mapped[List['ExpedienteMateria']] = relationship('ExpedienteMateria', uselist=True, back_populates='quorum_votacao')
    ordem_dia: Mapped[List['OrdemDia']] = relationship('OrdemDia', uselist=True, back_populates='quorum_votacao')


class RegimeTramitacao(Base):
    __tablename__ = 'regime_tramitacao'

    cod_regime_tramitacao = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    des_regime_tramitacao = mapped_column(VARCHAR(50))

    materia_legislativa: Mapped[List['MateriaLegislativa']] = relationship('MateriaLegislativa', uselist=True, back_populates='regime_tramitacao')


class StatusTramitacao(Base):
    __tablename__ = 'status_tramitacao'
    __table_args__ = (
        Index('des_status', 'des_status'),
        Index('sgl_status', 'sgl_status')
    )

    cod_status = mapped_column(Integer, primary_key=True)
    ind_fim_tramitacao = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_retorno_tramitacao = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    sgl_status = mapped_column(VARCHAR(10))
    des_status = mapped_column(VARCHAR(60))
    num_dias_prazo = mapped_column(Integer)

    tramitacao: Mapped[List['Tramitacao']] = relationship('Tramitacao', uselist=True, back_populates='status_tramitacao')


class StatusTramitacaoAdministrativo(Base):
    __tablename__ = 'status_tramitacao_administrativo'
    __table_args__ = (
        Index('des_status', 'des_status'),
        Index('sgl_status', 'sgl_status')
    )

    cod_status = mapped_column(Integer, primary_key=True)
    ind_fim_tramitacao = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_retorno_tramitacao = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    sgl_status = mapped_column(VARCHAR(10))
    des_status = mapped_column(VARCHAR(60))
    num_dias_prazo = mapped_column(Integer)

    tramitacao_administrativo: Mapped[List['TramitacaoAdministrativo']] = relationship('TramitacaoAdministrativo', uselist=True, back_populates='status_tramitacao_administrativo')


class TipoAfastamento(Base):
    __tablename__ = 'tipo_afastamento'

    tip_afastamento = mapped_column(Integer, primary_key=True)
    ind_afastamento = mapped_column(Integer, nullable=False)
    ind_fim_mandato = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    des_afastamento = mapped_column(VARCHAR(50))
    des_dispositivo = mapped_column(VARCHAR(50))

    mandato: Mapped[List['Mandato']] = relationship('Mandato', uselist=True, back_populates='tipo_afastamento')
    afastamento: Mapped[List['Afastamento']] = relationship('Afastamento', uselist=True, back_populates='tipo_afastamento')


class TipoAutor(Base):
    __tablename__ = 'tipo_autor'
    __table_args__ = (
        Index('des_tipo_autor', 'des_tipo_autor'),
    )

    tip_autor = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    des_tipo_autor = mapped_column(VARCHAR(50))
    tip_proposicao = mapped_column(VARCHAR(128))

    autor: Mapped[List['Autor']] = relationship('Autor', uselist=True, back_populates='tipo_autor')


class TipoComissao(Base):
    __tablename__ = 'tipo_comissao'
    __table_args__ = (
        Index('nom_tipo_comissao', 'nom_tipo_comissao'),
        Index('sgl_natureza_comissao', 'sgl_natureza_comissao')
    )

    tip_comissao = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    nom_tipo_comissao = mapped_column(VARCHAR(50))
    sgl_natureza_comissao = mapped_column(CHAR(1))
    sgl_tipo_comissao = mapped_column(VARCHAR(10))
    des_dispositivo_regimental = mapped_column(VARCHAR(50))

    comissao: Mapped[List['Comissao']] = relationship('Comissao', uselist=True, back_populates='tipo_comissao')


class TipoDependente(Base):
    __tablename__ = 'tipo_dependente'
    __table_args__ = (
        Index('des_tipo_dependente', 'des_tipo_dependente'),
    )

    tip_dependente = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    des_tipo_dependente = mapped_column(VARCHAR(50))

    dependente: Mapped[List['Dependente']] = relationship('Dependente', uselist=True, back_populates='tipo_dependente')


class TipoDocumento(Base):
    __tablename__ = 'tipo_documento'
    __table_args__ = (
        Index('des_tipo_documento', 'des_tipo_documento'),
    )

    tip_documento = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    des_tipo_documento = mapped_column(VARCHAR(50))

    documento_acessorio: Mapped[List['DocumentoAcessorio']] = relationship('DocumentoAcessorio', uselist=True, back_populates='tipo_documento')


class TipoDocumentoAdministrativo(Base):
    __tablename__ = 'tipo_documento_administrativo'
    __table_args__ = (
        Index('des_tipo_documento', 'des_tipo_documento'),
        Index('ind_publico', 'ind_publico')
    )

    tip_documento = mapped_column(Integer, primary_key=True)
    tip_natureza = mapped_column(CHAR(1), nullable=False, server_default=text("'P'"))
    ind_publico = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    sgl_tipo_documento = mapped_column(VARCHAR(5))
    des_tipo_documento = mapped_column(VARCHAR(50))

    documento_administrativo: Mapped[List['DocumentoAdministrativo']] = relationship('DocumentoAdministrativo', uselist=True, back_populates='tipo_documento_administrativo')
    documento_acessorio_administrativo: Mapped[List['DocumentoAcessorioAdministrativo']] = relationship('DocumentoAcessorioAdministrativo', uselist=True, back_populates='tipo_documento_administrativo')
    usuario_tipo_documento: Mapped[List['UsuarioTipoDocumento']] = relationship('UsuarioTipoDocumento', uselist=True, back_populates='tipo_documento_administrativo')
    usuario_consulta_documento: Mapped[List['UsuarioConsultaDocumento']] = relationship('UsuarioConsultaDocumento', back_populates='tipo_documento_administrativo')


class TipoEmenda(Base):
    __tablename__ = 'tipo_emenda'
    __table_args__ = (
        Index('des_tipo_emenda', 'des_tipo_emenda'),
    )

    tip_emenda = mapped_column(Integer, primary_key=True)
    des_tipo_emenda = mapped_column(VARCHAR(50), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    emenda: Mapped[List['Emenda']] = relationship('Emenda', uselist=True, back_populates='tipo_emenda')


class TipoExpediente(Base):
    __tablename__ = 'tipo_expediente'
    __table_args__ = (
        Index('nom_expediente', 'nom_expediente'),
    )

    cod_expediente = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(INTEGER, nullable=False)
    nom_expediente = mapped_column(VARCHAR(100))
    ordem = mapped_column(Integer)

    expediente_sessao_plenaria: Mapped[List['ExpedienteSessaoPlenaria']] = relationship('ExpedienteSessaoPlenaria', uselist=True, back_populates='tipo_expediente')


class TipoFimRelatoria(Base):
    __tablename__ = 'tipo_fim_relatoria'

    tip_fim_relatoria = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    des_fim_relatoria = mapped_column(VARCHAR(50))

    relatoria: Mapped[List['Relatoria']] = relationship('Relatoria', uselist=True, back_populates='tipo_fim_relatoria')


class TipoInstituicao(Base):
    __tablename__ = 'tipo_instituicao'

    tip_instituicao = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    nom_tipo_instituicao = mapped_column(VARCHAR(80))

    instituicao: Mapped[List['Instituicao']] = relationship('Instituicao', uselist=True, back_populates='tipo_instituicao')


class TipoMateriaLegislativa(Base):
    __tablename__ = 'tipo_materia_legislativa'
    __table_args__ = (
        Index('des_tipo_materia', 'des_tipo_materia'),
    )

    tip_materia = mapped_column(Integer, primary_key=True)
    ind_publico = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    ind_num_automatica = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    quorum_minimo_votacao = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    ind_excluido = mapped_column(Integer, nullable=False)
    sgl_tipo_materia = mapped_column(VARCHAR(5))
    des_tipo_materia = mapped_column(VARCHAR(50))
    tip_natureza = mapped_column(CHAR(1))
    ordem = mapped_column(Integer)

    materia_legislativa: Mapped[List['MateriaLegislativa']] = relationship('MateriaLegislativa', uselist=True, back_populates='tipo_materia_legislativa')
    numeracao: Mapped[List['Numeracao']] = relationship('Numeracao', uselist=True, back_populates='tipo_materia_legislativa')


class TipoNormaJuridica(Base):
    __tablename__ = 'tipo_norma_juridica'
    __table_args__ = (
        Index('des_tipo_norma', 'des_tipo_norma'),
    )

    tip_norma = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    voc_lexml = mapped_column(VARCHAR(50))
    sgl_tipo_norma = mapped_column(CHAR(3))
    des_tipo_norma = mapped_column(VARCHAR(50))

    norma_juridica: Mapped[List['NormaJuridica']] = relationship('NormaJuridica', uselist=True, back_populates='tipo_norma_juridica')


class TipoPeticionamento(Base):
    __tablename__ = 'tipo_peticionamento'
    __table_args__ = (
        Index('cod_unid_tram_dest', 'cod_unid_tram_dest'),
    )

    tip_peticionamento = mapped_column(Integer, primary_key=True)
    des_tipo_peticionamento = mapped_column(VARCHAR(50), nullable=False)
    tip_derivado = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    ind_norma = mapped_column(CHAR(1))
    ind_doc_adm = mapped_column(CHAR(1))
    ind_doc_materia = mapped_column(CHAR(1))
    cod_unid_tram_dest = mapped_column(Integer)

    usuario_peticionamento: Mapped[List['UsuarioPeticionamento']] = relationship('UsuarioPeticionamento', uselist=True, back_populates='tipo_peticionamento')
    peticao: Mapped[List['Peticao']] = relationship('Peticao', uselist=True, back_populates='tipo_peticionamento')


class TipoProposicao(Base):
    __tablename__ = 'tipo_proposicao'
    __table_args__ = (
        Index('des_tipo_proposicao', 'des_tipo_proposicao'),
    )

    tip_proposicao = mapped_column(Integer, primary_key=True)
    tip_mat_ou_doc = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    des_tipo_proposicao = mapped_column(VARCHAR(50))
    ind_mat_ou_doc = mapped_column(CHAR(1))
    nom_modelo = mapped_column(VARCHAR(50))

    assunto_proposicao: Mapped[List['AssuntoProposicao']] = relationship('AssuntoProposicao', uselist=True, back_populates='tipo_proposicao')
    proposicao: Mapped[List['Proposicao']] = relationship('Proposicao', uselist=True, back_populates='tipo_proposicao')


class TipoResultadoVotacao(Base):
    __tablename__ = 'tipo_resultado_votacao'
    __table_args__ = (
        Index('nom_resultado', 'nom_resultado'),
    )

    tip_resultado_votacao = mapped_column(INTEGER, primary_key=True)
    ind_excluido = mapped_column(INTEGER, nullable=False)
    nom_resultado = mapped_column(VARCHAR(100))


class TipoSessaoPlenaria(Base):
    __tablename__ = 'tipo_sessao_plenaria'
    __table_args__ = (
        Index('nom_sessao', 'nom_sessao'),
    )

    tip_sessao = mapped_column(Integer, primary_key=True)
    num_minimo = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    nom_sessao = mapped_column(VARCHAR(30))

    periodo_sessao: Mapped[List['PeriodoSessao']] = relationship('PeriodoSessao', uselist=True, back_populates='tipo_sessao_plenaria')
    sessao_plenaria: Mapped[List['SessaoPlenaria']] = relationship('SessaoPlenaria', uselist=True, back_populates='tipo_sessao_plenaria')


class TipoSituacaoMateria(Base):
    __tablename__ = 'tipo_situacao_materia'
    __table_args__ = (
        Index('des_tipo_situacao', 'des_tipo_situacao'),
    )

    tip_situacao_materia = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    des_tipo_situacao = mapped_column(VARCHAR(100))


class TipoSituacaoMilitar(Base):
    __tablename__ = 'tipo_situacao_militar'

    tip_situacao_militar = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    des_tipo_situacao = mapped_column(VARCHAR(50))

    parlamentar: Mapped[List['Parlamentar']] = relationship('Parlamentar', uselist=True, back_populates='tipo_situacao_militar')


class TipoSituacaoNorma(Base):
    __tablename__ = 'tipo_situacao_norma'
    __table_args__ = (
        Index('des_tipo_situacao', 'des_tipo_situacao'),
    )

    tip_situacao_norma = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    des_tipo_situacao = mapped_column(VARCHAR(100))

    norma_juridica: Mapped[List['NormaJuridica']] = relationship('NormaJuridica', uselist=True, back_populates='tipo_situacao_norma')


class TipoVinculoNorma(Base):
    __tablename__ = 'tipo_vinculo_norma'
    __table_args__ = (
        Index('idx_vinculo', 'tipo_vinculo', 'des_vinculo', 'des_vinculo_passivo', 'ind_excluido', unique=True),
        Index('tip_situacao', 'tip_situacao'),
        Index('tipo_vinculo', 'tipo_vinculo', unique=True)
    )

    cod_tip_vinculo = mapped_column(Integer, primary_key=True)
    tipo_vinculo = mapped_column(CHAR(1), nullable=False)
    des_vinculo = mapped_column(VARCHAR(50), nullable=False)
    des_vinculo_passivo = mapped_column(VARCHAR(50), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    tip_situacao = mapped_column(Integer)


class TipoVotacao(Base):
    __tablename__ = 'tipo_votacao'

    tip_votacao = mapped_column(Integer, primary_key=True)
    des_tipo_votacao = mapped_column(VARCHAR(50), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    expediente_materia: Mapped[List['ExpedienteMateria']] = relationship('ExpedienteMateria', uselist=True, back_populates='tipo_votacao')
    ordem_dia: Mapped[List['OrdemDia']] = relationship('OrdemDia', uselist=True, back_populates='tipo_votacao')


class TurnoDiscussao(Base):
    __tablename__ = 'turno_discussao'
    __table_args__ = (
        Index('idx_unique_key', 'cod_turno', 'sgl_turno', 'ind_excluido', unique=True),
    )

    cod_turno = mapped_column(Integer, primary_key=True)
    sgl_turno = mapped_column(CHAR(1), nullable=False, server_default=text("'S'"))
    des_turno = mapped_column(VARCHAR(50), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))

    expediente_materia: Mapped[List['ExpedienteMateria']] = relationship('ExpedienteMateria', uselist=True, back_populates='turno_discussao')
    ordem_dia: Mapped[List['OrdemDia']] = relationship('OrdemDia', uselist=True, back_populates='turno_discussao')


class AssuntoProposicao(Base):
    __tablename__ = 'assunto_proposicao'
    __table_args__ = (
        ForeignKeyConstraint(['tip_proposicao'], ['tipo_proposicao.tip_proposicao'], ondelete='RESTRICT', onupdate='RESTRICT', name='assunto_proposicao_ibfk_1'),
        Index('des_assunto', 'des_assunto'),
        Index('tip_proposicao', 'tip_proposicao')
    )

    cod_assunto = mapped_column(Integer, primary_key=True)
    tip_proposicao = mapped_column(Integer, nullable=False)
    des_assunto = mapped_column(VARCHAR(250), nullable=False)
    nom_orgao = mapped_column(VARCHAR(250), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    end_orgao = mapped_column(VARCHAR(250))

    tipo_proposicao: Mapped['TipoProposicao'] = relationship('TipoProposicao', back_populates='assunto_proposicao')
    proposicao: Mapped[List['Proposicao']] = relationship('Proposicao', uselist=True, back_populates='assunto_proposicao')


class Bancada(Base):
    __tablename__ = 'bancada'
    __table_args__ = (
        ForeignKeyConstraint(['cod_partido'], ['partido.cod_partido'], ondelete='RESTRICT', name='bancada_ibfk_1'),
        ForeignKeyConstraint(['num_legislatura'], ['legislatura.num_legislatura'], ondelete='RESTRICT', onupdate='RESTRICT', name='bancada_ibfk_2'),
        Index('cod_partido', 'cod_partido'),
        Index('idt_nom_bancada', 'nom_bancada'),
        Index('nom_bancada', 'nom_bancada'),
        Index('num_legislatura', 'num_legislatura')
    )

    cod_bancada = mapped_column(Integer, primary_key=True)
    num_legislatura = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_partido = mapped_column(Integer)
    nom_bancada = mapped_column(VARCHAR(60))
    descricao = mapped_column(TEXT)
    dat_criacao = mapped_column(Date)
    dat_extincao = mapped_column(Date)

    partido: Mapped[Optional['Partido']] = relationship('Partido', back_populates='bancada')
    legislatura: Mapped['Legislatura'] = relationship('Legislatura', back_populates='bancada')
    autor: Mapped[List['Autor']] = relationship('Autor', uselist=True, back_populates='bancada')
    composicao_bancada: Mapped[List['ComposicaoBancada']] = relationship('ComposicaoBancada', uselist=True, back_populates='bancada')


class Coligacao(Base):
    __tablename__ = 'coligacao'
    __table_args__ = (
        ForeignKeyConstraint(['num_legislatura'], ['legislatura.num_legislatura'], ondelete='RESTRICT', onupdate='RESTRICT', name='coligacao_ibfk_1'),
        Index('idx_coligacao_legislatura', 'num_legislatura', 'ind_excluido'),
        Index('idx_legislatura', 'num_legislatura')
    )

    cod_coligacao = mapped_column(Integer, primary_key=True)
    num_legislatura = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    nom_coligacao = mapped_column(VARCHAR(50))
    num_votos_coligacao = mapped_column(Integer)

    legislatura: Mapped['Legislatura'] = relationship('Legislatura', back_populates='coligacao')
    mandato: Mapped[List['Mandato']] = relationship('Mandato', uselist=True, back_populates='coligacao')


class Comissao(Base):
    __tablename__ = 'comissao'
    __table_args__ = (
        ForeignKeyConstraint(['tip_comissao'], ['tipo_comissao.tip_comissao'], ondelete='RESTRICT', onupdate='RESTRICT', name='comissao_ibfk_1'),
        Index('idx_comissao_nome', 'nom_comissao'),
        Index('idx_comissao_tipo', 'tip_comissao'),
        Index('nom_comissao', 'nom_comissao')
    )

    cod_comissao = mapped_column(Integer, primary_key=True)
    tip_comissao = mapped_column(Integer, nullable=False)
    dat_criacao = mapped_column(Date, nullable=False)
    ind_unid_deliberativa = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    nom_comissao = mapped_column(VARCHAR(200))
    sgl_comissao = mapped_column(VARCHAR(10))
    dat_extincao = mapped_column(Date)
    nom_apelido_temp = mapped_column(VARCHAR(100))
    dat_instalacao_temp = mapped_column(Date)
    dat_final_prevista_temp = mapped_column(Date)
    dat_prorrogada_temp = mapped_column(Date)
    dat_fim_comissao = mapped_column(Date)
    nom_secretario = mapped_column(VARCHAR(30))
    num_tel_reuniao = mapped_column(VARCHAR(15))
    end_secretaria = mapped_column(VARCHAR(100))
    num_tel_secretaria = mapped_column(VARCHAR(15))
    num_fax_secretaria = mapped_column(VARCHAR(15))
    des_agenda_reuniao = mapped_column(VARCHAR(100))
    loc_reuniao = mapped_column(VARCHAR(100))
    txt_finalidade = mapped_column(TEXT)
    end_email = mapped_column(VARCHAR(100))
    ordem = mapped_column(Integer)

    tipo_comissao: Mapped['TipoComissao'] = relationship('TipoComissao', back_populates='comissao')
    autor: Mapped[List['Autor']] = relationship('Autor', uselist=True, back_populates='comissao')
    composicao_comissao: Mapped[List['ComposicaoComissao']] = relationship('ComposicaoComissao', uselist=True, back_populates='comissao')
    despacho_inicial: Mapped[List['DespachoInicial']] = relationship('DespachoInicial', uselist=True, back_populates='comissao')
    documento_comissao: Mapped[List['DocumentoComissao']] = relationship('DocumentoComissao', uselist=True, back_populates='comissao')
    relatoria: Mapped[List['Relatoria']] = relationship('Relatoria', uselist=True, back_populates='comissao')
    reuniao_comissao: Mapped[List['ReuniaoComissao']] = relationship('ReuniaoComissao', uselist=True, back_populates='comissao')
    unidade_tramitacao: Mapped[List['UnidadeTramitacao']] = relationship('UnidadeTramitacao', uselist=True, back_populates='comissao')


class ComposicaoColigacao(Base):
    __tablename__ = 'composicao_coligacao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_partido'], ['partido.cod_partido'], ondelete='RESTRICT', name='composicao_coligacao_ibfk_1'),
        Index('idx_coligacao', 'cod_coligacao'),
        Index('idx_partido', 'cod_partido')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_partido = mapped_column(Integer, nullable=False)
    cod_coligacao = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    partido: Mapped['Partido'] = relationship('Partido', back_populates='composicao_coligacao')


class ComposicaoExecutivo(Base):
    __tablename__ = 'composicao_executivo'
    __table_args__ = (
        ForeignKeyConstraint(['cod_cargo'], ['cargo_executivo.cod_cargo'], ondelete='RESTRICT', onupdate='RESTRICT', name='composicao_executivo_ibfk_2'),
        ForeignKeyConstraint(['cod_partido'], ['partido.cod_partido'], ondelete='RESTRICT', onupdate='RESTRICT', name='composicao_executivo_ibfk_3'),
        ForeignKeyConstraint(['num_legislatura'], ['legislatura.num_legislatura'], ondelete='RESTRICT', onupdate='RESTRICT', name='composicao_executivo_ibfk_4'),
        Index('cod_cargo', 'cod_cargo'),
        Index('cod_partido', 'cod_partido'),
        Index('num_legislatura', 'num_legislatura')
    )

    cod_composicao = mapped_column(Integer, primary_key=True)
    num_legislatura = mapped_column(Integer, nullable=False)
    nom_completo = mapped_column(VARCHAR(50), nullable=False)
    cod_cargo = mapped_column(TINYINT, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_partido = mapped_column(Integer)
    dat_inicio_mandato = mapped_column(Date)
    dat_fim_mandato = mapped_column(Date)
    txt_observacao = mapped_column(TEXT)

    cargo_executivo: Mapped['CargoExecutivo'] = relationship('CargoExecutivo', back_populates='composicao_executivo')
    partido: Mapped[Optional['Partido']] = relationship('Partido', back_populates='composicao_executivo')
    legislatura: Mapped['Legislatura'] = relationship('Legislatura', back_populates='composicao_executivo')


class DocumentoAdministrativo(Base):
    __tablename__ = 'documento_administrativo'
    __table_args__ = (
        ForeignKeyConstraint(['tip_documento'], ['tipo_documento_administrativo.tip_documento'], ondelete='RESTRICT', name='documento_administrativo_ibfk_1'),
        Index('ano_documento', 'ano_documento'),
        Index('cod_autor', 'cod_autor'),
        Index('cod_entidade', 'cod_entidade'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_situacao', 'cod_situacao'),
        Index('dat_documento', 'dat_documento'),
        Index('idx_busca_documento', 'txt_assunto', 'txt_observacao'),
        Index('num_protocolo', 'num_protocolo'),
        Index('tip_documento', 'tip_documento', 'num_documento', 'ano_documento'),
        Index('txt_interessado', 'txt_interessado')
    )

    cod_documento = mapped_column(Integer, primary_key=True)
    tip_documento = mapped_column(Integer, nullable=False)
    num_documento = mapped_column(Integer, nullable=False)
    ano_documento = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_documento = mapped_column(Date, nullable=False)
    ind_tramitacao = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    num_protocolo = mapped_column(Integer)
    txt_interessado = mapped_column(VARCHAR(200))
    cod_autor = mapped_column(Integer)
    cod_entidade = mapped_column(Integer)
    cod_materia = mapped_column(Integer)
    num_dias_prazo = mapped_column(Integer)
    dat_fim_prazo = mapped_column(Date)
    txt_assunto = mapped_column(TEXT)
    txt_observacao = mapped_column(TEXT)
    cod_situacao = mapped_column(Integer)
    cod_assunto = mapped_column(Integer)

    tipo_documento_administrativo: Mapped['TipoDocumentoAdministrativo'] = relationship('TipoDocumentoAdministrativo', back_populates='documento_administrativo')
    cientificacao_documento: Mapped[List['CientificacaoDocumento']] = relationship('CientificacaoDocumento', uselist=True, back_populates='documento_administrativo')
    documento_acessorio_administrativo: Mapped[List['DocumentoAcessorioAdministrativo']] = relationship('DocumentoAcessorioAdministrativo', uselist=True, back_populates='documento_administrativo')
    documento_administrativo_materia: Mapped[List['DocumentoAdministrativoMateria']] = relationship('DocumentoAdministrativoMateria', uselist=True, back_populates='documento_administrativo')
    documento_administrativo_vinculado: Mapped[List['DocumentoAdministrativoVinculado']] = relationship('DocumentoAdministrativoVinculado', uselist=True, foreign_keys='[DocumentoAdministrativoVinculado.cod_documento_vinculado]', back_populates='documento_administrativo')
    documento_administrativo_vinculado_: Mapped[List['DocumentoAdministrativoVinculado']] = relationship('DocumentoAdministrativoVinculado', uselist=True, foreign_keys='[DocumentoAdministrativoVinculado.cod_documento_vinculante]', back_populates='documento_administrativo_')
    peticao: Mapped[List['Peticao']] = relationship('Peticao', uselist=True, foreign_keys='[Peticao.cod_documento]', back_populates='documento_administrativo')
    peticao_: Mapped[List['Peticao']] = relationship('Peticao', uselist=True, foreign_keys='[Peticao.cod_documento_vinculado]', back_populates='documento_administrativo_')
    tramitacao_administrativo: Mapped[List['TramitacaoAdministrativo']] = relationship('TramitacaoAdministrativo', uselist=True, back_populates='documento_administrativo')
    destinatario_oficio: Mapped[List['DestinatarioOficio']] = relationship('DestinatarioOficio', uselist=True, back_populates='documento_administrativo')
    materia_apresentada_sessao: Mapped[List['MateriaApresentadaSessao']] = relationship('MateriaApresentadaSessao', uselist=True, back_populates='documento_administrativo')


class Instituicao(Base):
    __tablename__ = 'instituicao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_localidade'], ['localidade.cod_localidade'], ondelete='RESTRICT', name='instituicao_ibfk_3'),
        ForeignKeyConstraint(['tip_instituicao'], ['tipo_instituicao.tip_instituicao'], ondelete='RESTRICT', name='instituicao_ibfk_2'),
        Index('cod_categoria', 'cod_categoria'),
        Index('cod_localidade', 'cod_localidade'),
        Index('idx_cod_cat', 'tip_instituicao', 'cod_categoria'),
        Index('idx_nom_instituicao', 'nom_instituicao'),
        Index('idx_nom_responsavel', 'nom_responsavel'),
        Index('ind_excluido', 'ind_excluido'),
        Index('tip_instituicao', 'tip_instituicao')
    )

    cod_instituicao = mapped_column(Integer, primary_key=True)
    tip_instituicao = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    timestamp_alteracao = mapped_column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    cod_categoria = mapped_column(Integer)
    nom_instituicao = mapped_column(VARCHAR(200))
    end_instituicao = mapped_column(TINYTEXT)
    nom_bairro = mapped_column(VARCHAR(80))
    cod_localidade = mapped_column(Integer)
    num_cep = mapped_column(VARCHAR(9))
    num_telefone = mapped_column(VARCHAR(50))
    num_fax = mapped_column(VARCHAR(50))
    end_email = mapped_column(VARCHAR(100))
    end_web = mapped_column(VARCHAR(100))
    nom_responsavel = mapped_column(VARCHAR(50))
    des_cargo = mapped_column(VARCHAR(80))
    txt_forma_tratamento = mapped_column(VARCHAR(30))
    txt_observacao = mapped_column(TINYTEXT)
    dat_insercao = mapped_column(DateTime)
    txt_user_insercao = mapped_column(VARCHAR(20))
    txt_ip_insercao = mapped_column(VARCHAR(15))
    txt_user_alteracao = mapped_column(VARCHAR(20))
    txt_ip_alteracao = mapped_column(VARCHAR(15))
    txt_atividade = mapped_column(VARCHAR(10))
    txt_origem = mapped_column(VARCHAR(5))

    localidade: Mapped[Optional['Localidade']] = relationship('Localidade', back_populates='instituicao')
    tipo_instituicao: Mapped['TipoInstituicao'] = relationship('TipoInstituicao', back_populates='instituicao')
    destinatario_oficio: Mapped[List['DestinatarioOficio']] = relationship('DestinatarioOficio', uselist=True, back_populates='instituicao')


class MateriaLegislativa(Base):
    __tablename__ = 'materia_legislativa'
    __table_args__ = (
        ForeignKeyConstraint(['cod_local_origem_externa'], ['origem.cod_origem'], ondelete='RESTRICT', name='materia_legislativa_ibfk_2'),
        ForeignKeyConstraint(['cod_regime_tramitacao'], ['regime_tramitacao.cod_regime_tramitacao'], ondelete='RESTRICT', onupdate='RESTRICT', name='materia_legislativa_ibfk_6'),
        ForeignKeyConstraint(['tip_id_basica'], ['tipo_materia_legislativa.tip_materia'], ondelete='RESTRICT', name='materia_legislativa_ibfk_5'),
        ForeignKeyConstraint(['tip_quorum'], ['quorum_votacao.cod_quorum'], ondelete='RESTRICT', name='materia_legislativa_ibfk_3'),
        Index('cod_local_origem_externa', 'cod_local_origem_externa'),
        Index('cod_regime_tramitacao', 'cod_regime_tramitacao'),
        Index('cod_situacao', 'cod_situacao'),
        Index('idx_assunto', 'cod_assunto'),
        Index('idx_busca', 'txt_ementa', 'txt_observacao', 'txt_indexacao'),
        Index('idx_dat_apresentacao', 'dat_apresentacao', 'tip_id_basica', 'ind_excluido'),
        Index('idx_mat_principal', 'cod_materia_principal'),
        Index('idx_matleg_dat_publicacao', 'dat_publicacao', 'tip_id_basica', 'ind_excluido'),
        Index('idx_matleg_ident', 'ind_excluido', 'tip_id_basica', 'ano_ident_basica', 'num_ident_basica'),
        Index('idx_tramitacao', 'ind_tramitacao'),
        Index('tip_id_basica', 'tip_id_basica'),
        Index('tip_origem_externa', 'tip_origem_externa'),
        Index('tip_quorum', 'tip_quorum')
    )

    cod_materia = mapped_column(Integer, primary_key=True)
    tip_id_basica = mapped_column(Integer, nullable=False)
    num_ident_basica = mapped_column(Integer, nullable=False)
    ano_ident_basica = mapped_column(Integer, nullable=False)
    cod_regime_tramitacao = mapped_column(Integer, nullable=False)
    ind_tramitacao = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    num_protocolo = mapped_column(Integer)
    dat_apresentacao = mapped_column(Date)
    tip_apresentacao = mapped_column(CHAR(1))
    dat_publicacao = mapped_column(Date)
    des_veiculo_publicacao = mapped_column(VARCHAR(50))
    tip_origem_externa = mapped_column(Integer)
    num_origem_externa = mapped_column(VARCHAR(5))
    ano_origem_externa = mapped_column(Integer)
    dat_origem_externa = mapped_column(Date)
    cod_local_origem_externa = mapped_column(Integer)
    nom_apelido = mapped_column(VARCHAR(50))
    num_dias_prazo = mapped_column(Integer)
    dat_fim_prazo = mapped_column(Date)
    ind_polemica = mapped_column(Integer)
    des_objeto = mapped_column(VARCHAR(150))
    ind_complementar = mapped_column(Integer)
    txt_ementa = mapped_column(TEXT)
    txt_indexacao = mapped_column(TEXT)
    txt_observacao = mapped_column(TEXT)
    tip_quorum = mapped_column(Integer)
    cod_situacao = mapped_column(Integer)
    cod_assunto = mapped_column(Integer)
    cod_materia_principal = mapped_column(Integer)
    autografo_numero = mapped_column(VARCHAR(10))
    autografo_data = mapped_column(Date)
    data_encerramento = mapped_column(Date)
    materia_num_tipo_status = mapped_column(Integer)

    origem: Mapped[Optional['Origem']] = relationship('Origem', back_populates='materia_legislativa')
    regime_tramitacao: Mapped['RegimeTramitacao'] = relationship('RegimeTramitacao', back_populates='materia_legislativa')
    tipo_materia_legislativa: Mapped['TipoMateriaLegislativa'] = relationship('TipoMateriaLegislativa', back_populates='materia_legislativa')
    quorum_votacao: Mapped[Optional['QuorumVotacao']] = relationship('QuorumVotacao', back_populates='materia_legislativa')
    anexada: Mapped[List['Anexada']] = relationship('Anexada', uselist=True, foreign_keys='[Anexada.cod_materia_anexada]', back_populates='materia_legislativa')
    anexada_: Mapped[List['Anexada']] = relationship('Anexada', uselist=True, foreign_keys='[Anexada.cod_materia_principal]', back_populates='materia_legislativa_')
    despacho_inicial: Mapped[List['DespachoInicial']] = relationship('DespachoInicial', uselist=True, back_populates='materia_legislativa')
    documento_acessorio: Mapped[List['DocumentoAcessorio']] = relationship('DocumentoAcessorio', uselist=True, back_populates='materia_legislativa')
    documento_administrativo_materia: Mapped[List['DocumentoAdministrativoMateria']] = relationship('DocumentoAdministrativoMateria', uselist=True, back_populates='materia_legislativa')
    emenda: Mapped[List['Emenda']] = relationship('Emenda', uselist=True, back_populates='materia_legislativa')
    norma_juridica: Mapped[List['NormaJuridica']] = relationship('NormaJuridica', uselist=True, back_populates='materia_legislativa')
    numeracao: Mapped[List['Numeracao']] = relationship('Numeracao', uselist=True, back_populates='materia_legislativa')
    relatoria: Mapped[List['Relatoria']] = relationship('Relatoria', uselist=True, back_populates='materia_legislativa')
    substitutivo: Mapped[List['Substitutivo']] = relationship('Substitutivo', uselist=True, back_populates='materia_legislativa')
    autoria: Mapped[List['Autoria']] = relationship('Autoria', uselist=True, back_populates='materia_legislativa')
    legislacao_citada: Mapped[List['LegislacaoCitada']] = relationship('LegislacaoCitada', uselist=True, back_populates='materia_legislativa')
    parecer: Mapped[List['Parecer']] = relationship('Parecer', uselist=True, back_populates='materia_legislativa')
    peticao: Mapped[List['Peticao']] = relationship('Peticao', uselist=True, back_populates='materia_legislativa')
    proposicao: Mapped[List['Proposicao']] = relationship('Proposicao', uselist=True, back_populates='materia_legislativa')
    protocolo: Mapped[List['Protocolo']] = relationship('Protocolo', uselist=True, back_populates='materia_legislativa')
    registro_votacao: Mapped[List['RegistroVotacao']] = relationship('RegistroVotacao', uselist=True, back_populates='materia_legislativa')
    reuniao_comissao_pauta: Mapped[List['ReuniaoComissaoPauta']] = relationship('ReuniaoComissaoPauta', uselist=True, back_populates='materia_legislativa')
    tramitacao: Mapped[List['Tramitacao']] = relationship('Tramitacao', uselist=True, back_populates='materia_legislativa')
    destinatario_oficio: Mapped[List['DestinatarioOficio']] = relationship('DestinatarioOficio', uselist=True, back_populates='materia_legislativa')
    expediente_materia: Mapped[List['ExpedienteMateria']] = relationship('ExpedienteMateria', uselist=True, back_populates='materia_legislativa')
    materia_apresentada_sessao: Mapped[List['MateriaApresentadaSessao']] = relationship('MateriaApresentadaSessao', uselist=True, back_populates='materia_legislativa')
    ordem_dia: Mapped[List['OrdemDia']] = relationship('OrdemDia', uselist=True, back_populates='materia_legislativa')


class Parlamentar(Base):
    __tablename__ = 'parlamentar'
    __table_args__ = (
        ForeignKeyConstraint(['cod_localidade_resid'], ['localidade.cod_localidade'], ondelete='RESTRICT', name='parlamentar_ibfk_1'),
        ForeignKeyConstraint(['cod_nivel_instrucao'], ['nivel_instrucao.cod_nivel_instrucao'], ondelete='RESTRICT', onupdate='RESTRICT', name='parlamentar_ibfk_4'),
        ForeignKeyConstraint(['tip_situacao_militar'], ['tipo_situacao_militar.tip_situacao_militar'], ondelete='RESTRICT', onupdate='RESTRICT', name='parlamentar_ibfk_5'),
        Index('cod_localidade_resid', 'cod_localidade_resid'),
        Index('cod_nivel_instrucao', 'cod_nivel_instrucao'),
        Index('ind_parlamentar_ativo', 'ind_ativo', 'ind_excluido'),
        Index('nom_completo', 'nom_completo'),
        Index('nom_parlamentar', 'nom_parlamentar'),
        Index('tip_situacao_militar', 'tip_situacao_militar')
    )

    cod_parlamentar = mapped_column(Integer, primary_key=True)
    ind_ativo = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    nom_completo = mapped_column(VARCHAR(50))
    nom_parlamentar = mapped_column(VARCHAR(50))
    nom_painel = mapped_column(VARCHAR(50))
    sex_parlamentar = mapped_column(CHAR(1))
    dat_nascimento = mapped_column(Date)
    dat_falecimento = mapped_column(Date)
    num_cpf = mapped_column(VARCHAR(14))
    num_rg = mapped_column(VARCHAR(15))
    num_tit_eleitor = mapped_column(VARCHAR(15))
    tip_situacao_militar = mapped_column(Integer)
    cod_nivel_instrucao = mapped_column(Integer)
    des_curso = mapped_column(VARCHAR(50))
    cod_casa = mapped_column(Integer)
    num_gab_parlamentar = mapped_column(VARCHAR(10))
    num_tel_parlamentar = mapped_column(VARCHAR(50))
    num_fax_parlamentar = mapped_column(VARCHAR(50))
    end_residencial = mapped_column(VARCHAR(100))
    cod_localidade_resid = mapped_column(Integer)
    num_cep_resid = mapped_column(VARCHAR(9))
    num_tel_resid = mapped_column(VARCHAR(50))
    num_celular = mapped_column(VARCHAR(50))
    num_fax_resid = mapped_column(VARCHAR(50))
    end_web = mapped_column(VARCHAR(100))
    nom_profissao = mapped_column(VARCHAR(50))
    end_email = mapped_column(VARCHAR(100))
    des_local_atuacao = mapped_column(VARCHAR(100))
    ind_unid_deliberativa = mapped_column(Integer)
    txt_biografia = mapped_column(TEXT)
    txt_observacao = mapped_column(TEXT)
    texto_parlamentar = mapped_column(TEXT)

    localidade: Mapped[Optional['Localidade']] = relationship('Localidade', back_populates='parlamentar')
    nivel_instrucao: Mapped[Optional['NivelInstrucao']] = relationship('NivelInstrucao', back_populates='parlamentar')
    tipo_situacao_militar: Mapped[Optional['TipoSituacaoMilitar']] = relationship('TipoSituacaoMilitar', back_populates='parlamentar')
    assessor_parlamentar: Mapped[List['AssessorParlamentar']] = relationship('AssessorParlamentar', uselist=True, back_populates='parlamentar')
    autor: Mapped[List['Autor']] = relationship('Autor', uselist=True, back_populates='parlamentar')
    composicao_bancada: Mapped[List['ComposicaoBancada']] = relationship('ComposicaoBancada', uselist=True, back_populates='parlamentar')
    composicao_comissao: Mapped[List['ComposicaoComissao']] = relationship('ComposicaoComissao', uselist=True, back_populates='parlamentar')
    composicao_mesa: Mapped[List['ComposicaoMesa']] = relationship('ComposicaoMesa', uselist=True, back_populates='parlamentar')
    dependente: Mapped[List['Dependente']] = relationship('Dependente', uselist=True, back_populates='parlamentar')
    filiacao: Mapped[List['Filiacao']] = relationship('Filiacao', uselist=True, back_populates='parlamentar')
    mandato: Mapped[List['Mandato']] = relationship('Mandato', uselist=True, back_populates='parlamentar')
    relatoria: Mapped[List['Relatoria']] = relationship('Relatoria', uselist=True, back_populates='parlamentar')
    unidade_tramitacao: Mapped[List['UnidadeTramitacao']] = relationship('UnidadeTramitacao', uselist=True, back_populates='parlamentar')
    afastamento: Mapped[List['Afastamento']] = relationship('Afastamento', uselist=True, back_populates='parlamentar')
    gabinete_eleitor: Mapped[List['GabineteEleitor']] = relationship('GabineteEleitor', uselist=True, back_populates='parlamentar')
    reuniao_comissao_pauta: Mapped[List['ReuniaoComissaoPauta']] = relationship('ReuniaoComissaoPauta', uselist=True, back_populates='parlamentar')
    reuniao_comissao_presenca: Mapped[List['ReuniaoComissaoPresenca']] = relationship('ReuniaoComissaoPresenca', uselist=True, back_populates='parlamentar')
    encerramento_presenca: Mapped[List['EncerramentoPresenca']] = relationship('EncerramentoPresenca', uselist=True, back_populates='parlamentar')
    expediente_presenca: Mapped[List['ExpedientePresenca']] = relationship('ExpedientePresenca', uselist=True, back_populates='parlamentar')
    gabinete_atendimento: Mapped[List['GabineteAtendimento']] = relationship('GabineteAtendimento', uselist=True, back_populates='parlamentar')
    liderancas_partidarias: Mapped[List['LiderancasPartidarias']] = relationship('LiderancasPartidarias', uselist=True, back_populates='parlamentar')
    mesa_sessao_plenaria: Mapped[List['MesaSessaoPlenaria']] = relationship('MesaSessaoPlenaria', uselist=True, back_populates='parlamentar')
    oradores: Mapped[List['Oradores']] = relationship('Oradores', uselist=True, back_populates='parlamentar')
    oradores_expediente: Mapped[List['OradoresExpediente']] = relationship('OradoresExpediente', uselist=True, back_populates='parlamentar')
    ordem_dia_presenca: Mapped[List['OrdemDiaPresenca']] = relationship('OrdemDiaPresenca', uselist=True, back_populates='parlamentar')
    registro_votacao_parlamentar: Mapped[List['RegistroVotacaoParlamentar']] = relationship('RegistroVotacaoParlamentar', uselist=True, back_populates='parlamentar')
    sessao_plenaria_presenca: Mapped[List['SessaoPlenariaPresenca']] = relationship('SessaoPlenariaPresenca', uselist=True, back_populates='parlamentar')
    expediente_discussao: Mapped[List['ExpedienteDiscussao']] = relationship('ExpedienteDiscussao', uselist=True, back_populates='parlamentar')
    ordem_dia_discussao: Mapped[List['OrdemDiaDiscussao']] = relationship('OrdemDiaDiscussao', uselist=True, back_populates='parlamentar')


class PeriodoCompBancada(Base):
    __tablename__ = 'periodo_comp_bancada'
    __table_args__ = (
        ForeignKeyConstraint(['num_legislatura'], ['legislatura.num_legislatura'], ondelete='RESTRICT', onupdate='RESTRICT', name='periodo_comp_bancada_ibfk_1'),
        Index('idx_legislatura', 'num_legislatura'),
        Index('ind_percompbancada_datas', 'dat_inicio_periodo', 'dat_fim_periodo', 'ind_excluido')
    )

    cod_periodo_comp = mapped_column(Integer, primary_key=True)
    num_legislatura = mapped_column(Integer, nullable=False)
    dat_inicio_periodo = mapped_column(Date, nullable=False)
    dat_fim_periodo = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    legislatura: Mapped['Legislatura'] = relationship('Legislatura', back_populates='periodo_comp_bancada')
    composicao_bancada: Mapped[List['ComposicaoBancada']] = relationship('ComposicaoBancada', uselist=True, back_populates='periodo_comp_bancada')


class PeriodoCompMesa(Base):
    __tablename__ = 'periodo_comp_mesa'
    __table_args__ = (
        ForeignKeyConstraint(['num_legislatura'], ['legislatura.num_legislatura'], ondelete='RESTRICT', onupdate='RESTRICT', name='periodo_comp_mesa_ibfk_1'),
        Index('idx_legislatura', 'num_legislatura'),
        Index('ind_percompmesa_datas', 'dat_inicio_periodo', 'dat_fim_periodo', 'ind_excluido')
    )

    cod_periodo_comp = mapped_column(Integer, primary_key=True)
    num_legislatura = mapped_column(Integer, nullable=False)
    dat_inicio_periodo = mapped_column(Date, nullable=False)
    dat_fim_periodo = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    txt_observacao = mapped_column(TEXT)

    legislatura: Mapped['Legislatura'] = relationship('Legislatura', back_populates='periodo_comp_mesa')
    composicao_mesa: Mapped[List['ComposicaoMesa']] = relationship('ComposicaoMesa', uselist=True, back_populates='periodo_comp_mesa')


class SessaoLegislativa(Base):
    __tablename__ = 'sessao_legislativa'
    __table_args__ = (
        ForeignKeyConstraint(['num_legislatura'], ['legislatura.num_legislatura'], ondelete='RESTRICT', onupdate='RESTRICT', name='sessao_legislativa_ibfk_1'),
        Index('idx_legislatura', 'num_legislatura'),
        Index('idx_sessleg_datas', 'dat_inicio', 'ind_excluido', 'dat_fim', 'dat_inicio_intervalo', 'dat_fim_intervalo'),
        Index('idx_sessleg_legislatura', 'num_legislatura', 'ind_excluido')
    )

    cod_sessao_leg = mapped_column(Integer, primary_key=True)
    num_legislatura = mapped_column(Integer, nullable=False)
    num_sessao_leg = mapped_column(Integer, nullable=False)
    dat_inicio = mapped_column(Date, nullable=False)
    dat_fim = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    tip_sessao_leg = mapped_column(CHAR(1))
    dat_inicio_intervalo = mapped_column(Date)
    dat_fim_intervalo = mapped_column(Date)

    legislatura: Mapped['Legislatura'] = relationship('Legislatura', back_populates='sessao_legislativa')
    composicao_mesa: Mapped[List['ComposicaoMesa']] = relationship('ComposicaoMesa', uselist=True, back_populates='sessao_legislativa')
    periodo_sessao: Mapped[List['PeriodoSessao']] = relationship('PeriodoSessao', uselist=True, back_populates='sessao_legislativa')
    sessao_plenaria: Mapped[List['SessaoPlenaria']] = relationship('SessaoPlenaria', uselist=True, back_populates='sessao_legislativa')
    mesa_sessao_plenaria: Mapped[List['MesaSessaoPlenaria']] = relationship('MesaSessaoPlenaria', uselist=True, back_populates='sessao_legislativa')


class Usuario(Base):
    __tablename__ = 'usuario'
    __table_args__ = (
        ForeignKeyConstraint(['cod_localidade_resid'], ['localidade.cod_localidade'], ondelete='RESTRICT', name='usuario_ibfk_1'),
        Index('idx_cod_localidade', 'cod_localidade_resid'),
        Index('idx_col_username', 'col_username'),
        Index('ind_ativo', 'ind_ativo'),
        Index('ind_interno', 'ind_interno')
    )

    cod_usuario = mapped_column(Integer, primary_key=True)
    col_username = mapped_column(VARCHAR(50), nullable=False)
    ind_interno = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    nom_completo = mapped_column(VARCHAR(50), nullable=False)
    num_cpf = mapped_column(VARCHAR(14), nullable=False)
    end_email = mapped_column(VARCHAR(100), nullable=False)
    ind_ativo = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    ind_excluido = mapped_column(Integer, nullable=False)
    password = mapped_column(VARCHAR(255))
    dat_nascimento = mapped_column(Date)
    des_estado_civil = mapped_column(VARCHAR(20))
    sex_usuario = mapped_column(CHAR(1))
    num_rg = mapped_column(VARCHAR(15))
    num_tit_eleitor = mapped_column(VARCHAR(15))
    num_ctps = mapped_column(VARCHAR(8))
    num_serie_ctps = mapped_column(VARCHAR(4))
    num_pis_pasep = mapped_column(VARCHAR(14))
    end_residencial = mapped_column(VARCHAR(100))
    cod_localidade_resid = mapped_column(Integer)
    num_cep_resid = mapped_column(VARCHAR(9))
    num_tel_resid = mapped_column(VARCHAR(50))
    num_tel_celular = mapped_column(VARCHAR(50))
    num_matricula = mapped_column(VARCHAR(10))
    nom_cargo = mapped_column(VARCHAR(50))
    des_lotacao = mapped_column(VARCHAR(50))
    des_vinculo = mapped_column(VARCHAR(20))
    num_tel_comercial = mapped_column(VARCHAR(50))
    num_ramal = mapped_column(VARCHAR(50))
    txt_observacao = mapped_column(TEXT)

    localidade: Mapped[Optional['Localidade']] = relationship('Localidade', back_populates='usuario')
    assinatura_documento: Mapped[List['AssinaturaDocumento']] = relationship('AssinaturaDocumento', uselist=True, foreign_keys='[AssinaturaDocumento.cod_solicitante]', back_populates='usuario')
    assinatura_documento_: Mapped[List['AssinaturaDocumento']] = relationship('AssinaturaDocumento', uselist=True, foreign_keys='[AssinaturaDocumento.cod_usuario]', back_populates='usuario_')
    cientificacao_documento: Mapped[List['CientificacaoDocumento']] = relationship('CientificacaoDocumento', uselist=True, foreign_keys='[CientificacaoDocumento.cod_cientificado]', back_populates='usuario')
    cientificacao_documento_: Mapped[List['CientificacaoDocumento']] = relationship('CientificacaoDocumento', uselist=True, foreign_keys='[CientificacaoDocumento.cod_cientificador]', back_populates='usuario_')
    funcionario: Mapped[List['Funcionario']] = relationship('Funcionario', uselist=True, back_populates='usuario')
    usuario_peticionamento: Mapped[List['UsuarioPeticionamento']] = relationship('UsuarioPeticionamento', uselist=True, back_populates='usuario')
    usuario_tipo_documento: Mapped[List['UsuarioTipoDocumento']] = relationship('UsuarioTipoDocumento', uselist=True, back_populates='usuario')
    usuario_consulta_documento: Mapped[List['UsuarioConsultaDocumento']] = relationship('UsuarioConsultaDocumento', back_populates='usuario')
    peticao: Mapped[List['Peticao']] = relationship('Peticao', uselist=True, back_populates='usuario')
    proposicao: Mapped[List['Proposicao']] = relationship('Proposicao', uselist=True, back_populates='usuario')
    tramitacao: Mapped[List['Tramitacao']] = relationship('Tramitacao', uselist=True, foreign_keys='[Tramitacao.cod_usuario_dest]', back_populates='usuario')
    tramitacao_: Mapped[List['Tramitacao']] = relationship('Tramitacao', uselist=True, foreign_keys='[Tramitacao.cod_usuario_local]', back_populates='usuario_')
    tramitacao1: Mapped[List['Tramitacao']] = relationship('Tramitacao', uselist=True, foreign_keys='[Tramitacao.cod_usuario_visualiza]', back_populates='usuario1')
    tramitacao_administrativo: Mapped[List['TramitacaoAdministrativo']] = relationship('TramitacaoAdministrativo', uselist=True, foreign_keys='[TramitacaoAdministrativo.cod_usuario_dest]', back_populates='usuario')
    tramitacao_administrativo_: Mapped[List['TramitacaoAdministrativo']] = relationship('TramitacaoAdministrativo', uselist=True, foreign_keys='[TramitacaoAdministrativo.cod_usuario_local]', back_populates='usuario_')
    tramitacao_administrativo1: Mapped[List['TramitacaoAdministrativo']] = relationship('TramitacaoAdministrativo', uselist=True, foreign_keys='[TramitacaoAdministrativo.cod_usuario_visualiza]', back_populates='usuario1')
    usuario_unid_tram: Mapped[List['UsuarioUnidTram']] = relationship('UsuarioUnidTram', uselist=True, back_populates='usuario')
    destinatario_oficio: Mapped[List['DestinatarioOficio']] = relationship('DestinatarioOficio', uselist=True, back_populates='usuario')


class Anexada(Base):
    __tablename__ = 'anexada'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia_anexada'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='anexada_ibfk_1'),
        ForeignKeyConstraint(['cod_materia_principal'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='anexada_ibfk_2'),
        Index('idx_materia_anexada', 'cod_materia_anexada'),
        Index('idx_materia_principal', 'cod_materia_principal')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_materia_principal = mapped_column(Integer, nullable=False)
    cod_materia_anexada = mapped_column(Integer, nullable=False)
    dat_anexacao = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    dat_desanexacao = mapped_column(Date)

    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', foreign_keys=[cod_materia_anexada], back_populates='anexada')
    materia_legislativa_: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', foreign_keys=[cod_materia_principal], back_populates='anexada_')


class AssessorParlamentar(Base):
    __tablename__ = 'assessor_parlamentar'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='CASCADE', name='assessor_parlamentar_ibfk_1'),
        Index('assessor_parlamentar', 'cod_assessor', 'cod_parlamentar', 'ind_excluido', unique=True),
        Index('cod_parlamentar', 'cod_parlamentar')
    )

    cod_assessor = mapped_column(Integer, primary_key=True)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    nom_assessor = mapped_column(VARCHAR(50), nullable=False)
    des_cargo = mapped_column(VARCHAR(80), nullable=False)
    dat_nomeacao = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_nascimento = mapped_column(Date)
    num_cpf = mapped_column(VARCHAR(14))
    num_rg = mapped_column(VARCHAR(15))
    num_tit_eleitor = mapped_column(VARCHAR(15))
    end_residencial = mapped_column(VARCHAR(100))
    num_cep_resid = mapped_column(VARCHAR(9))
    num_tel_resid = mapped_column(VARCHAR(50))
    num_tel_celular = mapped_column(VARCHAR(50))
    end_email = mapped_column(VARCHAR(100))
    dat_exoneracao = mapped_column(Date)
    txt_observacao = mapped_column(TEXT)
    col_username = mapped_column(VARCHAR(50))

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='assessor_parlamentar')
    gabinete_eleitor: Mapped[List['GabineteEleitor']] = relationship('GabineteEleitor', uselist=True, back_populates='assessor_parlamentar')
    proposicao: Mapped[List['Proposicao']] = relationship('Proposicao', uselist=True, back_populates='assessor_parlamentar')


class AssinaturaDocumento(Base):
    __tablename__ = 'assinatura_documento'
    __table_args__ = (
        ForeignKeyConstraint(['cod_solicitante'], ['usuario.cod_usuario'], ondelete='RESTRICT', onupdate='RESTRICT', name='assinatura_documento_ibfk_2'),
        ForeignKeyConstraint(['cod_usuario'], ['usuario.cod_usuario'], ondelete='RESTRICT', name='assinatura_documento_ibfk_1'),
        Index('assinatura_documento_ibfk', 'cod_usuario'),
        Index('cod_solicitante', 'cod_solicitante'),
        Index('idx_cod_assinatura_doc', 'cod_assinatura_doc', 'codigo', 'tipo_doc', 'cod_usuario', unique=True),
        Index('ind_assinado', 'ind_assinado'),
        Index('ind_recusado', 'ind_recusado'),
        Index('tipo_doc', 'tipo_doc')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_assinatura_doc = mapped_column(VARCHAR(16), nullable=False)
    codigo = mapped_column(Integer, nullable=False)
    tipo_doc = mapped_column(VARCHAR(30), nullable=False)
    dat_solicitacao = mapped_column(DateTime, nullable=False)
    cod_usuario = mapped_column(Integer, nullable=False)
    ind_assinado = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_recusado = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_separado = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_prim_assinatura = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    anexo = mapped_column(Integer)
    cod_solicitante = mapped_column(Integer)
    dat_assinatura = mapped_column(DateTime)
    dat_recusa = mapped_column(DateTime)
    txt_motivo_recusa = mapped_column(TEXT)

    usuario: Mapped[Optional['Usuario']] = relationship('Usuario', foreign_keys=[cod_solicitante], back_populates='assinatura_documento')
    usuario_: Mapped['Usuario'] = relationship('Usuario', foreign_keys=[cod_usuario], back_populates='assinatura_documento_')


class Autor(Base):
    __tablename__ = 'autor'
    __table_args__ = (
        ForeignKeyConstraint(['cod_bancada'], ['bancada.cod_bancada'], ondelete='RESTRICT', name='autor_ibfk_1'),
        ForeignKeyConstraint(['cod_comissao'], ['comissao.cod_comissao'], ondelete='RESTRICT', name='autor_ibfk_2'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='autor_ibfk_3'),
        ForeignKeyConstraint(['cod_partido'], ['partido.cod_partido'], ondelete='RESTRICT', name='autor_ibfk_4'),
        ForeignKeyConstraint(['tip_autor'], ['tipo_autor.tip_autor'], ondelete='RESTRICT', onupdate='RESTRICT', name='autor_ibfk_5'),
        Index('idx_bancada', 'cod_bancada'),
        Index('idx_comissao', 'cod_comissao'),
        Index('idx_parlamentar', 'cod_parlamentar'),
        Index('idx_partido', 'cod_partido'),
        Index('idx_tip_autor', 'tip_autor'),
        Index('nom_autor', 'nom_autor')
    )

    cod_autor = mapped_column(Integer, primary_key=True)
    tip_autor = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_partido = mapped_column(Integer)
    cod_comissao = mapped_column(Integer)
    cod_bancada = mapped_column(Integer)
    cod_parlamentar = mapped_column(Integer)
    nom_autor = mapped_column(VARCHAR(50))
    des_cargo = mapped_column(VARCHAR(50))
    col_username = mapped_column(VARCHAR(50))
    end_email = mapped_column(VARCHAR(100))

    bancada: Mapped[Optional['Bancada']] = relationship('Bancada', back_populates='autor')
    comissao: Mapped[Optional['Comissao']] = relationship('Comissao', back_populates='autor')
    parlamentar: Mapped[Optional['Parlamentar']] = relationship('Parlamentar', back_populates='autor')
    partido: Mapped[Optional['Partido']] = relationship('Partido', back_populates='autor')
    tipo_autor: Mapped['TipoAutor'] = relationship('TipoAutor', back_populates='autor')
    autoria: Mapped[List['Autoria']] = relationship('Autoria', uselist=True, back_populates='autor')
    autoria_emenda: Mapped[List['AutoriaEmenda']] = relationship('AutoriaEmenda', uselist=True, back_populates='autor')
    autoria_substitutivo: Mapped[List['AutoriaSubstitutivo']] = relationship('AutoriaSubstitutivo', uselist=True, back_populates='autor')
    proposicao: Mapped[List['Proposicao']] = relationship('Proposicao', uselist=True, back_populates='autor')
    protocolo: Mapped[List['Protocolo']] = relationship('Protocolo', uselist=True, back_populates='autor')


class CientificacaoDocumento(Base):
    __tablename__ = 'cientificacao_documento'
    __table_args__ = (
        ForeignKeyConstraint(['cod_cientificado'], ['usuario.cod_usuario'], ondelete='RESTRICT', onupdate='RESTRICT', name='cientificacao_documento_ibfk_3'),
        ForeignKeyConstraint(['cod_cientificador'], ['usuario.cod_usuario'], ondelete='RESTRICT', onupdate='RESTRICT', name='cientificacao_documento_ibfk_2'),
        ForeignKeyConstraint(['cod_documento'], ['documento_administrativo.cod_documento'], ondelete='RESTRICT', onupdate='RESTRICT', name='cientificacao_documento_ibfk_1'),
        Index('cod_cientificado', 'cod_cientificado'),
        Index('cod_cientificador', 'cod_cientificador'),
        Index('cod_documento', 'cod_documento')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_documento = mapped_column(Integer, nullable=False)
    cod_cientificador = mapped_column(Integer, nullable=False)
    dat_envio = mapped_column(DateTime, nullable=False)
    cod_cientificado = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_expiracao = mapped_column(DateTime)
    dat_leitura = mapped_column(DateTime)

    usuario: Mapped['Usuario'] = relationship('Usuario', foreign_keys=[cod_cientificado], back_populates='cientificacao_documento')
    usuario_: Mapped['Usuario'] = relationship('Usuario', foreign_keys=[cod_cientificador], back_populates='cientificacao_documento_')
    documento_administrativo: Mapped['DocumentoAdministrativo'] = relationship('DocumentoAdministrativo', back_populates='cientificacao_documento')


class ComposicaoBancada(Base):
    __tablename__ = 'composicao_bancada'
    __table_args__ = (
        ForeignKeyConstraint(['cod_bancada'], ['bancada.cod_bancada'], ondelete='RESTRICT', name='composicao_bancada_ibfk_1'),
        ForeignKeyConstraint(['cod_cargo'], ['cargo_bancada.cod_cargo'], ondelete='RESTRICT', onupdate='RESTRICT', name='composicao_bancada_ibfk_5'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='composicao_bancada_ibfk_4'),
        ForeignKeyConstraint(['cod_periodo_comp'], ['periodo_comp_bancada.cod_periodo_comp'], ondelete='RESTRICT', name='composicao_bancada_ibfk_3'),
        Index('cod_periodo_comp', 'cod_periodo_comp'),
        Index('idx_bancada', 'cod_bancada'),
        Index('idx_cargo', 'cod_cargo'),
        Index('idx_parlamentar', 'cod_parlamentar')
    )

    cod_comp_bancada = mapped_column(Integer, primary_key=True)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    cod_bancada = mapped_column(Integer, nullable=False)
    cod_cargo = mapped_column(Integer, nullable=False)
    ind_titular = mapped_column(Integer, nullable=False)
    dat_designacao = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_periodo_comp = mapped_column(Integer)
    dat_desligamento = mapped_column(Date)
    des_motivo_desligamento = mapped_column(VARCHAR(150))
    obs_composicao = mapped_column(VARCHAR(150))

    bancada: Mapped['Bancada'] = relationship('Bancada', back_populates='composicao_bancada')
    cargo_bancada: Mapped['CargoBancada'] = relationship('CargoBancada', back_populates='composicao_bancada')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='composicao_bancada')
    periodo_comp_bancada: Mapped[Optional['PeriodoCompBancada']] = relationship('PeriodoCompBancada', back_populates='composicao_bancada')


class ComposicaoComissao(Base):
    __tablename__ = 'composicao_comissao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_cargo'], ['cargo_comissao.cod_cargo'], ondelete='RESTRICT', onupdate='RESTRICT', name='composicao_comissao_ibfk_5'),
        ForeignKeyConstraint(['cod_comissao'], ['comissao.cod_comissao'], ondelete='RESTRICT', onupdate='RESTRICT', name='composicao_comissao_ibfk_3'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], name='composicao_comissao_ibfk_1'),
        ForeignKeyConstraint(['cod_periodo_comp'], ['periodo_comp_comissao.cod_periodo_comp'], ondelete='RESTRICT', name='composicao_comissao_ibfk_4'),
        Index('idx_cargo', 'cod_cargo'),
        Index('idx_comissao', 'cod_comissao'),
        Index('idx_parlamentar', 'cod_parlamentar'),
        Index('idx_periodo_comp', 'cod_periodo_comp')
    )

    cod_comp_comissao = mapped_column(Integer, primary_key=True)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    cod_comissao = mapped_column(Integer, nullable=False)
    cod_periodo_comp = mapped_column(Integer, nullable=False)
    cod_cargo = mapped_column(Integer, nullable=False)
    ind_titular = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    dat_designacao = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_desligamento = mapped_column(Date)
    des_motivo_desligamento = mapped_column(VARCHAR(150))
    obs_composicao = mapped_column(VARCHAR(150))

    cargo_comissao: Mapped['CargoComissao'] = relationship('CargoComissao', back_populates='composicao_comissao')
    comissao: Mapped['Comissao'] = relationship('Comissao', back_populates='composicao_comissao')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='composicao_comissao')
    periodo_comp_comissao: Mapped['PeriodoCompComissao'] = relationship('PeriodoCompComissao', back_populates='composicao_comissao')


class ComposicaoMesa(Base):
    __tablename__ = 'composicao_mesa'
    __table_args__ = (
        ForeignKeyConstraint(['cod_cargo'], ['cargo_mesa.cod_cargo'], ondelete='RESTRICT', onupdate='RESTRICT', name='composicao_mesa_ibfk_5'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='composicao_mesa_ibfk_2'),
        ForeignKeyConstraint(['cod_periodo_comp'], ['periodo_comp_mesa.cod_periodo_comp'], ondelete='RESTRICT', name='composicao_mesa_ibfk_3'),
        ForeignKeyConstraint(['cod_sessao_leg'], ['sessao_legislativa.cod_sessao_leg'], ondelete='RESTRICT', name='composicao_mesa_ibfk_4'),
        Index('cod_sessao_leg', 'cod_sessao_leg'),
        Index('idx_cargo', 'cod_cargo'),
        Index('idx_parlamentar', 'cod_parlamentar'),
        Index('idx_periodo_comp', 'cod_periodo_comp')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    cod_periodo_comp = mapped_column(Integer, nullable=False)
    cod_cargo = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_sessao_leg = mapped_column(Integer)

    cargo_mesa: Mapped['CargoMesa'] = relationship('CargoMesa', back_populates='composicao_mesa')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='composicao_mesa')
    periodo_comp_mesa: Mapped['PeriodoCompMesa'] = relationship('PeriodoCompMesa', back_populates='composicao_mesa')
    sessao_legislativa: Mapped[Optional['SessaoLegislativa']] = relationship('SessaoLegislativa', back_populates='composicao_mesa')


class Dependente(Base):
    __tablename__ = 'dependente'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='dependente_ibfk_1'),
        ForeignKeyConstraint(['tip_dependente'], ['tipo_dependente.tip_dependente'], ondelete='RESTRICT', onupdate='RESTRICT', name='dependente_ibfk_2'),
        Index('idx_dep_parlam', 'tip_dependente', 'cod_parlamentar', 'ind_excluido'),
        Index('idx_dependente', 'tip_dependente'),
        Index('idx_parlamentar', 'cod_parlamentar')
    )

    cod_dependente = mapped_column(Integer, primary_key=True)
    tip_dependente = mapped_column(Integer, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    nom_dependente = mapped_column(VARCHAR(50))
    sex_dependente = mapped_column(CHAR(1))
    dat_nascimento = mapped_column(Date)
    num_cpf = mapped_column(VARCHAR(14))
    num_rg = mapped_column(VARCHAR(15))
    num_tit_eleitor = mapped_column(VARCHAR(15))

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='dependente')
    tipo_dependente: Mapped['TipoDependente'] = relationship('TipoDependente', back_populates='dependente')


class DespachoInicial(Base):
    __tablename__ = 'despacho_inicial'
    __table_args__ = (
        ForeignKeyConstraint(['cod_comissao'], ['comissao.cod_comissao'], ondelete='RESTRICT', name='despacho_inicial_ibfk_1'),
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='despacho_inicial_ibfk_2'),
        Index('idx_comissao', 'cod_comissao'),
        Index('idx_despinic_comissao', 'cod_materia', 'num_ordem', 'cod_comissao'),
        Index('idx_materia', 'cod_materia'),
        Index('idx_unique', 'cod_materia', 'num_ordem', unique=True)
    )

    id = mapped_column(Integer, primary_key=True)
    cod_materia = mapped_column(Integer, nullable=False)
    num_ordem = mapped_column(INTEGER, nullable=False)
    cod_comissao = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    comissao: Mapped['Comissao'] = relationship('Comissao', back_populates='despacho_inicial')
    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='despacho_inicial')


class DocumentoAcessorio(Base):
    __tablename__ = 'documento_acessorio'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='RESTRICT', name='documento_acessorio_ibfk_1'),
        ForeignKeyConstraint(['tip_documento'], ['tipo_documento.tip_documento'], ondelete='RESTRICT', name='documento_acessorio_ibfk_2'),
        Index('idx_ementa', 'txt_ementa'),
        Index('idx_materia', 'cod_materia'),
        Index('idx_tip_documento', 'tip_documento'),
        Index('ind_publico', 'ind_publico')
    )

    cod_documento = mapped_column(Integer, primary_key=True)
    cod_materia = mapped_column(Integer, nullable=False)
    tip_documento = mapped_column(Integer, nullable=False)
    ind_publico = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    ind_excluido = mapped_column(Integer, nullable=False)
    nom_documento = mapped_column(VARCHAR(250))
    dat_documento = mapped_column(DateTime)
    num_protocolo = mapped_column(Integer)
    nom_autor_documento = mapped_column(VARCHAR(250))
    txt_ementa = mapped_column(TEXT)
    txt_observacao = mapped_column(TEXT)
    txt_indexacao = mapped_column(TEXT)

    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='documento_acessorio')
    tipo_documento: Mapped['TipoDocumento'] = relationship('TipoDocumento', back_populates='documento_acessorio')
    peticao: Mapped[List['Peticao']] = relationship('Peticao', uselist=True, back_populates='documento_acessorio')
    materia_apresentada_sessao: Mapped[List['MateriaApresentadaSessao']] = relationship('MateriaApresentadaSessao', uselist=True, back_populates='documento_acessorio')


class DocumentoAcessorioAdministrativo(Base):
    __tablename__ = 'documento_acessorio_administrativo'
    __table_args__ = (
        ForeignKeyConstraint(['cod_documento'], ['documento_administrativo.cod_documento'], ondelete='RESTRICT', name='documento_acessorio_administrativo_ibfk_1'),
        ForeignKeyConstraint(['tip_documento'], ['tipo_documento_administrativo.tip_documento'], ondelete='RESTRICT', name='documento_acessorio_administrativo_ibfk_2'),
        Index('idx_assunto', 'txt_assunto'),
        Index('idx_autor_documento', 'nom_autor_documento'),
        Index('idx_dat_documento', 'dat_documento'),
        Index('idx_documento', 'cod_documento'),
        Index('idx_tip_documento', 'tip_documento')
    )

    cod_documento_acessorio = mapped_column(Integer, primary_key=True)
    cod_documento = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    tip_documento = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    nom_documento = mapped_column(VARCHAR(250))
    nom_arquivo = mapped_column(VARCHAR(100))
    dat_documento = mapped_column(DateTime)
    nom_autor_documento = mapped_column(VARCHAR(50))
    txt_assunto = mapped_column(TEXT)
    txt_indexacao = mapped_column(TEXT)

    documento_administrativo: Mapped['DocumentoAdministrativo'] = relationship('DocumentoAdministrativo', back_populates='documento_acessorio_administrativo')
    tipo_documento_administrativo: Mapped['TipoDocumentoAdministrativo'] = relationship('TipoDocumentoAdministrativo', back_populates='documento_acessorio_administrativo')


class DocumentoAdministrativoMateria(Base):
    __tablename__ = 'documento_administrativo_materia'
    __table_args__ = (
        ForeignKeyConstraint(['cod_documento'], ['documento_administrativo.cod_documento'], ondelete='CASCADE', name='documento_administrativo_materia_ibfk_1'),
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='documento_administrativo_materia_ibfk_2'),
        Index('idx_cod_documento', 'cod_documento'),
        Index('idx_cod_materia', 'cod_materia')
    )

    cod_vinculo = mapped_column(Integer, primary_key=True)
    cod_documento = mapped_column(Integer, nullable=False)
    cod_materia = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    documento_administrativo: Mapped['DocumentoAdministrativo'] = relationship('DocumentoAdministrativo', back_populates='documento_administrativo_materia')
    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='documento_administrativo_materia')


class DocumentoAdministrativoVinculado(Base):
    __tablename__ = 'documento_administrativo_vinculado'
    __table_args__ = (
        ForeignKeyConstraint(['cod_documento_vinculado'], ['documento_administrativo.cod_documento'], ondelete='CASCADE', name='documento_administrativo_vinculado_ibfk_1'),
        ForeignKeyConstraint(['cod_documento_vinculante'], ['documento_administrativo.cod_documento'], ondelete='CASCADE', name='documento_administrativo_vinculado_ibfk_2'),
        Index('idx_cod_documento', 'cod_documento_vinculante'),
        Index('idx_doc_vinculado', 'cod_documento_vinculado'),
        Index('idx_doc_vinculo', 'cod_documento_vinculante', 'cod_documento_vinculado', unique=True)
    )

    cod_vinculo = mapped_column(Integer, primary_key=True)
    cod_documento_vinculante = mapped_column(Integer, nullable=False)
    cod_documento_vinculado = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_vinculacao = mapped_column(DateTime)

    documento_administrativo: Mapped['DocumentoAdministrativo'] = relationship('DocumentoAdministrativo', foreign_keys=[cod_documento_vinculado], back_populates='documento_administrativo_vinculado')
    documento_administrativo_: Mapped['DocumentoAdministrativo'] = relationship('DocumentoAdministrativo', foreign_keys=[cod_documento_vinculante], back_populates='documento_administrativo_vinculado_')


class DocumentoComissao(Base):
    __tablename__ = 'documento_comissao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_comissao'], ['comissao.cod_comissao'], ondelete='RESTRICT', name='documento_comissao_ibfk_1'),
        Index('cod_comissao', 'cod_comissao'),
        Index('txt_descricao', 'txt_descricao')
    )

    cod_documento = mapped_column(Integer, primary_key=True)
    cod_comissao = mapped_column(Integer, nullable=False)
    dat_documento = mapped_column(Date, nullable=False)
    txt_descricao = mapped_column(VARCHAR(200), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    txt_observacao = mapped_column(VARCHAR(250))

    comissao: Mapped['Comissao'] = relationship('Comissao', back_populates='documento_comissao')


class Emenda(Base):
    __tablename__ = 'emenda'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='emenda_ibfk_2'),
        ForeignKeyConstraint(['tip_emenda'], ['tipo_emenda.tip_emenda'], ondelete='RESTRICT', name='emenda_ibfk_1'),
        Index('cod_autor', 'cod_autor'),
        Index('idx_cod_materia', 'cod_materia'),
        Index('idx_emenda', 'cod_emenda', 'tip_emenda', 'cod_materia'),
        Index('idx_tip_emenda', 'tip_emenda'),
        Index('idx_txt_ementa', 'txt_ementa')
    )

    cod_emenda = mapped_column(Integer, primary_key=True)
    tip_emenda = mapped_column(Integer, nullable=False)
    num_emenda = mapped_column(Integer, nullable=False)
    cod_materia = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_autor = mapped_column(Integer)
    num_protocolo = mapped_column(Integer)
    dat_apresentacao = mapped_column(Date)
    txt_ementa = mapped_column(TEXT)
    txt_observacao = mapped_column(VARCHAR(150))
    exc_pauta = mapped_column(Integer)

    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='emenda')
    tipo_emenda: Mapped['TipoEmenda'] = relationship('TipoEmenda', back_populates='emenda')
    autoria_emenda: Mapped[List['AutoriaEmenda']] = relationship('AutoriaEmenda', uselist=True, back_populates='emenda')
    proposicao: Mapped[List['Proposicao']] = relationship('Proposicao', uselist=True, back_populates='emenda')
    registro_votacao: Mapped[List['RegistroVotacao']] = relationship('RegistroVotacao', uselist=True, back_populates='emenda')
    materia_apresentada_sessao: Mapped[List['MateriaApresentadaSessao']] = relationship('MateriaApresentadaSessao', uselist=True, back_populates='emenda')


class Filiacao(Base):
    __tablename__ = 'filiacao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='filiacao_ibfk_1'),
        ForeignKeyConstraint(['cod_partido'], ['partido.cod_partido'], ondelete='RESTRICT', name='filiacao_ibfk_2'),
        Index('dat_desfiliacao', 'dat_desfiliacao'),
        Index('dat_filiacao', 'dat_filiacao'),
        Index('idx_parlamentar', 'cod_parlamentar'),
        Index('idx_partido', 'cod_partido')
    )

    id = mapped_column(Integer, primary_key=True)
    dat_filiacao = mapped_column(Date, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    cod_partido = mapped_column(Integer, nullable=False)
    dat_desfiliacao = mapped_column(Date)
    ind_excluido = mapped_column(Integer)

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='filiacao')
    partido: Mapped['Partido'] = relationship('Partido', back_populates='filiacao')


class Funcionario(Base):
    __tablename__ = 'funcionario'
    __table_args__ = (
        ForeignKeyConstraint(['cod_usuario'], ['usuario.cod_usuario'], ondelete='RESTRICT', name='funcionario_ibfk_1'),
        Index('cod_usuario', 'cod_usuario')
    )

    cod_funcionario = mapped_column(Integer, primary_key=True)
    nom_funcionario = mapped_column(VARCHAR(255), nullable=False)
    dat_cadastro = mapped_column(Date, nullable=False)
    ind_ativo = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_usuario = mapped_column(Integer)
    des_cargo = mapped_column(VARCHAR(255))

    usuario: Mapped[Optional['Usuario']] = relationship('Usuario', back_populates='funcionario')
    visita: Mapped[List['Visita']] = relationship('Visita', uselist=True, back_populates='funcionario')


class Mandato(Base):
    __tablename__ = 'mandato'
    __table_args__ = (
        ForeignKeyConstraint(['cod_coligacao'], ['coligacao.cod_coligacao'], ondelete='RESTRICT', name='mandato_ibfk_3'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='CASCADE', name='mandato_ibfk_1'),
        ForeignKeyConstraint(['num_legislatura'], ['legislatura.num_legislatura'], ondelete='RESTRICT', onupdate='RESTRICT', name='mandato_ibfk_5'),
        ForeignKeyConstraint(['tip_afastamento'], ['tipo_afastamento.tip_afastamento'], ondelete='RESTRICT', onupdate='RESTRICT', name='mandato_ibfk_4'),
        Index('idx_afastamento', 'tip_afastamento'),
        Index('idx_coligacao', 'cod_coligacao'),
        Index('idx_legislatura', 'num_legislatura'),
        Index('idx_mandato_legislatura', 'num_legislatura', 'cod_parlamentar', 'ind_excluido'),
        Index('idx_parlamentar', 'cod_parlamentar'),
        Index('tip_causa_fim_mandato', 'tip_causa_fim_mandato')
    )

    cod_mandato = mapped_column(Integer, primary_key=True)
    num_legislatura = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_parlamentar = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_titular = mapped_column(Integer, nullable=False, server_default=text("'1'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_coligacao = mapped_column(Integer)
    dat_inicio_mandato = mapped_column(Date)
    tip_causa_fim_mandato = mapped_column(Integer)
    dat_fim_mandato = mapped_column(Date)
    num_votos_recebidos = mapped_column(Integer)
    dat_expedicao_diploma = mapped_column(Date)
    tip_afastamento = mapped_column(Integer)
    txt_observacao = mapped_column(TEXT)

    coligacao: Mapped[Optional['Coligacao']] = relationship('Coligacao', back_populates='mandato')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='mandato')
    legislatura: Mapped['Legislatura'] = relationship('Legislatura', back_populates='mandato')
    tipo_afastamento: Mapped[Optional['TipoAfastamento']] = relationship('TipoAfastamento', back_populates='mandato')
    afastamento: Mapped[List['Afastamento']] = relationship('Afastamento', uselist=True, back_populates='mandato')


class NormaJuridica(Base):
    __tablename__ = 'norma_juridica'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='SET NULL', name='norma_juridica_ibfk_1'),
        ForeignKeyConstraint(['cod_situacao'], ['tipo_situacao_norma.tip_situacao_norma'], ondelete='SET NULL', onupdate='RESTRICT', name='norma_juridica_ibfk_2'),
        ForeignKeyConstraint(['tip_norma'], ['tipo_norma_juridica.tip_norma'], ondelete='RESTRICT', onupdate='RESTRICT', name='norma_juridica_ibfk_3'),
        Index('cod_assunto', 'cod_assunto'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_situacao', 'cod_situacao'),
        Index('dat_norma', 'dat_norma'),
        Index('idx_ano_numero', 'ano_norma', 'num_norma', 'ind_excluido'),
        Index('idx_busca', 'txt_ementa', 'txt_observacao', 'txt_indexacao'),
        Index('ind_publico', 'ind_publico'),
        Index('tip_norma', 'tip_norma')
    )

    cod_norma = mapped_column(Integer, primary_key=True)
    tip_norma = mapped_column(Integer, nullable=False)
    num_norma = mapped_column(Integer, nullable=False)
    ano_norma = mapped_column(Integer, nullable=False)
    timestamp = mapped_column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    ind_publico = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_materia = mapped_column(Integer)
    tip_esfera_federacao = mapped_column(CHAR(1))
    dat_norma = mapped_column(Date)
    dat_publicacao = mapped_column(Date)
    des_veiculo_publicacao = mapped_column(VARCHAR(50))
    num_pag_inicio_publ = mapped_column(Integer)
    num_pag_fim_publ = mapped_column(Integer)
    txt_ementa = mapped_column(TEXT)
    txt_indexacao = mapped_column(TEXT)
    txt_observacao = mapped_column(TEXT)
    ind_complemento = mapped_column(Integer)
    cod_assunto = mapped_column(CHAR(16))
    cod_situacao = mapped_column(Integer)
    dat_vigencia = mapped_column(Date)

    materia_legislativa: Mapped[Optional['MateriaLegislativa']] = relationship('MateriaLegislativa', back_populates='norma_juridica')
    tipo_situacao_norma: Mapped[Optional['TipoSituacaoNorma']] = relationship('TipoSituacaoNorma', back_populates='norma_juridica')
    tipo_norma_juridica: Mapped['TipoNormaJuridica'] = relationship('TipoNormaJuridica', back_populates='norma_juridica')
    anexo_norma: Mapped[List['AnexoNorma']] = relationship('AnexoNorma', uselist=True, back_populates='norma_juridica')
    legislacao_citada: Mapped[List['LegislacaoCitada']] = relationship('LegislacaoCitada', uselist=True, back_populates='norma_juridica')
    logradouro: Mapped[List['Logradouro']] = relationship('Logradouro', uselist=True, back_populates='norma_juridica')
    vinculo_norma_juridica: Mapped[List['VinculoNormaJuridica']] = relationship('VinculoNormaJuridica', uselist=True, foreign_keys='[VinculoNormaJuridica.cod_norma_referente]', back_populates='norma_juridica')
    vinculo_norma_juridica_: Mapped[List['VinculoNormaJuridica']] = relationship('VinculoNormaJuridica', uselist=True, foreign_keys='[VinculoNormaJuridica.cod_norma_referida]', back_populates='norma_juridica_')


class Numeracao(Base):
    __tablename__ = 'numeracao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='RESTRICT', name='numeracao_ibfk_1'),
        ForeignKeyConstraint(['tip_materia'], ['tipo_materia_legislativa.tip_materia'], ondelete='RESTRICT', name='numeracao_ibfk_2'),
        Index('cod_materia', 'cod_materia'),
        Index('idx_numer_identificacao', 'tip_materia', 'num_materia', 'ano_materia', 'ind_excluido'),
        Index('tip_materia', 'tip_materia')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_materia = mapped_column(Integer, nullable=False)
    num_ordem = mapped_column(Integer, nullable=False)
    tip_materia = mapped_column(Integer, nullable=False)
    num_materia = mapped_column(Integer, nullable=False)
    ano_materia = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_materia = mapped_column(Date)

    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='numeracao')
    tipo_materia_legislativa: Mapped['TipoMateriaLegislativa'] = relationship('TipoMateriaLegislativa', back_populates='numeracao')


class PeriodoSessao(Base):
    __tablename__ = 'periodo_sessao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_sessao_leg'], ['sessao_legislativa.cod_sessao_leg'], ondelete='RESTRICT', onupdate='RESTRICT', name='periodo_sessao_ibfk_1'),
        ForeignKeyConstraint(['num_legislatura'], ['legislatura.num_legislatura'], ondelete='RESTRICT', onupdate='RESTRICT', name='periodo_sessao_ibfk_2'),
        ForeignKeyConstraint(['tip_sessao'], ['tipo_sessao_plenaria.tip_sessao'], ondelete='RESTRICT', onupdate='RESTRICT', name='periodo_sessao_ibfk_3'),
        Index('dat_fim', 'dat_fim'),
        Index('dat_incio', 'dat_inicio'),
        Index('idx_legislatura', 'num_legislatura'),
        Index('idx_sessao_leg', 'cod_sessao_leg'),
        Index('idx_tip_sessao', 'tip_sessao'),
        Index('num_periodo', 'num_periodo'),
        Index('periodo', 'num_periodo', 'num_legislatura', 'cod_sessao_leg', 'tip_sessao', unique=True)
    )

    cod_periodo = mapped_column(Integer, primary_key=True)
    num_periodo = mapped_column(Integer, nullable=False)
    num_legislatura = mapped_column(Integer, nullable=False)
    cod_sessao_leg = mapped_column(Integer, nullable=False)
    tip_sessao = mapped_column(Integer, nullable=False)
    dat_inicio = mapped_column(Date, nullable=False)
    dat_fim = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))

    sessao_legislativa: Mapped['SessaoLegislativa'] = relationship('SessaoLegislativa', back_populates='periodo_sessao')
    legislatura: Mapped['Legislatura'] = relationship('Legislatura', back_populates='periodo_sessao')
    tipo_sessao_plenaria: Mapped['TipoSessaoPlenaria'] = relationship('TipoSessaoPlenaria', back_populates='periodo_sessao')
    sessao_plenaria: Mapped[List['SessaoPlenaria']] = relationship('SessaoPlenaria', uselist=True, back_populates='periodo_sessao')


class Relatoria(Base):
    __tablename__ = 'relatoria'
    __table_args__ = (
        ForeignKeyConstraint(['cod_comissao'], ['comissao.cod_comissao'], ondelete='RESTRICT', name='relatoria_ibfk_1'),
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='relatoria_ibfk_2'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='relatoria_ibfk_3'),
        ForeignKeyConstraint(['tip_fim_relatoria'], ['tipo_fim_relatoria.tip_fim_relatoria'], ondelete='RESTRICT', onupdate='RESTRICT', name='relatoria_ibfk_4'),
        Index('cod_comissao', 'cod_comissao'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('idx_relat_materia', 'cod_materia', 'cod_parlamentar', 'ind_excluido'),
        Index('num_protocolo', 'num_protocolo'),
        Index('tip_fim_relatoria', 'tip_fim_relatoria')
    )

    cod_relatoria = mapped_column(Integer, primary_key=True)
    cod_materia = mapped_column(Integer, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    num_ordem = mapped_column(Integer, nullable=False)
    dat_desig_relator = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    tip_fim_relatoria = mapped_column(Integer)
    cod_comissao = mapped_column(Integer)
    dat_destit_relator = mapped_column(DateTime)
    tip_apresentacao = mapped_column(CHAR(1))
    num_parecer = mapped_column(Integer)
    num_protocolo = mapped_column(Integer)
    ano_parecer = mapped_column(Integer)
    txt_parecer = mapped_column(TEXT)
    tip_conclusao = mapped_column(CHAR(1))

    comissao: Mapped[Optional['Comissao']] = relationship('Comissao', back_populates='relatoria')
    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='relatoria')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='relatoria')
    tipo_fim_relatoria: Mapped[Optional['TipoFimRelatoria']] = relationship('TipoFimRelatoria', back_populates='relatoria')
    parecer: Mapped[List['Parecer']] = relationship('Parecer', uselist=True, back_populates='relatoria')
    registro_votacao: Mapped[List['RegistroVotacao']] = relationship('RegistroVotacao', uselist=True, back_populates='relatoria')
    expediente_materia: Mapped[List['ExpedienteMateria']] = relationship('ExpedienteMateria', uselist=True, back_populates='relatoria')
    materia_apresentada_sessao: Mapped[List['MateriaApresentadaSessao']] = relationship('MateriaApresentadaSessao', uselist=True, back_populates='relatoria')
    ordem_dia: Mapped[List['OrdemDia']] = relationship('OrdemDia', uselist=True, back_populates='relatoria')


class ReuniaoComissao(Base):
    __tablename__ = 'reuniao_comissao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_comissao'], ['comissao.cod_comissao'], ondelete='RESTRICT', name='reuniao_comissao_ibfk_1'),
        Index('cod_comissao', 'cod_comissao')
    )

    cod_reuniao = mapped_column(Integer, primary_key=True)
    cod_comissao = mapped_column(Integer, nullable=False)
    num_reuniao = mapped_column(Integer, nullable=False)
    dat_inicio_reuniao = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    des_tipo_reuniao = mapped_column(VARCHAR(15))
    txt_tema = mapped_column(TEXT)
    hr_inicio_reuniao = mapped_column(VARCHAR(5))
    hr_fim_reuniao = mapped_column(VARCHAR(5))
    txt_observacao = mapped_column(TEXT)
    url_video = mapped_column(VARCHAR(150))

    comissao: Mapped['Comissao'] = relationship('Comissao', back_populates='reuniao_comissao')
    reuniao_comissao_pauta: Mapped[List['ReuniaoComissaoPauta']] = relationship('ReuniaoComissaoPauta', uselist=True, back_populates='reuniao_comissao')
    reuniao_comissao_presenca: Mapped[List['ReuniaoComissaoPresenca']] = relationship('ReuniaoComissaoPresenca', uselist=True, back_populates='reuniao_comissao')


class Substitutivo(Base):
    __tablename__ = 'substitutivo'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='substitutivo_ibfk_1'),
        Index('cod_autor', 'cod_autor'),
        Index('idx_cod_materia', 'cod_materia'),
        Index('idx_substitutivo', 'cod_substitutivo', 'cod_materia'),
        Index('idx_txt_ementa', 'txt_ementa'),
        Index('txt_observacao', 'txt_observacao')
    )

    cod_substitutivo = mapped_column(Integer, primary_key=True)
    num_substitutivo = mapped_column(Integer, nullable=False)
    cod_materia = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_autor = mapped_column(Integer)
    num_protocolo = mapped_column(Integer)
    dat_apresentacao = mapped_column(Date)
    txt_ementa = mapped_column(TEXT)
    txt_observacao = mapped_column(TEXT)

    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='substitutivo')
    autoria_substitutivo: Mapped[List['AutoriaSubstitutivo']] = relationship('AutoriaSubstitutivo', uselist=True, back_populates='substitutivo')
    proposicao: Mapped[List['Proposicao']] = relationship('Proposicao', uselist=True, back_populates='substitutivo')
    registro_votacao: Mapped[List['RegistroVotacao']] = relationship('RegistroVotacao', uselist=True, back_populates='substitutivo')
    materia_apresentada_sessao: Mapped[List['MateriaApresentadaSessao']] = relationship('MateriaApresentadaSessao', uselist=True, back_populates='substitutivo')


class UnidadeTramitacao(Base):
    __tablename__ = 'unidade_tramitacao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_comissao'], ['comissao.cod_comissao'], ondelete='RESTRICT', name='unidade_tramitacao_ibfk_1'),
        ForeignKeyConstraint(['cod_orgao'], ['orgao.cod_orgao'], ondelete='RESTRICT', name='unidade_tramitacao_ibfk_2'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='unidade_tramitacao_ibfk_3'),
        Index('cod_comissao', 'cod_comissao'),
        Index('cod_orgao', 'cod_orgao'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('idx_unidtramit_comissao', 'cod_comissao', 'ind_excluido'),
        Index('idx_unidtramit_orgao', 'cod_orgao', 'ind_excluido'),
        Index('idx_unidtramit_parlamentar', 'cod_parlamentar', 'ind_excluido'),
        Index('ind_adm', 'ind_adm'),
        Index('ind_adm_2', 'ind_adm'),
        Index('ind_leg', 'ind_leg'),
        Index('ind_leg_2', 'ind_leg')
    )

    cod_unid_tramitacao = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_comissao = mapped_column(Integer)
    cod_orgao = mapped_column(Integer)
    cod_parlamentar = mapped_column(Integer)
    ind_leg = mapped_column(Integer, server_default=text("'0'"))
    unid_dest_permitidas = mapped_column(TEXT)
    status_permitidos = mapped_column(TEXT)
    ind_adm = mapped_column(Integer, server_default=text("'0'"))
    status_adm_permitidos = mapped_column(TEXT)

    comissao: Mapped[Optional['Comissao']] = relationship('Comissao', back_populates='unidade_tramitacao')
    orgao: Mapped[Optional['Orgao']] = relationship('Orgao', back_populates='unidade_tramitacao')
    parlamentar: Mapped[Optional['Parlamentar']] = relationship('Parlamentar', back_populates='unidade_tramitacao')
    tramitacao: Mapped[List['Tramitacao']] = relationship('Tramitacao', uselist=True, foreign_keys='[Tramitacao.cod_unid_tram_dest]', back_populates='unidade_tramitacao')
    tramitacao_: Mapped[List['Tramitacao']] = relationship('Tramitacao', uselist=True, foreign_keys='[Tramitacao.cod_unid_tram_local]', back_populates='unidade_tramitacao_')
    tramitacao_administrativo: Mapped[List['TramitacaoAdministrativo']] = relationship('TramitacaoAdministrativo', uselist=True, foreign_keys='[TramitacaoAdministrativo.cod_unid_tram_dest]', back_populates='unidade_tramitacao')
    tramitacao_administrativo_: Mapped[List['TramitacaoAdministrativo']] = relationship('TramitacaoAdministrativo', uselist=True, foreign_keys='[TramitacaoAdministrativo.cod_unid_tram_local]', back_populates='unidade_tramitacao_')
    usuario_unid_tram: Mapped[List['UsuarioUnidTram']] = relationship('UsuarioUnidTram', uselist=True, back_populates='unidade_tramitacao')


class UsuarioPeticionamento(Base):
    __tablename__ = 'usuario_peticionamento'
    __table_args__ = (
        ForeignKeyConstraint(['cod_usuario'], ['usuario.cod_usuario'], ondelete='RESTRICT', name='usuario_peticionamento_ibfk_1'),
        ForeignKeyConstraint(['tip_peticionamento'], ['tipo_peticionamento.tip_peticionamento'], ondelete='RESTRICT', name='usuario_peticionamento_ibfk_2'),
        Index('idx_tip_peticionamento', 'tip_peticionamento'),
        Index('idx_usuario', 'cod_usuario')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_usuario = mapped_column(Integer, nullable=False)
    tip_peticionamento = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(TINYINT, nullable=False, server_default=text("'0'"))

    usuario: Mapped['Usuario'] = relationship('Usuario', back_populates='usuario_peticionamento')
    tipo_peticionamento: Mapped['TipoPeticionamento'] = relationship('TipoPeticionamento', back_populates='usuario_peticionamento')


class UsuarioTipoDocumento(Base):
    __tablename__ = 'usuario_tipo_documento'
    __table_args__ = (
        ForeignKeyConstraint(['cod_usuario'], ['usuario.cod_usuario'], ondelete='RESTRICT', name='usuario_tipo_documento_ibfk_1'),
        ForeignKeyConstraint(['tip_documento'], ['tipo_documento_administrativo.tip_documento'], ondelete='RESTRICT', onupdate='RESTRICT', name='usuario_tipo_documento_ibfk_2'),
        Index('idx_tip_documento', 'tip_documento'),
        Index('idx_usuario', 'cod_usuario')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_usuario = mapped_column(Integer, nullable=False)
    tip_documento = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))

    usuario: Mapped['Usuario'] = relationship('Usuario', back_populates='usuario_tipo_documento')
    tipo_documento_administrativo: Mapped['TipoDocumentoAdministrativo'] = relationship('TipoDocumentoAdministrativo', back_populates='usuario_tipo_documento')


class UsuarioConsultaDocumento(Base):
    __tablename__ = 'usuario_consulta_documento'
    __table_args__ = (
        ForeignKeyConstraint(['cod_usuario'], ['usuario.cod_usuario'], ondelete='RESTRICT', onupdate='RESTRICT', name='usuario_consulta_documento_ibfk_1'),
        ForeignKeyConstraint(['tip_documento'], ['tipo_documento_administrativo.tip_documento'], ondelete='RESTRICT', onupdate='RESTRICT', name='usuario_consulta_documento_ibfk_2'),
        Index('idx_usuario', 'cod_usuario'),
        Index('idx_tip_documento', 'tip_documento'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cod_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    tip_documento: Mapped[int] = mapped_column(Integer, nullable=False)
    ind_excluido: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("'0'")
    )

    # Relationships - CHANGED 'tipo_documento' to 'tipo_documento_administrativo'
    usuario: Mapped['Usuario'] = relationship('Usuario', back_populates='usuario_consulta_documento')
    tipo_documento_administrativo: Mapped['TipoDocumentoAdministrativo'] = relationship('TipoDocumentoAdministrativo', back_populates='usuario_consulta_documento'
    )

class Afastamento(Base):
    __tablename__ = 'afastamento'
    __table_args__ = (
        ForeignKeyConstraint(['cod_mandato'], ['mandato.cod_mandato'], ondelete='CASCADE', onupdate='RESTRICT', name='afastamento_ibfk_1'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='CASCADE', name='afastamento_ibfk_2'),
        ForeignKeyConstraint(['num_legislatura'], ['legislatura.num_legislatura'], ondelete='RESTRICT', onupdate='RESTRICT', name='afastamento_ibfk_6'),
        ForeignKeyConstraint(['tip_afastamento'], ['tipo_afastamento.tip_afastamento'], ondelete='RESTRICT', onupdate='RESTRICT', name='afastamento_ibfk_5'),
        Index('cod_mandato', 'cod_mandato'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_parlamentar_suplente', 'cod_parlamentar_suplente'),
        Index('idx__parlamentar_suplente', 'cod_parlamentar_suplente', 'num_legislatura'),
        Index('idx_afastamento_datas', 'cod_parlamentar', 'dat_inicio_afastamento', 'dat_fim_afastamento'),
        Index('idx_parlamentar_mandato', 'cod_parlamentar', 'num_legislatura'),
        Index('idx_tip_afastamento', 'tip_afastamento'),
        Index('num_legislatura', 'num_legislatura')
    )

    cod_afastamento = mapped_column(Integer, primary_key=True)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    cod_mandato = mapped_column(Integer, nullable=False)
    num_legislatura = mapped_column(Integer, nullable=False)
    tip_afastamento = mapped_column(Integer, nullable=False)
    dat_inicio_afastamento = mapped_column(Date, nullable=False)
    cod_parlamentar_suplente = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    dat_fim_afastamento = mapped_column(Date)
    txt_observacao = mapped_column(TEXT)

    mandato: Mapped['Mandato'] = relationship('Mandato', back_populates='afastamento')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='afastamento')
    legislatura: Mapped['Legislatura'] = relationship('Legislatura', back_populates='afastamento')
    tipo_afastamento: Mapped['TipoAfastamento'] = relationship('TipoAfastamento', back_populates='afastamento')


class AnexoNorma(Base):
    __tablename__ = 'anexo_norma'
    __table_args__ = (
        ForeignKeyConstraint(['cod_norma'], ['norma_juridica.cod_norma'], ondelete='CASCADE', name='anexo_norma_ibfk_1'),
        Index('cod_norma', 'cod_norma')
    )

    cod_anexo = mapped_column(Integer, primary_key=True)
    cod_norma = mapped_column(Integer, nullable=False)
    txt_descricao = mapped_column(VARCHAR(250), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    norma_juridica: Mapped['NormaJuridica'] = relationship('NormaJuridica', back_populates='anexo_norma')


class Autoria(Base):
    __tablename__ = 'autoria'
    __table_args__ = (
        ForeignKeyConstraint(['cod_autor'], ['autor.cod_autor'], ondelete='RESTRICT', onupdate='RESTRICT', name='autoria_ibfk_2'),
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='autoria_ibfk_1'),
        Index('idx_autor', 'cod_autor'),
        Index('idx_materia', 'cod_materia')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_autor = mapped_column(Integer, nullable=False)
    cod_materia = mapped_column(Integer, nullable=False)
    ind_primeiro_autor = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    autor: Mapped['Autor'] = relationship('Autor', back_populates='autoria')
    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='autoria')


class AutoriaEmenda(Base):
    __tablename__ = 'autoria_emenda'
    __table_args__ = (
        ForeignKeyConstraint(['cod_autor'], ['autor.cod_autor'], ondelete='RESTRICT', name='autoria_emenda_ibfk_1'),
        ForeignKeyConstraint(['cod_emenda'], ['emenda.cod_emenda'], ondelete='CASCADE', name='autoria_emenda_ibfk_2'),
        Index('idx_autor', 'cod_autor'),
        Index('idx_emenda', 'cod_emenda')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_autor = mapped_column(Integer, nullable=False)
    cod_emenda = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    autor: Mapped['Autor'] = relationship('Autor', back_populates='autoria_emenda')
    emenda: Mapped['Emenda'] = relationship('Emenda', back_populates='autoria_emenda')


class AutoriaSubstitutivo(Base):
    __tablename__ = 'autoria_substitutivo'
    __table_args__ = (
        ForeignKeyConstraint(['cod_autor'], ['autor.cod_autor'], ondelete='RESTRICT', name='autoria_substitutivo_ibfk_1'),
        ForeignKeyConstraint(['cod_substitutivo'], ['substitutivo.cod_substitutivo'], ondelete='CASCADE', name='autoria_substitutivo_ibfk_2'),
        Index('idx_autor', 'cod_autor'),
        Index('idx_substitutivo', 'cod_substitutivo')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_autor = mapped_column(Integer, nullable=False)
    cod_substitutivo = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)

    autor: Mapped['Autor'] = relationship('Autor', back_populates='autoria_substitutivo')
    substitutivo: Mapped['Substitutivo'] = relationship('Substitutivo', back_populates='autoria_substitutivo')


class GabineteEleitor(Base):
    __tablename__ = 'gabinete_eleitor'
    __table_args__ = (
        ForeignKeyConstraint(['cod_assessor'], ['assessor_parlamentar.cod_assessor'], ondelete='RESTRICT', onupdate='RESTRICT', name='gabinete_eleitor_ibfk_2'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='gabinete_eleitor_ibfk_1'),
        Index('cod_assessor', 'cod_assessor'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('des_local_trabalho', 'des_local_trabalho'),
        Index('des_profissao', 'des_profissao'),
        Index('end_residencial', 'end_residencial'),
        Index('nom_bairro', 'nom_bairro'),
        Index('nom_eleitor', 'nom_eleitor'),
        Index('nom_localidade', 'nom_localidade'),
        Index('sex_eleitor', 'sex_eleitor')
    )

    cod_eleitor = mapped_column(Integer, primary_key=True)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    dat_cadastro = mapped_column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    dat_atualizacao = mapped_column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    nom_eleitor = mapped_column(VARCHAR(100))
    sex_eleitor = mapped_column(CHAR(1))
    dat_nascimento = mapped_column(Date)
    des_estado_civil = mapped_column(VARCHAR(15))
    doc_identidade = mapped_column(VARCHAR(50))
    num_cpf = mapped_column(VARCHAR(50))
    txt_classe = mapped_column(VARCHAR(50))
    des_profissao = mapped_column(VARCHAR(100))
    des_escolaridade = mapped_column(VARCHAR(50))
    num_tit_eleitor = mapped_column(VARCHAR(50))
    end_residencial = mapped_column(VARCHAR(100))
    nom_bairro = mapped_column(VARCHAR(150))
    num_cep = mapped_column(VARCHAR(15))
    nom_localidade = mapped_column(VARCHAR(100))
    sgl_uf = mapped_column(VARCHAR(5))
    num_telefone = mapped_column(VARCHAR(45))
    num_celular = mapped_column(VARCHAR(45))
    end_email = mapped_column(VARCHAR(45))
    nom_conjuge = mapped_column(VARCHAR(100))
    num_dependentes = mapped_column(TINYTEXT)
    txt_observacao = mapped_column(TEXT)
    des_local_trabalho = mapped_column(VARCHAR(100))
    cod_assessor = mapped_column(Integer)

    assessor_parlamentar: Mapped[Optional['AssessorParlamentar']] = relationship('AssessorParlamentar', back_populates='gabinete_eleitor')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='gabinete_eleitor')
    gabinete_atendimento: Mapped[List['GabineteAtendimento']] = relationship('GabineteAtendimento', uselist=True, back_populates='gabinete_eleitor')


class LegislacaoCitada(Base):
    __tablename__ = 'legislacao_citada'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='legislacao_citada_ibfk_1'),
        ForeignKeyConstraint(['cod_norma'], ['norma_juridica.cod_norma'], ondelete='CASCADE', name='legislacao_citada_ibfk_2'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_norma', 'cod_norma')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_materia = mapped_column(Integer, nullable=False)
    cod_norma = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    des_disposicoes = mapped_column(VARCHAR(15))
    des_parte = mapped_column(VARCHAR(8))
    des_livro = mapped_column(VARCHAR(7))
    des_titulo = mapped_column(VARCHAR(7))
    des_capitulo = mapped_column(VARCHAR(7))
    des_secao = mapped_column(VARCHAR(7))
    des_subsecao = mapped_column(VARCHAR(7))
    des_artigo = mapped_column(VARCHAR(4))
    des_paragrafo = mapped_column(CHAR(3))
    des_inciso = mapped_column(VARCHAR(10))
    des_alinea = mapped_column(CHAR(3))
    des_item = mapped_column(CHAR(3))

    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='legislacao_citada')
    norma_juridica: Mapped['NormaJuridica'] = relationship('NormaJuridica', back_populates='legislacao_citada')


class Logradouro(Base):
    __tablename__ = 'logradouro'
    __table_args__ = (
        ForeignKeyConstraint(['cod_localidade'], ['localidade.cod_localidade'], ondelete='RESTRICT', name='logradouro_ibfk_1'),
        ForeignKeyConstraint(['cod_norma'], ['norma_juridica.cod_norma'], ondelete='CASCADE', name='logradouro_ibfk_2'),
        Index('cod_localidade', 'cod_localidade'),
        Index('logradouro_ibfk_2', 'cod_norma'),
        Index('nom_logradouro', 'nom_logradouro'),
        Index('num_cep', 'num_cep')
    )

    cod_logradouro = mapped_column(Integer, primary_key=True)
    nom_logradouro = mapped_column(VARCHAR(100), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    nom_bairro = mapped_column(VARCHAR(100))
    num_cep = mapped_column(VARCHAR(9))
    cod_localidade = mapped_column(Integer)
    cod_norma = mapped_column(Integer)

    localidade: Mapped[Optional['Localidade']] = relationship('Localidade', back_populates='logradouro')
    norma_juridica: Mapped[Optional['NormaJuridica']] = relationship('NormaJuridica', back_populates='logradouro')


class Parecer(Base):
    __tablename__ = 'parecer'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='parecer_ibfk_1'),
        ForeignKeyConstraint(['cod_relatoria'], ['relatoria.cod_relatoria'], ondelete='CASCADE', name='parecer_ibfk_2'),
        Index('cod_materia', 'cod_materia'),
        Index('idx_parecer_materia', 'cod_materia', 'ind_excluido')
    )

    cod_relatoria = mapped_column(Integer, primary_key=True, nullable=False)
    cod_materia = mapped_column(Integer, primary_key=True, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    num_parecer = mapped_column(Integer)
    ano_parecer = mapped_column(Integer)
    tip_conclusao = mapped_column(CHAR(3))
    tip_apresentacao = mapped_column(CHAR(1))
    txt_parecer = mapped_column(TEXT)

    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='parecer')
    relatoria: Mapped['Relatoria'] = relationship('Relatoria', back_populates='parecer')


class Peticao(Base):
    __tablename__ = 'peticao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_doc_acessorio'], ['documento_acessorio.cod_documento'], ondelete='RESTRICT', name='peticao_ibfk_4'),
        ForeignKeyConstraint(['cod_documento'], ['documento_administrativo.cod_documento'], ondelete='RESTRICT', name='peticao_ibfk_5'),
        ForeignKeyConstraint(['cod_documento_vinculado'], ['documento_administrativo.cod_documento'], ondelete='RESTRICT', onupdate='RESTRICT', name='peticao_ibfk_7'),
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='RESTRICT', name='peticao_ibfk_3'),
        ForeignKeyConstraint(['cod_usuario'], ['usuario.cod_usuario'], ondelete='RESTRICT', name='peticao_ibfk_2'),
        ForeignKeyConstraint(['tip_peticionamento'], ['tipo_peticionamento.tip_peticionamento'], ondelete='RESTRICT', name='peticao_ibfk_1'),
        Index('cod_doc_acessorio', 'cod_doc_acessorio'),
        Index('cod_documento', 'cod_documento'),
        Index('cod_documento_vinculado', 'cod_documento_vinculado'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_norma', 'cod_norma'),
        Index('cod_usuario', 'cod_usuario'),
        Index('dat_envio', 'dat_envio'),
        Index('dat_norma', 'dat_norma'),
        Index('dat_recebimento', 'dat_recebimento'),
        Index('ind_excluido', 'ind_excluido'),
        Index('num_norma', 'num_norma'),
        Index('num_protocolo', 'num_protocolo'),
        Index('tip_peticionamento', 'tip_peticionamento')
    )

    cod_peticao = mapped_column(Integer, primary_key=True)
    tip_peticionamento = mapped_column(Integer, nullable=False)
    txt_descricao = mapped_column(TEXT, nullable=False)
    cod_usuario = mapped_column(Integer, nullable=False)
    timestamp = mapped_column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_materia = mapped_column(Integer)
    cod_doc_acessorio = mapped_column(Integer)
    cod_documento = mapped_column(Integer)
    cod_documento_vinculado = mapped_column(Integer)
    cod_norma = mapped_column(Integer)
    num_norma = mapped_column(Integer)
    ano_norma = mapped_column(Integer)
    dat_norma = mapped_column(Date)
    dat_publicacao = mapped_column(Date)
    des_veiculo_publicacao = mapped_column(VARCHAR(50))
    num_pag_inicio_publ = mapped_column(Integer)
    num_pag_fim_publ = mapped_column(Integer)
    dat_envio = mapped_column(DateTime)
    dat_recebimento = mapped_column(DateTime)
    num_protocolo = mapped_column(Integer)
    txt_observacao = mapped_column(MEDIUMTEXT)
    cod_unid_tram_dest = mapped_column(Integer)

    documento_acessorio: Mapped[Optional['DocumentoAcessorio']] = relationship('DocumentoAcessorio', back_populates='peticao')
    documento_administrativo: Mapped[Optional['DocumentoAdministrativo']] = relationship('DocumentoAdministrativo', foreign_keys=[cod_documento], back_populates='peticao')
    documento_administrativo_: Mapped[Optional['DocumentoAdministrativo']] = relationship('DocumentoAdministrativo', foreign_keys=[cod_documento_vinculado], back_populates='peticao_')
    materia_legislativa: Mapped[Optional['MateriaLegislativa']] = relationship('MateriaLegislativa', back_populates='peticao')
    usuario: Mapped['Usuario'] = relationship('Usuario', back_populates='peticao')
    tipo_peticionamento: Mapped['TipoPeticionamento'] = relationship('TipoPeticionamento', back_populates='peticao')


class Proposicao(Base):
    __tablename__ = 'proposicao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_assessor'], ['assessor_parlamentar.cod_assessor'], ondelete='RESTRICT', onupdate='RESTRICT', name='proposicao_ibfk_7'),
        ForeignKeyConstraint(['cod_assunto'], ['assunto_proposicao.cod_assunto'], ondelete='RESTRICT', onupdate='RESTRICT', name='proposicao_ibfk_6'),
        ForeignKeyConstraint(['cod_autor'], ['autor.cod_autor'], ondelete='RESTRICT', name='proposicao_ibfk_2'),
        ForeignKeyConstraint(['cod_emenda'], ['emenda.cod_emenda'], ondelete='SET NULL', name='proposicao_ibfk_1'),
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='SET NULL', name='proposicao_ibfk_3'),
        ForeignKeyConstraint(['cod_revisor'], ['usuario.cod_usuario'], ondelete='RESTRICT', onupdate='RESTRICT', name='proposicao_ibfk_8'),
        ForeignKeyConstraint(['cod_substitutivo'], ['substitutivo.cod_substitutivo'], ondelete='SET NULL', name='proposicao_ibfk_4'),
        ForeignKeyConstraint(['tip_proposicao'], ['tipo_proposicao.tip_proposicao'], ondelete='RESTRICT', name='proposicao_ibfk_5'),
        Index('cod_assessor', 'cod_assessor'),
        Index('cod_assunto', 'cod_assunto'),
        Index('cod_autor', 'cod_autor'),
        Index('cod_emenda', 'cod_emenda'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_parecer', 'cod_parecer'),
        Index('cod_revisor', 'cod_revisor'),
        Index('cod_substitutivo', 'cod_substitutivo'),
        Index('idx_prop_autor', 'dat_envio', 'dat_recebimento', 'ind_excluido'),
        Index('tip_proposicao', 'tip_proposicao')
    )

    cod_proposicao = mapped_column(Integer, primary_key=True)
    cod_autor = mapped_column(Integer, nullable=False)
    tip_proposicao = mapped_column(Integer, nullable=False)
    txt_descricao = mapped_column(TEXT, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_materia = mapped_column(Integer)
    dat_envio = mapped_column(DateTime)
    dat_recebimento = mapped_column(DateTime)
    cod_mat_ou_doc = mapped_column(Integer)
    cod_emenda = mapped_column(Integer)
    cod_substitutivo = mapped_column(Integer)
    cod_parecer = mapped_column(Integer)
    dat_solicitacao_devolucao = mapped_column(DateTime)
    dat_devolucao = mapped_column(DateTime)
    txt_justif_devolucao = mapped_column(TEXT)
    txt_observacao = mapped_column(TEXT)
    cod_assessor = mapped_column(Integer)
    cod_assunto = mapped_column(Integer)
    cod_revisor = mapped_column(Integer)
    # novos campos
    txt_justificativa = mapped_column(TEXT)
    num_cep = mapped_column(VARCHAR(9), nullable=True)
    nom_logradouro = mapped_column(VARCHAR(200), nullable=True)
    nom_bairro = mapped_column(VARCHAR(100), nullable=True)
    nom_cidade = mapped_column(VARCHAR(100), nullable=True)
    sgl_uf = mapped_column(VARCHAR(2), nullable=True)
    complemento_endereco = mapped_column(VARCHAR(100), nullable=True)  # se quiser complementar
    dat_criacao = mapped_column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

    assessor_parlamentar: Mapped[Optional['AssessorParlamentar']] = relationship('AssessorParlamentar', back_populates='proposicao')
    assunto_proposicao: Mapped[Optional['AssuntoProposicao']] = relationship('AssuntoProposicao', back_populates='proposicao')
    autor: Mapped['Autor'] = relationship('Autor', back_populates='proposicao')
    emenda: Mapped[Optional['Emenda']] = relationship('Emenda', back_populates='proposicao')
    materia_legislativa: Mapped[Optional['MateriaLegislativa']] = relationship('MateriaLegislativa', back_populates='proposicao')
    usuario: Mapped[Optional['Usuario']] = relationship('Usuario', back_populates='proposicao')
    substitutivo: Mapped[Optional['Substitutivo']] = relationship('Substitutivo', back_populates='proposicao')
    tipo_proposicao: Mapped['TipoProposicao'] = relationship('TipoProposicao', back_populates='proposicao')
    destinatario_oficio: Mapped[List['DestinatarioOficio']] = relationship('DestinatarioOficio', uselist=True, back_populates='proposicao')
    proposicao_geocode: Mapped[List['ProposicaoGeocode']] = relationship('ProposicaoGeocode', uselist=True, back_populates='proposicao')


class Protocolo(Base):
    __tablename__ = 'protocolo'
    __table_args__ = (
        ForeignKeyConstraint(['cod_autor'], ['autor.cod_autor'], ondelete='RESTRICT', name='protocolo_ibfk_1'),
        ForeignKeyConstraint(['cod_materia_principal'], ['materia_legislativa.cod_materia'], ondelete='SET NULL', name='protocolo_ibfk_2'),
        Index('ano_protocolo', 'ano_protocolo'),
        Index('cod_autor', 'cod_autor'),
        Index('cod_materia_principal', 'cod_materia_principal'),
        Index('codigo_acesso', 'codigo_acesso'),
        Index('dat_protocolo', 'dat_protocolo'),
        Index('idx_busca_protocolo', 'txt_assunto_ementa', 'txt_observacao'),
        Index('idx_num_protocolo', 'num_protocolo', 'ano_protocolo', unique=True),
        Index('tip_documento', 'tip_documento'),
        Index('tip_materia', 'tip_materia'),
        Index('tip_processo', 'tip_processo'),
        Index('tip_protocolo', 'tip_protocolo'),
        Index('txt_interessado', 'txt_interessado')
    )

    cod_protocolo = mapped_column(INTEGER(7), primary_key=True)
    ano_protocolo = mapped_column(Integer, nullable=False)
    dat_protocolo = mapped_column(Date, nullable=False)
    hor_protocolo = mapped_column(Time, nullable=False, server_default=text("'00:00:00'"))
    dat_timestamp = mapped_column(TIMESTAMP, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    tip_protocolo = mapped_column(Integer, nullable=False)
    ind_anulado = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    num_protocolo = mapped_column(INTEGER(7))
    tip_processo = mapped_column(Integer)
    txt_interessado = mapped_column(VARCHAR(60))
    cod_autor = mapped_column(Integer)
    cod_entidade = mapped_column(Integer)
    txt_assunto_ementa = mapped_column(TEXT)
    tip_documento = mapped_column(Integer)
    tip_materia = mapped_column(Integer)
    tip_natureza_materia = mapped_column(Integer)
    cod_materia_principal = mapped_column(Integer)
    num_paginas = mapped_column(Integer)
    txt_observacao = mapped_column(TEXT)
    txt_user_protocolo = mapped_column(VARCHAR(20))
    txt_user_anulacao = mapped_column(VARCHAR(20))
    txt_ip_anulacao = mapped_column(VARCHAR(15))
    txt_just_anulacao = mapped_column(VARCHAR(400))
    timestamp_anulacao = mapped_column(DateTime)
    codigo_acesso = mapped_column(VARCHAR(18))

    autor: Mapped[Optional['Autor']] = relationship('Autor', back_populates='protocolo')
    materia_legislativa: Mapped[Optional['MateriaLegislativa']] = relationship('MateriaLegislativa', back_populates='protocolo')


class RegistroVotacao(Base):
    __tablename__ = 'registro_votacao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_emenda'], ['emenda.cod_emenda'], ondelete='RESTRICT', name='registro_votacao_ibfk_1'),
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='RESTRICT', name='registro_votacao_ibfk_2'),
        ForeignKeyConstraint(['cod_parecer'], ['relatoria.cod_relatoria'], ondelete='RESTRICT', onupdate='RESTRICT', name='registro_votacao_ibfk_3'),
        ForeignKeyConstraint(['cod_substitutivo'], ['substitutivo.cod_substitutivo'], ondelete='RESTRICT', name='registro_votacao_ibfk_4'),
        Index('cod_emenda', 'cod_emenda'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_ordem', 'cod_ordem'),
        Index('cod_parecer', 'cod_parecer'),
        Index('cod_subemenda', 'cod_subemenda'),
        Index('cod_substitutivo', 'cod_substitutivo'),
        Index('idx_unique', 'cod_materia', 'cod_ordem', 'cod_emenda', 'cod_substitutivo', unique=True),
        Index('tip_resultado_votacao', 'tip_resultado_votacao')
    )

    cod_votacao = mapped_column(Integer, primary_key=True)
    tip_resultado_votacao = mapped_column(INTEGER, nullable=False)
    cod_materia = mapped_column(Integer, nullable=False)
    cod_ordem = mapped_column(Integer, nullable=False)
    num_votos_sim = mapped_column(INTEGER, nullable=False)
    num_votos_nao = mapped_column(INTEGER, nullable=False)
    num_abstencao = mapped_column(INTEGER, nullable=False)
    ind_excluido = mapped_column(INTEGER, nullable=False)
    cod_parecer = mapped_column(Integer)
    cod_emenda = mapped_column(Integer)
    cod_subemenda = mapped_column(Integer)
    cod_substitutivo = mapped_column(Integer)
    num_ausentes = mapped_column(INTEGER)
    txt_observacao = mapped_column(TEXT)
    txt_obs_anterior = mapped_column(TEXT)

    emenda: Mapped[Optional['Emenda']] = relationship('Emenda', back_populates='registro_votacao')
    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='registro_votacao')
    relatoria: Mapped[Optional['Relatoria']] = relationship('Relatoria', back_populates='registro_votacao')
    substitutivo: Mapped[Optional['Substitutivo']] = relationship('Substitutivo', back_populates='registro_votacao')
    registro_votacao_parlamentar: Mapped[List['RegistroVotacaoParlamentar']] = relationship('RegistroVotacaoParlamentar', uselist=True, back_populates='registro_votacao')


class ReuniaoComissaoPauta(Base):
    __tablename__ = 'reuniao_comissao_pauta'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='RESTRICT', onupdate='RESTRICT', name='reuniao_comissao_pauta_ibfk_2'),
        ForeignKeyConstraint(['cod_relator'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', onupdate='RESTRICT', name='reuniao_comissao_pauta_ibfk_3'),
        ForeignKeyConstraint(['cod_reuniao'], ['reuniao_comissao.cod_reuniao'], ondelete='RESTRICT', onupdate='RESTRICT', name='reuniao_comissao_pauta_ibfk_1'),
        Index('cod_emenda', 'cod_emenda'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_parecer', 'cod_parecer'),
        Index('cod_relator', 'cod_relator'),
        Index('cod_reuniao', 'cod_reuniao'),
        Index('cod_substitutivo', 'cod_substitutivo'),
        Index('tip_resultado_votacao', 'tip_resultado_votacao')
    )

    cod_item = mapped_column(Integer, primary_key=True)
    cod_reuniao = mapped_column(Integer, nullable=False)
    num_ordem = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_materia = mapped_column(Integer)
    cod_emenda = mapped_column(Integer)
    cod_substitutivo = mapped_column(Integer)
    cod_parecer = mapped_column(Integer)
    cod_relator = mapped_column(Integer)
    tip_resultado_votacao = mapped_column(INTEGER)
    txt_observacao = mapped_column(TEXT)

    materia_legislativa: Mapped[Optional['MateriaLegislativa']] = relationship('MateriaLegislativa', back_populates='reuniao_comissao_pauta')
    parlamentar: Mapped[Optional['Parlamentar']] = relationship('Parlamentar', back_populates='reuniao_comissao_pauta')
    reuniao_comissao: Mapped['ReuniaoComissao'] = relationship('ReuniaoComissao', back_populates='reuniao_comissao_pauta')


class ReuniaoComissaoPresenca(Base):
    __tablename__ = 'reuniao_comissao_presenca'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', onupdate='RESTRICT', name='reuniao_comissao_presenca_ibfk_1'),
        ForeignKeyConstraint(['cod_reuniao'], ['reuniao_comissao.cod_reuniao'], ondelete='RESTRICT', onupdate='RESTRICT', name='reuniao_comissao_presenca_ibfk_2'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_reuniao', 'cod_reuniao'),
        Index('idx_reuniao_parlamentar', 'cod_reuniao', 'cod_parlamentar', unique=True)
    )

    id = mapped_column(Integer, primary_key=True)
    cod_reuniao = mapped_column(Integer, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='reuniao_comissao_presenca')
    reuniao_comissao: Mapped['ReuniaoComissao'] = relationship('ReuniaoComissao', back_populates='reuniao_comissao_presenca')


class SessaoPlenaria(Base):
    __tablename__ = 'sessao_plenaria'
    __table_args__ = (
        ForeignKeyConstraint(['cod_periodo_sessao'], ['periodo_sessao.cod_periodo'], ondelete='RESTRICT', onupdate='RESTRICT', name='sessao_plenaria_ibfk_4'),
        ForeignKeyConstraint(['cod_sessao_leg'], ['sessao_legislativa.cod_sessao_leg'], ondelete='RESTRICT', name='sessao_plenaria_ibfk_1'),
        ForeignKeyConstraint(['num_legislatura'], ['legislatura.num_legislatura'], ondelete='RESTRICT', onupdate='RESTRICT', name='sessao_plenaria_ibfk_3'),
        ForeignKeyConstraint(['tip_sessao'], ['tipo_sessao_plenaria.tip_sessao'], ondelete='RESTRICT', onupdate='RESTRICT', name='sessao_plenaria_ibfk_5'),
        Index('cod_periodo_sessao', 'cod_periodo_sessao'),
        Index('cod_sessao_leg', 'cod_sessao_leg'),
        Index('dat_inicio_sessao', 'dat_inicio_sessao'),
        Index('num_legislatura', 'num_legislatura'),
        Index('num_sessao_plen', 'num_sessao_plen'),
        Index('tip_sessao', 'tip_sessao')
    )

    cod_sessao_plen = mapped_column(Integer, primary_key=True)
    tip_sessao = mapped_column(Integer, nullable=False)
    cod_sessao_leg = mapped_column(Integer, nullable=False)
    num_legislatura = mapped_column(Integer, nullable=False)
    dat_inicio_sessao = mapped_column(Date, nullable=False)
    num_sessao_plen = mapped_column(INTEGER, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    num_tip_sessao = mapped_column(Integer)
    cod_periodo_sessao = mapped_column(Integer)
    dia_sessao = mapped_column(VARCHAR(15))
    hr_inicio_sessao = mapped_column(VARCHAR(5))
    hr_fim_sessao = mapped_column(VARCHAR(5))
    dat_fim_sessao = mapped_column(Date)
    url_fotos = mapped_column(VARCHAR(150))
    url_audio = mapped_column(VARCHAR(150))
    url_video = mapped_column(VARCHAR(150))
    numero_ata = mapped_column(Integer)

    periodo_sessao: Mapped[Optional['PeriodoSessao']] = relationship('PeriodoSessao', back_populates='sessao_plenaria')
    sessao_legislativa: Mapped['SessaoLegislativa'] = relationship('SessaoLegislativa', back_populates='sessao_plenaria')
    legislatura: Mapped['Legislatura'] = relationship('Legislatura', back_populates='sessao_plenaria')
    tipo_sessao_plenaria: Mapped['TipoSessaoPlenaria'] = relationship('TipoSessaoPlenaria', back_populates='sessao_plenaria')
    encerramento_presenca: Mapped[List['EncerramentoPresenca']] = relationship('EncerramentoPresenca', uselist=True, back_populates='sessao_plenaria')
    expediente_materia: Mapped[List['ExpedienteMateria']] = relationship('ExpedienteMateria', uselist=True, back_populates='sessao_plenaria')
    expediente_presenca: Mapped[List['ExpedientePresenca']] = relationship('ExpedientePresenca', uselist=True, back_populates='sessao_plenaria')
    expediente_sessao_plenaria: Mapped[List['ExpedienteSessaoPlenaria']] = relationship('ExpedienteSessaoPlenaria', uselist=True, back_populates='sessao_plenaria')
    liderancas_partidarias: Mapped[List['LiderancasPartidarias']] = relationship('LiderancasPartidarias', uselist=True, back_populates='sessao_plenaria')
    materia_apresentada_sessao: Mapped[List['MateriaApresentadaSessao']] = relationship('MateriaApresentadaSessao', uselist=True, back_populates='sessao_plenaria')
    mesa_sessao_plenaria: Mapped[List['MesaSessaoPlenaria']] = relationship('MesaSessaoPlenaria', uselist=True, back_populates='sessao_plenaria')
    oradores: Mapped[List['Oradores']] = relationship('Oradores', uselist=True, back_populates='sessao_plenaria')
    oradores_expediente: Mapped[List['OradoresExpediente']] = relationship('OradoresExpediente', uselist=True, back_populates='sessao_plenaria')
    ordem_dia: Mapped[List['OrdemDia']] = relationship('OrdemDia', uselist=True, back_populates='sessao_plenaria')
    ordem_dia_presenca: Mapped[List['OrdemDiaPresenca']] = relationship('OrdemDiaPresenca', uselist=True, back_populates='sessao_plenaria')
    sessao_plenaria_painel: Mapped[List['SessaoPlenariaPainel']] = relationship('SessaoPlenariaPainel', uselist=True, back_populates='sessao_plenaria')
    sessao_plenaria_presenca: Mapped[List['SessaoPlenariaPresenca']] = relationship('SessaoPlenariaPresenca', uselist=True, back_populates='sessao_plenaria')


class Tramitacao(Base):
    __tablename__ = 'tramitacao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='CASCADE', name='tramitacao_ibfk_1'),
        ForeignKeyConstraint(['cod_status'], ['status_tramitacao.cod_status'], ondelete='RESTRICT', name='tramitacao_ibfk_2'),
        ForeignKeyConstraint(['cod_unid_tram_dest'], ['unidade_tramitacao.cod_unid_tramitacao'], ondelete='RESTRICT', name='tramitacao_ibfk_4'),
        ForeignKeyConstraint(['cod_unid_tram_local'], ['unidade_tramitacao.cod_unid_tramitacao'], ondelete='RESTRICT', name='tramitacao_ibfk_3'),
        ForeignKeyConstraint(['cod_usuario_dest'], ['usuario.cod_usuario'], ondelete='SET NULL', name='tramitacao_ibfk_6'),
        ForeignKeyConstraint(['cod_usuario_local'], ['usuario.cod_usuario'], ondelete='RESTRICT', name='tramitacao_ibfk_5'),
        ForeignKeyConstraint(['cod_usuario_visualiza'], ['usuario.cod_usuario'], ondelete='RESTRICT', onupdate='RESTRICT', name='tramitacao_ibfk_7'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_status', 'cod_status'),
        Index('cod_unid_tram_dest', 'cod_unid_tram_dest'),
        Index('cod_unid_tram_local', 'cod_unid_tram_local'),
        Index('cod_usuario_dest', 'cod_usuario_dest'),
        Index('cod_usuario_local', 'cod_usuario_local'),
        Index('cod_usuario_visualiza', 'cod_usuario_visualiza'),
        Index('idx_tramit_ultmat', 'ind_ult_tramitacao', 'dat_tramitacao', 'cod_materia', 'ind_excluido'),
        Index('sgl_turno', 'sgl_turno')
    )

    cod_tramitacao = mapped_column(Integer, primary_key=True)
    cod_materia = mapped_column(Integer, nullable=False)
    ind_ult_tramitacao = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_urgencia = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_status = mapped_column(Integer)
    dat_tramitacao = mapped_column(DateTime)
    cod_unid_tram_local = mapped_column(Integer)
    cod_usuario_local = mapped_column(Integer)
    dat_encaminha = mapped_column(DateTime)
    cod_unid_tram_dest = mapped_column(Integer)
    cod_usuario_dest = mapped_column(Integer)
    dat_recebimento = mapped_column(DateTime)
    sgl_turno = mapped_column(CHAR(1))
    txt_tramitacao = mapped_column(TEXT)
    dat_fim_prazo = mapped_column(Date)
    dat_visualizacao = mapped_column(DateTime)
    cod_usuario_visualiza = mapped_column(Integer)

    materia_legislativa: Mapped['MateriaLegislativa'] = relationship('MateriaLegislativa', back_populates='tramitacao')
    status_tramitacao: Mapped[Optional['StatusTramitacao']] = relationship('StatusTramitacao', back_populates='tramitacao')
    unidade_tramitacao: Mapped[Optional['UnidadeTramitacao']] = relationship('UnidadeTramitacao', foreign_keys=[cod_unid_tram_dest], back_populates='tramitacao')
    unidade_tramitacao_: Mapped[Optional['UnidadeTramitacao']] = relationship('UnidadeTramitacao', foreign_keys=[cod_unid_tram_local], back_populates='tramitacao_')
    usuario: Mapped[Optional['Usuario']] = relationship('Usuario', foreign_keys=[cod_usuario_dest], back_populates='tramitacao')
    usuario_: Mapped[Optional['Usuario']] = relationship('Usuario', foreign_keys=[cod_usuario_local], back_populates='tramitacao_')
    usuario1: Mapped[Optional['Usuario']] = relationship('Usuario', foreign_keys=[cod_usuario_visualiza], back_populates='tramitacao1')


class TramitacaoAdministrativo(Base):
    __tablename__ = 'tramitacao_administrativo'
    __table_args__ = (
        ForeignKeyConstraint(['cod_documento'], ['documento_administrativo.cod_documento'], ondelete='CASCADE', name='tramitacao_administrativo_ibfk_1'),
        ForeignKeyConstraint(['cod_status'], ['status_tramitacao_administrativo.cod_status'], ondelete='RESTRICT', name='tramitacao_administrativo_ibfk_2'),
        ForeignKeyConstraint(['cod_unid_tram_dest'], ['unidade_tramitacao.cod_unid_tramitacao'], ondelete='RESTRICT', name='tramitacao_administrativo_ibfk_3'),
        ForeignKeyConstraint(['cod_unid_tram_local'], ['unidade_tramitacao.cod_unid_tramitacao'], ondelete='RESTRICT', name='tramitacao_administrativo_ibfk_4'),
        ForeignKeyConstraint(['cod_usuario_dest'], ['usuario.cod_usuario'], ondelete='SET NULL', name='tramitacao_administrativo_ibfk_6'),
        ForeignKeyConstraint(['cod_usuario_local'], ['usuario.cod_usuario'], ondelete='RESTRICT', name='tramitacao_administrativo_ibfk_5'),
        ForeignKeyConstraint(['cod_usuario_visualiza'], ['usuario.cod_usuario'], ondelete='RESTRICT', onupdate='RESTRICT', name='tramitacao_administrativo_ibfk_7'),
        Index('cod_documento', 'cod_documento'),
        Index('cod_status', 'cod_status'),
        Index('cod_unid_tram_dest', 'cod_unid_tram_dest'),
        Index('cod_unid_tram_local', 'cod_unid_tram_local'),
        Index('cod_usuario_dest', 'cod_usuario_dest'),
        Index('cod_usuario_local', 'cod_usuario_local'),
        Index('cod_usuario_visualiza', 'cod_usuario_visualiza'),
        Index('tramitacao_ind1', 'ind_ult_tramitacao')
    )

    cod_tramitacao = mapped_column(Integer, primary_key=True)
    cod_documento = mapped_column(Integer, nullable=False)
    ind_ult_tramitacao = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_tramitacao = mapped_column(DateTime)
    cod_unid_tram_local = mapped_column(Integer)
    cod_usuario_local = mapped_column(Integer)
    dat_encaminha = mapped_column(DateTime)
    cod_unid_tram_dest = mapped_column(Integer)
    cod_usuario_dest = mapped_column(Integer)
    dat_recebimento = mapped_column(DateTime)
    cod_status = mapped_column(Integer)
    txt_tramitacao = mapped_column(TEXT)
    dat_fim_prazo = mapped_column(Date)
    dat_visualizacao = mapped_column(DateTime)
    cod_usuario_visualiza = mapped_column(Integer)

    documento_administrativo: Mapped['DocumentoAdministrativo'] = relationship('DocumentoAdministrativo', back_populates='tramitacao_administrativo')
    status_tramitacao_administrativo: Mapped[Optional['StatusTramitacaoAdministrativo']] = relationship('StatusTramitacaoAdministrativo', back_populates='tramitacao_administrativo')
    unidade_tramitacao: Mapped[Optional['UnidadeTramitacao']] = relationship('UnidadeTramitacao', foreign_keys=[cod_unid_tram_dest], back_populates='tramitacao_administrativo')
    unidade_tramitacao_: Mapped[Optional['UnidadeTramitacao']] = relationship('UnidadeTramitacao', foreign_keys=[cod_unid_tram_local], back_populates='tramitacao_administrativo_')
    usuario: Mapped[Optional['Usuario']] = relationship('Usuario', foreign_keys=[cod_usuario_dest], back_populates='tramitacao_administrativo')
    usuario_: Mapped[Optional['Usuario']] = relationship('Usuario', foreign_keys=[cod_usuario_local], back_populates='tramitacao_administrativo_')
    usuario1: Mapped[Optional['Usuario']] = relationship('Usuario', foreign_keys=[cod_usuario_visualiza], back_populates='tramitacao_administrativo1')


class UsuarioUnidTram(Base):
    __tablename__ = 'usuario_unid_tram'
    __table_args__ = (
        ForeignKeyConstraint(['cod_unid_tramitacao'], ['unidade_tramitacao.cod_unid_tramitacao'], ondelete='CASCADE', name='usuario_unid_tram_ibfk_1'),
        ForeignKeyConstraint(['cod_usuario'], ['usuario.cod_usuario'], ondelete='CASCADE', name='usuario_unid_tram_ibfk_2'),
        Index('idx_unid_tramitacao', 'cod_unid_tramitacao'),
        Index('idx_usuario', 'cod_usuario')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_usuario = mapped_column(Integer, nullable=False)
    cod_unid_tramitacao = mapped_column(Integer, nullable=False)
    ind_responsavel = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))

    unidade_tramitacao: Mapped['UnidadeTramitacao'] = relationship('UnidadeTramitacao', back_populates='usuario_unid_tram')
    usuario: Mapped['Usuario'] = relationship('Usuario', back_populates='usuario_unid_tram')


class VinculoNormaJuridica(Base):
    __tablename__ = 'vinculo_norma_juridica'
    __table_args__ = (
        ForeignKeyConstraint(['cod_norma_referente'], ['norma_juridica.cod_norma'], ondelete='CASCADE', name='vinculo_norma_juridica_ibfk_1'),
        ForeignKeyConstraint(['cod_norma_referida'], ['norma_juridica.cod_norma'], ondelete='CASCADE', name='vinculo_norma_juridica_ibfk_2'),
        Index('cod_norma_referente', 'cod_norma_referente'),
        Index('cod_norma_referida', 'cod_norma_referida'),
        Index('idx_vnj_norma_referente', 'cod_norma_referente', 'cod_norma_referida', 'ind_excluido'),
        Index('idx_vnj_norma_referida', 'cod_norma_referida', 'cod_norma_referente', 'ind_excluido'),
        Index('tip_vinculo', 'tip_vinculo')
    )

    cod_vinculo = mapped_column(Integer, primary_key=True)
    cod_norma_referente = mapped_column(Integer, nullable=False)
    cod_norma_referida = mapped_column(Integer)
    tip_vinculo = mapped_column(CHAR(1))
    txt_observacao_vinculo = mapped_column(VARCHAR(250))
    ind_excluido = mapped_column(Integer, server_default=text("'0'"))

    norma_juridica: Mapped['NormaJuridica'] = relationship('NormaJuridica', foreign_keys=[cod_norma_referente], back_populates='vinculo_norma_juridica')
    norma_juridica_: Mapped[Optional['NormaJuridica']] = relationship('NormaJuridica', foreign_keys=[cod_norma_referida], back_populates='vinculo_norma_juridica_')


class Visita(Base):
    __tablename__ = 'visita'
    __table_args__ = (
        ForeignKeyConstraint(['cod_funcionario'], ['funcionario.cod_funcionario'], ondelete='RESTRICT', onupdate='RESTRICT', name='visita_ibfk_3'),
        ForeignKeyConstraint(['cod_pessoa'], ['pessoa.cod_pessoa'], ondelete='CASCADE', name='visita_ibfk_2'),
        Index('cod_funcionario', 'cod_funcionario'),
        Index('cod_pessoa', 'cod_pessoa'),
        Index('dat_entrada', 'dat_entrada'),
        Index('des_situacao', 'des_situacao')
    )

    cod_visita = mapped_column(Integer, primary_key=True)
    cod_pessoa = mapped_column(Integer, nullable=False)
    dat_entrada = mapped_column(DateTime, nullable=False)
    cod_funcionario = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    num_cracha = mapped_column(Integer)
    dat_saida = mapped_column(DateTime)
    txt_atendimento = mapped_column(TEXT)
    des_situacao = mapped_column(VARCHAR(20))
    dat_solucao = mapped_column(Date)
    txt_observacao = mapped_column(TEXT)

    funcionario: Mapped['Funcionario'] = relationship('Funcionario', back_populates='visita')
    pessoa: Mapped['Pessoa'] = relationship('Pessoa', back_populates='visita')


class DestinatarioOficio(Base):
    __tablename__ = 'destinatario_oficio'
    __table_args__ = (
        ForeignKeyConstraint(['cod_documento'], ['documento_administrativo.cod_documento'], ondelete='RESTRICT', onupdate='RESTRICT', name='destinatario_oficio_ibfk_1'),
        ForeignKeyConstraint(['cod_instituicao'], ['instituicao.cod_instituicao'], ondelete='RESTRICT', onupdate='RESTRICT', name='destinatario_oficio_ibfk_2'),
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='RESTRICT', onupdate='RESTRICT', name='destinatario_oficio_ibfk_3'),
        ForeignKeyConstraint(['cod_proposicao'], ['proposicao.cod_proposicao'], ondelete='RESTRICT', onupdate='RESTRICT', name='destinatario_oficio_ibfk_4'),
        ForeignKeyConstraint(['cod_usuario'], ['usuario.cod_usuario'], ondelete='RESTRICT', onupdate='RESTRICT', name='destinatario_oficio_ibfk_5'),
        Index('cod_usuario', 'cod_usuario'),
        Index('idx_cod_documento', 'cod_documento'),
        Index('idx_cod_instituicao', 'cod_instituicao'),
        Index('idx_cod_materia', 'cod_materia'),
        Index('idx_cod_proposicao', 'cod_proposicao')
    )

    cod_destinatario = mapped_column(Integer, primary_key=True)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_materia = mapped_column(Integer)
    cod_proposicao = mapped_column(Integer)
    cod_documento = mapped_column(Integer)
    cod_instituicao = mapped_column(Integer)
    nom_destinatario = mapped_column(VARCHAR(300))
    end_email = mapped_column(VARCHAR(100))
    dat_envio = mapped_column(DateTime)
    cod_usuario = mapped_column(Integer)

    documento_administrativo: Mapped[Optional['DocumentoAdministrativo']] = relationship('DocumentoAdministrativo', back_populates='destinatario_oficio')
    instituicao: Mapped[Optional['Instituicao']] = relationship('Instituicao', back_populates='destinatario_oficio')
    materia_legislativa: Mapped[Optional['MateriaLegislativa']] = relationship('MateriaLegislativa', back_populates='destinatario_oficio')
    proposicao: Mapped[Optional['Proposicao']] = relationship('Proposicao', back_populates='destinatario_oficio')
    usuario: Mapped[Optional['Usuario']] = relationship('Usuario', back_populates='destinatario_oficio')


class EncerramentoPresenca(Base):
    __tablename__ = 'encerramento_presenca'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='encerramento_presenca_ibfk_1'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='CASCADE', name='encerramento_presenca_ibfk_2'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_sessao_plen', 'cod_sessao_plen'),
        Index('dat_ordem', 'dat_ordem'),
        Index('idx_sessao_parlamentar', 'cod_sessao_plen', 'cod_parlamentar', unique=True)
    )

    cod_presenca_encerramento = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_parlamentar = mapped_column(Integer, nullable=False)
    dat_ordem = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='encerramento_presenca')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='encerramento_presenca')


class ExpedienteMateria(Base):
    __tablename__ = 'expediente_materia'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='RESTRICT', name='expediente_materia_ibfk_1'),
        ForeignKeyConstraint(['cod_parecer'], ['relatoria.cod_relatoria'], ondelete='RESTRICT', onupdate='RESTRICT', name='expediente_materia_ibfk_2'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='CASCADE', name='expediente_materia_ibfk_3'),
        ForeignKeyConstraint(['tip_quorum'], ['quorum_votacao.cod_quorum'], ondelete='RESTRICT', name='expediente_materia_ibfk_4'),
        ForeignKeyConstraint(['tip_turno'], ['turno_discussao.cod_turno'], ondelete='RESTRICT', onupdate='RESTRICT', name='expediente_materia_ibfk_6'),
        ForeignKeyConstraint(['tip_votacao'], ['tipo_votacao.tip_votacao'], ondelete='RESTRICT', name='expediente_materia_ibfk_5'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_parecer', 'cod_parecer'),
        Index('cod_sessao_plen', 'cod_sessao_plen'),
        Index('idx_exped_datord', 'dat_ordem', 'ind_excluido'),
        Index('tip_quorum', 'tip_quorum'),
        Index('tip_turno', 'tip_turno'),
        Index('tip_votacao', 'tip_votacao')
    )

    cod_ordem = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False)
    dat_ordem = mapped_column(Date, nullable=False)
    tip_votacao = mapped_column(Integer, nullable=False)
    tip_quorum = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_materia = mapped_column(Integer)
    cod_parecer = mapped_column(Integer)
    txt_observacao = mapped_column(TEXT)
    num_ordem = mapped_column(Integer)
    txt_resultado = mapped_column(TEXT)
    tip_turno = mapped_column(Integer)

    materia_legislativa: Mapped[Optional['MateriaLegislativa']] = relationship('MateriaLegislativa', back_populates='expediente_materia')
    relatoria: Mapped[Optional['Relatoria']] = relationship('Relatoria', back_populates='expediente_materia')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='expediente_materia')
    quorum_votacao: Mapped['QuorumVotacao'] = relationship('QuorumVotacao', back_populates='expediente_materia')
    turno_discussao: Mapped[Optional['TurnoDiscussao']] = relationship('TurnoDiscussao', back_populates='expediente_materia')
    tipo_votacao: Mapped['TipoVotacao'] = relationship('TipoVotacao', back_populates='expediente_materia')
    expediente_discussao: Mapped[List['ExpedienteDiscussao']] = relationship('ExpedienteDiscussao', uselist=True, back_populates='expediente_materia')


class ExpedientePresenca(Base):
    __tablename__ = 'expediente_presenca'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='expediente_presenca_ibfk_1'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='CASCADE', name='expediente_presenca_ibfk_2'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_sessao_plen', 'cod_sessao_plen'),
        Index('dat_ordem', 'dat_ordem', 'ind_excluido'),
        Index('idx_sessao_parlamentar', 'cod_sessao_plen', 'cod_parlamentar', unique=True)
    )

    cod_presenca_expediente = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_parlamentar = mapped_column(Integer, nullable=False)
    dat_ordem = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='expediente_presenca')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='expediente_presenca')


class ExpedienteSessaoPlenaria(Base):
    __tablename__ = 'expediente_sessao_plenaria'
    __table_args__ = (
        ForeignKeyConstraint(['cod_expediente'], ['tipo_expediente.cod_expediente'], ondelete='RESTRICT', onupdate='RESTRICT', name='expediente_sessao_plenaria_ibfk_2'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='RESTRICT', onupdate='RESTRICT', name='expediente_sessao_plenaria_ibfk_1'),
        Index('cod_expediente', 'cod_expediente'),
        Index('cod_sessao_plen', 'cod_sessao_plen')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False)
    cod_expediente = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    txt_expediente = mapped_column(TEXT)

    tipo_expediente: Mapped['TipoExpediente'] = relationship('TipoExpediente', back_populates='expediente_sessao_plenaria')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='expediente_sessao_plenaria')


class GabineteAtendimento(Base):
    __tablename__ = 'gabinete_atendimento'
    __table_args__ = (
        ForeignKeyConstraint(['cod_eleitor'], ['gabinete_eleitor.cod_eleitor'], ondelete='CASCADE', onupdate='CASCADE', name='gabinete_atendimento_ibfk_1'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='CASCADE', onupdate='CASCADE', name='gabinete_atendimento_ibfk_2'),
        Index('idx_assunto', 'txt_assunto'),
        Index('idx_eleitor', 'cod_eleitor'),
        Index('idx_parlamentar', 'cod_parlamentar'),
        Index('idx_resultado', 'txt_resultado')
    )

    cod_atendimento = mapped_column(Integer, primary_key=True)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    cod_eleitor = mapped_column(Integer, nullable=False)
    dat_atendimento = mapped_column(Date, nullable=False)
    txt_assunto = mapped_column(VARCHAR(255), nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    dat_resultado = mapped_column(Date)
    txt_resultado = mapped_column(VARCHAR(255))
    nom_atendente = mapped_column(VARCHAR(100))
    txt_status = mapped_column(VARCHAR(50))

    gabinete_eleitor: Mapped['GabineteEleitor'] = relationship('GabineteEleitor', back_populates='gabinete_atendimento')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='gabinete_atendimento')


class LiderancasPartidarias(Base):
    __tablename__ = 'liderancas_partidarias'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='liderancas_partidarias_ibfk_1'),
        ForeignKeyConstraint(['cod_partido'], ['partido.cod_partido'], ondelete='RESTRICT', name='liderancas_partidarias_ibfk_2'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='RESTRICT', name='liderancas_partidarias_ibfk_3'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_partido', 'cod_partido'),
        Index('cod_sessao_plen', 'cod_sessao_plen'),
        Index('idx_num_ordem', 'cod_sessao_plen', 'num_ordem', 'ind_excluido', unique=True)
    )

    id = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    cod_partido = mapped_column(Integer, nullable=False)
    num_ordem = mapped_column(TINYINT, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    url_discurso = mapped_column(VARCHAR(150))

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='liderancas_partidarias')
    partido: Mapped['Partido'] = relationship('Partido', back_populates='liderancas_partidarias')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='liderancas_partidarias')


class MateriaApresentadaSessao(Base):
    __tablename__ = 'materia_apresentada_sessao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_doc_acessorio'], ['documento_acessorio.cod_documento'], ondelete='RESTRICT', name='materia_apresentada_sessao_ibfk_2'),
        ForeignKeyConstraint(['cod_documento'], ['documento_administrativo.cod_documento'], ondelete='RESTRICT', name='materia_apresentada_sessao_ibfk_1'),
        ForeignKeyConstraint(['cod_emenda'], ['emenda.cod_emenda'], ondelete='RESTRICT', name='materia_apresentada_sessao_ibfk_7'),
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='RESTRICT', name='materia_apresentada_sessao_ibfk_3'),
        ForeignKeyConstraint(['cod_parecer'], ['relatoria.cod_relatoria'], ondelete='RESTRICT', onupdate='RESTRICT', name='materia_apresentada_sessao_ibfk_4'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='RESTRICT', name='materia_apresentada_sessao_ibfk_6'),
        ForeignKeyConstraint(['cod_substitutivo'], ['substitutivo.cod_substitutivo'], ondelete='RESTRICT', name='materia_apresentada_sessao_ibfk_5'),
        Index('cod_doc_acessorio', 'cod_doc_acessorio'),
        Index('cod_emenda', 'cod_emenda'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_materia_2', 'cod_materia'),
        Index('cod_parecer', 'cod_parecer'),
        Index('cod_sessao_plen', 'cod_sessao_plen'),
        Index('cod_substitutivo', 'cod_substitutivo'),
        Index('fk_cod_materia', 'cod_materia'),
        Index('idx_apres_datord', 'dat_ordem'),
        Index('idx_cod_documento', 'cod_documento')
    )

    cod_ordem = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False)
    dat_ordem = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_materia = mapped_column(Integer)
    cod_emenda = mapped_column(Integer)
    cod_substitutivo = mapped_column(Integer)
    cod_parecer = mapped_column(Integer)
    cod_doc_acessorio = mapped_column(Integer)
    cod_documento = mapped_column(Integer)
    txt_observacao = mapped_column(TEXT)
    num_ordem = mapped_column(Integer)

    documento_acessorio: Mapped[Optional['DocumentoAcessorio']] = relationship('DocumentoAcessorio', back_populates='materia_apresentada_sessao')
    documento_administrativo: Mapped[Optional['DocumentoAdministrativo']] = relationship('DocumentoAdministrativo', back_populates='materia_apresentada_sessao')
    emenda: Mapped[Optional['Emenda']] = relationship('Emenda', back_populates='materia_apresentada_sessao')
    materia_legislativa: Mapped[Optional['MateriaLegislativa']] = relationship('MateriaLegislativa', back_populates='materia_apresentada_sessao')
    relatoria: Mapped[Optional['Relatoria']] = relationship('Relatoria', back_populates='materia_apresentada_sessao')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='materia_apresentada_sessao')
    substitutivo: Mapped[Optional['Substitutivo']] = relationship('Substitutivo', back_populates='materia_apresentada_sessao')


class MesaSessaoPlenaria(Base):
    __tablename__ = 'mesa_sessao_plenaria'
    __table_args__ = (
        ForeignKeyConstraint(['cod_cargo'], ['cargo_mesa.cod_cargo'], ondelete='RESTRICT', onupdate='RESTRICT', name='mesa_sessao_plenaria_ibfk_5'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', onupdate='RESTRICT', name='mesa_sessao_plenaria_ibfk_2'),
        ForeignKeyConstraint(['cod_sessao_leg'], ['sessao_legislativa.cod_sessao_leg'], ondelete='RESTRICT', onupdate='RESTRICT', name='mesa_sessao_plenaria_ibfk_3'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='RESTRICT', onupdate='RESTRICT', name='mesa_sessao_plenaria_ibfk_4'),
        Index('cod_cargo', 'cod_cargo'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_sessao_leg', 'cod_sessao_leg'),
        Index('cod_sessao_plen', 'cod_sessao_plen')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_cargo = mapped_column(Integer, nullable=False)
    cod_sessao_leg = mapped_column(Integer, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    cod_sessao_plen = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(INTEGER)

    cargo_mesa: Mapped['CargoMesa'] = relationship('CargoMesa', back_populates='mesa_sessao_plenaria')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='mesa_sessao_plenaria')
    sessao_legislativa: Mapped['SessaoLegislativa'] = relationship('SessaoLegislativa', back_populates='mesa_sessao_plenaria')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='mesa_sessao_plenaria')


class Oradores(Base):
    __tablename__ = 'oradores'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='oradores_ibfk_2'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='CASCADE', name='oradores_ibfk_1'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_sessao_plen', 'cod_sessao_plen'),
        Index('idx_num_ordem', 'cod_sessao_plen', 'num_ordem', 'ind_excluido', unique=True)
    )

    id = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    num_ordem = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    url_discurso = mapped_column(VARCHAR(150))

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='oradores')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='oradores')


class OradoresExpediente(Base):
    __tablename__ = 'oradores_expediente'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='oradores_expediente_ibfk_2'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='CASCADE', name='oradores_expediente_ibfk_1'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_sessao_plen', 'cod_sessao_plen'),
        Index('idx_num_ordem', 'cod_sessao_plen', 'num_ordem', 'ind_excluido', unique=True)
    )

    id = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    num_ordem = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    url_discurso = mapped_column(VARCHAR(150))

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='oradores_expediente')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='oradores_expediente')


class OrdemDia(Base):
    __tablename__ = 'ordem_dia'
    __table_args__ = (
        ForeignKeyConstraint(['cod_materia'], ['materia_legislativa.cod_materia'], ondelete='RESTRICT', name='ordem_dia_ibfk_1'),
        ForeignKeyConstraint(['cod_parecer'], ['relatoria.cod_relatoria'], ondelete='RESTRICT', onupdate='RESTRICT', name='ordem_dia_ibfk_6'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='CASCADE', name='ordem_dia_ibfk_2'),
        ForeignKeyConstraint(['tip_quorum'], ['quorum_votacao.cod_quorum'], ondelete='RESTRICT', name='ordem_dia_ibfk_3'),
        ForeignKeyConstraint(['tip_turno'], ['turno_discussao.cod_turno'], ondelete='RESTRICT', name='ordem_dia_ibfk_5'),
        ForeignKeyConstraint(['tip_votacao'], ['tipo_votacao.tip_votacao'], ondelete='RESTRICT', name='ordem_dia_ibfk_4'),
        Index('cod_materia', 'cod_materia'),
        Index('cod_sessao_plen', 'cod_sessao_plen'),
        Index('idx_cod_parecer', 'cod_parecer'),
        Index('idx_dat_ordem', 'dat_ordem'),
        Index('num_ordem', 'num_ordem'),
        Index('tip_quorum', 'tip_quorum'),
        Index('tip_turno', 'tip_turno'),
        Index('tip_votacao', 'tip_votacao')
    )

    cod_ordem = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False)
    dat_ordem = mapped_column(Date, nullable=False)
    tip_votacao = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False)
    cod_materia = mapped_column(Integer)
    cod_parecer = mapped_column(Integer)
    txt_observacao = mapped_column(TEXT)
    num_ordem = mapped_column(Integer)
    txt_resultado = mapped_column(TEXT)
    tip_turno = mapped_column(Integer)
    tip_quorum = mapped_column(Integer)
    urgencia = mapped_column(Integer)
    tipo_discussao_ordem = mapped_column(Integer)

    materia_legislativa: Mapped[Optional['MateriaLegislativa']] = relationship('MateriaLegislativa', back_populates='ordem_dia')
    relatoria: Mapped[Optional['Relatoria']] = relationship('Relatoria', back_populates='ordem_dia')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='ordem_dia')
    quorum_votacao: Mapped[Optional['QuorumVotacao']] = relationship('QuorumVotacao', back_populates='ordem_dia')
    turno_discussao: Mapped[Optional['TurnoDiscussao']] = relationship('TurnoDiscussao', back_populates='ordem_dia')
    tipo_votacao: Mapped['TipoVotacao'] = relationship('TipoVotacao', back_populates='ordem_dia')
    ordem_dia_discussao: Mapped[List['OrdemDiaDiscussao']] = relationship('OrdemDiaDiscussao', uselist=True, back_populates='ordem_dia')


class OrdemDiaPresenca(Base):
    __tablename__ = 'ordem_dia_presenca'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='ordem_dia_presenca_ibfk_2'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='CASCADE', name='ordem_dia_presenca_ibfk_1'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_sessao_plen', 'cod_sessao_plen'),
        Index('dat_ordem', 'dat_ordem'),
        Index('idx_sessao_parlamentar', 'cod_sessao_plen', 'cod_parlamentar'),
        Index('tip_frequencia', 'tip_frequencia')
    )

    cod_presenca_ordem_dia = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    cod_parlamentar = mapped_column(Integer, nullable=False)
    tip_frequencia = mapped_column(CHAR(1), nullable=False, server_default=text("'P'"))
    dat_ordem = mapped_column(Date, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    txt_justif_ausencia = mapped_column(VARCHAR(200))
    flag_presenca = mapped_column(Integer)

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='ordem_dia_presenca')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='ordem_dia_presenca')


class ProposicaoGeocode(Base):
    __tablename__ = 'proposicao_geocode'
    __table_args__ = (
        ForeignKeyConstraint(['cod_proposicao'], ['proposicao.cod_proposicao'], ondelete='RESTRICT', onupdate='RESTRICT', name='proposicao_geocode_ibfk_1'),
        Index('cod_proposicao', 'cod_proposicao', unique=True),
        Index('idx_cod_proposicao', 'cod_proposicao')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_proposicao = mapped_column(Integer, nullable=False)
    endereco = mapped_column(VARCHAR(300), nullable=False)
    lat = mapped_column(DECIMAL(18, 14), nullable=False)
    lng = mapped_column(DECIMAL(18, 13), nullable=False)

    proposicao: Mapped['Proposicao'] = relationship('Proposicao', back_populates='proposicao_geocode')


class RegistroVotacaoParlamentar(Base):
    __tablename__ = 'registro_votacao_parlamentar'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='registro_votacao_parlamentar_ibfk_1'),
        ForeignKeyConstraint(['cod_votacao'], ['registro_votacao.cod_votacao'], ondelete='CASCADE', name='registro_votacao_parlamentar_ibfk_2'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_votacao', 'cod_votacao')
    )

    cod_votacao = mapped_column(Integer, primary_key=True, nullable=False)
    cod_parlamentar = mapped_column(Integer, primary_key=True, nullable=False)
    ind_excluido = mapped_column(INTEGER, nullable=False)
    vot_parlamentar = mapped_column(VARCHAR(10))

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='registro_votacao_parlamentar')
    registro_votacao: Mapped['RegistroVotacao'] = relationship('RegistroVotacao', back_populates='registro_votacao_parlamentar')


class SessaoPlenariaPainel(Base):
    __tablename__ = 'sessao_plenaria_painel'
    __table_args__ = (
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='RESTRICT', onupdate='RESTRICT', name='sessao_plenaria_painel_ibfk_1'),
        Index('cod_sessao_plen', 'cod_sessao_plen')
    )

    cod_item = mapped_column(Integer, primary_key=True)
    tip_item = mapped_column(VARCHAR(30), nullable=False)
    cod_sessao_plen = mapped_column(Integer, nullable=False)
    num_ordem = mapped_column(Integer, nullable=False)
    txt_exibicao = mapped_column(TEXT, nullable=False)
    nom_fase = mapped_column(VARCHAR(30))
    cod_materia = mapped_column(Integer)
    txt_autoria = mapped_column(VARCHAR(400))
    txt_turno = mapped_column(VARCHAR(50))
    dat_inicio = mapped_column(DateTime)
    dat_fim = mapped_column(DateTime)
    ind_extrapauta = mapped_column(Integer, server_default=text("'0'"))
    ind_exibicao = mapped_column(Integer, server_default=text("'0'"))

    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='sessao_plenaria_painel')


class SessaoPlenariaPresenca(Base):
    __tablename__ = 'sessao_plenaria_presenca'
    __table_args__ = (
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='sessao_plenaria_presenca_ibfk_1'),
        ForeignKeyConstraint(['cod_sessao_plen'], ['sessao_plenaria.cod_sessao_plen'], ondelete='CASCADE', name='sessao_plenaria_presenca_ibfk_2'),
        Index('cod_parlamentar', 'cod_parlamentar'),
        Index('cod_sessao_plen', 'cod_sessao_plen'),
        Index('dat_sessao', 'dat_sessao'),
        Index('idx_sessao_parlamentar', 'cod_sessao_plen', 'cod_parlamentar'),
        Index('tip_frequencia', 'tip_frequencia')
    )

    cod_presenca_sessao = mapped_column(Integer, primary_key=True)
    cod_sessao_plen = mapped_column(Integer, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    tip_frequencia = mapped_column(CHAR(1), nullable=False, server_default=text("'P'"))
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))
    txt_justif_ausencia = mapped_column(VARCHAR(200))
    dat_sessao = mapped_column(Date)

    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='sessao_plenaria_presenca')
    sessao_plenaria: Mapped['SessaoPlenaria'] = relationship('SessaoPlenaria', back_populates='sessao_plenaria_presenca')


class ExpedienteDiscussao(Base):
    __tablename__ = 'expediente_discussao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_ordem'], ['expediente_materia.cod_ordem'], ondelete='CASCADE', name='fk_cod_ordem'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='expediente_discussao_ibfk_1'),
        Index('cod_ordem', 'cod_ordem'),
        Index('cod_parlamentar', 'cod_parlamentar')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_ordem = mapped_column(Integer, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))

    expediente_materia: Mapped['ExpedienteMateria'] = relationship('ExpedienteMateria', back_populates='expediente_discussao')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='expediente_discussao')


class OrdemDiaDiscussao(Base):
    __tablename__ = 'ordem_dia_discussao'
    __table_args__ = (
        ForeignKeyConstraint(['cod_ordem'], ['ordem_dia.cod_ordem'], ondelete='CASCADE', name='ordem_dia_discussao_ibfk_1'),
        ForeignKeyConstraint(['cod_parlamentar'], ['parlamentar.cod_parlamentar'], ondelete='RESTRICT', name='ordem_dia_discussao_ibfk_2'),
        Index('cod_ordem', 'cod_ordem'),
        Index('cod_parlamentar', 'cod_parlamentar')
    )

    id = mapped_column(Integer, primary_key=True)
    cod_ordem = mapped_column(Integer, nullable=False)
    cod_parlamentar = mapped_column(Integer, nullable=False)
    ind_excluido = mapped_column(Integer, nullable=False, server_default=text("'0'"))

    ordem_dia: Mapped['OrdemDia'] = relationship('OrdemDia', back_populates='ordem_dia_discussao')
    parlamentar: Mapped['Parlamentar'] = relationship('Parlamentar', back_populates='ordem_dia_discussao')
