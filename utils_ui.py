import streamlit as st


def load_custom_css():
    """Carrega o CSS global com tema Agro/Manutenção (Suporta Light/Dark mode)."""
    st.markdown("""
    <style>
        /* Fonte Moderna e Robusta */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* --- PALETA AGRO & MANUTENÇÃO (Adaptação Automática) --- */
        :root {
            /* Fundo levemente cinza/terra clara */
            --bg-color: #F4F7F6;         
            --sidebar-bg: #FFFFFF;       
            --card-bg: #FFFFFF;          
            --text-color: #1E293B;       
            --text-secondary: #526A5A;   /* Cinza com leve toque esverdeado */
            --sidebar-text: #475569;     
            --border-color: #E2E8F0;     
            --input-bg: #FFFFFF;         
            --hover-bg: #F0FDF4;         /* Verde ultra claro no hover */

            /* Cores Temáticas Agrícolas */
            --primary-color: #15803D;    /* Verde Trator (Força/Plantação) */
            --accent-color: #EAB308;     /* Amarelo Máquina (Atenção/Equipamento) */
            --metal-color: #64748B;      /* Cor de aço/oficina */
            --danger-color: #DC2626;     /* Vermelho Parada/Crítico */

            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            --shadow-agro: 0 10px 25px -5px rgba(21, 128, 61, 0.15); /* Sombra verde suave */
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --bg-color: #0B1120;         /* Azul muito escuro/noite */
                --sidebar-bg: #111827;
                --card-bg: #1F2937;
                --text-color: #F8FAFC;
                --text-secondary: #94A3B8;
                --sidebar-text: #CBD5E1;
                --border-color: #374151;
                --input-bg: #111827;
                --hover-bg: #162E25;         /* Fundo escuro esverdeado */

                --primary-color: #22C55E;    /* Verde mais vibrante para contraste escuro */
                --accent-color: #FACC15;
                --shadow-agro: 0 10px 25px -5px rgba(34, 197, 94, 0.2);
            }
        }

        /* --- ANIMAÇÕES TEMÁTICAS --- */
        /* Animação para alertas (Máquina Quebrada / Status Crítico) */
        @keyframes engine-pulse {
            0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.5); }
            70% { box-shadow: 0 0 0 12px rgba(220, 38, 38, 0); }
            100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }
        }

        /* --- ELEMENTOS GERAIS --- */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* CABEÇALHO DO APP (Efeito Metálico/Agro) */
        .ui-header {
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 2px solid var(--border-color);
            position: relative;
        }

        .ui-header::after {
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            width: 80px;
            height: 2px;
            background: linear-gradient(90deg, var(--primary-color), var(--accent-color));
        }

        .ui-header h1 {
            font-size: 2.2rem;
            font-weight: 800;
            margin: 0 0 0.5rem 0;
            /* Texto com gradiente Agro */
            background: linear-gradient(45deg, var(--primary-color), var(--accent-color));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .ui-header p {
            font-size: 1.05rem;
            color: var(--text-secondary);
            margin: 0;
            font-weight: 500;
        }

        /* --- CARDS DE KPI (Estilo Painel de Equipamento) --- */
        .ui-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: var(--shadow-sm);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        /* Efeito Luminoso no topo do card ao passar o rato (Painel Ligado) */
        .ui-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, var(--primary-color), var(--accent-color));
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .ui-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-agro);
            border-color: var(--primary-color);
        }

        .ui-card:hover::before {
            opacity: 1;
        }

        /* Aciona a animação de pulso se o card tiver cor vermelha (Crítico) */
        .ui-card[style*="#EF4444"], .ui-card[style*="#DC2626"], .ui-card[style*="red"] {
            animation: engine-pulse 2s infinite;
        }

        .card-label {
            font-size: 0.9rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .card-value {
            font-size: 2.5rem;
            font-weight: 800;
            color: var(--text-color);
            line-height: 1.2;
        }

        .card-subtext {
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 500;
        }

        /* --- ESTADO VAZIO (EMPTY STATE) --- */
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 3rem;
            background: var(--card-bg);
            border: 2px dashed var(--border-color);
            border-radius: 12px;
            color: var(--text-secondary);
            text-align: center;
            transition: all 0.3s ease;
        }

        .empty-state:hover {
            border-color: var(--accent-color);
            background: var(--hover-bg);
        }

        .empty-state-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
            opacity: 0.8;
            filter: grayscale(0.5); /* Tom mais de aço/ferramenta */
        }

        .empty-state-text {
            font-size: 1.1rem;
            font-weight: 600;
        }
    </style>
    """, unsafe_allow_html=True)


def ui_header(title, subtitle, icon="🚜"):
    """Renderiza o cabeçalho padronizado com estilo Agro."""
    st.markdown(f"""
    <div class="ui-header">
        <h1>{icon} {title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def ui_kpi_card(col, title, value, icon_svg="", color="var(--primary-color)", subtext=""):
    """Renderiza um card de KPI padronizado como um painel de máquina."""

    # Substituição de cores antigas pelas novas temáticas (se passadas como nome)
    if color == "#3B82F6" or color == "blue": color = "var(--primary-color)"  # Substitui Azul pelo Verde Agro
    if color == "#10B981" or color == "green": color = "var(--primary-color)"
    if color == "#F59E0B" or color == "orange": color = "var(--accent-color)"
    if color == "#EF4444" or color == "red": color = "var(--danger-color)"
    if color in ["#ddd", "#E0E0E0", "transparent", "white"]: color = "var(--metal-color)"

    icon_render = ""
    if icon_svg:
        svg = str(icon_svg).replace('\n', '').strip()
        if svg.startswith("<svg"):
            icon_render = svg
        else:
            icon_render = f"<span style='font-size: 1.4rem;'>{icon_svg}</span>"

    html = f"""
    <div class="ui-card" style="border-left: 5px solid {color};">
        <div class="card-label" style="color: {color};">
            {icon_render} {title}
        </div>
        <div class="card-value">{value}</div>
        <div class="card-subtext">{subtext}</div>
    </div>
    """
    col.markdown(html, unsafe_allow_html=True)


def ui_empty_state(message="Nenhum dado de máquina encontrado.", icon="🔧"):
    """Renderiza um visual para quando não há dados/frotas."""
    st.markdown(f"""
    <div class="empty-state">
        <div class="empty-state-icon">{icon}</div>
        <div class="empty-state-text">{message}</div>
    </div>
    """, unsafe_allow_html=True)


# --- RETROCOMPATIBILIDADE ---
# Alias para evitar erros de importação em páginas antigas (ex: 1_Painel_Principal.py)
card_kpi = ui_kpi_card