import sqlite3

def atualizar_tabela_usuarios_seguranca():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    try:
        # Adiciona coluna para forçar troca de senha (0 = Não, 1 = Sim)
        # Default é 0 para os atuais não serem bloqueados
        cursor.execute("ALTER TABLE usuarios ADD COLUMN force_change_password INTEGER DEFAULT 0")
        print("✅ Coluna 'force_change_password' adicionada.")
    except sqlite3.OperationalError:
        print("ℹ️ Coluna 'force_change_password' já existe.")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    atualizar_tabela_usuarios_seguranca()