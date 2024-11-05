from flask import Flask, jsonify, request, make_response
# from google_scholar_prototype import demo
# from gemini_prototype import section_pull_data

import google_scholar_prototype
import getting_full_text_prototype
import gemini_prototype
import mistral_prototype
import arXiv
import semantic_scholar_API
import util

app = Flask(__name__)

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

    paperGrabs = [("Semantic Scholar", semantic_scholar_API.demo),
                  ("arXiv", arXiv.demo), 
                  ("CoreAPI", getting_full_text_prototype.demo), 
                  ("Google Scholar", google_scholar_prototype.demo)]
    
    foundPaper = False
    api_server_fails = 0   # for tracking whether or not ALL API calls errored out

    for grabMethod in paperGrabs:
        print(f"Attempting to grab paper '{title}' from {grabMethod[0]}")
        f = grabMethod[1](title, authors)

        # f[0] = 1 indicates the paper was successfully retrieved.
        # all other values indicate error conditions.
        if f[0] != 1:
            error_message = f[1]
            # Internal response code of 500 indicates the API failed to respond
            # i.e. it broke/errored out
            if f[0] == 500:
                api_server_fails += 1
            print(f"Failed to grab paper from {grabMethod[0]}: {error_message}")
            continue

        print(f"Found paper from {grabMethod[0]}! Filename: {f[1]}")
        foundPaper = True
        break
        
    if foundPaper:
        filename = f[1]
        output = mistral_prototype.section_pull_data(filename)
        print("Attempting to get paper references from Semantic Scholar")
        output += semantic_scholar_API.getPaperReferences(title, authors, sem_scholar_id)
        return util.makeServerResponse(200, "success!", output)
    else:
        # If all API calls errored out, return code 500
        if api_server_fails == len(paperGrabs):
            return util.makeServerResponse(500, "All database API calls failed. Try again.")

        # unable to find open access version of paper: code 422
        return util.makeServerResponse(422, "Failed to find an open access version of the specified paper.")