"""One-click launcher: reuse the editor or start its hidden local helper."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

APP = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8780/'


def ready():
    try:
        with urlopen(URL + 'api/health', timeout=0.6) as response:
            value = json.load(response)
        return value.get('app') == 'lg-reverse-lab-editor' and value.get('version') == '0.2.1'
    except (OSError, ValueError):
        return False


def main():
    if not ready():
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        with (APP / 'server.log').open('a', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, str(APP / 'server.py')], cwd=APP,
                                       stdout=log, stderr=log, creationflags=flags)
        for _ in range(50):
            if ready():
                break
            if process.poll() is not None:
                raise RuntimeError('The editor did not start. Check server.log in this directory.')
            time.sleep(0.2)
        else:
            raise RuntimeError('The editor timed out while starting. Check server.log in this directory.')
    webbrowser.open(URL)
    print('Editor opened: ' + URL)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc))
        sys.exit(1)
