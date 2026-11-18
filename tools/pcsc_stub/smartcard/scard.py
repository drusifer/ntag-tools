SCARD_SCOPE_USER=0
SCARD_STATE_PRESENT=0x20
SCARD_STATE_UNAWARE=0
def SCardEstablishContext(*a,**k): return (0,None)
def SCardGetStatusChange(*a,**k): return (0,[])
def SCardReleaseContext(*a,**k): return 0
