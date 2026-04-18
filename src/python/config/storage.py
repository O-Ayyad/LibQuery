from __future__ import annotations
 
import posixpath
 
import pyarrow.fs as pa_fs
 
from config.settings import (
    USE_HDFS,
    HDFS_HOST,
    HDFS_PORT,
    HDFS_USER,
    PARQUET_DIR,
)
 
# All code that needs to read or write Parquet data goes through here
_fs: pa_fs.FileSystem | None = None #singleton
 
 
def get_fs() -> pa_fs.FileSystem:
    #Returns in use file system
    global _fs
    if _fs is None:
        if USE_HDFS:
            kwargs: dict = {"host": HDFS_HOST, "port": HDFS_PORT}
            if HDFS_USER:
                kwargs["user"] = HDFS_USER
            _fs = pa_fs.HadoopFileSystem(**kwargs)
            print(
                f"[storage] HDFS filesystem: {HDFS_HOST}:{HDFS_PORT}"
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
 
 
def rmdir(path: str) -> None:
    try:
        fs = get_fs()
        if fs.get_file_info(path).type != pa_fs.FileType.NotFound:
            fs.delete_dir(path)
    except Exception:
        pass
 
 
def mkdirs(path: str) -> None:
    get_fs().create_dir(path, recursive=True)