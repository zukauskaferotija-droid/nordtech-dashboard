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

# Sidebar filtri (collapsible)
with st.sidebar.expander("🔎 Filtri", expanded=True):

    all_categories = sorted(
        df["Product_Category_clean"]
          .dropna()
          .unique()
          .tolist()
    )

    selected_categories = st.multiselect(
        "Produktu kategorija",
        options=all_categories,
        default=all_categories,
        key="cat_filter"
    )

    # Product Name atkarīgs no kategorijas
    if selected_categories:
        available_products = (
            df[df["Product_Category_clean"].isin(selected_categories)]
            ["Product_Name_clean"]
            .dropna()
            .unique()
            .tolist()
        )
    else:
        available_products = df["Product_Name_clean"].dropna().unique().tolist()

    available_products = sorted(available_products)

    selected_products = st.multiselect(
        "Produkts",
        options=available_products,
        default=available_products,
        key="product_filter"
    )

    min_date = df["Date"].min()
    max_date = df["Date"].max()

    date_range = st.date_input(
        "Laika periods",
        value=(min_date.date(), max_date.date())
    )

    all_payments = sorted(df["Payment_Status"].dropna().unique().tolist())
    payment_choice = st.selectbox(
    "Payment status",
    options=["All"] + all_payments,
    index=0,
    key="payment_filter"
)

    if st.button("🔄 Reset Filters"):
        st.rerun()


# Filtrēšana
f = df.copy()

if selected_categories:
    f = f[f["Product_Category_clean"].isin(selected_categories)]

if selected_products:
    f = f[f["Product_Name_clean"].isin(selected_products)]

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    f = f[(f["Date"] >= start_date) & (f["Date"] <= end_date)]

if payment_choice != "All":
    f = f[f["Payment_Status"] == payment_choice]
    
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

# ===== Premium: Monthly agregācija =====
monthly = (
    f.dropna(subset=["Date"])
     .assign(month=f["Date"].dt.to_period("M").dt.to_timestamp())
     .groupby("month")
     .agg(
         revenue=("Revenue", "sum"),
         orders=("Transaction_ID", "count"),
         returns=("has_return", "sum"),
         tickets=("ticket_count", "sum"),
     )
     .reset_index()
)

monthly["return_rate"] = np.where(monthly["orders"] > 0, monthly["returns"] / monthly["orders"] * 100, 0)

# MoM (percent change)
monthly = monthly.sort_values("month")
monthly["revenue_mom_pct"] = monthly["revenue"].pct_change() * 100
monthly["return_rate_mom_pct"] = monthly["return_rate"].pct_change() * 100

# ===== KPI ar trendiem =====
total_revenue = float(f["Revenue"].sum())
return_rate = (float(f["has_return"].mean()) * 100) if len(f) else 0
returns_count = int(f["has_return"].sum())
tickets_total = int(f["ticket_count"].sum())

# Paņem pēdējo mēnesi un iepriekšējo mēnesi (ja ir)
last_mom_rev = monthly["revenue_mom_pct"].iloc[-1] if len(monthly) >= 2 else np.nan
last_mom_ret = monthly["return_rate_mom_pct"].iloc[-1] if len(monthly) >= 2 else np.nan

def trend_arrow(x):
    if pd.isna(x): 
        return ""
    return "↑" if x > 0 else ("↓" if x < 0 else "→")

k1, k2, k3, k4 = st.columns(4)

k1.metric(
    "💰 Kopējie ieņēmumi",
    f"{total_revenue:,.2f}",
    delta=(f"{trend_arrow(last_mom_rev)} {last_mom_rev:.1f}% MoM" if not pd.isna(last_mom_rev) else None)
)

# Atgriezumu % — šeit “↓” ir labi (uzlabojums), tāpēc delta_color="inverse"
k2.metric(
    "📦 Atgriezumu %",
    f"{return_rate:.2f}%",
    delta=(f"{trend_arrow(last_mom_ret)} {last_mom_ret:.1f}% MoM" if not pd.isna(last_mom_ret) else None),
    delta_color="inverse"
)

k3.metric("↩️ Atgriezumu skaits", f"{returns_count:,}")
k4.metric("🎧 Sūdzību skaits", f"{tickets_total:,}")

st.download_button(
    label="⬇️ Lejupielādēt filtrētos datus (CSV)",
    data=f.to_csv(index=False).encode("utf-8"),
    file_name="nordtech_filtered.csv",
    mime="text/csv"
)

st.divider()

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
fig_revenue = px.line(
    time,
    x="Date",
    y="revenue",
    title="Ieņēmumi pa nedēļām",
    hover_data={
        "revenue": ":,.0f",
        "orders": True,
        "returns": True,
        "tickets": True
    }
)

c1.plotly_chart(fig_revenue, use_container_width=True)
fig_returns = px.line(
    time,
    x="Date",
    y="return_rate",
    title="Atgriezumu īpatsvars (%) pa nedēļām",
    hover_data={
        "return_rate": ":.2f",
        "orders": True,
        "returns": True
    }
)

c2.plotly_chart(fig_returns, use_container_width=True)

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

st.subheader("Siltumkarte pa mēnešiem (heatmap)")

m = monthly.copy()
m["Year"] = m["month"].dt.year
m["Month"] = m["month"].dt.strftime("%b")

# izvēlies ko rādīt: "revenue" vai "return_rate"
metric_choice = st.radio("Ko rādīt heatmap?", ["Revenue", "Return rate %"], horizontal=True)

if metric_choice == "Revenue":
    value_col = "revenue"
    z_title = "Ieņēmumi"
else:
    value_col = "return_rate"
    z_title = "Atgriezumu %"

pivot = m.pivot_table(index="Year", columns="Month", values=value_col, aggfunc="sum")

fig_heat = px.imshow(
    pivot,
    aspect="auto",
    title=f"Heatmap: {z_title} pa mēnešiem",
)

st.plotly_chart(fig_heat, use_container_width=True)

st.subheader("Ieņēmumi vs atgriezumi: korelācija")

scatter_df = (
    f.dropna(subset=["Date"])
     .assign(month=f["Date"].dt.to_period("M").dt.to_timestamp())
     .groupby("month")
     .agg(
         revenue=("Revenue", "sum"),
         return_rate=("has_return", "mean"),
         orders=("Transaction_ID", "count"),
         returns=("has_return", "sum"),
         tickets=("ticket_count", "sum"),
     )
     .reset_index()
)

scatter_df["return_rate"] = scatter_df["return_rate"] * 100

fig_scatter = px.scatter(
    scatter_df,
    x="revenue",
    y="return_rate",
    size="orders",
    hover_data=["month", "orders", "returns", "tickets"],
    title="Vai lielāki ieņēmumi saistās ar lielākiem atgriezumiem?"
)

st.plotly_chart(fig_scatter, use_container_width=True)

st.plotly_chart(
    px.bar(seg, x="Product_Category_clean", y="return_rate",
           hover_data=["orders","returns","revenue","avg_tickets"],
           title="Atgriezumu % pa produktu kategorijām"),
    use_container_width=True
)

# Dinamisks secinājums
if len(seg) > 0:
    worst_cat = seg.iloc[0]["Product_Category_clean"]
    worst_rate = seg.iloc[0]["return_rate"]

    st.markdown(
        f"🔎 Augstākais atgriezumu līmenis novērots kategorijā "
        f"**{worst_cat}** ({worst_rate:.2f}%)."
    )

st.subheader("Pareto (80/20): kuri produkti rada lielāko daļu atgriezumu?")

# 1) Atgriezumu skaits pa produktiem
pareto = (
    f.groupby("Product_Name_clean")  # ja nav clean, liec "Product_Name"
     .agg(
         returns=("has_return", "sum"),
         orders=("Transaction_ID", "count"),
         revenue=("Revenue", "sum")
     )
     .reset_index()
)

# Ja nav atgriezumu vispār (drošībai)
if pareto["returns"].sum() == 0:
    st.info("Šajā filtrā nav atgriezumu, tāpēc Pareto grafiks nav izveidojams.")
else:
    # 2) Sakārto pēc returns (lielākie vispirms)
    pareto = pareto.sort_values("returns", ascending=False)

    # 3) Kumulatīvie %
    pareto["cum_returns"] = pareto["returns"].cumsum()
    pareto["cum_returns_pct"] = pareto["cum_returns"] / pareto["returns"].sum() * 100

    pareto["cum_products"] = np.arange(1, len(pareto) + 1)
    pareto["cum_products_pct"] = pareto["cum_products"] / len(pareto) * 100

    # 4) Atrodi punktu, kur sasniedz 80% atgriezumu
    idx_80 = pareto[pareto["cum_returns_pct"] >= 80].index.min()
    products_for_80 = int(pareto.loc[idx_80, "cum_products"]) if pd.notna(idx_80) else len(pareto)

    st.caption(f"🔎 ~{products_for_80} produkti (~{products_for_80/len(pareto)*100:.0f}%) veido ~80% no visiem atgriezumiem šajā filtrā.")

    # 5) Grafiks (līnija): X = kumulatīvais produktu %, Y = kumulatīvais atgriezumu %
    fig_pareto = px.line(
        pareto,
        x="cum_products_pct",
        y="cum_returns_pct",
        title="Pareto līkne: kumulatīvie produkti (%) vs kumulatīvie atgriezumi (%)",
        markers=True
    )

    # 6) 80% horizontālā līnija + vertikālā līnija pie atrastā punkta
    x80 = pareto.loc[idx_80, "cum_products_pct"] if pd.notna(idx_80) else 100

    fig_pareto.add_hline(y=80, line_dash="dash", annotation_text="80% atgriezumu", annotation_position="top left")
    fig_pareto.add_vline(x=x80, line_dash="dash", annotation_text=f"{x80:.1f}% produktu", annotation_position="top right")

    fig_pareto.update_yaxes(range=[0, 100], title="Kumulatīvie atgriezumi (%)")
    fig_pareto.update_xaxes(range=[0, 100], title="Kumulatīvie produkti (%)")

    st.plotly_chart(fig_pareto, use_container_width=True)

    # 7) Parādi TOP produktus, kas veido 80% (tabula)
    top_80 = pareto.loc[:idx_80, ["Product_Name_clean", "returns", "orders", "revenue", "cum_returns_pct"]].copy()
    top_80 = top_80.rename(columns={"Product_Name_clean": "Product_Name"})
    top_80["cum_returns_pct"] = top_80["cum_returns_pct"].round(2)

    st.markdown("**Produkti, kas kopā veido ~80% atgriezumu:**")
    st.dataframe(top_80, use_container_width=True)

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

# Risk ranking pievienošana
top_cases["Risk_Level"] = np.where(
    top_cases["return_rate"] > 10, "🔴 High",
    np.where(top_cases["return_rate"] > 5, "🟡 Medium", "🟢 Low")
)

top_cases = top_cases.rename(columns={
    "Product_Category_clean": "Category",
    "Product_Name_clean": "Product"
})

cols = ["Risk_Level"] + [c for c in top_cases.columns if c != "Risk_Level"]
top_cases = top_cases[cols]

st.dataframe(top_cases, use_container_width=True)

st.caption("Padoms: pamēģini atlasīt tikai 'Smart Home' un šaurāku periodu, lai redzētu, vai problēmas koncentrējas laikā.")
