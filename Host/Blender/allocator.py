"""Hand back to the system the memory this process has already freed.

Blender on Windows allocates through TBB's scalable allocator, which keeps what is freed in its own caches instead
of returning it. Measured: four level imports peaking at 12.7 GB, then an emptied file, still held 7.7 GB until TBB
was told to clean (5.6 GB after); plain Blender data does the same (8.1 GB held after emptying, 0.76 GB after
cleaning). Cleaning returns only memory nothing holds, so no result changes. It runs after the moments that free
the most: a command's long work settling, and a file opening (which frees the file before it). A process that does
not allocate through TBB has nothing for this to do."""

import ctypes
import sys

import bpy

#: ``scalable_allocation_command``'s commands and answers (oneTBB ``scalable_allocator.h``).
_CLEAN_ALL_BUFFERS = 0
_CLEAN_THREAD_BUFFERS = 1
_DONE = 0
_NO_EFFECT = 4


def _allocation_command():
    if sys.platform != "win32":
        return None
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    handle = kernel32.GetModuleHandleW("tbbmalloc.dll")
    if not handle:
        return None
    command = ctypes.CDLL("tbbmalloc.dll", handle=handle).scalable_allocation_command
    command.argtypes = [ctypes.c_int, ctypes.c_void_p]
    command.restype = ctypes.c_int
    return command


#: TBB's ``scalable_allocation_command`` when this process allocates through TBB, else None.
_COMMAND = _allocation_command()


def release():
    """Return to the system what the calling thread's and the shared TBB caches hold."""
    if _COMMAND is None:
        return
    for request in (_CLEAN_THREAD_BUFFERS, _CLEAN_ALL_BUFFERS):
        answer = _COMMAND(request, None)
        if answer not in (_DONE, _NO_EFFECT):
            raise RuntimeError("[allocator] TBB refused to clean its caches (command {0}, answer {1})".format(
                request, answer))


@bpy.app.handlers.persistent
def _on_load_post(_path):
    release()


def register():
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
