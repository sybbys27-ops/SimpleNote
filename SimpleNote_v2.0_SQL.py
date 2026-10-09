# -*- coding: utf-8 -*-
import json
import shutil
import re
import sqlite3 # SQLite db저장
import webbrowser
import sys  # sys 모듈 추가
import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter import ttk
from pathlib import Path

# PyInstaller로 패키징된 경우와 일반 스크립트로 실행될 경우를 구분하여 경로 설정
if getattr(sys, 'frozen', False):
    # exe 파일로 묶여서 실행될 때: 실제 exe 파일이 있는 위치를 찾음
    BASE_DIR = Path(sys.executable).parent
else:
    # 파이썬 스크립트(.py)로 실행될 때
    BASE_DIR = Path(__file__).resolve().parent

# 그 폴더 아래에 파일이 생성되도록 고정합니다.
DATA_FILE = BASE_DIR / "notes2.0.db"



DEFAULT_FONT_FAMILY = "Malgun Gothic"
DEFAULT_FONT_SIZE = 10
WINDOW_W, WINDOW_H = 540, 500


class SimpleNoteApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple Notes : 가라실험실 ver2.0")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.minsize(520, 420)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- 하이라이트 팔레트 ---
        self.bg_palette = [
            "#FC8DE4",
            "#F6B6C8",
            "#FFE291",
            "#C9F0AA",
            "#BDEEDC",
            "#B8C8FF",
            "#AAAAAA",
            "#D5D5D5",
            "#000000",
        ]
        self.bg_tags = [f"bg{i}" for i in range(len(self.bg_palette))]

        # --- 상태 ---
        self.folders = []
        self.notes = []
        self.current_note_id = None
        self.tree_iid_to_folder_id = {}
        self.tree_iid_to_note_id = {}
        self.search_window = None
        self.search_listbox = None
        self.search_result_note_ids = []
        self.link_tags = []

        # 폰트
        self.font_family = DEFAULT_FONT_FAMILY
        self.font_size = DEFAULT_FONT_SIZE
        self.text_font = (self.font_family, self.font_size)

        self._build_ui()
        self.load_all()
        self._build_tree()

    # ---------------- UI ----------------
    def _build_ui(self):

        top = tk.Frame(self, padx=6, pady=6)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Button(top, text="새폴더", command=self.new_folder).pack(side=tk.LEFT)
        tk.Button(top, text="새노트", command=self.new_note).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(top, text="저장💾", command=self.save_all).pack(side=tk.LEFT, padx=(6, 0))

        # --- 검색(본문 전체 검색, 결과는 메시지박스로만 표시) ---
        self.search_var = tk.StringVar()
        tk.Label(top, text="검색").pack(side=tk.LEFT, padx=(12, 4))
        self.search_entry = ttk.Entry(top, textvariable=self.search_var, width=12)
        self.search_entry.pack(side=tk.LEFT)
        # tk.Button(top, text="찾기", command=self.search_body_all_notes).pack(side=tk.LEFT, padx=(6, 0))
        self.search_entry.bind("<Return>", lambda e: self.search_body_all_notes())

        

        # 기호 버튼(우측)
        symbol_bar = tk.Frame(top)
        symbol_bar.pack(side=tk.RIGHT)
        self.symbols = ["✅", "▶", "→", "➜", "✔", "⭕", "❌", "🏴", "😁"]
        for s in self.symbols:
            tk.Button(symbol_bar, text=s, width=2, command=lambda ch=s: self.insert_symbol(ch)).pack(side=tk.LEFT, padx=2)

        # 글 크기 / 항상 위
        # tk.Label(top, text=" " ).pack(side=tk.LEFT, padx=(16, 4))
        self.font_size_var = tk.IntVar(value=self.font_size)
        self.font_spin = tk.Spinbox(top, from_=8, to=40, width=3, textvariable=self.font_size_var, command=self.apply_font_size)
        self.font_spin.pack(side=tk.RIGHT)

        self.topmost_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="위", variable=self.topmost_var, command=self.toggle_topmost).pack(side=tk.RIGHT, padx=(10, 0))

        # 하이라이트 바
        hl = tk.Frame(self, padx=6, pady=4)
        hl.pack(side=tk.TOP, fill=tk.X)

        self.path_label = tk.Label(hl, text="->", anchor="w")
        self.path_label.pack(side=tk.LEFT, padx=(0, 10))

        for i, hex_color in enumerate(self.bg_palette):
            tk.Button(
                hl,
                width=2,
                relief="solid",
                bd=1,
                bg=hex_color,
                activebackground=hex_color,
                command=lambda idx=i: self.apply_highlight(self.bg_tags[idx])
            ).pack(side=tk.LEFT, padx=3, pady=2)

        tk.Button(hl, text="지우기", command=self.clear_highlight).pack(side=tk.LEFT, padx=(10, 6))
        tk.Button(hl, text="ENTER", command=self.simulate_enter).pack(side=tk.LEFT, padx=4)
        tk.Button(hl, text="DEL", command=self.simulate_del).pack(side=tk.LEFT, padx=4)

        # Paned window
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: tree
        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        # left = ttk.Frame(paned)
        # paned.add(left, weight=1)

        self.tree = ttk.Treeview(left, show="tree")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)


        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Button-1>", self.on_tree_click_toggle)

        # 마우스 우클릭 메뉴
        self.tree.bind("<Button-3>", self.on_tree_right_click)  # Windows/Linux용 우클릭









        # Right: text editor
        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        self.text = tk.Text(right, wrap="word", undo=True, font=self.text_font)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ysb2 = ttk.Scrollbar(right, orient="vertical", command=self.text.yview)
        ysb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=ysb2.set)

        # setup tags for highlight colors
        for tag, color in zip(self.bg_tags, self.bg_palette):
            self.text.tag_configure(tag, background=color)

        # Tab 4칸 수정
        self.text.bind("<Tab>", self.handle_tab)
        self.text.bind("<KeyRelease>", self._on_text_key_release, add="+")


# ---------------- Data IO (SQLite CRUD 적용) ----------------
    def init_db(self):
        """앱 시작 시 DB 파일과 테이블이 없으면 생성합니다."""
        with sqlite3.connect(DATA_FILE) as conn:
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS folders
                           (id TEXT PRIMARY KEY, name TEXT)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS notes
                           (id TEXT PRIMARY KEY, folder_id TEXT, title TEXT, body TEXT, highlights TEXT)""")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_notes_folder_id ON notes(folder_id)")
            conn.commit()

    def load_all(self):
        self.init_db()
        self.folders = []
        self.notes = []

        with sqlite3.connect(DATA_FILE) as conn:
            cur = conn.cursor()

            cur.execute("SELECT id, name FROM folders ORDER BY rowid")
            for row in cur.fetchall():
                self.folders.append({"id": row[0], "name": row[1]})

            cur.execute("SELECT id, folder_id, title, body, highlights FROM notes ORDER BY rowid")
            for row in cur.fetchall():
                try:
                    hl = json.loads(row[4]) if row[4] else []
                except Exception:
                    hl = []

                self.notes.append({
                    "id": row[0],
                    "folder_id": row[1],
                    "title": row[2],
                    "body": row[3],
                    "highlights": hl,
                })

        if not self.folders:
            folder = {"id": "f1", "name": "Start Folder"}
            self.folders.append(folder)
            self._db_insert_folder(folder)

        if not self.notes:
            note = {
                "id": "n1",
                "folder_id": self.folders[0]["id"],
                "title": "메모",
                "body": "",
                "highlights": [],
            }
            self.notes.append(note)
            self._db_insert_note(note)

    def _db_insert_folder(self, folder):
        with sqlite3.connect(DATA_FILE) as conn:
            conn.execute(
                "INSERT INTO folders (id, name) VALUES (?, ?)",
                (folder["id"], folder.get("name", "")),
            )
            conn.commit()

    def _db_update_folder(self, folder):
        with sqlite3.connect(DATA_FILE) as conn:
            conn.execute(
                "UPDATE folders SET name = ? WHERE id = ?",
                (folder.get("name", ""), folder["id"]),
            )
            conn.commit()

    def _db_delete_folder(self, folder_id):
        with sqlite3.connect(DATA_FILE) as conn:
            conn.execute("DELETE FROM notes WHERE folder_id = ?", (folder_id,))
            conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
            conn.commit()

    def _db_insert_note(self, note):
        hl_str = json.dumps(note.get("highlights", []), ensure_ascii=False)
        with sqlite3.connect(DATA_FILE) as conn:
            conn.execute(
                """INSERT INTO notes (id, folder_id, title, body, highlights)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    note["id"],
                    note.get("folder_id"),
                    note.get("title", ""),
                    note.get("body", ""),
                    hl_str,
                ),
            )
            conn.commit()

    def _db_update_note(self, note):
        hl_str = json.dumps(note.get("highlights", []), ensure_ascii=False)
        with sqlite3.connect(DATA_FILE) as conn:
            conn.execute(
                """UPDATE notes
                   SET folder_id = ?, title = ?, body = ?, highlights = ?
                   WHERE id = ?""",
                (
                    note.get("folder_id"),
                    note.get("title", ""),
                    note.get("body", ""),
                    hl_str,
                    note["id"],
                ),
            )
            conn.commit()

    def _db_delete_note(self, note_id):
        with sqlite3.connect(DATA_FILE) as conn:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()

    def save_all(self):
        """
        DB 전체 삭제/재삽입을 하지 않고 현재 편집 중인 노트만
        실제 변경이 있을 때 UPDATE합니다.
        """
        self._save_editor_to_current_note()

    def on_close(self):
        try:
            self.save_all()
        finally:
            self.destroy()

# ---------------- Tree build ----------------
    def _build_tree(self):
        # 트리를 다시 만들기 전에 열려 있는 모든 폴더 상태를 기억합니다.
        open_folders = set()

        def collect_open_folders(parent_iid=""):
            for iid in self.tree.get_children(parent_iid):
                if iid.startswith("f:"):
                    if self.tree.item(iid, "open"):
                        open_folders.add(iid)
                    collect_open_folders(iid)

        collect_open_folders("")

        # 현재 선택된 항목 기억
        current_selection = self.tree.selection()

        # 3. 트리 초기화
        self.tree.delete(*self.tree.get_children())
        self.tree_iid_to_folder_id.clear()
        self.tree_iid_to_note_id.clear()

        # 4. 데이터 재구성
        for f in self.folders:
            iid = self._iid_folder(f["id"])
            # 이전 상태가 열려 있었는지 확인
            is_open = iid in open_folders
            self.tree.insert("", "end", iid=iid, text=f.get("name", "Folder"), open=is_open)
            self.tree_iid_to_folder_id[iid] = f["id"]

            for n in self.notes:
                if n.get("folder_id") == f["id"]:
                    niid = self._iid_note(n["id"])
                    self.tree.insert(iid, "end", iid=niid, text=n.get("title", "Note"))
                    self.tree_iid_to_note_id[niid] = n["id"]

        # 5. 선택 상태 복구 (지렁이가 가장 많이 생기는 구간!)
        if current_selection:
            target_iid = current_selection[0]
            if self.tree.exists(target_iid):
                self.tree.selection_set(target_iid)
                self.tree.see(target_iid) # 선택된 항목이 보이도록 스크롤
        elif self.notes:
            first_niid = self._iid_note(self.notes[0]["id"])
            if self.tree.exists(first_niid):
                self.tree.selection_set(first_niid)









    # ---------------- Tree events ----------------
    def on_tree_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]

        # save old note
        self._save_editor_to_current_note()

        if iid.startswith("n:"):
            note_id = self.tree_iid_to_note_id.get(iid)
            if note_id:
                self.current_note_id = note_id
                self.load_note(note_id)
        elif iid.startswith("f:"):
            # folder selected: update label only
            folder_id = self.tree_iid_to_folder_id.get(iid)
            if folder_id:
                f = self._find_folder(folder_id)
                if f:
                    self.path_label.config(text=f"-> {f.get('name','')}")
            return

    def on_tree_click_toggle(self, event):
        # single click on folder: toggle open/close
        iid = self.tree.identify_row(event.y)
        if iid and iid.startswith("f:"):
            is_open = self.tree.item(iid, "open")
            self.tree.item(iid, open=not is_open)
            
            
            
    # ---------------- 오른쪽 마우스 메뉴 ----------------
    def on_tree_right_click(self, event):
        # 클릭한 위치의 항목(iid) 찾기
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
            
        self.tree.selection_set(iid) # 우클릭한 항목 자동 선택
        
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="이름 변경", command=lambda: self.rename_item(iid))
        menu.add_separator()
        menu.add_command(label="삭제", command=lambda: self.delete_item(iid))
        menu.post(event.x_root, event.y_root)

    def rename_item(self, iid):
        current_name = ""
        target_type = None
        target_obj = None

        if iid.startswith("f:"):
            fid = self.tree_iid_to_folder_id.get(iid)
            folder = self._find_folder(fid) if fid else None
            if not folder:
                return
            current_name = folder.get("name", "")
            target_type = "folder"
            target_obj = folder

        elif iid.startswith("n:"):
            nid = self.tree_iid_to_note_id.get(iid)
            note = self._find_note(nid) if nid else None
            if not note:
                return
            current_name = note.get("title", "")
            target_type = "note"
            target_obj = note
        else:
            return

        new_name = simpledialog.askstring(
            "이름 변경",
            "새 이름을 입력하세요:",
            initialvalue=current_name
        )
        if not new_name:
            return

        if target_type == "folder":
            target_obj["name"] = new_name
            self._db_update_folder(target_obj)
        else:
            target_obj["title"] = new_name
            self._db_update_note(target_obj)

        self._build_tree()

    def delete_item(self, iid):
        if iid.startswith("f:"):
            fid = self.tree_iid_to_folder_id.get(iid)
            child_notes = [n for n in self.notes if n.get("folder_id") == fid]

            if child_notes:
                msg = f"폴더 내에 {len(child_notes)}개의 노트가 있습니다.\n정말로 폴더와 노트를 모두 삭제하시겠습니까?"
                if not messagebox.askyesno("삭제 확인", msg):
                    return
            else:
                if not messagebox.askyesno("삭제 확인", "정말로 삭제하시겠습니까?"):
                    return

            self._db_delete_folder(fid)
            self.folders = [f for f in self.folders if f["id"] != fid]
            self.notes = [n for n in self.notes if n.get("folder_id") != fid]

            if self.current_note_id and not self._find_note(self.current_note_id):
                self.current_note_id = None
                self.text.delete("1.0", tk.END)

        elif iid.startswith("n:"):
            if not messagebox.askyesno("삭제 확인", "정말로 삭제하시겠습니까?"):
                return

            nid = self.tree_iid_to_note_id.get(iid)
            if not nid:
                return

            self._db_delete_note(nid)
            self.notes = [n for n in self.notes if n["id"] != nid]

            if self.current_note_id == nid:
                self.current_note_id = None
                self.text.delete("1.0", tk.END)

        self._build_tree()

    # ---------------- CRUD ----------------

    # ---------------- CRUD ----------------
    def new_folder(self):
        name = simpledialog.askstring("새 폴더", "폴더 이름:")
        if not name:
            return
        new_id = self._new_id("f")
        folder = {"id": new_id, "name": name}
        self.folders.append(folder)
        self._db_insert_folder(folder)
        self._build_tree()

    def new_note(self):
        # must have selected folder
        folder_id = None
        sel = self.tree.selection()
        if sel:
            iid = sel[0]
            if iid.startswith("f:"):
                folder_id = self.tree_iid_to_folder_id.get(iid)
            elif iid.startswith("n:"):
                # note selected -> use its folder
                note_id = self.tree_iid_to_note_id.get(iid)
                if note_id:
                    n = self._find_note(note_id)
                    folder_id = n.get("folder_id") if n else None
                else:
                    folder_id = None

        if folder_id is None and self.folders:
            folder_id = self.folders[0]["id"]

        title = simpledialog.askstring("새 노트", "노트 제목:")
        if not title:
            return

        new_id = self._new_id("n")
        note = {"id": new_id, "folder_id": folder_id, "title": title, "body": "", "highlights": []}
        self.notes.append(note)
        self._db_insert_note(note)
        self._build_tree()
        # select new note
        self.tree.selection_set(self._iid_note(new_id))
        self.current_note_id = new_id
        self.load_note(new_id)

    def load_note(self, note_id: str):
        n = self._find_note(note_id)
        if not n:
            return

        # clear editor
        self.text.delete("1.0", tk.END)

        # insert body
        body = n.get("body", "")
        self.text.insert("1.0", body)

        # clear tags
        for tag in self.bg_tags:
            self.text.tag_remove(tag, "1.0", tk.END)

        # restore highlights
        for hl in n.get("highlights", []):
            tag = hl.get("tag")
            start = hl.get("start")
            end = hl.get("end")
            if tag in self.bg_tags and start and end:
                try:
                    self.text.tag_add(tag, start, end)
                except Exception:
                    pass

        self._apply_link_tags()

        # path label
        
        fid = n.get("folder_id")
        folder = self._find_folder(fid) if fid else None
        folder_name = folder["name"] if folder and "name" in folder else ""
        title = n.get("title", "")
        self.path_label.config(text=f"-> {folder_name} / {title}")

    def _save_editor_to_current_note(self):
        if not self.current_note_id:
            return

        n = self._find_note(self.current_note_id)
        if not n:
            return

        new_body = self.text.get("1.0", "end-1c")

        highlights = []
        for tag in self.bg_tags:
            ranges = self.text.tag_ranges(tag)
            for i in range(0, len(ranges), 2):
                start = str(ranges[i])
                end = str(ranges[i + 1])
                highlights.append({"tag": tag, "start": start, "end": end})

        if new_body != n.get("body", "") or highlights != n.get("highlights", []):
            n["body"] = new_body
            n["highlights"] = highlights
            self._db_update_note(n)

    # ---------------- Search (비모달 결과창) ----------------

    # ---------------- Search (messagebox only) ----------------
    def search_body_all_notes(self):
        query = (self.search_var.get() or "").strip()
        if not query:
            return

        self._save_editor_to_current_note()

        q = query.casefold()
        folder_name_by_id = {f.get("id"): f.get("name", "") for f in self.folders}

        hits = []
        for n in self.notes:
            body = (n.get("body") or "").casefold()
            title = (n.get("title") or "").casefold()

            if q in body or q in title:
                fid = n.get("folder_id")
                fname = folder_name_by_id.get(fid, "Unknown")
                display_title = (n.get("title") or "(제목없음)").strip()
                hits.append((n["id"], f"{fname} > {display_title}"))

        self._show_search_results(query, hits)

    def _show_search_results(self, query, hits):
        if self.search_window is None or not self.search_window.winfo_exists():
            self.search_window = tk.Toplevel(self)
            self.search_window.title("검색 결과")
            self.search_window.geometry("390x260")
            self.search_window.minsize(320, 180)

            info = tk.Label(
                self.search_window,
                text="결과를 한 번 클릭하면 해당 노트로 이동합니다.",
                anchor="w",
                padx=8,
                pady=6,
            )
            info.pack(fill=tk.X)

            frame = ttk.Frame(self.search_window)
            frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

            self.search_listbox = tk.Listbox(frame, activestyle="dotbox")
            self.search_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            sb = ttk.Scrollbar(frame, orient="vertical", command=self.search_listbox.yview)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            self.search_listbox.configure(yscrollcommand=sb.set)

            self.search_listbox.bind("<<ListboxSelect>>", self._on_search_result_click)
            self.search_window.protocol("WM_DELETE_WINDOW", self._close_search_window)

        self.search_window.title(f"검색 결과: {query} ({len(hits)}개)")
        self.search_listbox.delete(0, tk.END)
        self.search_result_note_ids = []

        if not hits:
            self.search_listbox.insert(tk.END, "검색 결과가 없습니다.")
            return

        for note_id, display in hits:
            self.search_result_note_ids.append(note_id)
            self.search_listbox.insert(tk.END, display)

        self.search_window.deiconify()
        self.search_window.lift()

    def _close_search_window(self):
        if self.search_window and self.search_window.winfo_exists():
            self.search_window.destroy()
        self.search_window = None
        self.search_listbox = None
        self.search_result_note_ids = []

    def _on_search_result_click(self, event=None):
        if not self.search_listbox:
            return

        selected = self.search_listbox.curselection()
        if not selected:
            return

        index = selected[0]
        if index >= len(self.search_result_note_ids):
            return

        note_id = self.search_result_note_ids[index]
        niid = self._iid_note(note_id)
        if not self.tree.exists(niid):
            return

        self._save_editor_to_current_note()

        parent = self.tree.parent(niid)
        if parent:
            self.tree.item(parent, open=True)

        self.tree.selection_set(niid)
        self.tree.see(niid)
        self.current_note_id = note_id
        self.load_note(note_id)

    # ---------------- URL / Markdown 링크 ----------------
    def _on_text_key_release(self, event=None):
        self._apply_link_tags()

    def _apply_link_tags(self):
        for tag in self.link_tags:
            try:
                self.text.tag_delete(tag)
            except Exception:
                pass
        self.link_tags = []

        content = self.text.get("1.0", "end-1c")
        if not content:
            return

        matches = []
        occupied = []

        md_pattern = re.compile(r"\[[^\]]+\]\((https?://[^\s)]+)\)")
        for m in md_pattern.finditer(content):
            matches.append((m.start(), m.end(), m.group(1)))
            occupied.append((m.start(), m.end()))

        url_pattern = re.compile(r"https?://[^\s<>\]\)]+")
        for m in url_pattern.finditer(content):
            if any(a <= m.start() < b for a, b in occupied):
                continue
            url = m.group(0).rstrip(".,;:")
            end = m.start() + len(url)
            matches.append((m.start(), end, url))

        for idx, (start_offset, end_offset, url) in enumerate(matches):
            tag = f"hyperlink_{idx}"
            self.link_tags.append(tag)

            start = f"1.0+{start_offset}c"
            end = f"1.0+{end_offset}c"

            self.text.tag_add(tag, start, end)
            self.text.tag_configure(tag, foreground="#0563C1", underline=True)
            self.text.tag_bind(
                tag,
                "<Button-1>",
                lambda e, target=url: self._open_web_link(target)
            )
            self.text.tag_bind(
                tag,
                "<Enter>",
                lambda e: self.text.config(cursor="hand2")
            )
            self.text.tag_bind(
                tag,
                "<Leave>",
                lambda e: self.text.config(cursor="xterm")
            )

    def _open_web_link(self, url):
        try:
            webbrowser.open(url, new=2)
        except Exception:
            messagebox.showerror("링크 열기 실패", f"웹페이지를 열 수 없습니다.\n{url}")

    # ---------------- Simulate ENTER key ----------------

    # ---------------- Simulate ENTER key ----------------
    # def simulate_enter(self):   기본 엔터 기능과 동일
        # Insert newline (same as Return)
        #self.text.insert(tk.INSERT, "\n")


    def simulate_enter(self):   # 자동 들여쓰기 기능 엔터
        current_index = self.text.index("insert linestart")
        current_line_content = self.text.get(current_index, "insert")
        match = re.match(r"\s*", current_line_content)
        whitespace = match.group(0) if match else ""
        self.text.insert(tk.INSERT, "\n" + whitespace)
        self.text.see(tk.INSERT)
        
        
#    def simulate_del(self):     # 범위 삭제 기능 DEL
#        try:    # Insert newline (same as Return)
#            if self.text.tag_ranges("sel"):
#                self.text.delete("sel.first", "sel.last")
#            else:
#                self.text.delete("INSERT")            
#        except Exception:
#            pass

    def simulate_del(self):
    # 텍스트 위젯의 포커스 확인 (예: self.text_area)
        target = self.text 
        try:
        # 1. 사용자가 마우스로 블록을 지정(selection)했을 경우
            if target.tag_ranges("sel"):
                target.delete("sel.first", "sel.last")
            else:
            # 2. 블록이 없다면 커서가 위치한 바로 '그' 자리(오른쪽 문자) 삭제
                target.delete("insert")
        except Exception as e:
            print(f"삭제 중 오류 발생: {e}")


    # ---------------- Tab key handling ----------------
    def handle_tab(self, event):
        self.text.insert(tk.INSERT, "    ")  # 4칸 공백 삽입
        return "break"  # 기본 Tab 동작 방지


    # ---------------- Highlight ----------------
    def apply_highlight(self, tag: str):
        try:
            start = self.text.index("sel.first")
            end = self.text.index("sel.last")
        except tk.TclError:
            return
        self.text.tag_add(tag, start, end)

    def clear_highlight(self):
        try:
            start = self.text.index("sel.first")
            end = self.text.index("sel.last")
        except tk.TclError:
            return
        for tag in self.bg_tags:
            self.text.tag_remove(tag, start, end)

    # ---------------- Symbols / Font / Topmost ----------------
    def insert_symbol(self, ch: str):
        self.text.insert(tk.INSERT, ch)

    def apply_font_size(self):
        try:
            # 값을 가져올 때 타입을 확실히 해줍니다.
            new_size = self.font_size_var.get()
            self.font_size = int(new_size)
            
            # 폰트 정보를 업데이트합니다.
            self.text_font = (self.font_family, self.font_size)
            self.text.configure(font=self.text_font)
        except (tk.TclError, ValueError, TypeError):
            # 값이 비어있거나 숫자가 아닐 경우 무시합니다.
            pass

    def toggle_topmost(self):
        self.attributes("-topmost", bool(self.topmost_var.get()))

    # ---------------- Helpers ----------------
    def _new_id(self, prefix: str) -> str:
        # very simple id generator
        existing = set()
        if prefix == "f":
            existing = {f["id"] for f in self.folders}
        else:
            existing = {n["id"] for n in self.notes}

        i = 1
        while True:
            nid = f"{prefix}{i}"
            if nid not in existing:
                return nid
            i += 1

    def _find_folder(self, folder_id: str):
        for f in self.folders:
            if f.get("id") == folder_id:
                return f
        return None

    def _find_note(self, note_id: str):
        for n in self.notes:
            if n.get("id") == note_id:
                return n
        return None

    # --- 파일 맨 아래 Helpers 섹션에 추가하세요 ---
    def _iid_folder(self, fid: str) -> str:
        return f"f:{fid}"

    def _iid_note(self, nid: str) -> str:
        return f"n:{nid}"




if __name__ == "__main__":
    app = SimpleNoteApp()
    app.mainloop()
