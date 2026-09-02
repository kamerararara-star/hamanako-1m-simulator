
import streamlit as st
import numpy as np
import pandas as pd

st.set_page_config(page_title="浜名湖 1M展開シミュレーター", page_icon="🚤", layout="centered")

st.title("🚤 浜名湖 1M展開シミュレーター")
st.caption("展示ST・展示タイム・進入・風から、第1ターンマークの展開を簡易モンテカルロ計算します。")

st.info("※これは試作モデルです。実際の舟券購入判断を保証するものではありません。")

# ---- Inputs ----
col1, col2 = st.columns(2)
with col1:
    wind_speed = st.number_input("風速 (m)", min_value=0.0, max_value=15.0, value=3.0, step=0.5)
with col2:
    wind_direction = st.selectbox("風向", ["向かい風", "追い風", "左横風", "右横風", "無風"])

st.subheader("6艇の展示データ")

default_st = [0.14, 0.15, 0.16, 0.17, 0.18, 0.19]
default_time = [6.72, 6.75, 6.78, 6.76, 6.80, 6.83]
default_course = [1, 2, 3, 4, 5, 6]

rows = []
for i in range(6):
    c1, c2, c3 = st.columns(3)
    with c1:
        st_val = st.number_input(f"{i+1}号艇 ST", min_value=0.01, max_value=0.50,
                                 value=default_st[i], step=0.01, format="%.2f", key=f"st{i}")
    with c2:
        time_val = st.number_input(f"{i+1}号艇 展示タイム", min_value=6.00, max_value=8.00,
                                   value=default_time[i], step=0.01, format="%.2f", key=f"time{i}")
    with c3:
        course_val = st.number_input(f"{i+1}号艇 進入", min_value=1, max_value=6,
                                     value=default_course[i], step=1, key=f"course{i}")
    rows.append([i+1, st_val, time_val, course_val])

boats = pd.DataFrame(rows, columns=["艇", "展示ST", "展示タイム", "進入"])

n_sim = st.slider("シミュレーション回数", 1000, 50000, 10000, step=1000)

# ---- Simulation ----
def simulate(df, wind_speed, wind_direction, n_sim):
    stv = df["展示ST"].to_numpy()
    et = df["展示タイム"].to_numpy()
    course = df["進入"].to_numpy()

    # 簡易スコア：
    # STを強く評価、展示タイムも評価、コースを補正。
    st_score = (0.22 - stv) * 50.0
    time_score = (et.mean() - et) * 35.0
    course_score = (7 - course) * 0.75

    # 風の簡易補正（実測データで後から学習可能）
    if wind_direction == "向かい風":
        wind_score = -(course - 1) * wind_speed * 0.08
    elif wind_direction == "追い風":
        wind_score = (course - 1) * wind_speed * 0.05
    elif wind_direction in ("左横風", "右横風"):
        wind_score = -np.abs(course - 3.5) * wind_speed * 0.015
    else:
        wind_score = np.zeros(6)

    base = st_score + time_score + course_score + wind_score

    rng = np.random.default_rng()
    # 1Mまでの不確実性
    samples = base[None, :] + rng.normal(0, 1.45, size=(n_sim, 6))
    order = np.argsort(samples, axis=1)[:, ::-1]

    first = order[:, 0] + 1
    second = order[:, 1] + 1
    third = order[:, 2] + 1

    win_prob = pd.Series(first).value_counts(normalize=True).reindex(range(1, 7), fill_value=0) * 100

    # 展開タイプの簡易分類
    pattern = []
    for a, b in zip(first, second):
        if a == 1:
            pattern.append("逃げ")
        elif a == 2:
            pattern.append("差し")
        elif a in (3, 4) and b == 1:
            pattern.append("まくり")
        elif a in (3, 4, 5, 6):
            pattern.append("まくり差し")
        else:
            pattern.append("その他")

    pattern_prob = pd.Series(pattern).value_counts(normalize=True) * 100
    pattern_prob = pattern_prob.reindex(["逃げ", "差し", "まくり", "まくり差し", "その他"], fill_value=0)

    # 上位の1-2-3着組み合わせ
    combos = pd.DataFrame({"1着": first, "2着": second, "3着": third})
    combo_prob = (
        combos.value_counts(normalize=True)
        .reset_index(name="確率")
        .head(10)
    )
    combo_prob["確率"] *= 100
    combo_prob["3連単"] = (
        combo_prob["1着"].astype(str)
        + "-"
        + combo_prob["2着"].astype(str)
        + "-"
        + combo_prob["3着"].astype(str)
    )

    return win_prob, pattern_prob, combo_prob, base

if st.button("🚤 1Mをシミュレーション", type="primary", use_container_width=True):
    win_prob, pattern_prob, combo_prob, base = simulate(
        boats, wind_speed, wind_direction, n_sim
    )

    st.subheader("1M先頭確率")
    result = pd.DataFrame({
        "艇": range(1, 7),
        "1M先頭確率": [f"{win_prob[i]:.1f}%" for i in range(1, 7)]
    })
    st.dataframe(result, use_container_width=True, hide_index=True)

    st.subheader("1M展開パターン")
    pattern_df = pattern_prob.reset_index()
    pattern_df.columns = ["展開", "確率"]
    pattern_df["確率"] = pattern_df["確率"].map(lambda x: f"{x:.1f}%")
    st.dataframe(pattern_df, use_container_width=True, hide_index=True)

    st.subheader("上位3連単（1M出口イメージ）")
    show_combo = combo_prob[["3連単", "確率"]].copy()
    show_combo["確率"] = show_combo["確率"].map(lambda x: f"{x:.1f}%")
    st.dataframe(show_combo, use_container_width=True, hide_index=True)

    st.subheader("今回の1M相対スコア")
    score_df = boats[["艇", "展示ST", "展示タイム", "進入"]].copy()
    score_df["1M相対スコア"] = np.round(base, 2)
    st.dataframe(score_df, use_container_width=True, hide_index=True)

    st.warning("このモデルは現段階では統計学習前の簡易モデルです。過去の浜名湖実績データを学習させることで、展開確率を改善できます。")

st.divider()
st.caption("浜名湖1M展開シミュレーター / prototype")
