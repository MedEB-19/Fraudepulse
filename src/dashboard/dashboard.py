import time

import helpers.charts as hc
import pandas as pd
import streamlit as st
from helpers.data_utils import load_data

st.set_page_config(page_title="FraudPulse | Threat Intelligence", page_icon="⬡", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@300;400;500;600&display=swap');

:root {
    --bg-base:       #080C12;
    --bg-panel:      #0D1320;
    --bg-card:       #111827;
    --bg-elevated:   #162032;
    --border:        rgba(56, 189, 248, 0.12);
    --border-glow:   rgba(56, 189, 248, 0.35);
    --accent-cyan:   #38BDF8;
    --accent-cyan2:  #0EA5E9;
    --accent-red:    #F43F5E;
    --accent-amber:  #F59E0B;
    --accent-green:  #10B981;
    --text-primary:  #E2EAF4;
    --text-muted:    #5B7A99;
    --text-dim:      #2D4A66;
    --font-display:  'Syne', sans-serif;
    --font-mono:     'IBM Plex Mono', monospace;
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: var(--bg-base) !important;
    font-family: var(--font-display) !important;
    color: var(--text-primary) !important;
}

p, span, li, div, label { color: var(--text-primary); font-family: var(--font-display) !important; }
h1, h2, h3, h4, h5, h6 { color: var(--text-primary); font-family: var(--font-display) !important; font-weight: 700; }

[data-testid="stSidebar"] {
    background-color: var(--bg-panel) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text-primary) !important; font-family: var(--font-display) !important; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: var(--text-muted) !important; font-size: 0.7rem !important; font-weight: 600 !important;
    text-transform: uppercase !important; letter-spacing: 0.12em !important; font-family: var(--font-mono) !important;
}

[data-baseweb="tag"] {
    background: rgba(56, 189, 248, 0.15) !important; border: 1px solid var(--border-glow) !important;
    color: var(--accent-cyan) !important; font-family: var(--font-mono) !important; font-size: 0.75rem !important;
}
[data-baseweb="tag"] span { color: var(--accent-cyan) !important; }
[data-baseweb="select"] { background: var(--bg-card) !important; border-color: var(--border) !important; }
[data-baseweb="select"] * { color: var(--text-primary) !important; font-family: var(--font-mono) !important; }
[data-baseweb="popover"] { background: var(--bg-elevated) !important; border: 1px solid var(--border-glow) !important; }
[data-baseweb="menu"] * { background: var(--bg-elevated) !important; color: var(--text-primary) !important; }

[data-testid="stMetric"] {
    background: var(--bg-card) !important; border: 1px solid var(--border) !important;
    border-radius: 10px !important; padding: 1.25rem 1.5rem !important; position: relative; overflow: hidden;
}
[data-testid="stMetric"]::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--accent-cyan2), transparent);
}
[data-testid="stMetricLabel"] p {
    color: var(--text-muted) !important; font-family: var(--font-mono) !important; font-size: 0.72rem !important;
    font-weight: 500 !important; text-transform: uppercase !important; letter-spacing: 0.1em !important;
}
[data-testid="stMetricValue"] { color: var(--text-primary) !important; font-weight: 800 !important; }

[data-testid="stTabs"] [role="tablist"] { background: transparent !important; border-bottom: 1px solid var(--border) !important; }
[data-testid="stTabs"] button[role="tab"] {
    background: transparent !important; color: var(--text-muted) !important;
    font-family: var(--font-mono) !important; font-size: 0.78rem !important; font-weight: 500 !important;
    letter-spacing: 0.08em !important; text-transform: uppercase !important;
    padding: 0.75rem 1.25rem !important; border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: var(--accent-cyan) !important; border-bottom-color: var(--accent-cyan) !important;
    background: rgba(56,189,248,0.06) !important;
}

[data-testid="stDataFrame"] {
    background: var(--bg-card) !important; border: 1px solid var(--border) !important; border-radius: 10px !important;
}
[data-testid="stDataFrame"] * { color: var(--text-primary) !important; font-family: var(--font-mono) !important; font-size: 0.8rem !important; }
[data-testid="stDataFrame"] thead th {
    background: var(--bg-elevated) !important; color: var(--accent-cyan) !important;
    font-weight: 600 !important; font-size: 0.72rem !important; text-transform: uppercase !important; letter-spacing: 0.08em !important;
}

[data-testid="stInfo"] {
    background: rgba(56, 189, 248, 0.08) !important; border: 1px solid var(--border-glow) !important;
    border-radius: 8px !important; color: var(--accent-cyan) !important; font-family: var(--font-mono) !important;
}

hr { border-color: var(--border) !important; }
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: var(--border-glow); border-radius: 2px; }

.fp-logo-mark {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, #0EA5E9 0%, #0369A1 100%);
    clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
}
.fp-brand { display: flex; align-items: center; gap: 12px; margin-bottom: 2rem; }
.fp-brand-name { font-family: 'Syne', sans-serif; font-size: 1.15rem; font-weight: 800; color: #E2EAF4; }
.fp-brand-version {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.65rem; color: #38BDF8;
    background: rgba(56,189,248,0.1); border: 1px solid rgba(56,189,248,0.35);
    padding: 2px 7px; border-radius: 4px; letter-spacing: 0.08em;
}
.fp-section-label {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.15em; color: #2D4A66;
    margin: 1.5rem 0 0.5rem 0;
}
.fp-topbar {
    display: flex; justify-content: space-between; align-items: center;
    padding: 1rem 0 1.25rem 0; border-bottom: 1px solid rgba(56,189,248,0.12); margin-bottom: 2rem;
}
.fp-topbar-title { font-family: 'Syne', sans-serif; font-size: 1.35rem; font-weight: 800; color: #E2EAF4; }
.fp-status-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3);
    border-radius: 20px; padding: 4px 12px; font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem; color: #10B981; letter-spacing: 0.06em;
}
.fp-pulse-dot {
    width: 6px; height: 6px; border-radius: 50%; background: #10B981;
    animation: pulse-ring 2s ease-out infinite;
}
@keyframes pulse-ring {
    0%   { box-shadow: 0 0 0 0 rgba(16,185,129,0.5); }
    70%  { box-shadow: 0 0 0 8px rgba(16,185,129,0); }
    100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); }
}
.fp-topbar-right { font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem; color: #2D4A66; }
.fp-risk-panel {
    background: #111827; border: 1px solid rgba(56,189,248,0.12); border-radius: 12px;
    padding: 2rem 2.5rem; position: relative; overflow: hidden;
    display: flex; align-items: center; gap: 3rem; margin-bottom: 1.5rem;
}
.fp-risk-panel::before {
    content: ''; position: absolute; inset: 0; pointer-events: none;
    background-image: linear-gradient(rgba(56,189,248,0.025) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(56,189,248,0.025) 1px, transparent 1px);
    background-size: 36px 36px;
}
.fp-risk-score-label {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.12em; color: #5B7A99; margin-bottom: 0.5rem;
}
.fp-risk-score-value { font-family: 'Syne', sans-serif; font-size: 4.5rem; font-weight: 800; line-height: 1; }
.fp-risk-desc { font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; color: #5B7A99; margin-top: 0.75rem; line-height: 1.5; }
.fp-gauge-wrap { flex: 0 0 280px; }
.fp-alert-card {
    background: #111827; border: 1px solid rgba(56,189,248,0.12); border-left: 3px solid #F43F5E;
    border-radius: 10px; padding: 1.25rem 1.5rem; margin-bottom: 0.75rem;
    display: flex; justify-content: space-between; align-items: center;
}
.fp-alert-id { font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; color: #5B7A99; margin-bottom: 0.35rem; }
.fp-alert-type { font-family: 'Syne', sans-serif; font-size: 1.05rem; font-weight: 700; color: #E2EAF4; margin-bottom: 0.25rem; }
.fp-alert-meta { font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem; color: #5B7A99; }
.fp-alert-amount { font-family: 'Syne', sans-serif; font-size: 1.4rem; font-weight: 800; color: #F43F5E; text-align: right; }
.fp-alert-time { font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; color: #2D4A66; text-align: right; margin-top: 4px; }
.fp-risk-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.05em; }
.fp-risk-high   { background: rgba(244,63,94,0.15); color: #F43F5E; border: 1px solid rgba(244,63,94,0.3); }
.fp-risk-medium { background: rgba(245,158,11,0.15); color: #F59E0B; border: 1px solid rgba(245,158,11,0.3); }
.fp-risk-low    { background: rgba(16,185,129,0.12); color: #10B981; border: 1px solid rgba(16,185,129,0.25); }
</style>
""", unsafe_allow_html=True)

df, total_docs = load_data()
if df is None: st.stop()
if df.empty:
    st.info("// INITIALIZING NETWORK STREAM...")
    time.sleep(5)
    st.rerun()

df['processed_at'] = pd.to_datetime(df['processed_at'])

with st.sidebar:
    st.markdown("""
    <div class="fp-brand">
        <div class="fp-logo-mark"></div>
        <div>
            <div class="fp-brand-name">FraudPulse</div>
            <div class="fp-brand-version">v2.4 PRO</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="fp-section-label">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("", ["OVERVIEW", "ANALYTICS", "EXPLORER", "ALERTS"], index=0, label_visibility="collapsed")
    st.markdown('<div class="fp-section-label">Active Filters</div>', unsafe_allow_html=True)
    f_type = st.multiselect("TRANS. TYPE", options=df['type'].unique(), default=df['type'].unique())
    f_risk = st.multiselect("RISK THRESHOLD", options=['HIGH', 'MEDIUM', 'LOW'], default=['HIGH', 'MEDIUM', 'LOW'])
    st.markdown('<div class="fp-section-label">Pipeline</div>', unsafe_allow_html=True)
    st.markdown(f"""<div style="background: rgba(56,189,248,0.06); border: 1px solid rgba(56,189,248,0.35);
        border-radius: 8px; padding: 0.75rem 1rem; font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem; color: #5B7A99;">
        <span style="color: #38BDF8;">⬡</span> {total_docs:,} events indexed</div>""", unsafe_allow_html=True)

filtered_df = df[(df['type'].isin(f_type)) & (df['risk_level'].isin(f_risk))]

last_sync = df['processed_at'].max().strftime('%H:%M:%S')
st.markdown(f"""
<div class="fp-topbar">
    <div style="display:flex; align-items:center; gap:1.25rem;">
        <div class="fp-topbar-title">{page}</div>
        <div class="fp-status-pill"><div class="fp-pulse-dot"></div>OPERATIONAL</div>
    </div>
    <div class="fp-topbar-right">LAST SYNC &nbsp;{last_sync} UTC</div>
</div>
""", unsafe_allow_html=True)

if page == "OVERVIEW":
    avg_score = filtered_df['fraud_probability'].mean()
    if avg_score < 0.3:
        gauge_color, risk_label, risk_cls = "#10B981", "LOW RISK", "fp-risk-low"
    elif avg_score < 0.7:
        gauge_color, risk_label, risk_cls = "#F59E0B", "MODERATE RISK", "fp-risk-medium"
    else:
        gauge_color, risk_label, risk_cls = "#F43F5E", "HIGH RISK", "fp-risk-high"

    arc = avg_score * 125
    st.markdown(f"""
    <div class="fp-risk-panel">
        <div style="flex:1; min-width:0;">
            <div class="fp-risk-score-label">Global Risk Index</div>
            <div class="fp-risk-score-value" style="color:{gauge_color};">{avg_score:.1%}</div>
            <div style="margin-top:0.75rem;"><span class="fp-risk-badge {risk_cls}">{risk_label}</span></div>
            <div class="fp-risk-desc">Aggregated threat probability across all active network streams and monitored nodes.</div>
        </div>
        <div class="fp-gauge-wrap">
            <svg viewBox="0 0 120 70" width="100%" style="overflow:visible;">
                <defs>
                    <linearGradient id="gGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" style="stop-color:{gauge_color};stop-opacity:0.3"/>
                        <stop offset="100%" style="stop-color:{gauge_color};stop-opacity:1"/>
                    </linearGradient>
                    <filter id="glow"><feGaussianBlur stdDeviation="2.5" result="b"/>
                        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
                </defs>
                <path d="M 12 60 A 42 42 0 0 1 108 60" fill="none" stroke="rgba(56,189,248,0.07)" stroke-width="9" stroke-linecap="round"/>
                <path d="M 12 60 A 42 42 0 0 1 108 60" fill="none" stroke="url(#gGrad)" stroke-width="8"
                    stroke-dasharray="{arc} 200" stroke-linecap="round" filter="url(#glow)"/>
                <text x="60" y="50" text-anchor="middle" font-family="'Syne',sans-serif" font-size="15"
                    font-weight="800" fill="{gauge_color}">{avg_score:.0%}</text>
                <text x="60" y="63" text-anchor="middle" font-family="'IBM Plex Mono',monospace"
                    font-size="5.5" fill="rgba(91,122,153,0.7)" letter-spacing="2">RISK SCORE</text>
            </svg>
        </div>
    </div>
    """, unsafe_allow_html=True)

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Throughput", f"{len(filtered_df):,}")
    fraud_count = len(filtered_df[filtered_df['fraud_flag'] == True])
    kpi2.metric("Identified Threats", f"{fraud_count:,}",
                delta=f"{(fraud_count/max(1,len(filtered_df))):.1%}", delta_color="inverse")
    total_val = filtered_df[filtered_df['fraud_flag'] == True]['amount'].sum()
    kpi3.metric("Capital at Risk", f"${total_val:,.0f}")

    st.markdown('<div class="fp-section-label" style="margin-top:2rem;">Stream Trajectory</div>', unsafe_allow_html=True)
    st.plotly_chart(hc.create_step_volume_chart(filtered_df), use_container_width=True)

elif page == "ANALYTICS":
    st.markdown('<div class="fp-section-label">Behavioral Intelligence</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["// LOSS ANALYSIS", "// ENGINE OVERLAP"])
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="fp-section-label">Threat Density by Type</div>', unsafe_allow_html=True)
            st.plotly_chart(hc.create_type_rate_chart(filtered_df), use_container_width=True)
        with c2:
            st.markdown('<div class="fp-section-label">Average Exposure per Case</div>', unsafe_allow_html=True)
            fig = hc.create_type_amt_chart(filtered_df)
            if fig: st.plotly_chart(fig, use_container_width=True)
            else: st.info("// No data in current view.")
    with tab2:
        c3, c4 = st.columns(2)
        with c3:
            st.markdown('<div class="fp-section-label">Detector Overlap — ML vs Rules</div>', unsafe_allow_html=True)
            fig_ov = hc.create_overlap_chart(filtered_df)
            if fig_ov: st.plotly_chart(fig_ov, use_container_width=True)
        with c4:
            st.markdown('<div class="fp-section-label">Confidence Clusters</div>', unsafe_allow_html=True)
            st.plotly_chart(hc.create_fraud_prob_chart(filtered_df), use_container_width=True)
    st.markdown('<div class="fp-section-label" style="margin-top:1.5rem;">Forensic Origin Mapping</div>', unsafe_allow_html=True)
    st.plotly_chart(hc.create_origin_scatter_chart(filtered_df), use_container_width=True)

elif page == "EXPLORER":
    st.markdown('<div class="fp-section-label">Forensic Transaction Explorer</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-family:\'IBM Plex Mono\',monospace; font-size:0.75rem; color:#5B7A99; margin-bottom:1.5rem;">// Displaying last 100 records — sorted by timestamp descending</p>', unsafe_allow_html=True)
    explorer_df = filtered_df.sort_values('processed_at', ascending=False).head(100).copy()
    def investigator_style(row):
        if row.fraud_flag:
            return ['color: #F43F5E !important; font-weight: 600; background-color: rgba(244,63,94,0.06) !important'] * len(row)
        return ['color: #5B7A99 !important; font-weight: 400'] * len(row)
    st.dataframe(
        explorer_df.style.apply(investigator_style, axis=1).format({"amount": "${:,.2f}", "fraud_probability": "{:.4f}"}),
        use_container_width=True, height=700
    )

elif page == "ALERTS":
    st.markdown('<div class="fp-section-label">Live Threat Feed</div>', unsafe_allow_html=True)
    threats = df[df['fraud_flag'] == True].sort_values('processed_at', ascending=False).head(30).copy()
    if threats.empty:
        st.markdown("""<div style="background:rgba(16,185,129,0.06); border:1px solid rgba(16,185,129,0.2);
            border-radius:10px; padding:2rem; text-align:center; font-family:'IBM Plex Mono',monospace;
            color:#10B981; font-size:0.85rem;">// NO CRITICAL THREATS DETECTED IN CURRENT STREAM BUFFER</div>""",
            unsafe_allow_html=True)
    else:
        for idx, row in threats.iterrows():
            r = row.fraud_probability
            badge = f'<span class="fp-risk-badge fp-risk-{"high" if r>=0.7 else "medium" if r>=0.3 else "low"}">{"HIGH" if r>=0.7 else "MED" if r>=0.3 else "LOW"}</span>'
            st.markdown(f"""
            <div class="fp-alert-card">
                <div>
                    <div class="fp-alert-id">ID: {row.nameOrig}</div>
                    <div class="fp-alert-type">{row.type} <span style="font-size:0.7em;opacity:0.5;">ATTEMPT</span></div>
                    <div class="fp-alert-meta">→ <span style="color:#E2EAF4;">{row.nameDest}</span> &nbsp;{badge}&nbsp;
                        <span style="color:#F43F5E;">{r:.1%}</span></div>
                </div>
                <div>
                    <div class="fp-alert-amount">${row.amount:,.2f}</div>
                    <div class="fp-alert-time">{row.processed_at.strftime('%H:%M:%S')}</div>
                </div>
            </div>""", unsafe_allow_html=True)

time.sleep(10)
st.rerun()
