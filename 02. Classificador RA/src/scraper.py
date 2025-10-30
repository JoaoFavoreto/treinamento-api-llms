import re
import json
import time
import os
from typing import List, Dict, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
import config


class PIIRemover:
    """Remove or mask personally identifiable information (PII) from text for LGPD compliance"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Replace sensitive data with placeholder tags"""
        if not text:
            return text
        
        # Replace names (capitalized words in sequence)
        text = re.sub(r'\b[A-Z][a-zÀ-ÿ]+(?:\s+[A-Z][a-zÀ-ÿ]+)+\b', '[NOME]', text)
        
        # Replace CPF (Brazilian SSN): 123.456.789-01
        text = re.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', '[CPF]', text)
        
        # Replace CNPJ (Company ID): 12.345.678/0001-90
        text = re.sub(r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b', '[CNPJ]', text)
        
        # Replace phone numbers with various formats
        text = re.sub(r'\b(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[-\s]?\d{4}\b', '[TELEFONE]', text)
        
        # Replace email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        
        # Replace vehicle license plates
        text = re.sub(r'\b[A-Z]{3}[-\s]?\d{4}\b', '[PLACA]', text)
        
        # Replace chassis numbers
        text = re.sub(r'\b(?:chassi|chassis)\s*:?\s*\w+\b', '[CHASSI]', text, flags=re.IGNORECASE)
        
        # Replace protocol numbers
        text = re.sub(r'\bprotocolo\s*:?\s*\d+\b', '[PROTOCOLO]', text, flags=re.IGNORECASE)
        
        return text


class ReclameAquiAPIExtractor:
    """Extract complaints from Reclame Aqui by parsing Next.js __NEXT_DATA__ JSON"""
    
    def __init__(self, base_url: str, delay: float = 2):
        self.base_url = base_url  # Company page URL on Reclame Aqui
        self.delay = delay         # Delay between requests (be respectful to the server)
        self.driver = None         # Selenium WebDriver instance
    
    def _init_driver(self):
        """Initialize headless Chrome browser with Selenium"""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium not available. Install with: pip install selenium webdriver-manager")
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run without GUI
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        # Mimic a real browser to avoid bot detection
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
    
    def _close_driver(self):
        """Clean up: close browser and free resources"""
        if self.driver:
            self.driver.quit()
    
    def extract_next_data(self, page: int = 1) -> Optional[Dict]:
        """Extract __NEXT_DATA__ JSON embedded in the page HTML (Next.js pattern)"""
        try:
            if not self.driver:
                self._init_driver()
            
            # Build URL for the specific page
            url = f"{self.base_url}/lista-reclamacoes/?pagina={page}" if page > 1 else f"{self.base_url}/lista-reclamacoes/"
            print(f"Fetching page {page}...")

            # Load page in browser
            self.driver.get(url)
            time.sleep(3)  # Wait for JavaScript to execute

            # Parse HTML and find the embedded JSON data
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            script_tag = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'})

            if not script_tag:
                print(f"Warning: No __NEXT_DATA__ found on page {page}")
                return None
            
            # Parse JSON string into Python dict
            data = json.loads(script_tag.string)
            return data
        
        except Exception as e:
            print(f"Error extracting data from page {page}: {e}")
            return None
    
    def parse_complaints_from_data(self, data: Dict, page: int) -> List[Dict]:
        """Parse complaints from __NEXT_DATA__ structure"""
        complaints = []
        
        try:
            page_props = data.get('props', {}).get('pageProps', {})
            # Navigate to complaints list
            complaints_data = page_props.get('complaints', {}).get('LAST', [])
            
            if not complaints_data:
                print(f"No complaints found in data for page {page}")
                return []
            
            for idx, complaint in enumerate(complaints_data):
                complaint_id = complaint.get('id', f'PAGE{page}_ITEM{idx}')
                title = complaint.get('title', '')
                description = complaint.get('description', '')
                created = complaint.get('created', '')
                status = complaint.get('status', '')
                url_slug = complaint.get('url', '')
                solved = complaint.get('solved', False)
                evaluated = complaint.get('evaluated', False)
                
                full_url = f"https://www.reclameaqui.com.br/empresa/mercedes-benz-cars-e-vans/{url_slug}" if url_slug else None
                
                # Remove personal data
                title_clean = PIIRemover.clean_text(title)
                description_clean = PIIRemover.clean_text(description)
                
                # Remove HTML tags from description
                description_clean = re.sub(r'<br\s*/?>', ' ', description_clean)
                description_clean = re.sub(r'<[^>]+>', '', description_clean)
                
                # Translate status
                status_map = {
                    'PENDING': 'Aguardando resposta',
                    'ANSWERED': 'Respondida',
                    'EVALUATED': 'Avaliada',
                    'NOT_ANSWERED': 'Não respondida'
                }
                status_text = status_map.get(status, status)
                if solved:
                    status_text = 'Resolvido'
                
                complaints.append({
                    'complaint_id': f"COMPLAINT_{complaint_id}",
                    'complaint_title': title_clean,
                    'complaint_text': description_clean,
                    'opened_at': created,
                    'status': status_text,
                    'public_link': full_url
                })
            
            print(f"✓ Extracted {len(complaints)} complaints from page {page}")
            return complaints
        
        except Exception as e:
            print(f"Error parsing complaints from page {page}: {e}")
            return []
    
    def scrape_all_complaints(self, max_pages: int = config.MAX_PAGES) -> List[Dict]:
        """Scrape complaints from multiple pages"""
        try:
            all_complaints = []
            pages_to_scrape = max_pages if max_pages else 10
            
            print(f"Starting scrape: up to {pages_to_scrape} pages")
            
            for page in range(1, pages_to_scrape + 1):
                data = self.extract_next_data(page)
                if not data:
                    print(f"Stopping at page {page} - no data returned")
                    break
                
                complaints = self.parse_complaints_from_data(data, page)
                if not complaints:
                    print(f"Stopping at page {page} - no complaints found")
                    break
                
                all_complaints.extend(complaints)
                
                if page < pages_to_scrape:
                    time.sleep(self.delay)
            
            print(f"\n✓ Total complaints collected: {len(all_complaints)}")
            return all_complaints
        
        finally:
            self._close_driver()


def run_phase1():
    """Execute Phase 1: Data Collection"""
    print("\n" + "="*60)
    print("PHASE 1: DATA COLLECTION - Reclame Aqui Scraping")
    print("="*60 + "\n")
    
    os.makedirs(config.DATA_DIR, exist_ok=True)
    
    if not SELENIUM_AVAILABLE:
        print("ERROR: Selenium is required for this scraper.")
        print("Install with: pip install selenium webdriver-manager")
        print("\nAlternatively, use sample data:")
        print("  python use_sample_data.py")
        return
    
    scraper = ReclameAquiAPIExtractor(config.RECLAME_AQUI_URL, config.REQUEST_DELAY)
    complaints = scraper.scrape_all_complaints(max_pages=config.MAX_PAGES)
    
    with open(config.COMPLAINTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(complaints, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print("PHASE 1 COMPLETE - DELIVERABLES:")
    print(f"{'='*60}")
    print(f"✓ Total complaints collected: {len(complaints)}")
    print(f"✓ Data saved to: {config.COMPLAINTS_FILE}")
    print(f"{'='*60}\n")
    
    return complaints


if __name__ == "__main__":
    run_phase1()
