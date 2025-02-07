#!/usr/bin/env python3

import json
import pickle
from pathlib import Path
import argparse
import sys
from dataclasses import dataclass, field, is_dataclass
from typing import List, Dict, Any
from datetime import datetime

def create_dynamic_class(name):
    """Create a new class dynamically."""
    return type(name, (object,), {
        '__init__': lambda self, *args, **kwargs: self.__dict__.update(kwargs),
        '__repr__': lambda self: f"{name}({', '.join(f'{k}={v!r}' for k, v in self.__dict__.items())})",
        'to_dict': lambda self: {k: v for k, v in self.__dict__.items()}
    })

# Cache for dynamic classes
_class_cache = {}

class LegacyUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == 'pytest_oof.utils':
            # Create or get cached dynamic class
            key = f"{module}.{name}"
            if key not in _class_cache:
                _class_cache[key] = create_dynamic_class(name)
            return _class_cache[key]
        return super().find_class(module, name)

def convert_to_json_safe(obj):
    """Convert an object to a JSON-safe format."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (list, tuple)):
        return [convert_to_json_safe(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: convert_to_json_safe(v) for k, v in obj.items()}
    elif hasattr(obj, 'to_dict'):
        return convert_to_json_safe(obj.to_dict())
    elif is_dataclass(obj):
        return {k: convert_to_json_safe(v) for k, v in obj.__dict__.items()}
    elif hasattr(obj, '__dict__'):
        return {k: convert_to_json_safe(v) for k, v in obj.__dict__.items()}
    return obj

def convert_pickle_to_json(pickle_path: str, json_path: str = None) -> None:
    """Convert a pytest-oof pickle results file to JSON format."""
    pickle_path = Path(pickle_path)
    if not json_path:
        json_path = pickle_path.with_suffix('.json')
    
    print(f"Reading pickle file: {pickle_path}")
    try:
        # Load the pickle file with our custom unpickler
        with open(pickle_path, 'rb') as f:
            try:
                results = LegacyUnpickler(f).load()
                print(f"Loaded pickle file. Type of results: {type(results)}")
            except Exception as e:
                print(f"Error unpickling file: {e}", file=sys.stderr)
                raise
        
        # Convert to JSON-safe dictionary
        try:
            results_dict = convert_to_json_safe(results)
            print(f"Converted results to dictionary")
        except Exception as e:
            print(f"Error converting to dictionary: {e}", file=sys.stderr)
            raise
        
        # Save as JSON
        with open(json_path, 'w') as f:
            json.dump(results_dict, f, indent=2, default=str)
        
        print(f"Successfully converted {pickle_path} to {json_path}")
    except Exception as e:
        print(f"Failed to convert file: {e}", file=sys.stderr)
        raise

def main():
    parser = argparse.ArgumentParser(description='Convert pytest-oof pickle results to JSON')
    parser.add_argument('pickle_file', help='Path to the pickle file')
    parser.add_argument('--output', '-o', help='Output JSON file path (optional)')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug output')
    args = parser.parse_args()
    
    try:
        convert_pickle_to_json(args.pickle_file, args.output)
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
