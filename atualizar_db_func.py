import sqlite3

def atualizar_tabela_os_funcionario():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE ordens_servico ADD COLUMN funcionario_id INTEGER REFERENCES funcionarios(id)")
        print("✅ Coluna 'funcionario_id' adicionada com sucesso.")
    except sqlite3.OperationalError:
        print("ℹ️ Coluna já existe.")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    atualizar_tabela_os_funcionario()