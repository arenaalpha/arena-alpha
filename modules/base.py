from database.banco import conectar


class Repositorio:
    tabela = ""
    campos = ()

    def cadastrar(self, **dados):
        valores = tuple(dados[campo] for campo in self.campos)
        colunas = ", ".join(self.campos)
        marcadores = ", ".join("?" for _ in self.campos)
        with conectar() as banco:
            resultado = banco.execute(
                f"INSERT INTO {self.tabela} ({colunas}) VALUES ({marcadores})", valores
            )
        return resultado.lastrowid

    def listar(self):
        with conectar() as banco:
            return banco.execute(f"SELECT * FROM {self.tabela} ORDER BY id DESC").fetchall()

    def excluir(self, identificador):
        with conectar() as banco:
            resultado = banco.execute(
                f"DELETE FROM {self.tabela} WHERE id = ?", (identificador,)
            )
        if resultado.rowcount == 0:
            raise ValueError("Registro nao encontrado.")
