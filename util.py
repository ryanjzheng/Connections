# keeping useful helpful functions in here

import csv
import requests
import time, random
import json
import io
import PyPDF2
from flask import jsonify, make_response, Response

# File "C:\Users\cwpoo\connect4\Prototype\util.py", line 23, in convert_json_list_to_csv
#     writer.writerow(json)
#   File "C:\Python312\Lib\csv.py", line 164, in writerow
#     return self.writer.writerow(self._dict_to_list(rowdict))
#                                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "C:\Python312\Lib\csv.py", line 159, in _dict_to_list
#     raise ValueError("dict contains fields not in fieldnames: "
# ValueError: dict contains fields not in fieldnames: ''

def convert_json_list_to_csv(jsons, filename):
    if jsons:
        headers = jsons[0].keys()
    
        # Open a file for writing
        ## NOV 1 CHANGE: changed mode from 'w' to 'a+' to append to existing file
        with open(filename, mode='a+', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            
            # Write the header
            writer.writeheader()
            
            # Write each dictionary as a row in the CSV
            for json in jsons:
                writer.writerow(json)

# Generic fetching with backoff using the requests module
def fetchWithBackoff(url, max_retries=4):
    got_response = False
    retry_delay = 1  # Initial delay in seconds
    print(f"Attempting fetch from {url}")
    for attempt in range(max_retries):
        response = requests.get(url)
        if response.status_code != 200:
            print(f"({attempt + 1}/{max_retries}) Waiting {retry_delay:.1f} sec before trying again...")
            time.sleep(retry_delay)
            retry_delay *= 2  # Double the delay for the next attempt
            retry_delay += random.uniform(0, 1)  # Add jitter
        else:
            got_response = True
            break
    
    if not got_response:
        print(f"Failed to receive response from {url}")
    return (json.loads(response.content), got_response)

def download_pdf(full_url):
    print(f"Fetching pdf from {full_url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    response = requests.get(full_url, headers=headers)
    print(f"Download response status code: {response.status_code}")
    return io.BytesIO(response.content)

def extract_text_pypdf2(pdf_file):
    print("Attempting to extract text from PDF using PyPDF2")
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        print(f"PDF has {len(reader.pages)} pages")
        text = ""
        for i, page in enumerate(reader.pages):
            print(f"Extracting text from page {i+1}")
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"  # Add extra newline between pages
        return text.strip()
    except Exception as e:
        print(f"Error extracting text with PyPDF2: {str(e)}")
        return None
    
# Since authors' names can be written in many different text encodings, try to 
# decode them using a bunch of different encodings.
def tryDecodings(str: str) -> str:
    encodings = ['utf-8', 'latin1', 'utf-16', 'utf-32', 'ascii', 'unicode_escape']
    byte_string = str.encode('raw_unicode_escape')
    for encoding in encodings:
        try:
            # Try decoding the byte string with the current encoding
            decoded = byte_string.decode(encoding)
            return decoded
        except (UnicodeDecodeError, AttributeError):
            pass

    return str

def makeServerResponse(status_code: int, message="", content=[]) -> Response:
    response = Response()

    match status_code:
        case 200:
            response = make_response(jsonify(content))
        case 400:
            response = make_response(jsonify({
                "message" : message,
                "status_code" : status_code
            }))
        case 422:
            response = make_response(jsonify({
                "message" : message,
                "status_code" : status_code
            }))
        case 500:
            response = make_response(jsonify({
                "message" : message,
                "status_code" : status_code
            }))
        case _:
            raise ValueError(f"Cannot make server response with code {status_code}")

    response.status_code = status_code
    response.mimetype = 'application/json'
    return response