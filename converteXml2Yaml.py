import xml.etree.ElementTree as ET
import yaml
import re

# Parse the XML file
tree = ET.parse("desc2026-1v01_subgroups.xml")
root = tree.getroot()

# This data structure will hold all the final data
turmas = []
# This will be a set of unique discipline names, then converted to the dict structure
unique_disciplinas = set()

# Regex to extract start and end times from the hour string (e.g., "M1 07:00-07:50")
hour_pattern = re.compile(r'(\d{2}:\d{2})-(\d{2}:\d{2})')

# Iterate through each <Subgroup> element in the XML
for subgroup in root.findall("Subgroup"):
    nome_turma = subgroup.get("name")
    if not nome_turma:
        continue

    horarios_individuais = []
    
    # Iterate through each <Day> inside the <Subgroup>
    for day in subgroup.findall("Day"):
        dia = day.get("name")
        # Iterate through each <Hour> inside the <Day>
        for hour in day.findall("Hour"):
            subject_element = hour.find("Subject")
            # If there's no <Subject>, it's an empty slot, so we skip it
            if subject_element is None:
                continue

            disciplina = subject_element.get("name", "Desconhecida")
            unique_disciplinas.add(disciplina)
            
            teacher_element = hour.find("Teacher")
            professor = teacher_element.get("name", "A definir") if teacher_element is not None else "A definir"

            room_element = hour.find("Room")
            sala = room_element.get("name", "Sem sala") if room_element is not None else "Sem sala"
            
            hour_name = hour.get("name", "")
            inicio, fim = "00:00", "00:00"
            time_match = hour_pattern.search(hour_name)
            if time_match:
                inicio = time_match.group(1)
                fim = time_match.group(2)
            
            # Append each hour block as a separate item
            horarios_individuais.append({
                "dia": dia,
                "inicio": inicio,
                "fim": fim,
                "disciplina": disciplina,
                "professor": professor,
                "sala": sala
            })

    # Define a ordem cronológica dos dias da semana para ordenação
    day_order = {"Seg": 0, "Ter": 1, "Qua": 2, "Qui": 3, "Sex": 4, "Sáb": 5, "Dom": 6}
    
    # Ordena os blocos de horas individuais cronologicamente por dia e, em seguida, pela hora de início
    horarios_individuais.sort(key=lambda x: (day_order.get(x['dia'], 99), x['inicio']))
    
    merged_horarios = []
    if horarios_individuais:
        # Start with the first hour block
        current_horario = horarios_individuais[0].copy()

        for i in range(1, len(horarios_individuais)):
            next_horario = horarios_individuais[i]
            
            # Check if the next block is the same class, same day, and immediately follows the current one
            if (next_horario['disciplina'] == current_horario['disciplina'] and
                next_horario['professor'] == current_horario['professor'] and
                next_horario['sala'] == current_horario['sala'] and
                next_horario['dia'] == current_horario['dia'] and
                next_horario['inicio'] == current_horario['fim']):
                
                # If so, merge them by extending the end time of the current block
                current_horario['fim'] = next_horario['fim']
            else:
                # Otherwise, the current block is complete. Add it to the merged list.
                merged_horarios.append(current_horario)
                # Start a new block with the next hour
                current_horario = next_horario.copy()
        
        # Add the very last processed block to the list
        merged_horarios.append(current_horario)

    # Add the processed subgroup (turma) to our list of turmas
    turmas.append({
        "nome": nome_turma,
        "horarios": merged_horarios
    })

# Create the final data structure for YAML output
disciplinas_dict = {disciplina: {"cor": None} for disciplina in sorted(list(unique_disciplinas))}

data = {
    "disciplinas": disciplinas_dict,
    "turmas": turmas
}

# Write the data to a YAML file
with open("data/horarios.yaml", "w", encoding="utf-8") as f:
    yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

print("Arquivo data/horarios.yaml gerado com sucesso.")