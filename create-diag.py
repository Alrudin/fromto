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
from typing import List, Tuple, Optional, Dict
from collections import defaultdict


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


def parse_hostname(hostname: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse a hostname of the form P-xxx-yyyzzz.

    Args:
        hostname (str): The hostname string.

    Returns:
        Optional[Tuple[str, str, str]]: (data_center, function, serial) or None if not matching.
    """
    import re
    match = re.match(r"p-([a-z]+)-([a-z]+)(\d+)", hostname, re.IGNORECASE)
    if match:
        data_center, function, serial = match.groups()
        return data_center, function, serial
    return None


def summarize_hosts(nodes: set[str], function_map: Dict[str, str]) -> Dict[str, Dict[str, list[str]]]:
    """
    Group hostnames by function and data center.

    Args:
        nodes (set[str]): Set of node names.
        function_map (Dict[str, str]): Mapping of function codes to human-readable names.

    Returns:
        Dict[str, Dict[str, list[str]]]: {function: {data_center: [hostnames]}}
    """
    summary: Dict[str, Dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for node in nodes:
        parsed = parse_hostname(node)
        if parsed:
            data_center, function, _ = parsed
            function_label = function_map.get(function, function)
            summary[function_label][data_center].append(node)
    return summary


def print_summary_table(summary: Dict[str, Dict[str, list[str]]]) -> None:
    """
    Print a summary table grouping servers by function and data center.

    Args:
        summary (Dict[str, Dict[str, list[str]]]): Grouped hostnames.
    """
    print("\nServer Grouping by Function and Data Center:")
    print("Function      Data Center      Hostnames")
    print("----------------------------------------------")
    for function, dc_dict in summary.items():
        for data_center, hosts in dc_dict.items():
            print(f"{function:<13} {data_center:<15} {', '.join(hosts)}")
    print()


def generate_mermaid(flows: List[Tuple[str, str]]) -> str:
    """
    Generate a Mermaid flowchart from a list of flows, grouping servers in subgraphs by function and data center.
    If the number of nodes of any type in a data center is greater than 5, collapse them into a single node labeled with the function.
    Hostnames of the form P-xxx-yyyzzz are parsed for function and data center.
    Function codes (e.g., 'sys', 'idx') are mapped to human-readable names.

    Args:
        flows (List[Tuple[str, str]]): List of (from, to) node pairs.

    Returns:
        str: Mermaid diagram as a string.
    """
    function_map = {
        'sysk': 'Syslog koncernet',
        'idx': 'Indexer',
    }
    nodes = set()
    for from_node, to_node in flows:
        nodes.add(from_node)
        nodes.add(to_node)
    # Group nodes by function and data center
    summary = summarize_hosts(nodes, function_map)
    # Track collapsed nodes
    collapsed_nodes = set()
    collapsed_map = {}  # node -> collapsed node name
    lines = ["flowchart TD"]
    # Create subgraphs for each function and data center
    for function, dc_dict in summary.items():
        for data_center, hosts in dc_dict.items():
            subgraph_label = f"{function} - {data_center}"
            if len(hosts) > 5:
                # Collapse nodes into one
                collapsed_node = f"{function}_{data_center}".replace(' ', '_')
                collapsed_label = f"{function} ({data_center})"
                lines.append(f'    "{collapsed_node}"["{collapsed_label}"]')
                for node in hosts:
                    collapsed_nodes.add(node)
                    collapsed_map[node] = collapsed_node
            else:
                lines.append(f"    subgraph {subgraph_label}")
                for node in sorted(hosts):
                    label = node
                    parsed = parse_hostname(node)
                    if parsed:
                        _, func, _ = parsed
                        if func in function_map:
                            label = f'{node} {function_map[func]}'
                    else:
                        node_lower = node.lower()
                        if 'sys' in node_lower:
                            label = f'{node} Syslog'
                        elif 'idx' in node_lower:
                            label = f'{node} indexer'
                        else:
                            label = f'{node} host'
                    lines.append(f'        "{node}"["{label}"]')
                lines.append("    end")
    # Add nodes not matching the pattern to the main graph
    for node in sorted(nodes):
        if not parse_hostname(node):
            label = node
            node_lower = node.lower()
            if 'sys' in node_lower:
                label = f'{node} Syslog'
            elif 'idx' in node_lower:
                label = f'{node} indexer'
            else:
                label = f'{node} host'
            lines.append(f'    "{node}"["{label}"]')
    # Then define edges, redirecting to collapsed nodes if needed
    edge_set = set()
    for from_node, to_node in flows:
        from_actual = collapsed_map.get(from_node, from_node)
        to_actual = collapsed_map.get(to_node, to_node)
        # Avoid self-loops for collapsed nodes
        if from_actual == to_actual:
            continue
        edge = (from_actual, to_actual)
        if edge not in edge_set:
            lines.append(f'    "{from_actual}" --> "{to_actual}"')
            edge_set.add(edge)
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
