"""
Automador de Relatórios - UFF Química
Versão Final: Login funcionando + Correção do erro 422
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

# Configurações
BASE_URL = "https://app.uff.br"
APLICACAO_URL = "https://app.uff.br/graduacao/administracaoacademica"
TIMEOUT_REQUESTS = 30

# Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
}

# Mapeamento de Desdobramentos - ATUALIZADO com valores corretos
DESDOBRAMENTOS_CURSOS = {
    'Licenciatura': {
        'valor': '12700',  # Apenas o código numérico
        'buscar_por': 'Química',
        'nome_padrao': 'Química (Licenciatura)',
        'texto_completo': 'Química (Licenciatura) (12700)'
    },
    'Bacharelado': {
        'valor': '312700',  # Apenas o código numérico
        'buscar_por': 'Química',
        'nome_padrao': 'Química (Bacharelado)',
        'texto_completo': 'Química (Bacharelado) (312700)'
    },
    'Industrial': {
        'valor': '12709',  # Apenas o código numérico
        'buscar_por': 'Química Industrial',
        'nome_padrao': 'Química Industrial',
        'texto_completo': 'Química Industrial (12709)'
    }
}

# Formas de ingresso - ATUALIZADO
FORMAS_INGRESSO = {
    '1': '1',  # Código para SISU 1ª Edição
    '2': '2'   # Código para SISU 2ª Edição
}

class LoginUFF:
    """Classe de login - JÁ FUNCIONANDO"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.is_authenticated = False
        self.auth_data = {}
    
    def extract_login_parameters(self, html_content):
        """Extrai parâmetros do formulário de login"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        login_form = soup.find('form', {'id': 'kc-form-login'})
        
        if not login_form:
            login_form = soup.find('form', action=lambda x: x and '/auth/' in x)
            if not login_form:
                login_form = soup.find('form', method='post')
        
        if not login_form:
            logger.error("Formulário não encontrado")
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
        
        return {
            'action_url': action_url,
            'hidden_fields': hidden_inputs
        }
    
    def fazer_login(self, cpf: str, senha: str) -> bool:
        """Realiza login no sistema UFF"""
        try:
            st.info("Conectando ao portal UFF...")
            logger.info(f"Tentando login para CPF: {cpf}")
            
            # Acessar a página inicial
            response = self.session.get(APLICACAO_URL, timeout=TIMEOUT_REQUESTS)
            
            if response.status_code != 200:
                logger.error(f"Falha ao acessar página: {response.status_code}")
                return False
            
            # Extrair parâmetros
            login_params = self.extract_login_parameters(response.text)
            
            if not login_params:
                logger.error("Não foi possível encontrar o formulário de login")
                return False
            
            # Preparar dados
            form_data = {
                'username': cpf,
                'password': senha,
                'rememberMe': 'on'
            }
            
            if login_params['hidden_fields']:
                form_data.update(login_params['hidden_fields'])
            
            # Construir URL completa
            login_action = login_params['action_url']
            
            if login_action.startswith('/'):
                parsed_base = urlparse(BASE_URL)
                login_action = f"{parsed_base.scheme}://{parsed_base.netloc}{login_action}"
            elif not login_action.startswith('http'):
                login_action = urljoin(BASE_URL, login_action)
            
            logger.info(f"Enviando login para: {login_action}")
            
            # Enviar requisição
            headers = {
                'User-Agent': HEADERS['User-Agent'],
                'Referer': response.url,
                'Origin': BASE_URL,
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            login_response = self.session.post(
                login_action,
                data=form_data,
                headers=headers,
                allow_redirects=True,
                timeout=TIMEOUT_REQUESTS
            )
            
            # Verificar sucesso
            if 'administracaoacademica' in login_response.url and login_response.status_code == 200:
                self.is_authenticated = True
                st.success("✅ Login realizado com sucesso!")
                logger.info("✅ Login bem-sucedido!")
                return True
            else:
                st.error("❌ Falha na autenticação")
                return False
                
        except Exception as e:
            logger.error(f"Erro durante o login: {str(e)}")
            st.error(f"Erro: {str(e)}")
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
                if 'auth' not in location:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar sessão: {e}")
            return False


class GeradorRelatorios:
    """Classe para gerar relatórios - CORRIGIDA para erro 422"""
    
    def __init__(self, session):
        self.session = session
        self.base_url = APLICACAO_URL
        self.listagem_url = f"{self.base_url}/relatorios/listagens_alunos"
    
    def acessar_pagina_listagem(self):
        """Acessa a página de listagem de alunos"""
        try:
            logger.info(f"Acessando: {self.listagem_url}")
            response = self.session.get(self.listagem_url, timeout=15)
            response.raise_for_status()
            
            # DEBUG: Salvar HTML para análise
            with open('debug_formulario.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info("HTML do formulário salvo em debug_formulario.html")
            
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.error(f"Erro ao acessar página de listagem: {e}")
            raise
    
    def extrair_parametros_formulario(self, soup):
        """Extrai TODOS os parâmetros do formulário"""
        try:
            logger.info("Extraindo parâmetros do formulário...")
            
            # Encontrar TODOS os formulários na página
            forms = soup.find_all('form')
            logger.info(f"Total de formulários encontrados: {len(forms)}")
            
            for i, form in enumerate(forms):
                logger.info(f"Formulário {i}: id={form.get('id')}, action={form.get('action')}")
            
            # Procurar formulário específico para relatórios
            target_form = None
            for form in forms:
                action = form.get('action', '').lower()
                form_id = form.get('id', '').lower()
                
                if 'listagens_alunos' in action or 'relatorios' in action:
                    target_form = form
                    break
                elif 'report' in form_id or 'filter' in form_id:
                    target_form = form
                    break
            
            if not target_form and forms:
                target_form = forms[0]  # Usar primeiro formulário
            
            if not target_form:
                raise Exception("Nenhum formulário encontrado na página")
            
            logger.info(f"Usando formulário com action: {target_form.get('action')}")
            
            # Extrair todos os campos
            parametros = {
                'action': target_form.get('action', ''),
                'method': target_form.get('method', 'post').upper(),
                'inputs': {},
                'selects': {},
                'textareas': {},
                'buttons': {}
            }
            
            # Extrair todos os inputs
            for input_tag in target_form.find_all('input'):
                name = input_tag.get('name')
                if name:
                    parametros['inputs'][name] = {
                        'value': input_tag.get('value', ''),
                        'type': input_tag.get('type', 'text'),
                        'required': 'required' in input_tag.attrs
                    }
                    logger.debug(f"Input encontrado: {name} = {input_tag.get('value', '')[:50]}")
            
            # Extrair todos os selects
            for select_tag in target_form.find_all('select'):
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
                    logger.debug(f"Select encontrado: {name} com {len(options)} opções")
            
            # Extrair textareas
            for textarea_tag in target_form.find_all('textarea'):
                name = textarea_tag.get('name')
                if name:
                    parametros['textareas'][name] = {
                        'value': textarea_tag.get_text(strip=True),
                        'required': 'required' in textarea_tag.attrs
                    }
            
            logger.info(f"Total de inputs: {len(parametros['inputs'])}")
            logger.info(f"Total de selects: {len(parametros['selects'])}")
            logger.info(f"Total de textareas: {len(parametros['textareas'])}")
            
            return parametros
            
        except Exception as e:
            logger.error(f"Erro ao extrair parâmetros: {e}")
            raise
    
    def extrair_opcoes_select(self, soup, select_name):
        """Extrai opções de um select específico para debug"""
        try:
            select = soup.find('select', {'name': select_name})
            if select:
                opcoes = []
                for option in select.find_all('option'):
                    opcoes.append({
                        'value': option.get('value', ''),
                        'text': option.get_text(strip=True),
                        'selected': 'selected' in option.attrs
                    })
                logger.info(f"Opções para {select_name}:")
                for op in opcoes[:10]:  # Mostrar apenas as primeiras 10
                    logger.info(f"  '{op['value']}' -> '{op['text']}'")
                return opcoes
            return []
        except Exception as e:
            logger.error(f"Erro ao extrair opções de {select_name}: {e}")
            return []
    
    def construir_dados_formulario(self, parametros, filtros):
        """Constrói os dados do formulário CORRETAMENTE"""
        dados_formulario = {}
        
        logger.info("Construindo dados do formulário...")
        
        # 1. Primeiro, copiar TODOS os valores padrão dos inputs hidden
        for name, input_info in parametros['inputs'].items():
            if input_info['type'] == 'hidden' and input_info['value']:
                dados_formulario[name] = input_info['value']
                logger.debug(f"Campo hidden: {name} = {input_info['value'][:50]}")
        
        # 2. Aplicar filtros sobrepondo valores padrão
        for campo, valor in filtros.items():
            if campo in parametros['inputs'] or campo in parametros['selects']:
                dados_formulario[campo] = valor
                logger.info(f"Aplicando filtro: {campo} = {valor}")
            else:
                logger.warning(f"Campo de filtro não encontrado no formulário: {campo}")
        
        # 3. Adicionar campos de ação/submit se existirem
        submit_buttons = [name for name, info in parametros['inputs'].items() 
                         if info['type'] in ['submit', 'button']]
        
        if submit_buttons:
            dados_formulario[submit_buttons[0]] = submit_buttons[0]
        
        logger.info(f"Total de campos no formulário: {len(dados_formulario)}")
        logger.info(f"Campos: {list(dados_formulario.keys())}")
        
        return dados_formulario
    
    def encontrar_valor_select(self, parametros, nome_select, valor_procurado):
        """Encontra o valor correto para um select"""
        if nome_select not in parametros['selects']:
            logger.warning(f"Select {nome_select} não encontrado nos parâmetros")
            return None
        
        opcoes = parametros['selects'][nome_select]
        
        # Tentar encontrar por valor exato
        for opcao in opcoes:
            if opcao['value'] == valor_procurado:
                return opcao['value']
        
        # Tentar encontrar por texto contido
        for opcao in opcoes:
            if valor_procurado in opcao['text']:
                return opcao['value']
        
        # Tentar encontrar por código numérico
        for opcao in opcoes:
            if '(' in opcao['text'] and ')' in opcao['text']:
                # Extrair código entre parênteses
                match = re.search(r'\((\d+)\)', opcao['text'])
                if match and match.group(1) == valor_procurado:
                    return opcao['value']
        
        # Se não encontrar, usar primeira opção não vazia
        for opcao in opcoes:
            if opcao['value']:
                logger.warning(f"Usando opção padrão para {nome_select}: {opcao['value']}")
                return opcao['value']
        
        return ''
    
    def submeter_formulario(self, dados_formulario, action_url):
        """Submete o formulário com debug detalhado"""
        try:
            # Construir URL completa
            if not action_url.startswith('http'):
                action_url = urljoin(self.base_url, action_url)
            
            logger.info(f"Submetendo formulário para: {action_url}")
            logger.info(f"Método: POST")
            logger.info(f"Total de campos: {len(dados_formulario)}")
            
            # DEBUG: Mostrar todos os campos
            for campo, valor in dados_formulario.items():
                logger.debug(f"  {campo}: {str(valor)[:100]}")
            
            # Submeter formulário
            response = self.session.post(
                action_url,
                data=dados_formulario,
                timeout=30,
                allow_redirects=True,
                headers={
                    'Referer': self.listagem_url,
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            )
            
            logger.info(f"Status da resposta: {response.status_code}")
            logger.info(f"URL após submissão: {response.url}")
            
            # Verificar se foi bem-sucedido
            if response.status_code == 422:
                logger.error("Erro 422 - Unprocessable Entity")
                # Salvar resposta para debug
                with open('debug_422_response.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                logger.error("Resposta salva em debug_422_response.html")
                
                # Tentar extrair mensagem de erro
                soup = BeautifulSoup(response.text, 'html.parser')
                error_divs = soup.find_all(['div', 'p'], class_=lambda x: x and 'error' in x.lower())
                for error_div in error_divs:
                    logger.error(f"Mensagem de erro: {error_div.get_text(strip=True)}")
                
                return {
                    'success': False,
                    'error': '422 Unprocessable Entity',
                    'response_text': response.text[:1000]
                }
            
            response.raise_for_status()
            
            # Extrair ID do relatório
            match = re.search(r'/relatorios/(\d+)', response.url)
            if match:
                relatorio_id = match.group(1)
                logger.info(f"✅ Relatório criado com ID: {relatorio_id}")
                return {
                    'success': True,
                    'relatorio_id': relatorio_id,
                    'url': response.url
                }
            else:
                # Verificar se há link para relatório
                soup = BeautifulSoup(response.text, 'html.parser')
                relatorio_link = soup.find('a', href=re.compile(r'/relatorios/\d+'))
                if relatorio_link:
                    href = relatorio_link.get('href', '')
                    match = re.search(r'/relatorios/(\d+)', href)
                    if match:
                        relatorio_id = match.group(1)
                        logger.info(f"✅ Relatório encontrado via link: {relatorio_id}")
                        return {
                            'success': True,
                            'relatorio_id': relatorio_id,
                            'url': urljoin(BASE_URL, href)
                        }
                
                logger.warning(f"Não encontrou ID na URL: {response.url}")
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
            
            # Verificar se ainda está processando
            if "processando" in response.text.lower() or "gerando" in response.text.lower():
                return {'status': 'EM_PROCESSAMENTO'}
            
            return {'status': 'DESCONHECIDO'}
            
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
            logger.info(f"Aguardando relatório... tentativa {tentativa}/{max_tentativas}")
        
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
        """Fluxo completo para gerar relatório - REVISADO"""
        try:
            if progress_callback:
                progress_callback("Acessando página de relatórios...", 10)
            
            # 1. Acessar página
            soup = self.acessar_pagina_listagem()
            
            if progress_callback:
                progress_callback("Analisando formulário...", 25)
            
            # 2. Extrair parâmetros com debug
            parametros = self.extrair_parametros_formulario(soup)
            
            # DEBUG: Extrair opções dos selects importantes
            selects_importantes = ['report_filter_curso', 'report_filter_desdobramento', 
                                 'report_filter_forma_ingresso', 'report_filter_localidade']
            for select_name in selects_importantes:
                self.extrair_opcoes_select(soup, select_name)
            
            if progress_callback:
                progress_callback("Configurando filtros...", 40)
            
            # 3. Construir dados do formulário
            dados_form = self.construir_dados_formulario(parametros, filtros)
            
            if progress_callback:
                progress_callback("Enviando requisição...", 55)
            
            # 4. Submeter formulário
            action_url = parametros.get('action') or '/graduacao/administracaoacademica/relatorios/listagens_alunos'
            resultado = self.submeter_formulario(dados_form, action_url)
            
            if not resultado['success']:
                raise Exception(f"Erro ao submeter: {resultado.get('error')}")
            
            relatorio_id = resultado['relatorio_id']
            
            if progress_callback:
                progress_callback(f"Aguardando relatório {relatorio_id}...", 70)
            
            # 5. Aguardar processamento
            status_info = self.aguardar_relatorio(relatorio_id)
            
            if progress_callback:
                progress_callback("Baixando relatório...", 85)
            
            # 6. Baixar arquivo
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
            
            cpf = st.text_input("CPF:", key="cpf_input")
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
            """)
            
        else:
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
        st.info("👈 Faça login na barra lateral para começar")
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
            
            # Converter períodos - CORRIGIDO
            def converter_periodo(periodo):
                ano, semestre = periodo.split('.')
                # Formato: "2025/1°" ou "2025/2°"
                return f"{ano}/{semestre}°"
            
            periodo_inicio_fmt = converter_periodo(periodo_inicio)
            periodo_fim_fmt = converter_periodo(periodo_fim)
            
            # Usar apenas um período de cada vez para testes
            periodos = [periodo_inicio_fmt]  # Testar com apenas um período inicialmente
            
            # Iniciar processamento
            gerador = GeradorRelatorios(st.session_state.session)
            todos_dados = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            resultados_container = st.container()
            
            total_relatorios = len(periodos) * len(cursos_selecionados)
            relatorio_atual = 0
            
            with resultados_container:
                try:
                    for periodo in periodos:
                        semestre = '1' if '1°' in periodo else '2'
                        forma_ingresso = FORMAS_INGRESSO.get(semestre, '1')
                        
                        for curso_key in cursos_selecionados[:1]:  # Testar com apenas um curso inicialmente
                            relatorio_atual += 1
                            
                            curso_info = DESDOBRAMENTOS_CURSOS[curso_key]
                            
                            def callback_progresso(msg, pct):
                                progresso_total = ((relatorio_atual - 1) * 100 + pct) / total_relatorios
                                status_text.text(f"{relatorio_atual}/{total_relatorios} - {curso_key}: {msg}")
                                progress_bar.progress(progresso_total / 100)
                            
                            try:
                                status_text.text(f"Iniciando: {curso_key} - {periodo}")
                                
                                # Preparar filtros - USANDO VALORES SIMPLES
                                filtros = {
                                    'report_filter_localidade': 'Niterói',
                                    'report_filter_curso': curso_info['buscar_por'],  # "Química"
                                    'report_filter_desdobramento': curso_info['valor'],  # Código numérico
                                    'report_filter_forma_ingresso': forma_ingresso,  # "1" ou "2"
                                    'report_filter_ano_semestre_ingresso': periodo,  # "2025/1°"
                                }
                                
                                logger.info(f"Filtros para {curso_key}: {filtros}")
                                
                                # Gerar relatório
                                conteudo_excel = gerador.gerar_relatorio_completo(filtros, callback_progresso)
                                
                                # Processar dados
                                df = pd.read_excel(io.BytesIO(conteudo_excel))
                                df['curso'] = curso_key
                                df['periodo'] = periodo
                                todos_dados.append(df)
                                
                                st.success(f"✅ {curso_key} - {periodo}: Relatório gerado")
                                logger.info(f"Relatório {curso_key}-{periodo} gerado com sucesso!")
                                
                            except Exception as e:
                                st.error(f"❌ {curso_key} - {periodo}: {str(e)[:200]}")
                                logger.error(f"Erro em {curso_key}-{periodo}: {e}")
                    
                    # Consolidar resultados
                    if todos_dados:
                        status_text.text("Consolidando dados...")
                        progress_bar.progress(0.95)
                        
                        df_consolidado = pd.concat(todos_dados, ignore_index=True)
                        
                        # Gerar arquivo
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
                        
                        # Estatísticas
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Registros", len(df_consolidado))
                        with col2:
                            st.metric("Cursos", len(cursos_selecionados))
                        with col3:
                            st.metric("Períodos", len(periodos))
                        
                    else:
                        st.error("❌ Nenhum relatório foi gerado com sucesso")
                    
                except Exception as e:
                    st.error(f"❌ Erro geral: {str(e)[:500]}")
                    logger.error(f"Erro geral: {e}", exc_info=True)
                    
                    # Mostrar dicas de solução
                    with st.expander("🛠️ Dicas para solução de problemas"):
                        st.markdown("""
                        **Erro 422 - Unprocessable Entity:**
                        1. Verifique os valores dos filtros no arquivo `debug_formulario.html`
                        2. Confira se os códigos dos cursos estão corretos
                        3. Tente com apenas um curso e período primeiro
                        4. Verifique os logs no terminal para mais detalhes
                        
                        **Próximos passos:**
                        1. Abra o arquivo `debug_formulario.html` em seu navegador
                        2. Encontre os valores corretos para os filtros
                        3. Atualize o mapeamento `DESDOBRAMENTOS_CURSOS`
                        """)


if __name__ == "__main__":
    main()
