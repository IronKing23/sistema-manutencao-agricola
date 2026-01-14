import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os
import io

# --- BLINDAGEM DE IMPORTAÇÃO ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_connection
from utils_ui import load_custom_css, card_kpi
from utils_icons import get_icon
from utils_log import registrar_log

# --- 1. CONFIGURAÇÃO VISUAL ---
load_custom_css()

st.title("🚜 Gestão de Frota")
st.caption("Cadastre, edite e monitorize os equipamentos agrícolas.")
st.markdown("---")


# --- 2. CARREGAMENTO DE DADOS ---
def carregar_dados():
    conn = get_db_connection()
    try:
        # Busca equipamentos
        df = pd.read_sql("SELECT * FROM equipamentos ORDER BY frota", conn)
        return df
    finally:
        conn.close()


df_equipamentos = carregar_dados()

# --- 3. KPIs (CARDS) ---
if not df_equipamentos.empty:
    total_frota = len(df_equipamentos)
    total_modelos = df_equipamentos['modelo'].nunique()
    # Gestor com mais máquinas
    try:
        top_gestor = df_equipamentos['gestao_responsavel'].mode()[0]
    except:
        top_gestor = "-"

    c1, c2, c3 = st.columns(3)

    # Ícones SVG
    icon_trator = get_icon("tractor", color="#2E7D32", size="32")
    icon_gear = get_icon("gear", color="#F59E0B", size="32")
    icon_check = get_icon("check", color="#2196F3", size="32")

    card_kpi(c1, "Total de Máquinas", total_frota, icon_trator, "#2E7D32")
    card_kpi(c2, "Modelos Distintos", total_modelos, icon_gear, "#F59E0B")
    card_kpi(c3, "Principal Gestor", str(top_gestor)[:15], icon_check, "#2196F3")

st.markdown("<br>", unsafe_allow_html=True)

# --- 4. ÁREA PRINCIPAL (ABAS) ---
tab_lista, tab_novo, tab_import = st.tabs(["📋 Lista & Edição Rápida", "➕ Novo Equipamento", "📂 Importação em Lote"])

# ==============================================================================
# ABA 1: LISTAGEM E EDIÇÃO
# ==============================================================================
with tab_lista:
    if df_equipamentos.empty:
        st.info("Nenhum equipamento cadastrado.")
    else:
        c_graf, c_tab = st.columns([1, 2])

        with c_graf:
            st.markdown("##### Distribuição por Modelo")
            df_chart = df_equipamentos['modelo'].value_counts().reset_index()
            df_chart.columns = ['Modelo', 'Qtd']
            fig = px.pie(df_chart, values='Qtd', names='Modelo', hole=0.6,
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=200)
            st.plotly_chart(fig, use_container_width=True)

        with c_tab:
            st.markdown("##### ✏️ Editor de Frota")
            st.caption("Altere 'Modelo' ou 'Gestão' diretamente na tabela.")

            # Adiciona coluna de seleção para exclusão
            df_edit = df_equipamentos.copy()
            df_edit.insert(0, "Selecionar", False)

            edited_df = st.data_editor(
                df_edit,
                use_container_width=True,
                hide_index=True,
                key="editor_equipamentos",
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Excluir?", width="small"),
                    "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                    "frota": st.column_config.TextColumn("Frota", disabled=True, width="small"),
                    "modelo": st.column_config.TextColumn("Modelo", width="medium", required=True),
                    "gestao_responsavel": st.column_config.TextColumn("Gestão Responsável", width="medium"),
                }
            )

            # --- LÓGICA DE SALVAR ALTERAÇÕES ---
            # Remove a coluna de seleção para comparar dados
            df_orig_data = df_edit.drop(columns=["Selecionar"])
            df_new_data = edited_df.drop(columns=["Selecionar"])

            if not df_orig_data.equals(df_new_data):
                conn = get_db_connection()
                try:
                    # Converte para dict para iterar
                    dict_orig = df_orig_data.set_index('id').to_dict('index')
                    dict_new = df_new_data.set_index('id').to_dict('index')

                    alteracoes = 0
                    for eid, row in dict_new.items():
                        orig_row = dict_orig.get(eid)
                        if orig_row['modelo'] != row['modelo'] or orig_row['gestao_responsavel'] != row[
                            'gestao_responsavel']:
                            conn.execute(
                                "UPDATE equipamentos SET modelo=?, gestao_responsavel=? WHERE id=?",
                                (row['modelo'], row['gestao_responsavel'], eid)
                            )
                            alteracoes += 1

                    if alteracoes > 0:
                        conn.commit()
                        st.toast(f"✅ {alteracoes} equipamento(s) atualizado(s)!", icon="💾")
                        import time;

                        time.sleep(1);
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
                finally:
                    conn.close()

            # --- LÓGICA DE EXCLUSÃO ---
            to_delete = edited_df[edited_df["Selecionar"]]
            if not to_delete.empty:
                st.markdown("---")
                st.error(f"⚠️ Você selecionou {len(to_delete)} item(ns) para exclusão.")

                col_confirm, _ = st.columns([1, 3])
                if col_confirm.button("🗑️ Confirmar Exclusão", type="primary"):
                    conn = get_db_connection()
                    try:
                        ids = to_delete['id'].tolist()
                        # Exclui um por um para segurança ou usa IN
                        for i in ids:
                            conn.execute("DELETE FROM equipamentos WHERE id=?", (i,))
                        conn.commit()

                        frotas_removidas = ", ".join(to_delete['frota'].astype(str).tolist())
                        registrar_log("EXCLUIR", "Equipamentos", f"Frotas: {frotas_removidas}")

                        st.toast("Equipamentos removidos com sucesso.", icon="🗑️")
                        import time;

                        time.sleep(1);
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
                    finally:
                        conn.close()

# ==============================================================================
# ABA 2: NOVO EQUIPAMENTO
# ==============================================================================
with tab_novo:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown("### Cadastro Manual")
        st.info("Preencha os dados para adicionar uma unidade individual à frota.")

    with c2:
        with st.container(border=True):
            with st.form("form_novo_equip", clear_on_submit=True):
                f_frota = st.text_input("Identificação da Frota (Número)*", placeholder="Ex: 64080")
                f_modelo = st.text_input("Modelo da Máquina*", placeholder="Ex: John Deere 8R")
                f_gestao = st.text_input("Gestor Responsável", placeholder="Ex: João Silva")

                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("💾 Salvar Equipamento", type="primary", use_container_width=True):
                    if not f_frota or not f_modelo:
                        st.error("Campos Frota e Modelo são obrigatórios.")
                    else:
                        conn = get_db_connection()
                        try:
                            # Verifica duplicidade
                            exist = conn.execute("SELECT id FROM equipamentos WHERE frota = ?", (f_frota,)).fetchone()
                            if exist:
                                st.error(f"Frota {f_frota} já existe no sistema.")
                            else:
                                conn.execute(
                                    "INSERT INTO equipamentos (frota, modelo, gestao_responsavel) VALUES (?, ?, ?)",
                                    (f_frota, f_modelo, f_gestao))
                                conn.commit()
                                registrar_log("CRIAR", "Equipamento", f"Frota: {f_frota}")
                                st.toast(f"Frota {f_frota} cadastrada!", icon="✅")
                                import time;

                                time.sleep(1);
                                st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
                        finally:
                            conn.close()

# ==============================================================================
# ABA 3: IMPORTAÇÃO
# ==============================================================================
with tab_import:
    st.subheader("Importação em Massa")


    # Gerar Modelo
    def gerar_modelo_equip():
        output = io.BytesIO()
        with pd.ExcelWriter(output) as writer:
            df = pd.DataFrame(
                {'frota': ['64080', '65010'], 'modelo': ['JD 8R', 'Colhedora CH570'], 'gestao': ['João', 'Maria']})
            df.to_excel(writer, index=False)
        output.seek(0)
        return output


    c_down, c_up = st.columns([1, 2])
    with c_down:
        st.markdown("1. Baixe o modelo:")
        st.download_button("📥 Baixar Planilha Modelo", gerar_modelo_equip(), "modelo_frotas.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

    with c_up:
        st.markdown("2. Faça o upload:")
        uploaded_file = st.file_uploader("Selecione o arquivo (.xlsx ou .csv)", type=['xlsx', 'csv'])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_up = pd.read_csv(uploaded_file)
            else:
                df_up = pd.read_excel(uploaded_file)

            # Normaliza colunas
            df_up.columns = [c.lower().strip() for c in df_up.columns]

            # Mapeia colunas esperadas
            col_map = {'frota': 'frota', 'modelo': 'modelo', 'gestao': 'gestao_responsavel',
                       'gestão': 'gestao_responsavel'}
            df_up = df_up.rename(columns=col_map)

            if 'frota' in df_up.columns and 'modelo' in df_up.columns:
                st.dataframe(df_up.head(), use_container_width=True)

                if st.button("🚀 Processar Importação", type="primary"):
                    conn = get_db_connection()
                    sucesso = 0
                    erros = 0

                    progress = st.progress(0)
                    for i, row in df_up.iterrows():
                        progress.progress((i + 1) / len(df_up))
                        try:
                            f = str(row['frota'])
                            m = str(row['modelo'])
                            g = str(row.get('gestao_responsavel', ''))

                            # Verifica se existe
                            exist = conn.execute("SELECT id FROM equipamentos WHERE frota = ?", (f,)).fetchone()
                            if exist:
                                conn.execute("UPDATE equipamentos SET modelo=?, gestao_responsavel=? WHERE frota=?",
                                             (m, g, f))
                            else:
                                conn.execute(
                                    "INSERT INTO equipamentos (frota, modelo, gestao_responsavel) VALUES (?, ?, ?)",
                                    (f, m, g))
                            sucesso += 1
                        except:
                            erros += 1

                    conn.commit()
                    conn.close()
                    st.toast(f"Importação concluída! {sucesso} processados.", icon="✅")
                    if erros > 0: st.warning(f"{erros} linhas falharam.")
                    import time;

                    time.sleep(1);
                    st.rerun()
            else:
                st.error("A planilha deve conter as colunas 'frota' e 'modelo'.")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")