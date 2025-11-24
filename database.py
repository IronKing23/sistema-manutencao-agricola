import sqlite3

# Nome do arquivo do banco de dados
DB_NAME = "manutencao.db"

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
    return conn

def inicializar_banco():
    """Cria as tabelas se elas não existirem."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela de Equipamentos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS equipamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        frota TEXT NOT NULL UNIQUE,
        modelo TEXT NOT NULL,
        gestao_responsavel TEXT
    );
    """)
    
    # Tabela de Funcionários
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS funcionarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        matricula TEXT NOT NULL UNIQUE,
        nome TEXT NOT NULL,
        setor TEXT
    );
    """)

    # Tabela de Tipos de Operação
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tipos_operacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE
    );
    """)
    
    # Tabela de Ordens de Serviço (a principal)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ordens_servico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_hora DATETIME NOT NULL,
        equipamento_id INTEGER NOT NULL,
        local_atendimento TEXT,
        descricao TEXT,
        tipo_operacao_id INTEGER NOT NULL,
        status TEXT NOT NULL, 
        numero_os_oficial TEXT,
        FOREIGN KEY (equipamento_id) REFERENCES equipamentos (id),
        FOREIGN KEY (tipo_operacao_id) REFERENCES tipos_operacao (id)
    );
    """)

    # Adiciona os tipos de operação padrão se a tabela estiver vazia
    cursor.execute("SELECT COUNT(*) FROM tipos_operacao")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO tipos_operacao (nome) VALUES ('Mecânico')")
        cursor.execute("INSERT INTO tipos_operacao (nome) VALUES ('Elétrico')")
        cursor.execute("INSERT INTO tipos_operacao (nome) VALUES ('Borracharia')")
        cursor.execute("INSERT INTO tipos_operacao (nome) VALUES ('Terceiro')")

    conn.commit()
    conn.close()
    print("Banco de dados inicializado com sucesso.")

# Se você executar este arquivo diretamente, ele cria o banco.
if __name__ == "__main__":
    inicializar_banco()