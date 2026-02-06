import json
import os
import shutil
import sys
from html import escape
from typing import BinaryIO, cast
from importlib.resources import files
from pathlib import Path

import pyprojroot
from converter_app.profile_migration.utils.registration import Migrations
from converter_app.validation import validate_profile

from mdutils.mdutils import MdUtils # https://github.com/didix21/mdutils

from profile_manager import get_chmo
from profile_manager.parse_ast import read_metadata_from_readercode

program_name = "Chemotion Converter"
profiles_dict = {}
readers_dict = {}

should_translate_code = False
code_explainer_json_path: Path = Path(__file__).parent.parent.joinpath("code_explainer.json")

def clean_value(val):
    # Convert to string and replace line breaks with space
    return str(val).replace("\n", "<br>").replace("\r", " ").strip()

def get_identifiers(json_file):
    identifiers = json_file.get("identifiers", [])

    required_identifiers = []
    for entry in identifiers:
        if entry.get("optional", True):
            continue

        key = entry.get("key")
        if key is None and entry.get("type") == "tableHeader":
            key = f"tableHeader (line{entry.get('lineNumber')})"

        if key is None or entry.get("value") is None:
            continue

        required_identifiers.append((key, entry.get("value")))

    return required_identifiers


def build_index():
    profile_entry = {}
    reader_entry = {}

    profile_dir = Path(__file__).parent.parent.joinpath('profiles/public')
    base_path = pyprojroot.find_root(pyprojroot.has_dir("build"))
    docs_profile_dir = Path(base_path, "docs", "atch", "server", "profiles")
    docs_reader_dir = Path(base_path, "docs", "atch", "server", "readers")
    os.makedirs(docs_profile_dir, exist_ok=True)
    os.makedirs(docs_reader_dir, exist_ok=True)

    reader_dir = files("converter_app") / "readers"

    for reader in sorted(reader_dir.iterdir(), key=lambda r: r.name):
        if reader.is_file() and reader.name.endswith(".py"):
            try:
                my_ast = read_metadata_from_readercode(reader)

                # works for Path and Traversable
                reader_name = reader.name.rsplit(".", 1)[0]
                reader_target = docs_reader_dir / reader.name
                if isinstance(reader, Path):
                    shutil.copy2(reader, reader_target)
                else:
                    with reader.open("rb") as source, open(reader_target, "wb") as dest:
                        # noinspection PyTypeChecker
                        shutil.copyfileobj(
                            cast(BinaryIO, source), cast(BinaryIO, dest)
                        )

                check_fkt_block = my_ast[3].strip() if my_ast[3] else ""

                reader_entry = {
                    "class name": my_ast[0],
                    "identifier": my_ast[1],
                    "priority": my_ast[2],
                    "check": check_fkt_block,
                }

                readers_dict[reader.name] = reader_entry

            except Exception as e:
                print(f"Skipping {reader.name}: {e}")
                continue

    check_translation = update_code_explainer_json() # if should_translate_code else load from disk or return empty dict

    # Attach explanation (dict: { "<reader filename>": <explanation> }) to readers_dict entries, if available
    for reader_filename, entry in readers_dict.items():
        if reader_filename in check_translation:
            entry["check explanation"] = check_translation[reader_filename]
        else:
            entry["check explanation"] = "No explanation or no valid check Function available."


    table_header = ["file name (click to download from this GitHub.io mirror)"]
    if reader_entry:
        table_header += list(reader_entry.keys())

    readers_row_data, readers_column_defs = readers_dict_to_grid_config()
    readers_table = dict_to_ag_grid_html(readers_row_data, readers_column_defs,  "readers")

    for profile in profile_dir.glob("*.json"):
        with open(profile, "r") as file:
            try:
                json_profile = json.loads(file.read())
            except json.JSONDecodeError:
                print(f"Skipping {profile}: invalid JSON")
                continue
        ''' to be done later, validation is needed or all versions to avoid faulty jsons
        try:
            validate_profile(json_profile)
        except:
            pass # continue
        '''

        # Extract relevant fields
        profile_id = json_profile.get("id")

        ols, _ = get_chmo.find_chmo_id(json_profile)
        try:
            ontology = get_chmo.fetch_chmo_entity(ols) if ols else {}
        except Exception as e :
            print(f"Error fetching ontology for {profile_id}: {e}, setting ontology to empty dict")
            ontology = {}

        profile_entry = {
            "reader": json_profile["data"]["metadata"].get("reader"),
            "extension": json_profile["data"]["metadata"].get("extension"),
            "title": json_profile.get("title"),
            "description": json_profile.get("description"),
            "devices": json_profile.get("devices"),
            "software": json_profile.get("software"),
            "identifiers": get_identifiers(json_profile),
            "ontology": (str(ols) if ols else "n.d.") + ": " + ( str(ontology.get("label") if ols else "") )
        }

        # Copy profile JSON to docs and link to the local docs path
        shutil.copy2(profile, docs_profile_dir / profile.name)
        profiles_dict[profile_id] = profile_entry

    profiles_row_data, profiles_column_defs = profiles_dict_to_grid_config()
    profiles_table = dict_to_ag_grid_html(profiles_row_data, profiles_column_defs, "profiles")

    template_path = Path(__file__).parent.joinpath("index_template.html")
    fill_data_into_html(template_path, readers_table, profiles_table)
    build_html_links_page(base_path)


def readers_dict_to_grid_config():
    row_data = [
        {"file name": k, **v}
        for k, v in readers_dict.items()
    ]

    header_tooltips = {
        "priority": "Priority of the reader if two or more reader checks would fit for the same file. Lower values are prioritized over higher ones.",
        "class name": "Name of the reader class in python code.",
        "check": "Python code block that checks whether a given file is supported by the reader.",
        "check explanation": "AI supported explanation of the reader's check function.",
    }

    special_column_defs = {
        "file name": {"field": "file name", "pinned": "left",  "cellRenderer": "linkRenderer"},
        "check": {"cellRenderer": "codeCellRenderer", "flex": 2},
        "check explanation": {"cellRenderer": "codeCellRenderer", "flex": 2},
    }

    column_defs = [
        special_column_defs["file name"],
        *[{
            "field": key,
            **special_column_defs.get(key, {}),
            **({
                "headerComponent": "HeaderWithInfo",
                "headerComponentParams": {"infoText": header_tooltips[key]}
            } if key in header_tooltips else {})
        } for key in next(iter(readers_dict.values()))],
    ]
    return row_data, column_defs

def profiles_dict_to_grid_config():
    row_data = [
        {"id": k, **v}
        for k, v in profiles_dict.items()
    ]
    special_column_defs = {
        "id": {"field": "id", "pinned": "left", "cellRenderer": "linkRenderer"},
        "identifiers": {"valueFormatter": "value && value.map(v => `${v[0]}: ${v[1]}`).join(', ')"},
        "software": {"valueFormatter": "value && value.map(v => `${v[0]}: ${v[1]}`).join(', ')"},
        "devices": {"valueFormatter": "value && value.map(v => `${v[0]}: ${v[1]}`).join(', ')"},
    }
    column_defs = [
        special_column_defs["id"],
        *[{
            "field": key,
            **special_column_defs.get(key, {})
        } for key in next(iter(profiles_dict.values()))],
    ]
    return row_data, column_defs


def dict_to_ag_grid_html(row_data, column_defs, dict_type):
    grid_id = f"""{dict_type}Grid"""

    return f"""<div id="{grid_id}" class="ag-theme-alpine" style="height: 400px; width: 100%;" data-dict-type="{dict_type}"></div>
        <script type="application/json" id="{grid_id}-column-defs">{json.dumps(column_defs)}</script>
        <script type="application/json" id="{grid_id}-row-data">{json.dumps(row_data)}</script>
        """



def fill_data_into_html(html_file: Path, readers_table, profiles_table):
    with open(html_file, "r") as file:
        html_content = file.read()
    html_content = html_content.replace("{{ PROGRAM_NAME }}", program_name)
    html_content = html_content.replace("{{ READERS_TABLE }}", readers_table)
    html_content = html_content.replace("{{ PROFILES_TABLE }}", profiles_table)
    base_path = pyprojroot.find_root(pyprojroot.has_dir("build"))
    os.makedirs(os.path.join(base_path, "docs"), exist_ok=True)
    index_path = Path(base_path, "docs", "index.html")
    with open(index_path, "w") as file:
        file.write(html_content)


def build_html_links_page(base_path: Path):
    docs_dir = Path(base_path, "docs")
    atch_dir = docs_dir / "atch"
    links_page_name = "all-pages.html"

    # Keep these customizable for future filtering needs.
    additional_folder_blacklist = {".git", "__pycache__"}
    extension_blacklist = {".md", ".jpg", ".jpeg", ".gif", ".css", ".js", ".json", ".txt", ".py", ".exe", ".sh"}
    folder_blacklist = {"server", *additional_folder_blacklist}

    root_links = []
    atch_links = []

    for page in sorted(docs_dir.iterdir()):
        if not page.is_file():
            continue
        if page.name == links_page_name or page.suffix.lower() in extension_blacklist:
            continue
        root_links.append(page.relative_to(docs_dir).as_posix())

    if atch_dir.exists():
        for page in sorted(atch_dir.rglob("*")):
            if not page.is_file() or page.suffix.lower() in extension_blacklist:
                continue
            rel_to_atch = page.relative_to(atch_dir)
            if any(part in folder_blacklist for part in rel_to_atch.parts[:-1]):
                continue
            atch_links.append(page.relative_to(docs_dir).as_posix())

    def render_links(paths):
        if not paths:
            return "<li>No matching files found.</li>"
        return "\n".join(
            f'        <li><a href="{escape(path)}">{escape(path)}</a></li>' for path in paths
        )

    html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>All Pages</title>
    <link rel="stylesheet" href="global.css" />
  </head>
  <body>
    <header>
      <h1>All Pages</h1>
      <nav>
        <a href="index.html">Back</a>
      </nav>
    </header>
    <main>
      <h2>docs root</h2>
      <ul>
{render_links(root_links)}
      </ul>
      <h2>docs/atch (without docs/atch/server)</h2>
      <ul>
{render_links(atch_links)}
      </ul>
    </main>
  </body>
</html>
"""

    with open(docs_dir / links_page_name, "w") as file:
        file.write(html_content)

def validate_profiles():
    profile_dir = Path(__file__).parent.parent.joinpath('profiles/public')
    for profile in profile_dir.glob("*.json"):
        with open(profile, "r") as file:
            validate_profile(json.loads(file.read()))


def migrate_profiles():
    profile_dir = Path(__file__).parent.parent.joinpath('profiles')
    Migrations().run_migration(str(profile_dir))

import json

def update_code_explainer_json():
    """
    Load or (re)generate a JSON cache of LLM-produced explanations for reader code blocks.

    This function has two modes controlled by the global flag `should_translate_code`:

    1) Translation disabled (`should_translate_code` is False)
       - Attempts to load an existing JSON file located at `code_explainer_json_path`.
       - If the file does not exist, returns an empty dict.
       - If the file exists but contains invalid JSON (e.g., empty/corrupted), returns an empty dict.

    2) Translation enabled (`should_translate_code` is True)
       - Creates a `ReaderFunctionBlockExplainer` backed by an Ollama LLM endpoint using the
         configuration in `OllamaConfig` (host/model/temperature/num_ctx).
       - Iterates over `readers_dict` (a dict of reader definitions). For each entry:
           * Reads the "check" field (expected to be a non-empty string).
           * Skips entries with missing/invalid "check" content.
           * Calls `explainer.explain(check_code)` and stores the result under the reader name.
           * Ensures the stored value is JSON-serializable; non-serializable results are coerced to `str`.
       - Writes the resulting mapping to `code_explainer_json_path` as UTF-8 JSON.

    Returns:
        dict: A mapping from the reader name to the explanation result (loaded from disk or freshly generated).

    Notes:
        - Requires the globals: `should_translate_code`, `readers_dict`, and `code_explainer_json_path`.
        - Translation mode requires `llm_tools` and a working local Ollama server at the configured host.
        - The output file is overwritten when translation mode is enabled.
    """

    translation = {}

    if not should_translate_code:
        print(
            "Skipping code translation and load local file if exists, because should_translate_code is False. "
            "Update is only possible and only runs locally on good hardware with a working Ollama server."
        )
        path = Path(code_explainer_json_path)

        if not path.exists():
            return {}  # JSON doesn't exist yet

        try:
            with path.open("r", encoding="utf-8") as ce:
                return json.load(ce)
        except json.JSONDecodeError:
            # File exists but is not valid JSON (empty/corrupted)
            return {}

    try:
        import llm_tools
        import llm_tools.code_translator

        explainer = llm_tools.code_translator.ReaderFunctionBlockExplainer(
            llm_tools.code_translator.OllamaConfig(
                host="http://localhost:11434",
                model="devstral-small-2:latest", # change this to a smaller model if needed, devstral-small-2 requires 17 GB RAM while qwen3:8B needs ~ 6 GB
                temperature=0.2,
                num_ctx=4096,
            )
        )
    except Exception as e:
        print(f"Skipping code translation: {e}")
        return translation

    for name, reader in readers_dict.items():
        check_code = reader.get("check")
        if not isinstance(check_code, str) or not check_code.strip():
            print(f"Skipping {name}: invalid or missing 'check'")
            continue

        print(f"Translating code for {name}")
        result = explainer.explain(check_code)

        # Make it JSON-safe if needed
        try:
            json.dumps(result)
            translation[name] = result
        except TypeError:
            translation[name] = str(result)

    Path(code_explainer_json_path).parent.mkdir(parents=True, exist_ok=True)

    with open(code_explainer_json_path, "w", encoding="utf-8") as ce:
        json.dump(translation, ce, ensure_ascii=False, indent=2)

    return translation



"""Will convert all md files in docs folder to html files, to be added an updated later
def convert_docs_md_to_html():
    docs_dir = Path(__file__).parent.parent.joinpath("docs")
    if not docs_dir.exists():
        return
    for md_file in docs_dir.glob("*.md"):
        with open(md_file, "r") as file:
            md_text = file.read()
        html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
        html_title = md_file.stem.replace("_", " ").title()
        html_text = (
            "<!doctype html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            f"  <title>{html_title}</title>\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "  <style>\n"
            "    body { font-family: Arial, sans-serif; margin: 2rem; line-height: 1.6; }\n"
            "    pre { overflow-x: auto; }\n"
            "    code { font-family: \"Courier New\", monospace; }\n"
            "    table { border-collapse: collapse; }\n"
            "    th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            f"{html_body}\n"
            "</body>\n"
            "</html>\n"
        )
        html_path = md_file.with_suffix(".html")
        with open(html_path, "w") as file:
            file.write(html_text)
"""

if __name__ == '__main__':
    sysargs = list(sys.argv)
    # print(sysargs)
    if len(sysargs) >= 3:
        try:
            import ollama
            has_ollama = True
        except ImportError:
            has_ollama = False
        if sys.argv[2] == 'explain_code_blocks' and has_ollama:
            should_translate_code = True
            print("Running explain_code_blocks with translation enabled.")
        else:
            print("Invalid argument or ollama package not installed. "
                  "This is only needed for the explain_code_blocks command and only runs locally on good hardware.")
            print(sys.modules.keys())
    if len(sysargs) >= 2:
        if sys.argv[1] == 'build_index':
            print("Building index.html")
            build_index()

    print("EOC reached")
