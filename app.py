import io
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Warehouse Performance Dashboard",
    page_icon="📦",
    layout="wide",
)

# ---------- Styling ----------
st.markdown("""
<style>
    .stApp { background: #0b1020; color: #f4f7ff; }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #23334f, #131d31);
        border: 1px solid #2a3b5a;
        padding: 16px;
        border-radius: 14px;
    }
    [data-testid="stMetricLabel"] { color: #aab8d0 !important; }
    [data-testid="stMetricValue"] { color: #35d7d0 !important; }
    h1, h2, h3 { color: #f4f7ff; }
    .hint { color: #aab8d0; }
</style>
""", unsafe_allow_html=True)

st.title("📦 Warehouse Performance Dashboard")
st.caption("Daily Operations · Outbound Shift Performance · Picking, Sorting & Packing")

uploaded = st.file_uploader(
    "Upload your daily Excel file",
    type=["xlsx", "xls"],
    help="Upload the latest staff performance workbook. Your data is processed for this session.",
)

if uploaded is None:
    st.info("Upload an Excel file to build the dashboard. If your workbook has multiple sheets, you can select the correct sheet after upload.")
    st.stop()

try:
    excel = pd.ExcelFile(uploaded)
    sheet_name = st.selectbox("Select worksheet", excel.sheet_names)
    raw = pd.read_excel(uploaded, sheet_name=sheet_name)
except Exception as exc:
    st.error(f"Could not read this Excel file: {exc}")
    st.stop()

if raw.empty:
    st.warning("The selected worksheet is empty.")
    st.stop()

# Keep original headers visible, while matching common header variations.
def norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())

def find_col(columns, candidates):
    lookup = {norm(c): c for c in columns}
    for candidate in candidates:
        if norm(candidate) in lookup:
            return lookup[norm(candidate)]
    # fallback: partial matching for common header variations
    for c in columns:
        nc = norm(c)
        for candidate in candidates:
            ncan = norm(candidate)
            if ncan and (ncan in nc or nc in ncan):
                return c
    return None

columns = list(raw.columns)
id_guess = find_col(columns, ["User ID", "UserID", "Employee ID", "Staff ID", "ID"])
name_guess = find_col(columns, ["Staff Name", "Employee Name", "Name", "Staff", "Employee"])
zone_order_guess = find_col(columns, ["Zone Pick Orders", "Zone Picking Orders", "Zone Pick Order"])
zone_item_guess = find_col(columns, ["Zone Pick Items", "Zone Picking Items", "Zone Pick Qty"])
normal_order_guess = find_col(columns, ["Normal Pick Orders", "Normal Picking Orders", "Normal Pick Order"])
normal_item_guess = find_col(columns, ["Normal Pick Items", "Normal Picking Items", "Normal Pick Qty"])
sort_order_guess = find_col(columns, ["Sorter Orders", "Sorting Orders", "Sort Orders"])
sort_item_guess = find_col(columns, ["Sorter Items", "Sorting Items", "Sort Items"])
pack_order_guess = find_col(columns, ["Packing Orders", "Pack Orders", "Packing Order"])
pack_item_guess = find_col(columns, ["Packing Items", "Pack Items", "Packing Qty"])

st.subheader("1. Confirm column mapping")
st.caption("The app tries to identify columns automatically. Check these selections if your Excel headers use different names.")

def choose(label, guess, allow_none=False):
    opts = (["— Not available —"] if allow_none else []) + columns
    default = (["— Not available —"].index("— Not available —") if False else 0)
    if guess in columns:
        idx = opts.index(guess)
    else:
        idx = 0
    val = st.selectbox(label, opts, index=idx, key=f"map_{label}")
    return None if val == "— Not available —" else val

c1, c2 = st.columns(2)
with c1:
    name_col = choose("Staff name", name_guess)
    id_col = choose("User / staff ID (optional)", id_guess, allow_none=True)
with c2:
    zone_orders_col = choose("Zone pick orders (optional)", zone_order_guess, allow_none=True)
    zone_items_col = choose("Zone pick items", zone_item_guess, allow_none=True)
    normal_orders_col = choose("Normal pick orders (optional)", normal_order_guess, allow_none=True)
    normal_items_col = choose("Normal pick items", normal_item_guess, allow_none=True)

c3, c4 = st.columns(2)
with c3:
    sort_orders_col = choose("Sorting orders (optional)", sort_order_guess, allow_none=True)
    sort_items_col = choose("Sorting items", sort_item_guess, allow_none=True)
with c4:
    pack_orders_col = choose("Packing orders (optional)", pack_order_guess, allow_none=True)
    pack_items_col = choose("Packing items", pack_item_guess, allow_none=True)

st.subheader("2. Dashboard settings")
a, b, c = st.columns(3)
with a:
    shift_hours = st.number_input("Shift length (hours)", min_value=1.0, max_value=24.0, value=11.0, step=0.5)
with b:
    shift_label = st.text_input("Shift label", value="7:00 PM – 7:00 AM")
with c:
    target_per_hour = st.number_input("Target items per person per hour (optional)", min_value=0, value=0, step=10)

# Normalize chosen data into a consistent structure.
data = pd.DataFrame()
data["Staff Name"] = raw[name_col].fillna("Unknown").astype(str).str.strip()
if id_col:
    data["User ID"] = raw[id_col].fillna("").astype(str).str.strip()
else:
    data["User ID"] = ""

def numeric_series(col):
    if not col:
        return pd.Series(0, index=raw.index, dtype="float64")
    return pd.to_numeric(raw[col], errors="coerce").fillna(0)

data["Zone Pick Orders"] = numeric_series(zone_orders_col)
data["Zone Pick Items"] = numeric_series(zone_items_col)
data["Normal Pick Orders"] = numeric_series(normal_orders_col)
data["Normal Pick Items"] = numeric_series(normal_items_col)
data["Sorting Orders"] = numeric_series(sort_orders_col)
data["Sorting Items"] = numeric_series(sort_items_col)
data["Packing Orders"] = numeric_series(pack_orders_col)
data["Packing Items"] = numeric_series(pack_items_col)

data["Picking Items"] = data["Zone Pick Items"] + data["Normal Pick Items"]
data["Total Items"] = data["Picking Items"] + data["Sorting Items"] + data["Packing Items"]
data["Total Orders"] = data["Zone Pick Orders"] + data["Normal Pick Orders"] + data["Sorting Orders"] + data["Packing Orders"]
data["Hours"] = shift_hours
data["Items per Hour"] = data["Total Items"] / shift_hours
data["Target Items"] = target_per_hour * shift_hours if target_per_hour > 0 else 0
if target_per_hour > 0:
    data["Target Achievement %"] = (data["Total Items"] / data["Target Items"] * 100).round(1)
else:
    data["Target Achievement %"] = pd.NA

# Consolidate duplicate names only if the same staff ID/name occurs more than once.
# Preserve the staff ID in grouping when supplied, since one person may have multiple IDs.
group_cols = ["User ID", "Staff Name"] if id_col else ["Staff Name"]
agg_cols = [c for c in data.columns if c not in group_cols and c != "Target Achievement %"]
data = data.groupby(group_cols, dropna=False, as_index=False)[agg_cols].sum()
data["Hours"] = shift_hours
data["Items per Hour"] = (data["Total Items"] / shift_hours).round(2)
data["Target Items"] = target_per_hour * shift_hours if target_per_hour > 0 else 0
data["Target Achievement %"] = (
    (data["Total Items"] / data["Target Items"] * 100).round(1)
    if target_per_hour > 0 else pd.NA
)
data = data.sort_values("Total Items", ascending=False).reset_index(drop=True)

if data["Staff Name"].str.strip().eq("").all():
    st.error("The selected staff-name column does not contain usable names.")
    st.stop()

total_items = int(data["Total Items"].sum())
pick_total = int(data["Picking Items"].sum())
sort_total = int(data["Sorting Items"].sum())
pack_total = int(data["Packing Items"].sum())
total_orders = int(data["Total Orders"].sum())
staff_count = int(data["Staff Name"].nunique())

st.subheader("3. Daily performance")
st.caption(f"Worksheet: {sheet_name} · Shift: {shift_label} · {shift_hours:g} hours per person")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Items Processed", f"{total_items:,}")
m2.metric("Staff Records", f"{len(data):,}")
m3.metric("Picking Items", f"{pick_total:,}")
m4.metric("Sorting Items", f"{sort_total:,}")
m5.metric("Packing Items", f"{pack_total:,}")

left, right = st.columns([1.7, 1])
with left:
    st.subheader("Staff performance — total items")
    chart = px.bar(
        data.sort_values("Total Items", ascending=True),
        x="Total Items", y="Staff Name", color="Total Items",
        orientation="h", text="Total Items",
        color_continuous_scale=["#ff718b", "#ffad66", "#35d7d0"],
        hover_data=["User ID", "Picking Items", "Sorting Items", "Packing Items", "Items per Hour"],
    )
    chart.update_layout(
        height=max(420, 26 * len(data)), template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False, xaxis_title="Items", yaxis_title="",
        margin=dict(l=10, r=20, t=20, b=10),
    )
    st.plotly_chart(chart, use_container_width=True)

with right:
    st.subheader("Task volume share")
    task_df = pd.DataFrame({
        "Task": ["Picking", "Sorting", "Packing"],
        "Items": [pick_total, sort_total, pack_total],
    })
    if task_df["Items"].sum() > 0:
        donut = px.pie(task_df, names="Task", values="Items", hole=0.62,
                       color="Task", color_discrete_map={
                           "Picking": "#c6f36b", "Sorting": "#35d7d0", "Packing": "#b68cff"
                       })
        donut.update_layout(
            height=320, template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=5, r=5, t=20, b=5), legend_title_text=""
        )
        st.plotly_chart(donut, use_container_width=True)
    else:
        st.info("No item values were detected in the selected task columns.")
    st.metric("Total Orders", f"{total_orders:,}")
    st.metric("Average items per staff record", f"{(total_items / len(data)) if len(data) else 0:,.1f}")

st.subheader("4. Staff detail")
search = st.text_input("Search by staff name or ID")
view = data.copy()
if search.strip():
    mask = (
        view["Staff Name"].str.contains(search, case=False, na=False)
        | view["User ID"].str.contains(search, case=False, na=False)
    )
    view = view[mask]

display_cols = [
    "User ID", "Staff Name", "Zone Pick Orders", "Zone Pick Items",
    "Normal Pick Orders", "Normal Pick Items", "Sorting Orders",
    "Sorting Items", "Packing Orders", "Packing Items", "Picking Items",
    "Total Orders", "Total Items", "Hours", "Items per Hour"
]
if target_per_hour > 0:
    display_cols.append("Target Achievement %")
st.dataframe(view[display_cols], use_container_width=True, hide_index=True)

csv = view[display_cols].to_csv(index=False).encode("utf-8-sig")
st.download_button("Download displayed data as CSV", data=csv,
                   file_name="warehouse_performance_dashboard.csv", mime="text/csv")

out = io.BytesIO()
with pd.ExcelWriter(out, engine="openpyxl") as writer:
    view[display_cols].to_excel(writer, index=False, sheet_name="Dashboard Data")
    data[display_cols].to_excel(writer, index=False, sheet_name="All Staff")
st.download_button("Download processed data as Excel", data=out.getvalue(),
                   file_name="warehouse_performance_dashboard.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with st.expander("Preview uploaded worksheet"):
    st.dataframe(raw.head(30), use_container_width=True)

st.caption("Note: Working hours are set to the shift length you enter. Target achievement is calculated only when you enter a target per hour. Confirm column mappings and totals before using the dashboard for official reporting.")
