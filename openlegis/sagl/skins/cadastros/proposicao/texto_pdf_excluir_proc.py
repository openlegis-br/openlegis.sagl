##parameters=cod_proposicao
import json
from DateTime import DateTime

REQUEST = container.REQUEST
RESPONSE = REQUEST.RESPONSE

id_texto = f"{cod_proposicao}.pdf"

resultado = {
    "assinaturas": {
        "consultadas": 0,
        "excluidas": 0,
        "falhas": 0,
        "ok": False,
    },
    "pdf": {
        "existia": False,
        "excluido": False,
        "tentou_excluir": False,
    },
}
erros = []

# 1) Consultar e excluir assinaturas (primeiro)
assinaturas = []
try:
    assinaturas = context.zsql.assinatura_documento_obter_zsql(
        codigo=cod_proposicao, tipo_doc='proposicao'
    )
    resultado["assinaturas"]["consultadas"] = len(assinaturas)
except Exception as e:
    erros.append(f"Falha ao consultar assinaturas: {e}")

if assinaturas:
    for assinatura in assinaturas:
        try:
            context.zsql.assinatura_documento_excluir_zsql(
                cod_assinatura_doc=assinatura.cod_assinatura_doc,
                cod_usuario=assinatura.cod_usuario
            )
            # resultado["assinaturas"]["excluidas"] += 1  # proibido
            atual = resultado["assinaturas"]["excluidas"]
            resultado["assinaturas"]["excluidas"] = atual + 1
        except Exception as e:
            # resultado["assinaturas"]["falhas"] += 1  # proibido
            atual = resultado["assinaturas"]["falhas"]
            resultado["assinaturas"]["falhas"] = atual + 1
            erros.append(
                f"Falha ao excluir assinatura cod={getattr(assinatura, 'cod_assinatura_doc', '?')}: {e}"
            )

# Se não havia assinaturas, etapa é OK (idempotente)
resultado["assinaturas"]["ok"] = (resultado["assinaturas"]["falhas"] == 0)

# 2) Excluir o PDF apenas se todas as assinaturas foram removidas
try:
    prop_folder = context.sapl_documentos.proposicao
    resultado["pdf"]["existia"] = hasattr(prop_folder, id_texto)

    if resultado["assinaturas"]["ok"]:
        resultado["pdf"]["tentou_excluir"] = True
        if resultado["pdf"]["existia"]:
            try:
                prop_folder.manage_delObjects([id_texto])
                resultado["pdf"]["excluido"] = True
            except Exception as e:
                erros.append(f"Falha ao excluir PDF no ZODB: {e}")
        else:
            # PDF já não existia; manter como idempotente
            resultado["pdf"]["excluido"] = False
    # Se assinaturas não OK, não tenta excluir o PDF
except Exception as e:
    erros.append(f"Erro ao acessar a pasta de proposições na ZODB: {e}")

# 3) Log de auditoria (best-effort)
try:
    if getattr(context, "dbcon_logs", False):
        usuario = REQUEST.get('AUTHENTICATED_USER', None)
        usuario_nome = usuario.getUserName() if usuario else "desconhecido"
        context.zsql.logs_registrar_zsql(
            usuario=usuario_nome,
            data=DateTime(datefmt='international').strftime('%Y-%m-%d %H:%M:%S'),
            modulo=str(REQUEST.get('URL1', '')).split('/')[-1],
            metodo='pdf_excluir',
            IP=getattr(container.pysc, 'get_ip', lambda: '0.0.0.0')(),
            cod_registro=cod_proposicao
        )
except Exception as e:
    erros.append(f"Falha ao registrar log (ignorada): {e}")

# 4) Resposta
RESPONSE.setHeader('Content-Type', 'application/json; charset=utf-8')

status_code = 200
mensagem = "Arquivo PDF excluído com sucesso."

if not resultado["assinaturas"]["ok"]:
    status_code = 500
    mensagem = "Falha ao excluir assinaturas; o PDF não foi removido."
elif (resultado["assinaturas"]["ok"]
      and resultado["pdf"]["tentou_excluir"]
      and resultado["pdf"]["existia"]
      and not resultado["pdf"]["excluido"]):
    status_code = 207
    mensagem = "Assinaturas excluídas, mas falhou ao excluir o PDF."

payload = {
    "success": status_code == 200,
    "message": mensagem,
    "detalhes": resultado,
    "erros": erros,
}

RESPONSE.setStatus(status_code)
return json.dumps(payload, ensure_ascii=False)
