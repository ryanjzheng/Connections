from flask import Flask, jsonify, request, make_response
import google_scholar_API
import core_API
import gemini_API
import mistral_API
import arXiv_API
import unpaywall_API
import semantic_scholar_API
import util
from os import listdir, remove
from os.path import isfile, join
from time import time
import threadUtil

app = Flask(__name__)

OUTPUT_DIR = "results/"
LENGTH_DIFF = 1000

@app.route("/")
def hello_world():
    return "Hello, World!"

@app.route('/papers')
def get_papers_ss():
    authors_raw = request.args.get('authors')
    authors = authors_raw.split(",") if authors_raw else None
    title = request.args.get('title')
    sem_scholar_id = request.args.get('id')

    # If user did not specify both authors and title, return code 400
    if not (authors and title):
        return util.makeServerResponse(400, "Please specify both author and title and try again.")
    
    paperGrabs = [("Semantic Scholar", semantic_scholar_API.retrievePDF, "semanticScholar.txt"),
                  ("arXiv", arXiv_API.retrievePDF, "arXiv.tex"), 
                  ("CoreAPI", core_API.retrievePDF, "coreAPI.txt"), 
                  ("Unpaywall", unpaywall_API.retrievePDF, "unpaywall.txt"), 
                  ("Google Scholar", google_scholar_API.retrievePDF, "googleScholar.txt")]

    threads = []

    timestamp = f"{time()}-"
    for grabMethod in paperGrabs:
        print(f"Attempting to grab paper '{title}' from {grabMethod[0]}")
        t = threadUtil.ThreadWithReturnValue(None, grabMethod[1], grabMethod[0], [title, authors, timestamp + grabMethod[2]])
        t.start()
        threads.append((t, grabMethod[0]))

    for (thread,name) in threads:
        thread.join()

    api_server_fails = 0
    for (thread,name) in threads:
        print("PDF fetch result:",name)
        print(thread._return)
        if thread._return[0] == 500:
            # Internal response code of 500 indicates the API failed to respond
            # i.e. it broke/errored out
            api_server_fails += 1

    outputFiles = [f for f in listdir(OUTPUT_DIR) if isfile(join(OUTPUT_DIR, f))]

    if len(outputFiles) == 0:
        # If all API calls errored out, return code 500
        if api_server_fails == len(paperGrabs):
            return util.makeServerResponse(500, "All database API calls failed. Try again.")

        # unable to find open access version of paper: code 422
        return util.makeServerResponse(422, "Failed to find an open access version of the specified paper.")

    resFiles = []
    for grabMethod in paperGrabs:
        if (timestamp + grabMethod[2]) in outputFiles:
            resFiles.append([grabMethod[0], (timestamp + grabMethod[2]), 0])

    maxLen = 0
    # Sometimes UTF-8 won't be able to read all the characters in the document.
    # Try a few common encodings, one should hopefully work.
    encodings = ['utf-8', 'ISO-8859-1', 'cp1252']
    for i in range(0, len(resFiles)):
        for enc in encodings:
            try:
                with open(OUTPUT_DIR + resFiles[i][1], "r", encoding=enc) as f:
                    resFiles[i][2] = len(f.read())
                    if resFiles[i][2] > maxLen:
                        maxLen = resFiles[i][2]
                    print(f"File from {resFiles[i][0]} has length: {resFiles[i][2]}")
                    break
            except UnicodeDecodeError:
                pass
    
    filename = resFiles[0][1]
    for f in resFiles:
        if f[2] > maxLen - LENGTH_DIFF:
            filename = OUTPUT_DIR + f[1]
            print(f"Choosing file from {f[0]}")
            break
    
    output, output_filename = mistral_API.section_pull_data(filename) # May be OUTPUT_DIR + filename
    print("Attempting to get paper references from Semantic Scholar")
    references = semantic_scholar_API.getPaperReferences(title, authors, sem_scholar_id)
    util.convert_json_list_to_csv(references, output_filename)
    output += references

    for f in outputFiles:
        remove(OUTPUT_DIR + f)

    return util.makeServerResponse(200, "", output)