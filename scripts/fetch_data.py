"""수원 AI 삼각 산업벨트 지도용 데이터 수집 (로컬 전용).

- VWorld 용도지역(LT_C_UQ111) 중 공업지역 폴리곤 -> data/industrial_zones.geojson
- 통계청 시군구 경계(2025 2Q) -> data/sigungu.geojson
API 키는 상위 폴더 .env 의 V-WORLD_KEY 에서 읽으며, 결과물에는 포함되지 않는다.
"""
import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT.parent / ".env"
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

BBOX = (126.60, 36.96, 127.42, 37.58)  # 서울 남부 ~ 평택, 시화 ~ 용인 원삼


def vworld_key():
    for line in ENV.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*V-WORLD_KEY\s*=\s*(.+)", line)
        if m:
            return m.group(1).strip().strip("\"'")
    sys.exit("V-WORLD_KEY not found in .env")


def fetch_industrial(key):
    feats, page = [], 1
    while True:
        r = requests.get(
            "https://api.vworld.kr/req/data",
            params=dict(
                service="data", request="GetFeature", data="LT_C_UQ111", key=key,
                format="json", size=1000, page=page, crs="EPSG:4326",
                geomFilter="BOX({},{},{},{})".format(*BBOX),
                attrFilter="uname:like:공업지역",
            ),
            timeout=60,
        )
        res = r.json()["response"]
        if res["status"] != "OK":
            break
        feats += res["result"]["featureCollection"]["features"]
        if page >= int(res["page"]["total"]):
            break
        page += 1
    gdf = gpd.GeoDataFrame.from_features(feats, crs=4326)[["uname", "sigg_name", "geometry"]]
    # 5179 에서 병합·단순화해 파일 크기 축소
    g = gdf.to_crs(5179)
    g["geometry"] = g.buffer(30).buffer(-30)
    g = g.dissolve(by="uname").explode(index_parts=False).reset_index()
    g = g[g.area > 20000]
    g["geometry"] = g.simplify(15)
    g = g.to_crs(4326)
    g["geometry"] = g.geometry.set_precision(1e-5)
    g[["uname", "geometry"]].to_file(DATA / "industrial_zones.geojson", driver="GeoJSON")
    print("industrial polygons:", len(g))


def export_sigungu():
    shp = ROOT.parent / "lecture04_spatial_data_analysis/bnd_all_00_2025_2Q/bnd_all_00_2025_2Q/bnd_sigungu_00_2025_2Q.shp"
    g = gpd.read_file(shp, encoding="utf-8")
    g = g[g.SIGUNGU_CD.str[:2].isin(["11", "31", "23"])]
    g = g.to_crs(4326)
    g = g[g.intersects(box(*BBOX))]
    # 시 단위로 병합 (수원 4개 구 -> 수원시 등)
    g["city"] = g.SIGUNGU_NM.str.split(" ").str[0]
    g.loc[g.SIGUNGU_CD.str[:2] == "11", "city"] = "서울특별시"
    g.loc[g.SIGUNGU_CD.str[:2] == "23", "city"] = "인천광역시"
    g = g.to_crs(5179).dissolve(by="city").reset_index()
    g["geometry"] = g.simplify(60)
    lp = g.representative_point().to_crs(4326)
    g = g.to_crs(4326)
    g["lat"], g["lng"] = lp.y.round(4), lp.x.round(4)
    g["geometry"] = g.geometry.set_precision(1e-5)
    g[["city", "lat", "lng", "geometry"]].to_file(DATA / "sigungu.geojson", driver="GeoJSON")
    print("cities:", len(g))


def export_suwon_gu():
    """수원시 4개 구 경계·라벨점 -> data/suwon_gu.geojson."""
    shp = ROOT.parent / "lecture04_spatial_data_analysis/bnd_all_00_2025_2Q/bnd_all_00_2025_2Q/bnd_sigungu_00_2025_2Q.shp"
    g = gpd.read_file(shp, encoding="utf-8")
    g = g[g.SIGUNGU_CD.isin(["31011", "31012", "31013", "31014"])].to_crs(5179)
    g["gu"] = g.SIGUNGU_NM.str.split(" ").str[-1]
    g["geometry"] = g.simplify(30)
    lp = g.representative_point().to_crs(4326)
    g = g.to_crs(4326)
    g["lat"], g["lng"] = lp.y.round(4), lp.x.round(4)
    g["geometry"] = g.geometry.set_precision(1e-5)
    g[["gu", "lat", "lng", "geometry"]].to_file(DATA / "suwon_gu.geojson", driver="GeoJSON")
    print(g[["gu", "lat", "lng"]].to_string())


BELT = {  # 삼각 산업벨트 기능 구분
    "안산시": "mfg", "시흥시": "mfg",
    "화성시": "semi", "평택시": "semi", "용인시": "semi", "오산시": "semi",
    "성남시": "sw",
    "수원시": "hub",
}


def tag_zones():
    z = gpd.read_file(DATA / "industrial_zones.geojson")[["uname", "geometry"]]
    c = gpd.read_file(DATA / "sigungu.geojson")[["city", "geometry"]]
    pts = z.copy()
    pts["geometry"] = z.to_crs(5179).representative_point().to_crs(4326)
    j = gpd.sjoin(pts, c, how="left", predicate="within")
    z["city"] = j["city"].values
    z["belt"] = z["city"].map(BELT).fillna("other")
    z.to_file(DATA / "industrial_zones.geojson", driver="GeoJSON")
    print(z.groupby("belt").size())


def fetch_complexes(key):
    """VWorld 산업단지 경계(LT_C_DAMDAN) -> data/complexes.geojson (단지명·유형·라벨점)."""
    feats, page = [], 1
    while True:
        res = requests.get(
            "https://api.vworld.kr/req/data",
            params=dict(service="data", request="GetFeature", data="LT_C_DAMDAN", key=key,
                        format="json", size=1000, page=page, crs="EPSG:4326",
                        geomFilter="BOX({},{},{},{})".format(*BBOX)),
            timeout=60,
        ).json()["response"]
        if res["status"] != "OK":
            break
        feats += res["result"]["featureCollection"]["features"]
        if page >= int(res["page"]["total"]):
            break
        page += 1
    g = gpd.GeoDataFrame.from_features(feats, crs=4326).to_crs(5179)
    g["geometry"] = g.buffer(0)
    g = g.dissolve(by=["dan_id", "dan_name", "cat_nam"]).reset_index()
    g["area_ha"] = (g.area / 1e4).round(1)
    g["name"] = g.dan_name.str.strip() + " " + g.cat_nam.str.strip()
    lp = g.representative_point().to_crs(4326)
    g["geometry"] = g.simplify(15)
    g = g.to_crs(4326)
    g["lat"], g["lng"] = lp.y.round(4), lp.x.round(4)
    g["geometry"] = g.geometry.set_precision(1e-5)
    g = g.sort_values("area_ha", ascending=False)
    c = gpd.read_file(DATA / "sigungu.geojson")[["city", "geometry"]]
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(g.lng, g.lat), crs=4326, index=g.index)
    g["belt"] = gpd.sjoin(pts, c, how="left", predicate="within")["city"].map(BELT).fillna("other")
    g[["name", "dan_name", "cat_nam", "area_ha", "belt", "lat", "lng", "geometry"]].to_file(
        DATA / "complexes.geojson", driver="GeoJSON")
    print("complexes:", len(g))


def fetch_highways(key):
    """VWorld 국가교통DB 링크(LT_L_MOCTLINK) 중 고속국도 본선 -> data/highways.geojson."""
    from shapely.ops import linemerge
    feats, page = [], 1
    while True:
        res = requests.get(
            "https://api.vworld.kr/req/data",
            params=dict(service="data", request="GetFeature", data="LT_L_MOCTLINK", key=key,
                        format="json", size=1000, page=page, crs="EPSG:4326",
                        geomFilter="BOX({},{},{},{})".format(*BBOX),
                        attrFilter="rd_rank_h:=:고속국도"),
            timeout=90,
        ).json()["response"]
        if res["status"] != "OK":
            break
        feats += res["result"]["featureCollection"]["features"]
        if page >= int(res["page"]["total"]):
            break
        page += 1
    g = gpd.GeoDataFrame.from_features(feats, crs=4326)
    print("highway link types:", g.rd_type_h.value_counts().to_dict())
    g = g[g.road_name.str.endswith("고속도로")].to_crs(5179)  # 교량·터널 포함해야 끊기지 않음
    g = g.dissolve(by="road_name").reset_index()
    g["geometry"] = g.geometry.apply(lambda x: linemerge(x) if x.geom_type == "MultiLineString" else x)
    # 분기점·IC에서 갈라지는 짧은 조각 제거: 이어진 선 중 2.5km 미만은 버림
    g = g.explode(index_parts=False)
    g = g[g.length > 2500]
    g = g.dissolve(by="road_name").reset_index()
    g["geometry"] = g.simplify(50)  # 상·하행 링크가 한 줄로 보이도록
    g = g[g.length > 3000].to_crs(4326)
    g["geometry"] = g.geometry.set_precision(1e-5)
    g = g.rename(columns={"road_name": "name"})[["name", "geometry"]]
    g.to_file(DATA / "highways.geojson", driver="GeoJSON")
    print("highways:", len(g), g.name.tolist())


RAIL = {
    "신분당선": "신사 논현 신논현 강남 양재 양재시민의숲 청계산입구 판교 정자 미금 동천 수지구청 성복 상현 광교중앙 광교",
    "수인분당선": "청량리 왕십리 서울숲 압구정로데오 강남구청 선정릉 선릉 한티 도곡 구룡 개포동 대모산입구 수서 복정 가천대 태평 모란 "
                 "야탑 이매 서현 수내 정자 미금 오리 죽전 보정 구성 신갈 기흥 상갈 청명 영통 망포 매탄권선 수원시청 매교 수원 "
                 "고색 오목천 어천 야목 사리 한대앞 중앙 고잔 초지 안산 신길온천 정왕 오이도 달월 월곶 소래포구 인천논현 호구포 "
                 "남동인더스파크 원인재 연수 송도 인하대 숭의 신포 인천",
}


STATION_FIX = {"광교": (37.3020, 127.0444)}  # 광교(경기대)역: 검색에 철도시설로 잡히지 않음


def _station(key, name, prev):
    if name in STATION_FIX:
        return STATION_FIX[name]
    w, s, e, n = BBOX[0] - .1, BBOX[1] - .1, BBOX[2] + .1, BBOX[3] + .1
    for q in (name + "역", name):
        items = requests.get(
            "https://api.vworld.kr/req/search",
            params=dict(service="search", request="search", query=q, type="place",
                        key=key, format="json", size=50),
            timeout=30,
        ).json()["response"].get("result", {}).get("items", [])
        c = [(float(i["point"]["y"]), float(i["point"]["x"])) for i in items
             if i["category"].startswith("철도시설") and i["title"].startswith(name)]
        c = [p for p in c if s < p[0] < n and w < p[1] < e]
        if c:
            if prev:
                c.sort(key=lambda p: (p[0] - prev[0]) ** 2 + (p[1] - prev[1]) ** 2)
            return c[0]
    return None


def fetch_rail(key):
    """역 좌표를 순서대로 이은 도식 노선 -> data/rail.geojson, data/stations.geojson."""
    from shapely.geometry import LineString, Point
    lines, stns = [], []
    for line, names in RAIL.items():
        pts, prev = [], None
        for nm in names.split():
            p = _station(key, nm, prev)
            if p is None:
                print("  not found:", line, nm)
                continue
            pts.append(p); prev = p
            stns.append({"line": line, "name": nm, "geometry": Point(p[1], p[0])})
        lines.append({"line": line, "geometry": LineString([(x, y) for y, x in pts])})
        print(line, len(pts), "stations")
    gpd.GeoDataFrame(lines, crs=4326).to_file(DATA / "rail.geojson", driver="GeoJSON")
    gpd.GeoDataFrame(stns, crs=4326).to_file(DATA / "stations.geojson", driver="GeoJSON")


def geocode(key, query):
    r = requests.get(
        "https://api.vworld.kr/req/search",
        params=dict(service="search", request="search", query=query, type="place",
                    key=key, format="json", size=3),
        timeout=30,
    ).json()["response"]
    items = r.get("result", {}).get("items", [])
    return [(i["title"], i["point"]["y"], i["point"]["x"]) for i in items]


if __name__ == "__main__":
    k = vworld_key()
    if "geocode" in sys.argv:
        for q in sys.argv[2:]:
            print(q, "->", geocode(k, q))
        sys.exit()
    fetch_industrial(k)
    export_sigungu()
    export_suwon_gu()
    tag_zones()
    fetch_complexes(k)
    fetch_highways(k)
    fetch_rail(k)
