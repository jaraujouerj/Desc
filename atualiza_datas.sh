#!/bin/bash

# Script para atualizar as datas dos arquivos com base no último commit do Git

# Encontra todos os arquivos .md no diretório content
find content -name "*.md" -type f | while read -r arquivo; do
    # Pega a data do último commit do arquivo
    data_commit=$(git log -1 --format="%ci" -- "$arquivo" 2>/dev/null | cut -d' ' -f1)
    
    # Se encontrou uma data de commit
    if [ ! -z "$data_commit" ]; then
        # Verifica se o arquivo tem frontmatter
        if grep -q "^---$" "$arquivo"; then
            # Verifica se já tem campo date
            if grep -q "^date:" "$arquivo"; then
                # Atualiza o campo date existente
                sed -i "s/^date:.*$/date: $data_commit/" "$arquivo"
                echo "Atualizado: $arquivo -> $data_commit"
            else
                # Adiciona o campo date após o primeiro ---
                sed -i "0,/^---$/!{s/^---$/date: $data_commit\n---/}" "$arquivo"
                echo "Adicionado: $arquivo -> $data_commit"
            fi
        fi
    fi
done

echo "Datas atualizadas com sucesso!"
