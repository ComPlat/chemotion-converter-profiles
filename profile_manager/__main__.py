import json
import os
import shutil
import sys
from typing import BinaryIO, cast
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
    base_path = pyprojroot.find_root(pyprojroot.has_dir("build"))
    docs_profile_dir = Path(base_path, "docs", "atch", "server", "profiles")
    docs_reader_dir = Path(base_path, "docs", "atch", "server", "readers")
    os.makedirs(docs_profile_dir, exist_ok=True)
    os.makedirs(docs_reader_dir, exist_ok=True)
    md_file = MdUtils(file_name='index', title=program_name)
    # Additional Markdown syntax...
    md_file.new_paragraph(f"{program_name} is a very powerful python file converter "
                          f"running as a stand-alone flask server or included in an ELN or scientific Repository "
                          f"(like the {md_file.new_inline_link(link="https://chemotion.net/", text="Chemotion ELN")}, other ELNs we cannot guarantee) "
                          f"and called via API during file upload. "
                          f"For local and offline users, it is also possible to use it as an CLI tool.")

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
                reader_link = f"<a href=\"atch/server/readers/{reader.name}\" download>{reader.name}</a>"

                reader_entry = {
                    "class name": my_ast[0],
                    "identifier": my_ast[1],
                    "priority": my_ast[2],
                    "check": my_ast[3].strip() if my_ast[3] else "",
                }

                readers_dict[reader_link] = reader_entry

            except Exception as e:
                print(f"Skipping {reader.name}: {e}")
                continue

    md_file.new_header(level=1, title='Readers')

    md_file.new_paragraph("A reader is a python class file handling the translation of your input file format to a usable python object."
                          " It is created by providing an example file to the developers or python coders and used and defined by the " +
                          md_file.new_inline_link(link="https://github.com/ComPlat/chemotion-converter-app",
                                                  text="converter app backend") + ".")

    table_header = ["file name (click to download from this GitHub.io mirror)"]
    if reader_entry:
        table_header += list(reader_entry.keys())
    dict_to_md_table(md_file, table_header, readers_dict)


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
        profile_entry = {
            "reader": json_profile["data"]["metadata"].get("reader"),
            "extension": json_profile["data"]["metadata"].get("extension"),
            "title": json_profile.get("title"),
            "description": json_profile.get("description"),
            "devices": json_profile.get("devices"),
            "software": json_profile.get("software"),
            "identifiers": get_identifiers(json_profile)
        }

        # Copy profile JSON to docs and link to the local docs path
        shutil.copy2(profile, docs_profile_dir / profile.name)
        profile_link = (
            f"<a href=\"atch/server/profiles/{profile_id}.json\" download>{profile_id}</a>"
        )
        profiles_dict[profile_link] = profile_entry

    md_file.new_header(level=1, title='Profiles')

    md_file.new_paragraph("A profile is JSON file defining a ruleset on how to convert your input file."
                          " Normally, it is created by uploading an example of your input file to the GUI of the "+
                          md_file.new_inline_link(link="https://github.com/ComPlat/chemotion-converter-client", text="converter client frontend") + ".")

    table_header = ["id (click to download from this GitHub.io mirror)"] + list(profile_entry.keys())
    profiles_sorted = dict(sorted(
        profiles_dict.items(),
        key=lambda item: (item[1].get("extension") or "").lower(),
    ))
    dict_to_md_table(md_file, table_header, profiles_sorted)

    md_file.create_md_file()

    template_path = Path(__file__).parent.joinpath("index_template.html")
    fill_md_into_html(md_file, template_path)



def fill_md_into_html(md_file: MdUtils, html_file: Path):
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
            convert_docs_md_to_html()
    print("EOC reached")
