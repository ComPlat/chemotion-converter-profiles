import json
import os
import sys
from importlib.resources import files
from pathlib import Path

import markdown
import pyprojroot
from converter_app.profile_migration.utils.registration import Migrations
from converter_app.validation import validate_profile

from mdutils.mdutils import MdUtils # https://github.com/didix21/mdutils

from profile_manager.parse_ast import read_metadata_from_readercode

program_name = "Chemotion Converter"
profiles_dict = {}
readers_dict = {}

def clean_value(val):
    # Convert to string and replace line breaks with space
    return str(val).replace("\n", "<br>").replace("\r", " ").strip()

def get_identifiers(json_file):
    identifiers = json_file.get("identifiers", [])

    # Filter and extract tuples where optional == False
    required_identifiers = [
        (entry.get("key"), entry.get("value"))
        for entry in identifiers
        if not entry.get("optional", True)
           and entry.get("key") is not None
           and entry.get("value") is not None
    ]

    return required_identifiers


def build_index():
    profile_entry = {}
    reader_entry = {}

    profile_dir = Path(__file__).parent.parent.joinpath('profiles/public')
    md_file = MdUtils(file_name='index', title=program_name)
    # Additional Markdown syntax...
    md_file.new_paragraph(f"{program_name} is a very powerful python file converter "
                          f"running as a stand-alone flask server or included in an ELN and called via API during file upload. "
                          f"For local and offline users, it is also possible to use it as an CLI tool.")
    for profile in profile_dir.glob("*.json"):
        with open(profile, "r") as file:
            json_profile = json.loads(file.read())
        try:
            validate_profile(json_profile)
        except:
            pass # continue

        # Extract relevant fields
        profile_id = json_profile.get("id")
        profile_entry = {
            "reader": json_profile["data"]["metadata"].get("reader"),
            "extension": json_profile["data"]["metadata"].get("extension"),
            "title": json_profile.get("title"),
            "description": json_profile.get("description"),
            "devices": json_profile.get("devices"),
            "software": json_profile.get("software"),
            "identifiers": get_identifiers(json_profile)
        }

        # Save to the main dictionary
        profiles_dict[profile_id] = profile_entry

    md_file.new_header(level=1, title='Profiles')

    md_file.new_paragraph("A profile is JSON file defining a ruleset on how to convert your input file."
                          "Normally, it is created by uploading an example of your input file to the GUI of the "+
                          md_file.new_inline_link(link="https://github.com/ComPlat/chemotion-converter-client", text="converter client frontend") + ".")

    table_header = ["id"] + list(profile_entry.keys())
    dict_to_md_table(md_file, table_header, profiles_dict)

    reader_dir = files("converter_app") / "readers"

    for reader in sorted(reader_dir.iterdir(), key=lambda r: r.name):
        if reader.is_file() and reader.name.endswith(".py"):
            try:
                my_ast = read_metadata_from_readercode(reader)

                # works for Path and Traversable
                reader_name = reader.name.rsplit(".", 1)[0]

                reader_entry = {
                    "class name": my_ast[0],
                    "identifier": my_ast[1],
                    "priority": my_ast[2],
                    "check": my_ast[3].strip() if my_ast[3] else "",
                }

                readers_dict[reader_name] = reader_entry

            except Exception as e:
                print(f"Skipping {reader.name}: {e}")
                continue

    md_file.new_header(level=1, title='Readers')

    md_file.new_paragraph("A reader is a python class file handling the translation of your input file format to a usable python object."
                          "Normally, it is created by uploading an example of your input file to the GUI of the " +
                          md_file.new_inline_link(link="https://github.com/ComPlat/chemotion-converter-client",
                                                  text="converter client frontend") + ".")

    table_header = ["file name"] + list(reader_entry.keys())
    dict_to_md_table(md_file, table_header, readers_dict)

    md_file.create_md_file()

    fill_md_into_html(md_file, "index_template.html")



def fill_md_into_html(md_file: MdUtils, html_file):
    with open(html_file, "r") as file:
        html_content = file.read()
    markdown_content = markdown.markdown(md_file.file_data_text, extensions=["tables", "fenced_code"])
    html_content = html_content.replace("{{ PROGRAM_NAME }}", program_name)
    html_content = html_content.replace("{{  TABLE_CONTENT  }}", markdown_content)
    base_path = pyprojroot.find_root(pyprojroot.has_dir("build"))
    os.makedirs(os.path.join(base_path, "docs"), exist_ok=True)
    index_path = Path(base_path, "docs", "index.html")
    with open(index_path, "w") as file:
        file.write(html_content)

def dict_to_md_table(md_file, table_header, dict_to_write):
    table_content = []
    for key in dict_to_write:
        row = [key] + [clean_value(value) for value in dict_to_write[key].values()]
        table_content.append(row)
    table = [table_header] + table_content
    # Flatten for Markdown or similar tools
    flat_table = [cell for row in table for cell in row]
    md_file.new_line()
    md_file.new_table(columns=len(table_header), rows=int(len(flat_table) / len(table_header)), text=flat_table)


def validate_profiles():
    profile_dir = Path(__file__).parent.parent.joinpath('profiles/public')
    for profile in profile_dir.glob("*.json"):
        with open(profile, "r") as file:
            validate_profile(json.loads(file.read()))


def migrate_profiles():
    profile_dir = Path(__file__).parent.parent.joinpath('profiles')
    Migrations().run_migration(str(profile_dir))

if __name__ == '__main__':
    sysargs = list(sys.argv)
    # print(sysargs)
    if len(sysargs) >= 2:
        if sys.argv[1] == 'build_index':
            build_index()
    print("EOC reached")