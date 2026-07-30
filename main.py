import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. 스트림릿 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 시군구 고령화 및 청소년 인구 지도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시군구 고령화 및 청소년 인구 지형도")
st.markdown("""
* 전국 읍·면·동 인구 데이터를 바탕으로 가장 최신 연도의 시군구별 인구 비율을 시각화합니다.
* 지도 상의 시군구 위에 마우스를 올리면 주요 정보를 확인하실 수 있습니다.
""")

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 전처리 (캐싱 적용으로 속도 향상)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 2-1. GeoJSON 지도 경계 데이터 불러오기
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    geojson_data = requests.get(geojson_url).json()

    # 2-2. 인구 데이터 불러오기 ('코드' 열은 반드시 문자열 str 형태로 읽기)
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(pop_url, dtype={"코드": str})

    # 최신 연도 자동 추출
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    # '코드' 앞 5자리를 잘라서 시군구 코드 생성
    df_latest["sigungu_code"] = df_latest["코드"].str.slice(0, 5)

    # 2-3. 나이별 열 분류 (65세 이상, 17세~19세, 전체 인구)
    total_cols = [c for c in df_latest.columns if c.startswith("계_")]
    
    # 65세 이상 '계_' 열 필터링
    elderly_cols = []
    for c in total_cols:
        try:
            age = int(c.replace("계_", "").replace("세 이상", "").replace("세", ""))
            if age >= 65:
                elderly_cols.append(c)
        except ValueError:
            pass

    # 17세~19세 '계_' 열 필터링
    youth_cols = ["계_17세", "계_18세", "계_19세"]
    youth_cols = [c for c in youth_cols if c in df_latest.columns]

    # 시군구 단위로 인구수 합산 (그룹화)
    group_cols = ["sigungu_code", "시도", "시군구"]
    df_grouped = df_latest.groupby(group_cols)[total_cols].sum().reset_index()

    # 총인구, 65세이상 인구, 17~19세 인구 합산 계산
    df_grouped["총인구"] = df_grouped[total_cols].sum(axis=1)
    df_grouped["고령인구"] = df_grouped[elderly_cols].sum(axis=1)
    df_grouped["청소년인구"] = df_grouped[youth_cols].sum(axis=1)

    # 비율(%) 계산 (소수점 둘째자리까지)
    df_grouped["65세이상비율"] = (df_grouped["고령인구"] / df_grouped["총인구"] * 100).round(2)
    df_grouped["17_19세비율"] = (df_grouped["청소년인구"] / df_grouped["총인구"] * 100).round(2)

    # 2-4. 5단계 구간(19%, 23%, 28%, 38%)에 따른 단계구분 범례 생성
    bins = [-1, 19, 23, 28, 38, 100]
    labels = ["19% 미만", "19% 이상 ~ 23% 미만", "23% 이상 ~ 28% 미만", "28% 이상 ~ 38% 미만", "38% 이상"]
    df_grouped["고령화구간"] = pd.cut(df_grouped["65세이상비율"], bins=bins, labels=labels)

    return df_grouped, geojson_data, latest_year

# 데이터 준비
with st.spinner("데이터와 지도 경계를 불러오는 중입니다..."):
    df_sigungu, geojson_kr, current_year = load_data()

st.subheader(f"📅 분석 기준 연도: {current_year}년")

# -----------------------------------------------------------------------------
# 3. 단계구분도(Choropleth) 및 시군구 이름 레이블 지도 생성
# -----------------------------------------------------------------------------
# 색상 팔레트 설정 (옅은 색 -> 진한 색 5단계)
color_discrete_map = {
    "19% 미만": "#edf8fb",
    "19% 이상 ~ 23% 미만": "#b2e2e2",
    "23% 이상 ~ 28% 미만": "#66c2a4",
    "28% 이상 ~ 38% 미만": "#2ca25f",
    "38% 이상": "#006d2c"
}

# 3-1. 단계구분도 기본 차트 생성
fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_kr,
    locations="sigungu_code",
    featureidkey="properties.코드",
    color="고령화구간",
    color_discrete_map=color_discrete_map,
    category_orders={"고령화구간": ["19% 미만", "19% 이상 ~ 23% 미만", "23% 이상 ~ 28% 미만", "28% 이상 ~ 38% 미만", "38% 이상"]},
    mapbox_style="white-bg",  # 배경 타일 없이 백색 처리
    center={"lat": 35.8, "lon": 127.8},  # 대한민국 중심 좌표
    zoom=6.2,
    hover_name="시군구",
    hover_data={
        "sigungu_code": False,
        "시도": True,
        "65세이상비율": ":.2f",
        "17_19세비율": ":.2f",
        "고령화구간": False
    },
    labels={
        "시도": "시도",
        "65세이상비율": "65세 이상 비율(%)",
        "17_19세비율": "17세~19세 비율(%)",
        "고령화구간": "65세 이상 비율 구간"
    }
)

# 3-2. GeoJSON 중심점에 시군구 이름을 검정색 50%(rgba(0,0,0,0.5))로 표시
label_lats = []
label_lons = []
label_texts = []

for feature in geojson_kr["features"]:
    props = feature["properties"]
    # Polygon / MultiPolygon 좌표 평균값으로 대략적인 중심점 계산
    geom = feature["geometry"]
    coords = geom["coordinates"]
    
    # 좌표들을 펼쳐서 위경도 평균값 도출
    all_coords = []
    if geom["type"] == "Polygon":
        all_coords = coords[0]
    elif geom["type"] == "MultiPolygon":
        for poly in coords:
            all_coords.extend(poly[0])
            
    if all_coords:
        lons = [c[0] for c in all_coords]
        lats = [c[1] for c in all_coords]
        center_lon = sum(lons) / len(lons)
        center_lat = sum(lats) / len(lats)
        
        label_lons.append(center_lon)
        label_lats.append(center_lat)
        label_texts.append(props.get("시군구", ""))

# 시군구 이름 텍스트 레이어 추가 (투명도 50% 검정색)
fig.add_trace(
    go.Scattermapbox(
        lat=label_lats,
        lon=label_lons,
        mode="text",
        text=label_texts,
        textfont=dict(size=10, color="rgba(0, 0, 0, 0.5)"),
        hoverinfo="skip",
        showlegend=False
    )
)

# 지도 레이아웃 세부 설정
fig.update_layout(
    margin={"r": 0, "t": 20, "l": 0, "b": 0},
    height=650,
    legend_title_text="65세 이상 인구 비율",
    legend=dict(
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.02,
        bgcolor="rgba(255, 255, 255, 0.8)"
    )
)

# 지도 출력
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 4. 하단 17세~19세 비율 상위/하위 10개 지역 표 표시
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📊 17세~19세 인구 비율 극단치 비교 (상위/하위 10개 지역)")

# 비율 기준 정렬
df_sorted = df_sigungu.sort_values(by="17_19세비율", ascending=False)

# 상위 10개 & 하위 10개 데이터 생성
top10 = df_sorted.head(10)[["시도", "시군구", "총인구", "17_19세비율", "65세이상비율"]].reset_index(drop=True)
bottom10 = df_sorted.tail(10).iloc[::-1][["시도", "시군구", "총인구", "17_19세비율", "65세이상비율"]].reset_index(drop=True)

# 표 컬럼명 변경
rename_cols = {
    "17_19세비율": "17~19세 비율(%)",
    "65세이상비율": "65세 이상 비율(%)",
    "총인구": "총 인구수(명)"
}
top10 = top10.rename(columns=rename_cols)
bottom10 = bottom10.rename(columns=rename_cols)

# 2개 컬럼 레이아웃으로 표 나란히 배치
col1, col2 = st.columns(2)

with col1:
    st.markdown("##### 🔝 17세~19세 비율 가장 높은 지역 Top 10")
    st.dataframe(top10, use_container_width=True)

with col2:
    st.markdown("##### 🔻 17세~19세 비율 가장 낮은 지역 Bottom 10")
    st.dataframe(bottom10, use_container_width=True)
