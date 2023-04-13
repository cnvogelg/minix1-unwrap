#!/usr/bin/env python3
#
# read_minix.py <disk_img>
#
# read good old amiga minix disks
#

import minix.fs
import sys
import os

# --- main ---
if len(sys.argv) != 2:
    print("no diskimage given!")
    sys.exit(1)

img_file_name = sys.argv[1]
out_dir_name = os.path.basename(img_file_name)
out_dir_name = os.path.splitext(out_dir_name)[0]

# read disk image
blk_dev = minix.fs.BlockDev(img_file_name)

# create minix fs
mfs = minix.fs.MinixFS(blk_dev)

# create out dir
if not os.path.isdir(out_dir_name):
    os.mkdir(out_dir_name)
os.chdir(out_dir_name)

for path, name, inode in mfs.walk():
    full = path + name
    print(f"{full:<40s} : {inode}")
    if inode.is_dir():
        # create sub dir if its not existing
        if not os.path.isdir(full):
            os.mkdir(full)
    else:
        # extract file
        data = inode.read_data()
        with open(full, "wb") as fh:
            fh.write(data)
