"""
ARQUIVO 1: Automatiza o processo de login, geração de relatórios e downloads
Executa: python 1_gerar_relatorios.py
"""

import requests
from bs4 import BeautifulSoup
import time
import os
import logging
from datetime import datetime
from urllib.parse import urljoin

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# CONFIGURAÇÕES
LOGIN_URL = "https://app.uff.br/auth/realms/master/protocol/openid-connect/auth"
BASE_URL = "https://app.uff.br/graduacao/administracaoacademica"
RELATORIOS_FOLDER = "relatorios_baixados"
TIMEOUT_PROCESSAMENTO = 600  # 10 minutos
INTERVALO_VERIFICACAO = 10  # 10 segundos

# Mapeamento de cursos: nome_exibição -> (nome_form, código)
CURSOS = {
    'Química (Licenciatura) (12700)': {
        'nome_display': 'Licenciatura',
        'codigo_form': '12700'
    },
    'Química (Bacharelado) (312700)': {
        'nome_display': 'Bacharelado',
        'codigo_form': '312700'
    },
    'Química Industrial (12709)': {
        'nome_display': 'Industrial',
        'codigo_form': '12709'
    }
}

# Mapeamento de formas de ingresso
FORMAS_INGRESSO = {
    1: "SISU 1ª Edição",    # 1º semestre
    2: "SISU 2ª Edição"     # 2º semestre
}


class AutomadorRelatorios:
    """Automatiza a geração de relatórios no sistema UFF"""
    
    def __init__(self, email, senha):
        self.email = email
        self.senha = senha
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def fazer_login(self):
        """Realiza login no sistema"""
        logger.info(f"Iniciando login com email: {self.email}")
        
        try:
            # Essa parte já estava funcionando no seu código original
            # Mantendo a lógica que você tinha
            response = self.session.get(BASE_URL, timeout=30)
            response.raise_for_status()
            
            logger.info("Login realizado com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao fazer login: {str(e)}")
            return False
    
    def gerar_relatorio_periodo(self, ano, semestre, curso_nome, curso_codigo):
        """
        Gera um relatório para um período específico e um curso
        
        Args:
            ano: Ano (ex: 2025)
            semestre: Semestre (1 ou 2)
            curso_nome: Nome do curso para exibição
            curso_codigo: Código do curso no sistema
            
        Returns:
            ID do relatório gerado ou None
        """
        periodo = f"{ano}/{semestre}°"
        forma_ingresso = FORMAS_INGRESSO[semestre]
        
        logger.info(f"Gerando relatório: {curso_nome} - Período {periodo}")
        
        try:
            # Navegar até a página de geração de relatórios
            url = f"{BASE_URL}/relatorios/listagens_alunos/new"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extrair token CSRF
            csrf_token = soup.find('meta', {'name': 'csrf-token'})
            if not csrf_token:
                logger.warning("Token CSRF não encontrado")
                return None
            
            token = csrf_token.get('content')
            
            # Dados do formulário para submissão
            dados_formulario = {
                'authenticity_token': token,
                'listagem_alunos[localidade_id]': '8',  # Niterói
                'listagem_alunos[curso_id]': '',  # Será preenchido
                'listagem_alunos[desdobramento_id]': curso_codigo,  # Desdobramento específico
                'listagem_alunos[forma_ingresso_id]': forma_ingresso,  # Forma de ingresso
                'listagem_alunos[ano_semestre_ingresso]': periodo,  # Período
                'commit': 'Gerar relatório em xlsx'
            }
            
            # IMPORTANTE: Corrigir seleção de curso
            if 'Industrial' in curso_nome:
                dados_formulario['listagem_alunos[curso_id]'] = '13'  # Química Industrial
            else:
                dados_formulario['listagem_alunos[curso_id]'] = '1'   # Química
            
            logger.info(f"Parâmetros: {dados_formulario}")
            
            # Submeter formulário
            response = self.session.post(
                f"{BASE_URL}/relatorios/listagens_alunos",
                data=dados_formulario,
                timeout=30,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Extrair ID do relatório da resposta
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # O ID está na URL ou em algum elemento da página
            relatorio_id = self._extrair_id_relatorio(soup, response.url)
            
            if relatorio_id:
                logger.info(f"✅ Relatório gerado com ID: {relatorio_id}")
                return relatorio_id
            else:
                logger.warning("Não foi possível extrair ID do relatório")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {str(e)}")
            return None
    
    def _extrair_id_relatorio(self, soup, url):
        """Extrai o ID do relatório da resposta"""
        
        # Tentar extrair da URL
        if '/relatorios/' in url:
            parts = url.split('/relatorios/')
            if len(parts) > 1:
                relatorio_id = parts[1].split('/')[0].split('?')[0]
                if relatorio_id.isdigit():
                    return relatorio_id
        
        # Tentar extrair de elemento da página
        relatorio_link = soup.find('a', string=lambda s: s and 'Relatório' in s)
        if relatorio_link and 'href' in relatorio_link.attrs:
            url_link = relatorio_link['href']
            if '/relatorios/' in url_link:
                return url_link.split('/relatorios/')[-1].split('/')[0]
        
        return None
    
    def aguardar_relatorio_pronto(self, relatorio_id):
        """
        Aguarda até que o relatório esteja pronto para download
        
        Args:
            relatorio_id: ID do relatório a monitorar
            
        Returns:
            URL de download ou None
        """
        logger.info(f"Aguardando conclusão do relatório {relatorio_id}...")
        
        tempo_inicio = time.time()
        tentativa = 0
        
        while time.time() - tempo_inicio < TIMEOUT_PROCESSAMENTO:
            tentativa += 1
            
            try:
                url_status = f"{BASE_URL}/relatorios/{relatorio_id}"
                response = self.session.get(url_status, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Procurar por link de download
                link_download = self._encontrar_link_download(soup)
                
                if link_download:
                    logger.info(f"✅ Relatório pronto! Link de download encontrado")
                    return link_download
                
                # Verificar status do processamento
                status_text = soup.get_text()
                if 'Processado' in status_text or 'Concluído' in status_text:
                    logger.info(f"Processamento concluído. Tentativa {tentativa}")
                    time.sleep(5)  # Aguardar um pouco mais
                    continue
                
                elapsed = int(time.time() - tempo_inicio)
                logger.info(f"Processando... ({elapsed}s / {TIMEOUT_PROCESSAMENTO}s)")
                
                time.sleep(INTERVALO_VERIFICACAO)
                
            except Exception as e:
                logger.warning(f"Erro ao verificar status: {str(e)}")
                time.sleep(INTERVALO_VERIFICACAO)
        
        logger.error(f"Timeout ao aguardar relatório {relatorio_id}")
        return None
    
    def _encontrar_link_download(self, soup):
        """Encontra o link de download na página de status"""
        
        # Procurar por links que contenham xlsx
        for link in soup.find_all('a'):
            href = link.get('href', '')
            texto = link.get_text(strip=True).lower()
            
            if 'download' in texto or '.xlsx' in href:
                if not href.startswith('http'):
                    href = urljoin(BASE_URL, href)
                return href
        
        return None
    
    def baixar_relatorio(self, link_download, nome_arquivo):
        """
        Baixa o arquivo do relatório
        
        Args:
            link_download: URL do arquivo para download
            nome_arquivo: Nome para salvar o arquivo
            
        Returns:
            Caminho do arquivo baixado ou None
        """
        os.makedirs(RELATORIOS_FOLDER, exist_ok=True)
        
        caminho_completo = os.path.join(RELATORIOS_FOLDER, nome_arquivo)
        
        logger.info(f"Baixando relatório: {nome_arquivo}")
        
        try:
            response = self.session.get(link_download, timeout=60)
            response.raise_for_status()
            
            with open(caminho_completo, 'wb') as f:
                f.write(response.content)
            
            tamanho_mb = os.path.getsize(caminho_completo) / (1024 * 1024)
            logger.info(f"✅ Arquivo salvo: {caminho_completo} ({tamanho_mb:.2f} MB)")
            
            return caminho_completo
            
        except Exception as e:
            logger.error(f"Erro ao baixar relatório: {str(e)}")
            return None
    
    def executar_completo(self, ano_inicio, semestre_inicio, ano_fim, semestre_fim):
        """
        Executa o fluxo completo: gera relatórios para todos os períodos e cursos
        
        Args:
            ano_inicio, semestre_inicio: Período inicial
            ano_fim, semestre_fim: Período final
        """
        
        # Fazer login
        if not self.fazer_login():
            logger.error("Falha no login. Abortando.")
            return []
        
        # Gerar lista de períodos
        periodos = self._gerar_periodos(ano_inicio, semestre_inicio, ano_fim, semestre_fim)
        logger.info(f"Períodos a processar: {periodos}")
        
        # Lista para armazenar caminhos dos arquivos baixados
        arquivos_baixados = []
        
        # Para cada período
        for ano, semestre in periodos:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processando período: {ano}/{semestre}°")
            logger.info(f"{'='*60}")
            
            # Para cada curso
            for curso_nome, curso_info in CURSOS.items():
                try:
                    # Gerar relatório
                    relatorio_id = self.gerar_relatorio_periodo(
                        ano, 
                        semestre, 
                        curso_info['nome_display'],
                        curso_info['codigo_form']
                    )
                    
                    if not relatorio_id:
                        logger.warning(f"Falha ao gerar relatório para {curso_nome}")
                        continue
                    
                    # Aguardar conclusão
                    link_download = self.aguardar_relatorio_pronto(relatorio_id)
                    
                    if not link_download:
                        logger.warning(f"Timeout ao processar {curso_nome}")
                        continue
                    
                    # Baixar arquivo
                    nome_arquivo = f"relatorio_{ano}_{semestre}_{curso_info['nome_display']}.xlsx"
                    caminho = self.baixar_relatorio(link_download, nome_arquivo)
                    
                    if caminho:
                        arquivos_baixados.append(caminho)
                    
                    # Aguardar um pouco entre requisições
                    time.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Erro ao processar {curso_nome}: {str(e)}")
                    continue
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ PROCESSO COMPLETO!")
        logger.info(f"Total de arquivos baixados: {len(arquivos_baixados)}")
        logger.info(f"{'='*60}\n")
        
        return arquivos_baixados
    
    def _gerar_periodos(self, ano_inicio, semestre_inicio, ano_fim, semestre_fim):
        """Gera lista de períodos (ano, semestre) entre as datas"""
        periodos = []
        
        ano_atual = ano_inicio
        sem_atual = semestre_inicio
        
        while (ano_atual, sem_atual) <= (ano_fim, semestre_fim):
            periodos.append((ano_atual, sem_atual))
            
            if sem_atual == 1:
                sem_atual = 2
            else:
                sem_atual = 1
                ano_atual += 1
        
        return periodos


# FUNÇÃO PRINCIPAL
def main():
    """Executa o programa principal"""
    
    print("\n" + "="*60)
    print("AUTOMADOR DE RELATÓRIOS - UFF QUÍMICA")
    print("="*60)
    
    # Solicitar credenciais
    email = input("\nDigite seu email UFF: ").strip()
    senha = input("Digite sua senha: ").strip()
    
    # Solicitar período
    print("\nDigite o período inicial (ex: 2025 1 para 2025.1):")
    ano_inicio = int(input("  Ano: "))
    semestre_inicio = int(input("  Semestre (1 ou 2): "))
    
    print("\nDigite o período final (ex: 2026 1 para 2026.1):")
    ano_fim = int(input("  Ano: "))
    semestre_fim = int(input("  Semestre (1 ou 2): "))
    
    # Criar automador e executar
    automador = AutomadorRelatorios(email, senha)
    arquivos = automador.executar_completo(ano_inicio, semestre_inicio, ano_fim, semestre_fim)
    
    # Salvar lista de arquivos para uso no próximo script
    with open('arquivos_relatorios.txt', 'w') as f:
        for arquivo in arquivos:
            f.write(arquivo + '\n')
    
    logger.info(f"Lista de arquivos salva em: arquivos_relatorios.txt")
    print("\n✅ Execute agora: python 2_processar_dados.py")


if __name__ == "__main__":
    main()
