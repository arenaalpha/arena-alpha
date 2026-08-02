import os


class AlphaAI:
    def __init__(self, chave=None):
        from openai import OpenAI
        self.client = OpenAI(api_key=chave or os.getenv("OPENAI_API_KEY"))

    def perguntar(self, texto):
        resposta = self.client.responses.create(
            model="gpt-5-mini",
            instructions="Você é o assistente da Arena Alpha.",
            input=texto,
        )
        return resposta.output_text
