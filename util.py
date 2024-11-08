# keeping useful helpful functions in here

import csv
import requests
import time, random
import json
import io
import PyPDF2, pdfplumber
from flask import jsonify, make_response, Response
import os
from urllib.parse import urljoin
from nameparser import HumanName
from langchain_text_splitters import RecursiveCharacterTextSplitter 
import typing_extensions as typing

# This function is used to append the jsons to the given csv file
def convert_json_list_to_csv(jsons: list[dict], filename: str) -> None:
    if jsons:
        headers = jsons[0].keys()

        # only write the header if the file does not already exist
        writeHeader = not os.path.exists(filename)
    
        # Open a file for writing
        ## NOV 1 CHANGE: changed mode from 'w' to 'a+' to append to existing file
        with open(filename, mode='a+', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            
            # Only write the geader rite the header
            if writeHeader:
                writer.writeheader()
            
            # Write each dictionary as a row in the CSV
            for json in jsons:
                writer.writerow(json)

# This funcion helps fetch data from the given url with backoff to avoid rate limits
# mainly used for semantic scholar API
def fetchWithBackoff(url: str, max_retries: int = 4) -> tuple[dict, bool]:
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

# Helper function to download a PDF from a given URL
# used for downloading the paper from the open access link
def download_pdf(full_url: str) -> io.BytesIO:
    print(f"Fetching pdf from {full_url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    response = requests.get(full_url, headers=headers)
    print(f"Download response status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Failed to download PDF from: {full_url}")
        return None
    return io.BytesIO(response.content)

# Helper function to extract text from a PDF file using PyPDF2
def extract_text_pypdf2(pdf_file: io.BytesIO) -> str:
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
   
# Uses PyPDF2 to read a binary stream to text; returns that text    
def extract_text_pdfplumber(pdf_file: io.BytesIO) -> str:
    print("Attempting to extract text from PDF using pdfplumber")
    try:
        with pdfplumber.open(pdf_file) as pdf:
            print(f"PDF has {len(pdf.pages)} pages")
            text = ""
            for i, page in enumerate(pdf.pages):
                print(f"Extracting text from page {i+1}")
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"  # Add extra newline between pages
        return text.strip()
    except Exception as e:
        print(f"Error extracting text with pdfplumber: {str(e)}")
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

# Helper function for making Flask response objects based on the different
# status code of the response
# Helper function to make a server response with the given status code, message, and content
# Mainly use status codes 200, 400, 422, and 500
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
        case 401:
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

# Uses simple rules to try to determine if a name could be considered ambiguous
# Returns True or False as strings (more compatible with output JSON schema)
def nameIsAmbiguous(name_string: str) -> str:
    hn = HumanName(name_string)
    
    # Check if the name has multiple possible interpretations
    if not(hn.first and hn.last):
        return "True"
    
    # Abbreviated first or last without period
    if len(hn.first) == 1 or len(hn.last) == 1:
        return "True"
    
    # Abbreviated first with period (J. for example)
    if len(hn.first) == 2 and hn.first[1] == '.':
        return "True"
    
    # Abbreviated last with period
    if len(hn.last) == 2 and hn.last[1] == '.':
        return "True"
    
    return "False"  


# This function takes a text file and chunks it into smaller pieces
# Used to avoid rate limits
def chunk_data(file: str, chunk_size : int) -> typing.List[str]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = chunk_size, # about 500 words
        chunk_overlap = 100,
        length_function = len,
    )
    text = ""
    with open(file, 'r', encoding="utf8") as file:
        for line in file:
            text += line.strip() 
    chunks = text_splitter.split_text(text)
    return chunks
