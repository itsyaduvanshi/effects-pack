---
name: effects-pack
description: Adds one of 42 face-tracked effects to a talking-head video, such as orbiting reels, a word behind the head, spotlight, LED sign, glass widgets, tier list, iPhone toggles, magazine cover or a split headline. Use when the user types /effects-pack, names one of these effects, or asks for an effect, zoom, grade, sticker or animation on their video.
---

# Effects pack

Keep replies short and do the work yourself; the user should never need to run a command.
Paths are relative to this folder. Use absolute paths in commands. On Windows the Python is `.venv\Scripts\python.exe`.

## Setup (first run only)
`bash scripts/setup.sh` ends with one of:
- `READY` - continue.
- `NEED_FFMPEG` - install it (`brew install ffmpeg` on Mac, `winget install ffmpeg` on Windows), then run setup again.
- `NEED_PYTHON` - install Python 3.12 (or `uv`), then run setup again.

## Steps
1. **Video**: the file they dropped in or the path they gave. Vertical works best.
2. **Effect**: match their words to the table. If you are unsure, show them the table.
3. **Timing**: if they mention a word ("when I say X"), run `.venv/bin/python scripts/words.py <video> --find "X"`. With no timing, ask once or use the whole clip. Effects look best in 1.5 to 4 second windows.
4. **Plan**: write `<video-name>.effects.json` next to the video:
   ```json
   {"effects": [
     {"fx": "orbit", "start": 2.0, "end": 5.0},
     {"fx": "backdrop-word", "start": 6.1, "end": 8.0, "text": "SHIP IT"}
   ]}
   ```
   Every key other than `fx`, `start` and `end` is an option.
5. **Check**: `.venv/bin/python scripts/fx.py --plan <plan> <video> <dir>/check.png --still 3.5,7.0`, using the middle of each window. Open the PNGs and look. If text covers the face, gets cut off or can't be read, fix the plan and check again.
6. **Render**: `.venv/bin/python scripts/fx.py --plan <plan> <video> <video-name>_fx.mp4` (1080p, original audio kept; add `--width 2160` for 4K).
7. Tell them where the file is, and remind them to watch it before posting.

A single effect works without a plan: `fx.py orbit in.mov out.mp4 --start 2 --end 5 --text "..." --opt speed=0.5`.

## Effects
| fx | What you see | Options |
|---|---|---|
| `noise` | Reel cards pop up and pile behind the head | `images`, `size`, `every` |
| `lineup` | Numbered tiles fan out in an arc over the head | `text` (labels with `\|`) |
| `orbit` | Reels circle the head, passing behind it at the top | `images`, `count`, `speed`, `size` |
| `backdrop-word` | A huge word springs down behind the head | `text`, `color`, `font` (`bold`/`serif`) |
| `shortcut-rain` | Keycaps tumble down behind you | `text` (keys with `\|`), `count` |
| `countdown-flip` | Flip-clock 3, 2, 1 above the head | `from` |
| `carousel-spin` | Reels on a 3D carousel around you, slowing to a stop | `images`, `count`, `size`, `turns` |
| `phone-fan` | Phones fan out from behind you, headline on top | `images`, `text` (2 lines with `\|`) |
| `headline-wall` | Headline cards stack behind you, then a total pops | `text` (`title::source\|...`), `total`, `label` |
| `match-cut` | Newspaper pages cut fast, one word stays boxed in place | `text`, `color`, `every` |
| `led-sign` | Lights go down, a dot-matrix sign types out behind you | `text` (lines with `\|`), `color` |
| `the-bill` | A receipt prints down from the top behind the head | `text` (lines with `\|`) |
| `profile-wall` | A reels grid scrolls behind you, counter ticks up | `images`, `count` (e.g. `10K`), `label` |
| `locked-on` | Corner brackets snap onto the face, camera follows | `zoom`, `text`, `color` |
| `lean-in` | Quick punch-in for one word | `zoom` (max 2), `speed` |
| `slow-push` | Slow push-in while the room blurs away | `zoom`, `blur` |
| `spotlight` | Room goes dark, you stay lit; optional glowing word | `text`, `color`, `push`, `look=sparkle` |
| `glitter-spotlight` | Spotlight with gold rays, shine and sparkles | same as spotlight |
| `moody` | Colour grade | `grade` (`moody`/`bw`/`warm`/`cool`/`pop`/`soft`/`film-red`) |
| `swipe` | Before/after wipe across the frame | `grade` |
| `rabbit-hole` | The room tunnels into itself behind you | `ratio`, `speed`, `spin` |
| `dot-reveal` | Frame builds from glowing dots, then snaps sharp | `color`, `cell` |
| `pause-point` | Freeze, flash and a marker arrow pointing at you | `text`, `color`, `label_x` |
| `uninstall` | Uninstall dialog fails while the frame glitches apart | `text` |
| `headline-box` | Punch-in with a two-line headline, second line boxed | `text` (2 lines with `\|`), `zoom` |
| `cover-star` | Magazine cover: masthead behind the head, cover lines | `text`, `lines`, `issue`, `color`, `accent`, `look=editorial`, `right` |
| `scribble` | Marker halo, stars and an arrow draw themselves | `text`, `color` |
| `red-collage` | B&W you, giant red word behind, three lines slam in | `text`, `lines`, `tag` |
| `split-headline` | Headline card pushes you to the bottom half | `text` (lines), `hl` (word to highlight), `pill` |
| `pastel-word` | Lavender room, big serif word, profile card gets a follow | `text`, `name`, `handle` |
| `check-pills` | Grid-paper room, pinned reels, a cursor ticks blue pills | `text` (pills with `\|`), `ticks`, `images` |
| `timeline` | Red film look, REC timecode and an editing timeline | `text`, `sub`, `tc` |
| `broll-split` | B-roll on top with a price tag, you below | `images`, `text` |
| `todo` | Checklist beside the head ticks off | `text`, `ticks` (seconds), `title` |
| `comment-box` | Comment types itself and posts | `text` |
| `tap` | Follow button gets tapped and flips to Following | `at` (second), `x`, `y`, `color` |
| `reject-stamp` | Red stamp slams down with a shake | `text`, `color`, `angle`, `y` |
| `checklist` | Claude-style task list under the chin, each step spins then ticks | `text` (`step::note\|...`), `title`, `ticks` |
| `apple-toggles` | iOS switches flip on one by one | `text`, `ticks`, `color`, `pos=below`, `zoom`, `overlap` |
| `liquid-glass-graph` | Glass card, climbing graph and counting number | `text`, `from`, `to`, `color`, `look=bento` (`donut`, `kpi`, `bars`) |
| `glass-widgets` | Frosted widgets float around the head | `text`, `name`, `handle`, `look=simple` |
| `tier-list` | Tier list drops in; the item flies to S | `title`, `item`, `others` |
| `reel-frame` | Video shrinks into a reel card with Instagram UI | `text` (handle) |

`images` takes a folder of screenshots or clips. Without one, the reel cards use frames from the user's own video.
Ask for real numbers when an effect shows a count or a graph.

## Rules
- Never put graphics over the face. If a check frame shows that, move or shorten them.
- Camera effects (`locked-on`, `lean-in`, `slow-push`, `spotlight`) run first when windows overlap.
- Visuals only. No sound or captions.
