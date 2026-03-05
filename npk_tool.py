import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import shutil
import sys
import fnmatch
import configparser
import time
import re

class NPKSearchTool:
    def __init__(self, root):
        self.root = root
        self.root.title("NPK检索工具")
        self.root.geometry("850x700")

        self.exe_dir = self.get_exe_dir()
        self.config_path = os.path.join(self.exe_dir, "config.ini")
        self.mapping_file_path = os.path.join(self.exe_dir, "npk_mapping.txt")
        self.npk_trans_path = os.path.join(self.exe_dir, "npk.txt")
        self.trans_file_encoding = "gbk"

        self.config = configparser.ConfigParser()
        self.load_config()
        self.NPK_ROOT_DIR = self.config.get("SETTINGS", "npk_root_dir", fallback="")

        self.cn_to_en_dict = {}
        self.mapping_quick_match = {}
        self.npk_file_info = {}
        self.npk_trans_dict = {}

        self.row_colors = ["#f8f8f8", "#e6f7ff"]
        self.filename_color_map = {}

        self.create_default_mapping_file()
        self.load_word_mapping()
        self.create_widgets()
        self.update_npk_dir_label()

        if self.NPK_ROOT_DIR and os.path.isdir(self.NPK_ROOT_DIR):
            self.scan_npk_files()
            self.do_search()

    def get_exe_dir(self):
        if hasattr(sys, '_MEIPASS'):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.abspath(".")

    def load_config(self):
        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding="utf-8")
        if "SETTINGS" not in self.config.sections():
            self.config["SETTINGS"] = {}

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                self.config.write(f)
        except:
            pass

    def update_npk_dir_label(self):
        if self.NPK_ROOT_DIR and os.path.isdir(self.NPK_ROOT_DIR):
            self.npk_dir_label.config(text=f"当前：{self.NPK_ROOT_DIR}")
        else:
            self.npk_dir_label.config(text="当前：未选择")

    def create_default_mapping_file(self):
        if not os.path.exists(self.mapping_file_path):
            with open(self.mapping_file_path, "w", encoding="utf-8") as f:
                f.write("""# 中文关键词=英文
上衣=top
上衣=top1
上衣红=topred
""")

    def load_word_mapping(self):
        self.cn_to_en_dict.clear()
        if os.path.exists(self.mapping_file_path):
            try:
                with open(self.mapping_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        cn_part, en_part = line.split("=", 1)
                        cn = cn_part.strip().lower()
                        en = en_part.strip().lower()
                        if cn not in self.cn_to_en_dict:
                            self.cn_to_en_dict[cn] = []
                        if en not in self.cn_to_en_dict[cn]:
                            self.cn_to_en_dict[cn].append(en)

                self.mapping_quick_match = {}
                for cn_kw, en_list in self.cn_to_en_dict.items():
                    for i in range(len(cn_kw)):
                        for j in range(i+1, len(cn_kw)+1):
                            sub = cn_kw[i:j]
                            if sub not in self.mapping_quick_match:
                                self.mapping_quick_match[sub] = set()
                            self.mapping_quick_match[sub].update(en_list)
            except:
                pass
        self.auto_load_npk_trans_file()

    def auto_load_npk_trans_file(self):
        self.npk_trans_dict.clear()
        if not os.path.exists(self.npk_trans_path):
            with open(self.npk_trans_path, "w", encoding="gbk") as f:
                f.write("# 文件名 翻译\n")
            return

        encodings = ["gbk", "gb2312", "utf-8", "utf-8-sig"]
        lines = None
        for e in encodings:
            try:
                with open(self.npk_trans_path, "r", encoding=e) as f:
                    lines = f.readlines()
                self.trans_file_encoding = e
                break
            except:
                continue

        if lines is None:
            return

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r'\s+', line, maxsplit=1)
            if len(parts) < 2:
                continue
            fname = parts[0].strip().lower()
            trans = parts[1].strip()
            if fname not in self.npk_trans_dict:
                self.npk_trans_dict[fname] = []
            self.npk_trans_dict[fname].append(trans)

    # ===================== 添加翻译（追加） =====================
    def add_translation(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择文件")
            return
        item = selected[0]
        fname = self.tree.item(item, "values")[0].strip()

        new_trans = simpledialog.askstring("添加翻译", f"文件：{fname}\n输入新翻译（追加）", initialvalue="")
        if new_trans is None or not new_trans.strip():
            return

        try:
            with open(self.npk_trans_path, "a", encoding=self.trans_file_encoding) as f:
                f.write(f"{fname} {new_trans.strip()}\n")
            self.load_word_mapping()
            self.scan_npk_files()
            self.do_search()
        except:
            messagebox.showerror("错误", "添加失败")

    # ===================== 修改翻译（替换选中行） =====================
    def edit_translation(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要修改的翻译")
            return
        item = selected[0]
        vals = self.tree.item(item, "values")
        fname, old_trans, _ = vals[0].strip(), vals[1].strip(), vals[2].strip()

        new_trans = simpledialog.askstring(
            "修改翻译",
            f"文件：{fname}\n原翻译：{old_trans}",
            initialvalue=old_trans
        )
        if new_trans is None or not new_trans.strip():
            return
        new_trans = new_trans.strip()

        try:
            with open(self.npk_trans_path, "r", encoding=self.trans_file_encoding) as f:
                lines = f.readlines()

            new_lines = []
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    new_lines.append(line)
                    continue
                parts = re.split(r'\s+', line, maxsplit=1)
                if len(parts) < 2:
                    new_lines.append(line)
                    continue
                f = parts[0].strip()
                t = parts[1].strip()
                if f == fname and t == old_trans:
                    new_lines.append(f"{fname} {new_trans}\n")
                else:
                    new_lines.append(line)

            with open(self.npk_trans_path, "w", encoding=self.trans_file_encoding) as f:
                f.writelines(new_lines)

            self.load_word_mapping()
            self.scan_npk_files()
            self.do_search()
        except:
            messagebox.showerror("错误", "修改失败")

    def on_tree_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        fname = self.tree.item(item, "values")[0].lower()
        if fname in self.npk_file_info:
            try:
                os.startfile(self.npk_file_info[fname][2])
            except:
                pass

    def select_npk_root_dir(self):
        d = filedialog.askdirectory()
        if not d:
            return
        self.NPK_ROOT_DIR = d
        self.config["SETTINGS"]["npk_root_dir"] = d
        self.save_config()
        self.update_npk_dir_label()
        self.scan_npk_files()
        self.do_search()

    def scan_npk_files(self):
        self.npk_file_info.clear()
        if not self.NPK_ROOT_DIR or not os.path.isdir(self.NPK_ROOT_DIR):
            messagebox.showwarning("警告", "请选择有效的NPK目录！")
            self.update_npk_dir_label()
            return

        for root_dir, _, files in os.walk(self.NPK_ROOT_DIR):
            for f in files:
                if f.lower().endswith(".npk"):
                    fname_low = f.lower()
                    full_path = os.path.join(root_dir, f)
                    mtime = os.path.getmtime(full_path)
                    time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
                    self.npk_file_info[fname_low] = (f, time_str, full_path)

    def create_widgets(self):
        # 顶部
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=5)
        ttk.Button(top, text="选择NPK目录", command=self.select_npk_root_dir).pack(side="left", padx=5)
        self.npk_dir_label = ttk.Label(top, text="")
        self.npk_dir_label.pack(side="left", padx=5)

        # 搜索
        search_frame = ttk.Frame(self.root)
        search_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(search_frame, text="搜索（空格分隔关键词）：").pack(side="left", padx=5)
        self.sv = tk.StringVar()
        entry = ttk.Entry(search_frame, textvariable=self.sv)
        entry.pack(side="left", fill="x", expand=True, padx=5)
        entry.bind("<Return>", lambda e: self.do_search())
        ttk.Button(search_frame, text="搜索", command=self.do_search).pack(side="left", padx=2)
        ttk.Button(search_frame, text="清空检索框", command=lambda: self.sv.set("") or self.do_search()).pack(side="left", padx=2)

        # 列表
        list_frame = ttk.Frame(self.root)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.style = ttk.Style()
        self.style.configure("Treeview", rowheight=26)
        self.style.map("Treeview", background=[("selected", "#0078d7")])

        self.tree = ttk.Treeview(list_frame, columns=("name", "trans", "time"), show="headings")
        self.tree.heading("name", text="文件名")
        self.tree.heading("trans", text="中文翻译")
        self.tree.heading("time", text="修改时间")
        self.tree.column("name", width=280)
        self.tree.column("trans", width=380)
        self.tree.column("time", width=120)

        scroll_y = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scroll_y.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=scroll_y.set)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # 按钮区：添加翻译 + 修改翻译 + 复制 + 重新加载
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="添加翻译", command=self.add_translation).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="修改翻译", command=self.edit_translation).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="复制选中文件", command=self.copy_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="重新加载映射表", command=self.load_word_mapping).pack(side="left", padx=5)

        # ===================== 新增：右下角红色文本 =====================
        author_label = tk.Label(
            self.root,  # 绑定到主窗口，确保在窗口右下角显示
            text="作者：果冻勇者 QQ912916994 本软件免费使用，请在COLG论坛下载正版",
            fg="red",  # 文本颜色设为红色
            font=("SimHei", 9)  # 设置字体和大小，确保中文正常显示
        )
        # anchor=se 表示东南方向（右下角），padx/pady 控制边距
        author_label.pack(side="bottom", anchor="se", padx=10, pady=5)

    def get_color_tag(self, fname_low):
        if fname_low not in self.filename_color_map:
            color_idx = len(self.filename_color_map) % len(self.row_colors)
            self.filename_color_map[fname_low] = f"color_{color_idx}"
        return self.filename_color_map[fname_low]

    def do_search(self):
        raw = self.sv.get().strip()
        self.tree.delete(*self.tree.get_children())
        self.filename_color_map.clear()

        self.tree.tag_configure("color_0", background=self.row_colors[0])
        self.tree.tag_configure("color_1", background=self.row_colors[1])

        display_rows = []
        for fname_low in self.npk_file_info:
            real_name, time_str, _ = self.npk_file_info[fname_low]
            trans_list = self.npk_trans_dict.get(fname_low, ["无翻译"])
            for t in trans_list:
                display_rows.append((real_name, t, time_str, fname_low))

        keys = [k.strip().lower() for k in raw.split() if k.strip()]
        if keys:
            filtered = []
            for row in display_rows:
                rn, t, ts, fl = row
                nl = fl
                tl = t.lower()
                ok = True
                for k in keys:
                    hit = False
                    if k in nl: hit = True
                    elif k in tl: hit = True
                    elif k in self.mapping_quick_match:
                        for en in self.mapping_quick_match[k]:
                            if en in nl:
                                hit = True
                                break
                    if not hit:
                        ok = False
                        break
                if ok:
                    filtered.append(row)
            display_rows = filtered

        for row in display_rows:
            rn, t, ts, fl = row
            tag = self.get_color_tag(fl)
            self.tree.insert("", "end", values=(rn, t, ts), tags=(tag,))

    def copy_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择")
            return
        to_dir = filedialog.askdirectory()
        if not to_dir:
            return
        copied = set()
        for item in selected:
            fname = self.tree.item(item, "values")[0].lower()
            if fname in copied:
                continue
            if fname in self.npk_file_info:
                try:
                    shutil.copy2(self.npk_file_info[fname][2], to_dir)
                    copied.add(fname)
                except:
                    pass

if __name__ == "__main__":
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
    root = tk.Tk()
    app = NPKSearchTool(root)
    root.mainloop()