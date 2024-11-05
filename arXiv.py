import requests
import gzip
import shutil

FILE_NAME = "paper"

def querySite(url, maxAttempts=10):
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

def getSourceLink(content):
    if b"http://arxiv.org/abs" not in content:
        return None
    
    link = content[content.index(b"http://arxiv.org/abs"):]
    link = link[:link.index(b"</id>")].decode()
    link = link.replace("abs", "src")

    return link

def downloadFile(url, filename):
    with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

def unzip(zipName, output):
    with gzip.open(zipName, 'rb') as s_file, \
            open(output, 'wb') as d_file:
        shutil.copyfileobj(s_file, d_file)

def extractLatex(latexFile):
    with open(latexFile, "rb") as f:
        latex = f.read()
        latex = latex[latex.index(rb"\documentclass"):latex.index(rb"\end{document}") + len(rb"\end{document}")]
    with open(latexFile, "wb") as f:
        f.write(latex)

def demo(paperName, authors):
    # paperName = PAPER_NAME # TODO: arXiv search does not work with non-alphanumeric characters
    url = f'http://export.arxiv.org/api/query?search_query=ti:"{paperName}"&start=0&max_results=1'
    
    data = querySite(url)

    # If arXiv failed to respond, return 500 to indicate server error
    if data == None:
        return [500, "Failed to retrieve data from arXiv."]

    link = getSourceLink(data.content)
    if link == None:
        return [0, "Could not find matching article."]
    
    zipFile = f"{FILE_NAME}.gz"
    latexFile = f"{FILE_NAME}.tex"
    downloadFile(link, zipFile)
    unzip(zipFile, latexFile)
    extractLatex(latexFile)

    return [1, latexFile]