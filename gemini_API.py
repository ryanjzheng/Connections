# documentation for gemini: https://ai.google.dev/api?lang=python
# use venv
# pip install google-generativeai
# pip install PyPDF2
# pip install langchain-text-splitters
# pip install python-dotenv

import json
import PyPDF2
import pandas as pd
import google.generativeai as genai
import os
from dotenv import load_dotenv
import csv
from langchain_text_splitters import RecursiveCharacterTextSplitter 
import typing_extensions as typing
from google.api_core.exceptions import ResourceExhausted
import random
import time
import util


load_dotenv()
# putting these here for the exponential backoff so itll be global 
safe = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_NONE",
        },
    ]
config = genai.GenerationConfig(
        response_mime_type="application/json",
        temperature=0.2
    )

# pdf text extraction function
def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

# using .env so user can use their own API key
key = os.getenv('GeminiAPI_KEY')
genai.configure(api_key=key)
model = genai.GenerativeModel(model_name='gemini-1.5-flash',generation_config={"response_mime_type": "application/json"})

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

# This function is used to remove duplicates and NULLs from the JSON data
def pandas_clean(arr: typing.List[dict]) -> None:
    df_raw = pd.DataFrame(arr)
    df_lower = df_raw.apply(lambda x: x.str.lower() if x.dtype == "object" else x) # makes all values lower case
    df_unique = df_lower.drop_duplicates(ignore_index=True) # drops duplicte values excluding index 
    df_unique = df_unique.dropna() 
    df_unique.to_csv('Prototype/results/gemini_results.csv', mode='w+')

# This function takes a text file and extracts connections from it using the Gemini API
def section_pull_data(txtfile: str) -> typing.List[dict]:
    #text = extract_text_from_pdf("connect4/Prototype/paper.pdf")
    chunk = chunk_data(txtfile, 3000) # well readable text file 
    base_query = '''Given this part of the research paper, Respond with every SPECIFIC, NAMED organization, person, or lab that helped the author (we call this a "connection").
    Only include named people, universities, or labs, ensuring they are PROPER nouns or formal entities. 
    Exclude any terms that describe roles, groups, or anonymous contributors, or are otherwise unclear.
    Return the information in this json format: 
    [
        {
            "name": [the name of the organization or person], 
            "connection_type": ["Organization" if this is an organization that helped the author; "Person" if this is a person that helped the author]
            "connection": [how this connection helped or relates to the author.],
            "is_ambiguous": ["True" if this connection is the author of a referenced work and full first and last name is not given; "False" otherwise]
        },
        ...
    ]
    To the best of your ability, please output the "name" field in title case where it is appropriate.
    Additionally, for the "name" field, please omit any formatting characters like quotation marks.
    Some guidelines for the "connection" field: 
    - the only options are "Co-author", "Referenced", and "Funded"
    - Only "Person" connections can be "Co-author"
    - "Funded" should only be used if "connection_type" is "Organization" and when it is EXPLICIT that the organization funded the authors of the paper whose text you are reading.

    An example of this format (DO NOT INCLUDE EITHER OF THESE EXAMPLE CONNECTIONS IN THE OUTPUT):
    [
        {
            "name": "J. Smith", 
            "connection_type": "Person",
            "connection": "Referenced",
            "is_ambiguous": "True"
        },
        {
            "name": "National Research Lab", 
            "connection_type": "Organization",
            "connection": "Funded",
            "is_ambiguous": "False"
        }
    ]

    Again, DO NOT INCLUDE EITHER OF THE GIVEN EXAMPLE CONNECTIONS IN THE OUTPUT.
    
    Do not explain. only return the json. if there are no such connections, return an empty json with no fields. do NOT format your response with markdown or any other formatting convention.
    '''
    connections = []
    unique_connections = set()

    # 5 chunks so that it doesn't max out the API call rates
    for c in chunk: 
        query = base_query + c
        response = fetch_with_backoff(query, 7)
        # print(f'\033[92mchunk {i} response:\033[0m') .   # commenting out for now for the demo
        # print(json.dumps(json.loads(response.text), indent=2))
        try:
            cleaned_text = response.text.strip()
            chunk_connections = json.loads(cleaned_text)
            for conn in chunk_connections:
                dict_tuple = frozenset(conn.items())
                if dict_tuple not in unique_connections:
                    unique_connections.add(dict_tuple)
                    ## CHANGE: instead of appending to connections, write to CSV,
                    # update the CSV file with the new connection
                    # This will make sure data is not lost if the program crashes
                    
                    # connections.append(conn)
                    util.convert_json_list_to_csv([conn], "Prototype/results/gemini_results.csv")
        except json.decoder.JSONDecodeError as e:
            print(f"JSON DECODE ERROR: {cleaned_text}")
        except:
            print("Some unknown error occurred; skipping")
            continue
    util.convert_json_list_to_csv(connections, "Prototype/results/gemini_results.csv")
    # pandas_clean(connections)
    return connections

# This helper function is used to fetch data from the API with exponential backoff
# This is used to avoid rate limits by waiting and retrying
def fetch_with_backoff(query: str, max_retries: int) -> genai.GenerativeModel.generate_content:
    retry_delay = 1  # Initial delay in seconds
    for attempt in range(max_retries):
        try:
            response = model.generate_content(query, safety_settings=safe, generation_config=config)
            #print(response.choices[0].message.content)
            return response
        except ResourceExhausted as e:
            time.sleep(retry_delay)
            retry_delay *= 2  # Double the delay for the next attempt
            retry_delay += random.uniform(0, 1)  # Add jitter
    print("api error User rate limit exceeded") 
    return json.dumps([]) # this return might not work always 



# def main():
#     section_pull_data("testPaper.txt")

# section_pull_data("Prototype/testPaper.txt")