#pip install boto3
#pip install api-brasil
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from api_brasil import APIBrasilClient, WhatsAppApi
import pandas as pd
import time


# Configuração do S3
ACCESS_KEY = "MINHAKEY"
SECRET_KEY = "MINHAKEY"     
REGION = "us-east-1"                 # Substitua pela região correta do seu bucket (ex: us-east-2 ou sa-east-1)
BUCKET_NAME = "relmeirelles"

# Configuração da API Brasil
BEARER_TOKEN = "MINHAKEY"  # Substitua pelo seu Bearer Token da API Brasil
DEVICE_TOKEN = "MINHAKEY"      # Substitua pelo seu Device Token


# Criando o cliente do S3 com as credenciais diretamente no código
s3 = boto3.client(
    "s3",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION
)

def upload_to_s3(arquivo_local, nome_no_s3):
    """
    Faz upload do arquivo para o bucket especificado.
    """
    try:
        content_type = "application/pdf" if arquivo_local.endswith('.pdf') else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        s3.upload_file(
            arquivo_local,
            BUCKET_NAME,
            nome_no_s3,
            ExtraArgs={"ContentType": content_type}  # Define o tipo de conteúdo como PDF ou XLSX
        )
        print(f"Arquivo enviado: {nome_no_s3}")
    except NoCredentialsError:
        print("Erro: Credenciais não encontradas.")
    except PartialCredentialsError:
        print("Erro: Credenciais incompletas.")
    except Exception as e:
        print(f"Erro ao fazer upload: {e}")

def verificar_disponibilidade_arquivo(nome_no_s3):
    """
    Verifica se o arquivo está disponível no S3.
    """
    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=nome_no_s3)
        print(f"Arquivo disponível no S3: {nome_no_s3}")
        return True
    except Exception as e:
        print(f"Arquivo não disponível no S3: {nome_no_s3}")
        return False

def gerar_url_pre_assinada(nome_no_s3, expiracao=3600):
    """
    Gera uma URL pré-assinada para acessar o arquivo no S3.
    :param nome_no_s3: Caminho do arquivo no S3.
    :param expiracao: Tempo de expiração da URL em segundos (padrão: 3600 segundos = 1 hora).
    :return: URL pré-assinada.
    """
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': nome_no_s3},
            ExpiresIn=expiracao
        )
        print(f"URL pré-assinada gerada: {url}")
        return url
    except Exception as e:
        print(f"Erro ao gerar URL pré-assinada: {e}")
        return None

def verificar_url(url):
    """
    Verifica se a URL pré-assinada está acessível.
    """
    try:
        response = requests.head(url)
        if response.status_code == 200:
            print(f"URL acessível: {url}")
            return True
        else:
            print(f"URL inacessível: {url}, Status Code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Erro ao verificar URL: {e}")
        return False

def enviar_mensagem(api_brasil_client, whatsapp_api, numero_destino, mensagem):
    whatsapp_api.to_number(phone_number=numero_destino)
    response, status_code = whatsapp_api.send_message(message=mensagem)
    print(f"Mensagem enviada para {numero_destino}: {response}, {status_code}")
    return status_code

def enviar_arquivo(api_brasil_client, whatsapp_api, numero_destino, url_pre_assinada, descricao_arquivo):
    whatsapp_api.to_number(phone_number=numero_destino)
    response, status_code = whatsapp_api.send_file(file_path=url_pre_assinada, file_description=descricao_arquivo)
    print(f"Arquivo enviado para {numero_destino}: {response}, {status_code}")
    return status_code

# Instancie o client da APIBrasil
api_brasil_client = APIBrasilClient(bearer_token=BEARER_TOKEN)

# Usando a API de WhatsApp
whatsapp_api = WhatsAppApi(api_brasil_client=api_brasil_client, device_token=DEVICE_TOKEN)

# Ler a planilha lista_de_envio
df = pd.read_excel('lista_de_envio.xlsx')

# Dicionário para armazenar URLs pré-assinadas
urls_pre_assinadas = {}

# Passo 1: Fazer upload de todos os arquivos para o S3
for index, row in df.iterrows():
    arquivos_locais = [row['arquivo_1'], row['arquivo_2']]
    for arquivo_local in arquivos_locais:
        if pd.notna(arquivo_local):  # Verifica se o campo não está vazio
            nome_no_s3 = f"uploads/{arquivo_local}"
            # Enviar o arquivo para o S3
            upload_to_s3(arquivo_local, nome_no_s3)

# Passo 2: Esperar 2 minutos
print("Aguardando 2 minutos para garantir que todos os arquivos estejam disponíveis no S3...")
time.sleep(120)  # Pausa de 2 minutos

# Passo 3: Gerar URLs pré-assinadas para todos os arquivos
for index, row in df.iterrows():
    arquivos_locais = [row['arquivo_1'], row['arquivo_2']]
    for arquivo_local in arquivos_locais:
        if pd.notna(arquivo_local):  # Verifica se o campo não está vazio
            nome_no_s3 = f"uploads/{arquivo_local}"
            # Verificar a disponibilidade do arquivo no S3
            if verificar_disponibilidade_arquivo(nome_no_s3):
                # Gerar URL pré-assinada para o arquivo
                url_pre_assinada = gerar_url_pre_assinada(nome_no_s3)
                if url_pre_assinada:
                    # Verificar se a URL pré-assinada está acessível
                    if verificar_url(url_pre_assinada):
                        urls_pre_assinadas[arquivo_local] = url_pre_assinada
                    else:
                        print(f"URL pré-assinada não acessível para {arquivo_local}.")
                else:
                    print(f"Falha ao gerar URL pré-assinada para {arquivo_local}.")
            else:
                print(f"Arquivo {nome_no_s3} não está disponível no S3.")

# Lista para armazenar mensagens que falharam
mensagens_falhadas = []

# Passo 4: Enviar mensagens e arquivos via WhatsApp
for index, row in df.iterrows():
    numero_destino = str(row['whatsapp'])
    nome_pessoa = row['nome']
    
    # Mensagem personalizada
    mensagem = f"Olá {nome_pessoa}, segue o documento solicitado:"

    # Enviar mensagem de texto
    status_code = enviar_mensagem(api_brasil_client, whatsapp_api, numero_destino, mensagem)
    if status_code != 200:
        mensagens_falhadas.append(('mensagem', numero_destino, mensagem, None))
    
    # Enviar cada arquivo
    arquivos_locais = [row['arquivo_1'], row['arquivo_2']]
    for arquivo_local in arquivos_locais:
        if pd.notna(arquivo_local):  # Verifica se o campo não está vazio
            if arquivo_local in urls_pre_assinadas:
                # Enviar arquivo
                url_pre_assinada = urls_pre_assinadas[arquivo_local]
                status_code = enviar_arquivo(api_brasil_client, whatsapp_api, numero_destino, url_pre_assinada, arquivo_local)
                if status_code != 200:
                    mensagens_falhadas.append(('arquivo', numero_destino, None, url_pre_assinada))
                # Pausa entre os envios para evitar problemas de envio rápido
                time.sleep(2)
            else:
                print(f"URL pré-assinada não encontrada para {arquivo_local}.")
    
    # Pausa entre o envio para contatos diferentes
    time.sleep(2)  # Pausa de 2 segundos antes de enviar para o próximo contato

# Passo 5: Reenviar mensagens que falharam
print("Reenviando mensagens que falharam...")
for tentativa in range(3):  # Até 3 tentativas
    if not mensagens_falhadas:
        break
    falhas_restantes = []
    for tipo, numero_destino, mensagem, url_pre_assinada in mensagens_falhadas:
        if tipo == 'mensagem':
            status_code = enviar_mensagem(api_brasil_client, whatsapp_api, numero_destino, mensagem)
            if status_code != 200:
                falhas_restantes.append((tipo, numero_destino, mensagem, url_pre_assinada))
        elif tipo == 'arquivo':
            status_code = enviar_arquivo(api_brasil_client, whatsapp_api, numero_destino, url_pre_assinada, 'Reenvio de arquivo')
            if status_code != 200:
                falhas_restantes.append((tipo, numero_destino, mensagem, url_pre_assinada))
        # Pausa entre os envios para evitar problemas de envio rápido
        time.sleep(2)
    mensagens_falhadas = falhas_restantes
    # Pausa entre as tentativas
    time.sleep(10)

if mensagens_falhadas:
    print("Algumas mensagens ainda falharam após 3 tentativas.")
else:
    print("Todas as mensagens foram enviadas comsucesso.")
