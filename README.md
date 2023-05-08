# minix1-unwrap

This tool allows to unpack Minix V1.x disk images used for big endian system
(e.g. Amiga, Atari ST, Mac). The files found in the images are extracted with
sub dirs into a host directory. Additionally, compressed archives found in the
images are automatically extracted (e.g. `SRC.a.Z` files).

## Installation

* You need a Python >=3.6 setup
* Install `unlzw3` package

		pip3 install unlzw3

* Clone this repo

## Run

Download some Minix V1.x disk images for Amiga, Atari ST, or Mac from
[Minix 1.x Versions](https://wiki.minix3.org/doku.php?id=www:download:previousversions)

Unpack the contents of the disk images by giving the disk name of one or
multiple images to `unpack_disk.py`:

		$ ./unpack_disk.py disk03 disk04

A new folder called `disk` will be created in the current directory and the
extracted files are placed there. Use option `-o <output_dir>` to set an
alternative output directory.

If source archives are found (i.e. `*.a.Z` files for the kernel sources) then
the archives are unpacked automatically. Use option `-k` to keep archives.

Note: the tool is only able to unpack disk images in Minix file format.
Typically, the first disks of an install set are in the native disk format
of the target system and cannot be unpacked with this tool.
