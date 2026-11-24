#!/usr/bin/env python3
"""Gera as páginas das disciplinas do curso de Engenharia de Computação (2027).

Lê os fontes LaTeX do PPC que ficam em extra/:
  - extra/disciplinasDB.sty                 nomes, carga horária e créditos
  - extra/fluxogramaEngenhariaComputacao.tex período de cada disciplina
  - extra/ementas/*.tex                     ementa, objetivos, professor, pré-requisitos
  - extra/ementas/bibliografia.bib          bibliografia (filtrada pela palavra-chave da ementa)

e escreve um arquivo .md por disciplina em content/course/.
Os arquivos gerados são sobrescritos a cada execução; não edite à mão.

Uso:  python3 gera_disciplinas.py
"""
import glob
import os
import re
import subprocess
import sys
import unicodedata
from datetime import date

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

RAIZ = os.path.dirname(os.path.abspath(__file__))
EXTRA = os.path.join(RAIZ, "extra")
SAIDA = os.path.join(RAIZ, "content", "course")
MARCA = "# gerado por gera_disciplinas.py"

# Professor (macro do disciplinasDB) -> título da página do professor no site
PROFESSORES = {
    "cristiana": "Cristiana Bentes, D.Sc.",
    "felipe": "Felipe Ulrichsen, M.Sc.",
    "gabriel": "Gabriel de Carvalho, D.Sc.",
    "giomar": "Giomar Sequeiros, Dr.",
    "araujo": "João Araujo, Dr.",
    "luiza": "Luiza Mourelle, Ph.D.",
    "margareth": "Margareth Simões, D.Sc.",
    "luigi": "Luigi Maciel Ribeiro, M.Sc.",
    "rafaela": "Rafaela Brum, Ds.C.",
    "robert": "Robert Mota, Dr.",
    "simone": "Simone Gama, M.Sc.",
    "thiago": "Thiago Medeiros, D.Sc.",
}

# Imagem de capa (reaproveita as imagens existentes do site)
# imagens próprias de cada disciplina: static/images/courses/2027/<chave em minúsculas>.jpg
# (fontes e licenças em content/creditos-imagens.md)
DIR_IMAGENS = "images/courses/2027"
IMAGEM_PADRAO = "images/banner/disciplina.jpg"


def imagem(chave):
    caminho = f"{DIR_IMAGENS}/{chave.lower()}.jpg"
    return caminho if os.path.exists(os.path.join(RAIZ, "static", caminho)) else IMAGEM_PADRAO


def le(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def sem_comentarios(tex):
    return re.sub(r"(?<!\\)%.*", "", tex)


def argumento(tex, inicio):
    """Devolve (conteúdo, fim) do grupo {…} que começa em tex[inicio] == '{'."""
    nivel = 0
    for i in range(inicio, len(tex)):
        if tex[i] == "{" and tex[i - 1] != "\\":
            nivel += 1
        elif tex[i] == "}" and tex[i - 1] != "\\":
            nivel -= 1
            if nivel == 0:
                return tex[inicio + 1:i], i + 1
    raise ValueError("chave sem par")


def comando(tex, nome):
    """Argumento de \\nome{…} (primeira ocorrência), ou None."""
    m = re.search(r"\\" + nome + r"\s*(?=\{)", tex)
    if not m:
        return None
    return argumento(tex, m.end())[0].strip()


# ---------------------------------------------------------------- base de dados
def le_base():
    tex = sem_comentarios(le(os.path.join(EXTRA, "disciplinasDB.sty")))
    macros = {}
    for m in re.finditer(r"\\newcommand\s*\{\\(\w+)\}\s*(?=\{)", tex):
        macros[m.group(1)] = argumento(tex, m.end())[0]
    disciplinas = {}
    for nome in macros:
        if nome + "CH" in macros and nome + "Cred" in macros:
            disciplinas[nome] = {
                "nome": macros[nome],
                "ch": int(macros[nome + "CH"]),
                "cred": int(macros[nome + "Cred"]),
                "codigo": macros.get(nome + "Cod", ""),
            }
    return macros, disciplinas


def le_periodos():
    tex = sem_comentarios(le(os.path.join(EXTRA, "fluxogramaEngenhariaComputacao.tex")))
    periodos = {}
    for m in re.finditer(r"\\disciplina\{(\w+)\}\{(\d+)\}\{\d+\}\s*\{\\(\w+)Cod\}", tex):
        periodos[m.group(3)] = (int(m.group(2)), m.group(1))
    return periodos


# ---------------------------------------------------------------- texto
def troca_macros(tex, macros):
    def sub(m):
        nome = m.group(1)
        return macros[nome] if nome in macros else m.group(0)
    return re.sub(r"\\([A-Za-z]+)(?![A-Za-z])", sub, tex)


def latex_para_md(tex, macros):
    tex = troca_macros(tex, macros).strip()
    if not tex:
        return ""
    md = subprocess.run(
        ["pandoc", "-f", "latex", "-t", "gfm", "--wrap=none"],
        input=tex, capture_output=True, text=True, check=True,
    ).stdout
    md = re.sub(r"\$`?([^$`]*)`?\$", r"\1", md)  # matemática simples: $k$ -> k
    return md.strip()


# ---------------------------------------------------------------- bibliografia
def le_bibliografia():
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    with open(os.path.join(EXTRA, "ementas", "bibliografia.bib"), encoding="utf-8") as f:
        return bibtexparser.load(f, parser=parser).entries


def autores(campo):
    nomes = [a.strip() for a in re.split(r"\s+and\s+", campo) if a.strip()]
    if "others" in nomes:
        nomes = nomes[:1] + ["others"] * 3  # força "et al."
    saida = []
    for n in nomes:
        if "," in n:
            sobrenome, prenome = [p.strip() for p in n.split(",", 1)]
            saida.append(f"{sobrenome.upper()}, {prenome}" if prenome else sobrenome.upper())
        else:
            saida.append(n)
    if len(saida) > 3:
        return saida[0] + " et al."
    return "; ".join(saida)


def limpa(s):
    s = re.sub(r"[{}]", "", s or "").strip()
    # \'{\i} vira "ı" + acento combinante; normaliza para "í"
    s = s.replace("ı́", "í").replace("ı", "i")
    return unicodedata.normalize("NFC", s)


def ponto(s):
    return s if s.endswith(".") else s + "."


def referencia(e):
    partes = []
    if e.get("author"):
        partes.append(ponto(autores(limpa(e["author"]))))
    titulo = limpa(e.get("title"))
    if titulo:
        partes.append(f"*{titulo}*.")
    if e.get("edition"):
        ed = limpa(e["edition"])
        partes.append(f"{ed}. ed." if ed.isdigit() else ponto(ed))
    pub = ", ".join(x for x in (limpa(e.get("publisher") or e.get("journal") or e.get("howpublished")), limpa(e.get("year"))) if x)
    if pub:
        partes.append(pub + ".")
    if e.get("url"):
        partes.append(f"Disponível em: <{limpa(e['url'])}>.")
    return " ".join(partes)


def bibliografia(entradas, chave):
    basica, complementar = [], []
    for e in entradas:
        chaves = [k.strip() for k in e.get("keywords", "").split(",")]
        if chave not in chaves:
            continue
        (complementar if e.get("entrysubtype") == "ref" else basica).append(referencia(e))
    return sorted(basica), sorted(complementar)


# ---------------------------------------------------------------- saída
def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def yaml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def resumo(texto, limite=200):
    texto = re.sub(r"[*_`#>]", "", texto).replace("\n", " ").strip()
    if len(texto) <= limite:
        return texto
    return texto[:limite].rsplit(" ", 1)[0] + "…"


def main():
    macros, base = le_base()
    periodos = le_periodos()
    entradas = le_bibliografia()

    # remove apenas as páginas geradas anteriormente
    for f in glob.glob(os.path.join(SAIDA, "*.md")):
        if MARCA in le(f):
            os.remove(f)

    ementas = {}
    for arq in sorted(glob.glob(os.path.join(EXTRA, "ementas", "*.tex"))):
        tex = sem_comentarios(le(arq))
        ementas[arq] = (tex, (comando(tex, "ndisciplina") or "").lstrip("\\"))
    com_ementa = {chave for _, chave in ementas.values()}

    geradas = []
    for arq, (tex, chave) in ementas.items():
        if chave not in base:
            print(f"AVISO: {os.path.basename(arq)}: disciplina '{chave}' não está no disciplinasDB", file=sys.stderr)
            continue
        d = base[chave]
        eletiva = "\\naoobrigatoria" in tex
        periodo = periodos.get(chave, (None, None))[0]
        if not eletiva and periodo is None:
            print(f"AVISO: {d['nome']} não aparece no fluxograma", file=sys.stderr)

        creditos = {k: int(comando(tex, "cred" + k) or 0) for k in ("teorica", "lab", "pratica", "extensao")}
        prof = (comando(tex, "nomeprofessor") or "").lstrip("\\")

        internos, externos = [], []
        for campo in ("preum", "predois", "pretres"):
            p = (comando(tex, campo) or "").lstrip("\\")
            if not p or p not in base:
                continue
            # pré-requisito com ementa própria tem página no site -> vira link
            (internos if p in com_ementa else externos).append(base[p]["nome"])

        ementa = latex_para_md(comando(tex, "ementa") or "", macros)
        objetivos = latex_para_md(comando(tex, "objetivos") or "", macros)
        basica, complementar = bibliografia(entradas, comando(tex, "formementa") or "")

        fm = [
            "---",
            MARCA + " a partir de extra/ — não edite à mão",
            f"title: {yaml_str(d['nome'])}",
            f"date: {date.today().isoformat()}",
            "draft: false",
            f"image: {yaml_str(imagem(chave))}",
            f"weight: {(periodo or 11) * 10}",
            f"creditos: {d['cred']}",
            f"cht: \"{d['ch']} horas\"",
            f"chs: \"{d['ch'] // 15} horas\"",
        ]
        if creditos["teorica"]:
            fm.append(f"chteorica: \"{creditos['teorica']} horas\"")
        if creditos["lab"]:
            fm.append(f"chlab: \"{creditos['lab']} horas\"")
        if creditos["pratica"]:
            fm.append(f"chpratica: \"{creditos['pratica']} horas\"")
        if creditos["extensao"]:
            fm.append(f"chextensao: \"{creditos['extensao']} horas\"")
        codigo = d["codigo"] if "xxx" not in d["codigo"] else "A definir"
        fm.append(f"codigo: {yaml_str(codigo)}")
        fm.append(f"periodo: {yaml_str('Eletiva') if eletiva else periodo}")
        if eletiva:
            fm.append("eletiva: true")
        if internos:
            fm.append("prerequisitos: [" + ", ".join(yaml_str(x) for x in internos) + "]")
        if externos:
            fm.append("prerequisitosfora:")
            fm += [f"  - prereqext: {yaml_str(x)}" for x in externos]
        if prof in PROFESSORES:
            fm.append(f"teacher: {yaml_str(PROFESSORES[prof])}")
        fm.append(f"summary: {yaml_str(resumo(objetivos or ementa))}")
        fm.append("---")

        corpo = []
        if objetivos:
            corpo += ["## Objetivos", objetivos, ""]
        if ementa:
            corpo += ["## Ementa", ementa, ""]
        if basica:
            corpo += ["## Bibliografia básica"] + [f"- {r}" for r in basica] + [""]
        if complementar:
            corpo += ["## Bibliografia complementar"] + [f"- {r}" for r in complementar] + [""]

        destino = os.path.join(SAIDA, slug(d["nome"]) + ".md")
        with open(destino, "w", encoding="utf-8") as f:
            f.write("\n".join(fm) + "\n" + "\n".join(corpo))
        geradas.append((periodo or 99, d["nome"], os.path.basename(destino)))

    for p, nome, arq in sorted(geradas):
        print(f"{'Eletiva' if p == 99 else str(p) + 'º':>8}  {nome}  ->  content/course/{arq}")
    print(f"{len(geradas)} disciplinas geradas")


if __name__ == "__main__":
    main()
