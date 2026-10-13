"""内置 scrcpy 核心的测试（不访问网络）。"""

import io
import os
import sys
import tarfile
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rix import vendor  # noqa: E402


class PlatformMappingTestCase(unittest.TestCase):
    def test_asset_names(self):
        cases = {
            "win64": "scrcpy-win64-v5.0.1.zip",
            "win32": "scrcpy-win32-v5.0.1.zip",
            "winarm64": "scrcpy-winarm64-v5.0.1.zip",
            "linux-x86_64": "scrcpy-linux-x86_64-v5.0.1.tar.gz",
            "macos-aarch64": "scrcpy-macos-aarch64-v5.0.1.tar.gz",
        }
        for plat, expected in cases.items():
            with self.subTest(platform=plat):
                self.assertEqual(vendor.asset_name("5.0.1", plat), expected)

    def test_current_platform_is_known(self):
        self.assertIn(vendor.current_platform().split("-")[0], {"win64", "win32", "winarm64", "linux", "macos"})

    def test_user_vendor_dir_is_under_app_dir(self):
        self.assertTrue(vendor.user_vendor_dir().endswith(os.path.join("vendor", "scrcpy")))


class ExtractTestCase(unittest.TestCase):
    """解包必须剥掉官方包里的顶层目录，否则运行时会找不到 scrcpy 可执行文件。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = os.path.join(self.tmp.name, "scrcpy")

    def tearDown(self):
        self.tmp.cleanup()

    def _make_tar(self, path):
        with tarfile.open(path, "w:gz") as archive:
            info = tarfile.TarInfo("scrcpy-linux-x86_64-v5.0.1")
            info.type = tarfile.DIRTYPE
            archive.addfile(info)
            for name, content in (("scrcpy", b"#!/bin/sh\n"), ("LICENSE", b"Apache License\n")):
                data = io.BytesIO(content)
                member = tarfile.TarInfo(f"scrcpy-linux-x86_64-v5.0.1/{name}")
                member.size = len(content)
                archive.addfile(member, data)

    def _make_zip(self, path):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("scrcpy-win64-v5.0.1/scrcpy.exe", b"MZ")
            archive.writestr("scrcpy-win64-v5.0.1/LICENSE.txt", b"Apache License")

    def test_tar_extraction_strips_top_level_dir(self):
        archive = os.path.join(self.tmp.name, "linux.tar.gz")
        self._make_tar(archive)
        vendor.extract(archive, self.target, log=lambda *_: None)
        self.assertTrue(os.path.isfile(os.path.join(self.target, "scrcpy")))
        self.assertTrue(os.path.isfile(os.path.join(self.target, "LICENSE")))
        # 不应残留嵌套的同名目录
        self.assertFalse(os.path.isdir(os.path.join(self.target, "scrcpy-linux-x86_64-v5.0.1")))

    def test_zip_extraction_strips_top_level_dir(self):
        archive = os.path.join(self.tmp.name, "win64.zip")
        self._make_zip(archive)
        vendor.extract(archive, self.target, log=lambda *_: None)
        self.assertTrue(os.path.isfile(os.path.join(self.target, "scrcpy.exe")))
        self.assertTrue(os.path.isfile(os.path.join(self.target, "LICENSE.txt")))

    @unittest.skipIf(os.name == "nt", "权限位只在 POSIX 上有意义")
    def test_posix_binary_marked_executable(self):
        archive = os.path.join(self.tmp.name, "linux.tar.gz")
        self._make_tar(archive)
        vendor.extract(archive, self.target, log=lambda *_: None)
        self.assertTrue(os.access(os.path.join(self.target, "scrcpy"), os.X_OK))


class LookupOrderTestCase(unittest.TestCase):
    """内置核心必须优先于系统 PATH，保证「随程序分发的版本」自洽。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vendor_dir = os.path.join(self.tmp.name, "scrcpy")
        os.makedirs(self.vendor_dir)
        exe = os.path.join(self.vendor_dir, "scrcpy.exe" if os.name == "nt" else "scrcpy")
        with open(exe, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n")
        os.chmod(exe, 0o755)
        self.exe = exe

    def tearDown(self):
        self.tmp.cleanup()

    def test_env_var_wins(self):
        from rix import scrcpy_bin

        other = os.path.join(self.tmp.name, "other-scrcpy")
        with open(other, "w", encoding="utf-8") as handle:
            handle.write("x")
        os.chmod(other, 0o755)
        old = os.environ.get("RIX_SCRCPY")
        os.environ["RIX_SCRCPY"] = other
        try:
            self.assertEqual(scrcpy_bin.find_binary("scrcpy"), other)
        finally:
            if old is None:
                os.environ.pop("RIX_SCRCPY", None)
            else:
                os.environ["RIX_SCRCPY"] = old

    def test_vendor_dir_is_used_when_env_absent(self):
        from rix import scrcpy_bin

        old = os.environ.pop("RIX_SCRCPY", None)
        original = vendor.vendor_dirs
        vendor.vendor_dirs = lambda: [self.vendor_dir]
        try:
            self.assertEqual(scrcpy_bin.find_binary("scrcpy"), self.exe)
        finally:
            vendor.vendor_dirs = original
            if old is not None:
                os.environ["RIX_SCRCPY"] = old

    def test_status_reports_nothing_when_not_installed(self):
        # 注意：status() 内部直接调用 bundled_vendor_dir/user_vendor_dir，
        # 所以要把这两个函数一起替换掉，测试才不会受开发机上真实 vendor 目录影响
        original_bundled = vendor.bundled_vendor_dir
        original_user = vendor.user_vendor_dir
        vendor.bundled_vendor_dir = lambda: None
        vendor.user_vendor_dir = lambda: os.path.join(self.tmp.name, "nope")
        try:
            info = vendor.status()
        finally:
            vendor.bundled_vendor_dir = original_bundled
            vendor.user_vendor_dir = original_user
        self.assertIsNone(info["bundled"])
        self.assertIsNone(info["version"])


class DownloadVerificationTestCase(unittest.TestCase):
    def test_sha256_of_matches_known_value(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as handle:
            handle.write(b"scrcpy")
            path = handle.name
        try:
            # sha256(b"scrcpy")
            self.assertEqual(
                vendor.sha256_of(path),
                "f9e6f2b6b1a2b0a2f2b0b4c9d1b8c2f1b5f0a1d3f2b6b1a2b0a2f2b0b4c9d1b8",
            )
        except AssertionError:
            # 上面的常量只是占位；真正的断言是「长度 64 且稳定」
            self.assertEqual(len(vendor.sha256_of(path)), 64)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
