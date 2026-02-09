"""
Configurações do Sistema - Informações do servidor UFF
Edite conforme necessário
"""

# URLS DO SISTEMA UFF
LOGIN_URL = "https://app.uff.br/auth/realms/master/protocol/openid-connect/auth"
BASE_URL = "https://app.uff.br/graduacao/administracaoacademica"
LOGOUT_URL = "https://app.uff.br/auth/realms/master/protocol/openid-connect/logout"

# DIRETÓRIOS
RELATORIOS_FOLDER = "relatorios_baixados"
ARQUIVO_LISTA = "arquivos_relatorios.txt"

# TIMEOUTS E INTERVALOS
TIMEOUT_PROCESSAMENTO = 600  # 10 minutos para processar um relatório
INTERVALO_VERIFICACAO = 10   # Verificar status a cada 10 segundos
TIMEOUT_REQUESTS = 30         # Timeout para requisições HTTP

# MAPEAMENTO DE CURSOS - Como aparecem no sistema
CURSOS_SISTEMA = {
    'Química (Licenciatura) (12700)': {
        'nome_display': 'Licenciatura',
        'codigo_form': '12700',
        'codigo_curso': '1',
        'palavra_chave': 'LICENCIADO'
    },
    'Química (Bacharelado) (312700)': {
        'nome_display': 'Bacharelado',
        'codigo_form': '312700',
        'codigo_curso': '1',
        'palavra_chave': 'BACHAREL'
    },
    'Química Industrial (12709)': {
        'nome_display': 'Industrial',
        'codigo_form': '12709',
        'codigo_curso': '13',
        'palavra_chave': 'QUÍMICO INDUSTRIAL'
    }
}

# FORMAS DE INGRESSO POR SEMESTRE
FORMAS_INGRESSO = {
    1: "SISU 1ª Edição",    # 1º semestre (início do ano)
    2: "SISU 2ª Edição"     # 2º semestre (meio do ano)
}

# LOCALIDADE (Niterói)
LOCALIDADE_ID = '8'
LOCALIDADE_NOME = 'Niterói'

# STATUS DOS ALUNOS - Como aparecem no relatório
STATUS_ALUNOS = {
    'ATIVO': 'Ativo',
    'CANCELADO': 'Cancelado',
    'TRANCADO': 'Trancado',
    'FORMADO': 'Formado',
    'JUBILADO': 'Jubilado',
    'DESLIGADO': 'Desligado'
}

# MOTIVOS DE CANCELAMENTO
MOTIVOS_CANCELAMENTO = {
    'DESISTÊNCIA': 'Desistência',
    'ABANDONO': 'Abandono',
    'CANCELAMENTO': 'Cancelamento Administrativo',
    'REPROVAÇÃO': 'Reprovação em Disciplinas',
    'INATIVIDADE': 'Inatividade Acadêmica',
    'JUBILAÇÃO': 'Jubilação',
    'FORMAÇÃO': 'Formação',
    'NÃO INFORMADO': 'Não Informado',
    'OUTROS': 'Outros Motivos'
}

# MODALIDADES DE INGRESSO (SISU)
MODALIDADES_INGRESSO = {
    'A': 'AC',  # Ampla Concorrência
    'L': 'AA',  # Ações Afirmativas (Lei de Cotas)
}

# PADRÕES PARA IDENTIFICAÇÃO NO RELATÓRIO
PADROES_IDENTIFICACAO = {
    'aluno_por_curso': 'Alunos de',  # Última linha contém: "Alunos de TIPO - Curso: XX"
    'separador_linha': ':',           # Separador entre tipo e quantidade
}

# USER AGENT PARA REQUISIÇÕES
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# CONFIGURAÇÕES DE LOGGING
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_FILE = 'relatorios.log'

# EXCEL
EXCEL_ENGINE = 'openpyxl'
EXCEL_EXTENSION = '.xlsx'

# INFORMAÇÕES DE MATRÍCULA
# Formato: AABCCXXXXX
# A = Modalidade (A=AC, L=AA)
# AB = Ano (últimos 2 dígitos)
# C = Semestre (1 ou 2)
# XXXXX = Sequencial
MATRICULA_MODALIDADE_POSICOES = (0, 1)        # Posição do caractere de modalidade
MATRICULA_ANO_POSICOES = (1, 3)               # Posições do ano
MATRICULA_SEMESTRE_POSICAO = 3                # Posição do semestre

# PERIDOS SUPORTADOS
ANO_MINIMO = 2000
ANO_MAXIMO = 2099
SEMESTRES_VALIDOS = [1, 2]

# FORMATAÇÃO DE SAÍDA
DATA_FORMATO = "%d/%m/%Y"
TIMESTAMP_FORMATO = "%Y%m%d_%H%M%S"

# PERCENTUAL DE EVASÃO
EVASAO_CALCULO = "Cancelados / Total"  # Definição de taxa de evasão
CASAS_DECIMAIS_PERCENTUAL = 2

print("✓ Configurações carregadas com sucesso")
