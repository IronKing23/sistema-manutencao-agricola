import streamlit as st
import streamlit.components.v1 as components # Importante para o relógio funcionar
import os
import autenticacao # Seu arquivo de login

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(layout="wide", page_title="Sistema de Manutenção")

# --- 2. VERIFICAÇÃO DE SEGURANÇA ---
if not autenticacao.check_password():
    st.stop()

# --- 3. DEFINIÇÃO SEGURA DAS PÁGINAS ---
def criar_pagina(arquivo, titulo, icone, default=False):
    if os.path.exists(arquivo):
        return st.Page(arquivo, title=titulo, icon=icone, default=default)
    return None

# Lista de páginas (ADICIONADO A NOVA PÁGINA AQUI)
paginas_brutas = [
    ("pages/0_Inicio.py", "Início", "🏠", True),
    ("pages/1_Painel_Principal.py", "Visão Geral", "📊", False),
    ("pages/15_Indicadores_KPI.py", "Indicadores KPI (MTBF/MTTR)", "📈", False), # <--- NOVA PÁGINA
    ("pages/7_Historico_Maquina.py", "Prontuário da Máquina", "🚜", False),
    ("pages/10_Mapa_Atendimentos.py", "Mapa de Ocorrências", "🗺️", False),
    ("pages/5_Nova_Ordem_Servico.py", "Abrir Chamado (OS)", "📝", False),
    ("pages/6_Gerenciar_Atendimento.py", "Gerenciar Atendimentos", "🔄", False),
    ("pages/11_Quadro_Avisos.py", "Quadro de Avisos", "📌", False),
    ("pages/13_Comunicacao.py", "Central WhatsApp", "📱", False),
    ("pages/2_Cadastro_Equipamentos.py", "Equipamentos", "🚛", False),
    ("pages/3_Cadastro_Funcionarios.py", "Funcionários", "👷", False),
    ("pages/4_Cadastro_Operacoes.py", "Tipos de Operação", "⚙️", False),
    ("pages/14_Cadastro_Areas.py", "Áreas / Talhões", "📍", False),
    ("pages/8_Backup_Seguranca.py", "Backup e Restore", "💾", False),
    ("pages/9_Gestao_Usuarios.py", "Gestão de Usuários", "🔐", False),
    ("pages/12_Auditoria.py", "Logs de Auditoria", "🕵️", False),
]

paginas_validas = {}
lista_plana = []

for arquivo, titulo, icone, default in paginas_brutas:
    pg = criar_pagina(arquivo, titulo, icone, default)
    if pg:
        paginas_validas[titulo] = pg
        lista_plana.append(pg)

# --- 4. NAVEGAÇÃO ---
if not lista_plana:
    st.error("🚨 Erro Crítico: Nenhuma página válida encontrada.")
    st.stop()

pg = st.navigation(lista_plana, position="hidden")

# --- 5. MENU LATERAL PERSONALIZADO ---
with st.sidebar:
    # --- WIDGET DE RELÓGIO + CALENDÁRIO ---
    # HTML/CSS/JS Otimizado para funcionar o clique
    relogio_iframe = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <style>
            body { 
                margin: 0; 
                font-family: "Source Sans Pro", sans-serif; 
                background-color: transparent;
                display: flex;
                justify-content: center;
                overflow: hidden; /* Evita barras de rolagem */
            }
            .clock-container {
                position: relative;
                width: 95%;
                background-color: #262730; 
                border: 1px solid #464b5d; 
                border-radius: 8px; 
                padding: 10px; 
                text-align: center; 
                cursor: pointer;
                transition: all 0.3s ease;
                box-sizing: border-box;
            }
            .clock-container:hover {
                border-color: #2196F3;
                transform: scale(1.02);
                box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            }
            .label { color: #aaa; font-size: 11px; letter-spacing: 1px; margin-bottom: 2px; }
            .time { color: #fff; font-size: 26px; font-weight: bold; line-height: 1; font-family: monospace; }
            .date { color: #4CAF50; font-size: 13px; font-weight: bold; margin-top: 4px; text-transform: uppercase; }
            
            /* Input invisível que cobre tudo para garantir o clique */
            input[type="date"] {
                position: absolute;
                top: 0; left: 0;
                width: 100%; height: 100%;
                opacity: 0;
                cursor: pointer;
                z-index: 10;
            }
        </style>
    </head>
    <body>
        <div class="clock-container" onclick="try{document.getElementById('picker').showPicker()}catch(e){}">
            <div class="label">AGORA</div>
            <div class="time" id="time">--:--:--</div>
            <div class="date" id="date">--/--/----</div>
            
            <input type="date" id="picker">
        </div>

        <script>
            function updateClock() {
                const now = new Date();
                
                // Formata Hora
                const timeStr = now.toLocaleTimeString('pt-BR');
                
                // Formata Data
                const options = { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' };
                let dateStr = now.toLocaleDateString('pt-BR', options);
                // Remove pontos extras de abreviação se houver
                dateStr = dateStr.replace(/\./g, '');
                
                // Atualiza Texto
                document.getElementById('time').innerText = timeStr;
                document.getElementById('date').innerText = dateStr;
                
                // Mantém o calendário sincronizado com o dia de hoje
                // formata YYYY-MM-DD
                const year = now.getFullYear();
                const month = String(now.getMonth() + 1).padStart(2, '0');
                const day = String(now.getDate()).padStart(2, '0');
                document.getElementById('picker').value = `${year}-${month}-${day}`;
            }
            
            // Roda a cada segundo
            setInterval(updateClock, 1000);
            updateClock();
        </script>
    </body>
    </html>
    """
    # Renderiza o widget com altura fixa suficiente
    components.html(relogio_iframe, height=110)

    st.title("Navegação")
    
    def link_se_existir(titulo_chave):
        if titulo_chave in paginas_validas:
            st.page_link(paginas_validas[titulo_chave])

    link_se_existir("Início")
    st.markdown("---")
    
    with st.expander("📊 Dashboards", expanded=True): # Mudei para True para já abrir mostrando
        link_se_existir("Visão Geral")
        link_se_existir("Indicadores KPI (MTBF/MTTR)") # <--- ADICIONADO NO MENU
        link_se_existir("Prontuário da Máquina")
        link_se_existir("Mapa de Ocorrências")
        
    with st.expander("🛠️ Operacional", expanded=False):
        link_se_existir("Abrir Chamado (OS)")
        link_se_existir("Gerenciar Atendimentos")
        link_se_existir("Quadro de Avisos")
        link_se_existir("Central WhatsApp")
        
    with st.expander("📂 Cadastros", expanded=False):
        link_se_existir("Equipamentos")
        link_se_existir("Funcionários")
        link_se_existir("Tipos de Operação")
        link_se_existir("Áreas / Talhões")
        
    with st.expander("⚙️ Sistema", expanded=False):
        link_se_existir("Backup e Restore")
        link_se_existir("Gestão de Usuários")
        link_se_existir("Logs de Auditoria")
    
    st.divider()
    
    # Botão Sair
    if st.button("Sair do Sistema", use_container_width=True):
        autenticacao.st.session_state["logged_in"] = False
        autenticacao.st.session_state["just_logged_out"] = True
        try:
            autenticacao.get_manager().delete("manutencao_user")
        except: pass
        st.rerun()
        
    if "user_nome" in st.session_state:
        st.caption(f"👤 {st.session_state['user_nome']}")

# --- 6. EXECUTAR ---
pg.run()