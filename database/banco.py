import os
import sqlite3
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parent.parent
BANCO = Path(os.environ.get("DATABASE_PATH", RAIZ_PROJETO / "arena_alpha.db"))


def conectar() -> sqlite3.Connection:
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_tabelas() -> None:
    tabelas = (
        """CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            telefone TEXT, modalidade TEXT)""",
        """CREATE TABLE IF NOT EXISTS professores (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            telefone TEXT, especialidade TEXT)""",
        """CREATE TABLE IF NOT EXISTS quadras (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            modalidade TEXT)""",
        """CREATE TABLE IF NOT EXISTS turmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            horario TEXT, professor TEXT, modalidade TEXT)""",
        """CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT, quadra TEXT NOT NULL,
            data TEXT NOT NULL, horario TEXT NOT NULL, cliente TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS pagamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, aluno TEXT NOT NULL,
            valor REAL NOT NULL, data TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS torneios (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            data TEXT, modalidade TEXT)""",
        """CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY, valor TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS despesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, descricao TEXT NOT NULL,
            categoria TEXT NOT NULL, valor REAL NOT NULL, data TEXT NOT NULL,
            observacao TEXT)""",
        """CREATE TABLE IF NOT EXISTS matriculas_turma (
            id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_id INTEGER NOT NULL,
            turma_id INTEGER NOT NULL, dia_treino TEXT,
            UNIQUE(aluno_id, turma_id))""",
        """CREATE TABLE IF NOT EXISTS presencas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, matricula_id INTEGER NOT NULL,
            data TEXT NOT NULL, UNIQUE(matricula_id, data))""",
        """CREATE TABLE IF NOT EXISTS aulas_experimentais (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            telefone TEXT NOT NULL, esporte TEXT NOT NULL, data TEXT NOT NULL,
            horario TEXT, confirmacao_enviada INTEGER DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS portal_acessos (
            aluno_id INTEGER PRIMARY KEY, ultimo_acesso TEXT,
            FOREIGN KEY(aluno_id) REFERENCES alunos(id))""",
    )
    with conectar() as banco:
        for comando in tabelas:
            banco.execute(comando)
        colunas_alunos = {
            linha["name"] for linha in banco.execute("PRAGMA table_info(alunos)").fetchall()
        }
        novas_colunas = {
            "data_nascimento": "TEXT",
            "cpf": "TEXT",
            "endereco": "TEXT",
            "esporte": "TEXT",
            "frequencia": "TEXT",
            "valor_plano": "REAL",
            "como_conheceu": "TEXT",
            "restricoes_alimentares": "TEXT",
            "problema_saude": "TEXT",
            "necessidades_especiais": "TEXT",
            "menor_idade": "TEXT",
            "responsavel_nome": "TEXT",
            "responsavel_cpf": "TEXT",
            "responsavel_parentesco": "TEXT",
            "autorizacao_imagem": "TEXT",
            "data_inscricao": "TEXT",
            "dia_vencimento": "INTEGER",
            "dia_semana": "TEXT",
            "whatsapp": "TEXT",
        }
        for nome, tipo in novas_colunas.items():
            if nome not in colunas_alunos:
                banco.execute(f"ALTER TABLE alunos ADD COLUMN {nome} {tipo}")

        colunas_turmas = {
            linha["name"] for linha in banco.execute("PRAGMA table_info(turmas)").fetchall()
        }
        if "dia_semana" not in colunas_turmas:
            banco.execute("ALTER TABLE turmas ADD COLUMN dia_semana TEXT")
        if "dia_semana_2" not in colunas_turmas:
            banco.execute("ALTER TABLE turmas ADD COLUMN dia_semana_2 TEXT")
        if "status_aula" not in colunas_turmas:
            banco.execute("ALTER TABLE turmas ADD COLUMN status_aula TEXT DEFAULT 'Normal'")
        if "aviso_aula" not in colunas_turmas:
            banco.execute("ALTER TABLE turmas ADD COLUMN aviso_aula TEXT")

        colunas_agenda = {
            linha["name"] for linha in banco.execute("PRAGMA table_info(agenda)").fetchall()
        }
        novas_colunas_agenda = {
            "tipo_locacao": "TEXT",
            "duracao_horas": "INTEGER",
            "valor": "REAL",
            "whatsapp": "TEXT",
        }
        for nome, tipo in novas_colunas_agenda.items():
            if nome not in colunas_agenda:
                banco.execute(f"ALTER TABLE agenda ADD COLUMN {nome} {tipo}")

        colunas_pagamentos = {
            linha["name"] for linha in banco.execute("PRAGMA table_info(pagamentos)").fetchall()
        }
        novas_colunas_pagamentos = {
            "aluno_id": "INTEGER",
            "data_vencimento": "TEXT",
            "valor_original": "REAL",
            "desconto": "REAL",
            "pago_em": "TEXT",
            "status": "TEXT",
        }
        for nome, tipo in novas_colunas_pagamentos.items():
            if nome not in colunas_pagamentos:
                banco.execute(f"ALTER TABLE pagamentos ADD COLUMN {nome} {tipo}")
        quantidade_quadras = banco.execute("SELECT COUNT(*) FROM quadras").fetchone()[0]
        if quantidade_quadras == 0:
            banco.execute(
                "INSERT INTO quadras (nome, modalidade) VALUES (?, ?)",
                ("Quadra Principal", "Arena Alpha"),
            )
