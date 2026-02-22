import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="NordTech Dashboard", layout="wide")

@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Revenue"] = df["Price"] * df["Quantity"]
    df["has_return"] = df["Return_ID"].notna()

    # ja kādā rindā trūkst signālu
    for col, default in [("ticket_count", 0), ("negative_tickets", 0), ("top_topic", "no_tickets")]:
        if col not in df.columns:
            df[col] = default

    return df

st.title("NordTech – Sales, Returns & Support Signals")

DATA_PATH = "orders_raw.csv"
df = load_data(DATA_PATH)

# Sidebar filtri
st.sidebar.header("Filtri")

all_categories = sorted(df["Product_Category"].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect(
    "Produktu kategorija",
    options=all_categories,
    default=all_categories
)

min_date = df["Date"].min()
max_date = df["Date"].max()
date_range = st.sidebar.date_input(
    "Laika periods",
    value=(min_date.date() if pd.notna(min_date) else None,
           max_date.date() if pd.notna(max_date) else None)
)

all_payments = sorted(df["Payment_Status"].dropna().unique().tolist())
selected_payments = st.sidebar.multiselect(
    "Payment status",
    options=all_payments,
    default=all_payments
)

f = df.copy()
if selected_categories:
    f = f[f["Product_Category"].isin(selected_categories)]

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    f = f[(f["Date"] >= start_date) & (f["Date"] <= end_date)]

if selected_payments:
    f = f[f["Payment_Status"].isin(selected_payments)]

# KPI
total_revenue = f["Revenue"].sum()
return_rate = (f["has_return"].mean() * 100) if len(f) else 0
returns_count = int(f["has_return"].sum())
tickets_total = int(f["ticket_count"].sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("Kopējie ieņēmumi", f"{total_revenue:,.2f}")
k2.metric("Atgriezumu %", f"{return_rate:.2f}%")
k3.metric("Atgriezumu skaits", f"{returns_count}")
k4.metric("Sūdzību skaits", int(tickets_total))

st.divider()

# Grafiki
st.subheader("Dinamika laikā")
time = (f.dropna(subset=["Date"])
          .set_index("Date")
          .resample("W")
          .agg(
              revenue=("Revenue","sum"),
              orders=("Transaction_ID","count"),
              returns=("has_return","sum"),
              tickets=("ticket_count","sum")
          )
          .reset_index())
time["return_rate"] = np.where(time["orders"] > 0, time["returns"] / time["orders"] * 100, 0)

c1, c2 = st.columns(2)
c1.plotly_chart(px.line(time, x="Date", y="revenue", title="Ieņēmumi pa nedēļām"), use_container_width=True)
c2.plotly_chart(px.line(time, x="Date", y="return_rate", title="Atgriezumu īpatsvars (%) pa nedēļām"), use_container_width=True)

st.subheader("Segmentācija")
seg = (f.groupby("Product_Category")
        .agg(
            orders=("Transaction_ID","count"),
            returns=("has_return","sum"),
            revenue=("Revenue","sum"),
            avg_tickets=("ticket_count","mean")
        )
        .reset_index())
seg["return_rate"] = np.where(seg["orders"] > 0, seg["returns"] / seg["orders"] * 100, 0)
seg = seg.sort_values("return_rate", ascending=False)

st.plotly_chart(
    px.bar(seg, x="Product_Category", y="return_rate",
           hover_data=["orders","returns","revenue","avg_tickets"],
           title="Atgriezumu % pa produktu kategorijām"),
    use_container_width=True
)

st.subheader("Top problem cases (pēc atgriezumiem)")
top_cases = (f.groupby(["Product_Category","Product_Name"])
              .agg(
                  orders=("Transaction_ID","count"),
                  returns=("has_return","sum"),
                  return_rate=("has_return", lambda s: (s.mean()*100) if len(s) else 0),
                  revenue=("Revenue","sum"),
                  tickets=("ticket_count","sum"),
                  top_topic=("top_topic", lambda s: s.value_counts().index[0] if len(s) else "n/a")
              )
              .reset_index()
              .sort_values(["returns","return_rate"], ascending=False)
              .head(15))

st.dataframe(top_cases, use_container_width=True)

st.caption("Padoms: pamēģini atlasīt tikai 'Smart Home' un šaurāku periodu, lai redzētu, vai problēmas koncentrējas laikā.")
