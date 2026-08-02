class Ranking:
    def calcular_posicao(self, pontos):
        if pontos >= 1000:
            return "🥇 Ouro"
        if pontos >= 500:
            return "🥈 Prata"
        return "🥉 Bronze"
