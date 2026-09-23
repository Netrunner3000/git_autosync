"""Keep a stray Objective-C exception from aborting the whole app.

macOS 27 / Qt: an NSException raised inside AppKit event dispatch unwinds into
C++, hits std::terminate and the process dies on SIGABRT with nothing written
anywhere — the tray-click crash was one instance (-[NSEvent clickCount] raising
an assertion inside libqcocoa). Removing that call fixed the trigger; this
covers the class.

Two things, both through ctypes so no PyObjC dependency is added:

1. Register NSApplicationCrashOnExceptions = NO, so AppKit's event loop logs an
   exception raised during event handling instead of turning it into a crash.
   It must be registered before NSApplication reads it, i.e. before the
   QApplication is constructed.
2. Install an uncaught-exception handler that appends name, reason and call
   stack to the app's own log directory, so a crash that still gets through
   leaves evidence instead of a silent abort.
"""
import ctypes
import ctypes.util
from datetime import datetime

from . import paths

_handler_ref = None   # keep the ctypes callback alive for the process lifetime

try:
    _objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    _objc.objc_getClass.restype = ctypes.c_void_p
    _objc.objc_getClass.argtypes = [ctypes.c_char_p]
    _objc.sel_registerName.restype = ctypes.c_void_p
    _objc.sel_registerName.argtypes = [ctypes.c_char_p]
except Exception:
    _objc = None


def _msg(restype, *argtypes):
    """objc_msgSend needs a fresh prototype per signature."""
    return ctypes.cast(_objc.objc_msgSend, ctypes.CFUNCTYPE(restype, *argtypes))


def _cls(name: bytes):
    return _objc.objc_getClass(name)


def _sel(name: bytes):
    return _objc.sel_registerName(name)


def _nsstring(text: str):
    send = _msg(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
    return send(_cls(b"NSString"), _sel(b"stringWithUTF8String:"), text.encode())


def _log(message: str) -> None:
    try:
        path = paths.user_log_dir() / "crash.log"
        with open(path, "a") as fh:
            fh.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n{message}\n")
    except Exception:
        pass


def install() -> bool:
    """Returns True if both guards were applied."""
    if _objc is None:
        return False
    try:
        # 1. AppKit: log, don't crash, on exceptions raised during event dispatch.
        send_id = _msg(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        send_bool = _msg(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)
        send_dict = _msg(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p)
        send_void = _msg(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

        no = send_bool(_cls(b"NSNumber"), _sel(b"numberWithBool:"), False)
        d = send_dict(_cls(b"NSDictionary"), _sel(b"dictionaryWithObject:forKey:"),
                      no, _nsstring("NSApplicationCrashOnExceptions"))
        defaults = send_id(_cls(b"NSUserDefaults"), _sel(b"standardUserDefaults"))
        send_void(defaults, _sel(b"registerDefaults:"), d)

        # 2. Last-resort handler: record what killed us.
        global _handler_ref
        foundation = ctypes.cdll.LoadLibrary(ctypes.util.find_library("Foundation"))
        proto = ctypes.CFUNCTYPE(None, ctypes.c_void_p)

        def _on_uncaught(exception):
            try:
                get = _msg(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
                utf8 = _msg(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)
                parts = []
                for sel in (b"name", b"reason", b"callStackSymbols"):
                    obj = get(exception, _sel(sel))
                    if not obj:
                        continue
                    desc = get(obj, _sel(b"description"))
                    raw = utf8(desc or obj, _sel(b"UTF8String"))
                    parts.append(raw.decode(errors="replace") if raw else "?")
                _log("Uncaught Objective-C exception\n" + "\n".join(parts))
            except Exception:
                _log("Uncaught Objective-C exception (details unavailable)")

        _handler_ref = proto(_on_uncaught)
        foundation.NSSetUncaughtExceptionHandler.argtypes = [proto]
        foundation.NSSetUncaughtExceptionHandler.restype = None
        foundation.NSSetUncaughtExceptionHandler(_handler_ref)
        return True
    except Exception:
        return False
