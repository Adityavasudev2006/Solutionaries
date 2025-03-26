import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import os
import time # Import time for potential delays

# --- Configuration ---
# !!! IMPORTANT: SECURITY RISK !!!
# Hardcoding API keys like this is insecure and strongly discouraged.
# Consider using environment variables or a configuration file for better security.
# Anyone who sees this code can use your key.
GEMINI_API_KEY = "AIzaSyD0QWnkS7PiYNGV9aKvdF_1ckzVV56A2z8" # <--- API KEY ADDED AS REQUESTED

try:
    # Check if the key is provided (basic check)
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY": # Keep the check just in case
         raise ValueError("Gemini API Key is missing or still set to the placeholder.")
    genai.configure(api_key=GEMINI_API_KEY)
    print("Attempting to initialize Gemini model...")
    # Simple check to see if configuration worked without immediate model listing
    # You could add model listing back if needed for early validation:
    # models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    # if not models:
    #     raise ValueError("No suitable generative models found. Check API key permissions and model availability.")
    # print("Gemini API configured.")
except ValueError as ve:
    print(f"Configuration Error: {ve}")
    exit()
except Exception as e:
    # Catch potential authentication errors specifically if possible
    # Example: Google API errors often have specific types or messages
    if "API key not valid" in str(e) or "permission" in str(e).lower():
         print(f"Error configuring Gemini API: {e}")
         print("Authentication failed. Please ensure your API key is correct, valid, enabled, and has necessary permissions.")
    else:
         print(f"Error configuring Gemini API: {e}")
         print("An unexpected error occurred during API setup.")
    exit() # Exit if API key setup fails

# List of URLs to scrape (ensure these are relevant to property listings)
urls_to_scrape = [
    "https://www.proptiger.com/filters?q=Mahabalipuram,%20Chennai",
    "https://www.squareyards.com/sale/property-for-sale-in-old-mahabalipuram-road-chennai",
    # "https://www.indiaproperty.com/searchs/c=omr&pt=allresidential&ci=chennai&litype=sale&vm=mNe00%5E~%5EFYlODimLKaZJfaztZvZKWuapvan66qlqdor6WqWt3OlNXq2dGio93cmbKZWdncxtaXn9jYpOfSlta0lZieoea2ZJvVnOW02NOelprsndmmWeHgya9nXaqla6GiX6OqkaNpXaatYKee&frm=15&srchtype=quick-search&f=srch&withapi=2&view=grid", # Often requires complex interaction/JS, might yield poor results
    "https://www.proptiger.com/chennai/property-sale-mahabalipuram-51685",
    # "https://www.squareyards.com/rent/property-for-rent-in-india", # Generic rent page, unlikely useful for descriptions
    "https://www.nobroker.in/property/sale/chennai/Old-Mahabalipuram-Road?searchParam=W3sibGF0IjoxMi44NDU1MjI1LCJsb24iOjgwLjIyMzMyLCJwbGFjZUlkIjoiQ2hJSmpVMFdiS0dWVnpqUlJ4YVVFVGxVTDZrIiwicGxhY2VOYW1lIjoiT2xkIE1haGFiYWxpcHVyYW0gUm9hZCIsInNob3dNYXAiOmZhbHNlfV0=&radius=2.0&city=chennai&locality=Old%20Mahabalipuram%20Road", # Changed to sale for consistency
    "https://www.99acres.com/search/property/buy/old-mahabalipuram-road-chennai-south?city=34&locality=563&preference=S&area_unit=1&budget_min=0&res_com=R",
    "https://housing.com/in/buy/chennai/omr",
    "https://www.magicbricks.com/property-for-sale/residential-real-estate?bedroom=2,3&proptype=Multistorey-Apartment,Builder-Floor-Apartment,Penthouse,Studio-Apartment,Residential-House,Villa&Locality=Old%20Mahabalipuram%20Road&cityName=Chennai",
    "https://www.commonfloor.com/listing-search?city=Chennai&cg=Chennai%20-%20Kanchipuram&iscg=&search_intent=sale&property_location_filter%5B%5D=area_2368&prop_name%5B%5D=Old%20Mahabalipuram%20Road&polygon=1&page=1&page_size=30",
    # "https://www.olx.in/chennai_g4058788/q-omr-property", # OLX often has less structured data, might be noisy
    # "https://www.quikr.com/homes/property/residential-for-sale-in-old_mahabalipuram_road-chennai-cid_25-rid_51b738f6b548b" # Quikr structure varies
]

# Output JSON filename
output_filename = "property_descriptions.json"
# --- End Configuration ---

# --- Helper Functions ---
def clean_gemini_response(text):
    """Removes common markdown formatting and trims whitespace."""
    text = text.strip()
    # Remove potential markdown code block fences
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:] # Handle cases without 'json' specifier

    if text.endswith("```"):
        text = text[:-3]

    # Sometimes Gemini might add explanatory text before/after the JSON block
    # Try to find the JSON block if it's embedded (robust check)
    json_start = text.find('{')
    json_end = text.rfind('}')

    # Ensure we found both and the end is after the start
    if json_start != -1 and json_end != -1 and json_end > json_start:
        potential_json = text[json_start : json_end + 1]
        # Basic validation: check if it looks like JSON
        try:
             json.loads(potential_json)
             text = potential_json # It's likely valid JSON, use it
        except json.JSONDecodeError:
             # It wasn't valid JSON, keep the original text (minus fences)
             # Or log a warning here if desired
             pass # Keep the cleaned text as is
    else:
        # If no braces found, or invalid order, keep the cleaned text
        pass

    return text.strip()

# --- Main Script ---
final_property_data = {} # Dictionary to hold {property_name: description}

# Initialize Gemini Model (do this once)
try:
    # Using a potentially more capable model for generation
    model = genai.GenerativeModel("gemini-1.5-pro-latest") # Or "gemini-1.5-flash-latest" for potentially faster/cheaper
    print("Gemini model initialized successfully.")
except Exception as e:
    print(f"Error initializing Gemini model instance: {e}")
    print("This might indicate an issue with the specific model name or access permissions.")
    exit()

# Loop through each URL
for url in urls_to_scrape:
    print(f"\n--- Processing URL: {url} ---")

    try:
        # 1. Fetch webpage content
        print("Fetching webpage content...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/' # Adding a referer can sometimes help
        }
        # Using a session object can improve performance and handle cookies
        session = requests.Session()
        session.headers.update(headers)
        req = session.get(url, timeout=30) # Increased timeout

        # Check for non-HTML content types which might indicate blocking or errors
        content_type = req.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            print(f"Warning: Received non-HTML content type '{content_type}' for {url}. May indicate an error or block page.")
            # Optionally skip here if non-HTML is always an error
            # continue

        req.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        print(f"Webpage content fetched successfully (Status: {req.status_code}).")

        # 2. Parse HTML content
        soup = BeautifulSoup(req.content, "html.parser")

        # 3. Extract raw text
        # Attempt to find a main content area first for better results
        main_content = soup.find('main') or soup.find('article') or soup.find('div', role='main') or soup.find('body')
        if main_content:
             scraped_text = main_content.get_text(separator='\n', strip=True)
             print("Extracted text from main content area.")
        else:
             scraped_text = soup.get_text(separator='\n', strip=True)
             print("Extracted text from entire page (fallback).")


        if not scraped_text:
            print("Warning: No text extracted from the page. Skipping Gemini analysis.")
            continue

        print(f"Raw text extracted (length: {len(scraped_text)} chars).")

        # Limit text size sent to Gemini to avoid excessive cost/token limits
        # Gemini 1.5 Pro has a large context window, but cost/performance are considerations
        max_chars = 100000 # Increased limit slightly, monitor performance/cost
        if len(scraped_text) > max_chars:
            print(f"Warning: Truncating scraped text from {len(scraped_text)} to {max_chars} characters for Gemini.")
            scraped_text = scraped_text[:max_chars]

        # 4. Send scraped data to Gemini for analysis and description generation
        prompt = f"""
        Analyze the following scraped text data from a real estate listings page: {url}.
        Your goal is to identify individual properties listed and generate engaging descriptions for them.

        Tasks:
        1.  Carefully read the text and identify distinct properties being offered (apartments, villas, houses, plots etc.).
        2.  For each property identified, extract its name or title (e.g., "3 BHK Apartment in OMR", "Luxury Villa near Kelambakkam", "Radiance Suprema"). Use a concise and descriptive name. If no clear name/title is available, try to create a brief one based on type and location (e.g., "Apartment on OMR"). Ensure the name is unique within this page's results if possible.
        3.  Gather all available descriptive information associated *specifically* with that property (e.g., features, amenities, location details, size hints like sqft/sqm/sqyd, configuration like BHK, floor, condition, nearby landmarks, project name, price if mentioned).
        4.  Using the gathered information, **generate an engaging, detailed, walkthrough-style description** for that property. Extrapolate *slightly* where appropriate to make it more vivid and appealing, imagining someone experiencing the space (e.g., if it mentions 'spacious balcony with city view', describe relaxing there after work). If very few details are available, generate a concise but appealing description based on what's known (e.g., property type, general location). Aim for descriptions that are informative yet captivating.
        5.  Structure the final output STRICTLY as a single JSON object (a dictionary).
            *   The **keys** of the JSON object MUST be the property names/titles you identified or created (as strings). Use descriptive keys.
            *   The **values** MUST be the generated walkthrough-style descriptions (as strings).

        Rules:
        *   Only include properties where you can confidently identify at least a name/title and some descriptive context. Do not include index entries, navigation links, advertisements, agent details, or other non-listing text in the final JSON output.
        *   Critically evaluate if text snippets represent actual distinct property listings.
        *   Ensure the output is ONLY the JSON object. Do NOT include any introductory text, explanations, apologies, status messages, or markdown formatting like ```json ```. Just the raw JSON structure.
        *   If no valid properties can be reasonably identified and described from the text, output an empty JSON object: {{}}

        Scraped Text Snippet (first {max_chars} chars):
        ---
        {scraped_text}
        ---

        Generate the JSON output now:
        """

        print("Sending data to Gemini for analysis and description generation...")
        try:
            # Configure safety settings to be less restrictive if needed, but be cautious
            # Use BLOCK_NONE with care, as it might allow harmful content generation.
            # Consider BLOCK_ONLY_HIGH or BLOCK_MEDIUM_AND_ABOVE first.
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
            response = model.generate_content(prompt, safety_settings=safety_settings)

            # Detailed check for blocked content or other issues
            if not response.parts:
                 finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                 safety_ratings = response.candidates[0].safety_ratings if response.candidates else []
                 print(f"Warning: Gemini response was empty for {url}.")
                 print(f"Finish Reason: {finish_reason}")
                 if safety_ratings: print(f"Safety Ratings: {safety_ratings}")
                 # print("Prompt Feedback:", response.prompt_feedback) # More detailed feedback
                 continue

            print("Received response from Gemini.")
        # Catch specific Google API errors if the library provides them
        # except google.api_core.exceptions.PermissionDenied as perm_err:
        #     print(f"Permission Denied Error during Gemini API call for {url}: {perm_err}")
        #     print("Check API key permissions and project billing status.")
        #     continue
        # except google.api_core.exceptions.ResourceExhausted as quota_err:
        #      print(f"Quota Exceeded during Gemini API call for {url}: {quota_err}")
        #      print("You may have hit API usage limits. Check your quotas.")
        #      # Consider adding a longer delay or stopping
        #      time.sleep(60) # Wait a minute before trying next
        #      continue
        except Exception as gen_err:
            print(f"Error during Gemini API call for {url}: {gen_err}")
            # Look for specific API errors if possible
            if hasattr(gen_err, 'message'): print(f"Gemini Error Message: {gen_err.message}")
            # Consider adding different handling based on error type (e.g., retry on temporary errors)
            continue # Skip to next URL

        # 5. Process and Validate Gemini's Response
        gemini_response_text = clean_gemini_response(response.text)

        if not gemini_response_text or gemini_response_text == "{}":
            print(f"Gemini returned no property data or an empty object for {url}. Skipping.")
            continue

        try:
            # Attempt to parse the response text as JSON
            parsed_json = json.loads(gemini_response_text)

            # **** VALIDATION ****
            if isinstance(parsed_json, dict):
                # Successfully parsed and is a dictionary (the expected format)
                count = len(parsed_json)
                if count > 0:
                    print(f"Successfully parsed {count} properties from Gemini for {url}.")
                    # Merge the results into the main dictionary
                    # Handle potential key collisions (e.g., if different URLs list the same property name)
                    # Simple update overwrites; could implement logic to merge/warn if needed
                    final_property_data.update(parsed_json)
                else:
                    print(f"Gemini returned an empty JSON object {{}} for {url}, although parsing succeeded.")

            else:
                # This case should be less likely if clean_gemini_response works well
                print(f"Warning: Gemini response for {url} parsed, but it's not a dictionary as expected. Type: {type(parsed_json)}. Skipping.")
                print("--- Raw Gemini Response Text Start ---")
                print(gemini_response_text) # Print the problematic text
                print("--- Raw Gemini Response Text End ---")


        except json.JSONDecodeError as e:
            print(f"Warning: Failed to decode JSON from Gemini's response for {url}. Skipping.")
            print(f"JSONDecodeError: {e}") # Print detailed error
            print("--- Raw Gemini Response Text Start ---")
            print(gemini_response_text) # Print the problematic text
            print("--- Raw Gemini Response Text End ---")

    # --- Graceful Error Handling for Fetch/Parse ---
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error fetching {url}: {e.Response.status_code} {e.Response.reason}. Skipping.")
        # Add more specific handling for common errors like 403 Forbidden or 404 Not Found
        if e.response.status_code == 403:
            print("Access Forbidden (403). The site may be blocking scrapers. Try rotating User-Agents or using proxies.")
        elif e.response.status_code == 404:
            print("Page Not Found (404). The URL might be outdated.")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error fetching {url}: {e}. Check network or URL validity. Skipping.")
    except requests.exceptions.Timeout as e:
        print(f"Timeout fetching {url}: {e}. Server might be slow or unreachable. Skipping.")
    except requests.exceptions.RequestException as e:
        print(f"General Network Error fetching {url}: {e}. Skipping.")
    except Exception as e:
        # Catch-all for other unexpected errors during processing a single URL
        print(f"An unexpected error occurred while processing {url}: {e.__class__.__name__} - {e}. Skipping.")
        # Optionally log the full traceback for debugging
        # import traceback
        # traceback.print_exc()


    # Optional: Add a small delay between requests to be polite to servers
    wait_time = 2 # seconds
    print(f"Waiting {wait_time} seconds before next request...")
    time.sleep(wait_time)

# --- Save Aggregated Data ---
print(f"\n--- Finished processing all URLs ---")
print(f"Total unique property names extracted across all sources: {len(final_property_data)}")

if not final_property_data:
    print("No property descriptions were successfully generated from any URL.")
else:
    try:
        # Determine output path (same directory as the script)
        try:
             script_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
             script_dir = os.getcwd() # Fallback to current working directory if __file__ is not defined
        output_filepath = os.path.join(script_dir, output_filename)

        with open(output_filepath, "w", encoding='utf-8') as outfile:
            # Save the dictionary of property names and descriptions
            json.dump(final_property_data, outfile, indent=4, ensure_ascii=False)

        print(f"\nAggregated property descriptions successfully saved to: {output_filepath}")

    except IOError as e:
        print(f"\nError: Could not write aggregated data to the file {output_filepath}")
        print(f"IOError: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred while saving the aggregated file: {e}")

    # Optionally, print a snippet of the final aggregated data
    # print("\n--- Sample of Aggregated Data (First 3 Entries) ---")
    # sample_count = 0
    # for name, desc in final_property_data.items():
    #     if sample_count >= 3:
    #         break
    #     print(f'\n"{name}": "{desc[:150]}..."') # Print name and start of description
    #     sample_count += 1
    # if not final_property_data: print ("(No data to sample)")
    # print("--- End of Sample ---")