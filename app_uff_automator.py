"""
Automador de Relatórios - UFF Química
Versão 5: Login com fluxo Keycloak completo e cookies persistentes
"""

import streamlit as st
import requests
import time
import re
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
import io
import json
import uuid

# Configurar logging detalhado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações
BASE_URL = "https://app.uff.br"
APLICACAO_URL = "https://app.uff.br/graduacao/administracaoacademica"
KEYCLOAK_BASE = "https://app.uff.br/auth/realms/master/protocol/openid-connect"
LISTAGEM_ALUNOS_URL = f"{APLICACAO_URL}/relatorios/listagens_alunos"

# Headers para simular navegador real
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

TIMEOUT_REQUESTS = 45

# Mapeamento de Desdobramentos
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

class UFFAuthenticator:
    """Autenticador robusto para o sistema UFF com Keycloak"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # Configurar para manter cookies entre requisições
        self.session.cookies.clear()
        self.is_authenticated = False
        self.session_id = str(uuid.uuid4())
        self.cookie_jar = {}
        
    def save_debug_info(self, step, response, html_snippet=None):
        """Salva informações de debug para análise"""
        debug_info = {
            'step': step,
            'timestamp': datetime.now().isoformat(),
            'url': response.url,
            'status_code': response.status_code,
            'cookies': dict(self.session.cookies),
            'headers': dict(response.headers),
            'redirect_history': [r.url for r in response.history]
        }
        
        logger.debug(f"\n{'='*80}")
        logger.debug(f"DEBUG STEP: {step}")
        logger.debug(f"URL: {response.url}")
        logger.debug(f"Status: {response.status_code}")
        logger.debug(f"Cookies: {dict(self.session.cookies)}")
        
        if html_snippet and len(html_snippet) < 2000:
            logger.debug(f"HTML snippet:\n{html_snippet}")
        
        return debug_info
    
    def discover_login_url(self):
        """Descobre a URL de login correta seguindo redirecionamentos"""
        try:
            logger.info("Descobrindo URL de login...")
            
            # 1. Acessar a aplicação principal
            response = self.session.get(
                APLICACAO_URL,
                timeout=TIMEOUT_REQUESTS,
                allow_redirects=True
            )
            
            self.save_debug_info("1. Acesso inicial", response)
            
            # 2. Procurar por links de login ou redirecionamento para Keycloak
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Verificar se já está autenticado
            if 'administracaoacademica' in response.url and response.status_code == 200:
                logger.info("Já autenticado!")
                return None
            
            # 3. Procurar por redirecionamento para Keycloak
            auth_patterns = [
                '/auth/realms/master',
                '/auth/',
                'openid-connect',
                'login-actions'
            ]
            
            for pattern in auth_patterns:
                if pattern in response.url:
                    logger.info(f"Encontrado padrão de autenticação: {pattern}")
                    return response.url
            
            # 4. Procurar por formulário de login no HTML
            login_form = soup.find('form', {'id': 'kc-form-login'})
            if login_form:
                action = login_form.get('action', '')
                if action:
                    full_url = urljoin(BASE_URL, action)
                    logger.info(f"Formulário de login encontrado: {full_url}")
                    return full_url
            
            # 5. Tentar URL padrão do Keycloak
            keycloak_url = f"{KEYCLOAK_BASE}/auth"
            logger.info(f"Tentando URL padrão do Keycloak: {keycloak_url}")
            
            response = self.session.get(
                keycloak_url,
                params={
                    'client_id': 'administracaoacademica',
                    'redirect_uri': APLICACAO_URL,
                    'response_type': 'code',
                    'scope': 'openid',
                    'state': self.session_id
                },
                timeout=TIMEOUT_REQUESTS,
                allow_redirects=True
            )
            
            self.save_debug_info("2. Keycloak padrão", response)
            
            if response.status_code == 200:
                return response.url
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao descobrir URL de login: {e}")
            return None
    
    def extract_login_form_data(self, html_content):
        """Extrai todos os dados do formulário de login"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Encontrar o formulário de login
        form = soup.find('form')
        if not form:
            # Tentar encontrar por ID específico do Keycloak
            form = soup.find('form', {'id': 'kc-form-login'})
        
        if not form:
            logger.error("Nenhum formulário encontrado no HTML")
            logger.error(f"Primeiros 1000 chars do HTML:\n{html_content[:1000]}")
            return None
        
        # Extrair action URL
        action = form.get('action', '')
        if not action.startswith('http'):
            action = urljoin(BASE_URL, action)
        
        # Extrair todos os inputs
        form_data = {}
        for input_tag in form.find_all('input'):
            name = input_tag.get('name')
            value = input_tag.get('value', '')
            input_type = input_tag.get('type', 'text')
            
            if name:
                form_data[name] = value
        
        logger.info(f"Formulário encontrado - Action: {action}")
        logger.info(f"Campos do formulário: {list(form_data.keys())}")
        
        return {
            'action': action,
            'data': form_data
        }
    
    def perform_keycloak_login(self, login_url, cpf, senha):
        """Executa o login no Keycloak"""
        try:
            # 1. Obter página de login
            logger.info(f"Acessando página de login: {login_url}")
            response = self.session.get(
                login_url,
                timeout=TIMEOUT_REQUESTS,
                allow_redirects=True
            )
            
            self.save_debug_info("3. Página de login", response, response.text[:1000])
            
            # 2. Extrair dados do formulário
            form_info = self.extract_login_form_data(response.text)
            if not form_info:
                return False, "Não foi possível extrair formulário de login"
            
            # 3. Preparar dados para envio
            form_data = form_info['data']
            form_data['username'] = cpf
            form_data['password'] = senha
            
            # Remover valores vazios que podem causar problemas
            form_data = {k: v for k, v in form_data.items() if v is not None}
            
            logger.info(f"Enviando login para: {form_info['action']}")
            logger.debug(f"Dados do formulário: {form_data}")
            
            # 4. Enviar requisição de login
            headers = {
                'User-Agent': HEADERS['User-Agent'],
                'Referer': response.url,
                'Origin': BASE_URL,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
            
            login_response = self.session.post(
                form_info['action'],
                data=form_data,
                headers=headers,
                timeout=TIMEOUT_REQUESTS,
                allow_redirects=True
            )
            
            self.save_debug_info("4. Resposta do login", login_response, login_response.text[:1000])
            
            # 5. Verificar se login foi bem-sucedido
            logger.info(f"URL após login: {login_response.url}")
            logger.info(f"Status após login: {login_response.status_code}")
            
            # Verificar cookies de sessão
            cookies = dict(self.session.cookies)
            logger.info(f"Cookies após login: {cookies}")
            
            # Critérios de sucesso
            success_indicators = [
                'administracaoacademica' in login_response.url,
                'JSESSIONID' in cookies,
                'AUTH_SESSION_ID' in cookies,
                login_response.status_code in [200, 302]
            ]
            
            if any(success_indicators):
                logger.info("✅ Indicadores de sucesso encontrados")
                
                # Salvar cookies importantes
                self.cookie_jar = {
                    'JSESSIONID': cookies.get('JSESSIONID'),
                    'AUTH_SESSION_ID': cookies.get('AUTH_SESSION_ID')
                }
                
                # Atualizar headers com cookies
                if 'JSESSIONID' in cookies:
                    self.session.headers['Cookie'] = f"JSESSIONID={cookies['JSESSIONID']}"
                
                return True, "Login bem-sucedido"
            
            # Verificar mensagens de erro
            soup = BeautifulSoup(login_response.text, 'html.parser')
            
            # Procurar mensagens de erro comuns
            error_messages = [
                "Invalid username or password",
                "Usuário ou senha inválidos",
                "Conta desativada",
                "Too many failed attempts",
                "Tentativas excessivas"
            ]
            
            for error_msg in error_messages:
                if error_msg in login_response.text:
                    return False, error_msg
            
            # Procurar elementos de erro do Keycloak
            error_div = soup.find('div', {'id': 'kc-error-message'})
            if error_div:
                return False, error_div.get_text(strip=True)
            
            return False, "Falha na autenticação. Verifique suas credenciais."
            
        except Exception as e:
            logger.error(f"Erro durante login: {e}", exc_info=True)
            return False, f"Erro: {str(e)}"
    
    def verify_session(self):
        """Verifica se a sessão é válida"""
        try:
            # Tentar acessar uma página que requer autenticação
            test_url = f"{APLICACAO_URL}/relatorios"
            
            response = self.session.get(
                test_url,
                timeout=10,
                allow_redirects=False
            )
            
            logger.info(f"Verificação de sessão - Status: {response.status_code}")
            
            # Se não for redirecionado para login, sessão é válida
            if response.status_code == 200:
                return True
            
            # Verificar se há redirecionamento para login
            if response.status_code == 302:
                location = response.headers.get('location', '')
                if 'auth' in location or 'login' in location:
                    logger.warning("Sessão expirada - redirecionado para login")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao verificar sessão: {e}")
            return False
    
    def login(self, cpf: str, senha: str) -> bool:
        """Fluxo completo de login"""
        try:
            st.info("🔍 Iniciando autenticação no portal UFF...")
            
            # Descobrir URL de login
            with st.spinner("Detectando portal de login..."):
                login_url = self.discover_login_url()
                
                if not login_url:
                    logger.error("Não foi possível encontrar URL de login")
                    st.error("❌ Não foi possível acessar o portal de login")
                    return False
            
            # Executar login no Keycloak
            with st.spinner("Autenticando no Keycloak..."):
                success, message = self.perform_keycloak_login(login_url, cpf, senha)
                
                if not success:
                    logger.error(f"Falha no login: {message}")
                    st.error(f"❌ {message}")
                    return False
            
            # Verificar sessão
            with st.spinner("Verificando sessão..."):
                if self.verify_session():
                    self.is_authenticated = True
                    st.success("✅ Login realizado com sucesso!")
                    logger.info("✅ Autenticação concluída com sucesso")
                    
                    # Log cookies finais
                    logger.info(f"Cookies finais: {dict(self.session.cookies)}")
                    
                    return True
                else:
                    logger.error("Falha na verificação da sessão")
                    st.error("❌ Falha na verificação da sessão")
                    return False
                
        except Exception as e:
            logger.error(f"Erro inesperado no login: {e}", exc_info=True)
            st.error(f"❌ Erro inesperado: {str(e)[:100]}")
            return False
    
    def get_session(self):
        """Retorna a sessão autenticada"""
        return self.session if self.is_authenticated else None


class GeradorRelatorios:
    """Classe para gerar relatórios"""
    
    def __init__(self, session):
        self.session = session
        self.base_url = APLICACAO_URL
    
    def acessar_pagina_listagem(self):
        """Acessa a página de listagem de alunos"""
        try:
            logger.info(f"Acessando: {LISTAGEM_ALUNOS_URL}")
            response = self.session.get(LISTAGEM_ALUNOS_URL, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.error(f"Erro ao acessar página de listagem: {e}")
            raise
    
    def extrair_parametros_formulario(self, soup):
        """Extrai parâmetros do formulário"""
        try:
            parametros = {
                'inputs': {},
                'selects': {},
                'action': None,
                'authenticity_token': None
            }
            
            form = soup.find('form')
            if not form:
                logger.error("Formulário não encontrado")
                logger.error(f"HTML disponível:\n{soup.prettify()[:2000]}")
                raise Exception("Formulário não encontrado")
            
            parametros['action'] = form.get('action', '')
            
            # Extrair todos os inputs
            for input_tag in form.find_all('input'):
                name = input_tag.get('name')
                if name:
                    parametros['inputs'][name] = {
                        'value': input_tag.get('value', ''),
                        'type': input_tag.get('type', 'text')
                    }
                    
                    if name == 'authenticity_token':
                        parametros['authenticity_token'] = input_tag.get('value')
            
            # Extrair todos os selects
            for select_tag in form.find_all('select'):
                name = select_tag.get('name')
                if name:
                    options = []
                    for option in select_tag.find_all('option'):
                        options.append({
                            'value': option.get('value', ''),
                            'text': option.get_text(strip=True),
                            'selected': 'selected' in option.attrs
                        })
                    parametros['selects'][name] = options
            
            logger.info(f"Formulário extraído - Token: {parametros.get('authenticity_token')}")
            logger.info(f"Selects disponíveis: {list(parametros['selects'].keys())}")
            
            return parametros
            
        except Exception as e:
            logger.error(f"Erro ao extrair parâmetros: {e}")
            raise
    
    def preencher_formulario_com_filtros(self, parametros, filtros):
        """Preenche o formulário com filtros"""
        dados_formulario = {}
        
        # Adicionar token CSRF se existir
        if parametros.get('authenticity_token'):
            dados_formulario['authenticity_token'] = parametros['authenticity_token']
        
        # Adicionar valores padrão dos inputs
        for name, input_info in parametros['inputs'].items():
            if input_info['value']:
                dados_formulario[name] = input_info['value']
        
        # Aplicar filtros
        for campo, valor_buscado in filtros.items():
            if campo in parametros['selects']:
                opcoes = parametros['selects'][campo]
                valor_encontrado = False
                
                # Tentar encontrar por valor exato
                for opcao in opcoes:
                    if str(opcao['value']).strip() == str(valor_buscado).strip():
                        dados_formulario[campo] = opcao['value']
                        logger.info(f"Filtro aplicado (exato): {campo} = {opcao['value']}")
                        valor_encontrado = True
                        break
                
                # Se não encontrou por valor, tentar por texto
                if not valor_encontrado:
                    for opcao in opcoes:
                        if valor_buscado in opcao['text']:
                            dados_formulario[campo] = opcao['value']
                            logger.info(f"Filtro aplicado (texto): {campo} = {opcao['value']}")
                            valor_encontrado = True
                            break
                
                if not valor_encontrado:
                    logger.warning(f"Filtro não encontrado: {campo} = {valor_buscado}")
        
        logger.info(f"Dados do formulário: {list(dados_formulario.keys())}")
        return dados_formulario
    
    def submeter_formulario(self, dados_formulario):
        """Submete o formulário"""
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
            
            # Extrair ID do relatório
            match = re.search(r'/relatorios/(\d+)', response.url)
            if match:
                relatorio_id = match.group(1)
                logger.info(f"Relatório criado - ID: {relatorio_id}")
                return {
                    'success': True,
                    'relatorio_id': relatorio_id,
                    'url': response.url
                }
            else:
                logger.error(f"Não encontrou ID na URL: {response.url}")
                return {'success': False, 'error': 'ID do relatório não encontrado'}
            
        except Exception as e:
            logger.error(f"Erro ao submeter formulário: {e}")
            return {'success': False, 'error': str(e)}
    
    def verificar_status_relatorio(self, relatorio_id):
        """Verifica status do relatório"""
        try:
            url = f"{BASE_URL}/relatorios/{relatorio_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procurar link de download
            download_link = soup.find('a', href=lambda x: x and '.xlsx' in x)
            if download_link:
                download_url = urljoin(BASE_URL, download_link.get('href'))
                return {
                    'status': 'PRONTO',
                    'download_url': download_url
                }
            
            return {'status': 'EM_PROCESSAMENTO'}
            
        except Exception as e:
            logger.error(f"Erro ao verificar status: {e}")
            return {'status': 'ERRO', 'error': str(e)}
    
    def aguardar_relatorio(self, relatorio_id, max_tentativas=30):
        """Aguarda relatório ficar pronto"""
        tentativa = 0
        while tentativa < max_tentativas:
            status_info = self.verificar_status_relatorio(relatorio_id)
            
            if status_info['status'] == 'PRONTO':
                return status_info
            elif status_info['status'] == 'ERRO':
                raise Exception(f"Erro no relatório: {status_info.get('error')}")
            
            tentativa += 1
            time.sleep(3)
        
        raise Exception(f"Timeout aguardando relatório {relatorio_id}")
    
    def baixar_relatorio(self, download_url):
        """Baixa o relatório"""
        try:
            response = self.session.get(download_url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Erro ao baixar relatório: {e}")
            raise
    
    def gerar_relatorio_completo(self, filtros, progress_callback=None):
        """Fluxo completo para gerar relatório"""
        try:
            if progress_callback:
                progress_callback("Acessando página...", 10)
            
            soup = self.acessar_pagina_listagem()
            
            if progress_callback:
                progress_callback("Extraindo parâmetros...", 25)
            
            parametros = self.extrair_parametros_formulario(soup)
            
            if progress_callback:
                progress_callback("Configurando filtros...", 40)
            
            dados_form = self.preencher_formulario_com_filtros(parametros, filtros)
            
            if progress_callback:
                progress_callback("Gerando relatório...", 55)
            
            resultado = self.submeter_formulario(dados_form)
            
            if not resultado['success']:
                raise Exception(f"Erro ao submeter: {resultado.get('error')}")
            
            relatorio_id = resultado['relatorio_id']
            
            if progress_callback:
                progress_callback(f"Aguardando relatório {relatorio_id}...", 70)
            
            status_info = self.aguardar_relatorio(relatorio_id)
            
            if progress_callback:
                progress_callback("Baixando relatório...", 85)
            
            conteudo_excel = self.baixar_relatorio(status_info['download_url'])
            
            if progress_callback:
                progress_callback("Relatório pronto!", 100)
            
            return conteudo_excel
            
        except Exception as e:
            logger.error(f"Erro no fluxo completo: {e}")
            raise


def main():
    """Aplicação principal"""
    st.set_page_config(
        page_title="Automador de Relatórios UFF",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Estilo CSS customizado
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        color: #374151;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton button {
        width: 100%;
        font-weight: bold;
    }
    .success-box {
        background-color: #D1FAE5;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #10B981;
    }
    .error-box {
        background-color: #FEE2E2;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #EF4444;
    }
    .info-box {
        background-color: #DBEAFE;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3B82F6;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="main-header">🎓 Automador de Relatórios - UFF Química</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Geração automatizada de relatórios de evasão</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Inicializar estado da sessão
    if 'auth' not in st.session_state:
        st.session_state.auth = None
    if 'session' not in st.session_state:
        st.session_state.session = None
    
    # Sidebar de login
    with st.sidebar:
        st.header("🔐 Autenticação")
        
        if st.session_state.session is None:
            st.markdown("### Credenciais UFF")
            
            cpf = st.text_input(
                "CPF:",
                placeholder="Somente números",
                help="Digite seu CPF sem pontuação (apenas números)"
            )
            
            senha = st.text_input(
                "Senha:",
                type="password",
                placeholder="Sua senha do portal UFF"
            )
            
            if st.button("🔑 Entrar no Portal", type="primary", use_container_width=True):
                if not cpf or not senha:
                    st.error("❌ CPF e senha são obrigatórios")
                else:
                    with st.spinner("Autenticando..."):
                        auth = UFFAuthenticator()
                        if auth.login(cpf, senha):
                            st.session_state.auth = auth
                            st.session_state.session = auth.get_session()
                            st.success("✅ Autenticado!")
                            st.rerun()
                        else:
                            st.error("❌ Falha na autenticação")
            
            st.markdown("---")
            st.markdown("""
            ### ℹ️ Informações:
            
            **Requisitos:**
            - Credenciais válidas do portal UFF
            - Conexão com rede UFF ou VPN
            - Navegador moderno
            
            **Suporte:**
            - CPF: apenas números
            - Senha: mesma do portal
            """)
            
        else:
            st.markdown('<div class="success-box">✅ Conectado ao portal UFF</div>', unsafe_allow_html=True)
            
            # Verificar sessão
            if st.session_state.auth and not st.session_state.auth.verify_session():
                st.warning("⚠️ Sessão expirada")
                if st.button("🔄 Reconectar"):
                    st.session_state.auth = None
                    st.session_state.session = None
                    st.rerun()
            
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.auth = None
                st.session_state.session = None
                st.rerun()
            
            st.markdown("---")
            st.markdown("""
            ### 📊 Pronto para gerar relatórios
            
            **Próximos passos:**
            1. Configure os filtros ao lado
            2. Selecione períodos e cursos
            3. Clique em gerar relatórios
            """)
    
    # Conteúdo principal
    if st.session_state.session is None:
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown('<div class="info-box">👈 Faça login na barra lateral para começar</div>', unsafe_allow_html=True)
            
            st.markdown("### 🚀 Como usar:")
            
            with st.expander("📋 Passo a passo", expanded=True):
                st.markdown("""
                1. **Login** - Use seu CPF e senha UFF
                2. **Configurar** - Selecione períodos e cursos
                3. **Processar** - O sistema gera os relatórios
                4. **Download** - Baixe a planilha consolidada
                """)
            
            with st.expander("⚙️ Configurações suportadas"):
                st.markdown("""
                **Períodos:**
                - 2025.1, 2025.2
                - 2026.1, 2026.2
                
                **Cursos (Química):**
                - Licenciatura
                - Bacharelado
                - Industrial
                
                **Filtros automáticos:**
                - Localidade: Niterói
                - Formas de ingresso: SISU
                """)
            
            with st.expander("⚠️ Solução de problemas"):
                st.markdown("""
                **Problemas comuns:**
                
                ❌ **Erro de autenticação:**
                - Verifique CPF e senha
                - Certifique-se de estar na rede UFF
                - Tente acessar manualmente o portal
                
                ⏱️ **Timeout:**
                - Verifique conexão com internet
                - Tente novamente mais tarde
                
                🔄 **Sessão expirada:**
                - Clique em Sair e faça login novamente
                """)
    
    else:
        # Interface para geração de relatórios
        st.header("⚙️ Configuração dos Relatórios")
        
        col1, col2 = st.columns(2)
        
        with col1:
            periodo_inicio = st.selectbox(
                "Período Inicial",
                options=['2025.1', '2025.2', '2026.1', '2026.2'],
                index=0,
                help="Selecione o período inicial da consulta"
            )
        
        with col2:
            periodo_fim = st.selectbox(
                "Período Final",
                options=['2025.1', '2025.2', '2026.1', '2026.2'],
                index=2,
                help="Selecione o período final da consulta"
            )
        
        cursos_selecionados = st.multiselect(
            "Selecione os cursos:",
            options=list(DESDOBRAMENTOS_CURSOS.keys()),
            default=list(DESDOBRAMENTOS_CURSOS.keys()),
            help="Selecione um ou mais cursos para gerar relatórios"
        )
        
        st.markdown("---")
        
        # Botão de ação principal
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(
                "🚀 GERAR RELATÓRIOS COMPLETOS",
                type="primary",
                use_container_width=True,
                help="Clique para iniciar a geração dos relatórios"
            ):
                if not cursos_selecionados:
                    st.error("❌ Selecione pelo menos um curso!")
                else:
                    # Verificar sessão
                    if not st.session_state.auth.verify_session():
                        st.error("❌ Sessão expirada. Faça login novamente.")
                        st.session_state.auth = None
                        st.session_state.session = None
                        st.rerun()
                    
                    # Converter períodos
                    def converter_periodo(periodo):
                        ano, semestre = periodo.split('.')
                        return f"{ano}/{semestre}°"
                    
                    periodo_inicio_fmt = converter_periodo(periodo_inicio)
                    periodo_fim_fmt = converter_periodo(periodo_fim)
                    
                    periodos = [periodo_inicio_fmt, periodo_fim_fmt]
                    
                    # Iniciar geração
                    gerador = GeradorRelatorios(st.session_state.session)
                    todos_dados = []
                    
                    # Configurar interface de progresso
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    resultados_container = st.container()
                    
                    total_relatorios = len(periodos) * len(cursos_selecionados)
                    relatorio_atual = 0
                    
                    try:
                        with resultados_container:
                            for periodo in periodos:
                                semestre = '1' if '1°' in periodo else '2'
                                forma_ingresso = FORMAS_INGRESSO[semestre]
                                
                                for curso_key in cursos_selecionados:
                                    relatorio_atual += 1
                                    
                                    curso_info = DESDOBRAMENTOS_CURSOS[curso_key]
                                    
                                    def callback_progresso(msg, pct):
                                        progresso_total = ((relatorio_atual - 1) * 100 + pct) / total_relatorios
                                        status_text.text(f"{relatorio_atual}/{total_relatorios} - {curso_key} - {periodo}: {msg}")
                                        progress_bar.progress(progresso_total / 100)
                                    
                                    try:
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
                                        
                                        # Processar dados
                                        df = pd.read_excel(io.BytesIO(conteudo_excel))
                                        df['curso'] = curso_key
                                        df['periodo'] = periodo
                                        todos_dados.append(df)
                                        
                                        st.success(f"✅ {curso_key} - {periodo}: Relatório gerado com sucesso!")
                                        
                                    except Exception as e:
                                        st.error(f"❌ {curso_key} - {periodo}: {str(e)[:100]}")
                                        logger.error(f"Erro em {curso_key}-{periodo}: {e}")
                            
                            # Consolidar resultados
                            if todos_dados:
                                status_text.text("Consolidando dados...")
                                progress_bar.progress(0.95)
                                
                                df_consolidado = pd.concat(todos_dados, ignore_index=True)
                                
                                # Gerar arquivo Excel
                                output = io.BytesIO()
                                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                    df_consolidado.to_excel(writer, sheet_name='Dados Consolidados', index=False)
                                
                                output.seek(0)
                                
                                # Botão de download
                                st.markdown("---")
                                st.markdown("### 📥 Download")
                                
                                st.download_button(
                                    label="⬇️ BAIXAR PLANILHA CONSOLIDADA",
                                    data=output.getvalue(),
                                    file_name=f"relatorios_uff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True
                                )
                                
                                progress_bar.progress(1.0)
                                status_text.text("✅ Processo concluído!")
                                
                                # Mostrar estatísticas
                                st.markdown("### 📊 Estatísticas")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total de Registros", len(df_consolidado))
                                with col2:
                                    st.metric("Cursos Processados", len(cursos_selecionados))
                                with col3:
                                    st.metric("Períodos", len(periodos))
                            
                            else:
                                st.error("❌ Nenhum relatório foi gerado com sucesso")
                        
                    except Exception as e:
                        st.error(f"❌ Erro geral: {str(e)}")
                        logger.error(f"Erro geral: {e}", exc_info=True)


if __name__ == "__main__":
    main()
