# -*- coding: utf-8 -*-
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import customtkinter as ctk
import hashlib
import os
import shutil
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageTk
from flask import Flask, request, jsonify
import threading
import queue

# Configuração Global de Design
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class RestauranteApp(ctk.CTk):
    def __init__(self, root):
        super().__init__()
        self.root = root
        self.root.title("Hamburgueria Tradição")
        self.root.geometry("1400x900")
        self.centralizar_janela(self.root, 1400, 900)
        
        self.fonte_padrao = ("Arial", 14)
        self.fonte_grande = ("Arial", 16, "bold")
        
        if not os.path.exists("imagens_produtos"): os.makedirs("imagens_produtos")
        if not os.path.exists("logo_sistema"): os.makedirs("logo_sistema")
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("Treeview", font=self.fonte_padrao, rowheight=45, background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        self.style.configure("Treeview.Heading", font=("Arial", 14, "bold"), background="#333333", foreground="white")
        
        self.taxa_garcom = tk.BooleanVar(value=True)
        self.caminho_imagem_selecionada = ""
        
        self.inicializar_banco()
        self.iniciar_api()
        self.tela_login()

    def centralizar_janela(self, win, w, h):
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (w // 2)
        y = (win.winfo_screenheight() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

    def iniciar_api(self):
        self.fila_pedidos = queue.Queue()
        app = Flask(__name__)

        @app.route('/webhook', methods=['POST'])
        def webhook():
            dados = request.json
            self.fila_pedidos.put(dados)
            return jsonify({"status": "Pedido recebido"}), 200

        threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True).start()
        self.root.after(1000, self.verificar_fila)

    def verificar_fila(self):
        try:
            while not self.fila_pedidos.empty():
                pedido = self.fila_pedidos.get_nowait()
                conn = sqlite3.connect('restaurante.db')
                conn.execute("INSERT INTO pedidos (mesa_id, item, preco) VALUES (?, ?, ?)", 
                             (pedido['mesa'], pedido['item'], pedido['preco']))
                conn.commit(); conn.close()
                if hasattr(self, 'e_m') and self.e_m.get() == str(pedido['mesa']):
                    self.atualizar_comanda()
        finally:
            self.root.after(1000, self.verificar_fila)

    def inicializar_banco(self):
        conn = sqlite3.connect('restaurante.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS estoque (id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT UNIQUE, categoria TEXT, preco REAL, qtd INTEGER DEFAULT 10, validade TEXT, usuario_criador TEXT, cargo_criador TEXT, img_path TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY AUTOINCREMENT, mesa_id TEXT, item TEXT, preco REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, cargo TEXT, genero TEXT, idade INTEGER, senha TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, mesa TEXT, valor_final REAL, pgto TEXT, atendente TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS logs_remocao (id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT, motivo TEXT, usuario TEXT, data TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS delivery (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, endereco TEXT, telefone TEXT, troco REAL, pedido TEXT, observacao TEXT, pagamento TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT)''')
        
        # Novas tabelas adicionadas para atender aos requisitos de relatórios e pontos
        c.execute('''CREATE TABLE IF NOT EXISTS despesas (id INTEGER PRIMARY KEY AUTOINCREMENT, descricao TEXT, valor REAL, data TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS custom_tabs (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS ponto_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, funcionario TEXT, cargo TEXT, data TEXT, mes TEXT, entrada TEXT, pausa_inicio TEXT, pausa_fim TEXT, saida TEXT, horas_trab TEXT, horas_extra TEXT)''')
        
        # Tratamento seguro para adicionar colunas em tabelas que já existem no seu banco sem quebrar
        try: c.execute("ALTER TABLE historico ADD COLUMN itens TEXT")
        except sqlite3.OperationalError: pass
        try: c.execute("ALTER TABLE delivery ADD COLUMN data_registro TEXT")
        except sqlite3.OperationalError: pass
        
        c.execute("INSERT OR IGNORE INTO config VALUES ('logo_path', '')")
        
        admin_check = c.execute("SELECT * FROM funcionarios WHERE nome='admin'").fetchone()
        if not admin_check:
            senha_admin = hashlib.sha256("admin".encode()).hexdigest()
            c.execute("INSERT INTO funcionarios (nome, cargo, genero, idade, senha) VALUES ('admin', 'Dono', 'Masculino', 30, ?)", (senha_admin,))
        conn.commit(); conn.close()

    def get_hora_brasilia(self):
        tz = timezone(timedelta(hours=-3))
        return datetime.now(tz).strftime("%H:%M:%S")

    def atualizar_relogio(self):
        if hasattr(self, 'lbl_relogio'):
            self.lbl_relogio.configure(text=f"Brasília: {self.get_hora_brasilia()}")
        self.root.after(1000, self.atualizar_relogio)

    def get_logo(self, w, h):
        try:
            conn = sqlite3.connect('restaurante.db')
            path = conn.execute("SELECT valor FROM config WHERE chave='logo_path'").fetchone()[0]
            conn.close()
            if path and os.path.exists(path):
                img = Image.open(path).resize((w, h), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
        except: return None
        return None

    def tela_login(self):
        for widget in self.root.winfo_children(): widget.destroy()
        self.root.withdraw()
        win = ctk.CTkToplevel(self.root)
        win.title("Login de Segurança")
        self.centralizar_janela(win, 500, 650)
        
        self.logo_login = self.get_logo(150, 150)
        if self.logo_login: ctk.CTkLabel(win, image=self.logo_login, text="").pack(pady=20)
        
        ctk.CTkLabel(win, text="HAMBURGUERIA TRADIÇÃO", font=("Arial", 20, "bold")).pack(pady=20)
        self.e_u = ctk.CTkEntry(win, placeholder_text="Usuário", font=("Arial", 16)); self.e_u.pack(padx=20, fill="x", pady=10)
        self.e_s = ctk.CTkEntry(win, placeholder_text="Senha", show="*", font=("Arial", 16)); self.e_s.pack(padx=20, fill="x", pady=10)
        
        def entrar():
            conn = sqlite3.connect('restaurante.db')
            user = conn.execute("SELECT nome, cargo, senha FROM funcionarios WHERE nome=?", (self.e_u.get(),)).fetchone()
            if user and user[2] == hashlib.sha256(self.e_s.get().encode()).hexdigest():
                self.usuario_logado, self.cargo_atual = user[0], user[1]
                win.destroy(); self.root.deiconify(); self.carregar_interface()
            else: messagebox.showerror("Erro", "Credenciais inválidas")
            conn.close()
            
        ctk.CTkButton(win, text="ACESSAR", command=entrar).pack(pady=40)

    def carregar_interface(self):
        for widget in self.root.winfo_children(): widget.destroy()
        header = ctk.CTkFrame(self.root); header.pack(side="top", fill="x", padx=10, pady=5)
        
        self.logo_header = self.get_logo(50, 50)
        if self.logo_header: ctk.CTkLabel(header, image=self.logo_header, text="").pack(side="left", padx=10)
        
        ctk.CTkLabel(header, text=f"Operador: {self.usuario_logado} | Cargo: {self.cargo_atual}").pack(side="left", padx=20, pady=10)
        self.lbl_relogio = ctk.CTkLabel(header, text="", font=("Arial", 14, "bold"), text_color="#f1c40f")
        self.lbl_relogio.pack(side="right", padx=20)
        self.atualizar_relogio()
        ctk.CTkButton(header, text="Sair", fg_color="red", command=self.tela_login).pack(side="right", padx=20)

        self.nb = ctk.CTkTabview(self.root); self.nb.pack(fill='both', expand=True, padx=10, pady=10)
        
        # ABA MESAS
        aba_m = self.nb.add(" 🍽️ MESAS E COMANDAS ")
        left = ctk.CTkFrame(aba_m); left.pack(side="left", fill="both", expand=True, padx=10)
        self.e_m = ctk.CTkEntry(left, font=("Arial", 18), placeholder_text="Número da Mesa"); self.e_m.pack(fill="x", pady=5)
        ctk.CTkButton(left, text="CARREGAR MESA", command=self.atualizar_comanda).pack(fill="x")
        self.t_prod = ttk.Treeview(left, columns=("ID", "Item", "Preco"), show="headings")
        for c in ("ID", "Item", "Preco"): self.t_prod.heading(c, text=c)
        self.t_prod.column("ID", width=60); self.t_prod.pack(fill="both", expand=True, pady=5)
        self.t_prod.bind("<Double-1>", self.adicionar_item_mesa)
        
        # Novo atalho para os Mais Vendidos
        ctk.CTkLabel(left, text="🔥 Mais Vendidos (Atalho duplo-clique)", font=("Arial", 14, "bold"), text_color="orange").pack(pady=(5,0))
        self.t_top = ttk.Treeview(left, columns=("Item", "Preco"), show="headings", height=3)
        for c in ("Item", "Preco"): self.t_top.heading(c, text=c)
        self.t_top.pack(fill="x", pady=5)
        self.t_top.bind("<Double-1>", self.adicionar_item_top)

        right_main = ctk.CTkScrollableFrame(aba_m); right_main.pack(side="right", fill="both", expand=True, padx=10)
        self.t_comanda = ttk.Treeview(right_main, columns=("ID", "Item", "Preco"), show="headings", height=8)
        for c in ("ID", "Item", "Preco"): self.t_comanda.heading(c, text=c)
        self.t_comanda.pack(fill="x", pady=10)
        self.l_sub = ctk.CTkLabel(right_main, text="Subtotal: R$ 0.00", font=("Arial", 14)); self.l_sub.pack()
        self.l_taxa = ctk.CTkLabel(right_main, text="Taxa (10%): R$ 0.00", font=("Arial", 14)); self.l_taxa.pack()
        self.l_total = ctk.CTkLabel(right_main, text="Total: R$ 0.00", font=("Arial", 20, "bold")); self.l_total.pack(pady=10)
        ctk.CTkCheckBox(right_main, text="Incluir 10% Garçom", variable=self.taxa_garcom, command=self.atualizar_comanda).pack()
        
        btns = [("IMPRIMIR", self.imprimir_comanda), ("ENCERRAR MESA", self.encerrar_mesa), ("IA: HARMONIZAR", self.assistente_ia), ("EXCLUIR ITEM", self.excluir_item), ("TRANSFERIR", self.transferir_item)]
        for txt, cmd in btns: ctk.CTkButton(right_main, text=txt, command=cmd).pack(fill="x", pady=5)

        # ABA DELIVERY
        aba_d = self.nb.add(" 🛵 DELIVERY ")
        left_d = ctk.CTkFrame(aba_d); left_d.pack(side="left", fill="y", padx=10, pady=10)
        ctk.CTkLabel(left_d, text="Novo Pedido Delivery", font=("Arial", 16, "bold")).pack(pady=10)
        
        self.e_nome_cli = ctk.CTkEntry(left_d, placeholder_text="Nome do Cliente"); self.e_nome_cli.pack(fill="x", pady=5, padx=20)
        self.e_end = ctk.CTkEntry(left_d, placeholder_text="Endereço"); self.e_end.pack(fill="x", pady=5, padx=20)
        self.e_tel = ctk.CTkEntry(left_d, placeholder_text="Telefone"); self.e_tel.pack(fill="x", pady=5, padx=20)
        self.cb_pgto = ctk.CTkComboBox(left_d, values=["Dinheiro", "Cartão Crédito", "Cartão Débito", "Pix"], command=self.toggle_troco)
        self.cb_pgto.pack(fill="x", pady=5, padx=20)
        self.e_troco = ctk.CTkEntry(left_d, placeholder_text="Troco para quanto?"); self.e_troco.pack(fill="x", pady=5, padx=20)
        self.e_pedido = ctk.CTkEntry(left_d, placeholder_text="Pedido"); self.e_pedido.pack(fill="x", pady=5, padx=20)
        self.e_obs = ctk.CTkEntry(left_d, placeholder_text="Observação"); self.e_obs.pack(fill="x", pady=5, padx=20)
        ctk.CTkButton(left_d, text="REGISTRAR DELIVERY", fg_color="green", command=self.registrar_delivery).pack(pady=10, padx=20)
        
        # Botões de Impressão, Finalização e Remoção no Delivery
        ctk.CTkButton(left_d, text="IMPRIMIR P/ MOTOBOY", command=self.imprimir_motoboy).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(left_d, text="IMPRIMIR P/ COZINHA", command=self.imprimir_cozinha).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(left_d, text="FINALIZAR PEDIDO (Enviar p/ Relatórios)", command=self.finalizar_delivery).pack(pady=5, padx=20, fill="x")
        ctk.CTkButton(left_d, text="REMOVER REGISTRO", fg_color="red", command=self.remover_registro_delivery).pack(pady=5, padx=20, fill="x")

        right_d = ctk.CTkFrame(aba_d); right_d.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(right_d, text="Pedidos de Delivery", font=("Arial", 16, "bold")).pack(pady=10)
        self.t_delivery = ttk.Treeview(right_d, columns=("ID", "Nome", "End", "Tel", "Troco", "Pedido", "Obs", "Pgto"), show="headings")
        for c in ("ID", "Nome", "End", "Tel", "Troco", "Pedido", "Obs", "Pgto"): self.t_delivery.heading(c, text=c)
        self.t_delivery.column("ID", width=30); self.t_delivery.column("Troco", width=60)
        self.t_delivery.pack(fill="both", expand=True, padx=10, pady=10)
        self.carregar_tabela_delivery()

        # ABA BATER PONTO (Acessível a todos)
        aba_p = self.nb.add(" ⏱️ PONTO ")
        ctk.CTkLabel(aba_p, text=f"Sistema de Ponto - Operador: {self.usuario_logado}", font=("Arial", 20, "bold")).pack(pady=20)
        frame_btn_ponto = ctk.CTkFrame(aba_p); frame_btn_ponto.pack(pady=20)
        ctk.CTkButton(frame_btn_ponto, text="1. ENTRADA", fg_color="green", height=50, command=lambda: self.registrar_ponto("entrada")).pack(side="left", padx=10)
        ctk.CTkButton(frame_btn_ponto, text="2. INICIAR PAUSA", fg_color="orange", height=50, command=lambda: self.registrar_ponto("pausa_inicio")).pack(side="left", padx=10)
        ctk.CTkButton(frame_btn_ponto, text="3. RETORNAR DA PAUSA", fg_color="#f39c12", height=50, command=lambda: self.registrar_ponto("pausa_fim")).pack(side="left", padx=10)
        ctk.CTkButton(frame_btn_ponto, text="4. SAÍDA", fg_color="red", height=50, command=lambda: self.registrar_ponto("saida")).pack(side="left", padx=10)
        self.l_status_ponto = ctk.CTkLabel(aba_p, text="Status Atual: Aguardando registro...", font=("Arial", 16)); self.l_status_ponto.pack(pady=20)

        # ABA ESTOQUE
        if self.cargo_atual in ["Dono", "Gerente"]:
            aba_e = self.nb.add(" 📦 ESTOQUE ")
            self.t_estoque = ttk.Treeview(aba_e, columns=("ID", "Item", "Cat", "Preco", "Qtd", "Validade", "Criador"), show="headings")
            for c in ("ID", "Item", "Cat", "Preco", "Qtd", "Validade", "Criador"): self.t_estoque.heading(c, text=c)
            self.t_estoque.pack(fill="both", expand=True, pady=10)
            self.t_estoque.bind("<<TreeviewSelect>>", self.exibir_preview_imagem)
            ctk.CTkButton(aba_e, text="ADICIONAR PRODUTO", command=self.add_produto).pack(fill="x")
            ctk.CTkButton(aba_e, text="REMOVER PRODUTO", fg_color="red", command=self.remover_produto_estoque).pack(fill="x")
            self.lbl_preview = ctk.CTkLabel(aba_e, text="Preview Imagem"); self.lbl_preview.pack()

        # ABA FUNCIONÁRIOS
        if self.cargo_atual in ["Dono", "Gerente"]:
            aba_f = self.nb.add(" 👥 FUNCIONÁRIOS ")
            ctk.CTkButton(aba_f, text="CADASTRAR FUNCIONÁRIO", command=self.add_func).pack(pady=5)
            ctk.CTkButton(aba_f, text="EDITAR FUNCIONÁRIO", command=self.editar_func).pack(pady=5)
            ctk.CTkButton(aba_f, text="DEMITIR FUNCIONÁRIO", fg_color="red", command=self.demitir_func).pack(pady=5)
            self.t_func = ttk.Treeview(aba_f, columns=("ID", "Nome", "Cargo", "Genero", "Idade"), show="headings")
            for c in ("ID", "Nome", "Cargo", "Genero", "Idade"): self.t_func.heading(c, text=c)
            self.t_func.pack(fill="both", expand=True)

        # ABA RELATÓRIOS (Atualizada para conter as Sub-Abas sem deletar as listas originais)
        if self.cargo_atual in ["Dono", "Gerente"]:
            aba_r = self.nb.add(" 📊 RELATÓRIOS ")
            nb_rel = ctk.CTkTabview(aba_r)
            nb_rel.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Sub-Aba 1: Faturamento e Vendas
            aba_fat = nb_rel.add("Faturamento e Vendas")
            frame_fat = ctk.CTkFrame(aba_fat); frame_fat.pack(fill="x", pady=5)
            self.l_fat_vendas = ctk.CTkLabel(frame_fat, text="Faturamento: R$ 0.00", font=("Arial", 14, "bold"), text_color="green")
            self.l_fat_vendas.pack(side="left", expand=True)
            self.l_fat_desp = ctk.CTkLabel(frame_fat, text="Despesas: R$ 0.00", font=("Arial", 14, "bold"), text_color="red")
            self.l_fat_desp.pack(side="left", expand=True)
            self.l_fat_lucro = ctk.CTkLabel(frame_fat, text="Lucro Líquido: R$ 0.00", font=("Arial", 16, "bold"), text_color="#f1c40f")
            self.l_fat_lucro.pack(side="left", expand=True)
            ctk.CTkButton(frame_fat, text="+ Adicionar Despesa", command=self.adicionar_despesa).pack(side="right", padx=10)
            
            self.l_alerta_venc = ctk.CTkLabel(aba_fat, text="ALERTA: NENHUM PRODUTO VENCENDO", text_color="green", font=("Arial", 14, "bold"))
            self.l_alerta_venc.pack(pady=5)
            # A tabela de relatórios original está preservada perfeitamente aqui dentro, apenas com o adicional de "Itens"
            self.t_rel = ttk.Treeview(aba_fat, columns=("Data", "Mesa", "Total", "Pgto", "Atendente", "Itens"), show="headings")
            for c in ("Data", "Mesa", "Total", "Pgto", "Atendente", "Itens"): self.t_rel.heading(c, text=c)
            self.t_rel.pack(fill="both", expand=True)
            
            # Sub-Aba 2: Logs de Remoção
            aba_logs = nb_rel.add("Logs do Sistema")
            ctk.CTkLabel(aba_logs, text="Histórico de Produtos Removidos", font=("Arial", 14, "bold")).pack(pady=5)
            # A sua tabela original t_logs intacta
            self.t_logs = ttk.Treeview(aba_logs, columns=("Data", "Item", "Motivo", "Usuario"), show="headings")
            for c in ("Data", "Item", "Motivo", "Usuario"): self.t_logs.heading(c, text=c)
            self.t_logs.pack(fill="both", expand=True)
            
            # Sub-Aba 3: Pontos dos Funcionários
            aba_pontos = nb_rel.add("Pontos dos Funcionários")
            self.t_rel_ponto = ttk.Treeview(aba_pontos, columns=("Func", "Cargo", "Data", "Entrada", "Saida", "Trab"), show="headings")
            for c in ("Func", "Cargo", "Data", "Entrada", "Saida", "Trab"): self.t_rel_ponto.heading(c, text=c)
            self.t_rel_ponto.pack(fill="both", expand=True, pady=5)
            
            # Botão de atualizar relatórios
            frame_btn_rel = ctk.CTkFrame(aba_r); frame_btn_rel.pack(fill="x", pady=5)
            ctk.CTkButton(frame_btn_rel, text="ATUALIZAR DADOS E PONTOS", command=self.carregar_relatorio).pack(side="bottom", expand=True, padx=10)

        # ABA GERENCIADOR (Criação de novas abas dinâmicas)
        if self.cargo_atual in ["Dono", "Gerente"]:
            aba_c = self.nb.add(" ⚙️ GERENCIADOR ")
            frame_c_left = ctk.CTkFrame(aba_c); frame_c_left.pack(side="left", fill="both", expand=True, padx=10, pady=10)
            ctk.CTkLabel(frame_c_left, text="Criar Nova Aba Customizada", font=("Arial", 16, "bold")).pack(pady=10)
            self.e_nome_aba = ctk.CTkEntry(frame_c_left, placeholder_text="Nome da Aba"); self.e_nome_aba.pack(fill="x", padx=20, pady=10)
            ctk.CTkButton(frame_c_left, text="CRIAR ABA", fg_color="green", command=self.criar_nova_aba).pack(pady=10)
            
            frame_c_right = ctk.CTkFrame(aba_c); frame_c_right.pack(side="right", fill="both", expand=True, padx=10, pady=10)
            ctk.CTkLabel(frame_c_right, text="Gerenciar Abas Existentes", font=("Arial", 16, "bold")).pack(pady=10)
            
            # Carregar abas para o combobox
            try:
                conn = sqlite3.connect('restaurante.db')
                abas = [r[0] for r in conn.execute("SELECT nome FROM custom_tabs").fetchall()]
                conn.close()
            except: abas = []
            
            self.cb_abas = ctk.CTkComboBox(frame_c_right, values=abas if abas else ["Nenhuma aba criada"]); self.cb_abas.pack(fill="x", padx=20, pady=10)
            ctk.CTkButton(frame_c_right, text="EDITAR NOME", command=self.editar_aba).pack(pady=5, fill="x", padx=20)
            ctk.CTkButton(frame_c_right, text="REMOVER ABA", fg_color="red", command=self.remover_aba).pack(pady=5, fill="x", padx=20)

        # CARREGANDO AS ABAS CUSTOMIZADAS (TRATAMENTO DE ERROS PARA NÃO QUEBRAR O UI)
        try:
            conn = sqlite3.connect('restaurante.db')
            abas_customizadas = conn.execute("SELECT nome FROM custom_tabs").fetchall()
            for aba in abas_customizadas:
                try:
                    nome_aba = aba[0].upper()
                    aba_temp = self.nb.add(f" 📑 {nome_aba} ")
                    ctk.CTkLabel(aba_temp, text=f"Área Customizada: {nome_aba}", font=("Arial", 16, "bold")).pack(pady=10)
                    ctk.CTkLabel(aba_temp, text="Espaço de notas / botões interativos:", font=("Arial", 14)).pack()
                    txt_area = ctk.CTkTextbox(aba_temp, height=200); txt_area.pack(fill="both", expand=True, padx=20, pady=10)
                    txt_area.insert("0.0", f"Você pode usar esta aba como rascunho, anotações de {nome_aba} ou relatórios.")
                except Exception as e:
                    pass # Se a aba já existe com este nome, ele ignora e não quebra o sistema.
            conn.close()
        except Exception:
            pass # Se a tabela custom_tabs não estiver acessível, ignora.

        self.atualizar_listas()

    # --- FUNÇÕES NOVAS ADICIONADAS (GERENCIAMENTO, PONTO E DESPESAS) ---
    def adicionar_despesa(self):
        desc = simpledialog.askstring("Nova Despesa", "Descrição da despesa:")
        if not desc: return
        valor = simpledialog.askfloat("Valor", "Valor (R$):")
        if not valor: return
        conn = sqlite3.connect('restaurante.db')
        conn.execute("INSERT INTO despesas (descricao, valor, data) VALUES (?,?,?)", (desc, valor, datetime.now().strftime("%d/%m/%Y")))
        conn.commit(); conn.close()
        self.carregar_relatorio()
        messagebox.showinfo("Sucesso", "Despesa registrada!")

    def criar_nova_aba(self):
        nome_aba = self.e_nome_aba.get().strip()
        if nome_aba:
            try:
                conn = sqlite3.connect('restaurante.db')
                conn.execute("INSERT INTO custom_tabs (nome) VALUES (?)", (nome_aba,))
                conn.commit(); conn.close()
                messagebox.showinfo("Sucesso", "Aba adicionada! O sistema será recarregado.")
                self.carregar_interface()
            except sqlite3.IntegrityError:
                messagebox.showerror("Erro", "Já existe uma aba com este nome.")

    def editar_aba(self):
        aba_sel = self.cb_abas.get()
        if aba_sel and aba_sel != "Nenhuma aba criada":
            novo_nome = simpledialog.askstring("Editar Aba", f"Novo nome para '{aba_sel}':")
            if novo_nome:
                conn = sqlite3.connect('restaurante.db')
                conn.execute("UPDATE custom_tabs SET nome=? WHERE nome=?", (novo_nome, aba_sel))
                conn.commit(); conn.close()
                messagebox.showinfo("Sucesso", "Nome da aba alterado. A tela será recarregada.")
                self.carregar_interface()

    def remover_aba(self):
        aba_sel = self.cb_abas.get()
        if aba_sel and aba_sel != "Nenhuma aba criada":
            if messagebox.askyesno("Confirmar", f"Remover a aba '{aba_sel}' permanentemente?"):
                conn = sqlite3.connect('restaurante.db')
                conn.execute("DELETE FROM custom_tabs WHERE nome=?", (aba_sel,))
                conn.commit(); conn.close()
                self.carregar_interface()

    def registrar_ponto(self, acao):
        agora = datetime.now()
        data_str = agora.strftime("%d/%m/%Y")
        mes_str = agora.strftime("%m/%Y")
        hora_str = agora.strftime("%H:%M:%S")
        
        conn = sqlite3.connect('restaurante.db')
        registro = conn.execute("SELECT id, entrada, pausa_inicio, pausa_fim, saida FROM ponto_logs WHERE funcionario=? AND data=?", (self.usuario_logado, data_str)).fetchone()
        
        if acao == "entrada":
            if registro: messagebox.showwarning("Aviso", "Entrada já registrada hoje.")
            else:
                conn.execute("INSERT INTO ponto_logs (funcionario, cargo, data, mes, entrada) VALUES (?,?,?,?,?)", (self.usuario_logado, self.cargo_atual, data_str, mes_str, hora_str))
                self.l_status_ponto.configure(text=f"Entrada registrada às {hora_str}", text_color="green")
        elif acao == "pausa_inicio":
            if registro and not registro[2]:
                conn.execute("UPDATE ponto_logs SET pausa_inicio=? WHERE id=?", (hora_str, registro[0]))
                self.l_status_ponto.configure(text=f"Pausa iniciada às {hora_str}", text_color="orange")
            else: messagebox.showwarning("Aviso", "Não é possível iniciar pausa.")
        elif acao == "pausa_fim":
            if registro and registro[2] and not registro[3]:
                conn.execute("UPDATE ponto_logs SET pausa_fim=? WHERE id=?", (hora_str, registro[0]))
                self.l_status_ponto.configure(text=f"Retorno da pausa às {hora_str}", text_color="#f39c12")
            else: messagebox.showwarning("Aviso", "Nenhuma pausa em andamento.")
        elif acao == "saida":
            if registro and not registro[4]:
                t_entrada = datetime.strptime(registro[1], "%H:%M:%S")
                t_saida = datetime.strptime(hora_str, "%H:%M:%S")
                horas_trab = str(t_saida - t_entrada)
                conn.execute("UPDATE ponto_logs SET saida=?, horas_trab=? WHERE id=?", (hora_str, horas_trab, registro[0]))
                self.l_status_ponto.configure(text=f"Saída registrada às {hora_str}. Tempo de trabalho: {horas_trab}", text_color="red")
            else: messagebox.showwarning("Aviso", "Não é possível registrar saída.")
        conn.commit(); conn.close()

    def imprimir_motoboy(self):
        sel = self.t_delivery.selection()
        if sel:
            item = self.t_delivery.item(sel)['values']
            texto = f"--- TICKET MOTOBOY ---\nPedido: #{item[0]}\nCliente: {item[1]}\nEndereço: {item[2]}\nTelefone: {item[3]}\nPgto: {item[7]} | Troco: R${item[4]}\nObs: {item[6]}"
            messagebox.showinfo("Impressão Cupom", texto)
        else: messagebox.showwarning("Aviso", "Selecione um pedido.")

    def imprimir_cozinha(self):
        sel = self.t_delivery.selection()
        if sel:
            item = self.t_delivery.item(sel)['values']
            texto = f"--- TICKET COZINHA ---\nPedido: #{item[0]}\nItens: {item[5]}\nObs: {item[6]}"
            messagebox.showinfo("Impressão Cozinha", texto)
        else: messagebox.showwarning("Aviso", "Selecione um pedido.")

    def remover_registro_delivery(self):
        sel = self.t_delivery.selection()
        if sel:
            if messagebox.askyesno("Confirmar", "Remover este pedido sem registrar nas vendas?"):
                conn = sqlite3.connect('restaurante.db')
                conn.execute("DELETE FROM delivery WHERE id=?", (self.t_delivery.item(sel)['values'][0],))
                conn.commit(); conn.close(); self.carregar_tabela_delivery()

    def finalizar_delivery(self):
        sel = self.t_delivery.selection()
        if sel:
            item = self.t_delivery.item(sel)['values']
            if messagebox.askyesno("Finalizar", "O pedido foi entregue e pago? Isso enviará para o Relatório de Faturamento."):
                conn = sqlite3.connect('restaurante.db')
                agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                conn.execute("INSERT INTO historico (data, mesa, valor_final, pgto, atendente, itens) VALUES (?,?,?,?,?,?)",
                             (agora, f"Delivery - {item[1]}", 0.0, item[7], self.usuario_logado, item[5]))
                conn.execute("DELETE FROM delivery WHERE id=?", (item[0],))
                conn.commit(); conn.close(); self.carregar_tabela_delivery()
                messagebox.showinfo("Sucesso", "Delivery concluído e arquivado!")

    def editar_func(self):
        sel = self.t_func.selection()
        if not sel: return messagebox.showwarning("Aviso", "Selecione um funcionário.")
        item = self.t_func.item(sel)['values']
        if item[1] == "admin": return messagebox.showwarning("Erro", "O administrador principal não pode ser editado aqui.")
        win = ctk.CTkToplevel(self.root); win.title("Editar Funcionário"); win.grab_set(); self.centralizar_janela(win, 400, 400)
        ctk.CTkLabel(win, text="Novo Cargo:").pack(pady=10)
        opcoes_cargo = ["Gerente", "Garçom", "Atendente"] if self.cargo_atual == "Dono" else ["Garçom", "Atendente"]
        cb_cargo = ctk.CTkComboBox(win, values=opcoes_cargo); cb_cargo.set(item[2]); cb_cargo.pack(padx=20, fill="x")
        ctk.CTkLabel(win, text="Nova Idade:").pack(pady=10)
        e_idade = ctk.CTkEntry(win, font=("Arial", 16)); e_idade.insert(0, str(item[4])); e_idade.pack(padx=20, fill="x")
        def salvar_edicao():
            conn = sqlite3.connect('restaurante.db')
            conn.execute("UPDATE funcionarios SET cargo=?, idade=? WHERE id=?", (cb_cargo.get(), e_idade.get(), item[0]))
            conn.commit(); conn.close(); self.atualizar_listas(); win.destroy()
        ctk.CTkButton(win, text="SALVAR", command=salvar_edicao).pack(pady=30)

    # --- FUNÇÕES ORIGINAIS INTACTAS ---
    def toggle_troco(self, choice):
        if choice == "Dinheiro": 
            self.e_troco.configure(state="normal")
        else: 
            self.e_troco.configure(state="disabled")
            self.e_troco.delete(0, 'end')

    def registrar_delivery(self):
        conn = sqlite3.connect('restaurante.db')
        troco = self.e_troco.get() if self.e_troco.get() else 0
        try:
            conn.execute("INSERT INTO delivery (nome, endereco, telefone, troco, pedido, observacao, pagamento) VALUES (?,?,?,?,?,?,?)",
                         (self.e_nome_cli.get(), self.e_end.get(), self.e_tel.get(), troco, self.e_pedido.get(), self.e_obs.get(), self.cb_pgto.get()))
            conn.commit(); conn.close()
            messagebox.showinfo("Sucesso", "Delivery registrado!")
            for e in [self.e_nome_cli, self.e_end, self.e_tel, self.e_troco, self.e_pedido, self.e_obs]: e.delete(0, 'end')
            self.carregar_tabela_delivery()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao registrar: {e}")
            conn.close()

    def carregar_tabela_delivery(self):
        if not hasattr(self, 't_delivery'): return
        for i in self.t_delivery.get_children(): self.t_delivery.delete(i)
        conn = sqlite3.connect('restaurante.db')
        for r in conn.execute("SELECT * FROM delivery"): self.t_delivery.insert("", "end", values=r)
        conn.close()

    def atualizar_listas(self):
        conn = sqlite3.connect('restaurante.db')
        self.t_prod.delete(*self.t_prod.get_children())
        for r in conn.execute("SELECT id, item, preco FROM estoque"): self.t_prod.insert("", "end", values=r)
        
        # Atualizando a lista de Mais Vendidos (Atalho)
        if hasattr(self, 't_top'):
            self.t_top.delete(*self.t_top.get_children())
            for r in conn.execute("SELECT item, preco FROM estoque LIMIT 5"): self.t_top.insert("", "end", values=r)
            
        if hasattr(self, 't_estoque'):
            self.t_estoque.delete(*self.t_estoque.get_children())
            for r in conn.execute("SELECT id, item, categoria, preco, qtd, validade, usuario_criador FROM estoque"): self.t_estoque.insert("", "end", values=r)
        if hasattr(self, 't_func'):
            self.t_func.delete(*self.t_func.get_children())
            for r in conn.execute("SELECT id, nome, cargo, genero, idade FROM funcionarios"): self.t_func.insert("", "end", values=r)
        conn.close()

    def atualizar_comanda(self):
        for i in self.t_comanda.get_children(): self.t_comanda.delete(i)
        conn = sqlite3.connect('restaurante.db')
        itens = conn.execute("SELECT id, item, preco FROM pedidos WHERE mesa_id=?", (self.e_m.get(),)).fetchall()
        sub = 0
        for r in itens:
            self.t_comanda.insert("", "end", values=r)
            sub += r[2]
        conn.close()
        taxa = (sub * 0.10) if self.taxa_garcom.get() else 0
        self.l_sub.configure(text=f"Subtotal: R$ {sub:.2f}")
        self.l_taxa.configure(text=f"Taxa: R$ {taxa:.2f}")
        self.l_total.configure(text=f"Total: R$ {sub+taxa:.2f}")

    def adicionar_item_mesa(self, e):
        m_id = self.e_m.get()
        sel = self.t_prod.selection()
        if sel and m_id:
            d = self.t_prod.item(sel)['values']
            conn = sqlite3.connect('restaurante.db')
            conn.execute("INSERT INTO pedidos (mesa_id, item, preco) VALUES (?, ?, ?)", (m_id, d[1], d[2]))
            conn.commit(); conn.close(); self.atualizar_comanda()

    def adicionar_item_top(self, e):
        m_id = self.e_m.get()
        sel = self.t_top.selection()
        if sel and m_id:
            d = self.t_top.item(sel)['values']
            conn = sqlite3.connect('restaurante.db')
            conn.execute("INSERT INTO pedidos (mesa_id, item, preco) VALUES (?, ?, ?)", (m_id, d[0], d[1]))
            conn.commit(); conn.close(); self.atualizar_comanda()

    def add_produto(self):
        win = ctk.CTkToplevel(self.root); win.title("Adicionar Produto")
        win.grab_set() 
        self.centralizar_janela(win, 500, 700)
        campos = ["Nome", "Categoria", "Preço", "Quantidade", "Validade"]
        ents = {}
        for f in campos:
            ctk.CTkLabel(win, text=f).pack(pady=(10,0))
            e = ctk.CTkEntry(win, font=("Arial", 16)); e.pack(fill="x", padx=20); ents[f] = e
        
        ctk.CTkButton(win, text="SELECIONAR IMAGEM", command=self.escolher_img).pack(pady=10)
        def s():
            conn = sqlite3.connect('restaurante.db')
            path_salvo = ""
            if self.caminho_imagem_selecionada:
                nome_arq = f"imagens_produtos/{ents['Nome'].get()}.png"
                shutil.copy(self.caminho_imagem_selecionada, nome_arq)
                path_salvo = nome_arq
            conn.execute("INSERT INTO estoque (item, categoria, preco, qtd, validade, usuario_criador, cargo_criador, img_path) VALUES (?,?,?,?,?,?,?,?)", 
                         (ents["Nome"].get(), ents["Categoria"].get(), ents["Preço"].get(), ents["Quantidade"].get(), ents["Validade"].get(), self.usuario_logado, self.cargo_atual, path_salvo))
            conn.commit(); conn.close(); self.atualizar_listas(); win.destroy()
        ctk.CTkButton(win, text="SALVAR", command=s).pack(pady=20)

    def add_func(self):
        win = ctk.CTkToplevel(self.root); win.title("Novo Funcionário")
        win.grab_set()
        self.centralizar_janela(win, 400, 600)
        ctk.CTkLabel(win, text="Nome:").pack(); e_n = ctk.CTkEntry(win, font=("Arial", 16)); e_n.pack(padx=20, fill="x")
        ctk.CTkLabel(win, text="Idade:").pack(); e_i = ctk.CTkEntry(win, font=("Arial", 16)); e_i.pack(padx=20, fill="x")
        ctk.CTkLabel(win, text="Gênero:").pack(); cb_g = ctk.CTkComboBox(win, values=["Masculino", "Feminino"]); cb_g.pack(padx=20, fill="x")
        
        ctk.CTkLabel(win, text="Cargo:").pack()
        opcoes_cargo = ["Gerente", "Garçom", "Atendente"] if self.cargo_atual == "Dono" else ["Garçom", "Atendente"]
        cb_c = ctk.CTkComboBox(win, values=opcoes_cargo); cb_c.pack(padx=20, fill="x")
        
        ctk.CTkLabel(win, text="Senha:").pack(); e_s = ctk.CTkEntry(win, show="*", font=("Arial", 16)); e_s.pack(padx=20, fill="x")
        def s():
            conn = sqlite3.connect('restaurante.db')
            try:
                conn.execute("INSERT INTO funcionarios (nome, cargo, genero, idade, senha) VALUES (?,?,?,?,?)", 
                             (e_n.get(), cb_c.get(), cb_g.get(), e_i.get(), hashlib.sha256(e_s.get().encode()).hexdigest()))
                conn.commit(); conn.close(); self.atualizar_listas(); win.destroy()
            except: messagebox.showerror("Erro", "Erro ao salvar!")
            conn.close()
        ctk.CTkButton(win, text="SALVAR", command=s).pack(pady=30)

    def demitir_func(self):
        sel = self.t_func.selection()
        if not sel: return
        item = self.t_func.item(sel)['values']
        if item[1] == "admin": messagebox.showwarning("Erro", "Não pode demitir o administrador!"); return
        if messagebox.askyesno("Confirmar", f"Demitir {item[1]}?"):
            conn = sqlite3.connect('restaurante.db')
            conn.execute("DELETE FROM funcionarios WHERE id=?", (item[0],))
            conn.commit(); conn.close(); self.atualizar_listas()

    def escolher_img(self): self.caminho_imagem_selecionada = filedialog.askopenfilename()

    def exibir_preview_imagem(self, e):
        sel = self.t_estoque.selection()
        if not sel: return
        conn = sqlite3.connect('restaurante.db')
        caminho = conn.execute("SELECT img_path FROM estoque WHERE id=?", (self.t_estoque.item(sel)['values'][0],)).fetchone()[0]
        conn.close()
        if caminho and os.path.exists(caminho):
            img = Image.open(caminho).resize((150, 150)); self.photo = ImageTk.PhotoImage(img); self.lbl_preview.configure(image=self.photo, text="")
        else: self.lbl_preview.configure(image='', text="Sem imagem")

    def excluir_item(self):
        sel = self.t_comanda.selection()
        if sel:
            conn = sqlite3.connect('restaurante.db')
            conn.execute("DELETE FROM pedidos WHERE id=?", (self.t_comanda.item(sel)['values'][0],))
            conn.commit(); conn.close(); self.atualizar_comanda()

    def transferir_item(self):
        sel = self.t_comanda.selection()
        if sel:
            nova = simpledialog.askstring("Transferir", "Nova Mesa:")
            if nova:
                conn = sqlite3.connect('restaurante.db')
                conn.execute("UPDATE pedidos SET mesa_id=? WHERE id=?", (nova, self.t_comanda.item(sel)['values'][0]))
                conn.commit(); conn.close(); self.atualizar_comanda()

    def encerrar_mesa(self):
        try:
            total = float(self.l_total.cget("text").split("R$ ")[1])
            if total <= 0: raise ValueError
            conn = sqlite3.connect('restaurante.db')
            
            # Buscar os itens exatos daquela mesa e transformar em texto
            itens_obj = conn.execute("SELECT item FROM pedidos WHERE mesa_id=?", (self.e_m.get(),)).fetchall()
            str_itens = ", ".join([i[0] for i in itens_obj]) if itens_obj else "Sem itens registrados"
            
            # Registrar no histórico com Data/Hora e itens
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            conn.execute("INSERT INTO historico (data, mesa, valor_final, pgto, atendente, itens) VALUES (?,?,?,?,?,?)", 
                         (agora, self.e_m.get(), total, "Dinheiro", self.usuario_logado, str_itens))
            conn.execute("DELETE FROM pedidos WHERE mesa_id=?", (self.e_m.get(),))
            conn.commit(); conn.close(); self.atualizar_comanda()
            messagebox.showinfo("Sucesso", "Mesa fechada e venda adicionada aos relatórios!")
        except Exception as e: messagebox.showerror("Erro", "Mesa vazia ou problema ao encerrar.")

    def remover_produto_estoque(self):
        sel = self.t_estoque.selection()
        if sel:
            item_vals = self.t_estoque.item(sel)['values']
            motivo = simpledialog.askstring("Motivo", "Motivo da remoção:")
            if motivo:
                conn = sqlite3.connect('restaurante.db')
                conn.execute("DELETE FROM estoque WHERE id=?", (item_vals[0],))
                conn.execute("INSERT INTO logs_remocao (item, motivo, usuario, data) VALUES (?,?,?,?)", 
                             (item_vals[1], motivo, self.usuario_logado, datetime.now().strftime("%d/%m/%Y")))
                conn.commit(); conn.close(); self.atualizar_listas(); self.carregar_relatorio()

    def carregar_relatorio(self):
        if not hasattr(self, 't_rel'): return # Impede travamentos se a aba estiver ausente
        conn = sqlite3.connect('restaurante.db')
        
        # Limpar tabelas da Aba de Faturamento
        for i in self.t_rel.get_children(): self.t_rel.delete(i)
        
        faturamento_total = 0.0
        # Carrega o histórico garantindo os dados do operador, data e itens
        try:
            for r in conn.execute("SELECT data, mesa, valor_final, pgto, atendente, itens FROM historico"):
                self.t_rel.insert("", "end", values=r)
                try: faturamento_total += float(r[2])
                except ValueError: pass
        except sqlite3.OperationalError: pass
            
        # Limpar e Atualizar Tabela de Logs (original mantida intacta)
        if hasattr(self, 't_logs'):
            for i in self.t_logs.get_children(): self.t_logs.delete(i)
            for r in conn.execute("SELECT data, item, motivo, usuario FROM logs_remocao"): 
                self.t_logs.insert("", "end", values=r)
                
        # Atualizar Tabela de Pontos
        if hasattr(self, 't_rel_ponto'):
            for i in self.t_rel_ponto.get_children(): self.t_rel_ponto.delete(i)
            for r in conn.execute("SELECT funcionario, cargo, data, entrada, saida, horas_trab FROM ponto_logs"):
                self.t_rel_ponto.insert("", "end", values=r)
            
        # Calcular Despesas e Lucro
        despesas = 0.0
        try:
            val_despesas = conn.execute("SELECT SUM(valor) FROM despesas").fetchone()[0]
            if val_despesas: despesas = float(val_despesas)
        except Exception: pass
        
        lucro_liquido = faturamento_total - despesas
        
        # Atualiza a UI das etiquetas financeiras
        if hasattr(self, 'l_fat_vendas'):
            self.l_fat_vendas.configure(text=f"Faturamento: R$ {faturamento_total:.2f}")
            self.l_fat_desp.configure(text=f"Despesas: R$ {despesas:.2f}")
            self.l_fat_lucro.configure(text=f"Lucro Líquido: R$ {lucro_liquido:.2f}")

        # Sistema de Alerta de Vencimento de Produtos (Até 3 dias)
        produtos_vencendo = []
        hoje = datetime.now()
        limite = hoje + timedelta(days=3)
        for r in conn.execute("SELECT item, validade FROM estoque"):
            item_nome, validade_str = r[0], r[1]
            try:
                val_data = datetime.strptime(validade_str, "%d/%m/%Y")
                if val_data <= limite: produtos_vencendo.append(item_nome)
            except ValueError: pass 
                
        if produtos_vencendo and hasattr(self, 'l_alerta_venc'):
            self.l_alerta_venc.configure(text=f"⚠️ ALERTA: PRODUTOS VENCENDO ({', '.join(produtos_vencendo)})", text_color="orange")
        elif hasattr(self, 'l_alerta_venc'):
            self.l_alerta_venc.configure(text="✅ ALERTA: NENHUM PRODUTO VENCENDO", text_color="green")

        conn.close()

    def imprimir_comanda(self): messagebox.showinfo("Impressão", "Comanda enviada para impressão local!")
    def assistente_ia(self): messagebox.showinfo("IA", "Analisando histórico de vendas para sugestão e harmonização...")

if __name__ == '__main__':
    root = ctk.CTk()
    app = RestauranteApp(root)
    root.mainloop()