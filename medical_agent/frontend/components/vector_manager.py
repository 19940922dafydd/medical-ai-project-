import streamlit as st
import chromadb
import pandas as pd
import plotly.express as px
from config.settings import CHROMA_DB_PATH

def render_vector_manager():
    st.markdown("<span style='color: #86909c; font-size: 14px;'>在此处监控 ChromaDB 系统库中所有的底层文本切片，提供「Jump-to-Fix」语义溯源与 WYSIWYG 原位修复能力。</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collections = client.list_collections()
        
        if not collections:
            st.warning("尚未检测到任何向量集合，请先进行知识库导入。")
            return

        selected_collection_name = st.selectbox("当前映射集合簇", options=[c.name for c in collections])
        collection = client.get_collection(name=selected_collection_name)
        count = collection.count()
        
        # 🔗 Jump-to-Fix Logic: 处理来自 Bad Case 页面的跳转
        jump_query = st.session_state.get('jump_to_vector_query')
        jump_log_id = st.session_state.get('jump_to_log_id')
        
        st.metric(label="当前集合内持有向量片段总数", value=f"{count:,}")
        
        tab1, tab2, tab3 = st.tabs(["📚 语义切片原位修复", "🔍 穿透式语义检索溯源", "📊 数据拓扑分布"])
        
        with tab1:
            page_size = 10
            page = st.number_input("深层分页页码", min_value=1, value=1)
            start_idx = (page - 1) * page_size
            
            results = collection.get(limit=page_size, offset=start_idx, include=["documents", "metadatas"])
            
            if results and results.get("documents"):
                for i, (doc, meta, doc_id) in enumerate(zip(results["documents"], results["metadatas"], results["ids"])):
                    with st.container(border=True):
                        col_text, col_edit = st.columns([4, 1])
                        with col_text:
                            st.markdown(f"**ID:** `{doc_id}` | **来源:** `{meta.get('source', '未知')}`")
                            st.text_area("切片内容", value=doc, height=100, key=f"txt_{doc_id}", disabled=True)
                        
                        with col_edit:
                            with st.popover("📝 修正内容", use_container_width=True):
                                new_doc = st.text_area("修正后的知识描述", value=doc, key=f"edit_txt_{doc_id}")
                                # 展平 Metadata 供编辑
                                st.write("---")
                                new_meta = {}
                                for k, v in meta.items():
                                    new_meta[k] = st.text_input(f"元数据: {k}", value=str(v), key=f"meta_{doc_id}_{k}")
                                
                                if st.button("保存修正", key=f"save_{doc_id}", type="primary"):
                                    collection.update(
                                        ids=[doc_id],
                                        documents=[new_doc],
                                        metadatas=[new_meta]
                                    )
                                    st.success("底层切片已刷新！")
                                    st.rerun()
            else:
                st.info("当前页无截留数据。")
                    
        with tab2:
            st.subheader("全链路溯源测试 (溯源推演沙盒)")
            
            # 如果是跳转过来的，自动填充查询
            default_q = jump_query if jump_query else ""
            test_query = st.text_input("输入查询语句或不良反馈疑问句", value=default_q)
            
            if jump_query:
                st.warning(f"⚠️ 正在处理来自 Bad Case 的溯源追踪请求: `{jump_query}`")

            if test_query:
                from langchain_ollama import OllamaEmbeddings
                from config.settings import EMBEDDING_MODEL
                embedder = OllamaEmbeddings(model=EMBEDDING_MODEL)
                query_vector = embedder.embed_query(test_query)
                
                results = collection.query(
                    query_embeddings=[query_vector],
                    n_results=5,
                    include=["documents", "metadatas", "distances"]
                )
                
                for i, (doc, meta, distance, doc_id) in enumerate(zip(results["documents"][0], results["metadatas"][0], results["distances"][0], results["ids"][0])):
                    with st.container(border=True):
                        st.markdown(f"**召回切片 {i+1}** (欧式距离: `{distance:.4f}`)")
                        st.write(doc)
                        st.caption(f"来源: {meta.get('source', '未知')} | ID: {doc_id}")
                        
                        # 提供原位修正按钮
                        with st.popover("🎯 针对该错误召回进行原位微调"):
                            edit_doc = st.text_area("修改切片以修正模型幻觉", value=doc, key=f"q_edit_{doc_id}")
                            if st.button("提交修正", key=f"q_save_{doc_id}"):
                                collection.update(ids=[doc_id], documents=[edit_doc])
                                st.success("修正已落库！")
                                
            if st.button("清除跳转上下文"):
                if 'jump_to_vector_query' in st.session_state:
                    del st.session_state['jump_to_vector_query']
                st.rerun()
                        
        with tab3:
            all_metas = collection.get(include=["metadatas"]).get("metadatas", [])
            if all_metas:
                sources = [m.get("source", "未知") for m in all_metas]
                from collections import Counter
                counts = Counter(sources)
                df = pd.DataFrame({"来源核心文件": list(counts.keys()), "裂变切片数量": list(counts.values())})
                fig = px.pie(df, names='来源核心文件', values='裂变切片数量', hole=0.4,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("尚无图表组装所需底层数据分布结构。")
    except Exception as e:
        st.error(f"严重级断联：挂载 ChromaDB 底层向量库引擎出现死锁或阻断: {str(e)}")
    except Exception as e:
        st.error(f"严重级断联：挂载 ChromaDB 底层向量库引擎出现死锁或阻断: {str(e)}")
