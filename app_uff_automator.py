"""
Automador de Relatórios - UFF Química
Versão 3: Login com método testado e funcional
"""

import streamlit as st
import requests
import time
import os
import re
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
import json
from urllib.parse import urljoin, urlparse
import io

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações
BASE_URL = "https://app.uff.br"
APLICACAO_URL = "https://app.uff.br/graduacao/administracaoacademica"
LOGIN_URL = "https://app.uff.br/auth/realms/master/protocol/openid-connect/auth"
TOKEN_URL = "https://app.uff.br/auth/realms/master/protocol/openid-connect/token"
LISTAGEM_ALUNOS_URL = f"{APLICACAO_URL}/relatorios/listagens_alunos"

# Headers para simular navegador
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

TIMEOUT_REQUESTS = 30

# Mapeamento de Desdobramentos (Ajuste para filtros corretos)
DESDOBRAMENTOS_CURSOS = {
    'Licenciatura': {
        'valor': 'Química (Licenciatura) (12700)',
        'buscar_por': 'Química',
        'nome_padrao': 'Química (Licenciatura)'
    },
    'Bacharelado': {
        'valor': 'Química (Bacharelado) (312700)',
        'buscar_por': 'Química',
        'nome_padrao': 'Química (Bacharelado)'
    },
    'Industrial': {
        'valor': 'Química Industrial (12709)',
        'buscar_por': 'Química Industrial',
        'nome_padrao': 'Química Industrial'
    }
}

# Formas de ingresso
FORMAS_INGRESSO = {
    '1': 'SISU 1ª Edição',
    '2': 'SISU 2ª Edição'
}

class LoginUFF:
    """Classe para fazer login via CPF e Senha usando método testado"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.is_authenticated = False
        self.auth_data = {}
    
    def extract_login_parameters(self, html_content):
        """Extrai parâmetros do formulário de login (função que estava funcionando)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Primeiro, tentar encontrar o formulário pelo ID
        login_form = soup.find('form', {'id': 'kc-form-login'})
        
        if not login_form:
            # Tentar outros padrões comuns
            login_form = soup.find('form', action=lambda x: x and '/auth/' in x)
            if not login_form:
                login_form = soup.find('form', method='post')
        
        if not login_form:
            logger.error("Formulário de login não encontrado. Conteúdo da página:")
            logger.error(html_content[:1000])
            return None
        
        action_url = login_form.get('action', '')
        hidden_inputs = {}
        
        for input_tag in login_form.find_all('input', type='hidden'):
            name = input_tag.get('name', '')
            value = input_tag.get('value', '')
            if name:
                hidden_inputs[name] = value
        
        logger.info(f"Parâmetros extraídos - Action URL: {action_url}")
        logger.info(f"Campos hidden: {list(hidden_inputs.keys())}")
        
        return {
            'action_url': action_url,
            'hidden_fields': hidden_inputs
        }
    
    def _extract_csrf_token(self, html_content):
        """Extrai token CSRF do HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Procurar meta tag CSRF
        meta_token = soup.find('meta', {'name': 'csrf-token'})
        if meta_token and meta_token.get('content'):
            self.auth_data['csrf_token'] = meta_token['content']
            self.session.headers['X-CSRF-Token'] = meta_token['content']
            logger.info(f"CSRF Token extraído: {meta_token['content'][:20]}...")
        
        # Procurar input hidden
        input_token = soup.find('input', {'name': 'authenticity_token'})
        if input_token and input_token.get('value'):
            self.auth_data['authenticity_token'] = input_token['value']
            logger.info(f"Authenticity Token extraído: {input_token['value'][:20]}...")
    
    def fazer_login(self, cpf: str, senha: str) -> bool:
        """Realiza login no sistema UFF usando a lógica que estava funcionando"""
        try:
            st.info("Conectando ao portal UFF...")
            logger.info(f"Tentando login para CPF: {cpf}")
            
            # 1. Acessar a página inicial da aplicação
            login_page_url = APLICACAO_URL
            response = self.session.get(login_page_url, timeout=TIMEOUT_REQUESTS)
            
            if response.status_code != 200:
                logger.error(f"Falha ao acessar página: {response.status_code}")
                st.error(f"Erro de conexão: Status {response.status_code}")
                return False
            
            # 2. Extrair parâmetros do formulário de login
            login_params = self.extract_login_parameters(response.text)
            
            if not login_params:
                logger.error("Não foi possível encontrar o formulário de login")
                st.error("Não foi possível acessar o formulário de login. Tente novamente.")
                return False
            
            # 3. Preparar dados do formulário
            form_data = {
                'username': cpf,
                'password': senha,
                'rememberMe': 'on'
            }
            
            # Adicionar campos hidden
            if login_params['hidden_fields']:
                form_data.update(login_params['hidden_fields'])
            
            # 4. Construir URL completa da ação
            login_action = login_params['action_url']
            
            # Se for URL relativa, construir URL completa
            if login_action.startswith('/'):
                parsed_base = urlparse(BASE_URL)
                login_action = f"{parsed_base.scheme}://{parsed_base.netloc}{login_action}"
            elif not login_action.startswith('http'):
                login_action = urljoin(BASE_URL, login_action)
            
            logger.info(f"Enviando login para: {login_action}")
            
            # 5. Enviar requisição de login
            headers = {
                'User-Agent': HEADERS['User-Agent'],
                'Referer': login_page_url,
                'Origin': BASE_URL,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            login_response = self.session.post(
                login_action,
                data=form_data,
                headers=headers,
                allow_redirects=True,
                timeout=TIMEOUT_REQUESTS
            )
            
            # 6. Verificar se login foi bem-sucedido
            if login_response.status_code == 200:
                # Verificar se estamos na aplicação correta
                if APLICACAO_URL in login_response.url or 'administracaoacademica' in login_response.url:
                    self.is_authenticated = True
                    
                    # Extrair token CSRF
                    self._extract_csrf_token(login_response.text)
                    
                    # Salvar informações da sessão
                    self.auth_data['cookies'] = dict(self.session.cookies)
                    self.auth_data['headers'] = dict(self.session.headers)
                    
                    # Verificar acesso à página de relatórios
                    test_url = f"{APLICACAO_URL}/relatorios"
                    test_response = self.session.get(test_url, timeout=10)
                    
                    if test_response.status_code == 200:
                        st.success("✅ Login realizado com sucesso!")
                        logger.info("✅ Login realizado com sucesso!")
                        return True
                    else:
                        st.warning("Login realizado, mas acesso à aplicação pode estar limitado")
                        logger.warning(f"Teste de acesso retornou: {test_response.status_code}")
                        return True
                else:
                    # Verificar se há mensagem de erro
                    soup = BeautifulSoup(login_response.text, 'html.parser')
                    
                    # Procurar mensagens de erro do Keycloak
                    error_div = soup.find('div', {'id': 'kc-error-message'}) or \
                               soup.find('span', class_='kc-feedback-text') or \
                               soup.find('div', class_='alert-error') or \
                               soup.find('div', class_='alert') or \
                               soup.find('div', class_='error')
                    
                    if error_div:
                        error_msg = error_div.get_text(strip=True)
                        logger.error(f"Erro no login: {error_msg}")
                        st.error(f"Erro de autenticação: {error_msg}")
                    else:
                        # Verificar mensagens genéricas
                        if "Invalid username or password" in login_response.text:
                            error_msg = "CPF ou senha inválidos"
                        elif "Account is disabled" in login_response.text:
                            error_msg = "Conta desativada"
                        elif "Too many failed attempts" in login_response.text:
                            error_msg = "Muitas tentativas falhas. Tente novamente mais tarde."
                        else:
                            error_msg = f"Redirecionado para URL incorreta: {login_response.url}"
                        
                        logger.error(f"Erro no login: {error_msg}")
                        st.error(f"Falha na autenticação: {error_msg}")
                    
                    return False
            else:
                logger.error(f"Status code inesperado: {login_response.status_code}")
                st.error(f"Erro do servidor: Status {login_response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Timeout ao tentar fazer login")
            st.error("Tempo limite excedido. Verifique sua conexão com a internet.")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Erro de conexão")
            st.error("Erro de conexão. Verifique se o portal UFF está acessível.")
            return False
        except Exception as e:
            logger.error(f"Erro durante o login: {str(e)}", exc_info=True)
            st.error(f"Erro inesperado: {str(e)}")
            return False
    
    def get_session(self):
        """Retorna a sessão autenticada"""
        return self.session if self.is_authenticated else None
    
    def check_session(self):
        """Verifica se a sessão ainda é válida"""
        if not self.is_authenticated:
            return False
        
        try:
            # Tentar acessar uma página que requer autenticação
            test_url = f"{APLICACAO_URL}/relatorios"
            response = self.session.get(test_url, timeout=10, allow_redirects=False)
            
            # Se for redirecionado para login, sessão expirou
            if response.status_code == 302:
                location = response.headers.get('location', '')
                if 'auth' in location or 'login' in location:
                    return False
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao verificar sessão: {str(e)}")
            return False


class GeradorRelatorios:
    """Classe para gerar relatórios com filtros corretos"""
    
    def __init__(self, session):
        self.session = session
        self.base_url = APLICACAO_URL
    
    def acessar_pagina_listagem(self):
        """Acessa a página de listagem de alunos"""
        try:
            response = self.session.get(LISTAGEM_ALUNOS_URL, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.error(f"Erro ao acessar página de listagem: {str(e)}")
            raise
    
    def extrair_parametros_formulario(self, soup):
        """Extrai parâmetros do formulário"""
        parametros = {
            'inputs': {},
            'selects': {},
            'action': None,
            'authenticity_token': None
        }
        
        # Encontrar o formulário
        form = soup.find('form')
        if not form:
            raise Exception("Formulário não encontrado")
        
        # Ação do formulário
        parametros['action'] = form.get('action', '')
        
        # Extrair inputs
        for input_tag in form.find_all('input'):
            name = input_tag.get('name', '')
            value = input_tag.get('value', '')
            
            if name == 'authenticity_token':
                parametros['authenticity_token'] = value
            
            if name:
                parametros['inputs'][name] = {'value': value, 'type': input_tag.get('type', 'text')}
        
        # Extrair selects
        for select_tag in form.find_all('select'):
            name = select_tag.get('name', '')
            if name:
                options = []
                for option in select_tag.find_all('option'):
                    options.append({
                        'value': option.get('value', ''),
                        'text': option.get_text(strip=True),
                        'selected': 'selected' in option.attrs
                    })
                parametros['selects'][name] = options
        
        return parametros
    
    def preencher_formulario_com_filtros(self, parametros, filtros):
        """Preenche o formulário com filtros específicos"""
        dados_formulario = {}
        
        # Adicionar token CSRF
        if parametros.get('authenticity_token'):
            dados_formulario['authenticity_token'] = parametros['authenticity_token']
        
        # Adicionar valores padrão dos inputs
        for name, input_info in parametros['inputs'].items():
            if input_info['value']:
                dados_formulario[name] = input_info['value']
        
        # Aplicar filtros com busca específica
        for campo, valor_buscado in filtros.items():
            if campo in parametros['selects']:
                opcoes = parametros['selects'][campo]
                valor_encontrado = False
                
                for opcao in opcoes:
                    # Busca exata ou parcial
                    if str(opcao['value']).strip() == str(valor_buscado).strip():
                        dados_formulario[campo] = opcao['value']
                        logger.info(f"Filtro exato: {campo} = {valor_buscado} (valor: {opcao['value']})")
                        valor_encontrado = True
                        break
                    elif opcao['text'].strip() == str(valor_buscado).strip():
                        dados_formulario[campo] = opcao['value']
                        logger.info(f"Filtro por texto: {campo} = {valor_buscado} (valor: {opcao['value']})")
                        valor_encontrado = True
                        break
                
                if not valor_encontrado:
                    # Busca parcial para desdobramentos
                    for opcao in opcoes:
                        if valor_buscado in opcao['text']:
                            dados_formulario[campo] = opcao['value']
                            logger.info(f"Filtro parcial: {campo} = {valor_buscado} encontrado em {opcao['text']} (valor: {opcao['value']})")
                            valor_encontrado = True
                            break
                
                if not valor_encontrado:
                    logger.warning(f"Filtro não encontrado: {campo} = {valor_buscado}")
                    logger.warning(f"Opções disponíveis: {[o['text'] for o in opcoes]}")
        
        return dados_formulario
    
    def submeter_formulario(self, dados_formulario):
        """Submete o formulário e obtém o ID do relatório"""
        try:
            action_url = urljoin(self.base_url, '/graduacao/administracaoacademica/relatorios/listagens_alunos')
            
            logger.info(f"Submetendo formulário para: {action_url}")
            
            response = self.session.post(
                action_url,
                data=dados_formulario,
                timeout=30,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Extrair ID do relatório da URL
            match = re.search(r'/relatorios/(\d+)', response.url)
            if match:
                relatorio_id = match.group(1)
                logger.info(f"Relatório criado com ID: {relatorio_id}")
                return {
                    'success': True,
                    'relatorio_id': relatorio_id,
                    'url': response.url
                }
            else:
                logger.error("Não foi possível extrair o ID do relatório")
                return {'success': False, 'error': 'ID do relatório não encontrado'}
            
        except Exception as e:
            logger.error(f"Erro ao submeter formulário: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def verificar_status_relatorio(self, relatorio_id):
        """Verifica o status do relatório"""
        try:
            url = f"{self.base_url}/relatorios/{relatorio_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procurar link de download
            download_links = soup.find_all('a', {'href': re.compile(r'\.xlsx')})
            
            if download_links:
                return {
                    'status': 'PRONTO',
                    'download_url': urljoin(self.base_url, download_links[0].get('href', ''))
                }
            else:
                # Verificar etapas de processamento
                steps = soup.find_all('div', {'class': 'step'})
                if steps:
                    return {
                        'status': 'EM_PROCESSAMENTO',
                        'etapas': len(steps)
                    }
                else:
                    return {'status': 'DESCONHECIDO'}
        
        except Exception as e:
            logger.error(f"Erro ao verificar status: {str(e)}")
            return {'status': 'ERRO', 'error': str(e)}
    
    def aguardar_relatorio(self, relatorio_id, max_tentativas=60):
        """Aguarda o relatório ficar pronto"""
        tentativa = 0
        while tentativa < max_tentativas:
            status_info = self.verificar_status_relatorio(relatorio_id)
            
            if status_info['status'] == 'PRONTO':
                return status_info
            elif status_info['status'] == 'ERRO':
                raise Exception(f"Erro ao verificar status: {status_info.get('error')}")
            
            tentativa += 1
            time.sleep(5)  # Aguardar 5 segundos
        
        raise Exception(f"Timeout aguardando relatório {relatorio_id}")
    
    def baixar_relatorio(self, download_url):
        """Baixa o arquivo Excel do relatório"""
        try:
            response = self.session.get(download_url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Erro ao baixar relatório: {str(e)}")
            raise
    
    def gerar_relatorio_completo(self, filtros, progress_callback=None):
        """Fluxo completo para gerar um relatório"""
        try:
            # 1. Acessar página
            if progress_callback:
                progress_callback("Acessando página de listagem...", 10)
            soup = self.acessar_pagina_listagem()
            
            # 2. Extrair parâmetros
            if progress_callback:
                progress_callback("Extraindo parâmetros do formulário...", 20)
            parametros = self.extrair_parametros_formulario(soup)
            
            # 3. Preencher com filtros corretos
            if progress_callback:
                progress_callback("Preenchendo formulário com filtros...", 30)
            dados_form = self.preencher_formulario_com_filtros(parametros, filtros)
            
            # 4. Submeter formulário
            if progress_callback:
                progress_callback("Submetendo formulário...", 40)
            resultado = self.submeter_formulario(dados_form)
            
            if not resultado['success']:
                raise Exception(f"Erro ao submeter formulário: {resultado.get('error')}")
            
            relatorio_id = resultado['relatorio_id']
            
            # 5. Aguardar processamento
            if progress_callback:
                progress_callback(f"Aguardando processamento do relatório {relatorio_id}...", 50)
            status_info = self.aguardar_relatorio(relatorio_id)
            
            # 6. Baixar arquivo
            if progress_callback:
                progress_callback("Baixando arquivo...", 80)
            conteudo_excel = self.baixar_relatorio(status_info['download_url'])
            
            if progress_callback:
                progress_callback("Relatório gerado com sucesso!", 100)
            
            return conteudo_excel
        
        except Exception as e:
            logger.error(f"Erro no fluxo completo: {str(e)}")
            raise


def main():
    """Função principal da aplicação"""
    st.set_page_config(page_title="Automador de Relatórios UFF - Química", layout="wide")
    
    st.title("🎓 Automador de Relatórios de Evasão - UFF Química")
    st.markdown("---")
    
    # Sidebar para login
    with st.sidebar:
        st.header("Login")
        
        if 'session' not in st.session_state:
            st.session_state.session = None
            st.session_state.login_instance = None
        
        if st.session_state.session is None:
            cpf = st.text_input("CPF:", type="password", help="Digite seu CPF sem pontuação")
            senha = st.text_input("Senha:", type="password")
            
            if st.button("Entrar", use_container_width=True):
                with st.spinner("Autenticando no portal UFF..."):
                    login = LoginUFF()
                    if login.fazer_login(cpf, senha):
                        st.session_state.session = login.get_session()
                        st.session_state.login_instance = login
                        st.rerun()
        else:
            # Verificar se a sessão ainda é válida
            if st.session_state.login_instance and not st.session_state.login_instance.check_session():
                st.warning("Sessão expirada")
                if st.button("Reconectar", use_container_width=True):
                    st.session_state.session = None
                    st.session_state.login_instance = None
                    st.rerun()
            else:
                st.success("✓ Conectado ao portal UFF")
            
            if st.button("Sair", use_container_width=True):
                st.session_state.session = None
                st.session_state.login_instance = None
                st.rerun()
    
    # Conteúdo principal
    if st.session_state.session is None:
        st.info("👉 Faça login no portal UFF usando seu CPF e senha para começar.")
        st.markdown("---")
        st.markdown("### 📋 Instruções:")
        st.markdown("""
        1. Digite seu CPF (sem pontuação) e senha do portal UFF
        2. Clique em **Entrar**
        3. Aguarde a autenticação (pode levar alguns segundos)
        4. Configure os filtros desejados
        5. Clique em **Gerar Relatórios e Planilha Consolidada**
        """)
    else:
        # Área de seleção de parâmetros
        st.header("Configuração de Consulta")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            periodo_inicio = st.selectbox(
                "Período de Início",
                options=['2025.1', '2025.2', '2026.1', '2026.2'],
                index=0
            )
        
        with col2:
            periodo_fim = st.selectbox(
                "Período de Fim",
                options=['2025.1', '2025.2', '2026.1', '2026.2'],
                index=2
            )
        
        with col3:
            cursos_selecionados = st.multiselect(
                "Cursos (padrão: todos)",
                options=list(DESDOBRAMENTOS_CURSOS.keys()),
                default=list(DESDOBRAMENTOS_CURSOS.keys())
            )
        
        st.markdown("---")
        
        if st.button("Gerar Relatórios e Planilha Consolidada", use_container_width=True, type="primary"):
            if not cursos_selecionados:
                st.error("Selecione pelo menos um curso!")
                return
            
            # Verificar sessão antes de começar
            if not st.session_state.login_instance.check_session():
                st.error("Sessão expirada. Por favor, faça login novamente.")
                st.session_state.session = None
                st.session_state.login_instance = None
                st.rerun()
                return
            
            # Converter períodos para o formato do sistema (2025/1, 2025/2, etc)
            def converter_periodo(periodo):
                ano, semestre = periodo.split('.')
                return f"{ano}/{semestre}°"
            
            # Gerar períodos
            periodo_inicio_fmt = converter_periodo(periodo_inicio)
            periodo_fim_fmt = converter_periodo(periodo_fim)
            
            # Extrair períodos entre início e fim
            periodos = [periodo_inicio_fmt, periodo_fim_fmt]
            # Adicionar períodos intermediários se necessário
            
            gerador = GeradorRelatorios(st.session_state.session)
            
            # Armazenar todos os dados
            todos_dados = []
            
            # Barra de progresso
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_relatorios = len(periodos) * len(cursos_selecionados)
            relatorio_atual = 0
            
            try:
                for periodo in periodos:
                    # Determinar forma de ingresso
                    semestre = '1' if '1°' in periodo else '2'
                    forma_ingresso = FORMAS_INGRESSO[semestre]
                    
                    for curso_key in cursos_selecionados:
                        relatorio_atual += 1
                        
                        curso_info = DESDOBRAMENTOS_CURSOS[curso_key]
                        
                        def callback_progresso(msg, pct):
                            status_text.text(f"[{relatorio_atual}/{total_relatorios}] {curso_key} - {periodo}: {msg}")
                            progress_bar.progress((relatorio_atual - 1 + pct/100) / total_relatorios)
                        
                        try:
                            status_text.text(f"Gerando relatório: {curso_key} - {periodo}...")
                            
                            # Preparar filtros
                            filtros = {
                                'report_filter_localidade': 'Niterói',
                                'report_filter_curso': curso_info['buscar_por'],
                                'report_filter_desdobramento': curso_info['valor'],
                                'report_filter_forma_ingresso': forma_ingresso,
                                'report_filter_ano_semestre_ingresso': periodo
                            }
                            
                            # Gerar relatório
                            conteudo_excel = gerador.gerar_relatorio_completo(filtros, callback_progresso)
                            
                            # Ler dados do Excel
                            df = pd.read_excel(io.BytesIO(conteudo_excel))
                            df['curso'] = curso_key
                            df['periodo'] = periodo
                            todos_dados.append(df)
                            
                            st.success(f"✓ Relatório gerado: {curso_key} - {periodo}")
                            
                        except Exception as e:
                            st.error(f"Erro ao gerar relatório de {curso_key} ({periodo}): {str(e)}")
                            logger.error(f"Erro: {str(e)}")
                
                if todos_dados:
                    status_text.text("Processando dados e gerando planilha consolidada...")
                    
                    # Combinar todos os dados
                    df_consolidado = pd.concat(todos_dados, ignore_index=True)
                    
                    # Gerar arquivo Excel consolidado
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_consolidado.to_excel(writer, sheet_name='Dados Brutos', index=False)
                    
                    output.seek(0)
                    
                    # Botão de download
                    st.success("✓ Planilha consolidada gerada com sucesso!")
                    st.download_button(
                        label="📥 Baixar Planilha Consolidada",
                        data=output.getvalue(),
                        file_name=f"planilha_consolidada_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                progress_bar.progress(1.0)
                status_text.text("✓ Processo concluído!")
            
            except Exception as e:
                st.error(f"Erro geral: {str(e)}")
                logger.error(f"Erro: {str(e)}")


if __name__ == "__main__":
    main()
