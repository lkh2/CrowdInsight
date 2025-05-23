# CrowdInsight

CrowdInsight is a robust web application designed with three primary objectives in mind: to gather and preprocess data from crowdfunding platforms, to predict the success rates of projects using advanced machine learning models, and to offer users a dynamic and intuitive interface for project exploration and improvement.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://crowdinsight.streamlit.app)

## Project Structure

This repository contains the prototype for the CrowdInsight Streamlit application. Key files and directories include:

- **`Data_Explorer.py`**: The main entry point and homepage of the Streamlit application.
- **`pages/`**: This directory contains the Python scripts for the subsequent pages of the application.
  - Files are named using a convention like `[number]_[Tab Name].py`.
  - The `[number]` prefix determines the order in which the pages appear in the sidebar navigation.
  - The `[Tab Name]` part of the filename is used as the title for the page in the navigation.
- **`explainer.py`**: Contains code related to explaining model predictions (likely used by one of the pages).
- **`component_generation.py`**: Utility functions for generating Streamlit components.
- **`Kickstarter_2025-04-10T03_20_09_833Z.parquet`**: The main dataset used by the application in Parquet format.
- **`filter_metadata.json`**: Contains metadata used for filtering options within the application (e.g., dropdown lists, slider ranges).
- **`chart.js` & `chartjs-plugin-datalabels.js`**: JavaScript libraries used for rendering interactive charts in the frontend.
- **`requirements.txt`**: Lists the Python dependencies required to run the application.
- **`.gitignore`**, **`LICENSE`**, **`README.md`**: Standard repository files.

## Data Sources

- The primary dataset (`Kickstarter_...parquet`) and the filter metadata (`filter_metadata.json`) are generated by an addition [repository](https://github.com/lkh2/WebRobots-Download).
- This process takes a local folder containing previously scraped `json.gz` dataset files as input and outputs the `.parquet` and `.json` files found in this repository.

## Frontend Dependencies

- The charting capabilities rely on `Chart.js` and the `chartjs-plugin-datalabels` plugin. These JavaScript files are included directly in the repository but were originally obtained from their respective official sources online.

## How to run it on your own machine

1.  **Install the requirements:**
    Ensure you have Python and pip installed. Then, install the necessary libraries:

    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the app:**
    Navigate to the repository's root directory in your terminal and run the main Streamlit script:

    ```bash
    streamlit run Data_Explorer.py
    ```

    This will start the Streamlit server, and the application should open in your default web browser.
