import os
import json
import sys
import re # Import regex for cleaning filename
from elevenlabs.client import ElevenLabs
from elevenlabs import save
# Note: python-dotenv is not needed when hardcoding the key
# from dotenv import load_dotenv

ELEVENLABS_API_KEY = "sk_cc8a082f36caea223483eaed88c5c06c86f4d5bc70a65b47"
# --- !!! END OF HARDCODED KEY !!! ---

# The JSON file is expected to be in the same directory as this script
JSON_FILENAME = "property_descriptions.json"

# Voice Selection (Find voice IDs on the ElevenLabs website: https://elevenlabs.io/voice-library)
VOICE_ID = '21m00Tcm4TlvDq8ikWAM' # Example: Rachel
MODEL_ID = 'eleven_multilingual_v2'
OUTPUT_DIR = "audio_outputs" # Directory to save MP3 files
# --- End Configuration ---

def load_property_data(filepath):
    """Loads property descriptions from a JSON file in the same directory."""
    try:
        # Assumes filepath is just the filename for the current directory
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully loaded data from {filepath}")
        return data
    except FileNotFoundError:
        print(f"Error: JSON file '{filepath}' not found in the script's directory.")
        print("Please ensure 'property_descriptions.json' is in the same folder as the Python script.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}. Check its format.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred loading {filepath}: {e}")
        return None

def generate_speech(api_key, text, voice_id, model_id, output_path):
    """Generates speech using ElevenLabs API and saves it to a file."""
    # API key presence check is less critical here as it's hardcoded,
    # but we keep the structure. Error handling below catches auth issues.
    if not api_key:
        print("Internal Error: API key variable is unexpectedly empty.")
        return False

    try:
        print("\nInitializing ElevenLabs client...")
        # Initialize client directly with the hardcoded key
        client = ElevenLabs(api_key=api_key)

        print(f"Generating audio for voice ID: {voice_id}...")
        audio = client.generate(
            text=text,
            voice=voice_id,
            model=model_id
        )

        # Create output directory if it doesn't exist
        output_directory = os.path.dirname(output_path)
        if output_directory and not os.path.exists(output_directory):
             os.makedirs(output_directory)
             print(f"Created output directory: {output_directory}")

        print(f"Saving audio to {output_path}...")
        save(audio, output_path)
        print("Audio generated and saved successfully!")
        return True

    except Exception as e:
        print(f"An error occurred during audio generation: {e}")
        if "Unauthenticated" in str(e) or "401" in str(e):
             print("Authentication failed. The hardcoded API Key might be invalid or inactive.")
        return False

def sanitize_filename(name):
    """Removes or replaces characters unsuitable for filenames."""
    name = name.strip()
    name = re.sub(r'[\\/*?:"<>|\s]+', '_', name)
    # Optional: Limit length
    # max_len = 100
    # name = name[:max_len]
    return name

# --- Main execution ---
if __name__ == "__main__":
    # Print the security warning every time the script runs
    print("\n--- 🚨🚨🚨 MAJOR SECURITY WARNING 🚨🚨🚨 ---")
    print("This script contains a hardcoded ElevenLabs API key.")
    print("EXPOSING THIS KEY IS A SIGNIFICANT SECURITY RISK.")
    print("Avoid sharing this file or committing it to version control (like Git).")
    print("Using a .env file or environment variables is strongly recommended.")
    print("---------------------------------------------\n")

    # Load property data from the JSON file expected in the same directory
    property_data = load_property_data(JSON_FILENAME)

    if property_data is None:
        sys.exit(1) # Exit if data loading failed

    # Get user input
    try:
        property_name_input = input("Enter the exact Property Name to generate audio for: ").strip()
    except EOFError:
        print("\nNo input received. Exiting.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user. Exiting.")
        sys.exit(1)


    # Find the description
    if property_name_input in property_data:
        description = property_data[property_name_input]
        print(f"\nFound description for '{property_name_input}'.")

        # Generate a safe filename from the property name
        safe_filename_base = sanitize_filename(property_name_input)
        output_filename = f"{safe_filename_base}.mp3"

        # Prepend output directory
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        # Generate the speech
        if generate_speech(ELEVENLABS_API_KEY, description, VOICE_ID, MODEL_ID, output_path):
            print(f"\nSuccess! Look for the file '{output_path}' in your file explorer.")
        else:
            print("\nAudio generation failed.")

    else:
        print(f"\nError: Property '{property_name_input}' not found in {JSON_FILENAME}.")
        print("Please ensure you entered the exact name as it appears in the JSON file (case-sensitive).")