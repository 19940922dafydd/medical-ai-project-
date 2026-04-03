import streamlit as st
from neo4j import GraphDatabase
import pandas as pd
import streamlit.components.v1 as components
from pyvis.network import Network
import os
from dotenv import load_dotenv

load_dotenv()

def get_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", "password123")
    return GraphDatabase.driver(uri, auth=(user, pwd))

def render_graph_manager():
    st.markdown("<span style='color: #86909c; font-size: 14px;'>基于 Neo4j 驱动的大型医疗实体库与图谱网。提供高级图算法、实体聚类与防幻觉路径挖掘可视透出机制。</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    try:
        driver = get_driver()
        with driver.session() as session:
            res = session.run("RETURN 1 as test")
            if res.single()["test"] == 1:
                st.success("✅ Neo4j 知识网谱数据库原生客户端连接信使已激活就绪！")
    except Exception as e:
        st.error(f"连接 Neo4j 失败: {str(e)}")
        return
        
    tab1, tab2, tab3 = st.tabs(["🕸️ 图谱总览", "⚙️ Cypher 查询控制台", "🔗 向量与图谱映射关系"])
    
    with tab1:
        st.subheader("⚕️ 医疗实体关联图谱")
        col_sel, col_btn = st.columns([3, 2])
        with col_sel:
            query_type = st.selectbox("显示算法选择", ["全库节点粗粒度抽样", "急症高危中心性分析", "病种关联分布"])
        with col_btn:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            run_render = st.button("生成渲染视图", use_container_width=True)
        
        if run_render:
            with st.spinner("正在计算布局并渲染图谱，请稍候..."):
                with driver.session() as session:
                    query = "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 80"
                    result = session.run(query)
                    
                    net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="#1d2129", directed=True)
                    net.barnes_hut(gravity=-3000, central_gravity=0.3, spring_length=150)
                    
                    for record in result:
                        node_n = record["n"]
                        node_m = record["m"]
                        rel = record["r"]
                        
                        n_label = list(node_n.labels)[0] if node_n.labels else "未知类别"
                        m_label = list(node_m.labels)[0] if node_m.labels else "未知类别"
                        n_name = node_n.get("name", str(node_n.id))
                        m_name = node_m.get("name", str(node_m.id))
                        
                        color_n = "#f53f3f" if "Disease" in n_label else "#1664ff" if "Category" in n_label else "#00b42a"
                        color_m = "#f53f3f" if "Disease" in m_label else "#1664ff" if "Category" in m_label else "#00b42a"
                        
                        net.add_node(node_n.id, label=n_name, title=n_label, color=color_n)
                        net.add_node(node_m.id, label=m_name, title=m_label, color=color_m)
                        net.add_edge(node_n.id, node_m.id, title=rel.type, label=rel.type, color="#86909c")
                    
                    html_path = "/tmp/neo4j_graph.html"
                    net.write_html(html_path)
                    
                    with open(html_path, "r", encoding="utf-8") as f:
                        components.html(f.read(), height=650)
                        
    with tab2:
        st.subheader("Cypher 查询控制台 (只读模式)")
        st.info("💡 您可以使用 Cypher 语句直接查询图数据库。系统已强制开启只读保护。")
        cypher_query = st.text_area("输入 Cypher 语句", value="MATCH (n) RETURN n.name as `实体名称`, labels(n) as `类别` LIMIT 15", height=150)
        
        if st.button("执行查询", type="primary"):
            # 前端安全拦截
            write_keywords = ["CREATE", "DELETE", "SET", "REMOVE", "MERGE", "DROP", "DETACH"]
            if any(kw in cypher_query.upper() for kw in write_keywords):
                st.error("🚫 安全权限拦截：检测到写操作指令。当前控制台仅允许 READ 操作。")
            else:
                try:
                    with driver.session(default_access_mode="READ") as session:
                        res = session.run(cypher_query)
                        records = [r.data() for r in res]
                        if records:
                            st.markdown(f"**查询结果 ({len(records)} 条数据)**")
                            st.dataframe(pd.DataFrame(records), use_container_width=True)
                        else:
                            st.info("查询成功，但未命中任何结果。")
                except Exception as e:
                    st.error(f"查询执行出错: {e}")
                
    with tab3:
        st.subheader("数据关联底层溯源")
        st.markdown("<span style='color: #86909c;'>审计映射表记录了向量切片与图谱节点的对应关系。</span>", unsafe_allow_html=True)
        
        import sqlite3
        db_path = "data/mapping_layer/mapping.db"
        if os.path.exists(db_path):
            # 增加搜索过滤功能
            search_query = st.text_input("🔍 搜索 vector_id 或 node_name", placeholder="输入关键词进行实时过滤...")
            
            with sqlite3.connect(db_path) as conn:
                df = pd.read_sql_query("SELECT * FROM vector_graph_mapping ORDER BY created_at DESC", conn)
                
                if search_query:
                    # 在 Python 层进行简单过滤
                    df = df[
                        df['vector_id'].astype(str).str.contains(search_query, case=False, na=False) |
                        df['graph_node_name'].astype(str).str.contains(search_query, case=False, na=False)
                    ]
                
                if not df.empty:
                    st.markdown(f"**审计记录 (共 {len(df)} 条记录)**")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("未找到匹配的审计记录。")
