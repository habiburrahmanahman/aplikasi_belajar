"""
main.py — Aplikasi Guru (tampilan modern: FAB, transisi, filled text field, snackbar)

Alurnya:
  BiodataScreen  -> sekali di awal, membuat identitas anonim
  MainScreen     -> Bottom Navigation 2 tab: Beranda (daftar materi + FAB buat baru) & Profil
  EditorScreen   -> form materi (judul, kelas, materi teks, objek 3D, rangkuman, kuis) + Terbitkan
  RekapScreen    -> daftar murid yang sudah mengerjakan + tombol "Izinkan Ulang"

Cara menjalankan (di komputer, belum perlu Android):
    pip install -r requirements.txt
    python main.py
"""

import os
import json

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDFloatingActionButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.dialog import MDDialog

from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.core.clipboard import Clipboard
from kivy.utils import get_color_from_hex

from firebase_client import FirebaseClient

# Warna senada dengan aplikasi murid
WARNA_UTAMA = get_color_from_hex("#1B4332")   # hijau tua
WARNA_AKSEN = get_color_from_hex("#F0A93B")   # amber
WARNA_TEKS_AKSEN = (0.16, 0.1, 0.02, 1)

# Ganti ini kalau nanti aplikasi hasil (murid) dipindah hosting.
STUDENT_APP_BASE_URL = "https://singular-zabaione-5f9869.netlify.app/"

JUMLAH_SLOT_TAHAP = 5
JUMLAH_SLOT_SOAL = 5
JUMLAH_SLOT_3D = 6


def tombol_aksen(text, **kwargs):
    """Tombol utama (CTA) berwarna amber, dipakai untuk aksi paling penting di tiap layar."""
    return MDRaisedButton(text=text, md_bg_color=WARNA_AKSEN, text_color=WARNA_TEKS_AKSEN, **kwargs)


def kolom(hint, **kwargs):
    """Text field bergaya 'filled' (kotak terisi) ala Material Design terbaru."""
    return MDTextField(hint_text=hint, mode="fill", **kwargs)


def app_bar(judul, dengan_kembali=False, on_back=None):
    bar = MDTopAppBar(title=judul, elevation=2, md_bg_color=WARNA_UTAMA,
                       specific_text_color=(1, 1, 1, 1))
    if dengan_kembali:
        aksi = on_back if on_back else (lambda x: MDApp.get_running_app().goto("beranda"))
        bar.left_action_items = [["arrow-left", aksi]]
    return bar


def kabari(teks):
    Snackbar(text=teks, duration=2.2).open()


# ---------------------------------------------------------------- BIODATA
class BiodataScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = MDBoxLayout(orientation="vertical")
        root.add_widget(app_bar("Selamat Datang"))

        layout = MDBoxLayout(orientation="vertical", padding=dp(28), spacing=dp(16))

        layout.add_widget(MDLabel(text="🌿 Lengkapi Profil Guru", font_style="H5",
                                   size_hint_y=None, height=dp(44)))
        layout.add_widget(MDLabel(
            text="Diisi sekali saja saat pertama membuka aplikasi.\nTidak ada kata sandi.",
            theme_text_color="Secondary", size_hint_y=None, height=dp(50)))

        self.input_nama = kolom("Nama guru", size_hint_y=None, height=dp(60))
        self.input_sekolah = kolom("Nama sekolah", size_hint_y=None, height=dp(60))
        layout.add_widget(self.input_nama)
        layout.add_widget(self.input_sekolah)

        self.status_label = MDLabel(text="", theme_text_color="Error",
                                     size_hint_y=None, height=dp(40))
        layout.add_widget(self.status_label)

        self.btn_simpan = tombol_aksen("Simpan & Mulai", size_hint_y=None, height=dp(52))
        self.btn_simpan.bind(on_release=self.simpan_profil)
        layout.add_widget(self.btn_simpan)

        layout.add_widget(Widget())
        root.add_widget(layout)
        self.add_widget(root)

    def simpan_profil(self, *args):
        nama = self.input_nama.text.strip()
        sekolah = self.input_sekolah.text.strip()
        if not nama:
            self.status_label.text = "Nama guru wajib diisi."
            return

        self.btn_simpan.disabled = True
        self.status_label.text = "Menyiapkan akun..."

        app = MDApp.get_running_app()
        try:
            uid = app.firebase.create_anonymous_identity()
        except Exception as e:
            self.status_label.text = "Gagal terhubung ke server: " + str(e)
            self.btn_simpan.disabled = False
            return

        app.profil["nama"] = nama
        app.profil["sekolah"] = sekolah
        app.profil["uid"] = uid
        app.simpan_profil_lokal()

        kabari("Selamat datang, " + nama + "! 👋")
        app.goto("beranda")


# ---------------------------------------------------------------- BERANDA
class BerandaKonten(MDBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        bar = app_bar("Aplikasi Guru")
        bar.right_action_items = [["refresh", lambda x: self.muat_daftar_materi()]]
        self.add_widget(bar)

        area = FloatLayout()

        body = MDBoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))

        self.welcome_label = MDLabel(text="👋 Halo!", font_style="H6",
                                      size_hint_y=None, height=dp(36))
        body.add_widget(self.welcome_label)
        body.add_widget(MDLabel(text="Apa yang mau diajarkan hari ini?",
                                 theme_text_color="Secondary",
                                 size_hint_y=None, height=dp(24)))

        body.add_widget(MDLabel(text="Materi yang sudah diterbitkan", font_style="Subtitle1",
                                 size_hint_y=None, height=dp(34)))

        self.status_label = MDLabel(text="", theme_text_color="Secondary",
                                     size_hint_y=None, height=dp(28))
        body.add_widget(self.status_label)

        scroll = ScrollView()
        self.list_box = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10),
                                     padding=(0, 0, 0, dp(88)))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll.add_widget(self.list_box)
        body.add_widget(scroll)

        area.add_widget(body)

        fab = MDFloatingActionButton(icon="plus", md_bg_color=WARNA_AKSEN,
                                      text_color=WARNA_TEKS_AKSEN,
                                      pos_hint={"right": 0.94, "y": 0.05})
        fab.bind(on_release=lambda *a: MDApp.get_running_app().buka_editor_baru())
        area.add_widget(fab)

        self.add_widget(area)

    def muat_daftar_materi(self):
        app = MDApp.get_running_app()
        self.welcome_label.text = "👋 Halo, " + app.profil.get("nama", "Guru") + "!"
        self.status_label.text = "Memuat daftar materi..."
        self.list_box.clear_widgets()
        try:
            daftar = app.firebase.ambil_materi_milik_saya()
        except Exception as e:
            self.status_label.text = "Gagal memuat: " + str(e)
            return

        self.status_label.text = "" if daftar else "📭 Belum ada materi. Ketuk + untuk buat yang pertama!"
        for item in daftar:
            self.list_box.add_widget(self._baris_materi(item))

    def _baris_materi(self, item):
        judul = item.get("judul", "(tanpa judul)")
        kelas = item.get("kelas", "-")
        materi_id = item.get("_id", "")

        card = MDCard(orientation="vertical", size_hint_y=None, height=dp(130),
                       padding=(dp(14), dp(10)), spacing=dp(8),
                       elevation=1, radius=[14, 14, 14, 14])

        card.add_widget(MDLabel(text=f"{judul}", font_style="Subtitle1",
                                 size_hint_y=None, height=dp(24)))
        card.add_widget(MDLabel(text=f"Kelas {kelas}", theme_text_color="Secondary",
                                 size_hint_y=None, height=dp(20)))

        link = STUDENT_APP_BASE_URL + "?id=" + materi_id
        btn_row = MDBoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))

        btn_edit = MDFlatButton(text="✏️ Edit")
        btn_edit.bind(on_release=lambda *a, it=item: MDApp.get_running_app().buka_editor_edit(it))
        btn_row.add_widget(btn_edit)

        btn_salin = MDFlatButton(text="🔗 Salin Link")

        def salin(*a, l=link):
            Clipboard.copy(l)
            kabari("Link disalin ke clipboard 📋")

        btn_salin.bind(on_release=salin)
        btn_row.add_widget(btn_salin)

        btn_hasil = MDFlatButton(text="📊 Hasil")
        btn_hasil.bind(on_release=lambda *a, mid=materi_id, j=judul: MDApp.get_running_app().buka_hasil(mid, j))
        btn_row.add_widget(btn_hasil)

        card.add_widget(btn_row)
        return card


class ProfilKonten(MDBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.add_widget(app_bar("Profil Guru"))

        body = MDBoxLayout(orientation="vertical", padding=dp(20), spacing=dp(14))

        body.add_widget(MDLabel(text="👤 Profil Guru", font_style="H6",
                                 size_hint_y=None, height=dp(40)))
        body.add_widget(MDLabel(text="Nama dan sekolah ini tampil di materi yang Anda terbitkan.",
                                 theme_text_color="Secondary", size_hint_y=None, height=dp(44)))

        self.input_nama = kolom("Nama guru", size_hint_y=None, height=dp(60))
        self.input_sekolah = kolom("Nama sekolah", size_hint_y=None, height=dp(60))
        body.add_widget(self.input_nama)
        body.add_widget(self.input_sekolah)

        btn_simpan = tombol_aksen("Simpan Perubahan", size_hint_y=None, height=dp(50))
        btn_simpan.bind(on_release=self.simpan)
        body.add_widget(btn_simpan)

        self.label_id = MDLabel(text="", theme_text_color="Secondary", size_hint_y=None, height=dp(24))
        body.add_widget(self.label_id)

        body.add_widget(Widget())
        self.add_widget(body)

    def muat_profil(self):
        app = MDApp.get_running_app()
        self.input_nama.text = app.profil.get("nama", "")
        self.input_sekolah.text = app.profil.get("sekolah", "")
        self.label_id.text = "ID guru: " + app.profil.get("uid", "-")

    def simpan(self, *args):
        nama = self.input_nama.text.strip()
        if not nama:
            kabari("Nama tidak boleh kosong")
            return
        app = MDApp.get_running_app()
        app.profil["nama"] = nama
        app.profil["sekolah"] = self.input_sekolah.text.strip()
        app.simpan_profil_lokal()
        kabari("Profil tersimpan ✅")


class MainScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        nav = MDBottomNavigation()

        tab_beranda = MDBottomNavigationItem(name="tab_beranda", text="Beranda", icon="home-variant")
        self.beranda = BerandaKonten()
        tab_beranda.add_widget(self.beranda)
        nav.add_widget(tab_beranda)

        tab_profil = MDBottomNavigationItem(name="tab_profil", text="Profil", icon="account-circle")
        self.profil = ProfilKonten()
        tab_profil.add_widget(self.profil)
        nav.add_widget(tab_profil)

        self.add_widget(nav)

    def on_pre_enter(self, *args):
        self.beranda.muat_daftar_materi()
        self.profil.muat_profil()


# ---------------------------------------------------------------- REKAP HASIL
class RekapScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.materi_id = None
        root = MDBoxLayout(orientation="vertical")

        self.bar = app_bar("Rekap Hasil", dengan_kembali=True)
        root.add_widget(self.bar)

        body = MDBoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        self.summary_card = MDCard(orientation="vertical", size_hint_y=None, height=dp(96),
                                    padding=dp(14), spacing=dp(6), elevation=1,
                                    radius=[16, 16, 16, 16], md_bg_color=WARNA_UTAMA)
        self.summary_judul = MDLabel(text="Memuat hasil...", font_style="Subtitle1",
                                      theme_text_color="Custom", text_color=(1, 1, 1, 1),
                                      size_hint_y=None, height=dp(30))
        self.summary_detail = MDLabel(text="", theme_text_color="Custom",
                                       text_color=(0.88, 0.94, 0.9, 1),
                                       size_hint_y=None, height=dp(44))
        self.summary_card.add_widget(self.summary_judul)
        self.summary_card.add_widget(self.summary_detail)
        body.add_widget(self.summary_card)

        scroll = ScrollView()
        self.list_box = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll.add_widget(self.list_box)
        body.add_widget(scroll)

        root.add_widget(body)
        self.add_widget(root)

    def tampilkan(self, materi_id, judul_materi):
        self.materi_id = materi_id
        self.bar.title = "Rekap: " + judul_materi
        self.summary_judul.text = "Memuat hasil..."
        self.summary_detail.text = ""
        self.list_box.clear_widgets()

        app = MDApp.get_running_app()
        try:
            daftar = app.firebase.ambil_hasil_kuis(materi_id)
        except Exception as e:
            self.summary_judul.text = "Gagal memuat"
            self.summary_detail.text = str(e)
            return

        if not daftar:
            self.summary_judul.text = "📭 Belum ada murid yang mengerjakan"
            self.summary_detail.text = "Rekap akan muncul di sini begitu ada yang selesai mengerjakan."
            return

        def persen(it):
            total = it.get("totalSoal") or 1
            return (it.get("skor", 0) / total) * 100 if total else 0

        daftar_urut = sorted(daftar, key=persen, reverse=True)
        nilai = [persen(it) for it in daftar_urut]

        self.summary_judul.text = f"👥 {len(daftar_urut)} murid sudah mengerjakan"
        self.summary_detail.text = (
            f"Rata-rata {sum(nilai)/len(nilai):.0f}%   •   "
            f"Tertinggi {max(nilai):.0f}%   •   Terendah {min(nilai):.0f}%"
        )

        for item in daftar_urut:
            self.list_box.add_widget(self._baris_hasil(item))

    def _baris_hasil(self, item):
        nama = item.get("nama", "-")
        kelas = item.get("kelas", "-")
        absen = item.get("absen", "-")
        skor = item.get("skor", 0)
        total = item.get("totalSoal") or 1
        persen = (skor / total) * 100 if total else 0

        if persen >= 80:
            warna_lencana = get_color_from_hex("#2E7D32")
        elif persen >= 50:
            warna_lencana = get_color_from_hex("#D98F1F")
        else:
            warna_lencana = get_color_from_hex("#C0392B")

        card = MDCard(orientation="horizontal", size_hint_y=None, height=dp(110),
                       padding=(dp(14), dp(10)), spacing=dp(10),
                       elevation=1, radius=[16, 16, 16, 16])

        kiri = MDBoxLayout(orientation="vertical", spacing=dp(4))
        kiri.add_widget(MDLabel(text=f"{nama}", font_style="Subtitle1",
                                 size_hint_y=None, height=dp(24)))
        kiri.add_widget(MDLabel(text=f"No. {absen}  •  Kelas {kelas}", theme_text_color="Secondary",
                                 size_hint_y=None, height=dp(20)))

        btn_izin = MDFlatButton(text="🔓 Izinkan Ulang", size_hint_y=None, height=dp(34))

        def beri_izin(*a, k=kelas, ab=absen, btn=btn_izin):
            btn.disabled = True
            btn.text = "Menyimpan..."
            app = MDApp.get_running_app()
            try:
                app.firebase.izinkan_ulang(self.materi_id, k, ab)
                btn.text = "✅ Boleh mengulang"
                kabari("Murid ini boleh mengerjakan ulang 🔓")
            except Exception as e:
                btn.text = "Gagal: " + str(e)
                btn.disabled = False

        btn_izin.bind(on_release=beri_izin)
        kiri.add_widget(btn_izin)
        card.add_widget(kiri)

        badge_wrap = AnchorLayout(anchor_x="center", anchor_y="center",
                                   size_hint_x=None, width=dp(72))
        badge = MDCard(size_hint=(None, None), size=(dp(64), dp(64)), padding=0,
                       md_bg_color=warna_lencana, radius=[32, 32, 32, 32])
        label_skor = MDLabel(text=f"{skor}/{total}", halign="center", valign="middle",
                              theme_text_color="Custom", text_color=(1, 1, 1, 1),
                              font_style="Caption")
        label_skor.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        badge.add_widget(label_skor)
        badge_wrap.add_widget(badge)
        card.add_widget(badge_wrap)

        return card


# ---------------------------------------------------------------- widget bantu
class TahapSlot(MDCard):
    def __init__(self, nomor, on_hapus=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(176),
                          padding=dp(12), spacing=dp(8), elevation=0.5,
                          radius=[12, 12, 12, 12], **kwargs)
        self.on_hapus = on_hapus

        header = MDBoxLayout(size_hint_y=None, height=dp(30))
        self.label_nomor = MDLabel(text=f"Tahap {nomor}", theme_text_color="Secondary")
        header.add_widget(self.label_nomor)
        btn_hapus = MDIconButton(icon="close-circle-outline", theme_text_color="Secondary",
                                  size_hint=(None, None), size=(dp(30), dp(30)))
        btn_hapus.bind(on_release=lambda *a: self.on_hapus(self) if self.on_hapus else None)
        header.add_widget(btn_hapus)
        self.add_widget(header)

        self.input_judul = kolom("Judul tahap", size_hint_y=None, height=dp(58))
        self.input_isi = kolom("Penjelasan singkat", multiline=True,
                                size_hint_y=None, height=dp(62))
        self.add_widget(self.input_judul)
        self.add_widget(self.input_isi)

    def atur_nomor(self, nomor):
        self.label_nomor.text = f"Tahap {nomor}"

    def ambil_data(self):
        judul = self.input_judul.text.strip()
        isi = self.input_isi.text.strip()
        if not judul:
            return None
        return {"judul": judul, "isi": isi}


class KuisSlot(MDCard):
    def __init__(self, nomor, on_hapus=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(342),
                          padding=dp(12), spacing=dp(8), elevation=0.5,
                          radius=[12, 12, 12, 12], **kwargs)
        self.on_hapus = on_hapus

        header = MDBoxLayout(size_hint_y=None, height=dp(30))
        self.label_nomor = MDLabel(text=f"Soal {nomor}", theme_text_color="Secondary")
        header.add_widget(self.label_nomor)
        btn_hapus = MDIconButton(icon="close-circle-outline", theme_text_color="Secondary",
                                  size_hint=(None, None), size=(dp(30), dp(30)))
        btn_hapus.bind(on_release=lambda *a: self.on_hapus(self) if self.on_hapus else None)
        header.add_widget(btn_hapus)
        self.add_widget(header)

        self.input_pertanyaan = kolom("Pertanyaan", size_hint_y=None, height=dp(58))
        self.add_widget(self.input_pertanyaan)

        self.input_opsi = []
        for label in ["Opsi A", "Opsi B", "Opsi C", "Opsi D"]:
            ti = kolom(label, size_hint_y=None, height=dp(52))
            self.input_opsi.append(ti)
            self.add_widget(ti)

        row = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        row.add_widget(MDLabel(text="Jawaban benar:", size_hint_x=None, width=dp(130)))
        self.spinner_jawaban = Spinner(text="A", values=["A", "B", "C", "D"])
        row.add_widget(self.spinner_jawaban)
        self.add_widget(row)

    def atur_nomor(self, nomor):
        self.label_nomor.text = f"Soal {nomor}"

    def ambil_data(self):
        pertanyaan = self.input_pertanyaan.text.strip()
        opsi = [ti.text.strip() for ti in self.input_opsi]
        if not pertanyaan or not all(opsi):
            return None
        jawaban_benar = {"A": 0, "B": 1, "C": 2, "D": 3}[self.spinner_jawaban.text]
        return {"pertanyaan": pertanyaan, "opsi": opsi, "jawabanBenar": jawaban_benar}


class Objek3DSlot(MDCard):
    def __init__(self, nomor, on_hapus=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(225),
                          padding=dp(12), spacing=dp(8), elevation=0.5,
                          radius=[12, 12, 12, 12], **kwargs)
        self.on_hapus = on_hapus

        header = MDBoxLayout(size_hint_y=None, height=dp(30))
        self.label_nomor = MDLabel(text=f"Sisi {nomor}", theme_text_color="Secondary")
        header.add_widget(self.label_nomor)
        btn_hapus = MDIconButton(icon="close-circle-outline", theme_text_color="Secondary",
                                  size_hint=(None, None), size=(dp(30), dp(30)))
        btn_hapus.bind(on_release=lambda *a: self.on_hapus(self) if self.on_hapus else None)
        header.add_widget(btn_hapus)
        self.add_widget(header)

        row = MDBoxLayout(size_hint_y=None, height=dp(66), spacing=dp(8))
        self.input_emoji = kolom("Emoji", size_hint_x=None, width=dp(90), height=dp(66))
        self.input_label = kolom("Label singkat (contoh: Matahari)", height=dp(66))
        row.add_widget(self.input_emoji)
        row.add_widget(self.input_label)
        self.add_widget(row)

        self.input_deskripsi = kolom("Deskripsi singkat", multiline=True, size_hint_y=None, height=dp(74))
        self.add_widget(self.input_deskripsi)

    def atur_nomor(self, nomor):
        self.label_nomor.text = f"Sisi {nomor}"

    def ambil_data(self):
        label = self.input_label.text.strip()
        if not label:
            return None
        return {
            "emoji": self.input_emoji.text.strip() or "🔹",
            "label": label,
            "deskripsi": self.input_deskripsi.text.strip(),
        }


# ---------------------------------------------------------------- EDITOR
class EditorScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.materi_id = None
        self.objek3d_slots = []
        self.tahap_slots = []
        self.kuis_slots = []

        outer = MDBoxLayout(orientation="vertical")
        self.bar = app_bar("Materi Baru", dengan_kembali=True, on_back=self.konfirmasi_keluar)
        outer.add_widget(self.bar)

        scroll = ScrollView()
        self.scroll = scroll
        form = MDBoxLayout(orientation="vertical", size_hint_y=None, padding=dp(16), spacing=dp(12))
        form.bind(minimum_height=form.setter("height"))

        self.input_judul = kolom("Judul materi", size_hint_y=None, height=dp(60))
        self.input_kelas = kolom("Kelas (contoh: 5A)", size_hint_y=None, height=dp(60))
        form.add_widget(self.input_judul)
        form.add_widget(self.input_kelas)

        form.add_widget(MDLabel(text="📝 Materi teks (pisahkan tiap paragraf dengan baris kosong)",
                                 theme_text_color="Secondary", size_hint_y=None, height=dp(26)))
        self.input_materi_teks = kolom("Tulis materinya di sini...", multiline=True,
                                        size_hint_y=None, height=dp(164))
        form.add_widget(self.input_materi_teks)

        row3d = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        self.check_3d = MDCheckbox(size_hint=(None, None), size=(dp(32), dp(32)))
        row3d.add_widget(self.check_3d)
        row3d.add_widget(MDLabel(text="Sertakan objek 3D untuk materi ini"))
        form.add_widget(row3d)

        form.add_widget(MDLabel(text="🧊 Objek 3D (opsional, isi kalau toggle di atas dinyalakan)",
                                 theme_text_color="Secondary", size_hint_y=None, height=dp(40)))
        self.objek3d_container = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        self.objek3d_container.bind(minimum_height=self.objek3d_container.setter("height"))
        form.add_widget(self.objek3d_container)
        btn_tambah_3d = MDFlatButton(text="+ Tambah Sisi", size_hint_y=None, height=dp(40))
        btn_tambah_3d.bind(on_release=lambda *a: self.tambah_objek3d())
        form.add_widget(btn_tambah_3d)

        form.add_widget(MDLabel(text="📋 Rangkuman / Tahapan", font_style="Subtitle1",
                                 size_hint_y=None, height=dp(30)))
        self.tahap_container = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        self.tahap_container.bind(minimum_height=self.tahap_container.setter("height"))
        form.add_widget(self.tahap_container)
        btn_tambah_tahap = MDFlatButton(text="+ Tambah Tahap", size_hint_y=None, height=dp(40))
        btn_tambah_tahap.bind(on_release=lambda *a: self.tambah_tahap())
        form.add_widget(btn_tambah_tahap)

        form.add_widget(MDLabel(text="❓ Kuis", font_style="Subtitle1",
                                 size_hint_y=None, height=dp(30)))
        self.kuis_container = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        self.kuis_container.bind(minimum_height=self.kuis_container.setter("height"))
        form.add_widget(self.kuis_container)
        btn_tambah_soal = MDFlatButton(text="+ Tambah Soal", size_hint_y=None, height=dp(40))
        btn_tambah_soal.bind(on_release=lambda *a: self.tambah_soal())
        form.add_widget(btn_tambah_soal)

        self.status_label = MDLabel(text="", theme_text_color="Error",
                                     size_hint_y=None, height=dp(50))
        form.add_widget(self.status_label)

        self.link_label = kolom("", readonly=True, size_hint_y=None, height=dp(58))
        form.add_widget(self.link_label)

        btn_salin_link = MDFlatButton(text="🔗 Salin Link Murid", size_hint_y=None, height=dp(46))
        btn_salin_link.bind(on_release=lambda *a: (Clipboard.copy(self.link_label.text),
                                                     kabari("Link disalin 📋")))
        form.add_widget(btn_salin_link)

        self.btn_terbitkan = tombol_aksen("🚀 Terbitkan", size_hint_y=None, height=dp(54))
        self.btn_terbitkan.bind(on_release=self.terbitkan)
        form.add_widget(self.btn_terbitkan)

        scroll.add_widget(form)
        outer.add_widget(scroll)
        self.add_widget(outer)

    # ---------- tambah/hapus slot objek 3D ----------
    def tambah_objek3d(self, data=None):
        slot = Objek3DSlot(len(self.objek3d_slots) + 1, on_hapus=self.hapus_objek3d)
        if data:
            slot.input_emoji.text = data.get("emoji", "")
            slot.input_label.text = data.get("label", "")
            slot.input_deskripsi.text = data.get("deskripsi", "")
        self.objek3d_slots.append(slot)
        self.objek3d_container.add_widget(slot)

    def hapus_objek3d(self, slot):
        if slot in self.objek3d_slots:
            self.objek3d_slots.remove(slot)
            self.objek3d_container.remove_widget(slot)
            for i, s in enumerate(self.objek3d_slots, start=1):
                s.atur_nomor(i)

    # ---------- tambah/hapus slot tahap ----------
    def tambah_tahap(self, data=None):
        slot = TahapSlot(len(self.tahap_slots) + 1, on_hapus=self.hapus_tahap)
        if data:
            slot.input_judul.text = data.get("judul", "")
            slot.input_isi.text = data.get("isi", "")
        self.tahap_slots.append(slot)
        self.tahap_container.add_widget(slot)

    def hapus_tahap(self, slot):
        if slot in self.tahap_slots:
            self.tahap_slots.remove(slot)
            self.tahap_container.remove_widget(slot)
            for i, s in enumerate(self.tahap_slots, start=1):
                s.atur_nomor(i)

    # ---------- tambah/hapus slot soal kuis ----------
    def tambah_soal(self, data=None):
        slot = KuisSlot(len(self.kuis_slots) + 1, on_hapus=self.hapus_soal)
        if data:
            slot.input_pertanyaan.text = data.get("pertanyaan", "")
            opsi = data.get("opsi") or ["", "", "", ""]
            for i, ti in enumerate(slot.input_opsi):
                ti.text = opsi[i] if i < len(opsi) else ""
            huruf = {0: "A", 1: "B", 2: "C", 3: "D"}
            slot.spinner_jawaban.text = huruf.get(data.get("jawabanBenar", 0), "A")
        self.kuis_slots.append(slot)
        self.kuis_container.add_widget(slot)

    def hapus_soal(self, slot):
        if slot in self.kuis_slots:
            self.kuis_slots.remove(slot)
            self.kuis_container.remove_widget(slot)
            for i, s in enumerate(self.kuis_slots, start=1):
                s.atur_nomor(i)

    def konfirmasi_keluar(self, *args):
        if not hasattr(self, "_dialog_keluar"):
            self._dialog_keluar = MDDialog(
                title="Keluar dari halaman ini?",
                text="Pastikan sudah menekan Terbitkan kalau ada perubahan yang ingin disimpan.",
                buttons=[
                    MDFlatButton(text="Batal", on_release=lambda *a: self._dialog_keluar.dismiss()),
                    tombol_aksen("Ya, Keluar", on_release=lambda *a: self._keluar_sekarang()),
                ],
            )
        self._dialog_keluar.open()

    def _keluar_sekarang(self):
        self._dialog_keluar.dismiss()
        MDApp.get_running_app().goto("beranda")

    def siapkan_materi_baru(self):
        app = MDApp.get_running_app()
        self.materi_id = app.firebase.buat_id_materi_baru()
        self.bar.title = "Materi Baru"
        self.input_judul.text = ""
        self.input_kelas.text = ""
        self.input_materi_teks.text = ""
        self.check_3d.active = False

        self.objek3d_container.clear_widgets()
        self.objek3d_slots = []
        self.tambah_objek3d()

        self.tahap_container.clear_widgets()
        self.tahap_slots = []
        self.tambah_tahap()

        self.kuis_container.clear_widgets()
        self.kuis_slots = []
        self.tambah_soal()

        self.status_label.text = ""
        self.link_label.text = ""

    def muat_untuk_edit(self, item):
        self.materi_id = item.get("_id")
        self.bar.title = "Edit Materi"
        self.input_judul.text = item.get("judul", "")
        self.input_kelas.text = item.get("kelas", "")
        self.input_materi_teks.text = "\n\n".join(item.get("materiTeks") or [])
        self.check_3d.active = bool(item.get("punya3d"))

        self.objek3d_container.clear_widgets()
        self.objek3d_slots = []
        objek3d = item.get("objek3d") or []
        for d in objek3d:
            self.tambah_objek3d(d)
        if not objek3d:
            self.tambah_objek3d()

        self.tahap_container.clear_widgets()
        self.tahap_slots = []
        rangkuman = item.get("rangkuman") or []
        for d in rangkuman:
            self.tambah_tahap(d)
        if not rangkuman:
            self.tambah_tahap()

        self.kuis_container.clear_widgets()
        self.kuis_slots = []
        kuis = item.get("kuis") or []
        for q in kuis:
            self.tambah_soal(q)
        if not kuis:
            self.tambah_soal()

        self.status_label.text = ""
        self.link_label.text = STUDENT_APP_BASE_URL + "?id=" + self.materi_id

    def terbitkan(self, *args):
        judul = self.input_judul.text.strip()
        kelas = self.input_kelas.text.strip()
        paragraf = [p.strip() for p in self.input_materi_teks.text.split("\n\n") if p.strip()]
        objek3d = [d for d in (s.ambil_data() for s in self.objek3d_slots) if d]
        rangkuman = [d for d in (s.ambil_data() for s in self.tahap_slots) if d]
        kuis = [d for d in (s.ambil_data() for s in self.kuis_slots) if d]

        if not judul:
            self.status_label.text = "Judul materi wajib diisi."
            kabari("⚠️ Judul materi wajib diisi.")
            self.scroll.scroll_y = 1
            return
        if not paragraf:
            self.status_label.text = "Materi teks wajib diisi."
            kabari("⚠️ Materi teks wajib diisi.")
            self.scroll.scroll_y = 1
            return
        if not kuis:
            self.status_label.text = "Isi minimal 1 soal kuis (pertanyaan + 4 opsi)."
            kabari("⚠️ Isi minimal 1 soal kuis (pertanyaan + 4 opsi).")
            self.scroll.scroll_y = 1
            return

        data = {
            "judul": judul,
            "kelas": kelas,
            "materiTeks": paragraf,
            "punya3d": bool(self.check_3d.active and objek3d),
            "objek3d": objek3d,
            "rangkuman": rangkuman,
            "kuis": kuis,
        }

        self.btn_terbitkan.disabled = True
        self.status_label.text = "Menerbitkan..."

        app = MDApp.get_running_app()
        try:
            app.firebase.terbitkan_materi(self.materi_id, data)
        except Exception as e:
            self.status_label.text = "Gagal menerbitkan: " + str(e)
            kabari("❌ Gagal menerbitkan: " + str(e))
            self.btn_terbitkan.disabled = False
            return

        self.status_label.text = "Berhasil diterbitkan!"
        self.link_label.text = STUDENT_APP_BASE_URL + "?id=" + self.materi_id
        self.btn_terbitkan.disabled = False
        kabari("Materi berhasil diterbitkan! 🎉")


# ---------------------------------------------------------------- APP
class AplikasiGuruApp(MDApp):
    def build(self):
        self.title = "Aplikasi Guru"
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Light"

        self.profil_path = os.path.join(self.user_data_dir, "profil_guru.json")
        self.token_path = os.path.join(self.user_data_dir, "auth_tokens.json")

        self.firebase = FirebaseClient(self.token_path)
        self.profil = self._muat_profil_lokal()

        self.sm = ScreenManager(transition=SlideTransition(direction="left", duration=0.22))
        self.sm.add_widget(BiodataScreen(name="biodata"))
        self.sm.add_widget(MainScreen(name="beranda"))
        self.sm.add_widget(EditorScreen(name="editor"))
        self.sm.add_widget(RekapScreen(name="rekap"))

        if self.firebase.has_identity() and self.profil.get("nama"):
            self.sm.current = "beranda"
        else:
            self.sm.current = "biodata"

        return self.sm

    def _muat_profil_lokal(self):
        try:
            with open(self.profil_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def simpan_profil_lokal(self):
        with open(self.profil_path, "w", encoding="utf-8") as f:
            json.dump(self.profil, f)

    def goto(self, nama_screen):
        urutan = ["biodata", "beranda", "editor", "rekap"]
        try:
            arah = "left" if urutan.index(nama_screen) >= urutan.index(self.sm.current) else "right"
            self.sm.transition.direction = arah
        except ValueError:
            pass
        self.sm.current = nama_screen

    def buka_editor_baru(self):
        editor = self.sm.get_screen("editor")
        editor.siapkan_materi_baru()
        self.goto("editor")

    def buka_editor_edit(self, item):
        editor = self.sm.get_screen("editor")
        editor.muat_untuk_edit(item)
        self.goto("editor")

    def buka_hasil(self, materi_id, judul_materi):
        rekap = self.sm.get_screen("rekap")
        rekap.tampilkan(materi_id, judul_materi)
        self.goto("rekap")


if __name__ == "__main__":
    AplikasiGuruApp().run()
