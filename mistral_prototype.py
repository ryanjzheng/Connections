# use venv
# pip install google-generativeai
# pip install PyPDF2
# pip install langchain-text-splitters
# pip install python-dotenv
import time
import random
import pandas as pd
import google.generativeai as genai
import os
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter 
from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
import json
import util

load_dotenv()

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
    #df_raw.to_csv('Prototype/compare.csv', mode='w+')
    df_lower = df_raw.apply(lambda x: x.str.lower() if x.dtype == "object" else x) # makes all values lower case
    df_unique = df_lower.drop_duplicates(ignore_index=True) # drops duplicte values excluding index 
    df_unique = df_unique.dropna() 
    df_unique.to_csv('Prototype/results/mistral_results.csv', mode='w+')

# going to change this to play around with 
# recursive chunking first trys to chunk by paragraphs then by sentences etc to keep it togeather  
def chunk_data(file):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 3000, # about 500 words
        chunk_overlap = 100,
        length_function = len,
    )
    text = ""
    with open(file, 'r', encoding="utf8") as file:
        for line in file:
            text += line.strip() 
    chunks = text_splitter.split_text(text)
    return chunks

# this makes sure not going over limit of requests and handles it nicely 
def fetch_with_backoff(messages, max_retries):
    retry_delay = 1  # Initial delay in seconds
    for attempt in range(max_retries):
        try:
            response = client.chat.complete(model = model,messages = messages, response_format = {
            "type": "json_object"}, temperature = 0.2) # lowere temp is less random
            #print(response.choices[0].message.content)
            return response.choices[0].message.content
        except SDKError as e:
            time.sleep(retry_delay)
            retry_delay *= 2  # Double the delay for the next attempt
            retry_delay += random.uniform(0, 1)  # Add jitter
    print("api error User rate limit exceeded") 
    return json.dumps([]) # this return might not work always 

# should add a part that sends what the section that it is getting each time and then give response
def section_pull_data(txtfile):
    chunk = chunk_data(txtfile) # well readable text file 
    base_query = '''Forget all previous prompts and memories.    
    Given this part of the research paper, Respond with every SPECIFIC, NAMED organization, person, or lab that helped the author (we call this a "connection").
    Only include named people, universities, or labs, ensuring they are PROPER nouns or formal entities. 
    Exclude any terms that describe roles, groups, or anonymous contributors, or are otherwise unclear.
    Return the information in this json format: 
    [
        {
            "name": [the name of the organization or person], 
            "connection_type": ["Organization" if this is an organization that helped the author; "Person" if this is a person that helped the author]
            "connection": [how this connection helped or relates to the author.],
            "is_ambiguous": ["True" if this connection is a person whose full first and last name is not given; "False" otherwise]
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

    Do not explain. only return the json. if there are no such connections, return an empty json with no fields. do NOT format your response with markdown or any other formatting convention.
    '''
    connections = []
    unique_connections = set()
    num_chunks = len(chunk)
    for (i, c) in enumerate(chunk): 
        print(f"(Mistral) Extracting connections from chunk {i + 1}/{num_chunks}")
        messages = [{"role": "user", "content": base_query + c}]
        response = fetch_with_backoff(messages, 5)
        chunk_connections = json.loads(response)

        for conn in chunk_connections:
            dict_tuple = frozenset(conn.items())
            if dict_tuple not in unique_connections:
                unique_connections.add(dict_tuple)
                # SAME CHANGE AS GEMINI PROTOTYPE NOV 1
                # connections.append(conn)
                util.convert_json_list_to_csv([conn], "Prototype/results/mistral_results.csv")

    util.convert_json_list_to_csv(connections, "Prototype/results/mistral_results.csv")
    return connections
       
# section_pull_data("Prototype/paper_extraction_output.txt")
# section_pull_data("Prototype/testPaper.txt")

