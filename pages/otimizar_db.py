import sqlite3

def criar_indices():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    print("Criando índices de performance...")
    
    # Índices para buscas frequentes
    comandos = [
        "CREATE INDEX IF NOT EXISTS idx_os_equipamento ON ordens_servico(equipamento_id)",
        "CREATE INDEX IF NOT EXISTS idx_os_status ON ordens_servico(status)",
        "CREATE INDEX IF NOT EXISTS idx_equip_frota ON equipamentos(frota)",
        "CREATE INDEX IF NOT EXISTS idx_os_data ON ordens_servico(data_hora)"
    ]
    
    for cmd in comandos:
        cursor.execute(cmd)
        
    conn.commit()
    conn.close()
    print("✅ Banco de dados otimizado!")

if __name__ == "__main__":
    criar_indices()