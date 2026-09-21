import re
import urllib.request
from pathlib import Path

OUTPUT = Path("playlist_italia.m3u8")

SOURCES = [
    "https://iptv-org.github.io/iptv/countries/it.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_italy.m3u8",
    "https://raw.githubusercontent.com/Tundrak/IPTV-Italia/master/iptvitaplus.m3u",
]

REGIONS = [
    "it-65", "it-77", "it-78", "it-72", "it-45",
    "it-36", "it-62", "it-42", "it-25", "it-57",
    "it-67", "it-21", "it-75", "it-88", "it-82",
    "it-52", "it-32", "it-55", "it-23", "it-34"
]

EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_IT1.xml.gz",
    "https://iptv-org.github.io/epg/guides/it/guidatv.sky.it.epg.xml",
    "https://iptv-org.github.io/epg/guides/it/mediaset.it.epg.xml",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 IPTV-Italia-Updater"
}


def download(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def add_source(url, entries):
    try:
        text = download(url)
        lines = [x.strip() for x in text.splitlines() if x.strip()]

        i = 0
        while i < len(lines):
            if lines[i].startswith("#EXTINF"):
                info = lines[i]
                extras = []

                j = i + 1

                # Preserve VLC options such as User-Agent
                while j < len(lines) and lines[j].startswith("#EXT"):
                    if lines[j].startswith("#EXTVLCOPT"):
                        extras.append(lines[j])
                    j += 1

                if j < len(lines) and not lines[j].startswith("#"):
                    stream = lines[j]

                    # Keep only actual video stream entries
                    if stream.startswith(("http://", "https://")):
                        entries.append((info, extras, stream))

                    i = j + 1
                    continue

            i += 1

        print(f"OK: {url}")

    except Exception as e:
        print(f"WARNING: {url} -> {e}")


entries = []

# Main Italian playlist
for source in SOURCES:
    add_source(source, entries)

# Regional Italian playlists from iptv-org
for region in REGIONS:
    add_source(
        f"https://iptv-org.github.io/iptv/subdivisions/{region}.m3u",
        entries
    )


def get_attr(info, name):
    match = re.search(
        rf'{re.escape(name)}="([^"]*)"',
        info,
        re.IGNORECASE
    )
    return match.group(1).strip() if match else ""


def clean_info(info):
    # Normalize group names
    info = info.replace('group-title="Italy"', 'group-title="Italia"')
    info = info.replace('group-title="Italian"', 'group-title="Italia"')
    return info


# Deduplicate:
# Prefer tvg-id when available, otherwise channel name,
# and finally the stream URL.
seen = set()
unique = []

for info, extras, stream in entries:
    info = clean_info(info)

    tvg_id = get_attr(info, "tvg-id")
    name = info.split(",", 1)[1].strip() if "," in info else ""

    key = (
        tvg_id.lower()
        if tvg_id
        else name.lower()
        if name
        else stream.lower()
    )

    if key in seen:
        continue

    seen.add(key)
    unique.append((info, extras, stream))


# EPG header
epg = ",".join(EPG_URLS)

output = [
    f'#EXTM3U x-tvg-url="{epg}"'
]

for info, extras, stream in unique:
    output.append(info)

    for extra in extras:
        output.append(extra)

    output.append(stream)

OUTPUT.write_text(
    "\n".join(output) + "\n",
    encoding="utf-8"
)

print(f"Created {OUTPUT}")
print(f"Channels: {len(unique)}")
