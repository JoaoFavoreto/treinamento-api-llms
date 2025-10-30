import json
import os
import time
from typing import List, Dict, Optional
from openai import OpenAI
from tqdm import tqdm
import config
from usage_tracker import OpenAIUsageTracker
from agent_loader import load_agent_config, format_message


class ComplaintClassifier:
    """Classify complaints using curated taxonomy and OpenAI API"""

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        track_usage: bool = True,
        agent_name: str = "complaint_classifier",
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
        self.messages = self.agent_config.get("messages", {})
        
        # Will hold the taxonomy during classification
        self.taxonomy = None
        
        # Optional: track API usage for cost monitoring
        self.tracker = (
            OpenAIUsageTracker(config.API_USAGE_LOG_FILE) if track_usage else None
        )

    def load_taxonomy(self, file_path: str) -> List[Dict]:
        """Load curated taxonomy from JSON file"""
        with open(file_path, "r", encoding="utf-8") as f:
            taxonomy_data = json.load(f)

        if isinstance(taxonomy_data, dict) and "proposed_categories" in taxonomy_data:
            return taxonomy_data["proposed_categories"]
        elif isinstance(taxonomy_data, list):
            return taxonomy_data
        else:
            raise ValueError(
                "Invalid taxonomy format. Expected list of categories or dict with 'proposed_categories' key."
            )

    def load_complaints(self, file_path: str) -> List[Dict]:
        """Load complaints from JSON file"""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def classify_complaint(self, complaint: Dict, taxonomy: List[Dict]) -> str:
        """Classify a single complaint using OpenAI API"""

        # Format taxonomy as readable text for the LLM
        taxonomy_text = "\n".join(
            [
                f"- {cat['category_name']}: {cat['category_description']}"
                for cat in taxonomy
            ]
        )

        # Format complaint for the LLM
        complaint_text = f"Title: {complaint.get('complaint_title', '')}\nText: {complaint.get('complaint_text', '')}"

        # Load prompts from YAML config
        system_prompt = self.messages.get(
            "system",
            "You are a complaint classification system. Return only the category name.",
        )
        user_template = self.messages.get("single_user_template")
        if not user_template:
            raise ValueError(
                "Complaint classifier agent must define a single_user_template message."
            )

        # Insert taxonomy and complaint into the prompt template
        user_prompt = format_message(
            user_template,
            taxonomy_text=taxonomy_text,
            complaint_text=complaint_text,
        )

        try:
            # Call OpenAI API for classification
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.parameters.get(
                    "single_temperature", self.parameters.get("temperature", 0.2)
                ),
                max_tokens=self.parameters.get(
                    "single_max_tokens", self.parameters.get("max_tokens", 500)
                ),
            )

            category = response.choices[0].message.content.strip()

            # Validate that the returned category exists in taxonomy
            valid_categories = [cat["category_name"] for cat in taxonomy]
            if category not in valid_categories:
                print(
                    f"Warning: API returned invalid category '{category}' for {complaint['complaint_id']}, defaulting to OTHER"
                )
                return "OTHER"

            return category

        except Exception as e:
            print(f"Error classifying {complaint['complaint_id']}: {e}")
            return "ERROR"

    def classify_batch(
        self, complaints: List[Dict], batch_size: int = 10
    ) -> List[Dict]:
        """Classify multiple complaints in batches using OpenAI API"""

        # Format taxonomy once for all batches
        taxonomy_text = "\n".join(
            [
                f"- {cat['category_name']}: {cat['category_description']}"
                for cat in self.taxonomy
            ]
        )

        results = []

        # Process complaints in chunks to reduce API calls
        for i in tqdm(
            range(0, len(complaints), batch_size), desc="Classifying complaints"
        ):
            batch = complaints[i : i + batch_size]

            # Format multiple complaints into a single prompt
            complaints_text = "\n\n".join(
                [
                    f"ID: {c['complaint_id']}\nTitle: {c.get('complaint_title', '')}\nText: {c.get('complaint_text', '')[:500]}"
                    for c in batch
                ]
            )

            # Load batch prompts from YAML config
            system_prompt = self.messages.get(
                "system",
                "You are a complaint classification system. Return only valid JSON.",
            )
            batch_template = self.messages.get("batch_user_template")
            if not batch_template:
                raise ValueError(
                    "Complaint classifier agent must define a batch_user_template message."
                )

            user_prompt = format_message(
                batch_template,
                taxonomy_text=taxonomy_text,
                complaints_text=complaints_text,
            )

            try:
                start_time = time.time()
                
                # Send batch to OpenAI API (one call for multiple complaints)
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=self.parameters.get("temperature", 0.1),
                    max_tokens=self.parameters.get("max_tokens", 1000),
                )
                duration = time.time() - start_time

                # Track API usage if enabled
                if self.tracker:
                    self.tracker.log_call(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        duration=duration,
                    )

                result_text = response.choices[0].message.content.strip()

                # Remove markdown code fences if present
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()

                # Parse JSON response
                batch_results = json.loads(result_text)

                # Validate all categories in the batch
                valid_categories = [cat["category_name"] for cat in self.taxonomy] + [
                    "OTHER"
                ]
                for result in batch_results:
                    if result["assigned_category"] not in valid_categories:
                        print(
                            f"Warning: Invalid category '{result['assigned_category']}' for {result['complaint_id']}, changing to OTHER"
                        )
                        result["assigned_category"] = "OTHER"

                results.extend(batch_results)

            except Exception as e:
                # If batch fails, mark all complaints as ERROR
                print(f"Error processing batch: {e}")
                for c in batch:
                    results.append(
                        {
                            "complaint_id": c["complaint_id"],
                            "assigned_category": "ERROR",
                        }
                    )

        return results

    def classify_all(
        self, complaints: List[Dict], taxonomy: List[Dict], use_batch: bool = False
    ) -> List[Dict]:
        """Classify all complaints (choose between single or batch mode)"""
        self.taxonomy = taxonomy

        # Use batch mode for efficiency if many complaints
        if use_batch and len(complaints) > 20:
            return self.classify_batch(complaints, batch_size=10)
        else:
            # Single-complaint mode (one API call per complaint)
            results = []
            for complaint in tqdm(complaints, desc="Classifying complaints"):
                category = self.classify_complaint(complaint, taxonomy)
                results.append(
                    {
                        "complaint_id": complaint["complaint_id"],
                        "assigned_category": category,
                    }
                )
            return results

    def generate_summary(self, results: List[Dict]) -> Dict:
        """Generate classification summary statistics"""
        total = len(results)
        category_counts = {}

        for result in results:
            category = result["assigned_category"]
            category_counts[category] = category_counts.get(category, 0) + 1

        summary = {
            "total_complaints": total,
            "category_distribution": [
                {
                    "category": cat,
                    "count": count,
                    "percentage": round((count / total) * 100, 2),
                }
                for cat, count in sorted(
                    category_counts.items(), key=lambda x: x[1], reverse=True
                )
            ],
        }

        return summary


def run_phase4():
    """Execute Phase 4: Large-Scale Classification"""
    print("\n" + "=" * 60)
    print("PHASE 4: LARGE-SCALE CLASSIFICATION")
    print("=" * 60 + "\n")

    if not os.path.exists(config.CURATED_TAXONOMY_FILE):
        print(f"ERROR: Curated taxonomy not found: {config.CURATED_TAXONOMY_FILE}")
        print("\nYou must complete Phase 3 (Human Curation) first:")
        print(f"1. Review: {config.PROPOSED_TAXONOMY_FILE}")
        print(f"2. Create: {config.CURATED_TAXONOMY_FILE}")
        print(f"3. Then run this script again")
        return

    if not os.path.exists(config.COMPLAINTS_FILE):
        print(f"ERROR: Complaints file not found: {config.COMPLAINTS_FILE}")
        print("Please run Phase 1 (scraper.py) first.")
        return

    if not config.OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY not found in environment variables.")
        return

    classifier = ComplaintClassifier(
        config.OPENAI_API_KEY, config.OPENAI_MODEL, track_usage=config.SHOW_API_USAGE
    )

    if classifier.tracker:
        classifier.tracker.start_session(
            "Phase 4 - Classification", config.OPENAI_MODEL
        )

    print("Loading curated taxonomy...")
    taxonomy = classifier.load_taxonomy(config.CURATED_TAXONOMY_FILE)
    print(f"✓ Loaded {len(taxonomy)} categories")
    for cat in taxonomy:
        print(f"  - {cat['category_name']}")

    print(f"\nLoading complaints...")
    complaints = classifier.load_complaints(config.COMPLAINTS_FILE)
    print(f"✓ Loaded {len(complaints)} complaints")

    print(f"\nClassifying all complaints using OpenAI API ({config.OPENAI_MODEL})...")
    results = classifier.classify_all(complaints, taxonomy, use_batch=True)

    summary = classifier.generate_summary(results)

    output_data = {
        "taxonomy_used": taxonomy,
        "classification_results": results,
        "summary": summary,
    }

    with open(config.CLASSIFICATION_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("PHASE 4 COMPLETE - DELIVERABLES:")
    print(f"{'='*60}\n")

    print(f"Classification Summary:")
    print(f"Total complaints classified: {summary['total_complaints']}\n")

    print("Category Distribution:")
    for dist in summary["category_distribution"]:
        print(f"  {dist['category']}: {dist['count']} ({dist['percentage']}%)")

    if classifier.tracker and config.SHOW_API_USAGE:
        session_data = classifier.tracker.end_session()
        if session_data:
            print(f"\n{'='*60}")
            print(f"OPENAI API USAGE - PHASE 4")
            print(f"{'='*60}")
            print(f"Model: {session_data['model']}")
            print(f"API Calls: {len(session_data['calls'])}")
            print(f"Input Tokens: {session_data['total_input_tokens']:,}")
            print(f"Output Tokens: {session_data['total_output_tokens']:,}")
            print(f"Total Tokens: {session_data['total_tokens']:,}")
            print(f"Estimated Cost: ${session_data['estimated_cost_usd']:.4f} USD")
            if config.SHOW_API_USAGE_DETAILS and session_data["calls"]:
                print(f"\nDetailed Calls:")
                for i, call in enumerate(session_data["calls"], 1):
                    print(
                        f"  Call {i}: {call['input_tokens']} in + {call['output_tokens']} out = {call['total_tokens']} tokens ({call['duration_seconds']}s)"
                    )
            print(f"{'='*60}\n")
    elif classifier.tracker:
        classifier.tracker.end_session()

    print(f"\n{'='*60}")
    print(f"✓ Full results saved to: {config.CLASSIFICATION_RESULTS_FILE}")
    print(f"✓ Results include: taxonomy, all classifications, and summary stats")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_phase4()
