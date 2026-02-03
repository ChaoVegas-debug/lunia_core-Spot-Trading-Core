#!/usr/bin/env python3
"""
Server-side Binance Balance DUMP Script (Proof of Life) - FORENSIC EDITION
"""
import requests
import sys
import os
import json
import time

BASE_URL = "http://localhost:8080"
OPS_TOKEN = os.getenv("OPS_TOKEN", "admin-ops-key-123")
HEADER = {"X-Admin-Token": OPS_TOKEN, "X-Data-Source": "REAL"}

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def run_dump():
    log("Forensic Balance Check Initiated...", "START")
    log(f"Target: {BASE_URL}/balances", "CONFIG")
    log(f"Header: X-Data-Source=REAL", "CONFIG")

    try:
        # 1. Check Runtime Keys first (Debug)
        log("Checking Runtime Credentials via /debug...", "STEP")
        try:
            d = requests.get(f"{BASE_URL}/api/exchanges/debug", headers={"X-Admin-Token": OPS_TOKEN}, timeout=2)
            if d.status_code == 200:
                debug_info = d.json()
                k_len = debug_info.get("key_len", "N/A")
                s_len = debug_info.get("secret_len", "N/A")
                is_mock = debug_info.get("mock", "UNKNOWN")
                base_url = debug_info.get("base_url", "UNKNOWN")
                log(f"Runtime State: KeyLen={k_len}, SecretLen={s_len}, Mock={is_mock}, BaseURL={base_url}", "DEBUG")
                
                if isinstance(k_len, int) and k_len < 60:
                     log("WARNING: Key length is suspiciously short (<60). Likely invalid for Mainnet.", "WARN")
            else:
                log(f"Debug Endpoint Failed: {d.status_code}", "WARN")
        except Exception as e:
            log(f"Debug Check Failed: {e}", "WARN")

        # 2. Request Balances
        log("Requesting REAL balances...", "STEP")
        r = requests.get(f"{BASE_URL}/balances", headers=HEADER)
        
        # Metadata
        log(f"HTTP Status: {r.status_code}", "HTTP")
        data = r.json()
        
        source = data.get("source", "UNKNOWN")
        env = data.get("env", "UNKNOWN")
        req_id = data.get("request_id", "N/A")
        upstream = data.get("upstream_status", "N/A")
        time_offset = data.get("time_offset", "N/A")
        err = data.get("error", None)

        log(f"Response Metadata: Source={source} | Env={env} | Upstream={upstream} | ReqID={req_id}", "META")
        
        if source != "REAL":
            log("FATAL: Backend returned SIMULATION data despite forced REAL request!", "FAIL")
            print(json.dumps(data, indent=2))
            return

        if r.status_code == 200:
            balances = data.get("balances", [])
            log(f"Balance Fetch SUCCESS. Asset Count: {len(balances)}", "SUCCESS")
            
            non_zero = [b for b in balances if float(b['free']) > 0 or float(b['locked']) > 0]
            log(f"Non-Zero Assets: {len(non_zero)}", "INFO")
            
            print("\n----- REAL ASSET DUMP (Non-Zero) -----")
            print(f"{'ASSET':<10} | {'FREE':<20} | {'LOCKED':<20}")
            print("-" * 56)
            for b in non_zero:
                print(f"{b['asset']:<10} | {b['free']:<20} | {b['locked']:<20}")
            print("---------------------------------------")
        
        elif r.status_code in [401, 502, 403]:
             log(f"Balance Fetch FAILED (Expected Fail-Closed Behavior).", "INFO")
             log(f"Error Message: {err}", "ERROR")
             log("This confirms REAL path was attempted and rejected by upstream.", "PROOF")
        else:
             log(f"Unexpected Failure: {r.status_code}", "FAIL")
             print(json.dumps(data, indent=2))

    except Exception as e:
        log(f"CRITICAL EXCEPTION: {e}", "CRITICAL")

if __name__ == "__main__":
    run_dump()
