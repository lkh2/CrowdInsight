from typing import Dict, List, Tuple
from pinecone import Pinecone
from pymongo import MongoClient
from openai import OpenAI
import streamlit as st
import json

class CampaignExplainerV2:
    def __init__(self):
        """
        Initializes the CampaignExplainerV2 by establishing connections
        to Pinecone for vector search, MongoDB for campaign data retrieval,
        and the DeepSeek LLM API for generating explanations.
        Secrets are fetched from Streamlit's secrets management.
        Handles potential connection errors during initialization.
        """
        try:
            self.pc = Pinecone(api_key=st.secrets["PINECONE_API_KEY"])
            self.index = self.pc.Index(st.secrets["PINECONE_INDEX_NAME"])
        except Exception as e:
            st.error(f"Failed to initialize Pinecone: {e}")
            st.stop()

        try:
            self.mongo_client = MongoClient(st.secrets["MONGO_URI"])
            self.db = self.mongo_client[st.secrets["MONGO_DB_NAME"]]
            self.campaigns_collection = self.db[st.secrets["MONGO_COLLECTION_NAME"]]
            self.mongo_client.admin.command('ping')
        except Exception as e:
            st.error(f"Failed to initialize MongoDB: {e}")
            st.stop()

        try:
            self.deepseek_client = OpenAI(
                api_key=st.secrets["DEEPSEEK_API_KEY"],
                base_url=st.secrets["DEEPSEEK_BASE_URL"]
            )
        except Exception as e:
            st.error(f"Failed to initialize DeepSeek client: {e}")
            st.stop()

    def find_similar_campaigns(self, query_embedding: List[float], k=20) -> Tuple[List[Dict], List[float]]:
        """
        Finds similar campaigns based on a provided embedding vector.

        Queries Pinecone for the top `k` nearest neighbors based on the
        `query_embedding`. Retrieves corresponding campaign details from
        MongoDB, filters for successful campaigns (state=1), and extracts
        selected comparable features. Returns the top 5 successful campaigns
        and their corresponding distances.

        Args:
            query_embedding: The embedding vector representing the campaign to find similarities for.
            k: The number of nearest neighbors to retrieve initially from Pinecone.

        Returns:
            A tuple containing:
            - A list of dictionaries, each representing a similar successful campaign
              with its rank, distance, ID, and comparable features. Limited to top 5.
            - A list of distances for the top 5 successful campaigns found.
        """
        if not isinstance(query_embedding, list) or not all(isinstance(x, (int, float)) for x in query_embedding):
             print("Error: Invalid query embedding format provided to find_similar_campaigns.")
             return [], []

        try:
            results = self.index.query(
                vector=query_embedding,
                top_k=k,
                include_metadata=True
            )
        except Exception as e:
             print(f"Error querying Pinecone: {e}")
             return [], []

        similar_campaigns_list = []
        successful_distances = []
        ids_to_fetch = [match.id for match in results.matches]

        if not ids_to_fetch:
            return [], []

        try:
            campaign_details = {doc["_id"]: doc for doc in self.campaigns_collection.find(
                {"_id": {"$in": ids_to_fetch}},
                {
                    "_id": 1, "state": 1, "raw_blurb": 1, "raw_category": 1, "raw_subcategory": 1,
                    "raw_country": 1, "funding_goal": 1, "image_count": 1, "video_count": 1,
                    "campaign_duration": 1, "previous_projects_count": 1, "previous_success_rate": 1
                }
            )}
        except Exception as e:
            print(f"Error fetching from MongoDB: {e}")
            return [], []

        rank = 1
        for match in results.matches:
            campaign_id = match.id
            campaign_data = campaign_details.get(campaign_id)

            if campaign_data and campaign_data.get("state") == 1:
                comparable_features = {
                    "Category": campaign_data.get("raw_category", "N/A"),
                    "Funding Goal (USD)": campaign_data.get("funding_goal", "N/A"),
                    "Image Count": campaign_data.get("image_count", "N/A"),
                    "Video Count": campaign_data.get("video_count", "N/A"),
                    "Duration (Days)": campaign_data.get("campaign_duration", "N/A")
                }
                similar_campaigns_list.append({
                    "rank": rank,
                    "distance": float(match.score),
                    "campaign_id": campaign_id,
                    "comparable_features": comparable_features
                })
                successful_distances.append(float(match.score))
                rank += 1
                if len(similar_campaigns_list) >= 5: 
                    break

        return similar_campaigns_list, successful_distances

    def generate_prediction_explanation(self, prediction_data: Dict, input_campaign_features: Dict, longformer_embedding: List[float]) -> Tuple[str, str]:
        """
        Generates an HTML explanation for a campaign prediction using a RAG approach.

        Takes prediction results (probability, outcome, SHAP values), user input features,
        and the campaign's embedding. Finds similar successful campaigns and constructs
        a detailed prompt for the LLM. The prompt includes the prediction, SHAP analysis
        (compared to averages), user input summary, and similar campaign data.
        Instructs the LLM to generate a structured HTML report comparing the campaign's
        features and SHAP values against averages and similar successful examples,
        providing actionable recommendations.

        Args:
            prediction_data: Dictionary containing success probability, predicted outcome, and SHAP values.
            input_campaign_features: Dictionary containing the features submitted by the user.
            longformer_embedding: The embedding vector for the user's campaign description/blurb.

        Returns:
            A tuple containing:
            - The generated explanation in HTML format (cleaned).
            - The raw response string received from the LLM.
            Handles potential errors during LLM call or data processing, returning error messages.
        """
        try:
            success_prob = prediction_data.get("success_probability", 0.0)
            predicted_outcome = prediction_data.get("predicted_outcome", "N/A")
            shap_values = prediction_data.get("shap_values", {})

            valid_shap_items = []
            for k, v in shap_values.items():
                try:
                    valid_shap_items.append((k, float(v)))
                except (ValueError, TypeError):
                    print(f"Warning: Could not convert SHAP value for '{k}' to float: {v}")
                    valid_shap_items.append((k, 0.0))

            sorted_features = sorted(
                valid_shap_items,
                key=lambda x: abs(x[1]),
                reverse=True
            )
            top_ten_sorted_features = sorted_features[:10]
            similar_campaigns, distances = self.find_similar_campaigns(longformer_embedding)

            similar_campaigns_summary_str = "[\n"
            if similar_campaigns:
                 for camp in similar_campaigns:
                     features_str = json.dumps(camp.get('comparable_features', {}))
                     similar_campaigns_summary_str += f"  Rank {camp['rank']} (Dist: {camp['distance']:.4f}): {features_str},\n"
                 similar_campaigns_summary_str = similar_campaigns_summary_str.rstrip(",\n") + "\n]"
            else:
                 similar_campaigns_summary_str = "[No similar successful campaigns found for comparison.]"

            average_shap_means = {
                "description_embedding": -0.1231, "blurb_embedding": -0.0005, "risk_embedding": -0.0006,
                "subcategory_embedding": 0.0022, "category_embedding": 0.0003, "country_embedding": 0.0018,
                "description_length": -0.0024, "funding_goal": -0.6590, "image_count": 0.0010,
                "video_count": 0.0011, "campaign_duration": -0.0052, "previous_projects_count": 0.0002,
                "previous_success_rate": 0.0002, "previous_pledged": 0.0003, "previous_funding_goal": -0.0008,
                "prediction": 0.6213
            }
            average_shap_means_str = json.dumps(average_shap_means, indent=2)

            user_input_summary_html = "<ul>\n"
            relevant_keys = [
                "raw_blurb", "raw_category", "raw_subcategory", "raw_country",
                "funding_goal", "image_count", "video_count", "campaign_duration",
                "previous_projects_count", "previous_success_rate",
                "previous_pledged", "previous_funding_goal"
            ]
            for key in relevant_keys:
                if key in input_campaign_features:
                    value = input_campaign_features[key]
                    value_str = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    user_input_summary_html += f"    <li><strong>{key.replace('_', ' ').title()}:</strong> {value_str}</li>\n"

            desc_provided = 'Provided' if input_campaign_features.get('raw_description') else 'Not Provided'
            risks_provided = 'Provided' if input_campaign_features.get('raw_risks') else 'Not Provided'
            user_input_summary_html += f"    <li><strong>Raw Description:</strong> {desc_provided}</li>\n"
            user_input_summary_html += f"    <li><strong>Raw Risks:</strong> {risks_provided}</li>\n"
            user_input_summary_html += "</ul>"
 
            prompt = f"""
You are an expert AI assistant specialized in generating **clean, semantic HTML** reports. Your task is to explain the predicted success rate of a user's Kickstarter campaign based on a neural network model analysis. Incorporate their specific input data, compare it to similar successful campaigns, AND compare its SHAP values to average SHAP values across campaigns.

**Input Data Summary:**
*   **Prediction:** Success Probability = {success_prob:.3g}, Predicted Outcome = {predicted_outcome}
*   **Top 10 Feature Importances (SHAP) for THIS Campaign:** {top_ten_sorted_features} (Feature name, SHAP value)
*   **User's Submitted Campaign Details (HTML format):**
{user_input_summary_html}
*   **Top 5 Similar Successful Campaigns (Selected Features for Comparison):**
{similar_campaigns_summary_str}
*   **Distances to Similar Campaigns:** {distances}
*   **Average SHAP Values Across All Campaigns (Mean):**
{average_shap_means_str}

**Output Requirements:**
Your response MUST be **ONLY valid HTML structure snippets**. Absolutely **NO Markdown syntax** or surrounding text like "Here is the HTML:" should be included. Do NOT include `<html>`, `<head>`, or `<body>` tags. Start the response *directly* with the first heading (`<h2>1. Prediction Summary</h2>`). Adhere strictly to the following structure and formatting rules:

**Structure Example:**

<p>[Provide a brief summary of the predicted success rate ({success_prob:.1f}%) and outcome ({predicted_outcome}) for *this specific campaign*. Offer concise congratulations or encouragement based on the prediction.]</p>

<h2>1. Feature Importance Analysis (SHAP Values)</h2>

<h3>How SHAP Works</h3>
<p>[Provide a fixed explanation: "SHAP (SHapley Additive exPlanations) values explain model predictions. Each feature's SHAP value shows its contribution (positive or negative) to the prediction compared to the average. Higher absolute values mean greater importance."]</p>

<h3>Top 10 Contributing Features for Your Campaign</h3>
<p>[Present the top 10 SHAP values ({top_ten_sorted_features}) specific to *this campaign* in a standard HTML table. Use `<thead>` for headers ('Feature', 'SHAP Value', 'Impact', 'Average') and `<tbody>` for data rows. Calculate 'Impact' as 'Positive' (SHAP > 0) or 'Negative' (SHAP < 0). Include the average SHAP value for each feature from 'Average SHAP Values' in the 'Average' column. Ensure numerical SHAP values are displayed clearly.]</p>
<!-- Example HTML Table Structure: -->
<table>
  <thead>
    <tr>
      <th>Feature</th>
      <th>SHAP Value</th>
      <th>Impact</th>
      <th>Average</th>
    </tr>
  </thead>
  <tbody>
    <!-- ... (Generate table rows for top 10 features) ... -->
  </tbody>
</table>

<h3>Interpretation (Compared to Average)</h3>
<p>[Provide a brief interpretation of what these SHAP values signify overall for the campaign's prediction. **Crucially, compare the impact of the top 2-3 features for THIS campaign against the 'Average SHAP Values' provided.** For example: "The funding goal has a significantly stronger negative impact ({top_ten_sorted_features[0][1]:.3f}) on your prediction compared to the average ({average_shap_means.get('funding_goal', 'N/A')}). Conversely, the impact of [positive feature name] ({{top_ten_sorted_features[X][1]:.3f}}) is [stronger/weaker/similar] than the average ({{average_shap_means.get('feature_name', 'N/A')}})."]</p>

<h2>2. Actionable Recommendations & Insights for Your Campaign</h2>
<p>[Focus on actionable advice tailored to the user's submitted details, based *only* on features the user can realistically change. **Critically, compare the user's features against the provided 'Similar Successful Campaigns' data AND consider the 'Average SHAP Values' context, especially for features with negative SHAP impact for this campaign.**]</p>

<h3>Areas for Improvement (Based on Negative SHAP, Your Inputs, Similar Campaigns & Average SHAP)</h3>
<ul>
    <li>[**START WITH THE DESCRIPTION: Begin by directly analyzing specific elements of the user's raw description text from 'User's Submitted Campaign Details'. Quote 1-2 actual phrases or sentences from their description and provide concrete suggestions for improvement. For example: "Your opening sentence '[quote from user text]' could be strengthened by..." or "The section where you describe '[specific feature from their text]' would benefit from more detailed explanation of..."**]</li>
    <li>[**Continue with 2-3 more specific recommendations about their description, each referencing actual content from their submitted text.** Consider clarity, emotional appeal, unique value proposition, addressing objections, and completeness. Be concrete and specific to their actual writing, not generic advice.]</li>
    <li>[Identify features with significant negative SHAP values from the table above.]</li>
    <li>[**Compare** the user's specific values (from 'User's Submitted Campaign Details') for these negative-impact, changeable features (e.g., funding goal, description clarity, risk clarity, media counts, duration) with the values/trends observed in the 'Similar Successful Campaigns' data. **Also, consider if this feature's negative impact is typical (based on 'Average SHAP Values') or particularly strong for this campaign.**]</li>
    <li>[Provide **specific, actionable recommendations** as HTML list items (`<li>`). These recommendations **must be informed by both comparisons**. For example: `<li>Your funding goal of ${input_campaign_features.get('funding_goal', 'N/A')} appears high compared to similar successful campaigns ({similar_campaigns_summary_str}) and has a much stronger negative impact than average ({average_shap_means.get('funding_goal', 'N/A')}); evaluate if adjustment is feasible.</li>`, `<li>Adding video (current: {input_campaign_features.get('video_count', 'N/A')}) could help, aligning with similar projects ({similar_campaigns_summary_str}) and potentially boosting impact (Avg SHAP: {average_shap_means.get('video_count', 'N/A')}).</li>`. **DO NOT suggest changing historical data**.]
</ul>

<h3>Strengths (Based on Positive SHAP, Your Inputs, Similar Campaigns & Average SHAP)</h3>
<ul>
    <li>[Briefly acknowledge 1-2 key strengths as HTML list items (`<li>`) based on positive SHAP values, user inputs, and potentially noting alignment with similar campaigns or better-than-average SHAP impact. E.g., `<li>Your category choice '{input_campaign_features.get('raw_category', 'N/A')}' is a positive factor, typical for successful campaigns ({similar_campaigns_summary_str}) and contributes positively (Avg SHAP: {average_shap_means.get('category_embedding', 'N/A')}).</li>`, `<li>Your campaign duration ({input_campaign_features.get('campaign_duration', 'N/A')} days) appears appropriate, aligning with similar projects ({similar_campaigns_summary_str}) and having a relatively neutral average impact (Avg SHAP: {average_shap_means.get('campaign_duration', 'N/A')}).</li>`).]
</ul>

<h2>3. Disclaimer</h2>
<p>The predictions and improvement suggestions provided by this platform are generated by a multimodal neural network trained on historical Kickstarter data. This model was trained using a binary cross-entropy loss function and evaluated primarily via ROC-AUC; as a result, it may produce more extreme probability estimates (i.e., values closer to 0 or 1) than actual campaign outcomes would warrant.</p>

<h3>Model Performance</h3>
<ul>
    <li>Training set: around 16,000 campaigns</li>
    <li>Validation set: around 2,000 campaigns</li>
    <li>Test set: around 2,000 campaigns</li>
    <li>Test accuracy: 90.24%</li>
    <li>Test ROC-AUC: 0.9607</li>
</ul>

<h3>Interpretability Caveats</h3>
<p>Feature attributions are computed using DeepSHAP, which approximates Shapley values based on a limited set of reference samples. These values can be biased—particularly when features are correlated or the reference set is not fully representative—and should be treated as rough indicators of feature importance rather than precise measurements.</p>

<h3>Use as Guidance Only</h3>
<p>All predictions and explanations are provided for informational purposes and should not be considered guarantees of campaign performance. Users are encouraged to combine these data-driven insights with their own market research, creative judgment, and qualitative factors when planning and refining their crowdfunding campaigns.</p>

**Strict Formatting Rules:**
*   **HTML ONLY:** Pure HTML fragments. No Markdown. No conversational text. Start *directly* with `<p>[Prediction Summary...]</p>`. No `<html>`, `<head>`, `<body>`.
*   **Tags:** Use semantic tags: `<h2>`, `<h3>`, `<p>`, `<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`, `<td>`, `<ul>`, `<li>`, `<strong>`.
*   **Comparison Integration:** Weave insights from comparing user data vs `similar_campaigns_summary_str` AND comparing user SHAP vs `average_shap_means_str` directly into the text content of `<p>` (Interpretation) and `<li>` (Recommendations/Strengths).
*   **Spacing:** Standard HTML indentation.
*   **Dollar Signs:** Use standard dollar signs ($).
*   **Lists:** Use `<ul>` and `<li>`.
*   **Table:** Standard HTML `<table>`.
*   **Conciseness:** Be direct.
*   **No Data Dumping:** Synthesize insights. Refer to input data contextually.

Generate the pure HTML report based *only* on the provided data and these strict instructions, ensuring both comparison analyses (vs similar campaigns, vs average SHAP) are integrated. Ensure no Markdown syntax is present.
"""
            raw_response = self._generate_response(prompt)
            cleaned_response = raw_response.strip()

            if cleaned_response.startswith("```html"):
                cleaned_response = cleaned_response[len("```html"):].strip()
            elif cleaned_response.startswith("```"):
                 cleaned_response = cleaned_response[len("```"):].strip()

            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-len("```")].strip()

            if not cleaned_response.startswith("<"):
                 print(f"Warning: LLM output doesn't look like HTML: {cleaned_response[:100]}...")

            return cleaned_response, raw_response

        except Exception as e:
            print(f"Error during explanation generation: {e}")
            error_message_html = "<p><strong>Error:</strong> An error occurred while generating the explanation. Please check the application logs or try again later.</p>"
            return error_message_html, f"Error: {e}"

    def _generate_response(self, prompt):
        """
        Sends a prompt to the configured DeepSeek LLM API and returns the response.

        Uses the initialized OpenAI client configured for the DeepSeek API endpoint
        and model specified in Streamlit secrets.

        Args:
            prompt: The complete prompt string to send to the LLM.

        Returns:
            The content of the LLM's response string, or an error message string
            if the API call fails.
        """
        try:
            response = self.deepseek_client.chat.completions.create(
                model=st.secrets["DEEPSEEK_MODEL"],
                messages=[
                    {"role": "user", "content": prompt},
                ],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling DeepSeek API: {e}")
            return f"Error: Failed to generate explanation due to an issue with the AI service ({type(e).__name__}). Please try again later."