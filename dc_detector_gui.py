#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox

KEYWORDS = ["papa","emojiAngry","F5 POLICE","halo"]
WINDOW_SECONDS = 30
COOLDOWN_SECONDS = 30

def load_messages(path):
    data=json.load(open(path,"r",encoding="utf-8"))
    msgs=[]
    for c in data.get("comments",[]):
        try:t=float(c.get("content_offset_seconds",0))
        except:continue
        body=str(c.get("message",{}).get("body",""))
        msgs.append({"time":t,"text":body})
    return sorted(msgs,key=lambda x:x["time"])

def hms(sec):
    sec=int(sec);h=sec//3600;m=(sec%3600)//60;s=sec%60
    return f"{h}:{m:02d}:{s:02d}"

def analyze(messages):
    marks=[]
    for m in messages:
        txt=m["text"].lower()
        marks.append(sum(1 for k in KEYWORDS if k.lower() in txt))
    half=WINDOW_SECONDS/2
    peaks=[]
    for i,m in enumerate(messages):
        score=0
        for j,o in enumerate(messages):
            if abs(o["time"]-m["time"])<=half:
                score+=marks[j]
        if score>0: peaks.append((m["time"],score))
    peaks.sort(key=lambda x:x[1],reverse=True)
    out=[];used=[]
    for t,s in peaks:
        if all(abs(t-u)>=COOLDOWN_SECONDS for u in used):
            out.append((t,s));used.append(t)
    return sorted(out)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DC Detector"); self.geometry("900x700")
        self.path=tk.StringVar()
        f=tk.Frame(self); f.pack(fill="x",padx=10,pady=10)
        tk.Entry(f,textvariable=self.path).pack(side="left",fill="x",expand=True)
        tk.Button(f,text="Wybierz JSON",command=self.pick).pack(side="left")
        tk.Button(f,text="Analizuj",command=self.run).pack(side="left")
        self.log=scrolledtext.ScrolledText(self); self.log.pack(fill="both",expand=True,padx=10,pady=10)
    def pick(self):
        p=filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if p:self.path.set(p)
    def run(self):
        try:
            res=analyze(load_messages(self.path.get()))
            self.log.delete("1.0","end")
            self.log.insert("end","===== TOP POTENCJALNE DC =====\n\n")
            for i,(t,s) in enumerate(sorted(res,key=lambda x:x[1],reverse=True)[:50],1):
                self.log.insert("end",f"{i:02d}. {hms(t)} | score={s}\n")
            self.log.insert("end","\n===== CHRONOLOGICZNIE =====\n\n")
            for t,s in res:
                self.log.insert("end",f"{hms(t)} | score={s}\n")
        except Exception as e:
            messagebox.showerror("Błąd",str(e))
if __name__=='__main__':
    App().mainloop()
