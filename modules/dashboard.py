import customtkinter as ctk


class Dashboard(ctk.CTkScrollableFrame):
    """Painel inicial com indicadores da arena."""

    CORES = ("#FFFCF5", "#1D1D1D")
    DESTAQUES = ("#C48818", "#C7C9CC", "#E6B94F", "#8F9499")

    def __init__(self, master, indicadores, ocupacoes):
        super().__init__(master, fg_color="transparent")
        cabecalho = ctk.CTkFrame(self, fg_color=("#F3E4BE", "#28231A"), corner_radius=18)
        cabecalho.pack(fill="x", pady=(4, 22))
        ctk.CTkLabel(cabecalho, text="Visao geral", font=("Segoe UI", 27, "bold"), text_color=("#261C0C", "#F8E9BD")).pack(anchor="w", padx=28, pady=(22, 2))
        ctk.CTkLabel(cabecalho, text="Acompanhe os principais numeros da sua arena.", font=("Segoe UI", 14), text_color=("#70551D", "#C7C9CC")).pack(anchor="w", padx=28, pady=(0, 22))

        ctk.CTkLabel(self, text="Calendario da quadra", font=("Segoe UI", 20, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(self, text="Turmas e reservas da semana. Cada item representa um horario ocupado.", font=("Segoe UI", 12), text_color=("#5B7280", "#B6D6E8")).pack(anchor="w", pady=(0, 8))
        calendario = ctk.CTkFrame(self, fg_color="transparent")
        calendario.pack(fill="x", pady=(0, 18))
        for coluna in range(7):
            calendario.grid_columnconfigure(coluna, weight=1, uniform="dias")
        for indice, dia in enumerate(ocupacoes):
            cartao = ctk.CTkFrame(calendario, fg_color=("#FFFFFF", "#163B52"), corner_radius=12, border_width=1, border_color=("#D9E4EB", "#28546B"))
            cartao.grid(row=0, column=indice, sticky="nsew", padx=3)
            ctk.CTkLabel(cartao, text=dia["semana"].upper(), font=("Segoe UI", 10, "bold"), text_color="#0E7490").pack(pady=(10, 0))
            ctk.CTkLabel(cartao, text=dia["data"], font=("Segoe UI", 14, "bold"), text_color=("#123147", "#F1FAFE")).pack(pady=(0, 7))
            for item in (dia["itens"] or ["Livre"]):
                cor = ("#E0F2FE", "#17435B") if item != "Livre" else ("#F1F5F9", "#244454")
                ctk.CTkLabel(cartao, text=item, font=("Segoe UI", 10), wraplength=105, justify="left", fg_color=cor, corner_radius=7, text_color=("#285064", "#DDF4FD")).pack(fill="x", padx=7, pady=(0, 6))

        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x")
        for coluna in range(2):
            cards.grid_columnconfigure(coluna, weight=1)

        for indice, (titulo, valor, detalhe) in enumerate(indicadores):
            card = ctk.CTkFrame(cards, fg_color=self.CORES, corner_radius=16, border_width=1, border_color=("#D8C9A4", "#454545"))
            card.grid(row=indice // 2, column=indice % 2, sticky="nsew", padx=7, pady=7)
            faixa = ctk.CTkFrame(card, width=6, height=86, fg_color=self.DESTAQUES[indice], corner_radius=8)
            faixa.pack(side="left", fill="y", padx=(13, 15), pady=15)
            textos = ctk.CTkFrame(card, fg_color="transparent")
            textos.pack(side="left", fill="both", expand=True, pady=15)
            ctk.CTkLabel(textos, text=titulo.upper(), font=("Segoe UI", 12, "bold"), text_color=("#70551D", "#C7C9CC")).pack(anchor="w")
            ctk.CTkLabel(textos, text=valor, font=("Segoe UI", 25, "bold"), text_color=("#241B0E", "#FFF6DE")).pack(anchor="w", pady=(2, 0))
            ctk.CTkLabel(textos, text=detalhe, font=("Segoe UI", 12), text_color=("#7C7160", "#B9B9B9")).pack(anchor="w")

        aviso = ctk.CTkFrame(self, fg_color=("#FFFFFF", "#163B52"), corner_radius=16)
        aviso.pack(fill="x", pady=(22, 0))
        ctk.CTkLabel(aviso, text="Proximo passo", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=22, pady=(18, 2))
        ctk.CTkLabel(aviso, text="Use o menu ao lado para cadastrar alunos, organizar horarios e registrar pagamentos.", font=("Segoe UI", 13), text_color=("#5B7280", "#B6D6E8"), wraplength=600, justify="left").pack(anchor="w", padx=22, pady=(0, 18))
