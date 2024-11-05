from nameparser import HumanName
import util
import time

# paperName = "ReBound An OpenSource 3D Bounding Box Annotation Tool for Active Learning"
# paperAuthor = "James Dfafeaw"

# Given the title and at least one author of a paper, returns the Semantic 
# Scholar paper ID of the most relevant paper that contains ANY ONE of the given authors
def getPaperID(given_title: str, given_authors: list[str]) -> tuple[int, str]:
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/search"
    fields = ['paperId', 'title', 'authors']
    link = endpoint + "?query=" + given_title + "&limit=5&fields=" + ','.join(fields)
    response, got_response = util.fetchWithBackoff(link)

    if response['total'] == 0:
        return 0, "Could not find matching article."

    if got_response:
        papers = response['data']

        # convert string names to HumanNames for comparison
        given_authors_as_hn = [HumanName(auth) for auth in given_authors]

        # convert first name to only first initial
        for hn in given_authors_as_hn:
            hn.first = hn.first[0] + '.'

        for paper in papers:
            authors = paper['authors']
            for author in authors:
                author_hn = HumanName(author['name'])
                # convert first name to only first initial
                author_hn.first = author_hn.first[0] + '.'
                if any([author_hn.first == given_auth_hn.first and author_hn.last == given_auth_hn.last for given_auth_hn in given_authors_as_hn]):
                    id = paper['paperId']
                    print(f'Got id {id}')
                    return 1, id
                
        return 0, "Failed to get Semantic Scholar paper ID"
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
        
        if isOpenAccess:
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
                "is-ambiguous" : nameIsAmbiguous(auth_name)
            }

            res.append(auth_connection)

    return res

def processAuthors(authors):
    res = []

    for auth in authors:
        auth_name = util.tryDecodings(auth['name'])
        author_connection = {
            "name" : auth_name, 
            "connection-type" : "Person",
            "connection" : "author",
            "is-ambiguous" : str(nameIsAmbiguous(auth_name))
        }
        res.append(author_connection)

    return res

# checks if the first name is only specified with first initial
# def nameIsAmbiguous(name):
#     first_name = name.split()[0]

#     if first_name is not None and len(first_name) == 2 and first_name[1] == '.' and first_name[0].isalpha():
#         return "True"
#     else:
#         return "False"

# needs adjusting but using this library is probably better than what i was doing before
def nameIsAmbiguous(name_string):
    hn = HumanName(name_string)
    
    # Check if the name has multiple possible interpretations
    if hn.first and hn.last:
        return False
    
    # Check for common ambiguous cases
    if hn.first and not hn.last:
        return True
    if hn.last and not hn.first:
        return True
    if hn.first == hn.last:
        return True
    
    # Check for potential title/name confusion
    if hn.title and not hn.first:
        return True
    
    return False

# connections = getPaperReferences(paperName, [paperAuthor])
# util.convert_json_list_to_csv(connections, 'Prototype/results/semScholarReferences.csv')

def demo(title: str, authors: list[str]) -> list:
    code, msg = getPaperID(title, authors)
    if code != 1:
        return [code, msg]
    time.sleep(5)
    res, url = getOpenAccessLink(msg)
    if res == 1:
        file = util.download_pdf(url)
        text = util.extract_text_pypdf2(file)
        filename = 'Prototype/results/semantic_scholar_paper_output.txt'
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"Semantic Scholar output at {filename}")
        return [1, filename]
    else:
        return [res, "Failed to get open access link."]