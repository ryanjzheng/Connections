import requests
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv('CoreAPI_KEY')

# This function retrieves the full text of the paper with the given title from the Core API.
# It returns a list with the status code and the filename of the retrieved full text.
def coreAPI(title: str, api_key: str) -> list:
    base_url = "https://api.core.ac.uk/v3/search/works"
    
    params = {
        "q": f"title:({title})",
        "limit": 1,
        "fulltext": True
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    response = requests.get(base_url, params=params, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data["totalHits"] > 0:
            paper = data["results"][0]
            if "fullText" in paper and paper["fullText"] is not None:
                return [1, paper["fullText"]]
            else:
                return [0, "Full text not available for this paper."]
        else:
            return [0, "No matching papers found."]
    else:
        return [500, f"Error: {response.status_code} - {response.text}"]

# This function retrieves the PDF of the paper with the given name and authors from Core.
# It returns a list with the status code and the filename of the retrieved PDF.
def retrievePDF(paperName: str, authors: list[str], filename = "coreAPI.txt") -> list:
    filename = f"./tmp/{filename}"
    full_text = coreAPI(paperName, api_key)
    if full_text[0] == 1:
        with open(filename, "w", encoding="UTF-8") as f:
            f.write(full_text[1])
        full_text[1] = filename

    return full_text