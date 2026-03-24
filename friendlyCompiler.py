#!/usr/bin/env python3
# friendlyCompiler.py
import subprocess
import sys
import re
import json
import argparse
from pathlib import Path


def capture_compiler_output(source_file, output_name='output'):
    """
    Compile a C file and capture error messages.
    
    Args:
        source_file: Path to the .c file
        output_name: Name for output executable
    
    Returns:
        tuple: (error_output, return_code)
    """
    try:
        result = subprocess.run(
            ['gcc', source_file, '-o', output_name, '-Wall'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return result.stderr, result.returncode
    
    except subprocess.TimeoutExpired:
        return "Error: Compilation timed out", 1
    except FileNotFoundError:
        return "Error: GCC not found. Is it installed?", 1
    except Exception as e:
        return f"Error: {str(e)}", 1


def parse_gcc_errors(error_output):
    """
    Parse GCC error output into structured format.
    
    Args:
        error_output: Raw stderr from GCC
    
    Returns:
        list: List of parsed error dictionaries
    """
    errors = []
    
    # GCC format: filename:line:column: severity: message
    # Example: test.c:4:27: error: expected ';' before 'return'
    pattern = r'([^:]+):(\d+):(\d+):\s*(error|warning|note):\s*(.+)'
    
    for line in error_output.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        match = re.match(pattern, line)
        
        if match:
            error_info = {
                'file': match.group(1),
                'line': int(match.group(2)),
                'column': int(match.group(3)),
                'severity': match.group(4),
                'message': match.group(5).strip()
            }
            errors.append(error_info)
    
    return errors


def load_error_patterns(json_file='error_patterns.json'):
    """
    Load error patterns from JSON file.
    
    Args:
        json_file: Path to the JSON file containing patterns
    
    Returns:
        list: List of pattern dictionaries
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        patterns = data.get('patterns', [])
        print(f"[+] Loaded {len(patterns)} error patterns from {json_file}\n")
        return patterns
    
    except FileNotFoundError:
        print(f"[!] Warning: {json_file} not found. Using empty pattern database.")
        print(f"    Create {json_file} to enable friendly error translations.\n")
        return []
    except json.JSONDecodeError as e:
        print(f"[!] Warning: Error parsing {json_file}: {e}\n")
        return []


def translate_error(error_message, patterns, debug=False):
    """
    Translate a compiler error message into friendly language.
    
    Args:
        error_message: The error message to translate
        patterns: List of pattern dictionaries
        debug: Whether to show debug information
    
    Returns:
        dict: Translation result with explanation, type, confidence, and match status
    """
    if debug:
        print(f"\n[DEBUG] Translating: {repr(error_message)}")
        print(f"[DEBUG] Testing against {len(patterns)} patterns")
    
    # Try to match against known patterns
    for idx, pattern_data in enumerate(patterns):
        regex_pattern = pattern_data['regex']
        
        try:
            match = re.search(regex_pattern, error_message, re.IGNORECASE)
            
            if match:
                if debug:
                    print(f"[DEBUG] MATCHED pattern #{idx}: {regex_pattern}")
                    print(f"[DEBUG] Captured groups: {match.groups()}")
                
                # Format explanation with captured groups
                explanation = pattern_data['explanation']
                
                # Replace {} placeholders with captured groups
                groups = match.groups()
                if groups:
                    try:
                        explanation = explanation.format(*groups)
                    except (IndexError, KeyError) as e:
                        if debug:
                            print(f"[DEBUG] Warning: Could not format explanation: {e}")
                        pass
                
                return {
                    'found': True,
                    'explanation': explanation,
                    'type': pattern_data['type'],
                    'confidence': pattern_data['confidence']
                }
        
        except re.error as e:
            if debug:
                print(f"[DEBUG] Invalid regex pattern #{idx}: {regex_pattern} - {e}")
            continue
    
    if debug:
        print("[DEBUG] No patterns matched")
    
    # No pattern matched
    return {
        'found': False,
        'explanation': "I don't recognize this error yet. This might be a complex or uncommon error.",
        'type': 'unknown',
        'confidence': 0.0
    }


def display_error(error, translation, index, show_original=False, debug=False):
    """
    Display a single error with its translation.
    
    Args:
        error: Parsed error dictionary
        translation: Translation result dictionary
        index: Error number
        show_original: Whether to always show original message
        debug: Whether to show debug info
    """
    # Header
    print(f"\n{'='*70}")
    print(f"ERROR #{index} | Line {error['line']}, Column {error['column']} | {error['severity'].upper()}")
    print(f"{'='*70}")
    
    # Show friendly explanation
    if translation['found']:
        print(f"\n[What went wrong]")
        print(f"  {translation['explanation']}")
        
        # Show confidence if high enough
        if translation['confidence'] >= 0.85:
            confidence_bar = "#" * int(translation['confidence'] * 10)
            print(f"\n[Confidence] {confidence_bar} {int(translation['confidence'] * 100)}%")
    else:
        print(f"\n[!] Unable to translate this error automatically.")
        print(f"    {translation['explanation']}")
    
    # Show original message when needed
    if show_original or not translation['found']:
        print(f"\n[Original compiler message]")
        print(f"  {error['message']}")
    
    # Debug info
    if debug:
        print(f"\n[DEBUG] Error type: {translation['type']}")
        print(f"[DEBUG] Pattern matched: {translation['found']}")


def main():
    """Main entry point for the friendly compiler."""
    
    # Set up command-line argument parser
    parser = argparse.ArgumentParser(
        description='Friendly C Compiler - Compile C programs with beginner-friendly error messages',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python friendlyCompiler.py test.c
  python friendlyCompiler.py test.c --patterns my_patterns.json
  python friendlyCompiler.py test.c --show-original
  python friendlyCompiler.py test.c --show-stats
  python friendlyCompiler.py test.c --debug
        """
    )
    
    parser.add_argument('source_file', 
                       help='C source file to compile')
    
    parser.add_argument('--patterns', 
                       default='error_patterns.json',
                       help='Path to error patterns JSON file (default: error_patterns.json)')
    
    parser.add_argument('--show-original', 
                       action='store_true',
                       help='Always show original error messages')
    
    parser.add_argument('--show-stats', 
                       action='store_true',
                       help='Show error type statistics at the end')
    
    parser.add_argument('--output', '-o',
                       default='output',
                       help='Output executable name (default: output)')
    
    parser.add_argument('--debug',
                       action='store_true',
                       help='Show debug information')
    
    args = parser.parse_args()
    
    # Check if source file exists
    if not Path(args.source_file).exists():
        print(f"[!] Error: File '{args.source_file}' not found!")
        sys.exit(1)
    
    print("="*70)
    print("FRIENDLY C COMPILER")
    print("="*70)
    print(f"[Compiling] {args.source_file}")
    print(f"[Output] {args.output}")
    print()
    
    # Load error patterns
    patterns = load_error_patterns(args.patterns)
    
    # Capture compilation errors
    error_output, return_code = capture_compiler_output(args.source_file, args.output)
    
    # Display results
    if return_code == 0:
        print("="*70)
        print("[SUCCESS] Compilation completed without errors.")
        print("="*70)
        print(f"[+] Created executable: {args.output}")
        
        # Show warnings if any
        parsed_warnings = parse_gcc_errors(error_output)
        if parsed_warnings:
            print(f"\n[!] Note: Found {len(parsed_warnings)} warning(s)")
            for i, warning in enumerate(parsed_warnings, 1):
                translation = translate_error(warning['message'], patterns, args.debug)
                display_error(warning, translation, i, args.show_original, args.debug)
    else:
        print("="*70)
        print("[FAILED] Compilation failed!")
        print("="*70)
        
        # Parse errors
        parsed_errors = parse_gcc_errors(error_output)
        
        if parsed_errors:
            print(f"\n[Found {len(parsed_errors)} issue(s)]\n")
            
            # For statistics
            error_types = {}
            found_count = 0
            
            # Process each error
            for i, error in enumerate(parsed_errors, 1):
                # Skip 'note' severity for main error count
                if error['severity'] == 'note':
                    continue
                
                # Translate the error
                translation = translate_error(error['message'], patterns, args.debug)
                
                # Track statistics
                error_type = translation['type']
                error_types[error_type] = error_types.get(error_type, 0) + 1
                if translation['found']:
                    found_count += 1
                
                # Display the error
                display_error(error, translation, i, args.show_original, args.debug)
            
            # Show statistics if requested
            if args.show_stats and error_types:
                print("\n" + "="*70)
                print("[ERROR STATISTICS]")
                print("="*70)
                
                print(f"\nTotal errors/warnings: {len(parsed_errors)}")
                print(f"Successfully translated: {found_count}/{len(parsed_errors)} ({found_count*100//len(parsed_errors)}%)")
                
                print("\n[Error Type Breakdown]")
                for error_type, count in sorted(error_types.items(), 
                                               key=lambda x: x[1], 
                                               reverse=True):
                    bar = "#" * count
                    print(f"  {error_type:25s} {bar} ({count})")
        
        else:
            print("\n[!] Could not parse errors. Raw compiler output:")
            print("-"*70)
            print(error_output)
        
        print("\n" + "="*70)
        sys.exit(1)


if __name__ == '__main__':
    main()