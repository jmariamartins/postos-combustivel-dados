"""
Fetches all gas station prices from the DGEG public API and writes Postos.csv
in the format expected by the app.

CSV columns: Nome;TipoPosto;Municipio;Preco;Marca;Combustivel;DataAtualizacao;
             Distrito;Morada;Localidade;CodPostal;Latitude;Longitude
"""

import csv
import sys
import time
from pathlib import Path
import requests

BASE_URL = "https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb"
OUTPUT_PATH = Path("Postos.csv")

# Headers that mimic a real browser request — required by the DGEG server
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://precoscombustiveis.dgeg.gov.pt/estatistica/postos/",
    "Origin": "https://precoscombustiveis.dgeg.gov.pt",
}

# Hardcoded fuel IDs from DGEG — used if the dynamic fetch fails.
# These are stable and rarely change.
FALLBACK_FUEL_IDS = [
    (3,  "Gasolina simples 95"),
    (4,  "Gasolina especial 95"),
    (5,  "Gasolina especial 98"),
    (6,  "Gasóleo simples"),
    (7,  "Gasóleo especial"),
    (8,  "Gasóleo colorido e marcado"),
    (9,  "Gasóleo de aquecimento"),
    (10, "GPL auto"),
    (11, "GNC - Gás Natural Comprimido"),
    (12, "GNL - Gás Natural Liquefeito"),
    (13, "Gasolina de mistura (motores a 2 tempos)"),
    (14, "Adblue"),
    (15, "Hidrogénio"),
]


def get_fuel_ids() -> list[tuple[int, str]]:
    """Try to fetch fuel types dynamically; fall back to hardcoded list."""
    url = f"{BASE_URL}/GetCombustiveis?idioma=0"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        print(f"  HTTP {resp.status_code} | Content-Type: {resp.headers.get('Content-Type', '?')}")
        data = resp.json()
        fuels = data if isinstance(data, list) else data.get("resultado") or data.get("items") or []
        result = [(item["Id"], item.get("Nome", "")) for item in fuels if "Id" in item]
        if result:
            print(f"  Combustíveis obtidos da API: {len(result)}")
            return result
        print("  API devolveu lista vazia — a usar lista predefinida.")
    except Exception as e:
        print(f"  Não foi possível obter combustíveis da API ({e}) — a usar lista predefinida.")

    print(f"  A usar {len(FALLBACK_FUEL_IDS)} combustíveis predefinidos.")
    return FALLBACK_FUEL_IDS


def fetch_postos_for_fuel(fuel_id: int) -> list[dict]:
    """Fetch all stations for a given fuel type ID."""
    url = f"{BASE_URL}/ListarDadosPostos"
    params = {
        "idioma": 0,
        "tipoPosto": "",
        "combustivel": fuel_id,
        "marca": "",
        "distrito": "",
        "municipio": "",
        "qtdPorPagina": 9999,
        "pagina": 1,
    }
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("resultado") or data.get("Resultado") or []
    print(f"  → {len(result)} postos")
    return result


def format_price(raw) -> str:
    """Convert a price value to the '1,599 €' string format the app expects."""
    if raw is None:
        return ""
    try:
        num = float(str(raw).replace(",", ".").replace("€", "").strip())
        return f"{num:.3f} €".replace(".", ",")
    except ValueError:
        return str(raw)


def format_date(raw) -> str:
    """Normalise date strings — keep first 16 chars (YYYY-MM-DD HH:MM)."""
    return str(raw)[:16] if raw else ""


def row_from_entry(entry: dict) -> dict:
    """Map an API JSON entry to the CSV row dict."""
    return {
        "Nome":            entry.get("Nome") or entry.get("name") or "",
        "TipoPosto":       entry.get("TipoPosto") or entry.get("stationType") or "",
        "Municipio":       entry.get("Municipio") or entry.get("municipality") or "",
        "Preco":           format_price(entry.get("Preco") or entry.get("price")),
        "Marca":           entry.get("Marca") or entry.get("brand") or "",
        "Combustivel":     entry.get("Combustivel") or entry.get("fuelType") or "",
        "DataAtualizacao": format_date(entry.get("DataAtualizacao") or entry.get("updateDate")),
        "Distrito":        entry.get("Distrito") or entry.get("district") or "",
        "Morada":          entry.get("Morada") or entry.get("address") or "",
        "Localidade":      entry.get("Localidade") or entry.get("locality") or "",
        "CodPostal":       entry.get("CodPostal") or entry.get("zipCode") or "",
        "Latitude":        entry.get("Latitude") or entry.get("latitude") or "",
        "Longitude":       entry.get("Longitude") or entry.get("longitude") or "",
    }


def main():
    print("A obter lista de combustíveis...")
    fuels = get_fuel_ids()

    print("\nA carregar postos por combustível...")
    all_rows = []
    for fuel_id, fuel_name in fuels:
        print(f"  {fuel_name} (id={fuel_id})", end=" ", flush=True)
        try:
            entries = fetch_postos_for_fuel(fuel_id)
            for entry in entries:
                all_rows.append(row_from_entry(entry))
        except Exception as e:
            print(f"  ERRO ao carregar fuel {fuel_id}: {e}")
        time.sleep(0.5)

    if not all_rows:
        print("ERRO: Nenhum dado recebido da API.", file=sys.stderr)
        sys.exit(1)

    # Deduplicate by (name + fuel type)
    seen = set()
    unique_rows = []
    for row in all_rows:
        key = (row["Nome"], row["Combustivel"])
        if key not in seen:
            seen.add(key)
            unique_rows.append(row)

    print(f"\nTotal: {len(unique_rows)} registos únicos")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "Nome", "TipoPosto", "Municipio", "Preco", "Marca",
        "Combustivel", "DataAtualizacao", "Distrito", "Morada",
        "Localidade", "CodPostal", "Latitude", "Longitude",
    ]

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";",
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(unique_rows)

    print(f"Ficheiro guardado em: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
