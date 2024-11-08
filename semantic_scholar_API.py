import util
import time

# Given the title and at least one author of a paper, returns the Semantic 
# Scholar paper ID of the most relevant paper that contains ANY ONE of the given authors
def getPaperID(given_title: str, given_authors: list[str]) -> tuple[int, str]:
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/search"
    fields = ['paperId', 'title', 'authors']
    link = endpoint + "?query=" + given_title + "&limit=5&fields=" + ','.join(fields)
    response, got_response = util.fetchWithBackoff(link)

    if got_response:
        # If Semantic Scholar finds no matching articles, return failure
        if response['total'] == 0:
            return 0, "Could not find matching article."
        papers = response['data']

        # For now, just return the best match. Will consider ways to 
        # incorporate authors after CDR
        best_matching_paper = papers[0]
        id = best_matching_paper['paperId']
        print(f'Got Semantic Scholar ID {id}')
        return 1, id
    else:
        return 500, "Failed to get response from Semantic Scholar"

# Given a Semantic Scholar paper ID, returns its open access pdf link if it is 
# available; returns empty string otherwise
def getOpenAccessLink(id: str) -> tuple[int, str]:
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/"
    fields = ["isOpenAccess", "openAccessPdf"]
    link = endpoint + id + "?fields=" + ",".join(fields)
    print("Attempting to find open access link from Semantic Scholar...")

    response, got_response = util.fetchWithBackoff(link)

    if got_response:
        isOpenAccess = response['isOpenAccess']
        
        if isOpenAccess and response['openAccessPdf'] is not None:
            pdf_url = response['openAccessPdf']['url']
            print(f'Got url: {pdf_url}')
            return 1, pdf_url
        else:
            return 0, "No open access pdf found from Semantic Scholar"
    else:
        return 500, "Failed to get response from Semantic Scholar"

# Given title and list of authors for a paper, returns a list of JSON-like objects
# where each object is a reference of the paper.
def getPaperReferences(title: str, authors: list[str], id="") -> list[dict]:
    endpoint = 'https://api.semanticscholar.org/graph/v1/paper/'
    fields = ['authors', 'title']

    # Semantic scholar paper id can be optionally specified in GET request.
    # Only need to try to fetch the id if it wasn't given.
    if not id:
        code, id = getPaperID(title, authors)
        if code != 1:
            print("Failed to get Semantic Scholar paper ID.")
            return []
    
    link = endpoint + id + "/references?fields=" + ','.join(fields)

    response, got_response = util.fetchWithBackoff(link)
        
    if not got_response:
        print("Failed to get references from Semantic Scholar references.")
        return []
    
    print("Found references from Semantic Scholar! Processing...")
    response = response['data']
    refs_and_authors_json = processReferencesAndAuthors(response)
    return refs_and_authors_json
    
# Given a list of references, returns a list of connections formed from the 
# referenced papers and their authors.
# See https://api.semanticscholar.org/api-docs/#tag/Paper-Data/operation/get_graph_get_paper_references
# for input schema.
def processReferencesAndAuthors(papers: list[dict]) -> list[dict]:
    res = []
    
    for paper in papers:
        ref = paper['citedPaper']
        ref_title = ref['title']
        ref_connection = {
            "name" : util.tryDecodings(ref_title),
            "connection-type" : "Paper",
            "connection" : "referenced", 
            "is-ambiguous" : "False"
        }

        res.append(ref_connection)

        # process the authors of the reference
        ref_authors = ref['authors']
        for auth in ref_authors:
            auth_name = util.tryDecodings(auth['name'])
            auth_connection = {
                "name" : auth_name, 
                "connection-type" : "Person",
                "connection" : "referenced",
                "is-ambiguous" : util.nameIsAmbiguous(auth_name)
            }

            res.append(auth_connection)

    return res

# Similar to the function in core_API.py, this function retrieves the PDF of the
# paper with the given name and authors from Semantic Scholar.
def retrievePDF(paperName: str, authors: list[str], filename: str) -> list:
    code, msg = getPaperID(paperName, authors)
    if code != 1:
        return [code, msg]
    res, url = getOpenAccessLink(msg)
    if res == 1:
        file = util.download_pdf(url)
        if file is None:
            return [500, f"Failed to download PDF from {url}"]
        text = util.extract_text_pypdf2(file)
        if text is None:
            return [500, "Failed to extract PDF with PyPDF2"]
        
        filename = f'./results/{filename}'
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"Semantic Scholar output at {filename}")
        return [1, filename]
    else:
        return [res, "Failed to get open access link."]
