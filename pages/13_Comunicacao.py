import streamlit as st
import pandas as pd
from urllib.parse import quote
from database import get_db_connection
import sqlite3

st.set_page_config(layout="wide", page_title="Central WhatsApp")
st.title("📱 Central de Comunicação & Agenda")

# --- Funções de Carregamento ---
def carregar_funcionarios():
    conn = get_db_connection()
    df = pd.read_sql("SELECT id, nome, telefone, setor FROM funcionarios ORDER BY nome", conn)
    conn.close()
    return df

def carregar_agenda_externa():
    conn = get_db_connection()
    try:
        df = pd.read_sql("SELECT * FROM agenda_externa ORDER BY nome", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

# --- Layout em Abas ---
tab_envio, tab_agenda = st.tabs(["💬 Enviar Mensagem", "📒 Gerenciar Agenda"])

# ==============================================================================
# ABA 1: ENVIAR MENSAGEM
# ==============================================================================
with tab_envio:
    col_esq, col_dir = st.columns([1, 1])

    # --- Coluna da Esquerda: Seleção de Destinatário ---
    with col_esq:
        with st.container(border=True):
            st.subheader("1. Selecionar Destinatário")
            
            # Escolha da Fonte
            origem = st.radio("Origem do Contato:", ["Digitar Manualmente", "Funcionário", "Agenda Externa"], horizontal=True)
            
            telefone_final = ""
            nome_destinatario = ""
            
            if origem == "Digitar Manualmente":
                c_ddi, c_ddd, c_num = st.columns([1, 1, 3])
                with c_ddi:
                    ddi = st.text_input("DDI", value="55", max_chars=3, key="man_ddi")
                with c_ddd:
                    # ALTERADO: Padrão 67
                    ddd = st.text_input("DDD", value="67", max_chars=2, key="man_ddd")
                with c_num:
                    num = st.text_input("Número", placeholder="Ex: 999998888", key="man_num")
                
                if ddd and num:
                    telefone_final = f"{ddi}{ddd}{num}"
                    
            elif origem == "Funcionário":
                df_func = carregar_funcionarios()
                if not df_func.empty:
                    df_func['label'] = df_func['nome'] + " - " + df_func['setor']
                    sel_func = st.selectbox("Buscar Funcionário:", options=df_func['label'], index=None)
                    
                    if sel_func:
                        row = df_func[df_func['label'] == sel_func].iloc[0]
                        tel_db = row['telefone']
                        if tel_db:
                            telefone_final = tel_db
                            nome_destinatario = row['nome']
                            st.success(f"📞 Telefone encontrado: {tel_db}")
                        else:
                            st.error("⚠️ Funcionário sem telefone. Vá na aba 'Gerenciar Agenda' para cadastrar.")
                else:
                    st.info("Nenhum funcionário cadastrado.")
                        
            elif origem == "Agenda Externa":
                df_ext = carregar_agenda_externa()
                if df_ext.empty:
                    st.warning("Agenda externa vazia.")
                else:
                    df_ext['label'] = df_ext['nome'] + " (" + df_ext['tipo'] + ")"
                    sel_ext = st.selectbox("Buscar Contato:", options=df_ext['label'], index=None)
                    
                    if sel_ext:
                        row = df_ext[df_ext['label'] == sel_ext].iloc[0]
                        telefone_final = row['telefone']
                        nome_destinatario = row['nome']
                        st.success(f"📞 Telefone carregado: {telefone_final}")

            # Limpeza do número
            if telefone_final:
                telefone_limpo = "".join(filter(str.isdigit, str(telefone_final)))
                if len(telefone_limpo) <= 11 and origem != "Digitar Manualmente":
                    telefone_limpo = "55" + telefone_limpo
            else:
                telefone_limpo = ""

    # --- Coluna da Direita: Mensagem e Envio ---
    with col_dir:
        with st.container(border=True):
            st.subheader("2. Compor Mensagem")
            
            templates = {
                "Personalizado": "",
                "Aviso de Conclusão": "Olá! Informamos que a manutenção do equipamento foi concluída e ele já está liberado.",
                "Solicitação de Peça": "Olá! Precisamos da aprovação para compra de peças referente à OS em aberto.",
                "Máquina Parada": "Alerta: Equipamento parado por falha mecânica. Aguardando instruções.",
                "Cobrança": "Olá, poderia me dar um retorno sobre o status da solicitação?"
            }
            
            choice = st.selectbox("Modelo de Texto:", list(templates.keys()))
            texto_base = templates[choice]
            
            mensagem = st.text_area("Texto da Mensagem:", value=texto_base, height=150)
            
            st.markdown("---")
            
            if telefone_limpo and mensagem:
                texto_encoded = quote(mensagem)
                link_zap = f"https://web.whatsapp.com/send?phone={telefone_limpo}&text={texto_encoded}"
                
                st.link_button(
                    label=f"🚀 Enviar para {nome_destinatario if nome_destinatario else telefone_limpo}", 
                    url=link_zap, 
                    type="primary", 
                    use_container_width=True
                )
            else:
                st.button("Preencha destinatário e mensagem", disabled=True, use_container_width=True)

# ==============================================================================
# ABA 2: GERENCIAR AGENDA (ATUALIZADA COM EDIÇÃO)
# ==============================================================================
with tab_agenda:
    c1, c2 = st.columns(2)
    
    # --- PARTE A: VINCULAR TELEFONE A FUNCIONÁRIOS ---
    with c1:
        st.subheader("👷 Telefones de Funcionários")
        st.caption("Atualize o contato dos colaboradores." \
        "Clique duas vezes para confirmar")
        
        df_funcs = carregar_funcionarios()
        
        with st.form("form_tel_func"):
            func_opcoes = df_funcs['nome'].tolist()
            func_selecionado = st.selectbox("Selecione o Funcionário:", options=func_opcoes)
            
            # Tenta pegar o telefone atual para mostrar no campo
            tel_atual = ""
            if func_selecionado:
                tel_atual = df_funcs[df_funcs['nome'] == func_selecionado]['telefone'].values[0]
                if tel_atual is None: tel_atual = ""
            
            # ALTERADO: Exemplo DDD 67
            novo_tel_func = st.text_input("Número (com DDD):", value=tel_atual, placeholder="Ex: 67999998888")
            
            if st.form_submit_button("💾 Atualizar Telefone"):
                if func_selecionado and novo_tel_func:
                    conn = get_db_connection()
                    conn.execute("UPDATE funcionarios SET telefone = ? WHERE nome = ?", (novo_tel_func, func_selecionado))
                    conn.commit()
                    conn.close()
                    st.success(f"Telefone de {func_selecionado} atualizado!")
                    st.rerun()

        st.dataframe(df_funcs[['nome', 'telefone']], use_container_width=True, hide_index=True)

    # --- PARTE B: AGENDA EXTERNA (COM EDIÇÃO) ---
    with c2:
        st.subheader("📒 Contatos Externos")
        st.caption("Fornecedores, Mecânicos Terceiros, etc.")
        
        # Carrega dados
        df_ext = carregar_agenda_externa()
        
        # Modo de Operação: Novo ou Editar
        modo = st.radio("Ação:", ["➕ Novo Contato", "✏️ Editar Existente"], horizontal=True, key="modo_agenda")
        
        # Dados do formulário
        nome_input = ""
        tipo_input = "Fornecedor"
        tel_input = ""
        id_editar = None
        
        if modo == "✏️ Editar Existente":
            if df_ext.empty:
                st.warning("Não há contatos para editar.")
            else:
                # Cria lista para seleção
                opcoes_ext = df_ext['nome'].tolist()
                contato_sel = st.selectbox("Selecione para editar:", options=opcoes_ext, key="sel_edit_ext")
                
                if contato_sel:
                    # Pega dados atuais
                    dados_contato = df_ext[df_ext['nome'] == contato_sel].iloc[0]
                    id_editar = int(dados_contato['id'])
                    nome_input = dados_contato['nome']
                    tipo_input = dados_contato['tipo']
                    tel_input = dados_contato['telefone']

        with st.form("form_agenda_ext"):
            nome_ext = st.text_input("Nome:", value=nome_input)
            tipo_ext = st.selectbox("Tipo:", ["Fornecedor", "Mecânico Terceiro", "Gestor Externo", "Outro"], 
                                    index=["Fornecedor", "Mecânico Terceiro", "Gestor Externo", "Outro"].index(tipo_input) if tipo_input in ["Fornecedor", "Mecânico Terceiro", "Gestor Externo", "Outro"] else 0)
            # ALTERADO: Exemplo DDD 67
            tel_ext = st.text_input("Telefone (com DDD):", value=tel_input, placeholder="Ex: 67988887777")
            
            texto_botao = "Salvar Alterações" if modo == "✏️ Editar Existente" else "Adicionar Contato"
            
            if st.form_submit_button(texto_botao):
                if nome_ext and tel_ext:
                    conn = get_db_connection()
                    if modo == "➕ Novo Contato":
                        conn.execute("INSERT INTO agenda_externa (nome, telefone, tipo) VALUES (?, ?, ?)", (nome_ext, tel_ext, tipo_ext))
                        msg = f"{nome_ext} adicionado!"
                    else:
                        # Modo Editar
                        conn.execute("UPDATE agenda_externa SET nome=?, telefone=?, tipo=? WHERE id=?", (nome_ext, tel_ext, tipo_ext, id_editar))
                        msg = f"{nome_ext} atualizado!"
                        
                    conn.commit()
                    conn.close()
                    st.success(msg)
                    st.rerun()
        
        # Lista e Exclusão
        if not df_ext.empty:
            st.markdown("###### Lista de Contatos:")
            for index, row in df_ext.iterrows():
                col_txt, col_del = st.columns([4, 1])
                with col_txt:
                    st.text(f"{row['nome']} ({row['tipo']}): {row['telefone']}")
                with col_del:
                    if st.button("🗑️", key=f"del_ext_{row['id']}"):
                        conn = get_db_connection()
                        conn.execute("DELETE FROM agenda_externa WHERE id = ?", (row['id'],))
                        conn.commit()
                        conn.close()
                        st.rerun()