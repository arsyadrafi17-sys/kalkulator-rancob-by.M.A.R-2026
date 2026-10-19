"""
================================================================================
Kalkulator Rancob by.M.A.R (AgroStat)
Kalkulator Perancangan Percobaan, ANOVA & Uji Lanjut Otomatis
================================================================================
Aplikasi Web Interaktif Python Streamlit untuk Analisis Data Penelitian Pertanian.
Mendukung 5 Rancangan Percobaan:
1. RAL Non-Faktorial
2. RAK Non-Faktorial
3. RAL Faktorial (a × b)
4. RAK Faktorial (a × b)
5. Split Plot Design (Petak Terbagi - RAK)

Struktur Tab:
Tab 1: 🗺️ Denah Lapang & Pengacakan (Perencanaan Percobaan & Tanaman Sampel)
Tab 2: 📊 Input Matriks Data Pengamatan
Tab 3: 📐 Langkah Perhitungan (FK, JK, KT)
Tab 4: 📋 Tabel Sidik Ragam (ANOVA)
Tab 5: 🔤 Hasil Uji Lanjut (BNT, BNJ, DMRT) & Notasi Huruf
Tab 6: 📥 Export Laporan Excel (.xlsx)

Fitur Khusus:
- Rumus Federer Baku: (t - 1)(r - 1) >= 15 untuk rekomendasi ulangan minimal
- Panduan Tanaman Sampel per Bedengan (Tanaman border vs tanaman sampel efektif)
- Kustomisasi Inisial Notasi Perlakuan (cth: V1-V6 atau P0-P4)
"""

import io
import math
import random
import numpy as np
import pandas as pd
from scipy import stats
import streamlit as st

# -----------------------------------------------------------------------------
# Konfigurasi Halaman & Tema Emerald Modern
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Kalkulator Rancob by.M.A.R",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #065f46;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #4b5563;
        margin-bottom: 1.5rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        background-color: #f0fdf4;
        border-radius: 6px;
        color: #065f46;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #059669 !important;
        color: #ffffff !important;
    }
    .plot-box {
        border-radius: 8px;
        padding: 10px;
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        border-top: 4px solid #059669;
        text-align: center;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-header">🌱 Kalkulator Rancob by.M.A.R</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">AgroStat: Kalkulator Perancangan Percobaan, ANOVA & Uji Lanjut Otomatis (RAL, RAK, Faktorial, Split Plot)</div>',
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Fungsi Bantuan Statistik & Notasi Huruf
# -----------------------------------------------------------------------------
def assign_letters(sorted_means_df, is_sig_func):
    n = len(sorted_means_df)
    if n == 0:
        return []
    if n == 1:
        return ["a"]

    subsets = []
    for i in range(n):
        for j in range(i, n):
            all_non_sig = True
            for u in range(i, j + 1):
                for v in range(u + 1, j + 1):
                    if is_sig_func(u, v):
                        all_non_sig = False
                        break
                if not all_non_sig:
                    break
            if all_non_sig:
                group = list(range(i, j + 1))
                is_contained = any(set(group).issubset(set(s)) for s in subsets)
                if not is_contained:
                    subsets = [s for s in subsets if not set(s).issubset(set(group))]
                    subsets.append(group)

    letters = "abcdefghijklmnopqrstuvwxyz"
    res = {i: [] for i in range(n)}
    subsets.sort(key=lambda x: min(x))

    for g_idx, group in enumerate(subsets):
        char = letters[g_idx % len(letters)]
        for item_idx in group:
            if char not in res[item_idx]:
                res[item_idx].append(char)

    extra_idx = len(subsets)
    for i in range(n):
        if not res[i]:
            res[i].append(letters[extra_idx % len(letters)])
            extra_idx += 1

    return ["".join(sorted(res[i])) for i in range(n)]

def get_studentized_range_q(alpha, k, df):
    try:
        from statsmodels.stats.libqsturng import qsturng
        return float(qsturng(1 - alpha, k, df))
    except Exception:
        z = stats.norm.ppf(0.5 + 0.5 * (1 - alpha) ** (1.0 / k))
        c1 = (z**3 + z) / 4.0
        c2 = (5 * z**5 + 16 * z**3 + 3 * z) / 96.0
        q_inf = math.sqrt(2) * z
        adj = 1.0 + (c1 / df) + (c2 / (df**2))
        return q_inf * adj * (1.0 + (0.12 * math.log(max(k, 2))) / max(df, 3))

# -----------------------------------------------------------------------------
# SIDEBAR: Konfigurasi Rancangan & Rekomendasi Ulangan Federer
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ Konfigurasi Analisis")

design_options = [
    "1. RAL Non-Faktorial",
    "2. RAK Non-Faktorial",
    "3. RAL Faktorial (a × b)",
    "4. RAK Faktorial (a × b)",
    "5. Split Plot Design (Petak Terbagi - RAK)",
]
selected_design = st.sidebar.selectbox("Pilih Rancangan Percobaan:", design_options)

# Inisialisasi awal parameter
if "RAL" in selected_design and "Faktorial" not in selected_design:
    t_default, r_default = 5, 4
    a_val, b_val = 1, 1
elif "RAK" in selected_design and "Faktorial" not in selected_design:
    t_default, r_default = 6, 3
    a_val, b_val = 1, 1
elif "Faktorial" in selected_design:
    a_val, b_val = 3, 3 if "RAL" in selected_design else 2
    t_default = a_val * b_val
    r_default = 3
else:
    # Split Plot
    a_val, b_val = 2, 3
    t_default = a_val * b_val
    r_default = 3

# -----------------------------------------------------------------------------
# REKOMENDASI ULANGAN BERDASARKAN RUMUS FEDERER: (t - 1)(r - 1) >= 15
# -----------------------------------------------------------------------------
st.sidebar.subheader("💡 Rekomendasi Ulangan (Rumus Federer)")

if "Faktorial" not in selected_design and "Split" not in selected_design:
    # (t - 1)(r - 1) >= 15 => (r - 1) >= 15 / (t - 1)
    denom = max(t_default - 1, 1)
    r_federer = max(3, math.ceil(15 / denom + 1))
    st.sidebar.info(f"**Rumus Federer: (t - 1)(r - 1) ≥ 15**\n\nUntuk t = {t_default} perlakuan, disarankan minimal **r = {r_federer} ulangan/kelompok**.")
elif "Faktorial" in selected_design:
    tot_comb = a_val * b_val
    denom = max(tot_comb - 1, 1)
    r_federer = max(2 if "RAL" in selected_design else 3, math.ceil(15 / denom + 1))
    st.sidebar.info(f"**Federer Faktorial: (ab - 1)(r - 1) ≥ 15**\n\nKombinasi ab = {tot_comb}, disarankan minimal **r = {r_federer} ulangan/kelompok**.")
else:
    # Split Plot
    tot_comb = a_val * b_val
    denom = max(a_val * (b_val - 1), 1)
    r_federer = max(3, math.ceil(15 / denom + 1))
    st.sidebar.info(f"**Split Plot: Galat(b) = a(b - 1)(r - 1) ≥ 15**\n\nPetak terbagi (a={a_val}, b={b_val}), disarankan minimal **r = {r_federer} kelompok**.")

# -----------------------------------------------------------------------------
# KUSTOMISASI INISIAL & NOTASI PERLAKUAN
# -----------------------------------------------------------------------------
st.sidebar.subheader("🏷️ Inisial Notasi Perlakuan")

if "Faktorial" not in selected_design and "Split" not in selected_design:
    col_p1, col_p2 = st.sidebar.columns(2)
    with col_p1:
        prefix_treat = st.text_input("Inisial Huruf:", "P").strip().upper() or "P"
    with col_p2:
        start_idx = st.selectbox("Mulai dari:", (0, 1), index=0)
    t_val = st.sidebar.number_input("Jumlah Perlakuan (t):", min_value=2, max_value=30, value=t_default, step=1)
    r_val = st.sidebar.number_input("Jumlah Ulangan/Kelompok (r):", min_value=2, max_value=20, value=r_default, step=1)
    row_labels = [f"{prefix_treat}{start_idx + i}" for i in range(t_val)]
else:
    col_f1, col_f2 = st.sidebar.columns(2)
    with col_f1:
        pref_a = st.text_input("Inisial Faktor A:", "A").strip().upper() or "A"
        start_a = st.selectbox("Mulai A:", (1, 0), index=0)
    with col_f2:
        pref_b = st.text_input("Inisial Faktor B:", "B" if "Split" not in selected_design else "P").strip().upper() or "B"
        start_b = st.selectbox("Mulai B:", (1, 0), index=0)

    a_val = st.sidebar.number_input("Level Faktor A (a):", min_value=2, max_value=10, value=a_val, step=1)
    b_val = st.sidebar.number_input("Level Faktor B (b):", min_value=2, max_value=10, value=b_val, step=1)
    t_val = a_val * b_val
    col_label = "Ulangan (r)" if "RAL" in selected_design else "Kelompok (r)"
    r_val = st.sidebar.number_input(f"Jumlah {col_label}:", min_value=2, max_value=20, value=r_default, step=1)
    row_labels = [f"{pref_a}{start_a + i}{pref_b}{start_b + j}" for i in range(a_val) for j in range(b_val)]

col_prefix = "K" if "RAK" in selected_design or "Split" in selected_design else "U"
col_labels = [f"{col_prefix}{j+1}" for j in range(r_val)]

posthoc_choice = st.sidebar.radio(
    "Pilih Uji Lanjut (Post-Hoc):",
    ("BNT 5% (LSD)", "BNJ 5% (Tukey HSD)", "DMRT 5% (Duncan)"),
)

variable_name = st.sidebar.text_input("Nama Peubah Diamati:", "Hasil Gabah / Produksi")
unit_name = st.sidebar.text_input("Satuan Pengamatan:", "ton/ha")

# Inisialisasi Matriks Data
if "current_design" not in st.session_state or st.session_state.current_design != selected_design:
    st.session_state.current_design = selected_design
    np.random.seed(42)
    st.session_state.data_matrix = np.round(np.random.uniform(12.0, 26.0, size=(t_val, r_val)), 2)

if st.sidebar.button("🎲 Muat Data Demo Pertanian"):
    np.random.seed(int(t_val * 7 + r_val * 3))
    demo_data = np.zeros((t_val, r_val))
    for i in range(t_val):
        effect = (i + 1) * 3.2
        demo_data[i, :] = np.round(14.0 + effect + np.random.normal(0, 0.7, size=r_val), 2)
    st.session_state.data_matrix = demo_data
    st.sidebar.success("Data demo berhasil dimuat!")

# Upload File Excel lokal
uploaded_file = st.sidebar.file_uploader("📂 Import Excel lokal (.xlsx, .csv):", type=["xlsx", "xls", "csv"])
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            df_upload = pd.read_csv(uploaded_file, index_col=0)
        else:
            df_upload = pd.read_excel(uploaded_file, index_col=0)
        st.session_state.data_matrix = df_upload.values.astype(float)
        st.sidebar.success("File Excel berhasil diimpor!")
    except Exception as e:
        st.sidebar.error(f"Gagal membaca file: {e}")

# Sesuaikan dimensi data jika berubah
curr_matrix = st.session_state.data_matrix
if curr_matrix.shape != (t_val, r_val):
    new_matrix = np.zeros((t_val, r_val))
    min_r = min(curr_matrix.shape[0], t_val)
    min_c = min(curr_matrix.shape[1], r_val)
    new_matrix[:min_r, :min_c] = curr_matrix[:min_r, :min_c]
    st.session_state.data_matrix = new_matrix

# -----------------------------------------------------------------------------
# STRUKTUR TAB UTAMA (TAB 1 ADALAH DENAH LAPANG & PANDUAN SAMPEL)
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🗺️ Denah Lapang & Acak",
    "📊 Input Matriks Data",
    "📐 Langkah Perhitungan",
    "📋 Tabel ANOVA Lengkap",
    "🔤 Hasil Uji Lanjut & Notasi",
    "📥 Export & Download (.xlsx)",
])

# =============================================================================
# TAB 1: Denah Lapang, Pengacakan & Panduan Tanaman Sampel
# =============================================================================
with tab1:
    st.subheader("🗺️ Denah Tata Letak Petakan, Pengacakan & Panduan Sampel")
    st.write(f"Total Unit Percobaan: **{t_val * r_val} bedengan/plot**.")

    # PANDUAN PENGAMBILAN SAMPEL TANAMAN
    st.markdown("### 🌿 Panduan Pengambilan Tanaman Sampel per Bedengan")
    st.info("""
    **Apakah seluruh tanaman di bedengan diukur lalu dimasukkan ke matriks?**  
    **TIDAK.** Nilai yang dimasukkan ke dalam 1 sel Matriks ANOVA adalah **NILAI RATA-RATA** dari tanaman sampel pada petak tersebut (atau total hasil panen petak efektif).
    - **Tanaman Pinggir (Border Plants):** Tanaman di tepi luar bedengan tidak boleh diambil sebagai sampel karena mengalami *border effect* (cahaya dan hara tidak seimbang).
    - **Tanaman Petak Efektif:** Pilih 3–5 tanaman sampel secara acak dari barisan bagian dalam.
    - **Input Data ke Matriks:** Nilai sel = $(y_1 + y_2 + y_3 + ... + y_k) / k$.
    """)

    col_cp1, col_cp2 = st.columns([1, 2])
    with col_cp1:
        compass_opt = st.selectbox("Arah Hadap Bedengan:", ("Utara - Selatan (0°)", "Timur - Barat (90°)", "Selatan - Utara (180°)", "Barat - Timur (270°)"))
        st.caption("🧭 Bedengan membujur **Utara - Selatan** memaksimalkan penyerapan radiasi matahari pagi & sore secara merata.")
    with col_cp2:
        st.success("💧 **Parit & Saluran:** Sediakan parit selebar 40–50 cm antar bedengan dan parit kelompok 80–100 cm sebagai jalan kontrol.")

    seed_val = st.number_input("Nomor Seed Acak:", value=42, step=1)
    random.seed(seed_val)

    st.write("##### 🌿 Peta Bedengan di Lahan:")
    if "RAL" in selected_design:
        all_units = []
        for t_idx, code in enumerate(row_labels):
            for rep_idx in range(r_val):
                all_units.append(code)
        random.shuffle(all_units)

        cols_per_row = 6
        num_plots = len(all_units)
        for i in range(0, num_plots, cols_per_row):
            row_plots = all_units[i : i + cols_per_row]
            c_grid = st.columns(len(row_plots))
            for c_idx, code in enumerate(row_plots):
                with c_grid[c_idx]:
                    st.markdown(f'<div class="plot-box"><strong>Plot #{i + c_idx + 1}</strong><br><span style="color:#059669; font-size:1.1rem; font-weight:bold;">{code}</span></div>', unsafe_allow_html=True)
    elif selected_design == "5. Split Plot Design (Petak Terbagi - RAK)":
        plot_no = 1
        for k in range(r_val):
            st.markdown(f"**Kelompok {k + 1}:**")
            main_plots = list(range(a_val))
            random.shuffle(main_plots)
            cols_main = st.columns(a_val)
            for m_idx, a_i in enumerate(main_plots):
                with cols_main[m_idx]:
                    prefA_label = row_labels[a_i * b_val][:2]
                    st.caption(f"Petak Utama: {prefA_label}")
                    sub_plots = list(range(b_val))
                    random.shuffle(sub_plots)
                    for b_j in sub_plots:
                        treat_code = row_labels[a_i * b_val + b_j]
                        st.markdown(f'<div class="plot-box"><small>Plot #{plot_no}</small><br><b style="color:#059669;">{treat_code}</b></div>', unsafe_allow_html=True)
                        plot_no += 1
    else:
        # RAK: Acak di dalam masing-masing kelompok
        plot_no = 1
        for k in range(r_val):
            st.markdown(f"**Kelompok {k + 1}:**")
            block_treats = list(row_labels)
            random.shuffle(block_treats)
            c_grid = st.columns(len(block_treats))
            for c_idx, code in enumerate(block_treats):
                with c_grid[c_idx]:
                    st.markdown(f'<div class="plot-box"><strong>Plot #{plot_no}</strong><br><span style="color:#059669; font-size:1.1rem; font-weight:bold;">{code}</span></div>', unsafe_allow_html=True)
                    plot_no += 1

# =============================================================================
# TAB 2: Input Matriks Data Pengamatan
# =============================================================================
with tab2:
    st.subheader("📊 Matriks Data Pengamatan")
    st.write(f"Peubah: **{variable_name}** ({unit_name})")

    df_edit = pd.DataFrame(st.session_state.data_matrix, index=row_labels, columns=col_labels)
    edited_df = st.data_editor(df_edit, use_container_width=True)
    st.session_state.data_matrix = edited_df.values

    data = st.session_state.data_matrix
    row_sums = np.sum(data, axis=1)
    row_means = np.mean(data, axis=1)
    col_sums = np.sum(data, axis=0)
    grand_total = np.sum(data)
    n_total = data.size
    grand_mean = grand_total / n_total if n_total > 0 else 0

    df_display = edited_df.copy()
    df_display["Total (Yi.)"] = np.round(row_sums, 4)
    df_display["Rata-rata (Ȳi)"] = np.round(row_means, 4)
    footer_vals = list(np.round(col_sums, 4)) + [round(grand_total, 4), round(grand_mean, 4)]
    df_display.loc["Grand Total"] = footer_vals
    st.dataframe(df_display.style.format("{:.2f}"), use_container_width=True)

# =============================================================================
# KALKULASI ANOVA
# =============================================================================
fk = (grand_total**2) / n_total
sum_sq_all = np.sum(data**2)
jkt = sum_sq_all - fk
dbt = n_total - 1

def get_ket(f_hit, f_05, f_01):
    if f_hit is None or f_05 is None: return "-"
    if f_hit >= f_01: return "**"
    elif f_hit >= f_05: return "*"
    else: return "tn"

if selected_design == "1. RAL Non-Faktorial":
    t, r = t_val, r_val
    dbp, dbg = t - 1, t * (r - 1)
    jkp = (np.sum(row_sums**2) / r) - fk
    jkg = max(0.0, jkt - jkp)
    ktp = jkp / dbp if dbp > 0 else 0
    ktg = jkg / dbg if dbg > 0 else 0
    f_p = ktp / ktg if ktg > 0 else 0
    f_05, f_01 = stats.f.ppf(0.95, dbp, dbg), stats.f.ppf(0.99, dbp, dbg)

    sk_list = ["Perlakuan", "Galat", "Total"]
    db_list, jk_list, kt_list = [dbp, dbg, dbt], [jkp, jkg, jkt], [ktp, ktg, None]
    f_hit_list, f_05_list, f_01_list = [f_p, None, None], [f_05, None, None], [f_01, None, None]
    ket_list = [get_ket(f_p, f_05, f_01), "-", "-"]
    calc_steps = [
        {"Komponen": "FK", "Rumus": "(Grand Total)² / N", "Substitusi": f"({grand_total:.2f})² / {n_total}", "Nilai": fk},
        {"Komponen": "JKT", "Rumus": "∑(Yij²) - FK", "Substitusi": f"{sum_sq_all:.4f} - {fk:.4f}", "Nilai": jkt},
        {"Komponen": "JKP", "Rumus": "(∑(Yi.)² / r) - FK", "Substitusi": f"({np.sum(row_sums**2):.2f} / {r}) - {fk:.4f}", "Nilai": jkp},
        {"Komponen": "JKG", "Rumus": "JKT - JKP", "Substitusi": f"{jkt:.4f} - {jkp:.4f}", "Nilai": jkg},
        {"Komponen": "KTP", "Rumus": "JKP / DBP", "Substitusi": f"{jkp:.4f} / {dbp}", "Nilai": ktp},
        {"Komponen": "KTG", "Rumus": "JKG / DBG", "Substitusi": f"{jkg:.4f} / {dbg}", "Nilai": ktg},
    ]
    posthoc_ktg, posthoc_dbg, posthoc_r = ktg, dbg, r

elif selected_design == "2. RAK Non-Faktorial":
    t, r = t_val, r_val
    dbk, dbp, dbg = r - 1, t - 1, (t - 1) * (r - 1)
    jkk = (np.sum(col_sums**2) / t) - fk
    jkp = (np.sum(row_sums**2) / r) - fk
    jkg = max(0.0, jkt - jkk - jkp)
    ktk = jkk / dbk if dbk > 0 else 0
    ktp = jkp / dbp if dbp > 0 else 0
    ktg = jkg / dbg if dbg > 0 else 0
    f_k = ktk / ktg if ktg > 0 else 0
    f_p = ktp / ktg if ktg > 0 else 0
    f_05_k, f_01_k = stats.f.ppf(0.95, dbk, dbg), stats.f.ppf(0.99, dbk, dbg)
    f_05_p, f_01_p = stats.f.ppf(0.95, dbp, dbg), stats.f.ppf(0.99, dbp, dbg)

    sk_list = ["Kelompok", "Perlakuan", "Galat", "Total"]
    db_list, jk_list, kt_list = [dbk, dbp, dbg, dbt], [jkk, jkp, jkg, jkt], [ktk, ktp, ktg, None]
    f_hit_list = [f_k, f_p, None, None]
    f_05_list, f_01_list = [f_05_k, f_05_p, None, None], [f_01_k, f_01_p, None, None]
    ket_list = [get_ket(f_k, f_05_k, f_01_k), get_ket(f_p, f_05_p, f_01_p), "-", "-"]
    calc_steps = [
        {"Komponen": "FK", "Rumus": "(Grand Total)² / (t × r)", "Substitusi": f"({grand_total:.2f})² / {n_total}", "Nilai": fk},
        {"Komponen": "JKT", "Rumus": "∑(Yij²) - FK", "Substitusi": f"{sum_sq_all:.4f} - {fk:.4f}", "Nilai": jkt},
        {"Komponen": "JKK", "Rumus": "(∑(Y.j)² / t) - FK", "Substitusi": f"({np.sum(col_sums**2):.2f} / {t}) - {fk:.4f}", "Nilai": jkk},
        {"Komponen": "JKP", "Rumus": "(∑(Yi.)² / r) - FK", "Substitusi": f"({np.sum(row_sums**2):.2f} / {r}) - {fk:.4f}", "Nilai": jkp},
        {"Komponen": "JKG", "Rumus": "JKT - JKK - JKP", "Substitusi": f"{jkt:.4f} - {jkk:.4f} - {jkp:.4f}", "Nilai": jkg},
        {"Komponen": "KTG", "Rumus": "JKG / DBG", "Substitusi": f"{jkg:.4f} / {dbg}", "Nilai": ktg},
    ]
    posthoc_ktg, posthoc_dbg, posthoc_r = ktg, dbg, r

elif "Faktorial" in selected_design:
    a, b, r = a_val, b_val, r_val
    jk_comb = (np.sum(row_sums**2) / r) - fk
    a_sums, b_sums = np.zeros(a), np.zeros(b)
    for i in range(a):
        for j in range(b):
            idx = i * b + j
            a_sums[i] += row_sums[idx]
            b_sums[j] += row_sums[idx]

    jk_a = (np.sum(a_sums**2) / (b * r)) - fk
    jk_b = (np.sum(b_sums**2) / (a * r)) - fk
    jk_ab = max(0.0, jk_comb - jk_a - jk_b)
    db_a, db_b, db_ab = a - 1, b - 1, (a - 1) * (b - 1)

    if "RAK" in selected_design:
        dbk = r - 1
        jkk = (np.sum(col_sums**2) / (a * b)) - fk
        ktk = jkk / dbk if dbk > 0 else 0
        dbg = (a * b - 1) * (r - 1)
        jkg = max(0.0, jkt - jkk - jk_comb)
    else:
        dbg = a * b * (r - 1)
        jkg = max(0.0, jkt - jk_comb)
        jkk, dbk, ktk = 0, 0, 0

    kt_a, kt_b, kt_ab, ktg = jk_a / db_a, jk_b / db_b, jk_ab / db_ab, jkg / dbg
    f_a, f_b, f_ab = kt_a / ktg, kt_b / ktg, kt_ab / ktg
    f_05_a, f_01_a = stats.f.ppf(0.95, db_a, dbg), stats.f.ppf(0.99, db_a, dbg)
    f_05_b, f_01_b = stats.f.ppf(0.95, db_b, dbg), stats.f.ppf(0.99, db_b, dbg)
    f_05_ab, f_01_ab = stats.f.ppf(0.95, db_ab, dbg), stats.f.ppf(0.99, db_ab, dbg)

    if "RAK" in selected_design:
        f_k = ktk / ktg if ktg > 0 else 0
        f_05_k, f_01_k = stats.f.ppf(0.95, dbk, dbg), stats.f.ppf(0.99, dbk, dbg)
        sk_list = ["Kelompok", "Faktor A", "Faktor B", "Interaksi (AxB)", "Galat", "Total"]
        db_list = [dbk, db_a, db_b, db_ab, dbg, dbt]
        jk_list = [jkk, jk_a, jk_b, jk_ab, jkg, jkt]
        kt_list = [ktk, kt_a, kt_b, kt_ab, ktg, None]
        f_hit_list = [f_k, f_a, f_b, f_ab, None, None]
        f_05_list = [f_05_k, f_05_a, f_05_b, f_05_ab, None, None]
        f_01_list = [f_01_k, f_01_a, f_01_b, f_01_ab, None, None]
        ket_list = [get_ket(f_k, f_05_k, f_01_k), get_ket(f_a, f_05_a, f_01_a), get_ket(f_b, f_05_b, f_01_b), get_ket(f_ab, f_05_ab, f_01_ab), "-", "-"]
    else:
        sk_list = ["Faktor A", "Faktor B", "Interaksi (AxB)", "Galat", "Total"]
        db_list = [db_a, db_b, db_ab, dbg, dbt]
        jk_list = [jk_a, jk_b, jk_ab, jkg, jkt]
        kt_list = [kt_a, kt_b, kt_ab, ktg, None]
        f_hit_list = [f_a, f_b, f_ab, None, None]
        f_05_list = [f_05_a, f_05_b, f_05_ab, None, None]
        f_01_list = [f_01_a, f_01_b, f_01_ab, None, None]
        ket_list = [get_ket(f_a, f_05_a, f_01_a), get_ket(f_b, f_05_b, f_01_b), get_ket(f_ab, f_05_ab, f_01_ab), "-", "-"]

    calc_steps = [
        {"Komponen": "FK", "Rumus": "(Grand Total)² / (a × b × r)", "Substitusi": f"({grand_total:.2f})² / {n_total}", "Nilai": fk},
        {"Komponen": "JK A", "Rumus": "(∑(Ai)² / (b × r)) - FK", "Substitusi": f"({np.sum(a_sums**2):.2f} / {b*r}) - {fk:.4f}", "Nilai": jk_a},
        {"Komponen": "JK B", "Rumus": "(∑(Bj)² / (a × r)) - FK", "Substitusi": f"({np.sum(b_sums**2):.2f} / {a*r}) - {fk:.4f}", "Nilai": jk_b},
        {"Komponen": "JK AB", "Rumus": "JK Kombinasi - JKA - JKB", "Substitusi": f"{jk_comb:.4f} - {jk_a:.4f} - {jk_b:.4f}", "Nilai": jk_ab},
        {"Komponen": "KTG", "Rumus": "JKG / DBG", "Substitusi": f"{jkg:.4f} / {dbg}", "Nilai": ktg},
    ]
    posthoc_ktg, posthoc_dbg, posthoc_r = ktg, dbg, r

else:
    # Split Plot
    a, b, r = a_val, b_val, r_val
    dbk, dba, db_ga = r - 1, a - 1, (r - 1) * (a - 1)
    dbb, db_ab, db_gb = b - 1, (a - 1) * (b - 1), a * (b - 1) * (r - 1)
    jkk = (np.sum(col_sums**2) / (a * b)) - fk
    ktk = jkk / dbk if dbk > 0 else 0

    ak_sums, a_sums, b_sums = np.zeros((a, r)), np.zeros(a), np.zeros(b)
    for i in range(a):
        for j in range(b):
            row_idx = i * b + j
            a_sums[i] += row_sums[row_idx]
            b_sums[j] += row_sums[row_idx]
            for k in range(r):
                ak_sums[i, k] += data[row_idx, k]

    jk_ak = (np.sum(ak_sums**2) / b) - fk
    jk_a = (np.sum(a_sums**2) / (b * r)) - fk
    kt_a = jk_a / dba if dba > 0 else 0
    jk_ga = max(0.0, jk_ak - jkk - jk_a)
    kt_ga = jk_ga / db_ga if db_ga > 0 else 0

    jk_b = (np.sum(b_sums**2) / (a * r)) - fk
    kt_b = jk_b / dbb if dbb > 0 else 0
    jk_comb = (np.sum(row_sums**2) / r) - fk
    jk_ab = max(0.0, jk_comb - jk_a - jk_b)
    kt_ab = jk_ab / db_ab if db_ab > 0 else 0
    jk_gb = max(0.0, jkt - jkk - jk_a - jk_ga - jk_b - jk_ab)
    kt_gb = jk_gb / db_gb if db_gb > 0 else 0

    f_k = ktk / kt_ga if kt_ga > 0 else 0
    f_a = kt_a / kt_ga if kt_ga > 0 else 0
    f_b = kt_b / kt_gb if kt_gb > 0 else 0
    f_ab = kt_ab / kt_gb if kt_gb > 0 else 0

    f_05_k, f_01_k = stats.f.ppf(0.95, dbk, db_ga), stats.f.ppf(0.99, dbk, db_ga)
    f_05_a, f_01_a = stats.f.ppf(0.95, dba, db_ga), stats.f.ppf(0.99, dba, db_ga)
    f_05_b, f_01_b = stats.f.ppf(0.95, dbb, db_gb), stats.f.ppf(0.99, dbb, db_gb)
    f_05_ab, f_01_ab = stats.f.ppf(0.95, db_ab, db_gb), stats.f.ppf(0.99, db_ab, db_gb)

    sk_list = ["Kelompok", "Petak Utama (A)", "Galat (a)", "Anak Petak (B)", "Interaksi (AxB)", "Galat (b)", "Total"]
    db_list = [dbk, dba, db_ga, dbb, db_ab, db_gb, dbt]
    jk_list = [jkk, jk_a, jk_ga, jk_b, jk_ab, jk_gb, jkt]
    kt_list = [ktk, kt_a, kt_ga, kt_b, kt_ab, kt_gb, None]
    f_hit_list = [f_k, f_a, None, f_b, f_ab, None, None]
    f_05_list = [f_05_k, f_05_a, None, f_05_b, f_05_ab, None, None]
    f_01_list = [f_01_k, f_01_a, None, f_01_b, f_01_ab, None, None]
    ket_list = [get_ket(f_k, f_05_k, f_01_k), get_ket(f_a, f_05_a, f_01_a), "-", get_ket(f_b, f_05_b, f_01_b), get_ket(f_ab, f_05_ab, f_01_ab), "-", "-"]

    calc_steps = [
        {"Komponen": "FK", "Rumus": "(Grand Total)² / (a × b × r)", "Substitusi": f"({grand_total:.2f})² / {n_total}", "Nilai": fk},
        {"Komponen": "JK A", "Rumus": "(∑(Ai)² / (b × r)) - FK", "Substitusi": f"({np.sum(a_sums**2):.2f} / {b*r}) - {fk:.4f}", "Nilai": jk_a},
        {"Komponen": "JK Galat(a)", "Rumus": "JK(AK) - JKK - JK A", "Substitusi": f"{jk_ak:.4f} - {jkk:.4f} - {jk_a:.4f}", "Nilai": jk_ga},
        {"Komponen": "F-Hit A", "Rumus": "KT A / KT Galat(a)", "Substitusi": f"{kt_a:.4f} / {kt_ga:.4f}", "Nilai": f_a},
        {"Komponen": "F-Hit B", "Rumus": "KT B / KT Galat(b)", "Substitusi": f"{kt_b:.4f} / {kt_gb:.4f}", "Nilai": f_b},
        {"Komponen": "F-Hit AB", "Rumus": "KT AB / KT Galat(b)", "Substitusi": f"{kt_ab:.4f} / {kt_gb:.4f}", "Nilai": f_ab},
    ]
    posthoc_ktg, posthoc_dbg, posthoc_r = kt_gb, db_gb, r

kk_val = (math.sqrt(posthoc_ktg) / grand_mean) * 100 if grand_mean > 0 else 0

# =============================================================================
# TAB 3: Langkah Perhitungan
# =============================================================================
with tab3:
    st.subheader("📐 Langkah Perhitungan Matematis (Transparan)")
    st.dataframe(pd.DataFrame(calc_steps), use_container_width=True)

# =============================================================================
# TAB 4: Tabel ANOVA Lengkap
# =============================================================================
with tab4:
    st.subheader("📋 Tabel Sidik Ragam (ANOVA) Baku")
    anova_dict = {
        "Sumber Keragaman (SK)": sk_list,
        "DB": db_list,
        "Jumlah Kuadrat (JK)": [f"{v:.4f}" if v is not None else "-" for v in jk_list],
        "Kuadrat Tengah (KT)": [f"{v:.4f}" if v is not None else "-" for v in kt_list],
        "F Hitung": [f"{v:.4f}" if v is not None else "-" for v in f_hit_list],
        "F Tabel 0.05": [f"{v:.4f}" if v is not None else "-" for v in f_05_list],
        "F Tabel 0.01": [f"{v:.4f}" if v is not None else "-" for v in f_01_list],
        "Keterangan": ket_list,
    }
    st.dataframe(pd.DataFrame(anova_dict), use_container_width=True)
    st.metric("Koefisien Keragaman (KK)", f"{kk_val:.2f} %")

# =============================================================================
# TAB 5: Hasil Uji Lanjut & Notasi Huruf
# =============================================================================
with tab5:
    st.subheader(f"🔤 Hasil Uji Lanjut: {posthoc_choice}")
    sy = math.sqrt(posthoc_ktg / posthoc_r) if posthoc_r > 0 else 0
    k_treat = len(row_labels)

    df_means = pd.DataFrame({
        "Perlakuan": row_labels,
        "Rata-rata": row_means,
    }).sort_values(by="Rata-rata", ascending=False).reset_index(drop=True)

    crit_values = []
    if "BNT" in posthoc_choice:
        t_crit = stats.t.ppf(0.975, posthoc_dbg)
        bnt_val = t_crit * math.sqrt(2 * posthoc_ktg / posthoc_r)
        crit_values.append({"Parameter": "BNT 5%", "Nilai Tabel": t_crit, "Nilai Kritis Beda": bnt_val})
        is_sig = lambda u, v: abs(df_means.loc[u, "Rata-rata"] - df_means.loc[v, "Rata-rata"]) >= bnt_val
    elif "BNJ" in posthoc_choice:
        q_crit = get_studentized_range_q(0.05, k_treat, posthoc_dbg)
        bnj_val = q_crit * sy
        crit_values.append({"Parameter": "BNJ 5%", "Nilai Tabel (q)": q_crit, "Nilai Kritis Beda": bnj_val})
        is_sig = lambda u, v: abs(df_means.loc[u, "Rata-rata"] - df_means.loc[v, "Rata-rata"]) >= bnj_val
    else:
        dmrt_crit_map = {}
        for p in range(2, k_treat + 1):
            alpha_p = 1.0 - (1.0 - 0.05)**(p - 1)
            q_p = get_studentized_range_q(min(alpha_p, 0.25), p, posthoc_dbg)
            rp = q_p * sy
            dmrt_crit_map[p] = rp
            crit_values.append({"Parameter": f"Rentang p={p}", "Nilai Tabel (SSR)": q_p, "Nilai Kritis Beda (Rp)": rp})
        is_sig = lambda u, v: abs(df_means.loc[u, "Rata-rata"] - df_means.loc[v, "Rata-rata"]) >= dmrt_crit_map.get(abs(u - v) + 1, 0)

    letters_list = assign_letters(df_means, is_sig)
    df_means["Notasi Huruf"] = letters_list
    df_means["Peringkat"] = range(1, len(df_means) + 1)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.write("##### 📋 Tabel Rataan & Notasi Huruf")
        st.dataframe(df_means[["Peringkat", "Perlakuan", "Rata-rata", "Notasi Huruf"]].style.format({"Rata-rata": "{:.3f}"}), use_container_width=True)
    with c2:
        st.write("##### 🎯 Nilai Kritis Pembanding")
        st.dataframe(pd.DataFrame(crit_values).style.format({"Nilai Tabel": "{:.3f}", "Nilai Kritis Beda": "{:.4f}"}), use_container_width=True)

# =============================================================================
# TAB 6: Export & Download Hasil (.xlsx)
# =============================================================================
with tab6:
    st.subheader("📥 Export Laporan Hasil ke Excel (.xlsx)")
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df_display.to_excel(writer, sheet_name="Data Pengamatan")
        pd.DataFrame(calc_steps).to_excel(writer, sheet_name="Langkah Perhitungan", index=False)
        pd.DataFrame(anova_dict).to_excel(writer, sheet_name="Tabel ANOVA", index=False)
        df_means[["Peringkat", "Perlakuan", "Rata-rata", "Notasi Huruf"]].to_excel(writer, sheet_name="Uji Lanjut & Notasi", index=False)

    st.download_button(
        label="📥 Download Laporan Lengkap (.xlsx)",
        data=excel_buffer.getvalue(),
        file_name=f"AgroStat_Analisis_{selected_design.split('.')[1].strip().replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.markdown("---")
st.caption("Dikembangkan dengan penuh dedikasi oleh **arsyad** untuk kemajuan riset sains pertanian Indonesia.")
