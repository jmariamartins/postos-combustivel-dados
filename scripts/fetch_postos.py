"""
Diagnostic script — tries multiple DGEG endpoints and prints raw responses
so we can identify the correct one for price data.
"""

import sys
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://precoscombustiveis.dgeg.gov.pt/estatistica/postos/",
    "Origin": "https://precoscombustiveis.dgeg.gov.pt",
}

BASE = "https://precoscombustiveis.dgeg.gov.pt"

PARAMS = {
    "idioma": 0,
    "tipoPosto": "",
    "combustivel": 6,  # Gasóleo simples — common fuel, likely to return results
    "marca": "",
    "distrito": "",
    "municipio": "",
    "qtdPorPagina": 5,  # Only 5 results for diagnostic
    "pagina": 1,
}

# Candidate endpoints to test
ENDPOINTS = [
    f"{BASE}/api/PrecoCombustivel/GetListPostos",
    f"{BASE}/api/PrecoComb/GetListPostos",
    f"{BASE}/api/PrecoComb/PesquisarPostos",
    f"{BASE}/api/PrecoCombustivel/PesquisarPostos",
    f"{BASE}/api/PrecoComb/GetPrecos",
    f"{BASE}/api/PrecoCombustivel/GetPrecos",
]

def test_endpoint(url: str):
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    try:
        # First try with a session (gets cookies from main page)
        session = requests.Session()
        session.get(f"{BASE}/estatistica/postos/", headers=HEADERS, timeout=15)
        
        resp = session.get(url, params=PARAMS, headers=HEADERS, timeout=30)
        print(f"  Status: {resp.status_code}")
        print(f"  Content-Type: {resp.headers.get('Content-Type', '?')}")
        print(f"  Response length: {len(resp.text)} chars")
        print(f"  First 300 chars: {resp.text[:300]}")
        
        # Try parsing as JSON
        try:
            data = resp.json()
            print(f"  ✅ Valid JSON! Keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
            items = data.get("resultado") or data.get("Resultado") or data.get("items") or (data if isinstance(data, list) else [])
            if items:
                print(f"  First item keys: {list(items[0].keys())}")
        except Exception as e:
            print(f"  ❌ Not valid JSON: {e}")

    except Exception as e:
        print(f"  ❌ Request failed: {e}")

def main():
    print("DGEG Endpoint Diagnostic\n")
    
    # Also test the one we know returns data, with session cookies
    print("Testing known working endpoint WITH session cookies:")
    test_endpoint(f"{BASE}/api/PrecoComb/ListarDadosPostos")
    
    for url in ENDPOINTS:
        test_endpoint(url)

if __name__ == "__main__":
    main()
