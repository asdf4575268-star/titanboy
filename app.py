import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, requests, polyline, math, os
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# --- [1. 기본 설정 및 유틸리티] ---
st.set_page_config(page_title="TITAN BOY", layout="wide")
plt.switch_backend('Agg')
CLIENT_ID, CLIENT_SECRET = '202274', '63f6a7007ebe6b405763fc3104e17bb53b468ad0'
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app"

def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (int(alpha),)

@st.cache_resource
def load_font_cached(name, size):
    urls = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "KirangHaerang": "https://github.com/google/fonts/raw/main/ofl/kiranghaerang/KirangHaerang-Regular.ttf",
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf"
    }
    path = f"font_{name}.ttf"
    if not os.path.exists(path) and name in urls:
        with open(path, "wb") as f: f.write(requests.get(urls[name]).content)
    try: return ImageFont.truetype(path, int(size))
    except: return ImageFont.load_default()

def draw_text(draw, pos, text, font, fill, shadow=True):
    if shadow: draw.text((pos[0]+2, pos[1]+2), text, font=font, fill=(0,0,0,220))
    draw.text(pos, text, font=font, fill=fill)

# --- [2. 데이터 처리 로직] ---
def get_stats(acts, mode, target):
    try:
        t_date = datetime.strptime(target, "%Y-%m-%d")
        if mode == "WEEKLY":
            s_date = t_date - timedelta(days=t_date.weekday())
            e_date = s_date + timedelta(days=6)
            days = 7; range_str = f"{s_date.strftime('%m.%d')} - {e_date.strftime('%m.%d')}"
        else:
            s_date = t_date.replace(day=1)
            e_date = (s_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            days = e_date.day; range_str = s_date.strftime('%Y.%m')
        
        dists = [0.0] * days; tot_d, tot_t, hr_s, hr_c = 0, 0, 0, 0
        for a in acts:
            if a.get('type') != 'Run': continue
            ad = datetime.strptime(a['start_date_local'][:10], "%Y-%m-%d")
            if s_date <= ad <= e_date:
                idx = ad.weekday() if mode == "WEEKLY" else ad.day - 1
                d = a.get('distance', 0)/1000
                dists[idx] += d; tot_d += d; tot_t += a.get('moving_time', 0)
                if a.get('average_heartrate'): hr_s += a['average_heartrate']; hr_c += 1
        return {"dists": dists, "total_dist": f"{tot_d:.2f}", "time": f"{tot_t//3600:02d}:{(tot_t%3600)//60:02d}:{tot_t%60:02d}", 
                "pace": f"{int((tot_t/tot_d)//60)}'{int((tot_t/tot_d)%60):02d}\"" if tot_d else "0'00\"", 
                "hr": str(int(hr_s/hr_c)) if hr_c else "0", "range": range_str, "labels": [str(i+1) for i in range(days)] if mode=="MONTHLY" else None}
    except: return None

# --- [3. 메인 화면 구성] ---
col_preview, col_style = st.columns([1.2, 1], gap="large")

if 'token' not in st.session_state: st.session_state.token = None
if 'acts' not in st.session_state: st.session_state.acts = []
qp = st.query_params

# Strava 인증 처리
if "token" in qp: st.session_state.token = qp["token"]
elif "code" in qp and not st.session_state.token:
    res = requests.post("https://www.strava.com/oauth/token", data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": qp["code"], "grant_type": "authorization_code"}).json()
    if 'access_token' in res:
        st.session_state.token = res['access_token']; st.query_params.clear(); st.query_params["token"] = res['access_token']; st.rerun()

if st.session_state.token and not st.session_state.acts:
    st.session_state.acts = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=50", headers={'Authorization': f"Bearer {st.session_state.token}"}).json()

# 기본 값 설정
v_act, v_date, v_dist, v_time, v_pace, v_hr, a, w_data, m_data = "RUNNING", "2026.02.16 00:00 AM", "0.00", "00:00:00", "0'00\"", "0", None, None, None

# 활동 데이터 파싱
if st.session_state.acts:
    mode = st.radio("분류 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True)
    if mode == "DAILY":
        acts_list = [f"{x['start_date_local'][:10]} - {x['name']}" for x in st.session_state.acts]
        sel = st.selectbox("활동 선택", acts_list)
        a = st.session_state.acts[acts_list.index(sel)]
        v
