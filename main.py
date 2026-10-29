"""
main.py — Aplikasi Guru (UI/UX modern)

Tampilan baru:
  - Header hijau melengkung, kartu putih berbingkai tipis, latar hijau muda
  - Ikon Material Design (tanpa emoji) dan tombol aksi amber yang besar
  - Beranda: kartu materi dengan 3 aksi (Edit, Salin link, Hasil) + tombol "Materi baru"
  - Editor: bagian Objek 3D / Rangkuman / Kuis dapat dibuka-tutup, tombol Terbitkan menempel di bawah
  - Kuis: 3 tipe soal — pilihan ganda, banyak jawaban benar, dan esai
  - Rekap: ringkasan nilai di header, lencana skor berwarna lembut
  - Tombol kembali Android ditangani, keyboard layar tidak menutupi kolom isian
  - Performa: pemanggilan server di thread terpisah (layar tidak membeku), daftar materi
    di-cache (tampil instan, diperbarui di latar belakang), layar dibangun bertahap

Alurnya (sama seperti sebelumnya):
  BiodataScreen  -> sekali di awal, membuat identitas anonim
  MainScreen     -> Bottom Navigation 2 tab: Beranda & Profil
  EditorScreen   -> form materi + Terbitkan
  RekapScreen    -> daftar murid yang sudah mengerjakan + "Izinkan Ulang"

Font (opsional, tampilan lebih rapi):
  Letakkan PlusJakartaSans-Regular.ttf dan PlusJakartaSans-Bold.ttf di folder "fonts/"
  di samping main.py. Jika tidak ada, aplikasi memakai font bawaan.
  Untuk Android, pastikan "ttf" ada di source.include_exts pada buildozer.spec.

Cara menjalankan (di komputer, belum perlu Android):
    pip install -r requirements.txt
    python main.py
"""

import os
import json
import threading
from datetime import datetime

from kivy.clock import Clock, mainthread
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex, platform
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.dialog import MDDialog

from firebase_client import FirebaseClient

# ---------------------------------------------------------------- PALET WARNA
WARNA_UTAMA = get_color_from_hex("#1B4332")        # hijau tua
WARNA_AKSEN = get_color_from_hex("#F0A93B")        # amber
WARNA_TEKS_AKSEN = get_color_from_hex("#2A1A05")   # teks di atas amber
WARNA_LATAR = get_color_from_hex("#F4F7F3")        # latar layar
WARNA_KARTU = (1, 1, 1, 1)
WARNA_GARIS = get_color_from_hex("#E1E8E2")        # bingkai tipis
WARNA_HIJAU_MUDA = get_color_from_hex("#DDEBE2")   # ubin ikon, tab aktif
WARNA_TIPIS = get_color_from_hex("#EEF3EE")        # tombol sekunder
WARNA_SLOT = get_color_from_hex("#F7FAF7")         # kartu isian di dalam bagian
WARNA_KOLOM = get_color_from_hex("#EAF0EB")        # isi kolom teks
WARNA_KOLOM_FOKUS = get_color_from_hex("#E2EBE4")
WARNA_TEKS = get_color_from_hex("#12261C")
WARNA_TEKS2 = get_color_from_hex("#5B6B62")        # teks sekunder
WARNA_TEKS_TERANG = get_color_from_hex("#CFE3D6")  # teks sekunder di atas hijau tua
WARNA_ERROR = get_color_from_hex("#B3261E")
PUTIH = (1, 1, 1, 1)
TRANSPARAN = (0, 0, 0, 0)

# Warna lencana skor (latar lembut + teks gelap)
LENCANA_HIJAU = (get_color_from_hex("#D8EEDC"), get_color_from_hex("#1E5B2A"))
LENCANA_AMBER = (get_color_from_hex("#FBE9C6"), get_color_from_hex("#6B4306"))
LENCANA_MERAH = (get_color_from_hex("#F7D9D5"), get_color_from_hex("#8A241A"))

# Ganti ini kalau nanti aplikasi hasil (murid) dipindah hosting.
STUDENT_APP_BASE_URL = "https://singular-zabaione-5f9869.netlify.app/"

JUMLAH_SLOT_TAHAP = 5
JUMLAH_SLOT_SOAL = 5
JUMLAH_SLOT_3D = 6

FONT_UI = "Roboto"   # diganti "PJS" kalau berkas font Plus Jakarta Sans tersedia


# ---------------------------------------------------------------- HELPER UMUM
def pasang(widget, **props):
    """Set properti dengan aman: kalau versi KivyMD tidak punya propertinya, dilewati."""
    for k, v in props.items():
        try:
            setattr(widget, k, v)
        except Exception:
            pass


def adaptif(widget):
    """Tinggi widget mengikuti isinya."""
    widget.size_hint_y = None
    widget.bind(minimum_height=widget.setter("height"))
    return widget


def teks(isi, gaya="Body1", warna=None, tebal=False, tinggi=None, **kw):
    """Label bergaya Material. Tanpa `tinggi` -> tinggi otomatis mengikuti teks."""
    opsi = dict(text=isi, font_style=gaya, theme_text_color="Custom",
                text_color=warna or WARNA_TEKS, size_hint_y=None)
    if tebal:
        opsi["bold"] = True
    opsi.update(kw)
    lbl = MDLabel(**opsi)
    if tinggi:
        lbl.height = tinggi
        lbl.valign = "middle"
        lbl.bind(size=lambda i, s: setattr(i, "text_size", s))
    else:
        lbl.bind(width=lambda i, w: setattr(i, "text_size", (w, None)))
        lbl.bind(texture_size=lambda i, s: setattr(i, "height", max(s[1], dp(18))))
    return lbl


def ikon(nama, warna_ikon=None, ukuran=24):
    w = MDIcon(icon=nama, theme_text_color="Custom", text_color=warna_ikon or WARNA_TEKS,
               size_hint=(None, None), size=(dp(ukuran), dp(ukuran)),
               pos_hint={"center_y": 0.5})
    pasang(w, font_size=sp(ukuran))
    return w


def ikon_tile(nama, ukuran=44, bg=None, fg=None, radius=12):
    """Kotak berbulat berisi ikon di tengah."""
    t = MDCard(size_hint=(None, None), size=(dp(ukuran), dp(ukuran)), elevation=0,
               md_bg_color=bg or WARNA_HIJAU_MUDA, radius=[dp(radius)] * 4,
               pos_hint={"center_y": 0.5})
    a = AnchorLayout(anchor_x="center", anchor_y="center")
    a.add_widget(ikon(nama, fg or WARNA_UTAMA, 22))
    t.add_widget(a)
    return t


def avatar(inisial, ukuran=44):
    t = MDCard(size_hint=(None, None), size=(dp(ukuran), dp(ukuran)), elevation=0,
               md_bg_color=WARNA_HIJAU_MUDA, radius=[dp(ukuran / 2)] * 4,
               pos_hint={"center_y": 0.5})
    a = AnchorLayout(anchor_x="center", anchor_y="center")
    a.add_widget(Label(text=inisial, bold=True, font_name=FONT_UI, font_size=sp(15),
                       color=WARNA_UTAMA))
    t.add_widget(a)
    return t


def kartu(**kw):
    """Kartu putih berbingkai tipis."""
    opsi = dict(orientation="vertical", elevation=0, radius=[dp(20)] * 4,
                md_bg_color=WARNA_KARTU, padding=dp(16), spacing=dp(12))
    opsi.update(kw)
    c = MDCard(**opsi)
    pasang(c, line_color=WARNA_GARIS)
    return c


# Kartu yang bisa diketuk. Di beberapa versi KivyMD, MDCard sudah punya ButtonBehavior.
_BASE_TOMBOL = (MDCard,) if issubclass(MDCard, ButtonBehavior) else (ButtonBehavior, MDCard)


class KartuTombol(*_BASE_TOMBOL):
    """Dasar semua tombol bergaya baru (kartu yang bisa diketuk)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("elevation", 0)
        super().__init__(**kwargs)
        self.label = None
        self.ikon_w = None

    def on_disabled(self, instance, value):
        self.opacity = 0.5 if value else 1


def tombol(isi, ikon_nama=None, on_release=None, bg=None, fg=None, tinggi=48,
           radius=14, ukuran_font=14, ukuran_ikon=20, jarak=8, tengah=True, **kw):
    """Tombol dengan ikon + teks. Lebar mengikuti ruang yang tersedia."""
    bg = WARNA_TIPIS if bg is None else bg
    fg = fg or WARNA_UTAMA
    t = KartuTombol(orientation="horizontal", size_hint_y=None, height=dp(tinggi),
                    md_bg_color=bg, radius=[dp(radius)] * 4, spacing=dp(jarak),
                    padding=(dp(8), 0), **kw)
    if tengah:
        t.add_widget(Widget())
    if ikon_nama:
        t.ikon_w = ikon(ikon_nama, fg, ukuran_ikon)
        t.add_widget(t.ikon_w)
    t.label = Label(text=isi, font_name=FONT_UI, bold=True, font_size=sp(ukuran_font),
                    color=fg, size_hint_x=None)
    t.label.bind(texture_size=lambda i, s: setattr(i, "width", s[0]))
    t.add_widget(t.label)
    t.add_widget(Widget())
    if on_release:
        t.bind(on_release=on_release)
    return t


def tombol_aksen(isi, ikon_nama=None, on_release=None, **kw):
    """Tombol utama (CTA) amber, dipakai untuk aksi terpenting di tiap layar."""
    return tombol(isi, ikon_nama, on_release, bg=WARNA_AKSEN, fg=WARNA_TEKS_AKSEN,
                  tinggi=56, radius=18, ukuran_font=16, **kw)


def tombol_dialog(isi, **kw):
    return MDRaisedButton(text=isi, md_bg_color=WARNA_AKSEN, text_color=WARNA_TEKS_AKSEN, **kw)


def kolom(hint, **kwargs):
    """Text field bergaya 'filled' (kotak terisi) ala Material Design."""
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(60))
    campo = MDTextField(hint_text=hint, mode="fill", **kwargs)
    pasang(campo, fill_color_normal=WARNA_KOLOM, fill_color_focus=WARNA_KOLOM_FOKUS,
           line_color_focus=WARNA_UTAMA, hint_text_color_focus=WARNA_UTAMA,
           text_color_focus=WARNA_TEKS)
    return campo


def header(judul, subjudul="", tinggi=128, kanan=None):
    """Header hijau tua dengan sudut bawah membulat."""
    h = MDCard(orientation="horizontal", size_hint_y=None, height=dp(tinggi), elevation=0,
               md_bg_color=WARNA_UTAMA, radius=[0, 0, dp(28), dp(28)],
               padding=(dp(20), dp(36), dp(12), dp(16)), spacing=dp(8))
    kol = MDBoxLayout(orientation="vertical", spacing=dp(4))
    h.judul = teks(judul, "H5", PUTIH, tebal=True)
    kol.add_widget(h.judul)
    h.sub = teks(subjudul, "Body2", WARNA_TEKS_TERANG)
    kol.add_widget(h.sub)
    h.add_widget(kol)
    if kanan is not None:
        h.add_widget(kanan)
    return h


def app_bar_putih(judul, on_back):
    bar = MDTopAppBar(title=judul, elevation=0, md_bg_color=WARNA_KARTU,
                      specific_text_color=WARNA_TEKS)
    bar.left_action_items = [["arrow-left", on_back]]
    return bar


def kabari(isi):
    Snackbar(text=isi, duration=2.2).open()


def salam():
    jam = datetime.now().hour
    if jam < 11:
        return "Selamat pagi"
    if jam < 15:
        return "Selamat siang"
    if jam < 18:
        return "Selamat sore"
    return "Selamat malam"


# ---------------------------------------------------------------- BIODATA
class BiodataScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(md_bg_color=WARNA_LATAR, **kwargs)
        root = MDBoxLayout(orientation="vertical")

        # Bagian atas: hero hijau + kartu form yang menimpa sedikit
        atas = MDBoxLayout(orientation="vertical", spacing=-dp(0))
        adaptif(atas)

        hero = MDCard(orientation="vertical", size_hint_y=None, height=dp(270), elevation=0,
                      md_bg_color=WARNA_UTAMA, radius=[0, 0, dp(32), dp(32)],
                      padding=(dp(28), dp(52), dp(28), dp(24)), spacing=dp(10))
        hero.add_widget(Widget(size_hint_y=None, height=dp(48)))
        hero.add_widget(teks("Selamat datang, Bapak/Ibu Guru", "H5", PUTIH, tebal=True))
        hero.add_widget(teks("Data ini cukup diisi satu kali. Tanpa kata sandi.", "Body2",
                             WARNA_TEKS_TERANG))
        atas.add_widget(hero)

        pembungkus = MDBoxLayout(padding=(dp(20), 0), size_hint_y=None)
        adaptif(pembungkus)
        form = kartu(padding=dp(20), radius=[dp(24)] * 4)
        adaptif(form)

        self.input_nama = kolom("Nama guru")
        self.input_sekolah = kolom("Nama sekolah")
        form.add_widget(self.input_nama)
        form.add_widget(self.input_sekolah)

        info = MDBoxLayout(size_hint_y=None, spacing=dp(8))
        adaptif(info)
        info.add_widget(ikon("lock-outline", WARNA_TEKS2, 16))
        info.add_widget(teks("Identitas anonim dibuat otomatis di perangkat ini.",
                             "Caption", WARNA_TEKS2))
        form.add_widget(info)

        self.status_label = teks("", "Body2", WARNA_ERROR)
        form.add_widget(self.status_label)

        pembungkus.add_widget(form)
        atas.add_widget(pembungkus)
        root.add_widget(atas)
        root.add_widget(Widget())

        cta = MDBoxLayout(padding=(dp(20), dp(12), dp(20), dp(24)), size_hint_y=None,
                          height=dp(92))
        self.btn_simpan = tombol_aksen("Simpan & Mulai", "arrow-right", self.simpan_profil)
        cta.add_widget(self.btn_simpan)
        root.add_widget(cta)

        self.add_widget(root)

    def simpan_profil(self, *args):
        nama = self.input_nama.text.strip()
        sekolah = self.input_sekolah.text.strip()
        if not nama:
            self.status_label.text = "Nama guru wajib diisi."
            return

        self.btn_simpan.disabled = True
        self.status_label.text = "Menyiapkan akun..."
        threading.Thread(target=self._buat_identitas, args=(nama, sekolah),
                         daemon=True).start()

    def _buat_identitas(self, nama, sekolah):
        """Berjalan di thread terpisah supaya layar tidak membeku."""
        app = MDApp.get_running_app()
        try:
            uid = app.firebase.create_anonymous_identity()
        except Exception as e:
            self._identitas_gagal(str(e))
            return
        self._identitas_berhasil(nama, sekolah, uid)

    @mainthread
    def _identitas_gagal(self, pesan):
        self.status_label.text = "Gagal terhubung ke server: " + pesan
        self.btn_simpan.disabled = False

   
    @mainthread
    def _identitas_berhasil(self, nama, sekolah, uid):
        app = MDApp.get_running_app()

        app.profil["nama"] = nama
        app.profil["sekolah"] = sekolah
        app.profil["uid"] = uid
        app.simpan_profil_lokal()
        app.tandai_daftar_kotor()

        self.status_label.text = "Membuka Beranda..."
        self.btn_simpan.disabled = True

        app.goto("beranda")

# ---------------------------------------------------------------- BERANDA
class BerandaKonten(MDBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical",
            md_bg_color=WARNA_LATAR,
            **kwargs
        )

        self.bar = header(
            "Selamat datang",
            "Materi apa yang akan diajarkan hari ini?",
            tinggi=128,
        )
        self.add_widget(self.bar)

        area = FloatLayout()

        body = MDBoxLayout(
            orientation="vertical",
            padding=(dp(20), dp(20), dp(20), 0),
            spacing=dp(10),
        )

        body.add_widget(
            Label(
                text="Materi yang sudah diterbitkan",
                font_size="18sp",
                color=WARNA_UTAMA,
                size_hint_y=None,
                height=dp(28),
            )
        )

        self.status_label = Label(
            text="Daftar materi untuk pengujian",
            font_size="14sp",
            color=WARNA_TEKS2,
            size_hint_y=None,
            height=dp(28),
        )
        body.add_widget(self.status_label)

        scroll = ScrollView()

        self.list_box = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(12),
            padding=(0, 0, 0, dp(20)),
        )
        self.list_box.bind(
            minimum_height=self.list_box.setter("height")
        )

        self.list_box.add_widget(
            Label(
                text="Contoh materi pertama",
                font_size="16sp",
                color=WARNA_UTAMA,
                size_hint_y=None,
                height=dp(50),
            )
        )

        scroll.add_widget(self.list_box)
        body.add_widget(scroll)
       
        area.add_widget(body)
        
        uji_tombol = TombolLabel(
            text="Materi baru",
            font_size="16sp",
            bold=True,
            color=WARNA_TEKS_AKSEN,
            size_hint=(None, None),
            size=(dp(172), dp(56)),
            pos_hint={"right": 0.95, "y": 0.03},
        )
        
        uji_tombol.bind(
            on_release=lambda *a: MDApp.get_running_app().buka_editor_baru()
        )
        
        area.add_widget(uji_tombol)

        self.add_widget(area)


    def perbarui_salam(self):
        pass

    def muat_daftar_materi(self):
        pass

class ProfilKonten(MDBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", md_bg_color=WARNA_LATAR, **kwargs)
        self.add_widget(header("Profil Guru",
                               "Nama dan sekolah ini tampil pada materi yang Anda terbitkan.",
                               tinggi=140))

        body = MDBoxLayout(orientation="vertical", padding=dp(20), spacing=dp(14))

        form = kartu(padding=dp(20))
        adaptif(form)
        self.input_nama = kolom("Nama guru")
        self.input_sekolah = kolom("Nama sekolah")
        form.add_widget(self.input_nama)
        form.add_widget(self.input_sekolah)
        form.add_widget(tombol_aksen("Simpan Perubahan", "check", self.simpan))
        body.add_widget(form)

        self.label_id = teks("", "Caption", WARNA_TEKS2)
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
        kabari("Profil tersimpan")


class MainScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(md_bg_color=WARNA_LATAR, **kwargs)

        nav = MDBottomNavigation()

        # Tab Beranda menggunakan konten asli
        tab_beranda = MDBottomNavigationItem(
            name="tab_beranda",
            text="Beranda",
            icon="home-variant",
        )
      
        self.beranda = BerandaKonten()
        tab_beranda.add_widget(self.beranda)
        nav.add_widget(tab_beranda)

        # Tab Profil tetap sederhana untuk pengujian
        tab_profil = MDBottomNavigationItem(
            name="tab_profil",
            text="Profil",
            icon="account-circle",
        )
        tab_profil.add_widget(
            Label(
                text="Uji Tab Profil",
                font_size="22sp",
                color=WARNA_UTAMA,
            )
        )
        nav.add_widget(tab_profil)

        self.add_widget(nav)

    def on_pre_enter(self, *args):
        # Sengaja tidak memuat data Firebase dahulu
        pass


# ---------------------------------------------------------------- REKAP HASIL
def warna_lencana(persen):
    if persen >= 80:
        return LENCANA_HIJAU
    if persen >= 50:
        return LENCANA_AMBER
    return LENCANA_MERAH


class RekapScreen(MDScreen):
    _permintaan = 0

    def __init__(self, **kwargs):
        super().__init__(md_bg_color=WARNA_LATAR, **kwargs)
        self.materi_id = None
        root = MDBoxLayout(orientation="vertical")

        head = MDCard(orientation="vertical", size_hint_y=None, height=dp(236), elevation=0,
                      md_bg_color=WARNA_UTAMA, radius=[0, 0, dp(28), dp(28)],
                      padding=(dp(12), dp(32), dp(20), dp(16)), spacing=dp(4))

        baris_atas = MDBoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        kembali = MDIconButton(icon="arrow-left", theme_text_color="Custom",
                               text_color=PUTIH, pos_hint={"center_y": 0.5})
        kembali.bind(on_release=lambda *a: MDApp.get_running_app().goto("beranda"))
        baris_atas.add_widget(kembali)
        self.judul_bar = teks("Rekap Hasil", "H6", PUTIH, tebal=True, tinggi=dp(48),
                              shorten=True, shorten_from="right")
        baris_atas.add_widget(self.judul_bar)
        head.add_widget(baris_atas)

        isi = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=(dp(8), 0, 0, 0))
        adaptif(isi)
        self.summary_judul = teks("Memuat hasil...", "Subtitle1", PUTIH, tebal=True)
        self.summary_detail = teks("", "Caption", WARNA_TEKS_TERANG)
        isi.add_widget(self.summary_judul)
        isi.add_widget(self.summary_detail)
        head.add_widget(isi)

        stat_baris = MDBoxLayout(size_hint_y=None, height=dp(58), spacing=dp(8),
                                 padding=(dp(8), 0, 0, 0))
        self.nilai_stat = []
        for nama_stat in ("Rata-rata", "Tertinggi", "Terendah"):
            tile = MDCard(orientation="vertical", elevation=0, md_bg_color=(1, 1, 1, 0.12),
                          radius=[dp(14)] * 4, padding=(dp(12), dp(8)), spacing=0)
            nilai = teks("–", "H6", PUTIH, tebal=True, tinggi=dp(26))
            tile.add_widget(nilai)
            tile.add_widget(teks(nama_stat, "Caption", WARNA_TEKS_TERANG, tinggi=dp(16)))
            self.nilai_stat.append(nilai)
            stat_baris.add_widget(tile)
        head.add_widget(stat_baris)
        root.add_widget(head)

        scroll = ScrollView()
        self.list_box = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8),
                                    padding=(dp(20), dp(16), dp(20), dp(24)))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll.add_widget(self.list_box)
        root.add_widget(scroll)

        self.add_widget(root)

    def _atur_statistik(self, rata="–", tertinggi="–", terendah="–"):
        for lbl, nilai in zip(self.nilai_stat, (rata, tertinggi, terendah)):
            lbl.text = nilai

    def tampilkan(self, materi_id, judul_materi):
        self._permintaan += 1
        token = self._permintaan
        self.materi_id = materi_id
        self.judul_bar.text = "Rekap: " + judul_materi
        self.summary_judul.text = "Memuat hasil..."
        self.summary_detail.text = ""
        self._atur_statistik()
        self.list_box.clear_widgets()
        threading.Thread(target=self._ambil, args=(token, materi_id), daemon=True).start()

    def _ambil(self, token, materi_id):
        """Berjalan di thread terpisah."""
        app = MDApp.get_running_app()
        try:
            daftar = app.firebase.ambil_hasil_kuis(materi_id)
        except Exception as e:
            self._gagal(token, str(e))
            return
        self._selesai(token, daftar)

    @mainthread
    def _gagal(self, token, pesan):
        if token != self._permintaan:
            return
        self.summary_judul.text = "Gagal memuat"
        self.summary_detail.text = pesan

    @mainthread
    def _selesai(self, token, daftar):
        if token != self._permintaan:
            return

        if not daftar:
            self.summary_judul.text = "Belum ada murid yang mengerjakan"
            self.summary_detail.text = ("Rekap akan muncul di sini begitu ada yang "
                                        "selesai mengerjakan.")
            return

        def persen(it):
            total = it.get("totalSoal") or 1
            return (it.get("skor", 0) / total) * 100 if total else 0

        daftar_urut = sorted(daftar, key=persen, reverse=True)
        nilai = [persen(it) for it in daftar_urut]

        self.summary_judul.text = f"{len(daftar_urut)} murid sudah mengerjakan"
        self._atur_statistik(f"{sum(nilai) / len(nilai):.0f}%",
                             f"{max(nilai):.0f}%", f"{min(nilai):.0f}%")

        for item in daftar_urut:
            self.list_box.add_widget(self._baris_hasil(item))

    def _kirim_izin(self, materi_id, kelas, absen, btn):
        """Berjalan di thread terpisah."""
        app = MDApp.get_running_app()
        try:
            app.firebase.izinkan_ulang(materi_id, kelas, absen)
        except Exception as e:
            self._izin_gagal(btn, str(e))
            return
        self._izin_berhasil(btn)

    @mainthread
    def _izin_gagal(self, btn, pesan):
        btn.label.text = "Izinkan ulang"
        btn.disabled = False
        kabari("Gagal: " + pesan)

    @mainthread
    def _izin_berhasil(self, btn):
        hijau = LENCANA_HIJAU[1]
        btn.label.text = "Boleh mengulang"
        btn.label.color = hijau
        btn.ikon_w.icon = "check"
        btn.ikon_w.text_color = hijau
        btn.opacity = 1
        kabari("Murid ini boleh mengerjakan ulang")

    def _baris_hasil(self, item):
        nama = item.get("nama", "-")
        kelas = item.get("kelas", "-")
        absen = item.get("absen", "-")
        skor = item.get("skor", 0)
        total = item.get("totalSoal") or 1
        persen = (skor / total) * 100 if total else 0
        latar_lencana, teks_lencana = warna_lencana(persen)

        card = kartu(orientation="horizontal", size_hint_y=None, height=dp(104),
                     padding=(dp(14), dp(8)), spacing=dp(12), radius=[dp(18)] * 4)

        inisial = "".join(k[0] for k in str(nama).split()[:2]).upper() or "?"
        card.add_widget(avatar(inisial))

        kiri = MDBoxLayout(orientation="vertical", spacing=dp(2))
        kiri.add_widget(teks(f"{nama}", "Subtitle1", tebal=True, tinggi=dp(24),
                             shorten=True, shorten_from="right"))
        kiri.add_widget(teks(f"No. {absen}  •  Kelas {kelas}", "Caption", WARNA_TEKS2,
                             tinggi=dp(18)))

        btn_izin = tombol("Izinkan ulang", "lock-open-outline", None, bg=TRANSPARAN,
                          fg=WARNA_UTAMA, tinggi=40, radius=10, ukuran_font=13,
                          ukuran_ikon=18, jarak=6, tengah=False,
                          size_hint_x=None, width=dp(150))

        def beri_izin(*a, k=kelas, ab=absen, btn=btn_izin, mid=self.materi_id):
            btn.disabled = True
            btn.label.text = "Menyimpan..."
            threading.Thread(target=self._kirim_izin, args=(mid, k, ab, btn),
                             daemon=True).start()

        btn_izin.bind(on_release=beri_izin)
        kiri.add_widget(btn_izin)
        card.add_widget(kiri)

        lencana = MDCard(orientation="vertical", size_hint=(None, None),
                         size=(dp(60), dp(60)), elevation=0, md_bg_color=latar_lencana,
                         radius=[dp(30)] * 4, padding=0, spacing=0,
                         pos_hint={"center_y": 0.5})
        lencana.add_widget(Widget())
        lencana.add_widget(teks(f"{persen:.0f}%", "Subtitle1", teks_lencana, tebal=True,
                                tinggi=dp(20), halign="center"))
        lencana.add_widget(teks(f"{skor}/{total}", "Caption", teks_lencana, tinggi=dp(16),
                                halign="center"))
        lencana.add_widget(Widget())
        card.add_widget(lencana)

        return card


# ---------------------------------------------------------------- widget bantu editor
class BagianLipat(MDCard):
    """Bagian editor yang bisa dibuka-tutup: judul + ringkasan di header, isi di bawahnya."""

    def __init__(self, ikon_nama, judul, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, elevation=0,
                         radius=[dp(18)] * 4, md_bg_color=WARNA_KARTU, padding=0,
                         spacing=0, **kwargs)
        pasang(self, line_color=WARNA_GARIS)
        self.terbuka = False

        self.header = KartuTombol(orientation="horizontal", size_hint_y=None,
                                  height=dp(68), md_bg_color=TRANSPARAN,
                                  radius=[dp(18)] * 4, padding=(dp(14), 0),
                                  spacing=dp(12))
        self.header.add_widget(ikon_tile(ikon_nama, 40))
        kol = MDBoxLayout(orientation="vertical", size_hint_y=None, height=dp(40),
                          pos_hint={"center_y": 0.5})
        kol.add_widget(teks(judul, "Subtitle1", tebal=True, tinggi=dp(22)))
        self.ringkasan = teks("", "Caption", WARNA_TEKS2, tinggi=dp(18))
        kol.add_widget(self.ringkasan)
        self.header.add_widget(kol)
        self.chevron = ikon("chevron-down", WARNA_TEKS2, 24)
        self.header.add_widget(self.chevron)
        self.header.bind(on_release=self.toggle)
        self.add_widget(self.header)

        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None, height=0,
                                padding=(dp(14), 0, dp(14), dp(14)), spacing=dp(10),
                                opacity=0, disabled=True)
        self.body.bind(minimum_height=self._sinkron)
        self.add_widget(self.body)
        self.height = self.header.height

    def tambah(self, widget):
        self.body.add_widget(widget)

    def atur_ringkasan(self, isi):
        self.ringkasan.text = isi

    def toggle(self, *args):
        self.terbuka = not self.terbuka
        self._terapkan()

    def buka(self):
        self.terbuka = True
        self._terapkan()

    def tutup(self):
        self.terbuka = False
        self._terapkan()

    def _terapkan(self):
        self.body.opacity = 1 if self.terbuka else 0
        self.body.disabled = not self.terbuka
        self.chevron.icon = "chevron-up" if self.terbuka else "chevron-down"
        self._sinkron()

    def _sinkron(self, *args):
        tinggi_body = self.body.minimum_height if self.terbuka else 0
        self.body.height = tinggi_body
        self.height = self.header.height + tinggi_body


class SlotBase(MDCard):
    """Kartu isian (Tahap / Soal / Sisi 3D) dengan header bernomor dan tombol hapus."""
    awalan = "Item"

    def __init__(self, nomor, on_hapus=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, padding=dp(12),
                         spacing=dp(8), elevation=0, radius=[dp(14)] * 4,
                         md_bg_color=WARNA_SLOT, **kwargs)
        pasang(self, line_color=WARNA_GARIS)
        self.bind(minimum_height=self.setter("height"))
        self.on_hapus = on_hapus

        header_row = MDBoxLayout(size_hint_y=None, height=dp(30))
        self.label_nomor = teks(f"{self.awalan} {nomor}", "Subtitle2", WARNA_UTAMA,
                                tebal=True, tinggi=dp(30))
        header_row.add_widget(self.label_nomor)
        btn_hapus = MDIconButton(icon="close-circle-outline", theme_text_color="Secondary",
                                 size_hint=(None, None), size=(dp(30), dp(30)))
        btn_hapus.bind(on_release=lambda *a: self.on_hapus(self) if self.on_hapus else None)
        header_row.add_widget(btn_hapus)
        self.add_widget(header_row)

    def atur_nomor(self, nomor):
        self.label_nomor.text = f"{self.awalan} {nomor}"


class TahapSlot(SlotBase):
    awalan = "Tahap"

    def __init__(self, nomor, on_hapus=None, **kwargs):
        super().__init__(nomor, on_hapus, **kwargs)
        self.input_judul = kolom("Judul tahap", height=dp(60))
        self.input_isi = kolom("Penjelasan singkat", multiline=True, height=dp(80))
        self.add_widget(self.input_judul)
        self.add_widget(self.input_isi)

    def ambil_data(self):
        judul = self.input_judul.text.strip()
        isi = self.input_isi.text.strip()
        if not judul:
            return None
        return {"judul": judul, "isi": isi}


class KuisSlot(SlotBase):
    """Soal kuis dengan 3 tipe: pilihan ganda, banyak jawaban benar, dan esai."""
    awalan = "Soal"
    TIPE = (("pilihan", "Pilihan ganda"), ("banyak", "Banyak benar"), ("esai", "Esai"))
    PETUNJUK = {
        "pilihan": "Centang satu jawaban yang benar.",
        "banyak": "Centang semua jawaban yang benar (boleh lebih dari satu).",
    }

    def __init__(self, nomor, on_hapus=None, **kwargs):
        super().__init__(nomor, on_hapus, **kwargs)
        self.tipe = "pilihan"
        self.on_tipe_berubah = None
        self._sibuk = False

        # Pemilih tipe soal (segmented)
        seg = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        self.tombol_tipe = {}
        for kode, nama in self.TIPE:
            b = tombol(nama, None, lambda *a, k=kode: self.atur_tipe(k), tinggi=40,
                       radius=12, ukuran_font=12)
            self.tombol_tipe[kode] = b
            seg.add_widget(b)
        self.add_widget(seg)

        self.input_pertanyaan = kolom("Pertanyaan", multiline=True, height=dp(84))
        self.add_widget(self.input_pertanyaan)

        # Isi yang berganti sesuai tipe
        self.konten = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.konten.bind(minimum_height=self.konten.setter("height"))
        self.add_widget(self.konten)

        # --- area pilihan (pilihan ganda & banyak benar)
        self.area_opsi = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.area_opsi.bind(minimum_height=self.area_opsi.setter("height"))
        self.petunjuk_opsi = teks("", "Caption", WARNA_TEKS2)
        self.area_opsi.add_widget(self.petunjuk_opsi)

        self.input_opsi = []
        self.cek_opsi = []
        for i, label in enumerate(["Opsi A", "Opsi B", "Opsi C", "Opsi D"]):
            baris = MDBoxLayout(size_hint_y=None, height=dp(56), spacing=dp(6))
            cek = MDCheckbox(size_hint=(None, None), size=(dp(40), dp(40)),
                             pos_hint={"center_y": 0.5})
            pasang(cek, selected_color=WARNA_UTAMA, unselected_color=WARNA_TEKS2)
            cek.bind(active=lambda inst, val, idx=i: self._saat_dicentang(idx, val))
            ti = kolom(label, height=dp(56))
            self.cek_opsi.append(cek)
            self.input_opsi.append(ti)
            baris.add_widget(cek)
            baris.add_widget(ti)
            self.area_opsi.add_widget(baris)

        # --- area esai
        self.area_esai = MDBoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.area_esai.bind(minimum_height=self.area_esai.setter("height"))
        self.input_kunci = kolom("Kunci jawaban / pedoman penilaian (opsional)",
                                 multiline=True, height=dp(100))
        self.area_esai.add_widget(self.input_kunci)
        self.area_esai.add_widget(teks("Soal esai tidak dinilai otomatis.", "Caption",
                                       WARNA_TEKS2))

        self.atur_tipe("pilihan")

    def _saat_dicentang(self, idx, val):
        """Pada pilihan ganda, hanya satu opsi yang boleh dicentang."""
        if self._sibuk or self.tipe != "pilihan" or not val:
            return
        self._sibuk = True
        for j, c in enumerate(self.cek_opsi):
            if j != idx and c.active:
                c.active = False
        self._sibuk = False

    def atur_tipe(self, kode):
        self.tipe = kode
        for k, b in self.tombol_tipe.items():
            aktif = (k == kode)
            b.md_bg_color = WARNA_UTAMA if aktif else WARNA_TIPIS
            b.label.color = PUTIH if aktif else WARNA_UTAMA
        self.konten.clear_widgets()
        if kode == "esai":
            self.konten.add_widget(self.area_esai)
        else:
            self.petunjuk_opsi.text = self.PETUNJUK[kode]
            if kode == "pilihan":
                for c in [c for c in self.cek_opsi if c.active][1:]:
                    c.active = False
            self.konten.add_widget(self.area_opsi)
        if self.on_tipe_berubah:
            self.on_tipe_berubah()

    def isi_dari_data(self, data):
        tipe = data.get("tipe", "pilihan")   # soal lama tanpa "tipe" = pilihan ganda
        if tipe not in ("pilihan", "banyak", "esai"):
            tipe = "pilihan"
        self.atur_tipe(tipe)
        self.input_pertanyaan.text = data.get("pertanyaan", "")
        if tipe == "esai":
            self.input_kunci.text = data.get("kunciJawaban", "")
            return
        opsi = data.get("opsi") or ["", "", "", ""]
        for i, ti in enumerate(self.input_opsi):
            ti.text = opsi[i] if i < len(opsi) else ""
        if tipe == "banyak":
            benar = data.get("jawabanBenarBanyak") or []
        else:
            benar = [data.get("jawabanBenar", 0)]
        for i in benar:
            if isinstance(i, int) and 0 <= i < len(self.cek_opsi):
                self.cek_opsi[i].active = True

    def ambil_data(self):
        pertanyaan = self.input_pertanyaan.text.strip()
        if not pertanyaan:
            return None

        if self.tipe == "esai":
            data = {"tipe": "esai", "pertanyaan": pertanyaan}
            kunci = self.input_kunci.text.strip()
            if kunci:
                data["kunciJawaban"] = kunci
            return data

        opsi = [ti.text.strip() for ti in self.input_opsi]
        benar = [i for i, c in enumerate(self.cek_opsi) if c.active]
        if not all(opsi) or not benar:
            return None

        if self.tipe == "pilihan":
            return {"tipe": "pilihan", "pertanyaan": pertanyaan, "opsi": opsi,
                    "jawabanBenar": benar[0]}
        return {"tipe": "banyak", "pertanyaan": pertanyaan, "opsi": opsi,
                "jawabanBenarBanyak": benar}


class Objek3DSlot(SlotBase):
    awalan = "Sisi"

    def __init__(self, nomor, on_hapus=None, **kwargs):
        super().__init__(nomor, on_hapus, **kwargs)
        row = MDBoxLayout(size_hint_y=None, height=dp(60), spacing=dp(8))
        self.input_emoji = kolom("Emoji", size_hint_x=None, width=dp(90), height=dp(60))
        self.input_label = kolom("Label singkat (contoh: Matahari)", height=dp(60))
        row.add_widget(self.input_emoji)
        row.add_widget(self.input_label)
        self.add_widget(row)

        self.input_deskripsi = kolom("Deskripsi singkat", multiline=True, height=dp(80))
        self.add_widget(self.input_deskripsi)

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
        super().__init__(md_bg_color=WARNA_LATAR, **kwargs)
        self.materi_id = None
        self.objek3d_slots = []
        self.tahap_slots = []
        self.kuis_slots = []

        outer = MDBoxLayout(orientation="vertical")
        self.bar = app_bar_putih("Materi Baru", self.konfirmasi_keluar)
        outer.add_widget(self.bar)
        outer.add_widget(MDBoxLayout(size_hint_y=None, height=dp(1), md_bg_color=WARNA_GARIS))

        scroll = ScrollView()
        self.scroll = scroll
        form = MDBoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        adaptif(form)

        self.status_label = teks("", "Body2", WARNA_ERROR)
        form.add_widget(self.status_label)

        # --- Informasi dasar
        dasar = kartu()
        adaptif(dasar)
        dasar.add_widget(teks("Informasi dasar", "Subtitle2", WARNA_UTAMA, tebal=True,
                              tinggi=dp(24)))
        baris = MDBoxLayout(size_hint_y=None, height=dp(60), spacing=dp(10))
        self.input_judul = kolom("Judul materi")
        self.input_kelas = kolom("Kelas", size_hint_x=None, width=dp(108))
        baris.add_widget(self.input_judul)
        baris.add_widget(self.input_kelas)
        dasar.add_widget(baris)
        self.input_materi_teks = kolom("Materi teks", multiline=True, height=dp(164))
        dasar.add_widget(self.input_materi_teks)
        dasar.add_widget(teks("Pisahkan tiap paragraf dengan baris kosong.", "Caption",
                              WARNA_TEKS2))
        form.add_widget(dasar)

        form.add_widget(teks("Bagian materi", "Subtitle2", WARNA_TEKS2, tebal=True,
                             tinggi=dp(24)))

        # --- Objek 3D
        self.sek_3d = BagianLipat("cube-outline", "Objek 3D")
        row3d = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        self.check_3d = MDCheckbox(size_hint=(None, None), size=(dp(32), dp(32)),
                                   pos_hint={"center_y": 0.5})
        pasang(self.check_3d, selected_color=WARNA_UTAMA)
        row3d.add_widget(self.check_3d)
        row3d.add_widget(teks("Sertakan objek 3D untuk materi ini", "Body2", tinggi=dp(44)))
        self.sek_3d.tambah(row3d)
        self.objek3d_container = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                             spacing=dp(10))
        self.objek3d_container.bind(minimum_height=self.objek3d_container.setter("height"))
        self.sek_3d.tambah(self.objek3d_container)
        self.sek_3d.tambah(tombol("Tambah Sisi", "plus", lambda *a: self.tambah_objek3d(),
                                  tinggi=44, radius=12))
        form.add_widget(self.sek_3d)

        # --- Rangkuman / Tahapan
        self.sek_tahap = BagianLipat("format-list-bulleted", "Rangkuman / Tahapan")
        self.tahap_container = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                           spacing=dp(10))
        self.tahap_container.bind(minimum_height=self.tahap_container.setter("height"))
        self.sek_tahap.tambah(self.tahap_container)
        self.sek_tahap.tambah(tombol("Tambah Tahap", "plus", lambda *a: self.tambah_tahap(),
                                     tinggi=44, radius=12))
        form.add_widget(self.sek_tahap)

        # --- Kuis
        self.sek_kuis = BagianLipat("help-circle-outline", "Kuis")
        self.kuis_container = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                          spacing=dp(10))
        self.kuis_container.bind(minimum_height=self.kuis_container.setter("height"))
        self.sek_kuis.tambah(self.kuis_container)
        self.sek_kuis.tambah(tombol("Tambah Soal", "plus", lambda *a: self.tambah_soal(),
                                    tinggi=44, radius=12))
        form.add_widget(self.sek_kuis)

        self.check_3d.bind(active=self._perbarui_ringkasan)

        # --- Tautan murid
        link_card = kartu()
        adaptif(link_card)
        link_card.add_widget(teks("Tautan untuk murid", "Subtitle2", WARNA_UTAMA,
                                  tebal=True, tinggi=dp(24)))
        self.link_label = kolom("Tautan muncul setelah diterbitkan", readonly=True)
        link_card.add_widget(self.link_label)

        def salin_link(*a):
            if not self.link_label.text:
                kabari("Tautan belum tersedia. Terbitkan materi terlebih dahulu.")
                return
            Clipboard.copy(self.link_label.text)
            kabari("Link disalin")

        link_card.add_widget(tombol("Salin Link Murid", "link-variant", salin_link,
                                    tinggi=48))
        form.add_widget(link_card)

        scroll.add_widget(form)
        outer.add_widget(scroll)

        # --- Bilah bawah: tombol Terbitkan selalu terlihat
        bawah = MDCard(orientation="vertical", size_hint_y=None, height=dp(84), elevation=0,
                       md_bg_color=WARNA_KARTU, radius=[0, 0, 0, 0],
                       padding=(dp(20), dp(12), dp(20), dp(16)))
        pasang(bawah, line_color=WARNA_GARIS)
        self.btn_terbitkan = tombol_aksen("Terbitkan", "send", self.terbitkan)
        bawah.add_widget(self.btn_terbitkan)
        outer.add_widget(bawah)

        self.add_widget(outer)

    # ---------- ringkasan di header tiap bagian ----------
    def _perbarui_ringkasan(self, *args):
        status = "Aktif" if self.check_3d.active else "Nonaktif"
        self.sek_3d.atur_ringkasan(f"{status} · {len(self.objek3d_slots)} sisi")
        self.sek_tahap.atur_ringkasan(f"{len(self.tahap_slots)} tahap")
        ringkas = f"{len(self.kuis_slots)} soal"
        n_esai = sum(1 for q in self.kuis_slots if q.tipe == "esai")
        n_banyak = sum(1 for q in self.kuis_slots if q.tipe == "banyak")
        if n_banyak:
            ringkas += f" · {n_banyak} banyak benar"
        if n_esai:
            ringkas += f" · {n_esai} esai"
        self.sek_kuis.atur_ringkasan(ringkas)

    # ---------- tambah/hapus slot objek 3D ----------
    def tambah_objek3d(self, data=None):
        slot = Objek3DSlot(len(self.objek3d_slots) + 1, on_hapus=self.hapus_objek3d)
        if data:
            slot.input_emoji.text = data.get("emoji", "")
            slot.input_label.text = data.get("label", "")
            slot.input_deskripsi.text = data.get("deskripsi", "")
        self.objek3d_slots.append(slot)
        self.objek3d_container.add_widget(slot)
        self._perbarui_ringkasan()

    def hapus_objek3d(self, slot):
        if slot in self.objek3d_slots:
            self.objek3d_slots.remove(slot)
            self.objek3d_container.remove_widget(slot)
            for i, s in enumerate(self.objek3d_slots, start=1):
                s.atur_nomor(i)
            self._perbarui_ringkasan()

    # ---------- tambah/hapus slot tahap ----------
    def tambah_tahap(self, data=None):
        slot = TahapSlot(len(self.tahap_slots) + 1, on_hapus=self.hapus_tahap)
        if data:
            slot.input_judul.text = data.get("judul", "")
            slot.input_isi.text = data.get("isi", "")
        self.tahap_slots.append(slot)
        self.tahap_container.add_widget(slot)
        self._perbarui_ringkasan()

    def hapus_tahap(self, slot):
        if slot in self.tahap_slots:
            self.tahap_slots.remove(slot)
            self.tahap_container.remove_widget(slot)
            for i, s in enumerate(self.tahap_slots, start=1):
                s.atur_nomor(i)
            self._perbarui_ringkasan()

    # ---------- tambah/hapus slot soal kuis ----------
    def tambah_soal(self, data=None):
        slot = KuisSlot(len(self.kuis_slots) + 1, on_hapus=self.hapus_soal)
        if data:
            slot.isi_dari_data(data)
        slot.on_tipe_berubah = self._perbarui_ringkasan
        self.kuis_slots.append(slot)
        self.kuis_container.add_widget(slot)
        self._perbarui_ringkasan()

    def hapus_soal(self, slot):
        if slot in self.kuis_slots:
            self.kuis_slots.remove(slot)
            self.kuis_container.remove_widget(slot)
            for i, s in enumerate(self.kuis_slots, start=1):
                s.atur_nomor(i)
            self._perbarui_ringkasan()

    def konfirmasi_keluar(self, *args):
        if not hasattr(self, "_dialog_keluar"):
            self._dialog_keluar = MDDialog(
                title="Keluar dari halaman ini?",
                text="Pastikan sudah menekan Terbitkan kalau ada perubahan yang ingin disimpan.",
                buttons=[
                    MDFlatButton(text="Batal", on_release=lambda *a: self._dialog_keluar.dismiss()),
                    tombol_dialog("Ya, Keluar", on_release=lambda *a: self._keluar_sekarang()),
                ],
            )
            pasang(self._dialog_keluar, radius=[dp(20)] * 4)
        self._dialog_keluar.open()

    def _keluar_sekarang(self):
        self._dialog_keluar.dismiss()
        MDApp.get_running_app().goto("beranda")

    def _tutup_semua_bagian(self):
        for sek in (self.sek_3d, self.sek_tahap, self.sek_kuis):
            sek.tutup()

    def siapkan_materi_baru(self):
        app = MDApp.get_running_app()
        self.materi_id = app.firebase.buat_id_materi_baru()
        self.bar.title = "Materi Baru"
        self.input_judul.text = ""
        self.input_kelas.text = ""
        self.input_materi_teks.text = ""
        self.check_3d.active = False
        self._tutup_semua_bagian()

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
        self.scroll.scroll_y = 1

    def muat_untuk_edit(self, item):
        self.materi_id = item.get("_id")
        self.bar.title = "Edit Materi"
        self.input_judul.text = item.get("judul", "")
        self.input_kelas.text = item.get("kelas", "")
        self.input_materi_teks.text = "\n\n".join(item.get("materiTeks") or [])
        self.check_3d.active = bool(item.get("punya3d"))
        self._tutup_semua_bagian()

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
        self.scroll.scroll_y = 1

    def terbitkan(self, *args):
        judul = self.input_judul.text.strip()
        kelas = self.input_kelas.text.strip()
        paragraf = [p.strip() for p in self.input_materi_teks.text.split("\n\n") if p.strip()]
        objek3d = [d for d in (s.ambil_data() for s in self.objek3d_slots) if d]
        rangkuman = [d for d in (s.ambil_data() for s in self.tahap_slots) if d]
        kuis = [d for d in (s.ambil_data() for s in self.kuis_slots) if d]

        if not judul:
            self.status_label.text = "Judul materi wajib diisi."
            kabari("Judul materi wajib diisi.")
            self.scroll.scroll_y = 1
            return
        if not paragraf:
            self.status_label.text = "Materi teks wajib diisi."
            kabari("Materi teks wajib diisi.")
            self.scroll.scroll_y = 1
            return
        if not kuis:
            self.status_label.text = "Isi minimal 1 soal kuis yang lengkap (pertanyaan, 4 opsi, dan jawaban benar; atau soal esai)."
            kabari("Isi minimal 1 soal kuis yang lengkap (pertanyaan, 4 opsi, dan jawaban benar; atau soal esai).")
            self.sek_kuis.buka()
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
        threading.Thread(target=self._kirim_terbitan, args=(self.materi_id, data),
                         daemon=True).start()

    def _kirim_terbitan(self, materi_id, data):
        """Berjalan di thread terpisah."""
        app = MDApp.get_running_app()
        try:
            app.firebase.terbitkan_materi(materi_id, data)
        except Exception as e:
            self._terbit_gagal(str(e))
            return
        self._terbit_berhasil(materi_id)

    @mainthread
    def _terbit_gagal(self, pesan):
        self.status_label.text = "Gagal menerbitkan: " + pesan
        kabari("Gagal menerbitkan: " + pesan)
        self.btn_terbitkan.disabled = False

    @mainthread
    def _terbit_berhasil(self, materi_id):
        MDApp.get_running_app().tandai_daftar_kotor()
        self.btn_terbitkan.disabled = False
        if materi_id != self.materi_id:   # pengguna sudah pindah ke materi lain
            kabari("Materi berhasil diterbitkan!")
            return
        self.status_label.text = ""
        self.link_label.text = STUDENT_APP_BASE_URL + "?id=" + materi_id
        self.scroll.scroll_y = 0   # tampilkan kartu tautan murid
        kabari("Materi berhasil diterbitkan!")


# ---------------------------------------------------------------- APP
class AplikasiGuruApp(MDApp):
    def _atur_font(self):
        global FONT_UI
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
        reguler = os.path.join(folder, "PlusJakartaSans-Regular.ttf")
        tebal = os.path.join(folder, "PlusJakartaSans-Bold.ttf")
        if not (os.path.exists(reguler) and os.path.exists(tebal)):
            return
        try:
            LabelBase.register(name="PJS", fn_regular=reguler, fn_bold=tebal)
            for gaya, nilai in self.theme_cls.font_styles.items():
                if gaya != "Icon":
                    nilai[0] = "PJS"
            FONT_UI = "PJS"
        except Exception:
            pass

    def build(self):
        self.title = "Aplikasi Guru"
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Light"
        self._atur_font()

        Window.clearcolor = WARNA_LATAR
        if platform in ("android", "ios"):
            try:
                Window.softinput_mode = "below_target"   # keyboard tidak menutupi kolom
            except Exception:
                pass
        else:
            Window.size = (390, 844)                      # proporsi ponsel saat uji di PC
        Window.bind(on_keyboard=self._tombol_kembali)

        self.profil_path = os.path.join(self.user_data_dir, "profil_guru.json")
        self.token_path = os.path.join(self.user_data_dir, "auth_tokens.json")

        self.cache_path = os.path.join(self.user_data_dir, "cache_materi.json")

        self.firebase = FirebaseClient(self.token_path)
        self.profil = self._muat_profil_lokal()
        self.cache_materi = self._baca_cache_materi()
        self.daftar_perlu_muat = True
        self._editor_dijadwalkan = False

        # Hanya layar pertama yang dibangun sekarang; sisanya dibangun saat dibutuhkan.
        self.sm = ScreenManager(transition=SlideTransition(direction="left", duration=0.22))
        sudah_masuk = self.firebase.has_identity() and self.profil.get("nama")
        awal = "beranda" if sudah_masuk else "biodata"
        self.layar(awal)
        self.sm.current = awal
        if awal == "beranda":
             pass  # Pengujian: jangan bangun Editor otomatis

        return self.sm

    def layar(self, nama):
        """Ambil layar; kalau belum dibangun, bangun dulu."""
        if not self.sm.has_screen(nama):
            pembuat = {"biodata": BiodataScreen, "beranda": MainScreen,
                       "editor": EditorScreen, "rekap": RekapScreen}[nama]
            self.sm.add_widget(pembuat(name=nama))
        return self.sm.get_screen(nama)

    def _jadwalkan_editor(self):
        """Bangun Editor (layar terberat) sesaat setelah Beranda tampil, bukan saat startup."""
        if self._editor_dijadwalkan or self.sm.has_screen("editor"):
            return
        self._editor_dijadwalkan = True
        Clock.schedule_once(lambda dt: self.layar("editor"), 0.8)

    def _tombol_kembali(self, window, key, *args):
        """Tombol kembali Android (kode 27 / Escape)."""
        if key != 27:
            return False
        saat_ini = self.sm.current
        if saat_ini == "editor":
            self.sm.get_screen("editor").konfirmasi_keluar()
            return True
        if saat_ini == "rekap":
            self.goto("beranda")
            return True
        return False   # di Beranda / Biodata: biarkan aplikasi menutup

    def _muat_profil_lokal(self):
        try:
            with open(self.profil_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def simpan_profil_lokal(self):
        with open(self.profil_path, "w", encoding="utf-8") as f:
            json.dump(self.profil, f)

    # ---------- cache daftar materi ----------
    def _baca_cache_materi(self):
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                isi = json.load(f)
        except (OSError, ValueError):
            return None
        uid = self.profil.get("uid")
        if uid and isi.get("uid") == uid and isinstance(isi.get("daftar"), list):
            return isi["daftar"]
        return None

    def simpan_cache_materi(self, daftar):
        """Dipanggil dari thread latar; menulis ke memori dan ke berkas."""
        self.cache_materi = daftar
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump({"uid": self.profil.get("uid"), "daftar": daftar}, f, default=str)
        except (OSError, TypeError):
            pass

    def tandai_daftar_kotor(self):
        """Daftar materi perlu diambil ulang (mis. setelah Terbitkan)."""
        self.daftar_perlu_muat = True

    # ---------- navigasi ----------
    def goto(self, nama_screen):
        self.layar(nama_screen)
        urutan = ["biodata", "beranda", "editor", "rekap"]
        try:
            arah = "left" if urutan.index(nama_screen) >= urutan.index(self.sm.current) else "right"
            self.sm.transition.direction = arah
        except ValueError:
            pass
        self.sm.current = nama_screen
        if nama_screen == "beranda":
            self._jadwalkan_editor()

    def buka_editor_baru(self):
        editor = self.layar("editor")
        editor.siapkan_materi_baru()
        self.goto("editor")

    def buka_editor_edit(self, item):
        editor = self.layar("editor")
        editor.muat_untuk_edit(item)
        self.goto("editor")

    def buka_hasil(self, materi_id, judul_materi):
        rekap = self.layar("rekap")
        rekap.tampilkan(materi_id, judul_materi)
        self.goto("rekap")


if __name__ == "__main__":
    AplikasiGuruApp().run()
