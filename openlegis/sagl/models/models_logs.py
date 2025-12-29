# -*- coding: utf-8 -*-
"""
Models SQLAlchemy para openlegis_logs
Contém todas as tabelas do banco openlegis_logs
"""
from sqlalchemy import Column, Integer, DateTime, Text, Index
from sqlalchemy.dialects.mysql import VARCHAR
from sqlalchemy.orm import declarative_base

# Base separada para o banco openlegis_logs
BaseLogs = declarative_base()


class Log(BaseLogs):
    """
    Model para a tabela logs do banco openlegis_logs
    Armazena logs de ações do sistema
    """
    __tablename__ = 'logs'
    __table_args__ = (
        Index('usuario', 'usuario'),
        Index('metodo', 'metodo'),
        Index('data', 'data'),
        Index('modulo', 'modulo'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_general_ci'}
    )

    cod_log = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    data = Column(DateTime, nullable=False)
    cod_registro = Column(Integer, nullable=False)
    modulo = Column(VARCHAR(100), nullable=False)
    metodo = Column(VARCHAR(100), nullable=False)
    usuario = Column(VARCHAR(50), nullable=False)
    IP = Column(VARCHAR(50), nullable=False)
    dados = Column(Text, nullable=True)

