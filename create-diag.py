"""
Script to generate a Mermaid diagram from a CSV file containing 'from' and 'to' node flows.

Usage:
    python create-diag.py [input_csv] [output_file]
If output_file is omitted, the diagram is printed to stdout.
"""
import csv
import logging
import os
import sys
from typing import List, Tuple, Optional


def setup_logging() -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def read_flows(csv_path: str) -> List[Tuple[str, str]]:
    """
    Read flows from a CSV file with 'from' and 'to' columns.

    Args:
        csv_path (str): Path to the CSV file.

    Returns:
        List[Tuple[str, str]]: List of (from, to) node pairs.
    """
    flows: List[Tuple[str, str]] = []
    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                from_node = row.get('from')
                to_node = row.get('to')
                if from_node is None or to_node is None:
                    logging.warning(f"Skipping row with missing data: {row}")
                    continue
                flows.append((from_node, to_node))
    except FileNotFoundError:
        logging.error(f"File not found: {csv_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading CSV: {e}")
        sys.exit(1)
    return flows


def generate_mermaid(flows: List[Tuple[str, str]]) -> str:
    """
    Generate a Mermaid flowchart from a list of flows, defining all unique nodes first with labels.
    If a node name contains 'sys' (case-insensitive), label it 'Syslog'.
    If it contains 'idx' (case-insensitive), label it 'indexer'.

    Args:
        flows (List[Tuple[str, str]]): List of (from, to) node pairs.

    Returns:
        str: Mermaid diagram as a string.
    """
    nodes = set()
    for from_node, to_node in flows:
        nodes.add(from_node)
        nodes.add(to_node)
    lines = ["graph TD"]
    # Define all nodes first with labels if applicable
    for node in sorted(nodes):
        label = node
        node_lower = node.lower()
        if 'sys' in node_lower:
            label = f'{node} Syslog'
        elif 'idx' in node_lower:
            label = f'{node} indexer'
        lines.append(f'    "{node}"["{label}"]')
    # Then define edges
    for from_node, to_node in flows:
        lines.append(f'    "{from_node}" --> "{to_node}"')
    return '\n'.join(lines)


def main() -> None:
    """
    Main function to read CSV and output Mermaid diagram.
    """
    setup_logging()
    input_csv: str = sys.argv[1] if len(sys.argv) > 1 else os.getenv('FROM_TO_CSV', 'from_to.csv')
    output_file: Optional[str] = sys.argv[2] if len(sys.argv) > 2 else None

    logging.info(f"Reading flows from: {input_csv}")
    flows = read_flows(input_csv)
    if not flows:
        logging.error("No flows found in the input file.")
        sys.exit(1)

    mermaid_diagram = generate_mermaid(flows)

    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(mermaid_diagram)
            logging.info(f"Mermaid diagram written to {output_file}")
        except Exception as e:
            logging.error(f"Failed to write output file: {e}")
            sys.exit(1)
    else:
        print(mermaid_diagram)


if __name__ == "__main__":
    main()
