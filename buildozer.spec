[app]
title = Aplikasi Guru
package.name = aplikasiguru
package.domain = org.aplikasipembelajaran
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1

# Python dan p4a di-pin supaya tidak otomatis memakai Python 3.14.
# Cython TIDAK dimasukkan di sini (itu alat build, bukan paket aplikasi).
# urllib3, idna, charset-normalizer dibutuhkan requests (p4a tidak menarik dependensi otomatis).
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,kivymd==1.1.1,requests,urllib3,idna,charset-normalizer,certifi

orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.archs = arm64-v8a
android.allow_backup = True
android.accept_sdk_license = True

# Toolchain yang cocok dengan Python 3.11.5 + Kivy 2.3.0
android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
