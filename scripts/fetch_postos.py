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

PRICE_URL = "https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/PesquisarPostos"
OUTPUT_PATH = Path("Postos.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://precoscombustiveis.dgeg.gov.pt/estatistica/postos/",
    "Origin": "https://precoscombustiveis.dgeg.gov.pt",
}

FUEL_IDS = [
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


def fetch_postos_for_fuel(fuel_id: int) -> list[dict]:
    """Fetch all stations with prices for a given fuel type."""
    session = requests.Session()
    # Get session cookies from the main page first
    session.get(
        "https://precoscombustiveis.dgeg.gov.pt/estatistica/postos/",
        headers=HEADERS,
        timeout=15
    )

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
    resp = session.get(PRICE_URL, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("resultado") or data.get("Resultado") or []
    print(f"  → {len(result)} postos")
    return result


def row_from_entry(entry: dict) -> dict:
    """Map an API JSON entry to the CSV row dict.
    Fields match exactly: Id, Nome, TipoPosto, Municipio, Preco, Marca,
    Combustivel, DataAtualizacao, Distrito, Morada, Localidade, CodPostal,
    Latitude, Longitude, Quantidade
    """
    return {
        "Nome":            entry.get("Nome", ""),
        "TipoPosto":       entry.get("TipoPosto", ""),
        "Municipio":       entry.get("Municipio", ""),
        "Preco":           entry.get("Preco", ""),  # Already in '1,599 €' format
        "Marca":           entry.get("Marca", ""),
        "Combustivel":     entry.get("Combustivel", ""),
        "DataAtualizacao": entry.get("DataAtualizacao", ""),
        "Distrito":        entry.get("Distrito", ""),
        "Morada":          entry.get("Morada", ""),
        "Localidade":      entry.get("Localidade", ""),
        "CodPostal":       entry.get("CodPostal", ""),
        "Latitude":        entry.get("Latitude", ""),
        "Longitude":       entry.get("Longitude", ""),
    }


def main():
    print("A carregar postos por combustível...")
    all_rows = []

    for fuel_id, fuel_name in FUEL_IDS:
        print(f"  {fuel_name} (id={fuel_id})", end=" ", flush=True)
        try:
            entries = fetch_postos_for_fuel(fuel_id)
            for entry in entries:
                all_rows.append(row_from_entry(entry))
        except Exception as e:
            print(f"  ERRO: {e}")
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

    # Sanity check
    prices_ok = sum(1 for r in unique_rows if r["Preco"] and r["Preco"] != "0,000 €")
    print(f"Registos com preço válido: {prices_ok}/{len(unique_rows)}")
    if prices_ok == 0:
        print("ERRO: Todos os preços estão a zero.", file=sys.stderr)
        sys.exit(1)

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
