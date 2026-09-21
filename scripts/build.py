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
    request = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(
        request,
        timeout=120
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="replace"
        )


# ============================================================
# PARSER M3U
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

        while j < len(lines) and lines[j].startswith("#"):

            if lines[j].startswith("#EXTVLCOPT"):
                extras.append(lines[j])

            j += 1

        if j < len(lines):

            stream = lines[j]

            if stream.startswith(
                ("http://", "https://")
            ):

                entries.append({
                    "info": info,
                    "extras": extras,
                    "stream": stream
                })

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

    value = get_attr(
        info,
        "tvg-chno"
    )

    if not value:
        return None

    try:
        return float(value)

    except ValueError:
        return None


# ============================================================
# FILTRO ITALIA
# ============================================================

def is_italian(info):

    country = get_attr(
        info,
        "tvg-country"
    ).upper()

    group = get_attr(
        info,
        "group-title"
    ).lower()

    return (
        country == "IT"
        or group == "italy"
        or group == "italia"
    )


# ============================================================
# STREAM DA ESCLUDERE
# ============================================================

def is_bad_stream(info, stream):

    text = (
        info + " " + stream
    ).lower()

    # NON disponibili
    if "[geo-blocked]" in text:
        return True

    if "[not 24/7]" in text:
        return True

    # YouTube
    if "youtube.com" in stream.lower():
        return True

    if "youtu.be" in stream.lower():
        return True

    # Twitch
    if "twitch.tv" in stream.lower():
        return True

    return False


# ============================================================
# NORMALIZZAZIONE
# ============================================================

def normalized_name(name):

    value = name.lower().strip()

    # Rimuove i simboli usati da Free-TV
    for symbol in [
        "ⓖ",
        "Ⓖ",
        "Ⓢ",
        "Ⓣ",
        "Ⓨ"
    ]:
        value = value.replace(
            symbol,
            ""
        )

    # Spazi multipli
    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# CANALI NAZIONALI
# ============================================================

# Questa lista serve SOLO per distinguere i canali nazionali
# dai regionali che possono avere accidentalmente un tvg-chno.
#
# I numeri NON vengono creati qui.
# Il numero viene SEMPRE letto da tvg-chno.

NATIONAL_CHANNELS = {
    "rai 1",
    "rai 2",
    "rai 3",

    "rete 4",
    "canale 5",
    "italia 1",

    "la7",
    "tv8",
    "nove",

    "20",
    "20 mediaset",

    "rai 4",
    "iris",
    "rai 5",
    "rai movie",
    "rai premium",
    "cielo",
    "27 twentyseven",

    "tv2000",
    "tv 2000",

    "la7 cinema",
    "la 5",
    "la5",

    "real time",
    "qvc",
    "food network",
    "cine34",
    "focus",
    "rtl 102.5",
    "discovery channel",

    "giallo",
    "top crime",
    "boing",

    "rai gulp",
    "rai yoyo",
    "cartoonito",
    "super!",

    "italia 2",
    "mediaset extra",

    "rai news 24",
    "tgcom24",
    "tgcom 24",

    "dmax",

    "rai storia",
    "rai scuola",
    "rai sport",

    "sportitalia",
    "sportitalia plus",
    "sportitalia solocalcio",

    "supert ennis",
    "supertennis",

    "sky tg24",

    "hgtv",
    "home & garden tv",

    "gambero rosso",

    "radio italia tv",
    "deejay tv",
    "r101 tv",
    "radio 105 tv",

    "senato tv",
    "camera dei deputati",
}


# ============================================================
# ORDINE
# ============================================================

def channel_sort_key(entry):

    name = entry["name"]

    chno = get_chno(
        entry["info"]
    )

    name_key = normalized_name(
        name
    )

    # --------------------------------------------------------
    # NAZIONALI
    # --------------------------------------------------------
    #
    # Solo i canali nazionali vengono ordinati tramite
    # il loro tvg-chno.
    #
    # Esempio:
    #
    # Rai 1          tvg-chno="1"
    # Rai 2          tvg-chno="2"
    # Rai 3          tvg-chno="3"
    #
    # Peer TV Südtirol può avere anch'esso tvg-chno="2",
    # ma NON è nella lista NATIONAL_CHANNELS.
    # Quindi viene mandato alla sezione regionali/locali.

    if (
        name_key in NATIONAL_CHANNELS
        and chno is not None
    ):

        return (
            0,
            chno,
            name_key
        )

    # --------------------------------------------------------
    # REGIONALI / LOCALI
    # --------------------------------------------------------
    #
    # Tutti gli altri canali vengono dopo i nazionali.
    #
    # Quindi Peer TV Südtirol NON può più inserirsi tra
    # Rai 1 e Rai 2.

    return (
        1,
        999999,
        name_key
    )


# ============================================================
# DOWNLOAD
# ============================================================

print()
print("==============================================")
print("DOWNLOAD PLAYLIST FREE-TV")
print("==============================================")

text = download(
    SOURCE
)

entries = parse_m3u(
    text
)

print(
    f"Entry ricevute: {len(entries)}"
)


# ============================================================
# FILTRO ITALIA
# ============================================================

italian = []

for entry in entries:

    info = entry["info"]
    stream = entry["stream"]

    if not is_italian(info):
        continue

    if is_bad_stream(
        info,
        stream
    ):
        continue

    name = get_channel_name(
        info
    )

    if not name:
        continue

    entry["name"] = name

    italian.append(
        entry
    )


print(
    f"Canali italiani: {len(italian)}"
)


# ============================================================
# DEDUPLICAZIONE
# ============================================================

unique = []

seen_ids = set()
seen_names = set()

for entry in italian:

    info = entry["info"]

    tvg_id = get_attr(
        info,
        "tvg-id"
    )

    name_key = normalized_name(
        entry["name"]
    )

    # --------------------------------------------------------
    # tvg-id
    # --------------------------------------------------------

    if tvg_id:

        id_key = tvg_id.lower()

        if id_key in seen_ids:
            continue

        seen_ids.add(
            id_key
        )

    else:

        # ----------------------------------------------------
        # Nome
        # ----------------------------------------------------

        if name_key in seen_names:
            continue

        seen_names.add(
            name_key
        )

    unique.append(
        entry
    )


print(
    f"Canali dopo deduplicazione: {len(unique)}"
)


# ============================================================
# ORDINAMENTO
# ============================================================

unique.sort(
    key=channel_sort_key
)


# ============================================================
# EPG
# ============================================================

first_line = ""

for line in text.splitlines():

    if line.strip().startswith(
        "#EXTM3U"
    ):

        first_line = line.strip()
        break


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

    output.append(
        "#EXTM3U"
    )


for entry in unique:

    output.append(
        entry["info"]
    )

    for extra in entry["extras"]:

        output.append(
            extra
        )

    output.append(
        entry["stream"]
    )


OUTPUT.write_text(
    "\n".join(output) + "\n",
    encoding="utf-8"
)


# ============================================================
# REPORT
# ============================================================

national = []
regional = []

for entry in unique:

    name_key = normalized_name(
        entry["name"]
    )

    chno = get_chno(
        entry["info"]
    )

    if (
        name_key in NATIONAL_CHANNELS
        and chno is not None
    ):

        national.append(
            entry
        )

    else:

        regional.append(
            entry
        )


print()
print("==============================================")
print("PLAYLIST CREATA")
print("==============================================")
print(
    f"Totale:              {len(unique)}"
)
print(
    f"Nazionali numerati:  {len(national)}"
)
print(
    f"Regionali/locali:    {len(regional)}"
)
print(
    f"File:                {OUTPUT}"
)
print("==============================================")

print()
print("PRIMI CANALI:")

for entry in unique[:20]:

    chno = get_chno(
        entry["info"]
    )

    if chno is not None:

        print(
            f"{chno:g}  {entry['name']}"
        )

    else:

        print(
            f"-  {entry['name']}"
        )
