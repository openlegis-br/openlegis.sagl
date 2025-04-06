from celery import Celery
import json
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Celery('tasks', config_source='celeryconfig')

@app.task(max_retries=2, default_retry_delay=10)
def protocolo_prefeitura_task(self, API_ENDPOINT, API_USER, API_PASSWORD, cod_materia, payload):
    """Tarefa Celery para enviar matéria para a API da prefeitura com timeouts, retentativas e confirmação de recebimento."""
    logging.info(f"Iniciando envio da matéria {cod_materia} para a API da prefeitura.")
    try:
        retry_strategy = Retry(
            total=2,  # Número total de tentativas
            status_forcelist=[429, 500, 502, 503, 504],  # Códigos HTTP para tentativa de retentativa
            backoff_factor=1,  # Fator de backoff para atraso entre retentativas
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        with requests.Session() as session:
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            session.auth = (API_USER, API_PASSWORD)
            logging.debug(f"Payload da matéria {cod_materia}: {payload}") #Log do payload
            response = session.post(API_ENDPOINT, json=payload, timeout=(10, 30))  # Adiciona timeouts (conexão, leitura)
            response.raise_for_status()
            resultado = response.json()[0]

            if response.status_code == 200 or response.status_code == 201:  # confirmação de recebimento (exemplo código 201 created).
                data_formatada = datetime.fromisoformat(resultado["criado_em"].replace("Z", "+00:00")).strftime("%d/%m/%Y às %H:%M:%S")

                mensagem = f"Protocolado na Prefeitura Municipal sob nº {resultado['numero_protocolo']} em {data_formatada}"
                logging.info(mensagem)  # Log de sucesso
                return mensagem
            else:
                logging.warning(f"A API da prefeitura retornou o código de status: {response.status_code}, e não confirmou o recebimento ao enviar a matéria {cod_materia}")
                raise ValueError(f"A API da prefeitura retornou o código de status: {response.status_code}, e não confirmou o recebimento ao enviar a matéria {cod_materia}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Erro na requisição para a API da prefeitura: {e} ao enviar a matéria {cod_materia}. Tentando novamente.")
        raise self.retry(exc=ValueError(f"Erro na requisição para a API da prefeitura: {e} ao enviar a matéria {cod_materia}"))
    except json.JSONDecodeError as e:
        logging.error(f"Erro ao decodificar JSON da resposta da API: {e} ao enviar a matéria {cod_materia}. Tentando novamente.")
        raise self.retry(exc=ValueError(f"Erro ao decodificar JSON da resposta da API: {e} ao enviar a matéria {cod_materia}"))
    except KeyError as e:
        logging.error(f"Chave ausente na resposta da API: {e} ao enviar a matéria {cod_materia}. Tentando novamente.")
        raise self.retry(exc=ValueError(f"Chave ausente na resposta da API: {e} ao enviar a matéria {cod_materia}"))
    except Exception as e: # captura outras exceções inesperadas
        logging.critical(f"Erro inesperado ao enviar a matéria {cod_materia}: {e}")
        raise
