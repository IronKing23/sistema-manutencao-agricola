import sqlite3
import pandas as pd

conn = sqlite3.connect("manutencao.db")

try:
    # QUERY CORRIGIDA: Usa JOIN para buscar o nome da frota na tabela certa
    query = """
    SELECT 
        os.id as Ticket,
        e.frota, 
        os.latitude, 
        os.longitude 
    FROM ordens_servico os
    JOIN equipamentos e ON os.equipamento_id = e.id
    ORDER BY os.id DESC 
    LIMIT 5
    """
    
    df = pd.read_sql_query(query, conn)
    
    print("\n--- ÚLTIMOS 5 REGISTROS (VERIFICAÇÃO GPS) ---")
    if df.empty:
        print("Nenhum registro encontrado.")
    else:
        print(df)
    print("-" * 50)
    print("LEGENDA:")
    print("- None ou NaN: Campo está vazio no banco.")
    print("- 0.0: Campo está zerado.")
    print("- Números (ex: -23.55): GPS gravado corretamente.")

except Exception as e:
    print("ERRO AO LER BANCO:", e)
    
finally:
    conn.close()