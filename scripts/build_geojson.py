"""Extract Prasat district (Surin, amp_code 3205) tambon polygons from the
national subdistrict GeoJSON and write a small, simplified file for the dashboard.

Source: https://github.com/chingchai/OpenGISData-Thailand (subdistricts.geojson)
Usage:  python scripts/build_geojson.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "th_subdistricts.geojson"
OUT = ROOT / "data" / "prasat_tambon.geojson"

# Official Thai names keyed by tambon code (avoids encoding issues in source).
TAMBON_TH = {
    "320501": "กังแอน", "320502": "ทมอ", "320503": "ไพล", "320504": "ปรือ",
    "320505": "ทุ่งมน", "320506": "ตาเบา", "320507": "หนองใหญ่", "320508": "โคกยาง",
    "320509": "โคกสะอาด", "320510": "บ้านไทร", "320511": "โชคนาสาม", "320512": "เชื้อเพลิง",
    "320513": "ปราสาททนง", "320514": "ตานี", "320515": "บ้านพลวง", "320516": "กันตวจระมวล",
    "320517": "สมุด", "320518": "ประทัดบุ",
}


def _round(coords, nd=5):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], nd), round(coords[1], nd)]
    return [_round(c, nd) for c in coords]


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    feats = []
    for f in data["features"]:
        p = f["properties"]
        if str(p.get("amp_code")) != "3205":
            continue
        code = str(p["tam_code"])
        geom = f["geometry"]
        geom["coordinates"] = _round(geom["coordinates"])
        feats.append({
            "type": "Feature",
            "id": code,
            "properties": {
                "tam_code": code,
                "tambon": TAMBON_TH[code],
                "tam_en": p.get("tam_en"),
                "area_sqkm": round(p.get("area_sqkm", 0), 2),
            },
            "geometry": geom,
        })
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                              ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(feats)} tambons -> {OUT}")


if __name__ == "__main__":
    main()
