import json
import os
import shutil
import sys
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

                reader_entry = {
                    "class name": my_ast[0],
                    "identifier": my_ast[1],
                    "priority": my_ast[2],
                    "check": my_ast[3].strip() if my_ast[3] else "",
                }

                readers_dict[reader.name] = reader_entry

            except Exception as e:
                print(f"Skipping {reader.name}: {e}")
                continue

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


def readers_dict_to_grid_config():
    row_data = [
        {"file name": k, **v}
        for k, v in readers_dict.items()
    ]

    column_defs = [
        {"field": "file name", "pinned": "left",  "cellRenderer": "linkRenderer"},
        *[
            {
                "field": key,
                **({"cellRenderer": "codeCellRenderer", "flex": 3} if key == "check" else {})
            }
            for key in next(iter(readers_dict.values()))
        ],
    ]
    return row_data, column_defs

def profiles_dict_to_grid_config():
    row_data = [
        {"id": k, **v}
        for k, v in profiles_dict.items()
    ]
    column_defs = [
        {"field": "id", "pinned": "left", "cellRenderer": "linkRenderer"},
        *[
            {
                "field": key,
                **({"valueFormatter": "value && value.map(v => `${v[0]}: ${v[1]}`).join(', ')"}
                   if key in ["identifiers", "software", "devices"] else {}
                )
            }
            for key in next(iter(profiles_dict.values()))
        ],
    ]
    return row_data, column_defs


def dict_to_ag_grid_html(row_data, column_defs, dict_type):
    grid_id = f"""{dict_type}Grid"""

    return f"""<div id="{grid_id}" class="ag-theme-alpine" style="height: 400px; width: 100%;"></div>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ag-grid-community/styles/ag-grid.css">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ag-grid-community/styles/ag-theme-alpine.css">
        <script src="https://cdn.jsdelivr.net/npm/ag-grid-community/dist/ag-grid-community.min.js"></script>
        
        <script>
        document.addEventListener("DOMContentLoaded", function () {{
        
          function codeCellRenderer(params) {{
            if (!params.value) return "";
        
            return `
              <code style="
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                white-space: pre-wrap;
                display: block;
                font-size: 12px;
                background: #f6f8fa;
                padding: 6px 8px;
                border-radius: 6px;
                line-height: 1.4;
              ">${{params.value}}</code>
            `;
          }}
          
          function linkRenderer(params) {{
            if (!params.value) return "";
              return `<a href="atch/server/{dict_type}/${{params.value}}{'.json' if dict_type == 'profiles' else ''}" download
                         target="_blank"
                         rel="noopener"
                      >
                ${{params.value}}
              </a>`;
          }}
        
          const gridOptions = {{
            theme: "legacy",
            columnDefs: {json.dumps(column_defs)},
            rowData: {json.dumps(row_data)},
            defaultColDef: {{
              flex: 1,
              sortable: true,
              filter: true,
              resizable: true,
              wrapText: true,
              autoHeight: true
            }},
            components: {{
              codeCellRenderer: codeCellRenderer,
              linkRenderer: linkRenderer,
            }}
          }};
        
          agGrid.createGrid(
            document.getElementById("{grid_id}"),
            gridOptions
          );
        }});
        </script>
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

def validate_profiles():
    profile_dir = Path(__file__).parent.parent.joinpath('profiles/public')
    for profile in profile_dir.glob("*.json"):
        with open(profile, "r") as file:
            validate_profile(json.loads(file.read()))


def migrate_profiles():
    profile_dir = Path(__file__).parent.parent.joinpath('profiles')
    Migrations().run_migration(str(profile_dir))


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
    if len(sysargs) >= 2:
        if sys.argv[1] == 'build_index':
            build_index()
    print("EOC reached")
