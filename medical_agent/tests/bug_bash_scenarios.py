
import sys
import os
import json
import time

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.agent import medical_agent_app

def run_scenario(name, queries):
    print(f"\n{'='*20} SCENARIO: {name} {'='*20}")
    history = []
    session_id = f"bash_{int(time.time())}"
    
    for i, q in enumerate(queries):
        print(f"\n[Turn {i+1}] User: {q}")
        state = {
            "session_id": session_id,
            "original_query": q,
            "history": history,
            "expert_advice": [],
            "retrieved_docs": [],
            "doc_sources": [],
            "graph_context": []
        }
        t0 = time.time()
        res = medical_agent_app.invoke(state)
        elapsed = time.time() - t0
        
        print(f"--- Thought Process ({elapsed:.2f}s) ---")
        print(f"Resolved Query: {res.get('resolved_query')}")
        print(f"Decomposed Queries: {res.get('decomposed_queries')}")
        print(f"--- final_answer ---")
        print(res.get('final_answer'))
        
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": res.get('final_answer')})

def main():
    # Scenario A: The "Wife + Headache" Image 1 & 3 failure
    # Goal: Verify NO "Suzhou 5th Hospital" or "Liver indicators" hallucination.
    run_scenario("A: Multi-intent & Context Resolution", [
        "我头痛，我老婆孕晚期。帮我看看她的肚子发紧发硬是怎么回事？",
        "那我老婆应该挂什么科"
    ])
    
    # Scenario B: Relevance & Anti-hallucination (Image 2 failure)
    # Goal: Verify NO "1-year dizziness" analysis if not mentioned.
    run_scenario("B: Irrelevance & Hallucination Defense", [
        "我头很痛，没有给回复"
    ])

if __name__ == "__main__":
    main()
