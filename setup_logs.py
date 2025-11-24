import sqlite3

def criar_tabela_logs():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora DATETIME,
            usuario TEXT,
            acao TEXT,      -- Ex: CRIAR, EDITAR, EXCLUIR, LOGIN
            alvo TEXT,      -- Ex: OS #50, Usuário 'joao'
            detalhes TEXT   -- Ex: Mudou status de Pendente para Concluído
        )
        """)
        print("✅ Tabela 'audit_logs' criada com sucesso.")
    except Exception as e:
        print(f"❌ Erro: {e}")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    criar_tabela_logs()