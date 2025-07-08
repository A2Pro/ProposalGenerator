from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from openai import OpenAI
import re
import os
import time
import base64
import glob
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

os.makedirs("screenshots", exist_ok=True)


def get_first_five_links():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        page.goto("https://www.google.com")
        page.goto("https://sam.gov/search/?page=1&pageSize=25&sort=-modifiedDate&sfm%5BsimpleSearch%5D%5BkeywordRadio%5D=ALL&sfm%5Bstatus%5D%5Bis_active%5D=true&sfm%5BagencyPicker%5D%5B0%5D%5BorgKey%5D=100000000&sfm%5BagencyPicker%5D%5B0%5D%5BorgText%5D=097%20-%20DEPT%20OF%20DEFENSE&sfm%5BagencyPicker%5D%5B0%5D%5BlevelText%5D=Dept%20%2F%20Ind.%20Agency&sfm%5BagencyPicker%5D%5B0%5D%5Bhighlighted%5D=true")
        
        time.sleep(3)
        source = page.content()
        
        with open("source.txt", "w", errors="ignore") as f:
            f.write(source)
        
        browser.close()

    with open("source.txt", "r", encoding="utf-8", errors="ignore") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    opp_links = soup.find_all('a', href=re.compile(r'^/opp/.+/view$'))
    base_url = "https://sam.gov"
    first_5_links = [base_url + link['href'] for link in opp_links[:5]]

    return(first_5_links)


def get_gpt_response(content):

    prefill = """2. Generate a fake bid/proposal outline from the following information that the government has posted - Create a realistic proposal structure that would respond to this opportunity, including:
   - Executive summary points
   - Technical approach sections
   - Key deliverables
   - Rough timeline
   - Any compliance requirements mentioned."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": prefill + " Here's the information: " + content
            }
        ],
        max_tokens=2000 
    )
    return response.choices[0].message.content

def get_text(link):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        page.goto(link)
        time.sleep(2)
        source = page.content()

    return source

def parse_contract_from_html(html_content):
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    response = ""
    response+=("CONTRACT OPPORTUNITY DETAILS")
    
    
    
    
    title_text = None
    h2_headers = soup.find_all('h2')
    if h2_headers:
        
        first_h2 = h2_headers[0]
        title_candidates = []
        for element in soup.descendants:
            if element == first_h2:
                break
            if hasattr(element, 'string') and element.string:
                text = element.string.strip()
                if text and len(text) > 5:  
                    title_candidates.append(text)
        
        
        if title_candidates:
            title_text = ' '.join(title_candidates)
            title_text = re.sub(r'\s+', ' ', title_text).strip()
    
   
    
    
    notice_id_elem = soup.find('div', id='header-solicitation-number')
    if notice_id_elem:
        description = notice_id_elem.find('div', class_='description')
        if description:
            notice_id = description.get_text(strip=True)
            response+=(f"\n Notice ID: {notice_id} \n")

    
    
    response+=("GENERAL INFORMATION \n")
    
    general_info_mapping = {
        'general-type': 'Contract Opportunity Type',
        'general-original-published-date': 'Original Published Date',
        'general-original-response-date': 'Original Date Offers Due',
        'general-archiving-policy': 'Inactive Policy',
        'general-original-archive-date': 'Original Inactive Date',
        'general-special-legislation': 'Initiative'
    }
    
    for element_id, label in general_info_mapping.items():
        element = soup.find('li', id=element_id)
        if element:
            
            strong_tag = element.find('strong')
            if strong_tag:
                strong_tag.extract()
            
            text = element.get_text(strip=True)
            text = re.sub(r'\s+', ' ', text)  
            
            if text and text.lower() != 'none':
                response+=(f"{label}: {text}\n")
    
    response+=("CLASSIFICATION\n")
    
    classification_mapping = {
        'classification-original-set-aside': 'Original Set Aside',
        'classification-classification-code': 'Product Service Code',
        'classification-naics-code': 'NAICS Code',
        'classification-pop': 'Place of Performance'
    }
    
    for element_id, label in classification_mapping.items():
        element = soup.find('li', id=element_id)
        if element:
            
            strong_tag = element.find('strong')
            if strong_tag:
                strong_tag.extract()
            
            text = element.get_text(strip=True)
            text = re.sub(r'\s+', ' ', text)
            
            if text:
                response+=(f"{label}: {text}\n")
    
    
    
    response+=("CONTRACTING OFFICE ADDRESS\n")
    
    contracting_office_div = soup.find('div', id='-contracting-office')
    if contracting_office_div:
        
        address_items = contracting_office_div.find_all('li')
        for item in address_items:
            address_line = item.get_text(strip=True)
            if address_line:
                response+=(f'{address_line} \n')
    
    
    
    response+=("PRIMARY POINT OF CONTACT\n")
    
    primary_poc_div = soup.find('div', id='contact-primary-poc')
    if primary_poc_div:
        
        name_elem = primary_poc_div.find('li', id='contact-primary-poc-full-name')
        if name_elem:
            name = name_elem.get_text(strip=True)
            response+=(f"Name: {name} \n")
        
        email_elem = primary_poc_div.find('li', id='contact-primary-poc-email')
        if email_elem:
            email_link = email_elem.find('a')
            if email_link:
                email = email_link.get_text(strip=True)
                response+=(f"Email: {email} \n")
        
        
        phone_elem = primary_poc_div.find('li', id='contact-primary-poc-phone')
        if phone_elem:
            phone_text = phone_elem.get_text(strip=True)
            
            phone_match = re.search(r'(\d{10})', phone_text)
            if phone_match:
                phone = phone_match.group(1)
                formatted_phone = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
                response+=(f"Phone: {formatted_phone}\n")
    
    response+=("SECONDARY POINT OF CONTACT \n")
    secondary_poc_div = soup.find('div', id='contact-secondary-poc')
    if secondary_poc_div:
        
        name_elem = secondary_poc_div.find('li', id='contact-secondary-poc-full-name')
        if name_elem:
            name = name_elem.get_text(strip=True)
            response+=(f"Name: {name}\n")
        
        
        email_elem = secondary_poc_div.find('li', id='contact-secondary-poc-email')
        if email_elem:
            email_link = email_elem.find('a')
            if email_link:
                email = email_link.get_text(strip=True)
                response+=(f"Email: {email}\n")
        
        
        phone_elem = secondary_poc_div.find('li', id='contact-secondary-poc-phone')
        if phone_elem:
            phone_text = phone_elem.get_text(strip=True)
            phone_match = re.search(r'(\d{10})', phone_text)
            if phone_match:
                phone = phone_match.group(1)
                formatted_phone = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
                response+=(f"Phone: {formatted_phone}\n")
    
    
    
    
    response+=("DEPARTMENT HIERARCHY\n")
    
    hierarchy_div = soup.find('div', id='header-hierarchy-level')
    if hierarchy_div:
        
        content_div = hierarchy_div.find('div', class_='content')
        if content_div:
            headers = content_div.find_all('div', class_='header')
            descriptions = content_div.find_all('div', class_='description')
            
            
            for i, header in enumerate(headers):
                header_text = header.get_text(strip=True)
                
                if i < len(descriptions):
                    desc_text = descriptions[i].get_text(strip=True)
                    if header_text and desc_text:
                        response+=(f"{header_text}: {desc_text}\n")
    return response


def main():
    print("Welcome to proposalgenerator! We automatically write proposals for you based on a contract. \n Please provide a link or choose one of the following:")
    for link in get_first_five_links():
        print(link)

    link = input("Input a link: ")
    source = get_text(link)
    response = parse_contract_from_html(source)
    final = get_gpt_response(response)
    print(final)
main()
