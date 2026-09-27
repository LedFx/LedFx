import sys,os
from typing import List


def probe( names:List[str] )->List[str]:
    return [ "{}!".format(n) for n in names if n!="" ]   
