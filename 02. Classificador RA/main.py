import sys
import os
from scraper import run_phase1
from theme_discovery import run_phase2
from classifier import run_phase4
import config


def main():
    """Main orchestrator for complaint classification pipeline"""
    
    print("\n" + "="*60)
    print("MERCEDES-BENZ COMPLAINT ANALYSIS PIPELINE")
    print("Reclame Aqui - Customer Experience Classification")
    print("="*60 + "\n")
    
    if len(sys.argv) < 2:
        print("Usage: python main.py <phase>")
        print("\nAvailable phases:")
        print("  1 or phase1  - Data Collection (Scraping)")
        print("  2 or phase2  - Theme Discovery (OpenAI API)")
        print("  4 or phase4  - Classification (OpenAI API)")
        print("  all          - Run all phases sequentially")
        print("\nExamples:")
        print("  python main.py 1")
        print("  python main.py phase2")
        print("  python main.py all")
        return
    
    phase = sys.argv[1].lower()
    
    if phase in ['1', 'phase1']:
        run_phase1()
    
    elif phase in ['2', 'phase2']:
        run_phase2()
    
    elif phase in ['4', 'phase4']:
        run_phase4()
    
    elif phase == 'all':
        print("Running all phases sequentially...\n")
        
        run_phase1()
        
        input("\nPress Enter to continue to Phase 2...")
        run_phase2()
        
        print("\n" + "="*60)
        print("PHASE 3: HUMAN CURATION REQUIRED")
        print("="*60)
        print(f"\nBefore continuing, you must:")
        print(f"1. Review: {config.PROPOSED_TAXONOMY_FILE}")
        print(f"2. Edit and save final taxonomy as: {config.CURATED_TAXONOMY_FILE}")
        print(f"3. Press Enter when ready to continue to Phase 4")
        print("="*60 + "\n")
        input("Press Enter to continue to Phase 4...")
        
        run_phase4()
        
        print("\n" + "="*60)
        print("ALL PHASES COMPLETE")
        print("="*60 + "\n")
    
    else:
        print(f"Unknown phase: {phase}")
        print("Valid options: 1, 2, 4, phase1, phase2, phase4, all")


if __name__ == "__main__":
    main()
