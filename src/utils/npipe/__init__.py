from os import name as _os_name

if _os_name == "nt":
    from ._win32 import AsyncNamedPipe
else:
    from ._posix import AsyncNamedPipe