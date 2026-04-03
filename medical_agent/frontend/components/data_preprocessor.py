import streamlit as st
import pandas as pd
import json
import io
from langchain_ollama import OllamaLLM
from config.settings import LLM_MODEL
import pdfplumber
import docx

def extract_text_from_file(uploaded_file):
    name = uploaded_file.name.lower()
    text = ""
    try:
        if name.endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
        elif name.endswith('.docx'):
            doc = docx.Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            text = uploaded_file.getvalue().decode("utf-8")
    except Exception as e:
        st.error(f"文件读取失败: {str(e)}")
    return text

def render_data_preprocessor():
    st.markdown("<span style='color: #86909c; font-size: 14px;'>使用本地大语言模型将复杂的长文档 (PDF/Word) 预处理、清洗和拆解为标准的一问一答 (Q&A) 表格数据，以便直接作为高质量逻辑切片灌入底层图谱库。</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.subheader("1. 原始医疗长文接入 (支持非结构化版 PDF/Word)")
    uploaded_file = st.file_uploader("上传待解析的文件 (非结构化纯文本或混杂段落)", type=['pdf', 'docx', 'txt'])
    
    raw_text = ""
    if uploaded_file:
        with st.spinner("系统正在进行 OCR 与结构化萃取流提取..."):
            raw_text = extract_text_from_file(uploaded_file)
        st.success(f"成功萃取物理文字：共计 {len(raw_text)} 字。")
        with st.expander("预览底层提取文本流 (前500字)"):
            st.write(raw_text[:500] + "...")
            
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("2. 大模型微调清洗控制台与指令护栏 (Prompt)")
    
    default_prompt = """你是一个结构严谨、逻辑清晰的【高级医疗数据标注与清洗专家】。
你的任务是将用户提供的一段非结构化医学长文本，精准提炼为标准的 Q&A 问答对齐格式，使其能被后续图谱系统高保真入库。

## 核心提取约束
1. 指代明确补全：任何涉及代词的地方，必须根据上下文补全为完整的医疗专有名词。
2. 实体穷尽不遗漏：绝对不能遗漏文本中的核心症状、用药指南与禁忌症。
3. 严格遵循 JSON 格式返回：不可包裹任何 markdown (如 ```json) 也不允许输出任何其他分析文字。

## 强制返回格式 (JSON Array)：
[
    {
        "query": "什么是妊娠期高血压？",
        "answer": "妊娠期高血压是指孕妇在怀孕期间出现的血压异常升高现象，通常伴有..."
    },
    {
        "query": "妊娠期高血压的日常处理干预有哪些？",
        "answer": "1. 居家每日监测血压情况；2. 控制摄入钠盐；3. 定期进行产检评估..."
    }
]"""

    system_prompt = st.text_area(
        "高质量数据预处理指令舱 (支持灵活调优 Prompt 规则，越详尽抽取效果越好)", 
        value=default_prompt,
        height=350
    )
        
    st.markdown("---")
    
    if st.button("全马力启动大模型流水线洗练 (LLM Extract Pipeline)", type="primary", disabled=not uploaded_file):
        if raw_text:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Simple chunking for LLM processing context window limits
            chunk_size = 1500
            chunks = [raw_text[i:i+chunk_size] for i in range(0, len(raw_text), chunk_size)]
            
            all_qa_pairs = []
            
            llm = OllamaLLM(model=LLM_MODEL, temperature=0.0)
            
            for i, chunk in enumerate(chunks):
                status_text.text(f"🚀 正在调度本地超级模型 {LLM_MODEL} 引擎清洗第 {i+1}/{len(chunks)} 个数据沙盒块...")
                prompt = f"{system_prompt}\n\n待处理的医疗长文本片段如下：\n{chunk}"
                
                try:
                    response = llm.invoke(prompt)
                    # 清理 markdown json wrap
                    clean_res = response.strip()
                    if clean_res.startswith("```json"):
                        clean_res = clean_res[7:]
                    elif clean_res.startswith("```"):
                        clean_res = clean_res[3:]
                    if clean_res.endswith("```"):
                        clean_res = clean_res[:-3]
                    
                    batch_qa = json.loads(clean_res.strip())
                    if isinstance(batch_qa, list):
                        all_qa_pairs.extend(batch_qa)
                except json.JSONDecodeError as jde:
                    st.warning(f"跳过处理区块 {i+1}：大模型未能遵守强 JSON 返回约束。")
                except Exception as e:
                    st.error(f"模型引擎计算超时崩溃: {str(e)}")
                    
                progress_bar.progress((i + 1) / len(chunks))
                
            status_text.text("🎉 数据流清洗重构工程完成！")
            
            if all_qa_pairs:
                st.subheader("3. 终态结构化双链表格 (可以直接交由左侧【词库及切片处理】导入打散)")
                df = pd.DataFrame(all_qa_pairs)
                st.dataframe(df, use_container_width=True)
                
                # Export to Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Medical_QA_Dataset')
                processed_data = output.getvalue()
                
                st.download_button(
                    label="📥 打包下载制成后的 Excel 标准结构库",
                    data=processed_data,
                    file_name=f"Refined_QA_{uploaded_file.name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            else:
                st.error("未能从文中提炼出任何标准 Q&A 对，请调整文本源或增加片段浓度。")
