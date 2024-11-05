import requests
from bs4 import BeautifulSoup
import PyPDF2
import pdfplumber
import io
from urllib.parse import urljoin
import sys

def search_paper(title):
    print(f"Searching for paper: {title}")
    query = f"https://scholar.google.com/scholar?q={title.replace(' ', '+')}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    response = requests.get(query, headers=headers)
    print(f"Search response status code: {response.status_code}")

    # If Google Scholar returned a bad response, return the response code
    if response.status_code != 200:
        return None, response.status_code
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.endswith('.pdf') or '/pdf' in href:
            print(f"Found PDF link: {href}")
            return href, response.url
        elif href.startswith('http') and 'google' not in href:
            print(f"Found external link: {href}")
            return href, href

    # Return None and the response code 200
    return None, response.status_code

def download_pdf(url, base_url):
    full_url = urljoin(base_url, url)
    print(f"Attempting to download PDF from: {full_url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    response = requests.get(full_url, headers=headers)
    print(f"Download response status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Failed to download PDF from: {full_url}")
        return None
    return io.BytesIO(response.content)

def extract_text_pypdf2(pdf_file):
    print("Attempting to extract text from PDF using PyPDF2")
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        print(f"PDF has {len(reader.pages)} pages")
        text = ""
        for i, page in enumerate(reader.pages):
            print(f"Extracting text from page {i+1}")
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"  # Add extra newline between pages
        return text.strip()
    except Exception as e:
        print(f"Error extracting text with PyPDF2: {str(e)}")
        return None

def extract_text_pdfplumber(pdf_file):
    print("Attempting to extract text from PDF using pdfplumber")
    try:
        with pdfplumber.open(pdf_file) as pdf:
            print(f"PDF has {len(pdf.pages)} pages")
            text = ""
            for i, page in enumerate(pdf.pages):
                print(f"Extracting text from page {i+1}")
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"  # Add extra newline between pages
        return text.strip()
    except Exception as e:
        print(f"Error extracting text with pdfplumber: {str(e)}")
        return None

def get_paper_text(title):
    pdf_url, base_url = search_paper(title)

    if not pdf_url:
        # base_url represents the error code if pdf_url is None
        # dont have time to fix/make it better
        if base_url == 200:
            return [0, "No suitable link found from Google Scholar"]
        else:
            return [500, "Google Scholar API call failed"]
        
    pdf_file = download_pdf(pdf_url, base_url)

    if not pdf_file:
        return [500, "Failed to download the PDF."]
    
    # Try PyPDF2 first
    text = extract_text_pypdf2(pdf_file)
    
    # If PyPDF2 fails or returns empty text, try pdfplumber
    if not text:
        pdf_file.seek(0)  # Reset file pointer
        text = extract_text_pdfplumber(pdf_file)
    
    if not text:
        return [0, "Unable to extract text from PDF using both PyPDF2 and pdfplumber"]
    
    # Post-processing to remove single-character lines and merge short lines
    lines = text.split('\n')
    processed_lines = []
    buffer = ""
    for line in lines:
        stripped_line = line.strip()
        if len(stripped_line) <= 1:
            continue
        if len(buffer) + len(stripped_line) < 80:
            buffer += " " + stripped_line
        else:
            if buffer:
                processed_lines.append(buffer.strip())
            buffer = stripped_line
    if buffer:
        processed_lines.append(buffer.strip())
    
    return [1, '\n'.join(processed_lines)]

def demo(title, authors):
    paper_title = title
    print(f"Starting process for paper: {paper_title}")

    paper_text = get_paper_text(paper_title)
    if paper_text[0] != 1:
        return paper_text
    
    # Redirect stdout to capture all print statements
    original_stdout = sys.stdout
    sys.stdout = io.StringIO()

    # Get the captured output
    output = sys.stdout.getvalue()
    
    # Restore stdout
    sys.stdout = original_stdout

    # Write the output and paper text to a file
    filename = 'paper_extraction_output.txt'
    with open(filename, 'w', encoding='utf-8') as f:
        #f.write(output) # commented out for now so only paper sent 
        f.write("\nFinal result:\n")
        f.write(paper_text[1])

    return [1, filename]
# if __name__ == "__main__":
#     main()