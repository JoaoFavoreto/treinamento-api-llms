import sys
from usage_tracker import OpenAIUsageTracker
import config


def main():
    """View OpenAI API usage statistics"""
    
    tracker = OpenAIUsageTracker(config.API_USAGE_LOG_FILE)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--details':
        show_details = True
    else:
        show_details = False
    
    if not tracker.sessions:
        print("\nNo API usage data found.")
        print("Run Phase 2 or Phase 4 to generate usage statistics.\n")
        return
    
    tracker.print_total_usage()
    
    if show_details:
        print(f"\n{'='*60}")
        print("DETAILED SESSION HISTORY")
        print(f"{'='*60}\n")
        
        for i, session in enumerate(tracker.sessions, 1):
            print(f"Session {i}: {session['phase']}")
            print(f"  Date: {session['start_datetime']}")
            print(f"  Model: {session['model']}")
            print(f"  API Calls: {len(session['calls'])}")
            print(f"  Tokens: {session['total_input_tokens']:,} in + {session['total_output_tokens']:,} out = {session['total_tokens']:,} total")
            print(f"  Duration: {session['duration_seconds']}s")
            print(f"  Cost: ${session['estimated_cost_usd']:.4f} USD")
            print()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("OPENAI API USAGE VIEWER")
    print("="*60)
    print("\nUsage:")
    print("  python view_usage.py          # Show summary")
    print("  python view_usage.py --details # Show all sessions")
    print("="*60)
    
    main()
