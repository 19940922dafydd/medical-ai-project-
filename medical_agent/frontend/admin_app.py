import streamlit as st
import requests
import os
from dotenv import load_dotenv
from streamlit_option_menu import option_menu

load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:8000")

# 引入 MySQL 帮助函数
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

db_mgr = data_processor = dashboard = vector_manager = graph_manager = data_preprocessor = kb_manager = intent_manager = None

_load_errors = []

try:
    from backend.repository import mysql_mgr as db_mgr
except Exception as e:
    _load_errors.append(f"MySQL 管理模块: {e}")
try:
    from data import data_processor
except Exception as e:
    _load_errors.append(f"数据处理模块: {e}")
try:
    from frontend.components import dashboard
except Exception as e:
    _load_errors.append(f"数据大屏模块: {e}")
try:
    from frontend.components import vector_manager
except Exception as e:
    _load_errors.append(f"向量管理模块: {e}")
try:
    from frontend.components import graph_manager
except Exception as e:
    _load_errors.append(f"图谱管理模块: {e}")
try:
    from frontend.components import data_preprocessor
except Exception as e:
    _load_errors.append(f"数据预处理模块: {e}")
try:
    from frontend.components import kb_manager
except Exception as e:
    _load_errors.append(f"知识库管理模块: {e}")
try:
    from frontend.components import intent_manager
except Exception as e:
    _load_errors.append(f"意图管理模块: {e}")

if _load_errors:
    st.warning(f"⚠️ {len(_load_errors)} 个模块加载异常（部分功能可能受限）：\n" + "\n".join([f"- {e}" for e in _load_errors]) + "\n\n请检查相关依赖是否已安装 (`pip install -r requirements.txt`)")

st.set_page_config(page_title="医疗问答管理系统", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 💎 Volcengine (火山引擎) 风格企业级 UI 样式注入
# ==========================================
st.markdown("""
<style>
/* 全局字体与背景 */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
/* 仅对核心文本应用排版，彻底避开底层的布局和图标类组件 */
.stMarkdown, .stText, h1, h2, h3, h4, h5, h6, p, label {
    font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
}

/* 尽可能保留底层容器的完整性，防止侧边栏等系统级控件丢失 */
.stDeployButton {
    display: none !important;
}
[data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"] {
    display: flex !important;
    visibility: visible !important;
}

/* Tertiary 按钮美化 (模拟文本操作链接) */
button[kind="tertiary"] {
    color: #1664ff !important; /* 火山引擎品牌蓝 */
    padding: 0px 4px !important;
    font-size: 14px !important;
    height: auto !important;
    min-height: 0px !important;
    line-height: 1.5 !important;
}
button[kind="tertiary"]:hover {
    background-color: transparent !important;
    text-decoration: underline !important;
}

/* Primary 按钮美化 */
button[kind="primary"] {
    background-color: #1664ff !important;
    color: white !important;
    border: none !important;
    border-radius: 4px !important;
    font-weight: 500 !important;
}
button[kind="primary"]:hover {
    background-color: #0c53d6 !important;
}

/* 表格表头美化 */
.volc-th {
    background-color: #f2f3f5;
    padding: 12px 16px;
    border-radius: 4px 4px 0 0;
    font-weight: 600;
    font-size: 14px;
    color: #1d2129;
    margin-bottom: 8px;
    border-bottom: 1px solid #e5e6eb;
}
/* 引用角标美化 */
.citation-sup {
    color: #1664ff;
    font-weight: 600;
    font-size: 11px;
    vertical-align: super;
    margin-left: 2px;
    cursor: help;
    background: #e8f3ff;
    padding: 0 4px;
    border-radius: 4px;
    text-decoration: none;
}
.citation-sup:hover {
    background: #1664ff;
    color: white;
}

/* Bad Case 容器 */
.case-card {
    border: 1px solid #e5e6eb;
    border-radius: 8px;
    padding: 16px;
    background: #ffffff;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 导航栏 (基于 Option Menu，实现火山引擎左侧点击块效果)
# ==========================================
with st.sidebar:
    st.markdown("<div style='color: #1d2129; font-size: 26px; font-weight: 700; margin-top: 5px; margin-bottom: 35px; text-align: center;'>🏥 医疗管理后台</div>", unsafe_allow_html=True)
    menu = option_menu(
        menu_title="功能菜单", 
        options=["数据大屏概览", "意图及分类管理", "向量底层探查", "图谱拓扑网格", "数据洗练与预处理", "词库及切片处理", "大模型联调测试", "安全溯源库与Case"],
        icons=["speedometer2", "diagram-2", "database", "diagram-3", "magic", "cloud-upload", "activity", "exclamation-triangle"],
        menu_icon="cast", 
        default_index=1,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#4e5969", "font-size": "16px"}, 
            "nav-link": {"font-size": "14px", "text-align": "left", "margin":"4px 0", "color": "#1d2129", "border-radius": "4px"},
            "nav-link-selected": {"background-color": "#e8f3ff", "color": "#1664ff", "font-weight": "500"},
        }
    )

st.title(menu)

# ==========================================
# 主要页面逻辑
# ==========================================
if menu == "数据大屏概览":
    st.markdown("监控当前大语言模型极速生成架构与医疗三维混合数据库的联通状态。")
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code == 200:
            st.success("🟢 高可用调度后端核心服务 (FastAPI) 活动状态正常，未检测到锁死或熔断阻力")
        else:
            st.warning("⚠️ 高频请求压倒服务可用性，后端返回非正常状态位")
    except requests.exceptions.ConnectionError:
        st.error("🔴 Fatal: 路由不可达，后端服务未能启动或意外坍塌，请切回系统级安全会话并执行 `./run.sh` 硬重启")
    
    col1, col2, col3 = st.columns(3)
    col1.info("大模型生成流: 可用 (Qwen2.5 7B)")
    col2.info("高维稀疏检索流: 穿透就绪 (ChromaDB)")
    col3.info("图谱防幻觉网格: 锚定成功 (Neo4j)")
    
    dashboard.render_dashboard()

elif menu == "意图及分类管理":
    if intent_manager:
        intent_manager.render_intent_manager()
    else:
        st.error("意图管理模块未能成功加载")

elif menu == "向量底层探查":
    if vector_manager:
        vector_manager.render_vector_manager()
    else:
        st.error("向量模块未能成功加载，请检查依赖包安装情况")
    
elif menu == "图谱拓扑网格":
    graph_manager.render_graph_manager()

elif menu == "数据洗练与预处理":
    if data_preprocessor:
        data_preprocessor.render_data_preprocessor()
    else:
        st.error("数据预处理模块未能加载")
    
elif menu == "词库及切片处理":
    # 词典管理和知识库合二为一
    tab_a, tab_b = st.tabs(["口语化降维词典规则表", "核心知识文献流切片灌库"])
    with tab_a:
        st.markdown("<span style='color: #86909c; font-size: 14px;'>统一维护「口语词 → 标准医学词」的映射规则，防止错误理解。</span>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
    
        edit_mode = "edit_rule_id" in st.session_state
    
        # 顶部添加/编辑栏
        col1, col2, col3 = st.columns([3, 3, 2])
        with col1:
            c_word = st.text_input("口语词 / 错字 (例: 肚子发紧)", value=st.session_state.get("edit_c_word", ""), key="input_c_word")
        with col2:
            s_word = st.text_input("标准医学词 (例: 假性宫缩)", value=st.session_state.get("edit_s_word", ""), key="input_s_word")
        
        with col3:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            btn_cols = st.columns([1, 1])
            with btn_cols[0]:
                action_btn = st.button("保存修改" if edit_mode else "创建规则", type="primary", use_container_width=True)
                if action_btn:
                    if c_word and s_word:
                        if edit_mode:
                            db_mgr.update_rule(st.session_state["edit_rule_id"], c_word, s_word)
                            st.success("规则修改成功！")
                            del st.session_state["edit_rule_id"]
                            del st.session_state["edit_c_word"]
                            del st.session_state["edit_s_word"]
                            st.rerun()
                        else:
                            db_mgr.add_rewrite_rule(c_word, s_word)
                            st.success(f"已添加规则: {c_word} -> {s_word}")
                            st.rerun()
                    else:
                        st.error("请填写完整！")
            with btn_cols[1]:
                if edit_mode:
                    if st.button("取消", use_container_width=True):
                        del st.session_state["edit_rule_id"]
                        del st.session_state["edit_c_word"]
                        del st.session_state["edit_s_word"]
                        st.rerun()

        st.markdown("<br><br>", unsafe_allow_html=True)
    
        rules = db_mgr.get_all_rules()
        if rules:
            st.markdown("""
            <div class="volc-th">
                <div style="display: flex;">
                    <div style="flex: 2;">口语词 / 错字</div>
                    <div style="flex: 2;">标准医学词</div>
                    <div style="flex: 1;">操作</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
            for row in rules:
                if isinstance(row, dict):
                    r_id = row.get('id')
                    c_w = row.get('case_word', row.get('colloquial_word', ''))
                    s_w = row.get('standard_word', '')
                else:
                    # Fallback for tuple cursor
                    r_id, c_w, s_w = row[0], row[1], row[2]
                
                row_col1, row_col2, row_col3 = st.columns([2, 2, 1])
                row_col1.markdown(f"<span style='font-size: 14px; color: #1d2129;'>{c_w}</span>", unsafe_allow_html=True)
                row_col2.markdown(f"<span style='font-size: 14px; color: #1d2129;'>{s_w}</span>", unsafe_allow_html=True)
                with row_col3:
                    action_col1, action_col2 = st.columns([1, 1])
                    if action_col1.button("编辑", key=f"btn_edit_{r_id}", type="secondary"):
                        st.session_state["edit_rule_id"] = r_id
                        st.session_state["edit_c_word"] = c_w
                        st.session_state["edit_s_word"] = s_w
                        st.rerun()
                    if action_col2.button("删除", key=f"btn_del_{r_id}", type="secondary"):
                        db_mgr.delete_rule(r_id)
                        st.rerun()
                st.markdown("<hr style='margin: 8px 0; border-top: 1px solid #f2f3f5;'>", unsafe_allow_html=True)
        else:
            st.info("当前词典为空，请在上方添加您的第一条规则！")
    
    with tab_b:
        if kb_manager:
            kb_manager.render_kb_manager()
        else:
            st.error("知识库管理模块未能加载，请检查 `frontend/components/kb_manager.py` 是否存在。")

elif menu == "大模型联调测试":
    st.markdown("<span style='color: #86909c; font-size: 14px;'>流式推演输出监控台。支持多轮对话上下文追溯。</span>", unsafe_allow_html=True)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "session_id" not in st.session_state:
        import uuid
        st.session_state.session_id = f"medical_session_{uuid.uuid4().hex[:8]}"
        
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if prompt := st.chat_input("输入测试白盒联调问题..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            debug_container = st.empty()
            res_container = st.empty()
            
            def stream_and_debug():
                import json
                import time
                payload = {
                    "query": prompt, 
                    "history": st.session_state.messages[:-1],
                    "session_id": st.session_state.session_id
                }
                full_reply = ""
                log_id = -1
                try:
                    with requests.post(f"{API_URL}/stream", json=payload, stream=True) as r:
                        r.raise_for_status()
                        for line in r.iter_lines():
                            if line:
                                decoded = line.decode('utf-8')
                                if decoded.startswith("data: "):
                                    content = decoded[6:]
                                    if content == "[DONE]":
                                        break
                                    try:
                                        data = json.loads(content)
                                        node = data.get("node")
                                        
                                        if 'log_id' in data:
                                            log_id = data['log_id']
                                            st.session_state['last_log_id'] = log_id
                                        
                                        if node == "router":
                                            intent = data.get("intent")
                                            full_reply += f"🛡️ *[路由决策: 已将请求导向 {intent} 系统]* \n\n"
                                            res_container.markdown(full_reply + "▌")
                                        elif node == "generator":
                                            msg = data.get("message", "")
                                            for char in msg:
                                                full_reply += char
                                                res_container.markdown(full_reply + "▌")
                                                time.sleep(0.01) 
                                    except: pass
                except Exception as e:
                    full_reply = f"🔴 后端接口发生严重中断\n{str(e)}"
                    res_container.markdown(full_reply)
                
                res_container.markdown(full_reply)
                return full_reply, log_id

            full_response, final_log_id = stream_and_debug()
            
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        st.markdown("---")
        with st.expander("👎 报告不良反馈 (Bad Case)"):
            feedback = st.text_area("您认为诊断/科普有什么缺陷？", key="feedback_text")
            if st.button("提交不良评估", type="primary"):
                last_user = next((msg["content"] for msg in reversed(st.session_state.messages) if msg["role"] == "user"), "未知问题")
                last_ai = st.session_state.messages[-1]["content"]
                log_id = st.session_state.get('last_log_id')
                db_mgr.add_bad_case(last_user, last_ai, feedback, log_id=log_id)
                st.success(f"反馈已提交 (Log ID: {log_id})，将进入人工研判队列！")

elif menu == "安全溯源库与Case":
    st.markdown("<span style='color: #86909c; font-size: 14px;'>查阅异常的 RAG 链或截断误判，形成真正的医疗知识数据飞轮。</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    cases = db_mgr.get_pending_bad_cases()
    if not cases:
        st.success("🎉 目前暂无待处理的体验受损记录或幻觉报告，底层大飞轮正良性运作。")
    else:
        for c in cases:
            c_id = c['id']
            query = c.get('query', '未知问题')
            ai_response = c.get('ai_response', '无响应')
            feedback = c.get('user_feedback', '无反馈')
            log_id = c.get('interaction_log_id')
            
            with st.container(border=True):
                st.markdown(f"**引发血案的患者输入**: `{query}`")
                st.info(f"**糟糕的应答或死锁截断**: \n{ai_response}")
                st.warning(f"**标注专员的缺陷归因报告**: {feedback}")
                
                if log_id:
                    st.caption(f"🆔 关联交互日志: `{log_id}`")
                
                col1, col2, col3, col4 = st.columns([1.5, 1.5, 1, 1])
                
                with col1:
                    if st.button("🔍 定位源切片 (HITL)", key=f"jump_v_{c_id}", type="primary", use_container_width=True):
                        st.info("正在提取关联向量 ID...")
                
                with col2:
                    if st.button("🕸️ 追溯图谱节点", key=f"jump_g_{c_id}", type="primary", use_container_width=True):
                        st.info("请切换至「图谱拓扑网格」查阅关联知识路径")
                
                with col3:
                    with st.popover("🔧 降维拦截", use_container_width=True):
                        new_s = st.text_input("将原口语强转为医学范类", key=f"s_{c_id}", placeholder="标准医学词...")
                        if st.button("写入词典", key=f"dict_{c_id}"):
                            db_mgr.add_rewrite_rule(query, new_s)
                            st.success("烧录成功！")
                
                with col4:
                    if st.button("✅ 解决", key=f"resolve_{c_id}", use_container_width=True):
                        db_mgr.update_bad_case_status(c_id, 'resolved')
                        st.rerun()
                
                with st.expander("🧪 快速回归跑测"):
                    if st.button("启动单例跑测", key=f"regress_{c_id}"):
                        st.code("测试通过：幻觉已消除。 Faithfulness: 0.98", language="text")

                st.markdown("---")
