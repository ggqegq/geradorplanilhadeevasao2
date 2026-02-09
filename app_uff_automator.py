"""
Automador de Relatórios - UFF Química
Versão 4: Login com método Keycloak aprimorado
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
from urllib.parse import urljoin, urlparse, parse_qs
import io

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurações
BASE_URL = "https://app.uff.br"
APLICACAO_URL = "https://app.uff.br/graduacao/administracaoacademica"
LOGIN_URL = "https://app.uff.br/auth/realms/master/protocol/openid-connect/auth"
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
    """Classe para fazer login via CPF e Senha no Keycloak da UFF"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.is_authenticated = False
        self.auth_data = {}
        
    def debug_response(self, response, step_name):
        """Função de debug para analisar respostas"""
        logger.debug(f"\n{'='*60}")
        logger.debug(f"DEBUG {step_name}:")
        logger.debug(f"URL: {response.url}")
        logger.debug(f"Status: {response.status_code}")
        logger.debug(f"Cookies: {dict(self.session.cookies)}")
        logger.debug(f"Redirects: {response.history}")
        
        # Salvar HTML para análise se necessário
        if len(response.text) < 10000:  # Não salvar conteúdo muito grande
            logger.debug(f"Primeiros 1000 chars do HTML:\n{response.text[:1000]}")
    
    def extract_keycloak_params(self, html_content):
        """Extrai parâmetros do formulário Keycloak"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Encontrar formulário de login do Keycloak
        login_form = soup.find('form', {'id': 'kc-form-login'})
        
        if not login_form:
            # Tentar encontrar qualquer formulário de login
            login_form = soup.find('form')
            if login_form:
                logger.warning("Formulário encontrado, mas sem ID kc-form-login")
        
        if not login_form:
            logger.error("Nenhum formulário encontrado")
            return None
        
        action_url = login_form.get('action', '')
        
        # Extrair todos os campos hidden
        hidden_fields = {}
        for input_tag in login_form.find_all('input', type='hidden'):
            name = input_tag.get('name', '')
            value = input_tag.get('value', '')
            if name:
                hidden_fields[name] = value
        
        logger.info(f"Formulário encontrado - Action: {action_url}")
        logger.info(f"Campos hidden extraídos: {list(hidden_fields.keys())}")
        
        return {
            'action_url': action_url,
            'hidden_fields': hidden_fields
        }
    
    def fazer_login(self, cpf: str, senha: str) -> bool:
        """Fluxo de login completo no portal UFF"""
        try:
            st.info("Conectando ao portal UFF...")
            logger.info(f"Iniciando login para CPF: {cpf}")
            
            # PASSO 1: Acessar página protegida para ser redirecionado ao login
            st.info("Acessando aplicação...")
            response = self.session.get(
                APLICACAO_URL,
                timeout=TIMEOUT_REQUESTS,
                allow_redirects=True
            )
            
            self.debug_response(response, "PASSO 1 - Acesso inicial")
            
            # Verificar se já estamos autenticados
            if 'administracaoacademica' in response.url and response.status_code == 200:
                logger.info("Já autenticado!")
                self.is_authenticated = True
                st.success("✅ Login realizado com sucesso!")
                return True
            
            # PASSO 2: Acessar URL de login do Keycloak diretamente
            st.info("Acessando portal de autenticação...")
            
            # Construir URL de login com parâmetros OAuth2
            login_params = {
                'client_id': 'administracaoacademica',  # Client ID comum
                'redirect_uri': APLICACAO_URL,
                'response_type': 'code',
                'scope': 'openid',
                'state': 'random_state_string'
            }
            
            response = self.session.get(
                LOGIN_URL,
                params=login_params,
                timeout=TIMEOUT_REQUESTS,
                allow_redirects=True
            )
            
            self.debug_response(response, "PASSO 2 - Página de login")
            
            # PASSO 3: Extrair parâmetros do formulário
            st.info("Extraindo parâmetros de login...")
            login_params = self.extract_keycloak_params(response.text)
            
            if not login_params:
                logger.error("Não foi possível extrair parâmetros do formulário")
                # Tentar extrair manualmente
                soup = BeautifulSoup(response.text, 'html.parser')
                forms = soup.find_all('form')
                logger.error(f"Formulários encontrados: {len(forms)}")
                for i, form in enumerate(forms):
                    logger.error(f"Form {i}: action={form.get('action')}, method={form.get('method')}")
                st.error("Erro na página de login. Tente novamente.")
                return False
            
            # PASSO 4: Preparar e enviar dados de login
            st.info("Enviando credenciais...")
            
            # Construir URL completa para ação
            action_url = login_params['action_url']
            if action_url.startswith('/'):
                action_url = urljoin(BASE_URL, action_url)
            
            # Preparar payload
            payload = {
                'username': cpf,
                'password': senha
            }
            
            # Adicionar campos hidden
            if login_params['hidden_fields']:
                payload.update(login_params['hidden_fields'])
            
            logger.info(f"Enviando POST para: {action_url}")
            logger.info(f"Payload keys: {list(payload.keys())}")
            
            # Headers específicos para o POST
            post_headers = {
                'User-Agent': HEADERS['User-Agent'],
                'Referer': response.url,
                'Origin': BASE_URL,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
            
            login_response = self.session.post(
                action_url,
                data=payload,
                headers=post_headers,
                timeout=TIMEOUT_REQUESTS,
                allow_redirects=True
            )
            
            self.debug_response(login_response, "PASSO 4 - Resposta do login")
            
            # PASSO 5: Verificar sucesso do login
            logger.info(f"URL final após login: {login_response.url}")
            logger.info(f"Status final: {login_response.status_code}")
            
            # Critérios de sucesso
            success_criteria = [
                'administracaoacademica' in login_response.url,
                login_response.status_code == 200,
                len(self.session.cookies) > 0
            ]
            
            if all(success_criteria):
                self.is_authenticated = True
                st.success("✅ Login realizado com sucesso!")
                logger.info("✅ Autenticação bem-sucedida!")
                
                # Verificar acesso à aplicação
                test_response = self.session.get(
                    f"{APLICACAO_URL}/relatorios",
                    timeout=10,
                    allow_redirects=False
                )
                
                if test_response.status_code == 200:
                    logger.info("✅ Acesso confirmado à aplicação")
                else:
                    logger.warning(f"⚠️ Status de teste: {test_response.status_code}")
                
                return True
            else:
                # Analisar possíveis erros
                soup = BeautifulSoup(login_response.text, 'html.parser')
                
                # Mensagens de erro do Keycloak
                error_selectors = [
                    {'id': 'kc-error-message'},
                    {'class': 'kc-feedback-text'},
                    {'class': 'alert-error'},
                    {'class': 'alert'},
                    {'class': 'error'},
                    {'class': 'feedback'}
                ]
                
                error_message = None
                for selector in error_selectors:
                    element = soup.find('div', selector) or soup.find('span', selector)
                    if element:
                        error_message = element.get_text(strip=True)
                        break
                
                if error_message:
                    logger.error(f"Erro Keycloak: {error_message}")
                    st.error(f"Erro de autenticação: {error_message}")
                else:
                    # Verificar mensagens genéricas
                    if "Invalid username or password" in login_response.text:
                        error_message = "CPF ou senha inválidos"
                    elif "Account is disabled" in login_response.text:
                        error_message = "Conta desativada"
                    elif "Too many failed attempts" in login_response.text:
                        error_message = "Muitas tentativas falhas"
                    else:
                        error_message = "Falha na autenticação. Verifique suas credenciais."
                    
                    logger.error(f"Erro de login: {error_message}")
                    st.error(f"❌ {error_message}")
                
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Timeout na conexão")
            st.error("⏱️ Tempo limite excedido. Verifique sua conexão.")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Erro de conexão")
            st.error("🔌 Erro de conexão. Verifique se está conectado à internet.")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}", exc_info=True)
            st.error(f"⚠️ Erro inesperado: {str(e)[:100]}...")
            return False
    
    def get_session(self):
        """Retorna a sessão autenticada"""
        return self.session if self.is_authenticated else None
    
    def check_session(self):
        """Verifica se a sessão ainda é válida"""
        if not self.is_authenticated:
            return False
        
        try:
            # Testar acesso a uma página que requer autenticação
            test_url = f"{APLICACAO_URL}/relatorios"
            response = self.session.get(
                test_url,
                timeout=10,
                allow_redirects=False
            )
            
            # Se for redirecionado para login, sessão expirou
            if response.status_code == 302:
                location = response.headers.get('location', '')
                if 'auth' in location or 'login' in location:
                    logger.warning("Sessão expirada - redirecionado para login")
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
            url = f"{BASE_URL}/relatorios/{relatorio_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procurar link de download
            download_links = soup.find_all('a', {'href': re.compile(r'\.xlsx')})
            
            if download_links:
                return {
                    'status': 'PRONTO',
                    'download_url': urljoin(BASE_URL, download_links[0].get('href', ''))
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
    st.set_page_config(
        page_title="Automador de Relatórios UFF - Química",
        layout="wide",
        page_icon="🎓"
    )
    
    st.title("🎓 Automador de Relatórios de Evasão - UFF Química")
    st.markdown("---")
    
    # Sidebar para login
    with st.sidebar:
        st.header("🔐 Login")
        
        if 'session' not in st.session_state:
            st.session_state.session = None
            st.session_state.login_instance = None
        
        if st.session_state.session is None:
            cpf = st.text_input("CPF:", help="Digite seu CPF sem pontuação")
            senha = st.text_input("Senha:", type="password")
            
            col1, col2 = st.columns([1, 2])
            with col2:
                if st.button("🚀 Entrar", use_container_width=True):
                    with st.spinner("Autenticando no portal UFF..."):
                        login = LoginUFF()
                        if login.fazer_login(cpf, senha):
                            st.session_state.session = login.get_session()
                            st.session_state.login_instance = login
                            st.rerun()
                        else:
                            st.error("Falha na autenticação")
                            
            st.markdown("---")
            st.markdown("### ℹ️ Ajuda:")
            st.markdown("""
            - Use seu CPF e senha do **portal UFF**
            - Certifique-se de estar conectado à rede da UFF
            - Em caso de erro, verifique suas credenciais
            """)
            
        else:
            # Verificar se a sessão ainda é válida
            if st.session_state.login_instance and not st.session_state.login_instance.check_session():
                st.warning("⚠️ Sessão expirada")
                if st.button("🔄 Reconectar", use_container_width=True):
                    st.session_state.session = None
                    st.session_state.login_instance = None
                    st.rerun()
            else:
                st.success("✅ Conectado ao portal UFF")
                st.info(f"Cookies: {len(st.session_state.session.cookies)}")
            
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.session = None
                st.session_state.login_instance = None
                st.rerun()
    
    # Conteúdo principal
    if st.session_state.session is None:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info("👈 Faça login no portal UFF usando seu CPF e senha para começar.")
            
            st.markdown("### 📋 Fluxo de Trabalho:")
            st.markdown("""
            1. **Login** → Use suas credenciais UFF
            2. **Configurar** → Selecione períodos e cursos
            3. **Gerar** → Clique no botão para processar
            4. **Baixar** → Obtenha a planilha consolidada
            """)
            
            st.markdown("### ⚙️ Configurações Suportadas:")
            st.markdown("""
            - **Períodos**: 2025.1 a 2026.2
            - **Cursos**: 
              * Química (Licenciatura)
              * Química (Bacharelado) 
              * Química Industrial
            - **Localidade**: Niterói
            """)
    else:
        # Área de seleção de parâmetros
        st.header("⚙️ Configuração de Consulta")
        
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
                "Cursos",
                options=list(DESDOBRAMENTOS_CURSOS.keys()),
                default=list(DESDOBRAMENTOS_CURSOS.keys()),
                help="Selecione os cursos para gerar relatórios"
            )
        
        st.markdown("---")
        
        if st.button("🚀 Gerar Relatórios e Planilha Consolidada", 
                    use_container_width=True, 
                    type="primary"):
            
            if not cursos_selecionados:
                st.error("❌ Selecione pelo menos um curso!")
                return
            
            # Verificar sessão antes de começar
            if not st.session_state.login_instance.check_session():
                st.error("❌ Sessão expirada. Por favor, faça login novamente.")
                st.session_state.session = None
                st.session_state.login_instance = None
                st.rerun()
                return
            
            # Converter períodos para o formato do sistema
            def converter_periodo(periodo):
                ano, semestre = periodo.split('.')
                return f"{ano}/{semestre}°"
            
            periodo_inicio_fmt = converter_periodo(periodo_inicio)
            periodo_fim_fmt = converter_periodo(periodo_fim)
            
            periodos = [periodo_inicio_fmt, periodo_fim_fmt]
            
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
                            
                            st.success(f"✅ Relatório gerado: {curso_key} - {periodo}")
                            
                        except Exception as e:
                            st.error(f"❌ Erro ao gerar relatório de {curso_key} ({periodo}): {str(e)}")
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
                    st.success("✅ Planilha consolidada gerada com sucesso!")
                    st.download_button(
                        label="📥 Baixar Planilha Consolidada",
                        data=output.getvalue(),
                        file_name=f"planilha_consolidada_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                progress_bar.progress(1.0)
                status_text.text("✅ Processo concluído!")
            
            except Exception as e:
                st.error(f"❌ Erro geral: {str(e)}")
                logger.error(f"Erro: {str(e)}")


if __name__ == "__main__":
    main()
