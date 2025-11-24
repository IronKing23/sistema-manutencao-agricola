import sqlite3

def atualizar_agenda():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    print("Atualizando banco de dados...")
    
    # 1. Adiciona coluna telefone em funcionários (se não existir)
    try:
        cursor.execute("ALTER TABLE funcionarios ADD COLUMN telefone TEXT")
        print("✅ Coluna 'telefone' adicionada em 'funcionarios'.")
    except:
        print("ℹ️ Coluna 'telefone' já existe em 'funcionarios'.")
        
    # 2. Cria tabela de agenda externa (para quem não é funcionário)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agenda_externa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT NOT NULL,
            tipo TEXT -- Ex: Fornecedor, Mecânico Terceiro, etc.
        )
    """)
    print("✅ Tabela 'agenda_externa' verificada.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    atualizar_agenda()