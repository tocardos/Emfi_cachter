import copy

from numpy import isin
from pycrate_asn1dir import S1AP
import pycrate_mobile.NAS
import sys
import json
from lte_cause import *

# see attach reject commentary
'''
TAU_NOT_ALLOWED = b'\x0C' # 12 
NO_SUITABLE_CELL = b'\x0F' # 15 force the UE to search another TAU
EPS_NOT_ALLOWED = b'\x07' # 7 no EPS switch to 2G
EPS_NONEPS_NOT_ALLOWED = b'\x08' # 8 This EMM cause is sent to the UE when it is not allowed to operate either EPS or non-EPS services. DOS
UE_ID_NOT_DERIVED = b'\x09' # This EMM cause is sent to the UE when the network cannot derive the UE’s identity from the GUTI/S-TMSI/P-TMSI and RAI 
 #e.g. no matching identity/context in the network or failure to validate the UE’s identity due to integrity check failure of the received message.
IMPLICITLY_DETACHED = b'\x0A' # implicitly detach ( used to force reconnect phone 
'''

class IMSI():
    def __init__(self,imsi,reject =LIBLTE_MME_EMM_CAUSE_IMPLICITLY_DETACHED, data=None):
        self.reject = reject
        self.imsi = imsi

    def set_reject(self,NAS_reject):
        self.reject = NAS_reject
    def get_imsi(self):
        return self.imsi
