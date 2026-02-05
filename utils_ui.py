import streamlit as st


def load_custom_css():
    """Carrega o CSS global com tema profissional (light/dark) e componentes consistentes."""
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root {
            --bg-color: #F4F7FB;
            --sidebar-bg: #FFFFFF;
            --card-bg: #FFFFFF;
            --text-color: #0F172A;
            --text-secondary: #64748B;
            --sidebar-text: #475569;
            --border-color: #E2E8F0;
            --input-bg: #FFFFFF;
            --hover-bg: #F1F5F9;
            --primary-color: #16A34A;
            --primary-soft: rgba(22, 163, 74, 0.10);
            --info-soft: rgba(37, 99, 235, 0.08);
            --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.06);
            --shadow-md: 0 8px 24px rgba(15, 23, 42, 0.08);
            --shadow-lg: 0 16px 36px rgba(15, 23, 42, 0.12);
            --radius-sm: 10px;
            --radius-md: 14px;
            --radius-lg: 18px;
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --bg-color: #0B1220;
                --sidebar-bg: #111827;
                --card-bg: #172033;
                --text-color: #E2E8F0;
                --text-secondary: #94A3B8;
                --sidebar-text: #CBD5E1;
                --border-color: #334155;
                --input-bg: #0F172A;
                --hover-bg: #1E293B;
                --primary-color: #22C55E;
                --primary-soft: rgba(34, 197, 94, 0.14);
                --info-soft: rgba(96, 165, 250, 0.12);
                --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.30);
                --shadow-md: 0 10px 28px rgba(0, 0, 0, 0.30);
                --shadow-lg: 0 18px 38px rgba(0, 0, 0, 0.36);
            }
        }

        [data-theme="dark"] {
            --bg-color: #0B1220;
            --sidebar-bg: #111827;
            --card-bg: #172033;
            --text-color: #E2E8F0;
            --text-secondary: #94A3B8;
            --sidebar-text: #CBD5E1;
            --border-color: #334155;
            --input-bg: #0F172A;
            --hover-bg: #1E293B;
            --primary-color: #22C55E;
            --primary-soft: rgba(34, 197, 94, 0.14);
        }

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: var(--text-color);
        }

        .stApp {
            background: radial-gradient(circle at 0% -10%, var(--info-soft), transparent 36%), var(--bg-color);
        }

        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 2rem;
            max-width: 96rem;
        }

        p, .stMarkdown, .stText { color: var(--text-color) !important; }
        .stCaption { color: var(--text-secondary) !important; }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, var(--sidebar-bg) 0%, color-mix(in srgb, var(--sidebar-bg) 85%, var(--info-soft)) 100%);
            border-right: 1px solid var(--border-color);
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 { color: var(--text-color) !important; }

        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span { color: var(--sidebar-text); }

        div[data-testid="stSidebarNav"] a,
        div[data-testid="stSidebarNav"] span {
            color: var(--sidebar-text) !important;
            font-weight: 600;
            border-radius: var(--radius-sm);
        }

        div[data-testid="stSidebarNav"] a:hover,
        div[data-testid="stSidebarNav"] a:hover span {
            background-color: var(--primary-soft) !important;
            color: var(--primary-color) !important;
        }

        div[data-testid="stSidebarNav"] a[aria-current="page"] {
            background: linear-gradient(90deg, var(--primary-soft), transparent);
            border-left: 3px solid var(--primary-color);
        }

        .stButton button,
        .stDownloadButton button {
            border-radius: var(--radius-sm);
            font-weight: 600;
            border: 1px solid transparent;
            transition: all 0.2s ease;
            box-shadow: var(--shadow-sm);
            min-height: 2.6rem;
        }

        .stButton button[kind="primary"],
        .stDownloadButton button[kind="primary"] {
            background: linear-gradient(135deg, color-mix(in srgb, var(--primary-color) 94%, white), var(--primary-color));
            color: #fff !important;
        }

        .stButton button[kind="primary"]:hover,
        .stDownloadButton button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: var(--shadow-md);
            filter: brightness(1.04);
        }

        .stButton button[kind="secondary"],
        .stDownloadButton button[kind="secondary"] {
            background: var(--card-bg);
            border-color: var(--border-color);
            color: var(--text-color);
        }

        .stButton button[kind="secondary"]:hover,
        .stDownloadButton button[kind="secondary"]:hover {
            background-color: var(--hover-bg);
            border-color: color-mix(in srgb, var(--primary-color) 50%, var(--border-color));
        }

        .stTextInput input,
        .stSelectbox div[data-baseweb="select"] > div,
        .stNumberInput input,
        .stTextArea textarea,
        .stDateInput input {
            background-color: var(--input-bg) !important;
            color: var(--text-color) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: var(--radius-sm);
        }

        .stTextInput input:focus,
        .stNumberInput input:focus,
        .stTextArea textarea:focus,
        .stDateInput input:focus {
            border-color: color-mix(in srgb, var(--primary-color) 65%, var(--border-color)) !important;
            box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color) 16%, transparent) !important;
        }

        .stTextInput label,
        .stSelectbox label,
        .stNumberInput label,
        .stTextArea label,
        .stDateInput label {
            color: var(--text-secondary) !important;
            font-weight: 600;
        }

        [data-testid="stDataFrame"],
        [data-testid="stDataEditor"] {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            overflow: hidden;
        }

        [data-testid="stDataFrame"] thead th,
        [data-testid="stDataEditor"] thead th {
            background: color-mix(in srgb, var(--hover-bg) 86%, transparent) !important;
            color: var(--text-secondary) !important;
            font-weight: 700;
            border-bottom: 1px solid var(--border-color) !important;
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            background: var(--card-bg);
            box-shadow: var(--shadow-sm);
            overflow: hidden;
        }

        div[data-testid="stToast"] {
            background: var(--card-bg);
            color: var(--text-color);
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-md);
        }

        h1, h2, h3, h4, h5, h6 {
            color: var(--text-color) !important;
            font-weight: 800;
            letter-spacing: -0.02em;
        }

        .stMarkdown hr { border-top: 1px solid var(--border-color); }

        [data-testid="stMetric"] {
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 10px 12px;
            background: var(--card-bg);
            box-shadow: var(--shadow-sm);
        }

        [data-testid="stMetricLabel"] {
            color: var(--text-secondary) !important;
            font-weight: 600;
        }

        [data-testid="stMetricValue"] {
            color: var(--text-color) !important;
            font-weight: 800;
        }

        .ui-card {
            background: linear-gradient(180deg, var(--card-bg), color-mix(in srgb, var(--card-bg) 80%, var(--hover-bg)));
            padding: 18px;
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-color);
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
            overflow: hidden;
        }

        .ui-card::after {
            content: "";
            position: absolute;
            top: 0;
            right: 0;
            width: 90px;
            height: 90px;
            background: radial-gradient(circle at top right, var(--primary-soft), transparent 72%);
            pointer-events: none;
        }

        .ui-card:hover {
            transform: translateY(-3px);
            box-shadow: var(--shadow-md);
            border-color: color-mix(in srgb, var(--primary-color) 28%, var(--border-color));
        }

        .card-title {
            color: var(--text-secondary);
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-top: 8px;
            margin-bottom: 6px;
        }

        .card-value {
            color: var(--text-color);
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            letter-spacing: -0.02em;
        }

        .card-icon svg {
            width: 34px;
            height: 34px;
            opacity: 0.95;
        }
    </style>
    """, unsafe_allow_html=True)


def card_kpi(col, titulo, valor, icone="📊", cor_borda="transparent", subtexto=""):
    """Renderiza um card de KPI profissional. Suporta Emoji ou SVG."""
    if cor_borda in ["#ddd", "#E0E0E0", "transparent", "white"]:
        cor_borda = "#64748B"

    icon_html = icone
    if not str(icone).strip().startswith("<svg"):
        icon_html = f'<span style="font-size: 1.8rem;">{icone}</span>'

    html = f"""
    <div class="ui-card" style="border-left: 4px solid {cor_borda};">
        <div>
            <div class="card-icon">{icon_html}</div>
            <div class="card-title">{titulo}</div>
            <div class="card-value">{valor}</div>
            <div style="font-size: 0.85em; color: var(--text-secondary); margin-top: 6px; font-weight: 500;">{subtexto}</div>
        </div>
    </div>
    """
    col.markdown(html, unsafe_allow_html=True)
