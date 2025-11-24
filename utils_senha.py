import bcrypt

def hash_senha(senha_plana):
    """Transforma '1234' em um hash seguro."""
    # Converte para bytes
    bytes = senha_plana.encode('utf-8') 
    # Gera o sal e o hash
    salt = bcrypt.gensalt() 
    hash = bcrypt.hashpw(bytes, salt) 
    return hash.decode('utf-8') # Retorna como string para salvar no banco

def verificar_senha(senha_plana, hash_banco):
    """Verifica se a senha digitada bate com o hash salvo."""
    try:
        bytes_plana = senha_plana.encode('utf-8')
        bytes_hash = hash_banco.encode('utf-8')
        return bcrypt.checkpw(bytes_plana, bytes_hash)
    except:
        return False # Se o hash estiver corrompido ou for antigo