import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from database import get_db_connection


st.title("🗺️ Mapa de Calor e Rastreamento")

# --- Carregamento de Dados ---
def carregar_dados_mapa():
    conn = get_db_connection()
    try:
        # ATUALIZADO: Adicionado 'os.numero_os_oficial' na query
        query = """
        SELECT 
            os.id,
            os.latitude, 
            os.longitude, 
            os.numero_os_oficial, -- CAMPO NOVO
            e.frota, 
            e.modelo, 
            op.nome as operacao,
            op.cor as cor_hex,
            os.local_atendimento, 
            os.descricao,
            os.status,
            os.data_hora
        FROM ordens_servico os
        JOIN equipamentos e ON os.equipamento_id = e.id
        JOIN tipos_operacao op ON os.tipo_operacao_id = op.id
        WHERE os.latitude IS NOT NULL AND os.longitude IS NOT NULL
        ORDER BY os.data_hora DESC
        """
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()

df_mapa = carregar_dados_mapa()

if df_mapa.empty:
    st.info("Ainda não há ordens de serviço com coordenadas GPS cadastradas.")
    st.markdown("💡 **Dica:** Edite os atendimentos na página 'Gerenciar' e adicione Latitude/Longitude.")
else:
    # ==============================================================================
    # ÁREA DE FILTROS
    # ==============================================================================
    with st.expander("🔎 Filtros Avançados (Clique para expandir)", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        lista_frotas = sorted(df_mapa['frota'].unique())
        filtro_frota = col1.multiselect("🚜 Frota / Máquina", options=lista_frotas, placeholder="Todas")
        
        # Remove vazios da lista de locais
        lista_locais = sorted([x for x in df_mapa['local_atendimento'].unique() if x])
        filtro_local = col2.multiselect("📍 Local / Talhão", options=lista_locais, placeholder="Todos")
        
        lista_ops = sorted(df_mapa['operacao'].unique())
        filtro_op = col3.multiselect("🔧 Tipo de Serviço", options=lista_ops, placeholder="Todos")
        
        ver_concluidos = col4.checkbox("Ver Concluídos?", value=True)

    # --- APLICAÇÃO DOS FILTROS ---
    df_plot = df_mapa.copy()

    if filtro_frota:
        df_plot = df_plot[df_plot['frota'].isin(filtro_frota)]
    
    if filtro_local:
        df_plot = df_plot[df_plot['local_atendimento'].isin(filtro_local)]
        
    if filtro_op:
        df_plot = df_plot[df_plot['operacao'].isin(filtro_op)]
        
    if not ver_concluidos:
        df_plot = df_plot[df_plot['status'] != 'Concluído']

    # ==============================================================================
    # RENDERIZAÇÃO DO MAPA
    # ==============================================================================
    st.divider()
    
    if df_plot.empty:
        st.warning("Nenhum ponto encontrado com esses filtros.")
    else:
        k1, k2, k3 = st.columns(3)
        k1.metric("Ocorrências no Mapa", len(df_plot))
        k2.metric("Frotas Distintas", df_plot['frota'].nunique())
        local_top = df_plot['local_atendimento'].mode()[0] if not df_plot.empty else "-"
        k3.metric("Local com mais Foco", local_top)

        avg_lat = df_plot['latitude'].mean()
        avg_lon = df_plot['longitude'].mean()
        
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)

        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satélite',
            overlay=False,
            control=True
        ).add_to(m)

        for _, row in df_plot.iterrows():
            cor_icon = row['cor_hex'] if row['cor_hex'] else "blue"
            
            # Texto do Popup (Ao Clicar)
            num_ref_popup = row['numero_os_oficial'] if row['numero_os_oficial'] else f"Ticket #{row['id']}"
            
            html_popup = f"""
            <div style="font-family: sans-serif; width: 220px;">
                <h4 style="margin-bottom: 5px;">{row['frota']} <small>({num_ref_popup})</small></h4>
                <span style="background-color: {cor_icon}; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 12px;">
                    {row['operacao']}
                </span>
                <hr style="margin: 5px 0;">
                <b>Modelo:</b> {row['modelo']}<br>
                <b>Local:</b> {row['local_atendimento']}<br>
                <b>Data:</b> {pd.to_datetime(row['data_hora']).strftime('%d/%m %H:%M')}<br>
                <br>
                <i>"{row['descricao']}"</i>
            </div>
            """
            
            # --- NOVA LÓGICA DO TOOLTIP (Ao Passar o Mouse) ---
            if row['numero_os_oficial']:
                # Se tiver número oficial, mostra ele
                label_os = f"O.S: {row['numero_os_oficial']}"
            else:
                # Se não tiver, mostra o Ticket ID interno
                label_os = f"Ticket: {row['id']}"
                
            texto_tooltip = f"Frota: {row['frota']} | Tipo: {row['operacao']} | {label_os}"

            # Marcador
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=folium.Popup(html_popup, max_width=300),
                tooltip=texto_tooltip, # Aplica o texto novo aqui
                icon=folium.Icon(color="gray", icon="wrench", prefix="fa")
            ).add_to(m)

            # Círculo
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=8,
                color=cor_icon,
                fill=True,
                fill_color=cor_icon,
                fill_opacity=0.8,
                tooltip=texto_tooltip # E aqui também
            ).add_to(m)

        st_folium(m, width="100%", height=600)