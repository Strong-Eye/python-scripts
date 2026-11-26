import os
import io
import re
import logging
from collections import defaultdict
from datetime import datetime

import boto3
import pandas as pd
import mysql.connector

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET = os.environ["BUCKET_NAME"]
PREFIXO_ENTRADA = os.environ.get("PREFIXO_ENTRADA", "raw/")
PREFIXO_SAIDA = os.environ.get("PREFIXO_SAIDA", "trusted/")

COLUNAS_OBRIGATORIAS = ["uuid", "cpu", "ram", "disco"]

s3 = boto3.client("s3")


def conectar():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "strong_eye"),
        connection_timeout=5,
    )


def detectar_separador(corpo: bytes) -> str:
    cabecalho = corpo.split(b"\n", 1)[0].decode("utf-8-sig", errors="ignore")
    return ";" if cabecalho.count(";") > cabecalho.count(",") else ","


def ler_csv(corpo: bytes, chave: str):
    if not corpo.strip():
        logger.warning("Arquivo vazio ignorado: %s", chave)
        return None

    df = pd.read_csv(
        io.BytesIO(corpo),
        sep=detectar_separador(corpo),
        encoding="utf-8-sig",
    )

    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.loc[:, ~df.columns.str.startswith("unnamed")]

    # Colunas que a silver recalcula a partir do banco. Se o arquivo já veio enriquecido
    # (por exemplo, uma saída da própria silver copiada para raw/), elas são descartadas
    # aqui para não duplicar colunas no merge.
    df = df.loc[:, ~df.columns.str.startswith(("valor alerta", "valor chamado"))]
    df = df.drop(columns=["empresa id", "id_radar"], errors="ignore")
    df = df.loc[:, ~df.columns.duplicated()]

    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        logger.warning("%s sem colunas %s (colunas: %s), ignorado",
                       chave, faltando, list(df.columns))
        return None
    return df


def ler_bronze():
    dfs = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIXO_ENTRADA):
        for obj in page.get("Contents", []):
            chave = obj["Key"]
            if not chave.lower().endswith(".csv"):
                continue
            try:
                corpo = s3.get_object(Bucket=BUCKET, Key=chave)["Body"].read()
                df = ler_csv(corpo, chave)
                if df is not None:
                    dfs.append(df)
            except Exception:
                logger.exception("Falha ao ler %s, arquivo ignorado", chave)
    if not dfs:
        return None
    leitura = pd.concat(dfs, ignore_index=True)
    del dfs
    return leitura


def limpar(leitura):
    leitura = leitura.copy()

    leitura["uuid"] = leitura["uuid"].astype(str).str.strip().str.upper()
    leitura.loc[leitura["uuid"].isin(["", "NAN", "NONE"]), "uuid"] = pd.NA
    for col in ["cpu", "ram", "disco"]:
        leitura[col] = pd.to_numeric(leitura[col], errors="coerce")

    leitura = leitura.dropna(subset=COLUNAS_OBRIGATORIAS).copy()
    leitura["cpu"] = leitura["cpu"].round(1)
    leitura["ram"] = leitura["ram"].round(2)
    leitura["disco"] = leitura["disco"].round(2)

    # --- novas colunas do formato atual ---
    if "data_hora" in leitura.columns:
        leitura["data_hora"] = pd.to_datetime(leitura["data_hora"], errors="coerce")

    if {"bytes_enviados_inicio", "bytes_enviados_fim", "intervalo_seg"} <= set(leitura.columns):
        inicio = pd.to_numeric(leitura["bytes_enviados_inicio"], errors="coerce")
        fim = pd.to_numeric(leitura["bytes_enviados_fim"], errors="coerce")
        intervalo = pd.to_numeric(leitura["intervalo_seg"], errors="coerce")

        delta = fim - inicio
        # contador de bytes resetado (reboot) ou intervalo inválido -> sem vazão
        valido = (delta >= 0) & (intervalo > 0)
        leitura["rede_mbps"] = ((delta * 8) / 1_000_000 / intervalo).where(valido).round(3)

    for col in ["total_processos", "total_threads"]:
        if col in leitura.columns:
            leitura[col] = pd.to_numeric(leitura[col], errors="coerce")

    if "data_hora" in leitura.columns:
        leitura = leitura.sort_values(["uuid", "data_hora"]).reset_index(drop=True)

    return leitura


def buscar_parametros(uuids):
    """Uma única consulta para todos os radares.
    Retorna (DataFrame de limites por uuid, dict {empresa_id: nome_fantasia}).

    valor_alerta  -> limite que gera notificação (é com ele que se decide se passou do parâmetro)
    valor_chamado -> limite que abre chamado direto no Jira
    """
    if not uuids:
        return pd.DataFrame(), {}

    placeholders = ",".join(["%s"] * len(uuids))
    sql = f"""
        SELECT
            r.id AS id_radar,
            r.uuid,
            r.fk_empresa,
            e.nome_fantasia,
            p.fk_componente,
            p.valor_alerta,
            p.valor_chamado
        FROM parametros p
        JOIN radares r ON p.fk_radar = r.id
        JOIN empresas e ON r.fk_empresa = e.id
        WHERE UPPER(r.uuid) IN ({placeholders})
        ORDER BY r.uuid, p.fk_componente
    """
    conn = conectar()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, [u.upper() for u in uuids])
        rows = cur.fetchall()
    finally:
        conn.close()

    por_radar = defaultdict(list)
    nomes = {}
    for r in rows:
        chave_uuid = str(r["uuid"]).strip().upper()  # mesma normalização da leitura
        por_radar[chave_uuid].append(r)
        nomes[r["fk_empresa"]] = r["nome_fantasia"]

    linhas = []
    for uuid, params in por_radar.items():
        parametros = {p["fk_componente"]: p for p in params}

        if not all(i in parametros for i in [1, 2, 3, 4]):
            logger.warning("Radar %s com parâmetros incompletos, ignorado", uuid)
            continue

        cpu = parametros[1]
        ram = parametros[2]
        disco = parametros[3]
        net = parametros[4]

        linhas.append({
            "uuid": uuid,
            "id_radar": params[0]["id_radar"],

            "Valor alerta CPU": cpu["valor_alerta"],
            "Valor chamado CPU": cpu["valor_chamado"],

            "Valor alerta RAM": ram["valor_alerta"],
            "Valor chamado RAM": ram["valor_chamado"],

            "Valor alerta DISCO": disco["valor_alerta"],
            "Valor chamado DISCO": disco["valor_chamado"],

            "Valor alerta NET": net["valor_alerta"],
            "Valor chamado NET": net["valor_chamado"],

            "Empresa ID": params[0]["fk_empresa"],
        })
    return pd.DataFrame(linhas), nomes


def lambda_handler(event, context):
    leitura = ler_bronze()
    if leitura is None:
        logger.warning("Nenhum CSV válido encontrado em %s", PREFIXO_ENTRADA)
        return {"statusCode": 200, "body": "sem dados"}

    leitura = limpar(leitura)
    if leitura.empty:
        logger.warning("Nenhuma linha válida após a limpeza")
        return {"statusCode": 200, "body": "sem dados válidos"}

    params_df, nomes = buscar_parametros(leitura["uuid"].unique().tolist())

    if params_df.empty:
        raise RuntimeError("Nenhum radar da bronze foi encontrado no banco")

    # remove da leitura qualquer coluna que venha do banco (evita _x/_y no merge)
    colunas_parametros = [c for c in params_df.columns if c != "uuid"]
    leitura = leitura.drop(columns=colunas_parametros, errors="ignore")

    leitura = leitura.merge(params_df, on="uuid", how="left")

    sem_radar = leitura["Empresa ID"].isna().sum()
    if sem_radar:
        logger.warning("%s linhas sem radar cadastrado foram descartadas", sem_radar)
    leitura = leitura.dropna(subset=["Empresa ID"])
    leitura["Empresa ID"] = leitura["Empresa ID"].astype(int)
    leitura["id_radar"] = leitura["id_radar"].astype(int)

    # id_radar logo depois do uuid
    colunas = list(leitura.columns)
    colunas.remove("id_radar")
    colunas.insert(colunas.index("uuid") + 1, "id_radar")
    leitura = leitura[colunas]

    logger.info("Data frame criado: %s linhas", len(leitura))

    agora = datetime.now()
    carimbo = f"{agora:%Y-%m-%d}_{agora.hour}-{agora.minute}"
    falhas = []

    for empresa_id, df_emp in leitura.groupby("Empresa ID"):
        try:
            nome = re.sub(r"[^\w\-]+", "_", nomes.get(empresa_id, str(empresa_id)))
            chave = f"{PREFIXO_SAIDA}leituraCompleta_{carimbo}_{nome}.csv"
            corpo = df_emp.to_csv(index=False).encode("utf-8")
            s3.put_object(Bucket=BUCKET, Key=chave, Body=corpo, ContentType="text/csv")
            logger.info("Enviado: %s", chave)
        except Exception:
            logger.exception("Falha na empresa id=%s", empresa_id)
            falhas.append(int(empresa_id))

    if falhas:
        raise RuntimeError(f"Falha ao processar empresas: {falhas}")

    return {"statusCode": 200, "body": "ok"}