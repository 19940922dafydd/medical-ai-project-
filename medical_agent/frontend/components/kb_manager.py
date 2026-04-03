"""
分层知识库管理组件 (L1→L2→L3)

精髓：意图识别后定位至L3三级库的向量子集，精准检索，不跨库污染。
每个切片入库时携带 l1/l2/l3 层级 metadata，供检索时按意图过滤。
"""
import streamlit as st
import os, sys, tempfile
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

LEVEL_ICONS = {1: "🏥", 2: "📂", 3: "📄"}
LEVEL_LABELS = {1: "一级库（主题域）", 2: "二级库（子领域）", 3: "三级库（知识专题）"}

def _db():
    from data import mysql_mgr
    return mysql_mgr

def render_kb_manager():
    db = _db()

    st.markdown(
        "<span style='color:#86909c;font-size:14px;'>核心知识文献流切片灌库与分层浏览。意图识别后的分类管理请前往「意图及分类管理」模块。</span>",
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

    tab_ingest, tab_browse, tab_history, tab_strategy = st.tabs([
        "📥 分级文档灌注",
        "🔍 分层切片浏览",
        "📜 入库历史追溯",
        "⚙️ 检索策略配置"
    ])

    # ── Tab 1: 分级文档灌注 (3-Step Flow) ──────────────────────────────────────
    with tab_ingest:
        from data import data_processor as dp
        st.markdown("#### 📥 分级文档入库：预览 → 调整 → 确认")
        st.caption("💡 闭环管理：入库前预览切片效果，入库后自动记录日志，支持一键撤销。")
        
        # ⚓ 专家选择前置：决定是否启用 L1/L2/L3 层级逻辑
        expert_options = {"诊断科普 (DIAG)": "DIAG", "行政/导诊 (ADMIN)": "ADMIN", "药理知识 (PHARMA)": "PHARMA"}
        sel_expert_label = st.radio("🎯 选择目标专家（资源绑定）", list(expert_options.keys()), horizontal=True, key="ingest_expert_sel")
        sel_expert = expert_options[sel_expert_label]
        
        # 动态渲染分级选择器
        sel_l1_name, sel_l2_name, sel_l3_name = "无", "无", "无"
        sel_l3_id = 0
        
        if sel_expert == "DIAG":
            l1_list = db.get_categories_by_level(1)
            if not l1_list:
                st.warning("⚠️ 请先在「意图及分类管理」中创建至少一个 L1 主题域，用于挂载诊断科普文献。")
            else:
                st.info("💡 诊断科普类文档需要精细的分级切分，以便执行 Metadata Filter 过滤。")
                col_sel1, col_sel2, col_sel3 = st.columns(3)
                l1_options = {r['name']: r['id'] for r in l1_list}
                sel_l1_name = col_sel1.selectbox("🏥 一级库", list(l1_options.keys()))
                sel_l1_id = l1_options[sel_l1_name]

                l2_list = db.get_children(sel_l1_id)
                if not l2_list:
                    st.warning(f"「{sel_l1_name}」下无二级库")
                else:
                    l2_options = {r['name']: r['id'] for r in l2_list}
                    sel_l2_name = col_sel2.selectbox("📂 二级库", list(l2_options.keys()))
                    sel_l2_id = l2_options[sel_l2_name]

                    l3_list = db.get_children(sel_l2_id)
                    if not l3_list:
                        st.warning(f"「{sel_l2_name}」下无三级专题")
                    else:
                        l3_options = {r['name']: r['id'] for r in l3_list}
                        sel_l3_name = col_sel3.selectbox("📄 三级专题", list(l3_options.keys()))
                        sel_l3_id = l3_options[sel_l3_name]
        else:
            st.success(f"🚀 已选择 {sel_expert_label}。该类文档将采用扁平化存储，无需配置三级库层级。")
            # 为扁平化存储设置默认 Meta
            sel_l1_name = sel_expert
            sel_l2_name = "Flat"
            sel_l3_name = "General"

        st.divider()
        # 1. 文件上传
        uploaded_files = st.file_uploader("1. 上传文档", type=['txt', 'md', 'pdf', 'docx', 'csv', 'xlsx'], key="kb_ingest_file", accept_multiple_files=True)
        
        # 提示信息展示区 (持久化)
        if "ingest_success_msg" in st.session_state:
            st.success(st.session_state["ingest_success_msg"])
            if st.button("清除提示"):
                del st.session_state["ingest_success_msg"]
                st.rerun()

        if uploaded_files:
            # 2. 参数调整与预览
            st.markdown("---")
            st.markdown(f"##### 2. 切片控制与效果预览 (已选择 {len(uploaded_files)} 个文件)")
            c1, c2, c3 = st.columns([3, 3, 2])
            chunk_sz = c1.slider("切片长度 (切片大小)", 100, 1500, 500, 50)
            chunk_ov = c2.slider("重叠程度 (重叠度)", 0, 300, 50, 10)
            
            # 预览逻辑
            if st.button("🔍 更新预览", use_container_width=True):
                with st.spinner("正在生成切片预览..."):
                    preview_files = []
                    for uploaded_file in uploaded_files:
                        suffix = os.path.splitext(uploaded_file.name)[1]
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                            tmp.write(uploaded_file.getbuffer())
                            tmp_path = tmp.name
                        preview_files.append({"path": tmp_path, "name": uploaded_file.name})
                    
                    try:
                        # 仅展示第一个文件的预览
                        primary_file = preview_files[0]
                        preview_data = dp.preview_chunks(primary_file["path"], chunk_sz, chunk_ov)
                        st.session_state['ingest_preview'] = preview_data
                        st.session_state['ingest_files_data'] = preview_files
                    except Exception as e:
                        st.error(f"预览失败: {e}")
            
            if 'ingest_preview' in st.session_state:
                previews = st.session_state['ingest_preview']
                avg_len = int(sum(p.get('word_count', 0) for p in previews)/max(len(previews), 1))
                st.info(f"📊 预估产生 **{len(previews)}** 个切片 | 平均长度: `{avg_len}` 字")
                
                # 展示前3个作为样例
                for i, p in enumerate(previews[:3]):
                    q_score = p.get('quality_score', 0.5)
                    with st.expander(f"切片样例 {i+1} | 质量评分: {q_score:.1f}"):
                        st.text(p['content'][:800] + "...")
                
                # 3. 正式入库
                st.markdown("---")
                st.markdown("##### 3. 确认入库")
                if st.button("🚀 开始持久化入库", type="primary", use_container_width=True):
                    with st.spinner(f"正在处理 {len(uploaded_files)} 个文件..."):
                        files_data = st.session_state.get('ingest_files_data', [])
                        success_count = 0
                        failed_files = []
                        
                        for f_info in files_data:
                            tmp_path = f_info["path"]
                            orig_name = f_info["name"]
                            if os.path.exists(tmp_path):
                                success = dp.process_hierarchical_document(
                                    file_path=tmp_path,
                                    l1_name=sel_l1_name,
                                    l2_name=sel_l2_name,
                                    l3_name=sel_l3_name,
                                    l3_id=sel_l3_id if sel_expert == "DIAG" else None,
                                    expert=sel_expert,
                                    chunk_size=chunk_sz, 
                                    chunk_overlap=chunk_ov,
                                    original_filename=orig_name
                                )
                                if success:
                                    success_count += 1
                                    os.unlink(tmp_path)
                                else:
                                    failed_files.append(orig_name)
                            else:
                                failed_files.append(f"{orig_name} (缓存失效)")
                        
                        if success_count > 0:
                            msg = f"✅ 成功入库 {success_count} 个文件！"
                            if failed_files:
                                msg += f" (失败: {', '.join(failed_files)})"
                            st.session_state["ingest_success_msg"] = msg
                            st.balloons()
                            if 'ingest_preview' in st.session_state:
                                del st.session_state['ingest_preview']
                            if 'ingest_files_data' in st.session_state:
                                del st.session_state['ingest_files_data']
                            st.rerun()
                        else:
                            st.error(f"❌ 全部导入失败: {', '.join(failed_files)}")

    # ── Tab 2: 分层切片浏览 ───────────────────────────────────────────────────
    with tab_browse:
        st.markdown("#### 按层级过滤浏览 ChromaDB 切片")
        try:
            import chromadb
            from config.settings import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME
            chroma = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            collection = chroma.get_or_create_collection(CHROMA_COLLECTION_NAME)
            total_count = collection.count()
            st.metric("ChromaDB 全局切片总量", f"{total_count:,}")
        except Exception as e:
            st.error(f"ChromaDB 连接失败: {e}")
            st.stop()

        filter_mode = st.radio("过滤模式", ["按专家领域过滤", "按L1一级库过滤", "按L3精准子集过滤（推荐）", "全量浏览"], horizontal=True)
        where_filter = None
        filter_label = "全部切片"

        if filter_mode == "按专家领域过滤":
            expert_options = {"诊断科普 (DIAG)": "DIAG", "行政/导诊 (ADMIN)": "ADMIN", "药理知识 (PHARMA)": "PHARMA"}
            sel_exp_label = st.selectbox("选择专家领域", list(expert_options.keys()))
            sel_exp = expert_options[sel_exp_label]
            where_filter = {"expert": {"$eq": sel_exp}}
            filter_label = f"专家: {sel_exp}"
            
        elif filter_mode == "按L1一级库过滤":
            l1_list = db.get_categories_by_level(1)
            if l1_list:
                l1_name = st.selectbox("选择一级主题域", [r['name'] for r in l1_list], key="browse_l1")
                where_filter = {"l1": {"$eq": l1_name}}
                filter_label = f"L1: {l1_name}"
        elif filter_mode == "按L3精准子集过滤（推荐）":
            l1_list = db.get_categories_by_level(1)
            if l1_list:
                l1_name = st.selectbox("一级域", [r['name'] for r in l1_list], key="browse_l3_l1")
                sel_l1 = next(r for r in l1_list if r['name'] == l1_name)
                l2_list = db.get_children(sel_l1['id'])
                if l2_list:
                    l2_name = st.selectbox("二级库", [r['name'] for r in l2_list], key="browse_l3_l2")
                    sel_l2 = next(r for r in l2_list if r['name'] == l2_name)
                    l3_list = db.get_children(sel_l2['id'])
                    if l3_list:
                        l3_name = st.selectbox("三级专题", [r['name'] for r in l3_list], key="browse_l3_l3")
                        where_filter = {"l3": {"$eq": l3_name}}
                        filter_label = f"L3 精准: {l1_name} → {l2_name} → {l3_name}"

        st.markdown(f"**当前过滤**: `{filter_label}`")
        page = st.number_input("翻页", min_value=1, value=1, step=1, key="browse_page")
        page_size = 10
        offset = (page - 1) * page_size

        try:
            query_kwargs = {"limit": page_size, "offset": offset, "include": ["documents", "metadatas"]}
            if where_filter: query_kwargs["where"] = where_filter
            results = collection.get(**query_kwargs)
            docs, metas = results.get("documents", []), results.get("metadatas", [])

            if not docs:
                st.info("暂无数据。")
            else:
                for i, (doc, meta) in enumerate(zip(docs, metas)):
                    l_path = f"{meta.get('l1','?')} → {meta.get('l2','?')} → {meta.get('l3','?')}"
                    with st.expander(f"**切片 {offset+i+1}** | 归属: `{l_path}` | 来源: `{meta.get('source','?')}`"):
                        st.markdown(f"**内容片段**:\n\n{doc[:800]}")
                        st.json(meta)
        except Exception as e:
            st.error(f"切片查询失败: {e}")

    # ── Tab 3: 入库历史记录 ───────────────────────────────────────────────────
    with tab_history:
        st.markdown("#### 📜 知识库入库审计日志")
        st.caption("系统自动记录的每次 Ingestion 操作。支持按批次一键从分层向量库中物理撤销。")
        
        if hasattr(db, 'get_ingestion_logs'):
            logs = db.get_ingestion_logs(limit=20)
        else:
            st.warning("⚠️ 数据库连接模块正在同步中，请稍后刷新页面。")
            logs = []
        if not logs:
            st.info("暂无入库记录。")
        else:
            for log in logs:
                batch_id = log['vector_ids_prefix']
                with st.container(border=True):
                    c1, c2, c3 = st.columns([5, 3, 2])
                    c1.markdown(f"📄 **{log['file_name']}**")
                    c1.caption(f"路径: `{log['l1_name']} → {log['l2_name']} → {log['l3_name']}`")
                    c2.markdown(f"🔢 切片数: **{log['chunk_count']}**")
                    c2.caption(f"参数: `大小={log['chunk_size']}, 重叠={log['chunk_overlap']}`")
                    
                    with c3:
                        pop_rev = st.popover("🗑 撤销批次", use_container_width=True)
                        pop_rev.error(f"警告：这将从向量库和数据库中物理抹除批次 `{batch_id}` 的所有切片。")
                        if pop_rev.button("确认为此批次撤库", key=f"conf_rev_{log['id']}", type="primary", use_container_width=True):
                            dp.delete_ingestion_batch(log['id'], batch_id)
                            st.success(f"已撤销批次 {batch_id}")
                            st.rerun()
                    
                    st.caption(f"操作人: {log['op_user']} | 时间: {log['created_at']}")

    # ── Tab 4: 检索策略配置 ───────────────────────────────────────────────────
    with tab_strategy:
        st.markdown("#### ⚙️ 意图分级检索策略面板")
        st.caption("可视化当前系统对于 L3 分层知识库的动态挂载与精准召回策略。")
        
        st.info("""
        **当前策略逻辑：**
        1. **Query 改写**：对用户口语化查询执行医疗术语对齐。
        2. **L3 意图挂载**：
           - 优先：关键词正则匹配三级专题名称。
           - 兜底：Qwen2.5 7B 模型进行零样本意图分类。
        3. **精准检索**：定位到特定 L3 子集执行 `where l3=...` 过滤，彻底消除跨库噪音。
        """)
        
        # 统计分布
        try:
            from data.vector_store import chroma_processor
            vp = chroma_processor.VectorProcessor()
            stats = vp.get_hierarchical_stats()
            if stats.get('has_hierarchy_data'):
                st.subheader("📊 切片分布分布 (L3 层级)")
                l3_df = pd.DataFrame(list(stats['l3_distribution'].items()), columns=['三级专题', '切片数量'])
                st.bar_chart(l3_df.set_index('三级专题'))
            else:
                st.info("暂无分级数据统计。")
        except Exception as e:
            st.error(f"统计获取失败: {e}")
