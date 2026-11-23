#!/usr/bin/env python3
"""
Converte o HTML exportado pelo FET (formato "groups_days_horizontal")
em data/pt/horarios.yaml, no mesmo formato gerado por converteXml2Yaml.py.

Uso:
    python3 converteHtml2Yaml.py desc2026-2_groups_days_horizontal_v02.html
    python3 converteHtml2Yaml.py arquivo.html --semestre 2026/2 --saida data/pt/horarios.yaml

Tipos de tabela reconhecidos no HTML:
  * "N Grupo Automático"   -> turma "N° Período <semestre>"
                              (célula: disciplina / professor / [sala])
  * Energia / Produção     -> turmas do 1° período; se a tabela for cópia de
                              outra (erro comum de exportação), é ignorada e as
                              aulas são obtidas da tabela da sala LABBAS
  * 5023D, 5029D, 5032D, LABBAS -> ocupação das salas
                              (célula: disciplina / Turma X / professor /
                               período / [curso])
"""
import argparse
import difflib
import re
import sys
import unicodedata

import yaml
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
HORARIOS = {
    "M1": ("07:00", "07:50"), "M2": ("07:50", "08:40"), "M3": ("08:50", "09:40"),
    "M4": ("09:40", "10:30"), "M5": ("10:40", "11:30"), "M6": ("11:30", "12:20"),
    "T1": ("12:30", "13:20"), "T2": ("13:20", "14:10"), "T3": ("14:20", "15:10"),
    "T4": ("15:10", "16:00"), "T5": ("16:10", "17:00"), "T6": ("17:00", "17:50"),
    "N1": ("18:00", "18:50"), "N2": ("18:50", "19:40"), "N3": ("19:40", "20:30"),
}
DAY_ORDER = {"Seg": 0, "Ter": 1, "Qua": 2, "Qui": 3, "Sex": 4, "Sáb": 5, "Dom": 6}

# Nome da tabela de sala no HTML -> nome usado no site
SALAS = {"5023D": "5023D", "5029D": "5029D", "5032D": "5032D", "LABBAS": "LabBas"}

TURMA_ENERGIA = "1° Período - Energia Renováveis"
TURMA_PRODUCAO = "1° Período - Eng. de Produção"

# Grafias alternativas de professores -> nome canônico
PROFESSOR_ALIAS = {
    "Joao Araujo": "João Araujo",
    "João": "João Araujo",
    "Mario João": "Mário João",
    "Mário": "Mário João",
    "Luiza": "Luiza Mourelle",
    "Robert": "Robert Mota",
    "Rafaela Brum": "Rafaela",
    "Gabriel Cardoso": "Gabriel",
}

VAZIO = {"", "-x-", "---"}


# ---------------------------------------------------------------------------
# Leitura das tabelas
# ---------------------------------------------------------------------------
def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def ler_tabela(table):
    """Retorna {(dia, slot): [linhas da célula]} expandindo rowspan/colspan."""
    dias = [th.get_text(strip=True) for th in table.thead.find_all("th")]
    grade = {}          # (linha, coluna) -> linhas
    ocupado = set()
    slots = []
    for r, tr in enumerate(table.tbody.find_all("tr", recursive=False)):
        th = tr.find("th")
        if th is None:  # linha de rodapé ("Horário gerado por FET...")
            continue
        slots.append(th.get_text(strip=True))
        c = 0
        for td in tr.find_all("td", recursive=False):
            while (r, c) in ocupado:
                c += 1
            linhas = [x.strip() for x in td.get_text("\n").split("\n") if x.strip()]
            rs, cs = int(td.get("rowspan", 1)), int(td.get("colspan", 1))
            for dr in range(rs):
                for dc in range(cs):
                    ocupado.add((r + dr, c + dc))
                    if linhas and linhas[0] not in VAZIO:
                        grade[(r + dr, c + dc)] = linhas
            c += cs
    return {(dias[c], slots[r]): v for (r, c), v in grade.items()
            if r < len(slots) and c < len(dias)}


def agrupar(blocos, chave):
    """Ordena por dia/horário e junta blocos consecutivos com a mesma chave."""
    blocos.sort(key=lambda x: (DAY_ORDER.get(x["dia"], 99), x["inicio"]))
    out = []
    for b in blocos:
        if out and out[-1]["dia"] == b["dia"] and all(out[-1][k] == b[k] for k in chave):
            out[-1]["fim"] = b["fim"]
        else:
            out.append(dict(b))
    return out


def canon_professor(nome):
    return PROFESSOR_ALIAS.get(nome, nome)


# ---------------------------------------------------------------------------
# Conversão
# ---------------------------------------------------------------------------
def converter(html_path, semestre, usar_salas=True):
    soup = BeautifulSoup(open(html_path, encoding="utf-8-sig"), "html.parser")
    tabelas = []
    for t in soup.find_all("table", id=True):
        nome = t.caption.find("span", class_="name").get_text(strip=True)
        tabelas.append((nome, str(t.tbody), ler_tabela(t)))

    avisos = []
    turmas = {}      # nome -> lista de blocos individuais
    salas_raw = {}   # nome da sala -> {(dia, slot): linhas}
    vistas = {}      # conteúdo do tbody -> nome da tabela (detecta cópias)

    for nome, corpo, celulas in tabelas:
        if nome.upper() in SALAS:
            salas_raw[SALAS[nome.upper()]] = celulas
            continue

        m = re.match(r"(\d+)\s+Grupo", nome)
        if m:
            turma = f"{m.group(1)}° Período {semestre}"
        elif sem_acento(nome).startswith("energia"):
            turma = TURMA_ENERGIA
        elif sem_acento(nome).startswith("produc"):
            turma = TURMA_PRODUCAO
        else:
            turma = nome

        if corpo in vistas:
            avisos.append(f"Tabela '{nome}' é cópia idêntica de '{vistas[corpo]}' — ignorada "
                          f"(as aulas de '{turma}' serão obtidas da sala LabBas, se houver).")
            continue
        vistas[corpo] = nome

        blocos = turmas.setdefault(turma, [])
        for (dia, slot), linhas in celulas.items():
            ini, fim = HORARIOS[slot]
            blocos.append({
                "dia": dia, "inicio": ini, "fim": fim,
                "disciplina": linhas[0],
                "professor": canon_professor(linhas[1]) if len(linhas) > 1 else "A definir",
                "sala": linhas[2] if len(linhas) > 2 else "Sem sala",
            })

    # Índice das aulas das turmas, para padronizar os nomes vindos das salas
    disciplinas_turmas = sorted({b["disciplina"] for bl in turmas.values() for b in bl})
    por_horario = {}
    for turma, bl in turmas.items():
        for b in bl:
            por_horario.setdefault((b["dia"], b["inicio"]), []).append((turma, b))

    salas = []
    for sala, celulas in salas_raw.items():
        blocos = []
        for (dia, slot), linhas in celulas.items():
            ini, fim = HORARIOS[slot]
            disc = linhas[0]
            sub = next((x for x in linhas[1:] if x.lower().startswith("turma")), None)
            resto = [x for x in linhas[1:] if x != sub]
            prof = canon_professor(resto[0]) if resto else "A definir"
            periodo = resto[1] if len(resto) > 1 else ""
            curso = resto[2] if len(resto) > 2 else ""

            # Aulas do 1° período de Energia/Produção (Algoritmos no LabBas)
            cursos = [sem_acento(c) for c in re.split(r"[\\/]", curso) if c]
            if any(c.startswith(("energia", "produc")) for c in cursos):
                disc_t = f"{disc} I - {sub}" if sub else disc
                destinos = [TURMA_ENERGIA if c.startswith("energia") else TURMA_PRODUCAO
                            for c in cursos]
                for t in destinos:
                    turmas.setdefault(t, []).append({"dia": dia, "inicio": ini, "fim": fim,
                                      "disciplina": disc_t, "professor": prof, "sala": sala})
                blocos.append({"dia": dia, "inicio": ini, "fim": fim, "disciplina": disc_t,
                               "professor": prof, "sala": sala, "turma": " / ".join(destinos)})
                continue

            # Tenta casar com a aula da turma no mesmo horário (nomes padronizados)
            num = re.match(r"(\d+)", periodo)
            turma = None
            if num and not curso and "(detel)" not in disc.lower():
                turma = f"{num.group(1)}° Período {semestre}"
                cand = [b for t, b in por_horario.get((dia, ini), []) if t == turma]
                match = difflib.get_close_matches(disc, [b["disciplina"] for b in cand], 1, 0.5)
                if match:
                    b = next(b for b in cand if b["disciplina"] == match[0])
                    disc, prof = b["disciplina"], b["professor"]
                else:
                    # mesmo sufixo final (I, II, A, B, XI-A...) é obrigatório
                    mesmos = [d for d in disciplinas_turmas if d.split()[-1] == disc.split()[-1]]
                    match = difflib.get_close_matches(disc, mesmos, 1, 0.75)
                    if match:
                        disc = match[0]
                        b = next(b for bl in turmas.values() for b in bl if b["disciplina"] == disc)
                        prof = b["professor"] if prof.split()[0] in b["professor"] else prof
            if turma is None:
                if "pós" in periodo.lower():
                    turma = "Pós-graduação"
                elif num:
                    turma = f"{num.group(1)}° Período" + (f" - {curso.title()}" if curso else "")
                    if "(detel)" in disc.lower():
                        turma += " - Detel"
                else:
                    turma = periodo or "—"

            blocos.append({"dia": dia, "inicio": ini, "fim": fim, "disciplina": disc,
                           "professor": prof, "sala": sala, "turma": turma})
        salas.append({"nome": sala,
                      "horarios": agrupar(blocos, ("disciplina", "professor", "turma"))})

    # Conferência: sala informada na turma x tabelas das salas.
    # As tabelas de sala prevalecem: se a mesma aula aparece, no mesmo horário,
    # em outra sala, a sala da turma é corrigida.
    ocup = {(s["nome"], b["dia"], h): b for s in salas for b in s["horarios"]
            for h, (i, f) in HORARIOS.items() if b["inicio"] <= i and f <= b["fim"]}
    for turma, bl in turmas.items():
        for b in bl:
            slot = next(h for h, (i, _) in HORARIOS.items() if i == b["inicio"])
            onde = [s for s in SALAS.values()
                    if (o := ocup.get((s, b["dia"], slot)))
                    and o["disciplina"] == b["disciplina"] and turma in o["turma"].split(" / ")]
            quando = f"{turma}: {b['disciplina']} ({b['dia']})"
            if onde and b["sala"] not in onde:
                if not usar_salas:
                    avisos.append(f"{quando} está na sala {b['sala']} na tabela da turma, "
                                  f"mas em {onde[0]} na tabela da sala (mantido {b['sala']}).")
                    continue
                avisos.append(f"{quando}: sala {b['sala']} -> {onde[0]} (pela tabela da sala).")
                b["sala"] = onde[0]
            elif not onde and b["sala"] in SALAS.values():
                o = ocup.get((b["sala"], b["dia"], slot))
                avisos.append(f"{quando} está na sala {b['sala']}, que nesse horário mostra "
                              f"{o['disciplina'] + ' (' + o['turma'] + ')' if o else 'vazio'} "
                              f"na tabela da sala — sala mantida, confira.")

    ordem = lambda n: (int(re.match(r"(\d+)", n).group(1)) if re.match(r"\d+", n) else 99, n)
    nomes_turmas = sorted(turmas, key=lambda n: (n.startswith("1°"), ordem(n)))
    turmas_out = [{"nome": n, "horarios": agrupar(turmas[n], ("disciplina", "professor", "sala"))}
                  for n in nomes_turmas]

    todas = {b["disciplina"] for t in turmas_out for b in t["horarios"]}
    todas |= {b["disciplina"] for s in salas for b in s["horarios"]}
    data = {
        "disciplinas": {d: {"cor": None} for d in sorted(todas)},
        "turmas": turmas_out,
        "salas": salas,
    }
    return data, avisos


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html")
    ap.add_argument("--semestre", help="ex.: 2026/2 (padrão: extraído do nome do arquivo)")
    ap.add_argument("--saida", default="data/pt/horarios.yaml")
    ap.add_argument("--manter-salas-das-turmas", action="store_true",
                    help="não corrige a sala das turmas pelas tabelas de sala (só avisa)")
    a = ap.parse_args()

    semestre = a.semestre
    if not semestre:
        m = re.search(r"(\d{4})-(\d)", a.html)
        if not m:
            sys.exit("Não consegui deduzir o semestre do nome do arquivo; use --semestre 2026/2")
        semestre = f"{m.group(1)}/{m.group(2)}"

    data, avisos = converter(a.html, semestre, not a.manter_salas_das_turmas)
    with open(a.saida, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"Arquivo {a.saida} gerado ({len(data['turmas'])} turmas, {len(data['salas'])} salas).")
    avisos = list(dict.fromkeys(avisos))
    if avisos:
        print(f"\n{len(avisos)} aviso(s) — confira com quem montou o horário:")
        for x in avisos:
            print("  -", x)


if __name__ == "__main__":
    main()
