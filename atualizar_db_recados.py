import sqlite3

def criar_tabela_recados():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS recados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora DATETIME,
            autor TEXT,
            mensagem TEXT,
            importante BOOLEAN
        )
        """)
        print("✅ Tabela 'recados' criada com sucesso.")
    except Exception as e:
        print(f"❌ Erro: {e}")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_tabela_recados()