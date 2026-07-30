import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. 스트림릿 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 시도/시군구 17~19세 청소년 인구 지도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시도/시군구 17세~19세 인구 비율 지형도")
st.markdown("""
* 전국 읍·면·동 인구 데이터를 바탕으로 시군구별 **17세~19세 인구 비율**을 시각화합니다.
* 상단에서 **연도**와 **시도**를 선택하면 해당 연도 및 지역의 데이터가 지도에 자동 반영·확대됩니다.
""")

# -----------------------------------------------------------------------------
# 2. 데이터 및 지도 데이터 로드 (캐싱 적용)
# -----------------------------------------------------------------------------
@st.cache_data
def load_raw_data():
    # 2-1. GeoJSON 지도 경계 데이터 불러오기
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    geojson_data = requests.get(geojson_url).json()

    # 2-2. 전체 인구 데이터 불러오기 ('코드' 열은 문자열 str 형태 유지)
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(pop_url, dtype={"코드": str})
    
    return df, geojson_data

# 데이터 준비
with st.spinner("데이터와 지도 경계를 불러오는 중입니다..."):
    df_raw, geojson_kr = load_raw_data()

# -----------------------------------------------------------------------------
# 3. 분석 연도 및 시도 선택 필터 (상단 드롭다운)
# -----------------------------------------------------------------------------
available_years = sorted(df_raw["연도"].unique(), reverse=True) # 내림차순 정렬 (최신 연도 우선)

col_year, col_sido = st.columns([1, 3])

with col_year:
    selected_year = st.selectbox(
        "📅 분석 연도 선택:",
        options=available_years,
        index=0  # 가장 최신 연도를 기본값으로 지정
    )

# 선택된 연도 데이터 필터링 및 가공
df_year = df_raw[df_raw["연도"] == selected_year].copy()
df_year["sigungu_code"] = df_year["코드"].str.slice(0, 5)

# 나이별 열 분류 (17세~19세, 전체 인구)
total_cols = [c for c in df_year.columns if c.startswith("계_")]
youth_cols = ["계_17세", "계_18세", "계_19세"]
youth_cols = [c for c in youth_cols if c in df_year.columns]

# 시군구 단위 그룹화 및 비율 계산
group_cols = ["sigungu_code", "시도", "시군구"]
df_sigungu = df_year.groupby(group_cols)[total_cols].sum().reset_index()

df_sigungu["총인구"] = df_sigungu[total_cols].sum(axis=1)
df_sigungu["청소년인구"] = df_sigungu[youth_cols].sum(axis=1)
df_sigungu["17_19세비율"] = (df_sigungu["청소년인구"] / df_sigungu["총인구"] * 100).round(2)

bins = [-1, 1.5, 2.0, 2.5, 3.0, 100]
labels = ["1.5% 미만", "1.5% 이상 ~ 2.0% 미만", "2.0% 이상 ~ 2.5% 미만", "2.5% 이상 ~ 3.0% 미만", "3.0% 이상"]
df_sigungu["비율구간"] = pd.cut(df_sigungu["17_19세비율"], bins=bins, labels=labels)

# 시도 필터링
all_sido = sorted(df_sigungu["시도"].unique())

with col_sido:
    selected_sido = st.multiselect(
        "🔍 지도에 색상을 칠할 '시도'를 선택해 주세요 (비어있으면 전체 시도를 표시합니다):",
        options=all_sido,
        default=[]  # 기본값은 전체 표시
    )

# 선택 조건에 따라 지도 표시용 데이터프레임 생성
df_map = df_sigungu.copy()

if selected_sido:
    df_map["색상구간"] = df_map.apply(
        lambda row: str(row["비율구간"]) if row["시도"] in selected_sido else "선택 안됨",
        axis=1
    )
else:
    df_map["색상구간"] = df_map["비율구간"].astype(str)

# -----------------------------------------------------------------------------
# 4. 지도 중심좌표(Center) 및 확대 기본값(Zoom) 계산
# -----------------------------------------------------------------------------
center_lat, center_lon = 35.8, 127.8
zoom_level = 6.2

if selected_sido:
    selected_lats = []
    selected_lons = []
    
    for feature in geojson_kr["features"]:
        sido_name = feature["properties"].get("시도", "")
        if sido_name in selected_sido:
            geom = feature["geometry"]
            coords = geom["coordinates"]
            
            all_coords = []
            if geom["type"] == "Polygon":
                all_coords = coords[0]
            elif geom["type"] == "MultiPolygon":
                for poly in coords:
                    all_coords.extend(poly[0])
            
            for c in all_coords:
                selected_lons.append(c[0])
                selected_lats.append(c[1])
                
    if selected_lats and selected_lons:
        min_lat, max_lat = min(selected_lats), max(selected_lats)
        min_lon, max_lon = min(selected_lons), max(selected_lons)
        
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        
        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon
        max_span = max(lat_span, lon_span)
        
        if max_span < 0.3:
            zoom_level = 9.8
        elif max_span < 0.8:
            zoom_level = 8.8
        elif max_span < 1.5:
            zoom_level = 7.8
        elif max_span < 2.5:
            zoom_level = 7.2
        else:
            zoom_level = 6.5

# -----------------------------------------------------------------------------
# 5. 단계구분도(Choropleth) 생성 및 경계선 설정
# -----------------------------------------------------------------------------
color_discrete_map = {
    "1.5% 미만": "#f2f0f7",
    "1.5% 이상 ~ 2.0% 미만": "#cbd5e8",
    "2.0% 이상 ~ 2.5% 미만": "#9ecae1",
    "2.5% 이상 ~ 3.0% 미만": "#4292c6",
    "3.0% 이상": "#084594",
    "선택 안됨": "#e0e0e0"
}

category_order = ["1.5% 미만", "1.5% 이상 ~ 2.0% 미만", "2.0% 이상 ~ 2.5% 미만", "2.5% 이상 ~ 3.0% 미만", "3.0% 이상"]
if "선택 안됨" in df_map["색상구간"].values:
    category_order.append("선택 안됨")

# 5-1. 기본 시군구 단계구분도
fig = px.choropleth_mapbox(
    df_map,
    geojson=geojson_kr,
    locations="sigungu_code",
    featureidkey="properties.코드",
    color="색상구간",
    color_discrete_map=color_discrete_map,
    category_orders={"색상구간": category_order},
    mapbox_style="white-bg",
    center={"lat": center_lat, "lon": center_lon},
    zoom=zoom_level,
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

# 시군구 구분 경계선을 50% 불투명도(rgba)로 설정
fig.update_traces(
    marker_line_width=1,
    marker_line_color="rgba(136, 136, 136, 0.5)"  # 회색 50% 불투명도 적용
)

# 5-2. 시도 경계선을 선명하고 굵게(3pt) 강조 표시
for feature in geojson_kr["features"]:
    props = feature["properties"]
    sido_name = props.get("시도", "")
    geom = feature["geometry"]
    
    # 선택된 시도는 선명한 검은색, 나머지는 50% 불투명도의 검은색/회색 적용
    if not selected_sido or sido_name in selected_sido:
        border_color = "rgba(0, 0, 0, 1.0)"  # 굵고 선명한 검은색 시도 경계선
    else:
        border_color = "rgba(170, 170, 170, 0.5)"  # 50% 불투명도 적용
    
    coords_list = []
    if geom["type"] == "Polygon":
        coords_list = [geom["coordinates"][0]]
    elif geom["type"] == "MultiPolygon":
        coords_list = [poly[0] for poly in geom["coordinates"]]
        
    for poly in coords_list:
        lons = [c[0] for c in poly]
        lats = [c[1] for c in poly]
        
        fig.add_trace(
            go.Scattermapbox(
                lon=lons,
                lat=lats,
                mode="lines",
                line=dict(width=3, color=border_color),  # 굵은 시도 경계선
                hoverinfo="skip",
                showlegend=False
            )
        )

# 5-3. 시군구 이름 텍스트 표시 (50% 불투명도 유지)
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
        textfont=dict(size=9, color="rgba(0, 0, 0, 0.5)"),  # 50% 불투명도
        hoverinfo="skip",
        showlegend=False
    )
)

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

st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 6. 하단 상위/하위 지역 표 (연도 및 시도 필터 연동)
# -----------------------------------------------------------------------------
st.markdown("---")

if selected_sido:
    df_filtered = df_sigungu[df_sigungu["시도"].isin(selected_sido)].copy()
    sido_label = ", ".join(selected_sido)
    target_count = 5
    st.subheader(f"📊 [{selected_year}년 {sido_label}] 지역 내 17세~19세 인구 비율 상위/하위 {target_count}개 지역")
else:
    df_filtered = df_sigungu.copy()
    target_count = 10
    st.subheader(f"📊 [{selected_year}년] 전국 기준 17세~19세 인구 비율 상위/하위 {target_count}개 지역")

df_sorted = df_filtered.sort_values(by="17_19세비율", ascending=False)

show_n = min(target_count, len(df_sorted))

top_df = df_sorted.head(show_n)[["시도", "시군구", "총인구", "청소년인구", "17_19세비율"]].reset_index(drop=True)
bottom_df = df_sorted.tail(show_n).iloc[::-1][["시도", "시군구", "총인구", "청소년인구", "17_19세비율"]].reset_index(drop=True)

top_df.index = range(1, len(top_df) + 1)
bottom_df.index = range(1, len(bottom_df) + 1)

rename_cols = {
    "총인구": "총 인구수(명)",
    "청소년인구": "17~19세 인구수(명)",
    "17_19세비율": "17~19세 비율(%)"
}

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"##### 🔝 17세~19세 비율 가장 높은 지역 Top {show_n}")
    st.dataframe(top_df.rename(columns=rename_cols), use_container_width=True)

with col2:
    st.markdown(f"##### 🔻 17세~19세 비율 가장 낮은 지역 Bottom {show_n}")
    st.dataframe(bottom_df.rename(columns=rename_cols), use_container_width=True)
