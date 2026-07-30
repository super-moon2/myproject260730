import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. 스트림릿 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 시군구 17~19세 청소년 인구 지도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시군구 17세~19세 인구 비율 지형도")
st.markdown("""
* 전국 읍·면·동 인구 데이터를 바탕으로 시군구별 **17세~19세 인구 비율**을 시각화합니다.
* 상단 리스트에서 원하는 지역을 선택하면 **선택한 지역만 색상이 칠해집니다.**
""")

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 전처리 (캐싱 적용)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 2-1. GeoJSON 지도 경계 데이터 불러오기
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    geojson_data = requests.get(geojson_url).json()

    # 2-2. 인구 데이터 불러오기 ('코드' 열은 문자열 str 형태 유지)
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(pop_url, dtype={"코드": str})

    # 최신 연도 자동 추출
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    # '코드' 앞 5자리를 잘라서 시군구 코드 생성
    df_latest["sigungu_code"] = df_latest["코드"].str.slice(0, 5)

    # 2-3. 나이별 열 분류 (17세~19세, 전체 인구)
    total_cols = [c for c in df_latest.columns if c.startswith("계_")]
    youth_cols = ["계_17세", "계_18세", "계_19세"]
    youth_cols = [c for c in youth_cols if c in df_latest.columns]

    # 시군구 단위로 그룹화하여 인구수 합산
    group_cols = ["sigungu_code", "시도", "시군구"]
    df_grouped = df_latest.groupby(group_cols)[total_cols].sum().reset_index()

    # 총인구 및 17~19세 인구 합산 계산
    df_grouped["총인구"] = df_grouped[total_cols].sum(axis=1)
    df_grouped["청소년인구"] = df_grouped[youth_cols].sum(axis=1)

    # 17세~19세 비율(%) 계산
    df_grouped["17_19세비율"] = (df_grouped["청소년인구"] / df_grouped["총인구"] * 100).round(2)

    # 2-4. 17세~19세 비율 5단계 구간 나누기
    bins = [-1, 1.5, 2.0, 2.5, 3.0, 100]
    labels = ["1.5% 미만", "1.5% 이상 ~ 2.0% 미만", "2.0% 이상 ~ 2.5% 미만", "2.5% 이상 ~ 3.0% 미만", "3.0% 이상"]
    df_grouped["비율구간"] = pd.cut(df_grouped["17_19세비율"], bins=bins, labels=labels)

    # 드롭다운 표시용 '시도 시군구' 전체 명칭 생성 (예: 서울특별시 종로구)
    df_grouped["지역명"] = df_grouped["시도"] + " " + df_grouped["시군구"]

    return df_grouped, geojson_data, latest_year

# 데이터 준비
with st.spinner("데이터와 지도 경계를 불러오는 중입니다..."):
    df_sigungu, geojson_kr, current_year = load_data()

st.subheader(f"📅 분석 기준 연도: {current_year}년")

# -----------------------------------------------------------------------------
# 3. 지도 상단 지역 선택 필터 (리스트 형식)
# -----------------------------------------------------------------------------
all_regions = sorted(df_sigungu["지역명"].unique())

selected_regions = st.multiselect(
    "🔍 지도에 색상을 칠할 지역을 선택해 주세요 (비어있으면 전체 지역을 표시합니다):",
    options=all_regions,
    default=[]  # 기본값은 전체 선택 효과를 위해 비워둠
)

# 선택 조건에 따라 표시용 데이터프레임 생성
df_map = df_sigungu.copy()

if selected_regions:
    # 선택된 지역이 있으면 그 외 지역은 '선택 안됨' 처리하여 기본 회색으로 표시
    df_map["색상구간"] = df_map.apply(
        lambda row: str(row["비율구간"]) if row["지역명"] in selected_regions else "선택 안됨",
        axis=1
    )
else:
    # 아무것도 선택하지 않은 경우 전체 표시
    df_map["색상구간"] = df_map["비율구간"].astype(str)

# -----------------------------------------------------------------------------
# 4. 단계구분도(Choropleth) 생성
# -----------------------------------------------------------------------------
# 17~19세 비율용 5단계 색상 팔레트 (연한 보라/푸른색 계열 -> 진한 색)
color_discrete_map = {
    "1.5% 미만": "#f2f0f7",
    "1.5% 이상 ~ 2.0% 미만": "#cbd5e8",
    "2.0% 이상 ~ 2.5% 미만": "#9ecae1",
    "2.5% 이상 ~ 3.0% 미만": "#4292c6",
    "3.0% 이상": "#084594",
    "선택 안됨": "#e0e0e0"  # 선택되지 않은 지역 회색 처리
}

category_order = ["1.5% 미만", "1.5% 이상 ~ 2.0% 미만", "2.0% 이상 ~ 2.5% 미만", "2.5% 이상 ~ 3.0% 미만", "3.0% 이상"]
if "선택 안됨" in df_map["색상구간"].values:
    category_order.append("선택 안됨")

fig = px.choropleth_mapbox(
    df_map,
    geojson=geojson_kr,
    locations="sigungu_code",
    featureidkey="properties.코드",
    color="색상구간",
    color_discrete_map=color_discrete_map,
    category_orders={"색상구간": category_order},
    mapbox_style="white-bg",  # 지도 배경 타일 없이 백색 처리
    center={"lat": 35.8, "lon": 127.8},
    zoom=6.2,
    hover_name="시군구",
    hover_data={
        "sigungu_code": False,
        "시도": True,
        "17_19세비율": ":.2f",
        "색상구간": False
    },
    labels={
        "시도": "시도",
        "17_19세비율": "17세~19세 비율(%)"
    }
)

# 4-1. 경계선 굵기 5pt 적용
fig.update_traces(
    marker_line_width=5,        # 5pt 경계선 굵기
    marker_line_color="#333333" # 경계선 색상 (진한 회색)
)

# 4-2. 시군구 이름 검정색 50% 텍스트 레이어 추가
label_lats, label_lons, label_texts = [], [], []

for feature in geojson_kr["features"]:
    props = feature["properties"]
    geom = feature["geometry"]
    coords = geom["coordinates"]
    
    all_coords = []
    if geom["type"] == "Polygon":
        all_coords = coords[0]
    elif geom["type"] == "MultiPolygon":
        for poly in coords:
            all_coords.extend(poly[0])
            
    if all_coords:
        lons = [c[0] for c in all_coords]
        lats = [c[1] for c in all_coords]
        label_lons.append(sum(lons) / len(lons))
        label_lats.append(sum(lats) / len(lats))
        label_texts.append(props.get("시군구", ""))

fig.add_trace(
    go.Scattermapbox(
        lat=label_lats,
        lon=label_lons,
        mode="text",
        text=label_texts,
        textfont=dict(size=9, color="rgba(0, 0, 0, 0.5)"),
        hoverinfo="skip",
        showlegend=False
    )
)

# 지도 레이아웃 설정
fig.update_layout(
    margin={"r": 0, "t": 20, "l": 0, "b": 0},
    height=650,
    legend_title_text="17세~19세 인구 비율",
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
# 5. 하단 17세~19세 비율 상위/하위 10개 지역 표 표시
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📊 17세~19세 인구 비율 상위/하위 10개 지역")

df_sorted = df_sigungu.sort_values(by="17_19세비율", ascending=False)

top10 = df_sorted.head(10)[["시도", "시군구", "총인구", "청소년인구", "17_19세비율"]].reset_index(drop=True)
bottom10 = df_sorted.tail(10).iloc[::-1][["시도", "시군구", "총인구", "청소년인구", "17_19세비율"]].reset_index(drop=True)

rename_cols = {
    "총인구": "총 인구수(명)",
    "청소년인구": "17~19세 인구수(명)",
    "17_19세비율": "17~19세 비율(%)"
}

col1, col2 = st.columns(2)

with col1:
    st.markdown("##### 🔝 17세~19세 비율 가장 높은 지역 Top 10")
    st.dataframe(top10.rename(columns=rename_cols), use_container_width=True)

with col2:
    st.markdown("##### 🔻 17세~19세 비율 가장 낮은 지역 Bottom 10")
    st.dataframe(bottom10.rename(columns=rename_cols), use_container_width=True)
