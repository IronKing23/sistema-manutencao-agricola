import sqlite3

DB_NAME = "manutencao.db"

def atualizar_tabela_cores():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # 1. Cria a coluna 'cor' se não existir
        cursor.execute("ALTER TABLE tipos_operacao ADD COLUMN cor TEXT")
        print("✅ Coluna 'cor' adicionada com sucesso.")
    except sqlite3.OperationalError:
        print("ℹ️ Coluna 'cor' já existia.")

    # 2. Atualiza as cores padrão (para não ficarem vazias)
    updates = [
        ('#2196F3', 'Elétrico'),      # Azul
        ('#9E9E9E', 'Mecânico'),      # Cinza
        ('#FF9800', 'Borracharia'),   # Laranja
        ('#9C27B0', 'Terceiro'),      # Roxo
    ]
    
    for cor, nome in updates:
        # O LIKE com % ajuda a pegar variações (ex: Mecanico, Mecânica)
        cursor.execute("UPDATE tipos_operacao SET cor = ? WHERE nome LIKE ?", (cor, f"%{nome}%"))
    
    # Define uma cor padrão (Cinza claro) para quem ficou sem cor
    cursor.execute("UPDATE tipos_operacao SET cor = '#BDC3C7' WHERE cor IS NULL")
    
    conn.commit()
    conn.close()
    print("✅ Cores padrão aplicadas aos itens existentes!")

if __name__ == "__main__":
    atualizar_tabela_cores()