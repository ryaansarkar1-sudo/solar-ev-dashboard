"""
LIVE Sydney solar dashboard for the EV backup-charging panels.

  * Pick any date (calendar, or the < > buttons) from 90 days ago to 6 days ahead
  * Day tab : power, energy and km of range for that day + an animated EV scene
  * Week tab: 7-day energy and range comparison
  * Real Sydney weather + forecast (Open-Meteo), refreshed every 5 minutes

Run it with:   py -m streamlit run live_dashboard.py
"""

import datetime as dt

import numpy as np
import pandas as pd
import pvlib
import requests
import altair as alt
import streamlit as st
import streamlit.components.v1 as components

LAT, LON, ELEV = -33.8688, 151.2093, 58
TZ = "Australia/Sydney"
URL = "https://api.open-meteo.com/v1/forecast"
REFRESH_SECONDS = 300
DAYS_BACK, DAYS_AHEAD = 90, 6

st.set_page_config(page_title="Sydney solar EV dashboard", layout="wide",
                   initial_sidebar_state="auto")

# ----------------------------------------------------------------------------
# Look and feel: Apple Human Interface Guidelines
#   system font (SF Pro on Mac/iOS), grouped background + rounded cards,
#   semantic light/dark colours, 44 px touch targets, reduced-motion support.
#   Text colours are chosen for contrast (all 4.5:1 or better).
# ----------------------------------------------------------------------------
STYLE = """
<style>
:root{
  --bg:#F2F2F7; --card:#FFFFFF; --label:#1C1C1E; --label2:#6C6C70;
  --blue:#0062CC; --fill:rgba(120,120,128,.12); --sep:rgba(60,60,67,.18);
  --font:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display","Helvetica Neue",Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#000000; --card:#1C1C1E; --label:#FFFFFF; --label2:#AEAEB2;
    --blue:#64A8FF; --fill:rgba(120,120,128,.24); --sep:rgba(84,84,88,.65);
  }
}
@media (prefers-contrast: more){
  :root{ --label2:#48484A; --sep:rgba(60,60,67,.5); }
}
@media (prefers-contrast: more) and (prefers-color-scheme: dark){
  :root{ --label2:#E5E5EA; --sep:rgba(235,235,245,.5); }
}
html, body, .stApp, .stApp p, .stApp label, .stApp button, .stApp input,
.stApp h1, .stApp h2, .stApp h3, .stApp li, .stApp td, .stApp th{
  font-family:var(--font) !important;
}
.stApp, [data-testid="stAppViewContainer"]{ background:var(--bg) !important; color:var(--label); }
[data-testid="stHeader"]{ background:transparent !important; }
[data-testid="stDecoration"], footer, #MainMenu{ display:none !important; }
.block-container{ max-width:1180px; padding-top:2.2rem; padding-bottom:3rem; }

/* sidebar = grouped settings list */
[data-testid="stSidebar"]{ background:var(--bg) !important; border-right:1px solid var(--sep); }
[data-testid="stSidebar"] label p{ font-size:15px; color:var(--label); }
.grp{ font-size:13px; font-weight:600; letter-spacing:.04em; text-transform:uppercase;
      color:var(--label2); margin:1.2rem 0 .3rem; }
.sbtitle{ font-size:28px; font-weight:700; letter-spacing:-.02em; margin:0 0 .2rem; color:var(--label); }

/* large title */
.largetitle{ font-size:34px; font-weight:700; letter-spacing:-.022em; line-height:1.12; margin:0; color:var(--label); }
.subtitle{ font-size:17px; color:var(--label2); margin:.25rem 0 1.1rem; }

/* controls: 44 px targets, rounded, tinted */
.stButton > button{
  min-height:44px; border-radius:12px; border:none; background:var(--card); color:var(--blue);
  font-size:17px; font-weight:600; box-shadow:none;
}
.stButton > button:hover{ background:var(--fill); color:var(--blue); }
.stButton > button:active{ transform:scale(.98); }
[data-testid="stDateInput"] input{ min-height:44px; font-size:17px; border-radius:12px; }
[data-testid="stDateInput"] > div > div, [data-baseweb="input"]{ border-radius:12px !important; border:none !important; background:var(--card) !important; }
[data-testid="stSelectbox"] [data-baseweb="select"] > div{ min-height:44px; border-radius:12px; }
button:focus-visible, input:focus-visible, [role="slider"]:focus-visible, [role="tab"]:focus-visible{
  outline:3px solid var(--blue) !important; outline-offset:2px;
}
[data-testid="stSliderThumbValue"], [data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"]{
  color:var(--label2) !important; font-size:13px !important;
}

/* segmented control (Day / Week) */
[data-testid="stButtonGroup"] button{ min-height:40px; font-size:15px; font-weight:600;
  background:var(--fill) !important; color:var(--label) !important; border:none !important; }
[data-testid="stButtonGroup"] button *{ color:inherit !important; }
[data-testid="stButtonGroup"] button[data-selected="true"]{ background:var(--card) !important; color:var(--blue) !important;
  box-shadow:0 1px 3px rgba(0,0,0,.18); }
/* Streamlit's default accent is red: shift sliders to system blue */
[data-testid="stSlider"] div[role="group"]{ filter:hue-rotate(205deg); }
@media (prefers-color-scheme: dark){ [data-testid="stSlider"] div[role="group"]{ filter:hue-rotate(205deg) brightness(1.25); } }
[data-testid="stMarkdownContainer"] p, [data-testid="stWidgetLabel"] p{ color:var(--label); }

/* cards */
[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--card); border:none !important; border-radius:20px; padding:.4rem .6rem .2rem;
}
.sec{ font-size:22px; font-weight:600; letter-spacing:-.01em; margin:.5rem 0 .2rem; color:var(--label); }
iframe{ border-radius:20px; border:none; width:100%; aspect-ratio:800 / 300; height:auto !important; display:block; }
[data-testid="stIFrame"], [data-testid="stCustomComponentV1"]{ height:auto !important; }

/* number tiles */
.tiles{ display:grid; grid-template-columns:1fr; gap:12px; margin-bottom:14px; }
.tile{ background:var(--card); border-radius:18px; padding:18px 22px 16px; }
.tile .k{ font-size:13px; font-weight:500; color:var(--label2); margin-bottom:4px; }
.tile .v{ font-size:34px; font-weight:600; letter-spacing:-.022em; line-height:1.08;
          font-variant-numeric:tabular-nums; color:var(--label); }
.tile .u{ font-size:17px; font-weight:500; color:var(--label2); margin-left:3px; letter-spacing:0; }
.foot{ font-size:13px; color:var(--label2); line-height:1.45; margin-top:1rem; }
.hint{ font-size:13px; color:var(--label2); margin:.1rem 0 0; }

@media (max-width: 760px){
  .largetitle{ font-size:28px; }
  .tile .v{ font-size:28px; }
}
@media (prefers-reduced-motion: reduce){
  *{ transition:none !important; animation:none !important; }
}
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)

CHART_AMBER = "#C96F00"     # solar energy: 3.7:1 on white, 4.7:1 on dark cards
CHART_BLUE = "#0A84FF"      # range gained


def area_chart(df, x, y, color, height):
    c = (alt.Chart(df).mark_area(color=color, opacity=.85, line={"color": color, "strokeWidth": 2},
                                 interpolate="monotone")
         .encode(x=alt.X(f"{x}:Q", title=None, scale=alt.Scale(domain=[0, 23]),
                         axis=alt.Axis(values=list(range(0, 24, 3)), labelExpr="datum.value + ':00'",
                                       labelAngle=0, grid=False, domain=False, ticks=False)),
                 y=alt.Y(f"{y}:Q", title=y, axis=alt.Axis(grid=True, domain=False, ticks=False,
                                                          gridOpacity=.25)),
                 tooltip=[alt.Tooltip(f"{x}:Q", title="Hour"), alt.Tooltip(f"{y}:Q", format=",.0f")])
         .properties(height=height).configure(background="transparent"))
    st.altair_chart(c, width="stretch")


def bar_chart(df, x, y, color, height):
    c = (alt.Chart(df).mark_bar(color=color, cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
         .encode(x=alt.X(f"{x}:N", title=None, sort=None,
                         axis=alt.Axis(labelAngle=0, domain=False, ticks=False)),
                 y=alt.Y(f"{y}:Q", title=y, axis=alt.Axis(grid=True, domain=False, ticks=False,
                                                          gridOpacity=.25)),
                 tooltip=[alt.Tooltip(f"{x}:N", title="Day"), alt.Tooltip(f"{y}:Q", format=",.2f")])
         .properties(height=height).configure(background="transparent"))
    st.altair_chart(c, width="stretch")

# ----------------------------------------------------------------------------
# Weather + solar model
# ----------------------------------------------------------------------------


@st.cache_data(ttl=REFRESH_SECONDS)
def fetch_weather():
    params = {
        "latitude": LAT, "longitude": LON,
        "hourly": "shortwave_radiation,direct_normal_irradiance,diffuse_radiation,"
                  "temperature_2m,wind_speed_10m",
        "wind_speed_unit": "ms",
        "past_days": DAYS_BACK + 2, "forecast_days": DAYS_AHEAD + 1,
        "timezone": "GMT",
    }
    r = requests.get(URL, params=params, timeout=30)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["hourly"])
    df["time"] = pd.to_datetime(df["time"]).dt.tz_localize("UTC")
    return df.set_index("time").interpolate(limit_direction="both").fillna(0)


def compute_power(weather, area_m2, efficiency, tilt, azimuth, losses_pct):
    """Hourly AC power (W) using the same PVWatts model SAM uses."""
    pdc0 = area_m2 * efficiency * 1000                       # watts at 1000 W/m2
    mid = weather.index - pd.Timedelta(minutes=30)           # values = hour ENDING
    loc = pvlib.location.Location(LAT, LON, tz=TZ, altitude=ELEV)
    sol = loc.get_solarposition(mid)
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt, surface_azimuth=azimuth,
        dni=weather["direct_normal_irradiance"].values,
        ghi=weather["shortwave_radiation"].values,
        dhi=weather["diffuse_radiation"].values,
        solar_zenith=sol["apparent_zenith"].values,
        solar_azimuth=sol["azimuth"].values,
    )["poa_global"]
    poa = np.clip(np.nan_to_num(np.asarray(poa, dtype=float)), 0, None)
    temp_params = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_glass"]
    cell_t = pvlib.temperature.sapm_cell(
        poa, weather["temperature_2m"].values, weather["wind_speed_10m"].values,
        **temp_params)
    dc = pvlib.pvsystem.pvwatts_dc(poa, cell_t, pdc0, gamma_pdc=-0.0035)
    ac = dc * (1 - losses_pct / 100) * 0.96                  # 0.96 = inverter efficiency
    return pd.Series(ac, index=weather.index).clip(lower=0)


def day_slice(local_power, d):
    """The 24 hourly values (W) for calendar day d in Sydney time."""
    start = pd.Timestamp(d, tz=TZ)
    end = start + pd.Timedelta(days=1)
    return local_power[(local_power.index > start) & (local_power.index <= end)]


def show_html(html, height):
    if hasattr(st, "iframe"):
        try:
            st.iframe(html, height="content")      # CSS keeps the scene's 800:300 shape
        except Exception:
            st.iframe(html, height=height)
    else:
        components.html(html, height=height)


# ----------------------------------------------------------------------------
# Animated EV scene (a generic electric car - original design, no brand)
# ----------------------------------------------------------------------------

SCENE = """
<style>
  html,body{margin:0;height:100%;overflow:hidden;background:transparent;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Arial,sans-serif}
  svg{width:100%;height:100%;display:block;border-radius:20px}
  .road-dash{stroke-dasharray:46 38;animation:dash .7s linear infinite}
  @keyframes dash{to{stroke-dashoffset:-84}}
  .hills{animation:scroll 14s linear infinite}
  .trees{animation:scroll 5s linear infinite}
  @keyframes scroll{to{transform:translateX(-800px)}}
  .wheel{transform-box:fill-box;transform-origin:center;animation:spin .55s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  .car{animation:bob .6s ease-in-out infinite alternate}
  @keyframes bob{from{transform:translate(250px,126px)}to{transform:translate(250px,124.5px)}}
  .pulse{animation:pulse 1.8s ease-in-out infinite alternate}
  @keyframes pulse{from{opacity:.55}to{opacity:1}}
  .cloud{animation:drift 40s linear infinite}
  @keyframes drift{from{transform:translateX(-200px)}to{transform:translateX(1000px)}}
  text{font-weight:600}
  .pilltxt{fill:#1C1C1E;font-size:17px}
  @media (prefers-reduced-motion: reduce){.road-dash,.hills,.trees,.wheel,.car,.pulse,.cloud{animation:none !important}}
  .stopped .road-dash,.stopped .hills,.stopped .trees,.stopped .wheel,.stopped .car{animation-play-state:paused}
</style>
<svg viewBox="0 0 800 300" role="img" aria-label="Animated electric car driving, powered by the sun">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop id="s1" offset="0" stop-color="#6ec3f4"/><stop id="s2" offset="1" stop-color="#d7f0ff"/>
    </linearGradient>
    <radialGradient id="sunglow"><stop offset="0" stop-color="#fff6b0"/><stop offset="1" stop-color="#ffd54a" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="800" height="300" fill="url(#sky)"/>
  <g id="stars" opacity="0">
    <circle cx="60" cy="40" r="1.5" fill="#fff"/><circle cx="150" cy="80" r="1.2" fill="#fff"/>
    <circle cx="260" cy="30" r="1.6" fill="#fff"/><circle cx="380" cy="70" r="1.2" fill="#fff"/>
    <circle cx="470" cy="28" r="1.5" fill="#fff"/><circle cx="560" cy="90" r="1.3" fill="#fff"/>
    <circle cx="690" cy="45" r="1.6" fill="#fff"/><circle cx="740" cy="100" r="1.2" fill="#fff"/>
    <circle cx="330" cy="110" r="1.1" fill="#fff"/><circle cx="110" cy="120" r="1.2" fill="#fff"/>
  </g>
  <g id="sun" opacity="0">
    <circle r="62" fill="url(#sunglow)"/><circle r="22" fill="#ffd54a"/>
  </g>
  <g id="moon" opacity="0"><circle r="20" fill="#f1f1e6"/><circle cx="9" cy="-4" r="18" fill="#1b2f55" id="moonshade"/></g>
  <g class="cloud" opacity=".85"><ellipse cx="120" cy="70" rx="46" ry="14" fill="#fff"/><ellipse cx="150" cy="60" rx="30" ry="14" fill="#fff"/></g>
  <g class="hills">
    <g id="hillset"></g>
  </g>
  <g class="trees">
    <g id="treeset"></g>
  </g>
  <rect y="192" width="800" height="12" fill="#5e9c5a"/>
  <rect y="204" width="800" height="96" fill="#48484A"/>
  <rect y="204" width="800" height="4" fill="#d9d9d9" opacity=".6"/>
  <line class="road-dash" x1="0" y1="262" x2="800" y2="262" stroke="#f2f2f2" stroke-width="5"/>

  <!-- the car (generic EV) -->
  <g class="car">
    <ellipse cx="160" cy="92" rx="150" ry="7" fill="#000" opacity=".25"/>
    <!-- body -->
    <path d="M12 70 L12 56 Q14 44 36 41 L84 37 Q104 11 150 9 L214 9 Q246 12 262 38 L286 44 Q302 48 302 62 L302 70 Q302 74 296 74 L18 74 Q12 74 12 70Z" fill="#F2F2F7"/>
    <path d="M12 62 L302 62 L302 70 Q302 74 296 74 L18 74 Q12 74 12 70Z" fill="#C7C7CC"/>
    <!-- windows -->
    <path d="M96 37 Q110 18 150 16 L172 16 L172 37Z" fill="#BFD9EE"/>
    <path d="M180 16 L210 16 Q232 20 246 37 L180 37Z" fill="#BFD9EE"/>
    <rect x="173" y="14" width="6" height="25" fill="#C7C7CC"/>
    <!-- lights -->
    <rect x="290" y="48" width="12" height="6" rx="3" fill="#fff8c4"/>
    <rect x="12" y="50" width="9" height="6" rx="3" fill="#ff5a4d"/>
    <!-- roof solar panel -->
    <g id="roofpanel">
      <polygon points="104,12 226,12 244,0 122,0" fill="#1c3a6b" id="panelfill" stroke="#ffffff" stroke-opacity=".7" stroke-width="1.2"/>
      <line x1="134" y1="0" x2="116" y2="12" stroke="#ffffff" stroke-width=".8" opacity=".55"/>
      <line x1="165" y1="0" x2="148" y2="12" stroke="#ffffff" stroke-width=".8" opacity=".55"/>
      <line x1="196" y1="0" x2="180" y2="12" stroke="#ffffff" stroke-width=".8" opacity=".55"/>
      <line x1="226" y1="0" x2="210" y2="12" stroke="#ffffff" stroke-width=".8" opacity=".55"/>
      <line x1="113" y1="6" x2="235" y2="6" stroke="#ffffff" stroke-width=".8" opacity=".55"/>
    </g>
    <!-- wheels -->
    <circle cx="82" cy="72" r="21" fill="#202228"/>
    <circle cx="238" cy="72" r="21" fill="#202228"/>
    <g class="wheel"><circle cx="82" cy="72" r="15" fill="#4a4d57"/><circle cx="82" cy="72" r="4" fill="#cfd3dc"/>
      <line x1="82" y1="58" x2="82" y2="86" stroke="#cfd3dc" stroke-width="3"/><line x1="68" y1="72" x2="96" y2="72" stroke="#cfd3dc" stroke-width="3"/>
      <line x1="72" y1="62" x2="92" y2="82" stroke="#cfd3dc" stroke-width="3"/><line x1="92" y1="62" x2="72" y2="82" stroke="#cfd3dc" stroke-width="3"/></g>
    <g class="wheel"><circle cx="238" cy="72" r="15" fill="#4a4d57"/><circle cx="238" cy="72" r="4" fill="#cfd3dc"/>
      <line x1="238" y1="58" x2="238" y2="86" stroke="#cfd3dc" stroke-width="3"/><line x1="224" y1="72" x2="252" y2="72" stroke="#cfd3dc" stroke-width="3"/>
      <line x1="228" y1="62" x2="248" y2="82" stroke="#cfd3dc" stroke-width="3"/><line x1="248" y1="62" x2="228" y2="82" stroke="#cfd3dc" stroke-width="3"/></g>
  </g>

  <!-- info pills -->
  <rect x="14" y="14" width="284" height="36" rx="18" fill="#fff" opacity=".88"/>
  <text class="pilltxt" x="30" y="38">__DATELABEL__ · __TIMELABEL__</text>
  <rect x="500" y="14" width="286" height="36" rx="18" fill="#fff" opacity=".88"/>
  <text class="pilltxt" id="wtxt" x="516" y="38"></text>
  <rect x="14" y="252" width="290" height="36" rx="18" fill="#fff" opacity=".88"/>
  <text class="pilltxt" id="odo" x="30" y="276"></text>
</svg>
<script>
  const H = __HOUR__, W = __WATTS__, PK = __PEAK__, RANGE = __RANGE__;
  const $ = id => document.getElementById(id);
  const mix = (a,b,t) => a.map((v,i)=>Math.round(v+(b[i]-v)*t));
  const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;
  const t = H + 0.5;
  // daylight 0..1
  const d = Math.max(0, Math.min(1, Math.sin(Math.PI*(t-5.2)/13.6)*1.6));
  $("s1").setAttribute("stop-color", rgb(mix([10,22,52],[96,184,242],d)));
  $("s2").setAttribute("stop-color", rgb(mix([34,52,92],[214,240,255],d)));
  $("stars").setAttribute("opacity", Math.max(0, 1-d*1.6));
  // sun arc 6am..6pm, moon otherwise
  if (t>=5.5 && t<=18.5) {
    const p = (t-5.5)/13, x = 70+p*660, y = 175 - Math.sin(p*Math.PI)*140;
    $("sun").setAttribute("transform", `translate(${x},${y})`); $("sun").setAttribute("opacity", 1);
  } else {
    $("moon").setAttribute("transform","translate(640,70)"); $("moon").setAttribute("opacity",1);
    $("moonshade").setAttribute("fill", rgb(mix([10,22,52],[34,52,92],0.3)));
  }
  // dim the scene a bit at night
  const hill = mix([36,70,56],[127,183,126],Math.max(d,0.25));
  let hills = "";
  for (let k=0;k<2;k++) {
    hills += `<path transform="translate(${k*800},0)" fill="${rgb(hill)}" d="M0 190 Q100 118 200 175 Q300 218 400 170 Q500 122 600 168 Q700 205 800 190 V200 H0Z"/>`;
  }
  $("hillset").innerHTML = hills;
  // trees (repeat so the loop is seamless)
  let trees = "";
  for (let k=0;k<2;k++) for (let i=0;i<10;i++){
    const x = k*800 + 30 + i*80 + (i%3)*14, h = 34 + (i%4)*8;
    trees += `<rect x="${x+8}" y="${192-h*0.3}" width="6" height="${h*0.3}" fill="#6b4f2a"/>`+
             `<polygon points="${x},${192-h*0.3} ${x+11},${192-h} ${x+22},${192-h*0.3}" fill="${rgb(mix([20,50,40],[58,128,76],Math.max(d,0.25)))}"/>`;
  }
  $("treeset").innerHTML = trees;
  // roof panel glows with power
  const i = PK > 0 ? Math.min(1, W/PK) : 0;
  $("panelfill").setAttribute("fill", rgb(mix([28,58,107],[255,176,32], i)));
  const RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (W > 1 && !RM) $("roofpanel").classList.add("pulse");
  $("wtxt").textContent = W > 1 ? `Solar now: ${Math.round(W)} W` : "Solar now: 0 W (no sun)";
  // no power = parked. Otherwise the car drives faster the more power the panel makes.
  const svgEl = document.querySelector("svg");
  svgEl.setAttribute("aria-label", `Electric car with a solar roof, ${Math.round(W)} watts at ${__HOUR__}:00`);
  const moving = W > 1;
  if (!moving) {
    svgEl.classList.add("stopped");
  } else {
    const f = 0.4 + 0.6 * Math.min(1, W / (PK || 1));
    const speedUp = (sel, secs) => document.querySelectorAll(sel).forEach(e => e.style.animationDuration = (secs / f) + "s");
    speedUp(".road-dash", 0.7); speedUp(".wheel", 0.55); speedUp(".hills", 14); speedUp(".trees", 5);
  }
  // trip counter: counts up to the km of range this day's sun is worth
  function loop(){
    if (!moving) { $("odo").textContent = "Parked: no solar power"; return; }
    if (RM) { $("odo").textContent = `Sun range: +${RANGE.toFixed(1)} km`; return; }
    const start = performance.now(), dur = 6000;
    (function frame(now){
      const p = Math.min(1,(now-start)/dur);
      $("odo").textContent = `Sun range: +${(RANGE*p).toFixed(1)} km`;
      if (p<1) requestAnimationFrame(frame); else setTimeout(loop, 2500);
    })(start);
  }
  loop();
</script>
"""


def car_scene(hour, watts, peak, range_km, date_label):
    h12 = hour % 12 or 12
    time_label = f"{h12}:00 {'am' if hour < 12 else 'pm'}"
    html = (SCENE
            .replace("__HOUR__", str(int(hour)))
            .replace("__WATTS__", f"{float(watts):.1f}")
            .replace("__PEAK__", f"{float(peak):.1f}")
            .replace("__RANGE__", f"{float(range_km):.2f}")
            .replace("__DATELABEL__", date_label)
            .replace("__TIMELABEL__", time_label))
    return html


# ----------------------------------------------------------------------------
# Sidebar settings
# ----------------------------------------------------------------------------
st.sidebar.markdown('<div class="sbtitle">Settings</div>', unsafe_allow_html=True)
st.sidebar.markdown('<div class="grp">Panel</div>', unsafe_allow_html=True)
area = st.sidebar.slider("Panel area (m²)", 0.5, 8.0, 2.0, 0.5)
eff = st.sidebar.slider("Panel efficiency (%)", 15, 25, 22) / 100
st.sidebar.markdown('<div class="grp">Position</div>', unsafe_allow_html=True)
tilt = st.sidebar.slider("Tilt (degrees)", 0, 90, 20)
az_name = st.sidebar.selectbox("Panels face", ["North", "East", "South", "West"], 0)
azimuth = {"North": 0, "East": 90, "South": 180, "West": 270}[az_name]
losses = st.sidebar.slider("System losses (%)", 5, 35, 20)
st.sidebar.markdown('<div class="grp">Vehicle</div>', unsafe_allow_html=True)
wh_km = st.sidebar.slider("Energy use (Wh per km)", 100, 250, 150)
batt = st.sidebar.number_input("Battery (kWh)", 40.0, 120.0, 60.0)

# ----------------------------------------------------------------------------
# Date controls
# ----------------------------------------------------------------------------
today = pd.Timestamp.now(tz=TZ).date()
min_d = today - dt.timedelta(days=DAYS_BACK)
max_d = today + dt.timedelta(days=DAYS_AHEAD)
if "sel_date" not in st.session_state:
    st.session_state.sel_date = today


def shift_day(n):
    new = st.session_state.sel_date + dt.timedelta(days=n)
    st.session_state.sel_date = min(max(new, min_d), max_d)


def go_today():
    st.session_state.sel_date = today


st.markdown('<div class="largetitle">Sydney solar EV dashboard</div>'
            '<div class="subtitle">How far the sun can drive an electric car</div>',
            unsafe_allow_html=True)
c1, c2, c3, c4, _ = st.columns([1.3, 2.2, 1.1, 1.1, 4])
c1.button("‹ Previous", on_click=shift_day, args=(-1,), width="stretch", help="Go to the previous day")
c2.date_input("Date", key="sel_date", min_value=min_d, max_value=max_d,
              format="DD/MM/YYYY", label_visibility="collapsed")
c3.button("Next ›", on_click=shift_day, args=(1,), width="stretch", help="Go to the next day")
c4.button("Today", on_click=go_today, width="stretch", help="Jump back to today")

if hasattr(st, "segmented_control"):
    st.segmented_control("View", ["Day", "Week"], default="Day", key="view",
                         label_visibility="collapsed")
else:
    st.radio("View", ["Day", "Week"], key="view", horizontal=True,
             label_visibility="collapsed")


@st.fragment(run_every=REFRESH_SECONDS)
def live_view():
    try:
        weather = fetch_weather()
    except Exception as e:                                   # no internet, API down...
        st.error(f"Could not get live weather: {e}")
        return

    power = compute_power(weather, area, eff, tilt, azimuth, losses)
    local = power.copy()
    local.index = local.index.tz_convert(TZ)
    now = pd.Timestamp.now(tz=TZ)
    sel = st.session_state.sel_date
    day = day_slice(local, sel)
    if day.empty:
        st.warning("No data for that date yet. Try a date closer to today.")
        return

    energy = float(day.sum()) / 1000                         # hourly mean W summed = Wh
    peak_w = float(day.max())
    range_km = energy * 1000 / wh_km
    kind = "Forecast" if sel > today else ("Today" if sel == today else "Past day")

    view = st.session_state.get("view") or "Day"

    def tile(label, value, unit=""):
        u = f'<span class="u">{unit}</span>' if unit else ""
        return f'<div class="tile"><div class="k">{label}</div><div class="v">{value}{u}</div></div>'

    # ---------------- DAY VIEW ----------------
    if view == "Day":
        left, right = st.columns([3, 2], gap="large")
        if sel == today:
            cur = local[(local.index > now) & (local.index <= now + pd.Timedelta(hours=1))]
            first = tile("Power now", f"{float(cur.iloc[0]) if len(cur) else 0:,.0f}", "W")
        else:
            first = tile("Peak power", f"{peak_w:,.0f}", "W")

        with left:
            scene_slot = st.container()                       # filled once the hour is known
            with st.container(border=True):
                default_hour = now.hour if sel == today else 13
                hour = st.slider("Time of day", 0, 23, default_hour, format="%d:00")
                st.markdown('<div class="hint">Move the slider to move the sun. The roof panel '
                            'glows amber with power and goes dark at night.</div>',
                            unsafe_allow_html=True)
        with right:
            st.markdown(
                '<div class="tiles">'
                + first
                + tile(f"Energy ({kind.lower()})", f"{energy:.2f}", "kWh")
                + tile("Range gained", f"{range_km:.1f}", "km")
                + tile("Share of battery", f"{100 * energy / batt:.1f}", "%")
                + '</div>', unsafe_allow_html=True)

        idx = min(hour, len(day) - 1)
        watts_h = float(day.iloc[idx])
        with scene_slot:
            show_html(car_scene(hour, watts_h, peak_w, range_km,
                                pd.Timestamp(sel).strftime("%a %d %b %Y")), 270)

        with st.container(border=True):
            st.markdown('<div class="sec">Power through the day</div>', unsafe_allow_html=True)
            chart = pd.DataFrame({"Hour": list(range(len(day))), "Power (W)": day.values})
            area_chart(chart, "Hour", "Power (W)", CHART_AMBER, 240)

    # ---------------- WEEK VIEW ----------------
    else:
        start = max(min_d, min(sel - dt.timedelta(days=3), max_d - dt.timedelta(days=6)))
        rows = []
        for i in range(7):
            d = start + dt.timedelta(days=i)
            sl = day_slice(local, d)
            if sl.empty:
                continue
            e = float(sl.sum()) / 1000
            rows.append({"Date": pd.Timestamp(d).strftime("%a %d %b"),
                         "Energy (kWh)": round(e, 2),
                         "Range (km)": round(e * 1000 / wh_km, 1),
                         "Peak (W)": round(float(sl.max()))})
        week = pd.DataFrame(rows).set_index("Date")
        with st.container(border=True):
            st.markdown('<div class="sec">Energy per day</div>', unsafe_allow_html=True)
            bar_chart(week.reset_index(), "Date", "Energy (kWh)", CHART_AMBER, 240)
        with st.container(border=True):
            st.markdown('<div class="sec">Range gained per day</div>', unsafe_allow_html=True)
            bar_chart(week.reset_index(), "Date", "Range (km)", CHART_BLUE, 220)
        with st.container(border=True):
            st.markdown('<div class="sec">Details</div>', unsafe_allow_html=True)
            st.dataframe(week, width="stretch")

    st.markdown(
        f'<div class="foot">Last updated {now:%H:%M:%S} Sydney time · refreshes every '
        f'{REFRESH_SECONDS // 60} min · Weather: Open-Meteo · Model: PVWatts (same as SAM). '
        'Modelled estimates, not measurements from a physical panel.</div>',
        unsafe_allow_html=True)


live_view()
