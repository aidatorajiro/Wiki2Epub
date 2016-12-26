# webutil.py: 主にwebアクセス関連の便利な関数群。
import requests
import vcr
import os
import time

def script_path(*args):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), *args)

# ローカルからファイルを取得する
def get_local_file(path):
    with open(path, 'rb') as f:
        ret = f.read()
    return ret

# インターネットからファイルを取得する。
def get_global_file_as_object(url):
    return requests.get(url)

def get_global_file(url):
    return get_global_file_as_object(url).content