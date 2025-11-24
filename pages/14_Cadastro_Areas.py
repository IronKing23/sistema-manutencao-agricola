import streamlit as st
import sqlite3
import pandas as pd
from database import get_db_connection

st.title("📍 Gestão de Áreas / Talhões")

# --- Funções Auxiliares ---
def carregar_areas():
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM areas ORDER BY codigo", conn)
        df['display'] = df['codigo'] + " - " + df['nome']
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# --- Layout em Abas ---
tab_novo, tab_importar, tab_editar, tab_excluir = st.tabs(["➕ Nova Área", "📂 Importar (Lote)", "✏️ Editar", "🗑️ Excluir"])

# ==============================================================================
# ABA 1: NOVO CADASTRO
# ==============================================================================
with tab_novo:
    st.subheader("Cadastrar Nova Área")
    
    with st.form("form_add_area", clear_on_submit=True):
        col1, col2 = st.columns([1, 2])
        with col1:
            codigo_novo = st.text_input("Código da Área*", placeholder="Ex: TL-10")
        with col2:
            nome_novo = st.text_input("Nome / Descrição*", placeholder="Ex: Talhão do Milho")
        
        btn_salvar = st.form_submit_button("Salvar Área")

    if btn_salvar:
        if not codigo_novo or not nome_novo:
            st.error("Código e Nome são obrigatórios.")
        else:
            conn = None
            try:
                conn = get_db_connection()
                conn.execute(
                    "INSERT INTO areas (codigo, nome) VALUES (?, ?)",
                    (codigo_novo, nome_novo)
                )
                conn.commit()
                st.success(f"✅ Área {codigo_novo} cadastrada com sucesso!")
                st.cache_data.clear()
            except sqlite3.IntegrityError:
                st.error("Erro: Já existe uma área com este código.")
            except Exception as e:
                st.error(f"Erro: {e}")
            finally:
                if conn: conn.close()

# ==============================================================================
# ABA 2: IMPORTAR EM LOTE
# ==============================================================================
with tab_importar:
    st.subheader("Importação em Massa")
    st.markdown("""
    **Instruções:** Faça upload de planilha (Excel/CSV) com as colunas:
    - `Codigo` (Obrigatório - Deve ser único)
    - `Nome` (Obrigatório)
    """)
    
    uploaded_file = st.file_uploader("Carregar arquivo de áreas", type=['xlsx', 'csv'])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)
            
            st.dataframe(df_upload.head(), use_container_width=True)
            
            if st.button("Processar Importação"):
                df_upload.columns = [c.title() for c in df_upload.columns]
                
                if not {'Codigo', 'Nome'}.issubset(df_upload.columns):
                    st.error("O arquivo deve conter as colunas 'Codigo' e 'Nome'.")
                else:
                    conn = get_db_connection()
                    sucessos = 0
                    duplicados = 0
                    
                    progress_bar = st.progress(0)
                    total = len(df_upload)

                    for index, row in df_upload.iterrows():
                        progress_bar.progress((index + 1) / total)
                        try:
                            conn.execute(
                                "INSERT INTO areas (codigo, nome) VALUES (?, ?)",
                                (str(row['Codigo']), str(row['Nome']))
                            )
                            sucessos += 1
                        except sqlite3.IntegrityError:
                            duplicados += 1
                    
                    conn.commit()
                    conn.close()
                    st.success(f"Concluído! ✅ {sucessos} novos, ⚠️ {duplicados} duplicados.")
                    if sucessos > 0: st.cache_data.clear()
                        
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")

# ==============================================================================
# ABA 3: EDITAR
# ==============================================================================
with tab_editar:
    st.subheader("Alterar Dados")
    
    df_areas = carregar_areas()
    
    if df_areas.empty:
        st.info("Nenhuma área cadastrada.")
    else:
        escolha_edit = st.selectbox("Buscar Área:", options=df_areas['display'], index=None, key="sb_edit_area")
        
        if escolha_edit:
            dados = df_areas[df_areas['display'] == escolha_edit].iloc[0]
            id_atual = int(dados['id'])
            
            with st.form("form_edit_area"):
                c1, c2 = st.columns([1, 2])
                with c1: new_cod = st.text_input("Código", value=dados['codigo'])
                with c2: new_nome = st.text_input("Nome", value=dados['nome'])
                
                if st.form_submit_button("💾 Salvar Alterações"):
                    conn = get_db_connection()
                    try:
                        conn.execute("UPDATE areas SET codigo=?, nome=? WHERE id=?", (new_cod, new_nome, id_atual))
                        conn.commit()
                        st.success("Atualizado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
                    finally: conn.close()

# ==============================================================================
# ABA 4: EXCLUIR
# ==============================================================================
with tab_excluir:
    st.subheader("Remover Área")
    
    df_del = carregar_areas()
    if not df_del.empty:
        escolha_del = st.selectbox("Selecione para Excluir:", options=df_del['display'], index=None, key="sb_del_area")
        
        if escolha_del:
            dados_del = df_del[df_del['display'] == escolha_del].iloc[0]
            id_del = int(dados_del['id'])
            
            with st.container(border=True):
                st.markdown(f"### 📍 {dados_del['codigo']}")
                st.markdown(f"**{dados_del['nome']}**")
                st.divider()
                confirm = st.checkbox("⚠️ Confirmo exclusão permanente.")
                
                if st.button("🗑️ Excluir", type="primary", disabled=not confirm):
                    conn = get_db_connection()
                    conn.execute("DELETE FROM areas WHERE id=?", (id_del,))
                    conn.commit()
                    conn.close()
                    st.success("Excluído.")
                    st.rerun()

st.divider()
with st.expander("📋 Ver Lista Completa"):
    st.dataframe(carregar_areas(), use_container_width=True, hide_index=True)