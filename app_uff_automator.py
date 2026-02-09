"""
Automador de Relatórios - UFF Química
Versão: Com tratamento de selects dependentes e formato correto
"""

import streamlit as st
import requests
import time
import re
from bs4 import BeautifulSoup
import pandas as pd
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlencode
import io
import json

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
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

class LoginUFF:
    """Classe de login"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.is_authenticated = False
    
    def fazer_login(self, cpf: str, senha: str) -> bool:
        """Realiza login no sistema UFF"""
        try:
            st.info("Conectando ao portal UFF...")
            
            response = self.session.get(APLICACAO_URL, timeout=TIMEOUT_REQUESTS)
            
            if response.status_code != 200:
                return False
            
            soup = BeautifulSoup(response.text, 'html.parser')
            login_form = soup.find('form', {'id': 'kc-form-login'}) or soup.find('form', method='post')
            
            if not login_form:
                return False
            
            action_url = login_form.get('action', '')
            if action_url.startswith('/'):
                parsed_base = urlparse(BASE_URL)
                action_url = f"{parsed_base.scheme}://{parsed_base.netloc}{action_url}"
            
            form_data = {
                'username': cpf,
                'password': senha,
                'rememberMe': 'on'
            }
            
            for input_tag in login_form.find_all('input', type='hidden'):
                name = input_tag.get('name', '')
                value = input_tag.get('value', '')
                if name:
                    form_data[name] = value
            
            headers = {
                'User-Agent': HEADERS['User-Agent'],
                'Referer': response.url,
                'Origin': BASE_URL,
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            login_response = self.session.post(
                action_url,
                data=form_data,
                headers=headers,
                allow_redirects=True,
                timeout=TIMEOUT_REQUESTS
            )
            
            if 'administracaoacademica' in login_response.url and login_response.status_code == 200:
                self.is_authenticated = True
                st.success("✅ Login realizado com sucesso!")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Erro durante o login: {str(e)}")
            return False
    
    def get_session(self):
        """Retorna a sessão autenticada"""
        return self.session if self.is_authenticated else None


class SistemaRelatorios:
    """Classe principal para lidar com o sistema de relatórios"""
    
    def __init__(self, session):
        self.session = session
        self.url_listagem = f"{APLICACAO_URL}/relatorios/listagens_alunos"
        self.token = None
        self.dados_formulario = {}
    
    def carregar_pagina_inicial(self):
        """Carrega a página inicial e extrai o token"""
        try:
            response = self.session.get(self.url_listagem, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extrair token CSRF
            token_input = soup.find('input', {'name': 'authenticity_token'})
            if token_input:
                self.token = token_input.get('value', '')
                logger.info(f"Token obtido: {self.token[:20]}...")
            
            # Extrair todos os dados do formulário
            self.extrair_dados_formulario(soup)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao carregar página: {e}")
            return False
    
    def extrair_dados_formulario(self, soup):
        """Extrai todos os dados do formulário"""
        form = soup.find('form')
        if not form:
            return
        
        # Extrair todos os campos
        self.dados_formulario = {
            'token': self.token,
            'action': form.get('action', ''),
            'method': form.get('method', 'post').upper(),
            'campos': {}
        }
        
        # Extrair inputs
        for input_tag in form.find_all('input'):
            name = input_tag.get('name')
            if name:
                self.dados_formulario['campos'][name] = {
                    'tipo': input_tag.get('type', 'text'),
                    'valor': input_tag.get('value', ''),
                    'id': input_tag.get('id', '')
                }
        
        # Extrair selects
        for select_tag in form.find_all('select'):
            name = select_tag.get('name')
            if name:
                opcoes = []
                for option in select_tag.find_all('option'):
                    opcoes.append({
                        'valor': option.get('value', ''),
                        'texto': option.get_text(strip=True),
                        'selecionado': 'selected' in option.attrs
                    })
                
                self.dados_formulario['campos'][name] = {
                    'tipo': 'select',
                    'opcoes': opcoes,
                    'id': select_tag.get('id', '')
                }
    
    def obter_cursos_para_localidade(self, id_localidade):
        """Obtém cursos disponíveis para uma localidade específica"""
        try:
            if not self.token:
                self.carregar_pagina_inicial()
            
            # Primeiro, enviar a seleção de localidade
            dados = {
                'authenticity_token': self.token,
                'idlocalidade': id_localidade,
                'utf8': '✓'
            }
            
            # Verificar se há outros campos hidden que precisam ser enviados
            for campo_nome, campo_info in self.dados_formulario['campos'].items():
                if campo_info['tipo'] == 'hidden' and campo_info['valor']:
                    dados[campo_nome] = campo_info['valor']
            
            logger.info(f"Enviando seleção de localidade {id_localidade}...")
            
            response = self.session.post(
                self.url_listagem,
                data=dados,
                timeout=15,
                headers={
                    'Referer': self.url_listagem,
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'  # Importante para AJAX
                }
            )
            
            # Analisar resposta
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procurar select de cursos
            select_curso = soup.find('select', {'id': 'idcurso', 'name': 'idcurso'})
            
            cursos = {}
            if select_curso:
                for option in select_curso.find_all('option'):
                    valor = option.get('value', '').strip()
                    texto = option.get_text(strip=True)
                    if valor:  # Ignorar opções vazias
                        cursos[valor] = texto
            
            logger.info(f"Encontrados {len(cursos)} cursos para localidade {id_localidade}")
            
            # Atualizar dados do formulário
            if 'idcurso' in self.dados_formulario['campos']:
                self.dados_formulario['campos']['idcurso']['opcoes'] = [
                    {'valor': k, 'texto': v, 'selecionado': False} 
                    for k, v in cursos.items()
                ]
            
            return cursos
            
        except Exception as e:
            logger.error(f"Erro ao obter cursos: {e}")
            return {}
    
    def obter_desdobramentos_para_curso(self, id_localidade, id_curso):
        """Obtém desdobramentos disponíveis para um curso específico"""
        try:
            if not self.token:
                self.carregar_pagina_inicial()
            
            # Enviar seleção de curso
            dados = {
                'authenticity_token': self.token,
                'idlocalidade': id_localidade,
                'idcurso': id_curso,
                'utf8': '✓'
            }
            
            # Adicionar campos hidden
            for campo_nome, campo_info in self.dados_formulario['campos'].items():
                if campo_info['tipo'] == 'hidden' and campo_info['valor']:
                    dados[campo_nome] = campo_info['valor']
            
            logger.info(f"Enviando seleção de curso {id_curso}...")
            
            response = self.session.post(
                self.url_listagem,
                data=dados,
                timeout=15,
                headers={
                    'Referer': self.url_listagem,
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            )
            
            # Analisar resposta
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procurar select de desdobramentos
            select_desdobramento = soup.find('select', {'id': 'iddesdobramento', 'name': 'iddesdobramento'})
            
            desdobramentos = {}
            if select_desdobramento:
                for option in select_desdobramento.find_all('option'):
                    valor = option.get('value', '').strip()
                    texto = option.get_text(strip=True)
                    if valor:  # Ignorar opções vazias
                        desdobramentos[valor] = texto
            
            logger.info(f"Encontrados {len(desdobramentos)} desdobramentos para curso {id_curso}")
            
            # Atualizar dados do formulário
            if 'iddesdobramento' in self.dados_formulario['campos']:
                self.dados_formulario['campos']['iddesdobramento']['opcoes'] = [
                    {'valor': k, 'texto': v, 'selecionado': False} 
                    for k, v in desdobramentos.items()
                ]
            
            return desdobramentos
            
        except Exception as e:
            logger.error(f"Erro ao obter desdobramentos: {e}")
            return {}
    
    def gerar_relatorio_excel(self, filtros):
        """Gera relatório em formato Excel (XLSX)"""
        try:
            if not self.token:
                self.carregar_pagina_inicial()
            
            # Preparar dados para envio
            dados = {
                'authenticity_token': self.token,
                'utf8': '✓',
                'format': 'xlsx'  # IMPORTANTE: Especificar formato Excel
            }
            
            # Adicionar filtros
            for campo, valor in filtros.items():
                dados[campo] = valor
            
            logger.info(f"Gerando relatório Excel com {len(dados)} campos")
            logger.info(f"Campos: {list(dados.keys())}")
            
            # Enviar requisição
            response = self.session.post(
                self.url_listagem,
                data=dados,
                timeout=30,
                allow_redirects=True,
                headers={
                    'Referer': self.url_listagem,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )
            
            logger.info(f"Status: {response.status_code}")
            logger.info(f"URL após envio: {response.url}")
            
            # Verificar se foi redirecionado para página de relatório
            if '/relatorios/' in response.url and response.status_code == 200:
                # Extrair ID do relatório
                match = re.search(r'/relatorios/(\d+)', response.url)
                if match:
                    relatorio_id = match.group(1)
                    logger.info(f"✅ Relatório criado! ID: {relatorio_id}")
                    return self.baixar_relatorio(relatorio_id)
            
            # Se não redirecionou, verificar se o arquivo foi retornado diretamente
            content_type = response.headers.get('content-type', '').lower()
            if 'excel' in content_type or 'xlsx' in content_type or 'spreadsheet' in content_type:
                logger.info("✅ Arquivo Excel retornado diretamente")
                return response.content
            
            # Se chegou aqui, algo deu errado
            raise Exception("Não foi possível gerar o relatório")
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório Excel: {e}")
            raise
    
    def baixar_relatorio(self, relatorio_id):
        """Aguarda e baixa o relatório"""
        try:
            logger.info(f"Aguardando relatório {relatorio_id}...")
            
            url_status = f"{BASE_URL}/relatorios/{relatorio_id}"
            
            # Tentar por 2 minutos
            for tentativa in range(40):
                response = self.session.get(url_status, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Procurar link de download Excel
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if '.xlsx' in href.lower():
                        download_url = urljoin(BASE_URL, href)
                        logger.info(f"✅ Baixando de: {download_url}")
                        
                        file_response = self.session.get(download_url, timeout=30)
                        file_response.raise_for_status()
                        
                        logger.info(f"✅ Download completo! {len(file_response.content)} bytes")
                        return file_response.content
                
                time.sleep(3)
            
            raise Exception("Timeout aguardando relatório")
            
        except Exception as e:
            logger.error(f"Erro ao baixar relatório: {e}")
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
        st.session_state.sistema = None
        st.session_state.localidade_selecionada = None
        st.session_state.cursos_disponiveis = {}
        st.session_state.desdobramentos_disponiveis = {}
        st.session_state.valores_selecionados = {
            'idlocalidade': '1',  # Niterói por padrão
            'idformaingresso': '1',  # SISU 1ª edição (valor hipotético)
            'anosem_ingresso': '20251',  # 2025/1º
            'idturno': '0'  # Todos
        }
    
    # Sidebar de login
    with st.sidebar:
        st.header("🔐 Login")
        
        if st.session_state.session is None:
            cpf = st.text_input("CPF:")
            senha = st.text_input("Senha:", type="password")
            
            if st.button("Entrar", use_container_width=True, type="primary"):
                if cpf and senha:
                    with st.spinner("Autenticando..."):
                        auth = LoginUFF()
                        if auth.fazer_login(cpf, senha):
                            st.session_state.auth = auth
                            st.session_state.session = auth.get_session()
                            
                            # Inicializar sistema
                            sistema = SistemaRelatorios(st.session_state.session)
                            if sistema.carregar_pagina_inicial():
                                st.session_state.sistema = sistema
                                st.rerun()
                        else:
                            st.error("Falha na autenticação")
                else:
                    st.warning("Preencha CPF e senha")
        else:
            st.success("✅ Conectado")
            if st.button("Sair", use_container_width=True):
                st.session_state.session = None
                st.session_state.auth = None
                st.session_state.sistema = None
                st.session_state.localidade_selecionada = None
                st.session_state.cursos_disponiveis = {}
                st.session_state.desdobramentos_disponiveis = {}
                st.session_state.valores_selecionados = {
                    'idlocalidade': '1',
                    'idformaingresso': '1',
                    'anosem_ingresso': '20251',
                    'idturno': '0'
                }
                st.rerun()
    
    # Conteúdo principal
    if st.session_state.session is None:
        st.info("👈 Faça login para começar")
    else:
        st.header("📊 Configuração do Relatório")
        
        if not st.session_state.sistema:
            st.error("❌ Erro ao inicializar sistema de relatórios")
            return
        
        sistema = st.session_state.sistema
        
        # Seção 1: Seleção de Localidade
        st.subheader("1. 📍 Localidade")
        
        # Obter opções de localidade
        localidades = {}
        if 'idlocalidade' in sistema.dados_formulario.get('campos', {}):
            campo_localidade = sistema.dados_formulario['campos']['idlocalidade']
            if campo_localidade['tipo'] == 'select':
                for opcao in campo_localidade['opcoes']:
                    if opcao['valor']:
                        localidades[opcao['valor']] = opcao['texto']
        
        if localidades:
            # Selecionar localidade
            localidade_selecionada = st.selectbox(
                "Selecione a localidade:",
                options=list(localidades.keys()),
                format_func=lambda x: localidades.get(x, x),
                index=list(localidades.keys()).index('1') if '1' in localidades else 0,
                key="select_localidade"
            )
            
            st.session_state.valores_selecionados['idlocalidade'] = localidade_selecionada
            
            # Botão para carregar cursos desta localidade
            if st.button("🔄 Carregar Cursos desta Localidade", key="btn_carregar_cursos"):
                with st.spinner("Carregando cursos..."):
                    cursos = sistema.obter_cursos_para_localidade(localidade_selecionada)
                    if cursos:
                        st.session_state.cursos_disponiveis = cursos
                        st.session_state.localidade_selecionada = localidade_selecionada
                        st.success(f"✅ {len(cursos)} cursos carregados!")
                    else:
                        st.error("❌ Não foi possível carregar os cursos")
        else:
            st.warning("Não foi possível carregar as localidades")
        
        st.markdown("---")
        
        # Seção 2: Seleção de Curso (se temos cursos carregados)
        if st.session_state.cursos_disponiveis:
            st.subheader("2. 🎓 Curso")
            
            # Filtrar cursos de Química
            cursos_quimica = {
                codigo: nome for codigo, nome in st.session_state.cursos_disponiveis.items()
                if 'química' in nome.lower() or 'quimica' in nome.lower()
            }
            
            if cursos_quimica:
                # Selecionar curso
                curso_selecionado = st.selectbox(
                    "Selecione o curso de Química:",
                    options=list(cursos_quimica.keys()),
                    format_func=lambda x: cursos_quimica.get(x, x),
                    key="select_curso"
                )
                
                st.session_state.valores_selecionados['idcurso'] = curso_selecionado
                
                # Botão para carregar desdobramentos deste curso
                if st.button("🔄 Carregar Desdobramentos deste Curso", key="btn_carregar_desdobramentos"):
                    with st.spinner("Carregando desdobramentos..."):
                        desdobramentos = sistema.obter_desdobramentos_para_curso(
                            st.session_state.localidade_selecionada or '1',
                            curso_selecionado
                        )
                        
                        if desdobramentos:
                            st.session_state.desdobramentos_disponiveis = desdobramentos
                            st.success(f"✅ {len(desdobramentos)} desdobramentos carregados!")
                        else:
                            st.warning("⚠️ Nenhum desdobramento encontrado ou o curso não tem desdobramentos")
            
            else:
                st.warning("Nenhum curso de Química encontrado na lista")
                
                # Mostrar todos os cursos disponíveis para debug
                with st.expander("📋 Todos os cursos disponíveis"):
                    for codigo, nome in list(st.session_state.cursos_disponiveis.items())[:20]:
                        st.write(f"`{codigo}`: {nome}")
        
        st.markdown("---")
        
        # Seção 3: Seleção de Desdobramento (se temos desdobramentos)
        if st.session_state.desdobramentos_disponiveis:
            st.subheader("3. 📚 Desdobramento")
            
            desdobramento_selecionado = st.selectbox(
                "Selecione o desdobramento:",
                options=list(st.session_state.desdobramentos_disponiveis.keys()),
                format_func=lambda x: st.session_state.desdobramentos_disponiveis.get(x, x),
                key="select_desdobramento"
            )
            
            st.session_state.valores_selecionados['iddesdobramento'] = desdobramento_selecionado
        
        st.markdown("---")
        
        # Seção 4: Outros Filtros
        st.subheader("4. ⚙️ Outros Filtros")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Forma de Ingresso
            formas_ingresso = {}
            if 'idformaingresso' in sistema.dados_formulario.get('campos', {}):
                campo_forma = sistema.dados_formulario['campos']['idformaingresso']
                if campo_forma['tipo'] == 'select':
                    for opcao in campo_forma['opcoes']:
                        if opcao['valor']:
                            formas_ingresso[opcao['valor']] = opcao['texto']
            
            if formas_ingresso:
                # Filtrar apenas formas de ingresso relacionadas a SISU/Vestibular
                formas_filtradas = {
                    k: v for k, v in formas_ingresso.items()
                    if any(termo in v.lower() for termo in ['sisu', 'vestibular', 'enem', 'seleção'])
                }
                
                if formas_filtradas:
                    forma_selecionada = st.selectbox(
                        "Forma de Ingresso:",
                        options=list(formas_filtradas.keys()),
                        format_func=lambda x: formas_filtradas.get(x, x),
                        key="select_forma_ingresso"
                    )
                    st.session_state.valores_selecionados['idformaingresso'] = forma_selecionada
        
        with col2:
            # Período de Ingresso
            periodos = {}
            if 'anosem_ingresso' in sistema.dados_formulario.get('campos', {}):
                campo_periodo = sistema.dados_formulario['campos']['anosem_ingresso']
                if campo_periodo['tipo'] == 'select':
                    for opcao in campo_periodo['opcoes']:
                        if opcao['valor']:
                            periodos[opcao['valor']] = opcao['texto']
            
            if periodos:
                periodo_selecionado = st.selectbox(
                    "Período de Ingresso:",
                    options=list(periodos.keys()),
                    format_func=lambda x: periodos.get(x, x),
                    index=0,
                    key="select_periodo"
                )
                st.session_state.valores_selecionados['anosem_ingresso'] = periodo_selecionado
        
        st.markdown("---")
        
        # Seção 5: Resumo e Geração
        st.subheader("5. 🚀 Gerar Relatório")
        
        # Mostrar valores selecionados
        with st.expander("📝 Valores Selecionados", expanded=True):
            for campo, valor in st.session_state.valores_selecionados.items():
                if valor:
                    # Buscar nome amigável se disponível
                    nome_amigavel = valor
                    if campo == 'idlocalidade' and localidades:
                        nome_amigavel = localidades.get(valor, valor)
                    elif campo == 'idcurso' and st.session_state.cursos_disponiveis:
                        nome_amigavel = st.session_state.cursos_disponiveis.get(valor, valor)
                    elif campo == 'iddesdobramento' and st.session_state.desdobramentos_disponiveis:
                        nome_amigavel = st.session_state.desdobramentos_disponiveis.get(valor, valor)
                    elif campo == 'idformaingresso' and formas_ingresso:
                        nome_amigavel = formas_ingresso.get(valor, valor)
                    elif campo == 'anosem_ingresso' and periodos:
                        nome_amigavel = periodos.get(valor, valor)
                    
                    st.write(f"**{campo}**: {nome_amigavel}")
        
        # Verificar campos obrigatórios
        campos_obrigatorios = ['idlocalidade', 'idcurso', 'iddesdobramento', 'anosem_ingresso']
        campos_preenchidos = [
            c for c in campos_obrigatorios 
            if st.session_state.valores_selecionados.get(c) and 
            st.session_state.valores_selecionados[c] not in ['', '0']
        ]
        
        status_campos = f"✅ {len(campos_preenchidos)}/{len(campos_obrigatorios)} campos obrigatórios"
        
        if len(campos_preenchidos) == len(campos_obrigatorios):
            st.success(status_campos)
            
            # Botão para gerar relatório
            if st.button("🚀 GERAR RELATÓRIO EXCEL", type="primary", use_container_width=True):
                with st.spinner("Gerando relatório Excel..."):
                    try:
                        # Adicionar campo 'format' para especificar Excel
                        filtros_completos = st.session_state.valores_selecionados.copy()
                        filtros_completos['format'] = 'xlsx'
                        
                        # Gerar relatório
                        conteudo_excel = sistema.gerar_relatorio_excel(filtros_completos)
                        
                        # Criar botão de download
                        st.success("✅ Relatório gerado com sucesso!")
                        
                        output = io.BytesIO()
                        output.write(conteudo_excel)
                        output.seek(0)
                        
                        st.download_button(
                            label="📥 BAIXAR RELATÓRIO EXCEL",
                            data=output.getvalue(),
                            file_name=f"relatorio_uff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar relatório: {str(e)}")
                        
                        # Sugestões de solução
                        with st.expander("🛠️ Solução de Problemas"):
                            st.markdown("""
                            **Possíveis causas:**
                            1. **Valores incorretos** - Verifique se os códigos dos cursos estão corretos
                            2. **Campo obrigatório faltando** - Pode haver outros campos obrigatórios
                            3. **Token expirado** - Tente recarregar a página
                            
                            **Soluções:**
                            1. **Teste manualmente** no sistema web para ver os valores corretos
                            2. **Verifique os logs** no terminal para mais detalhes
                            3. **Tente diferentes combinações** de valores
                            """)
        else:
            st.warning(f"{status_campos}")
            st.info("""
            **Para gerar o relatório, você precisa:**
            
            1. **Selecionar uma localidade** e clicar em "Carregar Cursos"
            2. **Selecionar um curso de Química** e clicar em "Carregar Desdobramentos"
            3. **Selecionar um desdobramento**
            4. **Selecionar período de ingresso**
            
            **Dica:** Comece selecionando Niterói (código 1) para ver os cursos disponíveis.
            """)
        
        st.markdown("---")
        st.info("""
        **📋 Fluxo de trabalho recomendado:**
        
        1. **Localidade** → Selecione "Niterói (1)" e clique em "Carregar Cursos"
        2. **Curso** → Selecione um curso de Química e clique em "Carregar Desdobramentos"
        3. **Desdobramento** → Selecione a especialização (Licenciatura/Bacharelado/Industrial)
        4. **Forma de Ingresso** → Selecione SISU ou outra forma
        5. **Período** → Selecione o período desejado
        6. **Clique em GERAR RELATÓRIO EXCEL**
        
        **🔍 Se não encontrar cursos de Química:**
        - Verifique se selecionou a localidade correta
        - Tente outras localidades onde Química é oferecida
        - Os cursos podem ter nomes diferentes (ex: "Química Industrial")
        """)
        
        # Debug: Mostrar estado atual
        with st.expander("🔧 Debug - Estado Atual", expanded=False):
            st.write("**Cursos carregados:**", len(st.session_state.cursos_disponiveis))
            st.write("**Desdobramentos carregados:**", len(st.session_state.desdobramentos_disponiveis))
            st.write("**Token:**", sistema.token[:20] + "..." if sistema.token else "Não disponível")


if __name__ == "__main__":
    main()
