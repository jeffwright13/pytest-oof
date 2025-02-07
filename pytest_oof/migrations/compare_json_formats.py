#!/usr/bin/env python3

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, List, Set


def flatten_dict(
    d: Dict[str, Any], parent_key: str = "", sep: str = "."
) -> Dict[str, Any]:
    """Flatten a nested dictionary."""
    items: List = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # For lists, we'll just note the length and type of first item
            items.append((new_key + ".length", len(v)))
            if v:
                sample_item = v[0]
                if isinstance(sample_item, dict):
                    items.extend(
                        flatten_dict(sample_item, new_key + ".item", sep=sep).items()
                    )
                else:
                    items.append((new_key + ".item_type", type(sample_item).__name__))
        else:
            items.append((new_key, type(v).__name__ if v is not None else "None"))
    return dict(items)


def analyze_test_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze test results to get statistics and field information."""
    if not isinstance(results, list):
        return {"error": f"Expected list of test results, got {type(results)}"}

    field_types = {}
    field_presence = {}
    total_tests = len(results)
    outcomes = {}

    for result in results:
        if not isinstance(result, dict):
            continue

        # Track field presence and types
        for field, value in result.items():
            if field not in field_presence:
                field_presence[field] = 0
            field_presence[field] += 1

            if field not in field_types:
                field_types[field] = set()
            field_types[field].add(type(value).__name__)

        # Track outcomes
        outcome = result.get("outcome", "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    return {
        "total_tests": total_tests,
        "outcomes": outcomes,
        "field_types": {k: list(v) for k, v in field_types.items()},
        "field_presence": field_presence,
    }


def compare_formats(original_path: str, new_path: str) -> Dict[str, Any]:
    """Compare the original and new JSON formats."""
    with open(original_path) as f:
        original = json.load(f)
    with open(new_path) as f:
        new = json.load(f)

    # Analyze structure
    original_flat = flatten_dict(original)
    new_flat = flatten_dict(new[0] if isinstance(new, list) else new)

    # Find unique and common keys
    original_keys = set(original_flat.keys())
    new_keys = set(new_flat.keys())

    # Get test results
    original_results = original.get("oof_test_results", [])
    new_results = (
        new[0]["test_results"] if isinstance(new, list) else new.get("test_results", [])
    )

    # Sample of actual values for comparison
    original_sample = {
        k: v for k, v in original.items() if not isinstance(v, (list, dict))
    }
    new_sample = {
        "session": new[0]["session"]
        if isinstance(new, list)
        else new.get("session", {}),
        "test_results_sample": new_results[0] if new_results else {},
    }

    comparison = {
        "structure_comparison": {
            "only_in_original": sorted(original_keys - new_keys),
            "only_in_new": sorted(new_keys - original_keys),
            "common_fields": sorted(original_keys & new_keys),
        },
        "original_format": {
            "top_level_keys": sorted(original.keys()),
            "test_results_analysis": analyze_test_results(original_results),
            "sample_values": original_sample,
        },
        "new_format": {
            "top_level_keys": ["session", "test_results"]
            if isinstance(new, list)
            else sorted(new.keys()),
            "test_results_analysis": analyze_test_results(new_results),
            "sample_values": new_sample,
        },
    }

    # Add summary statistics
    comparison["summary"] = {
        "original_test_count": len(original_results),
        "new_test_count": len(new_results),
        "original_fields_count": len(original_keys),
        "new_fields_count": len(new_keys),
        "common_fields_count": len(original_keys & new_keys),
        "fields_only_in_original": len(original_keys - new_keys),
        "fields_only_in_new": len(new_keys - original_keys),
    }

    return comparison


def main():
    parser = argparse.ArgumentParser(
        description="Compare original and new JSON formats"
    )
    parser.add_argument("original_json", help="Path to the original format JSON file")
    parser.add_argument("new_json", help="Path to the new format JSON file")
    parser.add_argument("--output", "-o", help="Output comparison file (optional)")
    args = parser.parse_args()

    try:
        comparison = compare_formats(args.original_json, args.new_json)

        # Print summary to console
        print("\n=== Format Comparison Summary ===")
        print(f"\nSummary Statistics:")
        for k, v in comparison["summary"].items():
            print(f"{k}: {v}")

        print("\nFields only in original format:")
        pprint(comparison["structure_comparison"]["only_in_original"])

        print("\nFields only in new format:")
        pprint(comparison["structure_comparison"]["only_in_new"])

        print("\nOriginal format test results analysis:")
        pprint(comparison["original_format"]["test_results_analysis"])

        print("\nNew format test results analysis:")
        pprint(comparison["new_format"]["test_results_analysis"])

        # Save detailed comparison if output file specified
        if args.output:
            with open(args.output, "w") as f:
                json.dump(comparison, f, indent=2)
            print(f"\nDetailed comparison saved to: {args.output}")

    except Exception as e:
        print(f"Error comparing formats: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
