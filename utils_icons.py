# utils_icons.py
# Coleção de ícones SVG High-Quality (Estilo Lucide/Outline Moderno)

def get_icon(name, color="#2E7D32", size="24px"):
    """
    Retorna o código SVG para um ícone específico com traços modernos.
    Args:
        name (str): Nome do ícone (tractor, dashboard, alert, etc.)
        color (str): Cor do ícone em Hex ou nome CSS.
        size (str): Altura/Largura do ícone (ex: '24px').
    """

    # Configuração base para manter consistência
    # stroke-width="2" é o padrão para ícones modernos (bom equilíbrio)
    base_style = f'xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'

    icons = {
        # 🚜 TRATOR (Refinado)
        # Um design mais claro de máquina agrícola
        "tractor": f"""
            <svg {base_style}>
                <path d="M3 17h18"/>
                <path d="M7 14V8H3v9h4v-3z"/>
                <path d="M11 17h-4V8h4v9z"/>
                <path d="M10 8L14 5L17 6V8"/>
                <circle cx="17" cy="17" r="3"/>
                <circle cx="7" cy="17" r="3"/>
            </svg>
        """,

        # 📋 PAINEL / DASHBOARD (Layout Grid)
        "dashboard": f"""
            <svg {base_style}>
                <rect width="7" height="9" x="3" y="3" rx="1"/>
                <rect width="7" height="5" x="14" y="3" rx="1"/>
                <rect width="7" height="9" x="14" y="12" rx="1"/>
                <rect width="7" height="5" x="3" y="16" rx="1"/>
            </svg>
        """,

        # 🔥 ALERTA / URGENTE (Chama Fluida)
        "fire": f"""
            <svg {base_style}>
                <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.1.2-2.2.5-3.3.3-1.2 1-2.4 1.5-3.2.5 1.5 1.5 3 1.5 4.5z"/>
            </svg>
        """,

        # ⏳ PENDENTE / TEMPO (Relógio Limpo)
        "clock": f"""
            <svg {base_style}>
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
            </svg>
        """,

        # ✅ OK / SISTEMA ONLINE (Check em Círculo)
        "check": f"""
            <svg {base_style}>
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
        """,

        # 📌 MURAL / LOCAL (Pin de Mapa)
        "pin": f"""
            <svg {base_style}>
                <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>
                <circle cx="12" cy="10" r="3"/>
            </svg>
        """,

        # ⚙️ CONFIG / ENGRENAGEM (Geométrico)
        "gear": f"""
            <svg {base_style}>
                <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.47a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.39a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
                <circle cx="12" cy="12" r="3"/>
            </svg>
        """,

        # 🛑 PARADA / ALERT (Octágono com Exclamação)
        "stop": f"""
            <svg {base_style}>
                <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/>
                <line x1="12" x2="12" y1="8" y2="12"/>
                <line x1="12" x2="12.01" y1="16" y2="16"/>
            </svg>
        """
    }

    return icons.get(name, "")