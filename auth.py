"""
auth.py - Módulo de autenticação no sistema UFF (versão funcional)
"""
import requests
from bs4 import BeautifulSoup
import re
import logging
from urllib.parse import urlparse, urljoin
from config import *

logger = logging.getLogger(__name__)

class UFFAuthenticator:
    """Classe para gerenciar autenticação no sistema UFF"""
    
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
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
            return None
        
        action_url = login_form.get('action', '')
        hidden_inputs = {}
        
        for input_tag in login_form.find_all('input', type='hidden'):
            name = input_tag.get('name', '')
            value = input_tag.get('value', '')
            if name:
                hidden_inputs[name] = value
        
        return {
            'action_url': action_url,
            'hidden_fields': hidden_inputs
        }
    
    def login(self, username=None, password=None):
        """Realiza login no sistema UFF usando a lógica que estava funcionando"""
        if username:
            self.username = username
        if password:
            self.password = password
        
        if not self.username or not self.password:
            raise ValueError("Usuário e senha são obrigatórios")
        
        try:
            logger.info(f"Tentando login para usuário: {self.username}")
            
            # 1. Acessar a página inicial da aplicação
            login_page_url = APLICACAO_URL
            response = self.session.get(login_page_url, timeout=TIMEOUT_REQUESTS)
            
            if response.status_code != 200:
                logger.error(f"Falha ao acessar página: {response.status_code}")
                return False
            
            # 2. Extrair parâmetros do formulário de login
            login_params = self.extract_login_parameters(response.text)
            
            if not login_params:
                logger.error("Não foi possível encontrar o formulário de login")
                return False
            
            # 3. Preparar dados do formulário
            form_data = {
                'username': self.username,
                'password': self.password,
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
            
            # 5. Enviar requisição de login
            headers = {
                'User-Agent': HEADERS['User-Agent'],
                'Referer': login_page_url,
                'Origin': BASE_URL,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            logger.info(f"Enviando login para: {login_action}")
            
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
                    
                    logger.info("✅ Login realizado com sucesso!")
                    return True
                else:
                    # Verificar se há mensagem de erro
                    soup = BeautifulSoup(login_response.text, 'html.parser')
                    error_div = soup.find('div', {'id': 'kc-error-message'}) or \
                               soup.find('span', class_='kc-feedback-text') or \
                               soup.find('div', class_='alert-error')
                    
                    if error_div:
                        error_msg = error_div.get_text(strip=True)
                        logger.error(f"Erro no login: {error_msg}")
                    else:
                        logger.error(f"Redirecionado para URL incorreta: {login_response.url}")
                    
                    return False
            
            logger.error(f"Status code inesperado: {login_response.status_code}")
            return False
                
        except Exception as e:
            logger.error(f"Erro durante o login: {str(e)}", exc_info=True)
            return False
    
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
        
        # Extrair outros tokens úteis
        for input_tag in soup.find_all('input', type='hidden'):
            name = input_tag.get('name', '')
            if name and 'token' in name.lower():
                value = input_tag.get('value', '')
                if value:
                    self.auth_data[name] = value
    
    def logout(self):
        """Realiza logout do sistema"""
        if self.is_authenticated:
            try:
                logout_url = f"{BASE_URL}/auth/realms/master/protocol/openid-connect/logout"
                response = self.session.get(logout_url, timeout=TIMEOUT_REQUESTS)
                self.is_authenticated = False
                self.session.cookies.clear()
                logger.info("Logout realizado com sucesso")
            except Exception as e:
                logger.error(f"Erro durante logout: {str(e)}")
    
    def check_session(self):
        """Verifica se a sessão ainda é válida"""
        if not self.is_authenticated:
            return False
        
        try:
            # Tentar acessar uma página que requer autenticação
            test_url = f"{APLICACAO_URL}/relatorios"
            response = self.session.get(test_url, timeout=TIMEOUT_REQUESTS, allow_redirects=False)
            
            # Se for redirecionado para login, sessão expirou
            if response.status_code == 302:
                location = response.headers.get('location', '')
                if 'auth' in location or 'login' in location:
                    return False
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao verificar sessão: {str(e)}")
            return False
    
    def get_session(self):
        """Retorna a sessão autenticada"""
        return self.session if self.is_authenticated else None
    
    def refresh_session(self):
        """Tenta renovar a sessão se estiver expirada"""
        if not self.check_session() and self.username and self.password:
            logger.info("Sessão expirada, tentando renovar...")
            return self.login(self.username, self.password)
        return self.is_authenticated
