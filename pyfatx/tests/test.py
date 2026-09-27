#!/usr/bin/env python3
import functools
import os
import tempfile
import unittest
import random
import time

from pyfatx import Fatx
from pyfatx.libfatx import ffi, lib


def with_formatted_disk(func):
	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
			hdd_img_path = tmp_file.name + "-fatx"
		try:
			Fatx.create(hdd_img_path)
			return func(*args, hdd_img_path, **kwargs)
		finally:
			os.remove(hdd_img_path)
			os.remove(tmp_file.name)
	return wrapper


class BasicTest(unittest.TestCase):
	"""
	Run basic tests.
	"""

	@with_formatted_disk
	def test_read_empty_file(self, path):
		fs = Fatx(path)
		empty_file = '/empty'
		fs.mknod(empty_file)

		res = fs.read(empty_file)
		fs.unlink(empty_file)
		assert len(res) == 0

	@with_formatted_disk
	def test_create_file(self, path):
		test_file_path = '/test_file.txt'
		fs = Fatx(path)
		content = b'12345'
		fs.write(test_file_path, content)

		written = fs.read(test_file_path)
		assert written == content

		fs.unlink(test_file_path)
		file_still_available = False
		try:
			fs.get_attr(test_file_path)
			file_still_available = True
		except AssertionError:
			pass
		assert not file_still_available

	@with_formatted_disk
	def test_truncate_file(self, path):
		test_file_path = '/test_file.txt'
		fs = Fatx(path)
		content = b'12345'
		fs.write(test_file_path, content)

		fs.truncate(test_file_path, 3)

		written = fs.read(test_file_path)
		assert written == content[:3]

		fs.unlink(test_file_path)

	@with_formatted_disk
	def test_rename_file(self, path):
		test_file_path = '/test_file.txt'
		fs = Fatx(path)
		content = b'12345'
		fs.write(test_file_path, content)

		new_filename = '/renamed_test_file.txt'
		fs.rename(test_file_path, new_filename)

		original_file_still_available = False
		try:
			fs.get_attr(test_file_path)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		fs.unlink(new_filename)

	@with_formatted_disk
	def test_write_large_file(self, path):
		test_file_path = '/largefile'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)
		b = bytes([rng.getrandbits(8) for _ in range(1024 * 1024)])
		
		fs.write(test_file_path, b)

		d = fs.read(test_file_path)
		fs.unlink(test_file_path)

		assert d == b

	
	@with_formatted_disk
	def test_write_offset(self, path):
		test_file_path = '/offsetfile'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		# Write 1KB of random data
		b = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file_path, b)

		# Delete the data
		d = fs.read(test_file_path)
		fs.unlink(test_file_path)
		assert d == b

		# Write 512KB of random data at offset 128
		b = bytes([rng.getrandbits(8) for _ in range(1024 * 512)])
		fs.write(test_file_path, b, offset=128)

		# Read from offset zero
		d = fs.read(test_file_path)
		fs.unlink(test_file_path)

		assert d == bytes([0] * 128) + b


	@with_formatted_disk
	def test_rename_overwrite(self, path):
		test_file1 = '/test_overwrite1'
		test_file2 = '/test_overwrite2'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		# file1 should be above file2 in the dirent list
		# so this tests that overwriting file1 removes it
		fs.rename(test_file2, test_file1)

		d = fs.read(test_file1)
		fs.unlink(test_file1)

		original_file_still_available = False
		try:
			fs.get_attr(test_file2)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		assert d == b2


	@with_formatted_disk
	def test_rename_exchange(self, path):
		test_file1 = '/test_xchg1'
		test_file2 = '/test_xchg2'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		fs.rename(test_file2, test_file1, exchange=True)

		d1 = fs.read(test_file1)
		d2 = fs.read(test_file2)

		fs.unlink(test_file1)
		fs.unlink(test_file2)

		assert d1 == b2
		assert d2 == b1


	@with_formatted_disk
	def test_rename_exchange_different_dirname_overwrite(self, path):
		test_file1 = '/test_xchg1'
		file2_dir = '/testdir'
		test_file2 = '{}/test_xchg2'.format(file2_dir)
		fs = Fatx(path)

		fs.mkdir(file2_dir)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		fs.rename(test_file2, test_file1, exchange=True)

		d1 = fs.read(test_file1)
		d2 = fs.read(test_file2)

		fs.unlink(test_file1)
		fs.unlink(test_file2)
		
		fs.rmdir(file2_dir)

		assert d1 == b2
		assert d2 == b1


	@with_formatted_disk
	def test_rename_different_dirname_overwrite(self, path):
		test_file1 = '/test_xchg1'
		file2_dir = '/testdir'
		test_file2 = '{}/test_xchg2'.format(file2_dir)
		fs = Fatx(path)

		fs.mkdir(file2_dir)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		fs.rename(test_file2, test_file1)

		d1 = fs.read(test_file1)
		fs.unlink(test_file1)

		fs.rmdir(file2_dir)

		original_file_still_available = False
		try:
			fs.get_attr(test_file2)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		assert d1 == b2


	@with_formatted_disk
	def test_rename_different_dirname_nonexisting(self, path):
		test_file1 = '/test_xchg1'
		file2_dir = '/testdir'
		test_file2 = '{}/test_xchg2'.format(file2_dir)
		fs = Fatx(path)

		fs.mkdir(file2_dir)

		rng = random.Random()
		rng.seed(12345)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		fs.rename(test_file2, test_file1)

		d1 = fs.read(test_file1)
		fs.unlink(test_file1)

		fs.rmdir(file2_dir)

		original_file_still_available = False
		try:
			fs.get_attr(test_file2)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		assert d1 == b2


	@with_formatted_disk
	def test_rename_no_replace_different_dirname_nonexisting(self, path):
		test_file1 = '/test_xchg1'
		file2_dir = '/testdir'
		test_file2 = '{}/test_xchg2'.format(file2_dir)
		fs = Fatx(path)

		fs.mkdir(file2_dir)

		rng = random.Random()
		rng.seed(12345)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		fs.rename(test_file2, test_file1, no_replace=True)

		d1 = fs.read(test_file1)
		fs.unlink(test_file1)

		fs.rmdir(file2_dir)

		original_file_still_available = False
		try:
			fs.get_attr(test_file2)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		assert d1 == b2


	@with_formatted_disk
	def test_rename_no_replace_different_dirname_existing_fails(self, path):
		test_file1 = '/test_xchg1'
		file2_dir = '/testdir'
		test_file2 = '{}/test_xchg2'.format(file2_dir)
		fs = Fatx(path)

		fs.mkdir(file2_dir)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		rename_failed = False
		try:
			fs.rename(test_file2, test_file1, no_replace=True)
			rename_failed = True
		except AssertionError:
			pass

		fs.unlink(test_file1)
		fs.unlink(test_file2)

		fs.rmdir(file2_dir)

		assert not rename_failed


	@with_formatted_disk
	def test_rename_exchange_nonexistent_file_fails(self, path):
		test_file1 = '/test_xchg1'
		test_file2 = '/test_xchg2'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		rename_failed = False
		try:
			fs.rename(test_file1, test_file2, exchange=True)
			rename_failed = True
		except AssertionError:
			pass

		if rename_failed:
			fs.unlink(test_file2)
		else:
			fs.unlink(test_file1)

		assert not rename_failed


	@with_formatted_disk
	def test_rename_no_replace_does_not_replace_file(self, path):
		test_file1 = '/test_xchg1'
		test_file2 = '/test_xchg2'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		b2 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file2, b2)

		rename_failed = False
		try:
			fs.rename(test_file2, test_file1, no_replace=True)
			rename_failed = True
		except AssertionError:
			pass

		fs.unlink(test_file1)
		fs.unlink(test_file2)

		assert not rename_failed


	@with_formatted_disk
	def test_rename_no_replace_with_nonexistent_destination_works(self, path):
		test_file1 = '/test_xchg1'
		test_file2 = '/test_xchg2'
		fs = Fatx(path)

		rng = random.Random()
		rng.seed(12345)

		b1 = bytes([rng.getrandbits(8) for _ in range(1024)])
		fs.write(test_file1, b1)

		fs.rename(test_file1, test_file2, no_replace=True)

		d2 = fs.read(test_file2)

		fs.unlink(test_file2)

		original_file_still_available = False
		try:
			fs.get_attr(test_file1)
			original_file_still_available = True
		except AssertionError:
			pass
		assert not original_file_still_available

		assert d2 == b1


def with_small_partition(size=1024 * 1024, sectors_per_cluster=32):
	"""
	Format a small image as one FATX partition, so that it is easy to fill.
	"""
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
				tmp_file.truncate(size)
				img_path = tmp_file.name
			try:
				fs = lib.pyfatx_open_helper()
				s = lib.fatx_disk_format_partition(fs, img_path.encode(), 0, size, 512, sectors_per_cluster)
				assert s == 0
				return func(*args, img_path, **kwargs)
			finally:
				os.remove(img_path)
		return wrapper
	return decorator


def fill_file(fs_ptr, path, size=2 * 1024 * 1024):
	"""
	Write to a file until a write fails. Return the last status and the number
	of bytes written.
	"""
	data = bytes(size)
	written = 0
	while written < size:
		n = lib.fatx_write(fs_ptr, path, written, size - written, data[written:])
		if n <= 0:
			return n, written
		written += n
	return 0, written


class RegressionTest(unittest.TestCase):
	"""
	Tests for bugs found in the audit of libfatx.
	"""

	@with_formatted_disk
	def test_truncate_grow_reads_zeros(self, path):
		fs = Fatx(path)
		fs.write('/f', b'SECRET')
		fs.truncate('/f', 0)
		fs.truncate('/f', 6)
		assert fs.read('/f') == bytes(6)

	@with_formatted_disk
	def test_truncate_grow_reads_zeros_across_clusters(self, path):
		fs = Fatx(path)
		fs.write('/f', b'\xaa' * 40000)
		fs.truncate('/f', 100)
		fs.truncate('/f', 40000)
		d = fs.read('/f')
		assert d[:100] == b'\xaa' * 100
		assert d[100:] == bytes(39900)

	@with_formatted_disk
	def test_zero_length_write_past_eof(self, path):
		fs = Fatx(path)
		fs.mknod('/z')
		assert lib.fatx_write(fs.fs, b'/z', 100, 0, b'') == 0
		assert fs.get_attr('/z').file_size == 0

	@with_formatted_disk
	def test_write_past_eof_sets_size(self, path):
		fs = Fatx(path)
		fs.mknod('/z')
		assert lib.fatx_write(fs.fs, b'/z', 100, 1, b'x') == 1
		assert fs.get_attr('/z').file_size == 101
		assert fs.read('/z') == bytes(100) + b'x'

	@with_formatted_disk
	def test_negative_offset(self, path):
		fs = Fatx(path)
		fs.write('/f', b'abc')
		assert lib.fatx_write(fs.fs, b'/f', -1, 1, b'x') == lib.FATX_STATUS_INVALID
		assert lib.fatx_truncate(fs.fs, b'/f', -1) == lib.FATX_STATUS_INVALID
		buf = ffi.new('char[4]')
		assert lib.fatx_read(fs.fs, b'/f', -1, 1, buf) == lib.FATX_STATUS_INVALID

	@with_formatted_disk
	def test_file_size_limit(self, path):
		fs = Fatx(path)
		fs.write('/f', b'abc')
		assert lib.fatx_truncate(fs.fs, b'/f', 2**32) == lib.FATX_STATUS_FILE_TOO_LARGE
		assert lib.fatx_write(fs.fs, b'/f', 2**32 - 1, 2, b'xy') == lib.FATX_STATUS_FILE_TOO_LARGE
		assert fs.read('/f') == b'abc'

	@with_formatted_disk
	def test_rename_to_self_keeps_file(self, path):
		fs = Fatx(path)
		fs.write('/f', b'keep me')
		assert lib.fatx_rename(fs.fs, b'/f', b'/f', False, False) == 0
		assert fs.read('/f') == b'keep me'

	@with_formatted_disk
	def test_unlink_directory_fails(self, path):
		fs = Fatx(path)
		fs.mkdir('/d')
		fs.write('/d/x', b'child')
		assert lib.fatx_unlink(fs.fs, b'/d') == lib.FATX_STATUS_IS_DIRECTORY
		assert fs.read('/d/x') == b'child'

	@with_formatted_disk
	def test_rmdir_status(self, path):
		fs = Fatx(path)
		fs.mkdir('/d')
		fs.mknod('/d/x')
		fs.mknod('/f')
		assert lib.fatx_rmdir(fs.fs, b'/d') == lib.FATX_STATUS_NOT_EMPTY
		assert lib.fatx_rmdir(fs.fs, b'/f') == lib.FATX_STATUS_NOT_DIRECTORY
		assert lib.fatx_rmdir(fs.fs, b'/') == lib.FATX_STATUS_INVALID
		fs.unlink('/d/x')
		assert lib.fatx_rmdir(fs.fs, b'/d') == 0

	@with_formatted_disk
	def test_create_existing(self, path):
		fs = Fatx(path)
		fs.mkdir('/d')
		fs.mknod('/f')
		assert lib.fatx_mkdir(fs.fs, b'/d') == lib.FATX_STATUS_EXISTS
		assert lib.fatx_mknod(fs.fs, b'/f') == lib.FATX_STATUS_EXISTS

	@with_formatted_disk
	def test_name_too_long(self, path):
		fs = Fatx(path)
		assert lib.fatx_mknod(fs.fs, b'/' + b'n' * 42) == lib.FATX_STATUS_NAME_TOO_LONG
		assert lib.fatx_mknod(fs.fs, b'/' + b'n' * 41) == 0

	@with_formatted_disk
	def test_rename_dir_into_own_subdir_fails(self, path):
		fs = Fatx(path)
		fs.mkdir('/a')
		fs.mkdir('/a/b')
		assert lib.fatx_rename(fs.fs, b'/a', b'/a/b/c', False, False) == lib.FATX_STATUS_INVALID
		assert fs.get_attr('/a/b').is_directory

	@with_formatted_disk
	def test_rename_over_directory(self, path):
		fs = Fatx(path)
		fs.mkdir('/d')
		fs.write('/d/x', b'child')
		fs.write('/f', b'file')
		fs.mkdir('/e')
		assert lib.fatx_rename(fs.fs, b'/f', b'/d', False, False) == lib.FATX_STATUS_IS_DIRECTORY
		assert lib.fatx_rename(fs.fs, b'/e', b'/d', False, False) == lib.FATX_STATUS_NOT_EMPTY
		assert lib.fatx_rename(fs.fs, b'/d', b'/f', False, False) == lib.FATX_STATUS_NOT_DIRECTORY
		assert fs.read('/d/x') == b'child'
		assert fs.read('/f') == b'file'

	@with_formatted_disk
	def test_rename_dir_over_empty_dir(self, path):
		fs = Fatx(path)
		fs.mkdir('/src')
		fs.write('/src/k', b'k')
		fs.mkdir('/dst')
		assert lib.fatx_rename(fs.fs, b'/src', b'/dst', False, False) == 0
		assert fs.read('/dst/k') == b'k'
		assert lib.fatx_get_attr(fs.fs, b'/src', ffi.new('struct fatx_attr *')) == lib.FATX_STATUS_FILE_NOT_FOUND

		fs.mkdir('/p')
		fs.mkdir('/p/dst')
		assert lib.fatx_rename(fs.fs, b'/dst', b'/p/dst', False, False) == 0
		assert fs.read('/p/dst/k') == b'k'
		assert lib.fatx_get_attr(fs.fs, b'/dst', ffi.new('struct fatx_attr *')) == lib.FATX_STATUS_FILE_NOT_FOUND

	@with_small_partition()
	def test_full_partition_reports_no_space(self, img_path):
		fs = Fatx(img_path, offset=0, size=1024 * 1024)
		fs.mknod('/big')
		status, written = fill_file(fs.fs, b'/big')
		assert status == lib.FATX_STATUS_NO_SPACE
		assert 0 < written < 1024 * 1024
		assert fs.get_attr('/big').file_size == written
		assert lib.fatx_mknod(fs.fs, b'/more') == lib.FATX_STATUS_NO_SPACE

	@with_formatted_disk
	def test_allocation_is_per_filesystem(self, path):
		# Move the allocator of a large filesystem past the end of a small
		# one. Then fill the small one. This hung when the allocator position
		# was shared between filesystems.
		big = Fatx(path)
		big.write('/f', bytes(200 * 16 * 1024))

		@with_small_partition()
		def fill_small(img_path):
			small = Fatx(img_path, offset=0, size=1024 * 1024)
			small.mknod('/big')
			status, _ = fill_file(small.fs, b'/big')
			assert status == lib.FATX_STATUS_NO_SPACE
		fill_small()

	@with_small_partition()
	def test_sync(self, img_path):
		fs = Fatx(img_path, offset=0, size=1024 * 1024)
		fs.write('/f', b'synced')
		assert lib.fatx_sync(fs.fs) == 0
		# Open the image again, without a close of the first handle.
		fs2 = Fatx(img_path, offset=0, size=1024 * 1024)
		assert fs2.read('/f') == b'synced'

	@with_formatted_disk
	def test_dates_out_of_range_are_clamped(self, path):
		fs = Fatx(path)
		fs.mknod('/f')
		ts = ffi.new('struct fatx_ts[2]')
		for t in ts:
			t.year, t.month, t.day, t.hour, t.minute, t.second = 1970, 1, 1, 0, 0, 0
		assert lib.fatx_utime(fs.fs, b'/f', ts) == 0
		attr = ffi.new('struct fatx_attr *')
		assert lib.fatx_get_attr(fs.fs, b'/f', attr) == 0
		assert (attr.modified.year, attr.modified.month, attr.modified.day) == (2000, 1, 1)

		out = ffi.new('struct fatx_ts *')
		lib.fatx_time_t_to_fatx_ts(0, out)
		assert out.year == 2000

	def test_time_round_trip_in_summer(self):
		old_tz = os.environ.get('TZ')
		os.environ['TZ'] = 'America/New_York'
		time.tzset()
		try:
			t = 1720000000  # July 2024, daylight saving time is in effect
			ts = ffi.new('struct fatx_ts *')
			lib.fatx_time_t_to_fatx_ts(t, ts)
			assert lib.fatx_ts_to_time_t(ts) == t
		finally:
			if old_tz is None:
				del os.environ['TZ']
			else:
				os.environ['TZ'] = old_tz
			time.tzset()


if __name__ == '__main__':
	unittest.main()
