import requests
import os

def coreAPI(title, api_key):
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

# Example usage
api_key = "jXB4ITAvyS68NnHC2Ywmu5bKstEpgJ7M"
outputName = "output.txt"

def demo(paperName, authors):
    full_text = coreAPI(paperName, api_key)
    if full_text[0] == 1:
        with open(outputName, "w", encoding="UTF-8") as f:
            f.write(full_text[1])
        full_text[1] = outputName

    return full_text