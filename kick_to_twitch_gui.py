#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import uuid
import re
from datetime import datetime, timezone
import tkinter as tk
from tkinter import filedialog, messagebox

# Kick emote format: [emote:12345:NAME]
EMOTE_RE = re.compile(r"\[emote:(\d+):([^\]]+)\]")

# Streamer "na sztywno" — pod 7TV/BTTV/FFZ w TwitchDownloader
FORCED_STREAMER = {
    "name": "xntentacion",
    "login": "xntentacion",
    "id": 461774409  # int32
}

# Template możliwie zbliżony do TwitchDownloader Chat.json
BUILTIN_TEMPLATE = {
    "FileInfo": {
        "Version": {"Major": 1, "Minor": 4, "Patch": 0},
        "CreatedAt": "",
        "UpdatedAt": "0001-01-01T00:00:00"
    },
    "streamer": {
        "name": "",
        "login": "",
        "id": 0
    },
    "clipper": None,
    "video": {
        "title": "Kick chat (converted)",
        "description": None,
        "id": "",
        "created_at": "",
        "start": 0,
        "end": 0,
        "length": 0,
        "viewCount": 0,
        "game": "",
        "chapters": []
    },
    "comments": [],
    "embeddedData": None
}


def iso_now_local():
    return datetime.now().astimezone().isoformat()


def parse_iso_z(ts):
    """
    Kick: "2026-02-02T11:58:37Z"
    """
    if not ts or not isinstance(ts, str):
        raise ValueError("Brak poprawnego timestampu")
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def digits_only_video_id(base_time: datetime) -> str:
    """
    video.id jako string z cyframi (jak Twitch) — epoch seconds
    """
    return str(int(base_time.timestamp()))


def build_body_and_fragments(content: str):
    """
    FIX #1 + #2:
    - Kickowe [emote:id:NAME] zamieniamy na czysty tekst " NAME " (z odstępami!)
    - Nie ustawiamy fragment.emoticon ani message.emoticons, bo TwitchDownloader
      wykrywa BTTV/FFZ/7TV po tokenach w message.body.
    """
    if content is None:
        content = ""

    # każdy emote -> " NAME " (spacje są krytyczne dla tokenizacji)
    def repl(m):
        name = m.group(2)
        return f" {name} "

    body = EMOTE_RE.sub(repl, content)

    # normalizacja whitespace: wiele spacji / nowe linie -> pojedyncza spacja
    body = re.sub(r"\s+", " ", body).strip()

    fragments = [{"text": body, "emoticon": None}]
    emoticons = []  # celowo puste

    return body, fragments, emoticons


def load_kick_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Plik Kick JSON musi być listą wiadomości (array).")

    return data


def convert_kick_to_twitch(kick_messages, base_time: datetime):
    # deep copy
    tpl = json.loads(json.dumps(BUILTIN_TEMPLATE))

    # FileInfo
    tpl["FileInfo"]["CreatedAt"] = iso_now_local()

    # streamer — na sztywno (dla emote providers)
    tpl["streamer"]["name"] = FORCED_STREAMER["name"]
    tpl["streamer"]["login"] = FORCED_STREAMER["login"]
    tpl["streamer"]["id"] = int(FORCED_STREAMER["id"])
    streamer_id = int(FORCED_STREAMER["id"])

    # video meta
    vid = digits_only_video_id(base_time)
    tpl["video"]["id"] = vid
    tpl["video"]["created_at"] = base_time.isoformat().replace("+00:00", "Z")
    tpl["video"]["game"] = "Just Chatting"

    comments = []

    for msg in kick_messages:
        # Kick czasem ma null/śmieci w tablicy -> pomijamy
        if not isinstance(msg, dict):
            continue

        # createdAt może nie istnieć
        try:
            created = parse_iso_z(msg.get("createdAt"))
        except Exception:
            created = base_time

        offset = (created - base_time).total_seconds()
        if offset < 0:
            offset = 0.0

        content = msg.get("content", "")
        body, fragments, _ = build_body_and_fragments(content)

        username = msg.get("username") or f"user_{msg.get('userId', '0')}"
        user_id = str(msg.get("userId", ""))

        comment = {
            "_id": str(uuid.uuid4()),
            "created_at": created.isoformat().replace("+00:00", "Z"),
            "channel_id": str(streamer_id),
            "content_type": "video",
            "content_id": vid,
            "content_offset_seconds": int(round(offset)),
            "commenter": {
                "display_name": username,
                "_id": user_id,
                "name": (username or "").lower(),
                "bio": None,
                # wymagane przez generator (DateTime, nie null)
                "created_at": base_time.isoformat().replace("+00:00", "Z"),
                "updated_at": base_time.isoformat().replace("+00:00", "Z"),
                "logo": None
            },
            "message": {
                "body": body,
                "bits_spent": 0,
                "fragments": fragments,
                "user_badges": [],
                "user_color": None,
                # FIX: zawsze puste, żeby nie udawać twitchowych emote po ID
                "emoticons": []
            }
        }

        comments.append(comment)

    comments.sort(key=lambda c: c["created_at"])
    tpl["comments"] = comments

    # video length/start/end
    tpl["video"]["start"] = 0
    if comments:
        last = int(comments[-1]["content_offset_seconds"])
        tpl["video"]["end"] = last
        tpl["video"]["length"] = last
    else:
        tpl["video"]["end"] = 0
        tpl["video"]["length"] = 0

    return tpl


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kick → Twitch Chat.json (GUI)")
        self.geometry("720x260")
        self.resizable(False, False)

        self.kick_path = tk.StringVar(value="")
        self.start_time = tk.StringVar(value="")  # ISO, np. 2026-02-02T11:58:00Z

        pad = {"padx": 10, "pady": 6}

        tk.Label(self, text="Plik Kick (.json):").grid(row=0, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.kick_path, width=72).grid(row=0, column=1, sticky="w", **pad)
        tk.Button(self, text="Wybierz…", command=self.pick_kick).grid(row=0, column=2, **pad)

        tk.Label(self, text="Start streama ISO (opcjonalnie):").grid(row=1, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.start_time, width=72).grid(row=1, column=1, sticky="w", **pad)
        tk.Label(self, text="np. 2026-02-02T11:58:00Z (jak puste: bierze pierwszą poprawną wiadomość)").grid(
            row=2, column=1, sticky="w", padx=10
        )

        tk.Button(self, text="Konwertuj i zapisz…", command=self.convert_and_save, height=2)\
            .grid(row=3, column=1, sticky="w", padx=10, pady=14)

        tk.Label(self, text="Streamer ustawiony na sztywno: xntentacion (emote providers).").grid(
            row=4, column=0, columnspan=3, sticky="w", padx=10
        )

    def pick_kick(self):
        path = filedialog.askopenfilename(
            title="Wybierz plik Kick JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.kick_path.set(path)

    def convert_and_save(self):
        kick_path = self.kick_path.get().strip()
        if not kick_path:
            messagebox.showerror("Błąd", "Wybierz plik Kick JSON.")
            return

        try:
            kick_messages = load_kick_file(kick_path)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie mogę wczytać pliku Kick:\n{e}")
            return

        # base time – odporny fallback
        try:
            start_txt = self.start_time.get().strip()
            if start_txt:
                base_time = parse_iso_z(start_txt)
            else:
                valid_times = []
                for m in kick_messages:
                    if not isinstance(m, dict):
                        continue
                    try:
                        valid_times.append(parse_iso_z(m.get("createdAt")))
                    except Exception:
                        pass

                if valid_times:
                    base_time = min(valid_times)
                else:
                    base_time = datetime(1970, 1, 1, tzinfo=timezone.utc)
        except Exception as e:
            messagebox.showerror("Błąd", f"Zły format czasu startu:\n{e}")
            return

        try:
            out_data = convert_kick_to_twitch(kick_messages, base_time)
        except Exception as e:
            messagebox.showerror("Błąd", f"Konwersja nieudana:\n{e}")
            return

        save_path = filedialog.asksaveasfilename(
            title="Zapisz jako…",
            defaultextension=".json",
            initialfile="Chat.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(out_data, f, ensure_ascii=False)
            messagebox.showinfo("OK", f"Zapisano!\nWiadomości: {len(out_data['comments'])}\nPlik: {save_path}")
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie mogę zapisać pliku:\n{e}")


if __name__ == "__main__":
    App().mainloop()