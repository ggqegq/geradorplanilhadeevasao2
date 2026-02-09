"""
Automador de Relatórios - UFF Química
Versão: Análise completa e seleção manual de valores
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


class AnalisadorFormulario:
    """Analisa completamente o formulário de relatórios"""
    
    def __init__(self, session):
        self.session = session
    
    def analisar_formulario_completo(self):
        """Analisa todos os campos do formulário"""
        try:
            url = f"{APLICACAO_URL}/relatorios/listagens_alunos"
            logger.info(f"Acessando página: {url}")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Encontrar todos os formulários
            forms = soup.find_all('form')
            logger.info(f"Total de formulários encontrados: {len(forms)}")
            
            # Procurar formulário principal de relatórios
            form_principal = None
            for form in forms:
                action = form.get('action', '').lower()
                if 'listagens_alunos' in action or 'relatorios' in action:
                    form_principal = form
                    break
            
            if not form_principal and forms:
                form_principal = forms[0]
            
            if not form_principal:
                raise Exception("Nenhum formulário encontrado")
            
            # Extrair token CSRF
            token = None
            for input_tag in form_principal.find_all('input'):
                if input_tag.get('name') == 'authenticity_token':
                    token = input_tag.get('value', '')
                    break
            
            # Analisar todos os campos
            analise = {
                'token': token,
                'action': form_principal.get('action', ''),
                'method': form_principal.get('method', 'post').upper(),
                'campos': {}
            }
            
            # Analisar todos os selects
            for select in form_principal.find_all('select'):
                nome = select.get('name', '')
                if nome:
                    opcoes = []
                    for option in select.find_all('option'):
                        opcoes.append({
                            'valor': option.get('value', ''),
                            'texto': option.get_text(strip=True),
                            'selecionado': 'selected' in option.attrs
                        })
                    
                    analise['campos'][nome] = {
                        'tipo': 'select',
                        'opcoes': opcoes,
                        'id': select.get('id', ''),
                        'required': 'required' in select.attrs
                    }
            
            # Analisar todos os inputs
            for input_tag in form_principal.find_all('input'):
                nome = input_tag.get('name', '')
                if nome:
                    analise['campos'][nome] = {
                        'tipo': input_tag.get('type', 'text'),
                        'valor': input_tag.get('value', ''),
                        'id': input_tag.get('id', ''),
                        'required': 'required' in input_tag.attrs
                    }
            
            # Analisar textareas
            for textarea in form_principal.find_all('textarea'):
                nome = textarea.get('name', '')
                if nome:
                    analise['campos'][nome] = {
                        'tipo': 'textarea',
                        'valor': textarea.get_text(strip=True),
                        'id': textarea.get('id', ''),
                        'required': 'required' in textarea.attrs
                    }
            
            # Analisar botões
            botoes = []
            for button in form_principal.find_all('button'):
                botoes.append({
                    'nome': button.get('name', ''),
                    'valor': button.get('value', ''),
                    'texto': button.get_text(strip=True),
                    'tipo': button.get('type', 'submit')
                })
            
            for input_tag in form_principal.find_all('input', type=['submit', 'button']):
                botoes.append({
                    'nome': input_tag.get('name', ''),
                    'valor': input_tag.get('value', ''),
                    'texto': input_tag.get('value', ''),
                    'tipo': input_tag.get('type', 'submit')
                })
            
            analise['botoes'] = botoes
            
            return analise
            
        except Exception as e:
            logger.error(f"Erro ao analisar formulário: {e}")
            raise


class GeradorRelatorios:
    """Gera relatórios com base na análise do formulário"""
    
    def __init__(self, session):
        self.session = session
        self.analisador = AnalisadorFormulario(session)
    
    def gerar_relatorio_com_valores(self, valores_selecionados):
        """Gera relatório com os valores selecionados"""
        try:
            # 1. Primeiro analisar o formulário para obter o token atual
            st.info("📋 Analisando formulário...")
            analise = self.analisador.analisar_formulario_completo()
            
            if not analise['token']:
                raise Exception("Token CSRF não encontrado")
            
            # 2. Preparar dados para envio
            dados = {
                'authenticity_token': analise['token']
            }
            
            # 3. Adicionar todos os valores selecionados
            for campo, valor in valores_selecionados.items():
                if valor:  # Só adicionar se tiver valor
                    dados[campo] = valor
            
            # 4. Adicionar botão submit (geralmente é 'commit')
            # Procurar botão submit no formulário
            botao_submit = None
            for botao in analise['botoes']:
                if botao['tipo'] == 'submit':
                    botao_submit = botao
                    break
            
            if botao_submit and botao_submit['nome']:
                dados[botao_submit['nome']] = botao_submit['valor'] or 'Gerar Relatório'
            else:
                dados['commit'] = 'Gerar Relatório'  # Fallback
            
            logger.info(f"Enviando {len(dados)} campos")
            logger.info(f"Campos: {list(dados.keys())}")
            
            # 5. Construir URL completa
            action_url = analise['action']
            if not action_url.startswith('http'):
                action_url = urljoin(APLICACAO_URL, action_url)
            
            # 6. Enviar requisição
            st.info("🚀 Enviando formulário...")
            response = self.session.post(
                action_url,
                data=dados,
                timeout=30,
                allow_redirects=True,
                headers={
                    'Referer': f"{APLICACAO_URL}/relatorios/listagens_alunos",
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            )
            
            logger.info(f"Status: {response.status_code}")
            logger.info(f"URL após envio: {response.url}")
            
            # 7. Verificar resultado
            if response.status_code != 200:
                logger.error(f"Erro {response.status_code}")
                
                # Salvar resposta de erro
                with open('erro_detalhado.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                
                # Tentar extrair mensagem de erro
                soup_erro = BeautifulSoup(response.text, 'html.parser')
                
                # Procurar várias classes de erro possíveis
                classes_erro = ['error', 'alert-error', 'alert-danger', 'flash-error']
                for classe in classes_erro:
                    erros = soup_erro.find_all(class_=classe)
                    for erro in erros:
                        texto_erro = erro.get_text(strip=True)
                        if texto_erro:
                            raise Exception(f"Erro do sistema: {texto_erro}")
                
                raise Exception(f"Erro HTTP {response.status_code}")
            
            # 8. Extrair ID do relatório
            match = re.search(r'/relatorios/(\d+)', response.url)
            if match:
                relatorio_id = match.group(1)
                st.info(f"✅ Relatório criado! ID: {relatorio_id}")
                
                # 9. Aguardar e baixar
                return self.baixar_relatorio(relatorio_id)
            else:
                # Verificar se a página contém link para relatório
                soup = BeautifulSoup(response.text, 'html.parser')
                links_relatorio = soup.find_all('a', href=re.compile(r'/relatorios/\d+'))
                
                if links_relatorio:
                    href = links_relatorio[0].get('href', '')
                    match = re.search(r'/relatorios/(\d+)', href)
                    if match:
                        relatorio_id = match.group(1)
                        st.info(f"✅ Relatório encontrado via link! ID: {relatorio_id}")
                        return self.baixar_relatorio(relatorio_id)
                
                # Se não encontrou ID, verificar se há mensagem de sucesso
                if 'relatório' in response.text.lower() and ('gerado' in response.text.lower() or 'criado' in response.text.lower()):
                    # Talvez o relatório esteja em uma tabela ou lista
                    st.warning("Relatório parece ter sido criado, mas ID não encontrado")
                    
                    # Procurar qualquer link que possa ser o relatório
                    todos_links = soup.find_all('a')
                    for link in todos_links:
                        href = link.get('href', '')
                        if '/relatorios/' in href:
                            match = re.search(r'/relatorios/(\d+)', href)
                            if match:
                                relatorio_id = match.group(1)
                                st.info(f"✅ Encontrado link alternativo! ID: {relatorio_id}")
                                return self.baixar_relatorio(relatorio_id)
                
                raise Exception("Não foi possível encontrar o ID do relatório")
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            raise
    
    def baixar_relatorio(self, relatorio_id):
        """Aguarda e baixa o relatório"""
        try:
            st.info(f"⏳ Aguardando processamento do relatório {relatorio_id}...")
            
            url_status = f"{BASE_URL}/relatorios/{relatorio_id}"
            
            # Barra de progresso
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Tentar por até 2 minutos
            for tentativa in range(40):
                progresso = (tentativa + 1) / 40
                progress_bar.progress(progresso)
                status_text.text(f"Aguardando... ({tentativa + 1}/40)")
                
                response = self.session.get(url_status, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Procurar link de download Excel
                download_links = []
                
                # Procurar por links .xlsx
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if '.xlsx' in href.lower():
                        download_links.append(href)
                
                if download_links:
                    # Usar o primeiro link Excel encontrado
                    download_url = urljoin(BASE_URL, download_links[0])
                    st.info(f"✅ Relatório pronto! Baixando...")
                    
                    # Baixar arquivo
                    file_response = self.session.get(download_url, timeout=30)
                    file_response.raise_for_status()
                    
                    progress_bar.progress(1.0)
                    status_text.text("✅ Download completo!")
                    
                    return file_response.content
                
                # Verificar se há mensagem de erro
                if "erro" in response.text.lower():
                    erros = soup.find_all(class_=lambda x: x and 'error' in x.lower())
                    for erro in erros:
                        texto = erro.get_text(strip=True)
                        if texto:
                            raise Exception(f"Erro no processamento: {texto}")
                
                # Verificar se está processando
                texto_pagina = response.text.lower()
                if "processando" in texto_pagina or "gerando" in texto_pagina:
                    time.sleep(3)
                    continue
                elif "pronto" in texto_pagina or "disponível" in texto_pagina:
                    # Talvez esteja pronto mas sem link explícito
                    # Procurar por qualquer link que possa ser o download
                    todos_links = soup.find_all('a')
                    for link in todos_links:
                        href = link.get('href', '')
                        if any(ext in href.lower() for ext in ['.xls', '.xlsx', '.csv', '.pdf']):
                            download_url = urljoin(BASE_URL, href)
                            file_response = self.session.get(download_url, timeout=30)
                            if file_response.status_code == 200:
                                progress_bar.progress(1.0)
                                status_text.text("✅ Download completo!")
                                return file_response.content
                
                time.sleep(3)  # Aguardar 3 segundos entre tentativas
            
            raise Exception("Timeout: Relatório não ficou pronto em 2 minutos")
            
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
        st.session_state.analise_formulario = None
        st.session_state.valores_selecionados = {}
    
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
                st.session_state.analise_formulario = None
                st.session_state.valores_selecionados = {}
                st.rerun()
    
    # Conteúdo principal
    if st.session_state.session is None:
        st.info("👈 Faça login para começar")
    else:
        st.header("📊 Configuração do Relatório")
        
        # Botão para analisar formulário
        if st.button("🔍 Analisar Formulário Completo", type="primary", use_container_width=True):
            with st.spinner("Analisando formulário..."):
                try:
                    analisador = AnalisadorFormulario(st.session_state.session)
                    analise = analisador.analisar_formulario_completo()
                    st.session_state.analise_formulario = analise
                    st.success(f"✅ Análise completa! {len(analise['campos'])} campos encontrados.")
                except Exception as e:
                    st.error(f"❌ Erro na análise: {str(e)}")
        
        # Se temos análise, mostrar campos
        if st.session_state.analise_formulario:
            analise = st.session_state.analise_formulario
            
            st.markdown("---")
            st.subheader("📋 Campos do Formulário")
            
            # Separar campos por tipo
            campos_select = {k: v for k, v in analise['campos'].items() if v['tipo'] == 'select'}
            campos_input = {k: v for k, v in analise['campos'].items() if v['tipo'] != 'select'}
            
            # Mostrar selects primeiro (são os mais importantes)
            if campos_select:
                st.write("### 🔽 Campos de Seleção (Selects)")
                
                # Campos importantes que já identificamos
                campos_importantes = ['idlocalidade', 'idcurso', 'iddesdobramento', 
                                     'idformaingresso', 'anosem_ingresso', 'idturno']
                
                for campo_nome in campos_importantes:
                    if campo_nome in campos_select:
                        campo = campos_select[campo_nome]
                        
                        with st.expander(f"**{campo_nome}** ({campo.get('id', 'sem id')})", expanded=True):
                            st.write(f"Obrigatório: {'✅ Sim' if campo['required'] else '❌ Não'}")
                            
                            # Criar lista de opções para o select
                            opcoes = campo['opcoes']
                            
                            if opcoes:
                                # Mostrar algumas informações sobre as opções
                                df_opcoes = pd.DataFrame([
                                    {
                                        'Valor': opt['valor'],
                                        'Texto': opt['texto'],
                                        'Selecionado': '✅' if opt['selecionado'] else '❌'
                                    }
                                    for opt in opcoes[:50]  # Mostrar até 50 opções
                                ])
                                
                                st.dataframe(df_opcoes, use_container_width=True)
                                
                                if len(opcoes) > 50:
                                    st.info(f"... e mais {len(opcoes) - 50} opções")
                                
                                # Selecionar valor
                                opcoes_dict = {opt['valor']: f"{opt['texto']} ({opt['valor']})" 
                                              for opt in opcoes if opt['valor'].strip()}
                                
                                if opcoes_dict:
                                    valor_atual = st.session_state.valores_selecionados.get(campo_nome, '')
                                    
                                    # Encontrar texto para valor atual
                                    texto_atual = ''
                                    if valor_atual and valor_atual in opcoes_dict:
                                        texto_atual = opcoes_dict[valor_atual]
                                    elif valor_atual:
                                        # Procurar valor nas opções
                                        for opt in opcoes:
                                            if opt['valor'] == valor_atual:
                                                texto_atual = f"{opt['texto']} ({opt['valor']})"
                                                break
                                    
                                    valor_selecionado = st.selectbox(
                                        f"Selecione valor para **{campo_nome}**:",
                                        options=list(opcoes_dict.keys()),
                                        index=list(opcoes_dict.keys()).index(valor_atual) if valor_atual in opcoes_dict else 0,
                                        format_func=lambda x: opcoes_dict.get(x, x),
                                        key=f"select_{campo_nome}"
                                    )
                                    
                                    st.session_state.valores_selecionados[campo_nome] = valor_selecionado
                                    st.info(f"Valor selecionado: `{valor_selecionado}`")
                
                # Outros selects não listados acima
                outros_selects = [k for k in campos_select.keys() if k not in campos_importantes]
                if outros_selects:
                    with st.expander(f"Outros campos de seleção ({len(outros_selects)})"):
                        for campo_nome in outros_selects[:10]:  # Mostrar até 10
                            campo = campos_select[campo_nome]
                            st.write(f"**{campo_nome}**: {len(campo['opcoes'])} opções")
            
            # Mostrar inputs
            if campos_input:
                st.write("### ⌨️ Outros Campos")
                
                # Filtrar inputs importantes
                inputs_importantes = {k: v for k, v in campos_input.items() 
                                     if v['tipo'] in ['hidden', 'text', 'number'] and v['valor']}
                
                if inputs_importantes:
                    with st.expander("Campos com valores pré-definidos"):
                        for campo_nome, campo in list(inputs_importantes.items())[:20]:  # Mostrar até 20
                            st.write(f"**{campo_nome}** ({campo['tipo']}): `{campo['valor'][:100]}`")
            
            # Mostrar botões
            if analise['botoes']:
                st.write("### 🔘 Botões do Formulário")
                for botao in analise['botoes']:
                    st.write(f"**{botao['nome'] or 'Sem nome'}**: {botao['texto']} (tipo: {botao['tipo']})")
            
            # Interface para gerar relatório
            st.markdown("---")
            st.subheader("🚀 Gerar Relatório")
            
            # Valores mínimos recomendados baseados na análise anterior
            st.info("**Valores recomendados para teste:**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("📍 **Localidade:**")
                st.code("idlocalidade: 1 (Niterói)")
            
            with col2:
                st.write("🎓 **Curso/Desdobramento:**")
                st.code("Precisa descobrir valores")
            
            with col3:
                st.write("📅 **Período:**")
                st.code("anosem_ingresso: 20251")
            
            # Verificar se temos valores selecionados suficientes
            campos_obrigatorios = ['idlocalidade', 'idcurso', 'iddesdobramento', 'anosem_ingresso']
            campos_preenchidos = [c for c in campos_obrigatorios if st.session_state.valores_selecionados.get(c)]
            
            if len(campos_preenchidos) >= 3:
                st.success(f"✅ {len(campos_preenchidos)}/{len(campos_obrigatorios)} campos obrigatórios preenchidos")
            else:
                st.warning(f"⚠️ Apenas {len(campos_preenchidos)}/{len(campos_obrigatorios)} campos obrigatórios preenchidos")
            
            # Mostrar valores selecionados
            if st.session_state.valores_selecionados:
                with st.expander("📝 Valores Selecionados", expanded=True):
                    for campo, valor in st.session_state.valores_selecionados.items():
                        st.write(f"**{campo}**: `{valor}`")
            
            # Botão para gerar relatório
            if st.button("🚀 GERAR RELATÓRIO COM VALORES SELECIONADOS", 
                        type="primary", 
                        use_container_width=True,
                        disabled=len(campos_preenchidos) < 3):
                
                with st.spinner("Gerando relatório..."):
                    try:
                        gerador = GeradorRelatorios(st.session_state.session)
                        
                        # Adicionar token aos valores selecionados
                        valores_completos = st.session_state.valores_selecionados.copy()
                        
                        # Garantir que temos os campos obrigatórios
                        if 'idlocalidade' not in valores_completos:
                            valores_completos['idlocalidade'] = '1'  # Niterói
                        
                        # Gerar relatório
                        conteudo_excel = gerador.gerar_relatorio_com_valores(valores_completos)
                        
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
                        st.info("""
                        **Possíveis soluções:**
                        1. Verifique se todos os campos obrigatórios estão preenchidos
                        2. Tente diferentes combinações de valores
                        3. Verifique os logs para mais detalhes
                        """)
        
        else:
            st.info("👆 Clique em 'Analisar Formulário Completo' para começar")
        
        st.markdown("---")
        st.info("""
        **📋 Instruções:**
        
        1. **Analise o formulário** clicando no botão acima
        2. **Preencha os campos obrigatórios:**
           - `idlocalidade`: 1 (Niterói)
           - `idcurso`: Código do curso de Química
           - `iddesdobramento`: Código da especialização
           - `anosem_ingresso`: Período no formato 20251, 20252, etc.
        3. **Clique em GERAR RELATÓRIO**
        
        **🔍 Para encontrar os valores corretos manualmente:**
        
        1. Acesse o sistema manualmente
        2. Selecione Niterói (já deve estar como padrão)
        3. Inspecione o select `idcurso` para ver o código do curso de Química
        4. Depois de selecionar o curso, inspecione `iddesdobramento`
        5. Anote os códigos e use aqui
        """)


if __name__ == "__main__":
    main()
