#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1024 - Compact (220x280) - Tkinter
紧凑版界面（220x280），保留核心玩法与快捷键：
- 4x4 网格，阶段性目标：先达 1024（提示）然后继续挑战 2048
- 方向键 / WASD 控制
- 撤销（Undo，最多使用次数可配置）、新游戏（New Game）
- 保存最高分到 game1024_compact_highscore.json
- Ctrl+M 最小化，Ctrl+Q 退出

改动说明：
- 新增阶段目标：游戏默认目标为 1024；首次到达 1024 时弹窗提示并把目标升级为 2048；
  达到 2048 时弹窗提示最终胜利。
- 在顶部显示当前目标（Goal: 1024 / Goal: 2048）。
- 其它交互（键盘绑定、生成分布、撤销限制、无 footer 等）保持不变。

运行：python game_1024_compact.py
"""
import tkinter as tk
from tkinter import messagebox
import random
import json
import os
from datetime import datetime
import copy

HS_FILE = "game1024_compact_highscore.json"
SIZE = 4

# Compact layout settings
WINDOW_W = 220
WINDOW_H = 280
CELL_SIZE = 40   # each cell pixel size
CELL_PAD = 4     # gap between cells
BOARD_BG = "#bbada0"

# Undo limit
MAX_UNDOS = 3  # 每局最多可撤销次数

# Spawn distribution / 可修改：数值越大权重越小
# 完整分布（当存在 >=64 时使用）
SPAWN_VALUES_FULL = [2, 4, 8, 16, 32, 64]
SPAWN_WEIGHTS_FULL = [600, 250, 90, 40, 15, 5]

# 受限分布（在未合成出 64 之前使用，只出现 2/4/8）
SPAWN_VALUES_SMALL = [2, 4, 8]
SPAWN_WEIGHTS_SMALL = [800, 160, 40]

# color mapping
COLOR_MAP = {
    0: ("#cdc1b4", "#776e65"),
    2: ("#eee4da", "#776e65"),
    4: ("#ede0c8", "#776e65"),
    8: ("#f2b179", "#f9f6f2"),
    16: ("#f59563", "#f9f6f2"),
    32: ("#f67c5f", "#f9f6f2"),
    64: ("#f65e3b", "#f9f6f2"),
    128: ("#edcf72", "#f9f6f2"),
    256: ("#edcc61", "#f9f6f2"),
    512: ("#edc850", "#f9f6f2"),
    1024: ("#edc53f", "#f9f6f2"),
    2048: ("#edc22e", "#f9f6f2"),
}

def color_for(val):
    return COLOR_MAP.get(val, ("#3c3a32", "#f9f6f2"))

class Game1024Compact:
    def __init__(self, root):
        self.root = root
        self.root.title("1024 - Compact")
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.root.resizable(False, False)

        # top bar small: score and best, buttons compressed
        top = tk.Frame(root)
        top.pack(padx=6, pady=(6, 2), fill="x")

        self.score = 0
        self.best = self.load_best()

        lbl_font = ("Helvetica", 9, "bold")
        btn_font = ("Helvetica", 8)

        self.score_label = tk.Label(top, text=f"Score: {self.score}", font=lbl_font)
        self.score_label.pack(side="left", padx=(0,6))
        self.best_label = tk.Label(top, text=f"Best: {self.best}", font=lbl_font)
        self.best_label.pack(side="left", padx=(0,6))
        # add goal label to show current objective (starts at 1024)
        self.goal = 1024
        self.goal_label = tk.Label(top, text=f"Goal: {self.goal}", font=lbl_font)
        self.goal_label.pack(side="left", padx=(0,6))

        btn_frame = tk.Frame(top)
        btn_frame.pack(side="right")
        self.new_btn = tk.Button(btn_frame, text="New", command=self.new_game, width=6, font=btn_font)
        self.new_btn.pack(side="left", padx=2)
        self.undo_btn = tk.Button(btn_frame, text="Undo", command=self.undo, width=6, font=btn_font)
        self.undo_btn.pack(side="left", padx=2)

        # board frame sized tightly
        board_frame = tk.Frame(root, bg=BOARD_BG)
        board_frame.pack(padx=6, pady=6)
        # create internal frame to hold cells with exact size
        self.cell_frames = [[None]*SIZE for _ in range(SIZE)]
        self.cells = [[None]*SIZE for _ in range(SIZE)]

        for r in range(SIZE):
            for c in range(SIZE):
                f = tk.Frame(board_frame, bg="#cdc1b4", width=CELL_SIZE, height=CELL_SIZE)
                f.grid(row=r, column=c, padx=CELL_PAD, pady=CELL_PAD)
                f.grid_propagate(False)
                lbl = tk.Label(f, text="", bg="#cdc1b4", fg="#776e65", font=("Helvetica", 12, "bold"))
                lbl.place(relx=0.5, rely=0.5, anchor="center")
                self.cell_frames[r][c] = f
                self.cells[r][c] = lbl

        # No footer (user requested removal)

        # game state
        self.grid = [[0]*SIZE for _ in range(SIZE)]
        self.prev_grid = None
        self.prev_score = 0

        # undo tracking
        self.undos_used = 0
        self.update_undo_button()

        # binds
        root.bind("<Up>", lambda e: self.move("up"))
        root.bind("<Down>", lambda e: self.move("down"))
        root.bind("<Left>", lambda e: self.move("left"))
        root.bind("<Right>", lambda e: self.move("right"))
        root.bind("w", lambda e: self.move("up"))
        root.bind("s", lambda e: self.move("down"))
        root.bind("a", lambda e: self.move("left"))
        root.bind("d", lambda e: self.move("right"))
        root.bind("<Control-m>", lambda e: root.iconify())
        root.bind("<Control-q>", lambda e: self.quit_game())

        # start game
        self.new_game()

    def update_undo_button(self):
        """更新撤销按钮文本和状态（根据剩余次数）"""
        remaining = max(0, MAX_UNDOS - self.undos_used)
        self.undo_btn.config(text=f"Undo ({remaining})")
        if remaining <= 0:
            self.undo_btn.config(state="disabled")
        else:
            self.undo_btn.config(state="normal")

    def load_best(self):
        if not os.path.exists(HS_FILE):
            return 0
        try:
            with open(HS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("best", 0)
        except Exception:
            return 0

    def save_best(self):
        try:
            data = {"best": self.best, "updated_at": datetime.utcnow().isoformat() + "Z"}
            with open(HS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def new_game(self):
        self.grid = [[0]*SIZE for _ in range(SIZE)]
        self.score = 0
        self.prev_grid = None
        self.prev_score = 0
        # reset undo counter & goal for new game
        self.undos_used = 0
        self.update_undo_button()
        self.goal = 1024
        self.goal_label.config(text=f"Goal: {self.goal}")
        self.spawn()
        self.spawn()
        self.update_ui()

    def undo(self):
        """撤销一次：仅在有 prev_grid 且未超过次数限制时生效"""
        remaining = MAX_UNDOS - self.undos_used
        if remaining <= 0:
            # safety: should be disabled already
            messagebox.showinfo("Undo", "The number of retractions has been exhausted.")
            return
        if self.prev_grid is None:
            messagebox.showinfo("Undo", "There are no operations that can be revoked。")
            return
        # 执行撤销
        self.grid = copy.deepcopy(self.prev_grid)
        self.score = self.prev_score
        self.prev_grid = None
        self.prev_score = 0
        # 增加撤销计数并更新按钮
        self.undos_used += 1
        self.update_undo_button()
        self.update_ui()

    def spawn(self):
        """
        根据当前棋盘状况选择生成分布：
        - 如果棋盘上尚未出现 >=64 的格子，则只从 SPAWN_VALUES_SMALL 中按权重抽取（以保证更多 2/4/8）
        - 否则使用完整分布 SPAWN_VALUES_FULL
        使用 random.choices（若不可用则用手动按权重抽样）。
        """
        empty = [(r,c) for r in range(SIZE) for c in range(SIZE) if self.grid[r][c] == 0]
        if not empty:
            return
        r, c = random.choice(empty)

        # 检查当前最大格子，判断是否已合成 64
        current_max = max(self.grid[r0][c0] for r0 in range(SIZE) for c0 in range(SIZE))
        if current_max < 64:
            values = SPAWN_VALUES_SMALL
            weights = SPAWN_WEIGHTS_SMALL
        else:
            values = SPAWN_VALUES_FULL
            weights = SPAWN_WEIGHTS_FULL

        try:
            val = random.choices(values, weights=weights, k=1)[0]
        except AttributeError:
            # 兼容旧 Python：手动按权重抽样
            total = sum(weights)
            pick = random.uniform(0, total)
            cum = 0.0
            val = values[-1]
            for v, w in zip(values, weights):
                cum += w
                if pick <= cum:
                    val = v
                    break

        self.grid[r][c] = val

    def update_ui(self):
        for r in range(SIZE):
            for c in range(SIZE):
                val = self.grid[r][c]
                lbl = self.cells[r][c]
                bg, fg = color_for(val)
                frame = self.cell_frames[r][c]
                frame.config(bg=bg)
                lbl.config(text=str(val) if val != 0 else "", bg=bg, fg=fg)
        self.score_label.config(text=f"Score: {self.score}")
        if self.score > self.best:
            self.best = self.score
            self.best_label.config(text=f"Best: {self.best}")
            self.save_best()

    def compress(self, row):
        new = [v for v in row if v != 0]
        changed = len(new) != len(row)
        new += [0] * (SIZE - len(new))
        return new, changed

    def merge_row(self, row):
        gained = 0
        changed = False
        for i in range(SIZE-1):
            if row[i] != 0 and row[i] == row[i+1]:
                row[i] *= 2
                row[i+1] = 0
                gained += row[i]
                changed = True
        return row, gained, changed

    def move_left(self):
        moved = False
        gained = 0
        new_grid = []
        for r in range(SIZE):
            row = list(self.grid[r])
            row, _ = self.compress(row)
            mrow, g, _ = self.merge_row(row)
            row, _ = self.compress(mrow)
            new_grid.append(row)
            if row != self.grid[r]:
                moved = True
            gained += g
        if moved:
            self.grid = new_grid
        return moved, gained

    def rotate_clock(self, grid):
        """顺时针旋转 90 度一次（不改变原 grid）"""
        size = len(grid)
        return [[grid[size-1-c][r] for c in range(size)] for r in range(size)]

    def rotate(self, grid, times):
        """顺时针旋转 times 次（times 可为 0..3）"""
        times = times % 4
        g = [row[:] for row in grid]
        for _ in range(times):
            g = self.rotate_clock(g)
        return g

    def move(self, direction):
        """
        使用显式旋转次数把任意方向转换为向左移动，映射为：
          left  -> 0
          up    -> 3
          right -> 2
          down  -> 1
        先顺时针旋转 times 次 -> 在旋转后的网格上做向左移动 -> 再旋回原位。
        """
        if direction not in ("left","right","up","down"):
            return

        # 保存用于 undo 的状态（仅在发生移动时才算一次 undo 可用）
        self.prev_grid = copy.deepcopy(self.grid)
        self.prev_score = self.score

        mapping = {
            "left": 0,
            "up": 3,     # 按上键要旋3次顺时针使原来的“上”对齐到“左”
            "right": 2,
            "down": 1,
        }
        times = mapping[direction]

        # 先把网格按 times 顺时针旋转
        rotated = self.rotate(self.grid, times)

        # 在旋转后的网格上做向左移动
        self.grid = rotated
        moved, gained = self.move_left()
        # move_left 已经在需要时修改了 self.grid；取回结果并旋回原位
        rotated_result = self.grid
        self.grid = self.rotate(rotated_result, (4 - times) % 4)

        if not moved:
            # 没动的话不允许 undo（清除保存的 prev）
            self.prev_grid = None
            self.prev_score = 0
            return

        self.score += gained
        self.spawn()
        self.update_ui()

        # 检查并升级阶段目标（1024 -> 2048）
        self.check_and_upgrade_goal()

        # 检查最终胜利（当目标为 2048 且已达成）
        if self.check_win():
            self.update_ui()
            messagebox.showinfo("You win!", f"Congratulations, you have achieved it {self.goal}！score：{self.score}")
        elif self.check_gameover():
            self.update_ui()
            messagebox.showinfo("Game Over", f"There are no available moves left. score：{self.score}")

    def check_and_upgrade_goal(self):
        """如果当前棋盘达到了当前 goal：
           - 若 goal==1024：升级到 2048（弹窗提示），继续游戏
           - 若 goal==2048：保持（由 check_win 处理最终胜利）
        """
        current_max = max(self.grid[r][c] for r in range(SIZE) for c in range(SIZE))
        if current_max >= self.goal:
            if self.goal == 1024:
                # 升级为 2048，提示并继续游戏
                self.goal = 2048
                self.goal_label.config(text=f"Goal: {self.goal}")
                messagebox.showinfo("Milestone", "Congratulations, you have achieved 1024！Challenge 2048 begins！")
            # if already 2048, leave for check_win to show final message

    def check_win(self):
        """只有当当前 goal 为 2048 且棋盘上存在 >=2048 时才视为最终胜利"""
        if self.goal != 2048:
            return False
        for r in range(SIZE):
            for c in range(SIZE):
                if self.grid[r][c] >= 2048:
                    return True
        return False

    def check_gameover(self):
        for r in range(SIZE):
            for c in range(SIZE):
                if self.grid[r][c] == 0:
                    return False
        for r in range(SIZE):
            for c in range(SIZE):
                v = self.grid[r][c]
                if r+1 < SIZE and self.grid[r+1][c] == v:
                    return False
                if c+1 < SIZE and self.grid[r][c+1] == v:
                    return False
        return True

    def quit_game(self):
        self.save_best()
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = Game1024Compact(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
