"""
ui.py — shared visual layer for the portfolio hub.

Gives every page one consistent, modern look: an injected CSS theme, a set of
inline SVG icons (no emoji), and small layout helpers (page header, sidebar
brand, cards, badges). Import it and call ui.setup(...) at the top of a page.
"""
import streamlit as st

# Palette — kept in sync with .streamlit/config.toml
INK, SUB, ACCENT, ACCENT_DK, LINE, BG = "#0f172a", "#64748b", "#0d9488", "#0f766e", "#e2e8f0", "#f8fafc"

# ---- Inline SVG icon set (stroke-based, inherit color via currentColor) ----
_IC = {
    "triage": '<rect x="5" y="4" width="14" height="17" rx="2"/>'
              '<path d="M9.5 4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1z"/>'
              '<path d="M8 14.5h2l1.4-3 2 5 1.3-2H16.5"/>',
    "regulatory": '<path d="M7 3h7l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/>'
                  '<path d="M14 3v4h4"/><path d="M9 12.5h6"/><path d="M9 16h4"/>',
    "safety": '<path d="M12 3l7 3v5c0 4.6-3 8.1-7 10-4-1.9-7-5.4-7-10V6z"/>'
              '<path d="M8.5 12h2l1.2-2.2L13.5 14l1-2h1"/>',
    "brand": '<path d="M12 2.5l8 4.6v9.8L12 21.5l-8-4.6V7.1z"/>'
             '<path d="M8.5 12h2l1.2-2.2L13.5 14l1-2h1"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 7.7h.01"/>',
    "arrow": '<path d="M5 12h13"/><path d="M12.5 6l6 6-6 6"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    "database": '<ellipse cx="12" cy="6" rx="7" ry="3"/>'
                '<path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/>'
                '<path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
    "check": '<path d="M4 12.5l5 5 11-11"/>',
    "scan": '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/><path d="M4 12h16"/>',
}


def icon(name, size=24, color="currentColor", sw=1.75):
    inner = _IC.get(name, "")
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">{inner}</svg>')


# ---- Global stylesheet (NOT an f-string: keep CSS braces literal) ----------
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root{--ink:#0f172a;--sub:#64748b;--acc:#0d9488;--acc-dk:#0f766e;--line:#e2e8f0;--bg:#f8fafc;}
html, body, [class*="css"], .stApp, [data-testid="stMarkdownContainer"]{
  font-family:'Inter',ui-sans-serif,system-ui,-apple-system,sans-serif;}
.stApp{background:var(--bg);}
.block-container{max-width:1060px;padding-top:2.1rem;padding-bottom:4rem;}
#MainMenu, footer, [data-testid="stDecoration"]{display:none !important;}
h1,h2,h3{color:var(--ink);font-weight:700;letter-spacing:-0.01em;}

/* page header */
.pv-head{display:flex;gap:15px;align-items:center;margin:0 0 4px;}
.pv-head .pv-ic{flex:0 0 auto;width:52px;height:52px;border-radius:14px;display:flex;
  align-items:center;justify-content:center;background:linear-gradient(135deg,#0d9488,#0f766e);
  color:#fff;box-shadow:0 6px 16px rgba(13,148,136,.28);}
.pv-head h1{margin:0;font-size:1.7rem;}
.pv-head .sub{margin:3px 0 0;color:var(--sub);font-size:.95rem;line-height:1.35;}
.pv-rule{height:1px;background:var(--line);margin:16px 0 20px;border:0;}

/* hero */
.pv-hero{background:linear-gradient(135deg,#0f172a 0%,#134e4a 58%,#0f766e 100%);color:#fff;
  border-radius:20px;padding:34px 38px;margin:2px 0 22px;}
.pv-hero .eyebrow{text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;color:#5eead4;font-weight:600;}
.pv-hero h1{color:#fff;font-size:2.05rem;margin:.35rem 0 .5rem;line-height:1.14;letter-spacing:-.02em;}
.pv-hero p{color:#cbd5e1;font-size:1.02rem;max-width:62ch;margin:0;line-height:1.5;}

/* cards */
.pv-card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:20px 22px;
  box-shadow:0 1px 2px rgba(15,23,42,.04);height:100%;min-height:208px;
  display:flex;flex-direction:column;transition:transform .15s,box-shadow .15s,border-color .15s;}
.pv-cardlink{text-decoration:none;display:block;height:100%;}
.pv-cardlink:hover .pv-card{transform:translateY(-3px);box-shadow:0 12px 28px rgba(15,23,42,.12);border-color:#5eead4;}
.pv-card .pv-ic{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;
  justify-content:center;background:#ecfdf5;color:var(--acc-dk);margin-bottom:13px;}
.pv-card h3{margin:0 0 5px;font-size:1.06rem;}
.pv-card .job{color:var(--ink);font-size:.9rem;line-height:1.45;}
.pv-card .who{color:var(--sub);font-size:.78rem;margin-top:11px;letter-spacing:.02em;}
.pv-card .go{margin-top:auto;padding-top:14px;color:var(--acc-dk);font-weight:600;font-size:.82rem;
  display:flex;align-items:center;gap:6px;}
.pv-cta{display:flex;align-items:center;gap:14px;background:#ecfdf5;border:1px solid #99f6e4;
  border-radius:14px;padding:15px 20px;margin:20px 0 4px;text-decoration:none;transition:background .15s;}
.pv-cta:hover{background:#d7f6ec;}
.pv-cta .ic{width:38px;height:38px;border-radius:10px;background:#fff;border:1px solid #99f6e4;
  display:flex;align-items:center;justify-content:center;color:var(--acc-dk);flex:0 0 auto;}
.pv-cta .tx{flex:1;line-height:1.35;}
.pv-cta .tx b{color:var(--ink);font-size:.98rem;}
.pv-cta .tx span{color:#475569;font-size:.85rem;display:block;}
.pv-cta .arr{color:var(--acc-dk);display:flex;flex:0 0 auto;}

/* info panel */
.pv-panel{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:8px 0 14px;}
.pv-panel h4{margin:0 0 6px;color:var(--ink);font-size:1rem;}
.pv-panel p{margin:0 0 8px;color:#334155;font-size:.92rem;line-height:1.55;}
.pv-panel .lead{color:var(--acc-dk);font-weight:600;}

/* flow chips */
.pv-flow{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin:12px 0 4px;}
.pv-step{display:flex;align-items:center;gap:8px;background:#fff;border:1px solid var(--line);
  border-radius:10px;padding:9px 13px;font-size:.85rem;color:var(--ink);}
.pv-step .pv-ic{color:var(--acc-dk);display:flex;}
.pv-arr{color:#94a3b8;display:flex;}

/* badges */
.pv-badge{display:inline-flex;align-items:center;gap:6px;padding:5px 14px;border-radius:999px;
  font-weight:600;font-size:.92rem;}
.pv-badge.red{background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;}
.pv-badge.green{background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;}
.pv-badge.gray{background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;}

/* buttons */
.stButton>button, .stDownloadButton>button{border-radius:10px;font-weight:600;}
.stButton>button[kind="primary"], [data-testid="stBaseButton-primary"]{
  background:var(--acc);border:1px solid var(--acc);color:#fff;}
.stButton>button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover{
  background:var(--acc-dk);border-color:var(--acc-dk);}

/* inputs */
.stTextInput input,.stTextArea textarea{border-radius:10px;}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:var(--acc);
  box-shadow:0 0 0 2px rgba(13,148,136,.16);}

/* metrics + expander */
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 16px;}
[data-testid="stExpander"] details{border:1px solid var(--line);border-radius:12px;background:#fff;}
[data-testid="stExpander"] summary{font-weight:600;color:var(--ink);}

/* sidebar */
[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line);}
.pv-brand{display:flex;align-items:center;gap:11px;padding:4px 2px 14px;margin-bottom:8px;
  border-bottom:1px solid var(--line);}
.pv-brand .m{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;
  justify-content:center;background:linear-gradient(135deg,#0d9488,#0f766e);color:#fff;}
.pv-brand .t{font-weight:700;color:var(--ink);font-size:1rem;line-height:1.05;}
.pv-brand .s{color:var(--sub);font-size:.72rem;letter-spacing:.02em;}
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_brand():
    st.sidebar.markdown(
        f'<div class="pv-brand"><div class="m">{icon("brand", 21, "#fff")}</div>'
        f'<div><div class="t">PV Suite</div><div class="s">Drug-safety tools</div></div></div>',
        unsafe_allow_html=True,
    )


def page_header(icon_name, title, subtitle):
    st.markdown(
        f'<div class="pv-head"><div class="pv-ic">{icon(icon_name, 28, "#fff")}</div>'
        f'<div><h1>{title}</h1><div class="sub">{subtitle}</div></div></div>'
        f'<hr class="pv-rule"/>',
        unsafe_allow_html=True,
    )


def setup(page_title, icon_name, title, subtitle, layout="wide"):
    """Standard page opener: config → CSS → sidebar brand → header. Call first."""
    st.set_page_config(page_title=page_title, layout=layout)
    inject_css()
    sidebar_brand()
    page_header(icon_name, title, subtitle)


def newcomer_note(lines, page_hint="See the **Overview** page for a full plain-language guide."):
    """A collapsed, jargon-free 'what am I looking at' helper for the uninitiated."""
    with st.expander("New here?  What am I looking at?"):
        for ln in lines:
            st.markdown(f"- {ln}")
        st.caption(page_hint)
