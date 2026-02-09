"""
Automador de Relatórios - UFF Química
Versão Final: Método de login baseado no auth.py original
"""

import streamlit as st
import requests
import time
import re
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse
import io

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações EXATAMENTE como no auth.py original
BASE_URL = "https://app.uff.br"
APLICACAO_URL = "https://app.uff.br/graduacao/administracaoacademica"
TIMEOUT_REQUESTS = 30

# Headers como no auth.py original
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
}

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

class LoginUFF:
    """Classe IDÊNTICA ao auth.py original que funcionava"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.is_authenticated = False
        self.auth_data = {}
    
    def extract_login_parameters(self, html_content):
        """Extrai parâmetros do formulário de login - MÉTODO ORIGINAL QUE FUNCIONAVA"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # PRIMEIRO, tentar encontrar o formulário pelo ID - como no original
        login_form = soup.find('form', {'id': 'kc-form-login'})
        
        if not login_form:
            # Tentar outros padrões comuns - como no original
            login_form = soup.find('form', action=lambda x: x and '/auth/' in x)
            if not login_form:
                login_form = soup.find('form', method='post')
        
        if not login_form:
            logger.error("Formulário não encontrado")
            # Debug: mostrar tipos de formulários encontrados
            forms = soup.find_all('form')
            for i, form in enumerate(forms):
                logger.error(f"Form {i}: id={form.get('id')}, action={form.get('action')}, method={form.get('method')}")
            return None
        
        action_url = login_form.get('action', '')
        hidden_inputs = {}
        
        for input_tag in login_form.find_all('input', type='hidden'):
            name = input_tag.get('name', '')
            value = input_tag.get('value', '')
            if name:
                hidden_inputs[name] = value
        
        logger.info(f"Formulário encontrado - Action: {action_url}")
        logger.info(f"Campos hidden extraídos: {list(hidden_inputs.keys())}")
        
        # DEBUG: Mostrar todos os campos do formulário
        logger.debug("Todos os campos do formulário:")
        for input_tag in login_form.find_all('input'):
            name = input_tag.get('name', '')
            value = input_tag.get('value', '')
            input_type = input_tag.get('type', 'text')
            if name:
                logger.debug(f"  Campo: name='{name}', value='{value}', type='{input_type}'")
        
        return {
            'action_url': action_url,
            'hidden_fields': hidden_inputs
        }
    
    def fazer_login(self, cpf: str, senha: str) -> bool:
        """Realiza login no sistema UFF - VERSÃO SIMPLIFICADA DO ORIGINAL"""
        try:
            st.info("Conectando ao portal UFF...")
            logger.info(f"Tentando login para CPF: {cpf}")
            
            # PASSO 1: Acessar a página inicial da aplicação - como no original
            st.info("Acessando aplicação...")
            response = self.session.get(APLICACAO_URL, timeout=TIMEOUT_REQUESTS)
            
            if response.status_code != 200:
                logger.error(f"Falha ao acessar página: {response.status_code}")
                st.error(f"Erro de conexão: Status {response.status_code}")
                return False
            
            # DEBUG: Mostrar redirecionamentos
            if response.history:
                logger.info("Histórico de redirecionamentos:")
                for i, resp in enumerate(response.history):
                    logger.info(f"  [{i}] {resp.status_code} → {resp.url}")
            
            logger.info(f"URL final: {response.url}")
            logger.info(f"Cookies após acesso inicial: {dict(self.session.cookies)}")
            
            # PASSO 2: Extrair parâmetros do formulário de login
            st.info("Extraindo parâmetros de login...")
            login_params = self.extract_login_parameters(response.text)
            
            if not login_params:
                logger.error("Não foi possível encontrar o formulário de login")
                # Mostrar um pouco do HTML para debug
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.find('title')
                if title:
                    logger.error(f"Título da página: {title.text}")
                
                # Procurar por texto indicativo
                if "login" in response.text.lower():
                    logger.error("Texto 'login' encontrado na página")
                if "keycloak" in response.text.lower():
                    logger.error("Texto 'keycloak' encontrado na página")
                
                st.error("Não foi possível acessar o formulário de login. Tente novamente.")
                return False
            
            # PASSO 3: Preparar dados do formulário - SIMPLES como no original
            st.info("Enviando credenciais...")
            
            form_data = {
                'username': cpf,
                'password': senha,
                'rememberMe': 'on'
            }
            
            # Adicionar campos hidden - IMPORTANTE: como no original
            if login_params['hidden_fields']:
                form_data.update(login_params['hidden_fields'])
            
            # PASSO 4: Construir URL completa da ação
            login_action = login_params['action_url']
            
            # Se for URL relativa, construir URL completa - como no original
            if login_action.startswith('/'):
                parsed_base = urlparse(BASE_URL)
                login_action = f"{parsed_base.scheme}://{parsed_base.netloc}{login_action}"
            elif not login_action.startswith('http'):
                # Se não começar com http, juntar com base
                login_action = urljoin(BASE_URL, login_action)
            
            logger.info(f"Enviando login para: {login_action}")
            logger.info(f"Payload com campos: {list(form_data.keys())}")
            
            # PASSO 5: Enviar requisição de login - SIMPLES como no original
            headers = {
                'User-Agent': HEADERS['User-Agent'],
                'Referer': response.url,
                'Origin': BASE_URL,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            login_response = self.session.post(
                login_action,
                data=form_data,
                headers=headers,
                allow_redirects=True,  # IMPORTANTE: permitir redirecionamentos
                timeout=TIMEOUT_REQUESTS
            )
            
            # DEBUG detalhado da resposta
            logger.info(f"Status após login: {login_response.status_code}")
            logger.info(f"URL após login: {login_response.url}")
            logger.info(f"Cookies após login: {dict(self.session.cookies)}")
            
            # PASSO 6: Verificar se login foi bem-sucedido - CRITÉRIOS SIMPLES
            success = False
            success_criteria = []
            
            # Critério 1: URL contém aplicação
            if 'administracaoacademica' in login_response.url:
                success_criteria.append("URL contém 'administracaoacademica'")
                success = True
            
            # Critério 2: Status 200
            if login_response.status_code == 200:
                success_criteria.append("Status 200 OK")
                success = True
                
                # Verificar se há mensagem de erro na página
                soup = BeautifulSoup(login_response.text, 'html.parser')
                
                # Procurar por mensagens de erro comuns
                error_selectors = [
                    {'id': 'kc-error-message'},
                    {'class': 'kc-feedback-text'},
                    {'class': 'alert-error'},
                    {'class': 'alert'},
                    {'class': 'error'}
                ]
                
                for selector in error_selectors:
                    error_element = soup.find('div', selector) or soup.find('span', selector)
                    if error_element:
                        error_text = error_element.get_text(strip=True)
                        if error_text:
                            logger.error(f"Mensagem de erro encontrada: {error_text}")
                            st.error(f"Erro: {error_text}")
                            return False
            
            # Critério 3: Cookies de sessão
            cookies = dict(self.session.cookies)
            if cookies:
                success_criteria.append(f"Cookies presentes: {len(cookies)}")
                logger.info(f"Cookies detalhados: {cookies}")
                if 'JSESSIONID' in cookies or 'AUTH_SESSION_ID' in cookies:
                    success_criteria.append("Cookies de sessão encontrados")
                    success = True
            
            logger.info(f"Critérios de sucesso: {success_criteria}")
            
            if success:
                self.is_authenticated = True
                
                # TESTAR ACESSO à página protegida
                test_url = f"{APLICACAO_URL}/relatorios"
                try:
                    test_response = self.session.get(test_url, timeout=10, allow_redirects=False)
                    
                    if test_response.status_code == 200:
                        st.success("✅ Login realizado com sucesso!")
                        logger.info("✅ Login bem-sucedido! Acesso à aplicação confirmado.")
                        return True
                    elif test_response.status_code == 302:
                        location = test_response.headers.get('location', '')
                        if 'auth' not in location:
                            st.success("✅ Login realizado com sucesso!")
                            logger.info("✅ Login bem-sucedido!")
                            return True
                        else:
                            st.warning("⚠️ Login realizado, mas sessão pode ser instável")
                            logger.warning(f"Redirecionado para: {location}")
                            return True
                    else:
                        st.warning("⚠️ Login pode ter sido bem-sucedido, mas verificação falhou")
                        logger.warning(f"Status do teste: {test_response.status_code}")
                        return True
                        
                except Exception as test_error:
                    logger.error(f"Erro no teste de acesso: {test_error}")
                    st.success("✅ Login realizado!")
                    return True
            else:
                # Analisar possíveis erros
                soup = BeautifulSoup(login_response.text, 'html.parser')
                
                # Verificar se é página de erro do Keycloak
                error_div = soup.find('div', {'id': 'kc-error-message'})
                if error_div:
                    error_msg = error_div.get_text(strip=True)
                    logger.error(f"Erro Keycloak: {error_msg}")
                    st.error(f"Erro de autenticação: {error_msg}")
                    return False
                
                # Verificar mensagens genéricas
                page_text = login_response.text.lower()
                if "invalid username or password" in page_text:
                    error_msg = "CPF ou senha inválidos"
                elif "account is disabled" in page_text:
                    error_msg = "Conta desativada"
                elif "too many failed attempts" in page_text:
                    error_msg = "Muitas tentativas falhas. Tente novamente mais tarde."
                else:
                    # Procurar por qualquer texto de erro
                    error_spans = soup.find_all('span', class_=lambda x: x and 'error' in x.lower())
                    if error_spans:
                        error_msg = error_spans[0].get_text(strip=True)
                    else:
                        error_msg = "Falha na autenticação. Verifique suas credenciais."
                
                logger.error(f"Falha no login: {error_msg}")
                st.error(f"❌ {error_msg}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Timeout ao tentar fazer login")
            st.error("⏱️ Tempo limite excedido. Verifique sua conexão com a internet.")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Erro de conexão")
            st.error("🔌 Erro de conexão. Verifique se o portal UFF está acessível.")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado durante o login: {str(e)}", exc_info=True)
            st.error(f"⚠️ Erro inesperado: {str(e)[:100]}")
            return False
    
    def get_session(self):
        """Retorna a sessão autenticada"""
        return self.session if self.is_authenticated else None
    
    def check_session(self):
        """Verifica se a sessão ainda é válida"""
        if not self.is_authenticated:
            return False
        
        try:
            test_url = f"{APLICACAO_URL}/relatorios"
            response = self.session.get(test_url, timeout=10, allow_redirects=False)
            
            if response.status_code == 200:
                return True
            elif response.status_code == 302:
                location = response.headers.get('location', '')
                if 'auth' not in location and 'login' not in location:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar sessão: {e}")
            return False


class GeradorRelatorios:
    """Classe para gerar relatórios"""
    
    def __init__(self, session):
        self.session = session
        self.base_url = APLICACAO_URL
    
    def acessar_pagina_listagem(self):
        """Acessa a página de listagem de alunos"""
        try:
            LISTAGEM_ALUNOS_URL = f"{self.base_url}/relatorios/listagens_alunos"
            response = self.session.get(LISTAGEM_ALUNOS_URL, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.error(f"Erro ao acessar página de listagem: {e}")
            raise
    
    def extrair_parametros_formulario(self, soup):
        """Extrai parâmetros do formulário"""
        parametros = {
            'inputs': {},
            'selects': {},
            'action': None,
            'authenticity_token': None
        }
        
        form = soup.find('form')
        if not form:
            raise Exception("Formulário não encontrado")
        
        parametros['action'] = form.get('action', '')
        
        for input_tag in form.find_all('input'):
            name = input_tag.get('name')
            if name:
                parametros['inputs'][name] = {
                    'value': input_tag.get('value', ''),
                    'type': input_tag.get('type', 'text')
                }
                if name == 'authenticity_token':
                    parametros['authenticity_token'] = input_tag.get('value')
        
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
        
        return parametros
    
    def preencher_formulario_com_filtros(self, parametros, filtros):
        """Preenche o formulário com filtros"""
        dados_formulario = {}
        
        if parametros.get('authenticity_token'):
            dados_formulario['authenticity_token'] = parametros['authenticity_token']
        
        for name, input_info in parametros['inputs'].items():
            if input_info['value']:
                dados_formulario[name] = input_info['value']
        
        for campo, valor_buscado in filtros.items():
            if campo in parametros['selects']:
                opcoes = parametros['selects'][campo]
                for opcao in opcoes:
                    if str(opcao['value']).strip() == str(valor_buscado).strip():
                        dados_formulario[campo] = opcao['value']
                        break
                    elif valor_buscado in opcao['text']:
                        dados_formulario[campo] = opcao['value']
                        break
        
        return dados_formulario
    
    def submeter_formulario(self, dados_formulario):
        """Submete o formulário"""
        try:
            action_url = urljoin(self.base_url, '/graduacao/administracaoacademica/relatorios/listagens_alunos')
            
            response = self.session.post(
                action_url,
                data=dados_formulario,
                timeout=30,
                allow_redirects=True
            )
            response.raise_for_status()
            
            match = re.search(r'/relatorios/(\d+)', response.url)
            if match:
                relatorio_id = match.group(1)
                return {
                    'success': True,
                    'relatorio_id': relatorio_id,
                    'url': response.url
                }
            else:
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
        page_title="Automador de Relatórios UFF - Química",
        layout="wide"
    )
    
    st.title("🎓 Automador de Relatórios - UFF Química")
    st.markdown("---")
    
    # Inicializar estado
    if 'session' not in st.session_state:
        st.session_state.session = None
        st.session_state.auth = None
    
    # Sidebar de login
    with st.sidebar:
        st.header("🔐 Login")
        
        if st.session_state.session is None:
            st.markdown("#### Credenciais UFF")
            
            cpf = st.text_input("CPF:", key="cpf_input", 
                               help="Digite apenas números, sem pontuação")
            senha = st.text_input("Senha:", type="password", key="senha_input")
            
            if st.button("🚀 Entrar", use_container_width=True, type="primary"):
                if cpf and senha:
                    with st.spinner("Autenticando..."):
                        auth = LoginUFF()
                        if auth.fazer_login(cpf, senha):
                            st.session_state.auth = auth
                            st.session_state.session = auth.get_session()
                            st.success("✅ Conectado!")
                            st.rerun()
                        else:
                            st.error("❌ Falha na autenticação")
                else:
                    st.warning("⚠️ Preencha CPF e senha")
            
            st.markdown("---")
            st.markdown("""
            **ℹ️ Ajuda:**
            - Use suas credenciais do portal UFF
            - Certifique-se de estar na rede UFF/VPN
            - CPF apenas números (ex: 12345678901)
            """)
            
        else:
            # Verificar sessão
            if st.session_state.auth and not st.session_state.auth.check_session():
                st.warning("⚠️ Sessão expirada")
                if st.button("🔄 Reconectar", use_container_width=True):
                    st.session_state.session = None
                    st.session_state.auth = None
                    st.rerun()
            else:
                st.success("✅ Conectado ao portal UFF")
            
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.session = None
                st.session_state.auth = None
                st.rerun()
    
    # Conteúdo principal
    if st.session_state.session is None:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info("👈 Faça login na barra lateral para começar")
            
            with st.expander("📋 Instruções detalhadas", expanded=True):
                st.markdown("""
                1. **Digite suas credenciais UFF** na barra lateral
                2. **Clique em Entrar** para autenticar
                3. **Configure os filtros** desejados
                4. **Clique em Gerar Relatórios** para processar
                5. **Baixe a planilha consolidada** ao final
                
                **Suporte técnico:**
                - Certifique-se de estar na rede UFF
                - Verifique se suas credenciais estão corretas
                - Em caso de erro, tente novamente em alguns minutos
                """)
    
    else:
        # Interface de configuração
        st.header("⚙️ Configuração dos Relatórios")
        
        col1, col2 = st.columns(2)
        
        with col1:
            periodo_inicio = st.selectbox(
                "Período Inicial",
                options=['2025.1', '2025.2', '2026.1', '2026.2'],
                index=0
            )
        
        with col2:
            periodo_fim = st.selectbox(
                "Período Final",
                options=['2025.1', '2025.2', '2026.1', '2026.2'],
                index=2
            )
        
        cursos_selecionados = st.multiselect(
            "Selecione os cursos:",
            options=list(DESDOBRAMENTOS_CURSOS.keys()),
            default=list(DESDOBRAMENTOS_CURSOS.keys())
        )
        
        st.markdown("---")
        
        # Botão principal
        if st.button("🚀 GERAR RELATÓRIOS", type="primary", use_container_width=True):
            if not cursos_selecionados:
                st.error("❌ Selecione pelo menos um curso!")
                return
            
            # Verificar sessão
            if not st.session_state.auth.check_session():
                st.error("❌ Sessão expirada. Faça login novamente.")
                st.session_state.session = None
                st.session_state.auth = None
                st.rerun()
                return
            
            # Converter períodos
            def converter_periodo(periodo):
                ano, semestre = periodo.split('.')
                return f"{ano}/{semestre}°"
            
            periodo_inicio_fmt = converter_periodo(periodo_inicio)
            periodo_fim_fmt = converter_periodo(periodo_fim)
            
            periodos = [periodo_inicio_fmt, periodo_fim_fmt]
            
            # Iniciar processamento
            gerador = GeradorRelatorios(st.session_state.session)
            todos_dados = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_relatorios = len(periodos) * len(cursos_selecionados)
            relatorio_atual = 0
            
            try:
                for periodo in periodos:
                    semestre = '1' if '1°' in periodo else '2'
                    forma_ingresso = FORMAS_INGRESSO[semestre]
                    
                    for curso_key in cursos_selecionados:
                        relatorio_atual += 1
                        
                        curso_info = DESDOBRAMENTOS_CURSOS[curso_key]
                        
                        def callback_progresso(msg, pct):
                            progresso_total = ((relatorio_atual - 1) * 100 + pct) / total_relatorios
                            status_text.text(f"{relatorio_atual}/{total_relatorios} - {curso_key}: {msg}")
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
                            
                            st.success(f"✅ {curso_key} - {periodo}: Relatório gerado")
                            
                        except Exception as e:
                            st.error(f"❌ {curso_key} - {periodo}: Erro ao gerar relatório")
                            logger.error(f"Erro: {e}")
                
                # Consolidar resultados
                if todos_dados:
                    df_consolidado = pd.concat(todos_dados, ignore_index=True)
                    
                    # Gerar arquivo
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_consolidado.to_excel(writer, sheet_name='Dados Consolidados', index=False)
                    
                    output.seek(0)
                    
                    # Botão de download
                    st.download_button(
                        label="📥 BAIXAR PLANILHA CONSOLIDADA",
                        data=output.getvalue(),
                        file_name=f"relatorios_uff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                    progress_bar.progress(1.0)
                    status_text.text("✅ Processo concluído!")
                    
                else:
                    st.error("❌ Nenhum relatório foi gerado com sucesso")
                
            except Exception as e:
                st.error(f"❌ Erro geral: {str(e)}")
                logger.error(f"Erro geral: {e}")


if __name__ == "__main__":
    main()
