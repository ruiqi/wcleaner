#!/usr/bin/env python

from wcleaner import __version__

import os
import argparse
import scandir
import heapq
import re

MAX_CAPACITY = 80

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
        print 'Warning: %s' %e

def get_re_path(paths):
    strings = re.findall(r'[^\d]+', paths[0])
    numbers_l = map(lambda path: re.findall(r'[\d]+', path), paths)

    for i, z_numbers in enumerate(zip(*numbers_l)):
        #print i, z_numbers[0], all([number == z_numbers[0] for number in z_numbers])
        if all([number == z_numbers[0] for number in z_numbers]):
            strings[i] += z_numbers[0] + '*'

    #print strings
    return '*'.join(strings).replace('**', '')

def get_human_size(size):
    size = float(size)
    if size < 1024:
        return '%.1fK' %size
    elif size < 1024*1024:
        return '%.1fM' %(size/1024)
    elif size < 1024*1024*1024:
        return '%.1fG' %(size/1024/1024)
    else:
        return '%.1fT' %(size/1024/1024/1024)

def wcleaner():
    parser = argparse.ArgumentParser(description='Wandoujia Cleaner')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('FILESYSTEM', type=str, nargs='?', help='the filesystem to clean')

    args = parser.parse_args()


    for Point, (Filesystem, Size, Capacity) in MOUNT_POINTS.items():
        #specify the filesystem to clean
        if args.FILESYSTEM and args.FILESYSTEM != Filesystem and args.FILESYSTEM != Point: continue

        #default to clean >MOUNT_POINTS% filesystem
        if not args.FILESYSTEM and Capacity < MAX_CAPACITY: continue

        print 'Cleaner: %s (%s) ...' %(Point, Filesystem)

        group_files = {}

        for f in walk(Point):
            stat = f.stat()
            path = f.path
            size = stat.st_blocks*stat.st_blksize/1024/8

            key = tuple(re.findall(r'[^\d]+', path))
            if not key in group_files:
                group_files[key] = {
                    'size': 0,
                    'paths': [],
                }

            group_files[key]['size'] += size
            group_files[key]['paths'].append(path)

        for v in heapq.nlargest(10, group_files.values(), key=lambda v: v['size']):
            print '%s\t%s' %(get_human_size(v['size']), get_re_path(v['paths']))
        print
        print

if __name__ == '__main__':
    wcleaner()
