import pandas as pd
import psutil
from datetime import datetime
import os

while True:
    try:
        radar = str(input("\nQual o radar? "))
        break
    except ValueError:
        print("Escreva um radar corretamente")


header = [
    'radar',
    'horario',
    'cpu usada %',
    'quantidade nucleos',
    'frequencia cpu',
    'load average',
    'processos cpu',
    'memoria total',
    'memoria usada %',
    'memoria disponível',
    'disco total',
    'disco usado',
    'disco disponível',
    'disco usado %',
    'bytes enviados',
    'bytes recebidos',
    'erros de entrada',
    'erros de saida',
    'pacotes descartados'
]

lista_dados = []

for x in range(5):

    dados = {
        'radar': radar,
        'horario': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        'cpu usada %': psutil.cpu_percent(interval=1),
        'quantidade nucleos': psutil.cpu_count(),
        'frequencia cpu': psutil.cpu_freq().current,
        'load average': psutil.getloadavg()[0],
        'processos cpu': len(psutil.pids()),

        'memoria total': psutil.virtual_memory().total,
        'memoria usada %': psutil.virtual_memory().percent,
        'memoria disponível': psutil.virtual_memory().free,


        'disco total': psutil.disk_usage("/").total,
        'disco usado': psutil.disk_usage("/").used,
        'disco disponível': psutil.disk_usage("/").free,
        'disco usado %': psutil.disk_usage("/").percent,

        'bytes enviados': psutil.net_io_counters(
            pernic=False,
            nowrap=True
        ).bytes_sent,
        'bytes recebidos': psutil.net_io_counters(
            pernic=False,
            nowrap=True
        ).bytes_recv,
        'erros de entrada': psutil.net_io_counters(
            pernic=False,
            nowrap=True
        ).errin,
        'erros de saida': psutil.net_io_counters(
            pernic=False,
            nowrap=True
        ).errout,
        'pacotes descartados': psutil.net_io_counters(
            pernic=False,
            nowrap=True
        ).dropin + psutil.net_io_counters(
            pernic=False,
            nowrap=True
        ).dropout

    }

    lista_dados.append(dados)


dados = pd.DataFrame(lista_dados, columns=header)

if os.path.exists(f'./csv/{radar}.csv'):

    dados.to_csv(
        f'./csv/{radar}.csv',
        mode='a',
        sep=';',
        index=False,
        header=False
    )

else:

    dados.to_csv(
        f'./csv/{radar}.csv',
        mode='w',
        sep=';',
        index=False,
        header=True
    )
