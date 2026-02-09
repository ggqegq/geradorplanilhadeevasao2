"""
ARQUIVO 2: Processa dados dos relatórios e gera planilha consolidada
Executa: python 2_processar_dados.py
"""

import pandas as pd
import os
import logging
from datetime import datetime
from pathlib import Path
import re

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MAPEAMENTO DE CURSOS - Identificar pelo texto da última linha
MAPEAMENTO_CURSOS = {
    'BACHAREL': 'Bacharelado',
    'QUÍMICO INDUSTRIAL': 'Industrial',
    'LICENCIADO': 'Licenciatura'
}

# Status dos alunos
STATUS_VALIDOS = {
    'ATIVO': 'Ativo',
    'CANCELADO': 'Cancelado',
    'TRANCADO': 'Trancado',
    'FORMADO': 'Formado',
    'JUBILADO': 'Jubilado',
}

# Motivos de cancelamento
MOTIVOS_CANCELAMENTO = {
    'DESISTÊNCIA': 'Desistência',
    'ABANDONO': 'Abandono',
    'CANCELAMENTO': 'Cancelamento Administrativo',
    'REPROVAÇÃO': 'Reprovação em Disciplinas',
    'INATIVIDADE': 'Inatividade Acadêmica',
    'OUTROS': 'Outros Motivos'
}


class ProcessadorDados:
    """Processa dados dos relatórios Excel e gera análise consolidada"""
    
    def __init__(self):
        self.dados_completos = []
        self.resumo_geral = {}
        
    def carregar_relatorio(self, caminho_arquivo):
        """
        Carrega um arquivo de relatório Excel
        
        Args:
            caminho_arquivo: Caminho para o arquivo .xlsx
            
        Returns:
            DataFrame com os dados ou None
        """
        logger.info(f"Carregando: {caminho_arquivo}")
        
        try:
            # Ler todas as abas para encontrar os dados
            xls = pd.ExcelFile(caminho_arquivo)
            logger.info(f"  Abas encontradas: {xls.sheet_names}")
            
            # Geralmente os dados estão na primeira aba
            df = pd.read_excel(caminho_arquivo, sheet_name=0)
            
            logger.info(f"  Registros carregados: {len(df)}")
            logger.info(f"  Colunas: {list(df.columns)}")
            
            return df
            
        except Exception as e:
            logger.error(f"Erro ao carregar {caminho_arquivo}: {str(e)}")
            return None
    
    def identificar_curso(self, df):
        """
        Identifica o curso pela última linha do relatório
        
        Args:
            df: DataFrame do relatório
            
        Returns:
            Nome padronizado do curso ou 'Desconhecido'
        """
        
        # A última linha geralmente contém "Alunos de [TIPO] - Química"
        ultima_linha = df.iloc[-1] if len(df) > 0 else None
        
        if ultima_linha is None:
            return 'Desconhecido'
        
        # Converter para string
        texto_ultima_linha = str(ultima_linha).upper()
        
        logger.info(f"Última linha (identificação): {texto_ultima_linha[:100]}")
        
        # Verificar qual tipo de curso
        for palavra_chave, nome_curso in MAPEAMENTO_CURSOS.items():
            if palavra_chave in texto_ultima_linha:
                logger.info(f"  ✓ Curso identificado: {nome_curso}")
                return nome_curso
        
        logger.warning(f"  ⚠ Curso não identificado na última linha")
        return 'Desconhecido'
    
    def extrair_periodo_ingresso(self, matricula):
        """
        Extrai o período de ingresso do aluno pelos 3 primeiros dígitos da matrícula
        
        Ex: 225XXXXXX -> 2° semestre de 2025
        Ex: 214XXXXXX -> 1° semestre de 2021
        
        Args:
            matricula: String da matrícula
            
        Returns:
            Dict com ano e semestre ou None
        """
        
        if not matricula or len(str(matricula)) < 3:
            return None
        
        matricula_str = str(matricula).strip()
        
        try:
            primeiro_digito = int(matricula_str[0])  # Semestre (1 ou 2)
            dois_ultimos = int(matricula_str[1:3])   # Últimos 2 dígitos do ano
            
            # Construir ano completo (2000 + 2 dígitos)
            ano_completo = 2000 + dois_ultimos
            
            if primeiro_digito not in [1, 2]:
                return None
            
            return {
                'ano': ano_completo,
                'semestre': primeiro_digito,
                'periodo': f"{ano_completo}.{primeiro_digito}"
            }
            
        except (ValueError, IndexError):
            return None
    
    def identificar_modalidade_ingresso(self, matricula):
        """
        Identifica a modalidade de ingresso pelo primeiro caractere
        
        A = Ampla Concorrência (AC)
        L = Ações Afirmativas (AA)
        
        Args:
            matricula: String da matrícula
            
        Returns:
            'AC' ou 'AA'
        """
        
        if not matricula:
            return 'Desconhecido'
        
        primeiro_char = str(matricula)[0].upper()
        
        if primeiro_char == 'A':
            return 'AC'
        elif primeiro_char == 'L':
            return 'AA'
        else:
            return 'Desconhecido'
    
    def extrair_status_aluno(self, texto_status):
        """
        Normaliza o status do aluno
        
        Args:
            texto_status: Texto do status no relatório
            
        Returns:
            Status normalizado
        """
        
        if not texto_status:
            return 'Desconhecido'
        
        texto = str(texto_status).upper().strip()
        
        for chave, valor in STATUS_VALIDOS.items():
            if chave in texto:
                return valor
        
        return texto
    
    def processar_relatorio(self, caminho_arquivo):
        """
        Processa um arquivo de relatório completo
        
        Args:
            caminho_arquivo: Caminho do arquivo .xlsx
            
        Returns:
            Dict com dados processados ou None
        """
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processando relatório: {os.path.basename(caminho_arquivo)}")
        logger.info(f"{'='*60}")
        
        # Carregar dados
        df = self.carregar_relatorio(caminho_arquivo)
        if df is None or len(df) == 0:
            return None
        
        # Remover última linha (contém informação do curso)
        df_dados = df.iloc[:-1].copy()
        
        if len(df_dados) == 0:
            logger.warning("Nenhum dado de aluno encontrado")
            return None
        
        # Identificar curso
        curso = self.identificar_curso(df)
        
        # Processar cada aluno
        alunos_processados = []
        
        for idx, row in df_dados.iterrows():
            try:
                # Extrair informações
                matricula = str(row.iloc[0]) if len(row) > 0 else None
                nome = str(row.iloc[1]) if len(row) > 1 else 'Desconhecido'
                status_original = str(row.iloc[2]) if len(row) > 2 else 'Desconhecido'
                motivo = str(row.iloc[3]) if len(row) > 3 else None
                
                # Normalizar dados
                periodo_ingresso = self.extrair_periodo_ingresso(matricula)
                modalidade = self.identificar_modalidade_ingresso(matricula)
                status = self.extrair_status_aluno(status_original)
                
                aluno = {
                    'matricula': matricula,
                    'nome': nome,
                    'curso': curso,
                    'status': status,
                    'modalidade': modalidade,
                    'periodo_ingresso': periodo_ingresso.get('periodo') if periodo_ingresso else 'Desconhecido',
                    'ano_ingresso': periodo_ingresso.get('ano') if periodo_ingresso else None,
                    'semestre_ingresso': periodo_ingresso.get('semestre') if periodo_ingresso else None,
                    'motivo_cancelamento': motivo if status == 'Cancelado' else None,
                    'status_original': status_original
                }
                
                alunos_processados.append(aluno)
                
            except Exception as e:
                logger.warning(f"Erro ao processar linha {idx}: {str(e)}")
                continue
        
        logger.info(f"  ✓ {len(alunos_processados)} alunos processados")
        
        return {
            'curso': curso,
            'arquivo': caminho_arquivo,
            'alunos': alunos_processados
        }
    
    def consolidar_dados(self, lista_arquivos):
        """
        Consolida dados de múltiplos relatórios
        
        Args:
            lista_arquivos: Lista com caminhos dos arquivos
            
        Returns:
            DataFrame consolidado
        """
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Consolidando {len(lista_arquivos)} relatórios")
        logger.info(f"{'='*60}")
        
        todos_alunos = []
        
        for arquivo in lista_arquivos:
            if not os.path.exists(arquivo):
                logger.warning(f"Arquivo não encontrado: {arquivo}")
                continue
            
            resultado = self.processar_relatorio(arquivo)
            
            if resultado and resultado['alunos']:
                todos_alunos.extend(resultado['alunos'])
        
        if not todos_alunos:
            logger.error("Nenhum dado foi processado!")
            return None
        
        df_consolidado = pd.DataFrame(todos_alunos)
        
        logger.info(f"\n✓ Total de alunos consolidados: {len(df_consolidado)}")
        logger.info(f"  Cursos: {df_consolidado['curso'].unique().tolist()}")
        logger.info(f"  Status: {df_consolidado['status'].unique().tolist()}")
        
        return df_consolidado
    
    def gerar_planilha_evasao(self, df_consolidado, caminho_saida):
        """
        Gera a planilha consolidada de análise de evasão
        
        Args:
            df_consolidado: DataFrame consolidado
            caminho_saida: Caminho para salvar o arquivo
        """
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Gerando planilha consolidada: {caminho_saida}")
        logger.info(f"{'='*60}")
        
        try:
            with pd.ExcelWriter(caminho_saida, engine='openpyxl') as writer:
                
                # ABA 1: RESUMO GERAL
                self._gerar_aba_resumo_geral(df_consolidado, writer)
                
                # ABA 2: DETALHES POR MODALIDADE
                self._gerar_aba_detalhes_modalidade(df_consolidado, writer)
                
                # ABA 3: ANÁLISE CANCELAMENTOS
                self._gerar_aba_cancelamentos(df_consolidado, writer)
                
                # ABA 4: DADOS BRUTOS
                df_consolidado.to_excel(writer, sheet_name='Dados Brutos', index=False)
            
            logger.info(f"✅ Planilha gerada com sucesso!")
            logger.info(f"   Arquivo: {caminho_saida}")
            
        except Exception as e:
            logger.error(f"Erro ao gerar planilha: {str(e)}")
    
    def _gerar_aba_resumo_geral(self, df, writer):
        """Gera aba de Resumo Geral"""
        
        resumo = []
        
        # Agrupar por curso
        for curso in df['curso'].unique():
            df_curso = df[df['curso'] == curso]
            
            total = len(df_curso)
            ativos = len(df_curso[df_curso['status'] == 'Ativo'])
            cancelados = len(df_curso[df_curso['status'] == 'Cancelado'])
            trancados = len(df_curso[df_curso['status'] == 'Trancado'])
            formados = len(df_curso[df_curso['status'] == 'Formado'])
            
            taxa_evasao = (cancelados / total * 100) if total > 0 else 0
            
            resumo.append({
                'Curso': curso,
                'Total de Alunos': total,
                'Ativos': ativos,
                'Cancelados': cancelados,
                'Trancados': trancados,
                'Formados': formados,
                'Taxa de Evasão (%)': f"{taxa_evasao:.2f}%"
            })
        
        # Total geral
        total_geral = len(df)
        cancelados_total = len(df[df['status'] == 'Cancelado'])
        taxa_geral = (cancelados_total / total_geral * 100) if total_geral > 0 else 0
        
        resumo.append({
            'Curso': 'TOTAL GERAL',
            'Total de Alunos': total_geral,
            'Ativos': len(df[df['status'] == 'Ativo']),
            'Cancelados': cancelados_total,
            'Trancados': len(df[df['status'] == 'Trancado']),
            'Formados': len(df[df['status'] == 'Formado']),
            'Taxa de Evasão (%)': f"{taxa_geral:.2f}%"
        })
        
        df_resumo = pd.DataFrame(resumo)
        df_resumo.to_excel(writer, sheet_name='Resumo Geral', index=False)
    
    def _gerar_aba_detalhes_modalidade(self, df, writer):
        """Gera aba de Detalhes por Modalidade de Ingresso"""
        
        detalhes = []
        
        for curso in df['curso'].unique():
            for modalidade in df['modalidade'].unique():
                if modalidade == 'Desconhecido':
                    continue
                
                df_filtrado = df[(df['curso'] == curso) & (df['modalidade'] == modalidade)]
                
                if len(df_filtrado) == 0:
                    continue
                
                total = len(df_filtrado)
                cancelados = len(df_filtrado[df_filtrado['status'] == 'Cancelado'])
                taxa = (cancelados / total * 100) if total > 0 else 0
                
                detalhes.append({
                    'Curso': curso,
                    'Modalidade': modalidade,
                    'Total': total,
                    'Cancelados': cancelados,
                    'Taxa Evasão (%)': f"{taxa:.2f}%",
                    'Ativos': len(df_filtrado[df_filtrado['status'] == 'Ativo']),
                    'Trancados': len(df_filtrado[df_filtrado['status'] == 'Trancado']),
                    'Formados': len(df_filtrado[df_filtrado['status'] == 'Formado'])
                })
        
        df_detalhes = pd.DataFrame(detalhes)
        df_detalhes.to_excel(writer, sheet_name='Detalhes Modalidade', index=False)
    
    def _gerar_aba_cancelamentos(self, df, writer):
        """Gera aba de Análise de Cancelamentos"""
        
        cancelamentos = []
        
        df_cancelados = df[df['status'] == 'Cancelado'].copy()
        
        for curso in df_cancelados['curso'].unique():
            df_curso = df_cancelados[df_cancelados['curso'] == curso]
            
            motivos_contagem = df_curso['motivo_cancelamento'].fillna('Não Informado').value_counts()
            
            total_curso = len(df_curso)
            
            for motivo, contagem in motivos_contagem.items():
                percentual = (contagem / total_curso * 100) if total_curso > 0 else 0
                
                cancelamentos.append({
                    'Curso': curso,
                    'Motivo': motivo,
                    'Quantidade': contagem,
                    'Percentual (%)': f"{percentual:.2f}%"
                })
        
        df_cancelamentos = pd.DataFrame(cancelamentos)
        df_cancelamentos.to_excel(writer, sheet_name='Cancelamentos', index=False)


def main():
    """Função principal - processa dados e gera planilha"""
    
    print("\n" + "="*60)
    print("PROCESSADOR DE DADOS - UFF QUÍMICA")
    print("="*60)
    
    # Carregar lista de arquivos gerada pelo script anterior
    if not os.path.exists('arquivos_relatorios.txt'):
        print("\n❌ Arquivo 'arquivos_relatorios.txt' não encontrado!")
        print("   Execute primeiro: python 1_gerar_relatorios.py")
        return
    
    with open('arquivos_relatorios.txt', 'r') as f:
        lista_arquivos = [linha.strip() for linha in f if linha.strip()]
    
    if not lista_arquivos:
        print("\n❌ Nenhum arquivo encontrado!")
        return
    
    print(f"\n✓ {len(lista_arquivos)} arquivo(s) encontrado(s):")
    for arquivo in lista_arquivos:
        print(f"  - {arquivo}")
    
    # Processar dados
    processador = ProcessadorDados()
    df_consolidado = processador.consolidar_dados(lista_arquivos)
    
    if df_consolidado is None:
        print("\n❌ Erro ao processar dados")
        return
    
    # Gerar planilha
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_saida = f"Relatorio_Evasao_Quimica_{timestamp}.xlsx"
    
    processador.gerar_planilha_evasao(df_consolidado, arquivo_saida)
    
    print(f"\n{'='*60}")
    print(f"✅ PROCESSO CONCLUÍDO!")
    print(f"{'='*60}")
    print(f"\nArquivo gerado: {arquivo_saida}")
    print(f"Diretório: {os.path.abspath(arquivo_saida)}")


if __name__ == "__main__":
    main()
