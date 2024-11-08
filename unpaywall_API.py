import requests
from typing import List
import fitz  # PyMuPDF

# precondition that is already checked and met: title and authors are given 
def retrievePDF(title: str, authors:List[str], file="unpaywall.txt") -> list:
    filename = f"./tmp/{file}"
    try:
        params = {
            'query': title,
            'email': 'placeholder@placeholder.com'
        }

        baseurl = "https://api.unpaywall.org/v2/search"
        response = requests.get(baseurl, params=params)

        if response.status_code != 200:
            return [500, "Error: Failed unpaywall API call."]

        query_results = response.json()['results']

        if not query_results:
            return [0, "Unpaywall API found no papers."]

    # download first result that meets all requirements: has OA link and authors mathch
        for result_obj in query_results:
            result_obj = result_obj["response"]
            if "best_oa_location" in result_obj and result_obj["best_oa_location"] is not None and "url_for_pdf" in result_obj["best_oa_location"]  and result_obj["best_oa_location"]["url_for_pdf"] is not None: 
                if "z_authors" in result_obj and result_obj["z_authors"] is not None and author_matches(authors, result_obj["z_authors"]):
                    pdf_oa_url = result_obj["best_oa_location"]["url_for_pdf"]
                    response = requests.get(pdf_oa_url)
                    
                    if response.status_code == 200:
                        pdf_data = response.content
                        pdf_doc = fitz.open(stream=pdf_data, filetype="pdf")
                        with open(filename, 'w') as f:
                            for page_num in range(pdf_doc.page_count):
                                page = pdf_doc[page_num]
                                pdf_text = page.get_text()  # Append the text of each page
                                f.write(pdf_text)
                        pdf_doc.close()
                        return [1, filename]

        return [0, "Unpaywall API found no papers."]
    except Exception as e:
        return [500, "Error: Failed unpaywall API call."]


# Bool function that checks if the given authors match the authors in the response
def author_matches(given_authors: List[str], reponse_authors: List[dict]) -> bool:
    for given_author in given_authors:
        given_author = set(given_author.lower().split())
        matched = False
        for response_author_obj in reponse_authors:
            response_author = response_author_obj['given'] if 'given' in response_author_obj else ""
            response_author += " "+response_author_obj['family'] if 'family' in response_author_obj is not None else ""
            if response_author == "": 
                continue
            response_author = set(response_author.lower().split())

            if(response_author.issubset(given_author) or given_author.issubset(response_author)):
                matched = True
        if not matched:
            return False
    return True




