import streamlit as st
import os
import json
import polars as pl
import datetime
from dateutil.relativedelta import relativedelta
import sys

current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from component_generation import generate_component

st.set_page_config(
    layout="wide",
    page_icon="📊",
    page_title="Campaign Insights",
    initial_sidebar_state="collapsed"
)

st.markdown(
    """
    <style>
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(180deg, #2A5D4E 0%, #65897F 50%, #2A5D4E 100%);
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
    </style>
    """,
    unsafe_allow_html=True
)

parquet_source_path = None
dataset_creation_date = None

import glob, re
parquet_files = glob.glob("*.parquet")
if len(parquet_files) == 1:
    parquet_source_path = parquet_files[0]
    match = re.search(r'_(\d{4}-\d{2}-\d{2})T', parquet_source_path)
    if match:
        try:
            dataset_creation_date = datetime.datetime.strptime(match.group(1), '%Y-%m-%d').date()
        except ValueError:
            pass
    if not dataset_creation_date:
         try:
             mtime = os.path.getmtime(parquet_source_path)
             dataset_creation_date = datetime.date.fromtimestamp(mtime)
             st.warning(f"Could not extract date from filename '{parquet_source_path}'. Using file modification date: {dataset_creation_date}")
         except Exception:
            st.error(f"Could not determine dataset date for '{parquet_source_path}'. Using today's date.")
            dataset_creation_date = datetime.date.today()
    st.session_state.dataset_creation_date = dataset_creation_date

elif len(parquet_files) == 0:
    st.error("No Parquet file found in the root directory.")
    st.stop()
else:
    st.error(f"Multiple Parquet files found: {parquet_files}. Please ensure only one exists.")
    st.stop()

filter_metadata_path = "filter_metadata.json"
if not os.path.exists(filter_metadata_path):
    st.error(f"Filter metadata file not found at '{filter_metadata_path}'. Please run `database_download.py` first.")
    st.stop()

try:
    with open(filter_metadata_path, 'r', encoding='utf-8') as f:
        loaded_metadata = json.load(f)
    filter_options = {
        'categories': loaded_metadata.get('categories') or ['All Categories'],
        'date_ranges': ['All Time', 'Last Month', 'Last 6 Months', 'Last Year']
    }
    if 'All Categories' not in filter_options['categories']:
        filter_options['categories'].insert(0, 'All Categories')

except Exception as e:
    st.error(f"Error loading filter metadata from '{filter_metadata_path}': {e}. Using default filters.")
    filter_options = {
        'categories': ['All Categories'],
        'date_ranges': ['All Time', 'Last Month', 'Last 6 Months', 'Last Year']
    }

DEFAULT_INSIGHTS_FILTERS = {
    'categories': ['All Categories'],
    'date': 'All Time',
}

if 'insights_filters' not in st.session_state:
    st.session_state.insights_filters = DEFAULT_INSIGHTS_FILTERS.copy()
if 'insights_component_value' not in st.session_state:
    st.session_state.insights_component_value = None
if 'insights_state_sent_to_component' not in st.session_state:
    st.session_state.insights_state_sent_to_component = DEFAULT_INSIGHTS_FILTERS.copy()

if 'base_lf' not in st.session_state:
    try:
        st.session_state.base_lf = pl.scan_parquet(parquet_source_path)
        if len(st.session_state.base_lf.collect_schema().names()) == 0:
             st.error(f"Loaded data from '{parquet_source_path}' has no columns.")
             st.stop()
    except Exception as e:
        st.error(f"Error scanning Parquet source '{parquet_source_path}': {e}")
        st.stop()

css = """
<style>
    body {
        font-family: 'Poppins', sans-serif;
        margin: 0;
        padding: 10px;
        box-sizing: border-box;
        background-color: transparent;
    }
    #component-root {
        width: 100%;
    }

    .hidden {
        display: none !important;
    }

    .component-header {
        color: white;
        font-family: 'Playfair Display';
        font-weight: 500;
        font-size: 70px;
        margin-bottom: 25px;
        text-align: center;
    }

    .filter-bar {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 15px;
        padding: 15px 20px;
        border-radius: 12px;
        margin-bottom: 35px;
        flex-wrap: wrap;
    }
    .filter-bar span {
        font-family: 'Playfair Display', serif;
        font-size: 24px;
        color: white;
        white-space: nowrap;
    }
    .filter-select, .multi-select-btn {
        padding: 8px 15px;
        border: 1px solid #ccc;
        border-radius: 8px;
        font-family: 'Poppins', sans-serif;
        font-size: 14px;
        min-width: 150px;
        background: #fff;
        cursor: pointer;
        text-align: left;
        line-height: 1.4;
        height: 38px;
        box-sizing: border-box;
        color: #333;
    }
    .filter-select:focus, .multi-select-btn:focus {
        outline: none;
        border-color: #5932EA;
        box-shadow: 0 0 0 2px rgba(89, 50, 234, 0.2);
    }

    /* Multi-select Dropdown Styles */
    .multi-select-dropdown {
        position: relative;
        display: inline-block;
    }
    .multi-select-content {
        display: none;
        position: absolute;
        background-color: #fff;
        min-width: 220px;
        box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.15);
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #eee;
        z-index: 1001;
        max-height: 300px;
        overflow-y: auto;
        font-size: 13px;
    }

    .multi-select-content::-webkit-scrollbar { width: 6px; }
    .multi-select-content::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 10px;}
    .multi-select-content::-webkit-scrollbar-thumb { background: #ccc; border-radius: 10px;}
    .multi-select-content::-webkit-scrollbar-thumb:hover { background: #aaa; }

    .category-option {
        padding: 8px 12px;
        cursor: pointer;
        border-radius: 4px;
        margin: 2px 0;
        transition: background-color 0.2s ease, color 0.2s ease;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: #333;
    }
    .category-option:hover { background-color: #f0f0f0; }
    .category-option.selected { background-color: #5932EA; color: white; }
    .category-option.selected:hover { background-color: #4a28c7; }

    .category-option[data-value="All Categories"] {
        border-bottom: 1px solid #eee;
        margin-bottom: 8px;
        padding-bottom: 10px;
        font-weight: 500;
    }

    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 25px;
        padding: 0 15px;
        margin-bottom: 35px;
    }
    .metric-card {
        border-radius: 12px;
        padding: 20px;
        background: linear-gradient(135deg, #e8f5f9, #ffffff);
        color: #2c3e50;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 130px;
        box-sizing: border-box;
        position: relative;
        overflow: hidden;
        border: 1px solid #dfe6e9;
    }
    .metric-card:nth-child(odd), .metric-card:nth-child(even) {
        background: linear-gradient(135deg, #e8f5f9, #ffffff);
    }
    .metric-card:nth-child(even)::before {
        content: none;
    }

    .metric-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
        position: relative;
        z-index: 2;
    }
    .metric-row:first-child {
        margin-bottom: 15px;
    }

    .metric-name {
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
        font-size: 16px;
        white-space: nowrap;
        color: #34495e;
    }
    .metric-value {
        font-family: 'Poppins', sans-serif;
        font-weight: 700;
        font-size: 26px;
        white-space: nowrap;
        color: #2c3e50;
    }
    .metric-change-icon {
        font-size: 18px;
        font-weight: bold;
    }
    .metric-change-icon.up { color: #27ae60; }
    .metric-change-icon.down { color: #c0392b; }
    .metric-change-icon.neutral { color: #7f8c8d; }

    .metric-change-percentage {
        font-family: 'Poppins', sans-serif;
        font-size: 14px;
        font-weight: 500;
        white-space: nowrap;
    }
    .metric-change-percentage.positive { color: #27ae60; }
    .metric-change-percentage.negative { color: #c0392b; }
    .metric-change-percentage.neutral { color: #7f8c8d; }

    .loading-overlay {
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(255, 255, 255, 0.8);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10;
        font-size: 1.1em;
        color: #34495e;
        border-radius: 12px;
        opacity: 0;
        transition: opacity 0.3s ease-in-out;
        pointer-events: none;
    }

    .metrics-grid.loading .metric-card .loading-overlay {
        opacity: 1;
        pointer-events: auto;
    }
    .metrics-grid.loading .metric-card > *:not(.loading-overlay) {
        opacity: 0.4;
        transition: opacity 0.2s ease-in-out;
    }
    .metrics-grid.loading p {
        display: none;
    }

    .secondary-metrics-row {
        display: flex;
        gap: 25px;
        padding: 0 15px;
        margin-bottom: 25px;
        align-items: stretch;
    }

    .chart-card {
        border-radius: 12px;
        padding: 20px;
        background: linear-gradient(135deg, #f8f9fa, #ffffff);
        color: #2c3e50;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
        display: flex;
        flex-direction: column;
        box-sizing: border-box;
        border: 1px solid #e9ecef;
    }

    .chart-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        flex-wrap: wrap;
        gap: 10px;
    }

    .chart-title {
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
        font-size: 16px;
        color: #34495e;
        white-space: nowrap;
    }

    .chart-controls {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: #566573;
    }
    .chart-controls select {
        padding: 4px 8px;
        border: 1px solid #ccc;
        border-radius: 6px;
        font-family: 'Poppins', sans-serif;
        font-size: 12px;
        background: #fff;
        cursor: pointer;
        max-width: 100px;
    }
    .chart-controls select:focus {
         outline: none;
         border-color: #5932EA;
         box-shadow: 0 0 0 1px rgba(89, 50, 234, 0.2);
    }
    .chart-controls.hidden {
        display: none;
    }

    .chart-content {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        min-height: 250px;
        position: relative;
        font-size: 14px;
        color: #7f8c8d;
        width: 100%;
        box-sizing: border-box;
    }

    .chart-controls select#trendingMetricSelect {
        max-width: 200px;
    }

    .trending-card {
        flex: 2;
    }

    .goal-distribution-card {
        flex: 1;
    }

    .bar-chart-container {
        display: flex;
        justify-content: space-around;
        align-items: flex-end;
        height: 100%;
        width: 100%;
        gap: 5px;
        padding: 10px 5px 0;
        box-sizing: border-box;
    }
    .bar-wrapper {
         display: flex;
         flex-direction: column;
         align-items: center;
         flex: 1;
         text-align: center;
         position: relative;
    }
    .bar {
        background-color: #5dade2;
        width: 70%;
        min-height: 2px;
        border-radius: 3px 3px 0 0;
        transition: height 0.3s ease-out;
        position: relative;
    }
    .bar-value {
        position: absolute;
        top: -18px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 11px;
        font-weight: 500;
        color: #34495e;
        white-space: nowrap;
    }

    .bar-label {
        font-size: 10px;
        color: #566573;
        margin-top: 5px;
        white-space: nowrap;
    }

    .chart-placeholder {
         font-size: 14px;
         color: #7f8c8d;
         text-align: center;
         width: 100%;
         padding: 20px 0;
    }

    .tertiary-metrics-row {
        display: flex;
        gap: 25px;
        padding: 0 15px;
        margin-bottom: 25px;
        align-items: stretch;
    }
    .location-card {
        flex: 1;
    }
    .avg-funding-backer-card {
        flex: 2;
    }

    .quaternary-metrics-row {
        display: flex;
        gap: 25px;
        padding: 0 15px;
        margin-bottom: 25px;
    }

    .top-funded-card {
        flex: 1;
        padding: 15px 20px;
        display: flex;
        flex-direction: column;
        min-height: 250px;
    }

    .top-funded-card .chart-card-header {
        margin-bottom: 15px;
    }

    .top-funded-card .table-container {
        flex-grow: 1;
        max-height: 300px;
        overflow-y: auto;
        border: 1px solid #eee;
        border-radius: 8px;
        background-color: #ffffff;
        position: relative;
    }

    .top-funded-card .table-container table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Poppins', sans-serif;
        font-size: 14px;
        table-layout: fixed;
        background: #ffffff;
    }

    .top-funded-card .table-container th {
        font-weight: 500;
        color: #B5B7C0;
        background-color: #ffffff;
        position: sticky;
        top: 0;
        z-index: 1;
        padding: 12px 8px;
        text-align: left;
        border-bottom: 1px solid #ddd;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .top-funded-card .table-container td {
        padding: 12px 8px;
        text-align: left;
        border-bottom: 1px solid #ddd;
        color: #333;
        font-size: 14px;
        white-space: nowrap;
        overflow: hidden;
    }

     .top-funded-card .table-container th:nth-child(1),
     .top-funded-card .table-container td:nth-child(1) {
         width: 30%;
         padding: 8px;
        text-align: left;
        border-bottom: 1px solid #ddd;
        white-space: nowrap;
        font-family: 'Poppins';
        font-size: 14px;
        overflow-x: auto;
        -ms-overflow-style: none;
        overflow: -moz-scrollbars-none;
        scrollbar-width: none;
     }

     .top-funded-card .table-container th:nth-child(2),
     .top-funded-card .table-container td:nth-child(2) {
        width: 15%;
        padding: 8px;
        text-align: left;
        border-bottom: 1px solid #ddd;
        white-space: nowrap;
        font-family: 'Poppins';
        font-size: 14px;
        overflow-x: auto;
        -ms-overflow-style: none;
        overflow: -moz-scrollbars-none;
        scrollbar-width: none;
    }

     .top-funded-card .table-container th:nth-child(3),
     .top-funded-card .table-container td:nth-child(3).pledged-cell {
        width: 10%;
     }

     .top-funded-card .table-container th:nth-child(4),
     .top-funded-card .table-container td:nth-child(4) { width: 15%; }

     .top-funded-card .table-container th:nth-child(5),
     .top-funded-card .table-container td:nth-child(5) { width: 15%; }

     .top-funded-card .table-container th:nth-child(6),
     .top-funded-card .table-container td:nth-child(6) {
        width: 15%;
        padding: 8px;
        text-align: left;
        border-bottom: 1px solid #ddd;
        white-space: nowrap;
        font-family: 'Poppins';
        font-size: 14px;
        overflow-x: auto;
        -ms-overflow-style: none;
        overflow: -moz-scrollbars-none;
        scrollbar-width: none;
     }

    .top-funded-card .table-container td:nth-child(6) a {
        color: black;
        text-decoration: underline;
        font-family: 'Poppins';
        font-size: 14px;
         white-space: nowrap;
         text-decoration: underline;
        overflow: hidden;
        white-space: nowrap;
    }

    .top-funded-card .table-container td:nth-child(6) a:hover {
        text-decoration: underline;
    }

    .top-funded-card .table-container tr:last-child td {
        border-bottom: none;
    }

    .top-funded-card .table-container td a:hover {
        text-decoration: underline;
    }

    @media (max-width: 1350px) {
        .metrics-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }

    @media (max-width: 750px) {
        .component-header {
            font-size: 48px;
        }
        .metrics-grid {
            grid-template-columns: repeat(1, 1fr);
        }
        .filter-bar span {
            font-size: 20px;
        }
        .secondary-metrics-row,
        .tertiary-metrics-row {
            flex-direction: column;
        }
        .trending-card,
        .goal-distribution-card,
        .location-card,
        .avg-funding-backer-card {
            flex-basis: auto;
        }

        .top-funded-card .table-container {
             max-height: 250px;
        }
        .top-funded-card .table-container th,
        .top-funded-card .table-container td {
            font-size: 13px;
            padding: 10px 6px;
        }
        .top-funded-card .table-container th:nth-child(1),
        .top-funded-card .table-container td:nth-child(1) {
            width: 35%;
        }
        .top-funded-card .table-container th:nth-child(n+2),
        .top-funded-card .table-container td:nth-child(n+2) {
            width: auto;
        }

    }
    @media (max-width: 480px) {
         .component-header {
            font-size: 36px;
         }
         .filter-bar {
            flex-direction: column;
            align-items: stretch;
            gap: 10px;
         }
         .filter-bar span {
             text-align: center;
             margin-bottom: 5px;
         }
         .filter-select, .multi-select-btn {
             width: 100%;
             min-width: unset;
         }
          .metric-card {
             padding: 15px;
          }
          .metric-value {
             font-size: 22px;
          }
           .chart-title {
               font-size: 15px;
           }
           .chart-controls {
                flex-direction: column;
                align-items: flex-start;
                gap: 5px;
           }
           .chart-controls select {
                max-width: none;
                width: 100%;
           }
            .top-funded-card .table-container th,
            .top-funded-card .table-container td {
                font-size: 12px;
                padding: 8px 4px;
            }
    }

</style>
"""

chartjs_script_content = ""
chartjs_path = os.path.join(project_root, 'chart.js')
try:
    if os.path.exists(chartjs_path):
        with open(chartjs_path, 'r', encoding='utf-8') as f:
            chartjs_script_content = f.read()
    else:
        st.warning(f"Local chart.js not found at '{chartjs_path}'. Charting features might not work. Please place chart.js in the project root: {project_root}")
except Exception as e:
    st.error(f"Error reading local chart.js from '{chartjs_path}': {e}")

datalabels_plugin_content = ""
datalabels_plugin_path = os.path.join(project_root, 'chartjs-plugin-datalabels.js')
try:
    if os.path.exists(datalabels_plugin_path):
        with open(datalabels_plugin_path, 'r', encoding='utf-8') as f:
            datalabels_plugin_content = f.read()
    else:
        st.warning(f"Local chartjs-plugin-datalabels.js not found at '{datalabels_plugin_path}'. Data labels on charts will not be available.")
except Exception as e:
    st.error(f"Error reading local chartjs-plugin-datalabels.js from '{datalabels_plugin_path}': {e}")

script_template = """
if (typeof ChartDataLabels !== 'undefined') {
    Chart.register(ChartDataLabels);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return 'N/A';
    if (Math.abs(num) >= 1e9) return (num / 1e9).toFixed(1) + 'B';
    if (Math.abs(num) >= 1e6) return (num / 1e6).toFixed(1) + 'M';
    if (Math.abs(num) >= 1e3) return (num / 1e3).toFixed(1) + 'K';
    if (Number.isInteger(num)) return num.toLocaleString();
    return num.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1});
}

function formatCurrency(num) {
     if (num === null || num === undefined || isNaN(num)) return 'N/A';
     const absNum = Math.abs(num);
     const prefix = num < 0 ? '-$' : '$';
     if (absNum >= 1e9) return prefix + (absNum / 1e9).toFixed(1) + 'B';
     if (absNum >= 1e6) return prefix + (absNum / 1e6).toFixed(1) + 'M';
     if (absNum >= 1e3) return prefix + (absNum / 1e3).toFixed(1) + 'K';
     return prefix + absNum.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function formatPercentage(num, decimals = 1) {
    if (num === null || num === undefined || isNaN(num)) return 'N/A';
    if (Math.abs(num) < 0.01 && decimals > 0) return '0.0%';
    return num.toFixed(decimals) + '%';
}

function formatChartValue(value, metricName, mode = 'value') {
    if (value === null || value === undefined || isNaN(value)) return 'N/A';

    if (mode === 'change') {
        if (metricName === 'success_rate') {
             const sign = value >= 0 ? '+' : '';
             const displayPoints = Math.abs(value) < 0.01 ? 0.0 : value.toFixed(1);
             return `${sign}${displayPoints} pts`;
        } else {
             const sign = value >= 0 ? '+' : '';
             if (value > 10000) return '>+10k%';
             if (value < -10000) return '< -10k%';
             if (value === 99999.0) return '>+10k%';
             const displayPercent = Math.abs(value) < 0.01 ? 0.0 : value.toFixed(1);
             return sign + displayPercent + '%';
        }
    } else {
         if (metricName === 'total_pledged') {
              return formatCurrency(value);
         } else if (metricName === 'success_rate') {
              return formatPercentage(value, 1);
         } else {
              return formatNumber(value);
         }
    }
    return value.toLocaleString();
}

function getChangeIcon(change) {
    if (change === null || change === undefined || isNaN(change) || Math.abs(change) < 0.01) {
        return '<span class="metric-change-icon neutral">-</span>';
    } else if (change > 0) {
        return '<span class="metric-change-icon up">▲</span>';
    } else {
        return '<span class="metric-change-icon down">▼</span>';
    }
}

function getChangePercentageClass(change) {
    if (change === null || change === undefined || isNaN(change) || Math.abs(change) < 0.01) {
        return 'neutral';
    } else if (change > 0) {
        return 'positive';
    } else {
        return 'negative';
    }
}

class InsightsDashboard {
    constructor(initialData) {
        this.componentRoot = document.getElementById('component-root');
        if (!this.componentRoot) {
            return;
        }

        this.currentFilters = initialData.filters || {};
        this.filterOptions = initialData.filter_options || {};
        this.metricsData = initialData.metrics || {};
        this.goalDistributionData = initialData.goal_distribution || [];
        this.trendingData = initialData.trending_data || { mode: 'value', type: 'category', data: {} };
        this.isAllTime = this.currentFilters.date === 'All Time';
        this.selectedCategories = new Set(this.currentFilters.categories || ['All Categories']);
        this.singleCategorySelected = this.selectedCategories.size === 1 && !this.selectedCategories.has('All Categories');

        this.trendingSort = 'Growth';
        this.trendingMetric = 'total_pledged';
        this.metricDisplayNames = {
            'total_campaigns': 'Number of Campaigns',
            'total_pledged': 'Funds Raised',
            'successful_campaigns': 'Successful Campaigns',
            'success_rate': 'Success Rate'
        };

        this.valueSort = 'Top';

        this.openDropdown = null;
        this.hideDropdownTimeout = null;
        this._multiSelectClickHandler = null;
        this._bodyClickListener = null;
        this.adjustHeightTimeout = null;
        this.lastHeight = 0;
        this.trendingChartInstance = null;
        this.goalChartInstance = null;
        this.locationsChartInstance = null;
        this.avgFundingBackerChartInstance = null;

        this.renderHTMLStructure();
        this.bindStaticElements();
        this.updateUIState(initialData);
        this.adjustHeight();
    }

    renderHTMLStructure() {
        const metricOptionsHTML = Object.entries(this.metricDisplayNames)
            .map(([key, name]) => `<option value="${key}">${name}</option>`)
            .join('');
        this.componentRoot.innerHTML = `
            <div class="component-header">Uncovering Campaign Insights</div>
            <div class="filter-bar">
                <span>Uncover Insights for</span>
                <div class="multi-select-dropdown">
                    <button id="categoryFilterBtn" class="multi-select-btn">Categories</button>
                    <div class="multi-select-content" id="categoryOptionsContainer">
                    </div>
                </div>
                <span>In</span>
                <select id="dateFilter" class="filter-select">
                     ${(this.filterOptions.date_ranges || []).map(opt => `<option value="${opt}">${opt}</option>`).join('')}
                </select>
            </div>

            <div class="metrics-grid" id="metrics-grid">
                 <p class="loading-message" style="color: #34495e; text-align: center; grid-column: 1 / -1; padding: 30px; font-size: 16px; display: none;">Loading metrics...</p>
            </div>

            <div class="secondary-metrics-row">
                 <div class="chart-card trending-card">
                     <div class="chart-card-header">
                         <h3 class="chart-title" id="trendingTitle">Trending Categories</h3>
                         <div class="chart-controls" id="trendingControls">
                             <select id="trendingSortSelect">
                                 <option value="Growth">Growth</option>
                                 <option value="Decline">Decline</option>
                             </select>
                             <span>in</span>
                             <select id="trendingMetricSelect">
                                 ${metricOptionsHTML}
                             </select>
                         </div>
                     </div>
                     <div class="chart-content" id="trendingChartContainer">
                          <canvas id="trendingLineChartCanvas"></canvas>
                          <span class="chart-placeholder hidden">Loading trending data...</span>
                     </div>
                 </div>

                 <div class="chart-card goal-distribution-card">
                      <div class="chart-card-header">
                         <h3 class="chart-title">Funding Goal Distribution</h3>
                      </div>
                     <div class="chart-content" id="goalChartContainer">
                          <canvas id="goalDistributionChartCanvas"></canvas>
                          <span class="chart-placeholder hidden">Loading distribution data...</span>
                     </div>
                 </div>
            </div>

            <div class="tertiary-metrics-row">
                 <div class="chart-card location-card">
                      <div class="chart-card-header">
                         <h3 class="chart-title">Top Project Locations</h3>
                      </div>
                     <div class="chart-content" id="locationsChartContainer">
                          <canvas id="locationsChartCanvas"></canvas>
                          <span class="chart-placeholder hidden">Loading location data...</span>
                     </div>
                 </div>

                 <div class="chart-card avg-funding-backer-card">
                      <div class="chart-card-header">
                         <h3 class="chart-title" id="avgFundingTitle">Average Funding per Backer</h3>
                      </div>
                     <div class="chart-content" id="avgFundingBackerChartContainer">
                           <canvas id="avgFundingBackerChartCanvas"></canvas>
                           <span class="chart-placeholder hidden">Loading average funding data...</span>
                     </div>
                 </div>
            </div>

            <div class="quaternary-metrics-row">
                 <div class="chart-card top-funded-card" id="topFundedCard">
                      <div class="chart-card-header">
                         <h3 class="chart-title">Top Funded Campaigns</h3>
                      </div>
                      <div class="table-container" id="topFundedTableContainer">
                           <span class="chart-placeholder hidden">Loading top funded campaigns...</span>
                      </div>
                 </div>
            </div>
        `;
         const categoryContainer = this.componentRoot.querySelector('#categoryOptionsContainer');
         if (categoryContainer) {
             categoryContainer.innerHTML = (this.filterOptions.categories || [])
                 .map(opt => `<div class="category-option" data-value="${opt}">${opt}</div>`).join('');
         }
    }

     bindStaticElements() {
        if (!this.componentRoot) return;

        this.categoryBtn = document.getElementById('categoryFilterBtn');
        this.dateFilterSelect = document.getElementById('dateFilter');
        this.metricsGrid = document.getElementById('metrics-grid');
        this.categoryOptionsContainer = document.getElementById('categoryOptionsContainer');

        this.trendingTitle = document.getElementById('trendingTitle');
        this.trendingControls = document.getElementById('trendingControls');
        this.trendingSortSelect = document.getElementById('trendingSortSelect');
        this.trendingMetricSelect = document.getElementById('trendingMetricSelect');
        this.trendingChartContainer = document.getElementById('trendingChartContainer');
        this.trendingCanvas = document.getElementById('trendingLineChartCanvas');
        this.goalChartContainer = document.getElementById('goalChartContainer');
        this.goalCanvas = document.getElementById('goalDistributionChartCanvas');

        this.locationsChartContainer = document.getElementById('locationsChartContainer');
        this.locationsCanvas = document.getElementById('locationsChartCanvas');
        this.avgFundingBackerChartContainer = document.getElementById('avgFundingBackerChartContainer');
        this.avgFundingBackerCanvas = document.getElementById('avgFundingBackerChartCanvas');
        this.avgFundingTitle = document.getElementById('avgFundingTitle');

        this.topFundedCard = document.getElementById('topFundedCard');
        this.topFundedTableContainer = document.getElementById('topFundedTableContainer');

        if (!this.categoryBtn || !this.dateFilterSelect || !this.metricsGrid || !this.categoryOptionsContainer || !this.trendingTitle || !this.trendingControls || !this.trendingSortSelect || !this.trendingMetricSelect || !this.trendingChartContainer || !this.trendingCanvas || !this.goalChartContainer || !this.goalCanvas
           || !this.locationsChartContainer || !this.locationsCanvas || !this.avgFundingBackerChartContainer || !this.avgFundingBackerCanvas || !this.avgFundingTitle
           || !this.topFundedCard || !this.topFundedTableContainer
           ) {
             return;
        }

        this.dateFilterSelect.addEventListener('change', (e) => {
             this.currentFilters.date = e.target.value;
             this.isAllTime = this.currentFilters.date === 'All Time';
             this.requestUpdate();
        });
        this.setupMultiSelectListener();
        this._bindDropdowns();
        this._bindBodyClickListener();

        this.trendingSortSelect.addEventListener('change', (e) => {
            if (this.isAllTime) {
                this.valueSort = e.target.value;
            } else {
                this.trendingSort = e.target.value;
            }
            this.updateTrendingHeaderAndControls();
            this.renderTrendingChart(this.trendingData);
        });

        this.trendingMetricSelect.addEventListener('change', (e) => {
             this.trendingMetric = e.target.value;
             this.updateTrendingHeaderAndControls();
             this.renderTrendingChart(this.trendingData);
        });
    }

    _bindBodyClickListener() {
        if (this._bodyClickListener) {
             document.body.removeEventListener('click', this._bodyClickListener, true);
        }
        this._bodyClickListener = (event) => {
            if (this.openDropdown) {
                const wrapper = this.openDropdown.trigger.closest('.multi-select-dropdown');
                if (wrapper && !wrapper.contains(event.target) && event.target !== this.openDropdown.trigger) {
                     this._hideDropdownImmediately();
                }
            }
        };
        document.body.addEventListener('click', this._bodyClickListener, true);
    }

     _bindDropdowns() {
         if (!this.componentRoot) return;
         const dropdowns = this.componentRoot.querySelectorAll('.multi-select-dropdown');

         dropdowns.forEach(wrapper => {
             const trigger = wrapper.querySelector('button');
             const content = wrapper.querySelector('.multi-select-content');
             if (!trigger || !content) return;

             const toggleShow = (event) => {
                 event.stopPropagation();
                 this._cancelHideDropdown();

                 if (this.openDropdown?.content === content) {
                      this._hideDropdownImmediately();
                 } else {
                      if (this.openDropdown && this.openDropdown.content !== content) {
                          this._hideDropdownImmediately();
                      }
                      this._showDropdown(trigger, content);
                 }
             };

             const scheduleHide = () => this._scheduleHideDropdown();
             const cancelHide = () => this._cancelHideDropdown();

             trigger.addEventListener('click', toggleShow);

             wrapper.addEventListener('focusin', (e) => {
                 this._cancelHideDropdown();
             });
             content.addEventListener('mouseenter', cancelHide);

             wrapper.addEventListener('mouseleave', scheduleHide);
             wrapper.addEventListener('focusout', (e) => {
                 setTimeout(() => {
                     if (!wrapper.contains(document.activeElement)) {
                        this._scheduleHideDropdown(150);
                     } else {
                         this._cancelHideDropdown();
                     }
                 }, 0);
             });
         });
    }

    _positionDropdown(trigger, content) {
         const triggerRect = trigger.getBoundingClientRect();
         const parent = trigger.offsetParent;
         const parentRect = parent ? parent.getBoundingClientRect() : { top: 0, left: 0 };
         const componentRect = this.componentRoot.getBoundingClientRect();

         let topPosition = (parent ? trigger.offsetTop : 0) + trigger.offsetHeight + 2;
         let leftPosition = parent ? trigger.offsetLeft : 0;

         content.style.position = 'absolute';
         content.style.top = `${topPosition}px`;
         content.style.left = `${leftPosition}px`;
         content.style.display = 'block';
         content.style.minWidth = `${trigger.offsetWidth}px`;
         content.style.maxHeight = '300px';

         const contentRect = content.getBoundingClientRect();
         const viewportWidth = window.innerWidth;
         const viewportBottom = componentRect.bottom - 10;

         if (contentRect.right > viewportWidth - 10) {
             leftPosition = (parent ? trigger.offsetLeft : 0) + trigger.offsetWidth - content.offsetWidth;
             if (leftPosition < 10) {
                  leftPosition = 10;
             }
             content.style.left = `${leftPosition}px`;
         }

         if (contentRect.bottom > viewportBottom) {
              const topAbove = (parent ? trigger.offsetTop : 0) - content.offsetHeight - 2;
              if (triggerRect.top - parentRect.top + topAbove > 0) {
                   content.style.top = `${topAbove}px`;
              } else {
                  const availableHeight = viewportBottom - (triggerRect.top + triggerRect.height) - 2;
                  content.style.maxHeight = `${Math.max(50, availableHeight)}px`;
                  content.style.top = `${topPosition}px`;
              }
         }
    }

    _showDropdown(trigger, content) {
         if (this.openDropdown?.content === content) return;
         this._hideDropdownImmediately();

         this._positionDropdown(trigger, content);
         this.openDropdown = { trigger, content };

         this.adjustHeight();
    }

    _hideDropdownImmediately() {
         if (!this.openDropdown) return;
         this._cancelHideDropdown();
         this.openDropdown.content.style.display = 'none';
         this.openDropdown.content.style.maxHeight = '300px';
         this.openDropdown = null;
         this.adjustHeight();
    }

    _scheduleHideDropdown(delay = 250) {
         this._cancelHideDropdown();
         this.hideDropdownTimeout = setTimeout(() => {
             const wrapper = this.openDropdown?.trigger.closest('.multi-select-dropdown');
              if (wrapper && wrapper.contains(document.activeElement)) {
                  return;
              }
             this._hideDropdownImmediately();
         }, delay);
    }

    _cancelHideDropdown() {
         if (this.hideDropdownTimeout) {
             clearTimeout(this.hideDropdownTimeout);
             this.hideDropdownTimeout = null;
         }
    }

    setupMultiSelectListener() {
        if (!this.categoryOptionsContainer) {
            return;
        }
        this._multiSelectClickHandler = (e) => {
            if (e.target.classList.contains('category-option')) {
                e.stopPropagation();
                const clickedValue = e.target.dataset.value;
                const allValue = 'All Categories';

                const isAllCategories = clickedValue === allValue;
                const wasAllSelected = this.selectedCategories.has(allValue);

                if (isAllCategories) {
                    this.selectedCategories.clear();
                    this.selectedCategories.add(allValue);
                } else {
                    if (wasAllSelected) {
                        this.selectedCategories.delete(allValue);
                    }
                    if (this.selectedCategories.has(clickedValue)) {
                        this.selectedCategories.delete(clickedValue);
                    } else {
                        this.selectedCategories.add(clickedValue);
                    }
                    if (this.selectedCategories.size === 0) {
                        this.selectedCategories.add(allValue);
                    }
                }

                const options = this.categoryOptionsContainer.querySelectorAll('.category-option');
                 options.forEach(option => {
                    const isSelected = this.selectedCategories.has(option.dataset.value);
                    option.classList.toggle('selected', isSelected);
                 });

                this.currentFilters.categories = Array.from(this.selectedCategories);
                this.requestUpdate();
            }
        };

        this.categoryOptionsContainer.removeEventListener('click', this._multiSelectClickHandler);
        this.categoryOptionsContainer.addEventListener('click', this._multiSelectClickHandler);
    }

    updateMultiSelectUI() {
        if (!this.categoryOptionsContainer || !this.categoryBtn) {
             return;
        }
        const options = this.categoryOptionsContainer.querySelectorAll('.category-option');
        const allValue = 'All Categories';

         if (!options || options.length === 0 || !this.selectedCategories) return;

         options.forEach(option => {
            const isSelected = this.selectedCategories.has(option.dataset.value);
            option.classList.toggle('selected', isSelected);
         });

         this.updateButtonText(this.selectedCategories, this.categoryBtn, allValue);
    }

    updateButtonText(selectedItems, buttonElement, allValueLabel) {
          if (!buttonElement || !selectedItems) return;
          const selectedArray = Array.from(selectedItems);

          if (selectedItems.has(allValueLabel) || selectedArray.length === 0) {
              buttonElement.textContent = allValueLabel;
              buttonElement.title = '';
          } else {
               const displayItems = selectedArray.filter(item => item !== allValueLabel);
               displayItems.sort((a, b) => a.localeCompare(b));
               if (displayItems.length > 2) {
                  let text = `${displayItems[0]}, ${displayItems[1]} +${displayItems.length - 2}`;
                  buttonElement.textContent = text;
                  buttonElement.title = displayItems.join(', ');
               } else {
                   buttonElement.textContent = displayItems.join(', ');
                   buttonElement.title = '';
               }
           }
    }

    updateUIState(data) {
        const filtersChanged = JSON.stringify(this.currentFilters) !== JSON.stringify(data.filters);

        this.currentFilters = data.filters || {};
        this.metricsData = data.metrics || {};
        this.goalDistributionData = data.goal_distribution || [];
        this.trendingData = data.trending_data || { mode: 'value', type: 'category', data: {} };
        this.topLocationsData = data.top_locations || [];
        this.avgFundingPerBackerData = data.avg_funding_per_backer || { type: 'category', data: [] };
        this.topFundedCampaignsData = data.top_funded_campaigns || { data: [], column_header: 'Category' };
        this.filterOptions = data.filter_options || {};
        this.isAllTime = this.currentFilters.date === 'All Time';
        this.selectedCategories = new Set(this.currentFilters.categories || ['All Categories']);
        this.singleCategorySelected = this.selectedCategories.size === 1 && !this.selectedCategories.has('All Categories');

        if (this.dateFilterSelect) {
             this.dateFilterSelect.value = this.currentFilters.date || 'All Time';
        }
         const categoryOptionsChanged = this._checkCategoryOptionsChanged(this.filterOptions.categories);
         if (this.categoryOptionsContainer && categoryOptionsChanged) {
             this.categoryOptionsContainer.innerHTML = (this.filterOptions.categories || [])
                 .map(opt => `<div class="category-option" data-value="${opt}">${opt}</div>`).join('');
         }
        this.updateMultiSelectUI();

        this.updateMetrics();
        this.updateSecondaryCharts();
        this.updateTertiaryCharts();
        this.updateQuaternaryTable();

        if (!this.openDropdown) { this._hideDropdownImmediately(); }
        this.adjustHeight();
    }

    _checkCategoryOptionsChanged(newOptionsData) {
        if (!this.categoryOptionsContainer) return true;
        const currentOptions = Array.from(this.categoryOptionsContainer.querySelectorAll('.category-option')).map(el => el.dataset.value);
        const newOptions = newOptionsData || [];
        return JSON.stringify(currentOptions) !== JSON.stringify(newOptions);
    }

    updateMetrics() {
        if (!this.metricsGrid) { return; }

        const loadingP = this.metricsGrid.querySelector('p.loading-message');
        this.metricsGrid.classList.remove('loading');
        if (loadingP) loadingP.style.display = 'none';

        this.metricsGrid.innerHTML = '';

        const metrics = this.metricsData;
        if (!metrics || Object.keys(metrics).length === 0 || Object.values(metrics).every(m => m === null || m.current === null || m.current === undefined)) {
            this.metricsGrid.innerHTML = `<p style="color: #7f8c8d; text-align: center; grid-column: 1 / -1; padding: 30px; font-size: 16px;">No data available for the selected filters.</p>`;
            return;
        }

        this.metricsGrid.appendChild(this.createMetricCard('Number of Campaigns', metrics.total_campaigns?.current, metrics.total_campaigns?.change_pct, formatNumber));
        this.metricsGrid.appendChild(this.createMetricCard('Funds Raised', metrics.total_pledged?.current, metrics.total_pledged?.change_pct, formatCurrency));
        this.metricsGrid.appendChild(this.createMetricCard('Successful Campaigns', metrics.successful_campaigns?.current, metrics.successful_campaigns?.change_pct, formatNumber));
        this.metricsGrid.appendChild(this.createMetricCard('Success Rate', metrics.success_rate?.current, metrics.success_rate?.change_pct, formatPercentage, true ));
    }

    createMetricCard(name, currentValue, changeValue, formatFn, isRate = false) {
        const card = document.createElement('div');
        card.className = 'metric-card';

        const nameElement = `<div class="metric-name">${name}</div>`;
        const formattedValue = (currentValue !== null && currentValue !== undefined) ? formatFn(currentValue) : 'N/A';
        const valueElement = `<div class="metric-value">${formattedValue}</div>`;

        let iconElement = '';
        let changeElement = '';

        if (!this.isAllTime && typeof changeValue === 'number' && !isNaN(changeValue)) {
            iconElement = getChangeIcon(changeValue);
            const changeClass = getChangePercentageClass(changeValue);

            let changeDisplayValue;
            if (isRate) {
                 const sign = changeValue >= 0 ? '+' : '';
                 const displayPoints = Math.abs(changeValue) < 0.01 ? 0.0 : changeValue.toFixed(1);
                 changeDisplayValue = `${sign}${displayPoints} pts`;
            } else {
                const sign = changeValue >= 0 ? '+' : '';
                const displayPercent = Math.abs(changeValue) < 0.01 ? 0.0 : changeValue.toFixed(1);
                changeDisplayValue = `${sign}${displayPercent}%`;
            }

            changeElement = `<div class="metric-change-percentage ${changeClass}">${changeDisplayValue}</div>`;
        } else if (!this.isAllTime) {
            iconElement = `<span class="metric-change-icon neutral">-</span>`;
            changeElement = `<div class="metric-change-percentage neutral">vs Prev</div>`;
        }

        card.innerHTML = `
            <div class="metric-row">
                ${nameElement}
                ${iconElement}
            </div>
            <div class="metric-row">
                ${valueElement}
                ${changeElement}
            </div>
            <div class="loading-overlay hidden">Loading...</div>
        `;
        const overlay = card.querySelector('.loading-overlay');
        if (overlay) { overlay.classList.add('hidden'); }
        return card;
    }

    updateSecondaryCharts() {
        this.updateTrendingHeaderAndControls();

        if (this.trendingCanvas) {
             this.renderTrendingChart(this.trendingData);
        } else {
             if(this.trendingChartContainer) this.trendingChartContainer.innerHTML = '<span class="chart-placeholder">Error: Canvas not found.</span>';
        }

        if (this.goalChartContainer) {
            this.renderGoalChart(this.goalDistributionData || []);
        }
    }

    updateTrendingHeaderAndControls() {
         if (!this.trendingTitle || !this.trendingControls || !this.trendingSortSelect || !this.trendingMetricSelect) {
             return;
         }
         const trendingInfo = this.trendingData;
         const trendType = trendingInfo?.type === 'subcategory' && this.singleCategorySelected ? 'Subcategories' : 'Categories';
         const metricName = this.metricDisplayNames[this.trendingMetric] || 'Metric';
         const mode = trendingInfo?.mode || 'value';

         if (this.isAllTime) {
              this.trendingSortSelect.innerHTML = `
                  <option value="Top">Top</option>
                  <option value="Bottom">Bottom</option>
              `;
              this.trendingSortSelect.value = this.valueSort;

              const sortPrefix = this.valueSort === 'Top' ? 'Top' : 'Bottom';
              this.trendingTitle.textContent = `${sortPrefix} ${trendType} by ${metricName}`;

              this.trendingControls.classList.remove('hidden');
              this.trendingSortSelect.style.display = 'inline-block';
              this.trendingMetricSelect.style.display = 'inline-block';
              this.trendingMetricSelect.value = this.trendingMetric;

         } else {
             this.trendingSortSelect.innerHTML = `
                  <option value="Growth">Growth</option>
                  <option value="Decline">Decline</option>
              `;
             this.trendingSortSelect.value = this.trendingSort;

             let titlePrefix = '';
             if (this.trendingMetric === 'success_rate') {
                  titlePrefix = this.trendingSort === 'Growth' ? 'Largest Increase' : 'Largest Decrease';
                  this.trendingTitle.textContent = `${titlePrefix} in ${trendType} Success Rate`;
                  this.trendingSortSelect.style.display = 'inline-block';
             } else {
                  titlePrefix = this.trendingSort === 'Growth' ? 'Fastest Growing' : 'Fastest Declining';
                  this.trendingTitle.textContent = `${titlePrefix} ${trendType} by ${metricName}`;
                  this.trendingSortSelect.style.display = 'inline-block';
             }

             this.trendingControls.classList.remove('hidden');
             this.trendingMetricSelect.style.display = 'inline-block';
             this.trendingMetricSelect.value = this.trendingMetric;
         }
    }

     renderGoalChart(data) {
         if (!this.goalChartContainer || !this.goalCanvas) return;
         if (typeof Chart === 'undefined' || typeof ChartDataLabels === 'undefined') {
             this.goalChartContainer.innerHTML = `<span class="chart-placeholder">Error: Charting library or plugin failed to load.</span>`;
             return;
         }

         const placeholder = this.goalChartContainer.querySelector('.chart-placeholder');
         if (placeholder) placeholder.classList.add('hidden');
         this.goalCanvas.style.display = 'block';

         if (!data || data.length === 0 || data.every(d => d.count === 0)) {
             if (placeholder) {
                  placeholder.textContent = "No goal data available.";
                  placeholder.classList.remove('hidden');
             }
             if (this.goalChartInstance) {
                 this.goalChartInstance.destroy();
                 this.goalChartInstance = null;
             }
             this.goalCanvas.style.display = 'none';
             return;
         }

         const labels = data.map(item => item.bin);
         const counts = data.map(item => item.count);
         const barBackgroundColor = 'rgba(32, 191, 182, 0.75)';
         const barBorderColor = 'rgba(32, 191, 182, 1)';

         if (this.goalChartInstance) {
             this.goalChartInstance.destroy();
         }

         const ctx = this.goalCanvas.getContext('2d');
         const chartConfig = {
             type: 'bar',
             data: {
                 labels: labels,
                 datasets: [{
                     label: 'Number of Campaigns',
                     data: counts,
                     backgroundColor: barBackgroundColor,
                     borderColor: barBorderColor,
                     borderWidth: 1
                 }]
             },
             options: {
                 responsive: true,
                 maintainAspectRatio: false,
                 layout: {
                     padding: {
                         top: 30
                     }
                 },
                 plugins: {
                     legend: { display: false },
                     tooltip: {
                          backgroundColor: 'rgba(0, 0, 0, 0.7)',
                          titleFont: { weight: 'bold' },
                          bodyFont: { size: 13 },
                          padding: 10,
                          cornerRadius: 4,
                          displayColors: false,
                          callbacks: {
                              label: (context) => {
                                   let label = context.dataset.label || '';
                                   if (label) { label += ': '; }
                                   const value = context.parsed.y;
                                   label += formatNumber(value);
                                   return label;
                              }
                          }
                     },
                     datalabels: {
                         display: true,
                         anchor: 'end',
                         align: 'end',
                         offset: 8,
                         color: '#333',
                         backgroundColor: 'rgba(255, 255, 255, 0.75)',
                         borderRadius: 3,
                         padding: { top: 2, bottom: 1, left: 4, right: 4 },
                         font: {
                             size: 11,
                             weight: '500',
                             family: "'Poppins', sans-serif"
                         },
                         formatter: (value, context) => {
                             return formatNumber(value);
                         },
                         display: (context) => context.dataset.data[context.dataIndex] > 0,
                     }
                 },
                 scales: {
                     y: {
                         display: false,
                         beginAtZero: true,
                         grid: {
                             display: false,
                             drawBorder: false
                         }
                     },
                     x: {
                         grid: {
                             display: false,
                             drawBorder: false
                         },
                         ticks: {
                             color: '#566573',
                             font: {
                                 size: 11,
                                 family: "'Poppins', sans-serif"
                             }
                         }
                     }
                 }
             }
         };

         try {
             this.goalChartInstance = new Chart(ctx, chartConfig);
         } catch (error) {
              this.goalChartContainer.innerHTML = `<span class="chart-placeholder">Error rendering goal chart.</span>`;
              this.goalCanvas.style.display = 'none';
         }
     }

    renderTrendingChart(trendingInfo) {
        if (!this.trendingCanvas || !this.trendingChartContainer) return;
        if (typeof Chart === 'undefined' || typeof ChartDataLabels === 'undefined') {
            this.trendingChartContainer.innerHTML = `<span class="chart-placeholder">Error: Charting library or plugin failed to load.</span>`;
            return;
        }

        const { type, mode, data } = trendingInfo || { type: 'category', mode: 'value', data: {} };
        const items = data[this.trendingMetric] || [];
        const TRENDING_LIMIT = 5;

        let processedItems = [];
        if (items && items.length > 0) {
             const validItems = items.filter(item => item.value !== null && item.value !== undefined);
             if (mode === 'change') {
                 if (this.trendingSort === 'Growth') {
                      processedItems = validItems.filter(item => item.value > 0)
                           .sort((a, b) => b.value - a.value).slice(0, TRENDING_LIMIT);
                 } else {
                      processedItems = validItems.filter(item => item.value < 0)
                           .sort((a, b) => a.value - b.value).slice(0, TRENDING_LIMIT);
                 }
             } else {
                  if (this.valueSort === 'Top') {
                       processedItems = validItems.sort((a, b) => b.value - a.value).slice(0, TRENDING_LIMIT);
                  } else {
                       processedItems = validItems.sort((a, b) => a.value - b.value).slice(0, TRENDING_LIMIT);
                  }
             }
        }

        const placeholder = this.trendingChartContainer.querySelector('.chart-placeholder');
        if (placeholder) placeholder.classList.add('hidden');
        this.trendingCanvas.style.display = 'block';

        if (processedItems.length === 0) {
            let placeholderText = `No ${type} data available for ${this.metricDisplayNames[this.trendingMetric]}.`;
             if (mode === 'change') {
                  const sortType = this.trendingSort === 'Growth' ? 'growth' : 'decline';
                  placeholderText = `No significant ${sortType} found for ${type}s in ${this.metricDisplayNames[this.trendingMetric]}.`;
             } else {
                  const sortType = this.valueSort === 'Top' ? 'top' : 'bottom';
                   placeholderText = `No data available to show ${sortType} ${type}s for ${this.metricDisplayNames[this.trendingMetric]}.`;
             }
             if (this.trendingChartInstance) {
                 this.trendingChartInstance.destroy();
                 this.trendingChartInstance = null;
             }
             if (placeholder) {
                 placeholder.textContent = placeholderText;
                 placeholder.classList.remove('hidden');
             }
             this.trendingCanvas.style.display = 'none';
            return;
        }

        const labels = processedItems.map(item => item.name);
        const values = processedItems.map(item => item.value);
        const pointBackgroundColors = mode === 'change'
           ? processedItems.map(item => item.value > 0 ? 'rgba(40, 167, 69, 0.9)' : 'rgba(220, 53, 69, 0.9)')
           : 'rgba(0, 123, 255, 0.9)';
        const pointBorderColor = '#fff';
        const lineBorderColor = 'rgba(0, 123, 255, 0.6)';

        const datasetLabel = this.metricDisplayNames[this.trendingMetric] || 'Value';

        if (this.trendingChartInstance) {
            this.trendingChartInstance.destroy();
        }

        const ctx = this.trendingCanvas.getContext('2d');
        const chartConfig = {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: datasetLabel,
                    data: values,
                    fill: false,
                    borderColor: lineBorderColor,
                    pointBackgroundColor: pointBackgroundColors,
                    pointBorderColor: pointBorderColor,
                    pointBorderWidth: 1.5,
                    tension: 0.3,
                    pointRadius: 6,
                    pointHoverRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: {
                        top: 40
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.7)',
                        titleFont: { weight: 'bold' },
                        bodyFont: { size: 13 },
                        padding: 10,
                        cornerRadius: 4,
                        displayColors: false,
                        callbacks: {
                            label: (context) => {
                                let label = context.dataset.label || '';
                                if (label) { label += ': '; }
                                const value = context.parsed.y;
                                label += formatChartValue(value, this.trendingMetric, mode);
                                return label;
                            }
                        }
                    },
                    datalabels: {
                        display: true,
                        anchor: 'end',
                        align: 'end',
                        offset: 12,
                        color: '#333',
                        backgroundColor: 'rgba(255, 255, 255, 0.75)',
                        borderRadius: 3,
                        padding: { top: 2, bottom: 1, left: 4, right: 4 },
                        font: {
                            size: 11,
                            weight: '600',
                            family: "'Poppins', sans-serif"
                        },
                        formatter: (value, context) => {
                             return formatChartValue(value, this.trendingMetric, mode);
                        },
                    }
                },
                scales: {
                    y: {
                        display: false,
                        beginAtZero: mode === 'value',
                        grid: {
                            display: false,
                            drawBorder: false
                        }
                    },
                    x: {
                        grid: {
                            display: false,
                            drawBorder: false
                        },
                        ticks: {
                             autoSkip: true,
                             maxRotation: 0,
                             minRotation: 0,
                             color: '#566573',
                             font: {
                                 size: 11,
                                 family: "'Poppins', sans-serif"
                             }
                        }
                    }
                },
                interaction: {
                   mode: 'index',
                   intersect: false
                }
            }
        };

        try {
            this.trendingChartInstance = new Chart(ctx, chartConfig);
        } catch (error) {
             this.trendingChartContainer.innerHTML = `<span class="chart-placeholder">Error rendering chart.</span>`;
             this.trendingCanvas.style.display = 'none';
        }
    }

    requestUpdate() {
        if (this.metricsGrid) {
             this.metricsGrid.classList.add('loading');
             const loadingP = this.metricsGrid.querySelector('p.loading-message');
             if (loadingP) loadingP.style.display = 'block';
             this.metricsGrid.querySelectorAll('.metric-card .loading-overlay').forEach(overlay => {
                  overlay.classList.remove('hidden');
             });
              this.metricsGrid.querySelectorAll('.metric-card > *:not(.loading-overlay)').forEach(el => {
                  el.style.opacity = '0.4';
              });
        }

         if (this.trendingChartContainer) {
             if (this.trendingChartInstance) {
                 this.trendingChartInstance.destroy();
                 this.trendingChartInstance = null;
             }
             const placeholder = this.trendingChartContainer.querySelector('.chart-placeholder');
             if (placeholder) {
                 placeholder.textContent = "Loading trending data...";
                 placeholder.classList.remove('hidden');
             }
             if (this.trendingCanvas) this.trendingCanvas.style.display = 'none';
         }
         if (this.goalChartContainer) {
             if (this.goalChartInstance) {
                 this.goalChartInstance.destroy();
                 this.goalChartInstance = null;
             }
             const placeholder = this.goalChartContainer.querySelector('.chart-placeholder');
             if (placeholder) {
                 placeholder.textContent = "Loading distribution data...";
                 placeholder.classList.remove('hidden');
             }
             if (this.goalCanvas) this.goalCanvas.style.display = 'none';
         }

         if (this.locationsChartContainer) {
              if (this.locationsChartInstance) { this.locationsChartInstance.destroy(); this.locationsChartInstance = null; }
              const placeholder = this.locationsChartContainer.querySelector('.chart-placeholder');
              if (placeholder) { placeholder.textContent = "Loading location data..."; placeholder.classList.remove('hidden'); }
              if (this.locationsCanvas) this.locationsCanvas.style.display = 'none';
         }

         if (this.avgFundingBackerChartContainer) {
              if (this.avgFundingBackerChartInstance) { this.avgFundingBackerChartInstance.destroy(); this.avgFundingBackerChartInstance = null; }
               const placeholder = this.avgFundingBackerChartContainer.querySelector('.chart-placeholder');
              if (placeholder) { placeholder.textContent = "Loading average funding data..."; placeholder.classList.remove('hidden'); }
              if (this.avgFundingBackerCanvas) this.avgFundingBackerCanvas.style.display = 'none';
         }

         if (this.topFundedTableContainer) {
             this.topFundedTableContainer.innerHTML = '<span class="chart-placeholder">Loading top funded campaigns...</span>';
             const placeholder = this.topFundedTableContainer.querySelector('.chart-placeholder');
             if (placeholder) placeholder.classList.remove('hidden');

         }

        this._hideDropdownImmediately();

        const state = {
            filters: {
                categories: Array.from(this.selectedCategories),
                date: this.dateFilterSelect.value,
            }
        };
        Streamlit.setComponentValue(state);
        this.adjustHeight();
    }

     adjustHeight() {
         if (this.adjustHeightTimeout) clearTimeout(this.adjustHeightTimeout);
         this.adjustHeightTimeout = setTimeout(() => {
             if (!this.componentRoot) return;

             let requiredHeight = this.componentRoot.scrollHeight;

             if (this.openDropdown) {
                 const dropdownContent = this.openDropdown.content;
                 const dropdownRect = dropdownContent.getBoundingClientRect();
                 const rootRect = this.componentRoot.getBoundingClientRect();
                 const dropdownBottomRelativeToRoot = (dropdownRect.top - rootRect.top) + dropdownRect.height;
                 requiredHeight = Math.max(requiredHeight, dropdownBottomRelativeToRoot);
             }

             const totalHeight = requiredHeight + 40;

             if (!this.lastHeight || Math.abs(this.lastHeight - totalHeight) > 5) {
                 this.lastHeight = totalHeight;
                 Streamlit.setFrameHeight(totalHeight);
             }
         }, 100);
     }

    updateTertiaryCharts() {
        if (this.locationsCanvas) {
            this.renderTopLocationsChart(this.topLocationsData || []);
        } else {
            if(this.locationsChartContainer) this.locationsChartContainer.innerHTML = '<span class="chart-placeholder">Error: Canvas not found.</span>';
        }

        if (this.avgFundingBackerCanvas) {
            this.renderAvgFundingPerBackerChart(this.avgFundingPerBackerData || { type: 'category', data: [] });
        } else {
             if(this.avgFundingBackerChartContainer) this.avgFundingBackerChartContainer.innerHTML = '<span class="chart-placeholder">Error: Canvas not found.</span>';
        }
    }

    renderTopLocationsChart(data) {
         if (!this.locationsCanvas || !this.locationsChartContainer) return;
         if (typeof Chart === 'undefined' || typeof ChartDataLabels === 'undefined') {
             this.locationsChartContainer.innerHTML = `<span class="chart-placeholder">Error: Charting library not loaded.</span>`;
             return;
         }

         const placeholder = this.locationsChartContainer.querySelector('.chart-placeholder');
         if (placeholder) placeholder.classList.add('hidden');
         this.locationsCanvas.style.display = 'block';

         if (!data || data.length === 0) {
             if (placeholder) {
                 placeholder.textContent = "No location data available.";
                 placeholder.classList.remove('hidden');
             }
             if (this.locationsChartInstance) {
                 this.locationsChartInstance.destroy();
                 this.locationsChartInstance = null;
             }
             this.locationsCanvas.style.display = 'none';
             return;
         }

         const labels = data.map(item => item.location);
         const counts = data.map(item => item.count);
         const barBackgroundColor = 'rgba(255, 159, 64, 0.75)';
         const barBorderColor = 'rgba(255, 159, 64, 1)';

         if (this.locationsChartInstance) {
             this.locationsChartInstance.destroy();
         }

         const ctx = this.locationsCanvas.getContext('2d');
         const chartConfig = {
             type: 'bar',
             data: {
                 labels: labels,
                 datasets: [{
                     label: 'Number of Campaigns',
                     data: counts,
                     backgroundColor: barBackgroundColor,
                     borderColor: barBorderColor,
                     borderWidth: 1
                 }]
             },
             options: {
                 indexAxis: 'y',
                 responsive: true,
                 maintainAspectRatio: false,
                  layout: {
                     padding: {
                         left: 10,
                         right: 20
                     }
                 },
                 plugins: {
                     legend: { display: false },
                     tooltip: {
                         backgroundColor: 'rgba(0, 0, 0, 0.7)',
                         titleFont: { weight: 'bold' }, bodyFont: { size: 13 }, padding: 10, cornerRadius: 4, displayColors: false,
                         callbacks: { label: (context) => `Campaigns: ${formatNumber(context.parsed.x)}` }
                     },
                     datalabels: {
                         display: true,
                         anchor: 'end',
                         align: 'end',
                         offset: 4,
                         color: '#444',
                         backgroundColor: 'rgba(255, 255, 255, 0.7)', borderRadius: 3, padding: { left: 3, right: 3, top:1, bottom:1 },
                         font: { size: 10, weight: '500', family: "'Poppins', sans-serif" },
                         formatter: (value, context) => formatNumber(value),
                          display: (context) => context.dataset.data[context.dataIndex] > 0,
                     }
                 },
                 scales: {
                     x: {
                         display: false,
                         beginAtZero: true,
                         grid: { display: false, drawBorder: false }
                     },
                     y: {
                         grid: { display: false, drawBorder: false },
                         ticks: {
                             color: '#566573',
                             font: { size: 11, family: "'Poppins', sans-serif" }
                         }
                     }
                 }
             }
         };

         try {
             this.locationsChartInstance = new Chart(ctx, chartConfig);
         } catch (error) {
              this.locationsChartContainer.innerHTML = `<span class="chart-placeholder">Error rendering locations chart.</span>`;
              this.locationsCanvas.style.display = 'none';
         }
    }

    renderAvgFundingPerBackerChart(avgFundingInfo) {
        if (!this.avgFundingBackerCanvas || !this.avgFundingBackerChartContainer) return;
         if (typeof Chart === 'undefined' || typeof ChartDataLabels === 'undefined') {
             this.avgFundingBackerChartContainer.innerHTML = `<span class="chart-placeholder">Error: Charting library not loaded.</span>`;
             return;
         }

         const { type, data } = avgFundingInfo || { type: 'category', data: [] };
         const groupTypeName = type === 'subcategory' ? 'Subcategory' : 'Category';

          if (this.avgFundingTitle) {
             this.avgFundingTitle.textContent = `Average Funding per Backer by ${groupTypeName}`;
         }

         const placeholder = this.avgFundingBackerChartContainer.querySelector('.chart-placeholder');
         if (placeholder) placeholder.classList.add('hidden');
         this.avgFundingBackerCanvas.style.display = 'block';

         if (!data || data.length === 0) {
             if (placeholder) {
                 placeholder.textContent = `No average funding data available by ${groupTypeName}.`;
                 placeholder.classList.remove('hidden');
             }
             if (this.avgFundingBackerChartInstance) {
                 this.avgFundingBackerChartInstance.destroy();
                 this.avgFundingBackerChartInstance = null;
             }
             this.avgFundingBackerCanvas.style.display = 'none';
             return;
         }

         const labels = data.map(item => item.name);
         const values = data.map(item => item.value);
         const lineBorderColor = 'rgba(75, 192, 192, 0.8)';
         const pointBackgroundColor = 'rgba(75, 192, 192, 1)';
         const pointBorderColor = '#fff';

         if (this.avgFundingBackerChartInstance) {
             this.avgFundingBackerChartInstance.destroy();
         }

         const ctx = this.avgFundingBackerCanvas.getContext('2d');
         const chartConfig = {
             type: 'line',
             data: {
                 labels: labels,
                 datasets: [{
                     label: 'Avg Funding/Backer',
                     data: values,
                     fill: false,
                     borderColor: lineBorderColor,
                     pointBackgroundColor: pointBackgroundColor,
                     pointBorderColor: pointBorderColor,
                     pointBorderWidth: 1.5,
                     tension: 0.1,
                     pointRadius: 5,
                     pointHoverRadius: 7
                 }]
             },
             options: {
                 responsive: true,
                 maintainAspectRatio: false,
                 layout: { padding: { top: 25 } },
                 plugins: {
                     legend: { display: false },
                     tooltip: {
                         backgroundColor: 'rgba(0, 0, 0, 0.7)', titleFont: { weight: 'bold' }, bodyFont: { size: 13 }, padding: 10, cornerRadius: 4, displayColors: false,
                         callbacks: {
                             label: (context) => {
                                 let label = context.dataset.label || '';
                                 if (label) { label += ': '; }
                                 const value = context.parsed.y;
                                 label += formatCurrency(value);
                                 return label;
                             }
                         }
                     },
                     datalabels: {
                         display: true, anchor: 'end', align: 'end', offset: 8,
                         color: '#333', backgroundColor: 'rgba(255, 255, 255, 0.75)', borderRadius: 3, padding: { top: 2, bottom: 1, left: 4, right: 4 },
                         font: { size: 10, weight: '600', family: "'Poppins', sans-serif" },
                         formatter: (value, context) => formatCurrency(value),
                     }
                 },
                 scales: {
                     y: { display: false, grid: { display: false, drawBorder: false }, beginAtZero: true },
                     x: {
                         grid: { display: false, drawBorder: false },
                         ticks: {
                              autoSkip: false,
                              maxRotation: 45,
                              minRotation: 45,
                              color: '#566573',
                              font: {
                                  size: 9,
                                  family: "'Poppins', sans-serif"
                              }
                         }
                     }
                 },
                 interaction: { mode: 'index', intersect: false }
             }
         };

         try {
             this.avgFundingBackerChartInstance = new Chart(ctx, chartConfig);
         } catch (error) {
              this.avgFundingBackerChartContainer.innerHTML = `<span class="chart-placeholder">Error rendering avg funding chart.</span>`;
              this.avgFundingBackerCanvas.style.display = 'none';
         }
    }

    updateQuaternaryTable() {
         const topFundedInfo = this.topFundedCampaignsData || { data: [], column_header: 'Category' };
         if (this.topFundedTableContainer) {
             this.renderTopFundedTable(topFundedInfo.data, topFundedInfo.column_header);
         }
    }

    renderTopFundedTable(data, columnHeader = 'Category') {
          if (!this.topFundedTableContainer) return;

          this.topFundedTableContainer.innerHTML = ''; 

          if (!data || data.length === 0) {
              const noDataPlaceholder = document.createElement('span');
              noDataPlaceholder.className = 'chart-placeholder';
              noDataPlaceholder.textContent = "No funded campaigns match the current filters.";
              this.topFundedTableContainer.appendChild(noDataPlaceholder);
              this.adjustHeight();
              return;
          }

          const headers = ['Project Name', 'Creator', 'Pledged', columnHeader, 'Country', 'Link'];
          const dataKeys = ['Project Name', 'Creator', 'Raw Pledged', 'Category', 'Country', 'Link'];

          let tableHTML = '<table><thead><tr>';
          headers.forEach(header => tableHTML += `<th>${header}</th>`);
          tableHTML += '</tr></thead><tbody>';

          data.forEach(row => {
              tableHTML += '<tr>';
              dataKeys.forEach((key, index) => {
                   let cellValue = row[key] !== null && row[key] !== undefined ? row[key] : 'N/A';
                   let cellContent = '';
                   let tdAttributes = '';

                   if (key === 'Raw Pledged') {
                        cellContent = formatCurrency(cellValue);
                        tdAttributes = 'class="pledged-cell"';
                   } else if (key === 'Link') {
                       if (cellValue !== 'N/A') {
                          const url = String(cellValue);
                           if (url.startsWith('http://') || url.startsWith('https://')) {
                               const escapedUrl = encodeURI(url);
                               const tempDiv = document.createElement('div');
                               tempDiv.textContent = url;
                               const escapedText = tempDiv.innerHTML;
                               cellContent = `<a href="${escapedUrl}" target="_blank" title="${escapedUrl}">${escapedText}</a>`;
                           } else {
                                cellContent = 'Invalid Link'; 
                           }
                       } else {
                            cellContent = 'N/A';
                       }
                   } else {
                        const tempDiv = document.createElement('div');
                        tempDiv.textContent = String(cellValue); 
                        cellContent = tempDiv.innerHTML;
                   }
                   tableHTML += `<td ${tdAttributes}>${cellContent}</td>`;
              });
              tableHTML += '</tr>';
          });

          tableHTML += '</tbody></table>';

          this.topFundedTableContainer.innerHTML = tableHTML;
          this.adjustHeight();
      }
}

let insightsDashboardInstance = null;

function onRender(event) {
    try {
        if (typeof Chart === 'undefined') {
            const root = document.getElementById('component-root');
            if (root) root.innerHTML = `<p style="color: red; padding: 20px;">Error: Charting library failed to load. Check if 'chart.js' exists in the project root and is valid.</p>`;
            Streamlit.setFrameHeight(100);
            return;
        }

        const data = event.detail.args.component_data;
        if (!data) { return; }

        if (!window.insightsDashboardInstance) {
            window.insightsDashboardInstance = new InsightsDashboard(data);
        } else {
            window.insightsDashboardInstance.updateUIState(data);
        }

        if (!window.insightsResizeObserver && document.getElementById('component-root')) {
             window.insightsResizeObserver = new ResizeObserver(debounce(() => {
                 if (window.insightsDashboardInstance) {
                     window.insightsDashboardInstance.adjustHeight();
                     if (window.insightsDashboardInstance.openDropdown) {
                        window.insightsDashboardInstance._positionDropdown(
                           window.insightsDashboardInstance.openDropdown.trigger,
                           window.insightsDashboardInstance.openDropdown.content
                        );
                     }
                 }
             }, 150));
             window.insightsResizeObserver.observe(document.getElementById('component-root'));
        }

    } catch (error) {
        const root = document.getElementById('component-root');
        if (root) root.innerHTML = `<p style="color: red; padding: 20px;">Error rendering component: ${error.message}. Check console.</p>`;
        Streamlit.setFrameHeight(100);
    }
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
"""

script = chartjs_script_content + "\n" + datalabels_plugin_content + "\n" + script_template

insights_component = generate_component(
    "campaign_insights_dashboard",
    template=css,
    script=script
)

def calculate_insights(lf: pl.LazyFrame, filters: dict, dataset_date: datetime.date):

    schema_names = lf.collect_schema().names()
    required_cols = ["Category", "State", "Raw Pledged", "Raw Goal"]
    optional_cols = {"Location": "Country", "Raw Backers": "Backer Count"}

    subcategory_needed = "Subcategory" in schema_names
    raw_deadline_needed = "Raw Deadline" in schema_names

    missing_essential_cols = [col for col in required_cols if col not in schema_names]
    if missing_essential_cols:
         st.error(f"Error: Missing required columns in the data: {', '.join(missing_essential_cols)}. Cannot calculate insights.")
         st.stop()

    location_col_name = optional_cols["Location"] if optional_cols["Location"] in schema_names else None
    backers_col_name = optional_cols["Raw Backers"] if optional_cols["Raw Backers"] in schema_names else None

    if not location_col_name:
        st.warning(f"Warning: Column '{optional_cols['Location']}' not found. 'Top Project Locations' chart will be empty.")
    if not backers_col_name:
        st.warning(f"Warning: Column '{optional_cols['Raw Backers']}' not found. 'Average Funding per Backer' chart will be empty.")

    categories = filters.get('categories', ['All Categories'])
    date_filter = filters.get('date', 'All Time')
    single_category_selected = len(categories) == 1 and categories[0] != 'All Categories'

    if categories != ['All Categories']:
        lf = lf.filter(pl.col('Category').is_in(categories))
        if single_category_selected and not subcategory_needed:
             st.warning("Warning: 'Subcategory' column not found. Cannot show trending subcategories for the selected category.")
             subcategory_needed = False

    current_start, current_end = None, None
    prev_start, prev_end = None, None
    is_all_time = date_filter == 'All Time'
    date_col_for_filtering = None
    current_lf_filtered = lf
    prev_lf_filtered = None

    if not is_all_time:
        if not raw_deadline_needed:
             st.error("Error: 'Raw Deadline' column not found. Cannot filter by specific date ranges.")
             st.stop()
        if 'Raw Deadline_dt' not in lf.collect_schema().names():
            lf = lf.with_columns(pl.from_epoch(pl.col("Raw Deadline"), time_unit="us").alias("Raw Deadline_dt"))
        date_col_for_filtering = 'Raw Deadline_dt'

        current_end_dt = datetime.datetime.combine(dataset_date, datetime.time.min)

        if date_filter == 'Last Month':
            current_start_dt = datetime.datetime.combine(dataset_date - relativedelta(months=1), datetime.time.min)
            prev_start_dt = datetime.datetime.combine(dataset_date - relativedelta(months=2), datetime.time.min)
            prev_end_dt = current_start_dt
        elif date_filter == 'Last 6 Months':
            current_start_dt = datetime.datetime.combine(dataset_date - relativedelta(months=6), datetime.time.min)
            prev_start_dt = datetime.datetime.combine(dataset_date - relativedelta(months=12), datetime.time.min)
            prev_end_dt = current_start_dt
        elif date_filter == 'Last Year':
            current_start_dt = datetime.datetime.combine(dataset_date - relativedelta(years=1), datetime.time.min)
            prev_start_dt = datetime.datetime.combine(dataset_date - relativedelta(years=2), datetime.time.min)
            prev_end_dt = current_start_dt
        else:
             is_all_time = True
             date_col_for_filtering = None

        if not is_all_time:
            current_start = current_start_dt
            current_end = current_end_dt
            prev_start = prev_start_dt
            prev_end = prev_end_dt

            current_lf_filtered = lf.filter(
                (pl.col(date_col_for_filtering) >= current_start) & (pl.col(date_col_for_filtering) < current_end)
            )
            prev_lf_filtered = lf.filter(
                (pl.col(date_col_for_filtering) >= prev_start) & (pl.col(date_col_for_filtering) < prev_end)
            )

    def get_grouped_metrics(period_lf: pl.LazyFrame, group_by_col: str | None = None) -> pl.DataFrame:
        """Calculates key metrics, optionally grouped by a column."""
        if period_lf is None:
            schema = {"total_campaigns": pl.UInt32, "total_pledged": pl.Float64, "successful_campaigns": pl.UInt32, "failed_campaigns": pl.UInt32, "success_rate": pl.Float64}
            if group_by_col: schema[group_by_col] = pl.Utf8
            return pl.DataFrame(schema=schema)

        try:
            period_schema = period_lf.collect_schema()
            state_lower_expr = pl.col("State").fill_null("").cast(pl.Utf8).str.to_lowercase()

            aggregations = [
                pl.len().alias("total_campaigns"),
                pl.sum("Raw Pledged").cast(pl.Float64).alias("total_pledged"),
                pl.when(state_lower_expr == "successful").then(pl.lit(1, dtype=pl.UInt32)).otherwise(pl.lit(0, dtype=pl.UInt32)).sum().alias("successful_campaigns"),
                pl.when(state_lower_expr == "failed").then(pl.lit(1, dtype=pl.UInt32)).otherwise(pl.lit(0, dtype=pl.UInt32)).sum().alias("failed_campaigns"),
            ]

            if group_by_col:
                if group_by_col not in period_schema.names():
                    schema = {group_by_col: pl.Utf8, "total_campaigns": pl.UInt32, "total_pledged": pl.Float64, "successful_campaigns": pl.UInt32, "failed_campaigns": pl.UInt32, "success_rate": pl.Float64}
                    return pl.DataFrame(schema=schema)

                grouped_lf = period_lf.filter(pl.col(group_by_col).is_not_null()).group_by(group_by_col).agg(aggregations)
            else:
                grouped_lf = period_lf.select(aggregations)

            results_df = grouped_lf.collect()
            if results_df.is_empty():
                 schema = {"total_campaigns": pl.UInt32, "total_pledged": pl.Float64, "successful_campaigns": pl.UInt32, "failed_campaigns": pl.UInt32}
                 if group_by_col: schema[group_by_col] = pl.Utf8
                 return pl.DataFrame(schema=schema)

            if not results_df.is_empty():
                 results_df = results_df.with_columns(
                      success_rate = pl.when((pl.col("successful_campaigns") + pl.col("failed_campaigns")) > 0)
                                     .then((pl.col("successful_campaigns") / (pl.col("successful_campaigns") + pl.col("failed_campaigns"))) * 100)
                                     .otherwise(None)
                 )
            return results_df

        except Exception as e:
            st.error(f"Error calculating metrics: {e}")
            schema = {"total_campaigns": pl.UInt32, "total_pledged": pl.Float64, "successful_campaigns": pl.UInt32, "failed_campaigns": pl.UInt32, "success_rate": pl.Float64}
            if group_by_col: schema[group_by_col] = pl.Utf8
            return pl.DataFrame(schema=schema)

    current_overall_metrics_df = get_grouped_metrics(current_lf_filtered)
    if not is_all_time:
        prev_overall_metrics_df = get_grouped_metrics(prev_lf_filtered)
    else:
        schema = {"total_campaigns": pl.UInt32, "total_pledged": pl.Float64, "successful_campaigns": pl.UInt32, "failed_campaigns": pl.UInt32}
        prev_overall_metrics_df = pl.DataFrame(schema=schema)

    current_data = current_overall_metrics_df.to_dicts()[0] if not current_overall_metrics_df.is_empty() else {"total_campaigns": 0, "total_pledged": None, "successful_campaigns": 0, "failed_campaigns": 0}
    prev_data = prev_overall_metrics_df.to_dicts()[0] if not prev_overall_metrics_df.is_empty() else {"total_campaigns": 0, "total_pledged": None, "successful_campaigns": 0, "failed_campaigns": 0}

    results = {}
    def calc_change(current, previous):
        if current is None or previous is None: return None
        try:
            current_f = float(current); previous_f = float(previous)
            if previous_f == 0:
                 return 0.0 if current_f == 0 else None
            if abs(previous_f) < 1e-9: return None
            change = ((current_f - previous_f) / previous_f) * 100
            return change
        except (TypeError, ValueError): return None

    results["total_campaigns"] = {
        "current": current_data.get("total_campaigns", 0),
        "previous": prev_data.get("total_campaigns", 0),
        "change_pct": calc_change(current_data.get("total_campaigns"), prev_data.get("total_campaigns")) if not is_all_time else None
    }
    results["total_pledged"] = {
        "current": current_data.get("total_pledged"),
        "previous": prev_data.get("total_pledged"),
        "change_pct": calc_change(current_data.get("total_pledged"), prev_data.get("total_pledged")) if not is_all_time else None
    }
    results["successful_campaigns"] = {
        "current": current_data.get("successful_campaigns", 0),
        "previous": prev_data.get("successful_campaigns", 0),
        "change_pct": calc_change(current_data.get("successful_campaigns"), prev_data.get("successful_campaigns")) if not is_all_time else None
    }

    current_success = results["successful_campaigns"]["current"]
    current_total = results["total_campaigns"]["current"]
    prev_success = results["successful_campaigns"]["previous"]
    prev_total = results["total_campaigns"]["previous"]

    current_rate = None
    prev_rate = None
    rate_change = None

    current_denominator = current_total
    if current_denominator is not None and current_denominator > 0:
        current_rate = (current_success / current_denominator) * 100

    if not is_all_time:
        prev_denominator = prev_total
        if prev_denominator is not None and prev_denominator > 0:
            prev_rate = (prev_success / prev_denominator) * 100

        if current_rate is not None and prev_rate is not None:
             rate_change = current_rate - prev_rate
        elif current_rate is not None and prev_denominator == 0:
             rate_change = None
        elif current_rate is not None and prev_rate is None and prev_denominator is not None and prev_denominator > 0:
             rate_change = None

    results["success_rate"] = {
        "current": current_rate,
        "previous": prev_rate,
        "change_pct": rate_change
    }

    goal_distribution = []
    try:
        bins = [0, 1000, 10000, 100000, 1000000]
        labels = ["<$1k", "$1k-$10k", "$10k-$100k", "$100k-$1m", ">$1m"]
        last_finite_bin = bins[-1]

        goal_lf = current_lf_filtered

        if goal_lf is None:
             goal_distribution = [{"bin": label, "count": 0} for label in labels]
        else:
            goal_bin_expr = (
                pl.when(pl.col("Raw Goal") < bins[1]).then(pl.lit(labels[0]))
                .when(pl.col("Raw Goal") < bins[2]).then(pl.lit(labels[1]))
                .when(pl.col("Raw Goal") < bins[3]).then(pl.lit(labels[2]))
                .when(pl.col("Raw Goal") < bins[4]).then(pl.lit(labels[3]))
                .when(pl.col("Raw Goal") >= last_finite_bin).then(pl.lit(labels[4]))
                .otherwise(None)
            ).alias("goal_bin")

            intermediate_lf = goal_lf.filter(
                    pl.col("Raw Goal").is_not_null() & (pl.col("Raw Goal") > 0)
                ).with_columns(goal_bin_expr).filter(pl.col("goal_bin").is_not_null())

            goal_dist_df = (
                intermediate_lf
                .group_by("goal_bin")
                .agg(pl.len().alias("count"))
                .with_columns(pl.col('goal_bin').cast(pl.Enum(categories=labels)))
                .sort("goal_bin")
                .collect()
            )

            if goal_dist_df.is_empty():
                 goal_distribution = [{"bin": label, "count": 0} for label in labels]
            else:
                 goal_map = {row['goal_bin']: row['count'] for row in goal_dist_df.to_dicts()}
                 goal_distribution = [{"bin": label, "count": goal_map.get(label, 0)} for label in labels]

    except Exception as e:
        goal_distribution = [{"bin": label, "count": 0} for label in labels]

    trending_payload = {"type": "category", "mode": "value", "data": {}}
    try:
        group_col = None
        group_type = "category"
        selected_main_category_name = categories[0] if single_category_selected else None

        if is_all_time:
            trending_payload["mode"] = "value"
            if categories == ['All Categories']:
                group_col = "Category"
                group_type = "category"
            elif single_category_selected and subcategory_needed:
                group_col = "Subcategory"
                group_type = "subcategory"
            else:
                group_col = "Category"
                group_type = "category"
        else:
            trending_payload["mode"] = "change"
            if single_category_selected and subcategory_needed:
                group_col = "Subcategory"
                group_type = "subcategory"
            else:
                group_col = "Category"
                group_type = "category"

        trending_payload["type"] = group_type

        if group_col:
            current_grouped_df = get_grouped_metrics(current_lf_filtered, group_col)

            if group_type == "subcategory" and selected_main_category_name:
                if not current_grouped_df.is_empty():
                    current_grouped_df = current_grouped_df.filter(pl.col(group_col) != selected_main_category_name)

            if not is_all_time:
                trending_payload["mode"] = "change"
                trending_data_for_js = {}
                metrics_to_calculate = ["total_campaigns", "total_pledged", "successful_campaigns", "success_rate"]
                for metric in metrics_to_calculate:
                     trending_data_for_js[metric] = []

                if prev_lf_filtered is None:
                     prev_grouped_df = pl.DataFrame(schema={group_col: pl.Utf8, **{m: pl.Float64 for m in metrics_to_calculate}})
                else:
                    prev_grouped_df = get_grouped_metrics(prev_lf_filtered, group_col)
                    if group_type == "subcategory" and selected_main_category_name:
                        if not prev_grouped_df.is_empty():
                            prev_grouped_df = prev_grouped_df.filter(pl.col(group_col) != selected_main_category_name)

                current_lookup = {row[group_col]: row for row in current_grouped_df.iter_rows(named=True)}
                prev_lookup = {row[group_col]: row for row in prev_grouped_df.iter_rows(named=True)}
                all_group_keys = set(current_lookup.keys()) | set(prev_lookup.keys())

                for key in all_group_keys:
                    if group_type == "subcategory" and key == selected_main_category_name:
                        continue

                    current_row = current_lookup.get(key, {})
                    prev_row = prev_lookup.get(key, {})

                    current_vals = {m: current_row.get(m) for m in metrics_to_calculate}
                    prev_vals = {m: prev_row.get(m) for m in metrics_to_calculate}

                    tc_change = calc_change(current_vals.get("total_campaigns"), prev_vals.get("total_campaigns"))
                    if tc_change is not None:
                         trending_data_for_js["total_campaigns"].append({"name": key, "value": tc_change})

                    tp_change = calc_change(current_vals.get("total_pledged"), prev_vals.get("total_pledged"))
                    if tp_change is not None:
                         trending_data_for_js["total_pledged"].append({"name": key, "value": tp_change})

                    sc_change = calc_change(current_vals.get("successful_campaigns"), prev_vals.get("successful_campaigns"))
                    if sc_change is not None:
                         trending_data_for_js["successful_campaigns"].append({"name": key, "value": sc_change})

                    sr_current = current_vals.get("success_rate")
                    sr_prev = prev_vals.get("success_rate")
                    sr_change = None
                    if sr_current is not None and sr_prev is not None:
                         try:
                             sr_change = float(sr_current) - float(sr_prev)
                         except (TypeError, ValueError):
                             sr_change = None
                    if sr_change is not None:
                         trending_data_for_js["success_rate"].append({"name": key, "value": sr_change})

                trending_payload["data"] = trending_data_for_js

            else:
                 trending_payload["mode"] = "value"
                 trending_data_for_js = {}
                 value_metrics = ["total_campaigns", "total_pledged", "successful_campaigns", "success_rate"]

                 if categories == ['All Categories'] and group_type == "category":
                     valid_main_categories = [cat for cat in filter_options.get('categories', []) if cat != 'All Categories']

                     if not current_grouped_df.is_empty() and valid_main_categories:
                         current_grouped_df = current_grouped_df.filter(pl.col(group_col).is_in(valid_main_categories))

                 if not current_grouped_df.is_empty():
                      for metric_key in value_metrics:
                           filtered_df = current_grouped_df.filter(
                                pl.col(group_col).is_not_null() & pl.col(metric_key).is_not_null()
                           )
                           trending_data_for_js[metric_key] = [
                                {"name": row[group_col], "value": row[metric_key]}
                                for row in filtered_df.select(group_col, metric_key).iter_rows(named=True)
                                if not (group_type == "subcategory" and row[group_col] == selected_main_category_name)
                           ]
                 else:
                      for metric_key in value_metrics: trending_data_for_js[metric_key] = []

                 trending_payload["data"] = trending_data_for_js

    except Exception as e:
        pass

    top_locations = []
    if location_col_name and current_lf_filtered is not None:
        try:
            locations_df = (
                current_lf_filtered
                .filter(pl.col(location_col_name).is_not_null() & (pl.col(location_col_name) != ""))
                .group_by(location_col_name)
                .agg(pl.len().alias("count"))
                .sort("count", descending=True)
                .head(5)
                .collect()
            )
            if not locations_df.is_empty():
                top_locations = locations_df.rename({location_col_name: "location"}).to_dicts()

        except Exception as e:
            top_locations = []

    avg_funding_per_backer_payload = {"type": "category", "data": []}
    if backers_col_name and current_lf_filtered is not None:
        try:
            funding_group_col = None
            funding_group_type = "category"
            if categories == ['All Categories']:
                funding_group_col = "Category"
                funding_group_type = "category"
            elif single_category_selected and subcategory_needed:
                funding_group_col = "Subcategory"
                funding_group_type = "subcategory"
            else:
                funding_group_col = "Category"
                funding_group_type = "category"

            avg_funding_per_backer_payload["type"] = funding_group_type

            if funding_group_col:
                avg_funding_lf = (
                    current_lf_filtered
                    .filter(
                        pl.col(backers_col_name).is_not_null() & (pl.col(backers_col_name) > 0) &
                        pl.col(funding_group_col).is_not_null() & (pl.col(funding_group_col) != "") &
                        pl.col("Raw Pledged").is_not_null()
                    )
                    .group_by(funding_group_col)
                    .agg(
                        pl.sum("Raw Pledged").cast(pl.Float64).alias("total_pledged"),
                        pl.sum(backers_col_name).cast(pl.Float64).alias("total_backers")
                    )
                    .filter(pl.col("total_backers") > 0)
                    .with_columns(
                        (pl.col("total_pledged") / pl.col("total_backers")).alias("avg_funding_per_backer")
                    )
                    .select(funding_group_col, "avg_funding_per_backer")
                )

                if funding_group_type == "subcategory" and selected_main_category_name:
                     avg_funding_lf = avg_funding_lf.filter(pl.col(funding_group_col) != selected_main_category_name)

                if categories == ['All Categories'] and funding_group_type == "category":
                     valid_main_categories = [cat for cat in filter_options.get('categories', []) if cat != 'All Categories']
                     if valid_main_categories:
                         avg_funding_lf = avg_funding_lf.filter(pl.col(funding_group_col).is_in(valid_main_categories))

                funding_df = avg_funding_lf.sort(funding_group_col).collect()

                if not funding_df.is_empty():
                     avg_funding_per_backer_payload["data"] = funding_df.rename({
                         funding_group_col: "name",
                         "avg_funding_per_backer": "value"
                     }).to_dicts()

        except Exception as e:
            avg_funding_per_backer_payload = {"type": "category", "data": []}

    top_funded_campaigns = []
    top_funded_column_header = 'Category' 
    if 'Raw Date' in schema_names and 'Raw Deadline' in schema_names and 'Raw Pledged' in schema_names:
        try:
            funded_lf = lf
            subcategory_exists = 'Subcategory' in funded_lf.collect_schema().names()
            use_subcategory = single_category_selected and subcategory_exists

            if not is_all_time and current_start and current_end:
                if 'Raw Date_dt' not in funded_lf.collect_schema().names():
                    funded_lf = funded_lf.with_columns(
                        pl.col("Raw Date").cast(pl.Datetime, strict=False).alias("Raw Date_dt")
                    )
                if 'Raw Deadline_dt' not in funded_lf.collect_schema().names():
                    funded_lf = funded_lf.with_columns(
                         pl.from_epoch(pl.col("Raw Deadline"), time_unit="us").alias("Raw Deadline_dt")
                    )

                funded_lf = funded_lf.filter(
                    (
                        (pl.col('Raw Date_dt') >= current_start) & (pl.col('Raw Date_dt') < current_end)
                    ) | (
                        (pl.col('Raw Deadline_dt') >= current_start) & (pl.col('Raw Deadline_dt') < current_end)
                    )
                )

            category_source_col = "Subcategory" if use_subcategory else "Category"
            top_funded_column_header = "Subcategory" if use_subcategory else "Category"

            required_display_cols = ['Project Name', 'Creator', 'Raw Pledged', category_source_col, 'Country', 'Link']
            existing_display_cols = [col for col in required_display_cols if col in funded_lf.collect_schema().names()]

            if category_source_col not in existing_display_cols:
                 st.warning(f"Warning: Required column '{category_source_col}' not found for top funded table.")
                 if use_subcategory and 'Category' in funded_lf.collect_schema().names():
                      category_source_col = "Category"
                      top_funded_column_header = "Category"
                      if category_source_col not in existing_display_cols: 
                          existing_display_cols.insert(3, category_source_col) 
                 else: 
                      existing_display_cols = [col for col in existing_display_cols if col != category_source_col]

            if 'Raw Pledged' in existing_display_cols and 'Project Name' in existing_display_cols: 
                select_cols_for_top_funded = existing_display_cols

                top_funded_df = (
                    funded_lf
                    .filter(pl.col('Raw Pledged').is_not_null())
                    .sort("Raw Pledged", descending=True)
                    .head(5)
                    .select(select_cols_for_top_funded)
                    .collect()
                )

                if use_subcategory and category_source_col == "Subcategory" and "Subcategory" in top_funded_df.columns:
                     if 'Category' not in top_funded_df.columns:
                         top_funded_df = top_funded_df.rename({"Subcategory": "Category"})
                     else:
                          top_funded_df = top_funded_df.drop("Subcategory")
                          top_funded_column_header = "Category" 

                if not top_funded_df.is_empty():
                    if 'Category' not in top_funded_df.columns and top_funded_column_header == 'Category':
                         top_funded_df = top_funded_df.with_columns(pl.lit(None).alias('Category'))

                    final_columns = ['Project Name', 'Creator', 'Raw Pledged', 'Category', 'Country', 'Link']
                    dict_list = []
                    for row in top_funded_df.iter_rows(named=True):
                        row_dict = {}
                        for col in final_columns:
                            row_dict[col] = row.get(col)
                        dict_list.append(row_dict)
                    top_funded_campaigns = dict_list

        except Exception as e:
            top_funded_campaigns = []
            top_funded_column_header = 'Category' 

    final_results = {
        "metrics": results,
        "goal_distribution": goal_distribution,
        "trending_data": trending_payload,
        "top_locations": top_locations,
        "avg_funding_per_backer": avg_funding_per_backer_payload,
        "top_funded_campaigns": {
             "data": top_funded_campaigns,
             "column_header": top_funded_column_header
        }
    }

    return final_results

component_state_from_last_run = st.session_state.get("insights_component_value", None)
state_sent_last_run = st.session_state.get('insights_state_sent_to_component', DEFAULT_INSIGHTS_FILTERS)

component_sent_new_state = False
if component_state_from_last_run is not None:
    try:
        if isinstance(component_state_from_last_run, dict) and 'filters' in component_state_from_last_run:
             last_run_str = json.dumps(component_state_from_last_run.get('filters'), sort_keys=True)
             sent_last_run_str = json.dumps(state_sent_last_run, sort_keys=True)
             if last_run_str != sent_last_run_str:
                 component_sent_new_state = True
    except TypeError as e:
         component_sent_new_state = True

if component_sent_new_state:
     if isinstance(component_state_from_last_run, dict) and 'filters' in component_state_from_last_run:
        new_filters_raw = component_state_from_last_run['filters']
        validated_filters = DEFAULT_INSIGHTS_FILTERS.copy()
        if isinstance(new_filters_raw.get('categories'), list):
            valid_cats = [cat for cat in new_filters_raw['categories'] if cat in filter_options['categories']]
            if not valid_cats:
                 validated_filters['categories'] = ['All Categories']
            else:
                 if 'All Categories' in valid_cats and len(valid_cats) > 1:
                     validated_filters['categories'] = [cat for cat in valid_cats if cat != 'All Categories']
                 elif not valid_cats:
                      validated_filters['categories'] = ['All Categories']
                 else:
                      validated_filters['categories'] = valid_cats
        if new_filters_raw.get('date') in filter_options['date_ranges']:
            validated_filters['date'] = new_filters_raw['date']

        st.session_state.insights_filters = validated_filters

if 'base_lf' in st.session_state and 'dataset_creation_date' in st.session_state:
    calculated_data = {}
    try:
        calculated_data = calculate_insights(
            st.session_state.base_lf,
            st.session_state.insights_filters,
            st.session_state.dataset_creation_date
        )
        calculated_metrics = calculated_data.get("metrics", {})
        goal_distribution_data = calculated_data.get("goal_distribution", [])
        trending_data_payload = calculated_data.get("trending_data", {"items": []})

    except Exception as e:
        st.error(f"Error calculating insights: {e}")
        calculated_metrics = {}
        goal_distribution_data = []
        trending_data_payload = {"type": "category", "mode": "value", "data": {}}
        calculated_data = {
             "metrics": {},
             "goal_distribution": [],
             "trending_data": {"type": "category", "mode": "value", "data": {}},
             "top_locations": [],
             "avg_funding_per_backer": {"type": "category", "data": []},
             "top_funded_campaigns": {"data": [], "column_header": "Category"}
        }


else:
    st.warning("Base data or dataset date not available.")
    calculated_metrics = {}
    goal_distribution_data = []
    trending_data_payload = {"type": "category", "mode": "value", "data": {}}
    calculated_data = {
         "metrics": {},
         "goal_distribution": [],
         "trending_data": {"type": "category", "mode": "value", "data": {}},
         "top_locations": [],
         "avg_funding_per_backer": {"type": "category", "data": []},
         "top_funded_campaigns": {"data": [], "column_header": "Category"}
    }

state_being_sent_this_run = st.session_state.insights_filters.copy()
st.session_state.insights_state_sent_to_component = state_being_sent_this_run

component_data_payload = {
    "filters": st.session_state.insights_filters,
    "filter_options": filter_options,
    "metrics": calculated_metrics,
    "goal_distribution": goal_distribution_data,
    "trending_data": trending_data_payload,
    "top_locations": calculated_data.get("top_locations", []),
    "avg_funding_per_backer": calculated_data.get("avg_funding_per_backer", {"type": "category", "data": []}),
    "top_funded_campaigns": calculated_data.get("top_funded_campaigns", {"data": [], "column_header": "Category"}) 
}

component_return_value = insights_component(
    component_data=component_data_payload,
    key="insights_state",
    default=None
)

needs_rerun = False
if component_return_value is not None:
    if (isinstance(component_return_value, dict) and 'filters' in component_return_value):
        try:
            received_state_str = json.dumps(component_return_value['filters'], sort_keys=True)
            sent_state_str = json.dumps(state_being_sent_this_run, sort_keys=True)

            if received_state_str != sent_state_str:
                new_filters_raw = component_return_value['filters']
                validated_filters = DEFAULT_INSIGHTS_FILTERS.copy()
                if isinstance(new_filters_raw.get('categories'), list):
                    valid_cats = [cat for cat in new_filters_raw['categories'] if cat in filter_options['categories']]
                    if not valid_cats: validated_filters['categories'] = ['All Categories']
                    else:
                         if 'All Categories' in valid_cats and len(valid_cats) > 1:
                            validated_filters['categories'] = [cat for cat in valid_cats if cat != 'All Categories']
                         elif not valid_cats: validated_filters['categories'] = ['All Categories']
                         else: validated_filters['categories'] = valid_cats
                if new_filters_raw.get('date') in filter_options['date_ranges']: validated_filters['date'] = new_filters_raw['date']

                if json.dumps(validated_filters, sort_keys=True) != json.dumps(st.session_state.insights_filters, sort_keys=True):
                    st.session_state.insights_filters = validated_filters
                    needs_rerun = True

        except Exception as e:
            pass

st.session_state.insights_component_value = component_return_value

if needs_rerun:
    st.rerun()