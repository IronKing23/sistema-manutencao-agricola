import streamlit as st
import sqlite3
import pandas as pd
import os
from database import get_db_connection

# Tenta importar o Pillow para recortar as fotos como "Avatar"
try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# OBS: A autenticação é feita pelo app.py, não precisa repetir aqui.

st.title("👷‍♂️ Gestão de Funcionários")

# ==============================================================================
# CONFIGURAÇÃO DE DIRETÓRIO DE FOTOS
# ==============================================================================
FOTOS_DIR = "fotos_funcionarios"
os.makedirs(FOTOS_DIR, exist_ok=True)  # Cria a pasta automaticamente se não existir


def processar_foto(uploaded_file, matricula):
    """Salva a foto e corta ela em formato quadrado perfeito para avatar."""
    if not uploaded_file: return

    caminho = os.path.join(FOTOS_DIR, f"{matricula}.jpg")

    if PIL_AVAILABLE:
        try:
            img = Image.open(uploaded_file)
            # Lógica para recortar a foto em formato quadrado (Crop central)
            width, height = img.size
            tamanho_quadrado = min(width, height)
            left = (width - tamanho_quadrado) / 2
            top = (height - tamanho_quadrado) / 2
            right = (width + tamanho_quadrado) / 2
            bottom = (height + tamanho_quadrado) / 2

            img = img.crop((left, top, right, bottom))
            img = img.resize((300, 300))  # Padroniza todas as fotos para 300x300 pixels
            img = img.convert('RGB')  # Evita erro com fundos transparentes de PNG
            img.save(caminho, "JPEG", quality=85)
        except Exception as e:
            st.error(f"Erro ao processar imagem: {e}")
    else:
        # Fallback de segurança: salva a imagem bruta se o Pillow não estiver instalado
        with open(caminho, "wb") as f:
            f.write(uploaded_file.getbuffer())


# --- Funções Auxiliares ---
def carregar_funcionarios():
    """Carrega a lista completa de funcionários."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM funcionarios ORDER BY nome", conn)
        if not df.empty:
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
        df = pd.read_sql_query(
            "SELECT DISTINCT setor FROM funcionarios WHERE setor IS NOT NULL AND setor != '' ORDER BY setor", conn)
        return df['setor'].tolist()
    except:
        return []
    finally:
        conn.close()


# --- Layout em Abas ---
tab_novo, tab_importar, tab_editar, tab_excluir = st.tabs(
    ["➕ Novo Unitário", "📂 Importar (Lote)", "✏️ Editar", "🗑️ Excluir"])

# ==============================================================================
# ABA 1: NOVO CADASTRO (UNITÁRIO)
# ==============================================================================
with tab_novo:
    st.subheader("Adicionar Novo Funcionário")

    # IMPORTANTE: clear_on_submit=True limpa o arquivo de upload após salvar
    with st.form("form_add_func", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome_novo = st.text_input("Nome Completo*")

            # Lógica de Setor Flexível
            lista_setores = carregar_setores_existentes()
            if not lista_setores:
                lista_setores = ["Mecânica", "Elétrica", "Operação"]
            lista_setores.append("➕ Outro (Digitar Novo...)")

            setor_selecionado = st.selectbox("Selecione o Setor", options=lista_setores)
            if setor_selecionado == "➕ Outro (Digitar Novo...)":
                setor_digitado = st.text_input("Digite o nome do Novo Setor*")
                setor_final = setor_digitado
            else:
                setor_final = setor_selecionado

        with col2:
            matricula_novo = st.text_input("Matrícula/ID*")
            foto_novo = st.file_uploader("📸 Foto de Perfil (Opcional)", type=['jpg', 'jpeg', 'png'],
                                         help="A imagem será recortada num quadrado perfeitamente alinhado.")

        st.markdown("---")
        btn_salvar = st.form_submit_button("Salvar Novo Funcionário")

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

                # Salva a foto associando-a à matrícula recém-criada
                if foto_novo:
                    processar_foto(foto_novo, matricula_novo)

                st.success(f"✅ Funcionário {nome_novo} cadastrado com sucesso!")
                st.cache_data.clear()
            except sqlite3.IntegrityError:
                st.error("Erro: Já existe um funcionário com essa matrícula.")
            except Exception as e:
                st.error(f"Erro no banco de dados: {e}")
            finally:
                if conn: conn.close()

# ==============================================================================
# ABA 2: IMPORTAR EM LOTE
# ==============================================================================
with tab_importar:
    st.subheader("Importação em Massa via Excel/CSV")
    st.markdown("""
    **Instruções:**
    Faça upload de uma planilha contendo as seguintes colunas exatas:
    - `Nome` (Obrigatório)
    - `Matricula` (Obrigatório - deve ser única)
    - `Setor` (Obrigatório)

    *Nota: Fotos não podem ser importadas em lote. Elas devem ser adicionadas posteriormente via aba "Editar" ou apenas colocando os arquivos de imagem com o número da matrícula na pasta `fotos_funcionarios` do sistema.*
    """)

    uploaded_file = st.file_uploader("Carregar arquivo de funcionários", type=['xlsx', 'csv'])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)

            st.dataframe(df_upload.head(), use_container_width=True)

            if st.button("Processar Importação de Funcionários"):
                df_upload.columns = [c.title() for c in df_upload.columns]
                required_cols = {'Nome', 'Matricula', 'Setor'}

                if not required_cols.issubset(df_upload.columns):
                    st.error(
                        f"O arquivo deve conter as colunas: {required_cols}. Encontradas: {list(df_upload.columns)}")
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
                        st.cache_data.clear()

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
            mat_atual = str(dados['matricula'])

            c1, c2 = st.columns([1, 4])
            with c1:
                # Mostra a foto atual, se existir
                caminho_foto_atual = os.path.join(FOTOS_DIR, f"{mat_atual}.jpg")
                if os.path.exists(caminho_foto_atual):
                    st.image(caminho_foto_atual, caption="Foto Atual", use_container_width=True)
                else:
                    st.info("👤 Sem Foto")

            with c2:
                with st.form("form_edit_func"):
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        novo_nome = st.text_input("Nome", value=dados['nome'])
                    with col_e2:
                        nova_mat = st.text_input("Matrícula", value=mat_atual)

                    lista_setores_edit = carregar_setores_existentes()
                    lista_setores_edit.append("➕ Outro (Digitar Novo...)")

                    index_setor = 0
                    if dados['setor'] in lista_setores_edit:
                        index_setor = lista_setores_edit.index(dados['setor'])

                    col_esel, col_edig = st.columns(2)
                    with col_esel:
                        setor_sel_edit = st.selectbox("Setor", options=lista_setores_edit, index=index_setor)
                        nova_foto = st.file_uploader("📸 Substituir/Adicionar Foto", type=['jpg', 'jpeg', 'png'])

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

                                # Gestão dos Arquivos de Imagem na Edição
                                if mat_atual != nova_mat:
                                    # Se a matrícula mudou, renomeamos o arquivo de foto antigo para a matrícula nova
                                    caminho_velho = os.path.join(FOTOS_DIR, f"{mat_atual}.jpg")
                                    caminho_novo = os.path.join(FOTOS_DIR, f"{nova_mat}.jpg")
                                    if os.path.exists(caminho_velho):
                                        os.rename(caminho_velho, caminho_novo)

                                if nova_foto:
                                    # Se o usuário enviou uma foto nova, ela sobrescreve qualquer coisa
                                    processar_foto(nova_foto, nova_mat)

                                st.success("✅ Dados atualizados com sucesso!")
                                st.cache_data.clear()
                                st.rerun()
                            except sqlite3.IntegrityError:
                                st.error("Erro: Já existe outro funcionário com essa nova matrícula.")
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
        escolha_del = st.selectbox("Selecione para Excluir:", options=df_funcs_del['display'], index=None,
                                   key="sb_del_func")

        if escolha_del:
            dados_del = df_funcs_del[df_funcs_del['display'] == escolha_del].iloc[0]
            id_del = int(dados_del['id'])
            mat_del = str(dados_del['matricula'])

            with st.container(border=True):
                c_del1, c_del2 = st.columns([1, 5])
                with c_del1:
                    foto_del = os.path.join(FOTOS_DIR, f"{mat_del}.jpg")
                    if os.path.exists(foto_del):
                        st.image(foto_del, use_container_width=True)
                    else:
                        st.markdown("👤")

                with c_del2:
                    st.markdown(f"### {dados_del['nome']}")
                    st.markdown(f"**Matrícula:** {mat_del} | **Setor:** {dados_del['setor']}")

                st.divider()
                confirmar = st.checkbox("⚠️ Confirmo que desejo excluir este registro e sua foto permanentemente.")

                if st.button("🗑️ Excluir Funcionário", type="primary", disabled=not confirmar):
                    conn = None
                    try:
                        conn = get_db_connection()
                        conn.execute("DELETE FROM funcionarios WHERE id = ?", (id_del,))
                        conn.commit()

                        # Limpa o lixo (Apaga a foto do HD se existir)
                        if os.path.exists(foto_del):
                            try:
                                os.remove(foto_del)
                            except Exception as e:
                                print(f"Não foi possível apagar a foto: {e}")

                        st.success("Funcionário excluído do banco de dados.")
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