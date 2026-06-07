import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io, os, requests, polyline, math
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import base64
import streamlit.components.v1 as components
import sqlite3
import time

# --- [1. 기본 설정 및 API] ---
API_CONFIGS = {
    "PRIMARY": {"ID": '202274', "SECRET": '63f6a7007ebe6b405763fc3104e17bb53b468ad0'},
    "SECONDARY": {"ID": '202275', "SECRET": '969201cab488e4eaf1398b106de1d4e520dc564c'}
}
CURRENT_CFG = API_CONFIGS["PRIMARY"] 
CLIENT_ID = CURRENT_CFG["ID"]
CLIENT_SECRET = CURRENT_CFG["SECRET"]
ACTUAL_URL = "https://titanboy-kgcnje3tg3hbfpfsp6uwzc.streamlit.app/"

try:
    logo = Image.open("logo.png")
    st.set_page_config(layout="centered", page_title="TITAN BOY", page_icon=logo, initial_sidebar_state="collapsed")
except Exception:
    st.set_page_config(layout="centered", page_title="TITAN BOY", initial_sidebar_state="collapsed")

mpl.use("Agg")

# --- [2. 유틸리티 함수] ---
def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

def draw_styled_text(draw, pos, text, font, fill, shadow=True):
    if shadow:
        draw.text((pos[0]+2, pos[1]+2), text, font=font, fill=(0, 0, 0, 220))
    draw.text(pos, text, font=font, fill=fill)

def load_font(name, size):
    fonts = {
        "BlackHanSans": "https://github.com/google/fonts/raw/main/ofl/blackhansans/BlackHanSans-Regular.ttf",
        "KirangHaerang": "https://github.com/google/fonts/raw/main/ofl/kiranghaerang/KirangHaerang-Regular.ttf",
        "Lacquer": "https://github.com/google/fonts/raw/main/ofl/lacquer/Lacquer-Regular.ttf",
        "Condiment": "https://github.com/google/fonts/raw/main/ofl/condiment/Condiment-Regular.ttf",
        "Bangers": "https://github.com/google/fonts/raw/main/ofl/bangers/Bangers-Regular.ttf",
        "BagelFatOne": "https://github.com/google/fonts/raw/main/ofl/bagelfatone/BagelFatOne-Regular.ttf"
    }
    f_path = f"font_{name}.ttf"
    
    if not os.path.exists(f_path):
        try:
            r = requests.get(fonts[name])
            with open(f_path, "wb") as f:
                f.write(r.content)
        except Exception:
            return ImageFont.load_default()
            
    try:
        return ImageFont.truetype(f_path, int(size))
    except Exception:
        return ImageFont.load_default()

@st.cache_data(show_spinner=False)
def get_icon_pil(name, size=(30, 30)):
    urls = {
        "dumbbell": "https://img.icons8.com/ios-filled/150/ffffff/dumbbell.png",
        "run": "https://img.icons8.com/ios-filled/150/ffffff/running.png",
        "ride": "https://img.icons8.com/ios-filled/150/ffffff/bicycle.png"
    }
    try:
        r = requests.get(urls.get(name), headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    except Exception:
        pass
    return None

def colorize_icon(icon, hex_color):
    if not icon: 
        return None
    c_rgb = hex_to_rgba(hex_color, 255)[:3]
    c_icon = Image.new("RGBA", icon.size, c_rgb)
    c_icon.putalpha(icon.getchannel('A'))
    return c_icon

WORKOUT_TYPES = ['Workout', 'WeightTraining', 'Pilates', 'HIIT']

def get_weekly_stats(activities, target_date_str):
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        weekly_run = [0.0] * 7
        weekly_ride = [0.0] * 7
        total_dist, total_time, hr_sum, hr_count = 0.0, 0, 0, 0
        other_count, other_total_time = 0, 0.0
        
        for act in activities:
            act_date = datetime.strptime(act['start_date_local'][:10], "%Y-%m-%d")
            if start_of_week <= act_date <= end_of_week:
                act_type = act.get('type')
                
                if act_type == "Run":
                    dist = act.get('distance', 0) / 1000
                    weekly_run[act_date.weekday()] += dist
                    total_dist += dist
                    total_time += act.get('moving_time', 0)
                    if act.get('average_heartrate'): 
                        hr_sum += act.get('average_heartrate')
                        hr_count += 1
                elif act_type == "Ride":
                    dist = act.get('distance', 0) / 1000
                    weekly_ride[act_date.weekday()] += dist
                elif act_type in WORKOUT_TYPES:
                    other_count += 1
                    other_total_time += act.get('moving_time', 0) / 60
                    
        avg_hr = int(hr_sum / hr_count) if hr_count > 0 else 0
        avg_pace_sec = (total_time / total_dist) if total_dist > 0 else 0
        avg_pace_str = f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\"" if total_dist > 0 else "0'00\""
        
        return {
            "run_dists": weekly_run,
            "ride_dists": weekly_ride,
            "total_dist": f"{total_dist:.2f}", 
            "total_time": f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}", 
            "avg_pace": avg_pace_str, 
            "avg_hr": str(avg_hr), 
            "range": f"{start_of_week.strftime('%m.%d')} - {end_of_week.strftime('%m.%d')}", 
            "other_count": other_count, 
            "other_total_time": other_total_time
        }
    except Exception: 
        return None

def get_monthly_stats(activities, target_date_str):
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        first_day = target_date.replace(day=1)
        next_month = first_day.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        num_days = last_day.day
        
        monthly_run = [0.0] * num_days
        monthly_ride = [0.0] * num_days
        total_dist, total_time, hr_sum, hr_count = 0.0, 0, 0, 0
        other_count, other_total_time = 0, 0.0
        
        for act in activities:
            act_date = datetime.strptime(act['start_date_local'][:10], "%Y-%m-%d")
            if first_day <= act_date <= last_day:
                act_type = act.get('type')
                
                if act_type == "Run":
                    dist = act.get('distance', 0) / 1000
                    monthly_run[act_date.day - 1] += dist
                    total_dist += dist
                    total_time += act.get('moving_time', 0)
                    if act.get('average_heartrate'): 
                        hr_sum += act.get('average_heartrate')
                        hr_count += 1
                elif act_type == "Ride":
                    dist = act.get('distance', 0) / 1000
                    monthly_ride[act_date.day - 1] += dist
                elif act_type in WORKOUT_TYPES:
                    other_count += 1
                    other_total_time += act.get('moving_time', 0) / 60
                    
        avg_hr = int(hr_sum / hr_count) if hr_count > 0 else 0
        avg_pace_sec = (total_time / total_dist) if total_dist > 0 else 0
        avg_pace_str = f"{int(avg_pace_sec//60)}'{int(avg_pace_sec%60):02d}\"" if total_dist > 0 else "0'00\""
        
        return {
            "run_dists": monthly_run,
            "ride_dists": monthly_ride,
            "total_dist": f"{total_dist:.2f}", 
            "total_time": f"{total_time//3600:02d}:{(total_time%3600)//60:02d}:{total_time%60:02d}", 
            "avg_pace": avg_pace_str, 
            "avg_hr": str(avg_hr), 
            "range": first_day.strftime('%Y.%m'), 
            "labels": [str(i+1) for i in range(num_days)], 
            "other_count": other_count, 
            "other_total_time": other_total_time
        }
    except Exception: 
        return None

def get_yearly_stats(activities, target_year_str):
    try:
        target_year = int(target_year_str)
        
        yearly_run = [0.0] * 12
        yearly_ride = [0.0] * 12
        total_dist, total_time, hr_sum, hr_count = 0.0, 0, 0, 0
        other_count, other_total_time = 0, 0.0
        
        for act in activities:
            act_date = datetime.strptime(act['start_date_local'][:10], "%Y-%m-%d")
            if act_date.year == target_year:
                act_type = act.get('type')
                
                if act_type == "Run":
                    dist = act.get('distance', 0) / 1000
                    yearly_run[act_date.month - 1] += dist
                    total_dist += dist
                    total_time += act.get('moving_time', 0)
                    if act.get('average_heartrate'): 
                        hr_sum +=
