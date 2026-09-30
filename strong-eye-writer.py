import requests
import platform
import subprocess
from getpass import getpass

# VARIAVEIS:
IP_API = "localhost"
PORTA_API = 3333

id_usuario = None
nome_usuario = None
id_empresa = None
uuid = None
id_radar = None
maquina = None
modelo_nome = None

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
    url = f"http://{IP_API}:{PORTA_API}/usuarios/autenticar"
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
            return True
        else:
            print("Erro: Email e/ou senha inválido(s)")
            return False

    except requests.exceptions.Timeout:
        print("Erro: O servidor demorou muito para responder")
    return login()

login()