"""Native Windows drag & drop for a Tk window (no extra packages).

Subclasses the top-level window procedure and handles WM_DROPFILES.
"""

import sys

WM_DROPFILES = 0x0233
GWLP_WNDPROC = -4


def enable(root, sink):
    """Put each dropped list of paths into sink (a queue.Queue). Returns True if active.

    The window procedure runs inside Tcl's event loop, so it must not call
    back into Tk; the caller drains the queue from its own after() loop."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    user32.GetParent.restype = wintypes.HWND
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.CallWindowProcW.restype = LRESULT
    user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
    shell32.DragQueryFileW.restype = wintypes.UINT
    shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    shell32.DragFinish.argtypes = [wintypes.HANDLE]

    root.update_idletasks()
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    shell32.DragAcceptFiles(hwnd, True)

    def proc(h, msg, wparam, lparam):
        if msg == WM_DROPFILES:
            count = shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
            paths = []
            for i in range(count):
                n = shell32.DragQueryFileW(wparam, i, None, 0) + 1
                buf = ctypes.create_unicode_buffer(n)
                shell32.DragQueryFileW(wparam, i, buf, n)
                paths.append(buf.value)
            shell32.DragFinish(wparam)
            sink.put(paths)
            return 0
        return user32.CallWindowProcW(old, h, msg, wparam, lparam)

    new_proc = WNDPROC(proc)
    old = user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ctypes.cast(new_proc, ctypes.c_void_p))
    root._dnd_keepalive = (new_proc, old)  # keep the callback alive
    return True
