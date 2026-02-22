import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="NordTech Dashboard", layout="wide")

@st.cache_data
def load_data(orders_path: str, returns_path: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(orders_path)
    df.columns = [c.strip() for c in df.columns]

    # Date
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Revenue
    if "Price" in df.columns and "Quantity" in df.columns:
        df["Revenue"] = pd.to_numeric(df["Price"], errors="coerce") * pd.to_numeric(df["Quantity"], errors="coerce")
    else:
        df["Revenue"] = 0

    # Default return flag
    df["has_return"] = False

    # Ja nav returns faila
    if returns_path is None:
        return df

    try:
        ret = pd.read_excel(returns_path)
        ret.columns = [c.strip() for c in ret.columns]

        # --- RETURNS LINKING (precīzi pēc tavām kolonnām) ---
        orders_key = "Transaction_ID"
        ret_key = "Original_Tx_ID"

        if orders_key in df.columns and ret_key in ret.columns:
            returned_ids = set(ret[ret_key].dropna().astype(str).str.strip())
            df["has_return"] = df[orders_key].astype(str).str.strip().isin(returned_ids)
        # --- /RETURNS LINKING ---

        return df

    except Exception:
        return df

st.title("NordTech – Sales, Returns & Support Signals")

DATA_PATH = "orders_raw.csv"
RETURNS_PATH = "returns_messy.xlsx"
df = load_data(DATA_PATH, RETURNS_PATH)

st.write("Tickets rows:", len(pd.read_json("customer_tickets.jsonl", lines=True)))

TICKETS_PATH = "customer_tickets.jsonl"

@st.cache_data
def load_tickets(path: str) -> pd.DataFrame:
    t = pd.read_json(path, lines=True)
    t.columns = [c.strip() for c in t.columns]
    return t

try:
    tickets = load_tickets(TICKETS_PATH)

    # Meklē atslēgu
    key_candidates = [
        "Transaction_ID", "TransactionID", "transaction_id",
        "Order_ID", "OrderID", "order_id"
    ]

    orders_key = next((k for k in key_candidates if k in df.columns), None)
    tickets_key = next((k for k in key_candidates if k in tickets.columns), None)

    if orders_key and tickets_key:
        t_agg = (
            tickets.groupby(tickets_key)
                   .agg(
                       ticket_count=(tickets_key, "size"),
                       top_topic=("Topic", lambda s: s.value_counts().index[0] if len(s) else "n/a")
                   )
                   .reset_index()
                   .rename(columns={tickets_key: orders_key})
        )

        df = df.merge(t_agg, on=orders_key, how="left")
        df["ticket_count"] = df["ticket_count"].fillna(0).astype(int)
        df["top_topic"] = df["top_topic"].fillna("no_tickets")
    else:
        df["ticket_count"] = 0
        df["top_topic"] = "no_tickets"

except Exception:
    df["ticket_count"] = 0
    df["top_topic"] = "no_tickets"

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
    
# --- SAFETY PATCH ---
# sakārto kolonnu nosaukumus
f.columns = [c.strip() for c in f.columns]

# Date droši
if "Date" in f.columns:
    f["Date"] = pd.to_datetime(f["Date"], errors="coerce")

# Revenue droši
if "Revenue" not in f.columns:
    if "Price" in f.columns and "Quantity" in f.columns:
        f["Revenue"] = pd.to_numeric(f["Price"], errors="coerce") * pd.to_numeric(f["Quantity"], errors="coerce")
    else:
        f["Revenue"] = 0

# has_return droši
if "has_return" not in f.columns:
    f["has_return"] = False

# ticket_count droši
if "ticket_count" not in f.columns:
    f["ticket_count"] = 0

# top_topic droši
if "top_topic" not in f.columns:
    f["top_topic"] = "n/a"

# JA NAV Transaction_ID → izveido
if "Transaction_ID" not in f.columns:
    f["Transaction_ID"] = np.arange(len(f))
# --- END SAFETY PATCH ---    

# KPI
total_revenue = f["Revenue"].sum()
return_rate = (f["has_return"].mean() * 100) if len(f) else 0
returns_count = int(f["has_return"].sum())
tickets_total = int(f.get("ticket_count", pd.Series(0, index=f.index)).sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("Kopējie ieņēmumi", f"{total_revenue:,.2f}")
k2.metric("Atgriezumu %", f"{return_rate:.2f}%")
k3.metric("Atgriezumu skaits", f"{returns_count}")
k4.metric("Sūdzību skaits", int(tickets_total))

st.divider()

# Grafiki
st.subheader("Dinamika laikā")
time = (
    f.assign(Date=pd.to_datetime(f["Date"], errors="coerce"))
     .dropna(subset=["Date"])
     .groupby(pd.Grouper(key="Date", freq="W"))
     .agg(
         revenue=("Revenue", "sum"),
         orders=("Transaction_ID", "count"),
         returns=("has_return", "sum"),
         tickets=("ticket_count", "sum"),
     )
     .reset_index()
)
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
