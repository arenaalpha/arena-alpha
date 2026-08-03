import os
import sqlite3
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
BANCO = Path(os.environ.get("DATABASE_PATH", RAIZ_PROJETO / "arena_alpha.db"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USAR_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))


class ResultadoPostgres:
    def __init__(self, cursor, lastrowid=None):
        self.cursor, self.lastrowid, self.rowcount = cursor, lastrowid, cursor.rowcount
    def fetchone(self): return self.cursor.fetchone()
    def fetchall(self): return self.cursor.fetchall()


class ConexaoPostgres:
    def __init__(self):
        import psycopg2
        from psycopg2.extras import DictCursor
        self.driver, self.cursor_factory = psycopg2, DictCursor
        self.conexao = psycopg2.connect(DATABASE_URL, sslmode="require")
    def execute(self, sql, parametros=()):
        cursor = self.conexao.cursor(cursor_factory=self.cursor_factory)
        cursor.execute(sql.replace("?", "%s"), parametros)
        identificador = None
        if sql.lstrip().upper().startswith("INSERT"):
            sequencia = self.conexao.cursor()
            try:
                sequencia.execute("SELECT LASTVAL()")
                identificador = sequencia.fetchone()[0]
            except self.driver.Error:
                pass
            finally:
                sequencia.close()
        return ResultadoPostgres(cursor, identificador)
    def __enter__(self): return self
    def __exit__(self, tipo, valor, rastreio):
        (self.conexao.commit if tipo is None else self.conexao.rollback)()
        self.conexao.close()


def conectar():
    if USAR_POSTGRES:
        return ConexaoPostgres()
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_tabelas():
    if USAR_POSTGRES:
        return _criar_postgres()
    return _criar_sqlite()


def _criar_postgres():
    tabelas = (
        "CREATE TABLE IF NOT EXISTS alunos (id SERIAL PRIMARY KEY,nome TEXT NOT NULL,telefone TEXT,modalidade TEXT,data_nascimento TEXT,cpf TEXT,endereco TEXT,esporte TEXT,frequencia TEXT,valor_plano REAL,como_conheceu TEXT,restricoes_alimentares TEXT,problema_saude TEXT,necessidades_especiais TEXT,menor_idade TEXT,responsavel_nome TEXT,responsavel_cpf TEXT,responsavel_parentesco TEXT,autorizacao_imagem TEXT,data_inscricao TEXT,dia_vencimento INTEGER,dia_semana TEXT,whatsapp TEXT)",
        "CREATE TABLE IF NOT EXISTS professores (id SERIAL PRIMARY KEY,nome TEXT NOT NULL,telefone TEXT,especialidade TEXT)",
        "CREATE TABLE IF NOT EXISTS quadras (id SERIAL PRIMARY KEY,nome TEXT NOT NULL,modalidade TEXT)",
        "CREATE TABLE IF NOT EXISTS turmas (id SERIAL PRIMARY KEY,nome TEXT NOT NULL,horario TEXT,professor TEXT,modalidade TEXT,dia_semana TEXT,dia_semana_2 TEXT,status_aula TEXT DEFAULT 'Normal',aviso_aula TEXT)",
        "CREATE TABLE IF NOT EXISTS agenda (id SERIAL PRIMARY KEY,quadra TEXT NOT NULL,data TEXT NOT NULL,horario TEXT NOT NULL,cliente TEXT NOT NULL,tipo_locacao TEXT,duracao_horas INTEGER,valor REAL,whatsapp TEXT)",
        "CREATE TABLE IF NOT EXISTS pagamentos (id SERIAL PRIMARY KEY,aluno TEXT NOT NULL,valor REAL NOT NULL,data TEXT NOT NULL,aluno_id INTEGER,data_vencimento TEXT,valor_original REAL,desconto REAL,pago_em TEXT,status TEXT)",
        "CREATE TABLE IF NOT EXISTS torneios (id SERIAL PRIMARY KEY,nome TEXT NOT NULL,data TEXT,modalidade TEXT)",
        "CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY,valor TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS despesas (id SERIAL PRIMARY KEY,descricao TEXT NOT NULL,categoria TEXT NOT NULL,valor REAL NOT NULL,data TEXT NOT NULL,observacao TEXT)",
        "CREATE TABLE IF NOT EXISTS matriculas_turma (id SERIAL PRIMARY KEY,aluno_id INTEGER NOT NULL,turma_id INTEGER NOT NULL,dia_treino TEXT,UNIQUE(aluno_id,turma_id))",
        "CREATE TABLE IF NOT EXISTS presencas (id SERIAL PRIMARY KEY,matricula_id INTEGER NOT NULL,data TEXT NOT NULL,UNIQUE(matricula_id,data))",
        "CREATE TABLE IF NOT EXISTS aulas_experimentais (id SERIAL PRIMARY KEY,nome TEXT NOT NULL,telefone TEXT NOT NULL,esporte TEXT NOT NULL,data TEXT NOT NULL,horario TEXT,confirmacao_enviada INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS portal_acessos (aluno_id INTEGER PRIMARY KEY,ultimo_acesso TEXT)",
    )
    with conectar() as banco:
        for sql in tabelas: banco.execute(sql)
        if banco.execute("SELECT COUNT(*) AS quantidade FROM quadras").fetchone()["quantidade"] == 0:
            banco.execute("INSERT INTO quadras (nome, modalidade) VALUES (?, ?)", ("Quadra Principal", "Arena Alpha"))


def _criar_sqlite():
    tabelas = (
        "CREATE TABLE IF NOT EXISTS alunos (id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,telefone TEXT,modalidade TEXT)",
        "CREATE TABLE IF NOT EXISTS professores (id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,telefone TEXT,especialidade TEXT)",
        "CREATE TABLE IF NOT EXISTS quadras (id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,modalidade TEXT)",
        "CREATE TABLE IF NOT EXISTS turmas (id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,horario TEXT,professor TEXT,modalidade TEXT)",
        "CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY AUTOINCREMENT,quadra TEXT NOT NULL,data TEXT NOT NULL,horario TEXT NOT NULL,cliente TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS pagamentos (id INTEGER PRIMARY KEY AUTOINCREMENT,aluno TEXT NOT NULL,valor REAL NOT NULL,data TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS torneios (id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,data TEXT,modalidade TEXT)",
        "CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY,valor TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS despesas (id INTEGER PRIMARY KEY AUTOINCREMENT,descricao TEXT NOT NULL,categoria TEXT NOT NULL,valor REAL NOT NULL,data TEXT NOT NULL,observacao TEXT)",
        "CREATE TABLE IF NOT EXISTS matriculas_turma (id INTEGER PRIMARY KEY AUTOINCREMENT,aluno_id INTEGER NOT NULL,turma_id INTEGER NOT NULL,dia_treino TEXT,UNIQUE(aluno_id,turma_id))",
        "CREATE TABLE IF NOT EXISTS presencas (id INTEGER PRIMARY KEY AUTOINCREMENT,matricula_id INTEGER NOT NULL,data TEXT NOT NULL,UNIQUE(matricula_id,data))",
        "CREATE TABLE IF NOT EXISTS aulas_experimentais (id INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,telefone TEXT NOT NULL,esporte TEXT NOT NULL,data TEXT NOT NULL,horario TEXT,confirmacao_enviada INTEGER DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS portal_acessos (aluno_id INTEGER PRIMARY KEY,ultimo_acesso TEXT)",
    )
    with conectar() as banco:
        for sql in tabelas: banco.execute(sql)
        existentes = {linha["name"] for linha in banco.execute("PRAGMA table_info(alunos)").fetchall()}
        alunos = {"data_nascimento":"TEXT","cpf":"TEXT","endereco":"TEXT","esporte":"TEXT","frequencia":"TEXT","valor_plano":"REAL","como_conheceu":"TEXT","restricoes_alimentares":"TEXT","problema_saude":"TEXT","necessidades_especiais":"TEXT","menor_idade":"TEXT","responsavel_nome":"TEXT","responsavel_cpf":"TEXT","responsavel_parentesco":"TEXT","autorizacao_imagem":"TEXT","data_inscricao":"TEXT","dia_vencimento":"INTEGER","dia_semana":"TEXT","whatsapp":"TEXT"}
        for nome, tipo in alunos.items():
            if nome not in existentes: banco.execute(f"ALTER TABLE alunos ADD COLUMN {nome} {tipo}")
        for tabela, colunas in (("turmas", {"dia_semana":"TEXT","dia_semana_2":"TEXT","status_aula":"TEXT DEFAULT 'Normal'","aviso_aula":"TEXT"}), ("agenda", {"tipo_locacao":"TEXT","duracao_horas":"INTEGER","valor":"REAL","whatsapp":"TEXT"}), ("pagamentos", {"aluno_id":"INTEGER","data_vencimento":"TEXT","valor_original":"REAL","desconto":"REAL","pago_em":"TEXT","status":"TEXT"})):
            existentes = {linha["name"] for linha in banco.execute(f"PRAGMA table_info({tabela})").fetchall()}
            for nome, tipo in colunas.items():
                if nome not in existentes: banco.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")
        if banco.execute("SELECT COUNT(*) FROM quadras").fetchone()[0] == 0:
            banco.execute("INSERT INTO quadras (nome, modalidade) VALUES (?, ?)", ("Quadra Principal", "Arena Alpha"))
