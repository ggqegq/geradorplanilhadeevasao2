"""
Automador de Relatórios - UFF Química
Versão: Análise completa do formulário primeiro
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

class LoginUFF:
    """Classe de login - JÁ FUNCIONANDO"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.is_authenticated = False
    
    def fazer_login(self, cpf: str, senha: str) -> bool:
        """Realiza login no sistema UFF"""
        try:
            st.info("Conectando ao portal UFF...")
            
            # Acessar a página inicial
            response = self.session.get(APLICACAO_URL, timeout=TIMEOUT_REQUESTS)
            
            if response.status_code != 200:
                return False
            
            # Extrair parâmetros
            soup = BeautifulSoup(response.text, 'html.parser')
            login_form = soup.find('form', {'id': 'kc-form-login'}) or soup.find('form', method='post')
            
            if not login_form:
                return False
            
            action_url = login_form.get('action', '')
            if action_url.startswith('/'):
                parsed_base = urlparse(BASE_URL)
                action_url = f"{parsed_base.scheme}://{parsed_base.netloc}{action_url}"
            
            # Preparar dados
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
            
            # Enviar requisição
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
            
            # Verificar sucesso
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
    """Classe para analisar o formulário de relatórios"""
    
    def __init__(self, session):
        self.session = session
    
    def analisar_pagina_relatorios(self):
        """Analisa completamente a página de relatórios"""
        try:
            url = f"{APLICACAO_URL}/relatorios/listagens_alunos"
            logger.info(f"Acessando página: {url}")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # Salvar HTML para análise
            with open('pagina_relatorios_completa.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info("Página salva em: pagina_relatorios_completa.html")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Encontrar todos os formulários
            forms = soup.find_all('form')
            logger.info(f"Total de formulários encontrados: {len(forms)}")
            
            relatorios_form = None
            for i, form in enumerate(forms):
                action = form.get('action', '').lower()
                form_id = form.get('id', '').lower()
                form_name = form.get('name', '').lower()
                
                logger.info(f"Formulário {i}:")
                logger.info(f"  ID: {form_id}")
                logger.info(f"  Name: {form_name}")
                logger.info(f"  Action: {action}")
                logger.info(f"  Method: {form.get('method', 'GET')}")
                
                # Critérios para identificar formulário de relatórios
                if 'listagens_alunos' in action or 'relatorios' in action:
                    relatorios_form = form
                    break
                elif any(keyword in form_id for keyword in ['relatorio', 'report', 'filter']):
                    relatorios_form = form
                    break
                elif any(keyword in form_name for keyword in ['relatorio', 'report', 'filter']):
                    relatorios_form = form
                    break
            
            if not relatorios_form and forms:
                logger.warning("Usando primeiro formulário encontrado")
                relatorios_form = forms[0]
            
            if not relatorios_form:
                raise Exception("Nenhum formulário encontrado")
            
            # 2. Analisar estrutura do formulário
            analise = self.analisar_formulario_detalhado(relatorios_form)
            
            # 3. Salvar análise em JSON
            with open('analise_formulario.json', 'w', encoding='utf-8') as f:
                json.dump(analise, f, indent=2, ensure_ascii=False)
            
            logger.info("Análise do formulário salva em: analise_formulario.json")
            
            return analise
            
        except Exception as e:
            logger.error(f"Erro ao analisar página: {e}")
            raise
    
    def analisar_formulario_detalhado(self, form):
        """Analisa detalhadamente um formulário"""
        analise = {
            'action': form.get('action', ''),
            'method': form.get('method', 'get').upper(),
            'inputs': [],
            'selects': [],
            'textareas': [],
            'buttons': []
        }
        
        # Analisar inputs
        for input_tag in form.find_all('input'):
            input_info = {
                'type': input_tag.get('type', 'text'),
                'name': input_tag.get('name', ''),
                'value': input_tag.get('value', ''),
                'id': input_tag.get('id', ''),
                'class': input_tag.get('class', []),
                'required': 'required' in input_tag.attrs,
                'placeholder': input_tag.get('placeholder', ''),
                'maxlength': input_tag.get('maxlength', ''),
                'size': input_tag.get('size', '')
            }
            analise['inputs'].append(input_info)
        
        # Analisar selects
        for select_tag in form.find_all('select'):
            select_info = {
                'name': select_tag.get('name', ''),
                'id': select_tag.get('id', ''),
                'class': select_tag.get('class', []),
                'required': 'required' in select_tag.attrs,
                'multiple': 'multiple' in select_tag.attrs,
                'size': select_tag.get('size', ''),
                'options': []
            }
            
            for option in select_tag.find_all('option'):
                option_info = {
                    'value': option.get('value', ''),
                    'text': option.get_text(strip=True),
                    'selected': 'selected' in option.attrs
                }
                select_info['options'].append(option_info)
            
            analise['selects'].append(select_info)
        
        # Analisar textareas
        for textarea_tag in form.find_all('textarea'):
            textarea_info = {
                'name': textarea_tag.get('name', ''),
                'id': textarea_tag.get('id', ''),
                'class': textarea_tag.get('class', []),
                'required': 'required' in textarea_tag.attrs,
                'placeholder': textarea_tag.get('placeholder', ''),
                'rows': textarea_tag.get('rows', ''),
                'cols': textarea_tag.get('cols', ''),
                'value': textarea_tag.get_text(strip=True)
            }
            analise['textareas'].append(textarea_info)
        
        # Analisar buttons
        for button_tag in form.find_all('button'):
            button_info = {
                'type': button_tag.get('type', 'submit'),
                'name': button_tag.get('name', ''),
                'value': button_tag.get('value', ''),
                'id': button_tag.get('id', ''),
                'class': button_tag.get('class', []),
                'text': button_tag.get_text(strip=True)
            }
            analise['buttons'].append(button_info)
        
        return analise
    
    def testar_submissao_simples(self, analise):
        """Testa submissão com valores mínimos"""
        try:
            # Construir URL completa
            action_url = analise['action']
            if not action_url.startswith('http'):
                action_url = urljoin(APLICACAO_URL, action_url)
            
            # Preparar dados mínimos
            dados = {}
            
            # Adicionar inputs hidden
            for input_info in analise['inputs']:
                if input_info['type'] == 'hidden' and input_info['value']:
                    dados[input_info['name']] = input_info['value']
            
            # Adicionar campos obrigatórios dos selects
            for select_info in analise['selects']:
                if select_info['required'] and select_info['options']:
                    # Usar primeira opção não vazia
                    for option in select_info['options']:
                        if option['value']:
                            dados[select_info['name']] = option['value']
                            break
            
            # Adicionar botão submit se existir
            for button_info in analise['buttons']:
                if button_info['type'] == 'submit' and button_info['name']:
                    dados[button_info['name']] = button_info['value'] or 'Submit'
                    break
            
            logger.info(f"Testando submissão com {len(dados)} campos")
            logger.info(f"Campos: {list(dados.keys())}")
            
            # Enviar requisição
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
            logger.info(f"URL após submissão: {response.url}")
            
            # Salvar resposta
            with open('resposta_teste.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'redirected': len(response.history) > 0,
                'final_url': response.url
            }
            
        except Exception as e:
            logger.error(f"Erro no teste: {e}")
            return {'success': False, 'error': str(e)}


class GeradorRelatorios:
    """Classe para gerar relatórios após análise"""
    
    def __init__(self, session):
        self.session = session
        self.analisador = AnalisadorFormulario(session)
    
    def gerar_relatorio(self, filtros_personalizados=None):
        """Gera relatório com base na análise"""
        try:
            # 1. Analisar formulário primeiro
            st.info("🔍 Analisando formulário de relatórios...")
            analise = self.analisador.analisar_pagina_relatorios()
            
            # 2. Mostrar análise para o usuário
            st.info("📋 Estrutura do formulário encontrada:")
            
            with st.expander("📝 Campos do formulário", expanded=True):
                # Mostrar selects
                if analise['selects']:
                    st.subheader("Selects disponíveis:")
                    for select in analise['selects']:
                        st.write(f"**{select['name']}** ({'obrigatório' if select['required'] else 'opcional'}):")
                        # Mostrar algumas opções
                        options_text = []
                        for option in select['options'][:5]:  # Mostrar apenas 5 primeiras
                            options_text.append(f"'{option['value']}' → '{option['text']}'")
                        
                        if len(select['options']) > 5:
                            options_text.append(f"... e mais {len(select['options']) - 5} opções")
                        
                        st.text("\n".join(options_text))
                
                # Mostrar inputs importantes
                if analise['inputs']:
                    st.subheader("Inputs importantes:")
                    important_inputs = [i for i in analise['inputs'] if i['type'] in ['hidden', 'text', 'number']]
                    for input_info in important_inputs[:10]:  # Mostrar até 10
                        st.write(f"**{input_info['name']}** (tipo: {input_info['type']}): {input_info['value'][:50]}...")
            
            # 3. Testar submissão simples
            st.info("🧪 Testando submissão básica...")
            resultado_teste = self.analisador.testar_submissao_simples(analise)
            
            if resultado_teste['success']:
                st.success("✅ Teste básico bem-sucedido!")
                # Agora podemos tentar com filtros específicos
                return self.gerar_com_filtros(analise, filtros_personalizados)
            else:
                st.error(f"❌ Teste básico falhou: Status {resultado_teste.get('status_code')}")
                st.info("📁 Arquivos salvos para análise:")
                st.info("- pagina_relatorios_completa.html: Página completa")
                st.info("- analise_formulario.json: Análise estruturada")
                st.info("- resposta_teste.html: Resposta do servidor")
                
                return None
                
        except Exception as e:
            st.error(f"❌ Erro ao gerar relatório: {str(e)}")
            logger.error(f"Erro: {e}", exc_info=True)
            return None
    
    def gerar_com_filtros(self, analise, filtros_personalizados):
        """Gera relatório com filtros específicos"""
        try:
            # Construir URL
            action_url = analise['action']
            if not action_url.startswith('http'):
                action_url = urljoin(APLICACAO_URL, action_url)
            
            # Preparar dados base
            dados = {}
            
            # Adicionar todos os campos hidden
            for input_info in analise['inputs']:
                if input_info['type'] == 'hidden' and input_info['value'] and input_info['name']:
                    dados[input_info['name']] = input_info['value']
            
            # Aplicar filtros personalizados
            if filtros_personalizados:
                for campo, valor in filtros_personalizados.items():
                    # Verificar se campo existe no formulário
                    campo_encontrado = False
                    
                    # Verificar em selects
                    for select in analise['selects']:
                        if select['name'] == campo:
                            # Verificar se valor é válido
                            for option in select['options']:
                                if option['value'] == str(valor) or str(valor) in option['text']:
                                    dados[campo] = option['value']
                                    campo_encontrado = True
                                    logger.info(f"Filtro aplicado em select: {campo} = {option['value']}")
                                    break
                    
                    # Verificar em inputs
                    if not campo_encontrado:
                        for input_info in analise['inputs']:
                            if input_info['name'] == campo:
                                dados[campo] = valor
                                campo_encontrado = True
                                logger.info(f"Filtro aplicado em input: {campo} = {valor}")
                                break
                    
                    if not campo_encontrado:
                        logger.warning(f"Campo não encontrado no formulário: {campo}")
            
            # Adicionar botão submit
            for button_info in analise['buttons']:
                if button_info['type'] == 'submit' and button_info['name']:
                    dados[button_info['name']] = button_info['value'] or 'Submit'
                    break
            
            logger.info(f"Submetendo com {len(dados)} campos")
            
            # Enviar requisição
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
            
            if response.status_code == 200:
                # Extrair ID do relatório
                match = re.search(r'/relatorios/(\d+)', response.url)
                if match:
                    relatorio_id = match.group(1)
                    st.success(f"✅ Relatório criado! ID: {relatorio_id}")
                    
                    # Aguardar e baixar relatório
                    return self.processar_relatorio(relatorio_id)
                else:
                    st.warning("Relatório criado, mas ID não encontrado na URL")
                    return None
            else:
                st.error(f"❌ Erro na submissão: Status {response.status_code}")
                return None
                
        except Exception as e:
            st.error(f"❌ Erro: {str(e)}")
            return None
    
    def processar_relatorio(self, relatorio_id):
        """Aguarda e baixa o relatório"""
        try:
            st.info(f"⏳ Aguardando relatório {relatorio_id}...")
            
            # Verificar status
            url = f"{BASE_URL}/relatorios/{relatorio_id}"
            
            for tentativa in range(30):  # 30 tentativas com 3 segundos cada = 90 segundos
                response = self.session.get(url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Procurar link de download
                download_link = soup.find('a', href=lambda x: x and '.xlsx' in x)
                if download_link:
                    download_url = urljoin(BASE_URL, download_link.get('href'))
                    
                    # Baixar arquivo
                    st.info("📥 Baixando arquivo...")
                    file_response = self.session.get(download_url, timeout=30)
                    file_response.raise_for_status()
                    
                    st.success("✅ Arquivo baixado com sucesso!")
                    return file_response.content
                
                time.sleep(3)  # Aguardar 3 segundos
            
            st.error("⏱️ Timeout aguardando relatório")
            return None
            
        except Exception as e:
            st.error(f"❌ Erro ao processar relatório: {str(e)}")
            return None


def main():
    """Aplicação principal"""
    st.set_page_config(
        page_title="Automador de Relatórios UFF",
        layout="wide"
    )
    
    st.title("🔍 Analisador de Relatórios UFF")
    st.markdown("---")
    
    # Inicializar estado
    if 'session' not in st.session_state:
        st.session_state.session = None
        st.session_state.auth = None
    
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
                st.rerun()
    
    # Conteúdo principal
    if st.session_state.session is None:
        st.info("👈 Faça login para começar")
    else:
        st.header("📊 Geração de Relatórios")
        
        # Primeiro, análise do formulário
        if st.button("🔍 Analisar Formulário de Relatórios", use_container_width=True):
            with st.spinner("Analisando..."):
                analisador = AnalisadorFormulario(st.session_state.session)
                
                try:
                    analise = analisador.analisar_pagina_relatorios()
                    
                    # Mostrar resumo
                    st.success("✅ Análise concluída!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Campos Input", len(analise['inputs']))
                    with col2:
                        st.metric("Campos Select", len(analise['selects']))
                    with col3:
                        st.metric("Campos Textarea", len(analise['textareas']))
                    
                    # Mostrar selects importantes
                    st.subheader("📋 Campos de Filtro (Selects):")
                    
                    for select in analise['selects']:
                        with st.expander(f"🔽 {select.get('name', 'Sem nome')}", expanded=False):
                            st.write(f"**ID:** {select.get('id', 'N/A')}")
                            st.write(f"**Obrigatório:** {'Sim' if select['required'] else 'Não'}")
                            
                            # Criar tabela com opções
                            if select['options']:
                                opcoes_data = []
                                for i, option in enumerate(select['options'][:20]):  # Mostrar até 20
                                    opcoes_data.append({
                                        'Valor': option['value'],
                                        'Texto': option['text'],
                                        'Selecionado': 'Sim' if option['selected'] else 'Não'
                                    })
                                
                                if opcoes_data:
                                    st.table(pd.DataFrame(opcoes_data))
                                
                                if len(select['options']) > 20:
                                    st.info(f"... e mais {len(select['options']) - 20} opções")
                    
                    # Testar submissão simples
                    st.subheader("🧪 Teste de Submissão")
                    if st.button("Testar Submissão Simples", type="secondary"):
                        resultado = analisador.testar_submissao_simples(analise)
                        
                        if resultado['success']:
                            st.success("✅ Teste bem-sucedido!")
                            st.write(f"URL final: {resultado['final_url']}")
                        else:
                            st.error(f"❌ Teste falhou: Status {resultado.get('status_code')}")
                    
                    # Interface para testes manuais
                    st.subheader("🔧 Teste Manual com Valores")
                    
                    # Criar inputs para os selects
                    selects_para_teste = [s for s in analise['selects'] if s.get('name')]
                    
                    if selects_para_teste:
                        st.write("Configure os valores para teste:")
                        
                        valores_teste = {}
                        for select in selects_para_teste[:5]:  # Testar com até 5 selects
                            nome = select['name']
                            opcoes = {opt['value']: f"{opt['text']} ({opt['value']})" 
                                     for opt in select['options'] if opt['value']}
                            
                            if opcoes:
                                valor_selecionado = st.selectbox(
                                    f"{nome}:",
                                    options=list(opcoes.keys()),
                                    format_func=lambda x: opcoes.get(x, x),
                                    key=f"test_{nome}"
                                )
                                valores_teste[nome] = valor_selecionado
                        
                        if st.button("Testar com Valores Selecionados", type="primary"):
                            gerador = GeradorRelatorios(st.session_state.session)
                            resultado = gerador.gerar_com_filtros(analise, valores_teste)
                            
                            if resultado:
                                st.success("✅ Relatório gerado!")
                                # Mostrar botão de download
                                st.download_button(
                                    label="📥 Baixar Relatório",
                                    data=resultado,
                                    file_name=f"relatorio_uff_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                    
                except Exception as e:
                    st.error(f"❌ Erro na análise: {str(e)}")
        
        st.markdown("---")
        st.info("""
        **Instruções:**
        1. Clique em **"Analisar Formulário de Relatórios"**
        2. Aguarde a análise completa
        3. Verifique os campos disponíveis
        4. Teste valores diferentes
        5. Gere o relatório
        
        **Arquivos gerados:**
        - `pagina_relatorios_completa.html`: Página completa
        - `analise_formulario.json`: Análise estruturada
        - `resposta_teste.html`: Respostas do servidor
        """)


if __name__ == "__main__":
    main()
