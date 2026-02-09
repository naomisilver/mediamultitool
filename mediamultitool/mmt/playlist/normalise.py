def normalise(s):
    """ small helper to strip down to the absolute bare required data for string/partial string matching """

    s = s.lower().strip()
    illegal = '<>:"/\\|?*\''
    s = "".join(c for c in s if c not in illegal) # solves the general case of illegal os characters (breaks AC/DC but is solved by discrete artist search)
    s = s.rstrip(".") # solves the case of hkmori's "i just want to be your friend..."
    return s