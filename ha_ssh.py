"""Shared SSH helper for HA scripts. Import and use ssh_connect()."""
import json
import os
import shlex
import urllib.request

import paramiko

from project_secrets import secret

HOST = secret("HA_SSH_HOST", secret("HA_HOST", ""))
PORT = int(secret("HA_SSH_PORT", "22"))
USER = secret("HA_SSH_USER", "root")
KEY = os.path.expanduser(secret("HA_SSH_KEY", "~/.ssh/ha_ed25519"))

TOKEN = secret("HA_TOKEN")
BASE = secret("HA_BASE_URL", f"http://{secret('HA_HOST', HOST)}:{secret('HA_PORT', '8123')}")
HDR = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"} if TOKEN else {
    "Content-Type": "application/json"
}

PASSWORD = secret("HA_SSH_PASSWORD", "")

def ssh_connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # Try key auth first, fall back to password (OpenSSH 10.3 compat)
    try:
        k = paramiko.Ed25519Key.from_private_key_file(KEY)
        c.connect(HOST, port=PORT, username=USER, pkey=k, timeout=10,
                  look_for_keys=False, allow_agent=False)
    except (paramiko.AuthenticationException, FileNotFoundError):
        c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=10,
                  look_for_keys=False, allow_agent=False)
    return c

def run(c, cmd):
    _, o, e = c.exec_command(cmd)
    return o.read().decode('utf-8', 'replace').strip(), e.read().decode('utf-8', 'replace').strip()

def write_remote(c, content, remote_path):
    tmp = '/tmp/_fix_' + str(abs(hash(remote_path)) % 9999)
    i = c.exec_command(f'cat > {tmp}')
    i[0].write(content if isinstance(content, bytes) else content.encode('utf-8'))
    i[0].channel.shutdown_write()
    i[0].channel.recv_exit_status()
    sudo_password = secret("HA_SUDO_PASSWORD", required=True)
    cmd = "printf '%s\\n' " + shlex.quote(sudo_password) + " | sudo -S cp " + shlex.quote(tmp) + " " + shlex.quote(remote_path)
    _, o, _ = c.exec_command(cmd)
    o.read()

def ha_post(path, data={}):
    if not TOKEN:
        raise RuntimeError("Missing HA_TOKEN")
    req = urllib.request.Request(f'{BASE}{path}',
        data=json.dumps(data).encode(), method='POST', headers=HDR)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status

def ha_get(path):
    if not TOKEN:
        raise RuntimeError("Missing HA_TOKEN")
    req = urllib.request.Request(f'{BASE}{path}', headers=HDR)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())
