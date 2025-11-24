import streamlit as st
import os
import sys



from datetime import datetime

st.title("💾 Backup e Segurança de Dados")

# Nome do arquivo de banco de dados
DB_FILE = "manutencao.db"

tab_backup, tab_restore = st.tabs(["📥 Fazer Backup (Download)", "📤 Restaurar Backup (Upload)"])

# ==============================================================================
# ABA 1: FAZER BACKUP
# ==============================================================================
with tab_backup:
    st.subheader("Salvar Cópia dos Dados")
    st.markdown("""
    **Por que fazer backup?**
    O sistema salva todos os dados em um arquivo local (`manutencao.db`). Se este computador der problema, você pode perder tudo.
    
    **Recomendação:**
    1. Clique no botão abaixo para baixar o arquivo.
    2. Salve-o em um local seguro (Google Drive, OneDrive, Pen Drive ou envie por e-mail para si mesmo).
    3. Faça isso pelo menos **uma vez por semana**.
    """)
    
    # Verifica se o banco existe antes de permitir o download
    if os.path.exists(DB_FILE):
        # Lê o arquivo em modo binário
        with open(DB_FILE, "rb") as f:
            db_bytes = f.read()
            
        # Gera um nome com data e hora (Ex: backup_manutencao_2023-10-27.db)
        timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")
        nome_arquivo = f"backup_manutencao_{timestamp}.db"
        
        st.download_button(
            label="⬇️ CLIQUE AQUI PARA BAIXAR O BACKUP",
            data=db_bytes,
            file_name=nome_arquivo,
            mime="application/x-sqlite3",
            type="primary", # Deixa o botão destacado
            help="Salva uma cópia completa de todas as máquinas, funcionários e ordens de serviço."
        )
        st.success(f"Arquivo pronto: {len(db_bytes) / 1024:.1f} KB")
        
    else:
        st.error("⚠️ Erro crítico: O arquivo de banco de dados não foi encontrado na pasta do sistema.")

# ==============================================================================
# ABA 2: RESTAURAR (RESTORE)
# ==============================================================================
with tab_restore:
    st.subheader("Restaurar Sistema Antigo")
    st.markdown("""
    **CUIDADO: ZONA DE PERIGO** 🚨
    
    Esta função serve para recuperar o sistema a partir de um arquivo salvo anteriormente.
    
    ⚠️ **Atenção:** Ao carregar um arquivo aqui, **TODOS os dados atuais serão apagados e substituídos** pelos dados do arquivo que você enviar.
    Se você cadastrou algo hoje e carregar um backup de ontem, os dados de hoje serão perdidos para sempre.
    """)
    
    st.divider()
    
    uploaded_file = st.file_uploader("Selecione o arquivo de backup (.db) para restaurar:", type=['db'])
    
    if uploaded_file:
        st.warning(f"Você selecionou o arquivo: **{uploaded_file.name}**")
        
        # Checkbox de segurança dupla
        confirmacao = st.checkbox("🔴 Estou ciente de que os dados atuais serão SUBSTITUÍDOS e não poderão ser recuperados.")
        
        if st.button("Confirmar Restauração", type="primary", disabled=not confirmacao):
            try:
                # Salva o arquivo enviado SOBRESCREVENDO o atual
                with open(DB_FILE, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                st.success("✅ Restauração concluída com sucesso! O sistema foi atualizado.")
                st.info("Por favor, recarregue a página ou navegue para o Painel Principal para ver os dados restaurados.")
                
                # Limpa cache do Streamlit para forçar recarregamento dos dados novos
                st.cache_data.clear()
                
            except Exception as e:
                st.error(f"Erro ao tentar restaurar o banco: {e}")