else:
        st.button("🔓 로그아웃", on_click=logout_and_clear, use_container_width=True)
        bg_files = st.file_uploader("📸 배경 사진", type=['jpg','jpeg','png'], accept_multiple_files=True)
        log_file = st.file_uploader("🔘 원형 로고", type=['jpg','jpeg','png'])
        
        # [수정] 라디오 버튼은 여기서 딱 한 번만 선언합니다.
        mode = st.radio("모드 선택", ["DAILY", "WEEKLY", "MONTHLY"], horizontal=True, key="main_mode_sel")
        
        if acts:
            if mode == "DAILY":
                act_opts = [f"{ac['start_date_local'][:10]} - {ac['name']}" for ac in acts]
                sel_act = st.selectbox("🏃 활동 선택", act_opts)
                a = acts[act_opts.index(sel_act)]
                
                if a:
                    # DAILY: 스트라바 원래 이름 유지
                    v_act = a['name'] 
                    v_date = a['start_date_local'][:10]
                    d_km = a.get('distance', 0)/1000; m_s = a.get('moving_time', 0)
                    v_dist = f"{d_km:.2f}"
                    v_time = f"{m_s//3600:02d}:{(m_s%3600)//60:02d}:{m_s%60:02d}"
                    v_pace = f"{int((m_s/d_km)//60)}'{int((m_s/d_km)%60):02d}\"" if d_km > 0 else "0'00\""
                    v_hr = str(int(a.get('average_heartrate', 0))) if a.get('average_heartrate') else "0"
                
            elif mode == "WEEKLY":
                weeks = sorted(list(set([(datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d") - timedelta(days=datetime.strptime(ac['start_date_local'][:10], "%Y-%m-%d").weekday())).strftime('%Y.%m.%d') for ac in acts])), reverse=True)
                sel_week = st.selectbox("📅 주차 선택", weeks)
                weekly_data = get_weekly_stats(acts, sel_week.replace('.','-'))
                
                if weekly_data:
                    dt_t = datetime.strptime(sel_week.replace('.','-'), "%Y-%m-%d")
                    # 연간 누적 주차 계산 (ISO)
                    w_num = dt_t.isocalendar()[1]
                    sfx = "TH" if 11 <= w_num <= 13 else {1: "ST", 2: "ND", 3: "RD"}.get(w_num % 10, "TH")
                    
                    v_act = f"{w_num}{sfx} WEEK"
                    v_date, v_dist, v_time, v_pace, v_hr = weekly_data['range'], weekly_data['total_dist'], weekly_data['total_time'], weekly_data['avg_pace'], weekly_data['avg_hr']
                    
            elif mode == "MONTHLY":
                months = sorted(list(set([ac['start_date_local'][:7] for ac in acts])), reverse=True)
                sel_month = st.selectbox("🗓️ 월 선택", months)
                monthly_data = get_monthly_stats(acts, f"{sel_month}-01")
                
                if monthly_data:
                    dt_t = datetime.strptime(f"{sel_month}-01", "%Y-%m-%d")
                    # 월 이름 대문자 (예: FEBRUARY)
                    v_act = dt_t.strftime("%B").upper()
                    v_date, v_dist, v_time, v_pace, v_hr = monthly_data['range'], monthly_data['total_dist'], monthly_data['total_time'], monthly_data['avg_pace'], monthly_data['avg_hr']
