
import sys
import os
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.agent import medical_agent_app

def test_multi_turn():
    session_id = "medcac_test_session"
    history = []
    
    # Turn 1: Multi-intent
    query1 = "我头疼，我老婆肚子发紧发硬，我们应该怎么办？"
    print(f"\n--- Turn 1: {query1} ---")
    state1 = {
        "session_id": session_id,
        "original_query": query1,
        "history": history,
        "expert_advice": [],
        "retrieved_docs": [],
        "doc_sources": [],
        "graph_context": [],
        "patient_profile": {}
    }
    res1 = medical_agent_app.invoke(state1)
    print(f"Resolved Query: {res1.get('resolved_query')}")
    print(f"Intents: {[q['intent'] for q in res1.get('decomposed_queries', [])]}")
    print(f"Answer: {res1.get('final_answer')[:200]}...")
    
    # Update history
    history.append({"role": "user", "content": query1})
    history.append({"role": "assistant", "content": res1.get("final_answer")})
    
    # Turn 2: Coreference Resolution (Wife)
    query2 = "那针对我老婆的情况，应该挂什么号？"
    print(f"\n--- Turn 2: {query2} ---")
    state2 = {
        "session_id": session_id,
        "original_query": query2,
        "history": history,
        "expert_advice": [],
        "retrieved_docs": [],
        "doc_sources": [],
        "graph_context": [],
        "patient_profile": res1.get("patient_profile", {})
    }
    res2 = medical_agent_app.invoke(state2)
    print(f"Resolved Query: {res2.get('resolved_query')}")
    print(f"Answer: {res2.get('final_answer')[:200]}...")
    
    # Turn 3: Coreference Resolution (Me)
    query3 = "那我呢？"
    print(f"\n--- Turn 3: {query3} ---")
    state3 = {
        "session_id": session_id,
        "original_query": query3,
        "history": history + [{"role": "user", "content": query2}, {"role": "assistant", "content": res2.get("final_answer")}],
        "expert_advice": [],
        "retrieved_docs": [],
        "doc_sources": [],
        "graph_context": [],
        "patient_profile": res2.get("patient_profile", {})
    }
    res3 = medical_agent_app.invoke(state3)
    print(f"Resolved Query: {res3.get('resolved_query')}")
    print(f"Answer: {res3.get('final_answer')[:200]}...")

if __name__ == "__main__":
    test_multi_turn()
