from database.banco import conectar


class Modalidades:
    def listar(self):
        with conectar() as banco:
            return banco.execute("SELECT id, nome FROM modalidades ORDER BY nome").fetchall()

    def criar(self, nome):
        nome = (nome or "").strip()
        if len(nome) < 3:
            raise ValueError("Digite um nome de modalidade com pelo menos 3 letras.")
        try:
            with conectar() as banco:
                banco.execute("INSERT INTO modalidades (nome) VALUES (?)", (nome,))
        except Exception as erro:
            if "UNIQUE" in str(erro).upper() or "DUPLICATE" in str(erro).upper():
                raise ValueError("Esta modalidade já existe.")
            raise

    def excluir(self, identificador):
        with conectar() as banco:
            modalidade = banco.execute("SELECT nome FROM modalidades WHERE id = ?", (identificador,)).fetchone()
            if modalidade is None:
                raise ValueError("Modalidade não encontrada.")
            vinculadas = banco.execute("SELECT COUNT(*) AS quantidade FROM turmas WHERE modalidade = ?", (modalidade["nome"],)).fetchone()["quantidade"]
            if vinculadas:
                raise ValueError("Não é possível excluir esta modalidade porque ela está sendo usada por uma turma.")
            banco.execute("DELETE FROM modalidades WHERE id = ?", (identificador,))
