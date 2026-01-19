# -*- coding: utf-8 -*-
"""Templates HTML para notificações por e-mail de tramitação"""


def gerar_html_notificacao_autor(
    projeto: str,
    ementa: str,
    nom_autor: str,
    data: str,
    status: str,
    link_mat: str,
    casa_legislativa: str,
    data_registro: str
) -> str:
    """
    Gera HTML para notificação de autor quando matéria sofre tramitação
    
    Args:
        projeto: Tipo e número da matéria (ex: "PL 123/2024")
        ementa: Texto da ementa da matéria
        nom_autor: Nome(s) do(s) autor(es)
        data: Data da ação/tramitação
        status: Descrição do status da tramitação
        link_mat: URL para visualizar a matéria
        casa_legislativa: Nome da casa legislativa
        data_registro: Data e hora do registro da tramitação (formato: "dd/mm/aaaa às HH:MM")
    
    Returns:
        String HTML formatada para envio por e-mail
    """
    html = """\
<html>
  <head></head>
  <body>
    <p>A seguinte matéria de sua autoria sofreu tramitação registrada em {data_registro}:</p>
    <p><a href="{link_mat}" target="blank">{projeto}</a><br>
       {ementa}<br>
       Autoria: {nom_autor}<br>    
       Data da Ação: {data}<br>
       Status: {status}
    </p>
    <p>
       <strong>{casa_legislativa}</strong><br>
       Processo Digital
    </p>
  </body>
</html>
""".format(
        data_registro=data_registro,
        projeto=projeto,
        link_mat=link_mat,
        ementa=ementa,
        nom_autor=nom_autor,
        data=data,
        status=status,
        casa_legislativa=casa_legislativa
    )
    
    return html


def gerar_html_notificacao_acompanhamento_materia(
    projeto: str,
    ementa: str,
    nom_autor: str,
    data: str,
    unidade_local: str,
    destino: str,
    status: str,
    link_mat: str,
    link_remocao: str,
    casa_legislativa: str,
    data_registro: str
) -> str:
    """
    Gera HTML para notificação de acompanhamento de matéria (acompanhantes + destino)
    
    Args:
        projeto: Tipo e número da matéria (ex: "PL nº 123/2024")
        ementa: Texto da ementa da matéria
        nom_autor: Nome(s) do(s) autor(es)
        data: Data da ação/tramitação
        unidade_local: Nome da unidade de origem
        destino: Nome do destino (usuário ou unidade)
        status: Descrição do status da tramitação
        link_mat: URL para visualizar a matéria
        link_remocao: URL para remover acompanhamento (hash do acompanhante)
        casa_legislativa: Nome da casa legislativa
        data_registro: Data e hora do registro da tramitação (formato: "dd/mm/aaaa às HH:MM")
    
    Returns:
        String HTML formatada para envio por e-mail
    """
    html = """\
<html>
  <head></head>
  <body>
    <p>A seguinte matéria legislativa sofreu tramitação registrada em {data_registro}:</p>
    <p><a href="{link_mat}" target="blank">{projeto}</a><br>
       {ementa}<br>
       Autoria: {nom_autor}<br>  
       Data da Ação: {data}<br>
       Origem: {unidade_local}<br>
       Destino: {destino}<br>
       Status: {status}
    </p>
    <p>
       <strong>{casa_legislativa}</strong><br>
       Processo Digital
    </p>
    <p>
       <small><a href="{link_remocao}" target="_blank">Clique aqui</a> para excluir seu e-mail da lista de envios.</small>
    </p>
  </body>
</html>
""".format(
        data_registro=data_registro,
        data=data,
        projeto=projeto,
        link_mat=link_mat,
        ementa=ementa,
        nom_autor=nom_autor,
        unidade_local=unidade_local,
        destino=destino,
        status=status,
        casa_legislativa=casa_legislativa,
        link_remocao=link_remocao
    )
    
    return html


def gerar_html_notificacao_documento(
    proc_adm: str,
    ementa: str,
    interessado: str,
    unidade_local: str,
    destino: str,
    status: str,
    link_doc: str,
    casa_legislativa: str,
    data_registro: str
) -> str:
    """
    Gera HTML para notificação de documento administrativo despachado
    
    Args:
        proc_adm: Tipo e número do documento (ex: "Ofício nº 123/2024")
        ementa: Assunto do documento (txt_assunto)
        interessado: Nome do interessado
        unidade_local: Nome da unidade de origem
        destino: Nome do destino (usuário ou unidade)
        status: Descrição do status da tramitação
        link_doc: URL para visualizar o documento ou página de login
        casa_legislativa: Nome da casa legislativa
        data_registro: Data e hora do registro da tramitação (formato: "dd/mm/aaaa às HH:MM")
    
    Returns:
        String HTML formatada para envio por e-mail
    """
    html = """\
<html>
  <head></head>
  <body>
    <p>O seguinte processo administrativo foi despachado aos seus cuidados, para as providências cabíveis:</p>
    <p><b>{proc_adm}</b><br>
       Assunto: {ementa}<br>
       Interessado: {interessado}<br>
       Origem: {unidade_local}<br>
       Destino: {destino}<br>
       Status: {status}<br>
       Encaminhado em: {data_registro}
    </p>
    <p>
       <a href="{link_doc}" target="_blank">Autentique-se no sistema</a> e verifique sua caixa de entrada (módulo de tramitação de documentos) para maiores informações.
    </p>
    <p>
       <strong>{casa_legislativa}</strong><br>
       Processo Digital
    </p>
  </body>
</html>
""".format(
        proc_adm=proc_adm,
        ementa=ementa,
        interessado=interessado,
        unidade_local=unidade_local,
        destino=destino,
        status=status,
        data_registro=data_registro,
        link_doc=link_doc,
        casa_legislativa=casa_legislativa
    )
    
    return html
