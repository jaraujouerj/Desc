#!/usr/bin/env python3
"""
Gerador de JSON para Projetos de Graduação Defendidos.
Cria arquivos JSON no formato esperado pelo site Hugo do DESC.
"""

import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from unicodedata import normalize, category


# Diretório padrão para salvar os JSONs
DEFAULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "projetos_defendidos")


def normalizar_nome_arquivo(nome: str) -> str:
    """Converte nome do aluno em nome de arquivo seguro (sem acentos, lowercase, underscores)."""
    # Remove acentos
    nfkd = normalize("NFKD", nome)
    sem_acento = "".join(c for c in nfkd if category(c) != "Mn" and c.isascii())
    # Converte para lowercase, troca espaços e hífens por underscore
    limpo = re.sub(r"[^a-z0-9]+", "_", sem_acento.lower().strip())
    return limpo.strip("_")


class AppProjetoDefendido(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cadastro de Projeto de Graduação Defendido")
        self.geometry("700x580")
        self.resizable(True, True)

        self.dir_saida = tk.StringVar(value=DEFAULT_DIR)
        self._criar_widgets()

    def _criar_widgets(self):
        pad = {"padx": 10, "pady": 5}

        # --- Diretório de saída ---
        frm_dir = ttk.LabelFrame(self, text="Diretório de saída")
        frm_dir.pack(fill="x", **pad)

        ttk.Entry(frm_dir, textvariable=self.dir_saida, width=70).pack(
            side="left", fill="x", expand=True, padx=(10, 5), pady=5)
        ttk.Button(frm_dir, text="Alterar…", command=self._escolher_dir).pack(
            side="right", padx=(0, 10), pady=5)

        # --- Dados do projeto ---
        frm_dados = ttk.LabelFrame(self, text="Dados do Projeto")
        frm_dados.pack(fill="both", expand=True, **pad)

        row = 0
        ttk.Label(frm_dados, text="Nome do Aluno:").grid(
            row=row, column=0, sticky="w", padx=10, pady=5)
        self.ent_nome = ttk.Entry(frm_dados, width=60)
        self.ent_nome.grid(row=row, column=1, sticky="ew", padx=10, pady=5)

        row += 1
        ttk.Label(frm_dados, text="Título do TCC:").grid(
            row=row, column=0, sticky="w", padx=10, pady=5)
        self.ent_titulo = ttk.Entry(frm_dados, width=60)
        self.ent_titulo.grid(row=row, column=1, sticky="ew", padx=10, pady=5)

        row += 1
        ttk.Label(frm_dados, text="Orientador:").grid(
            row=row, column=0, sticky="w", padx=10, pady=5)
        self.professores = [
            "Cristiana Bentes, Dra.",
            "Felipe Ulrichsen",
            "Gabriel Cardoso, Dr.",
            "Giomar Sequeiros, Dr.",
            "João Araujo, Dr.",
            "Luigi Maciel",
            "Luiza Mourelle, Dra.",
            "Margareth Simões, Dra.",
            "Rafaela Brum, Dra.",
            "Robert Mota, Dr.",
            "Simone Gama",
            "Thiago Medeiros, Dr.",
        ]
        self.cmb_orientador = ttk.Combobox(frm_dados, values=self.professores,
                                            state="readonly", width=40)
        self.cmb_orientador.grid(row=row, column=1, sticky="ew", padx=10, pady=5)

        row += 1
        ttk.Label(frm_dados, text="Ano da Defesa:").grid(
            row=row, column=0, sticky="w", padx=10, pady=5)
        self.ent_ano = ttk.Spinbox(frm_dados, from_=2000, to=2099, width=10)
        self.ent_ano.set(2026)
        self.ent_ano.grid(row=row, column=1, sticky="w", padx=10, pady=5)

        row += 1
        ttk.Label(frm_dados, text="Semestre:").grid(
            row=row, column=0, sticky="w", padx=10, pady=5)
        self.cmb_semestre = ttk.Combobox(frm_dados, values=["1", "2"],
                                          state="readonly", width=5)
        self.cmb_semestre.set("1")
        self.cmb_semestre.grid(row=row, column=1, sticky="w", padx=10, pady=5)

        row += 1
        ttk.Label(frm_dados, text="Resumo:").grid(
            row=row, column=0, sticky="nw", padx=10, pady=5)
        self.txt_resumo = tk.Text(frm_dados, width=60, height=8, wrap="word")
        self.txt_resumo.grid(row=row, column=1, sticky="ew", padx=10, pady=5)

        frm_dados.columnconfigure(1, weight=1)

        # --- Botões ---
        frm_btn = ttk.Frame(self)
        frm_btn.pack(fill="x", **pad)

        ttk.Button(frm_btn, text="Gerar JSON", command=self._gerar_json).pack(
            side="right", padx=5)
        ttk.Button(frm_btn, text="Limpar", command=self._limpar).pack(
            side="right", padx=5)

        # --- Status ---
        self.lbl_status = ttk.Label(self, text="", foreground="green")
        self.lbl_status.pack(fill="x", padx=10, pady=(0, 10))

    def _escolher_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_saida.get(),
                                     title="Escolha o diretório de saída")
        if d:
            self.dir_saida.set(d)

    def _validar(self) -> bool:
        if not self.ent_nome.get().strip():
            messagebox.showwarning("Campo obrigatório", "Preencha o nome do aluno.")
            self.ent_nome.focus()
            return False
        if not self.ent_titulo.get().strip():
            messagebox.showwarning("Campo obrigatório", "Preencha o título do TCC.")
            self.ent_titulo.focus()
            return False
        if not self.cmb_orientador.get().strip():
            messagebox.showwarning("Campo obrigatório", "Selecione o orientador.")
            self.cmb_orientador.focus()
            return False
        try:
            ano = int(self.ent_ano.get())
            if ano < 2000 or ano > 2099:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Campo inválido", "Ano deve ser um número entre 2000 e 2099.")
            self.ent_ano.focus()
            return False
        return True

    def _gerar_json(self):
        if not self._validar():
            return

        nome = self.ent_nome.get().strip()
        titulo = self.ent_titulo.get().strip()
        orientador = self.cmb_orientador.get().strip()
        ano = int(self.ent_ano.get())
        semestre = int(self.cmb_semestre.get())
        resumo = self.txt_resumo.get("1.0", "end").strip()

        dados = {
            "nome": nome,
            "titulo": titulo,
            "orientador": orientador,
            "ano": ano,
            "semestre": semestre,
            "resumo": resumo
        }

        nome_arquivo = normalizar_nome_arquivo(nome) + ".json"
        dir_saida = self.dir_saida.get()
        os.makedirs(dir_saida, exist_ok=True)
        caminho = os.path.join(dir_saida, nome_arquivo)

        if os.path.exists(caminho):
            resp = messagebox.askyesno(
                "Arquivo já existe",
                f"O arquivo '{nome_arquivo}' já existe.\nDeseja sobrescrevê-lo?")
            if not resp:
                return

        try:
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=4)
                f.write("\n")
            self.lbl_status.config(
                text=f"✓ Arquivo salvo: {caminho}",
                foreground="green")
            messagebox.showinfo("Sucesso", f"Arquivo criado:\n{caminho}")
        except OSError as e:
            messagebox.showerror("Erro", f"Não foi possível salvar o arquivo:\n{e}")

    def _limpar(self):
        self.ent_nome.delete(0, "end")
        self.ent_titulo.delete(0, "end")
        self.cmb_orientador.set("")
        self.ent_ano.set(2026)
        self.cmb_semestre.set("1")
        self.txt_resumo.delete("1.0", "end")
        self.lbl_status.config(text="")


if __name__ == "__main__":
    app = AppProjetoDefendido()
    app.mainloop()
