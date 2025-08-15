##parameters=cod_proposicao
import json
from DateTime import DateTime

REQUEST = container.REQUEST
RESPONSE = REQUEST.RESPONSE

erro = False

# Nome do arquivo PDF
id_texto = f"{cod_proposicao}.pdf"

# Tenta excluir o PDF da ZODB
if hasattr(context.sapl_documentos.proposicao, id_texto):
    try:
        context.sapl_documentos.proposicao.manage_delObjects([id_texto])
    except Exception:
        erro = True

# Tenta excluir assinaturas vinculadas ao documento
try:
    assinaturas = context.zsql.assinatura_documento_obter_zsql(codigo=cod_proposicao, tipo_doc='proposicao')
    for assinatura in assinaturas:
        try:
            context.zsql.assinatura_documento_excluir_zsql(
                cod_assinatura_doc=assinatura.cod_assinatura_doc,
                codigo=assinatura.codigo,
                tipo_doc=assinatura.tipo_doc
            )
        except Exception:
            erro = True
except Exception:
    erro = True

# LOG DE AUDITORIA (opcional, execute se necessário)
try:
    if getattr(context, "dbcon_logs", False):
        context.zsql.logs_registrar_zsql(
            usuario=REQUEST['AUTHENTICATED_USER'].getUserName(),
            data=DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
            modulo=str(REQUEST['URL1']).split('/')[-1],
            metodo='pdf_excluir',
            IP=container.pysc.get_ip(),
            cod_registro=cod_proposicao
        )
except Exception:
    pass

# Resposta JSON
RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')
if erro:
    result = {"success": False, "message": "Ocorreu um erro ao excluir o PDF da proposição!"}
else:
    result = {"success": True, "message": "Arquivo PDF excluído com sucesso!"}
return json.dumps(result)
