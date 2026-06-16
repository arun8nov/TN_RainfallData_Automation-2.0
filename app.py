import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import os
import requests
import streamlit.components.v1 as components
import pydeck as pdk
import numpy as np
import io
from fpdf import FPDF
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from main import run_daily_sync

# Set up page configurations
st.set_page_config(page_title="Rainfall Data Dashboard", layout="wide", page_icon="☔")

@st.cache_data(ttl=3600)  # Cache forecast for 1 hour
def fetch_weather_forecast(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max&timezone=Asia%2FKolkata"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        pass
    return None

def get_weather_desc(code):
    mapping = {
        0: ("Clear sky", "☀️"),
        1: ("Mainly clear", "🌤️"),
        2: ("Partly cloudy", "⛅"),
        3: ("Overcast", "☁️"),
        45: ("Fog", "🌫️"),
        48: ("Depositing rime fog", "🌫️"),
        51: ("Light drizzle", "🌦️"),
        53: ("Moderate drizzle", "🌦️"),
        55: ("Dense drizzle", "🌦️"),
        56: ("Light freezing drizzle", "❄️"),
        57: ("Dense freezing drizzle", "❄️"),
        61: ("Slight rain", "🌧️"),
        63: ("Moderate rain", "🌧️"),
        65: ("Heavy rain", "🌧️"),
        66: ("Light freezing rain", "❄️"),
        67: ("Heavy freezing rain", "❄️"),
        71: ("Slight snow fall", "🌨️"),
        73: ("Moderate snow fall", "🌨️"),
        75: ("Heavy snow fall", "🌨️"),
        77: ("Snow grains", "🌨️"),
        80: ("Slight rain showers", "🌦️"),
        81: ("Moderate rain showers", "🌦️"),
        82: ("Violent rain showers", "🌧️"),
        85: ("Slight snow showers", "🌨️"),
        86: ("Heavy snow showers", "🌨️"),
        95: ("Thunderstorm", "⚡"),
        96: ("Thunderstorm with slight hail", "⚡"),
        99: ("Thunderstorm with heavy hail", "⚡"),
    }
    return mapping.get(code, ("Unknown", "🌡️"))

class PDFReport(FPDF):
    def header(self):
        # Custom elegant header background
        self.set_fill_color(15, 23, 42)  # Slate-900 style
        self.rect(0, 0, 210, 35, 'F')
        
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 12, 'TAMIL NADU RAINFALL OBSERVATION REPORT', border=0, ln=1, align='C')
        self.set_font('Helvetica', 'I', 9)
        self.cell(0, 4, 'Automated Rainfall Telemetry & Historical Analytics Dashboard Output', border=0, ln=1, align='C')
        self.ln(12)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | Generated on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', border=0, ln=0, align='C')

def generate_pdf_report(filtered_df, selected_districts, start_date, end_date, fig_trend=None):
    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(15, 23, 42)
    
    # Report configuration
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Report Configuration Parameters', ln=1)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f'Date Range: {start_date} to {end_date}', ln=1)
    
    districts_str = ", ".join(selected_districts) if len(selected_districts) <= 6 else f"{len(selected_districts)} districts selected"
    pdf.cell(0, 6, f'Selected Districts: {districts_str}', ln=1)
    pdf.ln(5)
    
    if not filtered_df.empty:
        total_rainfall = filtered_df['value'].sum()
        rainy_days = filtered_df['date'].nunique()
        avg_daily_rain = total_rainfall / rainy_days if rainy_days > 0 else 0
        dist_grouped = filtered_df.groupby('dist')['value'].sum()
        top_district = dist_grouped.idxmax() if not dist_grouped.empty else "None"
        top_dist_val = dist_grouped.max() if not dist_grouped.empty else 0.0
        
        # KPI summary
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Key Observation Metrics Summary', ln=1)
        pdf.set_font('Helvetica', '', 10)
        
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(95, 7, ' Metric Parameter', 1, 0, 'L', True)
        pdf.cell(95, 7, ' Measured Observation', 1, 1, 'L', True)
        
        pdf.cell(95, 7, ' Cumulative Swept Precipitation', 1, 0, 'L')
        pdf.cell(95, 7, f' {total_rainfall:,.1f} mm', 1, 1, 'L')
        
        pdf.cell(95, 7, ' Average Daily Intensity', 1, 0, 'L')
        pdf.cell(95, 7, f' {avg_daily_rain:.2f} mm', 1, 1, 'L')
        
        pdf.cell(95, 7, ' Total Observation Range', 1, 0, 'L')
        pdf.cell(95, 7, f' {rainy_days:,} days', 1, 1, 'L')
        
        pdf.cell(95, 7, ' Peak District Accumulation', 1, 0, 'L')
        pdf.cell(95, 7, f' {top_district} ({top_dist_val:,.1f} mm)', 1, 1, 'L')
        
        pdf.ln(5)
        
        # District breakdowns
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'District Accumulation Standings', ln=1)
        
        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(95, 7, ' District Name', 1, 0, 'L', True)
        pdf.cell(95, 7, ' Cumulative Rainfall (mm)', 1, 1, 'R', True)
        
        pdf.set_text_color(15, 23, 42)
        pdf.set_font('Helvetica', '', 10)
        
        sorted_dist = dist_grouped.reset_index().sort_values(by='value', ascending=False)
        for index, row in sorted_dist.head(22).iterrows():
            pdf.cell(95, 6, f" {row['dist']}", 1, 0, 'L')
            pdf.cell(95, 6, f" {row['value']:,.1f} mm ", 1, 1, 'R')
            
        if len(sorted_dist) > 22:
            pdf.ln(2)
            pdf.set_font('Helvetica', 'I', 9)
            pdf.cell(0, 6, f'... and {len(sorted_dist) - 22} other districts detailed in the active dashboard filters.', ln=1, align='L')
            
        # Draw dynamic Plotly trends on a new page if provided
        if fig_trend is not None:
            try:
                pdf.add_page()
                pdf.set_font('Helvetica', 'B', 12)
                pdf.cell(0, 10, 'Visual Climatological Daily Trends', ln=1)
                pdf.ln(2)
                
                # Convert Plotly graph to PNG bytes via Kaleido engine
                img_bytes = fig_trend.to_image(format="png", width=700, height=350)
                pdf.image(io.BytesIO(img_bytes), x=10, y=pdf.get_y(), w=190)
            except Exception as e_img:
                pdf.ln(5)
                pdf.set_font('Helvetica', 'I', 9)
                pdf.cell(0, 6, f'Warning: Could not render graphical chart in PDF: {str(e_img)}', ln=1)
    else:
        pdf.cell(0, 10, 'No active observations compiled for selected criteria.', ln=1)
        
    return pdf.output()

# Initialize session states
if "syncing" not in st.session_state:
    st.session_state.syncing = False
if "sync_message" not in st.session_state:
    st.session_state.sync_message = None
if "sync_status" not in st.session_state:
    st.session_state.sync_status = None

# Custom styling injection
st.markdown("""
<style>
    /* CSS Variables & Theme Setup */
    :root {
        --bg-glass: rgba(15, 23, 42, 0.55);
        --bg-glass-hover: rgba(30, 41, 59, 0.7);
        --border-glass: rgba(99, 102, 241, 0.15);
        --border-glass-hover: rgba(6, 182, 212, 0.45);
        --glow-color: rgba(99, 102, 241, 0.2);
    }

    /* Import modern Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
    
    /* Global layout style */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .stApp {
        background: radial-gradient(circle at 50% 50%, #0d0b27 0%, #030307 100%) !important;
        color: #f8fafc !important;
    }
    
    /* Clean custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: rgba(15, 23, 42, 0.2);
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(99, 102, 241, 0.3);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(6, 182, 212, 0.5);
    }
    
    /* Main container padding */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 95%;
    }
    
    /* Falling Rain Header Container */
    .rain-header {
        position: relative;
        background: linear-gradient(135deg, #09090b 0%, #111035 50%, #030712 100%);
        border: 1px solid var(--border-glass);
        padding: 30px;
        border-radius: 24px;
        margin-bottom: 30px;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), inset 0 0 20px rgba(99, 102, 241, 0.1);
        overflow: hidden;
    }

    .rain-header-content {
        position: relative;
        z-index: 2;
    }

    .rain-header-title {
        background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 38px;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.03em;
        text-shadow: 0 0 40px rgba(99, 102, 241, 0.3);
    }

    .rain-header-subtitle {
        color: #94a3b8;
        font-size: 15px;
        margin-top: 8px;
        margin-bottom: 0;
        font-weight: 400;
    }

    .rain-header-bg {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 1;
        pointer-events: none;
    }

    .header-raindrop {
        position: absolute;
        background: linear-gradient(transparent, rgba(56, 189, 248, 0.45));
        width: 1px;
        height: 40px;
        opacity: 0.6;
        animation: dropFall linear infinite;
    }

    @keyframes dropFall {
        0% { transform: translateY(-40px); }
        100% { transform: translateY(160px); }
    }

    /* Glassmorphic KPI Cards Grid */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }

    .kpi-card {
        background: var(--bg-glass);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--border-glass);
        border-radius: 20px;
        padding: 24px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        animation: slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    }

    .kpi-card:hover {
        transform: translateY(-5px);
        border-color: var(--border-glass-hover);
        box-shadow: 0 0 20px rgba(6, 182, 212, 0.4), 0 0 45px rgba(99, 102, 241, 0.25), 0 16px 48px rgba(6, 182, 212, 0.15);
    }

    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 3px;
        background: linear-gradient(90deg, #6366f1, #06b6d4, #a855f7);
        opacity: 0.8;
    }

    .kpi-title {
        font-size: 13px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
        margin-bottom: 6px;
    }

    .kpi-value {
        font-size: 28px;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.02em;
        margin-bottom: 4px;
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.1);
    }

    .kpi-desc {
        font-size: 12px;
        color: #64748b;
    }

    .kpi-icon-container {
        position: absolute;
        right: 20px;
        bottom: 20px;
        opacity: 0.85;
    }

    /* Animations for SVG Vectors */
    @keyframes rainDrop {
        0% { stroke-dashoffset: 0; }
        100% { stroke-dashoffset: -8; }
    }
    .rain-line {
        animation: rainDrop 0.8s linear infinite;
    }
    .rain-line-2 {
        animation-delay: 0.25s;
    }
    .rain-line-3 {
        animation-delay: 0.5s;
    }

    @keyframes dropFallSingle {
        0% { transform: translateY(0); opacity: 0; }
        50% { opacity: 1; }
        100% { transform: translateY(8px); opacity: 0; }
    }
    .single-drop {
        animation: dropFallSingle 1.2s ease-in infinite;
    }

    @keyframes floatIcon {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-4px); }
    }
    .kpi-svg {
        animation: floatIcon 3.5s ease-in-out infinite;
    }

    @keyframes trophyPulse {
        0%, 100% { transform: scale(1); filter: drop-shadow(0 0 0px rgba(251, 191, 36, 0)); }
        50% { transform: scale(1.05); filter: drop-shadow(0 0 8px rgba(251, 191, 36, 0.6)); }
    }
    .trophy-svg {
        animation: trophyPulse 2s ease-in-out infinite;
    }

    @keyframes slideUp {
        from { opacity: 0; transform: translateY(24px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Audio Player Widget */
    .audio-card {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 16px;
        padding: 14px 18px;
        margin-bottom: 25px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }

    /* Sync Radar Loading Indicator */
    .radar-box {
        text-align: center;
        padding: 20px;
        background: rgba(6, 182, 212, 0.05);
        border: 1px solid rgba(6, 182, 212, 0.2);
        border-radius: 18px;
        margin: 20px 0;
    }
    .radar-circle {
        position: relative;
        width: 60px;
        height: 60px;
        border: 2px solid rgba(6, 182, 212, 0.3);
        border-radius: 50%;
        margin: 0 auto 12px auto;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .radar-pulse {
        position: absolute;
        width: 100%;
        height: 100%;
        border: 2px solid #06b6d4;
        border-radius: 50%;
        animation: radarGrow 1.5s linear infinite;
        box-sizing: border-box;
    }
    .radar-pulse-delay {
        animation-delay: 0.75s;
    }
    @keyframes radarGrow {
        0% { transform: scale(1); opacity: 1; }
        100% { transform: scale(2.2); opacity: 0; }
    }
    
    /* Section headers styling */
    .section-header {
        font-size: 22px;
        font-weight: 700;
        color: #f1f5f9;
        margin-top: 36px;
        margin-bottom: 18px;
        padding-left: 12px;
        border-left: 4px solid #06b6d4;
        letter-spacing: -0.01em;
        text-shadow: 0 0 20px rgba(6, 182, 212, 0.2);
    }
    
    /* Tab formatting overrides */
    div[data-testid="stTabs"] button {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        color: #94a3b8 !important;
        padding: 10px 20px !important;
        transition: all 0.3s ease !important;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: #06b6d4 !important;
        border-bottom-color: #06b6d4 !important;
        text-shadow: 0 0 10px rgba(6, 182, 212, 0.3);
    }
    
    /* Background falling rain particles */
    .rain-bg {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: -999;
        pointer-events: none;
        overflow: hidden;
        opacity: 0.08;
    }
    .rain-drop-bg {
        position: absolute;
        background: linear-gradient(transparent, rgba(56, 189, 248, 0.45));
        width: 1px;
        height: 80px;
        animation: rainFallBg linear infinite;
    }
    @keyframes rainFallBg {
        0% { transform: translateY(-100px); }
        100% { transform: translateY(110vh); }
    }
</style>
""", unsafe_allow_html=True)

# Render background rain particles
background_rain_html = "".join([
    f'<div class="rain-drop-bg" style="left: {i*2.5}%; animation-delay: {i*0.19:.2f}s; animation-duration: {1.0 + (i % 7)*0.2:.2f}s;"></div>'
    for i in range(40)
])
st.markdown(f'<div class="rain-bg">{background_rain_html}</div>', unsafe_allow_html=True)

# Cache data loading functions
@st.cache_data
def load_data():
    df = pd.read_csv("tnRainfallData.csv", index_col=0)
    df['date'] = pd.to_datetime(df['date'])
    return df

@st.cache_data
def load_stations():
    return pd.read_csv("raingauge_stations.csv")

# Load datasets
df = load_data()
df_stations = load_stations()
unique_districts = sorted(df['dist'].dropna().unique())

# Sidebar Filters
def sidebar():
    st.sidebar.header("⚙️ Controls & Sync")
    
    # Premium Audio loop integration
    st.sidebar.markdown("""
    <div class="audio-card">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div>
                <h4 style="margin: 0; color: #fff; font-size: 13px;">🎧 Ambient Rainscape</h4>
                <p style="margin: 2px 0 0 0; color: #10b981; font-size: 10px;">Loop soothing rain in background</p>
            </div>
            <audio controls loop style="height: 28px; width: 110px; filter: opacity(0.85) invert(0.9) hue-rotate(185deg);">
                <source src="https://assets.mixkit.co/active_storage/sfx/2522/2522-84.wav" type="audio/wav">
                <source src="https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3" type="audio/mp3">
            </audio>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Scraper sync trigger
    if st.sidebar.button("🔄 Sync Live Rainfall Data", use_container_width=True):
        st.session_state.syncing = True
        st.session_state.sync_status = None
        st.session_state.sync_message = None
        st.rerun()
        
    if st.session_state.sync_status == "success":
        st.sidebar.success(st.session_state.sync_message)
    elif st.session_state.sync_status == "error":
        st.sidebar.error(st.session_state.sync_message)
        
    if st.session_state.syncing:
        st.sidebar.markdown("""
        <div class="radar-box">
            <div class="radar-circle">
                <div class="radar-pulse"></div>
                <div class="radar-pulse radar-pulse-delay"></div>
                <span style="font-size: 20px;">🌧️</span>
            </div>
            <div style="font-size: 13px; font-weight:600; color:#06b6d4;">Scraping TNsmart Websource...</div>
            <div style="font-size: 11px; color:#64748b; margin-top:4px;">Updating tnRainfallData.csv</div>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            # Execute scraper natively
            success, message = run_daily_sync()
            if success:
                st.session_state.sync_status = "success"
                st.session_state.sync_message = message
                st.cache_data.clear()
            else:
                st.session_state.sync_status = "error"
                st.session_state.sync_message = message
        except Exception as e:
            st.session_state.sync_status = "error"
            st.session_state.sync_message = f"Sync failed: {str(e)}"
        finally:
            st.session_state.syncing = False
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🔍 Filters")
    
    select_all = st.sidebar.checkbox("Select All Districts", value=True)
    unique_districts = sorted(df['dist'].dropna().unique())
    
    if select_all:
        selected_dist = st.sidebar.multiselect("Select District(s)", options=unique_districts, default=unique_districts)
    else:
        # Default to Nilgiris & Chennai & Coimbatore
        default_districts = [d for d in ["Chennai", "Coimbatore", "The Nilgiris", "Madurai"] if d in unique_districts]
        if not default_districts:
            default_districts = unique_districts[:3]
        selected_dist = st.sidebar.multiselect("Select District(s)", options=unique_districts, default=default_districts)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Date Filters")
    
    if not df.empty:
        min_date = df['date'].min().to_pydatetime()
        max_date = df['date'].max().to_pydatetime()
    else:
        min_date = datetime.date.today() - datetime.timedelta(days=365)
        max_date = datetime.date.today()
        
    # Default to last 3 years of records to optimize initial load speed
    default_start = max(min_date, max_date - datetime.timedelta(days=3*365))
    
    date_input_range = st.sidebar.date_input(
        "Select Date Range", 
        [default_start, max_date],
        min_value=min_date,
        max_value=max_date
    )
    return selected_dist, date_input_range

selected_dist, date_range = sidebar()

# Handle Streamlit's date range returns safely
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = date_range[0] if isinstance(date_range, tuple) else date_range
    end_date = start_date

# Apply filtering
filtered_df = df[
    (df['dist'].isin(selected_dist)) &
    (df['date'] >= pd.to_datetime(start_date)) &
    (df['date'] <= pd.to_datetime(end_date))
]

# Pre-calculate daily trend chart for dashboard and PDF report
fig_time = None
if not filtered_df.empty:
    daily_trend = filtered_df.groupby('date')['value'].mean().reset_index()
    fig_time = px.line(
        daily_trend,
        x="date",
        y="value",
        labels={"date": "Date", "value": "Average Rain (mm)"},
        template="plotly_dark"
    )
    fig_time.update_traces(line=dict(color="#06b6d4", width=2))
    fig_time.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
        height=350,
        margin=dict(l=20, r=20, t=10, b=20),
        font=dict(family="Plus Jakarta Sans")
    )

# PDF Report Generator Sidebar Control
st.sidebar.markdown("---")
st.sidebar.subheader("📄 Report Export")
try:
    pdf_data = generate_pdf_report(filtered_df, selected_dist, start_date, end_date, fig_trend=fig_time)
    st.sidebar.download_button(
        label="📥 Download Weather Report (PDF)",
        data=bytes(pdf_data),
        file_name=f"TN_Rainfall_Report_{start_date}_to_{end_date}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
except Exception as e_pdf:
    st.sidebar.error(f"Failed to compile PDF: {str(e_pdf)}")

# Animated Raindrops Header Generation
raindrops_html = "".join([
    f'<div class="header-raindrop" style="left: {i*7}%; animation-delay: {i*0.13:.2f}s; animation-duration: {0.7 + (i % 3)*0.15:.2f}s;"></div>'
    for i in range(15)
])

st.markdown(f"""
<div class="rain-header">
    <div class="rain-header-bg">
        {raindrops_html}
    </div>
    <div class="rain-header-content">
        <h1 class="rain-header-title">☔ Tamil Nadu Rainfall Analytics</h1>
        <p class="rain-header-subtitle">Premium interactive climate dashboard with weather scrapers, live station mapping, and historical playback.</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Layout Setup using tabs
tab_metrics, tab_timeline, tab_map, tab_radar, tab_forecast, tab_compare, tab_monsoon, tab_anomaly = st.tabs([
    "📊 Live Analytics & KPI Metrics",
    "⏳ Historical Year-over-Year Playback",
    "📍 Rain Gauge Station Coordinates Map",
    "🛰️ Live Weather Radar (Windy)",
    "🔮 7-Day District Forecast",
    "⚔️ Comparative Analysis",
    "🌦️ Monsoon Seasons Tracker",
    "⛈️ Climate Anomalies & Drought"
])

with tab_metrics:
    # KPI Grid Section
    if not filtered_df.empty:
        total_rainfall = filtered_df['value'].sum()
        rainy_days = filtered_df['date'].nunique()
        avg_daily_rain = total_rainfall / rainy_days if rainy_days > 0 else 0
        top_district = filtered_df.groupby('dist')['value'].sum().idxmax()
        top_dist_val = filtered_df.groupby('dist')['value'].sum().max()

        # HTML KPI Grid with custom Animated SVGs
        st.markdown(f"""
        <div class="kpi-grid">
            <div class="kpi-card" style="animation-delay: 0.05s;">
                <div class="kpi-title">Total Rainfall</div>
                <div class="kpi-value">{total_rainfall:,.1f} mm</div>
                <div class="kpi-desc">Cumulative observation</div>
                <div class="kpi-icon-container">
                    <svg class="kpi-svg" viewBox="0 0 24 24" width="44" height="44" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M20 17.58A5 5 0 0 0 18 8h-1.26A8 8 0 1 0 4 16.25" stroke="#38bdf8"/>
                        <line class="rain-line" x1="8" y1="19" x2="8" y2="21" stroke="#38bdf8" stroke-dasharray="2 2"/>
                        <line class="rain-line rain-line-2" x1="12" y1="20" x2="12" y2="22" stroke="#38bdf8" stroke-dasharray="2 2"/>
                        <line class="rain-line rain-line-3" x1="16" y1="19" x2="16" y2="21" stroke="#38bdf8" stroke-dasharray="2 2"/>
                    </svg>
                </div>
            </div>
            <div class="kpi-card" style="animation-delay: 0.1s;">
                <div class="kpi-title">Avg. Daily Rain</div>
                <div class="kpi-value">{avg_daily_rain:.2f} mm</div>
                <div class="kpi-desc">Mean daily intensity</div>
                <div class="kpi-icon-container">
                    <svg class="kpi-svg" viewBox="0 0 24 24" width="44" height="44" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M20 17.58A5 5 0 0 0 18 8h-1.26A8 8 0 1 0 4 16.25" stroke="#22d3ee"/>
                        <path class="single-drop" d="M12 16v3" stroke="#22d3ee" stroke-width="3"/>
                    </svg>
                </div>
            </div>
            <div class="kpi-card" style="animation-delay: 0.15s;">
                <div class="kpi-title">Observed Days</div>
                <div class="kpi-value">{rainy_days:,}</div>
                <div class="kpi-desc">Total observation range</div>
                <div class="kpi-icon-container">
                    <svg class="kpi-svg" viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="#a78bfa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                        <line x1="16" y1="2" x2="16" y2="6"/>
                        <line x1="8" y1="2" x2="8" y2="6"/>
                        <line x1="3" y1="10" x2="21" y2="10"/>
                        <path d="M9 16l2 2 4-4" stroke="#c084fc"/>
                    </svg>
                </div>
            </div>
            <div class="kpi-card" style="animation-delay: 0.2s;">
                <div class="kpi-title">Top District</div>
                <div class="kpi-value" style="font-size: 20px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px;">{top_district}</div>
                <div class="kpi-desc">Max accumulation: {top_dist_val:,.0f}mm</div>
                <div class="kpi-icon-container">
                    <svg class="kpi-svg trophy-svg" viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="#fbbf24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/>
                        <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/>
                        <path d="M4 22h16"/>
                        <path d="M10 14.66V17c0 .55-.45 1-1 1H4v2h16v-2h-5c-.55 0-1-.45-1-1v-2.34"/>
                        <path d="M12 2a6 6 0 0 1 6 6v5a6 6 0 0 1-6 6 6 6 0 0 1-6-6V8a6 6 0 0 1 6-6z"/>
                    </svg>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("No data available for the selected filters. Please adjust your filters.")

    # Filtered Table
    with st.expander("🔍 View Raw Filtered Data Table", expanded=False):
        st.dataframe(filtered_df, use_container_width=True)

    # Main Visual Grid
    if not filtered_df.empty:
        st.markdown('<div class="section-header">📈 District & Yearly Trends</div>', unsafe_allow_html=True)
        chart1, chart2 = st.columns(2)
        
        with chart1:
            total_by_dist = filtered_df.groupby("dist")["value"].sum().reset_index().sort_values(by="value", ascending=True)
            fig1 = px.bar(
                total_by_dist,
                x="value",
                y="dist",
                orientation="h",
                title="Cumulative Rainfall by District (mm)",
                labels={"value": "Total Rain (mm)", "dist": "District"},
                color="value",
                color_continuous_scale="Purples",
                template="plotly_dark"
            )
            fig1.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(showgrid=False),
                coloraxis_showscale=False,
                height=450,
                font=dict(family="Plus Jakarta Sans"),
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig1, use_container_width=True)

        with chart2:
            daily_rainfall = filtered_df.groupby('date')['value'].sum().reset_index()
            daily_rainfall['year'] = daily_rainfall['date'].dt.year
            yearly_rainfall = daily_rainfall.groupby('year')['value'].sum().reset_index()
            yearly_rainfall['rolling_avg'] = yearly_rainfall['value'].rolling(window=3, min_periods=1).mean()

            fig2 = px.line(
                yearly_rainfall,
                x="year",
                y="rolling_avg",
                title="Overall Annual Rainfall (3-Year Rolling Average)",
                labels={"year": "Year", "rolling_avg": "Rainfall (mm)"},
                template="plotly_dark",
                markers=True
            )
            fig2.update_traces(line=dict(color="#06b6d4", width=3.5), marker=dict(size=8, color="#8b5cf6"))
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                height=450,
                font=dict(family="Plus Jakarta Sans"),
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig2, use_container_width=True)

        # Period Rain Snapshots
        st.markdown('<div class="section-header">📊 Period Rain Snapshots</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        # Max date calculations
        max_dt = filtered_df['date'].max()
        if pd.isnull(max_dt):
            today = datetime.datetime.now()
        else:
            today = max_dt.to_pydatetime()
        
        start_of_year = today.replace(month=1, day=1)
        start_of_month = today.replace(day=1)
        start_of_week = today - datetime.timedelta(days=today.weekday())
        
        def render_snapshot_chart(column_obj, subset_df, title, scale):
            with column_obj:
                st.markdown(f"**{title}**")
                if not subset_df.empty:
                    totals = subset_df.groupby('dist')['value'].sum().reset_index().sort_values(by="value")
                    if len(totals) > 10:
                        totals = totals.tail(10)
                        
                    fig = px.bar(
                        totals,
                        x="value",
                        y="dist",
                        orientation="h",
                        color="value",
                        color_continuous_scale=scale,
                        template="plotly_dark"
                    )
                    fig.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                        yaxis=dict(showgrid=False),
                        coloraxis_showscale=False,
                        height=280,
                        margin=dict(l=10, r=10, t=10, b=10),
                        font=dict(family="Plus Jakarta Sans")
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    st.metric(label="Sum total", value=f"{totals['value'].sum():,.1f} mm")
                else:
                    st.info("No records for this timeframe.")

        year_df = filtered_df[filtered_df['date'] >= pd.to_datetime(start_of_year)]
        render_snapshot_chart(col1, year_df, f"This Year ({today.year})", "Blues")

        month_df = filtered_df[filtered_df['date'] >= pd.to_datetime(start_of_month)]
        render_snapshot_chart(col2, month_df, f"This Month ({today.strftime('%B')})", "Teal")

        week_df = filtered_df[filtered_df['date'] >= pd.to_datetime(start_of_week)]
        render_snapshot_chart(col3, week_df, "This Week (Mon-Sun)", "Purples")

        # Daily rainfall line trend
        st.markdown('<div class="section-header">🌧️ Daily Average Rainfall Over Time</div>', unsafe_allow_html=True)
        if fig_time is not None:
            st.plotly_chart(fig_time, use_container_width=True)

with tab_timeline:
    st.markdown('<div class="section-header">⏳ Historical Year-over-Year Playback</div>', unsafe_allow_html=True)
    st.write("Click the **Play** button at the bottom of the chart to watch cumulative yearly rainfall records evolve across districts since 1990.")
    
    if not filtered_df.empty:
        # Prepare historical animation data
        animation_df = filtered_df.copy()
        animation_df['year'] = animation_df['date'].dt.year
        
        # Rollup by Year and District
        yearly_dist_sums = animation_df.groupby(['year', 'dist'])['value'].sum().reset_index()
        
        # Add all years to prevent layout jumps
        all_years = sorted(yearly_dist_sums['year'].unique())
        all_dists = sorted(yearly_dist_sums['dist'].unique())
        
        # Create full combinations to keep sorting stable during transition
        index = pd.MultiIndex.from_product([all_years, all_dists], names=['year', 'dist'])
        full_df = pd.DataFrame(index=index).reset_index()
        
        # Merge and fill missing values with 0
        yearly_playback_df = pd.merge(full_df, yearly_dist_sums, on=['year', 'dist'], how='left').fillna(0)
        yearly_playback_df = yearly_playback_df.sort_values(by=['year', 'value'], ascending=[True, True])
        
        max_val_limit = yearly_playback_df['value'].max() * 1.1
        
        fig_playback = px.bar(
            yearly_playback_df,
            x="value",
            y="dist",
            color="value",
            orientation="h",
            animation_frame="year",
            animation_group="dist",
            range_x=[0, max_val_limit],
            color_continuous_scale="Viridis",
            labels={"value": "Cumulative Rainfall (mm)", "dist": "District", "year": "Year"},
            template="plotly_dark",
            height=650
        )
        
        fig_playback.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(showgrid=False),
            font=dict(family="Plus Jakarta Sans"),
            margin=dict(l=10, r=10, t=30, b=10)
        )
        
        st.plotly_chart(fig_playback, use_container_width=True)
    else:
        st.info("No data available to animate.")

with tab_map:
    st.markdown('<div class="section-header">📍 Rain Gauge Station Coordinates Map</div>', unsafe_allow_html=True)
    
    # Standardize names and perform left join
    df_stations_clean = df_stations.copy()
    df_stations_clean = df_stations_clean.rename(columns={'Latitude': 'latitude', 'Longitude': 'longitude'})
    df_stations_clean = df_stations_clean.dropna(subset=['latitude', 'longitude'])
    
    # Calculate average rainfall for each station in the filtered data
    if not filtered_df.empty:
        station_avg = filtered_df.groupby('station')['value'].mean().reset_index()
        # Clean names for fuzzy matching key
        df_stations_clean['join_key'] = df_stations_clean['Name of the station'].str.lower().str.replace(r'[^a-z0-9]', '', regex=True)
        station_avg['join_key'] = station_avg['station'].str.lower().str.replace(r'[^a-z0-9]', '', regex=True)
        
        map_data = pd.merge(df_stations_clean, station_avg, on='join_key', how='inner')
    else:
        map_data = pd.DataFrame()
        
    if map_data.empty:
        st.markdown(f"Displaying spatial coordinates for **{len(df_stations_clean):,}** rain gauge stations across Tamil Nadu (Raw Coordinates).")
        st.map(df_stations_clean, color="#6366f1", size=15)
    else:
        map_mode = st.radio(
            "Select Map Style Mode", 
            ["3D Column Deck (Pydeck)", "Precipitation Density Heatmap (Folium)", "Flat Marker Map (Plotly Mapbox)"], 
            horizontal=True, 
            key="map_style_toggle"
        )
        
        if map_mode == "3D Column Deck (Pydeck)":
            st.markdown(f"Displaying average observed rainfall in 3D across **{len(map_data):,}** mapped gauge stations in Tamil Nadu.")
            
            # Setup colors: cyan/blue for low, purple/indigo for moderate, orange/red for heavy
            def calculate_color(val):
                if val == 0:
                    return [71, 85, 105, 120]  # Slate grey
                elif val < 15.6:
                    return [56, 189, 248, 160] # Cyan
                elif val < 64.5:
                    return [99, 102, 241, 180] # Indigo
                elif val < 115.6:
                    return [249, 115, 22, 200] # Orange
                else:
                    return [239, 68, 68, 220]  # Red
            
            map_data['fill_color'] = map_data['value'].apply(calculate_color)
            map_data['formatted_value'] = map_data['value'].apply(lambda x: f"{x:.1f}")
            
            # Dynamic height scale based on max observed rainfall
            max_val = map_data['value'].max() if not map_data['value'].empty else 1.0
            map_data['elevation'] = (map_data['value'] / max_val) * 20000 + 1000  # elevation in meters
            
            column_layer = pdk.Layer(
                "ColumnLayer",
                data=map_data,
                get_position=["longitude", "latitude"],
                get_elevation="elevation",
                elevation_scale=1,
                radius=3200,
                get_fill_color="fill_color",
                pickable=True,
                auto_highlight=True,
                extruded=True,
            )
            
            view_state = pdk.ViewState(
                latitude=11.1271,
                longitude=78.6569,
                zoom=6.3,
                pitch=48,
                bearing=-12
            )
            
            deck_map = pdk.Deck(
                layers=[column_layer],
                initial_view_state=view_state,
                map_style=pdk.map_styles.CARTO_DARK,
                tooltip={
                    "html": "<div style='font-family: \"Plus Jakarta Sans\", sans-serif; font-size: 12px;'>"
                            "<b>Station:</b> {Name of the station}<br/>"
                            "<b>District:</b> {District/Taluk/Revenue Village}<br/>"
                            "<b>Avg Rainfall:</b> {formatted_value} mm"
                            "</div>",
                    "style": {
                        "backgroundColor": "#0f172a",
                        "color": "#f8fafc",
                        "border": "1px solid rgba(99, 102, 241, 0.3)",
                        "borderRadius": "8px",
                        "padding": "10px"
                    }
                }
            )
            st.pydeck_chart(deck_map)
            
        elif map_mode == "Precipitation Density Heatmap (Folium)":
            st.markdown("Displaying continuous rainfall hotspots using Folium HeatMap aggregation overlay.")
            
            # Initialize folium dark-matter map centered in TN
            m = folium.Map(
                location=[11.1271, 78.6569], 
                zoom_start=7, 
                tiles="CartoDB dark_matter",
                control_scale=True
            )
            
            # Pull coordinates and rainfall average values
            heat_df = map_data[['latitude', 'longitude', 'value']].dropna()
            
            # Populate HeatMap structure: list of [lat, lon, weight]
            heat_list = heat_df.values.tolist()
            
            if heat_list:
                HeatMap(
                    data=heat_list, 
                    radius=22, 
                    blur=15, 
                    max_zoom=10, 
                    min_opacity=0.35,
                    gradient={0.4: '#06b6d4', 0.65: '#6366f1', 0.85: '#f97316', 1.0: '#ef4444'}
                ).addTo(m)
            
            # Render using st_folium with constrained reload state objects
            st_folium(m, height=600, width=1200, returned_objects=[])
            
        else:
            st.markdown(f"Displaying average observed rainfall dynamically across **{len(map_data):,}** mapped gauge stations in Tamil Nadu.")
            
            # Interactive Plotly Open-Street-Map
            fig_map = px.scatter_mapbox(
                map_data,
                lat="latitude",
                lon="longitude",
                color="value",
                size="value",
                hover_name="Name of the station",
                hover_data={"latitude": False, "longitude": False, "value": True},
                color_continuous_scale="Turbo",
                size_max=16,
                zoom=6.1,
                center=dict(lat=11.1271, lon=78.6569),
                mapbox_style="open-street-map",
                template="plotly_dark",
                height=600
            )
            
            fig_map.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Plus Jakarta Sans"),
                margin=dict(l=0, r=0, t=10, b=0)
            )
            st.plotly_chart(fig_map, use_container_width=True)

with tab_radar:
    st.markdown('<div class="section-header">🛰️ Live Weather Radar Tracking (Windy)</div>', unsafe_allow_html=True)
    st.markdown("Track real-time storm systems, cloud formations, and wind currents across Tamil Nadu.")
    
    # Windy Interactive IFrame centered around TN coordinates (lat: 11.1271, lon: 78.6569)
    windy_iframe_html = """
    <iframe 
        width="100%" 
        height="650" 
        src="https://embed.windy.com/embed2.html?lat=11.1271&lon=78.6569&zoom=6&level=surface&overlay=rain&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=11.1271&detailLon=78.6569&metricWind=default&metricTemp=default&radarRange=-1" 
        frameborder="0"
        style="border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 16px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);"
    ></iframe>
    """
    components.html(windy_iframe_html, height=670)

with tab_forecast:
    st.markdown('<div class="section-header">🔮 7-Day District Weather & Rain Forecast</div>', unsafe_allow_html=True)
    
    # Determine forecast coordinates
    lat, lon = 11.1271, 78.6569
    primary_dist = "Chennai"
    if selected_dist:
        primary_dist = selected_dist[0]
        matched_stations = df_stations_clean[
            df_stations_clean['District/Taluk/Revenue Village'].str.lower().str.startswith(primary_dist.lower(), na=False)
        ]
        if not matched_stations.empty:
            lat = float(matched_stations['latitude'].mean())
            lon = float(matched_stations['longitude'].mean())
            
    st.markdown(f"Fetching live forecast for **{primary_dist}** (resolved coordinates: `{lat:.4f}°N, {lon:.4f}°E`) from Open-Meteo API...")
    
    forecast_data = fetch_weather_forecast(lat, lon)
    
    if forecast_data and 'daily' in forecast_data:
        daily = forecast_data['daily']
        dates = daily.get('time', [])
        max_temps = daily.get('temperature_2m_max', [])
        min_temps = daily.get('temperature_2m_min', [])
        precip_sums = daily.get('precipitation_sum', [])
        precip_probs = daily.get('precipitation_probability_max', [])
        weather_codes = daily.get('weathercode', [])
        
        # Display 7-day weather cards
        st.markdown("""
        <style>
        .weather-card {
            background: rgba(15, 23, 42, 0.55);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(99, 102, 241, 0.15);
            border-radius: 18px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .weather-card:hover {
            transform: translateY(-5px);
            border-color: rgba(6, 182, 212, 0.45);
            box-shadow: 0 0 20px rgba(6, 182, 212, 0.4), 0 0 45px rgba(99, 102, 241, 0.25), 0 12px 40px rgba(6, 182, 212, 0.15);
        }
        .weather-date {
            font-size: 13px;
            color: #94a3b8;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .weather-emoji {
            font-size: 38px;
            margin: 10px 0;
        }
        .weather-desc {
            font-size: 13px;
            font-weight: 500;
            color: #f8fafc;
            margin-bottom: 12px;
            min-height: 36px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .weather-temp {
            font-size: 16px;
            font-weight: 700;
            color: #ffffff;
        }
        .weather-rain {
            font-size: 12px;
            color: #38bdf8;
            margin-top: 8px;
            font-weight: 500;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Create columns for cards
        card_cols = st.columns(len(dates))
        for i, date_str in enumerate(dates):
            dt_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            day_name = dt_obj.strftime("%a, %b %d")
            desc, emoji = get_weather_desc(weather_codes[i])
            
            with card_cols[i]:
                st.markdown(f"""
                <div class="weather-card">
                    <div class="weather-date">{day_name}</div>
                    <div class="weather-emoji">{emoji}</div>
                    <div class="weather-desc">{desc}</div>
                    <div class="weather-temp">{max_temps[i]:.1f}°C / {min_temps[i]:.1f}°C</div>
                    <div class="weather-rain">🌧️ {precip_sums[i]:.1f} mm ({precip_probs[i]}%)</div>
                </div>
                """, unsafe_allow_html=True)
                
        st.markdown('<div class="section-header">📈 Temperature & Precipitation Trend</div>', unsafe_allow_html=True)
        
        chart_df = pd.DataFrame({
            "Date": [datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") for d in dates],
            "Max Temp (°C)": max_temps,
            "Min Temp (°C)": min_temps,
            "Rainfall (mm)": precip_sums
        })
        
        fig_forecast = px.bar(
            chart_df,
            x="Date",
            y="Rainfall (mm)",
            title="Daily Forecasted Rainfall (bars) & Temperatures (lines)",
            template="plotly_dark"
        )
        fig_forecast.add_scatter(x=chart_df["Date"], y=chart_df["Max Temp (°C)"], name="Max Temp (°C)", yaxis="y2", line=dict(color="#fbbf24", width=3))
        fig_forecast.add_scatter(x=chart_df["Date"], y=chart_df["Min Temp (°C)"], name="Min Temp (°C)", yaxis="y2", line=dict(color="#60a5fa", width=3))
        
        fig_forecast.update_layout(
            yaxis2=dict(title="Temperature (°C)", overlaying="y", side="right"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            font=dict(family="Plus Jakarta Sans")
        )
        st.plotly_chart(fig_forecast, use_container_width=True)
    else:
        st.error("Failed to load forecast data from Open-Meteo. Please check your internet connection.")

    # Time-Series Seasonal Forecasting Section
    st.markdown('<div class="section-header">🔮 12-Month Climatological Trend Forecast</div>', unsafe_allow_html=True)
    st.markdown(f"Generating monthly forecasting projections for **{primary_dist}** based on historical trends since 1990.")
    
    # Filter historical data for primary_dist
    dist_history = df[df['dist'] == primary_dist].copy()
    if not dist_history.empty:
        dist_history['year'] = dist_history['date'].dt.year
        dist_history['month'] = dist_history['date'].dt.month
        
        # Aggregate monthly totals by year
        monthly_totals = dist_history.groupby(['year', 'month'])['value'].sum().reset_index()
        
        # Fit a linear trend for each month separately to capture both seasonality and long-term trend
        future_months = []
        forecast_vals = []
        lower_bounds = []
        upper_bounds = []
        
        # Let's project for the next 12 months starting from next month
        current_year = datetime.datetime.now().year
        current_month = datetime.datetime.now().month
        
        month_names = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
        
        for i in range(1, 13):
            proj_month = (current_month + i - 1) % 12 + 1
            proj_year = current_year + (current_month + i - 1) // 12
            
            # Select historical values for this specific month
            hist_month_data = monthly_totals[monthly_totals['month'] == proj_month]
            
            if len(hist_month_data) > 2:
                # Fit linear regression: Y = A * Year + B
                X = hist_month_data['year'].values
                Y = hist_month_data['value'].values
                
                # Fit trend line coefficients
                coef = np.polyfit(X, Y, 1)
                poly1d_fn = np.poly1d(coef)
                
                # Predict for future year
                pred = float(poly1d_fn(proj_year))
                if pred < 0:
                    pred = 0.0 # rainfall cannot be negative
                
                # Standard deviation of residuals for confidence bounds
                residuals = Y - poly1d_fn(X)
                std_err = np.std(residuals)
                
                # 95% Confidence Interval: margin of error = 1.96 * std_err
                margin = 1.96 * std_err
                
                lower = max(0.0, pred - margin)
                upper = pred + margin
            else:
                # Fallback to simple mean if data is sparse
                pred = float(hist_month_data['value'].mean()) if not hist_month_data.empty else 0.0
                lower = max(0.0, pred - 10)
                upper = pred + 10
                
            future_months.append(f"{month_names[proj_month]} {proj_year}")
            forecast_vals.append(pred)
            lower_bounds.append(lower)
            upper_bounds.append(upper)
            
        # Compile forecast dataframe
        forecast_df = pd.DataFrame({
            "Month": future_months,
            "Forecast (mm)": forecast_vals,
            "Lower Bound (95% CI)": lower_bounds,
            "Upper Bound (95% CI)": upper_bounds
        })
        
        # Render dynamic Plotly line + shaded area chart
        import plotly.graph_objects as go
        fig_fore = go.Figure()
        
        # Add shaded confidence interval area
        fig_fore.add_trace(go.Scatter(
            x=forecast_df["Month"].tolist() + forecast_df["Month"].tolist()[::-1],
            y=forecast_df["Upper Bound (95% CI)"].tolist() + forecast_df["Lower Bound (95% CI)"].tolist()[::-1],
            fill='toself',
            fillcolor='rgba(6, 182, 212, 0.12)',
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo="skip",
            showlegend=True,
            name="95% Confidence Bounds"
        ))
        
        # Add primary forecast line
        fig_fore.add_trace(go.Scatter(
            x=forecast_df["Month"],
            y=forecast_df["Forecast (mm)"],
            mode='lines+markers',
            name="Seasonal Trend Forecast",
            line=dict(color="#06b6d4", width=3),
            marker=dict(size=7, color="#a855f7")
        ))
        
        fig_fore.update_layout(
            title=f"Rainfall Projection & Confidence Limits: {primary_dist} (Next 12 Months)",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Precipitation (mm)"),
            font=dict(family="Plus Jakarta Sans"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_fore, use_container_width=True)
        
        # Forecast Summary Metrics
        st.markdown(f"**Forecasting Highlights for {primary_dist}**:")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            max_idx = np.argmax(forecast_vals)
            st.metric(label="Peak Forecasted Month", value=future_months[max_idx], delta=f"{forecast_vals[max_idx]:.1f} mm")
        with col_f2:
            min_idx = np.argmin(forecast_vals)
            st.metric(label="Driest Forecasted Month", value=future_months[min_idx], delta=f"{forecast_vals[min_idx]:.1f} mm")
        with col_f3:
            total_proj = sum(forecast_vals)
            st.metric(label="Estimated 12-Month Total", value=f"{total_proj:,.1f} mm")
            
    else:
        st.warning("No historical observations available for forecasting in this district.")

with tab_compare:
    st.markdown('<div class="section-header">⚔️ District & Year-over-Year Comparisons</div>', unsafe_allow_html=True)
    
    comp_type = st.radio("Choose Comparison Type", ["Between Two Districts", "Year-over-Year for a District"], horizontal=True)
    
    # Standardize names and perform comparisons
    if comp_type == "Between Two Districts":
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            dist_a = st.selectbox("Select District A", options=unique_districts, index=0)
        with col_c2:
            dist_b = st.selectbox("Select District B", options=unique_districts, index=min(1, len(unique_districts)-1))
        with col_c3:
            all_years = sorted(df['date'].dt.year.unique())
            comp_year = st.selectbox("Select Year to Compare", options=all_years, index=len(all_years)-1)
            
        comp_df = df[df['date'].dt.year == comp_year]
        df_a = comp_df[comp_df['dist'] == dist_a].groupby(comp_df['date'].dt.month)['value'].sum().reset_index()
        df_b = comp_df[comp_df['dist'] == dist_b].groupby(comp_df['date'].dt.month)['value'].sum().reset_index()
        
        month_names = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
        df_a['month_name'] = df_a['date'].map(month_names)
        df_b['month_name'] = df_b['date'].map(month_names)
        
        merged_comp = pd.merge(df_a, df_b, on='date', suffixes=(f'_{dist_a}', f'_{dist_b}'), how='outer').fillna(0)
        merged_comp['month_name'] = merged_comp['date'].map(month_names)
        merged_comp = merged_comp.sort_values(by='date')
        
        fig_comp = px.line(
            merged_comp,
            x='month_name',
            y=[f'value_{dist_a}', f'value_{dist_b}'],
            title=f"Monthly Rainfall Comparison: {dist_a} vs {dist_b} ({comp_year})",
            labels={"value": "Rainfall (mm)", "month_name": "Month", "variable": "District"},
            template="plotly_dark",
            markers=True
        )
        fig_comp.for_each_trace(lambda t: t.update(name=t.name.replace("value_", "")))
        fig_comp.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            font=dict(family="Plus Jakarta Sans")
        )
        st.plotly_chart(fig_comp, use_container_width=True)
        
    else:
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            dist_sel = st.selectbox("Select District", options=unique_districts, index=0, key="yoy_dist")
        with col_c2:
            all_years = sorted(df['date'].dt.year.unique())
            year_a = st.selectbox("Select Year A", options=all_years, index=max(0, len(all_years)-2))
        with col_c3:
            year_b = st.selectbox("Select Year B", options=all_years, index=len(all_years)-1)
            
        df_dist = df[df['dist'] == dist_sel]
        df_y1 = df_dist[df_dist['date'].dt.year == year_a].groupby(df_dist['date'].dt.month)['value'].sum().reset_index()
        df_y2 = df_dist[df_dist['date'].dt.year == year_b].groupby(df_dist['date'].dt.month)['value'].sum().reset_index()
        
        month_names = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
        df_y1['month_name'] = df_y1['date'].map(month_names)
        df_y2['month_name'] = df_y2['date'].map(month_names)
        
        merged_yoy = pd.merge(df_y1, df_y2, on='date', suffixes=(f'_{year_a}', f'_{year_b}'), how='outer').fillna(0)
        merged_yoy['month_name'] = merged_yoy['date'].map(month_names)
        merged_yoy = merged_yoy.sort_values(by='date')
        
        fig_yoy = px.line(
            merged_yoy,
            x='month_name',
            y=[f'value_{year_a}', f'value_{year_b}'],
            title=f"Year-over-Year Monthly Rainfall: {dist_sel} ({year_a} vs {year_b})",
            labels={"value": "Rainfall (mm)", "month_name": "Month", "variable": "Year"},
            template="plotly_dark",
            markers=True
        )
        fig_yoy.for_each_trace(lambda t: t.update(name=t.name.replace("value_", "")))
        fig_yoy.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            font=dict(family="Plus Jakarta Sans")
        )
        st.plotly_chart(fig_yoy, use_container_width=True)

with tab_monsoon:
    st.markdown('<div class="section-header">🌦️ Southwest & Northeast Monsoon Seasons Tracker</div>', unsafe_allow_html=True)
    st.markdown("Track and compare Tamil Nadu's two major annual monsoon seasons: Southwest Monsoon (June–Sept) vs. Northeast Monsoon (Oct–Dec) since 1990.")

    # District Selection for Monsoon Tracking
    monsoon_dist = st.selectbox("Select District for Monsoon Analysis", options=["All Districts"] + unique_districts, index=0)
    
    # Filter dataset for analysis
    if monsoon_dist == "All Districts":
        m_df = df.copy()
    else:
        m_df = df[df['dist'] == monsoon_dist].copy()
    
    if not m_df.empty:
        m_df['year'] = m_df['date'].dt.year
        m_df['month'] = m_df['date'].dt.month
        
        # Segment monsoons
        # Southwest Monsoon: June(6), July(7), Aug(8), Sept(9)
        sw_df = m_df[m_df['month'].isin([6, 7, 8, 9])]
        # Northeast Monsoon: Oct(10), Nov(11), Dec(12)
        ne_df = m_df[m_df['month'].isin([10, 11, 12])]
        
        # Aggregations YoY
        sw_yoy = sw_df.groupby('year')['value'].sum().reset_index().rename(columns={'value': 'Southwest Monsoon (Jun-Sep)'})
        ne_yoy = ne_df.groupby('year')['value'].sum().reset_index().rename(columns={'value': 'Northeast Monsoon (Oct-Dec)'})
        
        # Merge YoY datasets
        monsoon_merged = pd.merge(sw_yoy, ne_yoy, on='year', how='outer').fillna(0).sort_values(by='year')
        
        # Calculate normal (historical average) baselines
        sw_normal = float(sw_yoy['Southwest Monsoon (Jun-Sep)'].mean()) if not sw_yoy.empty else 0.0
        ne_normal = float(ne_yoy['Northeast Monsoon (Oct-Dec)'].mean()) if not ne_yoy.empty else 0.0
        
        # Anomaly highlights for selected year
        available_years = sorted(monsoon_merged['year'].unique())
        if available_years:
            selected_m_year = st.slider("Select Year to Inspect Anomaly", min_value=int(min(available_years)), max_value=int(max(available_years)), value=int(max(available_years)))
            
            # Fetch values for selected year
            year_data = monsoon_merged[monsoon_merged['year'] == selected_m_year]
            if not year_data.empty:
                sw_val = float(year_data['Southwest Monsoon (Jun-Sep)'].values[0])
                ne_val = float(year_data['Northeast Monsoon (Oct-Dec)'].values[0])
                
                # Anomaly percentages
                sw_pct = ((sw_val - sw_normal) / sw_normal * 100) if sw_normal > 0 else 0.0
                ne_pct = ((ne_val - ne_normal) / ne_normal * 100) if ne_normal > 0 else 0.0
                
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    # Southwest metric card
                    status_sw = "🔼 Above Normal" if sw_pct >= 0 else "🔽 Below Normal"
                    color_sw = "#10b981" if sw_pct >= 0 else "#ef4444"
                    st.markdown(f"""
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 20px; border-radius: 16px; border: 1px solid rgba(99, 102, 241, 0.15); text-align: center;">
                        <h4 style="margin: 0; color: #94a3b8; font-size: 13px; text-transform: uppercase;">Southwest Monsoon ({selected_m_year})</h4>
                        <div style="font-size: 28px; font-weight: 700; color: white; margin: 10px 0;">{sw_val:.1f} mm</div>
                        <div style="font-size: 13px; color: {color_sw}; font-weight: 600;">{status_sw} ({sw_pct:+.1f}%)</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Historical baseline normal: {sw_normal:.1f} mm</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_m2:
                    # Northeast metric card
                    status_ne = "🔼 Above Normal" if ne_pct >= 0 else "🔽 Below Normal"
                    color_ne = "#10b981" if ne_pct >= 0 else "#ef4444"
                    st.markdown(f"""
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 20px; border-radius: 16px; border: 1px solid rgba(99, 102, 241, 0.15); text-align: center;">
                        <h4 style="margin: 0; color: #94a3b8; font-size: 13px; text-transform: uppercase;">Northeast Monsoon ({selected_m_year})</h4>
                        <div style="font-size: 28px; font-weight: 700; color: white; margin: 10px 0;">{ne_val:.1f} mm</div>
                        <div style="font-size: 13px; color: {color_ne}; font-weight: 600;">{status_ne} ({ne_pct:+.1f}%)</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Historical baseline normal: {ne_normal:.1f} mm</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        # Visual trend chart
        st.markdown('<div class="section-header">📈 Annual Monsoon Totals YoY Trend</div>', unsafe_allow_html=True)
        fig_monsoon = px.line(
            monsoon_merged,
            x='year',
            y=['Southwest Monsoon (Jun-Sep)', 'Northeast Monsoon (Oct-Dec)'],
            title=f"Monsoon Rainfall Trends (1990 - Present) - {monsoon_dist}",
            labels={"value": "Total Rain (mm)", "year": "Year", "variable": "Monsoon Season"},
            template="plotly_dark",
            markers=True
        )
        # Add normal horizontal lines as references
        fig_monsoon.add_hline(y=sw_normal, line_dash="dash", line_color="#38bdf8", annotation_text="SW Normal Baseline")
        fig_monsoon.add_hline(y=ne_normal, line_dash="dash", line_color="#818cf8", annotation_text="NE Normal Baseline")
        
        fig_monsoon.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            font=dict(family="Plus Jakarta Sans"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_monsoon, use_container_width=True)
    else:
        st.warning("No historical records available for monsoon analysis.")

with tab_anomaly:
    st.markdown('<div class="section-header">⛈️ Standardized Precipitation Climate Anomalies</div>', unsafe_allow_html=True)
    st.markdown("Monitor multi-decade surplus and drought patterns using Standardized Precipitation Anomalies based on historical climate baseline normals.")
    
    # Selection options
    anomaly_dist = st.selectbox("Select District for Anomaly Sweep", options=["All Districts"] + unique_districts, index=0, key="anomaly_dist_select")
    
    # Filter dataset for analysis
    if anomaly_dist == "All Districts":
        a_df = df.copy()
    else:
        a_df = df[df['dist'] == anomaly_dist].copy()
        
    if not a_df.empty:
        a_df['year'] = a_df['date'].dt.year
        
        # Calculate yearly sum totals
        yearly_sums = a_df.groupby('year')['value'].sum().reset_index()
        
        # Compute mean (normal) and standard deviation of yearly precipitation
        mean_rain = float(yearly_sums['value'].mean())
        std_rain = float(yearly_sums['value'].std())
        
        if std_rain > 0:
            # Anomaly index calculation Z = (X - mean) / std
            yearly_sums['anomaly_index'] = (yearly_sums['value'] - mean_rain) / std_rain
            
            # Classification
            def classify_anomaly(z):
                if z >= 1.5:
                    return 'Extremely Wet'
                elif z >= 0.5:
                    return 'Moderately Wet'
                elif z > -0.5:
                    return 'Near Normal'
                elif z > -1.5:
                    return 'Moderate Drought'
                else:
                    return 'Severe Drought'
                    
            yearly_sums['classification'] = yearly_sums['anomaly_index'].apply(classify_anomaly)
            
            # Colors mapping for anomaly bar rendering: Dark Red for severe drought, Orange for moderate drought, Gray for normal, Blue for surplus
            color_map = {
                'Extremely Wet': '#2563eb',   # Deep blue
                'Moderately Wet': '#38bdf8',  # Light blue
                'Near Normal': '#64748b',     # Slate gray
                'Moderate Drought': '#f97316',# Orange
                'Severe Drought': '#ef4444'   # Red
            }
            
            yearly_sums['color'] = yearly_sums['classification'].map(color_map)
            
            # Render interactive anomaly bar chart
            fig_anomaly = px.bar(
                yearly_sums,
                x='year',
                y='anomaly_index',
                color='classification',
                color_discrete_map=color_map,
                title=f"Standardized Climate Anomalies (1990 - Present) - {anomaly_dist}",
                labels={"anomaly_index": "Anomaly Index (Z-Score)", "year": "Year", "classification": "Climate State"},
                template="plotly_dark"
            )
            
            fig_anomaly.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", dtick=2),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Standardized Anomaly (Z-Score)"),
                font=dict(family="Plus Jakarta Sans"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_anomaly, use_container_width=True)
            
            # Historical Stats Summary Cards
            st.markdown('<div class="section-header">📊 Climate Baseline Records</div>', unsafe_allow_html=True)
            col_a1, col_a2, col_a3 = st.columns(3)
            with col_a1:
                st.metric(label="Historical Normal Baseline", value=f"{mean_rain:,.1f} mm")
            with col_a2:
                # Year with maximum surplus
                max_row = yearly_sums.loc[yearly_sums['anomaly_index'].idxmax()]
                st.metric(label="Wettest Year Record", value=str(int(max_row['year'])), delta=f"{max_row['value']:,.1f} mm")
            with col_a3:
                # Year with maximum drought
                min_row = yearly_sums.loc[yearly_sums['anomaly_index'].idxmin()]
                st.metric(label="Driest Year Record", value=str(int(min_row['year'])), delta=f"{min_row['value']:,.1f} mm")
                
            # Class distributions details
            st.markdown("**Historical Anomaly Class Distributions (Number of years)**:")
            class_counts = yearly_sums['classification'].value_counts()
            
            col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns(5)
            for col_obj, c_name in zip([col_c1, col_c2, col_c3, col_c4, col_c5], ['Extremely Wet', 'Moderately Wet', 'Near Normal', 'Moderate Drought', 'Severe Drought']):
                count = int(class_counts.get(c_name, 0))
                c_color = color_map[c_name]
                col_obj.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.5); padding: 12px; border-radius: 12px; border-top: 3px solid {c_color}; text-align: center;">
                    <span style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">{c_name}</span>
                    <div style="font-size: 24px; font-weight: 700; color: white; margin-top: 4px;">{count} yrs</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Insufficient variance in observations to model standardization scales.")
    else:
        st.warning("No historical dataset loaded to process anomalies.")