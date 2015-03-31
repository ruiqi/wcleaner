# Wcleaner - Disk Space Cleaner

## Features
* Automatic identification log files.
* Automatic aggregation similar files.
* Automatic find deleted files which is not free up space.
* Auto delete log files when enable junk center.
* Junk center support greylist, whitelist, blacklist, redlist.

## Install
````bash
pip install wcleaner
````

## Usage
````
usage: wcleaner [-h] [-v] [-n N] [--max-capacity MAX_CAPACITY]
                [--target-capacity TARGET_CAPACITY] [--auto]
                [FILESYSTEM]

Disk Space Cleaner

positional arguments:
  FILESYSTEM            the filesystem to clean

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -n N                  print the largest N files
  --max-capacity MAX_CAPACITY
                        max capacity. default: 90
  --target-capacity TARGET_CAPACITY
                        target capacity. default: 50
  --auto                auto to clean junks (in whitelist, in greylist and
                        marched hostname)
````

## Enable Junk Center
````bash
echo_wcleaner_conf > /etc/wcleaner.conf
sed -i 's/your redis host/$host/g' /etc/wcleaner.conf
sed -i 's/6379/$port/g' /etc/wcleaner.conf
````

## Junk Center
Suport grey/white/black/red list

```python
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
```

* greylist:  '--auto' will clean junks in greylist and hostname marched. All junks cleaned up by wcleaner will submit to here. #safe or normal
* whitelist: '--auto' will clean junks in whitelist. #safe
* blacklist: All junks in blacklist can not be auto cleaned up. #normal
* readlist:  All junks in redlist can not be cleaned up. #dangerous
