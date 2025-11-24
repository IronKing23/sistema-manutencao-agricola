import streamlit as st
import sqlite3
import pandas as pd


from database import get_db_connection


st.title("⚙️ Gestão de Tipos de Operação")

# --- Funções Auxiliares ---
def carregar_operacoes():
    """Carrega lista de operações."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM tipos_operacao ORDER BY nome", conn)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# --- Layout em Abas ---
tab_novo, tab_editar, tab_excluir = st.tabs(["➕ Nova Operação", "✏️ Editar Operação", "🗑️ Excluir"])

# ==============================================================================
# ABA 1: NOVA OPERAÇÃO
# ==============================================================================
with tab_novo:
    st.subheader("Cadastrar Nova Operação")
    
    with st.form("form_operacoes", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            nome_novo = st.text_input("Nome da Operação*", placeholder="Ex: Hidráulica, Funilaria...")
        with col2:
            cor_novo = st.color_picker("Cor da Etiqueta", value="#BDC3C7")

        btn_salvar = st.form_submit_button("Salvar Operação")

    if btn_salvar:
        if not nome_novo:
            st.error("O campo 'Nome da Operação' é obrigatório.")
        else:
            conn = None
            try:
                conn = get_db_connection()
                conn.execute(
                    "INSERT INTO tipos_operacao (nome, cor) VALUES (?, ?)",
                    (nome_novo, cor_novo)
                )
                conn.commit()
                st.success(f"✅ Operação '{nome_novo}' cadastrada!")
                st.cache_data.clear()
                # st.rerun() # Opcional aqui
            except sqlite3.IntegrityError:
                st.error(f"Erro: O tipo de operação '{nome_novo}' já existe.")
            except Exception as e:
                st.error(f"Ocorreu um erro: {e}")
            finally:
                if conn: conn.close()

# ==============================================================================
# ABA 2: EDITAR OPERAÇÃO
# ==============================================================================
with tab_editar:
    st.subheader("Alterar Nome ou Cor")
    
    df_ops = carregar_operacoes()
    
    if df_ops.empty:
        st.info("Nenhuma operação cadastrada para editar.")
    else:
        options = df_ops['nome'].tolist()
        escolha_edit = st.selectbox("Selecione a Operação:", options=options, index=None, placeholder="Busque pelo nome...", key="sb_edit_op")
        
        if escolha_edit:
            # Pega dados atuais
            dados = df_ops[df_ops['nome'] == escolha_edit].iloc[0]
            id_atual = int(dados['id'])
            cor_atual = dados['cor'] if dados['cor'] else "#BDC3C7" # Fallback se estiver sem cor
            
            with st.form("form_edit_op"):
                col_e1, col_e2 = st.columns([3, 1])
                with col_e1:
                    novo_nome = st.text_input("Nome da Operação", value=dados['nome'])
                with col_e2:
                    nova_cor = st.color_picker("Cor da Etiqueta", value=cor_atual)
                
                btn_update = st.form_submit_button("💾 Salvar Alterações")
                
                if btn_update:
                    conn = None
                    try:
                        conn = get_db_connection()
                        conn.execute(
                            "UPDATE tipos_operacao SET nome = ?, cor = ? WHERE id = ?",
                            (novo_nome, nova_cor, id_atual)
                        )
                        conn.commit()
                        st.success("✅ Operação atualizada com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao atualizar: {e}")
                    finally:
                        if conn: conn.close()

# ==============================================================================
# ABA 3: EXCLUIR OPERAÇÃO
# ==============================================================================
with tab_excluir:
    st.subheader("Remover Tipo de Operação")
    st.warning("⚠️ Cuidado: Ao excluir um tipo de operação, os atendimentos antigos que usavam esse tipo perderão essa referência (ficarão sem categoria).")
    
    df_ops_del = carregar_operacoes()
    
    if df_ops_del.empty:
        st.info("Nada para excluir.")
    else:
        options_del = df_ops_del['nome'].tolist()
        escolha_del = st.selectbox("Selecione para Excluir:", options=options_del, index=None, key="sb_del_op")
        
        if escolha_del:
            dados_del = df_ops_del[df_ops_del['nome'] == escolha_del].iloc[0]
            id_del = int(dados_del['id'])
            
            # Cartão de segurança
            with st.container(border=True):
                st.markdown(f"### 🔧 {dados_del['nome']}")
                st.color_picker("Cor Atual", value=dados_del['cor'] if dados_del['cor'] else "#FFFFFF", disabled=True)
                st.divider()
                
                confirmar = st.checkbox(f"Tenho certeza que desejo excluir '{dados_del['nome']}' permanentemente.")
                
                if st.button("🗑️ Excluir Operação", type="primary", disabled=not confirmar):
                    conn = None
                    try:
                        conn = get_db_connection()
                        conn.execute("DELETE FROM tipos_operacao WHERE id = ?", (id_del,))
                        conn.commit()
                        st.success("Operação removida com sucesso.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
                    finally:
                        if conn: conn.close()

# --- Lista Geral ---
st.divider()
with st.expander("📋 Ver Lista de Operações e Cores"):
    df_full = carregar_operacoes()
    if not df_full.empty:
        st.dataframe(
            df_full, 
            use_container_width=True, 
            hide_index=True, 
            column_config={
                "nome": "Nome da Operação",
                "cor": st.column_config.Column(
                    "Etiqueta Visual",
                    width="small",
                    help="Cor usada no Painel Principal",
                    disabled=True
                ),
                "id": None # Oculta ID
            }
        )