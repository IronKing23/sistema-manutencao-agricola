import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px 

from database import get_db_connection


st.title("🚜 Cadastro de Equipamentos")

# --- 1. Formulário de Inserção Manual ---
with st.form("form_equipamentos", clear_on_submit=True):
    st.subheader("Adicionar Manualmente")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        frota = st.text_input("Frota*", placeholder="Ex: TR-001")
    with col2:
        modelo = st.text_input("Modelo*", placeholder="Ex: John Deere 8R")
    with col3:
        gestao = st.text_input("Gestão Responsável", placeholder="Ex: João Silva")

    submitted = st.form_submit_button("Salvar Equipamento")

if submitted:
    if not frota or not modelo:
        st.error("Campos 'Frota' e 'Modelo' são obrigatórios.")
    else:
        conn = None
        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO equipamentos (frota, modelo, gestao_responsavel) VALUES (?, ?, ?)",
                (frota, modelo, gestao)
            )
            conn.commit()
            st.success(f"Equipamento {frota} cadastrado com sucesso!")
        except sqlite3.IntegrityError:
            st.error(f"Erro: A frota '{frota}' já existe.")
        except Exception as e:
            st.error(f"Ocorreu um erro: {e}")
        finally:
            if conn:
                conn.close()

st.divider()

# --- 2. Área de Importação em Lote ---
with st.expander("📂 Importação em Lote (Excel / CSV)"):
    st.markdown("""
    **Instruções:** Faça upload de planilha com colunas: `Frota`, `Modelo`, `Gestao`
    """)
    uploaded_file = st.file_uploader("Carregar arquivo", type=['xlsx', 'csv'])
    
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)
            
            if st.button("Processar Importação"):
                df_upload.columns = [c.title() for c in df_upload.columns]
                required_cols = {'Frota', 'Modelo'}
                
                if not required_cols.issubset(df_upload.columns):
                    st.error(f"Colunas obrigatórias faltando. Necessário: {required_cols}")
                else:
                    conn = get_db_connection()
                    sucessos = 0
                    for index, row in df_upload.iterrows():
                        try:
                            val_gestao = row['Gestao'] if 'Gestao' in df_upload.columns else None
                            conn.execute(
                                "INSERT INTO equipamentos (frota, modelo, gestao_responsavel) VALUES (?, ?, ?)",
                                (str(row['Frota']), str(row['Modelo']), str(val_gestao) if pd.notna(val_gestao) else None)
                            )
                            sucessos += 1
                        except:
                            pass
                    conn.commit()
                    conn.close()
                    st.success(f"Importação concluída! {sucessos} registros inseridos.")
                    st.cache_data.clear()
                    st.rerun()
        except Exception as e:
            st.error(f"Erro no arquivo: {e}")

# --- 3. Troca de Gestão em Lote (Rotatividade Geral) ---
with st.expander("🔄 Troca de Gestão em Lote (Rotatividade Geral)"):
    st.info("Utilize esta função para transferir TODAS as máquinas de um Gestor Antigo para um Novo Gestor.")
    
    conn = get_db_connection()
    try:
        gestores_df = pd.read_sql("SELECT DISTINCT gestao_responsavel FROM equipamentos WHERE gestao_responsavel IS NOT NULL AND gestao_responsavel != '' ORDER BY gestao_responsavel", conn)
        lista_gestores = gestores_df['gestao_responsavel'].tolist()
    except:
        lista_gestores = []
    finally:
        conn.close()

    if not lista_gestores:
        st.warning("Não há gestores cadastrados.")
    else:
        with st.form("form_troca_gestao"):
            col_de, col_para = st.columns(2)
            with col_de:
                gestor_antigo = st.selectbox("De (Gestor Atual):", options=lista_gestores)
            with col_para:
                novo_gestor = st.text_input("Para (Novo Gestor):")
            
            btn_trocar = st.form_submit_button("Confirmar Transferência em Lote")
            
            if btn_trocar:
                if not novo_gestor:
                    st.error("Digite o nome do novo gestor.")
                elif gestor_antigo == novo_gestor:
                    st.warning("Nenhuma alteração necessária.")
                else:
                    conn = None
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE equipamentos SET gestao_responsavel = ? WHERE gestao_responsavel = ?",
                            (novo_gestor, gestor_antigo)
                        )
                        st.success(f"✅ {cursor.rowcount} máquinas transferidas de '{gestor_antigo}' para '{novo_gestor}'.")
                        conn.commit()
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
                    finally:
                        if conn: conn.close()

# --- 4. Edição Individual de Gestão (NOVIDADE AQUI) ---
with st.expander("✏️ Editar Gestão por Equipamento (Individual)"):
    st.info("Utilize esta função para alterar o gestor de UMA máquina específica (ex: Frota 64064).")
    
    # Carrega lista de equipamentos
    conn = None
    try:
        conn = get_db_connection()
        equip_df = pd.read_sql("SELECT id, frota, modelo, gestao_responsavel FROM equipamentos ORDER BY frota", conn)
        equip_df['display'] = equip_df['frota'] + " - " + equip_df['modelo']
    except Exception as e:
        st.error(f"Erro ao carregar lista: {e}")
        equip_df = pd.DataFrame()
    finally:
        if conn: conn.close()

    if equip_df.empty:
        st.warning("Nenhum equipamento cadastrado.")
    else:
        # Layout em colunas
        col_sel, col_edit = st.columns([1, 1])
        
        with col_sel:
            # Selectbox para escolher a máquina
            selected_display = st.selectbox(
                "Selecione o Equipamento:", 
                options=equip_df['display'],
                placeholder="Digite o número da frota..."
            )
            
            # Pega os dados da máquina selecionada
            selected_row = equip_df[equip_df['display'] == selected_display].iloc[0]
            current_id = int(selected_row['id'])
            current_gestor = selected_row['gestao_responsavel']
            
            st.markdown(f"**Gestor Atual:** {current_gestor if current_gestor else 'Sem Gestor'}")

        with col_edit:
            # Campo para digitar o novo nome
            novo_gestor_individual = st.text_input("Novo Gestor Responsável:", placeholder="Ex: Pedro")
            
            if st.button("Atualizar Frota Individual"):
                if not novo_gestor_individual:
                    st.error("Por favor, digite o nome do novo gestor.")
                else:
                    conn = None
                    try:
                        conn = get_db_connection()
                        conn.execute(
                            "UPDATE equipamentos SET gestao_responsavel = ? WHERE id = ?",
                            (novo_gestor_individual, current_id)
                        )
                        conn.commit()
                        st.success(f"✅ Frota {selected_row['frota']} atualizada! Agora está sob gestão de '{novo_gestor_individual}'.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao atualizar: {e}")
                    finally:
                        if conn: conn.close()

# --- 5. Exibição e Análise da Frota ---
st.divider()
st.subheader("📋 Inventário de Equipamentos")

conn = None
try:
    conn = get_db_connection()
    df_equipamentos = pd.read_sql_query("SELECT * FROM equipamentos ORDER BY frota", conn)
    
    if df_equipamentos.empty:
        st.info("Nenhum equipamento cadastrado ainda.")
    else:
        col_m1, col_m2, col_m3 = st.columns(3)
        
        total_maq = len(df_equipamentos)
        total_modelos = df_equipamentos['modelo'].nunique()
        try:
            gestao_princ = df_equipamentos['gestao_responsavel'].mode()[0]
        except:
            gestao_princ = "N/A"

        col_m1.metric("Total de Máquinas", total_maq)
        col_m2.metric("Modelos Diferentes", total_modelos)
        col_m3.metric("Gestão Principal", gestao_princ)
        
        st.markdown("<br>", unsafe_allow_html=True) 

        col_graf, col_tabela = st.columns([1, 2])
        
        with col_graf:
            st.markdown("##### Distribuição por Modelo")
            df_count_modelo = df_equipamentos['modelo'].value_counts().reset_index()
            df_count_modelo.columns = ['Modelo', 'Qtd']
            
            fig = px.pie(df_count_modelo, values='Qtd', names='Modelo', hole=0.4)
            fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

        with col_tabela:
            st.markdown("##### Lista Detalhada")
            st.dataframe(
                df_equipamentos,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "frota": st.column_config.TextColumn("Frota (ID)", width="small"),
                    "modelo": st.column_config.TextColumn("Modelo", width="medium"),
                    "gestao_responsavel": st.column_config.TextColumn("Gestão / Responsável", width="medium"),
                    "id": None 
                }
            )

except Exception as e:
    st.error(f"Erro ao carregar equipamentos: {e}")
finally:
    if conn:
        conn.close()