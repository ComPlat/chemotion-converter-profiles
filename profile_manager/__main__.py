import json
import os
import sys
import uuid
from io import BufferedReader
from pathlib import Path

import click
from converter_app.profile_migration.utils.registration import Migrations
from converter_app.validation import validate_profile
import converter_app.readers  as readers

from mdutils.mdutils import MdUtils  # https://github.com/didix21/mdutils

from profile_manager.parse_ast import read_metadata_from_readercode

program_name = "Chemotion Converter"

@click.group()
def cli():
    """A collection of helpful tools for maintaining converter profiles."""
    pass


def _clean_value(val):
    # Convert to string and replace line breaks with space
    return str(val).replace("\n", "<br>").replace("\r", " ").strip()


def _get_identifiers(json_file):
    identifiers = json_file.get("identifiers", [])

    # Filter and extract tuples where optional == False
    required_identifiers = [
        f'__{entry.get("key")}__ _must be:_ {entry.get("value")}'
        for entry in identifiers
        if not entry.get("optional", True)
           and entry.get("key") is not None
           and entry.get("value") is not None
    ]

    return '\n'.join(required_identifiers)


def _extract_profiles(profile):
    with open(profile, "r") as file:
        json_profile = json.loads(file.read())
    try:
        validate_profile(json_profile)
    except:
        pass  # continue
    # Extract relevant fields
    profile_id = json_profile.get("id")
    profile_entry = {
        "reader": json_profile["data"]["metadata"].get("reader"),
        "extension": json_profile["data"]["metadata"].get("extension"),
        "title": json_profile.get("title"),
        "description": json_profile.get("description"),
        "devices": json_profile.get("devices"),
        "software": json_profile.get("software"),
        "identifiers": _get_identifiers(json_profile)
    }
    return profile_entry, profile_id

def _build_content_table(content_dict: dict, md_file: MdUtils, table_header: list):

    table_content = []

    for entity_id in content_dict:
        row = [entity_id] + [_clean_value(value) for value in content_dict[entity_id].values()]
        table_content.append(row)

    table = [table_header] + table_content

    # Flatten for Markdown or similar tools
    flat_table = [cell for row in table for cell in row]
    md_file.new_line()
    md_file.new_table(columns=len(table_header), rows=len(content_dict) + 1, text=flat_table, text_align='left')


def _build_profiles_table(md_file: MdUtils):
    profile_dir = Path(__file__).parent.parent.joinpath('profiles/public')
    profiles_dict = {}
    for profile in profile_dir.glob("*.json"):
        profile_entry, profile_id = _extract_profiles(profile)
        profiles_dict[profile_id] = profile_entry

    profile_entry = next(iter(profiles_dict.values()))
    if not profile_entry:
        return
    md_file.new_header(level=1, title='Profiles')

    table_header = ["id"] + list(profile_entry.keys())

    _build_content_table(profiles_dict, md_file, table_header)



def _build_reader_table(md_file: MdUtils):
    reader_dir = Path(readers.__file__).parent
    readers_dict = {}
    for reader in reader_dir.glob("*.py"):
        my_ast = read_metadata_from_readercode(reader)
        reader_name = reader.stem
        reader_entry = {
            "class name": my_ast[0],
            "identifier": my_ast[1],
            "priority": my_ast[2],
            "check":  my_ast[3]
        }

        readers_dict[reader_name] = reader_entry

    md_file.new_header(level=1, title='Readers')
    reader_entry = next(iter(readers_dict.values()))
    if not reader_entry:
        return
    table_header = ["file name"] + list(reader_entry.keys())

    _build_content_table(readers_dict, md_file, table_header)


@cli.command('build')
@click.option('--reader', is_flag=True, default=False, help="If set, the index.md file contains only a table with information about all the readers!")
@click.option('--profiles', is_flag=True, default=False, help="If set, the index.md file contains only a table with information about all the profiles!")
def build_index(reader, profiles):
    """Builds an index.md page. This page contains a table of all public available Converter profiles and reader."""
    md_file_path = Path(__file__).parent.parent.joinpath('build/index.md')
    md_file_path.parent.mkdir(parents=True, exist_ok=True)
    md_file = MdUtils(file_name=md_file_path.__str__(), title=program_name)
    # Additional Markdown syntax...
    md_file.new_paragraph(f"{program_name} is a very powerful python file converter "
                          f"running as a stand-alone flask server or included in an ELN and called via API during file upload. "
                          f"For local and offline users, it is also possible to use it as an CLI tool.")

    if reader and profiles:
        reader = profiles = False

    if not reader:
        _build_profiles_table(md_file)
    if not profiles:
        _build_reader_table(md_file)

    old_file_content = ""
    if md_file_path.exists():
        old_md_file_path = md_file_path.rename(md_file_path.parent.joinpath('index_old.md'))
        with old_md_file_path.open('rb') as old_file:
            old_file_content = old_file.read()
        old_md_file_path.unlink()

    md_file.create_md_file()


    with md_file_path.open('rb') as old_file:
        if old_file.read() == old_file_content:
            click.echo("❌ no update necessary build/index.md is up to date")
            sys.exit(211)
    click.echo("build/index.md is updated")


def validate_profiles():
    profile_dir = Path(__file__).parent.parent.joinpath('profiles/public')
    for profile in profile_dir.glob("*.json"):
        with open(profile, "r") as file:
            validate_profile(json.loads(file.read()))


def migrate_profiles():
    profile_dir = Path(__file__).parent.parent.joinpath('profiles')
    Migrations().run_migration(str(profile_dir))


if __name__ == '__main__':
    cli()
