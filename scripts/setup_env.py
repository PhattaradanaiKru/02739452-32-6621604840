"""Create local secrets without overwriting an existing .env."""
import base64
import pathlib
import secrets

path = pathlib.Path(__file__).resolve().parents[1] / '.env'
if path.exists():
    print('.env exists; kept existing settings.')
else:
    text = (path.parent / '.env.example').read_text()
    values = {
        'AIRFLOW_PASSWORD': secrets.token_urlsafe(18),
        'METADATA_PASSWORD': secrets.token_hex(24),
        'TARGET_PASSWORD': secrets.token_hex(24),
        'AIRFLOW_SECRET_KEY': secrets.token_hex(32),
        'FERNET_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    }
    lines = [line.split('=', 1)[0] + '=' + values[line.split('=', 1)[0]]
             if line.split('=', 1)[0] in values else line for line in text.splitlines()]
    path.write_text('\n'.join(lines) + '\n')
    print('Created .env with random local credentials. See AIRFLOW_PASSWORD to log in.')
