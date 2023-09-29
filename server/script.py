import signal
import os
import sys
import subprocess
import shutil
import time
import fcntl
import user
import requests
from requests.exceptions import RequestException

def signal_handler(sig, frame):
    sys.exit(0)
signal.signal(signal.SIGTERM, signal_handler)

SERVERS_DIR: str = '/repo/servers'
STEAMCMD_DIR: str = '/repo/steamcmd' 
DOT_STEAM_DIR: str = '/home/server/.steam'
SERVER_DIR: str = '/home/server/cs2'
LOCK_FILE_NAME: str = 'watchdog.lock'
CS2_BIN_PATH: str = os.path.join(SERVER_DIR, 'game/bin/linuxsteamrt64/cs2')

def fetch_latest_version() -> int:
    response = requests.get('https://api.steampowered.com/ISteamApps/UpToDateCheck/v1?version=0&format=json&appid=730')
    if response.status_code != 200:
        raise RequestException('steam api response status is not 200')
    response = response.json()
    response = response['response']
    if not response['success']:
        raise RequestException('steam api response says it failed')
    return int(response['required_version'])

def symlink_dir(source: str, target: str) -> None:
    if os.path.lexists(target):
        if os.path.isfile(target) or os.path.islink(target):
            os.remove(target)
        elif os.path.isdir(target):
            shutil.rmtree(target)
    for root, _, files in os.walk(source):
        root_relative: str = os.path.relpath(root, source)
        if root_relative == '.':
            root_relative = '' # why?
        os.mkdir(os.path.join(target, root_relative))
        for filename in files:
            source_file = os.path.join(root, filename)
            target_file = os.path.join(target, root_relative, filename)
            os.symlink(source_file, target_file)

def main() -> None:
    latest_version: int = -1
    server_repo_dir: str = os.path.join(SERVERS_DIR, str(latest_version))
    attempts = 0
    while True:
        if attempts % 18 == 0:
            latest_version: int = fetch_latest_version()
        server_repo_dir: str = os.path.join(SERVERS_DIR, str(latest_version))
        lock_file_path: str = os.path.join(server_repo_dir, LOCK_FILE_NAME)
        if os.path.exists(lock_file_path):
            # Just leak the handle, we need it till the process dies
            lock_file = os.open(lock_file_path, os.O_RDONLY)
            fcntl.flock(lock_file, fcntl.LOCK_SH | fcntl.LOCK_NB)
            break
        attempts += 1
        time.sleep(10)
    symlink_dir(server_repo_dir, SERVER_DIR)
    os.makedirs(os.path.join(DOT_STEAM_DIR, 'sdk64'), exist_ok=True)
    shutil.copyfile(
        os.path.join(STEAMCMD_DIR, 'linux64', 'steamclient.so'), 
        os.path.join(DOT_STEAM_DIR, 'sdk64', 'steamclient.so'))
    try:
        user.post_build(version=latest_version, dir=SERVER_DIR)
    except:
        pass
    subprocess.run([
        CS2_BIN_PATH,
        '-dedicated',
        '+map de_inferno'
    ])

if __name__ == '__main__':
    main()