import pygame
import sys
import random
import math

# ======================================================================
#  SETUP
# ======================================================================
pygame.init()
pygame.display.set_caption("Space Shooter — Enhanced Edition")

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
FPS = 60

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
clock  = pygame.time.Clock()
scene  = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))   # drawn to, then shaken onto screen

# ======================================================================
#  PALETTE
# ======================================================================
BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
CYAN    = (0, 225, 255)
BLUE    = (70, 130, 255)
YELLOW  = (255, 225, 70)
ORANGE  = (255, 140, 40)
RED     = (255, 60, 70)
GREEN   = (80, 255, 140)
PURPLE  = (185, 90, 255)
GREY    = (150, 155, 175)

FONT_SM   = pygame.font.SysFont("consolas,couriernew,monospace", 16, bold=True)
FONT_MED  = pygame.font.SysFont("consolas,couriernew,monospace", 26, bold=True)
FONT_BIG  = pygame.font.SysFont("consolas,couriernew,monospace", 54, bold=True)
FONT_TINY = pygame.font.SysFont("consolas,couriernew,monospace", 13, bold=True)

# ======================================================================
#  HELPERS
# ======================================================================
def make_background(w, h):
    """Vertical deep-space gradient, built once."""
    bg = pygame.Surface((w, h))
    top, bottom = (6, 8, 22), (24, 16, 50)
    for y in range(h):
        t = y / (h - 1)
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        pygame.draw.line(bg, col, (0, y), (w, y))
    return bg

BACKGROUND = make_background(SCREEN_WIDTH, SCREEN_HEIGHT)

_GLOW_CACHE = {}

def get_glow(color, w, h, layers=5, strength=0.18):
    """Cached soft radial glow used with BLEND_ADD."""
    key = (color, w, h, layers, strength)
    if key not in _GLOW_CACHE:
        surf = pygame.Surface((w, h))
        surf.fill((0, 0, 0))
        dim = tuple(max(0, min(255, int(c * strength))) for c in color)
        for i in range(layers, 0, -1):
            frac = i / layers
            sw, sh = max(1, int(w * frac)), max(1, int(h * frac))
            rect = pygame.Rect(0, 0, sw, sh)
            rect.center = (w // 2, h // 2)
            pygame.draw.ellipse(surf, dim, rect)
        _GLOW_CACHE[key] = surf
    return _GLOW_CACHE[key]


def draw_text(surf, text, font, color, x, y, center=False, glow_color=None, alpha=255):
    img = font.render(text, True, color)
    if alpha < 255:
        img = img.convert_alpha()
        img.set_alpha(alpha)
    rect = img.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    if glow_color:
        gimg = font.render(text, True, glow_color)
        if alpha < 255:
            gimg = gimg.convert_alpha()
            gimg.set_alpha(alpha)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            surf.blit(gimg, (rect.x + dx, rect.y + dy))
    surf.blit(img, rect)
    return rect


# ======================================================================
#  STARFIELD
# ======================================================================
class Star:
    def __init__(self):
        self.x = random.uniform(0, SCREEN_WIDTH)
        self.y = random.uniform(0, SCREEN_HEIGHT)
        self.speed = random.uniform(0.4, 3.2)
        self.size = random.choice((1, 1, 1, 2, 2, 3))
        self.shade = random.randint(110, 255)

    def update(self):
        self.y += self.speed
        if self.y > SCREEN_HEIGHT:
            self.y = random.uniform(-20, -2)
            self.x = random.uniform(0, SCREEN_WIDTH)

    def draw(self, surf):
        c = (self.shade, self.shade, min(255, self.shade + 25))
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), self.size)


# ======================================================================
#  PLAYER
# ======================================================================
class Player:
    def __init__(self):
        self.rect = pygame.Rect(0, 0, 44, 40)
        self.rect.centerx = SCREEN_WIDTH // 2
        self.rect.bottom = SCREEN_HEIGHT - 30
        self.speed = 6
        self.lives = 3
        self.fire_timer = 0
        self.invuln = 0
        self.flame = 0.0
        self.spread_timer = 0
        self.rapid_timer = 0

    def update(self, keys):
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if dx and dy:                       # normalise diagonals
            dx *= 0.7071
            dy *= 0.7071
        self.rect.x += dx * self.speed
        self.rect.y += dy * self.speed
        # stay inside the lower half of the screen
        self.rect.clamp_ip(pygame.Rect(0, SCREEN_HEIGHT // 2, SCREEN_WIDTH, SCREEN_HEIGHT // 2))

        if self.fire_timer > 0:   self.fire_timer -= 1
        if self.invuln > 0:       self.invuln -= 1
        if self.spread_timer > 0: self.spread_timer -= 1
        if self.rapid_timer > 0:  self.rapid_timer -= 1
        self.flame += 0.45

    def shoot(self):
        if self.fire_timer > 0:
            return []
        self.fire_timer = 6 if self.rapid_timer > 0 else 11
        cx, top = self.rect.centerx, self.rect.top + 6
        if self.spread_timer > 0:
            return [
                Bullet(cx,     top,     0.0, -12.0, CYAN),
                Bullet(cx - 8, top + 6, -3.4, -11.0, CYAN),
                Bullet(cx + 8, top + 6,  3.4, -11.0, CYAN),
            ]
        return [Bullet(cx, top, 0.0, -12.0, YELLOW)]

    def draw(self, surf):
        if self.invuln > 0 and (self.invuln // 5) % 2 == 0:
            return                                       # invulnerability blink
        r  = self.rect
        cx = r.centerx
        flick = math.sin(self.flame) * 4

        # engine flame
        pygame.draw.polygon(surf, ORANGE,
                            [(cx - 9, r.bottom - 8), (cx, r.bottom + 13 + flick), (cx + 9, r.bottom - 8)])
        pygame.draw.polygon(surf, YELLOW,
                            [(cx - 5, r.bottom - 8), (cx, r.bottom + 6 + flick * 0.6), (cx + 5, r.bottom - 8)])

        # hull
        body = [
            (cx, r.top), (cx + 12, r.top + 14), (r.right, r.bottom - 6),
            (cx + 9, r.bottom - 2), (cx - 9, r.bottom - 2),
            (r.left, r.bottom - 6), (cx - 12, r.top + 14),
        ]
        pygame.draw.polygon(surf, (28, 118, 190), body)
        pygame.draw.polygon(surf, CYAN, body, 2)

        # cockpit
        pygame.draw.circle(surf, (10, 40, 70), (cx, r.top + 18), 7)
        pygame.draw.circle(surf, (150, 245, 255), (cx, r.top + 17), 4)


# ======================================================================
#  BULLET
# ======================================================================
class Bullet:
    def __init__(self, x, y, vx, vy, color, friendly=True):
        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2(vx, vy)
        self.color = color
        self.friendly = friendly
        self.alive = True
        self.rect = pygame.Rect(0, 0, 8, 18)
        self.rect.center = (int(x), int(y))

    def update(self):
        self.pos += self.vel
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if not (-30 < self.pos.x < SCREEN_WIDTH + 30 and -30 < self.pos.y < SCREEN_HEIGHT + 30):
            self.alive = False

    def draw(self, surf):
        glow = get_glow(self.color, 26, 40)
        surf.blit(glow, (int(self.pos.x) - 13, int(self.pos.y) - 20),
                  special_flags=pygame.BLEND_ADD)
        pygame.draw.ellipse(surf, self.color, self.rect)
        pygame.draw.ellipse(surf, WHITE, self.rect.inflate(-4, -10))


# ======================================================================
#  ENEMY
# ======================================================================
class Enemy:
    def __init__(self, level):
        size = random.randint(30, 46)
        self.rect = pygame.Rect(0, 0, size, size)
        self.rect.x = random.randint(10, SCREEN_WIDTH - size - 10)
        self.rect.y = -size
        self.base_x = self.rect.centerx
        self.t = random.uniform(0, math.tau)
        self.amp = random.uniform(15, 55)
        self.speed = random.uniform(1.4, 2.4) + level * 0.18
        self.hp = 1 + level // 3
        self.max_hp = self.hp
        self.color = random.choice([RED, ORANGE, PURPLE])
        self.alive = True
        self.flash = 0
        self.fire_cd = random.randint(70, 190)

    def update(self):
        self.t += 0.03
        self.rect.y += self.speed
        self.rect.centerx = self.base_x + math.sin(self.t) * self.amp
        self.rect.centerx = max(self.rect.w // 2,
                                min(SCREEN_WIDTH - self.rect.w // 2, self.rect.centerx))
        if self.flash > 0:
            self.flash -= 1
        self.fire_cd -= 1
        if self.rect.top > SCREEN_HEIGHT + 40:
            self.alive = False

    def draw(self, surf):
        r = self.rect
        cx, cy = r.center
        w2, h2 = r.w // 2, r.h // 2
        color = WHITE if self.flash > 0 else self.color

        glow = get_glow(self.color, r.w * 2, r.h * 2)
        surf.blit(glow, (r.centerx - r.w, r.centery - r.h), special_flags=pygame.BLEND_ADD)

        pts = [
            (cx, cy - h2), (cx + w2, cy - h2 // 3), (cx + int(w2 * 0.6), cy + h2),
            (cx - int(w2 * 0.6), cy + h2), (cx - w2, cy - h2 // 3),
        ]
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.polygon(surf, WHITE, pts, 2)
        pygame.draw.circle(surf, (255, 240, 200), (cx, cy), max(3, r.w // 8))


# ======================================================================
#  PARTICLE
# ======================================================================
class Particle:
    def __init__(self, x, y, color):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(0.8, 5.5)
        self.x, self.y = x, y
        self.vx = math.cos(ang) * spd
        self.vy = math.sin(ang) * spd
        self.life = random.randint(18, 46)
        self.max_life = self.life
        self.color = color
        self.size = random.uniform(1.5, 3.5)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.95
        self.vy *= 0.95
        self.life -= 1
        return self.life > 0

    def draw(self, surf):
        t = self.life / self.max_life
        col = (int(self.color[0] * t), int(self.color[1] * t), int(self.color[2] * t))
        pygame.draw.circle(surf, col, (int(self.x), int(self.y)),
                           max(1, int(self.size * t + 0.5)))


# ======================================================================
#  POWER-UP
# ======================================================================
POWER_COLORS = {"spread": CYAN, "rapid": YELLOW, "life": GREEN}
POWER_LETTERS = {"spread": "S", "rapid": "R", "life": "+"}

class PowerUp:
    def __init__(self, x, y):
        self.kind = random.choice(["spread", "rapid", "rapid", "life"])
        self.color = POWER_COLORS[self.kind]
        self.rect = pygame.Rect(0, 0, 24, 24)
        self.rect.center = (x, y)
        self.t = 0.0
        self.alive = True

    def update(self):
        self.t += 0.1
        self.rect.y += 2
        if self.rect.top > SCREEN_HEIGHT:
            self.alive = False

    def draw(self, surf):
        r = self.rect.copy()
        r.centery += int(math.sin(self.t) * 3)

        glow = get_glow(self.color, r.w * 3, r.h * 3)
        surf.blit(glow, (r.centerx - r.w * 3 // 2, r.centery - r.h * 3 // 2),
                  special_flags=pygame.BLEND_ADD)

        pygame.draw.rect(surf, self.color, r, border_radius=6)
        pygame.draw.rect(surf, WHITE, r, 2, border_radius=6)
        img = FONT_SM.render(POWER_LETTERS[self.kind], True, BLACK)
        surf.blit(img, img.get_rect(center=r.center))


# ======================================================================
#  GAME
# ======================================================================
class Game:
    def __init__(self):
        self.stars = [Star() for _ in range(140)]
        self.best = 0
        self.state = "menu"          # menu | playing | paused | gameover
        self.reset()

    # ------------------------------------------------------------------
    def reset(self):
        self.player = Player()
        self.bullets = []
        self.enemy_bullets = []
        self.enemies = []
        self.particles = []
        self.powerups = []
        self.score = 0
        self.level = 1
        self.kills = 0
        self.spawn_timer = 50
        self.shake = 0.0
        self.banner = ""
        self.banner_timer = 0

    # ------------------------------------------------------------------
    def burst(self, x, y, color, count):
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def set_banner(self, text, frames=110):
        self.banner = text
        self.banner_timer = frames

    # ------------------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type != pygame.KEYDOWN:
                continue
            key = event.key

            if key == pygame.K_ESCAPE:
                if self.state == "playing":
                    self.state = "paused"
                elif self.state == "paused":
                    self.state = "playing"
                else:
                    return False
            elif key == pygame.K_p:
                if self.state == "playing":
                    self.state = "paused"
                elif self.state == "paused":
                    self.state = "playing"
            elif key == pygame.K_r:
                self.reset()
                self.state = "playing"
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if self.state in ("menu", "gameover"):
                    self.reset()
                    self.state = "playing"
        return True

    # ------------------------------------------------------------------
    def update(self):
        # --- background & effects run in every state ---
        for s in self.stars:
            s.update()
        self.particles = [p for p in self.particles if p.update()]

        if self.shake > 0.3:
            self.shake *= 0.88
        else:
            self.shake = 0.0
        if self.banner_timer > 0:
            self.banner_timer -= 1

        if self.state != "playing":
            return

        # --- player ---
        keys = pygame.key.get_pressed()
        self.player.update(keys)
        if keys[pygame.K_SPACE]:
            self.bullets.extend(self.player.shoot())

        # --- spawn enemies ---
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self.enemies.append(Enemy(self.level))
            base = max(20, 72 - self.level * 5)
            self.spawn_timer = base + random.randint(-8, 18)

        # --- move bullets ---
        for b in self.bullets:
            b.update()
        self.bullets = [b for b in self.bullets if b.alive]

        for b in self.enemy_bullets:
            b.update()
        self.enemy_bullets = [b for b in self.enemy_bullets if b.alive]

        # --- move enemies (+ return fire) ---
        for e in self.enemies:
            e.update()
            if e.alive and e.rect.bottom > 0 and e.fire_cd <= 0:
                e.fire_cd = random.randint(90, 200)
                self.enemy_bullets.append(
                    Bullet(e.rect.centerx, e.rect.bottom, 0, 5.5, RED, friendly=False))
        self.enemies = [e for e in self.enemies if e.alive]

        # --- player bullets vs enemies ---
        for b in self.bullets:
            if not b.alive:
                continue
            for e in self.enemies:
                if not e.alive:
                    continue
                if b.rect.colliderect(e.rect):
                    b.alive = False
                    e.hp -= 1
                    e.flash = 4
                    self.burst(b.pos.x, b.pos.y, b.color, 6)
                    if e.hp <= 0:
                        e.alive = False
                        self.kills += 1
                        self.score += 10 * e.max_hp
                        self.burst(e.rect.centerx, e.rect.centery, e.color, 24)
                        self.shake = 7
                        if random.random() < 0.15:
                            self.powerups.append(PowerUp(e.rect.centerx, e.rect.centery))
                    break
        self.enemies = [e for e in self.enemies if e.alive]

        # --- level up ---
        if self.kills >= self.level * 10:
            self.level += 1
            self.set_banner(f"LEVEL {self.level}")

        # --- power-ups ---
        for p in self.powerups:
            p.update()
            if p.rect.colliderect(self.player.rect):
                p.alive = False
                if p.kind == "spread":
                    self.player.spread_timer = 600
                elif p.kind == "rapid":
                    self.player.rapid_timer = 600
                else:
                    self.player.lives = min(5, self.player.lives + 1)
                self.burst(p.rect.centerx, p.rect.centery, p.color, 16)
                self.score += 25
        self.powerups = [p for p in self.powerups if p.alive]

        # --- enemy bullets vs player ---
        for b in self.enemy_bullets:
            if b.alive and b.rect.colliderect(self.player.rect):
                b.alive = False
                self.hit_player()
        self.enemy_bullets = [b for b in self.enemy_bullets if b.alive]

        # --- enemy bodies vs player ---
        for e in self.enemies:
            if e.rect.colliderect(self.player.rect):
                e.alive = False
                self.burst(e.rect.centerx, e.rect.centery, e.color, 20)
                self.hit_player()
        self.enemies = [e for e in self.enemies if e.alive]

    # ------------------------------------------------------------------
    def hit_player(self):
        if self.player.invuln > 0 or self.state != "playing":
            return
        self.player.lives -= 1
        self.player.invuln = 120
        self.player.spread_timer = 0
        self.player.rapid_timer = 0
        self.shake = 16
        self.burst(self.player.rect.centerx, self.player.rect.centery, CYAN, 36)
        if self.player.lives <= 0:
            self.state = "gameover"
            self.best = max(self.best, self.score)

    # ------------------------------------------------------------------
    def draw(self):
        scene.blit(BACKGROUND, (0, 0))
        for s in self.stars:
            s.draw(scene)

        for p in self.powerups:
            p.draw(scene)
        for b in self.enemy_bullets:
            b.draw(scene)
        for b in self.bullets:
            b.draw(scene)
        for e in self.enemies:
            e.draw(scene)

        if self.state != "menu" and self.player.lives > 0:
            self.player.draw(scene)

        for p in self.particles:
            p.draw(scene)

        # --- UI ---
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "playing":
            self.draw_hud()
            self.draw_banner()
        elif self.state == "paused":
            self.draw_hud()
            self.draw_overlay("PAUSED", "Press  P  or  ESC  to resume")
        elif self.state == "gameover":
            self.draw_hud()
            self.draw_overlay("GAME OVER",
                              f"Score {self.score}    Best {self.best}    —    ENTER to play again")

    # ------------------------------------------------------------------
    def draw_hud(self):
        draw_text(scene, f"SCORE {self.score:05d}", FONT_MED, WHITE, 20, 14)
        draw_text(scene, f"LEVEL {self.level}", FONT_SM, CYAN, 22, 48)

        # lives
        for i in range(self.player.lives):
            cx = SCREEN_WIDTH - 32 - i * 34
            pts = [(cx, 18), (cx - 12, 42), (cx + 12, 42)]
            pygame.draw.polygon(scene, (0, 90, 130), pts)
            pygame.draw.polygon(scene, CYAN, pts, 2)

        # power-up timers
        y = 62
        for timer, color, label in ((self.player.spread_timer, CYAN, "SPREAD"),
                                    (self.player.rapid_timer, YELLOW, "RAPID")):
            if timer > 0:
                w = int(110 * timer / 600)
                draw_text(scene, label, FONT_TINY, color, SCREEN_WIDTH - 190, y - 2)
                pygame.draw.rect(scene, (45, 45, 70), (SCREEN_WIDTH - 140, y, 110, 10),
                                 border_radius=5)
                pygame.draw.rect(scene, color, (SCREEN_WIDTH - 140, y, max(2, w), 10),
                                 border_radius=5)
                y += 22

    def draw_banner(self):
        if self.banner_timer > 0:
            alpha = min(255, self.banner_timer * 4)
            draw_text(scene, self.banner, FONT_BIG, WHITE,
                      SCREEN_WIDTH // 2, 150, center=True, glow_color=CYAN, alpha=alpha)

    def draw_menu(self):
        pulse = 155 + int(100 * math.sin(pygame.time.get_ticks() * 0.005))
        draw_text(scene, "SPACE  SHOOTER", FONT_BIG, WHITE,
                  SCREEN_WIDTH // 2, 165, center=True, glow_color=CYAN)
        draw_text(scene, "E N H A N C E D   E D I T I O N", FONT_SM, CYAN,
                  SCREEN_WIDTH // 2, 212, center=True)

        lines = [
            ("MOVE",       "ARROW KEYS  /  W A S D"),
            ("FIRE",       "HOLD  SPACE"),
            ("PAUSE",      "P  or  ESC"),
            ("POWER-UPS",  "S = spread   R = rapid fire   + = extra life"),
        ]
        y = 300
        for label, desc in lines:
            draw_text(scene, label, FONT_SM, YELLOW, SCREEN_WIDTH // 2 - 190, y)
            draw_text(scene, desc, FONT_SM, GREY, SCREEN_WIDTH // 2 - 70, y)
            y += 32

        draw_text(scene, "PRESS  ENTER  TO  START", FONT_MED, (pulse, pulse, pulse),
                  SCREEN_WIDTH // 2, 490, center=True)
        draw_text(scene, "ESC to quit", FONT_TINY, GREY,
                  SCREEN_WIDTH // 2, 545, center=True)

    def draw_overlay(self, title, subtitle):
        veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 155))
        scene.blit(veil, (0, 0))
        draw_text(scene, title, FONT_BIG, WHITE,
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 45, center=True, glow_color=CYAN)
        draw_text(scene, subtitle, FONT_SM, GREY,
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 35, center=True)

    # ------------------------------------------------------------------
    def present(self):
        screen.fill(BLACK)
        if self.shake > 0.5:
            ox = random.uniform(-self.shake, self.shake)
            oy = random.uniform(-self.shake, self.shake)
        else:
            ox = oy = 0
        screen.blit(scene, (int(ox), int(oy)))
        pygame.display.flip()


# ======================================================================
#  MAIN LOOP
# ======================================================================
def main():
    game = Game()
    running = True
    while running:
        running = game.handle_events()
        game.update()
        game.draw()
        game.present()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()