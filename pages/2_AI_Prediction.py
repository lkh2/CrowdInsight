import streamlit as st
import os
import json
import sys
import requests

current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from component_generation import generate_component
from explainer import CampaignExplainerV2

if 'prediction_result_available' not in st.session_state:
    st.session_state.prediction_result_available = False
if 'predicted_success_rate' not in st.session_state:
    st.session_state.predicted_success_rate = None
if 'prediction_explanation' not in st.session_state:
    st.session_state.prediction_explanation = "No explanation generated yet."
if 'raw_llm_explanation' not in st.session_state:
    st.session_state.raw_llm_explanation = None
if 'api_response_data' not in st.session_state:
    st.session_state.api_response_data = None

st.set_page_config(
    layout="wide",
    page_icon="💡",
    page_title="AI Prediction",
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

        .st-key-make_another_prediction {
            margin: 0 auto;
            padding-bottom: 40px;
        }

        button[data-testid="stBaseButton-primary"] {
            padding: 12px 45px !important;
            background: linear-gradient(90deg, #5cb85c 0%, #65c3a1 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            font-family: 'Poppins', sans-serif !important;
            font-size: 16px !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 4px 15px rgba(101, 195, 161, 0.3) !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
        }

        .prediction-result-container {
            box-sizing: border-box;
            transition: opacity 0.3s ease-in-out;
            opacity: 0; 
            padding: 30px 40px; 
            max-width: 900px; 
            margin: 40px auto; 
        }

        .prediction-result-container.loaded {
            opacity: 1; 
        }

        .prediction-result-content {
            text-align: center;
            color: #f0f0f0;
        }

        .success-rate-label {
            font-size: 18px;
            font-weight: 500;
            color: #cccccc;
            margin-bottom: 10px;
        }

        .success-rate-value {
            font-family: 'Playfair Display', serif;
            font-size: 64px;
            font-weight: 600;
            color: #65c3a1; 
            margin-bottom: 75px;
            line-height: 1.1;
        }

        .ai-suggestions {
            font-size: 15px;
            line-height: 1.7;
            color: #ffffff;
            text-align: left;
            margin-bottom: 35px;
            white-space: normal; 
        }

        .ai-suggestions div[data-testid="stHeadingWithActionElements"] h2 {
            font-family: 'Playfair Display', serif !important;
            color: #ffffff !important;
            font-size: 24px !important;
            font-weight: 600 !important;
            margin-top: 35px !important;
            margin-bottom: 20px !important;
            padding-bottom: 10px !important;
            border-bottom: 2px solid #65c3a1 !important;
            text-align: left !important;
            border-top: none !important;
            padding-top: 0 !important;
        }

        .ai-suggestions div[data-testid="stHeadingWithActionElements"] h3 {
            font-family: 'Poppins', sans-serif !important;
            color: #e8e8e8 !important;
            font-size: 18px !important;
            font-weight: 600 !important;
            margin-top: 30px !important;
            margin-bottom: 12px !important;
            text-align: left !important;
            border: none !important;
            padding: 0 !important;
        }

        .ai-suggestions div[data-testid="stHeadingWithActionElements"]:first-of-type h2 {
            margin-top: 5px !important;
        }

        .ai-suggestions p {
            margin-bottom: 18px;
            text-align: left;
            line-height: 1.7;
            color: #ffffff;
        }

        .ai-suggestions table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            margin-bottom: 25px;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 3px 8px rgba(0, 0, 0, 0.15);
            color: #333333;
        }

        .ai-suggestions th,
        .ai-suggestions td {
            padding: 12px 18px;
            text-align: left;
            border-bottom: 1px solid #eeeeee;
            font-size: 14px;
            vertical-align: middle;
            color: #333333;
        }

        .ai-suggestions thead th {
            background-color: #f8f9fa;
            color: #212529;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #dee2e6;
        }

        .ai-suggestions tbody tr:last-child th,
        .ai-suggestions tbody tr:last-child td {
            border-bottom: none;
        }

        .ai-suggestions tbody tr:hover {
            background-color: #f1f1f1;
        }

        .ai-suggestions ul {
            list-style-type: none; 
            padding-left: 10px; 
            margin-top: 15px;
            margin-bottom: 25px;
        }

        .ai-suggestions li {
            margin-bottom: 12px;
            padding-left: 25px; 
            position: relative; 
            line-height: 1.6;
            color: #ffffff;
        }

        .ai-suggestions li::before { 
            content: '•';
            color: #65c3a1; 
            font-size: 18px;
            position: absolute;
            left: 0;
            top: 0px; 
            line-height: 1;
        }

        .ai-suggestions strong {
            color: #ffffff;
            font-weight: 700;
            border-bottom: 1.5px solid rgba(255, 255, 255, 0.7);
            padding-bottom: 1px;
        }

        .ai-suggestions div[data-testid="stHeadingWithActionElements"] a {
            display: none; 
        }

        .stSpinner {
            justify-self: center !important; 
            color: white !important;      
            margin-top: 10px; 
        }

        @media (max-width: 768px) {
            .prediction-result-container { padding: 25px 30px; margin: 30px auto; }
            .success-rate-value { font-size: 56px; }
            .ai-suggestions { font-size: 14px; }
            .ai-suggestions div[data-testid="stHeadingWithActionElements"] h2 { font-size: 22px !important; margin-bottom: 15px !important; }
            .ai-suggestions div[data-testid="stHeadingWithActionElements"] h3 { font-size: 17px !important; }
            .ai-suggestions th, .ai-suggestions td { padding: 10px 12px; font-size: 13px; }
            .ai-suggestions li { padding-left: 20px; margin-bottom: 10px; }
            .ai-suggestions li::before { font-size: 16px; }
        }
         @media (max-width: 480px) {
             .prediction-result-container { padding: 20px; margin: 20px auto;}
             .success-rate-value { font-size: 48px; }
             .ai-suggestions { font-size: 13px; }
             .ai-suggestions div[data-testid="stHeadingWithActionElements"] h2 { font-size: 20px !important; }
             .ai-suggestions div[data-testid="stHeadingWithActionElements"] h3 { font-size: 16px !important; }
             .ai-suggestions th, .ai-suggestions td { padding: 8px 10px; font-size: 12px; }
             .ai-suggestions li { padding-left: 18px; }
             .ai-suggestions li::before { font-size: 15px; }
         }

    </style>
    """,
    unsafe_allow_html=True
)

filter_metadata_path = "filter_metadata.json"
if not os.path.exists(filter_metadata_path):
    st.error(f"Filter metadata file not found at '{filter_metadata_path}'. Please run `database_download.py` first.")
    st.stop()

try:
    with open(filter_metadata_path, 'r', encoding='utf-8') as f:
        filter_metadata = json.load(f)
    category_options = [cat for cat in filter_metadata.get('categories', []) if cat != 'All Categories']
    subcategory_map = filter_metadata.get('category_subcategory_map', {})
    country_options = [country for country in filter_metadata.get('countries', []) if country != 'All Countries']
    for cat, subs in subcategory_map.items():
        if cat in subcategory_map:
             subcategory_map[cat] = [sub for sub in subs if sub != 'All Subcategories']

except Exception as e:
    st.error(f"Error loading filter metadata from '{filter_metadata_path}': {e}. Cannot create form.")
    st.stop()

css = """
<style>
    body {
        font-family: 'Poppins', sans-serif;
        margin: 0;
        padding: 10px;
        box-sizing: border-box;
        background-color: transparent;
        color: #e0e0e0;
    }

    #prediction-form-root {
        box-sizing: border-box;
        transition: opacity 0.3s ease-in-out;
        opacity: 0; 
    }


    #prediction-form-root.loaded {
        opacity: 1; 
    }

    .component-header {
        color: white;
        font-family: 'Playfair Display';
        font-weight: 500;
        font-size: 70px;
        margin-bottom: 25px;
        text-align: center;
    }

    .component-subheader {
        font-family: 'Playfair Display';
        font-size: 24px;
        color: white;
        white-space: nowrap;
        margin-bottom: 45px;
        text-align: center;
        line-height: 1.6;
        overflow-x: auto;
        -ms-overflow-style: none;
        overflow: -moz-scrollbars-none;
        scrollbar-width: none;
    }
    .component-subheader::-webkit-scrollbar { display: none; } /* Hide scrollbar for Chrome/Safari */

    .form-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 25px 35px;
        margin-bottom: 35px;
    }

    .form-field {
        display: flex;
        flex-direction: column;
    }
    .form-field.full-width {
        grid-column: 1 / -1;
    }

    .form-label {
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
        font-size: 16px;
        white-space: nowrap;
        color: #f0f0f0;
        margin-bottom: 8px;
        display: block;
    }

    .form-input,
    .form-textarea,
    .form-select-btn,
    .form-number-input {
        width: 100%;
        padding: 12px 18px;
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 8px;
        background-color: white; 
        color: black;
        font-family: 'Poppins', sans-serif;
        font-size: 14px;
        box-sizing: border-box;
        transition: border-color 0.3s ease, box-shadow 0.3s ease;
    }

    .form-input::placeholder,
    .form-textarea::placeholder {
        color: #a0a0a0;
        opacity: 0.8;
    }

    .form-input:focus,
    .form-textarea:focus,
    .form-select-btn:focus,
    .form-number-input:focus {
        outline: none;
        border-color: #65c3a1;
        box-shadow: 0 0 0 3px rgba(101, 195, 161, 0.3);
    }

    .form-textarea {
        min-height: 120px;
        resize: vertical;
    }

    .custom-select-container {
        position: relative;
        width: 100%;
    }

    .form-select-btn {
        text-align: left;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .form-select-btn::after {
        content: '▼';
        font-size: 10px;
        margin-left: 10px;
        opacity: 0.7;
        transition: transform 0.2s ease-in-out;
    }

    .form-select-btn.open::after {
        transform: rotate(180deg);
    }

    .form-select-btn:disabled {
        background-color: #eee; 
        cursor: not-allowed;
        opacity: 0.7;
    }

    .select-options-list {
        display: none;
        position: absolute;
        background-color: #2c3e50;
        min-width: 100%;
        box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.4);
        padding: 8px 0;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        z-index: 1050;
        max-height: 250px;
        overflow-y: auto;
        margin-top: 4px;
        font-size: 13px;
    }

    .select-options-list::-webkit-scrollbar { width: 6px; }
    .select-options-list::-webkit-scrollbar-track { background: #445566; border-radius: 10px;}
    .select-options-list::-webkit-scrollbar-thumb { background: #778899; border-radius: 10px;}
    .select-options-list::-webkit-scrollbar-thumb:hover { background: #99aabb; }

    .select-option {
        padding: 10px 15px;
        cursor: pointer;
        transition: background-color 0.2s ease, color 0.2s ease;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: #e0e0e0;
    }

    .select-option:hover { background-color: #65c3a1; color: white; }
    .select-option.selected { background-color: #4a9a7a; color: white; font-weight: 500; }
    .select-option.disabled {
        color: #888;
        cursor: not-allowed;
        background-color: transparent;
    }

    .radio-group {
        display: flex;
        gap: 20px;
        margin-top: 8px;
    }
    .radio-option {
        display: flex;
        align-items: center;
        cursor: pointer;
    }
    .radio-option input[type="radio"] { display: none; } 
    .radio-custom { 
        width: 18px; height: 18px;
        border: 2px solid rgba(255, 255, 255, 0.5);
        border-radius: 50%;
        margin-right: 8px;
        display: inline-block;
        position: relative;
        transition: border-color 0.3s ease;
    }
    .radio-option input[type="radio"]:checked + .radio-custom { border-color: #65c3a1; }
    .radio-option input[type="radio"]:checked + .radio-custom::after { 
        content: '';
        position: absolute;
        top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        width: 10px; height: 10px;
        background-color: #65c3a1;
        border-radius: 50%;
    }
    .radio-label {
        font-size: 14px;
        color: #e0e0e0;
    }

    .conditional-fields {
        grid-column: 1 / -1;
        border-top: 1px solid rgba(255, 255, 255, 0.2);
        margin-top: 15px;
        padding-top: 25px;
        display: none; 
        grid-template-columns: 1fr 1fr; 
        gap: 25px 35px; 
    }

    .conditional-fields.visible { display: grid; }

    .submit-button-container {
        grid-column: 1 / -1;
        display: flex;
        justify-content: center;
        margin-top: 35px;
    }
    
    .submit-button, .action-button {
        margin-top: 25px;
        padding: 12px 45px;
        background: linear-gradient(90deg, #5cb85c 0%, #65c3a1 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-family: 'Poppins', sans-serif;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(101, 195, 161, 0.3);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .submit-button:hover, .action-button:hover {
        opacity: 0.9;
        box-shadow: 0 6px 20px rgba(101, 195, 161, 0.4);
    }

    .submit-button:active, .action-button:active {
        transform: translateY(1px);
        box-shadow: 0 2px 10px rgba(101, 195, 161, 0.3);
    }

    .submit-button:disabled {
        background: #777;
        cursor: not-allowed;
        opacity: 0.6;
        box-shadow: none;
    }

    .spinner-overlay {
        position: absolute; 
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0, 0, 0, 0.6); 
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1100; 
        border-radius: 16px; 
        opacity: 0; visibility: hidden; 
        transition: opacity 0.3s ease, visibility 0.3s ease;
    }

    .spinner-overlay.visible { opacity: 1; visibility: visible; }
    .spinner {
        border: 4px solid rgba(255, 255, 255, 0.3);
        border-left-color: #65c3a1; 
        border-radius: 50%;
        width: 40px; height: 40px;
        animation: spin 1s linear infinite;
    }

    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

    @media (max-width: 768px) {
        .form-grid, .conditional-fields {
            grid-template-columns: 1fr; 
            gap: 20px; 
        }
        .form-field.full-width { grid-column: 1; }
        #prediction-form-root { padding: 25px 30px; margin: 30px auto; }
        .component-header { font-size: 40px; }
        .component-subheader { font-size: 16px; margin-bottom: 35px; white-space: normal;}

    }

    @media (max-width: 480px) {
         #prediction-form-root { padding: 20px; margin: 20px auto;}
         .component-header { font-size: 32px; }
         .component-subheader { font-size: 15px; }
         .form-input, .form-textarea, .form-select-btn, .form-number-input { padding: 10px 15px; }
         .submit-button, .action-button { padding: 10px 35px; font-size: 15px; }

    }
</style>
"""

script = """
/**
 * Returns a function, that, as long as it continues to be invoked, will not
 * be triggered. The function will be called after it stops being called for
 * N milliseconds.
 * @param {Function} func The function to debounce.
 * @param {number} wait The number of milliseconds to delay.
 * @returns {Function} The debounced function.
 */
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

/**
 * Manages the prediction form component, handling its rendering,
 * state, interactions, and communication with Streamlit.
 */
class PredictionForm {
    /**
     * Initializes the PredictionForm instance.
     * @param {HTMLElement} rootElement The container element for the form.
     * @param {object} initialData Data passed from Streamlit, including options for dropdowns.
     */
    constructor(rootElement, initialData) {
        this.componentRoot = rootElement;
        console.log("PredictionForm: Constructor called.");

        if (!this.componentRoot) {
            console.error("PredictionForm ERROR: Root element provided to constructor is invalid.");
            throw new Error("PredictionForm requires a valid root element.");
        }

        this.initialData = initialData || {};
        this.categoryOptions = this.initialData.category_options || [];
        this.subcategoryMap = this.initialData.subcategory_map || {};
        this.countryOptions = this.initialData.country_options || [];

        this.state = {
            shortDescription: '',
            longDescription: '',
            risk: '',
            category: null,
            subcategory: null,
            country: null,
            fundingGoal: '',
            imageCount: '',
            videoCount: '',
            campaignDuration: '',
            hasPreviousProjects: 'no',
            previousProjectCount: '',
            previousSuccessfulProjectCount: '',
            previousTotalPledged: '',
            previousTotalFundingGoal: '',
            isLoading: false,
        };

        this.dropdownStates = {};
        this._globalClickListener = this.handleGlobalClick.bind(this);
        this.isGlobalListenerAttached = false;
        this.lastHeight = 0;

        /**
         * Debounced function to adjust the Streamlit frame height based on the component's content height.
         */
        this.adjustHeight = debounce(() => {
            if (!this.componentRoot) {
                console.warn("adjustHeight: componentRoot not found.");
                return;
            }
            const currentHeight = this.componentRoot.scrollHeight;
            const targetHeight = currentHeight + 20;

            if (Math.abs(targetHeight - this.lastHeight) > 5) {
                console.log(`PredictionForm: Adjusting height to ${targetHeight}px (scrollHeight: ${currentHeight}px)`);
                Streamlit.setFrameHeight(targetHeight);
                this.lastHeight = targetHeight;
            }
        }, 150);

        try {
            this.renderHTMLStructure();
            this.bindElements();
            this.updateUIState();
            this.bindEventListeners();
            console.log("PredictionForm: Initial rendering and binding complete.");
            this.componentRoot.classList.add('loaded');
            this.adjustHeight();
        } catch (error) {
             console.error("PredictionForm ERROR during initialization:", error);
             this.componentRoot.innerHTML = `<p style="color: red; padding: 20px;">Form Initialization Error: ${error.message}</p>`;
             this.componentRoot.classList.add('loaded');
             Streamlit.setFrameHeight(80);
             throw error;
        }
    }

    /**
     * Generates and sets the inner HTML for the form component.
     */
    renderHTMLStructure() {
        this.componentRoot.innerHTML = `
            <div class="component-header">Boost Campaign Success!</div>
            <div class="component-subheader">Predict success rate, assess critical factors, & receive actionable improvement suggestions.</div>

            <form id="campaignForm">
                <div class="form-grid">
                    <div class="form-field full-width">
                        <label for="shortDescription" class="form-label">Short Description</label>
                        <textarea id="shortDescription" name="shortDescription" class="form-textarea" placeholder="A concise summary of your project" style="min-height: 80px;"></textarea>
                    </div>

                    <div class="form-field full-width">
                        <label for="longDescription" class="form-label">Long Description</label>
                        <textarea id="longDescription" name="longDescription" class="form-textarea" placeholder="Describe your project in detail"></textarea>
                    </div>

                    <div class="form-field full-width">
                        <label for="risk" class="form-label">Risks and Challenges</label>
                        <textarea id="risk" name="risk" class="form-textarea" placeholder="Outline potential risks and challenges"></textarea>
                    </div>

                    <div class="form-field">
                        <label for="category" class="form-label">Category</label>
                        ${this.renderCustomSelect('category', 'Select Category', this.categoryOptions)}
                    </div>

                    <div class="form-field">
                        <label for="subcategory" class="form-label">Subcategory</label>
                        ${this.renderCustomSelect('subcategory', 'Select Subcategory', [], true)}
                    </div>

                    <div class="form-field">
                        <label for="country" class="form-label">Country</label>
                        ${this.renderCustomSelect('country', 'Select Country', this.countryOptions)}
                    </div>

                    <div class="form-field">
                        <label for="fundingGoal" class="form-label">Funding Goal (USD)</label>
                        <input type="number" id="fundingGoal" name="fundingGoal" class="form-number-input" placeholder="e.g., 5000" min="0" step="any">
                    </div>

                    <div class="form-field">
                        <label for="imageCount" class="form-label">Image Count</label>
                        <input type="number" id="imageCount" name="imageCount" class="form-number-input" placeholder="e.g., 5" min="0" step="1">
                    </div>

                     <div class="form-field">
                        <label for="videoCount" class="form-label">Video Count</label>
                        <input type="number" id="videoCount" name="videoCount" class="form-number-input" placeholder="e.g., 1" min="0" step="1">
                    </div>

                    <div class="form-field">
                        <label for="campaignDuration" class="form-label">Campaign Duration (Days)</label>
                        <input type="number" id="campaignDuration" name="campaignDuration" class="form-number-input" placeholder="e.g., 30" min="1" step="1">
                    </div>

                    <div class="form-field full-width">
                         <label class="form-label">Have you initiated a crowdfunding project before?</label>
                         <div class="radio-group">
                             <label class="radio-option">
                                 <input type="radio" name="hasPreviousProjects" value="yes">
                                 <span class="radio-custom"></span>
                                 <span class="radio-label">Yes</span>
                             </label>
                             <label class="radio-option">
                                 <input type="radio" name="hasPreviousProjects" value="no" checked>
                                 <span class="radio-custom"></span>
                                 <span class="radio-label">No</span>
                             </label>
                         </div>
                     </div>

                     <!-- Conditional Fields -->
                    <div class="conditional-fields" id="conditionalFields">
                        <div class="form-field">
                            <label for="previousProjectCount" class="form-label">Previous Project Count</label>
                            <input type="number" id="previousProjectCount" name="previousProjectCount" class="form-number-input" placeholder="e.g., 3" min="0" step="1">
                        </div>
                        <div class="form-field">
                            <label for="previousSuccessfulProjectCount" class="form-label">Previous Successful Project Count</label>
                            <input type="number" id="previousSuccessfulProjectCount" name="previousSuccessfulProjectCount" class="form-number-input" placeholder="e.g., 2" min="0" step="1">
                        </div>
                        <div class="form-field">
                            <label for="previousTotalPledged" class="form-label">Previous Average Pledged (USD)</label>
                            <input type="number" id="previousTotalPledged" name="previousTotalPledged" class="form-number-input" placeholder="e.g., 15000" min="0" step="any">
                        </div>
                        <div class="form-field">
                            <label for="previousTotalFundingGoal" class="form-label">Previous Average Funding Goal (USD)</label>
                            <input type="number" id="previousTotalFundingGoal" name="previousTotalFundingGoal" class="form-number-input" placeholder="e.g., 10000" min="0" step="any">
                        </div>
                    </div>
                </div>

                <div class="submit-button-container">
                    <button type="submit" class="submit-button" id="submitBtn">Predict Success</button>
                </div>
            </form>
            <div class="spinner-overlay" id="spinnerOverlay">
                 <div class="spinner"></div>
            </div>
        `;
    }

    /**
     * Renders the HTML for a custom dropdown select element.
     * @param {string} id The base ID for the select element and its parts.
     * @param {string} placeholder The text displayed when no option is selected.
     * @param {Array<string>} options An array of string options for the dropdown.
     * @param {boolean} [disabled=false] Whether the dropdown should be initially disabled.
     * @returns {string} The HTML string for the custom select component.
     */
    renderCustomSelect(id, placeholder, options, disabled = false) {
        const safeOptions = Array.isArray(options) ? options : [];
        const optionsHTML = safeOptions.map(opt =>
            `<div class="select-option" data-value="${String(opt)}">${String(opt)}</div>`
        ).join('');

        return `
            <div class="custom-select-container" id="${id}-container">
                <button type="button" class="form-select-btn" id="${id}-button" data-value="" ${disabled ? 'disabled' : ''}>
                    ${placeholder}
                </button>
                <div class="select-options-list" id="${id}-list">
                    ${optionsHTML || '<div class="select-option disabled">No options available</div>'}
                </div>
            </div>
        `;
    }

    /**
     * Queries the DOM to find and store references to essential form elements.
     * Throws an error if critical elements cannot be found.
     */
    bindElements() {
        if (!this.componentRoot) {
             console.error("PredictionForm bindElements ERROR: componentRoot is null.");
             return;
        }
        this.form = this.componentRoot.querySelector('#campaignForm');
        this.shortDescriptionInput = this.componentRoot.querySelector('#shortDescription');
        this.longDescriptionInput = this.componentRoot.querySelector('#longDescription');
        this.riskInput = this.componentRoot.querySelector('#risk');
        this.fundingGoalInput = this.componentRoot.querySelector('#fundingGoal');
        this.imageCountInput = this.componentRoot.querySelector('#imageCount');
        this.videoCountInput = this.componentRoot.querySelector('#videoCount');
        this.campaignDurationInput = this.componentRoot.querySelector('#campaignDuration');
        this.previousProjectRadios = this.componentRoot.querySelectorAll('input[name="hasPreviousProjects"]');
        this.conditionalFieldsContainer = this.componentRoot.querySelector('#conditionalFields');
        this.previousProjectCountInput = this.componentRoot.querySelector('#previousProjectCount');
        this.previousSuccessfulProjectCountInput = this.componentRoot.querySelector('#previousSuccessfulProjectCount');
        this.previousTotalPledgedInput = this.componentRoot.querySelector('#previousTotalPledged');
        this.previousTotalFundingGoalInput = this.componentRoot.querySelector('#previousTotalFundingGoal');
        this.submitBtn = this.componentRoot.querySelector('#submitBtn');
        this.spinnerOverlay = this.componentRoot.querySelector('#spinnerOverlay');

        if (!this.form || !this.submitBtn || !this.spinnerOverlay || !this.shortDescriptionInput || !this.longDescriptionInput) {
             console.error("PredictionForm bindElements FATAL: Failed to find one or more critical form elements.");
             throw new Error("Critical form elements could not be bound.");
        }

        this.dropdownStates = {};
        this.dropdownStates['category'] = this.setupDropdown('category');
        this.dropdownStates['subcategory'] = this.setupDropdown('subcategory');
        this.dropdownStates['country'] = this.setupDropdown('country');
    }

    /**
     * Sets up the state object for a specific dropdown.
     * @param {string} id The ID of the dropdown to set up.
     * @returns {object|null} An object containing references to the button and list elements, and open state, or null if elements not found.
     */
    setupDropdown(id) {
        if (!this.componentRoot) return null;
        const button = this.componentRoot.querySelector(`#${id}-button`);
        const list = this.componentRoot.querySelector(`#${id}-list`);
        if (!button || !list) {
            console.warn(`PredictionForm setupDropdown: Could not find button or list for ID '${id}'.`);
            return null;
        }
        return { button, list, isOpen: false };
    }

     /**
      * Updates the form's UI elements to reflect the current internal state.
      * This includes input values, dropdown selections, and conditional field visibility.
      */
     updateUIState() {
         if (!this.shortDescriptionInput || !this.longDescriptionInput || !this.conditionalFieldsContainer) {
             console.warn("PredictionForm updateUIState: Skipping update, elements not bound or missing.");
             return;
         }
        this.shortDescriptionInput.value = this.state.shortDescription;
        this.longDescriptionInput.value = this.state.longDescription;
        this.riskInput.value = this.state.risk;
        this.fundingGoalInput.value = this.state.fundingGoal;
        this.imageCountInput.value = this.state.imageCount;
        this.videoCountInput.value = this.state.videoCount;
        this.campaignDurationInput.value = this.state.campaignDuration;

        this.updateDropdownButton('category', this.state.category, 'Select Category');
        this.updateDropdownButton('subcategory', this.state.subcategory, 'Select Subcategory');
        this.updateDropdownButton('country', this.state.country, 'Select Country');

        const showConditional = this.state.hasPreviousProjects === 'yes';
        this.conditionalFieldsContainer.classList.toggle('visible', showConditional);
        if (this.previousProjectCountInput) this.previousProjectCountInput.value = showConditional ? this.state.previousProjectCount : '';
        if (this.previousSuccessfulProjectCountInput) this.previousSuccessfulProjectCountInput.value = showConditional ? this.state.previousSuccessfulProjectCount : '';
        if (this.previousTotalPledgedInput) this.previousTotalPledgedInput.value = showConditional ? this.state.previousTotalPledged : '';
        if (this.previousTotalFundingGoalInput) this.previousTotalFundingGoalInput.value = showConditional ? this.state.previousTotalFundingGoal : '';

        if (this.previousProjectRadios) {
            this.previousProjectRadios.forEach(radio => {
                radio.checked = radio.value === this.state.hasPreviousProjects;
            });
        }

        if(this.spinnerOverlay) this.spinnerOverlay.classList.toggle('visible', this.state.isLoading);
        if(this.submitBtn) this.submitBtn.disabled = this.state.isLoading;
    }

    /**
     * Attaches event listeners to form elements for user interactions
     * (inputs, radio changes, dropdown clicks, form submission).
     */
    bindEventListeners() {
        if (!this.shortDescriptionInput || !this.longDescriptionInput) {
             console.error("PredictionForm bindEventListeners ERROR: Cannot bind listeners, standard elements missing.");
             return;
        }

        this.shortDescriptionInput.addEventListener('input', e => { this.state.shortDescription = e.target.value; this.adjustHeight(); });
        this.longDescriptionInput.addEventListener('input', e => { this.state.longDescription = e.target.value; this.adjustHeight(); });
        this.riskInput.addEventListener('input', e => { this.state.risk = e.target.value; this.adjustHeight(); });
        this.fundingGoalInput.addEventListener('input', e => this.state.fundingGoal = e.target.value);
        this.imageCountInput.addEventListener('input', e => this.state.imageCount = e.target.value);
        this.videoCountInput.addEventListener('input', e => this.state.videoCount = e.target.value);
        this.campaignDurationInput.addEventListener('input', e => this.state.campaignDuration = e.target.value);

        if (this.previousProjectCountInput) this.previousProjectCountInput.addEventListener('input', e => this.state.previousProjectCount = e.target.value);
        if (this.previousSuccessfulProjectCountInput) this.previousSuccessfulProjectCountInput.addEventListener('input', e => this.state.previousSuccessfulProjectCount = e.target.value);
        if (this.previousTotalPledgedInput) this.previousTotalPledgedInput.addEventListener('input', e => this.state.previousTotalPledged = e.target.value);
        if (this.previousTotalFundingGoalInput) this.previousTotalFundingGoalInput.addEventListener('input', e => this.state.previousTotalFundingGoal = e.target.value);

        if (this.previousProjectRadios) {
            this.previousProjectRadios.forEach(radio => {
                radio.addEventListener('change', e => {
                    if (e.target.checked) {
                        this.state.hasPreviousProjects = e.target.value;
                        this.updateUIState();
                        this.adjustHeight();
                    }
                });
            });
        }

        Object.keys(this.dropdownStates).forEach(id => {
            const dd = this.dropdownStates[id];
            if (!dd) return;
            dd.button.addEventListener('click', (event) => this.toggleDropdown(id, event));
            dd.list.addEventListener('click', (event) => this.handleOptionSelect(id, event));
        });

        if (!this.isGlobalListenerAttached) {
             document.addEventListener('click', this._globalClickListener, true);
             this.isGlobalListenerAttached = true;
             console.log("PredictionForm: Added global click listener.");
        }

        this.form.addEventListener('submit', this.handleSubmit.bind(this));
    }

    /**
     * Handles clicks outside of any open dropdowns to close them.
     * Attached to the document.
     * @param {Event} event The click event object.
     */
    handleGlobalClick(event) {
        Object.keys(this.dropdownStates).forEach(id => {
            const dd = this.dropdownStates[id];
            if (dd && dd.isOpen) {
                 const container = this.componentRoot?.querySelector(`#${id}-container`);
                 if (container && !container.contains(event.target)) {
                    this.closeDropdown(id);
                 }
            }
        });
    }

    /**
     * Toggles the visibility of a specific dropdown list.
     * Closes other open dropdowns before opening a new one.
     * @param {string} id The ID of the dropdown to toggle.
     * @param {Event} event The click event object.
     */
    toggleDropdown(id, event) {
         event.stopPropagation();
         const dd = this.dropdownStates[id];
         if (!dd || dd.button.disabled) return;

         Object.keys(this.dropdownStates).forEach(otherId => {
            if (otherId !== id && this.dropdownStates[otherId]?.isOpen) {
               this.closeDropdown(otherId);
            }
         });

         dd.isOpen = !dd.isOpen;
         dd.list.style.display = dd.isOpen ? 'block' : 'none';
         dd.button.classList.toggle('open', dd.isOpen);
         this.adjustHeight();
    }

    /**
     * Closes a specific dropdown list if it's open.
     * @param {string} id The ID of the dropdown to close.
     */
    closeDropdown(id) {
         const dd = this.dropdownStates[id];
         if (dd && dd.isOpen) {
             dd.list.style.display = 'none';
             dd.isOpen = false;
             dd.button.classList.remove('open');
             this.adjustHeight();
         }
    }

    /**
     * Handles the selection of an option within a dropdown list.
     * Updates the internal state and potentially updates related dropdowns (e.g., subcategory based on category).
     * @param {string} id The ID of the dropdown where the selection occurred.
     * @param {Event} event The click event object.
     */
    handleOptionSelect(id, event) {
        if (event.target.classList.contains('select-option') && !event.target.classList.contains('disabled')) {
            const value = event.target.dataset.value;
            this.state[id] = value;

            if (id === 'category') {
                this.state.subcategory = null;
                this.updateSubcategoryOptions(value);

                const subcatDD = this.dropdownStates['subcategory'];
                if (subcatDD && subcatDD.button) {
                     const subcatOptions = this.subcategoryMap[value] || [];
                     subcatDD.button.disabled = subcatOptions.length === 0;
                     this.updateDropdownButton('subcategory', null, subcatOptions.length === 0 ? 'N/A' : 'Select Subcategory');
                } else {
                     console.warn("handleOptionSelect: Could not find subcategory button to enable/disable.");
                }
            }

            this.updateDropdownButton(id, value);
            this.closeDropdown(id);
        }
    }

    /**
     * Updates the text and state of a dropdown button to reflect the selected value.
     * Also updates the 'selected' class on the corresponding option in the list.
     * @param {string} id The ID of the dropdown button to update.
     * @param {string|null} value The selected value (or null if none).
     * @param {string} [placeholder='Select Option'] The placeholder text if no value is selected.
     */
    updateDropdownButton(id, value, placeholder = 'Select Option') {
         const dd = this.dropdownStates[id];
         if (!dd) {
             console.warn(`updateDropdownButton: Dropdown state for '${id}' not found.`);
             return;
         }

         if (!dd.button) {
             console.warn(`updateDropdownButton: Button element for '${id}' not found.`);
             return;
         }

         const displayValue = value || placeholder;
         if (dd.button.textContent !== displayValue) {
            dd.button.textContent = displayValue;
         }
         dd.button.dataset.value = value || '';

         if (dd.list) {
             const options = dd.list.querySelectorAll('.select-option');
             options.forEach(opt => {
                 opt.classList.toggle('selected', opt.dataset.value === value);
             });
         }
    }

    /**
     * Updates the options available in the subcategory dropdown based on the selected category.
     * @param {string} selectedCategory The currently selected main category value.
     */
    updateSubcategoryOptions(selectedCategory) {
        const subcatDD = this.dropdownStates['subcategory'];
        if (!subcatDD || !subcatDD.list) {
            console.warn("updateSubcategoryOptions: Subcategory dropdown list element missing.");
            return;
        }

        const rawOptions = (this.subcategoryMap && selectedCategory && Array.isArray(this.subcategoryMap[selectedCategory]))
                       ? this.subcategoryMap[selectedCategory]
                       : [];
        const options = rawOptions.filter(opt => String(opt) !== String(selectedCategory));

        let optionsHTML = '';

        if (options.length > 0) {
             optionsHTML = options.map(opt =>
                `<div class="select-option" data-value="${String(opt)}">${String(opt)}</div>`
             ).join('');
        } else {
             optionsHTML = '<div class="select-option disabled">No relevant subcategories available</div>';
        }
        subcatDD.list.innerHTML = optionsHTML;
        this.adjustHeight();
    }

    /**
     * Handles the form submission event.
     * Prevents default submission, sets loading state, gathers form data,
     * cleans up conditional data, and sends it to Streamlit via setComponentValue.
     * @param {Event} event The form submission event.
     */
    handleSubmit(event) {
        event.preventDefault();
        if (this.state.isLoading) return;

        this.state.isLoading = true;
        this.updateUIState();

        requestAnimationFrame(() => {
            const formData = { ...this.state };

            delete formData.isLoading;

            if (formData.hasPreviousProjects === 'no') {
                formData.previousProjectCount = '0';
                formData.previousSuccessfulProjectCount = '0';
                formData.previousTotalPledged = '0';
                formData.previousTotalFundingGoal = '0';
            }

            Object.keys(formData).forEach(key => {
                if (typeof formData[key] === 'number') {
                    formData[key] = String(formData[key]);
                }
            });

            console.log("PredictionForm: Sending data to Streamlit:", formData);
            Streamlit.setComponentValue({ type: "predict", payload: formData });

             setTimeout(() => {
                 if (this.componentRoot) {
                    this.state.isLoading = false;
                    this.updateUIState();
                 }
             }, 150);

        });
    }

    /**
     * Cleans up resources used by the component instance, such as event listeners and observers.
     * Should be called if the component is removed or replaced.
     */
    destroy() {
         console.log("PredictionForm: Destroying instance.");
         if (this._globalClickListener && this.isGlobalListenerAttached) {
            document.removeEventListener('click', this._globalClickListener, true);
            this.isGlobalListenerAttached = false;
            console.log("PredictionForm: Removed global click listener.");
         }

         if (window.predictionFormResizeObserver) {
             window.predictionFormResizeObserver.disconnect();
             console.log("PredictionForm: Disconnected ResizeObserver.");
         }

         if (this.componentRoot) {
            this.componentRoot.innerHTML = '';
         }
    }
}

window.predictionFormInstance = null;
window.predictionFormResizeObserver = null;

/**
 * Streamlit component render event handler.
 * Initializes or updates the PredictionForm component when Streamlit signals a render.
 * @param {Event} event The Streamlit render event object containing component arguments.
 */
function onRender(event) {
    console.log("PredictionForm: onRender triggered.");
    const rootElementId = 'prediction-form-root';
    let rootElement = document.getElementById(rootElementId);

    if (!rootElement) {
         console.warn(`PredictionForm onRender: Root element '#${rootElementId}' not found initially. Retrying shortly...`);
         setTimeout(() => onRender(event), 100);
         return;
    }

    try {
        const data = event.detail.args.component_data;
        if (!data) {
             console.warn("PredictionForm onRender: No component_data received.");
             rootElement.innerHTML = '<p style="color: orange; padding: 20px;">Waiting for initial data...</p>';
             rootElement.classList.add('loaded');
             Streamlit.setFrameHeight(60);
             return;
        }

        if (!window.predictionFormInstance) {
            console.log("PredictionForm: Creating new instance.");
            if (window.predictionFormResizeObserver) {
                 window.predictionFormResizeObserver.disconnect();
                 window.predictionFormResizeObserver = null;
            }

            window.predictionFormInstance = new PredictionForm(rootElement, data);
            console.log("PredictionForm: Instance created successfully.");

             if ('ResizeObserver' in window && !window.predictionFormResizeObserver) {
                window.predictionFormResizeObserver = new ResizeObserver(() => {
                    window.predictionFormInstance?.adjustHeight();
                });
                window.predictionFormResizeObserver.observe(window.predictionFormInstance.componentRoot);
                console.log("PredictionForm: ResizeObserver setup complete and observing.");
             } else if (!('ResizeObserver' in window)) {
                  console.warn("PredictionForm: ResizeObserver not supported in this browser. Height adjustments might be less reliable.");
             }

        } else {
            console.log("PredictionForm: Instance already exists. Checking for updates (currently just adjusting height).");
            window.predictionFormInstance.adjustHeight();
        }

    } catch (error) {
         console.error("PredictionForm onRender FATAL ERROR:", error);
         if (rootElement) {
             rootElement.innerHTML = `<p style="color: red; padding: 20px;">Component Error: ${error.message}. Check console for details.</p>`;
             rootElement.classList.add('loaded');
             Streamlit.setFrameHeight(80);
         } else {
             console.error(`FATAL: Root element '#${rootElementId}' could not be found to display error message.`);
         }
         if (window.predictionFormInstance) {
             try { window.predictionFormInstance.destroy(); } catch (e) { console.error("Error during instance cleanup:", e);}
             window.predictionFormInstance = null;
         }
          if (window.predictionFormResizeObserver) {
             try { window.predictionFormResizeObserver.disconnect(); } catch (e) { console.error("Error during observer cleanup:", e);}
             window.predictionFormResizeObserver = null;
         }
    }
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
console.log("PredictionForm: Script loaded, event listener added, component ready signaled.");

"""

prediction_form_component = generate_component(
    "ai_prediction_form_v2",
    template=f'<div id="prediction-form-root"></div>\n{css}',
    script=script
)

try:
    explainer = CampaignExplainerV2()
except Exception as e:
    st.error(f"Fatal Error Initializing Services: {e}")
    st.stop()

if not st.session_state.get('prediction_result_available', False):
    component_data_payload = {
        "category_options": category_options,
        "subcategory_map": subcategory_map,
        "country_options": country_options,
    }
    component_return_value = prediction_form_component(
        component_data=component_data_payload,
        key="prediction_form_state_v2",
        default=None
    )

    if component_return_value and isinstance(component_return_value, dict) and component_return_value.get('type') == 'predict':
        raw_data = component_return_value.get('payload', {})
        st.session_state['last_raw_prediction_input'] = raw_data

        missing_fields = []
        error_messages = []

        def is_present(value):
            return value is not None and value != ''

        def is_valid_number_str(value_str, min_value=0, field_name="Field"):
            if not is_present(value_str):
                return False, f"{field_name} is required."
            try:
                value_num = float(value_str)
                if value_num < min_value:
                     if min_value > 0 and value_num <= 0 and field_name not in ["Image Count", "Video Count", "Previous Project Count", "Previous Successful Project Count", "Previous Total Pledged", "Previous Total Funding Goal"]:
                         return False, f"{field_name} must be greater than {min_value}."
                     elif value_num < min_value:
                          return False, f"{field_name} must be {min_value} or greater."
                return True, ""
            except (ValueError, TypeError):
                return False, f"{field_name} must be a valid number."

        if not is_present(raw_data.get('shortDescription')): missing_fields.append("Short Description")
        if not is_present(raw_data.get('longDescription')): missing_fields.append("Long Description")
        if not is_present(raw_data.get('risk')): missing_fields.append("Risks and Challenges")
        if not is_present(raw_data.get('category')): missing_fields.append("Category")

        selected_category = raw_data.get('category')
        if selected_category and selected_category in subcategory_map:
            valid_subcategories = [sub for sub in subcategory_map.get(selected_category, []) if sub != selected_category]
            if valid_subcategories and not is_present(raw_data.get('subcategory')):
                 missing_fields.append("Subcategory (required for this category)")

        if not is_present(raw_data.get('country')): missing_fields.append("Country")

        valid_funding, msg_funding = is_valid_number_str(raw_data.get('fundingGoal'), min_value=0.01, field_name="Funding Goal")
        if not valid_funding: error_messages.append(msg_funding)

        valid_img, msg_img = is_valid_number_str(raw_data.get('imageCount'), min_value=0, field_name="Image Count")
        if not valid_img: error_messages.append(msg_img)

        valid_vid, msg_vid = is_valid_number_str(raw_data.get('videoCount'), min_value=0, field_name="Video Count")
        if not valid_vid: error_messages.append(msg_vid)

        valid_dur, msg_dur = is_valid_number_str(raw_data.get('campaignDuration'), min_value=1, field_name="Campaign Duration")
        if not valid_dur: error_messages.append(msg_dur)


        if raw_data.get('hasPreviousProjects') == 'yes':
            valid_prev_count, msg_prev_count = is_valid_number_str(raw_data.get('previousProjectCount'), min_value=0, field_name="Previous Project Count")
            if not valid_prev_count: error_messages.append(msg_prev_count)

            valid_prev_succ, msg_prev_succ = is_valid_number_str(raw_data.get('previousSuccessfulProjectCount'), min_value=0, field_name="Previous Successful Project Count")
            if not valid_prev_succ: error_messages.append(msg_prev_succ)

            valid_prev_pledged, msg_prev_pledged = is_valid_number_str(raw_data.get('previousTotalPledged'), min_value=0, field_name="Previous Total Pledged")
            if not valid_prev_pledged: error_messages.append(msg_prev_pledged)

            valid_prev_goal, msg_prev_goal = is_valid_number_str(raw_data.get('previousTotalFundingGoal'), min_value=0, field_name="Previous Total Funding Goal")
            if not valid_prev_goal: error_messages.append(msg_prev_goal)

            if valid_prev_count and valid_prev_succ:
                try:
                    prev_count_val = int(raw_data.get('previousProjectCount', 0))
                    prev_succ_val = int(raw_data.get('previousSuccessfulProjectCount', 0))
                    if prev_succ_val > prev_count_val:
                        error_messages.append("Previous Successful Project Count cannot exceed Previous Project Count.")
                except (ValueError, TypeError):
                     pass

        if missing_fields or error_messages:
            full_error_message = "Please correct the following issues:\n"
            if missing_fields:
                full_error_message += f"\n*   **Missing fields:** {', '.join(missing_fields)}"
            if error_messages:
                 full_error_message += "\n*   " + "\n*   ".join(error_messages)

            st.error(full_error_message)
            st.session_state.prediction_result_available = False
        else:
            st.session_state.prediction_result_available = False
            st.session_state.prediction_explanation = "Generating prediction and explanation..."
            st.session_state.raw_llm_explanation = None

            with st.spinner("Analyzing your campaign data and generating insights... This may take a moment."):
                try:
                    funding_goal = float(raw_data.get('fundingGoal', 0))
                    image_count = int(raw_data.get('imageCount', 0))
                    video_count = int(raw_data.get('videoCount', 0))
                    campaign_duration = int(raw_data.get('campaignDuration', 0))

                    has_previous = raw_data.get('hasPreviousProjects') == 'yes'
                    prev_proj_count = int(raw_data.get('previousProjectCount', 0)) if has_previous else 0
                    prev_succ_count = int(raw_data.get('previousSuccessfulProjectCount', 0)) if has_previous else 0
                    prev_pledged = float(raw_data.get('previousTotalPledged', 0)) if has_previous else 0.0
                    prev_goal = float(raw_data.get('previousTotalFundingGoal', 0)) if has_previous else 0.0

                    previous_success_rate = 0.0
                    if has_previous and prev_proj_count > 0:
                        prev_succ_count_clamped = max(0, min(prev_succ_count, prev_proj_count))
                        previous_success_rate = prev_succ_count_clamped / prev_proj_count

                    api_payload = {
                        "raw_description": raw_data.get('longDescription', ''),
                        "raw_blurb": raw_data.get('shortDescription', ''),
                        "raw_risks": raw_data.get('risk', ''),
                        "raw_category": raw_data.get('category', ''),
                        "raw_subcategory": raw_data.get('subcategory', ''),
                        "raw_country": raw_data.get('country', ''),
                        "funding_goal": funding_goal,
                        "image_count": image_count,
                        "video_count": video_count,
                        "campaign_duration": campaign_duration,
                        "previous_projects_count": prev_proj_count,
                        "previous_success_rate": previous_success_rate,
                        "previous_pledged": prev_pledged,
                        "previous_funding_goal": prev_goal
                    }
                    st.session_state['last_api_payload'] = api_payload

                    api_url = st.secrets["HF_API_URL"]
                    headers = {"Content-Type": "application/json"}

                    response = requests.post(api_url, headers=headers, json=api_payload, timeout=180)
                    response.raise_for_status()

                    api_result = response.json()
                    st.session_state['api_response_data'] = api_result


                    predicted_rate_api = api_result.get("success_probability", 0.0) * 100
                    longformer_embedding = api_result.get("longformer_embedding")

                    if longformer_embedding is None:
                        st.error("Prediction successful, but failed to retrieve necessary embedding data from the API.")
                        st.session_state.prediction_result_available = False
                    else:
                        cleaned_explanation, raw_explanation = explainer.generate_prediction_explanation(
                            prediction_data=api_result,
                            input_campaign_features=api_payload,
                            longformer_embedding=longformer_embedding
                        )


                        st.session_state['predicted_success_rate'] = predicted_rate_api
                        st.session_state['prediction_explanation'] = cleaned_explanation
                        st.session_state['raw_llm_explanation'] = raw_explanation
                        st.session_state.prediction_result_available = True

                        st.rerun()

                except requests.exceptions.RequestException as e:
                    st.error(f"Network error connecting to the prediction service: {e}")
                    print(f"Network error: {e}")
                    st.session_state.prediction_result_available = False
                    st.session_state.raw_llm_explanation = f"Error during API call: {e}"
                except json.JSONDecodeError:
                    st.error("Failed to decode the response from the prediction service. The response might not be valid JSON.")
                    print(f"JSON Decode Error. Response Status: {response.status_code}, Response Text: {response.text[:500]}...")
                    st.session_state.prediction_result_available = False
                    st.session_state.raw_llm_explanation = f"JSON Decode Error. Response Text: {response.text[:500]}..."
                except Exception as e:
                    st.error(f"An unexpected error occurred during prediction or explanation: {e}")
                    print(f"Unexpected error: {e}")
                    st.session_state.prediction_result_available = False
                    st.session_state.raw_llm_explanation = f"Unexpected error during prediction/explanation: {e}"

else:
    success_rate = st.session_state.get('predicted_success_rate', 0.0)
    explanation_text = st.session_state.get('prediction_explanation', "<p>Explanation not available.</p>")

    st.markdown(f"""
    <div class="prediction-result-container loaded">
        <div class="prediction-result-content">
            <div class="success-rate-label">Predicted Success Rate</div>
            <div class="success-rate-value">{success_rate:.1f}%</div>
            <div class="ai-suggestions">
                {explanation_text}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Make Another Prediction", key="make_another_prediction", type="primary"):
         st.session_state.prediction_result_available = False
         st.session_state.predicted_success_rate = None
         st.session_state.prediction_explanation = "No explanation generated yet."
         st.session_state.api_response_data = None
         st.session_state.raw_llm_explanation = None
         if 'last_api_payload' in st.session_state:
             del st.session_state['last_api_payload']
         st.rerun()

    if 'api_response_data' in st.session_state and st.session_state['api_response_data']:
        with st.expander("View Full API Response Data"):
            api_data_display = st.session_state['api_response_data'].copy()
            if 'shap_values' in api_data_display:
                 shap_items = sorted(api_data_display['shap_values'].items(), key=lambda item: abs(float(item[1])), reverse=True)
                 api_data_display['shap_values_sorted'] = dict(shap_items)
                 del api_data_display['shap_values']
            if 'longformer_embedding' in api_data_display:
                embed_len = len(api_data_display['longformer_embedding'])
                api_data_display['longformer_embedding_preview'] = api_data_display['longformer_embedding'][:10] + ["..."]
                api_data_display['longformer_embedding_info'] = f"(Total {embed_len} dimensions)"
                del api_data_display['longformer_embedding']

            st.json(api_data_display)


    if 'last_api_payload' in st.session_state:
         with st.expander("View Data Sent to API"):
              st.json(st.session_state['last_api_payload'])

    if 'last_raw_prediction_input' in st.session_state:
         with st.expander("View Last Raw Input Data (From Form)"):
              st.json(st.session_state['last_raw_prediction_input'])

    if 'raw_llm_explanation' in st.session_state and st.session_state['raw_llm_explanation']:
        with st.expander("View Raw LLM Explanation Response"):
            st.text(st.session_state['raw_llm_explanation'])