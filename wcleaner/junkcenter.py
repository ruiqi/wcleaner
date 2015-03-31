#!/usr/bin/env python

'''
>>> JUNK_CENTER = JunkCenter('rd1.hy01', 6373, *[12, 13, 14, 15])
>>> for rd in [JUNK_CENTER.grey_rd, JUNK_CENTER.white_rd, JUNK_CENTER.black_rd, JUNK_CENTER.red_rd]: rd.flushdb()
True
True
True
True
>>> JUNK_CENTER.submit('/tmp/test.log.2015-03-*')
>>> for key in sorted(JUNK_CENTER.grey_rd.keys('*')): print key
/tmp/test.log.2015-03-*
>>> JUNK_CENTER.submit('/tmp/test.log.2015-*-*')
>>> for key in sorted(JUNK_CENTER.grey_rd.keys('*')): print key
/tmp/test.log.2015-*-*
>>> JUNK_CENTER.is_safe('/tmp/test.log.2015-03-05')
True
>>> for key in sorted(JUNK_CENTER.grey_rd.keys('*')): print key
/tmp/test.log.2015-*-*
>>> JUNK_CENTER.is_safe('/tmp/test.log.*-*-*')
False
>>> JUNK_CENTER.submit('/tmp/test.log.*-*-*')
>>> for key in sorted(JUNK_CENTER.grey_rd.keys('*')): print key
/tmp/test.log.*-*-*
>>> JUNK_CENTER.is_safe('/tmp/test.log.2015-*-05')
True
>>> for key in sorted(JUNK_CENTER.grey_rd.keys('*')): print key
/tmp/test.log.*-*-*
>>> JUNK_CENTER.grey_rd.move('/tmp/test.log.*-*-*', 14)
True
>>> for key in sorted(JUNK_CENTER.grey_rd.keys('*')): print key
>>> JUNK_CENTER.is_safe('/tmp/test.log.2015-*-05')
False
>>> JUNK_CENTER = JunkCenter('your redis host', 6379, *[12, 13, 14, 15])
>>> JUNK_CENTER.is_safe('/tmp/test.log.2015-*-05')
False
>>> JUNK_CENTER.is_dangerous('/tmp/test.log.2015-*-05')
False
>>> JUNK_CENTER.submit('/tmp/test.log.*-*-*')
'''

import re
import socket
import redis

class JunkCenter(object):
    '''
    ===Junk Center===

    grey/white/black/red list

    list: [
        junk1: set([
            hostname1,
            hostname2,
        ]),
        junk2: set([
            hostname1,
            hostname2,
        ]),
    ]

    greylist:  '--auto' will clean junks in greylist and hostname marched. All junks cleaned up by wcleaner will submit to here. #safe or normal
    whitelist: '--auto' will clean junks in whitelist. #safe
    blacklist: All junks in blacklist can not be auto cleaned up. #normal
    readlist:  All junks in redlist can not be cleaned up. #dangerous
    '''

    def __init__(self, host, port, grey_db, white_db, black_db, red_db):
        self.grey_rd = redis.StrictRedis(host=host, port=port, db=grey_db)
        self.white_rd = redis.StrictRedis(host=host, port=port, db=white_db)
        self.black_rd = redis.StrictRedis(host=host, port=port, db=black_db)
        self.red_rd = redis.StrictRedis(host=host, port=port, db=red_db)

        self.hostname = socket.gethostname()

    def get_similar_junk(self, rd, junk):
        pattern = re.sub('\d+', '*', junk)
        similar_junks = [key for key in rd.keys(pattern) if re.sub('\d+', '*', key) == pattern]

        if similar_junks:
            similar_junks.sort(key=lambda similar_junk: similar_junk.count('*'))

            #only keep the max one
            rd.sunionstore(similar_junks[-1], *similar_junks)
            for similar_junk in similar_junks[:-1]: rd.delete(similar_junk)

            return similar_junks[-1]
        else:
            return None

    def contain(self, rd, junk):
        similar_junk = self.get_similar_junk(rd, junk)
        if not similar_junk: return False

        if similar_junk.count('*') >= junk.count('*'):
            if rd != self.grey_rd: return True

            if self.hostname in rd.smembers(similar_junk): return True

        return False

    def submit(self, junk):
        try:
            for rd in [self.black_rd, self.white_rd, self.grey_rd]:
                if self.contain(rd, junk): return

            similar_junk = self.get_similar_junk(self.grey_rd, junk)
            if similar_junk is None: similar_junk = junk

            if similar_junk.count('*') >= junk.count('*'):
                self.grey_rd.sadd(similar_junk, self.hostname)
            else:
                self.grey_rd.sadd(junk, self.hostname)
                self.grey_rd.sunionstore(junk, similar_junk)
                self.grey_rd.delete(similar_junk)
        except redis.ConnectionError:
            pass

    def is_dangerous(self, junk):
        '''in redlist'''
        try:
            if self.contain(self.red_rd, junk): return True
        except redis.ConnectionError:
            pass

        return False

    def is_safe(self, junk):
        '''
        not in redlist and not in blacklist
        in whitelist or in greylist and hostname marched
        '''

        try:
            if self.contain(self.red_rd, junk) or self.contain(self.black_rd, junk): return False

            if self.contain(self.white_rd, junk): return True

            if self.contain(self.grey_rd, junk):
                similar_junk = self.get_similar_junk(self.grey_rd, junk)
                if self.hostname in self.grey_rd.smembers(similar_junk): return True
        except redis.ConnectionError:
            pass

        return False

if __name__ == '__main__':
    import doctest
    doctest.testmod()
