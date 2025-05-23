from pathlib import Path

from converter_app.profile_migration.utils.registration import Migrations

profile_dir = Path(__file__).parent.parent.joinpath('profiles')
Migrations().run_migration(str(profile_dir))