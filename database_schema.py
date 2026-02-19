import sqlite3
import logging

# Configuração de Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_FILE = "manutencao.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def inicializar_banco():
    """
    Verifica e cria/atualiza a estrutura completa do banco de dados.
    Execute esta função no início do app.py.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # --- 1. TABELAS BASE ---

        # Usuários
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                nome TEXT,
                force_change_password INTEGER DEFAULT 0,
                role TEXT DEFAULT 'user'
            )
        """)

        # Equipamentos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equipamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frota TEXT UNIQUE NOT NULL,
                modelo TEXT,
                gestao_responsavel TEXT
            )
        """)

        # Tipos de Operação
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tipos_operacao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                cor TEXT DEFAULT '#6c757d'
            )
        """)

        # Funcionários
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS funcionarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                matricula TEXT,
                setor TEXT,
                funcao TEXT
            )
        """)

        # Ordens de Serviço (Tabela Central)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ordens_servico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TIMESTAMP,
                equipamento_id INTEGER,
                local_atendimento TEXT,
                descricao TEXT,
                tipo_operacao_id INTEGER,
                status TEXT,
                numero_os_oficial TEXT,
                funcionario_id INTEGER,
                horimetro REAL,
                prioridade TEXT,
                latitude REAL,
                longitude REAL,
                data_encerramento TIMESTAMP,
                classificacao TEXT,
                maquina_parada INTEGER DEFAULT 0,
                solicitante_id INTEGER,
                FOREIGN KEY(equipamento_id) REFERENCES equipamentos(id),
                FOREIGN KEY(tipo_operacao_id) REFERENCES tipos_operacao(id),
                FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id)
            )
        """)

        # Recados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TIMESTAMP,
                usuario TEXT,
                mensagem TEXT,
                prioridade TEXT
            )
        """)

        # Auditoria (Logs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TIMESTAMP,
                usuario TEXT,
                acao TEXT,
                detalhes TEXT
            )
        """)

        # --- 2. MIGRAÇÕES (Verificação de Colunas Novas) ---
        # Função auxiliar para adicionar coluna se não existir
        def add_column_if_not_exists(table, column, definition):
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                logger.info(f"Coluna '{column}' adicionada à tabela '{table}'.")
            except sqlite3.OperationalError:
                # Coluna já existe
                pass

        # Lista de colunas que foram adicionadas ao longo do tempo (Migrações)
        add_column_if_not_exists("equipamentos", "gestao_responsavel", "TEXT")
        add_column_if_not_exists("tipos_operacao", "cor", "TEXT DEFAULT '#6c757d'")
        add_column_if_not_exists("ordens_servico", "classificacao", "TEXT")
        add_column_if_not_exists("ordens_servico", "maquina_parada", "INTEGER DEFAULT 0")
        add_column_if_not_exists("ordens_servico", "solicitante_id", "INTEGER")
        add_column_if_not_exists("ordens_servico", "latitude", "REAL")
        add_column_if_not_exists("ordens_servico", "longitude", "REAL")
        add_column_if_not_exists("usuarios", "role", "TEXT DEFAULT 'user'")

        conn.commit()
        logger.info("Banco de dados verificado e atualizado com sucesso.")

    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    # Permite rodar este arquivo diretamente para forçar atualização
    inicializar_banco()