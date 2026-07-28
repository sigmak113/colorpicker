# -*- coding: utf-8 -*-
"""
컬러 팔레트 매니저
- 무제한 세트, 세트당 5개 색상 슬롯 (단색 또는 그라데이션)
- 클릭 시 색상 코드(# 제외) 클립보드 자동 복사 (프리미어 프로 Lumetri 색상창 등에 붙여넣기)
- 색상 지정: 팔레트에서 선택 / 화면에서 스포이드로 추출
- 하단 미리보기: 흰 배경 / 검정 배경에 자막용 텍스트로 색상·그라데이션 미리보기 (Paperlogy 8ExtraBold)
- colors_data.json 파일에 자동 저장 (exe와 같은 폴더)
"""

import sys
import os
import json
import tkinter as tk
from tkinter import colorchooser, simpledialog, messagebox

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    from PIL import Image, ImageGrab, ImageTk, ImageDraw, ImageFont
except ImportError:
    Image = ImageGrab = ImageTk = ImageDraw = ImageFont = None

SLOT_COUNT = 5
SWATCH_SIZE = 70
MAGNIFIER_ZOOM = 8          # 스포이드 확대 배율
MAGNIFIER_GRID_PX = 11      # 확대해서 보여줄 원본 픽셀 범위 (11x11)

PREVIEW_TEXT = "자막 미리보기"
PREVIEW_W = 204
PREVIEW_H = 62
PREVIEW_FONT_SIZE = 24


def get_base_path():
    """exe로 빌드됐을 때와 스크립트로 실행할 때 모두 올바른 폴더를 반환 (데이터 저장용)"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_asset_path(*parts):
    """PyInstaller onefile 빌드에서도 번들된 자산(폰트 등)을 찾을 수 있는 경로 반환"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


DATA_FILE = os.path.join(get_base_path(), "colors_data.json")
FONT_PATH = get_asset_path("assets", "fonts", "Paperlogy-8ExtraBold.ttf")


def default_data():
    return {
        "current_set": 0,
        "set_names": ["세트 1"],
        "sets": [[None] * SLOT_COUNT],
    }


def migrate_slot(slot):
    """구버전(문자열 hex) 데이터를 새 형식({"type": ...})으로 변환"""
    if slot is None:
        return None
    if isinstance(slot, str):
        return {"type": "solid", "color": slot}
    if isinstance(slot, dict) and slot.get("type") in ("solid", "gradient"):
        return slot
    return None


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)

            raw_sets = raw.get("sets") or [[None] * SLOT_COUNT]
            set_names = raw.get("set_names") or [f"세트 {i + 1}" for i in range(len(raw_sets))]

            migrated_sets = []
            for s in raw_sets:
                s = list(s)
                if len(s) < SLOT_COUNT:
                    s = s + [None] * (SLOT_COUNT - len(s))
                else:
                    s = s[:SLOT_COUNT]
                migrated_sets.append([migrate_slot(slot) for slot in s])

            if len(set_names) < len(migrated_sets):
                set_names = set_names + [f"세트 {i + 1}" for i in range(len(set_names), len(migrated_sets))]
            elif len(set_names) > len(migrated_sets):
                set_names = set_names[:len(migrated_sets)]

            current_set = raw.get("current_set", 0)
            if not (0 <= current_set < len(migrated_sets)):
                current_set = 0

            return {"current_set": current_set, "set_names": set_names, "sets": migrated_sets}
        except Exception as e:
            print("데이터 로드 실패, 기본값 사용:", e)
    return default_data()


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("저장 실패:", e)


def readable_text_color(hex_color):
    """배경색 밝기에 따라 검/흰 텍스트 자동 선택"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b)
    return "#000000" if luminance > 150 else "#ffffff"


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def make_gradient_image(start_hex, end_hex, w, h):
    """좌->우 수평 그라데이션 이미지를 생성"""
    sr, sg, sb = hex_to_rgb(start_hex)
    er, eg, eb = hex_to_rgb(end_hex)
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for x in range(w):
        t = x / max(1, w - 1)
        r = int(sr + (er - sr) * t)
        g = int(sg + (eg - sg) * t)
        b = int(sb + (eb - sb) * t)
        draw.line([(x, 0), (x, h)], fill=(r, g, b))
    return img


_preview_font_cache = {}


def load_preview_font(size):
    if size in _preview_font_cache:
        return _preview_font_cache[size]
    try:
        font = ImageFont.truetype(FONT_PATH, size)
    except Exception as e:
        print("폰트 로드 실패, 기본 폰트로 대체:", e)
        font = ImageFont.load_default()
    _preview_font_cache[size] = font
    return font


def render_preview(slot_data, bg_rgb, w=PREVIEW_W, h=PREVIEW_H):
    """흰/검 배경 위에 자막 텍스트로 색상·그라데이션을 미리보여주는 이미지 생성"""
    img = Image.new("RGB", (w, h), bg_rgb)
    font = load_preview_font(PREVIEW_FONT_SIZE)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), PREVIEW_TEXT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (w - tw) / 2 - bbox[0]
    y = (h - th) / 2 - bbox[1]

    if slot_data["type"] == "solid":
        draw.text((x, y), PREVIEW_TEXT, font=font, fill=slot_data["color"])
    else:
        mask = Image.new("L", (w, h), 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.text((x, y), PREVIEW_TEXT, font=font, fill=255)
        grad = make_gradient_image(slot_data["start"], slot_data["end"], w, h)
        img.paste(grad, (0, 0), mask)
    return img


class EyedropperOverlay(tk.Toplevel):
    """화면 전체를 캡처해서 보여주고, 클릭한 픽셀의 색상을 골라주는 오버레이 창"""

    def __init__(self, master, on_pick, on_cancel=None,
                 prompt_text="화면을 클릭해서 색상을 추출하세요.  (ESC: 취소)"):
        super().__init__(master)
        self.on_pick = on_pick
        self.on_cancel = on_cancel

        if Image is None:
            messagebox.showerror("오류", "Pillow 라이브러리가 설치되어 있지 않습니다.\npip install pillow")
            self.destroy()
            if self.on_cancel:
                self.on_cancel()
            return

        self.screenshot = ImageGrab.grab()
        self.img_w, self.img_h = self.screenshot.size

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{self.img_w}x{self.img_h}+0+0")
        self.config(cursor="crosshair")

        self.tk_bg_image = ImageTk.PhotoImage(self.screenshot)
        self.canvas = tk.Canvas(self, width=self.img_w, height=self.img_h,
                                 highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.tk_bg_image, anchor="nw")

        self.canvas.create_rectangle(0, 0, 480, 34, fill="#111111", outline="")
        self.canvas.create_text(
            10, 17, anchor="w", fill="white",
            text=prompt_text,
            font=("맑은 고딕", 11)
        )

        self.magnifier_id = None
        self.hex_text_id = None
        self.hex_bg_id = None
        self._cancelled_by_click = False

        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Button-1>", self._on_click)
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.focus_force()

    def _get_pixel(self, x, y):
        x = max(0, min(self.img_w - 1, x))
        y = max(0, min(self.img_h - 1, y))
        return self.screenshot.getpixel((x, y))[:3]

    def _on_motion(self, event):
        x, y = event.x, event.y
        r, g, b = self._get_pixel(x, y)
        hex_color = "#%02x%02x%02x" % (r, g, b)

        half = MAGNIFIER_GRID_PX // 2
        left = max(0, x - half)
        top = max(0, y - half)
        right = min(self.img_w, x + half + 1)
        bottom = min(self.img_h, y + half + 1)
        crop = self.screenshot.crop((left, top, right, bottom))
        crop = crop.resize(
            (MAGNIFIER_GRID_PX * MAGNIFIER_ZOOM, MAGNIFIER_GRID_PX * MAGNIFIER_ZOOM),
            Image.NEAREST
        )
        draw = ImageDraw.Draw(crop)
        cx = cy = (MAGNIFIER_GRID_PX * MAGNIFIER_ZOOM) // 2
        s = MAGNIFIER_ZOOM // 2
        draw.rectangle([cx - s, cy - s, cx + s, cy + s], outline="red", width=2)
        self.tk_magnifier_image = ImageTk.PhotoImage(crop)

        mx = x + 25
        my = y + 25
        mag_size = MAGNIFIER_GRID_PX * MAGNIFIER_ZOOM
        if mx + mag_size > self.img_w:
            mx = x - mag_size - 25
        if my + mag_size + 30 > self.img_h:
            my = y - mag_size - 30

        if self.magnifier_id:
            self.canvas.delete(self.magnifier_id)
        if self.hex_text_id:
            self.canvas.delete(self.hex_text_id)
        if self.hex_bg_id:
            self.canvas.delete(self.hex_bg_id)

        self.magnifier_id = self.canvas.create_image(mx, my, image=self.tk_magnifier_image, anchor="nw")
        self.hex_bg_id = self.canvas.create_rectangle(
            mx, my + mag_size, mx + mag_size, my + mag_size + 26,
            fill=hex_color, outline="#222222"
        )
        self.hex_text_id = self.canvas.create_text(
            mx + mag_size / 2, my + mag_size + 13,
            text=hex_color, fill=readable_text_color(hex_color),
            font=("Consolas", 11, "bold")
        )

    def _on_click(self, event):
        r, g, b = self._get_pixel(event.x, event.y)
        hex_color = "#%02x%02x%02x" % (r, g, b)
        self._cancelled_by_click = True
        self.destroy()
        self.on_pick(hex_color)

    def _cancel(self):
        was_click = self._cancelled_by_click
        self.destroy()
        if not was_click and self.on_cancel:
            self.on_cancel()


class ColorPaletteApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("컬러 팔레트 매니저")
        self.resizable(False, False)
        self.configure(bg="#1e1e1e")

        self.data = load_data()
        self.set_buttons = []
        self.swatch_widgets = []

        self._build_ui()
        self._rebuild_set_buttons()
        self._refresh_swatches()

    # ---------- UI 구성 ----------

    def _build_ui(self):
        set_area = tk.Frame(self, bg="#1e1e1e")
        set_area.pack(padx=16, pady=(14, 6), fill="x")

        tk.Button(set_area, text="◀", width=2,
                  command=lambda: self.set_canvas.xview_scroll(-2, "units")).pack(side="left")

        self.set_canvas = tk.Canvas(set_area, height=34, bg="#1e1e1e", highlightthickness=0, width=280)
        self.set_canvas.pack(side="left", fill="x", expand=True, padx=4)

        tk.Button(set_area, text="▶", width=2,
                  command=lambda: self.set_canvas.xview_scroll(2, "units")).pack(side="left")

        tk.Button(set_area, text="+ 세트 추가", command=self._add_set, bg="#3a7bd5", fg="white") \
            .pack(side="left", padx=(6, 0))

        self.set_scroll_frame = tk.Frame(self.set_canvas, bg="#1e1e1e")
        self.set_canvas.create_window((0, 0), window=self.set_scroll_frame, anchor="nw")
        self.set_scroll_frame.bind(
            "<Configure>",
            lambda e: self.set_canvas.configure(scrollregion=self.set_canvas.bbox("all"))
        )

        hint = tk.Label(
            self,
            text="세트 더블클릭: 이름 변경 · 세트 우클릭: 삭제  |  색상 좌클릭: 복사 · 색상 우클릭: 지정/그라데이션",
            bg="#1e1e1e", fg="#9a9a9a", font=("맑은 고딕", 9)
        )
        hint.pack(pady=(0, 10))

        mid = tk.Frame(self, bg="#1e1e1e")
        mid.pack(padx=16, pady=4)

        for slot in range(SLOT_COUNT):
            frame = tk.Frame(mid, bg="#1e1e1e")
            frame.grid(row=0, column=slot, padx=8)

            canvas = tk.Canvas(
                frame, width=SWATCH_SIZE, height=SWATCH_SIZE,
                highlightthickness=1, highlightbackground="#555555", cursor="hand2"
            )
            canvas.pack()
            canvas.bind("<Button-1>", lambda e, s=slot: self._on_swatch_click(s))
            canvas.bind("<Button-3>", lambda e, s=slot: self._show_context_menu(e, s))

            label = tk.Label(frame, text="비어있음", bg="#1e1e1e", fg="#cccccc", font=("Consolas", 9))
            label.pack(pady=(4, 0))

            self.swatch_widgets.append((frame, canvas, label))

        self.status_label = tk.Label(
            self, text="색상을 클릭하면 클립보드에 복사됩니다.",
            bg="#1e1e1e", fg="#4caf50", font=("맑은 고딕", 10, "bold")
        )
        self.status_label.pack(pady=(12, 8))

        # ---- 미리보기 영역 (흰 배경 / 검정 배경) ----
        preview_outer = tk.Frame(self, bg="#1e1e1e")
        preview_outer.pack(padx=16, pady=(0, 16))

        tk.Label(preview_outer, text="자막 미리보기 (Paperlogy 8ExtraBold)",
                 bg="#1e1e1e", fg="#9a9a9a", font=("맑은 고딕", 9)).grid(row=0, column=0, columnspan=2, pady=(0, 4))

        white_box = tk.Frame(preview_outer, bg="#1e1e1e")
        white_box.grid(row=1, column=0, padx=4)
        self.white_canvas = tk.Canvas(white_box, width=PREVIEW_W, height=PREVIEW_H,
                                       highlightthickness=1, highlightbackground="#555555")
        self.white_canvas.pack()
        tk.Label(white_box, text="흰 배경", bg="#1e1e1e", fg="#777777", font=("맑은 고딕", 8)).pack(pady=(2, 0))

        black_box = tk.Frame(preview_outer, bg="#1e1e1e")
        black_box.grid(row=1, column=1, padx=4)
        self.black_canvas = tk.Canvas(black_box, width=PREVIEW_W, height=PREVIEW_H,
                                       highlightthickness=1, highlightbackground="#555555")
        self.black_canvas.pack()
        tk.Label(black_box, text="검정 배경", bg="#1e1e1e", fg="#777777", font=("맑은 고딕", 8)).pack(pady=(2, 0))

        self.white_canvas.create_rectangle(0, 0, PREVIEW_W, PREVIEW_H, fill="#ffffff", outline="")
        self.black_canvas.create_rectangle(0, 0, PREVIEW_W, PREVIEW_H, fill="#000000", outline="")

    # ---------- 세트 관리 ----------

    def _rebuild_set_buttons(self):
        for w in self.set_scroll_frame.winfo_children():
            w.destroy()
        self.set_buttons = []
        for i in range(len(self.data["sets"])):
            btn = tk.Button(self.set_scroll_frame, text=self.data["set_names"][i], width=8)
            btn.grid(row=0, column=i, padx=3)
            btn.config(command=lambda idx=i: self._switch_set(idx))
            btn.bind("<Double-Button-1>", lambda e, idx=i: self._rename_set(idx))
            btn.bind("<Button-3>", lambda e, idx=i: self._delete_set(idx))
            self.set_buttons.append(btn)
        self._refresh_set_buttons()

    def _refresh_set_buttons(self):
        current = self.data["current_set"]
        for i, btn in enumerate(self.set_buttons):
            btn.config(text=self.data["set_names"][i])
            if i == current:
                btn.config(relief="sunken", bg="#3a7bd5", fg="white", activebackground="#3a7bd5")
            else:
                btn.config(relief="raised", bg="#f0f0f0", fg="black")

    def _add_set(self):
        n = len(self.data["sets"]) + 1
        self.data["set_names"].append(f"세트 {n}")
        self.data["sets"].append([None] * SLOT_COUNT)
        self.data["current_set"] = len(self.data["sets"]) - 1
        save_data(self.data)
        self._rebuild_set_buttons()
        self._refresh_swatches()
        self.after(50, lambda: self.set_canvas.xview_moveto(1.0))

    def _delete_set(self, idx):
        if len(self.data["sets"]) <= 1:
            messagebox.showinfo("알림", "마지막 남은 세트는 삭제할 수 없습니다.")
            return
        name = self.data["set_names"][idx]
        if not messagebox.askyesno("세트 삭제", f"'{name}' 세트를 삭제할까요?\n안의 색상도 모두 사라집니다."):
            return
        del self.data["sets"][idx]
        del self.data["set_names"][idx]
        if self.data["current_set"] >= len(self.data["sets"]):
            self.data["current_set"] = len(self.data["sets"]) - 1
        elif self.data["current_set"] > idx:
            self.data["current_set"] -= 1
        save_data(self.data)
        self._rebuild_set_buttons()
        self._refresh_swatches()

    def _switch_set(self, idx):
        self.data["current_set"] = idx
        save_data(self.data)
        self._refresh_set_buttons()
        self._refresh_swatches()

    def _rename_set(self, idx):
        new_name = simpledialog.askstring(
            "세트 이름 변경", "새 이름을 입력하세요:",
            initialvalue=self.data["set_names"][idx], parent=self
        )
        if new_name:
            self.data["set_names"][idx] = new_name.strip()[:12]
            save_data(self.data)
            self._refresh_set_buttons()

    # ---------- 색상 표시 ----------

    def _refresh_swatches(self):
        current_set = self.data["sets"][self.data["current_set"]]
        for slot, (frame, canvas, label) in enumerate(self.swatch_widgets):
            slot_data = current_set[slot]
            canvas.delete("all")
            canvas.image = None
            if slot_data is None:
                canvas.config(bg="#2b2b2b")
                canvas.create_text(SWATCH_SIZE / 2, SWATCH_SIZE / 2, text="+",
                                    fill="#777777", font=("맑은 고딕", 20))
                label.config(text="비어있음")
            elif slot_data["type"] == "solid":
                canvas.config(bg=slot_data["color"])
                label.config(text=slot_data["color"].upper())
            else:
                img = make_gradient_image(slot_data["start"], slot_data["end"], SWATCH_SIZE, SWATCH_SIZE)
                photo = ImageTk.PhotoImage(img)
                canvas.image = photo
                canvas.create_image(0, 0, image=photo, anchor="nw")
                label.config(text=f"{slot_data['start'].upper()}→{slot_data['end'].upper()}")

    def _update_preview(self, slot_data):
        if not slot_data:
            return
        white_img = render_preview(slot_data, (255, 255, 255))
        black_img = render_preview(slot_data, (0, 0, 0))
        self.white_photo = ImageTk.PhotoImage(white_img)
        self.black_photo = ImageTk.PhotoImage(black_img)
        self.white_canvas.delete("all")
        self.white_canvas.create_image(0, 0, image=self.white_photo, anchor="nw")
        self.black_canvas.delete("all")
        self.black_canvas.create_image(0, 0, image=self.black_photo, anchor="nw")

    # ---------- 클립보드 ----------

    def _css_gradient(self, slot_data):
        return f"linear-gradient(90deg, {slot_data['start']}, {slot_data['end']})"

    def _copy_to_clipboard(self, text):
        ok = False
        if pyperclip:
            try:
                pyperclip.copy(text)
                ok = True
            except Exception:
                ok = False
        if not ok:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
        self.status_label.config(text=f"복사됨: {text}")

    def _copy_hex(self, hex_color):
        """프리미어 프로 등에 붙여넣기 위해 # 없이 복사"""
        stripped = hex_color.lstrip("#")
        self._copy_to_clipboard(stripped)

    # ---------- 슬롯 클릭 / 메뉴 ----------

    def _on_swatch_click(self, slot):
        current_set = self.data["sets"][self.data["current_set"]]
        slot_data = current_set[slot]
        if not slot_data:
            self._pick_solid_palette(slot)
            return
        if slot_data["type"] == "solid":
            self._copy_hex(slot_data["color"])
        else:
            self._copy_to_clipboard(self._css_gradient(slot_data))
        self._update_preview(slot_data)

    def _show_context_menu(self, event, slot):
        current_set = self.data["sets"][self.data["current_set"]]
        slot_data = current_set[slot]

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="🎨 단색 - 팔레트에서 선택", command=lambda: self._pick_solid_palette(slot))
        menu.add_command(label="💧 단색 - 화면에서 추출", command=lambda: self._pick_solid_screen(slot))
        menu.add_separator()
        menu.add_command(label="🌈 그라데이션 만들기 (팔레트)", command=lambda: self._pick_gradient_palette(slot))
        menu.add_command(label="🌈 그라데이션 만들기 (스포이드)", command=lambda: self._pick_gradient_screen(slot))

        if slot_data:
            menu.add_separator()
            if slot_data["type"] == "solid":
                menu.add_command(label="📋 색상 코드 복사 (#없이)",
                                  command=lambda: self._copy_hex(slot_data["color"]))
            else:
                menu.add_command(label="📋 시작색만 복사 (#없이)",
                                  command=lambda: self._copy_hex(slot_data["start"]))
                menu.add_command(label="📋 끝색만 복사 (#없이)",
                                  command=lambda: self._copy_hex(slot_data["end"]))
                menu.add_command(label="📋 CSS 코드 복사",
                                  command=lambda: self._copy_to_clipboard(self._css_gradient(slot_data)))
            menu.add_command(label="👁 미리보기에 보기", command=lambda: self._update_preview(slot_data))
            menu.add_separator()
            menu.add_command(label="🗑 비우기", command=lambda: self._clear_slot(slot))

        menu.tk_popup(event.x_root, event.y_root)

    # ---------- 단색 지정 ----------

    def _pick_solid_palette(self, slot):
        current_set = self.data["sets"][self.data["current_set"]]
        slot_data = current_set[slot]
        initial = slot_data["color"] if slot_data and slot_data["type"] == "solid" else "#ffffff"
        rgb, hex_color = colorchooser.askcolor(color=initial, title="색상 선택")
        if hex_color:
            self._set_slot_solid(slot, hex_color)

    def _pick_solid_screen(self, slot):
        self.withdraw()
        self.after(150, lambda: self._launch_solid_overlay(slot))

    def _launch_solid_overlay(self, slot):
        def on_pick(hex_color):
            self.deiconify()
            self._set_slot_solid(slot, hex_color)

        def on_cancel():
            self.deiconify()

        EyedropperOverlay(self, on_pick, on_cancel)

    def _set_slot_solid(self, slot, hex_color):
        hex_color = hex_color.lower()
        slot_data = {"type": "solid", "color": hex_color}
        self.data["sets"][self.data["current_set"]][slot] = slot_data
        save_data(self.data)
        self._refresh_swatches()
        self._copy_hex(hex_color)
        self._update_preview(slot_data)

    # ---------- 그라데이션 지정 ----------

    def _pick_gradient_palette(self, slot):
        _, start_hex = colorchooser.askcolor(title="그라데이션 - ① 시작 색상 선택")
        if not start_hex:
            return
        _, end_hex = colorchooser.askcolor(title="그라데이션 - ② 끝 색상 선택")
        if not end_hex:
            return
        self._set_slot_gradient(slot, start_hex, end_hex)

    def _pick_gradient_screen(self, slot):
        self.withdraw()
        self.after(150, lambda: self._launch_gradient_start_overlay(slot))

    def _launch_gradient_start_overlay(self, slot):
        def on_pick_start(start_hex):
            self.after(150, lambda: self._launch_gradient_end_overlay(slot, start_hex))

        def on_cancel():
            self.deiconify()

        EyedropperOverlay(self, on_pick_start, on_cancel,
                           prompt_text="① 시작 색상을 클릭하세요  (ESC: 취소)")

    def _launch_gradient_end_overlay(self, slot, start_hex):
        def on_pick_end(end_hex):
            self.deiconify()
            self._set_slot_gradient(slot, start_hex, end_hex)

        def on_cancel():
            self.deiconify()

        EyedropperOverlay(self, on_pick_end, on_cancel,
                           prompt_text="② 끝 색상을 클릭하세요  (ESC: 취소)")

    def _set_slot_gradient(self, slot, start_hex, end_hex):
        start_hex, end_hex = start_hex.lower(), end_hex.lower()
        slot_data = {"type": "gradient", "start": start_hex, "end": end_hex}
        self.data["sets"][self.data["current_set"]][slot] = slot_data
        save_data(self.data)
        self._refresh_swatches()
        self._copy_to_clipboard(self._css_gradient(slot_data))
        self._update_preview(slot_data)

    # ---------- 슬롯 비우기 ----------

    def _clear_slot(self, slot):
        self.data["sets"][self.data["current_set"]][slot] = None
        save_data(self.data)
        self._refresh_swatches()
        self.status_label.config(text="슬롯을 비웠습니다.")


if __name__ == "__main__":
    app = ColorPaletteApp()
    app.mainloop()
