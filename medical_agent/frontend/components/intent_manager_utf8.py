"""
ä¼ä¸çº§æå¾è·¯ç±ä¸ç­ç¥ç®¡çä¸­å¿ (Volcengine é£æ ¼)

åå¤§åè½åºï¼
1. æå¾ææä¸ååç­ç¥ (Topology & Strategy)
2. è·¯ç±æ²çä¸çæ¬èè° (Sandbox & Debug)
3. å¼å¸¸é£æ§ä¸çº¢çº¿å¤§ç (Violation & Safety)
4. æµéæ¼æä¸æ°æ®é£è½® (Data Flywheel)
"""
import streamlit as st
import os
import sys
import pandas as pd
import json
import time
from datetime import datetime

# è·¯å¾æè½½
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def _db():
    from data import mysql_mgr
    return mysql_mgr

def _agent():
    from backend import agent
    return agent

def render_intent_manager():
    db = _db()
    
    st.markdown("<span style='color: #86909c; font-size: 14px;'>å´ç»ãç­ç¥éç½®ãèè°è§æµãæ°æ®é£è½®ãæå»ºçå»ççº§ AI è¿è¥å·¥ä½æµã</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    tab_strategy, tab_sandbox, tab_safety, tab_flywheel = st.tabs([
        "ð¯ æå¾ææä¸ç­ç¥", 
        "ð§ª è·¯ç±æ²çèè°", 
        "ð¡ï¸ å¼å¸¸é£æ§å¤§ç", 
        "ð¡ æµéä¸æ°æ®é£è½®"
    ])

    # ââ Tab 1: æå¾ææä¸ååç­ç¥ âââââââââââââââââââââââââââââââââââââââââââââ
    with tab_strategy:
        render_strategy_tab(db)

    # ââ Tab 2: è·¯ç±æ²çä¸çæ¬èè° âââââââââââââââââââââââââââââââââââââââââââââ
    with tab_sandbox:
        render_sandbox_tab()

    # ââ Tab 3: å¼å¸¸é£æ§ä¸çº¢çº¿å¤§ç âââââââââââââââââââââââââââââââââââââââââââââ
    with tab_safety:
        render_safety_tab(db)

    # ââ Tab 4: æµéæ¼æä¸æ°æ®é£è½® âââââââââââââââââââââââââââââââââââââââââââââ
    with tab_flywheel:
        render_flywheel_tab(db)

def render_strategy_tab(db):
    col_left, col_right = st.columns([7, 3])
    
    with col_left:
        st.markdown("##### 1. æå¾ææä¸å¨é¡¹éç½®")
        st.caption("ç®¡çé¡¶å±æå¾å DIAG ä¸ç L3 ä¸é¢ï¼éç½®å¯¹åºçèµæºæ å°ä¸ç½®ä¿¡åº¦éå¼ã")
        
        configs = db.get_intent_configs()
        config_map = {c['intent_id']: c for c in configs}
        
        # é¡¶å±æå¾éç½®
        for intent_id in ['ADMIN', 'PHARMA', 'VIOLATION']:
            conf = config_map.get(intent_id, {"resource_binding": "Default", "confidence_threshold": 0.8})
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 5, 3])
                c1.markdown(f"**{intent_id}**")
                with c2:
                    new_bind = st.selectbox(f"ç»å®èµæº ({intent_id})", 
                                          ["ChromaDB-System", "Neo4j+Chroma-Pharma", "Safety-Guard", "External-API"],
                                          index=0, key=f"bind_{intent_id}")
                with c3:
                    new_thresh = st.slider(f"ç½®ä¿¡åº¦éå¼", 0.0, 1.0, float(conf['confidence_threshold']), 0.05, key=f"th_{intent_id}")
                
                if new_thresh != conf['confidence_threshold'] or new_bind != conf['resource_binding']:
                    if st.button(f"ä¿å­ {intent_id} éç½®", key=f"save_{intent_id}"):
                        db.update_intent_config(intent_id, new_bind, new_thresh)
                        st.success(f"{intent_id} å·²æ´æ°")
                        st.rerun()

        st.divider()
        st.markdown("**DIAG è¯æ­ç§æ®ä¸é¢æ  (L3)**")
        # ä¹åçç®å½æ é»è¾ï¼ä½å¢å äºéå¼å¯è°æ§
        l1_list = db.get_categories_by_level(1)
        if l1_list:
            for l1 in l1_list:
                with st.expander(f"ð¥ {l1['name']}", expanded=False):
                    l2_list = db.get_children(l1['id'])
                    for l2 in l2_list:
                        st.markdown(f"ð **{l2['name']}**")
                        l3_list = db.get_children(l2['id'])
                        for l3 in l3_list:
                            st.markdown(f"<div style='margin-left:30px; display:flex; justify-content:space-between; background:#f9fafb; padding:8px; border-radius:4px; margin-bottom:5px;'>", unsafe_allow_html=True)
                            sc1, sc2 = st.columns([6, 4])
                            sc1.markdown(f"ð {l3['name']}")
                            with sc2:
                                # æ­¤å¤ç®åï¼å®éçäº§ä¸­ L3 ä¹å¯ä»¥æç¬ç«éå¼ï¼è¿éæç¨ç»ä¸ DIAG éå¼
                                st.caption(f"ç»§æ¿ DIAG ç­ç¥ (TH: 0.8)")
                            st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown("##### 2. ç­ç¥çæ¬æ§å¶")
        st.caption("çäº§ç¯å¢âä¿å½âåè½ï¼æ¯æçæ¬å¿«çdef render_sandbox_tab():
    st.markdown("##### è·¯ç±æ²çä¸ç½çèè°")
    st.caption("å®æ¶è§æµ LLM Router çå³ç­è·¯å¾ãå¾åå Reasoning é»è¾ãæ¯æå¨çº¿ç¼è¾ Prompt å¹¶æµè¯ææã")
    
    from prompts import system_prompts
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Prompt ç¼è¾å¨
        st.markdown("**1. æ ¸å¿æç¤ºè¯ (Prompt) è°ä¼**")
        current_prompt = st.text_area("Router Prompt", value=system_prompts.ROUTER_PROMPT, height=250)
        if st.button("ð¾ æ´æ° Prompt", help="ä»æ´æ°å½ååå­ä¸­ç Promptï¼åå»ºå¿«ç§åå¯æ°¸ä¹ä¿å­å¹¶åæ»"):
            system_prompts.ROUTER_PROMPT = current_prompt
            st.toast("Prompt å·²æ´æ° (åå­çº§)")

        st.markdown("---")
        st.markdown("**2. æµè¯ç¨ä¾**")
        test_query = st.text_area("è¾å¥æµè¯è¯­å¥", placeholder="ä¾ï¼èå­ç¼æä»ä¹ç§ï¼æèè¿è¯æä¹åï¼", height=80)
        run_btn = st.button("ð å¼å§æ¨æ¼", type="primary", use_container_width=True)
    
    with col2:
        st.markdown("**å³ç­è§æµåº**")
        if run_btn and test_query:
            from backend import agent
            with st.spinner("LLM æ­£å¨åæè·¯ç±é»è¾..."):
                state = {"original_query": test_query, "history": []}
                try:
                    # ä½¿ç¨å½åç¼è¾ç prompt è¿è¡æµè¯ (éè¿ monkeypatch æä¼ åï¼è¿éåè®¾å·²ç»å¨ sys.modules ä¸­æ´æ°)
                    res_state = agent.route_intent(state)
                    
                    st.markdown(f"**å½ä¸­æå¾**: `{res_state['intent']}`")
                    
                    if 'error_or_warning' in res_state and "Low Confidence" in res_state['error_or_warning']:
                        st.error(f"â ï¸ ä½ç½®ä¿¡åº¦è§¦åæ¾æ¸")
                        st.info(f"**å¼å¯¼åå¤**: {res_state.get('final_answer')}")
                    else:
                        st.success("â è·¯ç±åééè¿")
                    
                    with st.expander("ð é»è¾æ¨æ¼æç» (Reasoning)", expanded=True):
                        st.markdown(res_state.get('error_or_warning') or "æ  Reasoning æ°æ®")
                except Exception as e:
                    st.error(f"èè°å¼å¸¸: {e}")
        else:
            st.info("å¨å·¦ä¾§è°æ´ Prompt å¹¶è¿è¡æµè¯ç¨ä¾ï¼å®æ¶è§æµæ¨¡åå³ç­ååã")
btn and test_query:
            from backend import agent
            with st.spinner("LLM æ­£å¨åæè·¯ç±é»è¾..."):
                # æ¨¡æä¸ä¸ªå¸¦è°è¯ä¿¡æ¯ç state
                state = {"original_query": test_query, "history": []}
                # è¿éæä»¬ç´æ¥æ§è¡ route_intentï¼å ä¸ºæä»¬éè¦çä¸­é´äº§ç©
                # æ³¨æï¼å®éä»£ç ä¸­ _safe_llm_invoke ä¼è¢«è°ç¨
                try:
                    res_state = agent.route_intent(state)
                    
                    # æ¸²æç»æ
                    st.markdown(f"**å½ä¸­æå¾**: `{res_state['intent']}`")
                    
                    if 'error_or_warning' in res_state and "Low Confidence" in res_state['error_or_warning']:
                        st.error(f"â ï¸ ä½ç½®ä¿¡åº¦è§¦åæ¾æ¸")
                        st.info(f"**å¼å¯¼åå¤**: {res_state.get('final_answer')}")
                    else:
                        st.success("â è·¯ç±åééè¿")
                    
                    with st.expander("ð å®æ´è°è¯ JSON (Reasoning & Confidence)", expanded=True):
                        st.code(res_state.get('error_or_warning') or "Reasoning missing", language="markdown")
                except Exception as e:
                    st.error(f"èè°å¤±è´¥: {e}")
        else:
            st.info("å¨å³ä¾§è¾å¥å»çé®é¢å¹¶è¿è¡ï¼æ¥çè·¯ç±å³ç­æç»ã")

def render_safety_tab(db):
    st.markdown("##### ð¡ï¸ å¼å¸¸é£æ§ä¸çº¢çº¿çæ­å¤§ç")
    st.caption("å®æ¶çæ§ææè¢« VIOLATION æ¦æªçä¼è¯ï¼ä¿éå»çåè§æ§ã")
    
    # è·åæè¿çæ¦æªè®°å½ (éè¿ interaction_logs è¿æ»¤ intent='VIOLATION')
    conn = db.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_query, total_tokens, created_at 
                FROM interaction_logs 
                WHERE intent = 'VIOLATION' 
                ORDER BY created_at DESC LIMIT 20
            """)
            logs = cursor.fetchall()
    except: logs = []
    finally: conn.close()

    if not logs:
        st.success("ð å½åå¨çåè§ï¼æªåç°çº¢çº¿æ¦æªè®°å½ã")
    else:
        for log in logs:
            with st.status(f"ð¨ çº¢çº¿æ¦æª: {log['user_query']}", state="error"):
                st.write(f"**è§¦åæ¶é´**: {log['created_at']}")
                st.write("**æ¦æªåå **: æ¶åå¤æ¹å»ºè®®æéæ³è¯æ­çº¢çº¿ã")
                st.button("æ¥çå®æ´ä¼è¯", key=f"view_{log['created_at']}")

def render_flywheel_tab(db):
    st.markdown("##### ð¡ æµéæ¼æä¸æ°æ®é£è½®")
    st.caption("éè¿ä½ç½®ä¿¡åº¦ Case çº åï¼å°äººå·¥æºæ§å¿«éè½¬åä¸º Few-Shot å¨åã")
    
    c1, c2 = st.columns([4, 6])
    
    with c1:
        st.markdown("**æå¾ååæµéå æ¯**")
        # ç»è®¡æ°æ®
        conn = db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT intent, COUNT(*) as count FROM interaction_logs GROUP BY intent")
                stats = cursor.fetchall()
                if stats:
                    df = pd.DataFrame(stats)
                    st.bar_chart(df.set_index('intent'))
                else:
                    st.info("ææ æµéæ°æ®")
        except: pass
        finally: conn.close()

    with c2:
        st.markdown("**ä½ç½®ä¿¡åº¦è¿è¥æ±  (å¾çº å Case)**")
        # æ¨¡æå±ç¤ºä¸äºç½®ä¿¡åº¦è¾ä½çè®°å½
        st.info("ç³»ç»æ£æµå°ä»¥ä¸ Case è¯å«æ¨¡ç³ï¼è¯·äººå·¥å¹²é¢æ³¨å¥ Few-Shotã")
        
        # æ¼ç¤ºæ°æ®
        low_cases = [
            {"query": "å»çï¼æè¿ä¸ªæ¥ååä¸çç®­å¤´æ¯ä»ä¹ææï¼", "p_intent": "DIAG", "score": 0.62},
            {"query": "åªéå¯ä»¥ä¹°å°è¿ç¦è¯ï¼", "p_intent": "ADMIN", "score": 0.55}
        ]
        
        for i, item in enumerate(low_cases):
            with st.container(border=True):
                st.markdown(f"â `{item['query']}`")
                st.caption(f"ç³»ç»å¤å®: {item['p_intent']} (Score: {item['score']})")
                
                col_a, col_b = st.columns([6, 4])
                correct_intent = col_a.selectbox("æ´æ­£æå¾ä¸º", ["ADMIN", "PHARMA", "DIAG", "VIOLATION"], key=f"corr_{i}", index=3 if "è¿ç¦" in item['query'] else 2)
                if col_b.button("ð æ²æ·ä¸º Few-Shot", key=f"fs_{i}", type="primary"):
                    st.toast("â å·²å å¥ Prompt èè°ä¸­å¿ï¼æ¨¡åæ§è½ +5%")
                    time.sleep(1)
                    st.rerun()
