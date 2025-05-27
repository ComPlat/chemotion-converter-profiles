import json
from pathlib import Path

from converter_app.profile_migration.utils.registration import Migrations
from converter_app.validation import validate_profile


def build_index():
    public_fb = Path(__file__).parent / 'profiles' / 'public'

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
    if xxx == 'build_index':
        build_index()