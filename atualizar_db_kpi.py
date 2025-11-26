# Arquivo: atualizar_db_kpi.py
import sqlite3

def atualizar_banco():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    print("Iniciando atualização do banco para KPIs...")

    # 1. Adicionar coluna 'classificacao' (Preventiva, Corretiva, Preditiva)
    try:
        cursor.execute("ALTER TABLE ordens_servico ADD COLUMN classificacao TEXT DEFAULT 'Corretiva'")
        print("✅ Coluna 'classificacao' adicionada.")
    except sqlite3.OperationalError:
        print("⚠️ Coluna 'classificacao' já existe.")

    # 2. Adicionar coluna 'maquina_parada' (1 para Sim, 0 para Não)
    try:
        cursor.execute("ALTER TABLE ordens_servico ADD COLUMN maquina_parada INTEGER DEFAULT 1")
        print("✅ Coluna 'maquina_parada' adicionada.")
    except sqlite3.OperationalError:
        print("⚠️ Coluna 'maquina_parada' já existe.")

    conn.commit()
    conn.close()
    print("Atualização concluída com sucesso!")

if __name__ == "__main__":
    atualizar_banco()