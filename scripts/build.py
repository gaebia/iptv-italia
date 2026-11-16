#!/usr/bin/env python3
# GAEBIA IPTV - preserva la playlist personalizzata.
# Legge playlist_sorgente.m3u8 e genera playlist_italia.m3u8.
# Non scarica Free-TV, non cambia URL, ID EPG, loghi o numerazione.

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "playlist_sorgente.m3u8"
OUTPUT = ROOT / "playlist_italia.m3u8"

# Eliminazioni richieste: solo RTL, radio, cartoni, religiosi ed economici.
RTL_RE = re.compile(r"\bRTL\b", re.I)
RADIO_RE = re.compile(r"\bradio\b", re.I)
CARTOON_TERMS = (
    "cartoon", "cartoonito", "boing", "disney", "nickelodeon",
    "baby tv", "rai gulp", "rai yoyo", "rai yo yo", "k2",
    "frisbee", "super! (", "teenage mutant ninja",
)
RELIGIOUS_TERMS = (
    "padre pio", "medjugorje", "telepace", "ewtn", "tele padre pio",
    "k-tv", "k tv", "canale bibbia", "bibbia", "cristiano",
    "cristiana", "religio", "catholic", "cattolic",
)
ECONOMIC_TERMS = (
    "borsa", "finanza", "economia", "economico",
    "business", "financial", "finance",
)

# Riordino mirato richiesto: tutti gli altri canali restano nella
# stessa sequenza della playlist sorgente.
AFTER_FOCUS_ORDER = ("Discovery Channel", "DMAX", "HGTV")
AFTER_RAI5_ORDER = ("Rai Storia", "Rai Scuola")


def parse_blocks(text):
    lines = text.splitlines()
    header, blocks, current = [], [], []
    for line in lines:
        if line.startswith("#EXTINF:"):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
        else:
            header.append(line)
    if current:
        blocks.append(current)
    return header, blocks


def channel_name(block):
    for line in block:
        if line.startswith("#EXTINF:"):
            return line.split(",", 1)[1].strip() if "," in line else ""
    return ""


def should_remove(name):
    n = name.casefold()
    if RTL_RE.search(name):
        return "RTL"
    if RADIO_RE.search(name):
        return "radio"
    if any(term in n for term in CARTOON_TERMS):
        return "cartoni"
    if any(term in n for term in RELIGIOUS_TERMS):
        return "religiosi"
    if any(term in n for term in ECONOMIC_TERMS):
        return "economici"
    return None


def move_named_after(blocks, anchor_name, wanted_names):
    selected, remaining, found = [], [], set()
    wanted_lower = [x.casefold() for x in wanted_names]

    for block in blocks:
        name = channel_name(block)
        match_index = next(
            (i for i, wanted in enumerate(wanted_lower)
             if name.casefold().startswith(wanted)),
            None,
        )
        if match_index is None:
            remaining.append(block)
        else:
            selected.append((match_index, block))
            found.add(wanted_names[match_index])

    selected.sort(key=lambda item: item[0])
    for wanted in wanted_names:
        if wanted not in found:
            print(f"ATTENZIONE: canale da posizionare non trovato: {wanted}")

    anchor_index = next(
        (i for i, block in enumerate(remaining)
         if channel_name(block).casefold().startswith(anchor_name.casefold())),
        None,
    )
    if anchor_index is None:
        print(f"ATTENZIONE: ancora non trovata: {anchor_name}")
        return remaining

    insert_at = anchor_index + 1
    return remaining[:insert_at] + [b for _, b in selected] + remaining[insert_at:]


def main():
    if not SOURCE.exists():
        sys.exit(
            f"ERRORE: non trovo {SOURCE.name}. "
            "Carica la tua playlist personalizzata con questo nome nella root del repository."
        )

    text = SOURCE.read_text(encoding="utf-8-sig", errors="replace")
    header, blocks = parse_blocks(text)
    if not header:
        header = ["#EXTM3U"]

    kept, removed = [], []
    for block in blocks:
        name = channel_name(block)
        reason = should_remove(name)
        if reason:
            removed.append((name, reason))
        else:
            kept.append(block)

    # Rai Storia e Rai Scuola subito dopo Rai 5.
    kept = move_named_after(kept, "Rai 5", AFTER_RAI5_ORDER)
    # Discovery, DMAX e HGTV subito dopo Focus.
    kept = move_named_after(kept, "Focus", AFTER_FOCUS_ORDER)

    output_lines = header[:]
    for block in kept:
        output_lines.extend(block)
    OUTPUT.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")

    print(f"Canali iniziali: {len(blocks)}")
    print(f"Canali eliminati: {len(removed)}")
    for name, reason in removed:
        print(f"  - [{reason}] {name}")
    print(f"Canali conservati: {len(kept)}")
    print(f"Playlist generata: {OUTPUT.name}")

    # Segnala voci senza URL: vengono conservate, non si inventano stream.
    malformed = []
    for block in kept:
        name = channel_name(block)
        has_stream = any(
            line.strip().startswith(("http://", "https://"))
            for line in block
        )
        if not has_stream:
            malformed.append(name)
    if malformed:
        print("ATTENZIONE: voci senza URL video nella sorgente:")
        for name in malformed:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
