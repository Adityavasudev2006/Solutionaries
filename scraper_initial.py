import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import os
import time # Import time for potential delays

# --- Configuration ---
# !!! IMPORTANT: Replace with your actual Gemini API key !!!
# Consider using environment variables for better security instead of hardcoding.
GEMINI_API_KEY = "AIzaSyAntBQpKkQGGm5EZiPyveKP4ZeV1V104MI" # Replace with your key
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    print("Please ensure your API key is correct and valid.")
    exit() # Exit if API key setup fails

# List of URLs to scrape
urls_to_scrape = [
    "https://www.proptiger.com/filters?q=Mahabalipuram,%20Chennai",
    "https://www.squareyards.com/sale/property-for-sale-in-old-mahabalipuram-road-chennai",
    "https://www.indiaproperty.com/searchs/c=omr&pt=allresidential&ci=chennai&litype=sale&vm=mNe00%5E~%5EFYlODimLKaZJfaztZvZKWuapvan66qlqdor6WqWt3OlNXq2dGio93cmbKZWdncxtaXn9jYpOfSlta0lZieoea2ZJvVnOW02NOelprsndmmWeHgya9nXaqla6GiX6OqkaNpXaatYKee&frm=15&srchtype=quick-search&f=srch&withapi=2&view=grid", # Often requires complex interaction/JS
    "https://www.proptiger.com/chennai/property-sale-mahabalipuram-51685",
    "https://www.squareyards.com/rent/property-for-rent-in-india", 
    "https://www.nobroker.in/property/rent/chennai/Old-Mahabalipuram-Road?searchParam=W3sibGF0IjoxMi44NDU1MjI1LCJsb24iOjgwLjIyMzMyLCJwbGFjZUlkIjoiQ2hJSmpVMFdiS0dWVnpqUlJ4YVVFVGxVTDZrIiwicGxhY2VOYW1lIjoiT2xkIE1haGFiYWxpcHVyYW0gUm9hZCIsInNob3dNYXAiOmZhbHNlfV0=&radius=2.0&city=chennai&locality=Old%20Mahabalipuram%20Road", # Modified NoBroker URL for OMR
    "https://www.99acres.com/search/property/buy/old-mahabalipuram-road-chennai-south?city=34&locality=563&preference=S&area_unit=1&budget_min=0&res_com=R", # Updated 99acres for OMR
    "https://housing.com/in/buy/chennai/omr",
    "https://www.magicbricks.com/property-for-sale/residential-real-estate?bedroom=2,3&proptype=Multistorey-Apartment,Builder-Floor-Apartment,Penthouse,Studio-Apartment,Residential-House,Villa&Locality=Old%20Mahabalipuram%20Road&cityName=Chennai", # Updated MagicBricks for OMR
    "https://www.commonfloor.com/listing-search?city=Chennai&cg=Chennai%20-%20Kanchipuram&iscg=&search_intent=sale&property_location_filter%5B%5D=area_2368&prop_name%5B%5D=Old%20Mahabalipuram%20Road&polygon=1&page=1&page_size=30", # Updated CommonFloor for OMR
    "https://www.olx.in/chennai_g4058788/q-omr-property",
    "https://www.quikr.com/homes/property/residential-for-sale-in-old_mahabalipuram_road-chennai-cid_25-rid_51b738f6b548b"
]

# Output JSON filename
output_filename = "aggregated_property_data.json"
# --- End Configuration ---

# --- Helper Functions ---
def clean_gemini_response(text):
    """Removes common markdown formatting and trims whitespace."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

# --- Main Script ---
all_extracted_data = [] # List to hold data from all successful scrapes

# Initialize Gemini Model (do this once)
try:
    model = genai.GenerativeModel("gemini-1.5-pro")
    print("Gemini model initialized successfully.")
except Exception as e:
    print(f"Error initializing Gemini model: {e}")
    exit()

# Loop through each URL
for url in urls_to_scrape:
    print(f"\n--- Processing URL: {url} ---")
    extracted_properties_for_url = [] # Reset for each URL

    try:
        # 1. Fetch webpage content
        print("Fetching webpage content...")
        # Add headers to mimic a browser, some sites block simple requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        req = requests.get(url, headers=headers, timeout=20) # Increased timeout, added headers
        req.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        print("Webpage content fetched successfully.")

        # 2. Parse HTML content
        soup = BeautifulSoup(req.content, "html.parser")

        # 3. Extract raw text
        # Getting the text from the main content area might be better if identifiable,
        # but get_text() is a general approach.
        scraped_text = soup.get_text(separator='\n', strip=True)
        if not scraped_text:
            print("Warning: No text extracted from the page. Skipping Gemini analysis.")
            continue # Skip to the next URL if no text found

        print(f"Raw text extracted (length: {len(scraped_text)} chars).")

        # Limit text size sent to Gemini to avoid excessive cost/token limits
        # Adjust limit as needed based on Gemini model and typical page size
        max_chars = 15000
        if len(scraped_text) > max_chars:
            print(f"Warning: Truncating scraped text to {max_chars} characters for Gemini.")
            scraped_text = scraped_text[:max_chars]

        # 4. Send scraped data to Gemini for analysis
        prompt = f"""
        Analyze the following scraped text data from the real estate listings page: {url}.
        Extract details for properties listed on this page, focusing ONLY on:
        1. Price (e.g., "₹ 1.5 Cr", "₹ 85 Lac", "$1.2M"). Include currency.
        2. Square Footage or Area (e.g., "1500 sqft", "200 sq yards", "180 sq m"). Include units.
        3. Property Title or a very brief description if available (e.g., "3 BHK Apartment", "Villa in OMR").

        Structure the output STRICTLY as a JSON object with a single key "properties".
        The value of "properties" should be a list of JSON objects.
        Each object in the list represents one property and MUST contain the keys "title", "price", and "area".
        If a specific value (title, price, or area) cannot be found for a property, use `null` or an empty string "" for that key's value within the property object.
        Do NOT include properties where you cannot find at least a price OR an area.
        Do NOT include any explanations or text outside the main JSON structure. Just output the JSON.

        Scraped Data Snippet:
        ---
        {scraped_text}
        ---
        """

        print("Sending data to Gemini for analysis...")
        try:
            response = model.generate_content(prompt)
            print("Received response from Gemini.")
        except Exception as gen_err:
            print(f"Error during Gemini API call for {url}: {gen_err}")
            continue # Skip to next URL

        # 5. Process and Validate Gemini's Response
        gemini_response_text = clean_gemini_response(response.text)

        if not gemini_response_text:
            print(f"Warning: Received empty response from Gemini for {url}. Skipping.")
            continue

        try:
            # Attempt to parse the response text as JSON
            parsed_json = json.loads(gemini_response_text)

            # **** VALIDATION ****
            if isinstance(parsed_json, dict) and 'properties' in parsed_json:
                if isinstance(parsed_json['properties'], list):
                    # Successfully parsed and has the expected structure
                    extracted_properties_for_url = parsed_json['properties']
                    print(f"Successfully parsed {len(extracted_properties_for_url)} properties from Gemini for {url}.")
                    # Optional: Add source URL to each property record
                    for prop in extracted_properties_for_url:
                         prop['source_url'] = url # Add source URL
                    # Add the valid list of properties to the main list
                    all_extracted_data.extend(extracted_properties_for_url)
                else:
                    print(f"Warning: Gemini response for {url} parsed, but 'properties' key is not a list. Skipping.")
                    # print("Raw Gemini Response Text:\n", gemini_response_text) # Uncomment for debugging
            else:
                print(f"Warning: Gemini response for {url} parsed, but is not a dictionary with a 'properties' key. Skipping.")
                # print("Raw Gemini Response Text:\n", gemini_response_text) # Uncomment for debugging

        except json.JSONDecodeError as e:
            print(f"Warning: Failed to decode JSON from Gemini's response for {url}. Skipping.")
            # print(f"JSONDecodeError: {e}") # Uncomment for detailed error
            # print("Raw Gemini Response Text was:\n", gemini_response_text) # Uncomment for debugging

    # --- Graceful Error Handling for Fetch/Parse ---
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error fetching {url}: {e}. Skipping.")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error fetching {url}: {e}. Skipping.")
    except requests.exceptions.Timeout as e:
        print(f"Timeout fetching {url}: {e}. Skipping.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}. Skipping.")
    except Exception as e:
        # Catch-all for other unexpected errors during processing a single URL
        print(f"An unexpected error occurred while processing {url}: {e}. Skipping.")

    # Optional: Add a small delay between requests to be polite to servers
    time.sleep(1) # Wait 1 second

# --- Save Aggregated Data ---
print(f"\n--- Finished processing all URLs ---")
print(f"Total properties extracted across all valid sources: {len(all_extracted_data)}")

if not all_extracted_data:
    print("No data was successfully extracted from any URL.")
else:
    try:
        # Determine output path (same directory as the script)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_filepath = os.path.join(script_dir, output_filename)

        with open(output_filepath, "w", encoding='utf-8') as outfile:
            # Save the list of all extracted properties
            json.dump(all_extracted_data, outfile, indent=4, ensure_ascii=False)

        print(f"\nAggregated data successfully saved to: {output_filepath}")

    except IOError as e:
        print(f"\nError: Could not write aggregated data to the file {output_filepath}")
        print(f"IOError: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred while saving the aggregated file: {e}")

    # Optionally, print a snippet of the final aggregated data
    # print("\n--- Sample of Aggregated Data ---")
    # print(json.dumps(all_extracted_data[:5], indent=4, ensure_ascii=False)) # Print first 5 entries
    # print("--- End of Sample ---")