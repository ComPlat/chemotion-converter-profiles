import re
import json
from typing import Any, List, Tuple, Optional, Union, Dict
import re
import urllib.parse
import requests

# Regex for typical CHMO IDs: "CHMO:0001234" or "CHMO_0001234"
CHMO_PATTERNS = [
    re.compile(r'\bCHMO[:_]\d{4,7}\b', re.IGNORECASE),
    # URLs like ".../obo/CHMO_0001234"
    re.compile(r'obo[/#]?CHMO[:_]\d{4,7}\b', re.IGNORECASE),
]

def _match_chmo(s: str) -> Optional[str]:
    for rx in CHMO_PATTERNS:
        m = rx.search(s)
        if m:
            return m.group(0)
    return None

def find_chmo_id(obj: Any) -> Tuple[Optional[str], List[Union[str, int]]]:
    """
    Depth-first search for a CHMO identifier anywhere in a nested dict/list structure.
    Returns (chmo_id, path). Path is the access path (keys/indices) to where it was found.
    Stops at the first valid match.
    """
    def dfs(node: Any, path: List[Union[str, int]]) -> Optional[Tuple[str, List[Union[str, int]]]]:
        # 1) If node is a string, test it directly
        if isinstance(node, str):
            hit = _match_chmo(node)
            if hit:
                return hit, path

        # 2) If node is a dict: test keys and values
        if isinstance(node, dict):
            for k, v in node.items():
                # Check key name
                if isinstance(k, str):
                    hit = _match_chmo(k)
                    if hit:
                        return hit, path + [k]
                # Check value if string
                if isinstance(v, str):
                    hit = _match_chmo(v)
                    if hit:
                        return hit, path + [k]
                # Recurse into value
                found = dfs(v, path + [k])
                if found:
                    return found

        # 3) If node is a list/tuple: recurse items
        elif isinstance(node, (list, tuple)):
            for i, item in enumerate(node):
                found = dfs(item, path + [i])
                if found:
                    return found

        return None

    res = dfs(obj, [])
    return res if res else (None, [])


_CHMO_ID_RE = re.compile(r"^CHMO[:_]\d{7}$", re.IGNORECASE)

def _to_iri(id_or_iri: str) -> str:
    """
    Convert an input (CHMO ID with ':' or '_' OR already an IRI) to a proper IRI.

    Accepted forms:
      - "CHMO:0000025"
      - "CHMO_0000025"
      - "http://purl.obolibrary.org/obo/CHMO_0000025"
      - "https://purl.obolibrary.org/obo/CHMO_0000025"

    Returns:
        str: IRI string like "http://purl.obolibrary.org/obo/CHMO_0000025"

    Raises:
        ValueError: If the input cannot be interpreted as CHMO reference.
    """
    s = id_or_iri.strip()

    # If it's already an IRI, accept it as-is (normalize scheme to http if needed)
    if s.lower().startswith(("http://", "https://")):
        return s

    # If it's a CHMO ID, normalize and build the IRI
    if _CHMO_ID_RE.match(s):
        norm = s.replace(":", "_").upper()
        return f"http://purl.obolibrary.org/obo/{norm}"

    raise ValueError(f"Unsupported CHMO reference format: {id_or_iri!r}")


def fetch_chmo_entity(id_or_iri: str,
                      ontology: str = "chmo",
                      timeout: float = 20.0) -> Dict:
    """
    Fetch an entity JSON from the OLS4 API given a CHMO ID or full IRI.

    Args:
        id_or_iri (str): "CHMO:0000025", "CHMO_0000025", or a full IRI.
        ontology (str): OLS ontology key (defaults to "chmo").
        timeout (float): Request timeout in seconds.

    Returns:
        dict: Parsed JSON from OLS4.

    Raises:
        requests.HTTPError: On non-2xx responses.
        ValueError: On invalid input formats.
        requests.RequestException: On network issues.
    """
    # Step 1: Ensure we have an IRI
    iri = _to_iri(id_or_iri)

    # Step 2: Double-encode the IRI so it is safe inside the path segment
    #   First encode reserved chars like ':' '/' -> %3A %2F
    once = urllib.parse.quote(iri, safe="")
    #   Then encode '%' -> %25, producing %253A, %252F, ...
    twice = urllib.parse.quote(once, safe="")

    # Step 3: Build the OLS4 endpoint
    url = f"https://www.ebi.ac.uk/ols4/api/v2/ontologies/{ontology}/entities/{twice}"

    # Step 4: Request and return JSON
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# --- Minimal examples ---
if __name__ == "__main__":
    print(fetch_chmo_entity("CHMO:0000025")["iri"])            # via CHMO:...
    print(fetch_chmo_entity("CHMO_0000025")["iri"])            # via CHMO_...
    print(fetch_chmo_entity("http://purl.obolibrary.org/obo/CHMO_0000025")["iri"])  # via IRI
