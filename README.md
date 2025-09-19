# 📊 Programs Dashboard — Companies & Monthly Trends

## 🔎 Project Overview
This project is an **interactive data analysis dashboard** built with **Streamlit**, **Pandas**, and **Plotly**.  
It reads structured data from a local **JSON file (`data.json`)** containing internship, training, or fellowship opportunities from top companies and startups.  

The dashboard allows users to:
- Analyze **which companies host the most programs**.
- Identify **seasonal and monthly trends** in hosted programs.
- Compare **domains** (AI, Data Analyst, Python, Go, etc.) and **program types** (Internship, Training, Fellowship).
- Drill down into a **single company** or **compare multiple companies** over time.
- Visualize results with **bar charts, area charts, heatmaps, and pie charts**.

This tool is designed for **students, analysts, or career researchers** who want insights into **how different companies release programs across months and years**.

---

## ✨ Features
- 📅 **Season → Month Mapping**: Flexible parsing of `start_date` (e.g., *"Summer 2026"* → **July 2026** or **June 2026**).  
- 🗓 **Year Range Selector**: Limit visualizations to a specific year range.  
- 🏢 **Top Companies Ranking**: Bar chart showing companies with the most programs.  
- 📈 **Monthly Timeline**: Stacked area chart of program counts by company.  
- 🔥 **Heatmap**: Compare companies vs months to see hosting intensity.  
- 🌟 **Top-Month per Company**: Automatically highlights each company’s busiest month.  
- 🕵️ **Drill-Down & Comparison**:  
  - Focus on one company.  
  - Compare multiple companies side-by-side.  
- 📊 **Domain & Program Type Breakdown**: Pie chart and bar chart analysis.  
- 📥 **Download CSV**: Export filtered/processed dataset.  

---

## 📂 Folder Structure
program-dashboard/
│
├── app.py # Main Streamlit app
├── data.json # Input dataset (sample provided)
├── requirements.txt # Dependencies (optional, use pip install instead)
└── venv/ # Virtual environment (created locally)

yaml
Copy code

---

## 🛠 Setup Guide

### 1. Clone or create project folder
```bash
mkdir program-dashboard
cd program-dashboard
2. Add the files
Save app.py (from this repo/code).

Save your dataset as data.json.

(Optional) create requirements.txt.

3. Create virtual environment
Windows (PowerShell):
powershell
Copy code
python -m venv venv
venv\Scripts\activate
macOS / Linux:
bash
Copy code
python3 -m venv venv
source venv/bin/activate
4. Install dependencies
Install each package separately for clarity:

bash
Copy code
pip install streamlit
pip install pandas
pip install plotly
pip install python-dateutil
(You already have them if you see them in pip list.)

🚀 Running the Dashboard
Once setup is done, run:

bash
Copy code
streamlit run app.py
Then open the link Streamlit provides (usually http://localhost:8501).

📊 Explanation of Visuals
1. KPIs (Top Metrics)
Total Programs → total number of entries in dataset.

Unique Companies → how many distinct companies host programs.

Programs with Month Info → how many start dates were successfully parsed.

Programs in Selected Year Range → filtered subset count.

2. Top Companies Bar Chart
Shows the companies hosting the most programs overall.

3. Monthly Timeline (Stacked)
Stacked area chart:

X-axis → months (Jan 2025, Feb 2025, etc.)

Y-axis → program count

Colors → companies

Helps visualize seasonal hosting trends.

4. Heatmap (Companies × Months)
Matrix visualization:

Rows → companies

Columns → months

Colors → intensity (# of programs)

Highlights when each company is most active.

5. Top Month per Company
Table showing each company’s busiest month with count.

6. Drill-Down View
Pick one company to analyze in detail:

Programs list

Timeline of that company’s activity

7. Company Comparisons
Select multiple companies → line chart + small multiples.
See how companies trend against each other over time.

8. Domain & Type Breakdown
Pie chart → which domains (AI, Data Analyst, Go, Python) dominate.

Bar chart → which program types (Internship, Training, Fellowship) dominate.

📥 Data Input Format
The dashboard expects a JSON array of objects with fields like:

json
Copy code
{
  "domain": "AI",
  "program_name": "Microsoft Research Internship (AI/ML)",
  "host_company_or_startup": "Microsoft",
  "type": "Internship",
  "application_deadline": "varies",
  "start_date": "Summer 2026",
  "location": "Global",
  "eligibility": "Grad/Undergrad",
  "short_summary": "Research internships in AI/ML teams.",
  "official_link": "https://careers.microsoft.com",
  "source_name": "careers.microsoft.com"
}
start_date can be free-text (Summer 2026, self-paced, rolling).

Parser will map seasons/months intelligently.

🔮 Future Improvements
⏩ Add rolling average trend lines (3-month smoothing).

🖱️ Enable click-to-drill-down using streamlit-plotly-events.

🛜 Add Google Sheets / API integration for live updates.

📑 Export PDF reports with charts and summaries.

