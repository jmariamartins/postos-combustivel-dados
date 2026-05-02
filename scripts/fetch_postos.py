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

# Correct endpoint for price searches (different from ListarDadosPostos which is registry data)
PRICE_URL = "https://precoscombustiveis.dgeg.gov.pt/api/PrecoCombustivel/GetListPostos"
OUTPUT_PATH = Path("Postos.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://precoscombustiveis.dgeg.gov.pt/estatistica/postos/",
    "Origin": "https://precoscombustiveis.dgeg.gov.pt",
}

# Fuel type IDs — one request per fuel type
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


def fetch_postos_for_fuel(fuel_id: int, fuel_name: str) -> list[dict]:
    """Fetch all stations with prices for a given fuel type."""
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
    resp = requests.get(PRICE_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    # DEBUG: show raw response on first fuel only
    if fuel_id == FUEL_IDS[0][0]:
        print(f"\n  DEBUG raw keys: {list(resp.json().keys())}")
        result_sample = (resp.json().get("resultado") or resp.json().get("Resultado") or [])
        if result_sample:
            print(f"  DEBUG first entry: {result_sample[0]}")

    data = resp.json()
    entries = data.get("resultado") or data.get("Resultado") or data.get("items") or []

    # Inject fuel name since the entry may not include it
    for e in entries:
        if not e.get("Combustivel") and not e.get("fuelType"):
            e["_fuelName"] = fuel_name

    print(f"  → {len(entries)} postos")
    return entries


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
        "TipoPosto":       entry.get("TipoPosto") or entry.get("stationType") or entry.get("TipoPostoDescritivo") or "",
        "Municipio":       entry.get("Municipio") or entry.get("municipality") or entry.get("MunicipioDescritivo") or "",
        "Preco":           format_price(entry.get("Preco") or entry.get("preco") or entry.get("price") or entry.get("Preco1") or entry.get("PrecoFormatado")),
        "Marca":           entry.get("Marca") or entry.get("brand") or entry.get("MarcaDescritivo") or "",
        "Combustivel":     entry.get("Combustivel") or entry.get("fuelType") or entry.get("CombustivelDescritivo") or entry.get("_fuelName") or "",
        "DataAtualizacao": format_date(entry.get("DataAtualizacao") or entry.get("DataAtualizacaoPreco") or entry.get("updateDate") or entry.get("DataRegisto")),
        "Distrito":        entry.get("Distrito") or entry.get("district") or entry.get("DistritoDescritivo") or "",
        "Morada":          entry.get("Morada") or entry.get("address") or "",
        "Localidade":      entry.get("Localidade") or entry.get("locality") or "",
        "CodPostal":       entry.get("CodPostal") or entry.get("zipCode") or "",
        "Latitude":        entry.get("Latitude") or entry.get("latitude") or "",
        "Longitude":       entry.get("Longitude") or entry.get("longitude") or "",
    }


def main():
    print(f"A usar endpoint: {PRICE_URL}\n")
    print("A carregar postos por combustível...")
    all_rows = []

    for fuel_id, fuel_name in FUEL_IDS:
        print(f"  {fuel_name} (id={fuel_id})", end=" ", flush=True)
        try:
            entries = fetch_postos_for_fuel(fuel_id, fuel_name)
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

    # Quick sanity check — warn if prices look wrong
    prices_ok = sum(1 for r in unique_rows if r["Preco"] and r["Preco"] != "0,000 €")
    print(f"Registos com preço válido: {prices_ok}/{len(unique_rows)}")
    if prices_ok == 0:
        print("AVISO: Todos os preços estão a zero — verificar endpoint ou campos da API.")

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
