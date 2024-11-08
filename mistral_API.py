# use venv
# pip install google-generativeai
# pip install PyPDF2
# pip install langchain-text-splitters
# pip install python-dotenv
# pip install tqdm #gives prgress bar
import time
import random
import os
import httpx
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter 
from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
import json
import util
from datetime import datetime
from tqdm import tqdm
import re

load_dotenv()

TIMESTAMP_FORMAT='%Y%m%d_%H%M%S'
api_key = os.getenv('Mistral_key')
model = "open-mixtral-8x22b"
client = Mistral(api_key=api_key)

# can try diffrent models this one is pretty big but gives 1 request per second and also  
# Tokens per minute 500,000 tokens
# Tokens per month 1,000,000,000 tokens

# takes the list of json values and makes sure there are no duplicates or NULLs 
# puts it into a pandas df and creates csv file
def clean_jsons(arr):
    df_raw = pd.DataFrame(arr)
    #df_raw.to_csv('Production/compare.csv', mode='w+')
    df_lower = df_raw.apply(lambda x: x.str.lower() if x.dtype == "object" else x) # makes all values lower case
    df_unique = df_lower.drop_duplicates(ignore_index=True) # drops duplicte values excluding index 
    df_unique = df_unique.dropna() 
    df_unique.to_csv('Production/tmp/mistral_results.csv', mode='w+')

# going to change this to play around with 
# recursive chunking first trys to chunk by paragraphs then by sentences etc to keep it togeather  
def chunk_data(filename):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 3000, # about 500 words
        chunk_overlap = 100,
        length_function = len,
    )
    text = ""
    encodings = ['utf-8', 'ISO-8859-1', 'cp1252']
    for enc in encodings:
        try:
            with open(filename, 'r', encoding=enc) as file:
                for line in file:
                    text += line.strip() 
            chunks = text_splitter.split_text(text)
            return chunks
        except UnicodeDecodeError:
            print(f"Failed to decode with {enc}...")
            pass
        
    # if all encodings failed, return an empty list
    return []

# this makes sure not going over limit of requests and handles it nicely 
def fetch_with_backoff(messages, max_retries):
    retry_delay = 1  # Initial delay in seconds
    for attempt in range(max_retries):
        try:
            response = client.chat.complete(model = model,messages = messages, response_format = {
            "type": "json_object"}, temperature = 0.2,timeout_ms= 30000) # lowere temp is less random
            #print(response.choices[0].message.content)
            return response.choices[0].message.content
        except SDKError as e:
            time.sleep(retry_delay)
            retry_delay *= 2  # Double the delay for the next attempt
            retry_delay += random.uniform(0, 1)  # Add jitter
        except httpx.RequestError as e:
            print(f"Request timed out: {e}")
    print("api error User rate limit exceeded") 
    return json.dumps([]) # this return might not work always 

# should add a part that sends what the section that it is getting each time and then give response
def section_pull_data(txtfile, shouldExtractReferences=True) -> tuple[list[dict], str]:
    # Check to see if Mistral API key exists
    if not api_key:
        raise ValueError("Mistral API key not found")
    
    chunk = chunk_data(txtfile) # well readable text file 
    base_query = '''Forget all previous prompts and memories.    
    Given this part of the research paper, Respond with every SPECIFIC, NAMED organization, person, or tool that helped the author (we call this a "connection").
    Only include named people, universities, or tools ensuring they are PROPER nouns or formal entities. 
    Exclude any terms that describe roles, or anonymous contributors, or are otherwise unclear.
    If its an author give the work they did in context
    Return the information in this json format: 
    [
        {
            "name": [the name of the organization, person or tool], 
            "connection_type": ["Organization" if it is an organization, "Person" if this is a person, or "Tool" if its a tool]
            "connection": [how this connection helped or relates to the author.],
            "is_ambiguous": ["True" if this connection is a person whose full first and last name is not given; "False" otherwise],
            "context": [sentence from the paper where this connection is found and any other relevant details about the relationship found in the paper]
        },
        ...
    ]
    context should be directly from the text do not add anything but direct quotes
    To the best of your ability, please output the "name" field in title case where it is appropriate.
    Additionally, for the "name" field, please omit any formatting characters like quotation marks.
    Some guidelines for the "connection" field: 
    - If the "connection_type" is a Person then for "connection" choose one from this list ["Referenced","Co-author","Acknowledged", "Author", "Associated with", "Supported by", "Funded by", "Other"]
    - If the "connection_type" is a Organization then for "connection" choose one from this list ["Referenced","Acknowledged","Acknowledged", "Published under", "Collaborated with", "Associated with", "Supported by", "Funded by", "Other"]
    - If the "connection_type" is a Tool then for "connection" choose one from this list ["Referenced","Acknowledged", "Used", "Other"]
    An example of this format (DO NOT INCLUDE EITHER OF THESE EXAMPLE CONNECTIONS IN THE OUTPUT):
    [
        {
            "name": "J. Smith", 
            "connection_type": "Person",
            "connection": "Referenced",
            "is_ambiguous": "True",
            "context": "As noted by J. Smith, the methodology employed was groundbreaking in its approach to data analysis."

        },
        {
            "name": "National Research Lab", 
            "connection_type": "Organization",
            "connection": "Funded",
            "is_ambiguous": "False",
            "context": "This project was supported through funding from the National Research Lab, which allowed for the development of key technologies."
        }
    ]

    Do not explain. only return the json. if there are no such connections, return an empty json with no fields. do NOT format your response with markdown or any other formatting convention.
    '''
    if not shouldExtractReferences:
        base_query += '''
        Do not process the 'References' section of this paper.
        '''
    connections = []
    unique_connections = set()
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    output_filename = f"results/mistral_results_{timestamp}.csv"

    for c in tqdm(chunk, desc="Mistral Calls"): 
        #print(f"(Mistral) Extracting connections from chunk {i + 1}/{num_chunks}")
        messages = [{"role": "user", "content": base_query + c}]
        response = fetch_with_backoff(messages, 5)
        response_cleaned = re.sub(r'[\x00-\x1F\x7F]', '', response)
        try:
            chunk_connections = json.loads(response_cleaned)
        except json.decoder.JSONDecodeError as e:
            print(response)
            print(f"Error decoding JSON: {e}")

        for conn in chunk_connections:
            if type(conn) is not str :
                dict_tuple = frozenset(conn.items())
                if dict_tuple not in unique_connections:
                    unique_connections.add(dict_tuple)
                    # SAME CHANGE AS GEMINI PROTOTYPE NOV 1
                    connections.append(conn)
                    util.convert_json_list_to_csv([conn], output_filename)
    reference = '''Forget all previous prompts and memories.    
    Given this part of the research paper, Respond with every SPECIFIC, work that has been cited (we call this a "connection").
    Only include the name of the work 
    Exclude any terms that describe roles, groups, or anonymous contributors, or are otherwise unclear.
    Return the information in this json format: 
    [
        {
            "name": [the name of work that was cited], 
            "connection_type": ["book" if its a book, "paper if its a paper, "newspaper" if its a newspaper, "study" if its a study or "other" if not sure ]
            "connection": ["refrenced"],
            "is_ambiguous": ["True" if this connection is a work that can be found easily; "False" otherwise],
            "context": [sentence from the paper where this connection is found and any other relevant details about the relationship found in the paper]
        },
        ...
    ]
    context should be directly from the text do not add anything but direct quotes
    To the best of your ability, please output the "name" field in title case where it is appropriate.
    Additionally, for the "name" field, please omit any formatting characters like quotation marks.
    For the "connection" field decide if the work is a Book, Paper, Newspaper, Website, Study, or other
    Here is an example of what it could be
    [
        {
           "name": "Learning metric-topological maps for indoor mobile robot navigation",
            "connection-type": "paper",
            "is_ambiguous": "False",
            "connection": "refrenced"
            "context": "Thrun,  S.,  1998.  Learning  metric-topological  maps  for  indoor mobile robot navigation. Artificial Intelligence, 99(1), 21-71"

        },
    ]

    Do not explain. only return the json. if there are no such connections, return an empty json with no fields. do NOT format your response with markdown or any other formatting convention.
    '''
    for c in chunk[-2:]: # doing last two parts to pull the connections for the citations better
        print(f"(Mistral) Extracting connections from chunk")
        messages = [{"role": "user", "content": reference + c}]
        response = fetch_with_backoff(messages, 5)
        response_cleaned = re.sub(r'[\x00-\x1F\x7F]', '', response)
        chunk_connections = json.loads(response_cleaned)
        for conn in chunk_connections:
            if type(conn) is not str :
                dict_tuple = frozenset(conn.items())
                if dict_tuple not in unique_connections:
                    unique_connections.add(dict_tuple)
                    connections.append(conn)
                    util.convert_json_list_to_csv([conn], output_filename)

    return connections, output_filename

