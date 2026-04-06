"""
Orbital Tetris — a circular Tetris variant built with Pygame.

Controls:
  LEFT / RIGHT : Rotate the wheel
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


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
def create_wav_sound(
    frequency: float,
    duration: float,
    volume: float = 0.1,
    slide: float = 0.0,
) -> pygame.mixer.Sound:
    """Generate a retro square-wave sound entirely in memory.

    Args:
        frequency: Starting frequency in Hz.
        duration:  Length of the sound in seconds.
        volume:    Peak amplitude (0.0 – 1.0).
        slide:     Total frequency change applied linearly over the duration.
    """
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

            # Simple attack / decay envelope
            if i < 500:
                env = i / 500.0
            elif i > n_samples - 1000:
                env = (n_samples - i) / 1000.0
            else:
                env = 1.0

            # Square wave derived from a sine
            square = 1.0 if math.sin(2.0 * math.pi * current_freq * t) > 0 else -1.0
            sample = int(volume * env * 32767.0 * square)
            wav.writeframesraw(struct.pack('<h', sample))

    buf.seek(0)
    return pygame.mixer.Sound(buf)


class SoundManager:
    """Owns all game sounds and provides a simple ``play`` interface."""

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
    """Convert polar coords (r, θ°) to screen Cartesian coords."""
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
    """Return polygon vertices that approximate a curved arc segment."""
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


def _shade(color: tuple, factor: float) -> tuple:
    """Scale RGB channels by *factor* (clamp to 0–255)."""
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def _light_factor(theta_deg: float, normal_type: str) -> float:
    """
    Compute a simple diffuse-lighting factor for a surface.

    Light source is fixed at upper-left (225° in screen coords, i.e. the
    vector points toward ~315° from positive-x).  Each surface type has a
    dominant normal direction; we dot that with the light vector.

    normal_type:
      'top'   – faces straight up (out of screen) → always well-lit
      'outer' – normal points radially outward
      'inner' – normal points radially inward
      'left'  – normal points counter-clockwise along arc
      'right' – normal points clockwise along arc
    """
    # Light direction in degrees (upper-left = 135° from +x in standard math)
    LIGHT_DEG = 135.0

    if normal_type == 'top':
        return 1.0          # top face always catches the light

    # Radial outward direction for this segment
    if normal_type == 'outer':
        surface_deg = theta_deg
    elif normal_type == 'inner':
        surface_deg = theta_deg + 180
    elif normal_type == 'left':
        surface_deg = theta_deg + 90
    else:  # 'right'
        surface_deg = theta_deg - 90

    dot = math.cos(math.radians(surface_deg - LIGHT_DEG))
    # Map from [-1, 1] → [0.25, 0.85] so no face goes fully black
    return 0.25 + 0.60 * ((dot + 1) / 2)


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
    """Draw one arc segment with a 3-D bevel effect.

    The illusion uses five faces:
      • Top face  – the main arc polygon, brightest
      • Outer wall – thin extrusion along the outer arc, darker
      • Inner wall – thin extrusion along the inner arc
      • Left wall  – wedge on the counter-clockwise side
      • Right wall – wedge on the clockwise side
    A soft glow halo and a specular highlight finish the look.
    """
    BEVEL = 4   # pixel depth of the side walls

    # ---- ghost / outline mode (falling piece preview) --------------------
    if outline_only:
        poly = get_arc_points(r_inner, r_outer, theta_center, width_deg, cx, cy)
        pygame.draw.polygon(alpha_surface, (*color, 120), poly, 2)
        return

    # ---- geometry --------------------------------------------------------
    theta_left  = theta_center + width_deg / 2   # CCW edge
    theta_right = theta_center - width_deg / 2   # CW  edge

    # We only need the corner points for the four side-wall quads.
    # Outer edge corners
    ol = polar_to_cartesian(r_outer,        theta_left,  cx, cy)   # outer-left
    or_ = polar_to_cartesian(r_outer,       theta_right, cx, cy)   # outer-right
    ol_b = polar_to_cartesian(r_outer - BEVEL, theta_left,  cx, cy)
    or_b = polar_to_cartesian(r_outer - BEVEL, theta_right, cx, cy)

    # Inner edge corners
    il  = polar_to_cartesian(r_inner,        theta_left,  cx, cy)
    ir  = polar_to_cartesian(r_inner,        theta_right, cx, cy)
    il_b = polar_to_cartesian(r_inner + BEVEL, theta_left,  cx, cy)
    ir_b = polar_to_cartesian(r_inner + BEVEL, theta_right, cx, cy)

    # Outer-wall arc (bevel inward from r_outer)
    outer_wall_pts = get_arc_points(r_outer - BEVEL, r_outer, theta_center, width_deg, cx, cy)
    # Inner-wall arc (bevel outward from r_inner)
    inner_wall_pts = get_arc_points(r_inner, r_inner + BEVEL, theta_center, width_deg, cx, cy)

    # ---- colours for each face ------------------------------------------
    top_color   = _shade(color, 1.10 * _light_factor(theta_center, 'top'))
    outer_color = _shade(color, _light_factor(theta_center, 'outer') * 0.70)
    inner_color = _shade(color, _light_factor(theta_center, 'inner') * 0.80)
    left_color  = _shade(color, _light_factor(theta_center, 'left')  * 0.75)
    right_color = _shade(color, _light_factor(theta_center, 'right') * 0.75)

    # ---- glow halo -------------------------------------------------------
    glow_poly = get_arc_points(
        r_inner - 3, r_outer + 3, theta_center, width_deg + 1, cx, cy
    )
    pygame.draw.polygon(alpha_surface, (*color, 55), glow_poly)

    # ---- side walls (drawn before top face so top overlaps neatly) -------
    # Outer wall
    pygame.draw.polygon(surface, outer_color, outer_wall_pts)

    # Inner wall
    pygame.draw.polygon(surface, inner_color, inner_wall_pts)

    # Left wall  (CCW side) — quad: ol → il → il_b → ol_b
    pygame.draw.polygon(surface, left_color,  [ol,  il,  il_b, ol_b])

    # Right wall (CW side)  — quad: or_ → ir → ir_b → or_b
    pygame.draw.polygon(surface, right_color, [or_, ir, ir_b, or_b])

    # ---- top face --------------------------------------------------------
    # Inset slightly so side walls remain visible
    top_face = get_arc_points(
        r_inner + BEVEL, r_outer - BEVEL,
        theta_center, width_deg - 0.4,
        cx, cy,
    )
    pygame.draw.polygon(surface, top_color, top_face)

    # ---- specular highlight (thin bright arc on outer-top edge) ----------
    spec_color = _shade(color, 1.6)
    spec_pts   = get_arc_points(
        r_outer - BEVEL - 1, r_outer - BEVEL + 1,
        theta_center, width_deg * 0.55,
        cx, cy, steps=6,
    )
    pygame.draw.polygon(surface, spec_color, spec_pts)


# ---------------------------------------------------------------------------
# Game objects
# ---------------------------------------------------------------------------
class Particle:
    """A short-lived spark ejected when a layer is cleared."""

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
    """A tetromino falling radially inward through the wheel."""

    def __init__(self, shape_id: str | None = None) -> None:
        self.shape_id = shape_id or random.choice(SHAPE_KEYS)
        data          = TETROMINOES[self.shape_id]
        self.color    = data['color']
        self.blocks   = list(data['blocks'])  # list of (dslot, dlayer) offsets
        self.r        = CX + 50              # current radial position (pixels)

    def rotate(self) -> None:
        """Rotate 90° clockwise (no-op for the O piece)."""
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
            dummy_alpha = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for ds, dl in self.blocks:
                theta = 90 + ds * SLOT_ANGLE
                r_in  = draw_r + dl * layer_scale
                draw_segment(
                    surface, dummy_alpha, self.color,
                    r_in, r_in + layer_scale,
                    theta, SLOT_ANGLE, cx, cy,
                )
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
# Main game class
# ---------------------------------------------------------------------------
class Game:
    def __init__(self) -> None:
        self.screen = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            pygame.SCALED | pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF,
        )
        # Off-screen buffer used for screen-shake rendering
        self.main_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        pygame.display.set_caption("Orbital Tetris")
        self.clock = pygame.time.Clock()
        self.audio = SoundManager()

        self.font       = pygame.font.SysFont("Consolas", 26, bold=True)
        self.large_font = pygame.font.SysFont("Verdana",  60, bold=True)
        self.small_font = pygame.font.SysFont("Consolas", 16)

        self.bg_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self._build_background()
        self.reset_game()

    # ------------------------------------------------------------------
    # Set-up helpers
    # ------------------------------------------------------------------
    def _build_background(self) -> None:
        """Pre-render a radial gradient background to *self.bg_surf*."""
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

    # ------------------------------------------------------------------
    # Game logic
    # ------------------------------------------------------------------
    def _spawn_next_piece(self) -> None:
        self.current_piece = self.next_piece
        self.next_piece    = FallingPiece()
        self.can_hold      = True
        self.fall_speed    = (
            self.base_fall_speed + (self.lines_cleared // 5) * 0.3
        )

    def lock_piece(self, base_slot: int) -> None:
        """Commit the current piece to the wheel grid."""
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
        """Remove fully-filled layers and award points."""
        cleared = [L for L in range(LAYERS) if None not in self.wheel[L]]
        if not cleared:
            return

        self.audio.play('clear')
        self.shake = 12

        # Spawn burst particles along each cleared layer
        for L in cleared:
            r = INNER_RADIUS + L * LAYER_WIDTH + LAYER_WIDTH // 2
            for slot in range(N_SLOTS):
                color = self.wheel[L][slot]
                theta = self.wheel_angle + slot * SLOT_ANGLE
                px, py = polar_to_cartesian(r, theta)
                for _ in range(3):
                    self.particles.append(Particle(px, py, theta, color))

        # Collapse cleared layers (removed rows sink to the top)
        kept = [row for i, row in enumerate(self.wheel) if i not in cleared]
        self.wheel = kept + [[None] * N_SLOTS for _ in cleared]

        n             = len(cleared)
        self.lines_cleared += n
        self.score         += (n ** 2) * 100

    def hold_piece(self) -> None:
        """Swap the current piece into the hold slot."""
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

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update(self) -> None:
        if self.game_over:
            return

        # Wheel rotation input
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.wheel_angle = (self.wheel_angle + self.rotation_speed) % 360
        if keys[pygame.K_RIGHT]:
            self.wheel_angle = (self.wheel_angle - self.rotation_speed) % 360

        # Particle lifecycle
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]

        # Advance piece inward
        self.current_piece.r -= self.fall_speed

        # Work out the landing layer for the current piece position
        target_i      = round((90 - self.wheel_angle) / SLOT_ANGLE) % N_SLOTS
        max_req_layer = 0

        for ds, dl in self.current_piece.blocks:
            slot = (target_i + ds) % N_SLOTS
            # Find the topmost occupied layer in this column
            occ = next(
                (L for L in range(LAYERS - 1, -1, -1) if self.wheel[L][slot] is not None),
                -1,
            )
            req_layer     = occ + 1 - dl
            max_req_layer = max(max_req_layer, req_layer, -dl)

        self.target_layer = max_req_layer
        self.target_r     = INNER_RADIUS + self.target_layer * LAYER_WIDTH

        # Clamp piece to landing position and lock if it has arrived
        if self.current_piece.r <= self.target_r:
            self.current_piece.r = self.target_r
            self.lock_piece(target_i)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _draw_ui_box(
        self,
        cx: int,
        cy: int,
        title: str,
        piece_id: str | None,
        alpha_surf: pygame.Surface,
    ) -> None:
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

        # --- Grid rings and spokes ---
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

        # --- Locked pieces ---
        for L in range(LAYERS):
            for slot in range(N_SLOTS):
                color = self.wheel[L][slot]
                if color is None:
                    continue
                r_inner     = INNER_RADIUS + L * LAYER_WIDTH
                theta_center = self.wheel_angle + slot * SLOT_ANGLE
                draw_segment(
                    self.main_surf, alpha_surf, color,
                    r_inner, r_inner + LAYER_WIDTH,
                    theta_center, SLOT_ANGLE,
                )

        # --- Central hub ---
        pygame.draw.circle(self.main_surf, COLOR_HUB,        (CX, CY), INNER_RADIUS)
        pygame.draw.circle(alpha_surf,     COLOR_HUB_GLOW,   (CX, CY), INNER_RADIUS + 2, 5)
        pygame.draw.circle(self.main_surf, COLOR_HUB_BORDER, (CX, CY), INNER_RADIUS,     2)

        score_label = self.font.render("SCORE", True, COLOR_GRID)
        score_value = self.large_font.render(str(self.score), True, WHITE)
        self.main_surf.blit(score_label, score_label.get_rect(center=(CX, CY - 25)))
        self.main_surf.blit(score_value, score_value.get_rect(center=(CX, CY + 15)))

        # --- Ghost piece + active piece ---
        if not self.game_over:
            self.current_piece.draw(self.main_surf, alpha_surf, ghost_r=self.target_r)
            self.current_piece.draw(self.main_surf, alpha_surf)

        # --- Particles ---
        for p in self.particles:
            p.draw(alpha_surf)

        # --- HUD boxes ---
        self._draw_ui_box(100, 100, "HOLD", self.hold_id,              alpha_surf)
        self._draw_ui_box(700, 100, "NEXT", self.next_piece.shape_id,  alpha_surf)

        # Composite alpha layer
        self.main_surf.blit(alpha_surf, (0, 0))

        controls = self.small_font.render("F / F11: Fullscreen  |  ESC: Quit", True, COLOR_GRID)
        self.main_surf.blit(controls, (10, SCREEN_HEIGHT - 30))

        # --- Game-over overlay ---
        if self.game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            self.main_surf.blit(overlay, (0, 0))

            panel = pygame.Rect(CX - 250, CY - 100, 500, 200)
            pygame.draw.rect(self.main_surf, COLOR_HUB,    panel, 0, 15)
            pygame.draw.rect(self.main_surf, (255, 50, 50), panel, 3, 15)

            go_surf    = self.large_font.render("GAME OVER",                   True, (255, 80,  80))
            score_surf = self.font.render(f"Final Score: {self.score}",         True, WHITE)
            hint_surf  = self.font.render("Press SPACE to Restart",             True, COLOR_GRID)

            self.main_surf.blit(go_surf,    go_surf.get_rect(center=(CX, CY - 40)))
            self.main_surf.blit(score_surf, score_surf.get_rect(center=(CX, CY + 20)))
            self.main_surf.blit(hint_surf,  hint_surf.get_rect(center=(CX, CY + 60)))

        # --- Screen shake ---
        dx, dy = 0, 0
        if self.shake > 0:
            dx        = random.randint(-self.shake, self.shake)
            dy        = random.randint(-self.shake, self.shake)
            self.shake -= 1

        self.screen.blit(self.main_surf, (dx, dy))
        pygame.display.flip()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_F11, pygame.K_f):
                        pygame.display.toggle_fullscreen()
                    elif self.game_over:
                        if event.key == pygame.K_SPACE:
                            self.reset_game()
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    Game().run()
