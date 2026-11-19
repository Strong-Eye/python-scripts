import boto3
import pandas
import os
import json
import glob
import mysql.connector
from datetime import datetime 
from datetime import date 
import time
import numpy as np


def descobrir_quantidade():

    mydb = mysql.connector.connect(
            host="localhost",
            user="USER",
            password="SENHA",
            database="DATABASE"
    )
    
      
    try:

            sql = f"select nome_fantasia, id from empresas;";
            cursor = mydb.cursor(dictionary=True)
            
            cursor.execute(sql)
            
            resultado = cursor.fetchall()    

            
        

            return resultado
    except :
                    print("Consulta no banco falhou")

def ouro():

  try:  
    session = boto3.Session(
   aws_access_key_id="AWS_ACCESS_KEY",
   aws_secret_access_key="AWS_SECRET_ACCESS",
   aws_session_token="AWS_SESSION_TOKEN",
   region_name="us-east-1",  # Substitua pela sua região se necessário
    )

    s3_client = session.client("s3")
    s3_resource = session.resource("s3")

    
    bucket = s3_resource.Bucket("NOME_BUCKET")
    buckets_objects = bucket.objects.all()
    objects = []

    
    

    for i in buckets_objects:
        #exemplo READ-1.csv / Letras iniciais = REA  
        if( "raw/3_Letras_iniciais_dos_Arquivos" in i.key):
            objects.append(i.key)

    

    
    print(f"-------Objetos do bucket alcançados com sucesso------------")

    i = 0;

    dfs = []
    for j in objects:
        
        
        with open(f'./comp{i}.csv', 'wb') as f:
            s3_client.download_fileobj('NOME_BUCKET', f'{j}', f) 
            f.write(b'\n')
        
        arq = glob.glob("./*.csv")
        for aq in arq:
             df = pandas.read_csv(aq)
             dfs.append(df)
             if "comp" in aq:
                  os.remove(aq)
        i += 1;    



   
    leitura = pandas.concat(dfs, ignore_index=True)
    print("Data frame foi criado")

    try:
        empresas = descobrir_quantidade()
        print("Consulta no banco realizada")
    except:
         print("consulta no banco falhou") 
    for e in empresas:
        jsonFinal = [];
        linhas = leitura.loc[leitura["Empresa ID"] == e["id"]]
        leituraUnica = pandas.DataFrame(linhas)
        c = leituraUnica[leituraUnica['Empresa ID'] == e["id"]].index.values.astype(int)
        
        for l in c:
            horas = list(range(len(leituraUnica)))
            
            def calc_predicao(componente):
                from datetime import datetime, timedelta
                data_limite = datetime.now() - timedelta(days=3)
                df_filtro = leituraUnica[(leituraUnica['Empresa ID'] == e['id']) & (leituraUnica['data/hora'] >= data_limite)]
                horas = list(range(len(df_filtro)))
                y_vals = df_filtro[componente].values
                if len(y_vals) < 2:
                    return None, None, None
                inclinacao, intercepto = np.polyfit(horas, y_vals, 1)
                correlacao = np.corrcoef(horas, y_vals)[0, 1]
                r_quadrado = correlacao ** 2
                limite_max = df_filtro[f'Valor maximo {componente.upper()}'].iloc[0]
                if inclinacao != 0:
                    return (limite_max - intercepto) / inclinacao, r_quadrado, inclinacao
                else:
                    return None, None, None
            
            predicao = []
            for comp in ['ram', 'cpu', 'disco']:
                valor_pred, r_quadrado, inclinacao = calc_predicao(comp)
                if valor_pred is not None:
                    valor_pred = round(valor_pred, 1)
                    r_quadrado = round(r_quadrado, 3)
                    inclinacao = round(inclinacao, 3)
                predicao.append({
                    comp.upper(): {
                        'horas': valor_pred,
                        'r_quadrado': r_quadrado,
                        'inclinacao': inclinacao
                    }
                })

            json1 = {
                'maquina': leituraUnica['maquina'][l],
                'uuid': leituraUnica['uuid'][l],
                'cpu': float(leituraUnica['cpu'][l]),
                'ram': float(leituraUnica['ram'][l]),
                'disco': float(leituraUnica['disco'][l]),
                'rede': float(leituraUnica['rede'][l]),
                'total_processos': int(leituraUnica['total_processos'][l]),
                'data/hora': leituraUnica['data/hora'][l],
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
            json1 = {
                'maquina': leituraUnica['maquina'][l],
                'uuid': leituraUnica['uuid'][l],
                'cpu': float(leituraUnica['cpu'][l]),
                'ram':float(leituraUnica['ram'][l]),
                'disco': float(leituraUnica['disco'][l]),
                'rede':float(leituraUnica['rede'][l]),
                'total_processos':int(leituraUnica['total_processos'][l]),
                'data/hora':leituraUnica['data/hora'][l],
                'Valor maximo CPU':int(leituraUnica['Valor maximo CPU'][l]),
                'Valor minimo CPU':int(leituraUnica['Valor minimo CPU'][l]),
                'Valor maximo RAM':int(leituraUnica['Valor maximo RAM'][l]),
                'Valor minimo RAM':int(leituraUnica['Valor minimo RAM'][l]),
                'Valor maximo DISCO':int(leituraUnica['Valor maximo DISCO'][l]),
                'Valor minimo DISCO':int(leituraUnica['Valor minimo DISCO'][l]),
                'Valor maximo NET':int(leituraUnica['Valor maximo NET'][l]),
                'Valor minimo NET':int(leituraUnica['Valor minimo NET'][l]),
                'Empresa ID':int(leituraUnica['Empresa ID'][l])
                }
            
            jsonFinal.append(json1)
            
        data = datetime.now()    
        dia = date.today()
        with open(f'leitura_{dia}_{data.hour}-{data.minute}_{e["nome_fantasia"]}.json','w', encoding='cp1252') as f:
                json.dump(jsonFinal,f,ensure_ascii=False, indent = 2 )      
        s3_client.upload_file(f'./leitura_{dia}_{data.hour}-{data.minute}_{e["nome_fantasia"]}.json', "atvd-itops", f"ouro/leitura_{dia}_{data.hour}-{data.minute}_{e["nome_fantasia"]}.json")  

        

        print("Arquivo json criado com sucesso")        
        arquivosJson = glob.glob("./*.json");

        for js in arquivosJson:
                  if"lei" in js:
                        os.remove(f"./{js}")

    arquivos = glob.glob("./*.csv");
    

    for a in arquivos:
            if "comp" in a:
                os.remove(f"./{a}")
    

    print("-------Arquivo enviado para bucket no prefixo ouro------------")            
    time.sleep(60)
    ouro()            
  except KeyboardInterrupt:
       print("Código interrompido de forma brusca!")

ouro();
        