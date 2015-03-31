#!/usr/bin/env python

#filesystem capacity > max capacity is bad
MAX_CAPACITY = 90

#filesystem capacity < target capacity is good
TARGET_CAPACITY = 50

#pattern marching files is junk
JUNK_PATTERN = r'.*\blogs?\b.*'

#junk center redis
JUNK_CENTER_HOST = 'your redis host'
JUNK_CENTER_PORT = 6379
JUNK_CENTER_DBS = [0, 1, 2, 3] #grey/white/black/red dbs
