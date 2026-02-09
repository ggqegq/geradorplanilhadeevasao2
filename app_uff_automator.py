"""
Automador de Relatórios - UFF Química
Versão: Com nomes corretos dos campos baseado na análise
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

# Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
}

# Mapeamento CORRETO baseado na análise
CURSOS_QUIMICA = {
    'Licenciatura': {
        'nome_curso': 'Química',
        'id_desdobramento': '12700',  # Precisa confirmar este valor
        'id_curso': '12700',  # Valor a ser descoberto após selecionar localidade
    },
    'Bacharelado': {
        'nome_curso': 'Química',
        'id_desdobramento': '312700',  # Precisa confirmar este valor
        'id_curso': '312700',  # Valor a ser descoberto após selecionar localidade
    },
    'Industrial': {
        'nome_curso': 'Química Industrial',
        'id_desdobramento': '12709',  # Precisa confirmar este valor
        'id_curso': '12709',  # Valor a ser descoberto após selecionar localidade
    }
}

# Formas de ingresso - Valores reais do select idformaingresso
FORMAS_INGRESSO = {
    '1': '1',  # SISU 1ª Edição - PRECISA CONFIRMAR O VALOR EXATO
    '2': '2'   # SISU 2ª Edição - PRECISA CONFIRMAR O VALOR EXATO
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


class GeradorRelatorios:
    """Classe para gerar relatórios com campos corretos"""
    
    def __init__(self, session):
        self.session = session
        self.base_url = APLICACAO_URL
    
    def obter_cursos_para_localidade(self, id_localidade='1'):
        """Obtém cursos disponíveis para uma localidade específica"""
        try:
            # Primeiro precisamos selecionar a localidade
            url = f"{self.base_url}/relatorios/listagens_alunos"
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Encontrar o formulário
            form = soup.find('form')
            if not form:
                return {}
            
            # Extrair token CSRF
            token = None
            for input_tag in form.find_all('input'):
                if input_tag.get('name') == 'authenticity_token':
                    token = input_tag.get('value', '')
                    break
            
            if not token:
                return {}
            
            # Montar requisição para obter cursos
            dados = {
                'authenticity_token': token,
                'idlocalidade': id_localidade,
                'commit': 'Filtrar'
            }
            
            # Enviar requisição AJAX para carregar cursos
            response = self.session.post(
                url,
                data=dados,
                timeout=10,
                headers={
                    'Referer': url,
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            )
            
            # Tentar extrair cursos da resposta
            # Esta parte pode precisar de ajuste dependendo da resposta
            cursos = {}
            
            # Se a resposta for HTML, tentar extrair options
            if 'text/html' in response.headers.get('content-type', ''):
                soup_resposta = BeautifulSoup(response.text, 'html.parser')
                select_curso = soup_resposta.find('select', {'id': 'idcurso'})
                if select_curso:
                    for option in select_curso.find_all('option'):
                        if option.get('value') and option.get('value').strip():
                            cursos[option.get('value')] = option.get_text(strip=True)
            
            return cursos
            
        except Exception as e:
            logger.error(f"Erro ao obter cursos: {e}")
            return {}
    
    def gerar_relatorio(self, filtros):
        """Gera um relatório com os filtros fornecidos"""
        try:
            logger.info("Iniciando geração de relatório...")
            
            # 1. Acessar página de listagem
            url = f"{self.base_url}/relatorios/listagens_alunos"
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. Encontrar formulário e extrair token
            form = soup.find('form')
            if not form:
                raise Exception("Formulário não encontrado")
            
            token = None
            for input_tag in form.find_all('input'):
                if input_tag.get('name') == 'authenticity_token':
                    token = input_tag.get('value', '')
                    break
            
            if not token:
                raise Exception("Token CSRF não encontrado")
            
            logger.info(f"Token CSRF encontrado: {token[:20]}...")
            
            # 3. Preparar dados do formulário com campos CORRETOS
            dados_formulario = {
                'authenticity_token': token,
                'commit': 'Gerar Relatório'  # Nome do botão submit
            }
            
            # 4. Adicionar filtros
            # Campos OBRIGATÓRIOS baseados na análise:
            # - idlocalidade: ID da localidade (1 = Niterói)
            # - idcurso: ID do curso (precisa ser selecionado após localidade)
            # - iddesdobramento: ID do desdobramento (especialização do curso)
            
            # Adicionar filtros fornecidos
            for campo, valor in filtros.items():
                dados_formulario[campo] = valor
            
            logger.info(f"Dados do formulário: {dados_formulario}")
            
            # 5. Submeter formulário
            response = self.session.post(
                url,
                data=dados_formulario,
                timeout=30,
                allow_redirects=True,
                headers={
                    'Referer': url,
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            )
            
            logger.info(f"Status da resposta: {response.status_code}")
            logger.info(f"URL após submissão: {response.url}")
            
            # 6. Verificar se foi bem-sucedido
            if response.status_code != 200:
                logger.error(f"Erro na submissão: {response.status_code}")
                
                # Salvar resposta para debug
                with open('erro_submissao.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                # Tentar extrair mensagem de erro
                soup_erro = BeautifulSoup(response.text, 'html.parser')
                erros = soup_erro.find_all(['div', 'p'], class_=lambda x: x and 'error' in str(x).lower())
                for erro in erros:
                    logger.error(f"Mensagem de erro: {erro.get_text(strip=True)}")
                
                raise Exception(f"Erro {response.status_code} na submissão")
            
            # 7. Extrair ID do relatório
            match = re.search(r'/relatorios/(\d+)', response.url)
            if match:
                relatorio_id = match.group(1)
                logger.info(f"✅ Relatório criado com ID: {relatorio_id}")
                
                # 8. Aguardar processamento e baixar
                return self.baixar_relatorio(relatorio_id)
            else:
                # Verificar se há link para o relatório na página
                soup_resposta = BeautifulSoup(response.text, 'html.parser')
                relatorio_link = soup_resposta.find('a', href=re.compile(r'/relatorios/\d+'))
                if relatorio_link:
                    href = relatorio_link.get('href', '')
                    match = re.search(r'/relatorios/(\d+)', href)
                    if match:
                        relatorio_id = match.group(1)
                        logger.info(f"✅ Relatório encontrado via link: {relatorio_id}")
                        return self.baixar_relatorio(relatorio_id)
                
                raise Exception("ID do relatório não encontrado")
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            raise
    
    def baixar_relatorio(self, relatorio_id):
        """Aguarda e baixa o relatório"""
        try:
            logger.info(f"Aguardando relatório {relatorio_id}...")
            
            url_status = f"{BASE_URL}/relatorios/{relatorio_id}"
            
            # Aguardar até 2 minutos (40 tentativas de 3 segundos)
            for tentativa in range(40):
                response = self.session.get(url_status, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Procurar link de download Excel
                download_link = soup.find('a', href=lambda x: x and '.xlsx' in str(x))
                
                if download_link:
                    download_url = urljoin(BASE_URL, download_link.get('href'))
                    logger.info(f"✅ Relatório pronto! Baixando de: {download_url}")
                    
                    # Baixar arquivo
                    file_response = self.session.get(download_url, timeout=30)
                    file_response.raise_for_status()
                    
                    logger.info(f"✅ Arquivo baixado! Tamanho: {len(file_response.content)} bytes")
                    return file_response.content
                
                # Verificar mensagens de processamento
                if "processando" in response.text.lower() or "gerando" in response.text.lower():
                    logger.info(f"Aguardando... ({tentativa + 1}/40)")
                else:
                    # Verificar se há erro
                    if "erro" in response.text.lower() or "error" in response.text.lower():
                        erro_div = soup.find(['div', 'p'], class_=lambda x: x and 'error' in str(x).lower())
                        if erro_div:
                            raise Exception(f"Erro no processamento: {erro_div.get_text(strip=True)}")
                
                time.sleep(3)  # Aguardar 3 segundos
            
            raise Exception(f"Timeout aguardando relatório {relatorio_id}")
            
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
        st.session_state.cursos_disponiveis = {}
    
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
                st.session_state.cursos_disponiveis = {}
                st.rerun()
    
    # Conteúdo principal
    if st.session_state.session is None:
        st.info("👈 Faça login para começar")
    else:
        st.header("⚙️ Configuração do Relatório")
        
        # Explicação dos campos corretos
        with st.expander("📋 Campos do formulário (baseado na análise)", expanded=True):
            st.markdown("""
            **Campos identificados na análise:**
            
            1. **idlocalidade** - Localidade (1 = Niterói)
            2. **idcurso** - Curso (depende da localidade)
            3. **iddesdobramento** - Desdobramento/Especialização do curso
            4. **idformaingresso** - Forma de ingresso
            5. **anosem_ingresso** - Ano/Semestre de ingresso (ex: 20251 = 2025/1º)
            
            **Campos opcionais:**
            - idturno, idstatusaluno, idsituacaoaluno, idacaoafirmativa, etc.
            """)
        
        # Configuração básica
        col1, col2 = st.columns(2)
        
        with col1:
            periodo = st.selectbox(
                "Período de Ingresso",
                options=['2025/1º', '2025/2º', '2026/1º', '2026/2º'],
                index=0,
                help="Formato: 20251 = 2025/1º, 20252 = 2025/2º"
            )
            
            # Converter para o formato do sistema
            def converter_periodo(periodo_str):
                # "2025/1º" -> "20251"
                # "2025/2º" -> "20252"
                partes = periodo_str.split('/')
                ano = partes[0]
                semestre = partes[1][0]  # Pega apenas o número
                return f"{ano}{semestre}"
            
            periodo_codigo = converter_periodo(periodo)
        
        with col2:
            curso_selecionado = st.selectbox(
                "Curso",
                options=list(CURSOS_QUIMICA.keys()),
                index=0
            )
        
        # Forma de ingresso
        forma_ingresso = st.selectbox(
            "Forma de Ingresso",
            options=['SISU 1ª Edição', 'SISU 2ª Edição', 'Vestibular', 'Transferência'],
            index=0,
            help="Precisamos descobrir os valores exatos do select 'idformaingresso'"
        )
        
        # Mapear forma de ingresso para código (PRECISA SER CONFIRMADO)
        forma_ingresso_map = {
            'SISU 1ª Edição': '1',
            'SISU 2ª Edição': '2',
            'Vestibular': '3',  # Valor hipotético
            'Transferência': '4'  # Valor hipotético
        }
        
        st.markdown("---")
        
        # Botão para testar com valores conhecidos
        st.info("⚠️ **Atenção:** Precisamos descobrir os valores exatos para os campos")
        
        col1, col2, col3 = st.columns(3)
        
        with col2:
            if st.button("🚀 Gerar Relatório de Teste", type="primary", use_container_width=True):
                with st.spinner("Gerando relatório..."):
                    try:
                        gerador = GeradorRelatorios(st.session_state.session)
                        
                        # Filtros mínimos para teste
                        filtros_teste = {
                            'authenticity_token': '',  # Será preenchido automaticamente
                            'idlocalidade': '1',  # Niterói
                            'idcurso': '',  # PRECISA SER DESCOBERTO
                            'iddesdobramento': '',  # PRECISA SER DESCOBERTO
                            'idformaingresso': forma_ingresso_map.get(forma_ingresso, '1'),
                            'anosem_ingresso': periodo_codigo,
                            'commit': 'Gerar Relatório'
                        }
                        
                        # Primeiro, tentar obter cursos disponíveis
                        st.info("🔍 Obtendo cursos disponíveis para Niterói...")
                        cursos = gerador.obter_cursos_para_localidade('1')
                        
                        if cursos:
                            st.success(f"✅ Encontrados {len(cursos)} cursos")
                            
                            # Mostrar cursos encontrados
                            with st.expander("📋 Cursos disponíveis"):
                                for codigo, nome in list(cursos.items())[:20]:  # Mostrar até 20
                                    st.write(f"`{codigo}`: {nome}")
                            
                            # Procurar curso de Química
                            curso_quimica = None
                            for codigo, nome in cursos.items():
                                if 'química' in nome.lower():
                                    curso_quimica = codigo
                                    st.info(f"Curso de Química encontrado: {nome} (código: {codigo})")
                                    break
                            
                            if curso_quimica:
                                filtros_teste['idcurso'] = curso_quimica
                                
                                # Agora precisamos do desdobramento
                                # Em muitos sistemas, o desdobramento é o mesmo código do curso
                                filtros_teste['iddesdobramento'] = curso_quimica
                                
                                st.info("🎯 Tentando gerar relatório com valores encontrados...")
                                
                                try:
                                    conteudo_excel = gerador.gerar_relatorio(filtros_teste)
                                    
                                    # Salvar arquivo
                                    output = io.BytesIO()
                                    output.write(conteudo_excel)
                                    output.seek(0)
                                    
                                    st.success("✅ Relatório gerado com sucesso!")
                                    
                                    # Botão de download
                                    st.download_button(
                                        label="📥 Baixar Relatório Excel",
                                        data=output.getvalue(),
                                        file_name=f"relatorio_uff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        use_container_width=True
                                    )
                                    
                                except Exception as e:
                                    st.error(f"❌ Erro ao gerar relatório: {str(e)}")
                                    st.info("""
                                    **Próximos passos:**
                                    1. Verifique os logs para mais detalhes
                                    2. Precisamos descobrir o valor correto para 'iddesdobramento'
                                    3. Talvez precisemos de outros campos obrigatórios
                                    """)
                            else:
                                st.error("❌ Curso de Química não encontrado na lista")
                        else:
                            st.warning("⚠️ Não foi possível obter a lista de cursos")
                            st.info("""
                            **Solução alternativa:**
                            1. Acesse manualmente o sistema
                            2. Gere um relatório manualmente
                            3. Inspecione os valores dos campos no formulário
                            4. Compartilhe os valores exatos encontrados
                            """)
                        
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")
        
        st.markdown("---")
        st.info("""
        **🔧 Para encontrar os valores corretos:**
        
        1. **Acesse manualmente:** https://app.uff.br/graduacao/administracaoacademica/relatorios/listagens_alunos
        2. **Preencha o formulário** para gerar um relatório de Química
        3. **Use as ferramentas de desenvolvedor** (F12) para inspecionar:
           - Valores do select `idcurso`
           - Valores do select `iddesdobramento` 
           - Valores do select `idformaingresso`
        4. **Compartilhe os valores exatos** para atualizarmos o código
        
        **Valores que precisamos descobrir:**
        - Código exato do curso de Química (Licenciatura/Bacharelado/Industrial)
        - Código do desdobramento correspondente
        - Código das formas de ingresso (SISU 1ª, SISU 2ª, etc.)
        """)
        
        # Seção para entrada manual de valores
        with st.expander("🔧 Entrada Manual de Valores (para teste)"):
            st.write("Digite os valores que você encontrar no formulário manual:")
            
            col1, col2 = st.columns(2)
            
            with col1:
                idcurso_manual = st.text_input("Código do Curso (idcurso):")
                iddesdobramento_manual = st.text_input("Código do Desdobramento (iddesdobramento):")
            
            with col2:
                idformaingresso_manual = st.text_input("Código Forma Ingresso (idformaingresso):")
            
            if st.button("Testar com Valores Manuais", type="secondary"):
                if idcurso_manual and iddesdobramento_manual:
                    with st.spinner("Testando..."):
                        try:
                            gerador = GeradorRelatorios(st.session_state.session)
                            
                            filtros_manual = {
                                'authenticity_token': '',  # Será preenchido
                                'idlocalidade': '1',
                                'idcurso': idcurso_manual,
                                'iddesdobramento': iddesdobramento_manual,
                                'idformaingresso': idformaingresso_manual or '1',
                                'anosem_ingresso': periodo_codigo,
                                'commit': 'Gerar Relatório'
                            }
                            
                            conteudo_excel = gerador.gerar_relatorio(filtros_manual)
                            
                            output = io.BytesIO()
                            output.write(conteudo_excel)
                            output.seek(0)
                            
                            st.success("✅ Sucesso com valores manuais!")
                            
                            st.download_button(
                                label="📥 Baixar Relatório",
                                data=output.getvalue(),
                                file_name=f"relatorio_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                            
                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")


if __name__ == "__main__":
    main()
