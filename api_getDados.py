import os
import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET = os.environ["BUCKET_NAME"]
PREFIXO_SAIDA = os.environ.get("PREFIXO_SAIDA", "client/")

TIPOS_VALIDOS = {"leitura", "previsao"}

s3 = boto3.client("s3")


def resposta(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,OPTIONS"
        },
        "body": json.dumps(body, ensure_ascii=False)
    }


def buscar_ultimo_json(empresa_id, tipo):
    prefixo = f"{PREFIXO_SAIDA}empresa_{empresa_id}/{tipo}_"

    paginator = s3.get_paginator("list_objects_v2")
    arquivos = []

    for pagina in paginator.paginate(
        Bucket=BUCKET,
        Prefix=prefixo
    ):
        for objeto in pagina.get("Contents", []):
            if objeto["Key"].endswith(".json"):
                arquivos.append(objeto)

    if not arquivos:
        return None

    return max(
        arquivos,
        key=lambda arquivo: arquivo["LastModified"]
    )


def lambda_handler(event, context):
    try:
        path_params = event.get("pathParameters") or {}
        empresa_id = path_params.get("empresa_id")
        tipo = (path_params.get("tipo") or "").lower()

        if not empresa_id or not empresa_id.isdigit():
            return resposta(400, {
                "erro": "ID da empresa inválido ou não informado"
            })

        if tipo not in TIPOS_VALIDOS:
            return resposta(400, {
                "erro": f"Tipo inválido. Use: {sorted(TIPOS_VALIDOS)}"
            })

        arquivo = buscar_ultimo_json(empresa_id, tipo)

        if arquivo is None:
            return resposta(404, {
                "erro": f"Nenhum JSON de {tipo} encontrado para essa empresa"
            })

        objeto = s3.get_object(
            Bucket=BUCKET,
            Key=arquivo["Key"]
        )

        conteudo = json.loads(
            objeto["Body"].read().decode("utf-8")
        )

        # O arquivo da gold vem como {"dados": [radares...]}. Devolvemos só a lista
        # em "dados", para a resposta não ficar com dados.dados.
        if isinstance(conteudo, dict) and "dados" in conteudo:
            radares = conteudo["dados"]
        else:
            # arquivo no formato antigo (objeto indexado por id_radar): devolvido como está
            radares = conteudo

        return resposta(200, {
            "empresa_id": int(empresa_id),
            "tipo": tipo,
            "ultima_atualizacao": arquivo["LastModified"].isoformat(),
            "dados": radares
        })

    except Exception:
        logger.exception("Erro ao consultar JSON")
        return resposta(500, {
            "erro": "Erro interno ao consultar os dados"
        })