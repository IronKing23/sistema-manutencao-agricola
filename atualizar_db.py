import sqlite3

DB_NAME = "manutencao.db"

def adicionar_coluna_encerramento():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Tenta adicionar a coluna. Se já existir, vai dar erro e o except pega.
        cursor.execute("ALTER TABLE ordens_servico ADD COLUMN data_encerramento DATETIME")
        conn.commit()
        print("✅ Sucesso! Coluna 'data_encerramento' adicionada.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ A coluna 'data_encerramento' já existe. Nenhuma alteração necessária.")
        else:
            print(f"❌ Erro: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    adicionar_coluna_encerramento()