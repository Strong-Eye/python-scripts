import boto3
import pandas
import os
import json
import glob
import mysql.connector
from datetime import datetime 
from datetime import date 
import time


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
        