import os
import uuid
import time
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.vectorstores import Chroma
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.schema import Document
import tempfile
import shutil

app = Flask(__name__)
CORS(app)
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


active_sessions = {}
TEMP_DIR = tempfile.mkdtemp()

def get_first_five_links():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto("https://sam.gov/search/?page=1&pageSize=25&sort=-modifiedDate&sfm%5BsimpleSearch%5D%5BkeywordRadio%5D=ALL&sfm%5Bstatus%5D%5Bis_active%5D=true&sfm%5BagencyPicker%5D%5B0%5D%5BorgKey%5D=100000000&sfm%5BagencyPicker%5D%5B0%5D%5BorgText%5D=097%20-%20DEPT%20OF%20DEFENSE&sfm%5BagencyPicker%5D%5B0%5D%5BlevelText%5D=Dept%20%2F%20Ind.%20Agency&sfm%5BagencyPicker%5D%5B0%5D%5Bhighlighted%5D=true")
            
            time.sleep(3)
            source = page.content()
            
            soup = BeautifulSoup(source, 'html.parser')
            opp_links = soup.find_all('a', href=re.compile(r'^/opp/.+/view$'))
            base_url = "https://sam.gov"
            first_5_links = [base_url + link['href'] for link in opp_links[:5]]
            
            
            link_data = []
            for link in opp_links[:5]:
                title = link.get_text(strip=True) or "Contract Opportunity"
                link_data.append({
                    'url': base_url + link['href'],
                    'title': title[:100] + '...' if len(title) > 100 else title
                })
            
            return link_data
        
        except Exception as e:
            print(f"Error scraping links: {e}")
            return []
        finally:
            browser.close()

def get_contract_content(link):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(link)
            time.sleep(2)
            source = page.content()
            return parse_contract_from_html(source)
        except Exception as e:
            print(f"Error getting contract content: {e}")
            return None
        finally:
            browser.close()

def parse_contract_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    response = "CONTRACT OPPORTUNITY DETAILS\n\n"
    
    
    notice_id_elem = soup.find('div', id='header-solicitation-number')
    if notice_id_elem:
        description = notice_id_elem.find('div', class_='description')
        if description:
            notice_id = description.get_text(strip=True)
            response += f"Notice ID: {notice_id}\n\n"
    
    
    response += "GENERAL INFORMATION\n"
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
                response += f"{label}: {text}\n"
    
    
    response += "\nCLASSIFICATION\n"
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
                response += f"{label}: {text}\n"
    
    
    response += "\nCONTRACTING OFFICE ADDRESS\n"
    contracting_office_div = soup.find('div', id='-contracting-office')
    if contracting_office_div:
        address_items = contracting_office_div.find_all('li')
        for item in address_items:
            address_line = item.get_text(strip=True)
            if address_line:
                response += f'{address_line}\n'
    
    
    response += "\nPRIMARY POINT OF CONTACT\n"
    primary_poc_div = soup.find('div', id='contact-primary-poc')
    if primary_poc_div:
        name_elem = primary_poc_div.find('li', id='contact-primary-poc-full-name')
        if name_elem:
            name = name_elem.get_text(strip=True)
            response += f"Name: {name}\n"
        
        email_elem = primary_poc_div.find('li', id='contact-primary-poc-email')
        if email_elem:
            email_link = email_elem.find('a')
            if email_link:
                email = email_link.get_text(strip=True)
                response += f"Email: {email}\n"
        
        phone_elem = primary_poc_div.find('li', id='contact-primary-poc-phone')
        if phone_elem:
            phone_text = phone_elem.get_text(strip=True)
            phone_match = re.search(r'(\d{10})', phone_text)
            if phone_match:
                phone = phone_match.group(1)
                formatted_phone = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
                response += f"Phone: {formatted_phone}\n"
    
    return response

def create_vector_store_from_content(content, session_id):
    try:
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        
        doc = Document(page_content=content, metadata={"source": "contract"})
        chunks = text_splitter.split_documents([doc])
        
        
        collection_name = f"contract-{session_id[:8]}"
        persist_directory = os.path.join(TEMP_DIR, collection_name)
        os.makedirs(persist_directory, exist_ok=True)
        
        embeddings = OpenAIEmbeddings()
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=persist_directory,
            collection_name=collection_name
        )
        
        vector_store.persist()
        return vector_store, persist_directory
    
    except Exception as e:
        print(f"Error creating vector store: {e}")
        raise

def setup_rag_chain(vector_store):
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.2)
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})
    
    
    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, just "
        "reformulate it if needed and otherwise return it as is."
    )
    
    contextualize_q_prompt = ChatPromptTemplate.from_messages([
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )
    
    
    qa_system_prompt = (
        "You are a helpful AI assistant that helps with government contract proposals. "
        "Use the contract information provided to answer questions and help generate "
        "proposal content. If asked about proposal outlines, create realistic "
        "structures including executive summary, technical approach, deliverables, "
        "timeline, and compliance requirements. Be detailed and professional.\n\n"
        "Contract Context: {context}"
    )
    
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", qa_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    
    return rag_chain

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

@app.route('/api/contracts/suggested', methods=['GET'])
def get_suggested_contracts():
    try:
        links = get_first_five_links()
        return jsonify({'contracts': links})
    except Exception as e:
        return jsonify({'error': f'Failed to fetch contracts: {str(e)}'}), 500

@app.route('/api/contracts/process', methods=['POST'])
def process_contract():
    data = request.json
    
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400
    
    url = data['url']
    
    try:
        
        contract_content = get_contract_content(url)
        if not contract_content:
            return jsonify({'error': 'Failed to extract contract content'}), 400
        
        
        session_id = str(uuid.uuid4())
        
        
        vector_store, persist_directory = create_vector_store_from_content(contract_content, session_id)
        rag_chain = setup_rag_chain(vector_store)
        
        
        active_sessions[session_id] = {
            'rag_chain': rag_chain,
            'vector_store': vector_store,
            'persist_directory': persist_directory,
            'contract_url': url,
            'contract_content': contract_content,
            'chat_history': []
        }
        
        
        initial_prompt = ("Generate a comprehensive fake bid/proposal outline from this contract information. "
                         "Include executive summary points, technical approach sections, key deliverables, "
                         "rough timeline, and any compliance requirements mentioned.")
        
        response = rag_chain.invoke({
            "input": initial_prompt,
            "chat_history": []
        })
        
        initial_outline = response.get("answer", "")
        
        
        active_sessions[session_id]['chat_history'].extend([
            {"type": "human", "content": "Please generate a proposal outline for this contract."},
            {"type": "ai", "content": initial_outline}
        ])
        
        return jsonify({
            'session_id': session_id,
            'contract_url': url,
            'initial_outline': initial_outline,
            'contract_content': contract_content[:1000] + '...' if len(contract_content) > 1000 else contract_content
        })
    
    except Exception as e:
        print(f"Error processing contract: {e}")
        return jsonify({'error': f'Failed to process contract: {str(e)}'}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    
    if not data or 'session_id' not in data or 'message' not in data:
        return jsonify({'error': 'Missing required fields: session_id and message'}), 400
    
    session_id = data['session_id']
    user_message = data['message']
    
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session ID. Please process a contract first.'}), 404
    
    try:
        session = active_sessions[session_id]
        rag_chain = session['rag_chain']
        chat_history = session['chat_history']
        
        
        formatted_chat_history = []
        for msg in chat_history:
            formatted_chat_history.append(msg)
        
        
        response = rag_chain.invoke({
            "input": user_message,
            "chat_history": formatted_chat_history
        })
        
        answer = response.get("answer", "")
        source_docs = response.get("context", [])
        
        
        sources = []
        if source_docs:
            for doc in source_docs[:3]:
                content_preview = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
                sources.append(content_preview)
        
        
        chat_history.extend([
            {"type": "human", "content": user_message},
            {"type": "ai", "content": answer}
        ])
        session['chat_history'] = chat_history
        
        return jsonify({
            "answer": answer,
            "sources": sources,
            "session_id": session_id
        })
    
    except Exception as e:
        print(f"Error in chat: {e}")
        return jsonify({'error': f'Failed to process message: {str(e)}'}), 500

@app.route('/api/highlight', methods=['POST'])
def handle_highlight():
    data = request.json
    
    if not data or 'session_id' not in data or 'highlighted_text' not in data:
        return jsonify({'error': 'Missing required fields: session_id and highlighted_text'}), 400
    
    session_id = data['session_id']
    highlighted_text = data['highlighted_text']
    
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    try:
        session = active_sessions[session_id]
        contract_content = session['contract_content']
        
        
        if highlighted_text in contract_content:
            
            start_index = contract_content.find(highlighted_text)
            
            
            context_start = max(0, start_index - 200)
            context_end = min(len(contract_content), start_index + len(highlighted_text) + 200)
            context = contract_content[context_start:context_end]
            
            return jsonify({
                'source': 'contract_document',
                'context': context,
                'highlighted_text': highlighted_text,
                'explanation': f'This text appears in the contract document. Here\'s the surrounding context: "{context}"'
            })
        else:
            return jsonify({
                'source': 'ai_generated',
                'explanation': 'This text appears to be AI-generated content based on the contract information, not directly from the source document.'
            })
    
    except Exception as e:
        print(f"Error handling highlight: {e}")
        return jsonify({'error': f'Failed to process highlight: {str(e)}'}), 500

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def end_session(session_id):
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    try:
        session = active_sessions[session_id]
        persist_directory = session['persist_directory']
        
        
        if os.path.exists(persist_directory):
            shutil.rmtree(persist_directory)
        
        del active_sessions[session_id]
        
        return jsonify({'message': 'Session ended successfully'})
    
    except Exception as e:
        print(f"Error ending session: {e}")
        return jsonify({'error': f'Failed to end session: {str(e)}'}), 500

@app.route('/api/sessions/<session_id>/history', methods=['GET'])
def get_chat_history(session_id):
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    session = active_sessions[session_id]
    
    return jsonify({
        'session_id': session_id,
        'contract_url': session['contract_url'],
        'chat_history': session['chat_history']
    })

if __name__ == '__main__':
    print("Contract Proposal Generator Backend")
    print("Make sure to set your OPENAI_API_KEY in your .env file")
    app.run(debug=True, host='0.0.0.0', port=5000)
