import sys

library = sys.argv[1] #library  
book    = sys.argv[2] #book
if library == "download_entire_library":
    print(f"Installing entire {library}...")
else:
    print(f"Installing {book} from {library}...")