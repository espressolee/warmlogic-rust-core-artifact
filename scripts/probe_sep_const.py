import ctypes
import ctypes.util


def check_security_const():
    path = "/System/Library/Frameworks/Security.framework/Security"
    lib = ctypes.CDLL(path)

    # helper
    def get_const(name):
        try:
            addr = ctypes.CDLL(None).dlsym(lib._handle, name.encode("utf-8"))
            if addr:
                val = ctypes.c_void_p.from_address(addr).value
                # If these are pointers to CFString, value is the address.
                return val
        except Exception as e:
            print(f"Error lookup {name}: {e}")
        return None

    # Constants to look for
    constants = [
        "kSecClass",
        "kSecKeyAlgorithmECIESEncryptionStandardX963SHA256AESGCM",
        "kSecAttrKeyTypeECSECPrimeRandom",
    ]

    for name in constants:
        ptr = get_const(name)
        print(f"{name}: {ptr}")
        if ptr:
            print(f"{name} found.")
        else:
            print(f"{name} NOT found.")


if __name__ == "__main__":
    check_security_const()
