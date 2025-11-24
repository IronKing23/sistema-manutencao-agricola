import sqlite3

def atualizar_gps():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    # Tenta adicionar latitude e longitude
    colunas = ["latitude", "longitude"]
    for col in colunas:
        try:
            cursor.execute(f"ALTER TABLE ordens_servico ADD COLUMN {col} REAL")
            print(f"✅ Coluna '{col}' adicionada.")
        except sqlite3.OperationalError:
            print(f"ℹ️ Coluna '{col}' já existe.")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    atualizar_gps()