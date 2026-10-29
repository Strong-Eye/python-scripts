import boto3
import pandas
import os
import glob
import mysql.connector
from datetime import datetime 
from datetime import date 
import time



def descobrir_nome(uuid):

    mydb = mysql.connector.connect(
                   host="localhost",
            user="USER",
            password="SENHA",
            database="DATABASE"
    )
    
      
    try:

            sql = f"select nome_fantasia from empresas e Join radares r on r.fk_empresa = e.id where uuid = '{uuid}';";
            cursor = mydb.cursor(dictionary=True)
            
            cursor.execute(sql)
            
            resultado = cursor.fetchall()    

            
            

            return resultado
    except :
                    print("consulta no banco falhou com o uuid")


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
                    print("Deu ruim")




def prata():

  try:
   
    session = boto3.Session(
        aws_access_key_id="AWS_ACCESS_KEY",
        aws_secret_access_key="AWS_SECRET_ACCESS",
        aws_session_token="AWS_SESSION_TOKEN",
        region_name="us-east-1",
    )

    s3_client = session.client("s3")
    s3_resource = session.resource("s3")

    
    bucket = s3_resource.Bucket("NOME_BUCKET")
    buckets_objects = bucket.objects.all()
    objects = []
    

    for i in buckets_objects:

        if( "bronze/ip" in i.key):
            objects.append(i.key)

        

    
    print(f"-------Objetos do bucket encontrados com sucesso------------")
    contador = 0 
    dfs = [] 
    for j in objects:
        
    
        with open(f'./comp{contador}.csv', 'wb') as f:
            s3_client.download_fileobj('NOME_BUCKET', f'{j}', f) 
            f.write(b'\n')
        
        arq = glob.glob("./*.csv");
        
        for aq in arq:
        
                 df = pandas.read_csv(aq)
                 dfs.append(df)
                 for aq in arq:
                    if "comp" in aq:
                        os.remove(f"./{aq}")
        contador += 1

    arquivos = glob.glob("./*.csv");
    
    leitura = pandas.concat(dfs, ignore_index=True)

    
    cpuR = []
    for k in leitura["cpu"]:
        if( k == None ):
            leitura.drop(k, axis = 1)
        
        k = round(k , 1)

        cpu = round(k,1);
        cpuR.append(cpu)
    leitura["cpu"] = cpuR


    ramR = []
    for r in leitura["ram"]:
            if( r == None ):
               leitura["ram"] = 0.0;
            
            r = round(r , 2)
    
            ram = round(r,2);
            ramR.append(ram)
    leitura["ram"] = ramR

    discoR = []
    for r in leitura["disco"]:
            if( r == None ):
                leitura.drop("disco")
            
            r = round(r , 2)
    
            disco = round(r,2); 
            discoR.append(disco)

    leitura["disco"] = discoR    

    mydb = mysql.connector.connect(
        host="localhost",
        user="USER",
        password="SENHA",
        database="DATABASE"
    )

   
    

    maxCpu = []
    maxRam = []
    maxDisco = []
    maxNet = []
    minCpu = []
    minRam = []
    minDisco = []
    minNet = []
    empresaId = []

    print("leitura com o banco de dados iniciada")
    for l in leitura['uuid']:

        

        try:

            sql = f"SELECT * FROM parametros p JOIN radares ON p.fk_radar = radares.id WHERE radares.uuid = '{l}' ;";
            cursor = mydb.cursor(dictionary=True)
            
            cursor.execute(sql)
            
            resultado = cursor.fetchall()    
                       

            if(len(resultado) > 0):

                maxCpu.append(resultado[0]['valor_maximo'])
                minCpu.append(resultado[0]['valor_minimo'])
                maxRam.append(resultado[1]['valor_maximo'])
                minRam.append(resultado[1]['valor_minimo'])
                maxDisco.append( resultado[2]['valor_maximo'])
                minDisco.append(resultado[2]['valor_minimo'])
                maxNet.append(resultado[3]['valor_maximo'])
                minNet.append(resultado[3]['valor_minimo'])
                empresaId.append(resultado[0]['fk_empresa'])

            else:

                leitura["Valor maximo CPU"] = 0.0
                leitura["Valor minimo CPU"] = 0.0
                leitura["Valor maximo RAM"] = 0.0
                leitura["Valor minimo RAM"] = 0.0
                leitura["Valor maximo DISCO"] = 0.0
                leitura["Valor minimo DISCO"] = 0.0
                leitura["Valor maximo NET"] = 0.0
                leitura["Valor minimo NET"] = 0.0
                leitura["Empresa ID"] = 0
                
            
        except :
            print("Conexão com o banco falhou")
    
    leitura["Valor maximo CPU"] = maxCpu
    leitura["Valor minimo CPU"] = minCpu
    leitura["Valor maximo RAM"] = maxRam
    leitura["Valor minimo RAM"] = minRam
    leitura["Valor maximo DISCO"] = maxDisco
    leitura["Valor minimo DISCO"] = minDisco
    leitura["Valor maximo NET"] = maxNet
    leitura["Valor minimo NET"] = minNet
    leitura["Empresa ID"] = empresaId

    print("Data frame criado!")

    data = datetime.now()
    dia = date.today()

    

    for a in arquivos:
            if "comp" in a:
                os.remove(f"./{a}")

            
    try:
        nomes = descobrir_quantidade();
    except:
        print("Descobrir quantidade deu errado!")
    for h in nomes:
        linhas = leitura.loc[leitura["Empresa ID"] == h["id"]]
        leituraUnica = pandas.DataFrame(linhas)
        leituraUnica.to_csv(f"leituraCompleta_{dia}_{data.hour}-{data.minute}_{h["nome_fantasia"]}.csv", index= False)

 
                      
        arquivos2 = glob.glob("./*.csv");

        for a2 in arquivos2:
            
            
            a3 = a2[2:]
            s3_client.upload_file(f'{a2}', "NOME_BUCKET", f"NOME_PREFIXO_SILVER/{a3}")

        for ad in arquivos2:
          if "lei" in ad:
             os.remove(f"./{ad}")

    print("-------Arquivos enviados para bucket no prefixo prata------------")          



    time.sleep(60)
    prata()
  except KeyboardInterrupt:
        print("Código interrompido de forma brusca")    
         
prata();    