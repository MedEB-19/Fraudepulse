import plotly.express as px
import plotly.graph_objects as go

DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="'IBM Plex Mono', monospace", size=12, color="#5B7A99"),
    margin=dict(l=0, r=0, t=20, b=0),
    xaxis=dict(
        gridcolor="rgba(56,189,248,0.06)",
        linecolor="rgba(56,189,248,0.12)",
        tickfont=dict(size=11, color="#3D6080", family="'IBM Plex Mono', monospace"),
        title_font=dict(family="'IBM Plex Mono', monospace", size=12, color="#5B7A99"),
        zeroline=False,
    ),
    yaxis=dict(
        gridcolor="rgba(56,189,248,0.06)",
        linecolor="rgba(56,189,248,0.12)",
        tickfont=dict(size=11, color="#3D6080", family="'IBM Plex Mono', monospace"),
        title_font=dict(family="'IBM Plex Mono', monospace", size=12, color="#5B7A99"),
        zeroline=False,
    ),
    hoverlabel=dict(
        bgcolor="#162032",
        bordercolor="rgba(56,189,248,0.35)",
        font=dict(family="'IBM Plex Mono', monospace", size=12, color="#E2EAF4"),
    ),
    legend=dict(
        bgcolor="rgba(13,19,32,0.9)",
        bordercolor="rgba(56,189,248,0.12)",
        borderwidth=1,
        font=dict(family="'IBM Plex Mono', monospace", size=11, color="#5B7A99"),
    ),
    colorway=["#38BDF8", "#0EA5E9", "#0369A1", "#F43F5E", "#F59E0B", "#10B981", "#8B5CF6"],
)

def apply_layout(fig, **extra):
    layout = {**DARK_LAYOUT, **extra}
    fig.update_layout(**layout)
    return fig

def create_step_volume_chart(filtered_df):
    step_grouped = filtered_df.groupby('step').agg(total=('amount', 'count'), fraud=('fraud_flag', 'sum')).reset_index()
    step_grouped = step_grouped.sort_values('step')
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=step_grouped['step'], y=step_grouped['total'], name='Total Volume',
        marker=dict(color='rgba(56,189,248,0.15)', line=dict(width=1, color='rgba(56,189,248,0.3)'))
    ))
    fig.add_trace(go.Scatter(
        x=step_grouped['step'], y=step_grouped['fraud'], name='Fraud Count', yaxis='y2',
        mode='lines+markers',
        line=dict(color='#F43F5E', width=2.5),
        marker=dict(size=6, color='#F43F5E', line=dict(width=2, color='#080C12')),
    ))
    return apply_layout(fig,
        yaxis=dict(title='Total Volume', gridcolor='rgba(56,189,248,0.05)', tickfont=dict(size=11, color='#3D6080', family="'IBM Plex Mono', monospace"), zeroline=False),
        yaxis2=dict(title='Fraud Count', overlaying='y', side='right', gridcolor='rgba(0,0,0,0)', tickfont=dict(size=11, color='#F43F5E', family="'IBM Plex Mono', monospace"), zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor='rgba(0,0,0,0)', borderwidth=0),
        hovermode="x unified",
    )

def create_fraud_prob_chart(filtered_df):
    fig = px.histogram(filtered_df, x="fraud_probability", nbins=50, color_discrete_sequence=['#0EA5E9'])
    fig.update_traces(marker=dict(line=dict(color='rgba(56,189,248,0.4)', width=1)), opacity=0.85)
    return apply_layout(fig)

def create_type_rate_chart(filtered_df):
    type_grouped = filtered_df.groupby('type').agg(txs=('amount', 'count'), frauds=('fraud_flag', 'sum')).reset_index()
    type_grouped['rate'] = type_grouped['frauds'] / type_grouped['txs'] * 100
    fig = px.bar(type_grouped, x='type', y='rate', color='type', text_auto='.2f',
                 color_discrete_sequence=['#38BDF8','#0EA5E9','#0369A1','#F43F5E','#F59E0B'])
    fig.update_traces(marker=dict(line=dict(width=0)), textfont_size=11, textfont_color='#E2EAF4',
                      textfont_family="'IBM Plex Mono', monospace", textposition='outside', opacity=0.9)
    return apply_layout(fig, showlegend=False)

def create_type_amt_chart(filtered_df):
    fraud_only = filtered_df[filtered_df['fraud_flag'] == True]
    if fraud_only.empty: return None
    avg_amt_type = fraud_only.groupby('type')['amount'].mean().reset_index()
    fig = px.bar(avg_amt_type, x='type', y='amount', color_discrete_sequence=['#F43F5E'], text_auto='.2f')
    fig.update_traces(marker=dict(line=dict(width=0), color='rgba(244,63,94,0.7)'),
                      textfont_size=11, textfont_color='#E2EAF4',
                      textfont_family="'IBM Plex Mono', monospace", textposition='outside')
    return apply_layout(fig)

def create_risk_pie_chart(filtered_df):
    risk_counts = filtered_df['risk_level'].value_counts().reset_index()
    risk_counts.columns = ['Risk Level', 'Count']
    fig = px.pie(risk_counts, values='Count', names='Risk Level', hole=0.6, color='Risk Level',
                 color_discrete_map={'HIGH': '#F43F5E', 'MEDIUM': '#F59E0B', 'LOW': '#10B981'})
    fig.update_traces(
        textfont_size=12, textfont_color="#E2EAF4",
        marker=dict(line=dict(color='#080C12', width=3)),
        pull=[0.05 if r == 'HIGH' else 0 for r in risk_counts['Risk Level']],
    )
    return apply_layout(fig, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5,
                                    bgcolor='rgba(0,0,0,0)', borderwidth=0))

def create_overlap_chart(filtered_df):
    overlap = filtered_df[filtered_df['fraud_flag'] == True].copy()
    if overlap.empty: return None
    def categorize(row):
        if row['model_flag'] and row['rule_engine_flag']: return 'Both'
        if row['model_flag']: return 'Model Only'
        return 'Rule Only'
    overlap['Overlap'] = overlap.apply(categorize, axis=1)
    overlap_counts = overlap['Overlap'].value_counts().reset_index()
    overlap_counts.columns = ['Category', 'Count']
    fig = px.bar(overlap_counts, x='Category', y='Count', color='Category',
                 color_discrete_sequence=['#38BDF8', '#F43F5E', '#F59E0B'])
    fig.update_traces(marker=dict(line=dict(width=0)), opacity=0.85)
    return apply_layout(fig, showlegend=False)

def create_origin_scatter_chart(filtered_df):
    fig = px.scatter(
        filtered_df.sample(min(1000, len(filtered_df))),
        x='oldbalanceOrg', y='amount', color='fraud_flag', size_max=10, opacity=0.65,
        color_discrete_map={True: '#F43F5E', False: '#1E3A52'},
    )
    fig.update_traces(marker=dict(line=dict(width=1, color='rgba(8,12,18,0.8)')))
    return apply_layout(fig, legend=dict(title='Is Fraud', bgcolor='rgba(13,19,32,0.9)',
                                   bordercolor='rgba(56,189,248,0.12)', borderwidth=1))
