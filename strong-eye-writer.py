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
║    -  Inicie o monitoramento.                                                       ║
║                                                                                     ║
╚═════════════════════════════════════════════════════════════════════════════════════╝""")
    login()

def validando_maquina():
    global uuid
    uuid = obter_uuid_da_placa()
    url = f"http://{IP_API}:{PORTA_API}/radares/buscarPorUuid/{uuid}"

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

            url = f"http://{IP_API}:{PORTA_API}/radares/cadastrar"
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

def coletar_dados():
    print("Monitoramento ainda não implementado.")
    return True

renderizar_index()