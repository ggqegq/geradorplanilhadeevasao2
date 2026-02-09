"""
Automador de Relatórios - UFF Química
Versão: Abordagem direta com simulação de navegador
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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações
BASE_URL = "https://app.uff.br"
APLICACAO_URL = "https://app.uff.br/graduacao/administracaoacademica"
TIMEOUT_REQUESTS = 30

# Headers completos para simular navegador
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

class LoginUFF:
    """Classe de login simplificada"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.is_authenticated = False
    
    def fazer_login(self, cpf: str, senha: str) -> bool:
        """Realiza login no sistema UFF"""
        try:
            st.info("Conectando ao portal UFF...")
            
            # Acessar página inicial
            response = self.session.get(APLICACAO_URL, timeout=TIMEOUT_REQUESTS)
            
            if response.status_code != 200:
                logger.error(f"Erro ao acessar página: {response.status_code}")
                return False
            
            # Encontrar formulário de login
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procurar formulário de várias formas
            login_form = None
            for form in soup.find_all('form'):
                form_action = form.get('action', '').lower()
                form_id = form.get('id', '').lower()
                form_method = form.get('method', '').lower()
                
                if 'kc-form-login' in form_id or '/auth/' in form_action or form_method == 'post':
                    login_form = form
                    break
            
            if not login_form:
                logger.error("Formulário de login não encontrado")
                return False
            
            # Extrair action URL
            action_url = login_form.get('action', '')
            if action_url.startswith('/'):
                parsed_base = urlparse(BASE_URL)
                action_url = f"{parsed_base.scheme}://{parsed_base.netloc}{action_url}"
            elif not action_url.startswith('http'):
                action_url = urljoin(BASE_URL, action_url)
            
            # Preparar dados do formulário
            form_data = {
                'username': cpf,
                'password': senha,
                'rememberMe': 'on'
            }
            
            # Adicionar campos hidden
            for input_tag in login_form.find_all('input', type='hidden'):
                name = input_tag.get('name', '')
                value = input_tag.get('value', '')
                if name:
                    form_data[name] = value
            
            # Headers para o POST
            post_headers = {
                'User-Agent': HEADERS['User-Agent'],
                'Referer': response.url,
                'Origin': BASE_URL,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
            
            # Enviar login
            login_response = self.session.post(
                action_url,
                data=form_data,
                headers=post_headers,
                allow_redirects=True,
                timeout=TIMEOUT_REQUESTS
            )
            
            # Verificar sucesso
            if 'administracaoacademica' in login_response.url and login_response.status_code == 200:
                self.is_authenticated = True
                st.success("✅ Login realizado com sucesso!")
                return True
            else:
                logger.error(f"Login falhou. URL final: {login_response.url}")
                return False
                
        except Exception as e:
            logger.error(f"Erro durante o login: {str(e)}")
            st.error(f"Erro: {str(e)[:100]}")
            return False
    
    def get_session(self):
        """Retorna a sessão autenticada"""
        return self.session if self.is_authenticated else None


class GeradorRelatoriosManual:
    """Gera relatórios usando valores manuais"""
    
    def __init__(self, session):
        self.session = session
        self.url_relatorios = f"{APLICACAO_URL}/relatorios/listagens_alunos"
    
    def testar_conexao(self):
        """Testa se consegue acessar a página de relatórios"""
        try:
            response = self.session.get(self.url_relatorios, timeout=15)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao testar conexão: {e}")
            return False
    
    def extrair_campos_formulario(self):
        """Extrai todos os campos do formulário manualmente"""
        try:
            response = self.session.get(self.url_relatorios, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Encontrar formulário principal
            form = soup.find('form')
            if not form:
                # Tentar encontrar por ação
                forms = soup.find_all('form')
                for f in forms:
                    if f.get('action') and 'listagens_alunos' in f.get('action'):
                        form = f
                        break
            
            if not form and len(forms) > 0:
                form = forms[0]
            
            if not form:
                return None
            
            # Extrair token
            token = None
            token_input = form.find('input', {'name': 'authenticity_token'})
            if token_input:
                token = token_input.get('value', '')
            
            # Extrair selects
            selects = {}
            for select in form.find_all('select'):
                name = select.get('name')
                if name:
                    options = []
                    for option in select.find_all('option'):
                        options.append({
                            'value': option.get('value', ''),
                            'text': option.get_text(strip=True),
                            'selected': 'selected' in option.attrs
                        })
                    selects[name] = options
            
            # Extrair inputs importantes
            inputs = {}
            for input_tag in form.find_all('input'):
                name = input_tag.get('name')
                if name:
                    inputs[name] = {
                        'type': input_tag.get('type', 'text'),
                        'value': input_tag.get('value', ''),
                        'id': input_tag.get('id', '')
                    }
            
            return {
                'token': token,
                'action': form.get('action', ''),
                'method': form.get('method', 'post'),
                'selects': selects,
                'inputs': inputs
            }
            
        except Exception as e:
            logger.error(f"Erro ao extrair campos: {e}")
            return None
    
    def gerar_relatorio_simples(self, id_localidade='1', id_curso='', id_desdobramento='', 
                                id_forma_ingresso='1', ano_semestre='20251'):
        """Gera um relatório simples com valores mínimos"""
        try:
            # Primeiro, obter token e dados do formulário
            dados_form = self.extrair_campos_formulario()
            if not dados_form or not dados_form['token']:
                raise Exception("Não foi possível obter token do formulário")
            
            # Preparar dados para envio
            dados_envio = {
                'authenticity_token': dados_form['token'],
                'utf8': '✓',
                'format': 'xlsx',  # Formato Excel
                'idlocalidade': id_localidade,
                'anosem_ingresso': ano_semestre,
                'idturno': '0',  # Todos os turnos
                'idstatusaluno': '0',  # Todos alunos ativos
                'idsituacaoaluno': '0',  # Todas situações
                'idacaoafirmativa': '0',  # Todas ações afirmativas
            }
            
            # Adicionar curso se fornecido
            if id_curso:
                dados_envio['idcurso'] = id_curso
            
            # Adicionar desdobramento se fornecido
            if id_desdobramento:
                dados_envio['iddesdobramento'] = id_desdobramento
            
            # Adicionar forma de ingresso
            if id_forma_ingresso:
                dados_envio['idformaingresso'] = id_forma_ingresso
            
            logger.info(f"Enviando relatório com {len(dados_envio)} campos")
            
            # Construir URL completa
            action_url = dados_form['action']
            if not action_url.startswith('http'):
                action_url = urljoin(APLICACAO_URL, action_url)
            
            # Enviar requisição
            response = self.session.post(
                action_url,
                data=dados_envio,
                timeout=30,
                allow_redirects=True,
                headers={
                    'Referer': self.url_relatorios,
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            )
            
            logger.info(f"Status: {response.status_code}")
            logger.info(f"URL após envio: {response.url}")
            
            # Verificar resultado
            if response.status_code != 200:
                logger.error(f"Erro HTTP {response.status_code}")
                
                # Salvar resposta para análise
                with open('erro_detalhado.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                # Tentar extrair mensagem de erro
                soup_erro = BeautifulSoup(response.text, 'html.parser')
                erros = soup_erro.find_all(['div', 'p'], class_=lambda x: x and 'error' in str(x).lower())
                for erro in erros:
                    logger.error(f"Erro: {erro.get_text(strip=True)}")
                
                raise Exception(f"Erro {response.status_code} ao gerar relatório")
            
            # Verificar se foi bem-sucedido
            # Opção 1: Foi redirecionado para página de relatório
            if '/relatorios/' in response.url and 'listagens_alunos' not in response.url:
                match = re.search(r'/relatorios/(\d+)', response.url)
                if match:
                    relatorio_id = match.group(1)
                    logger.info(f"Relatório criado com ID: {relatorio_id}")
                    return self.baixar_relatorio(relatorio_id)
            
            # Opção 2: O arquivo foi retornado diretamente
            content_type = response.headers.get('content-type', '').lower()
            if any(x in content_type for x in ['excel', 'xlsx', 'spreadsheet', 'octet-stream']):
                logger.info("Arquivo Excel retornado diretamente")
                return response.content
            
            # Opção 3: Verificar se há link para download na página
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if '.xlsx' in href.lower():
                    download_url = urljoin(BASE_URL, href)
                    logger.info(f"Encontrado link Excel: {download_url}")
                    
                    file_response = self.session.get(download_url, timeout=30)
                    file_response.raise_for_status()
                    return file_response.content
            
            # Se chegou aqui, não encontrou o relatório
            raise Exception("Não foi possível encontrar o relatório gerado")
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            raise
    
    def baixar_relatorio(self, relatorio_id):
        """Baixa um relatório pelo ID"""
        try:
            logger.info(f"Aguardando relatório {relatorio_id}...")
            
            url_relatorio = f"{BASE_URL}/relatorios/{relatorio_id}"
            
            # Tentar por 2 minutos
            for tentativa in range(40):
                response = self.session.get(url_relatorio, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Procurar links de download
                download_links = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if any(ext in href.lower() for ext in ['.xlsx', '.xls', '.csv']):
                        download_links.append(href)
                
                if download_links:
                    # Usar primeiro link Excel encontrado
                    for href in download_links:
                        if '.xlsx' in href.lower():
                            download_url = urljoin(BASE_URL, href)
                            logger.info(f"Baixando de: {download_url}")
                            
                            file_response = self.session.get(download_url, timeout=30)
                            file_response.raise_for_status()
                            
                            logger.info(f"Download completo: {len(file_response.content)} bytes")
                            return file_response.content
                
                # Verificar se há mensagem de "pronto" ou "disponível"
                texto = response.text.lower()
                if 'pronto' in texto or 'dispon' in texto:
                    # Talvez o link não esteja explícito, tentar padrões comuns
                    # Alguns sistemas usam: /relatorios/{id}/download ou /relatorios/{id}/file
                    for pattern in [f'/relatorios/{relatorio_id}/download', 
                                   f'/relatorios/{relatorio_id}/file',
                                   f'/relatorios/{relatorio_id}/export']:
                        download_url = urljoin(BASE_URL, pattern)
                        try:
                            file_response = self.session.get(download_url, timeout=10)
                            if file_response.status_code == 200:
                                return file_response.content
                        except:
                            pass
                
                time.sleep(3)
            
            raise Exception(f"Timeout aguardando relatório {relatorio_id}")
            
        except Exception as e:
            logger.error(f"Erro ao baixar relatório: {e}")
            raise


def main():
    """Aplicação principal - Versão simplificada"""
    st.set_page_config(
        page_title="Automador de Relatórios UFF",
        layout="wide"
    )
    
    st.title("🎓 Gerador de Relatórios UFF - Química")
    st.markdown("---")
    
    # Inicializar estado
    if 'session' not in st.session_state:
        st.session_state.session = None
        st.session_state.auth = None
    
    # Sidebar de login
    with st.sidebar:
        st.header("🔐 Login")
        
        if st.session_state.session is None:
            cpf = st.text_input("CPF (apenas números):")
            senha = st.text_input("Senha:", type="password")
            
            if st.button("Entrar", use_container_width=True, type="primary"):
                if cpf and senha:
                    with st.spinner("Autenticando..."):
                        auth = LoginUFF()
                        if auth.fazer_login(cpf, senha):
                            st.session_state.auth = auth
                            st.session_state.session = auth.get_session()
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
                st.rerun()
    
    # Conteúdo principal
    if st.session_state.session is None:
        st.info("👈 Faça login para começar")
    else:
        # Testar conexão
        gerador = GeradorRelatoriosManual(st.session_state.session)
        
        if st.button("🔍 Testar Conexão com Sistema de Relatórios"):
            with st.spinner("Testando conexão..."):
                if gerador.testar_conexao():
                    st.success("✅ Conexão estabelecida com sucesso!")
                    
                    # Extrair informações do formulário
                    dados = gerador.extrair_campos_formulario()
                    if dados:
                        st.info(f"✅ Formulário analisado: {len(dados.get('selects', {}))} selects encontrados")
                        
                        # Mostrar selects disponíveis
                        with st.expander("📋 Campos disponíveis no formulário"):
                            for nome_select, opcoes in dados['selects'].items():
                                st.write(f"**{nome_select}** ({len(opcoes)} opções):")
                                for opcao in opcoes[:5]:  # Mostrar apenas 5 primeiras
                                    if opcao['value']:
                                        st.write(f"  `{opcao['value']}` → {opcao['text']}")
                                if len(opcoes) > 5:
                                    st.write(f"  ... e mais {len(opcoes) - 5} opções")
                else:
                    st.error("❌ Não foi possível conectar ao sistema de relatórios")
        
        st.markdown("---")
        st.header("⚙️ Configuração do Relatório")
        
        # Configurações básicas
        st.subheader("Configurações Básicas")
        
        col1, col2 = st.columns(2)
        
        with col1:
            localidade = st.selectbox(
                "Localidade:",
                options=[
                    ('1', 'Niterói'),
                    ('6', 'Angra dos Reis'),
                    ('13', 'Arraial do Cabo'),
                    ('10', 'Bom Jesus do Itabapoana'),
                    ('11', 'Cabo Frio')
                ],
                format_func=lambda x: x[1],
                index=0
            )
            id_localidade = localidade[0]
        
        with col2:
            periodo = st.selectbox(
                "Período de Ingresso:",
                options=[
                    ('20261', '2026 / 1º'),
                    ('20252', '2025 / 2º'),
                    ('20251', '2025 / 1º'),
                    ('20242', '2024 / 2º'),
                    ('20241', '2024 / 1º')
                ],
                format_func=lambda x: x[1],
                index=0
            )
            id_periodo = periodo[0]
        
        # Campos para curso e desdobramento (manuais)
        st.subheader("Identificação do Curso")
        st.info("💡 **Importante:** Você precisa obter estes valores manualmente")
        
        col1, col2 = st.columns(2)
        
        with col1:
            id_curso = st.text_input(
                "Código do Curso (idcurso):",
                placeholder="Ex: 12700, 312700, 12709",
                help="Acesse o sistema manualmente e inspecione o select 'idcurso' para obter este valor"
            )
        
        with col2:
            id_desdobramento = st.text_input(
                "Código do Desdobramento (iddesdobramento):",
                placeholder="Ex: 12700, 312700, 12709",
                help="Após selecionar o curso, inspecione o select 'iddesdobramento' para obter este valor"
            )
        
        # Forma de ingresso
        forma_ingresso = st.selectbox(
            "Forma de Ingresso:",
            options=[
                ('1', 'SISU 1ª Edição (valor hipotético)'),
                ('2', 'SISU 2ª Edição (valor hipotético)'),
                ('13', 'Convenio Cultural/PEC-G'),
                ('0', 'Todas as formas'),
                ('212', 'Curso à Distância - REVINCULAÇÃO')
            ],
            format_func=lambda x: x[1],
            index=0
        )
        id_forma_ingresso = forma_ingresso[0]
        
        st.markdown("---")
        st.subheader("🚀 Gerar Relatório")
        
        # Mostrar configurações atuais
        with st.expander("📝 Configurações Atuais", expanded=True):
            st.write(f"**Localidade:** {localidade[1]} (código: {id_localidade})")
            st.write(f"**Período:** {periodo[1]} (código: {id_periodo})")
            st.write(f"**Forma de Ingresso:** {forma_ingresso[1]} (código: {id_forma_ingresso})")
            
            if id_curso:
                st.write(f"**Código do Curso:** {id_curso}")
            else:
                st.warning("⚠️ Código do curso não informado")
            
            if id_desdobramento:
                st.write(f"**Código do Desdobramento:** {id_desdobramento}")
            else:
                st.warning("⚠️ Código do desdobramento não informado")
        
        # Verificar se temos informações suficientes
        campos_obrigatorios = [id_curso, id_desdobramento]
        campos_preenchidos = [c for c in campos_obrigatorios if c and c.strip()]
        
        if len(campos_preenchidos) == 2:
            st.success("✅ Todos os campos necessários estão preenchidos!")
            
            if st.button("🚀 GERAR RELATÓRIO EXCEL", type="primary", use_container_width=True):
                with st.spinner("Gerando relatório..."):
                    try:
                        conteudo_excel = gerador.gerar_relatorio_simples(
                            id_localidade=id_localidade,
                            id_curso=id_curso,
                            id_desdobramento=id_desdobramento,
                            id_forma_ingresso=id_forma_ingresso,
                            ano_semestre=id_periodo
                        )
                        
                        # Criar botão de download
                        st.success("✅ Relatório gerado com sucesso!")
                        
                        output = io.BytesIO()
                        output.write(conteudo_excel)
                        output.seek(0)
                        
                        st.download_button(
                            label="📥 BAIXAR RELATÓRIO EXCEL",
                            data=output.getvalue(),
                            file_name=f"relatorio_uff_quimica_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar relatório: {str(e)}")
                        
                        # Sugestões de solução
                        with st.expander("🛠️ Solução de Problemas", expanded=True):
                            st.markdown(f"""
                            **Erro:** `{str(e)}`
                            
                            **Possíveis causas e soluções:**
                            
                            1. **Códigos incorretos** - Verifique se os códigos do curso e desdobramento estão corretos
                               - Acesse: {APLICACAO_URL}/relatorios/listagens_alunos
                               - Inspecione os selects para obter os valores exatos
                            
                            2. **Forma de ingresso incorreta** - Tente outras opções:
                               - '0' para todas as formas
                               - '13' para Convenio Cultural/PEC-G
                               - Outros valores da lista
                            
                            3. **Token expirado** - Tente:
                               - Sair e fazer login novamente
                               - Recarregar a página
                            
                            4. **Verifique os logs** no terminal para mais detalhes
                            """)
        else:
            st.warning("⚠️ Preencha os códigos do curso e desdobramento para gerar o relatório")
        
        st.markdown("---")
        st.info("""
        **📋 Como obter os códigos corretos:**
        
        1. **Acesse manualmente** o sistema de relatórios:
           ```
           https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos
           ```
        
        2. **Use as Ferramentas de Desenvolvedor** (F12):
           - Vá para a aba **"Elements"**
           - Procure: `<select name="idcurso" id="idcurso">`
           - Dentro dele, encontre a opção para **Química** e anote o `value`
        
        3. **Selecione o curso** de Química no sistema web
           - Agora procure: `<select name="iddesdobramento" id="iddesdobramento">`
           - Encontre a especialização desejada e anote o `value`
        
        4. **Volte aqui** e insira os códigos encontrados
        
        **💡 Dica:** Os códigos provavelmente são:
        - Química (Licenciatura): **12700**
        - Química (Bacharelado): **312700**  
        - Química Industrial: **12709**
        
        **Teste com esses valores primeiro!**
        """)
        
        # Seção para teste rápido com valores sugeridos
        with st.expander("🧪 Teste Rápido com Valores Sugeridos", expanded=False):
            st.write("Tente estas combinações (valores hipotéticos):")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Testar Licenciatura", key="test_lic"):
                    st.session_state.id_curso_test = "12700"
                    st.session_state.id_desdobramento_test = "12700"
                    st.info("Usando 12700 para curso e desdobramento")
            
            with col2:
                if st.button("Testar Bacharelado", key="test_bach"):
                    st.session_state.id_curso_test = "312700"
                    st.session_state.id_desdobramento_test = "312700"
                    st.info("Usando 312700 para curso e desdobramento")
            
            with col3:
                if st.button("Testar Industrial", key="test_ind"):
                    st.session_state.id_curso_test = "12709"
                    st.session_state.id_desdobramento_test = "12709"
                    st.info("Usando 12709 para curso e desdobramento")
            
            # Aplicar valores de teste se existirem
            if hasattr(st.session_state, 'id_curso_test'):
                id_curso = st.session_state.id_curso_test
            if hasattr(st.session_state, 'id_desdobramento_test'):
                id_desdobramento = st.session_state.id_desdobramento_test


if __name__ == "__main__":
    main()
