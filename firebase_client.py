"""
firebase_client.py

Koneksi ke Firebase (Authentication Anonymous + Firestore) lewat REST API,
persis seperti cara kerja versi web yang sudah kita uji coba sebelumnya.

Sengaja TIDAK memakai Firebase Admin SDK, karena Admin SDK butuh kunci
service-account rahasia yang kalau ikut dibagikan di aplikasi yang
diinstal banyak guru, siapa pun bisa membongkarnya dari file APK dan
mendapat akses penuh ke seluruh database (melewati Security Rules).
REST API + ID token anonim ini justru tunduk pada Security Rules yang
sudah kita pasang di Firestore, sama seperti murid mengakses lewat web.
"""

import json
import time
import uuid
import requests

FIREBASE_API_KEY = "AIzaSyDV1R9B30WieRoy7wg5PpAbPaTjwF8B268"
PROJECT_ID = "aplikasi-pembelajara"

AUTH_SIGNUP_URL = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
AUTH_REFRESH_URL = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
FIRESTORE_BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"


class FirebaseClient:
    def __init__(self, token_store_path):
        self.token_store_path = token_store_path
        self.id_token = None
        self.refresh_token = None
        self.uid = None
        self.token_expiry = 0
        self._load_tokens()

    # ---------------- identitas guru (anonim, tanpa layar login) ----------------
    def _load_tokens(self):
        try:
            with open(self.token_store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.id_token = data.get("id_token")
            self.refresh_token = data.get("refresh_token")
            self.uid = data.get("uid")
            self.token_expiry = data.get("token_expiry", 0)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_tokens(self):
        with open(self.token_store_path, "w", encoding="utf-8") as f:
            json.dump({
                "id_token": self.id_token,
                "refresh_token": self.refresh_token,
                "uid": self.uid,
                "token_expiry": self.token_expiry,
            }, f)

    def has_identity(self):
        return bool(self.uid and self.refresh_token)

    def create_anonymous_identity(self):
        """Dipanggil SEKALI saat guru pertama kali mengisi form biodata."""
        resp = requests.post(AUTH_SIGNUP_URL, json={"returnSecureToken": True}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        self.id_token = data["idToken"]
        self.refresh_token = data["refreshToken"]
        self.uid = data["localId"]
        self.token_expiry = time.time() + int(data.get("expiresIn", 3600)) - 60
        self._save_tokens()
        return self.uid

    def _ensure_fresh_token(self):
        if not self.refresh_token:
            raise RuntimeError("Belum ada identitas. Isi form biodata dulu.")
        if time.time() < self.token_expiry:
            return
        resp = requests.post(AUTH_REFRESH_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        self.id_token = data["id_token"]
        self.refresh_token = data["refresh_token"]
        self.token_expiry = time.time() + int(data.get("expires_in", 3600)) - 60
        self._save_tokens()

    # ---------------- konversi format dokumen Firestore REST ----------------
    def _to_firestore_value(self, value):
        if isinstance(value, bool):
            return {"booleanValue": value}
        if isinstance(value, int):
            return {"integerValue": str(value)}
        if isinstance(value, float):
            return {"doubleValue": value}
        if isinstance(value, str):
            return {"stringValue": value}
        if isinstance(value, list):
            return {"arrayValue": {"values": [self._to_firestore_value(v) for v in value]}}
        if isinstance(value, dict):
            return {"mapValue": {"fields": {k: self._to_firestore_value(v) for k, v in value.items()}}}
        if value is None:
            return {"nullValue": None}
        raise TypeError(f"Tipe data tidak didukung: {type(value)}")

    def _from_firestore_value(self, value):
        if "stringValue" in value:
            return value["stringValue"]
        if "integerValue" in value:
            return int(value["integerValue"])
        if "doubleValue" in value:
            return value["doubleValue"]
        if "booleanValue" in value:
            return value["booleanValue"]
        if "arrayValue" in value:
            return [self._from_firestore_value(v) for v in value["arrayValue"].get("values", [])]
        if "mapValue" in value:
            return {k: self._from_firestore_value(v) for k, v in value["mapValue"].get("fields", {}).items()}
        if "nullValue" in value:
            return None
        return None

    def _doc_to_dict(self, doc_json):
        fields = doc_json.get("fields", {})
        return {k: self._from_firestore_value(v) for k, v in fields.items()}

    # ---------------- operasi materi & hasil kuis ----------------
    def buat_id_materi_baru(self):
        return uuid.uuid4().hex[:12]

    def terbitkan_materi(self, materi_id, data: dict):
        """Menulis/menimpa dokumen materi/{materi_id}. guruId ditambahkan otomatis."""
        self._ensure_fresh_token()
        data = dict(data)
        data["guruId"] = self.uid
        body = {"fields": {k: self._to_firestore_value(v) for k, v in data.items()}}
        url = f"{FIRESTORE_BASE}/materi/{materi_id}"
        headers = {"Authorization": f"Bearer {self.id_token}"}
        resp = requests.patch(url, json=body, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def ambil_materi_milik_saya(self):
        """Semua materi yang guruId-nya cocok dengan identitas guru ini."""
        self._ensure_fresh_token()
        body = {
            "structuredQuery": {
                "from": [{"collectionId": "materi"}],
                "where": {
                    "fieldFilter": {
                        "field": {"fieldPath": "guruId"},
                        "op": "EQUAL",
                        "value": {"stringValue": self.uid},
                    }
                },
            }
        }
        url = f"{FIRESTORE_BASE}:runQuery"
        headers = {"Authorization": f"Bearer {self.id_token}"}
        resp = requests.post(url, json=body, headers=headers, timeout=20)
        resp.raise_for_status()
        hasil = []
        for item in resp.json():
            doc = item.get("document")
            if not doc:
                continue
            materi_id = doc["name"].split("/")[-1]
            data = self._doc_to_dict(doc)
            data["_id"] = materi_id
            hasil.append(data)
        return hasil

    def ambil_hasil_kuis(self, materi_id):
        self._ensure_fresh_token()
        body = {
            "structuredQuery": {
                "from": [{"collectionId": "hasil_kuis"}],
                "where": {
                    "fieldFilter": {
                        "field": {"fieldPath": "materiId"},
                        "op": "EQUAL",
                        "value": {"stringValue": materi_id},
                    }
                },
            }
        }
        url = f"{FIRESTORE_BASE}:runQuery"
        headers = {"Authorization": f"Bearer {self.id_token}"}
        resp = requests.post(url, json=body, headers=headers, timeout=20)
        resp.raise_for_status()
        hasil = []
        for item in resp.json():
            doc = item.get("document")
            if not doc:
                continue
            data = self._doc_to_dict(doc)
            data["_id"] = doc["name"].split("/")[-1]
            hasil.append(data)
        return hasil

    def izinkan_ulang(self, materi_id, kelas, absen):
        """Membuka kunci kuis murid (kelas+absen tertentu) supaya bisa mengerjakan lagi."""
        self._ensure_fresh_token()
        status_id = self._status_id(materi_id, kelas, absen)
        body = {"fields": {
            "materiId": {"stringValue": materi_id},
            "kelas": {"stringValue": kelas},
            "absen": {"stringValue": absen},
            "bolehUlangLagi": {"booleanValue": True},
        }}
        url = f"{FIRESTORE_BASE}/status_pengerjaan/{status_id}"
        headers = {"Authorization": f"Bearer {self.id_token}"}
        params = [
            ("updateMask.fieldPaths", "materiId"),
            ("updateMask.fieldPaths", "kelas"),
            ("updateMask.fieldPaths", "absen"),
            ("updateMask.fieldPaths", "bolehUlangLagi"),
        ]
        resp = requests.patch(url, params=params, json=body, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _status_id(materi_id, kelas, absen):
        def bersihkan(s):
            return "".join(ch if ch.isalnum() else "_" for ch in str(s).strip())
        return f"{materi_id}_{bersihkan(kelas)}_{bersihkan(absen)}"
