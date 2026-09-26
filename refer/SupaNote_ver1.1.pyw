# -*- coding: utf-8 -*-
# 파일명: SupaNote_ver1.1.py
import json
import shutil
import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter import ttk
from pathlib import Path




# 나중에 Supabase 연동 시 파일 입출력 대신 API 호출로 변경될 부분입니다.

# 파일이 위치한 폴더의 절대 경로를 먼저 찾습니다.
BASE_DIR = Path(__file__).resolve().parent

# 무조건 스크립트와 동일한 폴더에 저장되도록 경로를 묶어줍니다.
DATA_FILE = BASE_DIR / "supanotes.json"
BACKUP_FILE = BASE_DIR / "supanotes.json.bak"



DEFAULT_FONT_FAMILY = "Malgun Gothic"
DEFAULT_FONT_SIZE = 10
WINDOW_W, WINDOW_H = 650, 500

class SupaNoteApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("가라실험실 : SupaNotes_Ver1.1")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.minsize(520, 420)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- 하이라이트 팔레트 (9색 유지) ---
        self.bg_palette = [
            "#FC8DE4", "#F6B6C8", "#FFE291", "#C9F0AA", "#BDEEDC", 
            "#B8C8FF", "#AAAAAA", "#D5D5D5", "#000000"
        ]
        self.bg_tags = [f"bg{i}" for i in range(len(self.bg_palette))]

        # --- DB 구조 상태 (Supabase 마이그레이션 대비) ---
        self.folders = []
        self.notes = []
        self.current_note_id = None
        self.tree_iid_to_folder_id = {}
        self.tree_iid_to_note_id = {}

        # 폰트 설정
        self.font_family = DEFAULT_FONT_FAMILY
        self.font_size = DEFAULT_FONT_SIZE
        self.text_font = (self.font_family, self.font_size)

        self._build_ui()
        self.load_all()
        self._build_tree()

    # ---------------- UI 구성 ----------------
    def _build_ui(self):
        # 1열: 기본 컨트롤 및 기호 버튼
        top = tk.Frame(self, padx=6, pady=6)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Button(top, text="새폴더", command=self.new_folder).pack(side=tk.LEFT)
        tk.Button(top, text="새노트", command=self.new_note).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(top, text="저장💾", command=self.save_all).pack(side=tk.LEFT, padx=(6, 0))

        # 글 크기
        tk.Label(top, text="| 글").pack(side=tk.LEFT, padx=(12, 2))
        self.font_size_var = tk.IntVar(value=self.font_size)
        self.font_spin = tk.Spinbox(top, from_=8, to=40, width=3, textvariable=self.font_size_var, command=self.apply_font_size)
        self.font_spin.pack(side=tk.LEFT)

        # 항상 위
        self.topmost_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="위", variable=self.topmost_var, command=self.toggle_topmost).pack(side=tk.LEFT, padx=(8, 12))

        # 기호 버튼 (필요한 6개로 다이어트)
        self.symbols = ["✅", "▶", "➜", "✔", "⭕", "❌", "🏴", "😎"]
        for s in self.symbols:
            tk.Button(top, text=s, width=2, command=lambda ch=s: self.insert_symbol(ch)).pack(side=tk.LEFT, padx=1)

        # 2열: 경로 표시 및 하이라이트 바
        hl = tk.Frame(self, padx=6, pady=4)
        hl.pack(side=tk.TOP, fill=tk.X)

        self.path_label = tk.Label(hl, text="->", anchor="w")
        self.path_label.pack(side=tk.LEFT, padx=(0, 10))

        for i, hex_color in enumerate(self.bg_palette):
            tk.Button(
                hl, width=2, relief="solid", bd=1, bg=hex_color, activebackground=hex_color,
                command=lambda idx=i: self.apply_highlight(self.bg_tags[idx])
            ).pack(side=tk.LEFT, padx=2, pady=2)

        tk.Button(hl, text="지우기", command=self.clear_highlight).pack(side=tk.LEFT, padx=(10, 6))

        # 메인 영역 (Paned window)
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: Treeview (폴더 구조)
        left = ttk.Frame(paned)
        paned.add(left, weight=1)

        self.tree = ttk.Treeview(left, show="tree")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Button-1>", self.on_tree_click_toggle)
        self.tree.bind("<Button-3>", self.on_tree_right_click)

        # Right: Text Editor
        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        self.text = tk.Text(right, wrap="word", undo=True, font=self.text_font)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ysb2 = ttk.Scrollbar(right, orient="vertical", command=self.text.yview)
        ysb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=ysb2.set)

        # 태그 설정
        for tag, color in zip(self.bg_tags, self.bg_palette):
            self.text.tag_configure(tag, background=color)

        self.text.bind("<Tab>", self.handle_tab)

    # ---------------- Data IO (추후 Supabase 연동 시 수정될 부분) ----------------
    def load_all(self):
        if DATA_FILE.exists():
            try:
                data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}

        self.folders = data.get("folders", [])
        self.notes = data.get("notes", [])

        if not self.folders:
            self.folders = [{"id": "f1", "name": "Start Folder"}]
        if not self.notes:
            self.notes = [{"id": "n1", "folder_id": self.folders[0]["id"], "title": "메모", "body": "", "highlights": []}]

    def save_all(self):
        self._save_editor_to_current_note()
        data = {"folders": self.folders, "notes": self.notes}

        try:
            if DATA_FILE.exists():
                shutil.copy(DATA_FILE, BACKUP_FILE)
            DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            messagebox.showerror("에러", "저장 실패")

    def on_close(self):
        try:
            self.save_all()
        finally:
            self.destroy()

    # ---------------- Tree 빌드 및 이벤트 ----------------
    def _build_tree(self):
        open_folders = [iid for iid in self.tree.get_children("") if self.tree.item(iid, "open")]
        current_selection = self.tree.selection()

        self.tree.delete(*self.tree.get_children())
        self.tree_iid_to_folder_id.clear()
        self.tree_iid_to_note_id.clear()

        for f in self.folders:
            iid = self._iid_folder(f["id"])
            is_open = iid in open_folders
            self.tree.insert("", "end", iid=iid, text=f.get("name", "Folder"), open=is_open)
            self.tree_iid_to_folder_id[iid] = f["id"]

            for n in self.notes:
                if n.get("folder_id") == f["id"]:
                    niid = self._iid_note(n["id"])
                    self.tree.insert(iid, "end", iid=niid, text=n.get("title", "Note"))
                    self.tree_iid_to_note_id[niid] = n["id"]

        if current_selection and self.tree.exists(current_selection[0]):
            self.tree.selection_set(current_selection[0])
            self.tree.see(current_selection[0])
        elif self.notes:
            first_niid = self._iid_note(self.notes[0]["id"])
            if self.tree.exists(first_niid):
                self.tree.selection_set(first_niid)

    def on_tree_select(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        iid = sel[0]

        self._save_editor_to_current_note()

        if iid.startswith("n:"):
            note_id = self.tree_iid_to_note_id.get(iid)
            if note_id:
                self.current_note_id = note_id
                self.load_note(note_id)
        elif iid.startswith("f:"):
            folder_id = self.tree_iid_to_folder_id.get(iid)
            if folder_id:
                f = self._find_folder(folder_id)
                if f: self.path_label.config(text=f"-> {f.get('name','')}")

    def on_tree_click_toggle(self, event):
        iid = self.tree.identify_row(event.y)
        if iid and iid.startswith("f:"):
            is_open = self.tree.item(iid, "open")
            self.tree.item(iid, open=not is_open)

    def on_tree_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid: return
        self.tree.selection_set(iid)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="이름 변경", command=lambda: self.rename_item(iid))
        menu.add_separator()
        menu.add_command(label="삭제", command=lambda: self.delete_item(iid))
        menu.post(event.x_root, event.y_root)

    # ---------------- CRUD ----------------
    def rename_item(self, iid):
        new_name = simpledialog.askstring("이름 변경", "새 이름을 입력하세요:")
        if not new_name: return

        if iid.startswith("f:"):
            fid = self.tree_iid_to_folder_id.get(iid)
            folder = self._find_folder(fid) if fid else None
            if folder: folder["name"] = new_name
        elif iid.startswith("n:"):
            nid = self.tree_iid_to_note_id.get(iid)
            note = self._find_note(nid) if nid else None
            if note: note["title"] = new_name
        
        self._build_tree()
        self.save_all()

    def delete_item(self, iid):
        if not messagebox.askyesno("삭제 확인", "정말로 삭제하시겠습니까?"): return

        if iid.startswith("f:"):
            fid = self.tree_iid_to_folder_id.get(iid)
            self.folders = [f for f in self.folders if f["id"] != fid]
            self.notes = [n for n in self.notes if n.get("folder_id") != fid]
        elif iid.startswith("n:"):
            nid = self.tree_iid_to_note_id.get(iid)
            self.notes = [n for n in self.notes if n["id"] != nid]
            if self.current_note_id == nid:
                self.current_note_id = None
                self.text.delete("1.0", tk.END)

        self._build_tree()
        self.save_all()

    def new_folder(self):
        name = simpledialog.askstring("새 폴더", "폴더 이름:")
        if not name: return
        new_id = self._new_id("f")
        self.folders.append({"id": new_id, "name": name})
        self._build_tree()

    def new_note(self):
        folder_id = None
        sel = self.tree.selection()
        if sel:
            iid = sel[0]
            if iid.startswith("f:"): folder_id = self.tree_iid_to_folder_id.get(iid)
            elif iid.startswith("n:"):
                note_id = self.tree_iid_to_note_id.get(iid)
                if note_id:
                    n = self._find_note(note_id)
                    folder_id = n.get("folder_id") if n else None
        
        if folder_id is None and self.folders:
            folder_id = self.folders[0]["id"]

        title = simpledialog.askstring("새 노트", "노트 제목:")
        if not title: return

        new_id = self._new_id("n")
        self.notes.append({"id": new_id, "folder_id": folder_id, "title": title, "body": "", "highlights": []})
        self._build_tree()
        self.tree.selection_set(self._iid_note(new_id))
        self.current_note_id = new_id
        self.load_note(new_id)

    def load_note(self, note_id: str):
        n = self._find_note(note_id)
        if not n: return

        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", n.get("body", ""))

        for tag in self.bg_tags:
            self.text.tag_remove(tag, "1.0", tk.END)

        for hl in n.get("highlights", []):
            tag, start, end = hl.get("tag"), hl.get("start"), hl.get("end")
            if tag in self.bg_tags and start and end:
                try: self.text.tag_add(tag, start, end)
                except Exception: pass

        fid = n.get("folder_id")
        folder = self._find_folder(fid) if fid else None
        folder_name = folder["name"] if folder and "name" in folder else ""
        self.path_label.config(text=f"-> {folder_name} / {n.get('title', '')}")

    def _save_editor_to_current_note(self):
        if not self.current_note_id: return
        n = self._find_note(self.current_note_id)
        if not n: return
        n["body"] = self.text.get("1.0", tk.END).rstrip()

        highlights = []
        for tag in self.bg_tags:
            ranges = self.text.tag_ranges(tag)
            for i in range(0, len(ranges), 2):
                highlights.append({"tag": tag, "start": str(ranges[i]), "end": str(ranges[i + 1])})
        n["highlights"] = highlights

    # ---------------- 기타 편집 도구 ----------------
    def handle_tab(self, event):
        self.text.insert(tk.INSERT, "    ")
        return "break"

    def apply_highlight(self, tag: str):
        try:
            start, end = self.text.index("sel.first"), self.text.index("sel.last")
            self.text.tag_add(tag, start, end)
        except tk.TclError: pass

    def clear_highlight(self):
        try:
            start, end = self.text.index("sel.first"), self.text.index("sel.last")
            for tag in self.bg_tags: self.text.tag_remove(tag, start, end)
        except tk.TclError: pass

    def insert_symbol(self, ch: str):
        self.text.insert(tk.INSERT, ch)

    def apply_font_size(self):
        try:
            self.font_size = int(self.font_size_var.get())
            self.text_font = (self.font_family, self.font_size)
            self.text.configure(font=self.text_font)
        except (tk.TclError, ValueError): pass

    def toggle_topmost(self):
        self.attributes("-topmost", bool(self.topmost_var.get()))

    # ---------------- 헬퍼 함수 ----------------
    def _new_id(self, prefix: str) -> str:
        existing = {f["id"] for f in self.folders} if prefix == "f" else {n["id"] for n in self.notes}
        i = 1
        while f"{prefix}{i}" in existing: i += 1
        return f"{prefix}{i}"

    def _find_folder(self, folder_id: str):
        return next((f for f in self.folders if f.get("id") == folder_id), None)

    def _find_note(self, note_id: str):
        return next((n for n in self.notes if n.get("id") == note_id), None)

    def _iid_folder(self, fid: str) -> str: return f"f:{fid}"
    def _iid_note(self, nid: str) -> str: return f"n:{nid}"

if __name__ == "__main__":
    app = SupaNoteApp()
    app.mainloop()