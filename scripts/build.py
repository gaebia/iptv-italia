#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GAEBIA IPTV - pulizia della playlist personale.

Sorgente: playlist_sorgente.m3u8
Output:   playlist_italia.m3u8

Lo script NON scarica Free-TV e NON ricostruisce la numerazione.
Mantiene ordine, tvg-chno, tvg-id, loghi, intestazione EPG e URL originali.
Rimuove esclusivamente: canali RTL, radio, cartoni, religiosi ed economico-finanziari.
"""

import re
import unicodedata
from pathlib import Path
from collections import Counter

SOURCE = Path("playlist_sorgente.m3u8")
OUTPUT = Path("playlist_italia.m3u8")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def get_group(info: str) -> str:
    match = re.search(r'group-title="([^"]*)"', info, re.IGNORECASE)
    return normalize(match.group(1)) if match else ""


def removal_reason(info: str, name: str):
    n = normalize(name)
    words = set(n.split())
    group = get_group(info)

    # Tutti i canali del marchio RTL, non soltanto RTL 102.5.
    if "rtl" in words:
        return "RTL"

    # Tutte le radio, comprese quelle che nel nome terminano con TV.
    if "radio" in words or "radio" in group.split():
        return "radio"

    # Canali per bambini/cartoni, inclusi i franchise con nomi propri.
    cartoon_terms = {
        "boing", "cartoon", "cartoonito", "disney", "nickelodeon",
        "nick jr", "nickelodeon jr", "baby tv", "babytv", "k2",
        "frisbee", "rai gulp", "rai yoyo", "raiyoyo", "yoyo",
        "teenage mutant ninja turtles", "turtles", "tartarughe ninja"
    }
    if any(normalize(term) in n for term in cartoon_terms):
        return "cartoni"

    # Canali esplicitamente religiosi.
    religious_terms = (
        "religios", "religion", "religious", "chiesa", "cristian",
        "cattolic", "padre pio", "telepace", "vatican", "marian",
        "god tv", "eWTN".lower()
    )
    if any(term in n or term in group for term in religious_terms):
        return "religiosi"

    # Canali economici/finanziari; non rimuove televendite o shopping.
    economic_terms = (
        "economia", "economy", "finanza", "finanzi", "borsa",
        "business news", "financial", "finance", "stock market",
        "trading", "investimenti"
    )
    if any(term in n or term in group for term in economic_terms):
        return "economici"

    return None


def read_entries(lines):
    """Restituisce intestazione e blocchi canale, senza alterare le righe."""
    header = []
    entries = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if not line.startswith("#EXTINF"):
            if not entries:
                header.append(line)
            i += 1
            continue

        start = i
        i += 1
        # Include metadati supplementari e URL del canale.
        while i < len(lines) and not lines[i].startswith("#EXTINF"):
            i += 1
        block = lines[start:i]
        info = block[0]
        name = info.split(",", 1)[1].strip() if "," in info else ""
        entries.append((info, name, block))

    return header, entries


def main():
    if not SOURCE.is_file():
        raise SystemExit(
            f"ERRORE: non trovo {SOURCE}. "
            "Carica la tua playlist personale nella root del repository "
            "con questo nome esatto: playlist_sorgente.m3u8"
        )

    raw = SOURCE.read_text(encoding="utf-8-sig", errors="replace")
    lines = raw.splitlines()
    header, entries = read_entries(lines)

    if not entries:
        raise SystemExit("ERRORE: la playlist sorgente non contiene canali (#EXTINF).")

    removed = Counter()
    output_lines = []

    # Conserva l'intestazione originale (incluso x-tvg-url) senza modificarla.
    for line in header:
        if line.strip():
            output_lines.append(line)

    kept = 0
    for info, name, block in entries:
        reason = removal_reason(info, name)
        if reason:
            removed[reason] += 1
            continue

        # Copia letterale del blocco: numerazione, ID EPG, logo, gruppo,
        # eventuali opzioni e URL video restano identici alla sorgente.
        output_lines.extend(block)
        kept += 1

    OUTPUT.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")

    print("===== GAEBIA IPTV: RISULTATO =====")
    print(f"Playlist sorgente: {SOURCE}")
    print(f"Canali iniziali:   {len(entries)}")
    print(f"Canali mantenuti:  {kept}")
    print(f"Canali eliminati:  {sum(removed.values())}")
    for category in ("RTL", "radio", "cartoni", "religiosi", "economici"):
        print(f"  {category}: {removed[category]}")
    print(f"File creato:       {OUTPUT}")
    print("Numerazione, ordine, EPG e URL originali: mantenuti senza modifiche.")


if __name__ == "__main__":
    main()
