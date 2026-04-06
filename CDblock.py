"""
Orbital Tetris — a circular Tetris variant built with Pygame.

Controls:
  MOUSE LEFT   : Drag to rotate the wheel (stays in place on release)
  MOUSE RIGHT  : Rotate the falling piece
  MOUSE MIDDLE : Hold piece
  CENTER CLICK : Hard drop
  LEFT / RIGHT : Rotate the wheel (Keyboard)
  UP           : Rotate the falling piece
  DOWN / SPACE : Hard drop
  C            : Hold piece
  F / F11      : Toggle fullscreen
  ESC          : Quit
"""

import io
import math
import random
import struct
import sys
import wave

import pygame

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCREEN_WIDTH  = 800
SCREEN_HEIGHT = 800
FPS           = 60

# Wheel / grid geometry
CX           = SCREEN_WIDTH  // 2
CY           = SCREEN_HEIGHT // 2
N_SLOTS      = 36
SLOT_ANGLE   = 360 / N_SLOTS
INNER_RADIUS = 110
LAYER_WIDTH  = 22
LAYERS       = 14

# Colour palette
COLOR_BG_DARK    = (10,  10,  18)
COLOR_BG_CORE    = (25,  25,  45)
COLOR_GRID       = (50,  50,  80)
COLOR_GRID_GLOW  = (30,  30,  60,  100)
COLOR_HUB        = (20,  20,  30)
COLOR_HUB_BORDER = (0,   255, 255)
COLOR_HUB_GLOW   = (0,   255, 255, 50)
WHITE            = (255, 255, 255)

# Tetromino definitions
TETROMINOES = {
    'I': {'color': (0,   255, 255), 'blocks': [(-1, 0), (0, 0), (1, 0), (2, 0)]},
    'J': {'color': (50,  100, 255), 'blocks': [(-1, 1), (-1, 0), (0, 0), (1, 0)]},
    'L': {'color': (255, 150, 50),  'blocks': [(1,  1), (-1, 0), (0, 0), (1, 0)]},
    'O': {'color': (255, 255, 50),  'blocks': [(0,  0), (1, 0),  (0, 1), (1, 1)]},
    'S': {'color': (50,  255, 50),  'blocks': [(0,  0), (1, 0),  (-1, 1),(0, 1)]},
    'T': {'color': (200, 50,  255), 'blocks': [(-1, 0), (0, 0),  (1, 0), (0, 1)]},
    'Z': {'color': (255, 50,  50),  'blocks': [(-1, 0), (0, 0),  (0, 1), (1, 1)]},
}
SHAPE_KEYS = list(TETROMINOES.keys())

HIGH_SCORE_FILE = "orbital_tetris_hs.txt"

# Menu state constants
STATE_MENU     = "menu"
STATE_CONTROLS = "controls"
STATE_PLAYING  = "playing"


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
def create_wav_sound(
    frequency: float,
    duration: float,
    volume: float = 0.1,
    slide: float = 0.0,
) -> pygame.mixer.Sound:
    sample_rate = 44100
    n_samples   = int(sample_rate * duration)

    buf = io.BytesIO()
    with wave.open(buf, 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)

        for i in range(n_samples):
            t            = i / sample_rate
            current_freq = frequency + slide * (i / n_samples)

            if i < 500:
                env = i / 500.0
            elif i > n_samples - 1000:
                env = (n_samples - i) / 1000.0
            else:
                env = 1.0

            square = 1.0 if math.sin(2.0 * math.pi * current_freq * t) > 0 else -1.0
            sample = int(volume * env * 32767.0 * square)
            wav.writeframesraw(struct.pack('<h', sample))

    buf.seek(0)
    return pygame.mixer.Sound(buf)


class SoundManager:
    def __init__(self) -> None:
        self._sounds = {
            'rotate': create_wav_sound(800, 0.05, 0.05),
            'hold':   create_wav_sound(400, 0.08, 0.05, slide=-100),
            'thud':   create_wav_sound(80,  0.10, 0.15, slide=-30),
            'clear':  create_wav_sound(600, 0.30, 0.10, slide=400),
        }

    def play(self, name: str) -> None:
        sound = self._sounds.get(name)
        if sound:
            sound.play()


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def polar_to_cartesian(
    r: float, theta_deg: float, cx: int = CX, cy: int = CY
) -> tuple[float, float]:
    theta_rad = math.radians(theta_deg)
    return cx + r * math.cos(theta_rad), cy - r * math.sin(theta_rad)


def get_arc_points(
    r_inner: float,
    r_outer: float,
    theta_center: float,
    width_deg: float,
    cx: int = CX,
    cy: int = CY,
    steps: int = 10,
) -> list[tuple[float, float]]:
    theta_start = theta_center - width_deg / 2
    theta_end   = theta_center + width_deg / 2

    inner_pts = [
        polar_to_cartesian(
            r_inner,
            theta_start + (theta_end - theta_start) * (i / (steps - 1)),
            cx, cy,
        )
        for i in range(steps)
    ]
    outer_pts = [
        polar_to_cartesian(
            r_outer,
            theta_end - (theta_end - theta_start) * (i / (steps - 1)),
            cx, cy,
        )
        for i in range(steps)
    ]
    return inner_pts + outer_pts


def draw_segment(
    surface: pygame.Surface,
    alpha_surface: pygame.Surface,
    color: tuple,
    r_inner: float,
    r_outer: float,
    theta_center: float,
    width_deg: float,
    cx: int = CX,
    cy: int = CY,
    outline_only: bool = False,
) -> None:
    poly = get_arc_points(r_inner, r_outer, theta_center, width_deg, cx, cy)

    if outline_only:
        pygame.draw.polygon(alpha_surface, (*color, 120), poly, 2)
        return

    glow_poly = get_arc_points(
        r_inner - 3, r_outer + 3, theta_center, width_deg + 1, cx, cy
    )
    pygame.draw.polygon(alpha_surface, (*color, 60), glow_poly)

    pygame.draw.polygon(surface, color, poly)
    highlight = tuple(min(255, c + 50) for c in color)
    pygame.draw.polygon(surface, highlight, poly, 1)


# ---------------------------------------------------------------------------
# Game objects
# ---------------------------------------------------------------------------
class Particle:
    def __init__(self, x: float, y: float, angle_deg: float, color: tuple) -> None:
        self.x     = x
        self.y     = y
        self.color = color

        rad        = math.radians(angle_deg)
        speed      = random.uniform(3, 8)
        self.vx    = math.cos(rad) * speed + random.uniform(-1, 1)
        self.vy    = -math.sin(rad) * speed + random.uniform(-1, 1)

        self.life     = random.randint(20, 40)
        self.max_life = self.life
        self.size     = random.uniform(2, 5)

    def update(self) -> None:
        self.x    += self.vx
        self.y    += self.vy
        self.life -= 1

    def draw(self, surface: pygame.Surface) -> None:
        if self.life <= 0:
            return
        alpha  = int((self.life / self.max_life) * 255)
        center = (int(self.x), int(self.y))
        radius = int(self.size)
        pygame.draw.circle(surface, (*self.color, alpha), center, radius + 2)
        pygame.draw.circle(surface, WHITE, center, radius)


class FallingPiece:
    def __init__(self, shape_id: str | None = None) -> None:
        self.shape_id = shape_id or random.choice(SHAPE_KEYS)
        data          = TETROMINOES[self.shape_id]
        self.color    = data['color']
        self.blocks   = list(data['blocks'])
        self.r        = CX + 50

    def rotate(self) -> None:
        if self.shape_id == 'O':
            return
        self.blocks = [(-dl, ds) for ds, dl in self.blocks]

    def draw(
        self,
        surface: pygame.Surface,
        alpha_surface: pygame.Surface | None = None,
        cx: int = CX,
        cy: int = CY,
        is_preview: bool = False,
        ghost_r: float | None = None,
    ) -> None:
        if is_preview:
            draw_r      = 30
            layer_scale = 12
            for ds, dl in self.blocks:
                theta = 90 + ds * SLOT_ANGLE
                r_in  = draw_r + dl * layer_scale
                poly  = get_arc_points(r_in, r_in + layer_scale, theta, SLOT_ANGLE, cx, cy)
                pygame.draw.polygon(surface, self.color, poly)
                pygame.draw.polygon(surface, WHITE, poly, 1)
            return

        draw_r      = ghost_r if ghost_r is not None else self.r
        is_ghost    = ghost_r is not None
        layer_scale = LAYER_WIDTH

        for ds, dl in self.blocks:
            theta = 90 + ds * SLOT_ANGLE
            r_in  = draw_r + dl * layer_scale
            draw_segment(
                surface,
                alpha_surface or pygame.Surface((0, 0), pygame.SRCALPHA),
                self.color,
                r_in, r_in + layer_scale,
                theta, SLOT_ANGLE,
                cx, cy,
                outline_only=is_ghost,
            )


# ---------------------------------------------------------------------------
# High score persistence
# ---------------------------------------------------------------------------
def load_high_score() -> int:
    try:
        with open(HIGH_SCORE_FILE, 'r') as f:
            return int(f.read().strip())
    except Exception:
        return 0

def save_high_score(score: int) -> None:
    try:
        with open(HIGH_SCORE_FILE, 'w') as f:
            f.write(str(score))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Menu button
# ---------------------------------------------------------------------------
class MenuButton:
    """A rounded rectangle button with hover glow and click animation."""

    NORMAL_COLOR = (20,  20,  40)
    BORDER_COLOR = (0,   255, 255)
    HOVER_COLOR  = (0,   200, 220)
    TEXT_COLOR   = (255, 255, 255)
    CLICK_COLOR  = (0,   255, 255)

    def __init__(self, rect: pygame.Rect, text: str, font: pygame.font.Font) -> None:
        self.rect      = rect
        self.text      = text
        self.font      = font
        self.hovered   = False
        self._click_t  = 0   # frames remaining in click flash

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if this button was clicked."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._click_t = 8
                return True
        return False

    def update(self) -> None:
        self.hovered = self.rect.collidepoint(pygame.mouse.get_pos())
        if self._click_t > 0:
            self._click_t -= 1

    def draw(self, surface: pygame.Surface, alpha_surf: pygame.Surface) -> None:
        # Glow halo on hover
        if self.hovered or self._click_t > 0:
            glow = self.rect.inflate(10, 10)
            pygame.draw.rect(alpha_surf, (*self.BORDER_COLOR, 60), glow, border_radius=14)

        # Fill
        fill_color = self.CLICK_COLOR if self._click_t > 0 else (
            (30, 60, 70) if self.hovered else self.NORMAL_COLOR
        )
        pygame.draw.rect(surface, fill_color, self.rect, border_radius=10)

        # Border
        border_color = self.CLICK_COLOR if self._click_t > 0 else (
            self.HOVER_COLOR if self.hovered else self.BORDER_COLOR
        )
        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=10)

        # Label
        text_color = (10, 10, 10) if self._click_t > 0 else self.TEXT_COLOR
        label = self.font.render(self.text, True, text_color)
        surface.blit(label, label.get_rect(center=self.rect.center))


# ---------------------------------------------------------------------------
# Main game class
# ---------------------------------------------------------------------------
class Game:
    def __init__(self) -> None:
        self.screen = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            pygame.SCALED | pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF,
        )
        self.main_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        pygame.display.set_caption("Orbital Tetris")
        self.clock = pygame.time.Clock()
        self.audio = SoundManager()

        self.font       = pygame.font.SysFont("Consolas", 26, bold=True)
        self.large_font = pygame.font.SysFont("Verdana",  60, bold=True)
        self.small_font = pygame.font.SysFont("Consolas", 16)
        self.title_font = pygame.font.SysFont("Verdana",  72, bold=True)
        self.sub_font   = pygame.font.SysFont("Consolas", 20, bold=False)

        self.bg_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self._build_background()

        self.high_score   = load_high_score()
        self.state        = STATE_MENU
        self.menu_angle   = 0.0        # slowly rotating decorative wheel
        self.menu_tick    = 0          # frame counter for animations

        # Build menu buttons
        bw, bh = 260, 52
        bx = CX - bw // 2
        self._btn_play     = MenuButton(pygame.Rect(bx, 460, bw, bh), "▶  PLAY",     self.font)
        self._btn_controls = MenuButton(pygame.Rect(bx, 530, bw, bh), "⌨  CONTROLS", self.font)
        self._btn_quit     = MenuButton(pygame.Rect(bx, 600, bw, bh), "✕  QUIT",     self.font)
        self._btn_back     = MenuButton(pygame.Rect(bx, 660, bw, bh), "←  BACK",     self.font)

        # Pre-populate decorative wheel with random colours (sparse)
        self.deco_wheel = [[None] * N_SLOTS for _ in range(LAYERS)]
        for L in range(LAYERS):
            for slot in range(N_SLOTS):
                if random.random() < 0.35:
                    self.deco_wheel[L][slot] = random.choice(
                        [d['color'] for d in TETROMINOES.values()]
                    )

        self.reset_game()

    def _build_background(self) -> None:
        max_dist = math.sqrt(CX**2 + CY**2)
        for y in range(SCREEN_HEIGHT):
            for x in range(SCREEN_WIDTH):
                dist  = math.sqrt((x - CX) ** 2 + (y - CY) ** 2)
                ratio = min(1.0, dist / (max_dist * 0.8))
                r = int(COLOR_BG_CORE[0] * (1 - ratio) + COLOR_BG_DARK[0] * ratio)
                g = int(COLOR_BG_CORE[1] * (1 - ratio) + COLOR_BG_DARK[1] * ratio)
                b = int(COLOR_BG_CORE[2] * (1 - ratio) + COLOR_BG_DARK[2] * ratio)
                self.bg_surf.set_at((x, y), (r, g, b))

    def reset_game(self) -> None:
        self.wheel       = [[None] * N_SLOTS for _ in range(LAYERS)]
        self.wheel_angle = 0.0
        self.rotation_speed = 3.0

        # Accumulators for notched, grid-locked movement
        self.accumulated_drag = 0.0
        self.accumulated_keys = 0.0

        self.score         = 0
        self.lines_cleared = 0
        self.base_fall_speed = 1.2
        self.fall_speed      = self.base_fall_speed

        self.current_piece = FallingPiece()
        self.next_piece    = FallingPiece()
        self.hold_id       = None
        self.can_hold      = True

        self.particles = []
        self.shake     = 0
        self.game_over = False

        self.target_layer = 0
        self.target_r     = INNER_RADIUS
        
        # Track relative mouse movement
        self.last_mouse_angle = None

    def _spawn_next_piece(self) -> None:
        self.current_piece = self.next_piece
        self.next_piece    = FallingPiece()
        self.can_hold      = True
        self.fall_speed    = (
            self.base_fall_speed + (self.lines_cleared // 5) * 0.3
        )

    def lock_piece(self, base_slot: int) -> None:
        highest = self.target_layer + max(dl for _, dl in self.current_piece.blocks)
        if highest >= LAYERS:
            self.game_over = True
            return

        self.audio.play('thud')
        self.shake = 8

        for ds, dl in self.current_piece.blocks:
            slot = (base_slot + ds) % N_SLOTS
            self.wheel[self.target_layer + dl][slot] = self.current_piece.color

        self.check_clears()
        self._spawn_next_piece()

    def check_clears(self) -> None:
        cleared = [L for L in range(LAYERS) if None not in self.wheel[L]]
        if not cleared:
            return

        self.audio.play('clear')
        self.shake = 12

        for L in cleared:
            r = INNER_RADIUS + L * LAYER_WIDTH + LAYER_WIDTH // 2
            for slot in range(N_SLOTS):
                color = self.wheel[L][slot]
                theta = self.wheel_angle + slot * SLOT_ANGLE
                px, py = polar_to_cartesian(r, theta)
                for _ in range(3):
                    self.particles.append(Particle(px, py, theta, color))

        kept = [row for i, row in enumerate(self.wheel) if i not in cleared]
        self.wheel = kept + [[None] * N_SLOTS for _ in cleared]

        n             = len(cleared)
        self.lines_cleared += n
        self.score         += (n ** 2) * 100

    def hold_piece(self) -> None:
        if not self.can_hold:
            return

        self.audio.play('hold')
        if self.hold_id is None:
            self.hold_id = self.current_piece.shape_id
            self._spawn_next_piece()
        else:
            self.hold_id, swapped_id = self.current_piece.shape_id, self.hold_id
            self.current_piece = FallingPiece(swapped_id)

        self.can_hold = False

    def update(self) -> None:
        if self.game_over:
            return

        # --- Rotation Logic (Keyboard + Mouse) ---
        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()

        # Keyboard movement (accumulate for discrete grid steps)
        kb_delta = 0
        if keys[pygame.K_LEFT]:
            kb_delta += self.rotation_speed
        if keys[pygame.K_RIGHT]:
            kb_delta -= self.rotation_speed

        if kb_delta != 0:
            self.accumulated_keys += kb_delta
            # Snap to the next slot if we've accumulated enough rotation
            if abs(self.accumulated_keys) >= SLOT_ANGLE:
                steps = int(self.accumulated_keys / SLOT_ANGLE)
                self.wheel_angle = (self.wheel_angle + steps * SLOT_ANGLE) % 360
                self.accumulated_keys -= steps * SLOT_ANGLE
        else:
            self.accumulated_keys = 0.0

        # Mouse movement (Relative Drag logic, accumulate for discrete grid steps)
        if mouse_buttons[0]:
            mx, my = pygame.mouse.get_pos()
            rel_x, rel_y = mx - CX, CY - my
            current_m_angle = math.degrees(math.atan2(rel_y, rel_x))
            
            if self.last_mouse_angle is not None:
                # Calculate movement since last frame
                delta = current_m_angle - self.last_mouse_angle
                # Correct for 180/-180 wrap around jump
                if delta > 180: delta -= 360
                if delta < -180: delta += 360
                
                self.accumulated_drag += delta
                
                # Lock to grid slots
                if abs(self.accumulated_drag) >= SLOT_ANGLE:
                    steps = int(self.accumulated_drag / SLOT_ANGLE)
                    self.wheel_angle = (self.wheel_angle + steps * SLOT_ANGLE) % 360
                    self.accumulated_drag -= steps * SLOT_ANGLE
            
            self.last_mouse_angle = current_m_angle
        else:
            self.last_mouse_angle = None
            self.accumulated_drag = 0.0  # Reset on release

        # Particle lifecycle
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]

        # Advance piece inward
        self.current_piece.r -= self.fall_speed

        # Work out the landing layer
        target_i = round((90 - self.wheel_angle) / SLOT_ANGLE) % N_SLOTS
        max_req_layer = 0

        for ds, dl in self.current_piece.blocks:
            slot = (target_i + ds) % N_SLOTS
            occ = next(
                (L for L in range(LAYERS - 1, -1, -1) if self.wheel[L][slot] is not None),
                -1,
            )
            req_layer     = occ + 1 - dl
            max_req_layer = max(max_req_layer, req_layer, -dl)

        self.target_layer = max_req_layer
        self.target_r     = INNER_RADIUS + self.target_layer * LAYER_WIDTH

        if self.current_piece.r <= self.target_r:
            self.current_piece.r = self.target_r
            self.lock_piece(target_i)

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def _draw_deco_wheel(self, alpha_surf: pygame.Surface, angle: float) -> None:
        """Draw the dim decorative wheel used as menu background art."""
        dim_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for L in range(LAYERS):
            for slot in range(N_SLOTS):
                color = self.deco_wheel[L][slot]
                if color is None:
                    continue
                r_inner      = INNER_RADIUS + L * LAYER_WIDTH
                theta_center = angle + slot * SLOT_ANGLE
                poly = get_arc_points(r_inner, r_inner + LAYER_WIDTH, theta_center, SLOT_ANGLE)
                dc = tuple(int(c * 0.28) for c in color)
                pygame.draw.polygon(dim_surf, dc, poly)
        self.main_surf.blit(dim_surf, (0, 0))

        outer_r = INNER_RADIUS + LAYERS * LAYER_WIDTH
        for L in range(LAYERS + 1):
            r = INNER_RADIUS + L * LAYER_WIDTH
            pygame.draw.circle(self.main_surf, (30, 30, 50), (CX, CY), r, 1)
        for i in range(N_SLOTS):
            theta = angle + i * SLOT_ANGLE - SLOT_ANGLE / 2
            p1 = polar_to_cartesian(INNER_RADIUS, theta)
            p2 = polar_to_cartesian(outer_r, theta)
            pygame.draw.line(self.main_surf, (30, 30, 50), p1, p2, 1)

        pygame.draw.circle(self.main_surf, COLOR_HUB,        (CX, CY), INNER_RADIUS)
        pygame.draw.circle(self.main_surf, COLOR_HUB_BORDER, (CX, CY), INNER_RADIUS, 2)

    def _draw_menu(self) -> None:
        self.main_surf.blit(self.bg_surf, (0, 0))
        alpha_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._draw_deco_wheel(alpha_surf, self.menu_angle)

        pulse = 0.75 + 0.25 * math.sin(self.menu_tick * 0.04)
        glow_alpha = int(pulse * 80)
        for r in range(60, 0, -10):
            pygame.draw.circle(alpha_surf, (0, 255, 255, glow_alpha // (r // 10 + 1)),
                               (CX, 200), r)

        shadow = self.title_font.render("ORBITAL TETRIS", True, (0, 130, 130))
        title  = self.title_font.render("ORBITAL TETRIS", True, COLOR_HUB_BORDER)
        self.main_surf.blit(shadow, shadow.get_rect(center=(CX + 3, 203)))
        self.main_surf.blit(title,  title.get_rect(center=(CX, 200)))

        sub = self.sub_font.render("A circular Tetris variant", True, COLOR_GRID)
        self.main_surf.blit(sub, sub.get_rect(center=(CX, 265)))

        if self.high_score > 0:
            hs_label = self.font.render(f"BEST  {self.high_score}", True, (255, 220, 80))
            self.main_surf.blit(hs_label, hs_label.get_rect(center=(CX, 390)))

        for btn in (self._btn_play, self._btn_controls, self._btn_quit):
            btn.update()
            btn.draw(self.main_surf, alpha_surf)

        self.main_surf.blit(alpha_surf, (0, 0))
        self.screen.blit(self.main_surf, (0, 0))
        pygame.display.flip()

    def _draw_controls(self) -> None:
        self.main_surf.blit(self.bg_surf, (0, 0))
        alpha_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._draw_deco_wheel(alpha_surf, self.menu_angle)

        panel = pygame.Rect(CX - 280, 80, 560, 565)
        pygame.draw.rect(self.main_surf, (15, 15, 28), panel, border_radius=16)
        pygame.draw.rect(alpha_surf, (*COLOR_HUB_BORDER, 160), panel, 2, border_radius=16)

        heading = self.font.render("CONTROLS", True, COLOR_HUB_BORDER)
        self.main_surf.blit(heading, heading.get_rect(center=(CX, 115)))

        lines = [
            ("MOUSE",          ""),
            ("Left drag",      "Spin the wheel"),
            ("Right click",    "Rotate piece"),
            ("Middle/scroll",  "Hold piece"),
            ("Click centre",   "Hard drop"),
            ("",               ""),
            ("KEYBOARD",       ""),
            ("\u2190 \u2192",  "Spin the wheel"),
            ("\u2191",         "Rotate piece"),
            ("\u2193 / Space", "Hard drop"),
            ("C",              "Hold piece"),
            ("F / F11",        "Toggle fullscreen"),
            ("ESC",            "Quit / Back"),
        ]

        y = 158
        for key, desc in lines:
            if desc == "" and key == "":
                y += 8
                continue
            if desc == "":
                hdr = self.sub_font.render(key, True, (0, 200, 200))
                self.main_surf.blit(hdr, (panel.left + 30, y))
                pygame.draw.line(self.main_surf, (0, 120, 120),
                                 (panel.left + 30, y + 22),
                                 (panel.right - 30, y + 22), 1)
                y += 34
            else:
                k_surf = self.sub_font.render(key,  True, (220, 220, 220))
                d_surf = self.sub_font.render(desc, True, COLOR_GRID)
                self.main_surf.blit(k_surf, (panel.left + 40,  y))
                self.main_surf.blit(d_surf, (panel.left + 230, y))
                y += 28

        self._btn_back.update()
        self._btn_back.draw(self.main_surf, alpha_surf)

        self.main_surf.blit(alpha_surf, (0, 0))
        self.screen.blit(self.main_surf, (0, 0))
        pygame.display.flip()

    def _update_menu(self) -> None:
        self.menu_angle = (self.menu_angle + 0.18) % 360
        self.menu_tick += 1

    def _handle_menu_events(self, event: pygame.event.Event) -> bool:
        """Return False to quit."""
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state == STATE_CONTROLS:
                    self.state = STATE_MENU
                else:
                    return False
            elif event.key in (pygame.K_F11, pygame.K_f):
                pygame.display.toggle_fullscreen()
            elif event.key == pygame.K_RETURN and self.state == STATE_MENU:
                self.reset_game()
                self.state = STATE_PLAYING

        if self.state == STATE_MENU:
            if self._btn_play.handle_event(event):
                self.reset_game()
                self.state = STATE_PLAYING
            elif self._btn_controls.handle_event(event):
                self.state = STATE_CONTROLS
            elif self._btn_quit.handle_event(event):
                return False
        elif self.state == STATE_CONTROLS:
            if self._btn_back.handle_event(event):
                self.state = STATE_MENU
        return True

    def _draw_ui_box(self, cx: int, cy: int, title: str, piece_id: str | None, alpha_surf: pygame.Surface) -> None:
        box = pygame.Rect(cx - 60, cy - 60, 120, 120)
        pygame.draw.rect(self.main_surf, COLOR_HUB,        box,              0, 10)
        pygame.draw.rect(alpha_surf,    (*COLOR_HUB_BORDER, 100), box.inflate(4, 4), 2, 12)
        pygame.draw.rect(self.main_surf, COLOR_HUB_BORDER, box,              2, 10)

        label = self.font.render(title, True, COLOR_HUB_BORDER)
        self.main_surf.blit(label, label.get_rect(center=(cx, cy - 40)))

        if piece_id:
            FallingPiece(piece_id).draw(self.main_surf, cx=cx, cy=cy + 15, is_preview=True)

    def draw(self) -> None:
        self.main_surf.blit(self.bg_surf, (0, 0))
        alpha_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        for L in range(LAYERS + 1):
            r = INNER_RADIUS + L * LAYER_WIDTH
            pygame.draw.circle(self.main_surf, COLOR_GRID,      (CX, CY), r, 1)
            pygame.draw.circle(alpha_surf,     COLOR_GRID_GLOW, (CX, CY), r, 2)

        outer_r = INNER_RADIUS + LAYERS * LAYER_WIDTH
        for i in range(N_SLOTS):
            theta = self.wheel_angle + i * SLOT_ANGLE - SLOT_ANGLE / 2
            p1    = polar_to_cartesian(INNER_RADIUS, theta)
            p2    = polar_to_cartesian(outer_r,      theta)
            pygame.draw.line(self.main_surf, COLOR_GRID,      p1, p2, 1)
            pygame.draw.line(alpha_surf,     COLOR_GRID_GLOW, p1, p2, 2)

        for L in range(LAYERS):
            for slot in range(N_SLOTS):
                color = self.wheel[L][slot]
                if color is None: continue
                r_inner      = INNER_RADIUS + L * LAYER_WIDTH
                theta_center = self.wheel_angle + slot * SLOT_ANGLE
                draw_segment(self.main_surf, alpha_surf, color, r_inner, r_inner + LAYER_WIDTH, theta_center, SLOT_ANGLE)

        pygame.draw.circle(self.main_surf, COLOR_HUB,        (CX, CY), INNER_RADIUS)
        pygame.draw.circle(alpha_surf,     COLOR_HUB_GLOW,   (CX, CY), INNER_RADIUS + 2, 5)
        pygame.draw.circle(self.main_surf, COLOR_HUB_BORDER, (CX, CY), INNER_RADIUS,     2)

        score_label = self.font.render("SCORE", True, COLOR_GRID)
        score_value = self.large_font.render(str(self.score), True, WHITE)
        self.main_surf.blit(score_label, score_label.get_rect(center=(CX, CY - 25)))
        self.main_surf.blit(score_value, score_value.get_rect(center=(CX, CY + 15)))

        if not self.game_over:
            self.current_piece.draw(self.main_surf, alpha_surf, ghost_r=self.target_r)
            self.current_piece.draw(self.main_surf, alpha_surf)

        for p in self.particles: p.draw(alpha_surf)

        self._draw_ui_box(100, 100, "HOLD", self.hold_id,              alpha_surf)
        self._draw_ui_box(700, 100, "NEXT", self.next_piece.shape_id,  alpha_surf)

        self.main_surf.blit(alpha_surf, (0, 0))
        controls = self.small_font.render("F: Fullscreen  |  ESC: Quit  |  Mouse: Drag to Spin", True, COLOR_GRID)
        self.main_surf.blit(controls, (10, SCREEN_HEIGHT - 30))

        if self.game_over:
            # Save high score
            if self.score > self.high_score:
                self.high_score = self.score
                save_high_score(self.high_score)

            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            self.main_surf.blit(overlay, (0, 0))
            panel = pygame.Rect(CX - 250, CY - 120, 500, 240)
            pygame.draw.rect(self.main_surf, COLOR_HUB,    panel, 0, 15)
            pygame.draw.rect(self.main_surf, (255, 50, 50), panel, 3, 15)
            go_surf    = self.large_font.render("GAME OVER",                   True, (255, 80,  80))
            score_surf = self.font.render(f"Score: {self.score}",              True, WHITE)
            hs_surf    = self.font.render(f"Best:  {self.high_score}",         True, (255, 220, 80))
            hint_surf  = self.font.render("SPACE: Restart  |  M: Menu",        True, COLOR_GRID)
            self.main_surf.blit(go_surf,    go_surf.get_rect(center=(CX, CY - 60)))
            self.main_surf.blit(score_surf, score_surf.get_rect(center=(CX, CY)))
            self.main_surf.blit(hs_surf,    hs_surf.get_rect(center=(CX, CY + 40)))
            self.main_surf.blit(hint_surf,  hint_surf.get_rect(center=(CX, CY + 88)))

        dx, dy = 0, 0
        if self.shake > 0:
            dx = random.randint(-self.shake, self.shake)
            dy = random.randint(-self.shake, self.shake)
            self.shake -= 1

        self.screen.blit(self.main_surf, (dx, dy))
        pygame.display.flip()

    def run(self) -> None:
        running = True
        while running:
            # ---- Menu states ----------------------------------------
            if self.state in (STATE_MENU, STATE_CONTROLS):
                for event in pygame.event.get():
                    if not self._handle_menu_events(event):
                        running = False
                self._update_menu()
                if self.state == STATE_MENU:
                    self._draw_menu()
                else:
                    self._draw_controls()
                self.clock.tick(FPS)
                continue

            # ---- Playing state --------------------------------------
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if not self.game_over:
                        if event.button == 3:
                            self.current_piece.rotate()
                            self.audio.play('rotate')
                        elif event.button in (2, 4, 5):
                            self.hold_piece()
                        elif event.button == 1:
                            mx, my = pygame.mouse.get_pos()
                            dist = math.sqrt((mx - CX)**2 + (my - CY)**2)
                            if dist < INNER_RADIUS:
                                self.current_piece.r = self.target_r

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = STATE_MENU
                    elif event.key in (pygame.K_F11, pygame.K_f):
                        pygame.display.toggle_fullscreen()
                    elif self.game_over:
                        if event.key == pygame.K_SPACE:
                            self.reset_game()
                        elif event.key == pygame.K_m:
                            self.state = STATE_MENU
                    else:
                        if event.key in (pygame.K_DOWN, pygame.K_SPACE):
                            self.current_piece.r = self.target_r
                        elif event.key == pygame.K_UP:
                            self.current_piece.rotate()
                            self.audio.play('rotate')
                        elif event.key == pygame.K_c:
                            self.hold_piece()

            self.update()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    Game().run()