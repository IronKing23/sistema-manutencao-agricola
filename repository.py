import pandas as pd
import sqlite3
from database import get_db_connection


class DashboardRepository:
    """Centraliza as consultas usadas nos Dashboards (Início e Painel Principal)."""

    @staticmethod
    def get_kpis_gerais():
        """Retorna os contadores principais: Abertas, Paradas e Recados."""
        conn = get_db_connection()
        try:
            # Busca contagem de ordens não concluídas
            q_aberta = conn.execute("SELECT COUNT(*) FROM ordens_servico WHERE status != 'Concluído'").fetchone()[0]

            # Filtro lógico de parada: Não concluído, não pendente, não aguardando E maquina_parada=1
            filtro_parada = "status NOT IN ('Concluído', 'Pendente', 'Aguardando Peças') AND maquina_parada = 1"
            q_parada = conn.execute(f"SELECT COUNT(*) FROM ordens_servico WHERE {filtro_parada}").fetchone()[0]

            q_recados = conn.execute("SELECT COUNT(*) FROM recados").fetchone()[0]
            return q_aberta, q_parada, q_recados
        finally:
            conn.close()

    @staticmethod
    def get_top_pendencias(limit=20):
        """Retorna as ordens pendentes, ordenadas por prioridade."""
        conn = get_db_connection()
        # Query otimizada com aliases (os.* e e.*) para evitar ambiguidade
        query = """
            SELECT os.id, e.frota, os.descricao, os.data_hora, os.prioridade, os.status 
            FROM ordens_servico os
            JOIN equipamentos e ON os.equipamento_id = e.id 
            WHERE os.status != 'Concluído' 
            ORDER BY os.prioridade = 'Alta' DESC, os.data_hora DESC 
            LIMIT ?
        """
        try:
            return pd.read_sql(query, conn, params=(limit,))
        finally:
            conn.close()

    @staticmethod
    def get_maquinas_paradas():
        """Retorna detalhes das máquinas paradas atualmente."""
        conn = get_db_connection()
        query = """
            SELECT os.id, e.frota, os.descricao, os.data_hora 
            FROM ordens_servico os
            JOIN equipamentos e ON os.equipamento_id = e.id 
            WHERE os.status NOT IN ('Concluído', 'Pendente', 'Aguardando Peças') 
            AND os.maquina_parada = 1 
            ORDER BY os.data_hora DESC
        """
        try:
            return pd.read_sql(query, conn)
        finally:
            conn.close()

    @staticmethod
    def get_distribuicao_status():
        """Retorna dados para o gráfico de barras de status."""
        conn = get_db_connection()
        query = """
            SELECT status, COUNT(*) as qtd 
            FROM ordens_servico 
            WHERE status != 'Concluído' 
            GROUP BY status 
            ORDER BY qtd DESC
        """
        try:
            return pd.read_sql(query, conn)
        finally:
            conn.close()


class OrdemServicoRepository:
    """Manipulação de OS (Criar, Editar, Listar)."""

    @staticmethod
    def update_status(ticket_id, status, user_action=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Lógica para definir Data de Encerramento automaticamente
            if status == "Concluído":
                from datetime import datetime
                import pytz
                tz = pytz.timezone('America/Campo_Grande')
                dt_fim = datetime.now(tz).replace(tzinfo=None)
                cursor.execute("UPDATE ordens_servico SET status=?, data_encerramento=? WHERE id=?",
                               (status, dt_fim, ticket_id))
            else:
                # Se reabriu, limpa a data de encerramento
                cursor.execute("UPDATE ordens_servico SET status=?, data_encerramento=NULL WHERE id=?",
                               (status, ticket_id))

            conn.commit()
            return True
        except Exception as e:
            print(f"Erro update: {e}")
            return False
        finally:
            conn.close()