import sqlite3
from utils_senha import hash_senha

def migrar_banco():
    conn = sqlite3.connect("manutencao.db")
    cursor = conn.cursor()
    
    print("Iniciando migração de senhas...")
    
    # Pega todos os usuários
    cursor.execute("SELECT username, password FROM usuarios")
    usuarios = cursor.fetchall()
    
    count = 0
    for user in usuarios:
        username = user[0]
        senha_atual = user[1]
        
        # Verifica se já é um hash (hashes do bcrypt começam com $2b$)
        if not senha_atual.startswith("$2b$"):
            nova_senha_hash = hash_senha(senha_atual)
            cursor.execute("UPDATE usuarios SET password = ? WHERE username = ?", (nova_senha_hash, username))
            print(f"🔒 Usuário '{username}' migrado com segurança.")
            count += 1
            
    conn.commit()
    conn.close()
    print(f"✅ Migração concluída! {count} senhas criptografadas.")

if __name__ == "__main__":
    migrar_banco()