# Recovered — Mirror rev 2 and rev 3

Recovered from git on 2026-08-06 after the design was reported lost. **Nothing was
ever lost**; both revisions were committed and are reproduced here byte-for-byte from
their commits.

| Folder | Commit | Date | What it is | What was said about it |
|---|---|---|---|---|
| `rev2/` | `bba304a` | 5 Aug | Light, cool neutrals, **every block a card** | "these are good but you made every card component which i strictly said" |
| `rev3/` | `9f14d11` | 5 Aug | **One canvas**, flat sections, hairline rows | "grey and white thats it" |

`rev3` is the strongest candidate for the design remembered as *good but black and
white*: it is the only revision that is essentially monochrome. Its palette is
`#EEF1F5` ground, `#FFFFFF` canvas, `#E9EDF3` insets, `#0F1724` ink — colour appears
only on money figures and four small badges, roughly 2% of the pixels.

## What replaced it, and why that was a mistake

`rev3` was overwritten the same day by `rev4` (`c3bfee7`), which added three large
colour fields — an ink rail, a state-tinted hero band, and brand-tinted table headers.
That change was made in response to "it has become very bland", and it went too far in
one step: rev 4 was rejected outright.

The useful reading is that **rev 3 was close and needed a small amount of colour, not a
rebuild.** Everything between rev 3 and rev 4 exists as separate commits, so any
intermediate position can be reconstructed exactly.

## Extraction note

`git checkout <commit> -- <path>` restores files present at that commit but does not
remove files added later, so a naive extraction leaked `01-layout.html` and
`02-colour.html` into folders whose commits predate them. The file lists here were
verified against `git ls-tree -r <commit>` and the extras removed. `rev3` correctly
contains no `--rail` or `state-down` tokens.
