import time
import random
import os
import httpx
from dotenv import load_dotenv
from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
from mistralai.models.httpvalidationerror import HTTPValidationError
import json
import util
from datetime import datetime
from tqdm import tqdm
import re

load_dotenv()
api_key = os.getenv('Mistral_key')
model = "open-mixtral-8x22b"

def initialize_client():
    if not api_key:
        raise ValueError("Mistral API key not found in environment variables")
    return Mistral(api_key=api_key)

def fetch_with_backoff(messages, max_retries):
    client = initialize_client()
    retry_delay = 1
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = client.chat.complete(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
                timeout_ms=30000
            )
            return response.choices[0].message.content
            
        except HTTPValidationError as e:
            print(f"Validation error on attempt {attempt + 1}: {str(e)}")
            last_error = e
            # If it's a validation error, no point retrying
            break
            
        except SDKError as e:
            print(f"SDK error on attempt {attempt + 1}: {str(e)}")
            last_error = e
            time.sleep(retry_delay)
            retry_delay = calculate_next_delay(retry_delay)
            
        except httpx.RequestError as e:
            print(f"Request error on attempt {attempt + 1}: {str(e)}")
            last_error = e
            time.sleep(retry_delay)
            retry_delay = calculate_next_delay(retry_delay)
            
        except Exception as e:
            print(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
            last_error = e
            time.sleep(retry_delay)
            retry_delay = calculate_next_delay(retry_delay)

    print(f"Failed after {max_retries} attempts. Last error: {str(last_error)}")
    return json.dumps([])

def calculate_next_delay(current_delay):
    """Calculate the next delay with exponential backoff and jitter"""
    return (current_delay * 2) + random.uniform(0, 1)

def validate_response(response_text):
    """Validate and clean the response text"""
    try:
        # Remove any control characters
        cleaned_text = re.sub(r'[\x00-\x1F\x7F]', '', response_text)
        # Attempt to parse as JSON to validate
        json.loads(cleaned_text)
        return cleaned_text
    except json.JSONDecodeError as e:
        print(f"Invalid JSON response: {str(e)}")
        return json.dumps([])

def section_pull_data(txtfile, shouldExtractReferences=True):
    if not os.path.exists(txtfile):
        raise FileNotFoundError(f"Input file not found: {txtfile}")
        
    chunks = util.chunk_data(txtfile, 3000)
    connections = []
    unique_connections = set()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"./results/mistral_results_{timestamp}.csv"
    
    # Create base query with proper message format
    base_query = '''[Your existing base query text]'''
    if not shouldExtractReferences:
        base_query += '\nDo not process the References section of this paper.'

    try:
        for chunk in tqdm(chunks, desc="Processing chunks"):
            messages = [{"role": "user", "content": base_query + chunk}]
            response = fetch_with_backoff(messages, 5)
            cleaned_response = validate_response(response)
            
            try:
                chunk_connections = json.loads(cleaned_response)
                for conn in chunk_connections:
                    if isinstance(conn, dict):
                        dict_tuple = frozenset(conn.items())
                        if dict_tuple not in unique_connections:
                            unique_connections.add(dict_tuple)
                            connections.append(conn)
                            util.convert_json_list_to_csv([conn], output_filename)
            except json.JSONDecodeError as e:
                print(f"Error processing chunk: {str(e)}")
                continue
                
        return connections, output_filename
        
    except Exception as e:
        print(f"Error in section_pull_data: {str(e)}")
        return [], output_filename