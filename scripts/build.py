import re
import urllib.request
from pathlib import Path

OUTPUT = Path("playlist_italia.m3u8")

SOURCE = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"

HEADERS = {
    "User-Agent": "Mozilla/5.0 IPTV-Italia-Updater"
}

# ============================================================
# DOWNLOAD
# ============================================================

def download(url):
    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace")


# ============================================================
# M3U PARSER
# ============================================================

def parse_m3u(text):

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    entries = []

    i = 0

    while i < len(lines):

        if not lines[i].startswith("#EXTINF"):
            i += 1
            continue

        info = lines[i]
        extras = []

        j = i + 1

        # Conserviamo eventuali direttive associate
        # alla sorgente originale.
        while j < len(lines) and lines[j].startswith("#"):

            if lines[j].startswith("#EXTVLCOPT"):
                extras.append(lines[j])

            j += 1

        if j < len(lines):

            stream = lines[j]

            if stream.startswith(("http://", "https://")):

                entries.append(
                    (info, extras, stream)
                )

        i = j + 1

    return entries


# ============================================================
# ATTRIBUTI
# ============================================================

def get_attr(info, name):

    match = re.search(
        rf'{re.escape(name)}="([^"]*)"',
        info,
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return ""


def get_channel_name(info):

    if "," not in info:
        return ""

    return info.split(",", 1)[1].strip()


def get_chno(info):

    value = get_attr(info, "tvg-chno")

    if not value:
        return None

    try:
        # Gestisce anche eventuali valori come 22.1
        return float(value)
    except ValueError:
        return None


# ============================================================
# FILTRI
# ============================================================

def is_italian(info):

    country = get_attr(info, "tvg-country").upper()
    group = get_attr(info, "group-title").lower()

    return (
        country == "IT"
        or group == "italy"
        or group == "italia"
    )


def is_bad_stream(info, stream):

    text = (info + " " + stream).lower()

    # Canali esplicitamente non disponibili
    if "[geo-blocked]" in text:
        return True

    if "[not 24/7]" in text:
        return True

    # YouTube / Twitch
    if "youtube.com" in stream.lower():
        return True

    if "youtu.be" in stream.lower():
        return True

    if "twitch.tv" in stream.lower():
        return True

    return False


# ============================================================
# NORMALIZZAZIONE NOME
# ============================================================

def normalized_name(name):

    value = name.lower().strip()

    # Elimina i simboli utilizzati da Free-TV
    value = value.replace("ⓖ", "")
    value = value.replace("Ⓖ", "")
    value = value.replace("Ⓢ", "")
    value = value.replace("Ⓣ", "")
    value = value.replace("Ⓨ", "")

    # Spazi multipli
    value = re.sub(r"\s+", " ", value)

    return value.strip()


# ============================================================
# PRIORITÀ
# ============================================================

# Questi sono i canali con numerazione LCN.
# NON assegniamo noi il numero.
# Usiamo esclusivamente tvg-chno della sorgente Free-TV.

def channel_sort_key(entry):

    info = entry["info"]
    name = entry["name"]

    chno = get_chno(info)

    # Tutti i canali con tvg-chno vengono prima.
    if chno is not None:
        return (
            0,
            chno,
            normalized_name(name)
        )

    # Tutti quelli senza numero vengono dopo.
    return (
        1,
        999999,
        normalized_name(name)
    )


# ============================================================
# DOWNLOAD SORGENTE
# ============================================================

print("Download playlist Free-TV...")

text = download(SOURCE)

entries = parse_m3u(text)

print(f"Entry ricevute: {len(entries)}")


# ============================================================
# SELEZIONE ITALIA
# ============================================================

italian = []

for info, extras, stream in entries:

    if not is_italian(info):
        continue

    if is_bad_stream(info, stream):
        continue

    name = get_channel_name(info)

    if not name:
        continue

    italian.append({
        "info": info,
        "extras": extras,
        "stream": stream,
        "name": name
    })


print(
    f"Canali italiani dopo filtro: {len(italian)}"
)


# ============================================================
# DEDUPLICAZIONE
# ============================================================

# IMPORTANTISSIMO:
#
# Non deduplichiamo semplicemente per tvg-id.
#
# Free-TV può avere più righe dello stesso canale,
# alcune delle quali marcate Ⓖ e altre no.
#
# Manteniamo la prima versione utile.
#
# La playlist Free-TV è già ordinata secondo la propria
# selezione delle sorgenti, quindi NON sostituiamo gli URL.

seen_ids = set()
seen_names = set()

unique = []

for entry in italian:

    info = entry["info"]

    tvg_id = get_attr(info, "tvg-id")
    name_key = normalized_name(entry["name"])

    # Prima scelta: tvg-id
    if tvg_id:

        key = tvg_id.lower()

        if key in seen_ids:
            continue

        seen_ids.add(key)

    else:

        # Se manca tvg-id, usiamo il nome.
        if name_key in seen_names:
            continue

        seen_names.add(name_key)

    unique.append(entry)


print(
    f"Canali dopo deduplicazione: {len(unique)}"
)


# ============================================================
# ORDINAMENTO
# ============================================================

unique.sort(key=channel_sort_key)


# ============================================================
# EPG
# ============================================================

# Manteniamo ESATTAMENTE gli URL EPG presenti
# nell'header originale Free-TV.

first_line = text.splitlines()[0].strip()

epg_match = re.search(
    r'x-tvg-url="([^"]+)"',
    first_line,
    re.IGNORECASE
)

if epg_match:

    epg_url = epg_match.group(1)

else:

    epg_url = ""


# ============================================================
# OUTPUT
# ============================================================

output = []

if epg_url:

    output.append(
        f'#EXTM3U x-tvg-url="{epg_url}"'
    )

else:

    output.append("#EXTM3U")


# ============================================================
# SCRITTURA
# ============================================================

for entry in unique:

    output.append(entry["info"])

    for extra in entry["extras"]:
        output.append(extra)

    output.append(entry["stream"])


OUTPUT.write_text(
    "\n".join(output) + "\n",
    encoding="utf-8"
)


# ============================================================
# REPORT
# ============================================================

numbered = [
    e for e in unique
    if get_chno(e["info"]) is not None
]

regional = [
    e for e in unique
    if get_chno(e["info"]) is None
]


print()
print("=" * 60)
print("PLAYLIST ITALIA CREATA")
print("=" * 60)
print(f"Totale canali:       {len(unique)}")
print(f"Canali numerati:     {len(numbered)}")
print(f"Regionali/locali:    {len(regional)}")
print(f"File:                {OUTPUT}")
print("=" * 60)

print()
print("PRIMI CANALI:")

for entry in unique[:20]:

    chno = get_chno(entry["info"])
    name = entry["name"]

    if chno is not None:
        print(f"{chno:g}  {name}")
    else:
        print(f"-    {name}")
