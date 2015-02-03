#!/usr/bin/env python

from wcleaner import __version__

import os
import time
import argparse
import scandir
import heapq
import re
import tempfile

MAX_CAPACITY = 80
IGNORE_FILES_COUNT = 0

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
    global IGNORE_FILES_COUNT

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
        IGNORE_FILES_COUNT += 1

def get_re_path(paths):
    strings = re.findall(r'[^\d]+', paths[0]+'$')
    numbers_l = map(lambda path: re.findall(r'[\d]+', path), paths)

    for i, z_numbers in enumerate(zip(*numbers_l)):
        #print i, z_numbers[0], all([number == z_numbers[0] for number in z_numbers])
        if all([number == z_numbers[0] for number in z_numbers]):
            strings[i] += z_numbers[0] + '*'

    #print strings
    return '*'.join(strings).replace('**', '')[:-1]

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
    global MAX_CAPACITY, IGNORE_FILES_COUNT

    parser = argparse.ArgumentParser(description='Wandoujia Cleaner')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('FILESYSTEM', type=str, nargs='?', help='the filesystem to clean')
    parser.add_argument('-n', type=int, help='print the top number largest files')
    parser.add_argument('--max-capacity', type=int, help='max capacity')

    args = parser.parse_args()

    if args.max_capacity: MAX_CAPACITY = args.max_capacity

    for Point, (Filesystem, Size, Capacity) in MOUNT_POINTS.items():
        #specify the filesystem to clean
        if args.FILESYSTEM and args.FILESYSTEM != Filesystem and args.FILESYSTEM != Point: continue

        #default to clean >MOUNT_POINTS% filesystem
        if not args.FILESYSTEM and Capacity < MAX_CAPACITY: continue

        print 'Cleaner: %s (%s) ...' %(Point, Filesystem)

        group_files = {}
        IGNORE_FILES_COUNT = 0

        for f in walk(Point):
            try:
                stat = f.stat()
            except OSError, e:
                IGNORE_FILES_COUNT += 1

            path = f.path
            size = stat.st_blocks*stat.st_blksize/1024/8

            key = tuple(re.findall(r'[^\d]+', path+'$'))
            if not key in group_files:
                group_files[key] = {
                    'size': 0,
                    'paths': [],
                }

            group_files[key]['size'] += size
            group_files[key]['paths'].append(path)

        if IGNORE_FILES_COUNT: print 'Warning: Ignore the %d files ...' %IGNORE_FILES_COUNT

        if args.n:
            print 'The top %d largest files:' %args.n
            for v in heapq.nlargest(args.n, group_files.values(), key=lambda v: v['size']):
                print '%s\t%s' %(get_human_size(v['size']), get_re_path(v['paths']))
            print
            print
        else:
            for v in heapq.nlargest(30, group_files.values(), key=lambda v: v['size']):
                re_path = get_re_path(v['paths'])

                if re.match(r'.*\blog\b.*', re_path):
                    if '*' in re_path:
                        while True:
                            print
                            p = raw_input('Clean three days ago files "(%s) %s" [y/n/$days/l]:' %(get_human_size(v['size']), get_re_path(v['paths'])))

                            if p in ['y', 'yes', 'Y', 'YES']: p = '3'

                            if p in ['l', 'less', 'L', 'LESS']:
                                print 'List ...'

                                temp = tempfile.NamedTemporaryFile() 
                                temp.writelines(['%s\n' %path for path in sorted(v['paths'])])
                                temp.flush()
                                os.system('less %s' %temp.name)
                                temp.close()
                                continue

                            try:
                                days = int(p)

                                print 'Clean %d days ago files ...' %days

                                #clean $days ago files
                                now_ts = time.time()
                                for path in v['paths']:
                                    if now_ts - os.stat(path).st_mtime > days * 24 * 60 * 60:
                                        print 'rm %s' %path
                                        #os.remove(path)

                            except ValueError:
                                print 'Cancel ...'

                            break
                    else:
                        while True:
                            print
                            p = raw_input('Empty the file "(%s) %s" [y/n/l]:' %(get_human_size(v['size']), get_re_path(v['paths'])))

                            if p in ['y', 'yes', 'Y', 'YES']:
                                print 'Empty ... '

                                #empty file
                                print 'empty %s' %re_path
                                #open(re_path, 'w').close()
                            elif p in ['l', 'less', 'L', 'LESS']:
                                print 'List ...'

                                os.system('less %s' %re_path)
                                continue
                            else:
                                print 'Cancel ...'

                            break
            print
            print

if __name__ == '__main__':
    wcleaner()
