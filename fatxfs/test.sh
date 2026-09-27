#!/bin/bash
set -ex

function checksum {
	sha256sum $1 | cut -f1 -d' '
}

mkdir -p c

# Format the disk
if [[ "$(uname)" == "Darwin" ]]; then
	truncate -s 8g xbox_hdd.img
else
	fallocate -l 8G xbox_hdd.img
fi
fatxfs --format=retail --destroy-all-existing-data xbox_hdd.img c
sleep 1

# Copy a file in
fatxfs --log=log.txt --loglevel=100 xbox_hdd.img c
SRC_PATH=$(which fatxfs)
DST_PATH="c/a/b/c/d/randfile.bin"
mkdir -p $(dirname $DST_PATH)
cp $SRC_PATH $DST_PATH
sleep 1
fusermount -u c

# Mount and verify contents
fatxfs xbox_hdd.img c
[[ $(checksum $DST_PATH) = $(checksum $SRC_PATH) ]]
sleep 1
fusermount -u c

# A file must survive when fatxfs stops without an unmount. The FAT stayed in
# the cache until unmount, so the file was lost.
fatxfs xbox_hdd.img c -f &
FATXFS_PID=$!
sleep 1
DST_PATH="c/killed.bin"
cp $SRC_PATH $DST_PATH
kill -9 $FATXFS_PID
wait $FATXFS_PID || true
fusermount -u c
fatxfs xbox_hdd.img c
[[ $(checksum $DST_PATH) = $(checksum $SRC_PATH) ]]
sleep 1
fusermount -u c
