#!/usr/bin/env python3

import pygame
import random
import colorsys
import math
import collections
import sys
import time
import webbrowser

# --- CONFIG & SETUP ---
pygame.init()
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
BLOCK_SIZE = 30

GRID_WIDTH = 10
GRID_HEIGHT = 20

BOARD_START_X = (SCREEN_WIDTH - (GRID_WIDTH * BLOCK_SIZE)) // 2
BOARD_START_Y = (SCREEN_HEIGHT - (GRID_HEIGHT * BLOCK_SIZE)) // 2

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Neon Tetris By Liam's Electronics Lab")

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)
large_font = pygame.font.SysFont(None, 64)
# hyperlink font (slightly smaller)
link_font = pygame.font.SysFont(None, 20, bold=True)

# hyperlink config
HYPERLINK_TEXT = "Made By Liam's Electronics Lab"
HYPERLINK_URL = "https://www.youtube.com/@Slot1Gamer/videos"
HYPERLINK_MARGIN = 10  # px from window edges
HYPERLINK_GLOW_LAYERS = 6
HYPERLINK_BASE_ALPHA = 160

# --- VISUAL TUNABLES (adjust for performance) ---
GLOW_LAYERS = 2            # more layers for smoother falloff
GLOW_SPREAD = BLOCK_SIZE * 3  # how far glow spreads (in pixels)
BLOOM_SCALE = 90           # downscale factor for bloom blur (higher = softer blur)
BLOOM_INTENSITY = 0.22    # stronger bloom
ACCUM_DECAY = 0.90        # motion trail persistence (0..1) higher = longer trails
PARTICLE_COUNT = 30
PARTICLE_LIFE = 9000      # embers live long
PARTICLE_WISP_LENGTH = 18
PARTICLE_DRIFT = 0.50
MAX_PARTICLES = 1200
EXPLOSION_TOTAL_PER_LINE = 300
EXPLOSION_BATCH_SIZE = 40
EXPLOSION_LIFE = 2200
DOWN_PRESS_BURST = 50

# --- SHAPES ---
SHAPES = [
    [[1, 1, 1, 1]],  # I
    [[1, 1], [1, 1]],  # O
    [[0, 1, 0], [1, 1, 1]],  # T
    [[0, 1, 1], [1, 1, 0]],  # S
    [[1, 1, 0], [0, 1, 1]],  # Z
    [[1, 0, 0], [1, 1, 1]],  # J
    [[0, 0, 1], [1, 1, 1]]   # L
]
SHAPE_KEYS = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']

BASE_HUES = {
    'I': 0.00,
    'O': 0.12,
    'T': 0.24,
    'S': 0.36,
    'Z': 0.48,
    'J': 0.66,
    'L': 0.78
}

# --- UTILITIES ---
def hsv_to_rgb255(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
    return int(r * 255), int(g * 255), int(b * 255)

def neon_color_for(key, x, y, t_ms):
    base = BASE_HUES.get(key, 0.0)
    pos_offset = (x * 0.03 + y * 0.02)
    time_offset = (t_ms % 9000) / 9000.0
    hue = (base + pos_offset + time_offset) % 1.0
    return hsv_to_rgb255(hue, 0.98, 0.98)

# --- PIECE CLASS ---
class Piece:
    def __init__(self, x, y, shape_index):
        self.x = x
        self.y = y
        self.shape = [row[:] for row in SHAPES[shape_index]]
        self.color_key = SHAPE_KEYS[shape_index]

    def rotate(self):
        self.shape = [list(row) for row in zip(*self.shape[::-1])]

# --- VALIDATION ---
def valid_space(piece, locked_positions):
    for y, row in enumerate(piece.shape):
        for x, cell in enumerate(row):
            if cell:
                pos_y = piece.y + y
                pos_x = piece.x + x
                if pos_x < 0 or pos_x >= GRID_WIDTH:
                    return False
                if pos_y >= GRID_HEIGHT:
                    return False
                if pos_y >= 0 and (pos_y, pos_x) in locked_positions:
                    return False
    return True

# --- PARTICLES (long-lived wispy embers) ---
class Particle:
    __slots__ = ("x","y","vx","vy","color","created_ms","life_ms","history","size","noise_phase","speed_scale")
    def __init__(self, x=0.0, y=0.0, color_rgb=(255,255,255), created_ms=0, life_ms=1000, speed_scale=1.0):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.color = color_rgb
        self.created_ms = created_ms
        self.life_ms = life_ms
        self.history = collections.deque(maxlen=PARTICLE_WISP_LENGTH)
        self.history.append((self.x, self.y))
        self.size = 2.0
        self.noise_phase = random.random() * 10.0
        self.speed_scale = speed_scale

    def init_particle(self, x, y, color_rgb, created_ms, life_ms, speed_scale=1.0, vx=None, vy=None):
        self.x = x
        self.y = y
        self.color = color_rgb
        self.created_ms = created_ms
        self.life_ms = life_ms
        self.history.clear()
        self.history.append((self.x, self.y))
        self.size = max(1.2, random.uniform(1.2, 3.6) * (0.9 + 0.2 * speed_scale))
        self.noise_phase = random.random() * 10.0
        self.speed_scale = speed_scale
        if vx is None:
            self.vx = random.uniform(-0.6, 0.6) * 0.25 * speed_scale
        else:
            self.vx = vx
        if vy is None:
            self.vy = random.uniform(-0.6, -0.1) * 0.25 * speed_scale
        else:
            self.vy = vy

    def update(self, dt, now):
        t = dt / 16.67
        self.vy += 0.01 * t * self.speed_scale
        self.noise_phase += 0.01 * t
        drift = math.sin(self.noise_phase * 1.8) * PARTICLE_DRIFT * (0.6 + 0.8 * (self.speed_scale - 1))
        self.vx += drift * t
        self.vx *= 0.998
        self.vy *= 0.998
        self.x += self.vx * t
        self.y += self.vy * t
        self.history.append((self.x, self.y))

    def alive(self, now):
        return (now - self.created_ms) <= self.life_ms

    def draw_wisp(self, surf, now):
        age = now - self.created_ms
        life = self.life_ms
        if age < 0 or age > life:
            return
        fade = 1.0 - (age / life)
        points = list(self.history)
        if len(points) < 2:
            self.draw_simple(surf, now)
            return
        r,g,b = self.color
        steps = min(len(points), 8)
        for i in range(steps):
            idx = -1 - i
            px = int(points[idx][0] * BLOCK_SIZE + BOARD_START_X)
            py = int(points[idx][1] * BLOCK_SIZE + BOARD_START_Y)
            a = (i / max(1, steps-1))
            alpha = int(200 * (fade ** 1.1) * (1.0 - a))
            s = max(1, int(self.size * (1.0 - 0.12 * i)))
            p = pygame.Surface((s*3, s*3), pygame.SRCALPHA)
            pygame.draw.circle(p, (r, g, b, alpha), (s, s), s)
            surf.blit(p, (px - s, py - s), special_flags=pygame.BLEND_ADD)
        # head
        hx = int(points[-1][0] * BLOCK_SIZE + BOARD_START_X)
        hy = int(points[-1][1] * BLOCK_SIZE + BOARD_START_Y)
        head_surf = pygame.Surface((int(self.size*4), int(self.size*4)), pygame.SRCALPHA)
        pygame.draw.circle(head_surf, (r, g, b, int(220 * (fade ** 1.1))), (int(self.size*2), int(self.size*2)), int(self.size))
        surf.blit(head_surf, (hx - int(self.size*2), hy - int(self.size*2)), special_flags=pygame.BLEND_ADD)

    def draw_simple(self, surf, now):
        age = now - self.created_ms
        life = self.life_ms
        if age < 0 or age > life:
            return
        fade = 1.0 - (age / life)
        r,g,b = self.color
        alpha = int(220 * (fade ** 1.2))
        s = max(1, int(self.size))
        px = int(self.x * BLOCK_SIZE + BOARD_START_X)
        py = int(self.y * BLOCK_SIZE + BOARD_START_Y)
        p = pygame.Surface((s*3, s*3), pygame.SRCALPHA)
        pygame.draw.circle(p, (r,g,b,alpha), (s, s), s)
        surf.blit(p, (px - s, py - s), special_flags=pygame.BLEND_ADD)

# --- GLOW: radial gradient cache for very soft glow ---
_glow_cache = {}
def make_radial_glow(color_rgb, radius):
    """
    Create a soft radial gradient surface for the given color and radius.
    Cached by (color, radius) to avoid recomputation.
    """
    key = (color_rgb, radius)
    if key in _glow_cache:
        return _glow_cache[key]
    size = max(2, int(radius * 2))
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    r, g, b = color_rgb
    # draw concentric circles from outer (low alpha) to inner (higher alpha)
    # use quadratic falloff for smoothness
    max_alpha = 160
    for i in range(radius, 0, -1):
        frac = (i / radius)
        alpha = int(max_alpha * (frac ** 2))
        pygame.draw.circle(surf, (r, g, b, alpha), (radius, radius), i)
    _glow_cache[key] = surf
    return surf

def add_soft_glow(target_surf, grid_x, grid_y, color_rgb, layer_index, max_layers):
    """
    Use a precomputed radial gradient and scale it to the desired spread.
    This produces a very soft, smooth glow (non-pixelated).
    """
    px = grid_x * BLOCK_SIZE + BOARD_START_X
    py = grid_y * BLOCK_SIZE + BOARD_START_Y
    # compute radius for this layer (spread increases with layer index)
    base_radius = GLOW_SPREAD // 2
    # smaller inner layers, larger outer layers
    radius = int(base_radius * (0.5 + (layer_index / max(1, max_layers)) * 1.6))
    glow = make_radial_glow(color_rgb, radius)
    # scale glow smoothly to exact size (optional)
    size = radius * 2
    # center the glow on the block
    gx = px - (size - BLOCK_SIZE) // 2
    gy = py - (size - BLOCK_SIZE) // 2
    target_surf.blit(glow, (gx, gy), special_flags=pygame.BLEND_ADD)

def draw_solid_block(surface, grid_x, grid_y, color_rgb, alpha=255):
    px = grid_x * BLOCK_SIZE + BOARD_START_X
    py = grid_y * BLOCK_SIZE + BOARD_START_Y
    block = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
    block.fill((*color_rgb, alpha))
    surface.blit(block, (px, py))
    # crisp thin highlight
    highlight = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE // 6), pygame.SRCALPHA)
    hr, hg, hb = min(255, color_rgb[0] + 90), min(255, color_rgb[1] + 90), min(255, color_rgb[2] + 90)
    highlight.fill((hr, hg, hb, 140))
    surface.blit(highlight, (px, py))

def draw_black_outline(surface, grid_x, grid_y, thickness=2):
    px = grid_x * BLOCK_SIZE + BOARD_START_X
    py = grid_y * BLOCK_SIZE + BOARD_START_Y
    rect = pygame.Rect(px, py, BLOCK_SIZE, BLOCK_SIZE)
    pygame.draw.rect(surface, (0, 0, 0), rect, thickness)

# --- GRID & ROW CLEARING ---
def clear_rows(locked_positions):
    lines_cleared = 0
    for row in range(GRID_HEIGHT - 1, -1, -1):
        full = True
        for col in range(GRID_WIDTH):
            if (row, col) not in locked_positions:
                full = False
                break
        if full:
            lines_cleared += 1
            for col in range(GRID_WIDTH):
                if (row, col) in locked_positions:
                    del locked_positions[(row, col)]
            new_locked = {}
            for (r, c), key in locked_positions.items():
                if r < row:
                    new_locked[(r + 1, c)] = key
                else:
                    new_locked[(r, c)] = key
            locked_positions.clear()
            locked_positions.update(new_locked)
    return lines_cleared

# --- SURFACES FOR EFFECTS ---
accum_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
bloom_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
frame_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

# --- PARTICLE POOL ---
particle_pool = [Particle() for _ in range(MAX_PARTICLES)]
pool_index = 0
def get_particle_from_pool():
    global pool_index
    p = particle_pool[pool_index]
    pool_index = (pool_index + 1) % MAX_PARTICLES
    return p

# --- HYPERLINK RENDERING & INTERACTION ---
def draw_rainbow_hyperlink(target_surf, t_ms, hover=False):
    """
    Draw rainbow glowing hyperlink in bottom-right corner.
    Returns the rect (in screen coordinates) used for the link.
    """
    # render base text (opaque) to measure size
    base_surf = link_font.render(HYPERLINK_TEXT, True, (255, 255, 255))
    text_w, text_h = base_surf.get_size()
    # position bottom-right with margin
    br_x = SCREEN_WIDTH - HYPERLINK_MARGIN
    br_y = SCREEN_HEIGHT - HYPERLINK_MARGIN
    rect = pygame.Rect(br_x - text_w, br_y - text_h, text_w, text_h)

    # animated hue offset
    time_offset = (t_ms % 4000) / 4000.0  # 4s cycle
    intensity_scale = 1.4 if hover else 1.0

    # draw multiple colored layers for rainbow glow (outer -> inner)
    for layer in range(HYPERLINK_GLOW_LAYERS, 0, -1):
        frac = layer / HYPERLINK_GLOW_LAYERS
        # hue shifts across the text and over time
        hue = (time_offset + frac * 0.25) % 1.0
        rgb = hsv_to_rgb255(hue, 0.95, 0.95)
        alpha = int(HYPERLINK_BASE_ALPHA * (frac ** 1.2) * intensity_scale)
        # render text in this color
        col_surf = link_font.render(HYPERLINK_TEXT, True, rgb)
        # create glow surface by blitting colored text with additive blending and slight scale/blur effect
        glow = pygame.Surface((text_w + layer*6, text_h + layer*6), pygame.SRCALPHA)
        # center text in glow surface
        gx = (glow.get_width() - text_w) // 2
        gy = (glow.get_height() - text_h) // 2
        # draw multiple slightly offset copies to simulate soft spread
        spread = int(2 + layer * 1.2)
        step = max(1, spread // 2)
        for ox in range(-spread, spread+1, step):
            for oy in range(-spread, spread+1, step):
                tmp = col_surf.copy()
                tmp.set_alpha(max(8, alpha // (1 + abs(ox) + abs(oy))))
                glow.blit(tmp, (gx + ox, gy + oy), special_flags=pygame.BLEND_ADD)
        # position glow so its center aligns with rect
        glow_x = rect.x - (glow.get_width() - text_w) // 2
        glow_y = rect.y - (glow.get_height() - text_h) // 2
        target_surf.blit(glow, (glow_x, glow_y), special_flags=pygame.BLEND_ADD)

    # draw black outline by blitting black text slightly offset in 8 directions
    black_surf = link_font.render(HYPERLINK_TEXT, True, (0, 0, 0))
    offsets = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)]
    for ox, oy in offsets:
        target_surf.blit(black_surf, (rect.x + ox, rect.y + oy))

    # finally draw crisp white text on top
    white_surf = link_font.render(HYPERLINK_TEXT, True, (255, 255, 255))
    target_surf.blit(white_surf, (rect.x, rect.y))

    # underline
    underline_y = rect.y + rect.height - 2
    underline_color = (255, 255, 255)
    underline_alpha = 220 if hover else 140
    underline_surf = pygame.Surface((rect.width, 2), pygame.SRCALPHA)
    underline_surf.fill((*underline_color, underline_alpha))
    target_surf.blit(underline_surf, (rect.x, underline_y))

    return rect

# --- MAIN GAME ---
def main(screen):
    running = True
    locked_positions = {}
    embers = []
    explosion_queue = []
    explosion_particles = []
    explosion_active = False
    explosion_start = 0

    current_piece = Piece(GRID_WIDTH // 2 - 2, -1, random.randint(0, len(SHAPES) - 1))
    next_piece = Piece(GRID_WIDTH // 2 - 2, -1, random.randint(0, len(SHAPES) - 1))

    base_fall_speed = 500  # base milliseconds per drop
    last_fall = pygame.time.get_ticks()
    score = 0

    # track hyperlink rect for interaction
    link_rect = None
    hand_cursor = pygame.SYSTEM_CURSOR_HAND
    arrow_cursor = pygame.SYSTEM_CURSOR_ARROW
    using_hand = False

    while running:
        dt = clock.tick(60)
        now = pygame.time.get_ticks()

        # compute dynamic fall speed multiplier based on score
        # every 600 points increases speed by 0.2x, capped at 3x
        multiplier = 1.0 + 0.2 * (score // 600)
        multiplier = min(3.0, multiplier)
        fall_speed = int(base_fall_speed / multiplier)

        pressed_down = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if link_rect and link_rect.collidepoint(mx, my):
                    # open URL in default browser
                    try:
                        webbrowser.open(HYPERLINK_URL, new=2)
                    except Exception:
                        pass
            if event.type == pygame.KEYDOWN:
                moved = False
                if event.key == pygame.K_LEFT:
                    current_piece.x -= 1
                    if not valid_space(current_piece, locked_positions):
                        current_piece.x += 1
                    else:
                        moved = True
                elif event.key == pygame.K_RIGHT:
                    current_piece.x += 1
                    if not valid_space(current_piece, locked_positions):
                        current_piece.x -= 1
                    else:
                        moved = True
                elif event.key == pygame.K_DOWN:
                    current_piece.y += 1
                    pressed_down = True
                    if not valid_space(current_piece, locked_positions):
                        current_piece.y -= 1
                    else:
                        moved = True
                        for y, row in enumerate(current_piece.shape):
                            for x, cell in enumerate(row):
                                if cell:
                                    gx = current_piece.x + x
                                    gy = current_piece.y + y
                                    if 0 <= gx < GRID_WIDTH and 0 <= gy < GRID_HEIGHT:
                                        color = neon_color_for(current_piece.color_key, gx, gy, now)
                                        for _ in range(DOWN_PRESS_BURST):
                                            if len(embers) + len(explosion_particles) < MAX_PARTICLES:
                                                p = get_particle_from_pool()
                                                p.init_particle(gx + 0.5, gy + 0.5, color, now, 900, speed_scale=1.2)
                                                embers.append(p)
                elif event.key == pygame.K_UP:
                    old_shape = [row[:] for row in current_piece.shape]
                    current_piece.rotate()
                    if not valid_space(current_piece, locked_positions):
                        current_piece.shape = old_shape
                    else:
                        moved = True

                if moved and not pressed_down:
                    for y, row in enumerate(current_piece.shape):
                        for x, cell in enumerate(row):
                            if cell:
                                gx = current_piece.x + x
                                gy = current_piece.y + y
                                if 0 <= gx < GRID_WIDTH and 0 <= gy < GRID_HEIGHT:
                                    color = neon_color_for(current_piece.color_key, gx, gy, now)
                                    if len(embers) + len(explosion_particles) < MAX_PARTICLES:
                                        p = get_particle_from_pool()
                                        p.init_particle(gx + 0.5, gy + 0.5, color, now, 1200, speed_scale=0.9)
                                        embers.append(p)

        # automatic fall and slow ember trickle
        if now - last_fall > fall_speed:
            current_piece.y += 1
            for y, row in enumerate(current_piece.shape):
                for x, cell in enumerate(row):
                    if cell:
                        gx = current_piece.x + x
                        gy = current_piece.y + y
                        if 0 <= gx < GRID_WIDTH and 0 <= gy < GRID_HEIGHT:
                            color = neon_color_for(current_piece.color_key, gx, gy, now)
                            if random.random() < 0.35 and len(embers) + len(explosion_particles) < MAX_PARTICLES:
                                p = get_particle_from_pool()
                                p.init_particle(gx + 0.5, gy + 0.5, color, now, PARTICLE_LIFE, speed_scale=0.6)
                                embers.append(p)
            if not valid_space(current_piece, locked_positions):
                current_piece.y -= 1
                for y, row in enumerate(current_piece.shape):
                    for x, cell in enumerate(row):
                        if cell:
                            pos_y = current_piece.y + y
                            pos_x = current_piece.x + x
                            if pos_y >= 0:
                                locked_positions[(pos_y, pos_x)] = current_piece.color_key
                                color = neon_color_for(current_piece.color_key, pos_x, pos_y, now)
                                for _ in range(max(3, PARTICLE_COUNT // 3)):
                                    if len(embers) + len(explosion_particles) < MAX_PARTICLES:
                                        p = get_particle_from_pool()
                                        p.init_particle(pos_x + 0.5, pos_y + 0.5, color, now, PARTICLE_LIFE, speed_scale=0.9)
                                        embers.append(p)
                lines = clear_rows(locked_positions)
                if lines > 0:
                    score += lines * 300
                    embers.clear()
                    total_to_spawn = EXPLOSION_TOTAL_PER_LINE * lines
                    center_x = GRID_WIDTH / 2
                    center_y = GRID_HEIGHT / 2
                    explosion_queue.append([total_to_spawn, center_x, center_y, now, lines])
                    explosion_active = True
                    explosion_start = now
                current_piece = next_piece
                next_piece = Piece(GRID_WIDTH // 2 - 2, -1, random.randint(0, len(SHAPES) - 1))
                if not valid_space(current_piece, locked_positions):
                    running = False
            last_fall = now

        # process explosion queue in batches
        if explosion_queue:
            task = explosion_queue[0]
            remaining, cx, cy, start_time, lines = task
            spawn = min(EXPLOSION_BATCH_SIZE, remaining, MAX_PARTICLES - (len(embers) + len(explosion_particles)))
            for _ in range(spawn):
                rx = cx + random.uniform(-GRID_WIDTH/2, GRID_WIDTH/2)
                ry = cy + random.uniform(-GRID_HEIGHT/2, GRID_HEIGHT/2)
                key = random.choice(list(BASE_HUES.keys()))
                color = neon_color_for(key, int(rx), int(ry), now)
                p = get_particle_from_pool()
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(2.0, 6.0) * (1.0 + 0.2 * lines)
                vx = math.cos(angle) * speed
                vy = math.sin(angle) * speed
                p.init_particle(rx, ry, color, now, EXPLOSION_LIFE, speed_scale=random.uniform(1.6, 3.2), vx=vx, vy=vy)
                explosion_particles.append(p)
            task[0] -= spawn
            if task[0] <= 0:
                explosion_queue.pop(0)

        # update embers
        new_embers = []
        for p in embers:
            p.update(dt, now)
            if p.alive(now):
                new_embers.append(p)
        embers = new_embers

        # update explosion particles
        new_explosion = []
        for p in explosion_particles:
            p.update(dt, now)
            if p.alive(now):
                new_explosion.append(p)
        explosion_particles = new_explosion

        if not explosion_queue and not explosion_particles and explosion_active:
            explosion_active = False
            for _ in range(40):
                if len(embers) + len(explosion_particles) < MAX_PARTICLES:
                    rx = random.uniform(0, GRID_WIDTH)
                    ry = random.uniform(0, GRID_HEIGHT)
                    key = random.choice(list(BASE_HUES.keys()))
                    color = neon_color_for(key, int(rx), int(ry), now)
                    p = get_particle_from_pool()
                    p.init_particle(rx + 0.5, ry + 0.5, color, now, PARTICLE_LIFE, speed_scale=0.5)
                    embers.append(p)

        # --- RENDER PIPELINE ---
        frame_surf.fill((0, 0, 0, 0))
        bloom_surf.fill((0, 0, 0, 0))

        # background
        frame_surf.fill((8, 6, 14))

        # UI
        title_text = large_font.render("TETRIS", True, (255, 255, 255))
        frame_surf.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, 12))
        score_surf = font.render(f"Score: {score}", True, (255, 255, 255))
        frame_surf.blit(score_surf, (BOARD_START_X - 150, BOARD_START_Y + 100))

        # crisp grid lines
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                rect = (x * BLOCK_SIZE + BOARD_START_X, y * BLOCK_SIZE + BOARD_START_Y, BLOCK_SIZE, BLOCK_SIZE)
                pygame.draw.rect(frame_surf, (22, 22, 24), rect, 1)

        # locked blocks: soft glow -> bloom_surf, solid -> frame_surf
        for (r, c), key in locked_positions.items():
            color = neon_color_for(key, c, r, now)
            for i in range(GLOW_LAYERS):
                add_soft_glow(bloom_surf, c, r, color, i, GLOW_LAYERS)
            draw_solid_block(frame_surf, c, r, color, alpha=230)

        # current piece: glow -> bloom_surf, solid -> frame_surf
        for y, row in enumerate(current_piece.shape):
            for x, cell in enumerate(row):
                if cell:
                    gx = current_piece.x + x
                    gy = current_piece.y + y
                    if gy >= -4:
                        color = neon_color_for(current_piece.color_key, gx, gy, now)
                        for i in range(GLOW_LAYERS):
                            add_soft_glow(bloom_surf, gx, gy, color, i, GLOW_LAYERS)
                        draw_solid_block(frame_surf, gx, gy, color, alpha=240)

        # draw embers (wisp) onto frame
        for p in embers:
            p.draw_wisp(frame_surf, now)

        # draw explosion particles (simple circles) onto frame
        for p in explosion_particles:
            p.draw_simple(frame_surf, now)

        # next piece preview
        label_font = pygame.font.SysFont('Arial', 20)
        label = label_font.render("Next Piece", 1, (255, 255, 255))
        frame_surf.blit(label, (SCREEN_WIDTH - 180, BOARD_START_Y + 20))
        offset_x = SCREEN_WIDTH - 130
        offset_y = BOARD_START_Y + 60
        for y, row in enumerate(next_piece.shape):
            for x, cell in enumerate(row):
                if cell:
                    px = offset_x + x * BLOCK_SIZE
                    py = offset_y + y * BLOCK_SIZE
                    color = neon_color_for(next_piece.color_key, x, y, now)
                    glow = pygame.Surface((BLOCK_SIZE*2, BLOCK_SIZE*2), pygame.SRCALPHA)
                    glow.fill((*color, 48))
                    bloom_surf.blit(glow, (px - BLOCK_SIZE//2, py - BLOCK_SIZE//2), special_flags=pygame.BLEND_ADD)
                    preview = pygame.Surface((BLOCK_SIZE, BLOCK_SIZE), pygame.SRCALPHA)
                    preview.fill((*color, 220))
                    frame_surf.blit(preview, (px, py))

        # --- BLOOM PASS (smooth gradients) ---
        if BLOOM_SCALE <= 1:
            small = pygame.transform.smoothscale(bloom_surf, (SCREEN_WIDTH, SCREEN_HEIGHT))
        else:
            small = pygame.transform.smoothscale(bloom_surf, (max(1, SCREEN_WIDTH // BLOOM_SCALE), max(1, SCREEN_HEIGHT // BLOOM_SCALE)))
            # extra smooth pass for very soft glow
            small = pygame.transform.smoothscale(small, (SCREEN_WIDTH, SCREEN_HEIGHT))
        bloom_tint = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        bloom_tint.blit(small, (0, 0))
        bloom_tint.fill((255, 255, 255, int(220 * BLOOM_INTENSITY)), special_flags=pygame.BLEND_RGBA_MULT)

        # --- MOTION TRAIL ACCUMULATION ---
        fade_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        fade_surf.fill((0, 0, 0, int(255 * (1.0 - ACCUM_DECAY))))
        accum_surf.blit(fade_surf, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        accum_surf.blit(bloom_tint, (0, 0), special_flags=pygame.BLEND_ADD)

        # --- FINAL COMPOSITE ---
        screen.fill((0, 0, 0))
        screen.blit(accum_surf, (0, 0), special_flags=pygame.BLEND_ADD)
        screen.blit(frame_surf, (0, 0))
        screen.blit(bloom_tint, (0, 0), special_flags=pygame.BLEND_ADD)

        # crisp black outlines on top
        for (r, c), key in locked_positions.items():
            draw_black_outline(screen, c, r, thickness=2)
        for y, row in enumerate(current_piece.shape):
            for x, cell in enumerate(row):
                if cell:
                    gx = current_piece.x + x
                    gy = current_piece.y + y
                    if gy >= -4:
                        draw_black_outline(screen, gx, gy, thickness=2)

        # --- HYPERLINK (draw last so it's on top) ---
        mouse_pos = pygame.mouse.get_pos()
        hover = False
        # draw onto screen directly (not frame_surf) so it's always crisp
        link_rect = draw_rainbow_hyperlink(screen, now, hover=False)
        # check hover and update cursor/glow if needed
        mx, my = mouse_pos
        if link_rect.collidepoint(mx, my):
            hover = True
            # redraw with hover effect (stronger glow)
            link_rect = draw_rainbow_hyperlink(screen, now, hover=True)
            if not using_hand:
                try:
                    pygame.mouse.set_cursor(hand_cursor)
                    using_hand = True
                except Exception:
                    using_hand = False
        else:
            if using_hand:
                try:
                    pygame.mouse.set_cursor(arrow_cursor)
                    using_hand = False
                except Exception:
                    using_hand = False

        pygame.display.update()

    # Game over
    screen.fill((0, 0, 0))
    game_over_text = large_font.render("GAME OVER", True, (255, 0, 0))
    final_score_text = font.render(f"Final Score: {score}", True, (255, 255, 255))
    screen.blit(game_over_text, (SCREEN_WIDTH // 2 - game_over_text.get_width() // 2, SCREEN_HEIGHT // 3))
    screen.blit(final_score_text, (SCREEN_WIDTH // 2 - final_score_text.get_width() // 2, SCREEN_HEIGHT // 2))
    pygame.display.update()
    pygame.time.wait(3000)
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main(screen)
