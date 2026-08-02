import hashlib
import hmac
import os

from database.banco import conectar


class Permissoes:
    """Controle local da senha usada nas operacoes de exclusao."""

    CHAVE = "senha_administrador"

    def tem_senha(self):
        with conectar() as banco:
            return banco.execute(
                "SELECT 1 FROM configuracoes WHERE chave = ?", (self.CHAVE,)
            ).fetchone() is not None

    def definir_senha(self, senha):
        if len(senha) < 4:
            raise ValueError("A senha deve ter pelo menos 4 caracteres.")
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 200_000)
        valor = f"{salt.hex()}:{digest.hex()}"
        with conectar() as banco:
            banco.execute(
                "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)",
                (self.CHAVE, valor),
            )

    def autorizar(self, senha):
        with conectar() as banco:
            registro = banco.execute(
                "SELECT valor FROM configuracoes WHERE chave = ?", (self.CHAVE,)
            ).fetchone()
        if registro is None:
            return False
        salt_hex, digest_hex = registro["valor"].split(":", 1)
        tentativa = hashlib.pbkdf2_hmac(
            "sha256", senha.encode("utf-8"), bytes.fromhex(salt_hex), 200_000
        ).hex()
        return hmac.compare_digest(tentativa, digest_hex)
