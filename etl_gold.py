import os
import io
import re
import json
import logging
from datetime import datetime

import boto3
import numpy as np
import pandas as pd
import mysql.connector

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET = os.environ["BUCKET_NAME"]
PREFIXO_ENTRADA = os.environ.get("PREFIXO_ENTRADA", "trusted/lei")
PREFIXO_SAIDA = os.environ.get("PREFIXO_SAIDA", "client/")

LATITUDE = float(os.environ.get("LATITUDE", "-23.7145"))
LONGITUDE = float(os.environ.get("LONGITUDE", "-46.4132"))
HORIZONTES = tuple(int(h) for h in os.environ.get("HORIZONTES", "14").split(","))
MIN_DIAS_HISTORICO = int(os.environ.get("MIN_DIAS_HISTORICO", "2"))

COMPONENTES_PADRAO = ["cpu", "ram", "disco", "rede"]

MAX_HISTORICO = 30
COMPONENTES_JSON = ["ram", "cpu", "disco"]

STATUS_ZUMBI = {"zombie", "stopped"}

# Teto das previsões dos componentes percentuais. A rede é medida em Mbps, então não entra.
TETO_PERCENTUAL = 100
COMPONENTES_PERCENTUAIS = {"cpu", "ram", "disco"}

# Coluna do CSV da silver com o valor de alerta de cada componente (nomes já em minúsculas)
COLUNA_ALERTA = {
    "cpu": "valor alerta cpu",
    "ram": "valor alerta ram",
    "disco": "valor alerta disco",
    "rede": "valor alerta net",
}

s3 = boto3.client("s3")


# ----------------------------------------------------------------------------
# Banco
# ----------------------------------------------------------------------------
def buscar_empresas():
    conn = mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "strong_eye"),
        connection_timeout=5
    )

    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("select nome_fantasia, id from empresas")
        return cur.fetchall()
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# Leitura da silver
# ----------------------------------------------------------------------------
def normalizar(df):
    df.columns = [str(c).strip().lower() for c in df.columns]

    df = df.loc[:, ~df.columns.duplicated(keep="last")]

    if "data/hora" not in df.columns and "data_hora" in df.columns:
        df = df.rename(columns={"data_hora": "data/hora"})

    if "rede" not in df.columns and "rede_mbps" in df.columns:
        df = df.rename(columns={"rede_mbps": "rede"})

    return df


def ler_leituras():
    dfs = []

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIXO_ENTRADA):
        for obj in page.get("Contents", []):
            chave = obj["Key"]

            if not chave.lower().endswith(".csv"):
                continue

            try:
                corpo = s3.get_object(
                    Bucket=BUCKET,
                    Key=chave
                )["Body"].read()

                if corpo.strip():
                    dfs.append(
                        normalizar(
                            pd.read_csv(
                                io.BytesIO(corpo),
                                encoding="utf-8-sig"
                            )
                        )
                    )

            except Exception:
                logger.exception("Falha ao ler %s, arquivo ignorado", chave)

    if not dfs:
        return None

    return pd.concat(dfs, ignore_index=True)


def preparar(df):
    obrigatorias = [
        "uuid",
        "id_radar",
        "cpu",
        "ram",
        "disco",
        "data/hora",
        "empresa id"
    ]

    faltando = [c for c in obrigatorias if c not in df.columns]

    if faltando:
        raise RuntimeError(
            f"CSV sem as colunas {faltando}. Colunas: {list(df.columns)}"
        )

    df = df.copy()

    for col in [
        "id_radar",
        "cpu",
        "ram",
        "disco",
        "rede",
        "empresa id",
        "total_processos",
        "total_threads"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["data/hora"] = pd.to_datetime(
        df["data/hora"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["uuid", "id_radar", "cpu", "ram", "disco", "empresa id", "data/hora"]
    )

    df["empresa id"] = df["empresa id"].astype(int)
    df["id_radar"] = df["id_radar"].astype(int)

    return df.drop_duplicates(
        subset=["id_radar", "data/hora"],
        keep="last"
    )


# ----------------------------------------------------------------------------
# Processos
# ----------------------------------------------------------------------------
def parse_processos(texto):
    processos = []

    if not isinstance(texto, str) or not texto.strip():
        return processos

    for item in texto.split("&"):
        partes = item.split("|")

        if len(partes) < 5:
            continue

        pid = partes[0]
        criacao = partes[-1]
        threads = partes[-2]
        status = partes[-3]

        nome = "|".join(partes[1:-3])

        processos.append({
            "pid": int(pid) if pid.strip().isdigit() else pid,
            "nome": nome,
            "status": status,
            "threads": int(threads) if threads.strip().isdigit() else None,
            "criacao": None if criacao.strip().upper() == "N/A" else criacao
        })

    return processos


def contar_zumbis(processos):
    return sum(
        1 for p in processos
        if str(p["status"]).lower() in STATUS_ZUMBI
    )


# ----------------------------------------------------------------------------
# Tendência e JSON de leitura
# ----------------------------------------------------------------------------
def _int(v):
    return None if pd.isna(v) else int(round(float(v)))


def montar_registro(grupo):
    """Registro de um radar. O id_radar vira a chave do objeto em
    montar_json_empresa; o uuid fica aqui dentro como um campo comum."""
    grupo = grupo.sort_values("data/hora")
    u = grupo.iloc[-1]

    processos = parse_processos(u.get("top_processos"))
    tem_lista = len(processos) > 0

    return {
        "uuid": u["uuid"],
        "maquina": u.get("maquina"),
        "data/hora": u["data/hora"].strftime("%Y-%m-%d %H:%M:%S"),

        "Valor alerta CPU": _int(u.get("valor alerta cpu")),
        "Valor chamado CPU": _int(u.get("valor chamado cpu")),

        "Valor alerta RAM": _int(u.get("valor alerta ram")),
        "Valor chamado RAM": _int(u.get("valor chamado ram")),

        "Valor alerta DISCO": _int(u.get("valor alerta disco")),
        "Valor chamado DISCO": _int(u.get("valor chamado disco")),

        "Valor alerta NET": _int(u.get("valor alerta net")),
        "Valor chamado NET": _int(u.get("valor chamado net")),

        "Empresa ID": int(u["empresa id"]),

        "processos": {
            "TOTAL_PROCESSOS": _int(u.get("total_processos")),
            "TOTAL_THREADS": _int(u.get("total_threads")),
            "30_PROCESSOS": processos[:30],
            "PROCESSOS_ZUMBI": contar_zumbis(processos) if tem_lista else None
        },

        "componentes": [
            {comp.upper(): {
                "historico": [
                    round(float(v), 2) for v in grupo[comp].tail(MAX_HISTORICO)
                ],
                "ultimo_valor": round(float(grupo[comp].iloc[-1]), 2)
            }}
            for comp in COMPONENTES_JSON
        ]
    }


def montar_json_empresa(df_empresa):
    """Objeto com a lista de radares: {"dados": [{"id_radar": 12, ...}, {"id_radar": 13, ...}]}"""
    return {
        "dados": [
            {"id_radar": int(id_radar), **montar_registro(grupo)}
            for id_radar, grupo in df_empresa.groupby("id_radar")
        ]
    }


# ----------------------------------------------------------------------------
# Clima
# ----------------------------------------------------------------------------
def buscar_clima(dias):
    import requests

    resposta = requests.get(
        "https://ensemble-api.open-meteo.com/v1/ensemble",
        params={
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation",
            "models": "ncep_gefs05",
            "forecast_days": dias,
            "timezone": "America/Sao_Paulo"
        },
        timeout=60
    )

    resposta.raise_for_status()

    dados = resposta.json()["hourly"]

    tempo = pd.to_datetime(dados["time"])

    def membros(variavel, aceitar_unico=True):
        colunas = [
            c for c in dados
            if c.startswith(variavel + "_member")
        ]

        if not colunas and aceitar_unico and variavel in dados:
            colunas = [variavel]

        if not colunas:
            raise ValueError(
                f"Variável {variavel} não encontrada na API: {list(dados.keys())}"
            )

        quadro = pd.DataFrame({
            c: dados[c] for c in colunas
        })

        quadro.index = tempo

        return quadro

    horario = pd.DataFrame({
        "temperatura": membros("temperature_2m").mean(axis=1),
        "umidade": membros("relative_humidity_2m").mean(axis=1)
    })

    diario = horario.resample("1D").mean()

    chuva = membros("precipitation", aceitar_unico=False)

    chuva_dia = chuva.resample("1D").sum()

    diario["probabilidade_chuva"] = (
        (chuva_dia >= 10.0).sum(axis=1)
        / chuva.shape[1]
        * 100
    )

    diario = diario.dropna()

    return {
        dia.strftime("%Y-%m-%d"): {
            "temperatura": round(float(l["temperatura"]), 2),
            "umidade": round(float(l["umidade"]), 2),
            "probabilidade_chuva": round(
                float(l["probabilidade_chuva"]), 2
            )
        }
        for dia, l in diario.iterrows()
    }


# ----------------------------------------------------------------------------
# Previsão NumPy + clima
# ----------------------------------------------------------------------------
def valor_alerta_do_radar(df_radar, comp):
    """Valor de alerta do componente para este radar (o mais recente do CSV da silver).
    Devolve None se a coluna não existir ou estiver vazia."""
    coluna = COLUNA_ALERTA.get(comp)

    if coluna is None or coluna not in df_radar.columns:
        return None

    serie = pd.to_numeric(
        df_radar.sort_values("data/hora")[coluna],
        errors="coerce"
    ).dropna()

    if serie.empty:
        return None

    return round(float(serie.iloc[-1]), 2)


def prever_numpy(df_radar, clima=None):
    passos = max(HORIZONTES)

    componentes = [
        c for c in COMPONENTES_PADRAO
        if c in df_radar.columns
    ]

    df = df_radar.copy()

    df["data/hora"] = (
        pd.to_datetime(df["data/hora"], utc=True)
        .dt.tz_localize(None)
    )

    diario = (
        df.set_index("data/hora")[componentes]
        .resample("D")
        .mean()
    )

    ultima_data = diario.index.max()

    datas_futuras = pd.date_range(
        ultima_data + pd.Timedelta(days=1),
        periods=passos,
        freq="D"
    )

    resultado = {}

    for comp in componentes:
        y = (
            diario[comp]
            .interpolate()
            .dropna()
            .tail(MAX_HISTORICO)
            .to_numpy(dtype=float)
        )

        if len(y) < MIN_DIAS_HISTORICO:
            resultado[comp] = None
            continue

        x = np.arange(len(y), dtype=float)

        # Regressão linear
        inclinacao, intercepto = np.polyfit(x, y, 1)
        ajustados = inclinacao * x + intercepto

        # R² da regressão linear deste componente.
        variacao_total = np.sum((y - np.mean(y)) ** 2)
        erro_residual = y - ajustados

        if variacao_total > 0:
            r2 = 1 - (
                np.sum(erro_residual ** 2) / variacao_total
            )
            confiabilidade = round(float(r2), 4)
        else:
            # R² é indefinido quando todos os valores históricos são iguais.
            confiabilidade = None

        valor_alerta = valor_alerta_do_radar(df, comp)

        resultado[comp] = {
            "confiabilidade": confiabilidade,
            "valor_alerta": valor_alerta
        }

        dias = []

        for i in range(passos):
            data = datas_futuras[i].strftime("%Y-%m-%d")

            # Previsão baseada na tendência histórica, nunca abaixo de 0
            # e, nos componentes percentuais, nunca acima do teto (100).
            previsao = max(float(inclinacao * (len(y) + i) + intercepto), 0.0)

            if comp in COMPONENTES_PERCENTUAIS:
                previsao = min(previsao, float(TETO_PERCENTUAL))

            previsao = round(previsao, 2)

            item = {
                "data": data,
                "previsao": previsao,
                # True se a previsão do dia ultrapassa o valor de alerta (None se o radar não tem alerta)
                "estourou_alerta": (
                    None if valor_alerta is None else bool(previsao > valor_alerta)
                )
            }

            if clima and data in clima:
                item["clima"] = clima[data]

            dias.append(item)

        # Um único horizonte, até 14 dias (ou o maior valor configurado).
        resultado[comp]["previsao"] = dias

    return resultado


def montar_previsao_empresa(df_empresa, clima):
    """Objeto com a lista de radares: {"dados": [{"id_radar": 12, "uuid": ..., "cpu": {...}, ...}]}"""
    radares = []
    for _, df_radar in df_empresa.groupby("id_radar"):
        radares.append({
            "id_radar": int(df_radar["id_radar"].iloc[0]),
            "uuid": df_radar["uuid"].iloc[0],
            **prever_numpy(df_radar, clima)
        })
    return {"dados": radares}


# ----------------------------------------------------------------------------
# Envio para S3
# ----------------------------------------------------------------------------
def enviar_json(chave, conteudo):
    corpo = json.dumps(
        conteudo,
        ensure_ascii=False,
        indent=2
    ).encode("utf-8")

    s3.put_object(
        Bucket=BUCKET,
        Key=chave,
        Body=corpo,
        ContentType="application/json"
    )

    logger.info("Enviado: %s", chave)


# ----------------------------------------------------------------------------
# Handler
# ----------------------------------------------------------------------------
def lambda_handler(event, context):

    leitura = ler_leituras()

    if leitura is None:
        logger.warning(
            "Nenhum CSV encontrado em %s",
            PREFIXO_ENTRADA
        )

        return {
            "statusCode": 200,
            "body": "sem dados"
        }

    leitura = preparar(leitura)

    if leitura.empty:
        logger.warning("Nenhuma linha válida após a limpeza")

        return {
            "statusCode": 200,
            "body": "sem dados válidos"
        }

    logger.info(
        "Data frame criado: %s linhas",
        len(leitura)
    )

    empresas = buscar_empresas()

    try:
        clima = buscar_clima(max(HORIZONTES))

        logger.info(
            "Clima obtido para %s dias",
            len(clima)
        )

    except Exception:
        logger.exception(
            "Falha ao buscar clima; previsões seguem sem clima"
        )

        clima = None

    agora = datetime.now()

    carimbo = f"{agora:%Y-%m-%d}_{agora.hour}-{agora.minute}"

    falhas = []

    for e in empresas:

        df_emp = leitura[
            leitura["empresa id"] == e["id"]
        ]

        if df_emp.empty:
            continue

        nome = re.sub(
            r"[^\w\-]+",
            "_",
            e["nome_fantasia"]
        )

        pasta = f"{PREFIXO_SAIDA}empresa_{e['id']}/"

        # JSON de leitura: objeto indexado por id_radar
        try:
            enviar_json(
                f"{pasta}leitura_{carimbo}_{nome}.json",
                montar_json_empresa(df_emp)
            )

        except Exception:
            logger.exception(
                "Falha no json de leitura da empresa id=%s",
                e["id"]
            )

            falhas.append(int(e["id"]))
            continue

        # JSON de previsão: NumPy + ajuste climático
        try:
            enviar_json(
                f"{pasta}previsao_{carimbo}_{nome}.json",
                montar_previsao_empresa(df_emp, clima)
            )

        except Exception:
            logger.exception(
                "Falha na previsão NumPy da empresa id=%s",
                e["id"]
            )

            falhas.append(int(e["id"]))

    if falhas:
        raise RuntimeError(
            f"Falha ao processar empresas: {falhas}"
        )

    return {
        "statusCode": 200,
        "body": "ok"
    }