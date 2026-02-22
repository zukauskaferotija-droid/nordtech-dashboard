import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="NordTech Dashboard", layout="wide")
st.caption("Interaktīva pārdošanas, atgriezumu un klientu kvalitātes analīze (Streamlit + Python)")
st.markdown("---")

px.defaults.template = "plotly_white"

color_revenue = "#1f77b4"
color_returns = "#d62728"
color_tickets = "#ff7f0e"

px.line(
    time,
    x="Date",
    y="revenue",
    hover_data={
        "revenue": ":,.0f",
        "orders": True,
        "returns": True,
        "tickets": True
    }
)

@st.cache_data
def load_data(orders_path: str, returns_path: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(orders_path)
    df.columns = [c.strip() for c in df.columns]

    # Revenue (jo enriched failā nav kolonnas Revenue)
    df["Revenue"] = pd.to_numeric(df["Price"], errors="coerce") * pd.to_numeric(df["Quantity"], errors="coerce")
    df["Revenue"] = df["Revenue"].fillna(0)

    # has_return (enriched failā ir Return_ID, nevis has_return)
    df["has_return"] = df["Return_ID"].notna()

    # ticket_count droši kā skaitlis
    df["ticket_count"] = pd.to_numeric(df["ticket_count"], errors="coerce").fillna(0).astype(int)

    # Date
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Revenue
    if "Price" in df.columns and "Quantity" in df.columns:
        df["Revenue"] = pd.to_numeric(df["Price"], errors="coerce") * pd.to_numeric(df["Quantity"], errors="coerce")
    else:
        df["Revenue"] = 0

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

DATA_PATH = "enriched_data.csv"
df = pd.read_csv(DATA_PATH)

df["Product_Category_clean"] = (
    df["Product_Category"]
      .astype(str)
      .str.strip()
      .str.replace(r"\s+", " ", regex=True)
)

df["Product_Name_clean"] = (
    df["Product_Name"]
      .astype(str)
      .str.strip()
      .str.replace(r"\s+", " ", regex=True)
)

# Datums
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

# Revenue (obligāti PIRMS jebkādiem aprēķiniem / debug)
df["Revenue"] = pd.to_numeric(df["Price"], errors="coerce") * pd.to_numeric(df["Quantity"], errors="coerce")
df["Revenue"] = df["Revenue"].fillna(0)

# has_return no Return_ID (enriched failā nav has_return)
df["has_return"] = df["Return_ID"].notna()

# ticket_count kā skaitlis
df["ticket_count"] = pd.to_numeric(df["ticket_count"], errors="coerce").fillna(0).astype(int)

# Sidebar filtri
st.sidebar.header("Filtri")

all_categories = sorted(
    df["Product_Category_clean"]
      .astype(str)
      .str.strip()
      .str.replace(r"\s+", " ", regex=True)
      .dropna()
      .unique()
      .tolist()
)

selected_categories = st.sidebar.multiselect(
    "Produktu kategorija",
    options=all_categories,
    default=all_categories,
    key="cat_filter"
)

# --- Product Name atkarīgs no kategorijas ---
if selected_categories:
    available_products = (
        df[df["Product_Category_clean"].isin(selected_categories)]
        ["Product_Name_clean"]
        .dropna()
        .unique()
        .tolist()
    )

# --- Product Name atkarīgs no kategorijas ---
if selected_categories:
    available_products = (
        df[df["Product_Category_clean"].isin(selected_categories)]["Product_Name"]
        .dropna()
        .unique()
        .tolist()
    )
else:
    available_products = df["Product_Name_clean"].dropna().unique().tolist()

available_products = sorted(available_products)

selected_products = st.sidebar.multiselect(
    "Produkts",
    options=available_products,
    default=available_products,
    key="product_filter"
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
    f = f[f["Product_Category_clean"].isin(selected_categories)]

if selected_products:
    f = f[f["Product_Name"].isin(selected_products)]

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
tickets_total = int(f["ticket_count"].sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("💰 Kopējie ieņēmumi", f"{total_revenue:,.0f} €")
k2.metric("📦 Atgriezumu īpatsvars", f"{return_rate:.2f}%")
k3.metric("↩️ Atgriezumu skaits", f"{returns_count:,}")
k4.metric("🎧 Klientu sūdzības", f"{tickets_total:,}")

if return_rate > 7:
    st.warning("⚠️ Atgriezumu līmenis pārsniedz 7% — nepieciešama produktu kvalitātes analīze.")
elif return_rate > 4:
    st.info("ℹ️ Atgriezumu līmenis virs 4% — ieteicams monitorēt.")
else:
    st.success("✅ Atgriezumu līmenis kontrolēts.")

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
seg = (f.groupby("Product_Category_clean")
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
    px.bar(seg, x="Product_Category_clean", y="return_rate",
           hover_data=["orders","returns","revenue","avg_tickets"],
           title="Atgriezumu % pa produktu kategorijām"),
    use_container_width=True
)

st.subheader("Top problem cases (pēc atgriezumiem)")
top_cases = (f.groupby(["Product_Category_clean","Product_Name_clean"])
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
