import json
import random
import os
import time
from typing import List, Dict, Optional
from openai import OpenAI
import config
from usage_tracker import OpenAIUsageTracker
from agent_loader import load_agent_config, format_message


class ThemeDiscovery:
    """Discover recurring themes in complaints using OpenAI API"""
    
    def __init__(
        self,
    api_key: str,
    model: Optional[str] = None,
        track_usage: bool = False,
        agent_name: str = "theme_discovery",
    ):
        # Initialize OpenAI client
        self.client = OpenAI(api_key=api_key)
        
        # Load agent configuration from YAML file
        self.agent_config = load_agent_config(agent_name)
        configured_model = self.agent_config.get("model")
        
        # Model priority: runtime param > YAML config > default fallback
        self.model = model or configured_model or "gpt-4o-mini"
        
        # Load parameters (temperature, max_tokens, etc.) from YAML
        self.parameters = self.agent_config.get("parameters", {})
        
        # Optional: track API usage for cost monitoring
        self.tracker = OpenAIUsageTracker(config.API_USAGE_LOG_FILE) if track_usage else None
    
    def load_complaints(self, file_path: str) -> List[Dict]:
        """Load complaints from JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def sample_complaints(self, complaints: List[Dict], sample_size: int) -> List[Dict]:
        """Select a representative random sample of complaints for analysis"""
        if len(complaints) <= sample_size:
            return complaints
        
        return random.sample(complaints, sample_size)
    
    def generate_taxonomy(self, complaints_sample: List[Dict]) -> Dict:
        """Call OpenAI API to discover themes and generate proposed taxonomy"""

        # Format sample complaints as text for the LLM
        complaints_text = "\n\n---\n\n".join([
            f"Complaint {c['complaint_id']}:\nTitle: {c['complaint_title']}\nText: {c['complaint_text']}"
            for c in complaints_sample if c.get('complaint_text')
        ])

        # Load prompts from YAML config
        messages = self.agent_config.get("messages", {})
        system_prompt = messages.get(
            "system", "You are an expert automotive CX analyst. Return only valid JSON."
        )
        user_template = messages.get("user_template")
        if not user_template:
            raise ValueError("The theme discovery agent must define a user_template message.")

        # Insert sample into the prompt template
        user_prompt = format_message(
            user_template,
            min_categories=config.MIN_CATEGORIES,
            max_categories=config.MAX_CATEGORIES,
            complaints_sample=complaints_text,  # Truncate to avoid token limits
        )

        start_time = time.time()
        
        # Call OpenAI API to analyze complaints and discover themes
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},   
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.parameters.get("temperature", 0.3),
            max_tokens=self.parameters.get("max_tokens", 3000),
        )
        duration = time.time() - start_time
        
        # Track API usage if enabled
        if self.tracker:
            self.tracker.log_call(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                duration=duration
            )
        
        # Extract response text
        result_text = response.content.strip() if hasattr(response, 'content') else response.choices[0].message.content.strip()
        
        # Remove markdown code fences if present
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()
        
        # Parse JSON taxonomy
        taxonomy = json.loads(result_text)
        
        # Return structured taxonomy with metadata
        return {
            "sample_size": len(complaints_sample),
            "total_complaints": len(self.load_complaints(config.COMPLAINTS_FILE)),
            "proposed_categories": taxonomy,
            "status": "AWAITING_HUMAN_CURATION"
        }
    
    def save_taxonomy(self, taxonomy: Dict, file_path: str):
        """Save proposed taxonomy to JSON file"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(taxonomy, f, ensure_ascii=False, indent=2)


def run_phase2():
    """Execute Phase 2: Theme Discovery"""
    print("\n" + "="*60)
    print("PHASE 2: THEME DISCOVERY")
    print("="*60 + "\n")
    
    if not os.path.exists(config.COMPLAINTS_FILE):
        print(f"ERROR: Complaints file not found: {config.COMPLAINTS_FILE}")
        print("Please run Phase 1 (scraper.py) first.")
        return
    
    if not config.OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY not found in environment variables.")
        print("Please create a .env file with your OpenAI API key.")
        return
    
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    
    discovery = ThemeDiscovery(config.OPENAI_API_KEY, config.OPENAI_MODEL, track_usage=config.SHOW_API_USAGE)
    
    if discovery.tracker:
        discovery.tracker.start_session('Phase 2 - Theme Discovery', config.OPENAI_MODEL)
    
    print("Loading complaints...")
    complaints = discovery.load_complaints(config.COMPLAINTS_FILE)
    print(f"✓ Loaded {len(complaints)} complaints")
    
    print(f"\nSampling {config.SAMPLE_SIZE_FOR_DISCOVERY} complaints for analysis...")
    sample = discovery.sample_complaints(complaints, config.SAMPLE_SIZE_FOR_DISCOVERY)
    print(f"✓ Selected {len(sample)} complaints")
    
    print(f"\nCalling OpenAI API ({config.OPENAI_MODEL}) to discover themes...")
    taxonomy = discovery.generate_taxonomy(sample)
    print(f"✓ Generated {len(taxonomy['proposed_categories'])} categories")
    
    discovery.save_taxonomy(taxonomy, config.PROPOSED_TAXONOMY_FILE)
    
    if discovery.tracker and config.SHOW_API_USAGE:
        session_data = discovery.tracker.end_session()
        if session_data:
            print(f"\n{'='*60}")
            print(f"OPENAI API USAGE - PHASE 2")
            print(f"{'='*60}")
            print(f"Model: {session_data['model']}")
            print(f"API Calls: {len(session_data['calls'])}")
            print(f"Input Tokens: {session_data['total_input_tokens']:,}")
            print(f"Output Tokens: {session_data['total_output_tokens']:,}")
            print(f"Total Tokens: {session_data['total_tokens']:,}")
            print(f"Estimated Cost: ${session_data['estimated_cost_usd']:.4f} USD")
            if config.SHOW_API_USAGE_DETAILS and session_data['calls']:
                print(f"\nDetailed Calls:")
                for i, call in enumerate(session_data['calls'], 1):
                    print(f"  Call {i}: {call['input_tokens']} in + {call['output_tokens']} out = {call['total_tokens']} tokens ({call['duration_seconds']}s)")
            print(f"{'='*60}\n")
    elif discovery.tracker:
        discovery.tracker.end_session()
    
    print(f"\n{'='*60}")
    print("PHASE 2 COMPLETE - DELIVERABLES:")
    print(f"{'='*60}\n")
    
    for idx, category in enumerate(taxonomy['proposed_categories'], 1):
        print(f"{idx}. {category['category_name']}")
        print(f"   Description: {category['category_description']}")
        print(f"   Examples:")
        for example in category['representative_examples']:
            print(f"   - {example}")
        print()
    
    print(f"{'='*60}")
    print(f"✓ Proposed taxonomy saved to: {config.PROPOSED_TAXONOMY_FILE}")
    print(f"✓ Sample size: {taxonomy['sample_size']} complaints")
    print(f"✓ Total categories: {len(taxonomy['proposed_categories'])}")
    print(f"\n{'='*60}")
    print("⚠️  AWAITING HUMAN CURATION")
    print("DO NOT USE THESE CATEGORIES FOR FULL DATASET CLASSIFICATION YET")
    print(f"{'='*60}")
    print(f"\nNext steps:")
    print(f"1. Review {config.PROPOSED_TAXONOMY_FILE}")
    print(f"2. Merge, rename, or refine categories as needed")
    print(f"3. Save final taxonomy to: {config.CURATED_TAXONOMY_FILE}")
    print(f"4. Run Phase 4 (classifier.py) with curated taxonomy")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_phase2()
