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

    filesystem = line_cells[0]
    point = line_cells[-1]
    capacity = int(line_cells[-2][:-1])
    size = int(line_cells[-5])

    MOUNT_POINTS[point] = (filesystem, size, capacity)
#print MOUNT_POINTS

def get_filesystem_capacity(filesystem):
    return int(os.popen("df -Plk | grep '%s'" %filesystem).read().split()[-2][:-1])

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
    global MAX_CAPACITY, TARGET_CAPACITY, IGNORE_FILES_COUNT

    parser = argparse.ArgumentParser(description='Disk Space Cleaner')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('FILESYSTEM', type=str, nargs='?', help='the filesystem to clean')
    parser.add_argument('-n', type=int, help='print the largest N files')
    parser.add_argument('--max-capacity', type=int, help='max capacity. default: 90')
    parser.add_argument('--target-capacity', type=int, help='target capacity. default: 50')
    parser.add_argument('--auto', action='store_true', help='auto to clean junks (in whitelist, in greylist and marched hostname)')

    args = parser.parse_args()

    if args.max_capacity: MAX_CAPACITY = args.max_capacity
    if args.target_capacity: TARGET_CAPACITY = args.target_capacity
    TARGET_CAPACITY = min(TARGET_CAPACITY, int(MAX_CAPACITY*0.8))
    #print MAX_CAPACITY, TARGET_CAPACITY

    for Point, (Filesystem, Size, Capacity) in MOUNT_POINTS.items():
        #specify the filesystem to clean
        if args.FILESYSTEM and args.FILESYSTEM != Filesystem and args.FILESYSTEM != Point: continue

        print 'Cleaner: %s (%s) ...' %(Point, Filesystem)

        #default to clean >MAX_CAPACITY% filesystem
        if not args.n and (Capacity < TARGET_CAPACITY or not args.FILESYSTEM and Capacity < MAX_CAPACITY):
            print 'Do not need to clean ...\n\n'
            continue

        group_files = {}
        IGNORE_FILES_COUNT = 0

        for f in walk(Point):
            try:
                stat = f.stat()
            except OSError, e:
                IGNORE_FILES_COUNT += 1

            path = f.path
            size = stat.st_blocks*stat.st_blksize/1024/8
            mtime = int(stat.st_mtime)

            key = tuple(re.findall(r'[^\d]+', path+'$'))
            if not key in group_files:
                group_files[key] = {
                    'total-size': 0,
                    'infos': [],
                }

            group_files[key]['total-size'] += size
            group_files[key]['infos'].append((path, size, mtime))

        if IGNORE_FILES_COUNT: print '\nWarning: Ignore the %d files ...' %IGNORE_FILES_COUNT

        if args.n:
            print '\nThe largest %d files:' %args.n
            for v in heapq.nlargest(args.n, group_files.values(), key=lambda v: v['total-size']):
                print '%s\t%s' %(get_human_size(v['total-size']), get_re_path(zip(*v['infos'])[0]))
            print
            print
        else:
            #default to clean >MAX_CAPACITY% filesystem
            if Capacity < TARGET_CAPACITY or not args.FILESYSTEM and Capacity < MAX_CAPACITY:
                print 'Do not need to clean ...'
                continue

            nlargest_files = heapq.nlargest(20, group_files.values(), key=lambda v: v['total-size'])

            #clean for largest 10
            for i, v in enumerate(nlargest_files[:10]):
                #update capacity
                Capacity = get_filesystem_capacity(Filesystem)
                if Capacity <= TARGET_CAPACITY: break

                #stop ... need clean other files
                if Size*(Capacity-MAX_CAPACITY)/100 > v['total-size']*(10-i): break

                human_size = get_human_size(v['total-size'])
                re_path = get_re_path(zip(*v['infos'])[0])

                #sort infos by mtime
                v['infos'].sort(key=lambda x: x[2])

                if not re.match(JUNK_PATTERN, re_path): continue

                #dangerous
                if JUNK_CENTER.is_dangerous(re_path):continue

                #cancel cleaner flag
                cancel_flag = False
                
                if '*' in re_path:
                    v['infos'].sort(key=lambda x: x[2])
                    mtime_2_3 = v['infos'][len(v['infos'])*2/3][2]
                    now_ts = int(time.time())

                    default_p = min((now_ts - mtime_2_3)/(24*60*60), 3)

                    while True:
                        print
                        print "Junk: (%s) %s" %(human_size, re_path)
                        if args.auto and JUNK_CENTER.is_safe(re_path):
                            print 'Auto Clean %d days ago files (recently safe) ...' %default_p
                            p = 'y'
                        else:
                            p = raw_input('Clean %d days ago files (recently safe)? [y/n/$days/l/d/h]:' %default_p)

                        if p in ['h', 'help', 'H', 'HELP']:
                            print 'Help ... Default: n'
                            print 'y:\tExecute the default action.'
                            print 'n:\tDo nothing.'
                            print '$days:\tClean $days ago files (recently safe).'
                            print 'l:\tLists the files to be cleaned.'
                            print 'd:\tDelete all files (recently safe).'
                            print 'h:\tPrint help message.'
                            continue

                        if p in ['y', 'yes', 'Y', 'YES']: p = default_p

                        if p in ['d', 'delete', 'D', 'DELETE']: p = -1

                        if p in ['l', 'less', 'L', 'LESS']:
                            print 'List ...'

                            temp = tempfile.NamedTemporaryFile() 
                            temp.writelines(['%s\n' %path for path, size, mtime in v['infos']])
                            temp.flush()
                            os.system('less %s' %temp.name)
                            temp.close()
                            continue

                        try:
                            days = int(p)

                            if days == -1:
                                print 'Delete ...'
                            else:
                                print 'Clean %d days ago files ...' %days

                            #clean $days ago files
                            for path, size, mtime in v['infos']:
                                if now_ts - mtime > max(days*24*60*60, 3*60*60):
                                    #print 'rm %s' %path
                                    v['total-size'] -= size
                                    os.remove(path)

                        except ValueError:
                            print 'Cancel ...'
                            cancel_flag = True

                        break
                else:
                    while True:
                        print
                        if args.auto and JUNK_CENTER.is_safe(re_path):
                            print 'Auto Empty the file "(%s) %s ...' %(human_size, re_path)
                            p = 'y'
                        else:
                            p = raw_input('Empty the file "(%s) %s"? [y/n/l/d/h]:' %(human_size, re_path))

                        if p in ['h', 'help', 'H', 'HELP']:
                            print 'Help ... Default: n'
                            print 'y:\tExecute the default action.'
                            print 'n:\tDo nothing.'
                            print 'l:\tLists the file contents to be cleaned.'
                            print 'd:\tDelete the file.'
                            print 'h:\tPrint help message.'
                            continue

                        if p in ['y', 'yes', 'Y', 'YES']:
                            print 'Empty ... '

                            #empty file
                            #print 'empty %s' %re_path
                            v['total-size'] -= v['infos'][0][1]
                            open(re_path, 'w').close()
                        elif p in ['d', 'delete', 'D', 'DELETE']:
                            print 'Delete ... '

                            #print 'delete %s' %re_path
                            v['total-size'] -= v['infos'][0][1]
                            os.remove(re_path)
                        elif p in ['l', 'less', 'L', 'LESS']:
                            print 'List ...'

                            os.system('less %s' %re_path)
                            continue
                        else:
                            print 'Cancel ...'
                            cancel_flag = True

                        break

                #submit junk
                if not cancel_flag: JUNK_CENTER.submit(re_path)

            Capacity = get_filesystem_capacity(Filesystem)
            if Capacity > MAX_CAPACITY:
                print
                print 'Warning: Can not reduce capacity < %d%%. This is the largest 10 files:' %MAX_CAPACITY
                for v in sorted(nlargest_files, key=lambda v: v['total-size'], reverse=True)[:10]:
                    print '%s\t%s' %(get_human_size(v['total-size']), get_re_path(zip(*v['infos'])[0]))


                FILES_TOTAL_SIZE = sum([v['total-size'] for v in group_files.values()])
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
                        print 'Warning: Some files have been deleted, but not free up space. This is the largest 10 files:'
                        print 'SIZE\tPID\tCOMMAND\tFILE'
                        for deleted_file in deleted_files[:10]:
                            print '%s\t%d\t%s\t%s (deleted)' %(get_human_size(deleted_file[1]), deleted_file[2], deleted_file[3], deleted_file[0])
            else:
                print
                print 'Now the %s (%s) capacity is %d%% < %d%%' %(Point, Filesystem, Capacity, MAX_CAPACITY)

            print
            print


def echo_wcleaner_conf():
    from pkg_resources import Requirement, resource_filename

    conf = resource_filename(Requirement.parse('wcleaner'), 'wcleaner/settings.py')

    with open(conf) as conf_f:
        print conf_f.read(),

if __name__ == '__main__':
    wcleaner()
