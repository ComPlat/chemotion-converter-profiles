import json
import sys
from pathlib import Path

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

    table_header = ["id"] + list(profile_entry.keys())
    table_content = []

    for profile_id in profiles_dict:
        row = [profile_id] + [clean_value(value) for value in profiles_dict[profile_id].values()]
        table_content.append(row)

    table = [table_header] + table_content

    # Flatten for Markdown or similar tools
    flat_table = [cell for row in table for cell in row]
    md_file.new_line()
    md_file.new_table(columns=len(table_header), rows=int(len(flat_table)/len(table_header)), text=flat_table)

    reader_dir = Path(__file__).parent.parent.joinpath('readers')

    for reader in reader_dir.glob("*.py"):
        my_ast = read_metadata_from_readercode(reader)
        reader_name = reader.stem
        reader_entry = {
            "class name": my_ast[0],
            "identifier": my_ast[1],
            "priority": my_ast[2],
            "check": str(my_ast[3]).split('"""')[-1].strip()
        }

        readers_dict[reader_name] = reader_entry

    md_file.new_header(level=1, title='Readers')

    table_header = ["file name"] + list(reader_entry.keys())
    table_content = []

    for profile_id in readers_dict:
        row = [profile_id] + [clean_value(value) for value in readers_dict[profile_id].values()]
        table_content.append(row)

    table = [table_header] + table_content

    # Flatten for Markdown or similar tools
    flat_table = [cell for row in table for cell in row]
    md_file.new_line()
    md_file.new_table(columns=len(table_header), rows=int(len(flat_table) / len(table_header)), text=flat_table)

    md_file.create_md_file()




    # ...

    # todo: write to index html

def validate_profiles():
    profile_dir = Path(__file__).parent.parent.joinpath('profiles/public')
    for profile in profile_dir.glob("*.json"):
        with open(profile, "r") as file:
            validate_profile(json.loads(file.read()))


def migrate_profiles():
    profile_dir = Path(__file__).parent.parent.joinpath('profiles')
    Migrations().run_migration(str(profile_dir))

if __name__ == '__main__':
    print(88)
    sysargs = list(sys.argv)
    print(sysargs)
    if len(sysargs) >= 2:
        print(33)
        if sys.argv[1] == 'build_index':
            print(55)
            build_index()
    print("EOC reached")