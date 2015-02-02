#!/usr/bin/env python

from wcleaner import __version__

import os
import argparse
import scandir
import heapq

MAX_CAPACITY = 20

MOUNT_POINTS = {}
for line in os.popen('df -Plk').readlines()[1:]:
    line_cells = line.split()

    filesystem = line_cells[0]
    point = line_cells[-1]
    capacity = int(line_cells[-2][:-1])
    size = int(line_cells[-5])

    MOUNT_POINTS[point] = (filesystem, size, capacity)
#print MOUNT_POINTS

def walk(path):
    try:
        for f in scandir.scandir(path):
            #print f.path, f.is_dir(), f.is_symlink(), f.is_file()
            if f.is_symlink(): continue

            if f.is_dir() and not f.path in MOUNT_POINTS:
                #print f.path, f.is_dir()
                #yield from walk(f)
                for sub_f in walk(f.path):
                    yield sub_f
            else:
                yield f
    except OSError, e:
        print e

def wcleaner():
    parser = argparse.ArgumentParser(description='Wandoujia Cleaner')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('FILESYSTEM', type=str, nargs='?', help='the filesystem to clean')
    parser.add_argument('--max-capacity', type=str, nargs='?', help='the filesystem to clean')

    args = parser.parse_args()

    files_info = []

    for Point, (Filesystem, Size, Capacity) in MOUNT_POINTS.items():
        #specify the filesystem to clean
        if args.FILESYSTEM and args.FILESYSTEM != Filesystem and args.FILESYSTEM != Point: continue

        #default to clean >MOUNT_POINTS% filesystem
        if not args.FILESYSTEM and Capacity < MAX_CAPACITY: continue

        print 'Point: ', Point

        for i, f in enumerate(walk(Point)):
            stat = f.stat()
            f_size = stat.st_blocks*stat.st_blksize/1024/8

            files_info.append((f.path, f_size))

    for path, size in heapq.nlargest(10, files_info, key=lambda x: x[1]):
        print path, size
    print

if __name__ == '__main__':
    wcleaner()
