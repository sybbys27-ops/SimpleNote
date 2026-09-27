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

        # 1단 폴더는 옅은 배경색으로, 2단 폴더는 배경색 없이 굵은 글씨로 구분
        # ttk.Treeview는 기본적으로 '글자 부분만' 배경색을 넣는 기능이 없어
        # 2단 폴더는 행 하이라이트 대신 bold 폰트를 사용합니다.
        self.tree.tag_configure("folder_level1", background="#EAF3FF")
        self.tree.tag_configure(
            "folder_level2",
            font=(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, "bold")
        )

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
        # 입력 중 URL이 추가/수정되면 링크 태그 갱신
        self.text.bind("<KeyRelease>", self._on_text_key_release, add="+")


# ---------------- Data IO (SQLite CRUD 적용) ----------------
    def _connect_db(self):
        conn = sqlite3.connect(DATA_FILE)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        """DB/테이블을 만들고 기존 v2.0 DB에는 parent_id 컬럼을 자동 추가합니다."""
        with self._connect_db() as conn:
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS folders
                           (id TEXT PRIMARY KEY, name TEXT, parent_id TEXT)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS notes
                           (id TEXT PRIMARY KEY, folder_id TEXT, title TEXT, body TEXT, highlights TEXT)""")

            # 기존 DB의 folders 테이블에는 parent_id가 없으므로 마이그레이션
            cur.execute("PRAGMA table_info(folders)")
            columns = {row[1] for row in cur.fetchall()}
            if "parent_id" not in columns:
                cur.execute("ALTER TABLE folders ADD COLUMN parent_id TEXT")

            cur.execute("CREATE INDEX IF NOT EXISTS idx_notes_folder_id ON notes(folder_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_folders_parent_id ON folders(parent_id)")
            conn.commit()

    def load_all(self):
        self.init_db()
        self.folders = []
        self.notes = []

        with self._connect_db() as conn:
            cur = conn.cursor()

            cur.execute("SELECT id, name, parent_id FROM folders ORDER BY rowid")
            for row in cur.fetchall():
                self.folders.append({
                    "id": row[0],
                    "name": row[1],
                    "parent_id": row[2],
                })

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

        # 최초 실행 시 기본 데이터는 INSERT로 한 번만 생성
        if not self.folders:
            folder = {"id": "f1", "name": "Start Folder", "parent_id": None}
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

    # ---- 개별 CRUD ----
    def _db_insert_folder(self, folder):
        with self._connect_db() as conn:
            conn.execute(
                "INSERT INTO folders (id, name, parent_id) VALUES (?, ?, ?)",
                (folder["id"], folder.get("name", ""), folder.get("parent_id")),
            )
            conn.commit()

    def _db_update_folder(self, folder):
        with self._connect_db() as conn:
            conn.execute(
                "UPDATE folders SET name = ?, parent_id = ? WHERE id = ?",
                (folder.get("name", ""), folder.get("parent_id"), folder["id"]),
            )
            conn.commit()

    def _db_insert_note(self, note):
        hl_str = json.dumps(note.get("highlights", []), ensure_ascii=False)
        with self._connect_db() as conn:
            conn.execute(
                """INSERT INTO notes (id, folder_id, title, body, highlights)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    note["id"], note.get("folder_id"), note.get("title", ""),
                    note.get("body", ""), hl_str,
                ),
            )
            conn.commit()

    def _db_update_note(self, note):
        hl_str = json.dumps(note.get("highlights", []), ensure_ascii=False)
        with self._connect_db() as conn:
            conn.execute(
                """UPDATE notes
                   SET folder_id = ?, title = ?, body = ?, highlights = ?
                   WHERE id = ?""",
                (
                    note.get("folder_id"), note.get("title", ""),
                    note.get("body", ""), hl_str, note["id"],
                ),
            )
            conn.commit()

    def _db_delete_note(self, note_id):
        with self._connect_db() as conn:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()

    def _db_delete_folders(self, folder_ids):
        if not folder_ids:
            return
        placeholders = ",".join("?" for _ in folder_ids)
        with self._connect_db() as conn:
            conn.execute(
                f"DELETE FROM notes WHERE folder_id IN ({placeholders})",
                tuple(folder_ids),
            )
            conn.execute(
                f"DELETE FROM folders WHERE id IN ({placeholders})",
                tuple(folder_ids),
            )
            conn.commit()

    def save_all(self):
        """
        예전처럼 DB 전체를 DELETE 후 INSERT하지 않습니다.
        현재 편집 중인 노트에서 실제 변경이 있을 때만 UPDATE합니다.
        """
        self._save_editor_to_current_note()

    def on_close(self):
        try:
            self.save_all()
        finally:
            self.destroy()

# ---------------- Tree build ----------------
    def _build_tree(self):
        # 트리를 다시 만들기 전에 1단/2단을 포함한 모든 열린 폴더 상태를 기억합니다.
        # 기존 코드는 최상위 폴더만 검사해서 2단 폴더가 매번 닫히는 문제가 있었습니다.
        open_folders = set()

        def collect_open_folders(parent_iid=""):
            for iid in self.tree.get_children(parent_iid):
                if iid.startswith("f:"):
                    if self.tree.item(iid, "open"):
                        open_folders.add(iid)
                    # 부모가 닫혀 있어도 자식의 open 상태 자체는 남아 있을 수 있으므로
                    # 하위 폴더까지 항상 재귀적으로 확인합니다.
                    collect_open_folders(iid)

        collect_open_folders("")
        current_selection = self.tree.selection()

        self.tree.delete(*self.tree.get_children())
        self.tree_iid_to_folder_id.clear()
        self.tree_iid_to_note_id.clear()

        folder_ids = {f.get("id") for f in self.folders}
        # parent가 없거나 유실된 폴더는 1단 폴더로 복구해서 표시
        level1_folders = [
            f for f in self.folders
            if not f.get("parent_id") or f.get("parent_id") not in folder_ids
        ]

        for f in level1_folders:
            fid = f["id"]
            iid = self._iid_folder(fid)
            self.tree.insert(
                "", "end", iid=iid, text=f.get("name", "Folder"),
                open=(iid in open_folders), tags=("folder_level1",)
            )
            self.tree_iid_to_folder_id[iid] = fid

            # 같은 폴더 안에서는 '글'을 먼저 배치
            for n in self.notes:
                if n.get("folder_id") == fid:
                    niid = self._iid_note(n["id"])
                    self.tree.insert(iid, "end", iid=niid, text=n.get("title", "Note"))
                    self.tree_iid_to_note_id[niid] = n["id"]

            # 그 다음 2단 폴더를 배치
            children = [x for x in self.folders if x.get("parent_id") == fid]
            for child in children:
                cfid = child["id"]
                ciid = self._iid_folder(cfid)
                self.tree.insert(
                    iid, "end", iid=ciid, text=child.get("name", "Folder"),
                    open=(ciid in open_folders), tags=("folder_level2",)
                )
                self.tree_iid_to_folder_id[ciid] = cfid

                for n in self.notes:
                    if n.get("folder_id") == cfid:
                        niid = self._iid_note(n["id"])
                        self.tree.insert(ciid, "end", iid=niid, text=n.get("title", "Note"))
                        self.tree_iid_to_note_id[niid] = n["id"]

        if current_selection:
            target_iid = current_selection[0]
            if self.tree.exists(target_iid):
                self.tree.selection_set(target_iid)
                self.tree.see(target_iid)
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
                    self.path_label.config(text=f"-> {self._folder_path_name(folder_id)}")
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
        new_name = simpledialog.askstring("이름 변경", "새 이름을 입력하세요:")
        if not new_name:
            return

        if iid.startswith("f:"):
            fid = self.tree_iid_to_folder_id.get(iid)
            folder = self._find_folder(fid) if fid else None
            if folder:
                folder["name"] = new_name
                self._db_update_folder(folder)

        elif iid.startswith("n:"):
            nid = self.tree_iid_to_note_id.get(iid)
            note = self._find_note(nid) if nid else None
            if note:
                note["title"] = new_name
                self._db_update_note(note)

        self._build_tree()

    def delete_item(self, iid):
        if iid.startswith("f:"):
            fid = self.tree_iid_to_folder_id.get(iid)
            if not fid:
                return

            folder_ids = [fid]
            # 1단 폴더 삭제 시 2단 폴더도 함께 삭제
            folder_ids.extend([
                f["id"] for f in self.folders
                if f.get("parent_id") == fid
            ])
            child_notes = [
                n for n in self.notes
                if n.get("folder_id") in folder_ids
            ]
            nested_count = max(0, len(folder_ids) - 1)

            if child_notes or nested_count:
                msg = (
                    f"이 폴더에는 하위 폴더 {nested_count}개, "
                    f"노트 {len(child_notes)}개가 있습니다.\n"
                    "폴더와 포함된 노트를 모두 삭제하시겠습니까?"
                )
            else:
                msg = "정말로 이 폴더를 삭제하시겠습니까?"

            if not messagebox.askyesno("삭제 확인", msg):
                return

            self._db_delete_folders(folder_ids)
            folder_id_set = set(folder_ids)
            self.folders = [f for f in self.folders if f["id"] not in folder_id_set]
            self.notes = [n for n in self.notes if n.get("folder_id") not in folder_id_set]

            if self.current_note_id and not self._find_note(self.current_note_id):
                self.current_note_id = None
                self.text.delete("1.0", tk.END)

        elif iid.startswith("n:"):
            if not messagebox.askyesno("삭제 확인", "정말로 이 노트를 삭제하시겠습니까?"):
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
        parent_id = None

        # 현재 선택 위치를 기준으로 '2단 폴더' 후보를 잡습니다.
        selected_folder_id = None
        sel = self.tree.selection()
        if sel:
            iid = sel[0]
            if iid.startswith("f:"):
                selected_folder_id = self.tree_iid_to_folder_id.get(iid)
            elif iid.startswith("n:"):
                nid = self.tree_iid_to_note_id.get(iid)
                note = self._find_note(nid) if nid else None
                selected_folder_id = note.get("folder_id") if note else None

        candidate_parent_id = None
        if selected_folder_id:
            selected_folder = self._find_folder(selected_folder_id)
            if selected_folder:
                candidate_parent_id = (
                    selected_folder["id"]
                    if not selected_folder.get("parent_id")
                    else selected_folder.get("parent_id")
                )

        if candidate_parent_id:
            parent = self._find_folder(candidate_parent_id)
            parent_name = parent.get("name", "") if parent else ""
            make_child = messagebox.askyesno(
                "새 폴더 위치",
                f"'{parent_name}' 아래에 2단 폴더로 만들까요?\n"
                "예 = 2단 폴더 / 아니오 = 새 1단 폴더"
            )
            if make_child:
                parent_id = candidate_parent_id

        name = simpledialog.askstring(
            "새 폴더",
            "2단 폴더 이름:" if parent_id else "1단 폴더 이름:"
        )
        if not name:
            return

        new_id = self._new_id("f")
        folder = {"id": new_id, "name": name, "parent_id": parent_id}
        self.folders.append(folder)
        self._db_insert_folder(folder)
        self._build_tree()

        iid = self._iid_folder(new_id)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.see(iid)

    def new_note(self):
        folder_id = None
        sel = self.tree.selection()

        if sel:
            iid = sel[0]
            if iid.startswith("f:"):
                folder_id = self.tree_iid_to_folder_id.get(iid)
            elif iid.startswith("n:"):
                note_id = self.tree_iid_to_note_id.get(iid)
                n = self._find_note(note_id) if note_id else None
                folder_id = n.get("folder_id") if n else None

        if folder_id is None and self.folders:
            folder_id = self.folders[0]["id"]

        title = simpledialog.askstring("새 노트", "노트 제목:")
        if not title:
            return

        new_id = self._new_id("n")
        note = {
            "id": new_id,
            "folder_id": folder_id,
            "title": title,
            "body": "",
            "highlights": [],
        }
        self.notes.append(note)
        self._db_insert_note(note)
        self._build_tree()

        niid = self._iid_note(new_id)
        if self.tree.exists(niid):
            self.tree.selection_set(niid)
            self.tree.see(niid)

        self.current_note_id = new_id
        self.load_note(new_id)

    def load_note(self, note_id: str):
        n = self._find_note(note_id)
        if not n:
            return

        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", n.get("body", ""))

        for tag in self.bg_tags:
            self.text.tag_remove(tag, "1.0", tk.END)

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

        folder_path = self._folder_path_name(n.get("folder_id"))
        self.path_label.config(text=f"-> {folder_path} / {n.get('title', '')}")

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
                highlights.append({
                    "tag": tag,
                    "start": str(ranges[i]),
                    "end": str(ranges[i + 1]),
                })

        # 실제 변경된 경우에만 UPDATE
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
        folder_name_by_id = {
            f.get("id"): self._folder_path_name(f.get("id"))
            for f in self.folders
        }

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

            # modal grab을 사용하지 않으므로 검색창을 열어둔 채 메인 GUI도 조작 가능
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
        self._select_note_from_search(note_id)

    def _select_note_from_search(self, note_id):
        niid = self._iid_note(note_id)
        if not self.tree.exists(niid):
            return

        # 현재 편집 내용 먼저 저장
        self._save_editor_to_current_note()

        # 조상 폴더를 펼쳐 검색된 노트가 보이게 함
        parent = self.tree.parent(niid)
        while parent:
            self.tree.item(parent, open=True)
            parent = self.tree.parent(parent)

        self.tree.selection_set(niid)
        self.tree.see(niid)
        self.current_note_id = note_id
        self.load_note(note_id)

    # ---------------- URL / Markdown 링크 ----------------
    def _on_text_key_release(self, event=None):
        self._apply_link_tags()

    def _apply_link_tags(self):
        # 이전 링크 태그 제거
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

        # Markdown: [표시문자](https://...)
        md_pattern = re.compile(r"\[[^\]]+\]\((https?://[^\s)]+)\)")
        for m in md_pattern.finditer(content):
            matches.append((m.start(), m.end(), m.group(1)))
            occupied.append((m.start(), m.end()))

        # 일반 URL. Markdown 내부 URL은 중복 태깅하지 않음
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
    def _folder_path_name(self, folder_id: str) -> str:
        folder = self._find_folder(folder_id) if folder_id else None
        if not folder:
            return ""

        parent_id = folder.get("parent_id")
        if parent_id:
            parent = self._find_folder(parent_id)
            if parent:
                return f"{parent.get('name', '')} / {folder.get('name', '')}"

        return folder.get("name", "")

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
