import fnmatch
import os

EFFECTLET_LIST = []

files = os.listdir(os.path.dirname(__file__))
for entry in files:
    if fnmatch.fnmatch(entry, "*.npy"):
        EFFECTLET_LIST.append(entry)
