"""Numeric SquashFS metadata contracts;not image or hardware acceptance."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
import verify_merged_image as image


def listing():
    return '\n'.join(mode + ' 0/0 123 2026-09-23 11:51 squashfs-root' + ('/' + name if name else '')
        for name,mode in image.ROOTFS_BOOT_MODES.items()) + '\n'


class NumericRootfsOwnersTests(unittest.TestCase):
    def test_exact_numeric_root_ownership_and_permissions(self):
        result = image.rootfs_owner_table(listing())
        self.assertEqual(set(result),set(image.ROOTFS_BOOT_MODES))
        self.assertEqual(result['etc/shadow'],dict(mode='-rw-------',uid=0,gid=0))

    def test_nonroot_uid_or_gid_rejected(self):
        for owner in ('1000/0','0/1000','1/1'):
            with self.subTest(owner=owner),self.assertRaises(AssertionError):
                image.rootfs_owner_table(listing().replace('0/0',owner,1))

    def test_names_instead_of_numeric_ids_rejected(self):
        with self.assertRaises(AssertionError): image.rootfs_owner_table(listing().replace('0/0','root/root'))

    def test_missing_or_empty_metadata_rejected(self):
        for text in ('','\n'.join(listing().splitlines()[:-1])):
            with self.subTest(text=text),self.assertRaises(AssertionError): image.rootfs_owner_table(text)

    def test_duplicate_extra_and_escaping_paths_rejected(self):
        for extra in (listing().splitlines()[0],'-rw------- 0/0 1 2026-09-23 11:51 squashfs-root/extra',
                '-rw------- 0/0 1 2026-09-23 11:51 squashfs-root/../etc/shadow'):
            with self.subTest(extra=extra),self.assertRaises(AssertionError): image.rootfs_owner_table(listing() + extra)

    def test_shadow_must_not_be_a_link_or_world_readable(self):
        for mode in ('lrwxrwxrwx','-rw-r--r--','-rw-r-----'):
            with self.subTest(mode=mode),self.assertRaises(AssertionError):
                image.rootfs_owner_table(listing().replace('-rw-------',mode))

    def test_parent_directories_and_executables_keep_strict_modes(self):
        for before,after in (('drwxr-xr-x','drwxrwxrwx'),('-rwxr-xr-x','-rwsr-xr-x'),('-rwxr-xr-x','-rw-r--r--')):
            with self.subTest(after=after),self.assertRaises(AssertionError):
                image.rootfs_owner_table(listing().replace(before,after,1))

    def test_checker_reads_numeric_metadata_without_extraction(self):
        with patch.object(image,'run',return_value=listing().encode()) as command:
            result = image.verify_rootfs_ownership(Path('/synthetic/rootfs.bin'))
        argv = command.call_args.args[0]
        self.assertEqual(argv[:4],['unsquashfs','-lln','-UTC',Path('/synthetic/rootfs.bin')])
        self.assertEqual(set(argv[4:]),{name for name,mode in image.ROOTFS_BOOT_MODES.items() if mode.startswith('-')})
        self.assertEqual(len(result),12)

    def test_non_utf8_output_is_not_silently_normalized(self):
        with patch.object(image,'run',return_value=b'\xff'),self.assertRaises(UnicodeDecodeError):
            image.verify_rootfs_ownership(Path('/synthetic/rootfs.bin'))


if __name__ == '__main__': unittest.main()
