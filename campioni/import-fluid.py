"""Rebuild the local FluidR3 subset. Development-only; never run by the app.

Reads declarative WebAudioFont objects as JSON after a restricted conversion.
No downloaded JavaScript is executed. Python standard library only.
"""
import base64
import concurrent.futures
import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = "https://raw.githubusercontent.com/surikov/webaudiofontdata/master/"


def fetch(path):
    with urllib.request.urlopen(REPO + path, timeout=45) as response:
        return response.read().decode("utf-8-sig")


def parse_data(text):
    match = re.search(r"var\s+\w+\s*=\s*({[\s\S]*})\s*;?\s*$", text)
    if not match:
        raise ValueError("Unsupported source wrapper")
    raw = re.sub(r"(?m)^\s*//[^\n]*", "", match[1])
    raw = re.sub(r"'([^'\\]*)'", lambda m: json.dumps(m[1]), raw)
    raw = re.sub(r"([{,]\s*)([A-Za-z_$][\w$]*)\s*:", r'\1"\2":', raw)
    return json.loads(raw)


def import_preset(item):
    instrument, filename, midi = item
    source = "sound/" + filename + ".js"
    preset = parse_data(fetch(source))
    target = ROOT / instrument
    target.mkdir(exist_ok=True)
    zones = []
    for index, original in enumerate(preset["zones"]):
        data = base64.b64decode(original["file"], validate=True)
        name = f"{midi if midi is not None else filename[:4]}-{index}.mp3"
        (target / name).write_bytes(data)
        zone = {key: original[key] for key in (
            "originalPitch", "keyRangeLow", "keyRangeHigh", "loopStart",
            "loopEnd", "coarseTune", "fineTune", "sampleRate"
        ) if key in original}
        zone.update(file=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                    source=REPO + source)
        if midi is not None:
            zone.update(keyRangeLow=midi, keyRangeHigh=midi, midi=midi,
                        loopStart=0, loopEnd=0)
        zones.append(zone)
    return instrument, zones


def main():
    presets = [("flauto", "0740_FluidR3_GM_sf2_file", None),
               ("violino", "0400_FluidR3_GM_sf2_file", None),
               ("tromba", "0560_FluidR3_GM_sf2_file", None)]
    presets += [("batteria", f"128{note}_0_FluidR3_GM_sf2_file", note)
                for note in range(35, 82)]
    grouped = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for instrument, zones in executor.map(import_preset, presets):
            grouped.setdefault(instrument, []).extend(zones)
    for instrument, zones in grouped.items():
        manifest = dict(version=1, instrument=instrument, soundfont="FluidR3 GM",
                        program={"flauto": 74, "violino": 40, "tromba": 56}.get(instrument),
                        note="Recorder / flauto dolce" if instrument == "flauto" else None,
                        zones=zones)
        (ROOT / instrument / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(instrument, len(zones), "samples", sum(z["bytes"] for z in zones), "bytes")
    (ROOT / "FluidR3-LICENSE.txt").write_text(
        urllib.request.urlopen("https://raw.githubusercontent.com/LibreScore/sf3/master/FluidR3Mono_License.md").read().decode(),
        encoding="utf-8")
    (ROOT / "WebAudioFontData-LICENSE.txt").write_text(fetch("LICENSE"), encoding="utf-8")


if __name__ == "__main__":
    main()
