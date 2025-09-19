import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from io import StringIO
import re
from dateutil import parser
from datetime import datetime

# -------- CONFIG --------
st.set_page_config(page_title="Programs Dashboard — Companies & Monthly Trends", layout="wide")
BASE = Path(__file__).parent
LOCAL_JSON = BASE / "data.json"

# --------- Helpers & season mapping ---------
DEFAULT_SEASON_MAP = {"spring": 4, "summer": 7, "autumn": 10, "fall": 10, "winter": 1}
ALT_SEASON_MAP = {"spring": 4, "summer": 6, "autumn": 9, "fall": 9, "winter": 1}  # example alt (summer->June, autumn->Sep)

def get_season_map(choice):
    return ALT_SEASON_MAP if choice == "Summer → June (alternate)" else DEFAULT_SEASON_MAP

def normalize_start_date(raw, season_map):
    """
    Return dict with:
     - 'bucket_type' : category
     - 'month_year'   : pandas.Timestamp or None
     - 'label'        : string label
    Best-effort parsing for free-text start_date fields.
    """
    if not raw or pd.isna(raw):
        return {"bucket_type": "unknown", "month_year": None, "label": "Unknown"}

    s = str(raw).strip().lower()

    # Self-paced / immediate
    if any(k in s for k in ["self-paced", "self paced", "immediate", "on demand", "online"]):
        return {"bucket_type": "self-paced", "month_year": None, "label": "Self-paced"}
    if any(k in s for k in ["rolling", "varies", "various", "tbd", "to be decided", "to be determined"]):
        return {"bucket_type": "rolling", "month_year": None, "label": "Rolling/Varies"}

    # exact season + year e.g., "summer 2026"
    match = re.search(r"(spring|summer|autumn|fall|winter)[^\d]*(\d{4})", s)
    if match:
        season = match.group(1)
        year = int(match.group(2))
        m = season_map.get(season, 1)
        ts = pd.Timestamp(year=year, month=m, day=1)
        return {"bucket_type": "season", "month_year": ts, "label": ts.strftime("%b %Y")}

    # season without year: use current year
    if s in season_map:
        m = season_map[s]
        year = datetime.now().year
        ts = pd.Timestamp(year=year, month=m, day=1)
        return {"bucket_type": "season", "month_year": ts, "label": ts.strftime("%b %Y")}

    # month + year like "June 2026"
    match = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[^\d]*(\d{4})", s)
    if match:
        month_str = match.group(1)
        year = int(match.group(2))
        try:
            dt = parser.parse(f"{month_str} {year}")
            ts = pd.Timestamp(dt.year, dt.month, 1)
            return {"bucket_type": "month-year", "month_year": ts, "label": ts.strftime("%b %Y")}
        except Exception:
            pass

    # only year present -> choose mid-year
    match = re.search(r"^(\d{4})$", s)
    if match:
        year = int(match.group(1))
        ts = pd.Timestamp(year=year, month=7, day=1)
        return {"bucket_type": "year-only", "month_year": ts, "label": ts.strftime("%b %Y")}

    # season + 'rolling'
    if "rolling" in s and any(season in s for season in season_map):
        for season in season_map:
            if season in s:
                py = re.search(r"(\d{4})", s)
                year = int(py.group(1)) if py else datetime.now().year
                ts = pd.Timestamp(year=year, month=season_map[season], day=1)
                return {"bucket_type": "season", "month_year": ts, "label": ts.strftime("%b %Y")}
        return {"bucket_type": "rolling", "month_year": None, "label": "Rolling/Varies"}

    # try fuzzy parse
    try:
        dt = parser.parse(raw, fuzzy=True, default=datetime(datetime.now().year, 1, 1))
        ts = pd.Timestamp(dt.year, dt.month, 1)
        return {"bucket_type": "month-year", "month_year": ts, "label": ts.strftime("%b %Y")}
    except Exception:
        pass

    return {"bucket_type": "unknown", "month_year": None, "label": raw}

# --------- Data load ---------
@st.cache_data
def load_from_path(path: Path):
    return pd.read_json(path)

@st.cache_data
def load_from_buffer(buffer: StringIO):
    buffer.seek(0)
    return pd.read_json(buffer)

# --------- UI: controls ---------
st.title("Programs Dashboard — Companies & Monthly Trends")
st.markdown("Upload a JSON (same schema) or let the app read the local `data.json` in this folder.")

col_top = st.columns([3,1])
with col_top[1]:
    uploaded = st.file_uploader("Upload JSON", type=["json"], help="Optional: override local data.json")

# Season mapping choice (user wanted ability to map Summer->June)
st.sidebar.header("Display / parsing options")
season_choice = st.sidebar.selectbox("Season → month mapping", ("Default (Summer→July)", "Summer → June (alternate)"))
season_map = get_season_map(season_choice)

# Top-N companies and comparison selection
top_n = st.sidebar.slider("Top N companies for timeline / heatmap", 1, 12, 6)
compare_companies = st.sidebar.multiselect("Select companies to compare (multi-select)", options=[], default=[])

# Year range slider placeholder (will be built after we know data years)
st.sidebar.markdown("---")
st.sidebar.markdown("Tip: select companies above to drill down or compare them.")

# --------- Load data ---------
try:
    if uploaded:
        df = load_from_buffer(StringIO(uploaded.getvalue().decode("utf-8")))
    else:
        if not LOCAL_JSON.exists():
            st.error(f"Local file not found: {LOCAL_JSON}. Upload a JSON file or create one named data.json")
            st.stop()
        df = load_from_path(LOCAL_JSON)
except Exception as e:
    st.exception(e)
    st.stop()

if df.empty:
    st.warning("Dataset is empty.")
    st.stop()

# Ensure expected columns
expected_cols = ["domain", "program_name", "host_company_or_startup", "type",
                 "application_deadline", "start_date", "location", "eligibility",
                 "short_summary", "official_link", "source_name"]
for c in expected_cols:
    if c not in df.columns:
        df[c] = pd.NA

# Normalize columns and create convenience columns
df['company'] = df['host_company_or_startup'].fillna("Unknown").astype(str).str.strip()
df['domain'] = df['domain'].fillna("Unknown").astype(str)
df['type'] = df['type'].fillna("Unknown").astype(str)
df['program_count'] = 1

# Normalize start_date using chosen season_map
norms = df['start_date'].apply(lambda x: normalize_start_date(x, season_map))
norms_df = pd.json_normalize(norms)
df = pd.concat([df, norms_df], axis=1)
df['month_label'] = df['label'].fillna("Unknown")
df['month_dt'] = df['month_year']  # may have NaT

# Year slider: build from available month_dt (if none, use current year)
available_years = sorted(pd.Series([d.year for d in df['month_dt'].dropna().unique()]) if df['month_dt'].notna().any() else [datetime.now().year])
if len(available_years) >= 2:
    year_min, year_max = available_years[0], available_years[-1]
else:
    year_min = available_years[0] if available_years else datetime.now().year
    year_max = year_min + 2

year_range = st.sidebar.slider("Limit timeline to year range", int(year_min), int(year_max), (int(year_min), int(year_max)))

# sidebar update for compare_companies after data loaded
company_options = list(df['company'].value_counts().index)
# replace compare_companies placeholder if empty
if not compare_companies:
    # choose top 3 by default
    compare_companies = company_options[:3]
# re-render multiselect with actual options
compare_companies = st.sidebar.multiselect("Select companies to compare (multi-select)", options=company_options, default=compare_companies)

# Domain & type filters
domains = sorted(df['domain'].dropna().unique())
sel_domains = st.sidebar.multiselect("Filter domain(s)", options=domains, default=domains)
types = sorted(df['type'].dropna().unique())
sel_types = st.sidebar.multiselect("Filter type(s)", options=types, default=types)

# Apply filters
mask = (df['domain'].isin(sel_domains)) & (df['type'].isin(sel_types))
filtered = df[mask].copy()

# year range mask for timeline-related visuals
if filtered['month_dt'].notna().any():
    start_year_dt = pd.Timestamp(year=year_range[0], month=1, day=1)
    end_year_dt = pd.Timestamp(year=year_range[1], month=12, day=31)
    year_mask = (filtered['month_dt'].notna()) & (filtered['month_dt'] >= start_year_dt) & (filtered['month_dt'] <= end_year_dt)
else:
    year_mask = pd.Series([False]*len(filtered), index=filtered.index)

# ---------- KPIs ----------
st.markdown("### Quick KPIs")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total programs", int(filtered['program_count'].sum()))
k2.metric("Unique host companies", int(filtered['company'].nunique()))
k3.metric("Programs with month info", int(filtered['month_dt'].notna().sum()))
k4.metric("Programs in selected year range", int(filtered[year_mask]['program_count'].sum()))

# ---------- Top companies ----------
st.markdown("### Top host companies (by number of programs)")
by_company = filtered.groupby('company', as_index=False)['program_count'].sum().sort_values('program_count', ascending=False)
st.dataframe(by_company.head(30).reset_index(drop=True))

# top companies bar (clicking is not captured reliably in Streamlit; use selection control below to drill)
fig_comp = px.bar(by_company.head(20), x='company', y='program_count', title="Programs by company (top 20)")
fig_comp.update_layout(xaxis_tickangle=-45, height=420)
st.plotly_chart(fig_comp, use_container_width=True)

# company drill-down selector (the user wanted to click to drill; provide explicit select)
st.markdown("Select a company to drill down (or select multiple for comparison).")
sel_company = st.selectbox("Drill-down company (single)", options=["--All--"] + company_options, index=0)
sel_company_multi = st.multiselect("Or pick companies to compare (multi-select)", options=company_options, default=compare_companies)

# ---------- Monthly timeline (stacked) for Top N companies ----------
st.markdown("### Monthly timeline (stacked) — Top N companies")
top_companies = list(by_company.head(top_n)['company'])
timeline_df = filtered[filtered['company'].isin(top_companies) & filtered['month_dt'].notna()].copy()

if timeline_df.empty:
    st.info("No entries with parsable month/year for selected filters or top N.")
else:
    agg = (timeline_df.groupby([pd.Grouper(key='month_dt', freq='MS'), 'company'])
           .size().reset_index(name='count').sort_values('month_dt'))
    # limit to year range
    agg = agg[(agg['month_dt'] >= pd.Timestamp(year=year_range[0], month=1, day=1)) & (agg['month_dt'] <= pd.Timestamp(year=year_range[1], month=12, day=31))]
    fig_time = px.area(agg, x='month_dt', y='count', color='company', line_group='company',
                       title=f"Monthly program counts (top {top_n} companies) — stacked")
    fig_time.update_xaxes(dtick="M1", tickformat="%b\n%Y")
    fig_time.update_layout(height=480)
    st.plotly_chart(fig_time, use_container_width=True)

# ---------- Heatmap: companies vs months ----------
st.markdown("### Heatmap — Companies vs Months (counts)")
# build pivot for heatmap using top_companies (or top_n)
heat_companies = top_companies if top_companies else company_options[:top_n]
heat_df = filtered[filtered['company'].isin(heat_companies) & filtered['month_dt'].notna()].copy()
if heat_df.empty:
    st.info("No month-parsable rows to build heatmap. Try adjusting filters or season mapping.")
else:
    heat_agg = (heat_df.groupby([pd.Grouper(key='month_dt', freq='MS'), 'company']).size().reset_index(name='count'))
    # restrict by year_range
    heat_agg = heat_agg[(heat_agg['month_dt'] >= pd.Timestamp(year=year_range[0], month=1, day=1)) & (heat_agg['month_dt'] <= pd.Timestamp(year=year_range[1], month=12, day=31))]
    if heat_agg.empty:
        st.info("No heatmap data after applying the selected year range.")
    else:
        pivot = heat_agg.pivot(index='company', columns='month_dt', values='count').fillna(0)
        # sort companies by total desc
        pivot['total'] = pivot.sum(axis=1)
        pivot = pivot.sort_values('total', ascending=False).drop(columns='total')
        # prepare labels
        mx = pivot.columns
        col_labels = [c.strftime("%b %Y") for c in mx]
        fig_heat = px.imshow(pivot.values,
                            x=col_labels,
                            y=pivot.index,
                            labels=dict(x="Month", y="Company", color="Programs"),
                            aspect="auto",
                            title=f"Programs heatmap — companies vs months (top {len(pivot.index)} companies)")
        fig_heat.update_layout(height=500)
        st.plotly_chart(fig_heat, use_container_width=True)

# ---------- Top-month per company ----------
st.markdown("### Top month per company (month with highest program count)")
# compute month for each company
month_comp = filtered[filtered['month_dt'].notna()].copy()
if month_comp.empty:
    st.info("No parsable month entries to compute top-month per company.")
else:
    comp_month = (month_comp.groupby(['company', pd.Grouper(key='month_dt', freq='MS')])
                  .size().reset_index(name='count'))
    top_months = comp_month.loc[comp_month.groupby('company')['count'].idxmax()].sort_values('count', ascending=False)
    top_months['month_label'] = top_months['month_dt'].dt.strftime("%b %Y")
    st.dataframe(top_months[['company', 'month_label', 'count']].reset_index(drop=True).head(200))

# ---------- Drill-down / Comparison graphs for selected companies ----------
st.markdown("### Drill-down / Comparison")

# If user selected a single company to drill:
if sel_company != "--All--":
    cd = filtered[filtered['company'] == sel_company].copy()
    st.markdown(f"#### Drill-down: {sel_company}")
    st.write(f"Total programs: {int(cd['program_count'].sum())}")
    st.dataframe(cd[['program_name','domain','type','start_date','month_label','official_link']].reset_index(drop=True))
    # monthly trend for selected company
    if cd['month_dt'].notna().any():
        cd_agg = cd.groupby(pd.Grouper(key='month_dt', freq='MS')).size().reset_index(name='count')
        cd_agg = cd_agg[(cd_agg['month_dt'] >= pd.Timestamp(year=year_range[0], month=1, day=1)) & (cd_agg['month_dt'] <= pd.Timestamp(year=year_range[1], month=12, day=31))]
        fig_cd = px.bar(cd_agg, x='month_dt', y='count', title=f"Monthly counts — {sel_company}")
        fig_cd.update_xaxes(tickformat="%b\n%Y")
        st.plotly_chart(fig_cd, use_container_width=True)
    else:
        st.info("No month-parsable programs for this company.")

# Comparison for multi-selected companies
if sel_company_multi:
    comp_filter = filtered[filtered['company'].isin(sel_company_multi) & filtered['month_dt'].notna()].copy()
    if comp_filter.empty:
        st.info("No data for the selected companies (or months missing).")
    else:
        comp_agg = (comp_filter.groupby([pd.Grouper(key='month_dt', freq='MS'), 'company'])
                    .size().reset_index(name='count'))
        comp_agg = comp_agg[(comp_agg['month_dt'] >= pd.Timestamp(year=year_range[0], month=1, day=1)) & (comp_agg['month_dt'] <= pd.Timestamp(year=year_range[1], month=12, day=31))]
        fig_cmp = px.line(comp_agg, x='month_dt', y='count', color='company', markers=True,
                          title="Compare companies — monthly program counts")
        fig_cmp.update_xaxes(tickformat="%b\n%Y")
        st.plotly_chart(fig_cmp, use_container_width=True)

        # side-by-side small multiples: small bar charts per company
        st.markdown("#### Small multiples: monthly bars per selected company")
        cols = st.columns(min(len(sel_company_multi), 4))
        for i, comp in enumerate(sel_company_multi):
            with cols[i % len(cols)]:
                one = comp_filter[comp_filter['company'] == comp]
                agg_one = one.groupby(pd.Grouper(key='month_dt', freq='MS')).size().reset_index(name='count')
                if agg_one.empty:
                    st.write(f"{comp} — no month data")
                else:
                    fig_o = px.bar(agg_one, x='month_dt', y='count', title=comp)
                    fig_o.update_xaxes(tickformat="%b\n%Y")
                    st.plotly_chart(fig_o, use_container_width=True)

# ---------- Domain breakdown & comparisons ----------
st.markdown("### Domain & Type breakdowns")
domain_agg = filtered.groupby('domain', as_index=False)['program_count'].sum().sort_values('program_count', ascending=False)
type_agg = filtered.groupby('type', as_index=False)['program_count'].sum().sort_values('program_count', ascending=False)
col1, col2 = st.columns(2)
with col1:
    fig_dom = px.pie(domain_agg, names='domain', values='program_count', title="Programs by Domain")
    st.plotly_chart(fig_dom, use_container_width=True)
with col2:
    fig_typ = px.bar(type_agg, x='type', y='program_count', title="Programs by Type")
    fig_typ.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_typ, use_container_width=True)

# ---------- Raw / processed preview + download ----------
st.markdown("### Raw / processed data (preview)")
show_cols = ['program_name','company','domain','type','start_date','month_label','month_dt','official_link','source_name']
st.dataframe(filtered[show_cols].sort_values(['month_dt','company'], ascending=[False, True]).reset_index(drop=True))

csv = filtered.to_csv(index=False).encode('utf-8')
st.download_button("Download processed CSV", data=csv, file_name="programs_processed.csv", mime="text/csv")

# ---------- Footer notes ----------
st.markdown("---")
st.markdown("""
**Notes**
- Season → month mapping is selectable in the sidebar (you asked for Summer→June option).
- The app uses best-effort parsing for free-text `start_date` values. Explicit "June 2026" style dates produce the most accurate timeline.
- Streamlit's native plotly chart does not reliably capture JS click events for drill-down; that's why the app exposes explicit selection controls (`Drill-down company` and `Compare companies`) which provide deterministic drilling and comparisons.
- If you'd like, I can:
  - add clickable drill-down using a community component (e.g., `streamlit-plotly-events`) if you want that dependency,
  - produce a downloadable ZIP with these files,
  - or change the alternate season mapping to any other month numbers you prefer.
""")

