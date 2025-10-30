import json
import time
from typing import Dict, List, Optional
from datetime import datetime
import os


class OpenAIUsageTracker:
    """Track OpenAI API usage: tokens, time, and estimated costs"""
    
    # Pricing per 1M tokens (as of 2024)
    PRICING = {
        'gpt-4o-mini': {
            'input': 0.150,   # $0.150 per 1M input tokens
            'output': 0.600   # $0.600 per 1M output tokens
        },
        'gpt-4o': {
            'input': 2.50,
            'output': 10.00
        },
        'gpt-4-turbo': {
            'input': 10.00,
            'output': 30.00
        }
    }
    
    def __init__(self, log_file: str = "output/openai_usage.json"):
        self.log_file = log_file
        self.sessions = []
        self.current_session = None
        self._load_history()
    
    def _load_history(self):
        """Load previous usage history"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.sessions = data.get('sessions', [])
            except Exception:
                self.sessions = []
    
    def _save_history(self):
        """Save usage history to file"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump({
                'sessions': self.sessions,
                'last_updated': datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)
    
    def start_session(self, phase: str, model: str):
        """Start tracking a new session"""
        self.current_session = {
            'phase': phase,
            'model': model,
            'start_time': time.time(),
            'start_datetime': datetime.now().isoformat(),
            'calls': [],
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_tokens': 0,
            'duration_seconds': 0,
            'estimated_cost_usd': 0.0
        }
    
    def log_call(self, input_tokens: int, output_tokens: int, duration: float):
        """Log a single API call"""
        if not self.current_session:
            return
        
        call_data = {
            'timestamp': datetime.now().isoformat(),
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'duration_seconds': round(duration, 2)
        }
        
        self.current_session['calls'].append(call_data)
        self.current_session['total_input_tokens'] += input_tokens
        self.current_session['total_output_tokens'] += output_tokens
        self.current_session['total_tokens'] += (input_tokens + output_tokens)
    
    def end_session(self):
        """End current session and calculate totals"""
        if not self.current_session:
            return
        
        self.current_session['duration_seconds'] = round(
            time.time() - self.current_session['start_time'], 2
        )
        
        # Calculate cost
        model = self.current_session['model']
        pricing = self.PRICING.get(model, self.PRICING['gpt-4o-mini'])
        
        input_cost = (self.current_session['total_input_tokens'] / 1_000_000) * pricing['input']
        output_cost = (self.current_session['total_output_tokens'] / 1_000_000) * pricing['output']
        self.current_session['estimated_cost_usd'] = round(input_cost + output_cost, 4)
        
        # Remove start_time (not JSON serializable in readable format)
        del self.current_session['start_time']
        
        self.sessions.append(self.current_session)
        self._save_history()
        
        session = self.current_session
        self.current_session = None
        return session
    
    def get_summary(self, show_details: bool = False) -> str:
        """Get formatted summary of current session"""
        if not self.current_session:
            return "No active session"
        
        session = self.current_session
        lines = [
            f"\n{'='*60}",
            f"OPENAI API USAGE - {session['phase'].upper()}",
            f"{'='*60}",
            f"Model: {session['model']}",
            f"API Calls: {len(session['calls'])}",
            f"Input Tokens: {session['total_input_tokens']:,}",
            f"Output Tokens: {session['total_output_tokens']:,}",
            f"Total Tokens: {session['total_tokens']:,}",
            f"Estimated Cost: ${session.get('estimated_cost_usd', 0.0):.4f} USD"
        ]
        
        if show_details and session['calls']:
            lines.append(f"\nDetailed Calls:")
            for i, call in enumerate(session['calls'], 1):
                lines.append(
                    f"  Call {i}: {call['input_tokens']} in + {call['output_tokens']} out "
                    f"= {call['total_tokens']} tokens ({call['duration_seconds']}s)"
                )
        
        lines.append(f"{'='*60}\n")
        return '\n'.join(lines)
    
    def get_total_usage(self) -> Dict:
        """Get total usage across all sessions"""
        total = {
            'total_sessions': len(self.sessions),
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_tokens': 0,
            'total_cost_usd': 0.0,
            'by_phase': {}
        }
        
        for session in self.sessions:
            total['total_input_tokens'] += session['total_input_tokens']
            total['total_output_tokens'] += session['total_output_tokens']
            total['total_tokens'] += session['total_tokens']
            total['total_cost_usd'] += session.get('estimated_cost_usd', 0.0)
            
            phase = session['phase']
            if phase not in total['by_phase']:
                total['by_phase'][phase] = {
                    'sessions': 0,
                    'tokens': 0,
                    'cost_usd': 0.0
                }
            total['by_phase'][phase]['sessions'] += 1
            total['by_phase'][phase]['tokens'] += session['total_tokens']
            total['by_phase'][phase]['cost_usd'] += session.get('estimated_cost_usd', 0.0)
        
        total['total_cost_usd'] = round(total['total_cost_usd'], 4)
        return total
    
    def print_total_usage(self):
        """Print total usage summary"""
        total = self.get_total_usage()
        
        print(f"\n{'='*60}")
        print("TOTAL OPENAI API USAGE (ALL TIME)")
        print(f"{'='*60}")
        print(f"Total Sessions: {total['total_sessions']}")
        print(f"Total Tokens: {total['total_tokens']:,}")
        print(f"  Input: {total['total_input_tokens']:,}")
        print(f"  Output: {total['total_output_tokens']:,}")
        print(f"Total Estimated Cost: ${total['total_cost_usd']:.4f} USD")
        
        if total['by_phase']:
            print(f"\nBy Phase:")
            for phase, data in total['by_phase'].items():
                print(f"  {phase}: {data['sessions']} sessions, "
                      f"{data['tokens']:,} tokens, ${data['cost_usd']:.4f}")
        
        print(f"{'='*60}\n")
