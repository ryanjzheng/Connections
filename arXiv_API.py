import requests
import gzip
import shutil
from os import remove

# This function queries the arXiv API for the paper with the given title.
def querySite(url: str, maxAttempts = 5) -> requests.models.Response:
    attempts = 0
    success = False
    while not success and attempts < maxAttempts:
        attempts += 1
        try:
            data = requests.get(url)
            success = True
        except requests.exceptions.ConnectionError:
            print(f"Connection Failed, retrying ({attempts}/{maxAttempts})")

    if not success:
        return None

    if (data.status_code != 200):
        print("Website not responding, report this error.")
        return None
    
    return data

# This function extracts the source link from the arXiv API response.
def getSourceLink(content: bytes) -> str:
    if b"http://arxiv.org/abs" not in content:
        return None
    
    link = content[content.index(b"http://arxiv.org/abs"):]
    link = link[:link.index(b"</id>")].decode()
    link = link.replace("abs", "src")

    return link

# This function downloads the file from the given URL and saves it to the given filename.
def downloadFile(url: str, filename: str):
    with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

# This function unzips the given file and saves it to the given output filename.
def unzip(zipName: str, output: str):
    with gzip.open(zipName, 'rb') as s_file, \
            open(output, 'wb') as d_file:
        shutil.copyfileobj(s_file, d_file)

# This function extracts the latex content from the given file.
def extractLatex(latexFile: str):
    with open(latexFile, "rb") as f:
        latex = f.read()
        latex = latex[latex.index(rb"\documentclass"):latex.index(rb"\end{document}") + len(rb"\end{document}")]
    with open(latexFile, "wb") as f:
        f.write(latex)

# This function retrieves the PDF of the paper with the given name and authors from arXiv.
# It returns a list with the status code and the filename of the retrieved PDF.
def retrievePDF(paperName: str, authors: list[str], filename = "arXiv.tex") -> list:
    url = f'http://export.arxiv.org/api/query?search_query=ti:"{paperName}"&start=0&max_results=1'
    
    data = querySite(url)

    # If arXiv failed to respond, return 500 to indicate server error
    if data == None:
        return [500, "Failed to retrieve data from arXiv."]

    link = getSourceLink(data.content)
    if link == None:
        return [0, "Could not find matching article."]
    
    zipFile = f"./tmp/arXiv.gz"
    latexFile = f"./tmp/{filename}"
    downloadFile(link, zipFile)
    unzip(zipFile, latexFile)
    extractLatex(latexFile)
    remove(zipFile)
    return [1, latexFile]