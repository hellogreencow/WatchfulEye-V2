#!/usr/bin/env python3
import os
import time
import json
import requests

API_URL = os.environ.get("WATCHFUL_API_URL", "http://localhost:5000")

# Basic smoke test for RAG freshness and retrieval
# 1) Hit /api/chat with use_rag=True for a generic query
# 2) Ensure sources exist and response text is non-empty
# 3) Optionally, re-run after a short delay to see stable behavior

def run_once(query: str = "What are the latest market risks?") -> dict:
    url = f"{API_URL}/api/chat"
    payload = {"query": query, "use_rag": True}
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    assert isinstance(data, dict)
    # expect keys: response, sources
    assert data.get("response"), "Empty response text"
    assert isinstance(data.get("sources", []), list), "Sources missing or not a list"
    return data

if __name__ == "__main__":
    print("[RAG-FRESHNESS] First query...")
    a = run_once()
    print("Response length:", len(a.get("response", "")))
    print("Num sources:", len(a.get("sources", [])))
    time.sleep(3)
    print("[RAG-FRESHNESS] Second query (stability check)...")
    b = run_once()
    print("Response length:", len(b.get("response", "")))
    print("Num sources:", len(b.get("sources", [])))
    print("OK")
