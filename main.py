# -*- coding: utf-8 -*-
"""
컬러 팔레트 매니저 - Sigma.K
- 무제한 세트, 세트당 5개 색상 슬롯 (단색 또는 그라데이션)
- 클릭 시 색상 코드(# 제외) 클립보드 자동 복사 (프리미어 프로 Lumetri 색상창 등에 붙여넣기)
- 색상 지정: 포토샵 스타일 커스텀 선택창 / 화면에서 스포이드로 추출
- 하단 미리보기: 흰 배경 / 검정 배경에 자막용 텍스트로 색상·그라데이션 미리보기 (Paperlogy 8ExtraBold)
- colors_data.json 파일에 자동 저장 (쓰기 권한 없으면 AppData로 자동 대체)
"""

import sys
import os
import json
import colorsys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import simpledialog, messagebox

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    from PIL import Image, ImageGrab, ImageTk, ImageDraw, ImageFont
except ImportError:
    Image = ImageGrab = ImageTk = ImageDraw = ImageFont = None

# ---------- 상수 ----------

SLOT_COUNT = 5
SWATCH_SIZE = 78
CARD_PAD = 7          # 흰 카드 안에서 색상 사각형까지의 여백
CARD_RADIUS = 16       # 카드(흰 배경) 모서리 둥글기
COLOR_RADIUS = 11      # 색상 사각형 모서리 둥글기
MAGNIFIER_ZOOM = 8
MAGNIFIER_GRID_PX = 11

TAB_HEIGHT = 32
TAB_RADIUS = 16
TAB_PADX = 16
TAB_FONT = ("맑은 고딕", 10, "bold")

# 라이트 테마 색상
BG = "#f2f2f5"           # 페이지 배경
CARD_BG = "#ffffff"      # 카드/스와치 배경
BORDER = "#e2e2e8"       # 카드 테두리
TEXT_DARK = "#222222"
TEXT_MUTED = "#8a8a92"
TEXT_FAINT = "#c3c3ca"
ACCENT = "#3a7bd5"
TAB_SELECTED_BG = "#1a1a1e"
STATUS_GREEN = "#2fae4e"

PREVIEW_TEXT = "자막 미리보기"
PREVIEW_W = 204
PREVIEW_H = 62
PREVIEW_FONT_SIZE = 24


def draw_rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    """캔버스에 둥근 사각형(알약 모양) 그리기"""
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def safe_log(*args):
    """--noconsole exe에서는 sys.stdout이 None이라 print()가 예외를 던지고
    콜백 안에서 그 예외가 처리되며 응답없음처럼 보일 수 있음 -> 항상 안전하게 무시"""
    try:
        print(*args)
    except Exception:
        pass


def get_base_path():
    """exe로 빌드됐을 때와 스크립트로 실행할 때 모두 올바른 폴더를 반환 (데이터 저장용)"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_asset_path(*parts):
    """PyInstaller onefile 빌드에서도 번들된 자산(폰트/아이콘 등)을 찾을 수 있는 경로 반환"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def get_data_file_path():
    """exe가 있는 폴더에 저장 권한이 없으면(다운로드 폴더 정책, Program Files 등)
    자동으로 사용자 AppData 폴더로 대체 -> '저장 실패' 반복으로 인한 멈춤 방지"""
    base = get_base_path()
    candidate = os.path.join(base, "colors_data.json")
    try:
        test_path = os.path.join(base, ".write_test_tmp")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("test")
        os.remove(test_path)
        return candidate
    except Exception:
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        fallback_dir = os.path.join(appdata, "ColorPaletteManager")
        try:
            os.makedirs(fallback_dir, exist_ok=True)
        except Exception:
            pass
        return os.path.join(fallback_dir, "colors_data.json")


DATA_FILE = get_data_file_path()
FONT_PATH = get_asset_path("assets", "fonts", "Paperlogy-8ExtraBold.ttf")


def apply_window_icon(window):
    """스포이드 모양 아이콘 적용 (ico 우선, 실패 시 png로 대체). 모든 창(메인+다이얼로그)에 적용."""
    try:
        ico_path = get_asset_path("assets", "icon", "icon.ico")
        if os.path.exists(ico_path):
            window.iconbitmap(ico_path)
            return
    except Exception as e:
        safe_log("아이콘(ico) 설정 실패:", e)
    try:
        png_path = get_asset_path("assets", "icon", "icon_32.png")
        if os.path.exists(png_path):
            window._icon_photo_ref = tk.PhotoImage(file=png_path)  # 참조 유지 필요
            window.iconphoto(True, window._icon_photo_ref)
    except Exception as e:
        safe_log("아이콘(png) 설정 실패:", e)


def default_data():
    """저장된 데이터가 아직 없을 때(첫 실행) 기본으로 보여줄 값 - 가독성 좋은 색상 세트를 기본 제공"""
    readability_colors = ["#fe01a9", "#f5e712", "#04f31d", "#18fef8", "#d6f508"]
    return {
        "current_set": 0,
        "set_names": ["가독성"],
        "sets": [[{"type": "solid", "color": c} for c in readability_colors]],
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
            safe_log("데이터 로드 실패, 기본값 사용:", e)
    return default_data()


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        safe_log("저장 실패:", e)


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
    """아래(시작색) -> 위(끝색) 수직 그라데이션 이미지를 생성"""
    sr, sg, sb = hex_to_rgb(start_hex)
    er, eg, eb = hex_to_rgb(end_hex)
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)  # y=0(맨 위)일 때 t=0(끝색), y=h-1(맨 아래)일 때 t=1(시작색)
        r = int(er + (sr - er) * t)
        g = int(eg + (sg - eg) * t)
        b = int(eb + (sb - eb) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def make_rounded_image(fill_img, w, h, radius):
    """이미지를 둥근 사각형 마스크로 잘라 RGBA로 반환"""
    if fill_img.mode != "RGBA":
        fill_img = fill_img.convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(fill_img, (0, 0), mask)
    return out


def make_rounded_solid_image(hex_color, w, h, radius):
    solid = Image.new("RGB", (w, h), hex_to_rgb(hex_color))
    return make_rounded_image(solid, w, h, radius)


def make_rounded_gradient_image(start_hex, end_hex, w, h, radius):
    grad = make_gradient_image(start_hex, end_hex, w, h)
    return make_rounded_image(grad, w, h, radius)


_preview_font_cache = {}


def load_preview_font(size):
    if size in _preview_font_cache:
        return _preview_font_cache[size]
    try:
        font = ImageFont.truetype(FONT_PATH, size)
    except Exception as e:
        safe_log("폰트 로드 실패, 기본 폰트로 대체:", e)
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


PICKER_SQ_SIZE = 200
PICKER_HUE_W = 24
PICKER_HUE_GAP = 14


class PhotoshopColorPicker(tk.Toplevel):
    """포토샵 스타일 색상 선택창 (SV 사각형 + 색상 슬라이더 + 숫자 입력).
    result 속성에 선택한 hex(취소 시 None)가 담김."""

    def __init__(self, master, initial_hex="#ffffff", title_text="색상 선택"):
        super().__init__(master)
        self.title(title_text)
        self.resizable(False, False)
        self.configure(bg="#2b2b2b")
        self.result = None
        self._updating = False

        apply_window_icon(self)
        self.transient(master)

        r, g, b = hex_to_rgb(initial_hex)
        self.h, self.s, self.v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

        self._build_ui()
        self._redraw_hue_bar()
        self._redraw_sv_square()
        self._sync_all_from_hsv()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda e: self._on_cancel())

        self.update_idletasks()
        self.grab_set()
        master.wait_window(self)

    def _build_ui(self):
        outer = tk.Frame(self, bg="#2b2b2b")
        outer.pack(padx=14, pady=14)

        left = tk.Frame(outer, bg="#2b2b2b")
        left.grid(row=0, column=0, sticky="n")

        self.sq_canvas = tk.Canvas(left, width=PICKER_SQ_SIZE, height=PICKER_SQ_SIZE,
                                    highlightthickness=1, highlightbackground="#555", cursor="crosshair")
        self.sq_canvas.grid(row=0, column=0)
        self.sq_canvas.bind("<Button-1>", self._on_sq_click)
        self.sq_canvas.bind("<B1-Motion>", self._on_sq_click)

        self.hue_canvas = tk.Canvas(left, width=PICKER_HUE_W, height=PICKER_SQ_SIZE,
                                     highlightthickness=1, highlightbackground="#555")
        self.hue_canvas.grid(row=0, column=1, padx=(PICKER_HUE_GAP, 0))
        self.hue_canvas.bind("<Button-1>", self._on_hue_click)
        self.hue_canvas.bind("<B1-Motion>", self._on_hue_click)

        right = tk.Frame(outer, bg="#2b2b2b")
        right.grid(row=0, column=1, sticky="n", padx=(18, 0))

        tk.Label(right, text="미리보기", bg="#2b2b2b", fg="#aaaaaa", font=("맑은 고딕", 8)) \
            .grid(row=0, column=0, columnspan=2, sticky="w")
        self.new_swatch = tk.Canvas(right, width=110, height=44, highlightthickness=1, highlightbackground="#555")
        self.new_swatch.grid(row=1, column=0, columnspan=2, pady=(2, 10))

        self.entries = {}
        for i, name in enumerate(["H", "S", "V"]):
            tk.Label(right, text=name, bg="#2b2b2b", fg="#cccccc", font=("Consolas", 9)) \
                .grid(row=2 + i, column=0, sticky="w", pady=2)
            e = tk.Entry(right, width=6, bg="#1e1e1e", fg="#ffffff", insertbackground="#ffffff", relief="flat")
            e.grid(row=2 + i, column=1, sticky="w")
            e.bind("<Return>", self._on_hsv_entry_change)
            e.bind("<FocusOut>", self._on_hsv_entry_change)
            self.entries[name] = e

        for i, name in enumerate(["R", "G", "B"]):
            tk.Label(right, text=name, bg="#2b2b2b", fg="#cccccc", font=("Consolas", 9)) \
                .grid(row=5 + i, column=0, sticky="w", pady=2)
            e = tk.Entry(right, width=6, bg="#1e1e1e", fg="#ffffff", insertbackground="#ffffff", relief="flat")
            e.grid(row=5 + i, column=1, sticky="w")
            e.bind("<Return>", self._on_rgb_entry_change)
            e.bind("<FocusOut>", self._on_rgb_entry_change)
            self.entries[name] = e

        tk.Label(right, text="#", bg="#2b2b2b", fg="#cccccc", font=("Consolas", 9)) \
            .grid(row=8, column=0, sticky="w", pady=(8, 2))
        self.hex_entry = tk.Entry(right, width=10, bg="#1e1e1e", fg="#ffffff", insertbackground="#ffffff", relief="flat")
        self.hex_entry.grid(row=8, column=1, sticky="w", pady=(8, 2))
        self.hex_entry.bind("<Return>", self._on_hex_entry_change)
        self.hex_entry.bind("<FocusOut>", self._on_hex_entry_change)

        btn_frame = tk.Frame(self, bg="#2b2b2b")
        btn_frame.pack(pady=(0, 14))
        tk.Button(btn_frame, text="확인", width=10, command=self._on_ok, bg="#3a7bd5", fg="white").pack(side="left", padx=4)
        tk.Button(btn_frame, text="취소", width=10, command=self._on_cancel).pack(side="left", padx=4)

    def _redraw_hue_bar(self):
        data = []
        for y in range(PICKER_SQ_SIZE):
            hue = y / (PICKER_SQ_SIZE - 1)
            r, g, b = colorsys.hsv_to_rgb(hue, 1, 1)
            data.extend([(int(r * 255), int(g * 255), int(b * 255))] * PICKER_HUE_W)
        img = Image.new("RGB", (PICKER_HUE_W, PICKER_SQ_SIZE))
        img.putdata(data)
        self._hue_photo = ImageTk.PhotoImage(img)
        self.hue_canvas.delete("all")
        self.hue_canvas.create_image(0, 0, image=self._hue_photo, anchor="nw")
        y = int(self.h * (PICKER_SQ_SIZE - 1))
        self.hue_canvas.create_rectangle(0, y - 2, PICKER_HUE_W, y + 2, outline="white", width=2)

    def _redraw_sv_square(self):
        size = PICKER_SQ_SIZE
        data = []
        for y in range(size):
            v = 1 - y / (size - 1)
            for x in range(size):
                s = x / (size - 1)
                r, g, b = colorsys.hsv_to_rgb(self.h, s, v)
                data.append((int(r * 255), int(g * 255), int(b * 255)))
        img = Image.new("RGB", (size, size))
        img.putdata(data)
        self._sq_photo = ImageTk.PhotoImage(img)
        self.sq_canvas.delete("all")
        self.sq_canvas.create_image(0, 0, image=self._sq_photo, anchor="nw")
        x = int(self.s * (size - 1))
        y = int((1 - self.v) * (size - 1))
        marker_color = "white" if self.v < 0.6 else "black"
        self.sq_canvas.create_oval(x - 5, y - 5, x + 5, y + 5, outline=marker_color, width=2)

    def _on_sq_click(self, event):
        x = min(max(event.x, 0), PICKER_SQ_SIZE - 1)
        y = min(max(event.y, 0), PICKER_SQ_SIZE - 1)
        self.s = x / (PICKER_SQ_SIZE - 1)
        self.v = 1 - y / (PICKER_SQ_SIZE - 1)
        self._redraw_sv_square()
        self._sync_all_from_hsv(skip_square=True)

    def _on_hue_click(self, event):
        y = min(max(event.y, 0), PICKER_SQ_SIZE - 1)
        self.h = y / (PICKER_SQ_SIZE - 1)
        self._redraw_hue_bar()
        self._redraw_sv_square()
        self._sync_all_from_hsv(skip_square=True)

    def _on_hsv_entry_change(self, event=None):
        if self._updating:
            return
        try:
            h = max(0, min(360, float(self.entries["H"].get()))) / 360
            s = max(0, min(100, float(self.entries["S"].get()))) / 100
            v = max(0, min(100, float(self.entries["V"].get()))) / 100
        except ValueError:
            return
        self.h, self.s, self.v = h, s, v
        self._redraw_hue_bar()
        self._redraw_sv_square()
        self._sync_all_from_hsv(skip_hsv=True)

    def _on_rgb_entry_change(self, event=None):
        if self._updating:
            return
        try:
            r = max(0, min(255, int(self.entries["R"].get())))
            g = max(0, min(255, int(self.entries["G"].get())))
            b = max(0, min(255, int(self.entries["B"].get())))
        except ValueError:
            return
        self.h, self.s, self.v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        self._redraw_hue_bar()
        self._redraw_sv_square()
        self._sync_all_from_hsv(skip_rgb=True)

    def _on_hex_entry_change(self, event=None):
        if self._updating:
            return
        text = self.hex_entry.get().strip().lstrip("#")
        if len(text) != 6:
            return
        try:
            r, g, b = hex_to_rgb("#" + text)
        except ValueError:
            return
        self.h, self.s, self.v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        self._redraw_hue_bar()
        self._redraw_sv_square()
        self._sync_all_from_hsv(skip_hex=True)

    def _current_hex(self):
        r, g, b = colorsys.hsv_to_rgb(self.h, self.s, self.v)
        return "#%02x%02x%02x" % (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))

    def _sync_all_from_hsv(self, skip_square=False, skip_hsv=False, skip_rgb=False, skip_hex=False):
        self._updating = True
        hexcode = self._current_hex()
        r, g, b = hex_to_rgb(hexcode)
        if not skip_hsv:
            self.entries["H"].delete(0, "end"); self.entries["H"].insert(0, str(round(self.h * 360)))
            self.entries["S"].delete(0, "end"); self.entries["S"].insert(0, str(round(self.s * 100)))
            self.entries["V"].delete(0, "end"); self.entries["V"].insert(0, str(round(self.v * 100)))
        if not skip_rgb:
            self.entries["R"].delete(0, "end"); self.entries["R"].insert(0, str(r))
            self.entries["G"].delete(0, "end"); self.entries["G"].insert(0, str(g))
            self.entries["B"].delete(0, "end"); self.entries["B"].insert(0, str(b))
        if not skip_hex:
            self.hex_entry.delete(0, "end"); self.hex_entry.insert(0, hexcode.lstrip("#"))
        self.new_swatch.delete("all")
        self.new_swatch.create_rectangle(0, 0, 110, 44, fill=hexcode, outline="")
        self._updating = False

    def _on_ok(self):
        self.result = self._current_hex()
        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


class GradientPickerDialog(tk.Toplevel):
    """시작색/끝색을 한 화면에서 명확하게 지정하는 그라데이션 선택창.
    result 속성에 (start_hex, end_hex) 또는 취소 시 None."""

    def __init__(self, master, initial_start="#ffffff", initial_end="#000000"):
        super().__init__(master)
        self.title("그라데이션 만들기")
        self.resizable(False, False)
        self.configure(bg="#2b2b2b")
        self.result = None
        self.start_hex = initial_start
        self.end_hex = initial_end

        apply_window_icon(self)
        self.transient(master)

        tk.Label(self, text="아래(시작)와 위(끝) 색상을 각각 클릭해서 지정하세요",
                 bg="#2b2b2b", fg="#aaaaaa", font=("맑은 고딕", 9)).pack(padx=16, pady=(14, 8))

        row = tk.Frame(self, bg="#2b2b2b")
        row.pack(padx=16)

        start_box = tk.Frame(row, bg="#2b2b2b")
        start_box.grid(row=0, column=0, padx=8)
        tk.Label(start_box, text="시작색 (아래)", bg="#2b2b2b", fg="#cccccc", font=("맑은 고딕", 8)).pack()
        self.start_canvas = tk.Canvas(start_box, width=90, height=90,
                                       highlightthickness=1, highlightbackground="#555", cursor="hand2")
        self.start_canvas.pack(pady=4)
        self.start_canvas.bind("<Button-1>", lambda e: self._pick_start())

        tk.Label(row, text="→", bg="#2b2b2b", fg="#666666", font=("맑은 고딕", 16)).grid(row=0, column=1)

        end_box = tk.Frame(row, bg="#2b2b2b")
        end_box.grid(row=0, column=2, padx=8)
        tk.Label(end_box, text="끝색 (위)", bg="#2b2b2b", fg="#cccccc", font=("맑은 고딕", 8)).pack()
        self.end_canvas = tk.Canvas(end_box, width=90, height=90,
                                     highlightthickness=1, highlightbackground="#555", cursor="hand2")
        self.end_canvas.pack(pady=4)
        self.end_canvas.bind("<Button-1>", lambda e: self._pick_end())

        tk.Label(self, text="미리보기", bg="#2b2b2b", fg="#aaaaaa", font=("맑은 고딕", 8)).pack(pady=(10, 2))
        self.preview_canvas = tk.Canvas(self, width=280, height=40, highlightthickness=1, highlightbackground="#555")
        self.preview_canvas.pack(padx=16)

        btn_frame = tk.Frame(self, bg="#2b2b2b")
        btn_frame.pack(pady=14)
        tk.Button(btn_frame, text="확인", width=10, command=self._on_ok, bg="#3a7bd5", fg="white").pack(side="left", padx=4)
        tk.Button(btn_frame, text="취소", width=10, command=self._on_cancel).pack(side="left", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._refresh()

        self.update_idletasks()
        self.grab_set()
        master.wait_window(self)

    def _refresh(self):
        self.start_canvas.delete("all")
        self.start_canvas.create_rectangle(0, 0, 90, 90, fill=self.start_hex, outline="")
        self.end_canvas.delete("all")
        self.end_canvas.create_rectangle(0, 0, 90, 90, fill=self.end_hex, outline="")

        w, h = 280, 40
        sr, sg, sb = hex_to_rgb(self.start_hex)
        er, eg, eb = hex_to_rgb(self.end_hex)
        img = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(img)
        for x in range(w):
            t = x / (w - 1)
            r = int(sr + (er - sr) * t)
            g = int(sg + (eg - sg) * t)
            b = int(sb + (eb - sb) * t)
            draw.line([(x, 0), (x, h)], fill=(r, g, b))
        self._preview_photo = ImageTk.PhotoImage(img)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(0, 0, image=self._preview_photo, anchor="nw")

    def _pick_start(self):
        picker = PhotoshopColorPicker(self, initial_hex=self.start_hex, title_text="시작색(아래) 선택")
        if picker.result:
            self.start_hex = picker.result
            self._refresh()

    def _pick_end(self):
        picker = PhotoshopColorPicker(self, initial_hex=self.end_hex, title_text="끝색(위) 선택")
        if picker.result:
            self.end_hex = picker.result
            self._refresh()

    def _on_ok(self):
        self.result = (self.start_hex, self.end_hex)
        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


class ColorPaletteApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("컬러 팔레트 매니저 - Sigma.K")
        apply_window_icon(self)
        self.resizable(False, False)
        self.configure(bg=BG)

        self.data = load_data()
        self.set_buttons = []
        self.swatch_widgets = []

        self._build_ui()
        self._rebuild_set_buttons()
        self._refresh_swatches()

        # 첫 실행(혹은 처음 켰을 때) 미리보기가 비어있지 않도록 첫 슬롯 색상을 기본으로 보여줌
        first_slot = self.data["sets"][self.data["current_set"]][0]
        if first_slot:
            self._update_preview(first_slot)

    def _draw_pin(self):
        """항상 위에 고정 버튼 그리기 (켜짐: 파란 원, 꺼짐: 연회색 원)"""
        self.pin_canvas.delete("all")
        active = bool(self.attributes("-topmost"))
        fill = ACCENT if active else "#e4e4ea"
        text_color = "#ffffff" if active else "#6c6c74"
        self.pin_canvas.create_oval(1, 1, TAB_HEIGHT - 1, TAB_HEIGHT - 1, fill=fill, outline="")
        self.pin_canvas.create_text(TAB_HEIGHT / 2, TAB_HEIGHT / 2, text="TOP",
                                     fill=text_color, font=("맑은 고딕", 7, "bold"))

    def _toggle_always_on_top(self):
        current = bool(self.attributes("-topmost"))
        self.attributes("-topmost", not current)
        self._draw_pin()
        self.status_label.config(
            text="항상 위에 고정: 켜짐 (다른 창 위에 계속 표시됩니다)" if not current else "항상 위에 고정: 꺼짐"
        )

    def _scroll_sets(self, direction):
        """세트 탭이 보이는 영역보다 좁으면(스크롤할 게 없으면) 아무 것도 하지 않음 -> 불필요한 위치 이동 방지"""
        self.set_scroll_frame.update_idletasks()
        content_w = self.set_scroll_frame.winfo_reqwidth()
        canvas_w = self.set_canvas.winfo_width()
        if content_w <= canvas_w:
            self.set_canvas.xview_moveto(0)
            return
        self.set_canvas.xview_scroll(direction, "units")

    # ---------- UI 구성 ----------

    def _build_ui(self):
        set_area = tk.Frame(self, bg=BG, height=TAB_HEIGHT)
        set_area.pack(padx=16, pady=(16, 6), fill="x")
        set_area.pack_propagate(False)

        self._make_arrow_button(set_area, "◀", lambda: self._scroll_sets(-2)) \
            .pack(side="left", padx=(0, 4))

        self.set_canvas = tk.Canvas(set_area, height=TAB_HEIGHT, bg=BG,
                                     highlightthickness=0, width=250)
        self.set_canvas.pack(side="left", fill="x", expand=True)

        self._make_arrow_button(set_area, "▶", lambda: self._scroll_sets(2)) \
            .pack(side="left", padx=(4, 6))

        self._make_pill_button(set_area, "+ 세트 추가", self._add_set,
                                fill=ACCENT, text_color="#ffffff").pack(side="left")

        self.pin_canvas = tk.Canvas(set_area, width=TAB_HEIGHT, height=TAB_HEIGHT,
                                     bg=BG, highlightthickness=0, cursor="hand2")
        self.pin_canvas.pack(side="left", padx=(6, 0))
        self.pin_canvas.bind("<Button-1>", lambda e: self._toggle_always_on_top())
        self._draw_pin()

        self.set_scroll_frame = tk.Frame(self.set_canvas, bg=BG)
        self.set_canvas.create_window((0, 0), window=self.set_scroll_frame, anchor="nw")
        self.set_scroll_frame.bind(
            "<Configure>",
            lambda e: self.set_canvas.configure(scrollregion=self.set_canvas.bbox("all"))
        )

        hint = tk.Label(
            self,
            text="세트 더블클릭: 이름 변경 · 세트 우클릭: 삭제  |  색상 좌클릭: 복사 · 색상 우클릭: 지정/그라데이션",
            bg=BG, fg=TEXT_MUTED, font=("맑은 고딕", 9)
        )
        hint.pack(pady=(0, 12), padx=16)

        mid = tk.Frame(self, bg=BG)
        mid.pack(padx=16, pady=4)

        for slot in range(SLOT_COUNT):
            frame = tk.Frame(mid, bg=BG, width=SWATCH_SIZE, height=SWATCH_SIZE + 38)
            frame.grid(row=0, column=slot, padx=8)
            frame.grid_propagate(False)
            frame.pack_propagate(False)

            canvas = tk.Canvas(
                frame, width=SWATCH_SIZE, height=SWATCH_SIZE,
                highlightthickness=0, bg=BG, takefocus=0, cursor="hand2"
            )
            canvas.pack()
            canvas.bind("<Button-1>", lambda e, s=slot: self._on_swatch_click(s))
            canvas.bind("<Button-3>", lambda e, s=slot: self._show_context_menu(e, s))

            label = tk.Label(frame, text="비어있음", bg=BG, fg=TEXT_MUTED,
                              font=("Consolas", 8), wraplength=SWATCH_SIZE, justify="center")
            label.pack(pady=(6, 0))

            self.swatch_widgets.append((frame, canvas, label))

        self.status_label = tk.Label(
            self, text="색상을 클릭하면 클립보드에 복사됩니다.",
            bg=BG, fg=STATUS_GREEN, font=("맑은 고딕", 10, "bold")
        )
        self.status_label.pack(pady=(14, 10))

        # ---- 미리보기 영역 (흰 배경 / 검정 배경) ----
        preview_outer = tk.Frame(self, bg=BG)
        preview_outer.pack(padx=16, pady=(0, 18))

        self.white_canvas = tk.Canvas(preview_outer, width=PREVIEW_W, height=PREVIEW_H,
                                       highlightthickness=1, highlightbackground=BORDER)
        self.white_canvas.grid(row=0, column=0, padx=4)

        self.black_canvas = tk.Canvas(preview_outer, width=PREVIEW_W, height=PREVIEW_H,
                                       highlightthickness=1, highlightbackground=BORDER)
        self.black_canvas.grid(row=0, column=1, padx=4)

        self.white_canvas.create_rectangle(0, 0, PREVIEW_W, PREVIEW_H, fill="#ffffff", outline="")
        self.black_canvas.create_rectangle(0, 0, PREVIEW_W, PREVIEW_H, fill="#000000", outline="")

    # ---------- 버튼 생성 헬퍼 ----------

    def _make_arrow_button(self, parent, text, command):
        """화살표는 세트 탭과 구분되도록 연회색 원형 버튼으로"""
        size = TAB_HEIGHT
        canvas = tk.Canvas(parent, width=size, height=size, bg=BG, highlightthickness=0, cursor="hand2")
        canvas.create_oval(1, 1, size - 1, size - 1, fill="#e4e4ea", outline="")
        canvas.create_text(size / 2, size / 2, text=text, fill="#6c6c74", font=("맑은 고딕", 10, "bold"))
        canvas.bind("<Button-1>", lambda e: command())
        return canvas

    def _make_pill_button(self, parent, text, command, fill, text_color, outline=""):
        font = tkfont.Font(family=TAB_FONT[0], size=TAB_FONT[1], weight="bold")
        w = font.measure(text) + TAB_PADX * 2
        canvas = tk.Canvas(parent, width=w, height=TAB_HEIGHT, bg=BG, highlightthickness=0, cursor="hand2")
        draw_rounded_rect(canvas, 1, 1, w - 1, TAB_HEIGHT - 1, TAB_RADIUS, fill=fill, outline=outline)
        canvas.create_text(w / 2, TAB_HEIGHT / 2, text=text, fill=text_color, font=(TAB_FONT[0], TAB_FONT[1], "bold"))
        canvas.bind("<Button-1>", lambda e: command())
        return canvas

    # ---------- 세트 관리 ----------

    def _draw_tab(self, canvas, idx):
        """탭 캔버스에 알약 배경 + 텍스트를 (다시) 그림. 위젯 자체는 재사용."""
        canvas.delete("all")
        text = self.data["set_names"][idx]
        selected = (idx == self.data["current_set"])
        fill = TAB_SELECTED_BG if selected else CARD_BG
        text_color = "#ffffff" if selected else TEXT_DARK
        outline = "" if selected else BORDER
        w = int(canvas["width"])
        draw_rounded_rect(canvas, 1, 1, w - 1, TAB_HEIGHT - 1, TAB_RADIUS, fill=fill, outline=outline)
        canvas.create_text(w / 2, TAB_HEIGHT / 2, text=text, fill=text_color,
                            font=(TAB_FONT[0], TAB_FONT[1], "bold"))

    def _rebuild_set_buttons(self):
        """세트 개수/이름이 바뀌었을 때만 호출 (위젯을 새로 만듦)"""
        for w in self.set_scroll_frame.winfo_children():
            w.destroy()
        self.set_buttons = []
        font = tkfont.Font(family=TAB_FONT[0], size=TAB_FONT[1], weight="bold")

        for i in range(len(self.data["sets"])):
            text = self.data["set_names"][i]
            w = font.measure(text) + TAB_PADX * 2
            canvas = tk.Canvas(self.set_scroll_frame, width=w, height=TAB_HEIGHT,
                                bg=BG, highlightthickness=0, cursor="hand2")
            canvas.grid(row=0, column=i, padx=3)
            canvas.bind("<Button-1>", lambda e, idx=i: self._switch_set(idx))
            canvas.bind("<Double-Button-1>", lambda e, idx=i: self._rename_set(idx))
            canvas.bind("<Button-3>", lambda e, idx=i: self._delete_set(idx))
            self.set_buttons.append(canvas)
            self._draw_tab(canvas, i)

    def _refresh_tab_colors(self):
        """세트 개수는 그대로, 선택 상태(색상)만 다시 칠함 (위젯은 유지 → 더블클릭 인식 유지)"""
        for i, canvas in enumerate(self.set_buttons):
            self._draw_tab(canvas, i)

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
        self._refresh_tab_colors()
        self._refresh_swatches()

    def _rename_set(self, idx):
        new_name = simpledialog.askstring(
            "세트 이름 변경", "새 이름을 입력하세요:",
            initialvalue=self.data["set_names"][idx], parent=self
        )
        if new_name:
            self.data["set_names"][idx] = new_name.strip()[:12]
            save_data(self.data)
            self._rebuild_set_buttons()

    # ---------- 색상 표시 ----------

    def _refresh_swatches(self):
        current_set = self.data["sets"][self.data["current_set"]]
        inner = SWATCH_SIZE - 2 * CARD_PAD
        for slot, (frame, canvas, label) in enumerate(self.swatch_widgets):
            slot_data = current_set[slot]
            canvas.delete("all")
            canvas.image = None
            draw_rounded_rect(canvas, 0, 0, SWATCH_SIZE - 1, SWATCH_SIZE - 1, CARD_RADIUS,
                               fill=CARD_BG, outline=BORDER)
            if slot_data is None:
                canvas.create_text(SWATCH_SIZE / 2, SWATCH_SIZE / 2, text="+",
                                    fill=TEXT_FAINT, font=("맑은 고딕", 20))
                label.config(text="비어있음")
            elif slot_data["type"] == "solid":
                img = make_rounded_solid_image(slot_data["color"], inner, inner, COLOR_RADIUS)
                photo = ImageTk.PhotoImage(img)
                canvas.image = photo
                canvas.create_image(CARD_PAD, CARD_PAD, image=photo, anchor="nw")
                label.config(text=slot_data["color"].upper())
            else:
                img = make_rounded_gradient_image(slot_data["start"], slot_data["end"], inner, inner, COLOR_RADIUS)
                photo = ImageTk.PhotoImage(img)
                canvas.image = photo
                canvas.create_image(CARD_PAD, CARD_PAD, image=photo, anchor="nw")
                label.config(text=f"{slot_data['start'].upper()}\n{slot_data['end'].upper()}")

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

    def _gradient_code(self, slot_data):
        """간결한 그라데이션 표기 (CSS 유효 문법이 아닌, 이 프로그램 전용의 짧은 표기)"""
        return f"gradient({slot_data['start']}, {slot_data['end']})"

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
            self._copy_to_clipboard(self._gradient_code(slot_data))
        self._update_preview(slot_data)

    def _show_context_menu(self, event, slot):
        current_set = self.data["sets"][self.data["current_set"]]
        slot_data = current_set[slot]

        def deferred(fn):
            """메뉴의 grab이 완전히 풀린 뒤에 실행되도록 지연 -> 다이얼로그와의 grab 충돌(멈춤) 방지"""
            return lambda: self.after(80, fn)

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="🎨 단색 - 팔레트에서 선택", command=deferred(lambda: self._pick_solid_palette(slot)))
        menu.add_command(label="💧 단색 - 화면에서 추출", command=deferred(lambda: self._pick_solid_screen(slot)))
        menu.add_separator()
        menu.add_command(label="🌈 그라데이션 만들기 (팔레트)", command=deferred(lambda: self._pick_gradient_palette(slot)))
        menu.add_command(label="🌈 그라데이션 만들기 (스포이드)", command=deferred(lambda: self._pick_gradient_screen(slot)))

        if slot_data:
            menu.add_separator()
            if slot_data["type"] == "solid":
                menu.add_command(label="📋 색상 코드 복사 (#없이)",
                                  command=deferred(lambda: self._copy_hex(slot_data["color"])))
            else:
                menu.add_command(label="📋 시작색만 복사 (#없이)",
                                  command=deferred(lambda: self._copy_hex(slot_data["start"])))
                menu.add_command(label="📋 끝색만 복사 (#없이)",
                                  command=deferred(lambda: self._copy_hex(slot_data["end"])))
                menu.add_command(label="📋 그라데이션 코드 복사",
                                  command=deferred(lambda: self._copy_to_clipboard(self._gradient_code(slot_data))))
            menu.add_command(label="👁 미리보기에 보기", command=deferred(lambda: self._update_preview(slot_data)))
            menu.add_separator()
            menu.add_command(label="🗑 비우기", command=deferred(lambda: self._clear_slot(slot)))

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ---------- 단색 지정 ----------

    def _pick_solid_palette(self, slot):
        current_set = self.data["sets"][self.data["current_set"]]
        slot_data = current_set[slot]
        initial = slot_data["color"] if slot_data and slot_data["type"] == "solid" else "#ffffff"
        picker = PhotoshopColorPicker(self, initial_hex=initial, title_text="색상 선택")
        if picker.result:
            self._set_slot_solid(slot, picker.result)

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
        current_set = self.data["sets"][self.data["current_set"]]
        slot_data = current_set[slot]
        init_start = slot_data["start"] if slot_data and slot_data["type"] == "gradient" else "#ffffff"
        init_end = slot_data["end"] if slot_data and slot_data["type"] == "gradient" else "#000000"
        dialog = GradientPickerDialog(self, initial_start=init_start, initial_end=init_end)
        if dialog.result:
            start_hex, end_hex = dialog.result
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
                           prompt_text="① 아래쪽(시작) 색상을 클릭하세요  (ESC: 취소)")

    def _launch_gradient_end_overlay(self, slot, start_hex):
        def on_pick_end(end_hex):
            self.deiconify()
            self._set_slot_gradient(slot, start_hex, end_hex)

        def on_cancel():
            self.deiconify()

        EyedropperOverlay(self, on_pick_end, on_cancel,
                           prompt_text="② 위쪽(끝) 색상을 클릭하세요  (ESC: 취소)")

    def _set_slot_gradient(self, slot, start_hex, end_hex):
        start_hex, end_hex = start_hex.lower(), end_hex.lower()
        slot_data = {"type": "gradient", "start": start_hex, "end": end_hex}
        self.data["sets"][self.data["current_set"]][slot] = slot_data
        save_data(self.data)
        self._refresh_swatches()
        self._copy_to_clipboard(self._gradient_code(slot_data))
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
