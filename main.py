import customtkinter as ctk
from tkinter import messagebox, simpledialog
from datetime import date, datetime, timedelta
import calendar
from pathlib import Path
from PIL import Image, ImageOps

from database.banco import criar_tabelas
from modules.agenda import Agenda
from modules.aulas_experimentais import AulasExperimentais
from modules.alunos import Alunos
from modules.backup import Backup
from modules.dashboard import Dashboard
from modules.financeiro import Financeiro
from modules.modalidades import Modalidades
from modules.pagamentos import Pagamentos
from modules.permissoes import Permissoes
from modules.professores import Professores
from modules.quadras import Quadras
from modules.relatorios import Relatorios
from modules.turmas import Turmas
from modules.whatsapp import WhatsApp


class ArenaAlpha(ctk.CTk):
    FUNDO = "#F4F0E7"
    PRIMARIA = "#B7790B"
    SIDEBAR = "#111111"
    DOURADO_CLARO = "#E6B94F"
    PRATA = "#C7C9CC"

    def __init__(self):
        super().__init__()
        criar_tabelas()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.title("Arena Alpha | Gestao esportiva")
        self.geometry("1120x700")
        self.minsize(900, 560)
        self.configure(fg_color=self.FUNDO)
        self._carregar_imagens()
        self._montar_layout()
        self.mostrar_dashboard()

    def _carregar_imagens(self):
        caminho_logo = Path(__file__).resolve().parent / "assets" / "arena_alpha_logo.jpeg"
        imagem = Image.open(caminho_logo).convert("RGB")
        self.logo = ctk.CTkImage(light_image=imagem, dark_image=imagem, size=(165, 165))
        fundo = ImageOps.fit(imagem, (900, 700), method=Image.Resampling.LANCZOS)
        base = Image.new("RGB", fundo.size, "#F4F0E7")
        fundo_suave = Image.blend(base, fundo, 0.075)
        self.imagem_fundo = ctk.CTkImage(light_image=fundo_suave, dark_image=fundo_suave, size=(900, 700))
        self.fundo_visual = ctk.CTkLabel(self, image=self.imagem_fundo, text="", fg_color="transparent")
        self.fundo_visual.place(relx=1.0, rely=0.5, anchor="e")
        self.fundo_visual.lower()

    def _montar_layout(self):
        self.menu = ctk.CTkFrame(self, width=235, corner_radius=0, fg_color=self.SIDEBAR)
        self.menu.pack(side="left", fill="y")
        self.menu.pack_propagate(False)
        marca = ctk.CTkFrame(self.menu, fg_color="transparent")
        marca.pack(fill="x", padx=25, pady=(22, 22))
        ctk.CTkLabel(marca, image=self.logo, text="").pack()
        ctk.CTkLabel(marca, text="GESTAO ESPORTIVA", font=("Segoe UI", 10, "bold"), text_color=self.DOURADO_CLARO).pack(pady=(1, 0))

        opcoes = [
            ("Inicio", self.mostrar_dashboard),
            ("Inscricao de aluno", self.mostrar_inscricao_aluno),
            ("Alunos", self.mostrar_alunos),
            ("Aula experimental", self.mostrar_aula_experimental),
            ("Professores", lambda: self.mostrar_formulario("Professores", "Organize a equipe tecnica.", Professores(), [("Nome completo", "nome"), ("Telefone", "telefone"), ("Especialidade", "especialidade")], "cadastrar")),
            ("Quadra", self.mostrar_quadra),
            ("Turmas", self.mostrar_turmas),
            ("Check-in", self.mostrar_checkin),
            ("Locação do espaço", self.mostrar_locacao),
            ("Pagamentos", self.mostrar_pagamentos),
            ("Financeiro", self.mostrar_financeiro),
            ("WhatsApp", self.mostrar_whatsapp),
            ("Administracao", self.mostrar_administracao),
        ]
        for nome, comando in opcoes:
            ctk.CTkButton(self.menu, text=nome, command=comando, anchor="w", height=38, corner_radius=8, fg_color="transparent", hover_color="#3A2A12", text_color="#F5E7C5", font=("Segoe UI", 14)).pack(fill="x", padx=17, pady=2)
        ctk.CTkButton(self.menu, text="Fazer backup", command=self.criar_backup, height=38, fg_color=self.PRIMARIA, hover_color="#8F5E08", text_color="#16120B", font=("Segoe UI", 13, "bold")).pack(side="bottom", fill="x", padx=22, pady=(5, 28))
        ctk.CTkLabel(self.menu, text="Dados protegidos localmente", font=("Segoe UI", 10), text_color="#B8B8B8").pack(side="bottom", pady=(0, 0))

        area = ctk.CTkFrame(self, fg_color="transparent")
        area.pack(side="right", expand=True, fill="both", padx=32, pady=24)
        topo = ctk.CTkFrame(area, fg_color="transparent", height=42)
        topo.pack(fill="x")
        ctk.CTkLabel(topo, text="PAINEL DE CONTROLE", font=("Segoe UI", 12, "bold"), text_color="#70551D").pack(side="left")
        ctk.CTkLabel(topo, text="ARENA ALPHA", font=("Segoe UI", 14, "bold"), text_color=self.PRIMARIA).pack(side="right")
        self.conteudo = ctk.CTkFrame(area, fg_color="transparent")
        self.conteudo.pack(expand=True, fill="both", pady=(12, 0))

    def limpar(self):
        for filho in self.conteudo.winfo_children():
            filho.destroy()

    def mostrar_dashboard(self):
        self.limpar()
        relatorio = Relatorios()
        indicadores = [
            ("Alunos ativos", str(relatorio.total_alunos()), "cadastros realizados"),
            ("Quadra", "1", "quadra principal"),
            ("Receita", f"R$ {relatorio.total_receita():,.2f}", "pagamentos registrados"),
        ]
        Dashboard(self.conteudo, indicadores, self._ocupacoes_semana()).pack(expand=True, fill="both")

    def _ocupacoes_semana(self):
        hoje = date.today()
        inicio = hoje.fromordinal(hoje.toordinal() - hoje.weekday())
        nomes_dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
        ocupacoes = [
            {"semana": nomes_dias[indice], "data": inicio.fromordinal(inicio.toordinal() + indice).strftime("%d/%m"), "itens": []}
            for indice in range(7)
        ]
        mapa_dias = {
            "segunda": 0, "segunda-feira": 0, "terca": 1, "terça": 1, "terca-feira": 1, "terça-feira": 1,
            "quarta": 2, "quarta-feira": 2, "quinta": 3, "quinta-feira": 3,
            "sexta": 4, "sexta-feira": 4, "sabado": 5, "sábado": 5, "domingo": 6,
        }
        for turma in Turmas().listar():
            for campo_dia in ("dia_semana", "dia_semana_2"):
                indice = mapa_dias.get((turma[campo_dia] or "").strip().lower())
                if indice is not None:
                    ocupacoes[indice]["itens"].append(f"Turma\n{turma['horario']} - {turma['nome']}")
        for reserva in Agenda().listar():
            try:
                data_reserva = datetime.strptime(reserva["data"], "%d/%m/%Y").date()
            except (TypeError, ValueError):
                continue
            indice = (data_reserva - inicio).days
            if 0 <= indice < 7:
                ocupacoes[indice]["itens"].append(f"Reserva\n{reserva['horario']} - {reserva['cliente']}")
        return ocupacoes

    def mostrar_aula_experimental(self):
        self.limpar()
        ctk.CTkLabel(self.conteudo, text="Aula experimental", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="Volei de Areia: aulas experimentais somente as segundas-feiras.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 14))
        tela = ctk.CTkScrollableFrame(self.conteudo, fg_color="transparent")
        tela.pack(fill="both", expand=True)
        formulario = ctk.CTkFrame(tela, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=16)
        formulario.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(formulario, text="Agendar aula", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 10))
        nome = ctk.CTkEntry(formulario, placeholder_text="Nome completo", height=36)
        nome.pack(fill="x", padx=22, pady=(0, 8))
        telefone = ctk.CTkEntry(formulario, placeholder_text="Telefone / WhatsApp (com DDD)", height=36)
        telefone.pack(fill="x", padx=22, pady=(0, 8))
        turmas_experimentais = Turmas().listar()
        mapa_turmas_experimentais = {
            f"{turma['nome']} | {turma['dia_semana']} e {turma['dia_semana_2']} | {turma['horario']}": turma
            for turma in turmas_experimentais
        }
        turma_experimental_var = ctk.StringVar(value="Selecione a turma e horario")
        menu_turma_experimental = ctk.CTkOptionMenu(
            formulario, values=list(mapa_turmas_experimentais) or ["Nenhuma turma cadastrada"],
            variable=turma_experimental_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08"
        )
        menu_turma_experimental.pack(fill="x", padx=22, pady=(0, 8))
        esporte_var = ctk.StringVar(value="Selecione o esporte")
        menu_esporte_experimental = ctk.CTkOptionMenu(formulario, values=["Futvolei", "Volei de areia"], variable=esporte_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08")
        menu_esporte_experimental.pack(fill="x", padx=22, pady=(0, 8))
        data_prevista = ctk.CTkLabel(formulario, text="Selecione a turma para definir a proxima aula disponivel.", font=("Segoe UI", 12), text_color=("#7C7160", "#B9B9B9"), justify="left")
        data_prevista.pack(anchor="w", padx=22, pady=(0, 8))
        horario = ctk.CTkEntry(formulario, placeholder_text="Horario (opcional)", height=36)
        horario.pack(fill="x", padx=22, pady=(0, 10))

        def preencher_horario_turma(valor=None):
            turma = mapa_turmas_experimentais.get(turma_experimental_var.get())
            if turma is None:
                return
            esporte_var.set(turma["modalidade"])
            horario.delete(0, "end")
            horario.insert(0, turma["horario"])
            proxima = proxima_data_turma(turma)
            data_prevista.configure(text=f"Proxima aula disponivel: {proxima:%d/%m/%Y}")

        menu_turma_experimental.configure(command=preencher_horario_turma)

        def proxima_data_turma(turma):
            dias = {"Segunda-feira": 0, "Terca-feira": 1, "Quarta-feira": 2, "Quinta-feira": 3, "Sexta-feira": 4, "Sabado": 5, "Domingo": 6}
            esporte = (turma["modalidade"] or "").lower()
            dias_alvo = [0] if "volei" in esporte and "fut" not in esporte else [dias.get(turma["dia_semana"], 0), dias.get(turma["dia_semana_2"], 0)]
            hoje = date.today()
            diferencas = [(dia - hoje.weekday()) % 7 for dia in dias_alvo]
            return hoje + timedelta(days=min(diferencas))

        def salvar_aula():
            if turma_experimental_var.get() not in mapa_turmas_experimentais:
                messagebox.showwarning("Turma obrigatoria", "Selecione a turma e o horario desejados.")
                return
            if esporte_var.get() == "Selecione o esporte":
                messagebox.showwarning("Esporte obrigatorio", "Selecione o esporte desejado.")
                return
            turma = mapa_turmas_experimentais[turma_experimental_var.get()]
            data_agendada = proxima_data_turma(turma).strftime("%d/%m/%Y")
            try:
                AulasExperimentais().agendar(nome.get(), telefone.get(), esporte_var.get(), data_agendada, horario.get())
            except ValueError as erro:
                messagebox.showerror("Aula nao agendada", str(erro))
                return
            messagebox.showinfo("Aula agendada", "Aula experimental registrada. Use a lista abaixo para enviar a confirmacao pelo WhatsApp.")
            self.mostrar_aula_experimental()

        ctk.CTkButton(formulario, text="Agendar aula experimental", command=salvar_aula, height=40, fg_color=self.PRIMARIA, hover_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 20))
        painel = ctk.CTkFrame(tela, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=16)
        painel.pack(fill="both", expand=True)
        ctk.CTkLabel(painel, text="Agendamentos e confirmacao", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 8))
        aulas = AulasExperimentais().listar()
        mapa_aulas = {
            f"{aula['id']} - {aula['nome']} | {aula['esporte']} | {aula['data']}": aula
            for aula in aulas
        }
        aula_var = ctk.StringVar(value="Selecione um agendamento")
        ctk.CTkOptionMenu(painel, values=list(mapa_aulas) or ["Nenhuma aula agendada"], variable=aula_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 10))

        def confirmar_whatsapp():
            aula = mapa_aulas.get(aula_var.get())
            if aula is None:
                messagebox.showwarning("Agendamento obrigatorio", "Selecione uma aula experimental.")
                return
            data_formatada = datetime.strptime(aula["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
            horario_texto = f" as {aula['horario']}" if aula["horario"] else ""
            mensagem = f"Ola, {aula['nome']}! Sua aula experimental de {aula['esporte']} esta confirmada para {data_formatada}{horario_texto}, na Arena Alpha. Esperamos voce!"
            try:
                WhatsApp().abrir_mensagem(aula["telefone"], mensagem)
            except ValueError as erro:
                messagebox.showerror("WhatsApp invalido", str(erro))
                return
            AulasExperimentais().marcar_confirmacao(aula["id"])
            messagebox.showinfo("WhatsApp aberto", "A mensagem de confirmacao foi aberta no WhatsApp.")
            self.mostrar_aula_experimental()

        ctk.CTkButton(painel, text="Abrir confirmacao no WhatsApp", command=confirmar_whatsapp, height=40, fg_color="#166534", hover_color="#14532D").pack(fill="x", padx=22, pady=(0, 12))
        def resetar_historico_aulas():
            if not aulas:
                messagebox.showinfo("Historico vazio", "Nao ha aulas experimentais para apagar.")
                return
            if messagebox.askyesno("Resetar historico", "Apagar todo o historico de aulas experimentais? Esta acao nao pode ser desfeita."):
                AulasExperimentais().limpar_historico()
                messagebox.showinfo("Historico resetado", "O historico de aulas experimentais foi apagado.")
                self.mostrar_aula_experimental()
        ctk.CTkButton(painel, text="Limpar aulas experimentais", command=resetar_historico_aulas, height=36, fg_color="#B91C1C", hover_color="#991B1B").pack(fill="x", padx=22, pady=(0, 12))
        lista = ctk.CTkTextbox(painel, height=170, font=("Cascadia Mono", 12), fg_color=("#F6F1E7", "#111111"), corner_radius=10)
        lista.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        texto = "Nenhuma aula experimental agendada." if not aulas else "\n\n".join(
            f"{datetime.strptime(aula['data'], '%Y-%m-%d'):%d/%m/%Y} | {aula['horario'] or '-'}\n{aula['nome']} | {aula['telefone']} | {aula['esporte']} | {'CONFIRMADO' if aula['confirmacao_enviada'] else 'PENDENTE'}"
            for aula in aulas
        )
        lista.insert("1.0", texto)
        lista.configure(state="disabled")

    def mostrar_turmas(self):
        self.limpar()
        ctk.CTkLabel(self.conteudo, text="Turmas", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="Cadastre turmas e consulte os alunos vinculados.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 14))
        tela = ctk.CTkScrollableFrame(self.conteudo, fg_color="transparent")
        tela.pack(fill="both", expand=True)
        form = ctk.CTkFrame(tela, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=16)
        form.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(form, text="Nova turma", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(18, 10))
        nome = ctk.CTkEntry(form, placeholder_text="Nome da turma", height=36)
        nome.pack(fill="x", padx=22, pady=(0, 8))
        dias = ["Segunda-feira", "Terca-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sabado", "Domingo"]
        dia_1 = ctk.StringVar(value="Primeiro dia")
        dia_2 = ctk.StringVar(value="Segundo dia")
        ctk.CTkOptionMenu(form, values=dias, variable=dia_1, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 8))
        ctk.CTkOptionMenu(form, values=dias, variable=dia_2, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 8))
        horario = ctk.CTkEntry(form, placeholder_text="Horario (ex.: 18:00 as 19:00)", height=36)
        horario.pack(fill="x", padx=22, pady=(0, 8))
        professor = ctk.CTkEntry(form, placeholder_text="Professor", height=36)
        professor.pack(fill="x", padx=22, pady=(0, 8))
        modalidade = ctk.CTkEntry(form, placeholder_text="Modalidade", height=36)
        modalidade.pack(fill="x", padx=22, pady=(0, 10))

        def salvar_turma():
            if not all([nome.get().strip(), horario.get().strip(), professor.get().strip(), modalidade.get().strip()]) or dia_1.get() not in dias or dia_2.get() not in dias:
                messagebox.showwarning("Campos obrigatorios", "Preencha todos os dados da turma.")
                return
            try:
                Turmas().criar(nome.get().strip(), dia_1.get(), dia_2.get(), horario.get().strip(), professor.get().strip(), modalidade.get().strip())
            except ValueError as erro:
                messagebox.showerror("Turma nao criada", str(erro))
                return
            messagebox.showinfo("Turma criada", "Turma cadastrada com sucesso.")
            self.mostrar_turmas()

        ctk.CTkButton(form, text="Criar turma", command=salvar_turma, height=40, fg_color=self.PRIMARIA, hover_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 20))
        relatorio = ctk.CTkFrame(tela, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=16)
        relatorio.pack(fill="both", expand=True)
        ctk.CTkLabel(relatorio, text="Relatorio de alunos por turma", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(18, 8))
        turmas = Turmas().listar()
        mapa_turmas = {f"{turma['id']} - {turma['nome']} | {turma['horario']}": turma for turma in turmas}
        turma_var = ctk.StringVar(value="Selecione uma turma")
        ctk.CTkOptionMenu(relatorio, values=list(mapa_turmas) or ["Nenhuma turma cadastrada"], variable=turma_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 10))
        lista = ctk.CTkTextbox(relatorio, height=210, font=("Cascadia Mono", 12), fg_color=("#F6F1E7", "#111111"), corner_radius=10)
        lista.pack(fill="both", expand=True, padx=22, pady=(0, 20))

        def carregar_relatorio(valor=None):
            turma = mapa_turmas.get(turma_var.get())
            lista.configure(state="normal")
            lista.delete("1.0", "end")
            if turma is None:
                lista.insert("1.0", "Selecione uma turma para ver os alunos.")
            else:
                alunos_turma = Turmas().alunos_da_turma(turma["id"])
                texto = "Nenhum aluno vinculado a esta turma." if not alunos_turma else "\n".join(
                    f"• {aluno['nome']}" for aluno in alunos_turma
                )
                lista.insert("1.0", texto)
            lista.configure(state="disabled")

        # O relatorio e carregado apenas quando a turma for escolhida.
        for filho in relatorio.winfo_children():
            if isinstance(filho, ctk.CTkOptionMenu):
                filho.configure(command=carregar_relatorio)

        aviso = ctk.CTkFrame(tela, fg_color=("#FFF7ED", "#3A1F0B"), corner_radius=16)
        aviso.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(aviso, text="Status da aula no Portal do Aluno", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(18, 8))
        aviso_turma_var = ctk.StringVar(value="Selecione uma turma")
        ctk.CTkOptionMenu(aviso, values=list(mapa_turmas) or ["Nenhuma turma cadastrada"], variable=aviso_turma_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 8))
        status_var = ctk.StringVar(value="Normal")
        ctk.CTkOptionMenu(aviso, values=["Normal", "Aula cancelada"], variable=status_var, height=36, fg_color="#B7790B", button_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 8))
        texto_aviso = ctk.CTkEntry(aviso, placeholder_text="Aviso para os alunos (ex.: Aula cancelada por chuva)", height=36)
        texto_aviso.pack(fill="x", padx=22, pady=(0, 10))
        def salvar_status_aula():
            turma = mapa_turmas.get(aviso_turma_var.get())
            if turma is None:
                messagebox.showwarning("Turma obrigatoria", "Selecione uma turma.")
                return
            try:
                Turmas().atualizar_status_aula(turma["id"], status_var.get(), texto_aviso.get())
            except ValueError as erro:
                messagebox.showerror("Status nao atualizado", str(erro))
                return
            messagebox.showinfo("Portal atualizado", "O status e o aviso ja podem ser vistos no Portal do Aluno.")
            self.mostrar_turmas()
        ctk.CTkButton(aviso, text="Salvar status da aula", command=salvar_status_aula, height=40, fg_color="#B91C1C", hover_color="#991B1B").pack(fill="x", padx=22, pady=(0, 20))

    def mostrar_checkin(self):
        self.limpar()
        ctk.CTkLabel(self.conteudo, text="Check-in", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="Alunos programados para hoje. Registre a presenca com um clique.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 14))
        turmas = Turmas()
        presencas = turmas.matriculas_do_dia()
        painel = ctk.CTkFrame(self.conteudo, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=16)
        painel.pack(fill="both", expand=True)
        ctk.CTkLabel(painel, text=f"Check-in de hoje - {date.today():%d/%m/%Y}", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        mapa_presencas = {
            f"{registro['aluno']} | {registro['turma']} | {registro['horario']} | {'PRESENTE' if registro['presente'] else 'PENDENTE'}": registro
            for registro in presencas
        }
        checkin_var = ctk.StringVar(value="Selecione um aluno para check-in")
        ctk.CTkOptionMenu(painel, values=list(mapa_presencas) or ["Nenhum aluno programado para hoje"], variable=checkin_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08").pack(fill="x", padx=22, pady=(8, 10))

        def registrar_checkin_hoje():
            registro = mapa_presencas.get(checkin_var.get())
            if registro is None:
                messagebox.showwarning("Aluno obrigatorio", "Selecione um aluno programado para hoje.")
                return
            try:
                turmas.registrar_checkin(registro["matricula_id"])
            except ValueError as erro:
                messagebox.showwarning("Check-in", str(erro))
                return
            messagebox.showinfo("Check-in concluido", f"Presenca de {registro['aluno']} registrada.")
            self.mostrar_checkin()

        ctk.CTkButton(painel, text="Registrar check-in", command=registrar_checkin_hoje, height=40, fg_color="#166534", hover_color="#14532D", font=("Segoe UI", 13, "bold")).pack(fill="x", padx=22, pady=(0, 20))
        return

        ctk.CTkLabel(self.conteudo, text="Check-in e turmas", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="Vincule o aluno a uma turma e marque sua presenca no dia correto.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 14))
        tela = ctk.CTkScrollableFrame(self.conteudo, fg_color="transparent")
        tela.pack(fill="both", expand=True)
        turmas = Turmas()
        alunos = Alunos().listar()
        lista_turmas = turmas.listar()
        mapa_alunos = {f"{aluno['id']} - {aluno['nome']} | {aluno['frequencia'] or 'sem plano'}": aluno for aluno in alunos}
        mapa_turmas = {f"{turma['id']} - {turma['nome']} | {turma['horario']}": turma for turma in lista_turmas}

        vinculo = ctk.CTkFrame(tela, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=16)
        vinculo.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(vinculo, text="Vincular aluno a turma", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 3))
        ctk.CTkLabel(vinculo, text="Para plano 1x por semana, escolha qual dos dois dias sera o treino do aluno.", font=("Segoe UI", 12), text_color=("#7C7160", "#B9B9B9")).pack(anchor="w", padx=22, pady=(0, 10))
        aluno_var = ctk.StringVar(value="Selecione um aluno")
        turma_var = ctk.StringVar(value="Selecione uma turma")
        dia_var = ctk.StringVar(value="Escolha primeiro a turma")
        menu_aluno = ctk.CTkOptionMenu(vinculo, values=list(mapa_alunos) or ["Nenhum aluno cadastrado"], variable=aluno_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08")
        menu_aluno.pack(fill="x", padx=22, pady=(0, 8))
        menu_turma = ctk.CTkOptionMenu(vinculo, values=list(mapa_turmas) or ["Nenhuma turma cadastrada"], variable=turma_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08")
        menu_turma.pack(fill="x", padx=22, pady=(0, 8))
        menu_dia = ctk.CTkOptionMenu(vinculo, values=["Escolha primeiro a turma"], variable=dia_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08")
        menu_dia.pack(fill="x", padx=22, pady=(0, 8))

        def atualizar_dias(valor=None):
            turma = mapa_turmas.get(turma_var.get())
            if turma is None:
                return
            dias = [turma["dia_semana"], turma["dia_semana_2"]]
            menu_dia.configure(values=dias)
            dia_var.set(dias[0])

        menu_turma.configure(command=atualizar_dias)

        def salvar_vinculo():
            aluno = mapa_alunos.get(aluno_var.get())
            turma = mapa_turmas.get(turma_var.get())
            if aluno is None or turma is None:
                messagebox.showwarning("Dados obrigatorios", "Selecione um aluno e uma turma.")
                return
            try:
                turmas.vincular_aluno(aluno["id"], turma["id"], dia_var.get())
            except ValueError as erro:
                messagebox.showerror("Nao foi possivel vincular", str(erro))
                return
            messagebox.showinfo("Aluno vinculado", "O aluno foi vinculado a turma com sucesso.")
            self.mostrar_checkin()

        ctk.CTkButton(vinculo, text="Vincular aluno", command=salvar_vinculo, height=40, fg_color=self.PRIMARIA, hover_color="#8F5E08", font=("Segoe UI", 13, "bold")).pack(fill="x", padx=22, pady=(0, 20))

        presencas = turmas.matriculas_do_dia()
        painel = ctk.CTkFrame(tela, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=16)
        painel.pack(fill="x")
        ctk.CTkLabel(painel, text=f"Check-in de hoje - {date.today():%d/%m/%Y}", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 3))
        ctk.CTkLabel(painel, text="Aparecem somente os alunos que devem treinar hoje. Marque a presenca com um clique.", font=("Segoe UI", 12), text_color=("#7C7160", "#B9B9B9")).pack(anchor="w", padx=22, pady=(0, 10))
        mapa_presencas = {
            f"{registro['aluno']} | {registro['turma']} | {registro['horario']} | {'PRESENTE' if registro['presente'] else 'PENDENTE'}": registro
            for registro in presencas
        }
        checkin_var = ctk.StringVar(value="Selecione um aluno para check-in")
        ctk.CTkOptionMenu(painel, values=list(mapa_presencas) or ["Nenhum aluno programado para hoje"], variable=checkin_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 10))

        def registrar_checkin():
            registro = mapa_presencas.get(checkin_var.get())
            if registro is None:
                messagebox.showwarning("Aluno obrigatorio", "Selecione um aluno programado para hoje.")
                return
            try:
                turmas.registrar_checkin(registro["matricula_id"])
            except ValueError as erro:
                messagebox.showwarning("Check-in", str(erro))
                return
            messagebox.showinfo("Check-in concluido", f"Presenca de {registro['aluno']} registrada.")
            self.mostrar_checkin()

        ctk.CTkButton(painel, text="Registrar check-in", command=registrar_checkin, height=40, fg_color="#166534", hover_color="#14532D", font=("Segoe UI", 13, "bold")).pack(fill="x", padx=22, pady=(0, 20))

    def mostrar_locacao(self):
        self.limpar()
        ctk.CTkLabel(self.conteudo, text="Locação do espaço", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="Funcionamento: 09h as 22h | Quadra: R$ 40,00 por hora | Evento: R$ 300,00 das 09h as 22h.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 16))
        painel = ctk.CTkFrame(self.conteudo, fg_color=("#FFFFFF", "#163B52"), corner_radius=16)
        painel.pack(fill="x")
        ctk.CTkLabel(painel, text="Nova locacao", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 12))
        cliente = ctk.CTkEntry(painel, placeholder_text="Nome do cliente", height=36)
        cliente.pack(fill="x", padx=22, pady=(0, 8))
        whatsapp = ctk.CTkEntry(painel, placeholder_text="WhatsApp do cliente (com DDD)", height=36)
        whatsapp.pack(fill="x", padx=22, pady=(0, 8))
        data_locacao = ctk.CTkEntry(painel, placeholder_text="Data da locacao (dd/mm/aaaa)", height=36)
        data_locacao.pack(fill="x", padx=22, pady=(0, 8))
        tipo = ctk.StringVar(value="Quadra - R$ 40,00 por hora")
        menu_tipo = ctk.CTkOptionMenu(painel, values=["Quadra - R$ 40,00 por hora", "Evento - R$ 300,00 (09h as 22h)"], variable=tipo, height=36, fg_color=self.PRIMARIA, button_color="#0891B2")
        menu_tipo.pack(fill="x", padx=22, pady=(0, 8))
        horario = ctk.CTkEntry(painel, placeholder_text="Horario de inicio (ex.: 14:00)", height=36)
        horario.pack(fill="x", padx=22, pady=(0, 8))
        duracao = ctk.CTkEntry(painel, placeholder_text="Quantidade de horas", height=36)
        duracao.pack(fill="x", padx=22, pady=(0, 8))
        valor = ctk.CTkLabel(painel, text="Valor: informe a quantidade de horas.", font=("Segoe UI", 13, "bold"), text_color=("#0E7490", "#67E8F9"))
        valor.pack(anchor="w", padx=22, pady=(0, 8))

        def atualizar_valor(evento=None):
            if tipo.get().startswith("Evento"):
                horario.delete(0, "end")
                horario.insert(0, "09:00 as 22:00")
                horario.configure(state="disabled")
                duracao.delete(0, "end")
                duracao.insert(0, "13")
                duracao.configure(state="disabled")
                valor.configure(text="Valor da locacao para evento: R$ 300,00")
            else:
                horario.configure(state="normal")
                duracao.configure(state="normal")
                try:
                    total = int(duracao.get() or 0) * 40
                    valor.configure(text=f"Valor da locacao: R$ {total:.2f}")
                except ValueError:
                    valor.configure(text="Informe uma quantidade inteira de horas.")

        menu_tipo.configure(command=atualizar_valor)
        duracao.bind("<KeyRelease>", atualizar_valor)

        def salvar_locacao():
            if not cliente.get().strip() or not whatsapp.get().strip() or not data_locacao.get().strip():
                messagebox.showwarning("Campos obrigatorios", "Informe o cliente, WhatsApp e a data da locacao.")
                return
            try:
                datetime.strptime(data_locacao.get().strip(), "%d/%m/%Y")
                total, horario_final = Agenda().reservar_locacao(
                    cliente.get().strip(), whatsapp.get().strip(), data_locacao.get().strip(), tipo.get(), horario.get().strip(), duracao.get().strip()
                )
            except ValueError as erro:
                messagebox.showerror("Nao foi possivel registrar", str(erro))
                return
            messagebox.showinfo("Locacao registrada", f"Horario: {horario_final}\nValor total: R$ {total:.2f}")
            self.mostrar_locacao()

        ctk.CTkButton(painel, text="Registrar locacao", command=salvar_locacao, height=40, fg_color=self.PRIMARIA, hover_color="#0891B2", font=("Segoe UI", 13, "bold")).pack(fill="x", padx=22, pady=(5, 22))
        def resetar_historico_locacoes():
            if not Agenda().listar():
                messagebox.showinfo("Historico vazio", "Nao ha locacoes para apagar.")
                return
            if messagebox.askyesno("Resetar historico", "Apagar todo o historico de locacoes da quadra? Esta acao nao pode ser desfeita."):
                Agenda().limpar_historico()
                messagebox.showinfo("Historico resetado", "O historico de locacoes foi apagado.")
                self.mostrar_locacao()
        ctk.CTkButton(painel, text="Limpar reservas da quadra", command=resetar_historico_locacoes, height=36, fg_color="#B91C1C", hover_color="#991B1B").pack(fill="x", padx=22, pady=(0, 12))
        ctk.CTkLabel(self.conteudo, text="Locacoes recentes", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(20, 8))
        lista = ctk.CTkTextbox(self.conteudo, height=170, font=("Cascadia Mono", 12), fg_color=("#FFFFFF", "#163B52"), corner_radius=14)
        lista.pack(fill="both", expand=True)
        registros = Agenda().listar()
        texto = "Nenhuma locacao registrada." if not registros else "\n\n".join(
            f"{linha['data']} | {linha['horario']} | {linha['cliente']}\nWhatsApp: {linha['whatsapp'] or '-'} | {linha['tipo_locacao'] or 'Locacao'} | R$ {float(linha['valor'] or 0):.2f}"
            for linha in registros
        )
        lista.insert("1.0", texto)
        lista.configure(state="disabled")

    def mostrar_alunos(self):
        self.limpar()
        ctk.CTkLabel(self.conteudo, text="Alunos", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="Consulte todos os dados informados no cadastro inicial.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 14))
        alunos = Alunos().listar()
        mapa = {f"{aluno['id']} - {aluno['nome']}": aluno for aluno in alunos}
        seletor = ctk.CTkFrame(self.conteudo, fg_color=("#FFFFFF", "#163B52"), corner_radius=16)
        seletor.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(seletor, text="Relatorio individual", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(18, 8))
        aluno_var = ctk.StringVar(value="Selecione um aluno")
        menu = ctk.CTkOptionMenu(seletor, values=list(mapa) or ["Nenhum aluno cadastrado"], variable=aluno_var, height=38, fg_color=self.PRIMARIA, button_color="#8F5E08")
        menu.pack(fill="x", padx=22, pady=(0, 18))
        relatorio = ctk.CTkTextbox(self.conteudo, font=("Cascadia Mono", 12), fg_color=("#F6F1E7", "#111111"), corner_radius=14)
        relatorio.pack(fill="both", expand=True)
        campos = (
            ("DADOS PESSOAIS", ("nome", "data_nascimento", "cpf", "telefone", "whatsapp", "endereco", "esporte")),
            ("PLANO E INSCRICAO", ("frequencia", "valor_plano", "data_inscricao", "dia_vencimento", "modalidade")),
            ("INFORMACOES ADICIONAIS", ("como_conheceu", "restricoes_alimentares", "problema_saude", "necessidades_especiais")),
            ("RESPONSAVEL", ("menor_idade", "responsavel_nome", "responsavel_cpf", "responsavel_parentesco")),
            ("AUTORIZACAO", ("autorizacao_imagem",)),
        )
        nomes = {"nome":"Nome completo", "data_nascimento":"Data de nascimento", "cpf":"CPF", "telefone":"Telefone", "whatsapp":"WhatsApp", "endereco":"Endereco", "esporte":"Esporte", "frequencia":"Frequencia", "valor_plano":"Valor do plano", "data_inscricao":"Data de inscricao", "dia_vencimento":"Dia de vencimento", "modalidade":"Modalidade", "como_conheceu":"Como conheceu", "restricoes_alimentares":"Restricoes alimentares", "problema_saude":"Problema de saude", "necessidades_especiais":"Necessidades especiais", "menor_idade":"Menor de idade", "responsavel_nome":"Nome do responsavel", "responsavel_cpf":"CPF do responsavel", "responsavel_parentesco":"Parentesco", "autorizacao_imagem":"Uso de imagem e voz"}

        def carregar_relatorio(valor=None):
            aluno = mapa.get(aluno_var.get())
            relatorio.configure(state="normal")
            relatorio.delete("1.0", "end")
            if aluno is None:
                relatorio.insert("1.0", "Selecione um aluno para ver o relatorio completo.")
            else:
                linhas = [f"RELATORIO DO ALUNO #{aluno['id']}", "=" * 48]
                for titulo, chaves in campos:
                    linhas.extend(("", titulo, "-" * len(titulo)))
                    for chave in chaves:
                        valor = aluno[chave] if aluno[chave] not in (None, "") else "-"
                        if chave == "valor_plano" and valor != "-":
                            valor = f"R$ {float(valor):.2f}"
                        linhas.append(f"{nomes[chave]}: {valor}")
                relatorio.insert("1.0", "\n".join(linhas))
            relatorio.configure(state="disabled")

        menu.configure(command=carregar_relatorio)
        carregar_relatorio()

    def mostrar_inscricao_aluno(self):
        self.limpar()
        ctk.CTkLabel(self.conteudo, text="Inscricao de aluno", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="Preencha a ficha e confirme as autorizacoes.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 12))
        formulario = ctk.CTkScrollableFrame(self.conteudo, fg_color=("#FFFFFF", "#163B52"), corner_radius=16)
        formulario.pack(fill="both", expand=True)

        entradas = {}
        selecoes = {}

        def titulo(texto):
            ctk.CTkLabel(formulario, text=texto, font=("Segoe UI", 17, "bold"), text_color=("#0E7490", "#67E8F9")).pack(anchor="w", padx=22, pady=(20, 5))

        def campo(rotulo, chave, obrigatorio=True):
            ctk.CTkLabel(formulario, text=f"{rotulo}{' *' if obrigatorio else ''}", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=22, pady=(9, 3))
            entrada = ctk.CTkEntry(formulario, placeholder_text=rotulo, height=36)
            entrada.pack(fill="x", padx=22)
            entradas[chave] = (entrada, obrigatorio)
            return entrada

        def escolha(rotulo, chave, valores, obrigatorio=True):
            ctk.CTkLabel(formulario, text=f"{rotulo}{' *' if obrigatorio else ''}", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=22, pady=(9, 3))
            variavel = ctk.StringVar(value="Selecione uma opcao")
            menu = ctk.CTkOptionMenu(formulario, values=valores, variable=variavel, height=36, fg_color=self.PRIMARIA, button_color="#0891B2")
            menu.pack(fill="x", padx=22)
            selecoes[chave] = (variavel, obrigatorio, menu)
            return variavel, menu

        titulo("Dados do aluno")
        campo("Nome completo", "nome")
        campo("Data de nascimento (dd/mm/aaaa)", "data_nascimento")
        campo("CPF", "cpf")
        campo("WhatsApp (com DDD)", "whatsapp")
        campo("Endereco completo", "endereco")
        esporte, menu_esporte = escolha("Qual esporte?", "esporte", ["Futvolei", "Volei de areia"])

        titulo("Plano de treino")
        plano, menu_plano = escolha("Frequencia", "frequencia", ["Escolha primeiro o esporte"])
        dias_semana, menu_dias_semana = escolha("Quantos dias por semana o aluno vai treinar?", "dias_semana", ["1 dia por semana", "2 dias por semana"])
        valor_exibido = ctk.CTkLabel(formulario, text="Selecione o esporte e a frequencia para ver o valor.", font=("Segoe UI", 13), text_color=("#5B7280", "#ABC6D2"))
        valor_exibido.pack(anchor="w", padx=22, pady=(5, 0))
        planos = {
            "Volei de areia": [("1x por semana - R$ 65,00", 65), ("2x por semana - R$ 120,00", 120), ("Diaria - R$ 25,00 por dia", 25)],
            "Futvolei": [("1x por semana - R$ 60,00", 60), ("2x por semana - R$ 85,00", 85), ("Diaria - R$ 20,00 por dia", 20)],
        }

        def atualizar_planos(valor=None):
            opcoes = [item[0] for item in planos.get(esporte.get(), [])] or ["Escolha primeiro o esporte"]
            menu_plano.configure(values=opcoes)
            plano.set("Selecione uma opcao")
            valor_exibido.configure(text="Selecione a frequencia para ver o valor.")
            if dias_semana.get() != "Selecione uma opcao":
                atualizar_plano_por_dias()

        def atualizar_valor(valor=None):
            for descricao, preco in planos.get(esporte.get(), []):
                if descricao == plano.get():
                    valor_exibido.configure(text=f"Valor do plano: R$ {preco:,.2f}".replace(".", "X").replace(",", ".").replace("X", ","))
                    return

        def atualizar_plano_por_dias(valor=None):
            if esporte.get() not in planos or dias_semana.get() == "Selecione uma opcao":
                return
            inicio = "1x" if dias_semana.get().startswith("1 dia") else "2x"
            plano_correspondente = next((descricao for descricao, _ in planos[esporte.get()] if descricao.startswith(inicio)), None)
            if plano_correspondente:
                plano.set(plano_correspondente)
                atualizar_valor()

        menu_esporte.configure(command=atualizar_planos)
        menu_plano.configure(command=atualizar_valor)
        menu_dias_semana.configure(command=atualizar_plano_por_dias)

        titulo("Turma do aluno")
        turmas_disponiveis = Turmas().listar()
        mapa_turmas_inscricao = {
            f"{turma['id']} - {turma['nome']} | {turma['horario']}": turma
            for turma in turmas_disponiveis
        }
        turma_inscricao_var = ctk.StringVar(value="Selecione uma turma")
        menu_turma_inscricao = ctk.CTkOptionMenu(
            formulario, values=list(mapa_turmas_inscricao) or ["Nenhuma turma cadastrada"],
            variable=turma_inscricao_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08"
        )
        menu_turma_inscricao.pack(fill="x", padx=22, pady=(2, 5))
        ctk.CTkLabel(formulario, text="Os dias e horarios serao definidos pela programacao da turma.", font=("Segoe UI", 12), text_color=("#7C7160", "#B9B9B9")).pack(anchor="w", padx=22, pady=(0, 4))

        titulo("Informacoes adicionais")
        escolha("Como conheceu nossa arena?", "como_conheceu", ["Instagram", "Indicacao", "Passou pelo local", "Era aluno(a) de outro CT"])
        campo("Restricoes alimentares (escreva 'Nenhuma' se nao houver)", "restricoes_alimentares")
        campo("Algum problema de saude? (escreva 'Nao' se nao houver)", "problema_saude")
        campo("Possui necessidades especiais? (escreva 'Nao' se nao houver)", "necessidades_especiais")

        titulo("Cadastro de menor de idade")
        menor, _ = escolha("O aluno e menor de idade?", "menor_idade", ["Nao", "Sim"])
        campo("Nome completo do responsavel (obrigatorio se menor)", "responsavel_nome", False)
        campo("CPF do responsavel (obrigatorio se menor)", "responsavel_cpf", False)
        campo("Parentesco do responsavel (obrigatorio se menor)", "responsavel_parentesco", False)

        titulo("Autorizacao de uso de imagem e voz")
        termo = ctk.CTkTextbox(formulario, height=175, font=("Segoe UI", 12), fg_color=("#F6FAFC", "#102B3A"), corner_radius=10, wrap="word")
        termo.pack(fill="x", padx=22, pady=(4, 6))
        termo.insert("1.0", "Eu autorizo, a titulo nao oneroso e nao exclusivo, o uso cultural e institucional de fotografia, filmes, videos, impressos, audios, slides e meios analogos para divulgacao pedagogica e institucional da Arena Alpha, incluindo cartazes, folhetos, site e redes sociais.\n\nA autorizacao tambem abrange o uso das criacoes realizadas durante os treinos e a cessao desses direitos a entidades parceiras para divulgacao, total ou parcial, sem necessidade de nova notificacao. Declaro autorizar os usos acima descritos de imagem e voz, sem reclamacao futura de direitos conexos ou quaisquer outros.")
        termo.configure(state="disabled")
        escolha("Voce leu e autoriza o uso de imagem e voz?", "autorizacao_imagem", ["Sim, autorizo", "Nao autorizo"])

        def salvar_inscricao():
            valores = {}
            for chave, (entrada, obrigatorio) in entradas.items():
                texto = entrada.get().strip()
                if obrigatorio and not texto:
                    messagebox.showwarning("Campo obrigatorio", f"Preencha o campo: {chave.replace('_', ' ')}.")
                    return
                valores[chave] = texto
            for chave, (variavel, obrigatorio, _) in selecoes.items():
                texto = variavel.get()
                if obrigatorio and texto == "Selecione uma opcao":
                    messagebox.showwarning("Campo obrigatorio", f"Selecione uma opcao para: {chave.replace('_', ' ')}.")
                    return
                valores[chave] = texto
            if valores["menor_idade"] == "Sim":
                for chave in ("responsavel_nome", "responsavel_cpf", "responsavel_parentesco"):
                    if not valores[chave]:
                        messagebox.showwarning("Responsavel obrigatorio", "Para menor de idade, preencha todos os dados do responsavel.")
                        return
            preco = next((preco for descricao, preco in planos[valores["esporte"]] if descricao == valores["frequencia"]), None)
            if preco is None:
                messagebox.showwarning("Plano obrigatorio", "Escolha a frequencia de treino.")
                return
            if valores["frequencia"].startswith("1x") and valores["dias_semana"] != "1 dia por semana":
                messagebox.showwarning("Plano e dias", "O plano 1x por semana deve ter 1 dia de treino.")
                return
            if valores["frequencia"].startswith("2x") and valores["dias_semana"] != "2 dias por semana":
                messagebox.showwarning("Plano e dias", "O plano 2x por semana deve ter 2 dias de treino.")
                return
            turma = mapa_turmas_inscricao.get(turma_inscricao_var.get())
            if turma is None:
                messagebox.showwarning("Turma obrigatoria", "Selecione a turma do aluno.")
                return
            valores["valor_plano"] = preco
            valores["modalidade"] = valores["esporte"]
            valores["data_inscricao"] = date.today().isoformat()
            valores["dia_vencimento"] = date.today().day
            aluno_id = Alunos().cadastrar(**valores)
            try:
                dia_treino = turma["dia_semana"] if valores["frequencia"].startswith("1x") else "Todos os dias da turma"
                Turmas().vincular_aluno(aluno_id, turma["id"], dia_treino)
            except ValueError as erro:
                messagebox.showerror("Vinculo nao criado", str(erro))
                return
            messagebox.showinfo("Inscricao concluida", "Cadastro do aluno salvo com sucesso.")
            self.mostrar_inscricao_aluno()

        ctk.CTkButton(formulario, text="Salvar inscricao", command=salvar_inscricao, height=42, fg_color=self.PRIMARIA, hover_color="#0891B2", font=("Segoe UI", 14, "bold")).pack(fill="x", padx=22, pady=26)

    def mostrar_pagamentos(self):
        self.limpar()
        ctk.CTkLabel(self.conteudo, text="Gerenciamento de pagamentos", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="O vencimento mensal e o mesmo dia da inscricao do aluno.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 16))
        financeiro = Pagamentos()
        alunos = financeiro.alunos_com_plano()
        mapa_alunos = {
            f"{aluno['id']} - {aluno['nome']} | vence dia {aluno['dia_vencimento']}": aluno
            for aluno in alunos
        }
        painel = ctk.CTkFrame(self.conteudo, fg_color=("#FFFFFF", "#163B52"), corner_radius=16)
        painel.pack(fill="x")
        ctk.CTkLabel(painel, text="Registrar pagamento", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(painel, text="Para Volei de Areia, o pagamento ate o vencimento recebe desconto de R$ 20,00.", font=("Segoe UI", 12), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", padx=22, pady=(0, 12))
        aluno_var = ctk.StringVar(value="Selecione um aluno")
        opcoes = list(mapa_alunos) or ["Nenhum aluno com plano cadastrado"]
        menu_alunos = ctk.CTkOptionMenu(painel, values=opcoes, variable=aluno_var, height=36, fg_color=self.PRIMARIA, button_color="#0891B2")
        menu_alunos.pack(fill="x", padx=22, pady=(0, 8))
        data_entrada = ctk.CTkEntry(painel, height=36, placeholder_text="Data do pagamento (dd/mm/aaaa)")
        data_entrada.insert(0, date.today().strftime("%d/%m/%Y"))
        data_entrada.pack(fill="x", padx=22, pady=(0, 8))
        resumo = ctk.CTkLabel(painel, text="", font=("Segoe UI", 13, "bold"), text_color=("#0E7490", "#67E8F9"), justify="left")
        resumo.pack(anchor="w", padx=22, pady=(0, 5))

        def exibir_previsao(valor=None):
            aluno = mapa_alunos.get(aluno_var.get())
            if not aluno:
                resumo.configure(text="")
                return
            try:
                data_pagamento = datetime.strptime(data_entrada.get().strip(), "%d/%m/%Y").date()
                ultimo = calendar.monthrange(data_pagamento.year, data_pagamento.month)[1]
                vencimento = date(data_pagamento.year, data_pagamento.month, min(aluno["dia_vencimento"], ultimo))
                desconto = 20 if aluno["esporte"] == "Volei de areia" and data_pagamento <= vencimento else 0
                total = float(aluno["valor_plano"]) - desconto
                resumo.configure(text=f"Vencimento: {vencimento:%d/%m/%Y} | Plano: R$ {float(aluno['valor_plano']):.2f} | Desconto: R$ {desconto:.2f} | Total: R$ {total:.2f}")
            except ValueError:
                resumo.configure(text="Informe a data no formato dd/mm/aaaa.")

        menu_alunos.configure(command=exibir_previsao)
        data_entrada.bind("<KeyRelease>", exibir_previsao)

        def registrar():
            aluno = mapa_alunos.get(aluno_var.get())
            if aluno is None:
                messagebox.showwarning("Aluno obrigatorio", "Selecione um aluno.")
                return
            try:
                resultado = financeiro.registrar_mensalidade(aluno["id"], data_entrada.get().strip())
            except ValueError as erro:
                messagebox.showerror("Nao foi possivel registrar", str(erro))
                return
            messagebox.showinfo("Pagamento registrado", f"{resultado['nome']}\n{resultado['status']}\nVencimento: {resultado['vencimento']:%d/%m/%Y}\nDesconto: R$ {resultado['desconto']:.2f}\nTotal pago: R$ {resultado['valor_final']:.2f}")
            self.mostrar_pagamentos()

        ctk.CTkButton(painel, text="Confirmar pagamento", command=registrar, height=40, fg_color=self.PRIMARIA, hover_color="#0891B2", font=("Segoe UI", 13, "bold")).pack(fill="x", padx=22, pady=(8, 20))
        ctk.CTkLabel(self.conteudo, text="Situacao dos alunos neste mes", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(20, 7))
        lista = ctk.CTkTextbox(self.conteudo, font=("Cascadia Mono", 12), fg_color=("#FFFFFF", "#163B52"), corner_radius=14)
        lista.pack(fill="both", expand=True)
        situacoes = financeiro.situacao_atual()
        texto = "Nenhum aluno com plano cadastrado." if not situacoes else "\n\n".join(
            f"{item['aluno']['nome']}  |  {item['aluno']['esporte']}\nVence: {item['vencimento']:%d/%m/%Y}  |  Status: {item['status']}  |  Pago em: {item['pago_em']}"
            for item in situacoes
        )
        lista.insert("1.0", texto)
        lista.configure(state="disabled")

    def mostrar_financeiro(self):
        self.limpar()
        financeiro = Financeiro()
        resumo = financeiro.resumo_mes()
        ctk.CTkLabel(self.conteudo, text="Financeiro", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text=f"Resumo de {date.today():%m/%Y}: entradas, gastos e saldo da Arena Alpha.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 14))
        cards = ctk.CTkFrame(self.conteudo, fg_color="transparent")
        cards.pack(fill="x")
        for coluna in range(3):
            cards.grid_columnconfigure(coluna, weight=1)
        dados_cards = [
            ("RECEITAS", resumo["receitas"], "#166534"),
            ("DESPESAS", resumo["despesas"], "#B91C1C"),
            ("SALDO", resumo["saldo"], self.PRIMARIA),
        ]
        for indice, (titulo, valor, cor) in enumerate(dados_cards):
            card = ctk.CTkFrame(cards, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=14, border_width=1, border_color=("#D8C9A4", "#454545"))
            card.grid(row=0, column=indice, sticky="nsew", padx=5)
            ctk.CTkLabel(card, text=titulo, font=("Segoe UI", 11, "bold"), text_color=cor).pack(anchor="w", padx=18, pady=(16, 0))
            ctk.CTkLabel(card, text=f"R$ {valor:,.2f}", font=("Segoe UI", 23, "bold"), text_color=("#241B0E", "#FFF6DE")).pack(anchor="w", padx=18, pady=(2, 16))

        corpo = ctk.CTkFrame(self.conteudo, fg_color="transparent")
        corpo.pack(fill="both", expand=True, pady=(20, 0))
        formulario = ctk.CTkFrame(corpo, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=16)
        formulario.pack(side="left", fill="y", padx=(0, 9))
        ctk.CTkLabel(formulario, text="Registrar despesa", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 10))
        descricao = ctk.CTkEntry(formulario, placeholder_text="Descricao do gasto", width=300, height=36)
        descricao.pack(padx=22, pady=(0, 8))
        categoria_var = ctk.StringVar(value="Selecione a categoria")
        ctk.CTkOptionMenu(formulario, values=["Aluguel", "Agua e energia", "Material esportivo", "Marketing", "Manutencao", "Professor", "Outros"], variable=categoria_var, width=300, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08").pack(padx=22, pady=(0, 8))
        valor = ctk.CTkEntry(formulario, placeholder_text="Valor (R$)", width=300, height=36)
        valor.pack(padx=22, pady=(0, 8))
        data_despesa = ctk.CTkEntry(formulario, placeholder_text="Data (dd/mm/aaaa)", width=300, height=36)
        data_despesa.insert(0, date.today().strftime("%d/%m/%Y"))
        data_despesa.pack(padx=22, pady=(0, 8))
        observacao = ctk.CTkEntry(formulario, placeholder_text="Observacao (opcional)", width=300, height=36)
        observacao.pack(padx=22, pady=(0, 12))

        def salvar_despesa():
            if categoria_var.get() == "Selecione a categoria":
                messagebox.showwarning("Categoria obrigatoria", "Selecione uma categoria para a despesa.")
                return
            try:
                financeiro.registrar_despesa(descricao.get(), categoria_var.get(), valor.get(), data_despesa.get(), observacao.get())
            except ValueError as erro:
                messagebox.showerror("Nao foi possivel registrar", str(erro))
                return
            messagebox.showinfo("Despesa registrada", "O gasto foi adicionado ao financeiro.")
            self.mostrar_financeiro()

        ctk.CTkButton(formulario, text="Salvar despesa", command=salvar_despesa, height=40, fg_color="#B91C1C", hover_color="#991B1B", font=("Segoe UI", 13, "bold")).pack(fill="x", padx=22, pady=(0, 22))
        historico = ctk.CTkFrame(corpo, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=16)
        historico.pack(side="right", fill="both", expand=True, padx=(9, 0))
        ctk.CTkLabel(historico, text="Historico de lancamentos", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 3))
        ctk.CTkLabel(historico, text=f"{resumo['pagamentos']} pagamento(s) confirmado(s) neste mes.", font=("Segoe UI", 12), text_color=("#7C7160", "#B9B9B9")).pack(anchor="w", padx=22, pady=(0, 10))
        lista = ctk.CTkTextbox(historico, font=("Cascadia Mono", 12), fg_color=("#F6F1E7", "#111111"), corner_radius=10)
        lista.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        lancamentos = financeiro.lancamentos_recentes()
        texto = "Nenhum lancamento financeiro ainda." if not lancamentos else "\n\n".join(
            f"{item['data']} | {item['tipo']} | {item['categoria']}\n{item['descricao']}  |  R$ {float(item['valor']):.2f}"
            for item in lancamentos
        )
        lista.insert("1.0", texto)
        lista.configure(state="disabled")

    def mostrar_whatsapp(self):
        self.limpar()
        ctk.CTkLabel(self.conteudo, text="Central WhatsApp", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="Escolha um contato. O WhatsApp abre com a mensagem pronta; basta revisar e enviar.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 14))
        conteudo = ctk.CTkScrollableFrame(self.conteudo, fg_color="transparent")
        conteudo.pack(fill="both", expand=True)
        whatsapp = WhatsApp()

        def bloco(titulo, descricao):
            painel = ctk.CTkFrame(conteudo, fg_color=("#FFFCF5", "#1D1D1D"), corner_radius=16)
            painel.pack(fill="x", pady=7)
            ctk.CTkLabel(painel, text=titulo, font=("Segoe UI", 18, "bold"), text_color=("#241B0E", "#FFF6DE")).pack(anchor="w", padx=22, pady=(18, 2))
            ctk.CTkLabel(painel, text=descricao, font=("Segoe UI", 12), text_color=("#7C7160", "#B9B9B9")).pack(anchor="w", padx=22, pady=(0, 10))
            return painel

        alunos = [aluno for aluno in Alunos().listar() if aluno["whatsapp"]]
        contatos_alunos = {f"{aluno['id']} - {aluno['nome']}": aluno for aluno in alunos}
        treino = bloco("Confirmacao de treino", "Envie uma confirmacao de treino para um aluno cadastrado.")
        aluno_treino_var = ctk.StringVar(value="Selecione um aluno")
        opcoes_alunos = list(contatos_alunos) or ["Nenhum aluno com WhatsApp cadastrado"]
        ctk.CTkOptionMenu(treino, values=opcoes_alunos, variable=aluno_treino_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 10))

        def confirmar_treino():
            aluno = contatos_alunos.get(aluno_treino_var.get())
            if aluno is None:
                messagebox.showwarning("Aluno obrigatorio", "Selecione um aluno com WhatsApp cadastrado.")
                return
            esporte = aluno["esporte"] or aluno["modalidade"] or "treino"
            mensagem = f"Ola, {aluno['nome']}! Seu treino de {esporte} esta confirmado na Arena Alpha. Esperamos voce na quadra!"
            try:
                whatsapp.abrir_mensagem(aluno["whatsapp"], mensagem)
            except ValueError as erro:
                messagebox.showerror("WhatsApp invalido", str(erro))

        ctk.CTkButton(treino, text="Abrir confirmacao de treino", command=confirmar_treino, fg_color=self.PRIMARIA, hover_color="#8F5E08", height=38).pack(fill="x", padx=22, pady=(0, 18))

        reservas = [reserva for reserva in Agenda().listar() if reserva["whatsapp"]]
        contatos_reservas = {f"{reserva['id']} - {reserva['cliente']} | {reserva['data']}": reserva for reserva in reservas}
        locacao = bloco("Confirmacao de locacao", "Envie a confirmacao do aluguel da Quadra Principal.")
        reserva_var = ctk.StringVar(value="Selecione uma locacao")
        opcoes_reservas = list(contatos_reservas) or ["Nenhuma locacao com WhatsApp cadastrada"]
        ctk.CTkOptionMenu(locacao, values=opcoes_reservas, variable=reserva_var, height=36, fg_color=self.PRIMARIA, button_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 10))

        def confirmar_locacao():
            reserva = contatos_reservas.get(reserva_var.get())
            if reserva is None:
                messagebox.showwarning("Locacao obrigatoria", "Selecione uma locacao com WhatsApp cadastrado.")
                return
            mensagem = f"Ola, {reserva['cliente']}! Sua locacao da Quadra Principal esta confirmada para {reserva['data']}, das {reserva['horario']}. Valor: R$ {float(reserva['valor'] or 0):.2f}. Arena Alpha agradece!"
            try:
                whatsapp.abrir_mensagem(reserva["whatsapp"], mensagem)
            except ValueError as erro:
                messagebox.showerror("WhatsApp invalido", str(erro))

        ctk.CTkButton(locacao, text="Abrir confirmacao de locacao", command=confirmar_locacao, fg_color=self.PRIMARIA, hover_color="#8F5E08", height=38).pack(fill="x", padx=22, pady=(0, 18))

        pagamentos = Pagamentos()
        atrasados = [item for item in pagamentos.situacao_atual() if item["status"] == "Em atraso" and item["aluno"]["whatsapp"]]
        contatos_atrasados = {f"{item['aluno']['id']} - {item['aluno']['nome']} | venceu {item['vencimento']:%d/%m}": item for item in atrasados}
        cobranca = bloco("Cobranca de pagamento em atraso", "Envie uma mensagem de lembrete para alunos com mensalidade em atraso.")
        atraso_var = ctk.StringVar(value="Selecione um aluno em atraso")
        opcoes_atrasados = list(contatos_atrasados) or ["Nenhum aluno em atraso com WhatsApp"]
        ctk.CTkOptionMenu(cobranca, values=opcoes_atrasados, variable=atraso_var, height=36, fg_color="#B7790B", button_color="#8F5E08").pack(fill="x", padx=22, pady=(0, 10))

        def cobrar_atraso():
            item = contatos_atrasados.get(atraso_var.get())
            if item is None:
                messagebox.showwarning("Aluno obrigatorio", "Selecione um aluno em atraso com WhatsApp cadastrado.")
                return
            aluno = item["aluno"]
            mensagem = f"Ola, {aluno['nome']}! Identificamos que sua mensalidade da Arena Alpha venceu em {item['vencimento']:%d/%m/%Y} e ainda esta pendente. Por favor, entre em contato para regularizar o pagamento."
            try:
                whatsapp.abrir_mensagem(aluno["whatsapp"], mensagem)
            except ValueError as erro:
                messagebox.showerror("WhatsApp invalido", str(erro))

        ctk.CTkButton(cobranca, text="Abrir cobranca no WhatsApp", command=cobrar_atraso, fg_color="#B7790B", hover_color="#8F5E08", height=38).pack(fill="x", padx=22, pady=(0, 18))

    def mostrar_administracao(self):
        permissoes = Permissoes()
        if not permissoes.tem_senha():
            senha = simpledialog.askstring(
                "Criar senha", "Defina a senha de administrador para exclusoes:\n(minimo de 4 caracteres)",
                show="*", parent=self,
            )
            if senha is None:
                return
            confirmar = simpledialog.askstring(
                "Confirmar senha", "Digite a senha novamente:", show="*", parent=self
            )
            if senha != confirmar:
                messagebox.showerror("Senhas diferentes", "As senhas nao conferem.")
                return
            try:
                permissoes.definir_senha(senha)
            except ValueError as erro:
                messagebox.showerror("Senha invalida", str(erro))
                return
            messagebox.showinfo("Senha criada", "Senha de administrador criada com sucesso.")
        senha = simpledialog.askstring(
            "Autorizacao", "Digite a senha de administrador para gerenciar exclusoes:",
            show="*", parent=self,
        )
        if senha is None:
            return
        if not permissoes.autorizar(senha):
            messagebox.showerror("Acesso negado", "Senha de administrador incorreta.")
            return

        self.limpar()
        ctk.CTkLabel(self.conteudo, text="Administracao", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="Exclusoes exigem senha de administrador e confirmacao.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 16))
        painel = ctk.CTkFrame(self.conteudo, fg_color=("#FFFFFF", "#163B52"), corner_radius=16)
        painel.pack(fill="both", expand=True)
        ctk.CTkLabel(painel, text="Excluir cadastro", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(painel, text="Escolha o tipo de registro e depois selecione o item a excluir.", font=("Segoe UI", 12), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", padx=22, pady=(0, 12))
        tipos = {"Aluno": (Alunos(), "nome"), "Turma": (Turmas(), "nome"), "Professor": (Professores(), "nome"), "Modalidade": (Modalidades(), "nome"), "Pagamento recebido": (Pagamentos(), "aluno"), "Despesa": (Financeiro(), "descricao")}
        tipo_var = ctk.StringVar(value="Aluno")
        item_var = ctk.StringVar(value="Selecione um registro")
        menu_tipo = ctk.CTkOptionMenu(painel, values=list(tipos), variable=tipo_var, height=36, fg_color=self.PRIMARIA, button_color="#0891B2")
        menu_tipo.pack(fill="x", padx=22, pady=(0, 8))
        menu_item = ctk.CTkOptionMenu(painel, values=["Selecione um registro"], variable=item_var, height=36, fg_color=self.PRIMARIA, button_color="#0891B2")
        menu_item.pack(fill="x", padx=22, pady=(0, 10))
        lista = ctk.CTkTextbox(painel, height=200, font=("Cascadia Mono", 12), fg_color=("#F6FAFC", "#102B3A"), corner_radius=10)
        lista.pack(fill="both", expand=True, padx=22, pady=(0, 12))
        registros_atuais = {}

        def atualizar_registros(valor=None):
            nonlocal registros_atuais
            repositorio, campo_nome = tipos[tipo_var.get()]
            registros = repositorio.listar()
            registros_atuais = {
                f"#{linha['id']} - {linha[campo_nome]}": linha["id"] for linha in registros
            }
            opcoes = list(registros_atuais) or ["Nenhum registro encontrado"]
            menu_item.configure(values=opcoes)
            item_var.set(opcoes[0])
            lista.configure(state="normal")
            lista.delete("1.0", "end")
            if registros:
                lista.insert("1.0", "\n\n".join(" | ".join(f"{chave}: {valor}" for chave, valor in dict(linha).items()) for linha in registros))
            else:
                lista.insert("1.0", "Nao ha registros para excluir.")
            lista.configure(state="disabled")

        def excluir_selecionado():
            identificador = registros_atuais.get(item_var.get())
            if identificador is None:
                messagebox.showwarning("Registro obrigatorio", "Selecione um registro valido.")
                return
            tipo = tipo_var.get().lower()
            if not messagebox.askyesno("Confirmar exclusao", f"Excluir este {tipo}? Esta acao nao pode ser desfeita."):
                return
            try:
                tipos[tipo_var.get()][0].excluir(identificador)
            except ValueError as erro:
                messagebox.showerror("Erro", str(erro))
                return
            messagebox.showinfo("Exclusao concluida", f"{tipo.capitalize()} excluido com sucesso.")
            atualizar_registros()

        menu_tipo.configure(command=atualizar_registros)
        atualizar_registros()
        ctk.CTkButton(painel, text="Excluir registro selecionado", command=excluir_selecionado, height=40, fg_color="#B91C1C", hover_color="#991B1B", font=("Segoe UI", 13, "bold")).pack(fill="x", padx=22, pady=(0, 22))

    def mostrar_formulario(self, titulo, subtitulo, repositorio, campos, metodo):
        self.limpar()
        ctk.CTkLabel(self.conteudo, text=titulo, font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text=subtitulo, font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 18))
        corpo = ctk.CTkFrame(self.conteudo, fg_color="transparent")
        corpo.pack(fill="both", expand=True)
        formulario = ctk.CTkFrame(corpo, fg_color=("#FFFFFF", "#163B52"), corner_radius=16)
        formulario.pack(side="left", fill="y", padx=(0, 10))
        ctk.CTkLabel(formulario, text="Novo registro", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=24, pady=(22, 4))
        ctk.CTkLabel(formulario, text="Preencha os dados abaixo.", font=("Segoe UI", 12), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", padx=24, pady=(0, 12))
        entradas = {}
        selecoes = {}
        for definicao in campos:
            rotulo, chave = definicao[:2]
            ctk.CTkLabel(formulario, text=rotulo, font=("Segoe UI", 12, "bold"), text_color=("#405C69", "#CAE4EF")).pack(anchor="w", padx=24, pady=(10, 3))
            if len(definicao) == 3:
                variavel = ctk.StringVar(value="Selecione uma opcao")
                ctk.CTkOptionMenu(formulario, values=definicao[2], variable=variavel, width=300, height=38, fg_color=self.PRIMARIA, button_color="#0891B2").pack(padx=24)
                selecoes[chave] = variavel
            else:
                entrada = ctk.CTkEntry(formulario, placeholder_text=f"Informe {rotulo.lower()}", width=300, height=38, border_color=("#C7D9E1", "#34627B"))
                entrada.pack(padx=24)
                entradas[chave] = entrada
        def salvar():
            valores = []
            for definicao in campos:
                chave = definicao[1]
                valor = (selecoes[chave] if chave in selecoes else entradas[chave]).get().strip()
                valores.append(valor)
            if not all(valores) or "Selecione uma opcao" in valores:
                messagebox.showwarning("Campos obrigatorios", "Preencha todos os campos.")
                return
            try:
                getattr(repositorio, metodo)(*valores)
            except ValueError as erro:
                mensagem = str(erro) or "Informe um valor numerico para o pagamento."
                messagebox.showerror("Nao foi possivel salvar", mensagem)
                return
            messagebox.showinfo("Arena Alpha", "Registro salvo com sucesso.")
            self.mostrar_formulario(titulo, subtitulo, repositorio, campos, metodo)
        ctk.CTkButton(formulario, text="Salvar registro", command=salvar, height=40, fg_color=self.PRIMARIA, hover_color="#0891B2", font=("Segoe UI", 13, "bold")).pack(fill="x", padx=24, pady=24)
        painel_lista = ctk.CTkFrame(corpo, fg_color=("#FFFFFF", "#163B52"), corner_radius=16)
        painel_lista.pack(side="right", fill="both", expand=True, padx=(10, 0))
        ctk.CTkLabel(painel_lista, text="Registros recentes", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(22, 3))
        ctk.CTkLabel(painel_lista, text="Os ultimos cadastros aparecem aqui.", font=("Segoe UI", 12), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", padx=22, pady=(0, 12))
        lista = ctk.CTkTextbox(painel_lista, font=("Cascadia Mono", 12), fg_color=("#F6FAFC", "#102B3A"), corner_radius=10)
        lista.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        registros = repositorio.listar()
        texto = "Nenhum registro ainda.\n\nUse o formulario ao lado para comecar." if not registros else "\n\n".join("  |  ".join(str(valor) for valor in linha) for linha in registros)
        lista.insert("1.0", texto)
        lista.configure(state="disabled")

    def mostrar_quadra(self):
        self.limpar()
        ctk.CTkLabel(self.conteudo, text="Quadra Principal", font=("Segoe UI", 29, "bold"), text_color=("#123147", "#F1FAFE")).pack(anchor="w")
        ctk.CTkLabel(self.conteudo, text="A Arena Alpha opera com uma unica quadra.", font=("Segoe UI", 14), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", pady=(0, 22))
        card = ctk.CTkFrame(self.conteudo, fg_color=("#FFFFFF", "#163B52"), corner_radius=18, border_width=1, border_color=("#D9E4EB", "#28546B"))
        card.pack(fill="x", pady=6)
        ctk.CTkLabel(card, text="QUADRA 01", font=("Segoe UI", 12, "bold"), text_color="#0E7490").pack(anchor="w", padx=28, pady=(26, 2))
        ctk.CTkLabel(card, text="Quadra Principal", font=("Segoe UI", 25, "bold")).pack(anchor="w", padx=28)
        ctk.CTkLabel(card, text="Disponivel para reservas pela agenda.", font=("Segoe UI", 13), text_color=("#5B7280", "#ABC6D2")).pack(anchor="w", padx=28, pady=(4, 26))

    def criar_backup(self):
        try:
            arquivo = Backup().criar_backup()
            messagebox.showinfo("Backup concluido", f"Backup criado com sucesso:\n{arquivo.name}")
        except FileNotFoundError:
            messagebox.showerror("Backup", "Ainda nao existe banco de dados para copiar.")


if __name__ == "__main__":
    ArenaAlpha().mainloop()
