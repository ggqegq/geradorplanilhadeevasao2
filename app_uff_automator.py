"""
Automador de Relatórios - UFF Química
Versão 2.1: Login Corrigido com Fluxo Keycloak
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
from urllib.parse import urljoin, parse_qs, urlparse
import io
import urllib3

# Desativar warnings de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações
BASE_URL = "https://app.uff.br"
APLICACAO_URL = "https://app.uff.br/graduacao/administracaoacademica"
LOGIN_URL = "https://app.uff.br/auth/realms/master/protocol/openid-connect/auth"
TOKEN_URL = "https://app.uff.br/auth/realms/master/protocol/openid-connect/token"
LISTAGEM_ALUNOS_URL = f"{APLICACAO_URL}/relatorios/listagens_alunos"

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
    """Classe para fazer login via CPF e Senha usando fluxo Keycloak"""
    
    def __init__(self):
        self.session = requests.Session()
        # Configurar session para verificar SSL
        self.session.verify = False  # Desativar verificação SSL (pode ser necessário para alguns proxies)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Estado da autenticação
        self.is_authenticated = False
        self.auth_cookies = {}
    
    def _extract_login_parameters(self, html_content):
        """Extrai parâmetros do formulário de login (baseado no código funcional anterior)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Procurar formulário de login do Keycloak
        login_form = soup.find('form', {'id': 'kc-form-login'})
        
        if not login_form:
            # Tentar outros padrões
            login_form = soup.find('form', action=lambda x: x and '/auth/' in x)
            if not login_form:
                login_form = soup.find('form', method='post')
        
        if not login_form:
            logger.error("Formulário de login não encontrado no HTML")
            logger.debug(f"HTML: {html_content[:1000]}")
            return None
        
        action_url = login_form.get('action', '')
        if action_url and not action_url.startswith('http'):
            action_url = urljoin(BASE_URL, action_url)
        
        hidden_inputs = {}
        for input_tag in login_form.find_all('input', type='hidden'):
            name = input_tag.get('name')
            value = input_tag.get('value', '')
            if name:
                hidden_inputs[name] = value
        
        logger.info(f"Formulário encontrado. Action: {action_url}")
        logger.info(f"Campos hidden: {list(hidden_inputs.keys())}")
        
        return {
            'action_url': action_url,
            'hidden_fields': hidden_inputs
        }
    
    def fazer_login(self, cpf: str, senha: str) -> bool:
        """Faz login no portal UFF usando fluxo OAuth2/Keycloak"""
        try:
            st.info("Iniciando autenticação no portal UFF...")
            logger.info(f"Tentando login para CPF: {cpf}")
            
            # 1. Acessar página da aplicação para iniciar fluxo OAuth
            st.info("Acessando aplicação...")
            response = self.session.get(
                APLICACAO_URL,
                timeout=10,
                allow_redirects=True
            )
            
            # 2. Seguir redirecionamentos até a página de login
            redirect_count = 0
            while redirect_count < 5:
                if response.status_code == 200:
                    break
                elif response.status_code in [301, 302, 303, 307, 308]:
                    location = response.headers.get('Location', '')
                    if not location:
                        break
                    
                    if location.startswith('/'):
                        location = urljoin(BASE_URL, location)
                    
                    logger.info(f"Redirecionando para: {location}")
                    response = self.session.get(
                        location,
                        timeout=10,
                        allow_redirects=False
                    )
                    redirect_count += 1
                else:
                    break
            
            if response.status_code != 200:
                st.error(f"Falha ao acessar página de login. Status: {response.status_code}")
                return False
            
            logger.info("Página de login carregada")
            
            # 3. Extrair parâmetros do formulário
            login_params = self._extract_login_parameters(response.text)
            if not login_params:
                st.error("Não foi possível encontrar o formulário de login")
                logger.error(f"HTML da página: {response.text[:500]}")
                return False
            
            # 4. Preparar dados do formulário
            form_data = {
                'username': cpf,
                'password': senha,
                'rememberMe': 'on'
            }
            
            # Adicionar campos hidden
            form_data.update(login_params['hidden_fields'])
            
            # 5. Enviar requisição de login
            login_action = login_params['action_url']
            logger.info(f"Enviando login para: {login_action}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': response.url,
                'Origin': BASE_URL,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            }
            
            login_response = self.session.post(
                login_action,
                data=form_data,
                headers=headers,
                timeout=15,
                allow_redirects=False  # Importante: não seguir redirecionamentos automaticamente
            )
            
            # 6. Verificar resposta e seguir redirecionamentos
            if login_response.status_code in [301, 302, 303, 307, 308]:
                location = login_response.headers.get('Location', '')
                if location:
                    if location.startswith('/'):
                        location = urljoin(BASE_URL, location)
                    
                    logger.info(f"Login redirecionando para: {location}")
                    
                    # Seguir o redirecionamento
                    final_response = self.session.get(
                        location,
                        timeout=15,
                        allow_redirects=True
                    )
                    
                    # 7. Verificar se login foi bem-sucedido
                    if final_response.status_code == 200:
                        # Verificar se estamos na aplicação correta
                        if 'administracaoacademica' in final_response.url or APLICACAO_URL in final_response.url:
                            # Verificar cookies de sessão
                            if self.session.cookies.get('JSESSIONID'):
                                self.is_authenticated = True
                                self.auth_cookies = dict(self.session.cookies)
                                
                                # Verificar se podemos acessar página protegida
                                test_response = self.session.get(
                                    LISTAGEM_ALUNOS_URL,
                                    timeout=10,
                                    allow_redirects=False
                                )
                                
                                if test_response.status_code == 200:
                                    st.success("✅ Login realizado com sucesso!")
                                    logger.info(f"Login bem-sucedido para CPF: {cpf}")
                                    return True
                                else:
                                    st.warning("Login aparentemente bem-sucedido, mas acesso a relatórios falhou")
                                    logger.warning(f"Teste de acesso falhou: {test_response.status_code}")
                                    return True
                            else:
                                st.error("Sessão não estabelecida (cookies ausentes)")
                                return False
                        else:
                            # Verificar se há mensagem de erro
                            soup = BeautifulSoup(final_response.text, 'html.parser')
                            error_msg = soup.find('span', {'id': 'input-error'}) or \
                                       soup.find('div', {'class': 'alert-error'}) or \
                                       soup.find('div', {'class': 'kc-feedback-text'})
                            
                            if error_msg:
                                error_text = error_msg.get_text(strip=True)
                                st.error(f"Erro no login: {error_text}")
                            else:
                                st.error(f"Redirecionado para página inesperada: {final_response.url}")
                            return False
                else:
                    st.error("Redirecionamento sem URL de destino")
                    return False
            elif login_response.status_code == 200:
                # Verificar se há mensagem de erro na página
                soup = BeautifulSoup(login_response.text, 'html.parser')
                error_div = soup.find('div', {'id': 'kc-error-message'}) or \
                           soup.find('span', class_='kc-feedback-text')
                
                if error_div:
                    error_text = error_div.get_text(strip=True)
                    st.error(f"Erro de autenticação: {error_text}")
                else:
                    st.error("Falha no login - não houve redirecionamento")
                
                return False
            else:
                st.error(f"Status inesperado: {login_response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            st.error("Tempo limite excedido ao tentar fazer login")
            logger.error("Timeout no login")
            return False
        except requests.exceptions.ConnectionError:
            st.error("Erro de conexão. Verifique sua internet.")
            logger.error("Connection error no login")
            return False
        except Exception as e:
            st.error(f"Erro inesperado ao fazer login: {str(e)}")
            logger.error(f"Erro no login: {str(e)}", exc_info=True)
            return False
    
    def get_session(self):
        """Retorna a sessão autenticada"""
        if self.is_authenticated:
            return self.session
        return None
    
    def check_authentication(self):
        """Verifica se a autenticação ainda é válida"""
        if not self.is_authenticated:
            return False
        
        try:
            # Tentar acessar uma página protegida
            response = self.session.get(
                f"{APLICACAO_URL}/relatorios",
                timeout=10,
                allow_redirects=False
            )
            
            return response.status_code == 200
        except:
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
            
            # Verificar se estamos autenticados
            if 'auth' in response.url or response.status_code == 302:
                raise Exception("Sessão expirada ou não autenticada")
            
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
            # Tentar encontrar form por ID ou classe
            form = soup.find('form', {'id': 'new_report'}) or \
                   soup.find('form', {'class': 'report-form'})
        
        if not form:
            raise Exception("Formulário não encontrado na página")
        
        # Ação do formulário
        action = form.get('action', '')
        if action:
            if action.startswith('/'):
                action = urljoin(self.base_url, action)
            parametros['action'] = action
        else:
            parametros['action'] = LISTAGEM_ALUNOS_URL
        
        # Extrair inputs
        for input_tag in form.find_all('input'):
            name = input_tag.get('name', '')
            value = input_tag.get('value', '')
            
            if name == 'authenticity_token' or name == 'csrf_token':
                parametros['authenticity_token'] = value
            
            if name:
                parametros['inputs'][name] = {
                    'value': value, 
                    'type': input_tag.get('type', 'text'),
                    'id': input_tag.get('id', '')
                }
        
        # Extrair selects
        for select_tag in form.find_all('select'):
            name = select_tag.get('name', '')
            if name:
                options = []
                for option in select_tag.find_all('option'):
                    options.append({
                        'value': option.get('value', ''),
                        'text': option.get_text(strip=True),
                        'selected': 'selected' in option.attrs,
                        'data': option.attrs
                    })
                parametros['selects'][name] = options
        
        logger.info(f"Formulário extraído. Selects: {list(parametros['selects'].keys())}")
        return parametros
    
    def preencher_formulario_com_filtros(self, parametros, filtros):
        """Preenche o formulário com filtros específicos"""
        dados_formulario = {}
        
        # Adicionar token CSRF/authenticity_token
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
                
                # Primeiro tentar busca exata pelo valor
                for opcao in opcoes:
                    if str(opcao['value']).strip() == str(valor_buscado).strip():
                        dados_formulario[campo] = opcao['value']
                        logger.info(f"Filtro exato por valor: {campo} = {valor_buscado}")
                        valor_encontrado = True
                        break
                
                # Se não encontrou, buscar pelo texto
                if not valor_encontrado:
                    for opcao in opcoes:
                        if opcao['text'].strip() == str(valor_buscado).strip():
                            dados_formulario[campo] = opcao['value']
                            logger.info(f"Filtro exato por texto: {campo} = {valor_buscado}")
                            valor_encontrado = True
                            break
                
                # Se ainda não encontrou, busca parcial
                if not valor_encontrado:
                    for opcao in opcoes:
                        if valor_buscado in opcao['text']:
                            dados_formulario[campo] = opcao['value']
                            logger.info(f"Filtro parcial: {campo} = {valor_buscado} em '{opcao['text']}'")
                            valor_encontrado = True
                            break
                
                if not valor_encontrado:
                    logger.warning(f"Filtro não encontrado: {campo} = {valor_buscado}")
                    logger.warning(f"Opções disponíveis para {campo}:")
                    for opcao in opcoes[:10]:  # Mostrar apenas as primeiras 10 opções
                        logger.warning(f"  - '{opcao['text']}' (valor: {opcao['value']})")
            
            elif campo in parametros['inputs']:
                # É um campo de input
                dados_formulario[campo] = valor_buscado
                logger.info(f"Input definido: {campo} = {valor_buscado}")
        
        # Log dos dados que serão enviados
        logger.info(f"Dados do formulário: {list(dados_formulario.keys())}")
        
        return dados_formulario
    
    def submeter_formulario(self, dados_formulario, action_url):
        """Submete o formulário e obtém o ID do relatório"""
        try:
            logger.info(f"Submetendo formulário para: {action_url}")
            logger.info(f"Campos: {list(dados_formulario.keys())}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': LISTAGEM_ALUNOS_URL,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            }
            
            response = self.session.post(
                action_url,
                data=dados_formulario,
                headers=headers,
                timeout=30,
                allow_redirects=True
            )
            response.raise_for_status()
            
            logger.info(f"Formulário submetido. Status: {response.status_code}")
            logger.info(f"URL final: {response.url}")
            
            # Extrair ID do relatório da URL ou do HTML
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
                # Tentar encontrar no HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a', href=re.compile(r'/relatorios/\d+'))
                if links:
                    href = links[0].get('href', '')
                    match = re.search(r'/relatorios/(\d+)', href)
                    if match:
                        relatorio_id = match.group(1)
                        logger.info(f"Relatório ID encontrado no HTML: {relatorio_id}")
                        return {
                            'success': True,
                            'relatorio_id': relatorio_id,
                            'url': urljoin(self.base_url, href)
                        }
                
                logger.error("Não foi possível extrair o ID do relatório")
                logger.debug(f"HTML resposta: {response.text[:1000]}")
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
            download_links = soup.find_all('a', href=re.compile(r'\.(xlsx|xls|csv)$'))
            
            if download_links:
                download_url = download_links[0].get('href', '')
                if download_url.startswith('/'):
                    download_url = urljoin(self.base_url, download_url)
                
                logger.info(f"Relatório pronto para download: {download_url}")
                return {
                    'status': 'PRONTO',
                    'download_url': download_url
                }
            
            # Verificar se ainda está processando
            processando_text = soup.find(text=re.compile(r'processando|gerando|aguarde', re.I))
            if processando_text:
                return {'status': 'EM_PROCESSAMENTO'}
            
            # Verificar erros
            erro_text = soup.find(text=re.compile(r'erro|falha|não foi possível', re.I))
            if erro_text:
                return {'status': 'ERRO', 'error': erro_text.get_text(strip=True)}
            
            return {'status': 'DESCONHECIDO'}
        
        except Exception as e:
            logger.error(f"Erro ao verificar status: {str(e)}")
            return {'status': 'ERRO', 'error': str(e)}
    
    def aguardar_relatorio(self, relatorio_id, max_tentativas=60):
        """Aguarda o relatório ficar pronto"""
        tentativa = 0
        while tentativa < max_tentativas:
            logger.info(f"Verificando relatório {relatorio_id} (tentativa {tentativa + 1}/{max_tentativas})")
            status_info = self.verificar_status_relatorio(relatorio_id)
            
            if status_info['status'] == 'PRONTO':
                logger.info(f"Relatório {relatorio_id} está pronto!")
                return status_info
            elif status_info['status'] == 'ERRO':
                error_msg = status_info.get('error', 'Erro desconhecido')
                raise Exception(f"Erro ao processar relatório {relatorio_id}: {error_msg}")
            elif status_info['status'] == 'EM_PROCESSAMENTO':
                logger.info(f"Relatório {relatorio_id} ainda processando...")
                time.sleep(5)  # Aguardar 5 segundos
                tentativa += 1
            else:
                logger.info(f"Status desconhecido para relatório {relatorio_id}, aguardando...")
                time.sleep(5)
                tentativa += 1
        
        raise Exception(f"Timeout aguardando relatório {relatorio_id} após {max_tentativas} tentativas")
    
    def baixar_relatorio(self, download_url):
        """Baixa o arquivo Excel do relatório"""
        try:
            logger.info(f"Baixando relatório: {download_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': f"{self.base_url}/relatorios",
                'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,*/*'
            }
            
            response = self.session.get(
                download_url,
                headers=headers,
                timeout=30,
                stream=True
            )
            response.raise_for_status()
            
            # Ler conteúdo
            content = response.content
            
            if len(content) < 100:  # Arquivo muito pequeno pode ser erro
                logger.warning(f"Arquivo muito pequeno: {len(content)} bytes")
            
            logger.info(f"Relatório baixado: {len(content)} bytes")
            return content
            
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
            resultado = self.submeter_formulario(dados_form, parametros['action'])
            
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
    
    # Inicializar estado da sessão
    if 'uff_session' not in st.session_state:
        st.session_state.uff_session = None
    if 'login_instance' not in st.session_state:
        st.session_state.login_instance = None
    if 'gerador' not in st.session_state:
        st.session_state.gerador = None
    
    # Sidebar para login
    with st.sidebar:
        st.header("🔐 Login UFF")
        
        if st.session_state.uff_session is None:
            st.info("Informe suas credenciais UFF")
            
            cpf = st.text_input(
                "CPF:",
                type="password",
                help="Digite seu CPF sem pontuação",
                placeholder="12345678900"
            )
            
            senha = st.text_input(
                "Senha:",
                type="password",
                help="Digite sua senha do portal UFF",
                placeholder="Sua senha"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Entrar", use_container_width=True, type="primary"):
                    if not cpf or not senha:
                        st.error("CPF e senha são obrigatórios")
                    else:
                        with st.spinner("Autenticando no portal UFF..."):
                            login = LoginUFF()
                            if login.fazer_login(cpf, senha):
                                st.session_state.login_instance = login
                                st.session_state.uff_session = login.get_session()
                                
                                # Criar instância do gerador
                                if st.session_state.uff_session:
                                    st.session_state.gerador = GeradorRelatorios(st.session_state.uff_session)
                                
                                st.success("✅ Autenticado com sucesso!")
                                st.rerun()
                            else:
                                st.error("❌ Falha na autenticação. Verifique CPF e senha.")
            
            with col2:
                if st.button("Limpar", use_container_width=True):
                    st.session_state.uff_session = None
                    st.session_state.login_instance = None
                    st.session_state.gerador = None
                    st.rerun()
        
        else:
            st.success("✅ Conectado ao portal UFF")
            
            # Verificar status da sessão
            if st.session_state.login_instance:
                status = "ativo" if st.session_state.login_instance.check_authentication() else "expirado"
                st.caption(f"Status da sessão: {status}")
            
            if st.button("Sair", use_container_width=True, type="secondary"):
                st.session_state.uff_session = None
                st.session_state.login_instance = None
                st.session_state.gerador = None
                st.rerun()
        
        st.markdown("---")
        st.markdown("### 📋 Informações")
        st.markdown("""
        Este sistema automatiza a geração de relatórios de evasão dos cursos de Química da UFF.
        
        **Funcionalidades:**
        - Autenticação via CPF/senha UFF
        - Geração de múltiplos relatórios
        - Consolidação em planilha única
        """)
    
    # Conteúdo principal
    if st.session_state.uff_session is None:
        st.info("👈 Faça login no portal UFF usando seu CPF e senha para começar.")
        st.markdown("""
        ### Instruções:
        1. Use seu CPF e senha do portal UFF
        2. O sistema seguirá o fluxo de autenticação oficial
        3. Após login, configure os filtros e gere os relatórios
        """)
        
        # Exemplo de credenciais (apenas para demonstração)
        with st.expander("⚠️ Informações de Teste (se aplicável)"):
            st.markdown("""
            **Para ambiente de teste/demonstração:**
            - CPF: Utilize seu CPF real do sistema UFF
            - Senha: Sua senha do portal UFF
            
            **Observação:** 
            Este sistema utiliza a autenticação oficial da UFF.
            As credenciais não são armazenadas e são usadas apenas para estabelecer uma sessão.
            """)
    
    else:
        # Área de seleção de parâmetros
        st.header("⚙️ Configuração de Consulta")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            periodo_inicio = st.selectbox(
                "Período de Início",
                options=['2024.1', '2024.2', '2025.1', '2025.2', '2026.1'],
                index=2,
                help="Selecione o período inicial para consulta"
            )
        
        with col2:
            periodo_fim = st.selectbox(
                "Período de Fim",
                options=['2024.1', '2024.2', '2025.1', '2025.2', '2026.1'],
                index=4,
                help="Selecione o período final para consulta"
            )
        
        with col3:
            cursos_selecionados = st.multiselect(
                "Cursos para Consulta",
                options=list(DESDOBRAMENTOS_CURSOS.keys()),
                default=list(DESDOBRAMENTOS_CURSOS.keys()),
                help="Selecione os cursos para gerar relatórios"
            )
        
        # Verificar se períodos são válidos
        def periodo_para_numero(periodo):
            ano, semestre = periodo.split('.')
            return int(ano) * 10 + int(semestre)
        
        inicio_num = periodo_para_numero(periodo_inicio)
        fim_num = periodo_para_numero(periodo_fim)
        
        if inicio_num > fim_num:
            st.warning("⚠️ Período inicial é maior que o período final. Ajuste as datas.")
        
        st.markdown("---")
        
        # Botão para gerar relatórios
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            btn_gerar = st.button(
                "🚀 Gerar Relatórios e Planilha Consolidada",
                use_container_width=True,
                type="primary",
                disabled=not cursos_selecionados
            )
        
        if btn_gerar:
            if not cursos_selecionados:
                st.error("Selecione pelo menos um curso.")
                return
            
            # Converter períodos para o formato do sistema
            def converter_periodo(periodo):
                ano, semestre = periodo.split('.')
                return f"{ano}/{semestre}°"
            
            # Gerar períodos
            periodo_inicio_fmt = converter_periodo(periodo_inicio)
            periodo_fim_fmt = converter_periodo(periodo_fim)
            
            # Criar lista de períodos (apenas início e fim por enquanto)
            periodos = [periodo_inicio_fmt, periodo_fim_fmt]
            
            # Verificar se gerador está disponível
            if st.session_state.gerador is None:
                st.session_state.gerador = GeradorRelatorios(st.session_state.uff_session)
            
            gerador = st.session_state.gerador
            
            # Armazenar todos os dados
            todos_dados = []
            relatorios_gerados = []
            
            # Configurar interface de progresso
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_container = st.container()
            
            total_relatorios = len(periodos) * len(cursos_selecionados)
            relatorio_atual = 0
            
            with log_container:
                st.subheader("📊 Log de Execução")
                log_messages = st.empty()
                
                try:
                    logs = []
                    
                    for periodo in periodos:
                        # Determinar forma de ingresso
                        semestre = '1' if '1°' in periodo else '2'
                        forma_ingresso = FORMAS_INGRESSO[semestre]
                        
                        for curso_key in cursos_selecionados:
                            relatorio_atual += 1
                            progresso_base = (relatorio_atual - 1) / total_relatorios
                            
                            curso_info = DESDOBRAMENTOS_CURSOS[curso_key]
                            
                            def callback_progresso(msg, pct):
                                nonlocal logs
                                progresso_total = progresso_base + (pct / 100 / total_relatorios)
                                progress_bar.progress(progresso_total)
                                
                                log_msg = f"[{relatorio_atual}/{total_relatorios}] {curso_key} - {periodo}: {msg}"
                                logs.append(log_msg)
                                if len(logs) > 10:  # Manter apenas últimos 10 logs
                                    logs.pop(0)
                                log_messages.text("\n".join(logs))
                            
                            try:
                                callback_progresso("Preparando filtros...", 0)
                                
                                # Preparar filtros
                                filtros = {
                                    'report_filter_localidade': 'Niterói',
                                    'report_filter_curso': curso_info['buscar_por'],
                                    'report_filter_desdobramento': curso_info['valor'],
                                    'report_filter_forma_ingresso': forma_ingresso,
                                    'report_filter_ano_semestre_ingresso': periodo
                                }
                                
                                logger.info(f"Gerando relatório: {curso_key} - {periodo}")
                                logger.info(f"Filtros: {filtros}")
                                
                                # Gerar relatório
                                conteudo_excel = gerador.gerar_relatorio_completo(filtros, callback_progresso)
                                
                                # Ler dados do Excel
                                df = pd.read_excel(io.BytesIO(conteudo_excel))
                                
                                # Adicionar colunas identificadoras
                                df['curso'] = curso_key
                                df['periodo_ingresso'] = periodo
                                df['forma_ingresso'] = forma_ingresso
                                df['data_geracao'] = datetime.now()
                                
                                todos_dados.append(df)
                                relatorios_gerados.append({
                                    'curso': curso_key,
                                    'periodo': periodo,
                                    'registros': len(df),
                                    'status': 'sucesso'
                                })
                                
                                callback_progresso(f"✓ Gerado ({len(df)} registros)", 100)
                                
                            except Exception as e:
                                error_msg = f"Erro ao gerar relatório de {curso_key} ({periodo}): {str(e)}"
                                logger.error(error_msg)
                                logs.append(f"❌ {error_msg}")
                                
                                relatorios_gerados.append({
                                    'curso': curso_key,
                                    'periodo': periodo,
                                    'registros': 0,
                                    'status': 'erro',
                                    'erro': str(e)
                                })
                    
                    # Processar resultados
                    progress_bar.progress(1.0)
                    
                    if todos_dados:
                        callback_progresso("Processando dados consolidados...", 0)
                        
                        # Combinar todos os dados
                        df_consolidado = pd.concat(todos_dados, ignore_index=True)
                        
                        # Adicionar resumo
                        st.success(f"✅ Processo concluído! Total de {len(df_consolidado)} registros consolidados.")
                        
                        # Mostrar estatísticas
                        with st.expander("📈 Estatísticas da Consulta", expanded=True):
                            col_stat1, col_stat2, col_stat3 = st.columns(3)
                            with col_stat1:
                                st.metric("Total de Registros", len(df_consolidado))
                            with col_stat2:
                                st.metric("Cursos Processados", len(set(df_consolidado['curso'])))
                            with col_stat3:
                                st.metric("Períodos", len(set(df_consolidado['periodo_ingresso'])))
                        
                        # Mostrar resumo dos relatórios
                        st.subheader("📋 Resumo dos Relatórios Gerados")
                        df_resumo = pd.DataFrame(relatorios_gerados)
                        st.dataframe(
                            df_resumo,
                            use_container_width=True,
                            column_config={
                                'curso': 'Curso',
                                'periodo': 'Período',
                                'registros': 'Registros',
                                'status': st.column_config.TextColumn(
                                    'Status',
                                    help="Status do relatório"
                                )
                            }
                        )
                        
                        # Gerar arquivo Excel consolidado
                        callback_progresso("Gerando arquivo consolidado...", 0)
                        
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            # Dados consolidados
                            df_consolidado.to_excel(writer, sheet_name='Dados_Consolidados', index=False)
                            
                            # Resumo
                            df_resumo.to_excel(writer, sheet_name='Resumo_Execucao', index=False)
                            
                            # Metadados
                            metadados = pd.DataFrame({
                                'Parametro': ['Data Geração', 'Usuário CPF', 'Periodo Inicio', 'Periodo Fim', 'Cursos'],
                                'Valor': [
                                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'CPF_OCULTO',  # Por segurança
                                    periodo_inicio,
                                    periodo_fim,
                                    ', '.join(cursos_selecionados)
                                ]
                            })
                            metadados.to_excel(writer, sheet_name='Metadados', index=False)
                        
                        output.seek(0)
                        
                        # Botão de download
                        nome_arquivo = f"relatorios_consolidados_quimica_uff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        
                        st.download_button(
                            label="📥 Baixar Planilha Consolidada",
                            data=output.getvalue(),
                            file_name=nome_arquivo,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            type="primary"
                        )
                        
                        # Opção para visualizar dados
                        with st.expander("👁️ Visualizar Dados Consolidados"):
                            st.dataframe(df_consolidado.head(50), use_container_width=True)
                    
                    else:
                        st.error("❌ Nenhum relatório foi gerado com sucesso.")
                        if relatorios_gerados:
                            st.write("Detalhes dos erros:")
                            for rel in relatorios_gerados:
                                if rel['status'] == 'erro':
                                    st.error(f"{rel['curso']} - {rel['periodo']}: {rel.get('erro', 'Erro desconhecido')}")
                
                except Exception as e:
                    st.error(f"❌ Erro geral no processo: {str(e)}")
                    logger.error(f"Erro geral: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()
