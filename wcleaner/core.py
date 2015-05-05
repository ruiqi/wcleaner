#!/usr/bin/env python

from wcleaner import __version__

import os
import time
import argparse
import scandir
import heapq
import re
import tempfile
import redis
from settings import *
from junkcenter import JunkCenter

conf_paths = [
    os.path.join(os.path.expanduser('~'), '.wcleaner.conf'),
    '/etc/wcleaner.conf',
]

for conf_path in conf_paths:
    try:
        with open(conf_path) as conf_f:
            exec conf_f.read()
        break
    except IOError:
        pass

JUNK_CENTER = JunkCenter(JUNK_CENTER_HOST, JUNK_CENTER_PORT, *JUNK_CENTER_DBS)

MOUNT_POINTS = {}
for line in os.popen('df -Plk').readlines()[1:]:
    if line[0] != '/': continue

    line_cells = line.split()
    #print line_cells

    filesystem = line_cells[0]
    point = line_cells[5]
    capacity = int(line_cells[4][:-1])
    size = int(line_cells[1])

    MOUNT_POINTS[point] = (filesystem, size, capacity)
#print MOUNT_POINTS

def get_filesystem_capacity(filesystem):
    return int(os.popen("df -Plk | grep '%s'" %filesystem).read().split()[-2][:-1])

def is_opened(path):
    return not bool(os.system("fuser '%s' 2>&1 | grep '%s' >/dev/null" %(path, path)))

def walk(path, pattern=None):
    try:
        for f in scandir.scandir(path):
            #print f.path, f.is_dir(), f.is_symlink(), f.is_file()
            if f.is_symlink(): continue

            if f.is_dir() and not f.path in MOUNT_POINTS:
                #print f.path, f.is_dir()
                #yield from walk(f.path) #yield bug
                for path, size, mtime in walk(f.path, pattern):
                    yield (path, size, mtime)
            else:
                if pattern is None or re.match(pattern, f.path): 
                    #get file info
                    path = f.path
                    stat = f.stat()
                    size = stat.st_blocks*stat.st_blksize/1024/8
                    mtime = int(stat.st_mtime)

                    yield (path, size, mtime)
    except OSError, e:
        yield (path, None, None)

def get_junk(fileinfos):
    paths = zip(*fileinfos)[0]
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

def clean_files(groupinfos):
    fileinfos = sorted(groupinfos['fileinfos'], key=lambda (path, size, mtime): mtime)
    clean_before_mtime = fileinfos[int(len(fileinfos)*0.6)][2]/86400*86400 + 86400

    for path, size, mtime in fileinfos:
        if mtime >= clean_before_mtime: break

        groupinfos['total-size'] -= size

        if not is_opened(path):
            os.remove(path)
        else:
            open(path, 'w').close()

def get_group_fileinfos(Point):
    fileinfos = list(walk(Point))

    #Warning ignore files
    ignore_count = len(filter(lambda (path, size, mtime): size is None, fileinfos))
    if ignore_count: print '\nWarning: Ignore %d file(s) ...' %ignore_count

    fileinfos = filter(lambda (path, size, mtime): not size is None, fileinfos)

    group_fileinfos = {}
    for path, size, mtime in fileinfos:
        key = tuple(re.findall(r'[^\d]+', path+'$'))
        if not key in group_fileinfos:
            group_fileinfos[key] = {
                'total-size': 0,
                'fileinfos': [],
            }

        group_fileinfos[key]['total-size'] += size
        group_fileinfos[key]['fileinfos'].append((path, size, mtime))

    return group_fileinfos

def can_not_reduce_capacity(Point, Filesystem, Size, Capacity, group_fileinfos, nlargest_groupinfos):
    print
    print 'Warning: Can not reduce capacity < %d%%. These are the largest 10 files:' %MAX_CAPACITY
    for groupinfos in sorted(nlargest_groupinfos, key=lambda groupinfos: groupinfos['total-size'], reverse=True)[:10]:
        print '%s\t%s' %(get_human_size(groupinfos['total-size']), get_junk(groupinfos['fileinfos']))

    FILES_TOTAL_SIZE = sum([groupinfos['total-size'] for groupinfos in group_fileinfos.values()])
    #print 'miss capa:', Capacity-FILES_TOTAL_SIZE*100/Size

    #when miss capacity > 20%
    if Capacity-FILES_TOTAL_SIZE*100/Size >= 20:
        #lsof | grep deleted files
        deleted_files = []
        current_pid = os.getpid()
        current_tmp_file = None
        for line in os.popen("lsof %s | grep -E '\(deleted\)$'" %Point).readlines():
            try:
                cells = line.split()
                command = cells[0]
                pid = int(cells[1])
                fd = int(cells[3][:-1])
                proc_fd = '/proc/%d/fd/%d' %(pid, fd)
            except ValueError:
                continue

            try:
                stat = os.stat(proc_fd)
                size = stat.st_blocks*stat.st_blksize/1024/8
            except OSError:
                continue

            if pid == current_pid: current_tmp_file = cells[-2]

            deleted_files.append((cells[-2], size, pid, command))

        deleted_files = [deleted_file for deleted_file in deleted_files if deleted_file[0] != current_tmp_file]
        deleted_files.sort(key=lambda deleted_file: deleted_file[1], reverse=True)
        if deleted_files:
            print
            print 'Warning: Some files have been deleted, but allocated space has not been freed. These are the largest 10 files:'
            print 'SIZE\tPID\tCOMMAND\tFILE'
            for deleted_file in deleted_files[:10]:
                print '%s\t%d\t%s\t%s (deleted)' %(get_human_size(deleted_file[1]), deleted_file[2], deleted_file[3], deleted_file[0])


def print_nlargest(Point, Filesystem, N=10):
        group_fileinfos = get_group_fileinfos(Point)
        nlargest_groupinfos = heapq.nlargest(N, group_fileinfos.values(), key=lambda groupinfos: groupinfos['total-size'])

        print '\nLargest %d file(s) are:' %N
        for i, groupinfos in enumerate(nlargest_groupinfos):
            print '%s\t%s' %(get_human_size(groupinfos['total-size']), get_junk(groupinfos['fileinfos']))
        print
        print

def clean_filesystem(Point, Filesystem, Size, Capacity, Auto=False, No_Interface=False):
    #default to clean >MAX_CAPACITY% filesystem
    if Capacity < MAX_CAPACITY:
        print 'No need to clean ...\n\n'
        return

    group_fileinfos = get_group_fileinfos(Point)
    nlargest_groupinfos = heapq.nlargest(20, group_fileinfos.values(), key=lambda groupinfos: groupinfos['total-size'])

    #clean for largest 10
    for i, groupinfos in enumerate(nlargest_groupinfos[:10]):
        #stop when capacity < target capacity
        Capacity = get_filesystem_capacity(Filesystem)
        if Capacity <= TARGET_CAPACITY: break

        #stop ... need clean other files
        if Size*(Capacity-MAX_CAPACITY)/100 > groupinfos['total-size']*(10-i): break

        human_total_size = get_human_size(groupinfos['total-size'])
        junk = get_junk(groupinfos['fileinfos'])

        if not re.match(JUNK_PATTERN, junk): continue

        #dangerous
        if JUNK_CENTER.is_dangerous(junk): continue

        if Auto and JUNK_CENTER.is_safe(junk):
            print
            print "Junk file(s): (%s) %s" %(human_total_size, junk)
            print 'Automatically Clean ... '
            clean_files(groupinfos)

            continue

        if No_Interface: continue

        while True:
            print
            print "Junk file(s): (%s) %s" %(human_total_size, junk)
            p = raw_input('Clean old junk files (opened or recent ones are safe)? [y/n/l/h]:')

            if p in ['y', 'yes', 'Y', 'YES']:
                print 'Clean ...'

                clean_files(groupinfos)

                #submit junk
                JUNK_CENTER.submit(junk)

                break

            elif p in ['l', 'list', 'L', 'LIST']:
                print 'Listing ...'

                temp = tempfile.NamedTemporaryFile() 
                temp.writelines(['%s\n' %path for path, size, mtime in groupinfos['fileinfos']])
                temp.flush()
                os.system('less %s' %temp.name)
                temp.close()

            elif p in ['h', 'help', 'H', 'HELP']:
                print 'Help ... Default: n'
                print 'y:\tExecute the default action.'
                print 'n:\tDo nothing.'
                print 'l:\tList junk files to be cleaned.'
                print 'h:\tPrint help message.'

            else:
                print 'Cancelling ...'

                break

    time.sleep(1)
    Capacity = get_filesystem_capacity(Filesystem)
    if Capacity < MAX_CAPACITY:
        print
        print 'Now the %s (%s) capacity is %d%% < %d%%' %(Point, Filesystem, Capacity, MAX_CAPACITY)
    else:
        can_not_reduce_capacity(Point, Filesystem, Size, Capacity, group_fileinfos, nlargest_groupinfos)

    print
    print
    print

def wcleaner():
    global MAX_CAPACITY, TARGET_CAPACITY

    parser = argparse.ArgumentParser(description='Disk Space Cleaner')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('FILESYSTEM', type=str, nargs='?', help='filesystem to clean')
    parser.add_argument('-n', type=int, help='print the largest N files')
    parser.add_argument('--max-capacity', type=int, help='max capacity. default: 90')
    parser.add_argument('--target-capacity', type=int, help='target capacity. default: 50')
    parser.add_argument('--auto', action='store_true', help='automatically clean junk files in whitelist, greylist and on matched hostname')
    parser.add_argument('--no-interface', action='store_true', help='none-interactive mode')

    args = parser.parse_args()

    if args.max_capacity: MAX_CAPACITY = args.max_capacity
    if args.target_capacity: TARGET_CAPACITY = args.target_capacity
    TARGET_CAPACITY = min(TARGET_CAPACITY, int(MAX_CAPACITY*0.8))
    #print MAX_CAPACITY, TARGET_CAPACITY

    for Point, (Filesystem, Size, Capacity) in MOUNT_POINTS.items():
        #specify the filesystem to clean
        if args.FILESYSTEM and not args.FILESYSTEM in [Filesystem, Point]: continue

        print '#'*70
        print '#' + ' '*68 + '#'
        print '#%s#' %'{0: ^68}'.format('WCleaner: %s (%s) ...' %(Point, Filesystem))
        print '#' + ' '*68 + '#'
        print '#'*70

        if args.n:
            print_nlargest(Point, Filesystem, args.n)
        else:
            clean_filesystem(Point, Filesystem, Size, Capacity, Auto=args.auto, No_Interface=args.no_interface)

def echo_wcleaner_conf():
    from pkg_resources import Requirement, resource_filename

    conf = resource_filename(Requirement.parse('wcleaner'), 'wcleaner/settings.py')

    with open(conf) as conf_f:
        print conf_f.read(),
