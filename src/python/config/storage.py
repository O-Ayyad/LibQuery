from __future__ import annotations
 
import posixpath
 
import pyarrow.fs as pa_fs
 
from config.settings import (
    USE_HDFS,
    HDFS_HOST,
    HDFS_WEBHDFS_PORT,
    HDFS_USER,
    PARQUET_DIR,
)
 
# All code that needs to read or write Parquet data goes through here
_fs: pa_fs.FileSystem | None = None #singleton
_fsspec_fs = None
 
def get_fs() -> pa_fs.FileSystem:
    #Returns the inuse file syste,
    global _fs, _fsspec_fs
    if _fs is None:
        if USE_HDFS:
            import fsspec
            kwargs: dict = {"host": HDFS_HOST, "port": HDFS_WEBHDFS_PORT}
            if HDFS_USER:
                kwargs["user"] = HDFS_USER
            _fsspec_fs = fsspec.filesystem("webhdfs", **kwargs)
            _fs = pa_fs.PyFileSystem(pa_fs.FSSpecHandler(_fsspec_fs))
            print(
                f"[storage] WebHDFS filesystem: {HDFS_HOST}:{HDFS_WEBHDFS_PORT}"
                + (f" user={HDFS_USER}" if HDFS_USER else ""),
                flush=True,
            )
        else:
            _fs = pa_fs.LocalFileSystem()
            print("[storage] Local filesystem.", flush=True)
    return _fs
def book_path(library: str, book: str) -> str:
    return posixpath.join(PARQUET_DIR, library, book)
 
 
def library_path(library: str) -> str:
    return posixpath.join(PARQUET_DIR, library)

def isdir(path: str) -> bool:
    #True if path exists and is dir
    try:
        return get_fs().get_file_info(path).type == pa_fs.FileType.Directory
    except Exception:
        return False
 
 
def has_parquet(path: str) -> bool:
    #True if *path* is a dir that has a paraquet file
    try:
        if get_fs().get_file_info(path).type != pa_fs.FileType.Directory:
            return False
        selector = pa_fs.FileSelector(path, recursive=False)
        return any(
            fi.base_name.endswith(".parquet") and fi.type == pa_fs.FileType.File
            for fi in get_fs().get_file_info(selector)
        )
    except Exception:
        return False
 