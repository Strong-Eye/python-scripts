import requests
import platform
import subprocess
import psutil
import time
import os
import boto3
from pathlib import Path
from getpass import getpass
from datetime import datetime
from dotenv import load_dotenv

# VARIAVEIS:
load_dotenv()
ip_api = os.getenv("IP_API")
porta_api = os.getenv("PORTA_API")
session = os.getenv("SESSION_AWS")
bucket_name = os.getenv("BUCKET_NAME")
s3_client = boto3.client("s3")

id_usuario = None
nome_usuario = None
id_empresa = None
uuid = None
id_radar = None
maquina = None
modelo_nome = None

contador_coletas = 0
contador_lote = 1

def obter_uuid_da_placa():
    sistema = platform.system().lower()

    if sistema == "windows":
        cmd = ["powershell", "-Command", "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"]
        return subprocess.check_output(cmd, text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip()
    
    elif sistema == "linux":
        return subprocess.check_output("sudo cat /sys/class/dmi/id/product_uuid", shell=True, text=True).strip()

    else:
        return None

def login():
    url = f"http://{ip_api}:{porta_api}/usuarios/autenticar"
    email = input("Email: ")
    senha = getpass("Senha: ")
    dados = {
        "emailServer": email,
        "senhaServer": senha
    }

    try:
        fetch = requests.post(url, json=dados, timeout=10)

        if fetch.ok:
            resposta = fetch.json()

            global id_usuario, nome_usuario, id_empresa
            id_usuario = resposta['id']
            nome_usuario = resposta['nome']
            id_empresa = resposta['id_empresa']

            print(f"Login efetuado com sucesso!")
            print(f"Validando máquina...")
            return validando_maquina()
        else:
            print("Erro: Email e/ou senha inválido(s)")
            return False

    except requests.exceptions.Timeout:
        print("Erro: O servidor demorou muito para responder")
    return renderizar_index()

def renderizar_index():
    print("""
╔═════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                     ║
║  ███████╗████████╗██████╗  ██████╗ ███╗   ██╗ ██████╗    ███████╗██╗   ██╗███████╗  ║
║  ██╔════╝╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║██╔════╝    ██╔════╝╚██╗ ██╔╝██╔════╝  ║
║  ███████╗   ██║   ██████╔╝██║   ██║██╔██╗ ██║██║  ███╗   █████╗   ╚████╔╝ █████╗    ║
║  ╚════██║   ██║   ██╔══██╗██║   ██║██║╚██╗██║██║   ██║   ██╔══╝    ╚██╔╝  ██╔══╝    ║
║  ███████║   ██║   ██║  ██║╚██████╔╝██║ ╚████║╚██████╔╝   ███████╗   ██║   ███████╗  ║
║  ╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝    ╚══════╝   ╚═╝   ╚══════╝  ║
║                                                                                     ║
║═════════════════════════════════════════════════════════════════════════════════════║
║                                                                                     ║
║   Instruções:                                                                       ║
║    -  Faça login com sua conta empresarial;                                         ║
║    -  Valide esta máquina;                                                          ║
║    -  Caso necessário, realize o cadastro da mesma;                                 ║
║       -   Defina Parâmetros de coleta;                                              ║
║    -  Inicie o monitoramento.                                                       ║
║                                                                                     ║
╚═════════════════════════════════════════════════════════════════════════════════════╝""")
    login()

def validando_maquina():
    global uuid
    uuid = obter_uuid_da_placa()
    url = f"http://{ip_api}:{porta_api}/radares/buscarPorUuid/{uuid}"

    try:
        fetch = requests.get(url, params={"fkEmpresaUsuario": id_empresa}, timeout=10)

        if fetch.status_code == 204:
            print("Máquina não cadastrada.")
            return cadastrar_maquina()

        if fetch.status_code == 403:
            print("Esse computador não pertence a essa empresa.")
            return login()

        if fetch.ok:
            resposta = fetch.json()
            
            global id_radar
            id_radar = resposta[0]['id']
            global modelo_nome
            modelo_nome = resposta[0]['modelo']

            print("Máquina validada!")
            return coletar_dados()
        else:
            print(f"Erro: Falha ao se comunicar com o servidor")
            print(f"Tentando novamente...")
            return validando_maquina()

    except requests.exceptions.Timeout:
        print("Erro: O servidor demorou muito para responder")
    return renderizar_index()

def cadastrar_maquina():
    print("Iniciando cadastro de máquina...")
    modelo = input("Modelo do radar: ")
    print("Informações de endereço...")
    cep = input("Insira o cep do endereço desse radar: ")

    url = f"https://viacep.com.br/ws/{cep}/json/"

    try:
        fetch = requests.get(url, timeout=5)
        dados = fetch.json()
        if dados.get("erro"):
            print("CEP não encontrado no banco de dados.")
            return None

        longradouro = dados.get('logradouro')
        bairro = dados.get('bairro')
        localidade = dados.get('localidade')
        uf = dados.get('uf')
        estado = dados.get('estado')
        km = input("KM: ")
        complemento_validacao = input("Possui complemento? (s/n)")
        if (complemento_validacao == "s"):
            complemento = input("Insira o Complemento:")
        else:
            complemento = None

        print(f"Confirme os dados do Radar...")
        print(f"Radar:")
        print(f"Modelo: {modelo}, UUID: {uuid}")
        print(f"Enderço:")
        print(f"{longradouro}, Km {km}, {bairro}, {localidade} - {estado}/{uf}")

        confirmar_cadastro = input("Confirmar cadastro? (s/n)")
        if (confirmar_cadastro == "s"):

            url = f"http://{ip_api}:{porta_api}/radares/cadastrar"
            dados = {
                "uuidServer": uuid,
                "modeloServer": modelo,
                "fk_empresaServer": id_empresa,
                "cepServer": cep,
                "longradouroServer": longradouro,
                "bairroServer": bairro,
                "localidadeServer": localidade,
                "ufServer": uf,
                "estadoServer": estado,
                "kmServer": km,
                "complementoServer": complemento
            }

            try:
                fetch = requests.post(url, json=dados, timeout=10)
                if fetch.ok:
                    print(f"Radar cadastrado com sucesso!")
                    resposta = fetch.json()

                    global id_radar
                    id_radar = resposta.get("id")
                    global modelo_nome
                    modelo_nome = resposta.get("nome")

                    print("Iniciando cadastro dos parâmetros de máquina...")
                    cadastrar_parametros(1)
                    cadastrar_parametros(2)
                    cadastrar_parametros(3)
                    cadastrar_parametros(4)
                    print("Máquina cadastrada com sucesso!")
                    return coletar_dados()
                    
                else:
                    print(f"Erro: Falha ao se comunicar com o servidor")
                    print(f"Tentando novamente...")
                    return cadastrar_maquina()
                
            except requests.exceptions.Timeout:
                print("Erro: O servidor demorou muito para responder")
            return renderizar_index()
        
        else:
            return cadastrar_maquina()

    except requests.exceptions.Timeout:
        print("Erro: O servidor demorou muito para responder")
    return renderizar_index()

def cadastrar_parametros(fk_componente):
    atual = fk_componente
    componentes = {
        1: "CPU",
        2: "RAM",
        3: "Disco",
        4: "Rede"
    }

    confirmar = input(f"Deseja monitorar {componentes[fk_componente]}? (s/n)")
    if (confirmar == "s"):
        valor_maximo = input("Insira o valor máximo de leitura (Ex. 00.00):")
        valor_minimo = input("Insira o valor mínimo de leitura (Ex. 00.00):")

        print(f"Confirme os dados sobre monitoramento de {componentes[fk_componente]}")
        print(f"Monitorar {componentes[fk_componente]}? Sim | Valor máximo de leitura: {valor_maximo} | Valor mínimo de leitura: {valor_minimo}")
        confirmar_dados = input("Confirmar? (s/n) ")
        if (confirmar_dados == "s"):
            url = f"http://{ip_api}:{porta_api}/radares/cadastrarParametro"
            dados = {
                "fk_componenteServer": fk_componente,
                "fk_radarServer": id_radar,
                "valor_maximoServer": valor_maximo,
                "valor_minimoServer": valor_minimo
            }

            try:
                fetch = requests.post(url, json=dados, timeout=10)
                if fetch.ok:
                    print(f"Parametro de {componentes[fk_componente]} cadastrado com sucesso!")
                    return True
                else:
                    print(f"Erro: Falha ao se comunicar com o servidor")
                    print(f"Tentando novamente...")
                    return cadastrar_parametros(atual)

            except requests.exceptions.Timeout:
                print("Erro: O servidor demorou muito para responder")
            return renderizar_index()
        else:
            print(f"Tentando novamente...")
            return cadastrar_parametros(atual)

    else:
        return False    
        
def gerar_nomes_arquivo(contador_lote):
    data_hoje = datetime.now().strftime("%m-%d-%Y")
    nome_local = f"{modelo_nome}_{data_hoje}_READ-{contador_lote}.csv"
    chave_s3 = f"raw/{nome_local}"
    return nome_local, chave_s3

def enviar_arquivo(nome_arquivo, chave_s3):
    try:
        s3_client.upload_file(nome_arquivo, bucket_name, chave_s3)
        print(f"Sincronizado no S3: s3://{bucket_name}/{chave_s3}")
    except Exception as e:
        print(f"Erro ao enviar para o S3: {e}")
        
def coletar_dados():
    print("Iniciando processo de monitoramento")

    url = f"http://{ip_api}:{porta_api}/radares/buscarParametros/{id_radar}"
    
    try:
        fetch = requests.get(url, timeout=10)
    
        if fetch.ok:
            resposta = fetch.json()
                
            print(resposta)

            alvo_cpu = None
            alvo_ram = None
            alvo_disco = None
            alvo_rede = None

            if (len(resposta) == 0):
                confirmar = input("Não foram definidos parâmetros... Deseja configurar agora? (s/n) ")
                if (confirmar == 's'):
                    print("Iniciando configuração dos parâmetros de máquina...")
                    cadastrar_parametros(1)
                    cadastrar_parametros(2)
                    cadastrar_parametros(3)
                    cadastrar_parametros(4)
                    print("Todos os parametros foram configurados!")
                else:
                    print("Você pode solicitar ao seu gestor para que defina os parâmetros pela dashboard")
                    print("Abortando...")
                    renderizar_index()

            for item in resposta:
                if item["nome"] == "cpu":
                    alvo_cpu = True
                if item["nome"] == "ram":
                    alvo_ram = True
                if item["nome"] == "disco":
                    alvo_disco = True
                if item["nome"] == "rede":
                    alvo_rede = True

            print("Iniciando captura de dados:")

            try:
                while True:
                    global contador_lote
                    nome_arquivo, chave_s3 = gerar_nomes_arquivo(contador_lote)
                    
                    if not Path(f"./{nome_arquivo}").exists():
                        with open(f'./{nome_arquivo}', 'a', newline='') as csvfile:
                            csvfile.write("maquina,uuid,cpu,ram,desco,rede,total_processos,data/hora\n")
                    
                    cpu = psutil.cpu_percent(interval=1) if alvo_cpu else None
                    ram = psutil.virtual_memory().percent if alvo_ram else None
                    disco = psutil.disk_usage("/").percent if alvo_disco else None
                    total_processos = len(psutil.pids())

                    if alvo_rede == True:
                        rede_inicio = psutil.net_io_counters() 
                        time.sleep(10)
                        rede_fim = psutil.net_io_counters()
                        upload_mbps = f"{(rede_fim.bytes_sent - rede_inicio.bytes_sent) * 8 / 1_000_000:.3f}"
                    else:
                        upload_mbps = None

                    data_hora = datetime.now().replace(microsecond=0)                    
                    
                    with open(f'./{nome_arquivo}', 'a', newline='') as csvfile:
                        csvfile.write(f"{modelo_nome},{uuid},{cpu},{ram},{disco},{upload_mbps},{total_processos},{data_hora}\n")
                    
                    global contador_coletas
                    contador_coletas += 1
                    
                    if alvo_cpu: print(f"CPU: {cpu}%")
                    if alvo_ram: print(f"Memória: {ram}%")
                    if alvo_disco: print(f"Disco: {disco}%")
                    if alvo_rede: print(f"Rede: {upload_mbps} Mbps")
                    
                    print("Data e hora local:", data_hora)
                    print("---------------------------------------------")
                    
                    if (contador_coletas == 3):
                        enviar_arquivo(nome_arquivo, chave_s3)
                        contador_coletas = 0
                        contador_lote += 1
                    
                    time.sleep(5)
                    
            except KeyboardInterrupt:
                print("Programa encerrado de forma abrupta")
                
            print("Programa encerrado.")
            
            print("Máquina validada!")
            return True
        
        else:
            print(f"Erro: Falha ao se comunicar com o servidor")
            print(f"Tentando novamente...")
            return coletar_dados()
    
    except requests.exceptions.Timeout:
        print("Erro: O servidor demorou muito para responder")
    return renderizar_index() 

renderizar_index()