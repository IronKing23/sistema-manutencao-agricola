import sqlite3

def criar_tabela_usuarios():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    # Cria tabela
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            nome TEXT
        )
    """)
    
    # Verifica se já existe o admin
    cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not cursor.fetchone():
        # Cria o usuário padrão
        # Login: admin
        # Senha: 1234
        cursor.execute("INSERT INTO usuarios VALUES ('admin', '1234', 'Administrador Geral')")
        print("✅ Usuário 'admin' criado com senha '1234'.")
    else:
        print("ℹ️ Usuário 'admin' já existe.")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_tabela_usuarios()