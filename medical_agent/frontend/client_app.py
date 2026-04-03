import streamlit as st
import requests
import json
import time
import os
import uuid
from dotenv import load_dotenv
import sys

load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:8000")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── UI 配置 ───────────────────────────────────────────────────────────────────
st.set_page_config(page_title="您的 AI 医疗健康伙伴", page_icon="💖", layout="centered")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #f2f5fa; }
    .stApp header { background-color: transparent; }
    * { font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif; }

    /* 顶部医疗信任横幅 */
    .trust-banner {
        background: linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%);
        padding: 14px 20px;
        border-radius: 10px;
        color: #0d47a1;
        font-weight: 600;
        font-size: 14px;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 25px;
        border-left: 5px solid #1976d2;
    }

    /* 底部免责声明 */
    .disclaimer {
        font-size: 11.5px;
        color: #90a4ae;
        text-align: center;
        margin-top: 50px;
        padding-top: 20px;
        border-top: 1px solid #cfd8dc;
        line-height: 1.8;
    }

    /* 正向反馈确认徽章 */
    .feedback-positive {
        display: inline-block;
        color: #00a854;
        font-size: 13px;
        font-weight: 500;
        padding: 4px 12px;
        background: #f0faf5;
        border-radius: 20px;
        border: 1px solid #b7ebd5;
        margin-top: 8px;
    }

    /* 负向反馈确认徽章 */
    .feedback-negative {
        display: inline-block;
        color: #ff6b35;
        font-size: 13px;
        font-weight: 500;
        padding: 4px 12px;
        background: #fff5f0;
        border-radius: 20px;
        border: 1px solid #ffd0b5;
        margin-top: 8px;
    }

    /* 通用按钮 */
    .stButton > button {
        border-radius: 6px !important;
        font-size: 13px !important;
        transition: all 0.2s ease !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="trust-banner">🏥 卫健委/三甲医院知识联合支持 · 全天候为您提供权威科普与健康护航</div>', unsafe_allow_html=True)


# ── 辅助函数：提交反馈至后端 API ──────────────────────────────────────────────
def submit_feedback(log_id: int, feedback_type: str, query: str = "", ai_response: str = "",
                    reason: str = "", detail: str = "") -> bool:
    """
    向后端 /feedback 接口提交用户反馈，实现前后端分层解耦。
    若后端不可达则降级直接写 DB，确保反馈数据不丢失。
    """
    try:
        payload = {
            "log_id": log_id,
            "feedback_type": feedback_type,
            "query": query,
            "ai_response": ai_response,
            "reason": reason,
            "detail": detail,
        }
        resp = requests.post(f"{API_URL}/feedback", json=payload, timeout=5)
        return resp.json().get("success", False)
    except Exception:
        # NOTE: 降级兜底 — 后端不可达时直接写 DB 防止反馈丢失
        try:
            from backend.repository import mysql_mgr as db_mgr
            db_mgr.update_interaction_feedback(log_id, feedback_type)
            if feedback_type == "negative":
                full = reason + (f"；{detail}" if detail else "")
                db_mgr.add_bad_case(query, ai_response, full, log_id=log_id)
            return True
        except Exception:
            return False


# ── Session 状态初始化 ────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "patient_messages" not in st.session_state:
    st.session_state.patient_messages = [
        {
            "role": "assistant",
            "content": "您好！我是您的**专属 AI 健康科普伙伴** 🩺\n\n我可以帮您解答疾病科普、解读体检指标或规划就医科室。请用平常的口语向我描述您的疑问或不适。"
        }
    ]

# NOTE: feedback_state 字典以消息 idx 为键，记录每条 AI 消息的反馈状态，
#       防止 Streamlit 重渲染时重复提交，可取值：None/"positive"/"form_open"/"submitted"
if "feedback_state" not in st.session_state:
    st.session_state.feedback_state = {}


# ── 渲染消息历史 ──────────────────────────────────────────────────────────────
for idx, msg in enumerate(st.session_state.patient_messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # 仅对携带 log_id 的 AI 回答消息渲染反馈区块
        if msg["role"] == "assistant" and msg.get("log_id"):
            log_id = msg["log_id"]
            state = st.session_state.feedback_state.get(idx)

            # ── 已正向反馈：显示绿色确认徽章 ────────────────────────────────
            if state == "positive":
                st.markdown('<span class="feedback-positive">✅ 已采纳，感谢您的认可！</span>', unsafe_allow_html=True)

            # ── 负向表单已提交：显示橙色上报确认徽章 ─────────────────────────
            elif state == "submitted":
                st.markdown('<span class="feedback-negative">🚨 已上报至专家组，感谢您帮助我们改进！</span>', unsafe_allow_html=True)

            # ── 负向反馈表单展开中 ────────────────────────────────────────────
            elif state == "form_open":
                with st.form(key=f"feedback_form_{idx}", clear_on_submit=True):
                    st.markdown("**📝 请告诉我们哪里需要改进**")
                    reason = st.radio(
                        "反馈原因",
                        options=["答非所问", "内容有误", "信息不足", "缺乏依据", "其他"],
                        horizontal=True,
                        key=f"reason_{idx}",
                    )
                    detail = st.text_area(
                        "补充说明（可选）",
                        placeholder="请描述您期待的正确答案或改进方向...",
                        max_chars=500,
                        key=f"detail_{idx}",
                    )
                    col_submit, col_cancel, _ = st.columns([1, 1, 3])
                    submitted = col_submit.form_submit_button("📨 提交反馈", type="primary", use_container_width=True)
                    cancelled = col_cancel.form_submit_button("取消", use_container_width=True)

                    if submitted:
                        # 向前回溯找到该 AI 消息对应的用户提问
                        prev_user_msg = ""
                        for m in reversed(st.session_state.patient_messages[:idx]):
                            if m["role"] == "user":
                                prev_user_msg = m["content"]
                                break
                        submit_feedback(
                            log_id=log_id,
                            feedback_type="negative",
                            query=prev_user_msg,
                            ai_response=msg["content"],
                            reason=reason,
                            detail=detail,
                        )
                        st.session_state.feedback_state[idx] = "submitted"
                        st.rerun()

                    if cancelled:
                        st.session_state.feedback_state[idx] = None
                        st.rerun()

            # ── 初始状态：显示 👍 / 👎 两个操作按钮 ──────────────────────────
            else:
                f_cols = st.columns([1, 1, 8])
                if f_cols[0].button("👍 有用", key=f"up_{idx}", help="回答准确，对我有帮助"):
                    submit_feedback(log_id=log_id, feedback_type="positive")
                    st.session_state.feedback_state[idx] = "positive"
                    st.rerun()
                if f_cols[1].button("👎 有误", key=f"down_{idx}", help="回答有误，我想提供反馈"):
                    st.session_state.feedback_state[idx] = "form_open"
                    st.rerun()


# ── 快速场景引导（首次对话时展示）───────────────────────────────────────────
quick_prompt = None
if len(st.session_state.patient_messages) == 1:
    st.markdown("### 💡 快速医疗场景引导")
    col1, col2, col3 = st.columns(3)
    if col1.button("🤰 孕期关怀指南"):
        quick_prompt = "孕产妇在怀孕初期肚子发紧正常吗？有哪些注意事项？"
    if col2.button("🩸 慢病指标解读"):
        quick_prompt = "高血压患者日常应该怎么控制饮食和监测异常？"
    if col3.button("🏥 急救与首诊指引"):
        quick_prompt = "我的胃突然像针扎一样刺痛，而且在冒冷汗，这算急性病吗？该去医院的哪个科室？"


# ── Chat 输入与流式回答 ───────────────────────────────────────────────────────
prompt = st.chat_input("您可以这样问：我最近总觉得头昏脑胀，该去医院挂什么科？")
actual_prompt = quick_prompt or prompt

if actual_prompt:
    st.session_state.patient_messages.append({"role": "user", "content": actual_prompt})
    with st.chat_message("user"):
        st.markdown(actual_prompt)

    with st.chat_message("assistant"):
        def stream_response_generator():
            payload = {
                "query": actual_prompt,
                "session_id": st.session_state.session_id,
                "history": [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.patient_messages[:-1]
                ],
            }
            full_ans = ""
            try:
                with requests.post(f"{API_URL}/stream", json=payload, stream=True) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if line:
                            decoded = line.decode("utf-8")
                            if decoded.startswith("data: "):
                                content = decoded[6:]
                                if content == "[DONE]":
                                    break
                                try:
                                    data = json.loads(content)
                                    node = data.get("node")

                                    # 🎯 从后端流推中捕获 log_id，供后续反馈绑定使用
                                    if "log_id" in data:
                                        st.session_state.current_log_id = data["log_id"]

                                    if node == "router":
                                        yield "⏳ *[AI 正潜入多模态图谱，飞速重组您的病理答案...]* \n\n"
                                        msg_text = data.get("message", "")
                                        if msg_text and msg_text not in ["", "处理中..."]:
                                            for char in msg_text:
                                                full_ans += char
                                                yield char
                                                time.sleep(0.01)
                                    elif node == "generator":
                                        msg_text = data.get("message", "")
                                        if msg_text and msg_text not in ["", "处理中..."]:
                                            for char in msg_text:
                                                full_ans += char
                                                yield char
                                                time.sleep(0.01)
                                except json.JSONDecodeError:
                                    pass
            except requests.exceptions.ConnectionError:
                yield "🔴 **暂时无法连接到后端服务**，请确认服务已启动后刷新页面重试。\n\n> 💡 提示：可在终端执行 `bash run.sh` 重启服务"
            except requests.exceptions.Timeout:
                yield "⏳ **请求超时**，服务器可能正在处理大量请求。请稍等片刻后重新提问。"
            except Exception as e:
                yield f"🔴 **服务异常**，请稍后再试。\n\n> 错误详情: {str(e)[:100]}"

        full_response = st.write_stream(stream_response_generator())

    log_id = st.session_state.get("current_log_id")
    st.session_state.patient_messages.append({
        "role": "assistant",
        "content": full_response,
        "log_id": log_id,
    })

    st.rerun()


st.markdown(
    '<div class="disclaimer">⚠️ 医疗免责声明：本模块提供的全部内容（含AI智能问诊、病理切片检索、指标判定等）'
    '绝对仅用于健康医疗科普。它不能作为确诊的临床依据，更无法替代人类专家的当面面诊与处方开具。'
    '在发生紧急严重病征时（如昏厥、阵发性刺痛、大出血脱水），请立刻拨打 120 急救中心求助。'
    '本平台谢绝担负由此引发的医疗风险责任。</div>',
    unsafe_allow_html=True,
)
