# Python-Neon-Tetris

Neon Tetris is a fast, neon‑glow Tetris clone built with Pygame featuring soft bloom, long‑lived particle embers, and explosive line clears.

# Features
- Neon glow and bloom with multi‑layer radial gradients for soft lighting.
- Wisp and explosion particles with pooled particle system for performance.
- Dynamic difficulty: drop speed increases every 600 points.

  <img width="789" height="597" alt="Screenshot" src="https://github.com/user-attachments/assets/4e56a559-fd47-43c0-a992-26b324ad2eac" />


## Requirements: 

Python 3.8+
pygame

## Install

`pip install pygame`

## Run
`Python tetris.py`
OR
`py tetris.py`

## Controls
- Left / Right arrows — move piece.

- Up arrow — rotate.

- Down arrow — soft drop (creates ember burst).

- Close window or Esc — quit.

## Installation Notes
Tweak visuals: adjust GLOW_LAYERS, BLOOM_SCALE, and MAX_PARTICLES at the top of the script to balance quality vs performance.
