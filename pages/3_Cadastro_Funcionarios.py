import streamlit as st
import sqlite3
import pandas as pd
from database import get_db_connection

# OBS: A autenticação é feita pelo app.py, não precisa repetir aqui.

st.title("👷‍♂️ Gestão de Funcionários")

# --- Funções Auxiliares ---
def carregar_funcionarios():
    """Carrega a lista completa de funcionários."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM funcionarios ORDER BY nome", conn)
        df['display'] = df['nome'] + " (Matrícula: " + df['matricula'].astype(str) + ")"
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def carregar_setores_existentes():
    """Busca todos os setores que já existem no banco."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT DISTINCT setor FROM funcionarios WHERE setor IS NOT NULL AND setor != '' ORDER BY setor", conn)
        return df['setor'].tolist()
    except:
        return []
    finally:
        conn.close()

# --- Layout em Abas (Adicionada a aba de Importação) ---
tab_novo, tab_importar, tab_editar, tab_excluir = st.tabs(["➕ Novo Unitário", "📂 Importar (Lote)", "✏️ Editar", "🗑️ Excluir"])

# ==============================================================================
# ABA 1: NOVO CADASTRO (UNITÁRIO)
# ==============================================================================
with tab_novo:
    st.subheader("Adicionar Novo Funcionário")
    
    with st.form("form_add_func", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome_novo = st.text_input("Nome Completo*")
        with col2:
            matricula_novo = st.text_input("Matrícula/ID*")
        
        # Lógica de Setor Flexível
        lista_setores = carregar_setores_existentes()
        if not lista_setores:
            lista_setores = ["Mecânica", "Elétrica", "Operação"]
        lista_setores.append("➕ Outro (Digitar Novo...)")
        
        col_sel, col_digit = st.columns(2)
        with col_sel:
            setor_selecionado = st.selectbox("Selecione o Setor", options=lista_setores)
        
        with col_digit:
            if setor_selecionado == "➕ Outro (Digitar Novo...)":
                setor_digitado = st.text_input("Digite o nome do Novo Setor*")
                setor_final = setor_digitado
            else:
                st.text_input("Novo Setor", value=setor_selecionado, disabled=True)
                setor_final = setor_selecionado

        st.markdown("---")
        btn_salvar = st.form_submit_button("Salvar Novo")

    if btn_salvar:
        if not nome_novo or not matricula_novo:
            st.error("Nome e Matrícula são obrigatórios.")
        elif not setor_final:
            st.error("Por favor, informe o setor.")
        else:
            conn = None
            try:
                conn = get_db_connection()
                conn.execute(
                    "INSERT INTO funcionarios (nome, matricula, setor) VALUES (?, ?, ?)",
                    (nome_novo, matricula_novo, setor_final)
                )
                conn.commit()
                st.success(f"✅ Funcionário {nome_novo} cadastrado com sucesso!")
                st.cache_data.clear()
            except sqlite3.IntegrityError:
                st.error("Erro: Já existe um funcionário com essa matrícula.")
            except Exception as e:
                st.error(f"Erro: {e}")
            finally:
                if conn: conn.close()

# ==============================================================================
# ABA 2: IMPORTAR EM LOTE (NOVO!)
# ==============================================================================
with tab_importar:
    st.subheader("Importação em Massa via Excel/CSV")
    st.markdown("""
    **Instruções:**
    Faça upload de uma planilha contendo as seguintes colunas exatas:
    - `Nome` (Obrigatório)
    - `Matricula` (Obrigatório - deve ser única)
    - `Setor` (Obrigatório)
    """)
    
    uploaded_file = st.file_uploader("Carregar arquivo de funcionários", type=['xlsx', 'csv'])
    
    if uploaded_file:
        try:
            # Lê o arquivo
            if uploaded_file.name.endswith('.csv'):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)
            
            # Mostra prévia
            st.dataframe(df_upload.head(), use_container_width=True)
            
            if st.button("Processar Importação de Funcionários"):
                # Normaliza colunas para Title Case (Nome, Matricula, Setor)
                df_upload.columns = [c.title() for c in df_upload.columns]
                
                required_cols = {'Nome', 'Matricula', 'Setor'}
                
                if not required_cols.issubset(df_upload.columns):
                    st.error(f"O arquivo deve conter as colunas: {required_cols}. Encontradas: {list(df_upload.columns)}")
                else:
                    conn = get_db_connection()
                    sucessos = 0
                    duplicados = 0
                    erros = 0
                    
                    progress_bar = st.progress(0)
                    total_lines = len(df_upload)

                    for index, row in df_upload.iterrows():
                        progress_bar.progress((index + 1) / total_lines)
                        
                        try:
                            conn.execute(
                                "INSERT INTO funcionarios (nome, matricula, setor) VALUES (?, ?, ?)",
                                (str(row['Nome']), str(row['Matricula']), str(row['Setor']))
                            )
                            sucessos += 1
                        except sqlite3.IntegrityError:
                            duplicados += 1
                        except Exception:
                            erros += 1
                    
                    conn.commit()
                    conn.close()
                    
                    st.success(f"Processamento concluído!")
                    col_res1, col_res2, col_res3 = st.columns(3)
                    col_res1.metric("✅ Novos Cadastros", sucessos)
                    col_res2.metric("⚠️ Duplicados (Ignorados)", duplicados)
                    col_res3.metric("❌ Erros", erros)
                    
                    if sucessos > 0:
                        st.cache_data.clear() # Limpa cache para atualizar listas
                        
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")

# ==============================================================================
# ABA 3: EDITAR
# ==============================================================================
with tab_editar:
    st.subheader("Alterar Dados do Funcionário")
    
    df_funcs = carregar_funcionarios()
    
    if df_funcs.empty:
        st.info("Nenhum funcionário para editar.")
    else:
        escolha_edit = st.selectbox("Buscar Funcionário:", options=df_funcs['display'], index=None, key="sb_edit_func")
        
        if escolha_edit:
            dados = df_funcs[df_funcs['display'] == escolha_edit].iloc[0]
            id_atual = int(dados['id'])
            
            with st.form("form_edit_func"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    novo_nome = st.text_input("Nome", value=dados['nome'])
                with col_e2:
                    nova_mat = st.text_input("Matrícula", value=dados['matricula'])
                
                # Setor Flexível na Edição
                lista_setores_edit = carregar_setores_existentes()
                lista_setores_edit.append("➕ Outro (Digitar Novo...)")
                
                index_setor = 0
                if dados['setor'] in lista_setores_edit:
                    index_setor = lista_setores_edit.index(dados['setor'])
                
                col_esel, col_edig = st.columns(2)
                with col_esel:
                    setor_sel_edit = st.selectbox("Setor", options=lista_setores_edit, index=index_setor)
                
                with col_edig:
                    if setor_sel_edit == "➕ Outro (Digitar Novo...)":
                        setor_dig_edit = st.text_input("Digite o Novo Setor")
                        setor_final_edit = setor_dig_edit
                    else:
                        st.text_input("Novo Setor", value=setor_sel_edit, disabled=True)
                        setor_final_edit = setor_sel_edit

                btn_update = st.form_submit_button("💾 Salvar Alterações")
                
                if btn_update:
                    if not setor_final_edit:
                        st.error("O setor não pode ficar vazio.")
                    else:
                        conn = None
                        try:
                            conn = get_db_connection()
                            conn.execute(
                                "UPDATE funcionarios SET nome = ?, matricula = ?, setor = ? WHERE id = ?",
                                (novo_nome, nova_mat, setor_final_edit, id_atual)
                            )
                            conn.commit()
                            st.success("✅ Dados atualizados com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
                        finally:
                            if conn: conn.close()

# ==============================================================================
# ABA 4: EXCLUSÃO
# ==============================================================================
with tab_excluir:
    st.subheader("Remover Funcionário")
    
    df_funcs_del = carregar_funcionarios()
    
    if df_funcs_del.empty:
        st.info("Nenhum funcionário para excluir.")
    else:
        escolha_del = st.selectbox("Selecione para Excluir:", options=df_funcs_del['display'], index=None, key="sb_del_func")
        
        if escolha_del:
            dados_del = df_funcs_del[df_funcs_del['display'] == escolha_del].iloc[0]
            id_del = int(dados_del['id'])
            
            with st.container(border=True):
                st.markdown(f"### 👤 {dados_del['nome']}")
                st.markdown(f"**Matrícula:** {dados_del['matricula']}")
                st.divider()
                
                confirmar = st.checkbox("⚠️ Confirmo que desejo excluir este registro permanentemente.")
                
                if st.button("🗑️ Excluir Funcionário", type="primary", disabled=not confirmar):
                    conn = None
                    try:
                        conn = get_db_connection()
                        conn.execute("DELETE FROM funcionarios WHERE id = ?", (id_del,))
                        conn.commit()
                        st.success("Funcionário excluído.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
                    finally:
                        if conn: conn.close()

# --- Lista Geral ---
st.divider()
with st.expander("📋 Ver Lista Completa de Funcionários"):
    df_full = carregar_funcionarios()
    if not df_full.empty:
        st.dataframe(
            df_full[['nome', 'matricula', 'setor']], 
            use_container_width=True, 
            hide_index=True
        )