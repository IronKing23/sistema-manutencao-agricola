import sqlite3

def criar_tabela_areas():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS areas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL
        )
        """)
        print("✅ Tabela 'areas' criada com sucesso.")
        
        # Insere um exemplo se estiver vazia
        cursor.execute("SELECT count(*) FROM areas")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO areas (codigo, nome) VALUES ('TL-01', 'Talhão da Entrada')")
            conn.commit()
            print("ℹ️ Área de exemplo inserida.")
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_tabela_areas()