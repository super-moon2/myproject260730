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
* 상단에서 **시도**를 선택하면 해당 지역만 지도에 색상이 칠해지며, 하단의 **상위/하위 10개 지역 표**도 함께 연동됩니다.
""")

# -----------------------------------------------------------------------------
# 2. 데이터 및 지도 데이터 로드 (캐싱 적용)
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

    return df_grouped, geojson_data, latest_year

# 데이터 준비
with st.spinner("데이터와 지도 경계를 불러오는 중입니다..."):
    df_sigungu, geojson_kr, current_year = load_data()

st.subheader(f"📅 분석 기준 연도: {current_year}년")

# -----------------------------------------------------------------------------
# 3. 지도 상단 '시도' 선택 필터
# -----------------------------------------------------------------------------
all_sido = sorted(df_sigungu["시도"].unique())

selected_sido = st.multiselect(
    "🔍 지도에 색상을 칠할 '시도'를 선택해 주세요 (비어있으면 전체 시도를 표시합니다):",
    options=all_sido,
    default=[]  # 기본값은 전체 표시
)

# 선택 조건에 따라 지도 표시용 데이터프레임 생성
df_map = df_sigungu.copy()

if selected_sido:
    # 선택된 시도만 실제 비율 구간을 유지하고, 나머지는 '선택 안됨' 회색 처리
    df_map["색상구간"] = df_map.apply(
        lambda row: str(row["비율구간"]) if row["시도"] in selected_sido else "선택 안됨",
        axis=1
    )
else:
    # 선택된 것이 없으면 전체 지역의 비율 구간 표시
    df_map["색상구간"] = df_map["비율구간"].astype(str)

# -----------------------------------------------------------------------------
# 4. 단계구분도(Choropleth) 생성 및 경계선(시군구 1pt, 시도 3pt) 설정
# -----------------------------------------------------------------------------
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

# 4-1. 기본 시군구 단계구분도 (시군구 경계선 1pt 적용)
fig = px.choropleth_mapbox(
    df_map,
    geojson=geojson_kr,
    locations="sigungu_code",
    featureidkey="properties.코드",
    color="색상구간",
    color_discrete_map=color_discrete_map,
    category_orders={"색상구간": category_order},
    mapbox_style="white-bg",
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

# 시군구 경계선 굵기 1pt 설정
fig.update_traces(
    marker_line_width=1,
    marker_line_color="#888888"
)

# 4-2. 시도 경계선을 3pt 두께로 굵게 표시하기 위한 트레이스 생성
# GeoJSON 내의 좌표들을 시도별로 그룹화하여 외곽선 레이어를 별도로 얹습니다.
for feature in geojson_kr["features"]:
    props = feature["properties"]
    sido_name = props.get("시도", "")
    geom = feature["geometry"]
    
    # 선택된 시도가 있거나 전체 보기일 때 시도 외곽선 3pt 도출
    border_color = "#111111" if (not selected_sido or sido_name in selected_sido) else "#aaaaaa"
    
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
                line=dict(width=3, color=border_color), # 시도 경계선 굵기 3pt
                hoverinfo="skip",
                showlegend=False
            )
        )

# 4-3. 시군구 이름 검정색 50% 텍스트 표시
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

# 지도 레이아웃 세부 설정
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
# 5. 선택된 시도에 연동되는 하단 상위/하위 10개 지역 표
# -----------------------------------------------------------------------------
st.markdown("---")

# 선택 여부에 따른 표용 데이터 필터링
if selected_sido:
    df_filtered = df_sigungu[df_sigungu["시도"].isin(selected_sido)].copy()
    sido_label = ", ".join(selected_sido)
    st.subheader(f"📊 [{sido_label}] 지역 내 17세~19세 인구 비율 상위/하위 지역")
else:
    df_filtered = df_sigungu.copy()
    st.subheader("📊 전국 기준 17세~19세 인구 비율 상위/하위 10개 지역")

# 비율 기준 내림차순 정렬
df_sorted = df_filtered.sort_values(by="17_19세비율", ascending=False)

# 선택 지역 수가 10개 미만일 경우 전체 출력 처리
top_n = min(10, len(df_sorted))

top10 = df_sorted.head(top_n)[["시도", "시군구", "총인구", "청소년인구", "17_19세비율"]].reset_index(drop=True)
bottom10 = df_sorted.tail(top_n).iloc[::-1][["시도", "시군구", "총인구", "청소년인구", "17_19세비율"]].reset_index(drop=True)

rename_cols = {
    "총인구": "총 인구수(명)",
    "청소년인구": "17~19세 인구수(명)",
    "17_19세비율": "17~19세 비율(%)"
}

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"##### 🔝 17세~19세 비율 가장 높은 지역 Top {top_n}")
    st.dataframe(top10.rename(columns=rename_cols), use_container_width=True)

with col2:
    st.markdown(f"##### 🔻 17세~19세 비율 가장 낮은 지역 Bottom {top_n}")
    st.dataframe(bottom10.rename(columns=rename_cols), use_container_width=True)
