import re
import urllib.request
from pathlib import Path

OUTPUT = Path("playlist_italia.m3u8")

# ============================================================
# CONFIGURAZIONE
# ============================================================

# Sorgente principale:
# iptv-org genera quotidianamente la playlist pubblica
# scegliendo una sola sorgente preferibile per ogni canale.
PRIMARY_SOURCE = (
    "https://iptv-org.github.io/iptv/countries/it.m3u"
)

# Fallback nazionale:
# usato soltanto per canali che non sono già presenti.
FALLBACK_SOURCES = [
    "https://raw.githubusercontent.com/Tundrak/IPTV-Italia/main/iptvitaplus.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_italy.m3u8",
]

# Regioni/locali aggiuntivi.
# NON vengono più caricati tutti indiscriminatamente:
# servono soltanto per recuperare eventuali canali locali
# che non compaiono nella playlist nazionale.
REGIONAL_SOURCES = [
    "it-65",  # Emilia-Romagna
    "it-77",  # Basilicata
    "it-78",  # Calabria
    "it-72",  # Campania
    "it-45",  # Friuli-Venezia Giulia
    "it-36",  # Lazio
    "it-62",  # Liguria
    "it-42",  # Lombardia
    "it-25",  # Marche
    "it-57",  # Piemonte
    "it-67",  # Puglia
    "it-21",  # Piemonte / Valle d'Aosta
    "it-75",  # Sardegna
    "it-88",  # Sicilia
    "it-82",  # Toscana
    "it-52",  # Trentino-Alto Adige
    "it-32",  # Trentino-Alto Adige
    "it-55",  # Umbria
    "it-23",  # Valle d'Aosta
    "it-34",  # Veneto
]

EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 IPTV-Italia-Updater"
}

# ============================================================
# FILTRI
# ============================================================

BLOCKED_TEXT = [
    "[geo-blocked]",
    "[not 24/7]",
    "geo-blocked",
    "not 24/7",
]

BLOCKED_STREAMS = [
    "youtube.com",
    "youtu.be",
    "twitch.tv",
]

# Non vogliamo stream DASH .mpd nel risultato finale.
# DIIXTREAM lavora meglio con gli HLS .m3u8.
BLOCKED_EXTENSIONS = [
    ".mpd",
]

# Etichette che indicano contenuti esteri / versioni straniere
# che non vogliamo nella playlist italiana.
FOREIGN_MARKERS = [
    "(germany)",
    "(france)",
    "(spain)",
    "(uk)",
    "(united kingdom)",
    "(poland)",
    "(portugal)",
    "(switzerland)",
    "(austria)",
    "(netherlands)",
]

# ============================================================
# ALIAS
# ============================================================

# Normalizzazione dei nomi per eliminare duplicati come:
# Rai 1 / Rai 1 HD / Rai 1 (720p) ecc.
ALIASES = {
    "rete 4": "Rete 4",
    "rete 4 hd": "Rete 4",
    "canale 5": "Canale 5",
    "canale 5 hd": "Canale 5",
    "italia 1": "Italia 1",
    "italia 1 hd": "Italia 1",
    "la7": "La7",
    "la 7": "La7",
    "tv8": "TV8",
    "nove": "Nove",
    "20": "20 Mediaset",
    "20 mediaset": "20 Mediaset",
    "rai 1": "Rai 1",
    "rai 2": "Rai 2",
    "rai 3": "Rai 3",
    "rai 4": "Rai 4",
    "rai 5": "Rai 5",
    "rai movie": "Rai Movie",
    "rai premium": "Rai Premium",
    "rai storia": "Rai Storia",
    "rai scuola": "Rai Scuola",
    "rai sport": "Rai Sport",
    "mediaset extra": "Mediaset Extra",
    "iris": "Iris",
    "la5": "La5",
    "cielo": "Cielo",
}

# ============================================================
# FUNZIONI
# ============================================================

def download(url):
    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode(
            "utf-8",
            errors="replace"
        )


def parse_m3u(text):
    """
    Restituisce:
    (EXTINF, EXT-X-..., URL)
    """

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


def get_attr(info, name):

    match = re.search(
        rf'{re.escape(name)}="([^"]*)"',
        info,
        re.IGNORECASE
    )

    return (
        match.group(1).strip()
        if match
        else ""
    )


def channel_name(info):

    if "," not in info:
        return ""

    name = info.split(",", 1)[1].strip()

    # Rimuove eventuali indicazioni di qualità
    name = re.sub(
        r"\s*\((?:1080p|720p|576p|480p|360p)\)\s*$",
        "",
        name,
        flags=re.IGNORECASE
    )

    return name.strip()


def normalized_name(name):

    value = name.lower().strip()

    value = re.sub(
        r"\s*\((?:1080p|720p|576p|480p|360p)\)",
        "",
        value,
        flags=re.IGNORECASE
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    if value in ALIASES:
        return ALIASES[value].lower()

    return value


def is_allowed(info, stream):

    text = (
        info + " " + stream
    ).lower()

    # Geo-blocked / non-24/7
    for blocked in BLOCKED_TEXT:
        if blocked in text:
            return False

    # YouTube / Twitch
    for blocked in BLOCKED_STREAMS:
        if blocked in stream.lower():
            return False

    # DASH
    for extension in BLOCKED_EXTENSIONS:
        if stream.lower().split("?", 1)[0].endswith(extension):
            return False

    # Contenuti stranieri
    name = channel_name(info).lower()

    for marker in FOREIGN_MARKERS:
        if marker in name:
            return False

    return True


def clean_info(info):

    info = info.replace(
        'group-title="Italy"',
        'group-title="Italia"'
    )

    info = info.replace(
        'group-title="Italian"',
        'group-title="Italia"'
    )

    return info


def load_source(url):

    try:
        print(f"DOWNLOAD: {url}")

        text = download(url)

        entries = parse_m3u(text)

        print(
            f"  -> {len(entries)} entries"
        )

        return entries

    except Exception as error:

        print(
            f"WARNING: {url} -> {error}"
        )

        return []


# ============================================================
# COSTRUZIONE
# ============================================================

# Dizionario:
# nome normalizzato -> entry scelta
channels = {}


def add_entries(entries, source_name):

    added = 0
    rejected = 0
    duplicates = 0

    for info, extras, stream in entries:

        info = clean_info(info)

        if not is_allowed(info, stream):
            rejected += 1
            continue

        name = channel_name(info)

        if not name:
            rejected += 1
            continue

        key = normalized_name(name)

        if key in channels:
            duplicates += 1
            continue

        channels[key] = (
            info,
            extras,
            stream,
            source_name
        )

        added += 1

    print(
        f"{source_name}: "
        f"aggiunti={added}, "
        f"duplicati={duplicates}, "
        f"scartati={rejected}"
    )


# ------------------------------------------------------------
# 1. PRIMA SCELTA:
#    iptv-org
# ------------------------------------------------------------

primary = load_source(PRIMARY_SOURCE)

add_entries(
    primary,
    "iptv-org"
)


# ------------------------------------------------------------
# 2. REGIONALI:
#    solo canali che mancano
# ------------------------------------------------------------

for region in REGIONAL_SOURCES:

    url = (
        "https://iptv-org.github.io/iptv/"
        f"subdivisions/{region}.m3u"
    )

    regional = load_source(url)

    add_entries(
        regional,
        f"region-{region}"
    )


# ------------------------------------------------------------
# 3. FALLBACK NAZIONALI
# ------------------------------------------------------------

for source in FALLBACK_SOURCES:

    fallback = load_source(source)

    add_entries(
        fallback,
        "fallback"
    )


# ============================================================
# ORDINAMENTO
# ============================================================

# Canali nazionali principali prima.
PRIORITY = [
    "rai 1",
    "rai 2",
    "rai 3",
    "rete 4",
    "canale 5",
    "italia 1",
    "la7",
    "tv8",
    "nove",
    "20 mediaset",
    "rai 4",
    "rai 5",
    "rai movie",
    "rai premium",
    "rai storia",
    "rai scuola",
    "rai sport",
    "mediaset extra",
    "iris",
    "la5",
    "cielo",
]


def sort_key(item):

    key = item[0]

    if key in PRIORITY:
        return (
            0,
            PRIORITY.index(key)
        )

    return (
        1,
        key
    )


ordered = sorted(
    channels.items(),
    key=sort_key
)


# ============================================================
# OUTPUT
# ============================================================

epg = ",".join(EPG_URLS)

output = [
    f'#EXTM3U x-tvg-url="{epg}"'
]

for key, (
    info,
    extras,
    stream,
    source
) in ordered:

    output.append(info)

    for extra in extras:
        output.append(extra)

    output.append(stream)


OUTPUT.write_text(
    "\n".join(output) + "\n",
    encoding="utf-8"
)

print()
print("=" * 60)
print("PLAYLIST CREATA")
print("=" * 60)
print(
    f"Canali finali: {len(ordered)}"
)
print(
    f"File: {OUTPUT}"
)
print(
    f"EPG: {len(EPG_URLS)} sorgente"
)
print("=" * 60)
