# --- [5. 메인 레이아웃 구성] ---
col_main, col_design = st.columns([1.1, 1], gap="medium")

with col_main:
    st.title("TITAN BOY")
    if not st.session_state['access_token']:
        st.link_button("🚀 Strava 연동", f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={ACTUAL_URL}&scope=read,activity:read_all&approval_prompt=force", use_container_width=True)
    else:
        st.button("🔓 로그아웃", on_click=logout_and_clear)
    
    mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True, label_visibility="collapsed")
    
    # 1. 데이터 선택 섹션
    with st.container(border=True):
        st.subheader("🏃 DATA SELECT")
        v_act, v_date, v_dist, v_time, v_pace, v_hr = "RUNNING", "2026-02-14", "0.00", "00:00:00", "0'00\"", "0"
        weekly_data, monthly_data, a = None, None, None

        if acts:
            if mode == "DAILY":
                act_opts = [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts]
                sel_act = st.selectbox("활동 선택", act_opts)
                a = acts[act_opts.index(sel_act)]
                d_km = a.get('distance', 0)/1000; m_s = a.get('moving_time', 0)
                v_act, v_date, v_dist, v_time = a['name'], a['start_date_local'][:10], f"{d_km:.2f}", f"{m_s//3600:02d}:{(m_s%3600)//60:02d}:{m_s%60:02d}"
                v_pace = f"{int((m_s/d_km)//60)}'{int((m_s/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
                v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
            elif mode == "WEEKLY":
                weeks = sorted(list(set([(datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d") - timedelta(days=datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d").weekday())).strftime('%Y.%m.%d') for ac in acts])), reverse=True)
                sel_week = st.selectbox("주차 선택", weeks)
                weekly_data = get_weekly_stats(acts, sel_week.replace('.','-'))
                if weekly_data: v_act, v_date, v_dist, v_time, v_pace, v_hr = "WEEKLY RUN", weekly_data['range'], weekly_data['total_dist'], weekly_data['total_time'], weekly_data['avg_pace'], weekly_data['avg_hr']
            elif mode == "MONTHLY":
                months = sorted(list(set([ac['start_date_local'][:7] for ac in acts])), reverse=True)
                sel_month = st.selectbox("월 선택", months)
                monthly_data = get_monthly_stats(acts, f"{sel_month}-01")
                if monthly_data: v_act, v_date, v_dist, v_time, v_pace, v_hr = "MONTHLY RUN", monthly_data['range'], monthly_data['total_dist'], monthly_data['total_time'], monthly_data['avg_pace'], monthly_data['avg_hr']

    # 2. 디자인 설정 섹션 (위로 올림)
    with st.container(border=True):
        st.subheader("🎨 DESIGN")
        bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
        log_file = st.file_uploader("🔘 로고", type=['jpg','jpeg','png'])
        
        c1, c2 = st.columns(2)
        box_orient = c1.radio("박스 방향", ["Vertical", "Horizontal"], horizontal=True)
        sel_font = c2.selectbox("폰트", ["BlackHanSans", "Jua", "DoHyeon", "NanumBrush", "Sunflower"])
        
        COLOR_OPTS = {"Yellow": "#FFD700", "White": "#FFFFFF", "Orange": "#FF4500", "Blue": "#00BFFF", "Grey": "#AAAAAA"}
        m_color = COLOR_OPTS[c1.selectbox("포인트 컬러", list(COLOR_OPTS.keys()))]
        sub_color = COLOR_OPTS[c2.selectbox("서브 컬러", list(COLOR_OPTS.keys()), index=1)]

        with st.expander("📍 세부 위치 조절 (OCR/Custom)"):
            rx = st.number_input("X 위치", 0, 1080, 70)
            ry = st.number_input("Y 위치", 0, 1920, 1250 if mode=="DAILY" else 850)
            rw = st.number_input("박스 너비", 100, 1080, 1080 if box_orient=="Horizontal" else 450)
            rh = st.number_input("박스 높이", 100, 1920, 260 if box_orient=="Horizontal" else 630)
            box_alpha = st.slider("박스 투명도", 0, 255, 110)
            vis_sz = st.slider("시각화 크기", 50, 1000, 250 if mode=="DAILY" else 1000)
            vis_alpha = st.slider("시각화 투명도", 0, 255, 180)

    # 최종 수기 보정 적용
    v_act, v_date, v_dist, v_time, v_pace, v_hr = v_act_in or v_act, v_date_in or v_date, v_dist_in or v_dist, v_time_in or v_time, v_pace_in or v_pace, v_hr_in or v_hr

with col_design:
    st.subheader("🖼️ PREVIEW")
    try:
        # 캔버스 크기 결정 (DAILY: 9:16, 그 외: 4:5)
        CW, CH = (1080, 1920) if mode == "DAILY" else (1080, 1350)
        
        f_t, f_d, f_n, f_l = load_font(sel_font, 90), load_font(sel_font, 30), load_font(sel_font, 60), load_font(sel_font, 23)
        f_path = f"font_{sel_font}_90.ttf"
        
        canvas = make_smart_collage(bg_files, (CW, CH)) if bg_files else Image.new("RGBA", (CW, CH), (20, 20, 20, 255))
        overlay = Image.new("RGBA", (CW, CH), (0,0,0,0)); draw = ImageDraw.Draw(overlay)
        
        # 데이터 박스 그리기 로직
        items = [("distance", f"{v_dist} km"), ("time", v_time), ("pace", v_pace), ("avg bpm", f"{v_hr} bpm")]
        if box_orient == "Vertical":
            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=(0,0,0,box_alpha))
            draw.text((rx+40, ry+30), v_act, font=f_t, fill=m_color)
            draw.text((rx+40, ry+145), v_date, font=f_d, fill="#AAAAAA")
            y_c = ry + 240
            for lab, val in items:
                draw.text((rx+40, y_c), lab.lower(), font=f_l, fill="#AAAAAA")
                draw.text((rx+40, y_c+30), val.lower() if any(x in val for x in ["km","bpm"]) else val, font=f_n, fill=sub_color); y_c += 130
        else:
            draw.rectangle([0, ry, 1080, ry + rh], fill=(0,0,0,box_alpha))
            draw.text(((1080 - draw.textlength(v_act, font=f_t))//2, ry + 35), v_act, font=f_t, fill=m_color)
            draw.text(((1080 - draw.textlength(v_date, font=f_d))//2, ry + 140), v_date, font=f_d, fill="#AAAAAA")
            sec_w = 1080 // 4
            for i, (lab, val) in enumerate(items):
                cx = (i * sec_w) + (sec_w // 2); v_s = val.lower() if any(x in val for x in ["km","bpm"]) else val
                draw.text((cx - draw.textlength(lab.lower(), font=f_l)//2, ry + 195), lab.lower(), font=f_l, fill="#AAAAAA")
                draw.text((cx - draw.textlength(v_s, font=f_n)//2, ry + 235), v_s, font=f_n, fill=sub_color)

        # 지도/그래프 렌더링
        if mode == "DAILY" and acts and 'a' in locals() and a and a.get('map', {}).get('summary_polyline'):
            pts = polyline.decode(a['map']['summary_polyline']); lats, lons = zip(*pts)
            vis_layer = Image.new("RGBA", (vis_sz, vis_sz), (0,0,0,0)); m_draw = ImageDraw.Draw(vis_layer)
            def tr(la, lo): return 15+(lo-min(lons))/(max(lons)-min(lons)+1e-5)*(vis_sz-30), (vis_sz-15)-(la-min(lats))/(max(lats)-min(lats)+1e-5)*(vis_sz-30)
            m_draw.line([tr(la, lo) for la, lo in pts], fill=hex_to_rgba(m_color, vis_alpha), width=5)
            overlay.paste(vis_layer, (int(rx + 40 + draw.textlength(v_act, font=f_t) + 20), int(ry + 30)), vis_layer)
        elif mode in ["WEEKLY", "MONTHLY"] and (weekly_data or monthly_data):
            d_obj = weekly_data if mode == "WEEKLY" else monthly_data
            chart_img = create_bar_chart(d_obj['dists'], m_color, mode=mode, labels=d_obj.get('labels'), font_path=f_path)
            vis_layer = chart_img.resize((vis_sz, int(chart_img.size[1]*(vis_sz/chart_img.size[0]))), Image.Resampling.LANCZOS)
            vis_layer.putalpha(vis_layer.getchannel('A').point(lambda x: x * (vis_alpha / 255)))
            overlay.paste(vis_layer, ((CW - vis_layer.width)//2, CH - vis_layer.height - 80), vis_layer)

        if log_file:
            ls = 100; l_img = ImageOps.fit(Image.open(log_file).convert("RGBA"), (ls, ls))
            mask = Image.new('L', (ls, ls), 0); ImageDraw.Draw(mask).ellipse((0, 0, ls, ls), fill=255); l_img.putalpha(mask)
            l_pos = (1080 - ls - 30, ry + 30) if box_orient == "Horizontal" else (rx + rw - ls - 25, ry + rh - ls - 25)
            overlay.paste(l_img, l_pos, l_img)

        # 결과물 출력 (use_container_width=True로 컬럼 너비에 맞춤)
        final = Image.alpha_composite(canvas, overlay).convert("RGB")
        st.image(final, use_container_width=True)
        
        buf = io.BytesIO(); final.save(buf, format="JPEG", quality=95)
        st.download_button(f"📥 {mode} 저장", buf.getvalue(), f"{mode.lower()}.jpg", use_container_width=True)

    except Exception as e:
        st.info("데이터를 선택하면 미리보기가 나타납니다.")
