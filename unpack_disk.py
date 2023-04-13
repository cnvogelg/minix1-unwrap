#!/usr/bin/env python3
#
# unpack_disk.py <disk1> ...
#
# unpack minix1 disk images

import argparse
import os
import io

import minix.fs
import minix.ar
import unlzw3


HELP = """
This tool allows to unpack Minix V1.x disk images used for litte and
big endian system (e.g. PC, Amiga, Atari ST). The files found in the
images are extracted with sub dirs into a host directory. Additionally,
compressed archives found in the images are automatically extracted
(e.g. SRC.a.Z files).
"""


def parse_args():
    # parse arguments
    parser = argparse.ArgumentParser(description=HELP)
    parser.add_argument("disk_images", nargs="+")
    parser.add_argument(
        "--output-dir", "-o", help="output directory for all files", default="disk"
    )
    parser.add_argument(
        "--keep-archives", "-k", help="keep archives unpacked", action="store_true"
    )
    args = parser.parse_args()
    return args


def unpack_archive(name, data, dest_dir):
    print(f"unpack archive '{name}' to '{dest_dir}'")
    raw_data = unlzw3.unlzw(data)
    fobj = io.BytesIO(raw_data)
    ar = minix.ar.MinixArchive(fobj=fobj)
    for entry in ar.walk():
        dest_file = os.path.join(dest_dir, entry.name)
        print(f"extract file '{dest_file}'")
        file_data = ar.read(entry)
        with open(dest_file, "wb") as fh:
            fh.write(file_data)


def unpack_disk(disk_name, output_dir, keep_archives=False):
    print(f"unpacking disk '{disk_name}'' to '{output_dir}'")
    # setup block dev for disk image
    blk_dev = minix.fs.BlockDev(disk_name)
    # create minix fs
    mfs = minix.fs.MinixFS(blk_dev)
    # walk through minix fs
    for path, inode in mfs.walk():
        dest_path = os.path.join(output_dir, *path)
        # make dir
        if inode.is_dir():
            if not os.path.exists(dest_path):
                print(f"creating dir '{dest_path}'")
                os.mkdir(dest_path)
        elif inode.is_file():
            # is archive?
            name = path[-1]
            if name.endswith(".a.Z") and not keep_archives:
                data = inode.read_data()
                base_dir = os.path.join(output_dir, *path[:-1])
                unpack_archive(name, data, base_dir)
            else:
                print(f"extract file '{dest_path}'")
                data = inode.read_data()
                with open(dest_path, "wb") as fh:
                    if data:
                        fh.write(data)


def unpack_disks(disk_names, output_dir, keep_archives=False):
    # make sure output path exists
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    # run through images
    for disk_name in disk_names:
        unpack_disk(disk_name, output_dir, keep_archives)


if __name__ == "__main__":
    args = parse_args()
    unpack_disks(args.disk_images, args.output_dir, args.keep_archives)
