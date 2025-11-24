import sqlite3

def atualizar_tabela_os_v2():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    colunas = [
        ("horimetro", "REAL"),
        ("prioridade", "TEXT")
    ]
    
    for col, tipo in colunas:
        try:
            cursor.execute(f"ALTER TABLE ordens_servico ADD COLUMN {col} {tipo}")
            print(f"✅ Coluna '{col}' adicionada com sucesso.")
        except sqlite3.OperationalError:
            print(f"ℹ️ Coluna '{col}' já existe.")
            
    # Define prioridade padrão para os antigos
    cursor.execute("UPDATE ordens_servico SET prioridade = 'Média' WHERE prioridade IS NULL")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    atualizar_tabela_os_v2()