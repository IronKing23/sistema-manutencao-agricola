# Arquivo: atualizar_db_solicitante.py
import sqlite3

def atualizar_banco():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    print("Iniciando atualização do banco...")

    # Adicionar coluna 'solicitante_id' na tabela ordens_servico
    try:
        cursor.execute("ALTER TABLE ordens_servico ADD COLUMN solicitante_id INTEGER")
        print("✅ Coluna 'solicitante_id' adicionada com sucesso.")
    except sqlite3.OperationalError:
        print("⚠️ Coluna 'solicitante_id' já existe (nada a fazer).")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    atualizar_banco()