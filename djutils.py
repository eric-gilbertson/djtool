import datetime
import pathlib
import shutil
import subprocess

def logit(msg):
    timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S: ")
    msg = f'{timestr}:  {msg}'
    print(msg)
    with open(get_logfile_path(), 'a') as logfile:
        logfile.write(msg + '\n')


def get_logfile_path():
    return str(pathlib.Path.home()) + "/djtool_log.txt"

def get_certifi_version(python_path):
    logit(f"Check certifi version")
    result = subprocess.run( [python_path, "-m", "pip", "show", "certifi"], capture_output=True,)
    stdout = str(result.stdout.strip())
    token = "Version:"
    index = stdout.find("Version:")
    version = ''
    if index != -1:
        start_index = index + len(token)
        end_index = stdout.find('\\n', start_index)
        if end_index > start_index:
            version = stdout[start_index:end_index].strip()

    logit(f"Certifi version: -{version}-")
    return version

def upgrade_certifi(python_path):
    logit(f"Installing/updating certifi for: {python_path}")

    try:
        logit("Try installing certifi with pip")
        subprocess.check_call([ python_path, "-m", "pip", "install", "--upgrade", "certifi"])
        return True
    except Exception as ex:
        logit(f"Error installing certifi with pip: {ex}")
        homebrew_path = shutil.which('brew')
        if homebrew_path:
            logit("Try installing certifi with brew.")
            try:
                subprocess.check_call([homebrew_path, 'install', 'certifi'])
                return True
            except Exception as ex:
                logit(f"Error installing certifi with brew: {ex}")

    return False

def compare_python_versions(version1, version2):
    # Split by '.' and convert components to integers
    v1_components = [int(x) for x in version1.split(".")]
    v2_components = [int(x) for x in version2.split(".")]

    # Pad shorter list with zeros for correct comparison (e.g. 1.0 is same as 1.0.0)
    max_len = max(len(v1_components), len(v2_components))
    v1_components = v1_components + [0] * (max_len - len(v1_components))
    v2_components = v2_components + [0] * (max_len - len(v2_components))

    # Python can compare lists/tuples element-wise
    if v1_components < v2_components:
        return -1
    elif v1_components > v2_components:
        return 1
    else:
        return 0

