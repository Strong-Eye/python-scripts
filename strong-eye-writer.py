import pandas as pd 
import glob # glob = "pega" e unifica os arquivos csv

arquivos_csv = glob.glob('./csv/*.csv') # pega todos os arquivos csv da pasta 'csv'

df = pd.concat([pd.read_csv(arquivo, sep=';') for arquivo in arquivos_csv], ignore_index=True) # junta todos os arquivos csv na tabela 'df' e lê um por um


# print(f'\n------------------ STATUS CPU POR RADAR ------------------\n')

def classificar_cpu(cpu): # função classificação de cpu

    if cpu > 70:
        return 'crítico'
    elif cpu >= 60:
        return 'atenção'
    else: 
        return 'normal'

df['status_cpu'] = df['cpu usada %'].apply(classificar_cpu) # aplica a função na coluna 'cpu' , criando uma nova coluna chamada 'status_cpu'

problemas_de_cpu = df[df['status_cpu'] == 'crítico'].groupby('radar').size() # filtra só os status 'críticos', agrupa por usuário e conta por meio do 'size()' quantas vezes cada usuário apareceu com status 'critico'

print(f'\n------------------ MÉDIA DE CPU POR RADAR ------------------\n')

media_cpu = df['media_cpu'] = df.groupby('radar')['cpu usada %'].mean() # cálculando a média de cpu por usuário
    
for usuario, cpu in media_cpu.items():
    situacao_cpu =  classificar_cpu(cpu)  # ver em qual categoria a situação se encaixa por usuárfio, por isso eu criei essa "situação_cpu"
    print(f"{usuario} - {cpu:.2f}% ({situacao_cpu})")


print(f'\n------------------ PICO DE CPU POR RADAR ------------------\n')


pico_cpu = df['pico_cpu'] = df.groupby('radar')['cpu usada %'].max()

for usuario, cpu in pico_cpu.items():
    situacao_cpu =  classificar_cpu(cpu) 
    print(f"{usuario} - {cpu:.2f}% ({situacao_cpu})")

# print(f'\n------------------ STATUS RAM POR RADAR ------------------\n')

def classificar_ram(ram): # função de classificação de ram

    if ram > 70:
        return 'crítico'
    elif ram >= 60:
        return 'atenção'
    else: 
        return 'normal'

df['status_ram'] = df['memoria usada %'].apply(classificar_ram) # aplica a função na coluna 'memoria usada %' , criando uma nova coluna chamada 'status_ram'


problemas_de_ram = df[df['status_ram'] == 'crítico'].groupby('radar').size() # filtra só os status 'críticos', agrupa por usuário e conta por meio do 'size()' quantas vezes cada usuário apareceu com status 'critico'


print(f'\n------------------ MÉDIA DE RAM POR RADAR ------------------\n')

media_ram = df['media_ram'] = df.groupby('radar')['memoria usada %'].mean()

for usuario, ram in media_ram.items():
    situacao_ram =  classificar_ram(ram) 
    print(f"{usuario} - {ram:.2f}% ({situacao_ram})")


print(f'\n------------------ PICO DE RAM POR RADAR ------------------\n')


pico_ram = df['pico_ram'] = df.groupby('radar')['memoria usada %'].max()

for usuario, ram in pico_ram.items():
    situacao_ram =  classificar_ram(ram) 
    print(f"{usuario} - {ram:.2f}% ({situacao_ram})")


# print(f'\n------------------ STATUS DISCO POR RADAR ------------------\n')

def classificar_disco(disco): # função de classificação de disco

    if disco > 70:
        return 'crítico'
    elif disco >= 60:
        return 'atenção'
    else: 
        return 'normal'

df['status_disco'] = df['disco usado %'].apply(classificar_disco) # aplica a função na coluna 'disco usado %' , criando uma nova coluna chamada 'status'

problemas_de_disco = df[df['status_disco'] == 'crítico'].groupby('radar').size() # filtra só os status 'críticos', agrupa por usuário e conta por meio do 'size()' quantas vezes cada usuário apareceu com status 'critico'


print(f'\n------------------ MÉDIA DO DISCO POR RADAR ------------------\n')

media_disco = df['media_disco'] = df.groupby('radar')['disco usado %'].mean()


for usuario, disco in media_disco.items():
    situacao_disco =  classificar_disco(disco)  
    print(f"{usuario} - {disco:.2f}% ({situacao_disco})")


print(f'\n------------------ CRESCIMENTO MÉDIO DO DISCO POR RADAR ------------------\n')

df['horario'] = pd.to_datetime(df['horario']) # transforma o timestamp em tempo
df = df.sort_values(['radar', 'horario']) # ordena por usuário e ordem de tempo, por isso o 'sort_values'

df['crescimento_disco'] = df.groupby('radar')['disco usado %'].diff() # o '.diff' calcula a diferença entre uma medição de disco e a seguinte. Ex: 30% -> 35% = 5%
df['tempo_minutos'] = ((df.groupby('radar')['horario'].diff().dt.total_seconds()) / 60) # calcula quantos min se passou entre uma medição e outra (mesmo esquema da anterior) - e transforma em min -> '/60' -> transforma seg em min
df['taxa_crescimento'] = df['crescimento_disco'] / df['tempo_minutos'] # a taxa de crescimento é = o crescimento do disco / pelo tempo (como se fosse o cálculo da velocidade média)
crescimento_medio = df.groupby('radar')['taxa_crescimento'].mean() # pega a média da taxa de crescimento por usuário

for usuario, crescimento in crescimento_medio.items():
    print(f"{usuario} - {crescimento:.2f}% por minuto")

print(f'\n------------------ STATUS DE REDE POR RADAR ------------------\n')

df['bytes_enviados_diff'] = df.groupby('radar')['bytes enviados'].diff() # 'diff' calcula a variação entre os bytes enviados (mesmo esquema das anteriores)
df['bytes_recebidos_diff'] = df.groupby('radar')['bytes recebidos'].diff() # 'diff' calcula a variação entre os bytes recebidos


df['sem_trafego'] = (df['bytes_enviados_diff'] <= 0) & (df['bytes_recebidos_diff'] <= 0) # cria uma nova coluna chamada 'sem_trafego' para ver se algum usuário teve tráfego de dados ou nn -> true = sem_trafico
sem_trafego = df.groupby('radar')['sem_trafego'].sum() # soma de quantas vezes cada usuário ficou sem tráfego


def classificar_rede(sem_trafego): # classificação da rede baseado na soma de 'sem_trafego'

    if sem_trafego == 0: # os bytes recebidos e enviados circulacpu normalmente, nn constando na sem_trafego, ent é igual a zero
        return 'online'
    elif sem_trafego <=3: # 3 vezes o usuário ficou sem tráfego
        return 'instável'
    else: #+3 offline
        return 'offline'

status_rede = sem_trafego.apply(classificar_rede) # aplica essa função na coluna 'sem_trafego', que foi criada anteriormente

for usuario, status in status_rede.items(): # print
    print(f"{usuario} - {status}")

problemas_de_rede = sem_trafego.sort_values(ascending=False) # ordena em ordem decrescente os usuários com mais até menos problemas de rede, por isso o 'ascending=False'

print(f'\n------------------ RELATÓRIO FINAL ------------------\n')

# em cada componente eu já utilizei group by antes, ent ela já aparece nessa nova tabela problemas 

problemas = pd.DataFrame({ # cria uma nova tabela só com os problemas
    'cpu': problemas_de_cpu,
    'ram': problemas_de_ram, # quantos alertas 'críticos' cada user teve
    'disco': problemas_de_disco,
    'rede': sem_trafego # quantas vezes esse user ficou sem rede
}).fillna(0).astype(int) # deixa esses números em formato inteiro, ou seja, ('int')

# print(problemas)

print(f'\n---- RADAR | PROBLEMA\n')

# Exibe cada usuário e a quantidade de problemas de CPU, RAM, DISCO E REDE
for usuario, coluna in problemas.iterrows(): # faz isso percorrendo cada linha 
    print(f"{usuario} - CPU: {coluna['cpu']} | RAM: {coluna['ram']} | Disco: {coluna['disco']} | Rede: {coluna['rede']}")


print(f'\n---- PROBLEMA MAIS RECORRENTE\n')

total_por_problema = problemas.sum() # vẽ a soma de cada problema 
problema_mais_recorrente = total_por_problema.idxmax() # ve qual o nome do problema mais recorrente por meio do 'idmax'
quantidade_problema = total_por_problema.max() # pega o valor total desse problema, por isso o max()

print(f"Problema mais recorrente: {problema_mais_recorrente}")
print(f"Quantidade de problemas: {quantidade_problema}\n")

print(f'\n------------------ SAÚDE GERAL ------------------\n')

print("\n---- CPU\n")
print(media_cpu.apply(classificar_cpu).value_counts().to_string()) # aplica a funçãod de classificar cada cpu pela média do usuário e conta quantas vezes cada status aconteceu. EX: estado critico = 10 vezes
# to.string deixa esse cálculo formatado

print("\n---- RAM\n")
print(media_ram.apply(classificar_ram).value_counts().to_string())

print("\n---- DISCO\n")
print(media_disco.apply(classificar_disco).value_counts().to_string())
