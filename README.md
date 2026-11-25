# 수원, AI 삼각 산업벨트의 연계거점

판교(소프트웨어·팹리스), 경부축(반도체 생산), 서해안(제조업 집적지)이 이루는 삼각 산업벨트와, 그 가운데 있는 수원을 연계거점으로 제안하는 내용을 그린 도식 지도입니다.

- `light.html`: 흰 배경 시안. 고속도로, 수인분당선·신분당선, 산업단지 이름 포함
- `index.html`: 어두운 위성 배경 시안 (Esri World Imagery / OSM)

## 데이터

| 파일 | 내용 | 출처 |
| --- | --- | --- |
| `data/industrial_zones.geojson` | 용도지역 중 공업지역 | VWorld 용도지역도(LT_C_UQ111) |
| `data/complexes.geojson` | 산업단지 경계·명칭 | VWorld 산업단지 경계(LT_C_DAMDAN) |
| `data/highways.geojson` | 고속도로 본선 | VWorld 국가교통DB 링크(LT_L_MOCTLINK) |
| `data/rail.geojson`, `data/stations.geojson` | 수인분당선·신분당선 (역 좌표를 이은 도식선) | VWorld 장소 검색 |
| `data/sigungu.geojson`, `data/land.geojson` | 시군구 경계, 해안선 | 통계청 SGIS 경계(2025 2Q) |

입지 표시와 연결선은 도식적 표현입니다. 제3판교 위치는 대략적인 위치입니다.

## 데이터 다시 받기

```bash
python scripts/fetch_data.py
```

VWorld API 키는 상위 폴더의 `.env`(`V-WORLD_KEY`)에서 읽습니다. 키는 수집 스크립트에서만 쓰고, 지도 페이지와 데이터 파일에는 들어가지 않습니다.

## 로컬에서 보기

지도 페이지가 `fetch()`로 데이터를 불러오므로 로컬 서버로 열어야 합니다.

```bash
python -m http.server
# http://localhost:8000/light.html
```
