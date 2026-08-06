import re
import webbrowser
from urllib.parse import quote
from database.banco import normalizar_telefone_brasil


class WhatsApp:
    @staticmethod
    def link(numero, mensagem):
        numero = normalizar_telefone_brasil(numero)
        if len(numero) < 12:
            raise ValueError("Informe um WhatsApp valido com DDD.")
        return f"https://wa.me/{numero}?text={quote(mensagem)}"

    def abrir_mensagem(self, numero, mensagem):
        endereco = self.link(numero, mensagem)
        webbrowser.open_new_tab(endereco)
        return endereco
