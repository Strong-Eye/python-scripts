import boto3
import pandas
import os
import json
import glob
import mysql.connector
from datetime import datetime 
from datetime import date
from datetime import timedelta
import time
import numpy as np

def descobrir_quantidade():      
    try:
        mydb = mysql.connector.connect(
            host="localhost",
            user="aluno",
            password="sptech",
            database="strong_eye"
        )

        sql = f"select nome_fantasia, id from strong_eye.empresas;"
        cursor = mydb.cursor(dictionary=True)
        
        cursor.execute(sql)
        
        resultado = cursor.fetchall()    

        return resultado
    except Exception as erro:
        print(f"Erro durante a consulta: {erro}")
        return None

def ouro():
  try:  
    session = boto3.Session(
        aws_access_key_id="",
        aws_secret_access_key="",
        aws_session_token="",
        region_name="us-east-1"
    )

    s3_client = session.client("s3")
    s3_resource = session.resource("s3")
    BUCKET_NAME = "strong-eye-s3-data-lake-us-east-1-d01mh1ttcp"
    
    bucket = s3_resource.Bucket(BUCKET_NAME)
    buckets_objects = bucket.objects.all()
    objects = []

    for i in buckets_objects:
        #exemplo READ-1.csv / Letras iniciais = REA  
        if( "trusted/lei" in i.key):
            objects.append(i.key)
    
    print(f"-------Objetos do bucket alcançados com sucesso------------")

    i = 0

    dfs = []
    for j in objects:
        
        with open(f'./comp{i}.csv', 'wb') as f:
            s3_client.download_fileobj(BUCKET_NAME, f'{j}', f) 
            f.write(b'\n')
        
        arq = glob.glob("./*.csv")
        for aq in arq:
             df = pandas.read_csv(aq)
             dfs.append(df)
             if "comp" in aq:
                  os.remove(aq)
        i += 1

    leitura = pandas.concat(dfs, ignore_index=True)
    leitura['data/hora'] = pandas.to_datetime(leitura['data/hora'], errors='coerce')
    print("Data frame foi criado")

    try:
        empresas = descobrir_quantidade()
        print("Consulta no banco realizada")
    except:
         print("consulta no banco falhou") 
    for e in empresas:
        jsonFinal = []
        linhas = leitura.loc[leitura["Empresa ID"] == e["id"]]
        leituraUnica = pandas.DataFrame(linhas)
        ultimas = leituraUnica.sort_values('data/hora').groupby('uuid').tail(1)
        for l in ultimas.index:
            historico = leituraUnica[leituraUnica['uuid'] == leituraUnica['uuid'][l]]
            horas = list(range(len(historico)))

            predicao = []
            for comp in ['ram', 'cpu', 'disco']:
                y_vals = historico[comp].values
                valor_pred, r_quadrado, inclinacao = None, None, None
                if len(y_vals) >= 2:
                    inclinacao, intercepto = np.polyfit(horas, y_vals, 1)
                    r_quadrado = np.corrcoef(horas, y_vals)[0, 1] ** 2
                    limite_max = historico[f'Valor maximo {comp.upper()}'].iloc[0]
                    if inclinacao != 0:
                        valor_pred = round((limite_max - intercepto) / inclinacao, 1)
                        r_quadrado = round(r_quadrado, 3)
                        inclinacao = round(inclinacao, 3)
                    else:
                        r_quadrado, inclinacao = None, None
                predicao.append({comp.upper(): {'horas': valor_pred, 'r_quadrado': r_quadrado, 'inclinacao': inclinacao}})

            json1 = {
                'maquina': leituraUnica['maquina'][l],
                'uuid': leituraUnica['uuid'][l],
                'cpu': float(leituraUnica['cpu'][l]),
                'ram': float(leituraUnica['ram'][l]),
                'disco': float(leituraUnica['disco'][l]),
                'rede': float(leituraUnica['rede'][l]),
                'total_processos': int(leituraUnica['total_processos'][l]),
                'data/hora': leituraUnica['data/hora'][l].strftime('%Y-%m-%d %H:%M:%S'),
                'Valor maximo CPU': int(leituraUnica['Valor maximo CPU'][l]),
                'Valor minimo CPU': int(leituraUnica['Valor minimo CPU'][l]),
                'Valor maximo RAM': int(leituraUnica['Valor maximo RAM'][l]),
                'Valor minimo RAM': int(leituraUnica['Valor minimo RAM'][l]),
                'Valor maximo DISCO': int(leituraUnica['Valor maximo DISCO'][l]),
                'Valor minimo DISCO': int(leituraUnica['Valor minimo DISCO'][l]),
                'Valor maximo NET': int(leituraUnica['Valor maximo NET'][l]),
                'Valor minimo NET': int(leituraUnica['Valor minimo NET'][l]),
                'Empresa ID': int(leituraUnica['Empresa ID'][l]),
                'predicao': predicao
            }
            jsonFinal.append(json1)
            
        data = datetime.now()    
        dia = date.today()
        with open(f'leitura_{dia}_{data.hour}-{data.minute}_{e["nome_fantasia"]}.json','w', encoding='cp1252') as f:
                json.dump(jsonFinal,f,ensure_ascii=False, indent = 2 )      
        s3_client.upload_file(f'./leitura_{dia}_{data.hour}-{data.minute}_{e["nome_fantasia"]}.json', BUCKET_NAME, f"client/leitura_{dia}_{data.hour}-{data.minute}_{e["nome_fantasia"]}.json")  

        print("Arquivo json criado com sucesso")        
        arquivosJson = glob.glob("./*.json")

        for js in arquivosJson:
                  if"lei" in js:
                        os.remove(f"./{js}")

    arquivos = glob.glob("./*.csv")
    

    for a in arquivos:
            if "comp" in a:
                os.remove(f"./{a}")
    

    print("-------Arquivo enviado para bucket no prefixo ouro------------")                     
  except KeyboardInterrupt:
       print("Código interrompido de forma brusca!")

ouro()